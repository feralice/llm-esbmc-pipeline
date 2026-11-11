"""Irreversible filesystem confinement for disposable CPython workers.

Landlock ABI >= 3 protects opens, truncation, removal and cross-directory moves.
Seccomp closes the metadata-write and process-control gaps Landlock does not cover.
This module must run in the child, before loading any untrusted Python.
See https://docs.kernel.org/userspace-api/landlock.html .
"""

from __future__ import annotations

import ctypes
import errno
import os
import platform
import sys
from pathlib import Path


class IsolationUnavailable(RuntimeError):
    """The host cannot enforce the required boundary; do not run user code."""


class _Ruleset(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class _PathRule(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


class _Argument(ctypes.Structure):
    _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]


def _deny_host_mutation() -> None:
    """Deny metadata writes, new processes and access to host network endpoints."""
    try:
        seccomp = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    except OSError as exc:
        raise IsolationUnavailable("libseccomp is required for worker isolation") from exc
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                             ctypes.c_uint, ctypes.POINTER(_Argument)]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    context = seccomp.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise IsolationUnavailable("cannot create worker syscall policy")
    denied = (
        "chmod", "fchmod", "fchmodat", "fchmodat2", "chown", "fchown", "lchown", "fchownat",
        "setxattr", "lsetxattr", "fsetxattr", "removexattr", "lremovexattr", "fremovexattr",
        "utime", "utimes", "futimesat", "utimensat", "mount", "umount2", "pivot_root",
        "ptrace", "process_vm_writev", "open_by_handle_at", "bpf", "io_uring_setup",
        "kill", "tkill", "tgkill", "pidfd_send_signal", "pidfd_getfd", "prlimit64",
        "execve", "execveat", "fork", "vfork", "clone", "clone3", "unshare", "setns",
        "connect", "bind", "sendto", "sendmsg", "sendmmsg",
    )
    try:
        for name in (*denied, "socket"):
            number = seccomp.seccomp_syscall_resolve_name(name.encode())
            if number == -1:
                continue  # No syscall with this name on the host architecture.
            # asyncio needs a private AF_UNIX socketpair; host connections remain denied.
            argument = _Argument(0, 1, 1, 0)  # SCMP_CMP_NE, AF_UNIX
            count = 1 if name == "socket" else 0
            if seccomp.seccomp_rule_add_array(context, 0x00050000 | errno.EPERM, number, count,
                                               ctypes.byref(argument) if count else None) != 0:
                raise IsolationUnavailable(f"cannot restrict worker syscall {name}")
        if seccomp.seccomp_load(context) != 0:
            raise IsolationUnavailable("cannot enforce worker syscall policy")
    finally:
        seccomp.seccomp_release(context)


def confine_writes(directory: Path) -> None:
    """Allow file writes only below ``directory``; fail closed on unsupported hosts.

    Read access is unchanged so original modules and their dependencies can load.
    This is a local execution boundary, not a VM or a guarantee against kernel bugs.
    """
    if sys.platform != "linux" or platform.machine() not in {"x86_64", "aarch64"}:
        raise IsolationUnavailable("worker isolation requires Linux x86_64 or aarch64")
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, None, 0, 1)  # landlock_create_ruleset: query ABI
    if abi < 3:
        raise IsolationUnavailable("Landlock ABI >= 3 is required for worker isolation")
    # All write rights through ABI 3, excluding EXECUTE/READ_FILE/READ_DIR.
    handled = ((1 << 15) - 1) & ~((1 << 0) | (1 << 2) | (1 << 3))
    if abi >= 5:
        handled |= 1 << 15  # IOCTL_DEV
    ruleset = _Ruleset(handled)
    ruleset_fd = libc.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0)
    if ruleset_fd < 0:
        raise IsolationUnavailable(f"cannot create Landlock ruleset: {os.strerror(ctypes.get_errno())}")
    try:
        parent_fd = os.open(Path(directory).resolve(strict=True), os.O_PATH | os.O_CLOEXEC)
        try:
            # No device nodes, FIFOs or sockets are needed in disposable output directories.
            allowed = handled & ~((1 << 6) | (1 << 9) | (1 << 10) | (1 << 11) | (1 << 15))
            rule = _PathRule(allowed, parent_fd)
            if libc.syscall(445, ruleset_fd, 1, ctypes.byref(rule), 0) < 0:
                raise IsolationUnavailable("cannot add worker directory to Landlock")
        finally:
            os.close(parent_fd)
        # pytest's descriptor capture opens /dev/null for stdin; it contains no user data.
        null_fd = os.open(os.devnull, os.O_PATH | os.O_CLOEXEC)
        try:
            null_rule = _PathRule((1 << 1) | ((1 << 15) if abi >= 5 else 0), null_fd)
            if libc.syscall(445, ruleset_fd, 1, ctypes.byref(null_rule), 0) < 0:
                raise IsolationUnavailable("cannot allow the null device for worker capture")
        finally:
            os.close(null_fd)
        if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
            raise IsolationUnavailable("cannot disable privilege escalation")
        if libc.syscall(446, ruleset_fd, 0) < 0:
            raise IsolationUnavailable("cannot enforce Landlock ruleset")
        _deny_host_mutation()
    finally:
        os.close(ruleset_fd)
