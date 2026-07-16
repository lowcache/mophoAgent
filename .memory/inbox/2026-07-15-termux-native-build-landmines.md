# Termux native-venv build landmines (forwarded from phone relay, 2026-07-15)

**STATUS (2026-07-15 20:36, from phone screenshots): describes the EARLIER
uv-venv + cryptography build path.** The phone has since pivoted to a
`~/phone-agent-runtime/{bin,lib}` .deb-extraction runtime (llama-server from
extracted Termux .debs, whisper-server cmake-built, numpy/PIL/onnxruntime .deb
payloads copied into the project venv; `$PREFIX` untouched because the phone's
permission classifier blocked prefix writes). The phone's own forthcoming
step-6 inbox note captures the *current* build's landmines (cmake needs
`$PREFIX` env under proot; gate readiness on `/health` 200 not port-open; proot
tar hardlink failure → python tarfile fallback; scratchpad fs rejects
hardlinks; OCR dict blank-at-0). Reconcile the two once the phone pushes — keep
whichever of the below is still true for the .deb path, drop the rest as
historical. Retained for now as build history.

Reference knowledge for building the phone-agent venv under native Termux
python (3.14) driven from proot. Source: relay/to-laptop native-venv-built
note (commit bdad36d). All three were hit and solved on-device; record so a
rebuild does not rediscover them.

1. **uv hardlink install poisons dlopen under proot.** uv-extracted `.so`
   inodes fail the Android linker (`not accessible for the namespace
   "(default)"`); a byte-identical copy loads but a hardlink to the same inode
   does not. uv's default hardlink mode propagates the bad inodes into venvs
   and PEP-517 build envs (broke the `cryptography` build importing `cffi`).
   **Fix: `UV_LINK_MODE=copy` on every uv install targeting Termux python.**

2. **maturin can't detect Android API level under proot** (no `getprop`).
   **Fix: `ANDROID_API_LEVEL=24`** (matches Termux minSdk / cffi's own tag).

3. **maturin abi3 wheels don't link libpython.** `cryptography`'s
   `_rust.abi3.so` failed with `cannot locate symbol "PyExc_Warning"`
   (non-abi3 crates like pydantic-core link `libpython3.14.so` and were fine).
   **Fix: `patchelf --add-needed libpython3.14.so`** on the built `.so` (Ubuntu
   patchelf from proot works on bionic ELFs). Caveat: this patch lives in the
   venv only — a reinstall of `cryptography` needs re-patching, and the cached
   wheel is still unlinked. A durable fix (patched wheel in a local cache, or a
   build-env wrapper exporting the two env vars) is worth doing before Phase 1
   dependency installs (`onnxruntime`, `Pillow`, `numpy`) if any pull a
   maturin/abi3 build.
