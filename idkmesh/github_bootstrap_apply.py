"""C8-F local GitHub bootstrap apply with digest-bound, fail-closed re-runs.

Only the eight files in the canonical bootstrap plan can be installed. A small
local state record remembers generated hashes; it is not an authority token.
No network, provider, GitHub API, secret-value, dispatch, or merge operations.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any

from idkmesh.github_bootstrap import GitHubBootstrapPlan
from idkmesh.github_bootstrap_render import BootstrapRenderedFile

STATE_PATH = ".idkmesh/bootstrap-state.json"
STATE_KIND = "idkmesh-github-bootstrap-state"
STATE_VERSION = "0.1"
MAX_READ_BYTES = 2 * 1024 * 1024
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")


class BootstrapApplyError(ValueError):
    """Local bootstrap refusal with a stable machine-readable error code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _root_fd(root: Path) -> int:
    if not (hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
            and os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
            and os.mkdir in os.supports_dir_fd and os.link in os.supports_dir_fd
            and os.rename in os.supports_dir_fd):
        raise BootstrapApplyError("unsupported_filesystem", "secure POSIX directory-relative operations required")
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise BootstrapApplyError("invalid_root", "root must be a real directory, not a symlink") from exc
    try:
        metadata = os.stat(".git", dir_fd=fd, follow_symlinks=False)
        if not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)):
            raise OSError("unsupported .git marker")
    except OSError as exc:
        os.close(fd)
        raise BootstrapApplyError("git_repository_required", "run from an initialized Git repository") from exc
    return fd


def _parent_fd(root_fd: int, path: str, *, create: bool) -> tuple[int | None, str]:
    parts = path.split("/")
    if (not path or path.startswith("/") or any(part in {"", ".", "..", ".git"} for part in parts)
            or "\\" in path):
        raise BootstrapApplyError("unsafe_path", f"invalid generated path: {path!r}")
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    os.close(fd)
                    return None, parts[-1]
                try:
                    os.mkdir(part, mode=0o755, dir_fd=fd)
                except FileExistsError:
                    pass
                try:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                except OSError as exc:
                    raise BootstrapApplyError("unsafe_path", f"unsafe parent for {path}") from exc
            except OSError as exc:
                raise BootstrapApplyError("unsafe_path", f"unsafe parent for {path}") from exc
            os.close(fd)
            fd = child
        return fd, parts[-1]
    except BaseException:
        os.close(fd)
        raise


