# tether on the phone — Claude→Gemini delegation from the proot-distro

`tether` lets claude-phone delegate scoped, parallelizable sub-work (research,
verification, bulk-mechanical edits) to Gemini, the same way claude-laptop
does. It's a bash wrapper over `agy` (antigravity-cli, the Gemini worker).

## Prerequisite: agy must run in the proot

The `agy` binary is architecture-specific and must already work in your phone
environment (`agy models` should list tiers; auth token at
`~/.gemini/antigravity-cli/antigravity-oauth-token`). tether does not install
or provide agy — it only drives it. If `agy models` errors, fix agy/auth
first; tether can't paper over it.

## Install

Auth must be set up first (see `SETUP-AUTH.md`) — clemini is a private repo.

```bash
git clone git@github.com:lowcache/clemini.git ~/tether
ln -s ~/tether/bin/tether ~/.local/bin/tether     # ensure ~/.local/bin is on PATH
```

Set env (add to your proot shell profile, e.g. `~/.bashrc`):

```bash
export TETHER_DIR="$HOME/tether"    # else defaults to a laptop path that won't exist
export AGY_BIN="agy"                # or an absolute path if agy isn't on PATH
# AGY_BRAIN resolves via $HOME automatically; no need to set it
```

## Worker contract

Gemini follows a fixed report format (`RESULT / EVIDENCE / BLOCKERS`) and
worker rules. Two pieces:

- `PROTOCOL.md` ships inside the clemini clone — nothing to do.
- `~/.gemini/GEMINI.md` §XIII (global worker rules) lives outside the repo.
  Copy the laptop's `~/.gemini/GEMINI.md` into the proot's `~/.gemini/GEMINI.md`
  (out-of-band — Tailscale file copy or paste). Without it tether still runs,
  but Gemini won't strictly honor the worker protocol.

The laptop-specific `~/volnix` ↔ `~/.nix-config` path remapping inside the
script is inert on the phone (no `volnix` dir → it falls through). Ignore it.

## Smoke test

```bash
tether ask "Reply RESULT: ok"
tether models                       # should list the Gemini tiers
```

If `ask` hangs or errors, the cause is almost always agy auth or `AGY_BIN`
not resolving — not tether.

## Usage

```bash
tether run [-m TIER] [-d DIR] [-t TASK] [-y] [--timeout SECS] "BRIEF"
tether continue TASK "FOLLOW-UP"    # resume a named task (needs -t on the run)
tether ask "BRIEF"                  # low-ceremony one-shot (flash tier, ephemeral)
tether status | log [N] | models
```

- `-m TIER`: `pro` (default) | `pro-low` | `flash` | `flash-high` | `flash-low`
- `-d DIR`: worker's working directory (pass the repo path for edit tasks)
- `-t TASK`: name the task so you can `continue` it
- `-y`: skip agy's permission prompts (use for trusted, scoped briefs)
- `--timeout SECS`: hard cap
- `BRIEF` may be `-` to read from stdin (good for long briefs)

Run in the background and poll `tether status` for long jobs, exactly as the
laptop side does.

## What NOT to delegate

Same rules as the laptop orchestrator (from the global toolchain contract):

- **Never delegate:** architecture decisions, `.memory/` curation, destructive
  or system-state operations, and final answers. Claude owns decomposition,
  briefing, integration, and every decision + the final output.
- Gemini is a worker: it produces `RESULT / EVIDENCE / BLOCKERS`, you verify
  and integrate. Core constraints in `~/.claude/CLAUDE.md` and
  `~/.gemini/GEMINI.md` are never suspended through the delegation protocol.
- On this project specifically: don't let a delegated task amend
  `phoneAgentBuild/DECISIONS.md` or invent an architecture change — those go
  through the relay to claude-laptop (`relay/README.md`).
