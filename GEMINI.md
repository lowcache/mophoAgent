# mophoAgent — worker rules (Gemini/agy via tether)

These rules apply to every delegated task run in this repository. They mirror
the tether worker contract (clemini `PROTOCOL.md` §5 / GEMINI.md §XIII) and add
project-specific constraints.

## Authority

- `phoneAgentBuild/DECISIONS.md` (D1–D10) is authoritative. It overrides any
  contradiction in `phoneAgentBuild/design/` or the phase prompts. Never amend
  it; architecture changes go through the relay (`relay/README.md`), not you.
- Execute the BRIEF literally. No adjacent work, no unsolicited refactors.
  Design choices the brief doesn't settle go in BLOCKERS, not into code.

## Environment facts (do not rediscover, do not assume otherwise)

- You are in a proot-distro container on an Android phone. proot home is
  `/root`; native Termux home is bind-mounted at `/termux`.
- Server code lives at `~/phone-agent` (Termux root) / `repo:phone-agent/`.
  Runtime config and token live at `~/.config/phone-agent/`.
- The live MCP server binds the Tailscale IP (fallback `0.0.0.0`) on port 8462.
  For tests, boot a second instance on loopback with a different port — never
  fight the live server for 8462.
- `curl` resolves to `/system/bin/curl` and fails under proot; use Python
  (`urllib`/`httpx`) for HTTP checks.
- Heavy scratch goes under the session scratch dir or `~/Storage/tmp`, not
  tmpfs `/tmp` (small, wiped on boot).

## Quality bar for reports

- RESULT must state what was verified vs. what is inferred. Anything you did
  not run or read this session is labeled per GEMINI.md §VI.B.
- EVIDENCE lists the exact commands run and files read, with paths and line
  numbers (`file.py:42`), plus the relevant output — enough for the
  orchestrator to re-run every check.
- Code changes: minimal diffs matching surrounding style; no new dependencies
  unless the brief authorizes them; run the affected code path before
  reporting it fixed (a passing import is not verification).
- Security-sensitive code (auth middleware, token handling): treat all header
  and request input as attacker-controlled; test the malformed/edge case, not
  only the happy path.

## Hard limits

- Never edit `.memory/*` directly; deliberate records go to `.memory/inbox/`
  as dated notes.
- Never `git push`, tag, or perform destructive/irreversible operations unless
  the brief explicitly contains them and permissions allow.
- Never commit secrets; `~/.config/phone-agent/token` and anything matching
  `.gitignore` secret patterns stay out of the repo and out of reports.
