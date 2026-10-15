"""Operational primitives for the API's durable SQLite stores (issue #750).

Three bounded, stdlib-only pieces that ``docs/specifications/API_STORAGE_PROFILES_V0_1.md``
required but that did not exist as code:

* a **forward-only, checksummed migration runner** with a dry-run plan and an
  all-or-nothing apply (one ``BEGIN IMMEDIATE`` transaction, so a crash at any
  point leaves the previous schema intact);
* a **retention evaluator** that classifies records as ``keep`` or ``expire``
  and can never expire evidence a Human Decision Record refers to. It is a pure
  planner: it deletes nothing;
* a **digest-bound backup, verify and restore** procedure for one SQLite file.

Authority: none of this grants execution, acceptance, repository-write or merge
authority. A digest detects corruption and accidental substitution; it does not
authenticate a writer who can rewrite both the file and its manifest. Nothing
here implements a network-profile adapter, and no credential is read or stored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from urllib.parse import quote
from typing import Any, Callable, Iterable, Mapping, Sequence

MIGRATION_LEDGER_TABLE = "idkmesh_schema_migrations"
BACKUP_MANIFEST_KIND = "idkmesh-sqlite-backup-manifest"
BACKUP_MANIFEST_VERSION = "0.1"
MANIFEST_SUFFIX = ".manifest.json"
_CHUNK = 1 << 20
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class StorageOpsError(RuntimeError):
    """Controlled storage-operations failure carrying a stable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------


def sql_checksum(sql: str) -> str:
    """Return ``sha256:<hex>`` of the migration text with line endings normalised."""

    normalised = sql.replace("\r\n", "\n").replace("\r", "\n").strip()
    return "sha256:" + hashlib.sha256(normalised.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MigrationStep:
    """One forward-only schema step. ``version`` is the schema version it reaches."""

    version: int
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return sql_checksum(self.sql)


@dataclass(frozen=True)
class MigrationPlan:
    """What :func:`plan_migrations` found; ``pending`` is what apply would run."""

    current_version: int
    target_version: int
    pending: tuple[MigrationStep, ...]
    adopt: tuple[MigrationStep, ...] = field(default=())

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_version": self.current_version,
            "target_version": self.target_version,
            "pending": [
                {"version": s.version, "name": s.name, "checksum": s.checksum}
                for s in self.pending
            ],
            "adopt": [
                {"version": s.version, "name": s.name, "checksum": s.checksum}
                for s in self.adopt
            ],
        }


MAX_MIGRATION_FILES = 1000
MAX_MIGRATION_BYTES = 1 << 20
_MIGRATION_FILE = re.compile(r"^([0-9]{4})_([a-z0-9][a-z0-9_]*)\.sql$")


def load_migration_steps(directory: str | Path) -> tuple[MigrationStep, ...]:
    """Read ``NNNN_name.sql`` files from a directory as ordered migration steps.

    Fail closed: every ``*.sql`` entry must be a regular, non-symlink UTF-8 file
    named ``NNNN_name.sql`` (lower-case ``name``), and the numbers must run
    contiguously from ``0001``. Other file types are ignored. Only reads.
    """

    root = Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise StorageOpsError("invalid_migrations", "migrations path is not a directory")
    try:
        entries = sorted(e for e in root.iterdir() if e.name.endswith(".sql"))
    except OSError as exc:
        raise StorageOpsError(
            "invalid_migrations", f"cannot list migrations: {exc.strerror}"
        ) from exc
    if len(entries) > MAX_MIGRATION_FILES:
        raise StorageOpsError("invalid_migrations", "too many migration files")
    steps: list[MigrationStep] = []
    for entry in entries:
        match = _MIGRATION_FILE.match(entry.name)
        if match is None:
            raise StorageOpsError(
                "invalid_migrations", f"{entry.name!r} is not named NNNN_name.sql"
            )
        if entry.is_symlink() or not entry.is_file():
            raise StorageOpsError(
                "invalid_migrations", f"{entry.name!r} is not a regular file"
            )
        try:
            if entry.stat().st_size > MAX_MIGRATION_BYTES:
                raise StorageOpsError("invalid_migrations", f"{entry.name!r} is too large")
            text = entry.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise StorageOpsError(
                "invalid_migrations", f"cannot read {entry.name!r} as UTF-8 text"
            ) from exc
        steps.append(MigrationStep(int(match.group(1)), match.group(2), text))
    return _validate_steps(steps)