def _read(root_fd: int, path: str, *, content: bool) -> bytes | bool | None:
    parent, name = _parent_fd(root_fd, path, create=False)
    if parent is None:
        return None
    try:
        try:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode):
            raise BootstrapApplyError("unsafe_path", f"non-regular file or symlink at {path}")
        if not content:
            return True
        if info.st_size > MAX_READ_BYTES:
            raise BootstrapApplyError("oversized_file", f"refusing to read {path} (>2 MiB)")
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise BootstrapApplyError("unsafe_path", f"non-regular file at {path}")
            data = bytearray()
            while len(data) <= MAX_READ_BYTES:
                chunk = os.read(fd, min(65536, MAX_READ_BYTES + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            if len(data) > MAX_READ_BYTES:
                raise BootstrapApplyError("oversized_file", f"refusing to read {path} (>2 MiB)")
            return bytes(data)
        finally:
            os.close(fd)
    except OSError as exc:
        raise BootstrapApplyError("filesystem_error", f"cannot inspect {path}: {exc.strerror}") from exc
    finally:
        os.close(parent)


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def _state_body(plan: GitHubBootstrapPlan, rendered: dict[str, BootstrapRenderedFile]) -> dict[str, Any]:
    return {
        "kind": STATE_KIND,
        "schema_version": STATE_VERSION,
        "plan_version": plan.plan_version,
        "idkmesh_ref": plan.idkmesh_ref,
        "default_branch": plan.default_branch,
        "managed_digests": {
            path: item.content_digest for path, item in sorted(rendered.items())
            if item.ownership == "idkmesh_managed"
        },
    }


def _encode_state(body: dict[str, Any]) -> bytes:
    return _canonical({**body, "self_digest": _digest(_canonical(body))}) + b"\n"


def _load_state(raw: bytes | None, allowed: set[str]) -> dict[str, str] | None:
    if raw is None:
        return None
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_pairs)
        if not isinstance(obj, dict) or set(obj) != {
            "kind", "schema_version", "plan_version", "idkmesh_ref",
            "default_branch", "managed_digests", "self_digest",
        }:
            raise ValueError("unknown/missing state fields")
        body = {key: value for key, value in obj.items() if key != "self_digest"}
        if (body["kind"] != STATE_KIND or body["schema_version"] != STATE_VERSION
                or body["plan_version"] != "0.1" or not isinstance(body["idkmesh_ref"], str)
                or not isinstance(body["default_branch"], str)
                or obj["self_digest"] != _digest(_canonical(body))):
            raise ValueError("unsupported or altered state")
        digests = body["managed_digests"]
        if (not isinstance(digests, dict) or set(digests) != allowed
                or any(not isinstance(v, str) or not _SHA256.fullmatch(v) for v in digests.values())):
            raise ValueError("invalid managed digest inventory")
        return digests
    except (UnicodeError, ValueError, TypeError, KeyError) as exc:
        raise BootstrapApplyError("invalid_state", "bootstrap-state.json is invalid or modified") from exc


def _render_map(plan: GitHubBootstrapPlan, files: tuple[BootstrapRenderedFile, ...]) -> dict[str, BootstrapRenderedFile]:
    expected = {spec.path: spec for spec in plan.files}
    if (len(expected) != len(plan.files) or len({file.path for file in files}) != len(files)
            or {file.path for file in files} != set(expected) or STATE_PATH in expected):
        raise BootstrapApplyError("render_plan_mismatch", "generated file inventory differs from the canonical plan")
    by_path: dict[str, BootstrapRenderedFile] = {}
    for item in files:
        spec = expected[item.path]
        actual = item.content.encode("utf-8")
        if (item.ownership != spec.ownership or item.overwrite_policy != spec.overwrite_policy
                or item.render_source != spec.render_source or item.size_bytes != len(actual)
                or item.content_digest != _digest(actual)):
            raise BootstrapApplyError("render_plan_mismatch", f"renderer metadata or digest mismatch: {item.path}")
        by_path[item.path] = item
    return by_path


def _inspect(root_fd: int, plan: GitHubBootstrapPlan, rendered: dict[str, BootstrapRenderedFile]) -> dict[str, Any]:
    managed = {path for path, item in rendered.items() if item.ownership == "idkmesh_managed"}
    state_raw = _read(root_fd, STATE_PATH, content=True)
    assert state_raw is None or isinstance(state_raw, bytes)
    old_digests = _load_state(state_raw, managed)
    actions = []
    for path, item in sorted(rendered.items()):
        existing = _read(root_fd, path, content=item.ownership == "idkmesh_managed")
        current_digest = _digest(existing) if isinstance(existing, bytes) else None
        if item.ownership == "user_seed":
            action = "preserve" if existing is not None else "create"
        elif old_digests is None:
            if existing is None:
                action = "create"
            elif current_digest == item.content_digest:
                action = "unchanged"
            else:
                raise BootstrapApplyError("untracked_managed_file", f"existing {path} lacks matching generated digest state")
        else:
            if existing is None:
                raise BootstrapApplyError("managed_file_missing", f"managed file was deleted: {path}")
            if current_digest != old_digests[path]:
                raise BootstrapApplyError("managed_file_modified", f"local edits detected: {path}")
            action = "unchanged" if current_digest == item.content_digest else "replace"
        actions.append({"path": path, "action": action, "ownership": item.ownership,
                        "content_digest": item.content_digest, "current_digest": current_digest})
    state_bytes = _encode_state(_state_body(plan, rendered))
    return {"kind": "idkmesh-github-bootstrap-local-plan", "schema_version": "0.1",
            "writes_performed": False, "github_mutation_performed": False,
            "secret_values_accessed": False, "state_path": STATE_PATH,
            "state_update_required": state_raw != state_bytes, "actions": actions}


def plan_github_bootstrap_apply(root: Path, plan: GitHubBootstrapPlan,
                                files: tuple[BootstrapRenderedFile, ...]) -> dict[str, Any]:
    """Read-only conflict check; no files or directories are created."""
    rendered = _render_map(plan, files)
    root_fd = _root_fd(Path(root))
    try:
        return _inspect(root_fd, plan, rendered)
    finally:
        os.close(root_fd)


def _atomic_write(root_fd: int, path: str, data: bytes, *, old_digest: str | None) -> None:
    parent, name = _parent_fd(root_fd, path, create=True)
    assert parent is not None
    temp_name = f".idkmesh-init-{secrets.token_hex(12)}.tmp"
    try:
        existing = _read(root_fd, path, content=True)
        actual_digest = _digest(existing) if isinstance(existing, bytes) else None
        if actual_digest != old_digest:
            raise BootstrapApplyError("head_changed", f"file changed after preflight: {path}")
        fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if old_digest is None:
                os.link(temp_name, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            else:
                os.rename(temp_name, name, src_dir_fd=parent, dst_dir_fd=parent)
        finally:
            try:
                os.unlink(temp_name, dir_fd=parent)
            except FileNotFoundError:
                pass
    except OSError as exc:
        raise BootstrapApplyError("filesystem_error", f"cannot safely write {path}: {exc.strerror}") from exc
    finally:
        os.close(parent)


def apply_github_bootstrap(root: Path, plan: GitHubBootstrapPlan,
                           files: tuple[BootstrapRenderedFile, ...]) -> dict[str, Any]:
    """Install only vetted local files; refuse modified managed files.

    A preflight checks all paths before writing any of them. Multiple-file
    replacement is not transactional; use only with one local writer. State is
    written last, so an interrupted upgrade fails closed on the next re-run.
    """
    rendered = _render_map(plan, files)
    root_fd = _root_fd(Path(root))
    try:
        report = _inspect(root_fd, plan, rendered)
        prior_state = _read(root_fd, STATE_PATH, content=True)
        assert prior_state is None or isinstance(prior_state, bytes)
        for action in report["actions"]:
            if action["action"] in {"create", "replace"}:
                item = rendered[action["path"]]
                _atomic_write(root_fd, item.path, item.content.encode("utf-8"),
                              old_digest=action["current_digest"])
        if report["state_update_required"]:
            current_state = _read(root_fd, STATE_PATH, content=True)
            if current_state != prior_state:
                raise BootstrapApplyError("head_changed", "bootstrap state changed during apply")
            _atomic_write(root_fd, STATE_PATH, _encode_state(_state_body(plan, rendered)),
                          old_digest=_digest(prior_state) if prior_state is not None else None)
        wrote = any(action["action"] in {"create", "replace"} for action in report["actions"])
        return {**report, "kind": "idkmesh-github-bootstrap-apply",
                "writes_performed": wrote or report["state_update_required"]}
    finally:
        os.close(root_fd)
