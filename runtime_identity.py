"""Exact installed-runtime identity, independent of controller and model state.

Owns stable retained executable descriptors, hardened managed Uzu admission
and pinned llama.cpp executable/library closure verification. Immutable policy
objects supply release paths/identity; only llama.cpp's existing stable-file
hash cache is injected. No CLI execution, model load, install or network use.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import stat
import sys
from typing import Any, Callable


@dataclass(frozen=True)
class UzuRuntimePolicy:
    executable: Path
    tag: str
    directory_mode: int
    binary_mode: int
    release_url: str
    upstream_commit: str
    source_patch_sha256: str
    source_patches: tuple[str, ...]
    binary_sha256: str
    binary_size: int
    boundary_contract_id: str
    memory_hotfix_url: str
    sandbox_executable: Path


@dataclass(frozen=True)
class LlamaCppRuntimePolicy:
    server: Path
    directory: Path
    tag: str
    commit: str
    archive_sha256: str
    required_flags: tuple[str, ...]
    files: tuple[tuple[str, str, str], ...]



def executable_stat_identity(details: os.stat_result) -> tuple[int, ...]:
    """Return the fields that must remain stable while executable bytes are read."""
    return (
        details.st_dev,
        details.st_ino,
        details.st_mode,
        details.st_uid,
        details.st_gid,
        details.st_nlink,
        details.st_size,
        details.st_mtime_ns,
        details.st_ctime_ns,
    )


@dataclass
class OpenExecutableRevision:
    """An executable revision whose already-verified descriptor remains open."""

    path: Path
    fd: int
    identity: dict[str, Any]

    def close(self) -> None:
        if self.fd < 0:
            return
        descriptor, self.fd = self.fd, -1
        try:
            os.close(descriptor)
        except OSError:
            pass


def open_executable_revision(
    path: Path, *, required_owner: int | None = None,
    required_mode: int | None = None, required_links: int | None = None,
) -> OpenExecutableRevision:
    """Hash one non-symlink executable through a stable, retained descriptor."""
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise ValueError("This platform cannot safely open the runtime executable without following links.")
    flags = os.O_RDONLY | no_follow | getattr(os, "O_CLOEXEC", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        named_before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("The installed runtime executable is not a regular file.")
        if (before.st_mode & 0o111) == 0:
            raise ValueError("The installed runtime candidate is no longer executable.")
        if before.st_size <= 0 or before.st_size > 512 * 1024**2:
            raise ValueError("The installed runtime executable has an unexpected size.")
        if required_owner is not None and before.st_uid != required_owner:
            raise ValueError("The launcher-managed Uzu executable is not owner-controlled.")
        if required_mode is not None and stat.S_IMODE(before.st_mode) != required_mode:
            raise ValueError("The launcher-managed Uzu executable must remain owner-executable mode 0500.")
        if required_links is not None and before.st_nlink != required_links:
            raise ValueError("The launcher-managed Uzu executable must have exactly one filesystem link.")
        if (
            named_before.st_dev != before.st_dev
            or named_before.st_ino != before.st_ino
        ):
            raise ValueError("The installed runtime executable changed before it could be identified.")
        digest = hashlib.sha256()
        os.lseek(descriptor, 0, os.SEEK_SET)
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
        after = os.fstat(descriptor)
        named_after = path.lstat()
        if (
            executable_stat_identity(before) != executable_stat_identity(after)
            or named_after.st_dev != after.st_dev
            or named_after.st_ino != after.st_ino
        ):
            raise ValueError("The installed runtime executable changed while it was being identified.")
        identity = {
            "resolvedPath": str(path),
            "device": after.st_dev,
            "inode": after.st_ino,
            "size": after.st_size,
            "modifiedNs": after.st_mtime_ns,
            "changedNs": after.st_ctime_ns,
            "sha256": digest.hexdigest(),
        }
        identity["id"] = hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()[:24]
        return OpenExecutableRevision(path, descriptor, identity)
    except (OSError, ValueError) as error:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if isinstance(error, ValueError):
            raise
        raise ValueError(
            "The installed runtime executable changed while it was being identified."
        ) from error


def executable_revision(path_value: Any) -> dict[str, Any]:
    """Bind promotion evidence to stable bytes read through an O_NOFOLLOW fd."""
    try:
        path = Path(str(path_value or "")).expanduser().resolve(strict=True)
    except OSError as error:
        raise ValueError("The installed runtime executable could not be revalidated.") from error
    opened = open_executable_revision(path)
    try:
        return copy.deepcopy(opened.identity)
    finally:
        opened.close()


def uzu_runtime_path(path_value: Any, policy: UzuRuntimePolicy) -> Path:
    """Accept only the exact, non-symlink path beneath safe directory ancestors."""
    raw_path = "" if path_value is None else str(path_value)
    if not raw_path.strip():
        raise ValueError("The launcher-managed Uzu executable is not installed.")
    requested = Path(raw_path).expanduser()
    try:
        direct = requested.lstat()
    except OSError as error:
        raise ValueError("The launcher-managed Uzu executable is not installed.") from error
    if stat.S_ISLNK(direct.st_mode):
        raise ValueError("The launcher-managed Uzu executable must not be a symbolic link.")
    requested = Path(os.path.abspath(requested))
    expected = Path(os.path.abspath(policy.executable.expanduser()))
    if requested != expected:
        raise ValueError(
            f"Only the launcher-managed hardened Uzu {policy.tag} executable is accepted."
        )
    ancestors = (requested.parent, *requested.parent.parents)
    for index, ancestor in enumerate(ancestors):
        try:
            details = ancestor.lstat()
        except OSError as error:
            raise ValueError("The launcher-managed Uzu executable has an unsafe ancestor.") from error
        if stat.S_ISLNK(details.st_mode):
            # macOS commonly spells the protected system path /private/var as
            # the root-owned /var symlink. It is not mutable by this user and
            # is safe to traverse; user-owned or writable-container symlinks
            # remain rejected. The canonical target chain is checked below.
            try:
                container = ancestor.parent.lstat()
            except OSError as error:
                raise ValueError(
                    "The launcher-managed Uzu executable has an unsafe ancestor."
                ) from error
            if (
                index == 0
                or details.st_uid != 0
                or container.st_uid != 0
                or not stat.S_ISDIR(container.st_mode)
                or stat.S_IMODE(container.st_mode) & (stat.S_IWGRP | stat.S_IWOTH)
            ):
                raise ValueError(
                    "The launcher-managed Uzu executable has a symbolic or non-directory ancestor."
                )
            continue
        if not stat.S_ISDIR(details.st_mode):
            raise ValueError("The launcher-managed Uzu executable has a non-directory ancestor.")
        mode = stat.S_IMODE(details.st_mode)
        if index == 0:
            if details.st_uid != os.geteuid() or mode != policy.directory_mode:
                raise ValueError(
                    "The launcher-managed Uzu runtime directory must be owner-only mode 0700."
                )
        elif details.st_uid not in {0, os.geteuid()} or mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ValueError(
                "The launcher-managed Uzu executable has a writable or untrusted directory ancestor."
            )
    try:
        canonical = requested.resolve(strict=True)
    except OSError as error:
        raise ValueError("The launcher-managed Uzu executable has an unsafe ancestor.") from error
    for ancestor in (canonical.parent, *canonical.parent.parents):
        details = ancestor.lstat()
        if (
            stat.S_ISLNK(details.st_mode)
            or not stat.S_ISDIR(details.st_mode)
            or details.st_uid not in {0, os.geteuid()}
            or stat.S_IMODE(details.st_mode) & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise ValueError(
                "The launcher-managed Uzu executable has a writable or untrusted directory ancestor."
            )
    return canonical


def open_uzu_runtime_executable(path_value: Any, policy: UzuRuntimePolicy) -> OpenExecutableRevision:
    path = uzu_runtime_path(path_value, policy)
    return open_executable_revision(
        path,
        required_owner=os.geteuid(),
        required_mode=policy.binary_mode,
        required_links=1,
    )


def confirm_open_uzu_executable(opened: OpenExecutableRevision, policy: UzuRuntimePolicy) -> None:
    """Confirm the managed name still resolves to the retained verified inode."""
    if opened.fd < 0:
        raise ValueError("The verified Uzu executable descriptor is already closed.")
    try:
        descriptor = os.fstat(opened.fd)
        named = opened.path.lstat()
    except OSError as error:
        raise ValueError("The Uzu executable path changed immediately before launch.") from error
    identity = opened.identity
    if (
        not stat.S_ISREG(descriptor.st_mode)
        or descriptor.st_uid != os.geteuid()
        or stat.S_IMODE(descriptor.st_mode) != policy.binary_mode
        or descriptor.st_nlink != 1
        or descriptor.st_dev != identity.get("device")
        or descriptor.st_ino != identity.get("inode")
        or descriptor.st_size != identity.get("size")
        or descriptor.st_mtime_ns != identity.get("modifiedNs")
        or descriptor.st_ctime_ns != identity.get("changedNs")
        or named.st_dev != descriptor.st_dev
        or named.st_ino != descriptor.st_ino
    ):
        raise ValueError("The Uzu executable path changed immediately before launch.")


def uzu_runtime_contract(
    path_value: Any, policy: UzuRuntimePolicy, *, opened_revision: OpenExecutableRevision | None = None,
) -> dict[str, Any]:
    """Verify the exact launcher-owned hardened Uzu build without executing it."""
    result: dict[str, Any] = {
        "ready": False,
        "version": f"Uzu {policy.tag}",
        "releaseUrl": policy.release_url,
        "upstreamCommit": policy.upstream_commit,
        "sourcePatchSha256": policy.source_patch_sha256,
        "sourcePatchFiles": list(policy.source_patches),
        "expectedBinarySha256": policy.binary_sha256,
        "expectedBinarySize": policy.binary_size,
        "networkSandbox": False,
        "sourcePinned": True,
        "binaryIdentityPinned": False,
        "memorySafetyBlocked": True,
        "rawListenerAuthenticated": False,
        "rawListenerIsolated": False,
        "listenerIsolationBlocked": True,
        "boundedContextReady": False,
        "nativeBearerAuthentication": False,
        "oneUseApiKeyFile": False,
        "nativeContextLimit": False,
        "nativeOutputLimit": False,
        "nativeBoundaryContractId": policy.boundary_contract_id,
        "memoryHotfixUrl": policy.memory_hotfix_url,
    }
    owns_descriptor = opened_revision is None
    try:
        opened = opened_revision or open_uzu_runtime_executable(path_value, policy)
        path = uzu_runtime_path(path_value, policy)
        if opened.path != path:
            raise ValueError("The retained Uzu executable does not match the requested runtime path.")
        confirm_open_uzu_executable(opened, policy)
        revision = copy.deepcopy(opened.identity)
    except ValueError as error:
        result["reason"] = str(error)
        return result
    finally:
        if owns_descriptor and "opened" in locals():
            opened.close()
    result["binary"] = revision
    expected_sha = str(policy.binary_sha256 or "")
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha) is None:
        result["reason"] = (
            "The hardened Uzu build exists, but its final executable SHA-256 has not been "
            "pinned in this launcher yet."
        )
        return result
    if revision.get("size") != policy.binary_size:
        result["reason"] = (
            f"The hardened Uzu executable size changed; expected "
            f"{policy.binary_size:,} bytes."
        )
        return result
    if not secrets.compare_digest(str(revision.get("sha256") or ""), expected_sha):
        result["reason"] = (
            f"The Uzu executable no longer matches the pinned hardened {policy.tag} build bytes."
        )
        return result
    result["binaryIdentityPinned"] = True
    sandbox_ready = (
        sys.platform == "darwin"
        and platform.machine().lower() in {"arm64", "aarch64"}
        and policy.sandbox_executable.is_file()
        and os.access(policy.sandbox_executable, os.X_OK)
    )
    result["networkSandbox"] = sandbox_ready
    if not sandbox_ready:
        result["reason"] = "Uzu requires Apple Silicon and the macOS outbound-network sandbox."
        return result
    # This launcher-owned binary is pinned to Uzu 0.5.23 plus the reviewed
    # ordered source patches. These add bounded prefill allocation lifetimes
    # to PR #794's fix and native bearer/context/output enforcement. Exact
    # bytes—not signing status or a reported version—are the trust root.
    result.update({
        "ready": True,
        "memorySafetyBlocked": False,
        "rawListenerAuthenticated": True,
        "listenerIsolationBlocked": False,
        "boundedContextReady": True,
        "nativeBearerAuthentication": True,
        "oneUseApiKeyFile": True,
        "nativeContextLimit": True,
        "nativeOutputLimit": True,
        "reason": (
            f"Exact launcher-managed hardened Uzu {policy.tag} bytes are ready with "
            "native bearer authentication and native context/output ceilings."
        ),
    })
    result["localOnly"] = True
    result["telemetryBlocked"] = True
    result["automaticDownloadsBlocked"] = True
    return result


def uzu_listener_protection_ready(runtime: Any) -> bool:
    """Require positive proof that clients cannot bypass the Uzu relay."""
    return bool(
        isinstance(runtime, dict)
        and runtime.get("listenerIsolationBlocked") is False
        and (
            runtime.get("rawListenerAuthenticated") is True
            or runtime.get("rawListenerIsolated") is True
        )
    )


def strong_path_identity(path: Path) -> tuple[Any, ...]:
    """Capture one runtime/model path strongly enough to detect replacement."""
    requested = path.expanduser()
    details = requested.lstat()
    resolved = requested.resolve(strict=True)
    return (
        str(requested), str(resolved), details.st_dev, details.st_ino,
        details.st_mode, details.st_size, details.st_mtime_ns,
        details.st_ctime_ns, os.readlink(requested) if requested.is_symlink() else None,
    )


def llamacpp_runtime_closure_identities(root: Path, policy: LlamaCppRuntimePolicy) -> tuple[tuple[Any, ...], ...]:
    """Snapshot every executable, dylib load name, and dylib target."""
    paths = [root]
    for load_name, target_name, _expected_digest in policy.files:
        paths.extend((root / load_name, root / target_name))
    unique = sorted({str(item.expanduser()) for item in paths})
    return tuple(strong_path_identity(Path(item)) for item in unique)


def llamacpp_runtime_payload_contract(root: Path, policy: LlamaCppRuntimePolicy, sha256_matches: Callable[[Path, str], bool]) -> tuple[bool, str | None]:
    """Verify each @loader_path file and exact archive symlink target."""
    try:
        root_details = root.lstat()
        resolved_root = root.resolve(strict=True)
    except OSError:
        return False, "runtime directory"
    if stat.S_ISLNK(root_details.st_mode) or not stat.S_ISDIR(root_details.st_mode):
        return False, "runtime directory"
    for load_name, target_name, expected_digest in policy.files:
        load_path = resolved_root / load_name
        target_path = resolved_root / target_name
        try:
            load_details = load_path.lstat()
            resolved_load = load_path.resolve(strict=True)
            resolved_target = target_path.resolve(strict=True)
        except OSError:
            return False, load_name
        if resolved_load != resolved_target or resolved_target.parent != resolved_root:
            return False, load_name
        if load_name == target_name:
            if stat.S_ISLNK(load_details.st_mode) or not stat.S_ISREG(load_details.st_mode):
                return False, load_name
        else:
            try:
                linked_target = os.readlink(load_path)
            except OSError:
                return False, load_name
            if not stat.S_ISLNK(load_details.st_mode) or linked_target != target_name:
                return False, load_name
        if not sha256_matches(resolved_target, expected_digest):
            return False, load_name
    return True, None


def llamacpp_runtime_contract(path: str | None, policy: LlamaCppRuntimePolicy, sha256_matches: Callable[[Path, str], bool]) -> dict[str, Any]:
    """Accept only the launcher-owned b10740 server with the fixed PLE flags."""
    base = {
        "ready": False,
        "tag": policy.tag,
        "commit": policy.commit,
        "archiveSha256": policy.archive_sha256,
        "version": f"llama.cpp {policy.tag} · {policy.commit[:12]}",
        "path": None,
        "missingFlags": [],
        "requiredFlags": list(policy.required_flags),
        "verifiedFiles": [item[0] for item in policy.files],
    }
    if not path:
        return {**base, "reason": f"Install the audited llama.cpp {policy.tag} runtime."}
    try:
        requested = Path(path).expanduser()
        requested.lstat()
        resolved = requested.resolve(strict=True)
        expected = policy.server.expanduser().resolve(strict=False)
    except OSError:
        return {**base, "reason": "The audited llama.cpp server is missing or unreadable."}
    base["path"] = str(resolved)
    if (
        requested.is_symlink() or resolved != expected
        or not resolved.is_file() or not os.access(resolved, os.X_OK)
    ):
        return {
            **base,
            "reason": (
                f"This route accepts only the launcher-managed {policy.tag} "
                "llama-server; embedded and PATH copies fail closed."
            ),
        }
    try:
        before_payload = llamacpp_runtime_closure_identities(policy.directory, policy)
    except OSError:
        return {
            **base,
            "reason": "The managed llama.cpp runtime closure is missing or unsafe.",
        }
    payload_ready, failed_file = llamacpp_runtime_payload_contract(policy.directory, policy, sha256_matches)
    if not payload_ready:
        return {
            **base,
            "failedFile": failed_file,
            "reason": (
                "The managed llama.cpp executable or one of its bundled libraries "
                "does not match the verified official b10740 archive."
            ),
        }
    try:
        verified_closure = llamacpp_runtime_closure_identities(policy.directory, policy)
    except OSError:
        return {
            **base,
            "reason": "The managed llama.cpp runtime changed after byte verification.",
        }
    if verified_closure != before_payload:
        return {
            **base,
            "reason": "The managed llama.cpp runtime changed during byte verification.",
        }
    return {
        **base,
        "ready": True,
        "reason": (
            f"Exact audited llama.cpp {policy.tag} commit "
            f"{policy.commit[:12]} bytes establish the fixed SSD-PLE flag contract."
        ),
    }