def _validate_steps(steps: Sequence[MigrationStep]) -> tuple[MigrationStep, ...]:
    if not steps:
        raise StorageOpsError("invalid_migrations", "at least one migration step is required")
    ordered = tuple(steps)
    for index, step in enumerate(ordered, start=1):
        if not isinstance(step, MigrationStep):
            raise StorageOpsError("invalid_migrations", "steps must be MigrationStep values")
        if type(step.version) is not int or step.version != index:
            raise StorageOpsError(
                "invalid_migrations",
                f"step versions must be contiguous from 1; step {index} has version "
                f"{step.version!r}",
            )
        if not isinstance(step.name, str) or not step.name.strip():
            raise StorageOpsError("invalid_migrations", f"step {index} needs a name")
        if not isinstance(step.sql, str) or not step.sql.strip():
            raise StorageOpsError("invalid_migrations", f"step {index} has empty SQL")
    return ordered


def _split_statements(sql: str) -> list[str]:
    """Split on complete statements without ``executescript`` (which commits)."""

    statements: list[str] = []
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statements.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        raise StorageOpsError("invalid_migrations", "migration SQL ends mid-statement")
    return [s for s in statements if s]


_FORBIDDEN_IN_STEP = re.compile(
    r"^\s*(BEGIN|COMMIT|END|ROLLBACK|SAVEPOINT|RELEASE|PRAGMA\s+user_version|VACUUM|ATTACH|DETACH)\b",
    re.IGNORECASE,
)


def _ro_uri(path: Path) -> str:
    return f"file:{quote(str(path.resolve()))}?mode=ro"


def _connect(path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    try:
        if read_only:
            conn = sqlite3.connect(_ro_uri(path), uri=True, timeout=5.0)
        else:
            conn = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    except sqlite3.Error as exc:
        raise StorageOpsError("store_error", f"cannot open database: {exc}") from exc
    conn.row_factory = sqlite3.Row
    return conn


def _ledger_rows(conn: sqlite3.Connection) -> dict[int, tuple[str, str]]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (MIGRATION_LEDGER_TABLE,),
    ).fetchone()
    if exists is None:
        return {}
    rows = conn.execute(
        f"SELECT version, name, checksum FROM {MIGRATION_LEDGER_TABLE} ORDER BY version"
    ).fetchall()
    return {int(r["version"]): (str(r["name"]), str(r["checksum"])) for r in rows}


def _plan(
    conn: sqlite3.Connection, steps: tuple[MigrationStep, ...], adopt_existing: bool
) -> MigrationPlan:
    current = int(conn.execute("PRAGMA user_version").fetchone()[0])
    target = steps[-1].version
    if current > target:
        raise StorageOpsError(
            "schema_newer_than_code",
            f"database schema version {current} is newer than supported {target}; "
            "downgrade is refused",
        )
    ledger = _ledger_rows(conn)
    if not ledger:
        if current == 0:
            return MigrationPlan(0, target, steps)
        if not adopt_existing:
            raise StorageOpsError(
                "unmanaged_schema",
                f"database is at schema version {current} but has no migration ledger; "
                "pass adopt_existing=True to record the already-applied steps",
            )
        return MigrationPlan(current, target, steps[current:], adopt=steps[:current])
    if sorted(ledger) != list(range(1, len(ledger) + 1)):
        raise StorageOpsError("ledger_gap", "migration ledger versions are not contiguous")
    if max(ledger) != current:
        raise StorageOpsError(
            "ledger_version_mismatch",
            f"user_version {current} disagrees with ledger version {max(ledger)}",
        )
    for version, (name, checksum) in ledger.items():
        step = steps[version - 1]
        if checksum != step.checksum or name != step.name:
            raise StorageOpsError(
                "checksum_mismatch",
                f"applied migration {version} differs from the shipped definition "
                "(edited after it was applied)",
            )
    return MigrationPlan(current, target, steps[current:])


