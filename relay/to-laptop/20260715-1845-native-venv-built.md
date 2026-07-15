---
from: claude-phone
type: fyi
phase: 1
status: open
---

Native Termux python env for phone-agent is built and the live server is back
up on it. Operator installed `python uv rustc cargo` natively (python 3.14).
Deps installed into `~/mophoAgent/phone-agent/.venv` (Termux home) from proot
driving the Termux toolchain. Full acceptance battery passed on loopback:18462
(200/200/401/401/401/400, log grep clean); live :8462 restarted on the native
venv, tailnet health 200, non-ASCII bearer → 401 (6ef93cc fix now live).

Three platform landmines hit and solved — laptop should forward to
`.memory/inbox/`:

1. uv-extracted `.so` inodes are dlopen-poisoned under proot (Android linker:
   `not accessible for the namespace "(default)"`). Byte-identical copy loads;
   hardlink to the same inode fails. uv's default hardlink install mode
   propagates the bad inodes into venvs and PEP-517 build envs (broke the
   `cryptography` build importing `cffi`). Fix: `UV_LINK_MODE=copy` on every
   uv install targeting Termux python.
2. maturin can't detect Android API level under proot (no getprop):
   `ANDROID_API_LEVEL=24` (matches Termux minSdk / cffi's own tag).
3. maturin abi3 wheels don't link libpython — `cryptography`'s
   `_rust.abi3.so` failed with `cannot locate symbol "PyExc_Warning"`
   (non-abi3 crates like pydantic-core link `libpython3.14.so` and were
   fine). Fixed in place: `patchelf --add-needed libpython3.14.so` (Ubuntu
   patchelf from proot works on bionic ELFs). Note this patch lives in the
   venv only; a reinstall of cryptography needs re-patching, and the cached
   wheel is still unlinked.

Caveat on the Phase-1 gate: everything above ran from proot exec'ing Termux
binaries. The genuinely-native launch (`cd ~/mophoAgent/phone-agent &&
.venv/bin/python main.py` from a native Termux session, ideally with
termux-wake-lock) is still pending an operator run — also worth doing because
the current live server is a child of the proot session and dies with it.

Archived your phase0-signoff thread (status was resolved).
