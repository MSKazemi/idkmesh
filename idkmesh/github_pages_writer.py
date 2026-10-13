"""Local-directory writer for the C14-E Pages site file map (#609).

``idkmesh.github_pages_site.render_github_pages_site`` returns a deterministic
``path -> text`` mapping and deliberately writes nothing. This module is the
smallest possible companion: it validates that mapping again, then writes
exactly those files to a local directory. It performs no network, GitHub,
publication, verification, decision, or repository mutation and adds no file
beyond the render result.

Safety properties:

* every path must be a relative, normalised, POSIX path of safe segments, so a
  hand-built mapping cannot name a file outside the target (absolute paths,
  ``..``, backslashes, drive letters, NUL, and file/directory collisions are
  all refused before anything is written);
* the whole site is staged in a fresh sibling directory and moved into place
  only after every file was written, so a failure leaves the previous target
  untouched and no half-written site behind;
* the target itself must not be a symlink, and nothing existing is ever
  followed or written through: files are created only inside the fresh staging
  directory;
* a non-empty target is replaced only when it is recognisably a site produced
  by this writer (exact generated layout, no symlinks, a generated
  ``index.html``) or when the caller passes ``force=True``; ``force`` still
  refuses the filesystem root, the current directory and its ancestors, the
  home directory, and any directory that holds a ``.git`` entry.

The remaining race is the usual one for local tools: another process
swapping the target between the check and the rename is not defended against.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from idkmesh.github_pages_site import MAX_RUNS, MAX_SITE_BYTES


# index + .nojekyll, plus one page and one JSON file per run.
MAX_FILES = 2 + 2 * MAX_RUNS

_SEGMENT_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\Z|\.nojekyll\Z")
_MAX_PATH_BYTES = 256
_GENERATED_PATH_RES = (
    re.compile(r"\.nojekyll\Z"),
    re.compile(r"index\.html\Z"),
    re.compile(r"runs/[0-9a-f]{16}\.html\Z"),
    re.compile(r"data/runs/[0-9a-f]{16}\.json\Z"),
)
# Stable fragments of every generated index page (see github_pages_site._page).
_INDEX_SIGNATURE = (
    '<meta name="robots" content="noindex">',
    "Read-only publication of digest-bound public metadata.",
)
_MAX_INDEX_BYTES = 2 * 1024 * 1024
_MAX_SCAN_ENTRIES = 2 * MAX_FILES + 16


class GitHubPagesWriteError(ValueError):
    """Fail-closed Pages writer error."""


@dataclass(frozen=True)
class PagesWriteResult:
    """What was written; ``files`` is ``(path, size_bytes, sha256)`` sorted."""

    out_dir: str
    files: tuple[tuple[str, int, str], ...]
    replaced_existing: bool

    @property
    def total_bytes(self) -> int:
        return sum(size for _, size, _ in self.files)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GitHubPagesWriteError(message)


def _validate_file_map(files: Mapping[str, str]) -> dict[str, bytes]:
    """Return ``path -> UTF-8 bytes`` or raise before any filesystem access."""

    _require(isinstance(files, Mapping), "file map must be a mapping")
    _require(bool(files), "file map is empty")
    _require(len(files) <= MAX_FILES, f"at most {MAX_FILES} files may be written")
    encoded: dict[str, bytes] = {}
    folded: set[str] = set()
    total = 0
    for path, text in files.items():
        _require(
            isinstance(path, str) and isinstance(text, str),
            "file map paths and contents must be strings",
        )
        _require(
            0 < len(path.encode("utf-8", "surrogatepass")) <= _MAX_PATH_BYTES,
            "file path is empty or too long",
        )
        segments = path.split("/")
        for segment in segments:
            # The pattern excludes "", ".", ".." and any other leading dot
            # except the one generated ".nojekyll" marker.
            _require(
                _SEGMENT_RE.fullmatch(segment) is not None,
                f"unsafe file path: {path!r}",
            )
        key = path.casefold()
        _require(key not in folded, f"duplicate file path: {path!r}")
        folded.add(key)
        try:
            data = text.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise GitHubPagesWriteError(
                f"file content is not UTF-8 encodable: {path!r}"
            ) from exc
        total += len(data)
        encoded[path] = data
    _require(
        total <= MAX_SITE_BYTES,
        f"generated site exceeds {MAX_SITE_BYTES} UTF-8 bytes",
    )
    # A path may not be both a file and a directory prefix of another path.
    for path in encoded:
        parts = path.split("/")
        for i in range(1, len(parts)):
            _require(
                "/".join(parts[:i]) not in encoded,
                f"file path conflicts with a directory: {path!r}",
            )
    return dict(sorted(encoded.items()))


def _is_generated_site(directory: Path) -> bool:
    """True only for a tree that matches the generated layout exactly."""

    found: list[str] = []
    stack: list[tuple[Path, str]] = [(directory, "")]
    seen = 0
    while stack:
        current, prefix = stack.pop()
        try:
            with os.scandir(current) as entries:
                listing = list(entries)
        except OSError:
            return False
        for entry in listing:
            seen += 1
            if seen > _MAX_SCAN_ENTRIES:
                return False
            rel = f"{prefix}{entry.name}"
            try:
                if entry.is_symlink():
                    return False
                if entry.is_dir(follow_symlinks=False):
                    if rel not in {"runs", "data", "data/runs"}:
                        return False
                    stack.append((Path(entry.path), rel + "/"))
                    continue
                if not entry.is_file(follow_symlinks=False):
                    return False
            except OSError:
                return False
            if not any(p.fullmatch(rel) for p in _GENERATED_PATH_RES):
                return False
            found.append(rel)
    if "index.html" not in found:
        return False
    index = directory / "index.html"
    try:
        if index.stat().st_size > _MAX_INDEX_BYTES:
            return False
        with index.open("rb") as handle:
            head = handle.read(_MAX_INDEX_BYTES + 1)
        text = head.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return all(marker in text for marker in _INDEX_SIGNATURE)


def _refuse_dangerous_force_target(target: Path) -> None:
    cwd = Path.cwd().resolve()
    resolved = target.resolve()
    home = Path.home().resolve()
    _require(
        resolved.parent != resolved,
        "refusing to replace the filesystem root",
    )
    _require(
        resolved != cwd and resolved not in cwd.parents,
        "refusing to replace the current directory or one of its ancestors",
    )
    _require(
        resolved != home and resolved not in home.parents,
        "refusing to replace the home directory or one of its ancestors",
    )
    _require(
        not os.path.lexists(resolved / ".git"),
        "refusing to replace a directory that contains .git",
    )


def _make_stage(parent: Path, name: str, kind: str) -> Path:
    for _ in range(16):
        candidate = parent / f".{name}.idkmesh-{kind}-{secrets.token_hex(6)}"
        try:
            os.mkdir(candidate)
        except FileExistsError:
            continue
        return candidate
    raise GitHubPagesWriteError("cannot allocate a staging directory")


def write_github_pages_site(
    files: Mapping[str, str],
    out_dir: str | os.PathLike[str],
    *,
    force: bool = False,
) -> PagesWriteResult:
    """Write a rendered Pages file map to ``out_dir`` (all-or-nothing).

    ``out_dir`` must not exist, or must be an empty directory, or a site this
    writer produced, or (with ``force``) any other directory that passes the
    force guards. Its parent directory must already exist. Raises
    :class:`GitHubPagesWriteError` for every refusal or filesystem failure.
    """

    encoded = _validate_file_map(files)
    target = Path(os.fspath(out_dir))
    name = target.name
    _require(
        name not in {"", ".", ".."},
        "out directory needs a final path component (not '.', '..' or '/')",
    )
    parent = target.parent
    _require(parent.is_dir(), f"parent directory does not exist: {parent}")
    if os.path.islink(target):
        raise GitHubPagesWriteError(f"out directory is a symlink: {target}")

    replaced = False
    if os.path.lexists(target):
        _require(
            target.is_dir() and not os.path.islink(target),
            f"out path exists and is not a directory: {target}",
        )
        if any(target.iterdir()):
            if _is_generated_site(target):
                pass
            elif force:
                _refuse_dangerous_force_target(target)
            else:
                raise GitHubPagesWriteError(
                    f"out directory is not empty and was not produced by this "
                    f"tool (pass --force to replace it): {target}"
                )
        replaced = True

    stage = _make_stage(parent, name, "tmp")
    backup: Path | None = None
    try:
        for path, data in encoded.items():
            destination = stage.joinpath(*path.split("/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(destination, "xb") as handle:
                handle.write(data)
        if replaced:
            backup = _make_stage(parent, name, "old")
            os.rmdir(backup)
            os.rename(target, backup)
            try:
                os.rename(stage, target)
            except OSError:
                os.rename(backup, target)
                backup = None
                raise
        else:
            os.rename(stage, target)
    except OSError as exc:
        shutil.rmtree(stage, ignore_errors=True)
        raise GitHubPagesWriteError(
            f"cannot write Pages site to {target}: "
            f"{exc.strerror or type(exc).__name__}"
        ) from exc
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    if backup is not None:
        shutil.rmtree(backup, ignore_errors=True)
    return PagesWriteResult(
        out_dir=str(target),
        files=tuple(
            (path, len(data), hashlib.sha256(data).hexdigest())
            for path, data in encoded.items()
        ),
        replaced_existing=replaced,
    )