def plan_migrations(
    path: str | Path,
    steps: Sequence[MigrationStep],
    *,
    adopt_existing: bool = False,
) -> MigrationPlan:
    """Dry run: report what apply would do. Opens the file read-only and writes nothing."""

    ordered = _validate_steps(steps)
    db = Path(path)
    if not db.is_file():
        return MigrationPlan(0, ordered[-1].version, ordered)
    conn = _connect(db, read_only=True)
    try:
        return _plan(conn, ordered, adopt_existing)
    except sqlite3.Error as exc:
        raise StorageOpsError("store_error", f"database error: {exc}") from exc
    finally:
        conn.close()


def apply_migrations(
    path: str | Path,
    steps: Sequence[MigrationStep],
    *,
    adopt_existing: bool = False,
    after_step: Callable[[MigrationStep], None] | None = None,
) -> MigrationPlan:
    """Apply every pending step in a single atomic transaction and return the plan applied.

    ``user_version``, the ledger rows and the DDL commit together or not at all,
    so a crash or error in any step leaves the database exactly as it was.
    ``after_step`` is a test seam called inside the transaction after each step.
    Already-applied steps are verified against their checksums first; an edited
    historical step, a ledger gap or a newer database fails closed.
    """

    ordered = _validate_steps(steps)
    db = Path(path)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            plan = _plan(conn, ordered, adopt_existing)
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {MIGRATION_LEDGER_TABLE} (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    adopted INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            for step in plan.adopt:
                conn.execute(
                    f"INSERT INTO {MIGRATION_LEDGER_TABLE}(version, name, checksum, adopted) "
                    "VALUES (?, ?, ?, 1)",
                    (step.version, step.name, step.checksum),
                )
            for step in plan.pending:
                for statement in _split_statements(step.sql):
                    if _FORBIDDEN_IN_STEP.match(statement):
                        raise StorageOpsError(
                            "invalid_migrations",
                            f"step {step.version} may not contain transaction or "
                            "version control statements",
                        )
                    conn.execute(statement)
                conn.execute(
                    f"INSERT INTO {MIGRATION_LEDGER_TABLE}(version, name, checksum) "
                    "VALUES (?, ?, ?)",
                    (step.version, step.name, step.checksum),
                )
                conn.execute(f"PRAGMA user_version = {int(step.version)}")
                if after_step is not None:
                    after_step(step)
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    except sqlite3.Error as exc:
        raise StorageOpsError("migration_failed", f"migration rolled back: {exc}") from exc
    finally:
        conn.close()
    return plan


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

RETAIN_FOREVER_CLASSES = frozenset({"essential", "configuration"})
EXPIRABLE_CLASSES = frozenset({"expendable", "ephemeral"})
KNOWN_CLASSES = RETAIN_FOREVER_CLASSES | EXPIRABLE_CLASSES


@dataclass(frozen=True)
class RetentionRecord:
    """A record as the evaluator sees it. Identity fields link it to decisions."""

    record_id: str
    record_class: str
    created_at: str
    run_id: str | None = None
    evidence_digest: str | None = None


@dataclass(frozen=True)
class DecisionReferences:
    """Run IDs and evidence digests that at least one Human Decision refers to."""

    run_ids: frozenset[str] = frozenset()
    evidence_digests: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RetentionDecision:
    record_id: str
    action: str  # "keep" | "expire"
    reason: str


def _parse_time(value: str, what: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise StorageOpsError("invalid_timestamp", f"{what} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StorageOpsError("invalid_timestamp", f"{what} is not ISO-8601") from exc
    if parsed.tzinfo is None:
        raise StorageOpsError("invalid_timestamp", f"{what} must carry a timezone")
    return parsed.astimezone(timezone.utc)


def validate_retention_policy(policy: Mapping[str, int | None]) -> dict[str, int | None]:
    """Return a checked ``class -> max age in days`` mapping.

    Essential and configuration records can never be given an age limit.
    Expirable classes must be given a positive integer limit explicitly, so a
    missing entry is an error rather than a silent "keep forever" or "delete".
    """

    if not isinstance(policy, Mapping):
        raise StorageOpsError("invalid_policy", "policy must be a mapping")
    unknown = set(policy) - KNOWN_CLASSES
    if unknown:
        raise StorageOpsError("invalid_policy", f"unknown record classes: {sorted(unknown)}")
    checked: dict[str, int | None] = {}
    for record_class in sorted(KNOWN_CLASSES):
        if record_class in RETAIN_FOREVER_CLASSES:
            if policy.get(record_class) is not None:
                raise StorageOpsError(
                    "invalid_policy", f"class {record_class!r} is retained forever; no age limit"
                )
            checked[record_class] = None
            continue
        days = policy.get(record_class)
        if type(days) is not int or days < 1:
            raise StorageOpsError(
                "invalid_policy", f"class {record_class!r} needs a positive integer day limit"
            )
        checked[record_class] = days
    return checked


def evaluate_retention(
    records: Iterable[RetentionRecord],
    policy: Mapping[str, int | None],
    *,
    now: str,
    references: DecisionReferences = DecisionReferences(),
) -> list[RetentionDecision]:
    """Plan retention. Pure: it returns decisions and deletes nothing.

    A record is expired only when its class is expirable, it is older than the
    class limit, and no Human Decision refers to its run or evidence digest.
    Every other outcome is ``keep`` with a reason. An unknown class, a bad
    timestamp or a duplicate record ID raises: the evaluator never guesses.
    """

    limits = validate_retention_policy(policy)
    now_dt = _parse_time(now, "now")
    seen: set[str] = set()
    decisions: list[RetentionDecision] = []
    for record in records:
        if not isinstance(record, RetentionRecord) or not record.record_id:
            raise StorageOpsError("invalid_record", "records must be RetentionRecord values")
        if record.record_id in seen:
            raise StorageOpsError("invalid_record", f"duplicate record id {record.record_id!r}")
        seen.add(record.record_id)
        if record.record_class not in KNOWN_CLASSES:
            raise StorageOpsError(
                "invalid_record", f"unknown class {record.record_class!r} for {record.record_id!r}"
            )
        created = _parse_time(record.created_at, f"created_at of {record.record_id!r}")
        if (
            record.run_id in references.run_ids
            or record.evidence_digest in references.evidence_digests
        ):
            decisions.append(
                RetentionDecision(record.record_id, "keep", "referenced_by_human_decision")
            )
        elif record.record_class in RETAIN_FOREVER_CLASSES:
            decisions.append(RetentionDecision(record.record_id, "keep", "retained_class"))
        elif created > now_dt:
            decisions.append(RetentionDecision(record.record_id, "keep", "created_in_future"))
        elif now_dt - created <= timedelta(days=limits[record.record_class] or 0):
            decisions.append(RetentionDecision(record.record_id, "keep", "within_retention"))
        else:
            decisions.append(RetentionDecision(record.record_id, "expire", "past_retention"))
    return decisions


def decision_references_from_store(path: str | Path) -> DecisionReferences:
    """Read run IDs and evidence digests from a ``HumanDecisionStore`` file, read-only.

    A missing file means no decisions exist. A file that exists but cannot be
    read fails closed: the caller must not treat "unreadable" as "unreferenced".
    """

    db = Path(path)
    if not db.is_file():
        return DecisionReferences()
    conn = _connect(db, read_only=True)
    try:
        rows = conn.execute(
            "SELECT run_id, evidence_report_digest FROM human_decisions"
        ).fetchall()
    except sqlite3.Error as exc:
        raise StorageOpsError("store_error", f"cannot read decisions: {exc}") from exc
    finally:
        conn.close()
    return DecisionReferences(
        run_ids=frozenset(str(r["run_id"]) for r in rows),
        evidence_digests=frozenset(str(r["evidence_report_digest"]) for r in rows),
    )


# ---------------------------------------------------------------------------
# Backup, verify, restore
# ---------------------------------------------------------------------------


def _file_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return "sha256:" + digest.hexdigest(), size


def _manifest_digest(body: Mapping[str, Any]) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _describe(path: Path) -> dict[str, Any]:
    """Facts about a SQLite file: integrity, schema version and per-table row counts."""

    conn = _connect(path, read_only=True)
    try:
        check = conn.execute("PRAGMA integrity_check").fetchone()
        if check is None or check[0] != "ok":
            raise StorageOpsError("backup_corrupt", "SQLite integrity check failed")
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        names = [
            str(r[0])
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts: dict[str, int] = {}
        for name in names:
            if not _IDENT.match(name):
                raise StorageOpsError("backup_corrupt", "unexpected table name in database")
            counts[name] = int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
    except sqlite3.Error as exc:
        raise StorageOpsError("backup_corrupt", f"cannot read database: {exc}") from exc
    finally:
        conn.close()
    return {"schema_version": version, "row_counts": counts}


def manifest_path_for(backup: str | Path) -> Path:
    backup_path = Path(backup)
    return backup_path.with_name(backup_path.name + MANIFEST_SUFFIX)


def _refuse_symlink(path: Path, what: str) -> None:
    if path.is_symlink():
        raise StorageOpsError("unsafe_path", f"{what} must not be a symlink")


def _check_backup_paths(
    source: str | Path, destination: str | Path
) -> tuple[Path, Path, Path]:
    """Validate a backup's paths without writing; return ``(source, backup, manifest)``."""

    src = Path(source)
    dest = Path(destination)
    if not src.is_file():
        raise StorageOpsError("source_missing", "source database does not exist")
    _refuse_symlink(dest, "backup destination")
    manifest = manifest_path_for(dest)
    _refuse_symlink(manifest, "manifest path")
    if dest.exists() or manifest.exists():
        raise StorageOpsError("destination_exists", "backup or manifest already exists")
    if not dest.parent.is_dir():
        raise StorageOpsError("unsafe_path", "backup parent directory must already exist")
    if dest.resolve(strict=False) == src.resolve(strict=False):
        raise StorageOpsError("unsafe_path", "cannot back up a database onto itself")
    return src, dest, manifest


def plan_backup(source: str | Path, destination: str | Path) -> dict[str, str]:
    """Dry run of :func:`create_backup`: run every path check, write nothing."""

    src, dest, manifest = _check_backup_paths(source, destination)
    return {"source": str(src), "backup": str(dest), "manifest": str(manifest)}


def create_backup(source: str | Path, destination: str | Path) -> Path:
    """Take an online-consistent snapshot and write a digest manifest beside it.

    Refuses to overwrite an existing backup or manifest. The snapshot is built
    under a temporary name and only renamed into place after it passes an
    integrity check, so an interrupted backup never looks complete. Returns the
    manifest path.
    """

    src, dest, manifest = _check_backup_paths(source, destination)

    partial = dest.with_name(dest.name + ".partial")
    partial.unlink(missing_ok=True)
    try:
        source_conn = sqlite3.connect(_ro_uri(src), uri=True, timeout=5.0)
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            os.close(os.open(partial, flags, 0o600))
            target_conn = sqlite3.connect(partial)
            try:
                source_conn.backup(target_conn)
            finally:
                target_conn.close()
        finally:
            source_conn.close()
        facts = _describe(partial)
        digest, size = _file_digest(partial)
        _fsync_file(partial)
        body = {
            "kind": BACKUP_MANIFEST_KIND,
            "schema_version": BACKUP_MANIFEST_VERSION,
            "backup_file": dest.name,
            "backup_digest": digest,
            "backup_size": size,
            "database_schema_version": facts["schema_version"],
            "row_counts": facts["row_counts"],
        }
        document = dict(body, manifest_digest=_manifest_digest(body))
        os.replace(partial, dest)
        _write_new(manifest, json.dumps(document, indent=2, sort_keys=True) + "\n")
    except (sqlite3.Error, OSError) as exc:
        partial.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        manifest.unlink(missing_ok=True)
        raise StorageOpsError("backup_failed", f"backup failed: {exc}") from exc
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return manifest


def _fsync_file(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_new(path: Path, text: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())


@dataclass(frozen=True)
class BackupReport:
    backup_digest: str
    database_schema_version: int
    row_counts: dict[str, int]


def verify_backup(
    backup: str | Path,
    *,
    manifest: str | Path | None = None,
    max_supported_schema_version: int | None = None,
) -> BackupReport:
    """Check a backup against its manifest. Reads only; raises on any disagreement."""

    backup_path = Path(backup)
    manifest_file = Path(manifest) if manifest is not None else manifest_path_for(backup_path)
    _refuse_symlink(backup_path, "backup")
    _refuse_symlink(manifest_file, "manifest")
    if not backup_path.is_file():
        raise StorageOpsError("backup_missing", "backup file does not exist")
    if not manifest_file.is_file():
        raise StorageOpsError("manifest_missing", "backup manifest does not exist")
    try:
        document = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StorageOpsError("manifest_invalid", "manifest is not readable JSON") from exc
    expected_keys = {
        "kind", "schema_version", "backup_file", "backup_digest", "backup_size",
        "database_schema_version", "row_counts", "manifest_digest",
    }
    if not isinstance(document, dict) or set(document) != expected_keys:
        raise StorageOpsError("manifest_invalid", "manifest fields are not exactly as specified")
    if (
        document["kind"] != BACKUP_MANIFEST_KIND
        or document["schema_version"] != BACKUP_MANIFEST_VERSION
    ):
        raise StorageOpsError("manifest_invalid", "unsupported manifest kind or version")
    body = {k: v for k, v in document.items() if k != "manifest_digest"}
    if document["manifest_digest"] != _manifest_digest(body):
        raise StorageOpsError("manifest_digest_mismatch", "manifest was altered")
    if not isinstance(document["backup_digest"], str) or not _SHA256.match(
        document["backup_digest"]
    ):
        raise StorageOpsError("manifest_invalid", "backup_digest is malformed")
    if document["backup_file"] != backup_path.name:
        raise StorageOpsError("manifest_invalid", "manifest names a different backup file")
    digest, size = _file_digest(backup_path)
    if digest != document["backup_digest"] or size != document["backup_size"]:
        raise StorageOpsError("backup_digest_mismatch", "backup content differs from manifest")
    facts = _describe(backup_path)
    if (
        facts["schema_version"] != document["database_schema_version"]
        or facts["row_counts"] != document["row_counts"]
    ):
        raise StorageOpsError("backup_corrupt", "backup contents differ from manifest facts")
    if (
        max_supported_schema_version is not None
        and facts["schema_version"] > max_supported_schema_version
    ):
        raise StorageOpsError(
            "schema_newer_than_code",
            f"backup schema version {facts['schema_version']} is newer than supported "
            f"{max_supported_schema_version}",
        )
    return BackupReport(digest, facts["schema_version"], facts["row_counts"])


def _check_restore_target(target_path: Path, replace: bool) -> Path:
    """Validate a restore target without writing; return the staging path."""

    _refuse_symlink(target_path, "restore target")
    if target_path.exists() and not replace:
        raise StorageOpsError("target_exists", "restore target exists; pass replace=True")
    if not target_path.parent.is_dir():
        raise StorageOpsError("unsafe_path", "restore target directory must already exist")
    staging = target_path.with_name(target_path.name + ".restoring")
    _refuse_symlink(staging, "staging path")
    return staging


def plan_restore(
    backup: str | Path,
    target: str | Path,
    *,
    manifest: str | Path | None = None,
    replace: bool = False,
    max_supported_schema_version: int | None = None,
) -> BackupReport:
    """Dry run of :func:`restore_backup`: verify the backup and the target, write nothing."""

    report = verify_backup(
        backup,
        manifest=manifest,
        max_supported_schema_version=max_supported_schema_version,
    )
    _check_restore_target(Path(target), replace)
    return report


def restore_backup(
    backup: str | Path,
    target: str | Path,
    *,
    manifest: str | Path | None = None,
    replace: bool = False,
    max_supported_schema_version: int | None = None,
) -> BackupReport:
    """Verify, then restore a backup to ``target`` atomically.

    The backup is verified first; it is copied beside the target under a
    temporary name, re-verified by digest, fsynced, and moved into place with
    ``os.replace``, so a crash leaves either the old target or the full new one.
    An existing target needs ``replace=True``; stale ``-wal``/``-shm`` files of
    the replaced database are removed so they cannot be replayed onto the
    restored file.
    """

    backup_path = Path(backup)
    target_path = Path(target)
    report = verify_backup(
        backup_path,
        manifest=manifest,
        max_supported_schema_version=max_supported_schema_version,
    )
    staging = _check_restore_target(target_path, replace)
    staging.unlink(missing_ok=True)
    try:
        shutil.copyfile(backup_path, staging)
        os.chmod(staging, 0o600)
        digest, _ = _file_digest(staging)
        if digest != report.backup_digest:
            raise StorageOpsError("backup_digest_mismatch", "copy differs from verified backup")
        _fsync_file(staging)
        for suffix in ("-wal", "-shm", "-journal"):
            Path(str(target_path) + suffix).unlink(missing_ok=True)
        os.replace(staging, target_path)
    except OSError as exc:
        staging.unlink(missing_ok=True)
        raise StorageOpsError("restore_failed", f"restore failed: {exc}") from exc
    except BaseException:
        staging.unlink(missing_ok=True)
        raise
    return report
