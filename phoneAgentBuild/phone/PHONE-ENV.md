# Phone Build Environment — read before Phase 0

You are Claude Code running on the Galaxy S26 Ultra, inside a proot-distro
under Termux. You build and maintain the phone MCP server described by
`prompts/phase-0` … `phase-7` and the specs in `../design/`. Decisions in
`../DECISIONS.md` override anything that contradicts them.

## The two worlds you straddle

| | proot-distro (you) | native Termux (the server) |
|---|---|---|
| Filesystem | own rootfs + binds | `/data/data/com.termux/files/home` |
| Python | distro python (dev tooling ok) | `pkg install python` — **runs the server** |
| termux-api tools | not directly usable | microphone/camera/sensor/notify/location |
| rish (Shizuku) | no | yes (after `rish` setup) |

Rules that follow:

1. **Code lives in native Termux home, inside the cloned repo.** Clone
   mophoAgent to `~/mophoAgent` in the **native Termux home** (reached from
   proot via the bind mount, e.g. `proot-distro login --bind
   /data/data/com.termux/files/home:/termux`). Product code goes in
   `~/mophoAgent/phone-agent/` on the **`phone` branch**; symlink
   `~/phone-agent -> ~/mophoAgent/phone-agent` so the phase file-trees
   resolve. Edit through the bind; never copy code into the proot rootfs.
   Phase 0 has the exact clone/checkout/symlink commands.
2. **Run and test with Termux python**, not proot python. From proot, exec
   through the bind: `/data/data/com.termux/files/usr/bin/python`. If a
   pip package needs to build native wheels, install it from a native Termux
   session (bionic libc), not from proot (glibc) — wheels are not
   interchangeable.
3. `termux-api` binaries live at `/data/data/com.termux/files/usr/bin/` and
   need the Termux:API app installed plus per-permission grants (mic, camera,
   location) in Android settings.
4. Config: `~/.config/phone-agent/` (Termux home). Models:
   `~/phone-agent/models/` (gitignored). Ingest: `~/ingest/`.
5. The server binds the phone's Tailscale IP, port 8462 (D1). Find the IP in
   the Tailscale Android app — there is no `tailscale` CLI on the phone.
6. Git: this repo is cloned from github.com/lowcache/mophoAgent. **Work on
   the `phone` branch only** — never commit to `main` or `laptop`. Commit
   per phase with the given commit message and tag, push after each phase
   commit and each relay message. Full branch/relay protocol:
   `relay/README.md` at the repo root. Rebase on main after integration
   merges: `git pull --rebase origin main`.
7. Cross-agent communication (blockers, questions, handoffs) goes through
   `relay/to-laptop/` — NOT `.memory/`, which is laptop-local. Read
   `relay/README.md` before Phase 0.

## Companion setup docs (this directory)

- `SETUP-AUTH.md` — generate an on-device SSH key / PAT to clone private
  repos. Do this first; the clone commands above and tether both need it.
- `TETHER-SETUP.md` — wire up `tether` in the proot so you can delegate
  parallel sub-work to Gemini (optional, but recommended for bulk/mechanical
  or verification tasks).

## Verifying each phase

Each phase prompt has a Test Procedure. Tests that need hardware
(mic/camera/sensors/Shizuku) must run from a **native Termux session**; ask
the user to run them there if your proot session can't reach the API socket,
and have them paste output back.

## Escalation

If a dependency won't build on Termux (bionic), first check the
termux-user-repository (`tur-repo`), then consider a pure-python fallback,
then flag the blocker in your phase summary rather than substituting an
architecture change — architecture changes go through the laptop agent and
`DECISIONS.md`.

## Runtime boundary (P2 — binding rule, 2026-07-16)

Two environments; errors live at their boundary:
- **proot-distro** = dev/orchestration ONLY (Claude Code, edits, commits).
- **native Termux** = runtime + ALL device I/O.

The agent NEVER launches the MCP server, backend servers, or termux-api calls
from proot. The runit service (`sv up/down/status phone-agent`, installed by
`phone-agent/scripts/bootstrap.sh`) owns the server lifecycle; dev verifies
over local HTTP only — against the server's bind address: the configured
tailnet IP while the VPN is up (loopback is then REFUSED; 127.0.0.1 only
answers after the 0.0.0.0 fallback when the VPN is down). Launch logic lives
in `phone-agent/scripts/run.sh` (fast-fails under proot).
