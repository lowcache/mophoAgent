# relay/ — claude-phone ↔ claude-laptop dropbox

Cross-device collaboration channel during the build. The repo is the only
shared surface between the two agents, so git is the transport: write a
message, commit, push; the other side pulls before starting work and before
ending a session.

This is NOT memd. `.memory/` is laptop-local (memd curator runs there);
claude-phone must not write to `.memory/`. Anything in the relay worth
persisting gets forwarded to `.memory/inbox/` by claude-laptop.

## Layout

```
relay/
├── to-laptop/     # phone writes here, laptop consumes
├── to-phone/      # laptop writes here, phone consumes
└── archive/       # resolved threads, moved here by the consumer
```

## Message format

One markdown file per thread: `YYYYMMDD-HHMM-<slug>.md` (sender's local
time). Frontmatter:

```markdown
---
from: claude-phone | claude-laptop
type: blocker | question | decision-request | handoff | fyi
phase: 0-8
status: open | answered | resolved
---

Body: what happened, what you tried, exact error output. For
decision-request: the options considered and your recommendation.
```

Replies are appended to the same file under a `## Reply (from <agent>,
<date>)` heading — one file per thread, not per message. Whoever writes the
resolution flips `status:` and moves the file to `archive/` in the same
commit.

## Rules

1. **Blockers before workarounds.** If a phase prompt can't be implemented
   as written (dependency won't build, tool doesn't exist, spec conflict),
   file a `blocker` and stop that thread of work — don't improvise an
   architecture change. Architecture lives in `phoneAgentBuild/DECISIONS.md`
   and only claude-laptop amends it (after a `decision-request` round-trip
   if the phone found the problem).
2. **Handoffs are explicit.** Phase 8 depends on phone-side realities
   (actual Tailscale IP, actual port, tool output shapes that drifted from
   spec). When a phone phase lands, drop a `handoff` note in `to-laptop/`
   listing anything that deviated from the phase prompt.
3. **Pull before write.** Both agents: `git pull --rebase` before writing
   relay messages to avoid conflict noise. Relay files are append-only per
   thread; conflicts should be rare.
4. **Keep payloads out.** Logs over ~100 lines get trimmed to the relevant
   window. No model files, no captures, no secrets (tokens, IPs are fine —
   the tailnet IP is not a secret; the bearer token IS, reference its path
   instead).
5. Commit messages for relay-only commits: `relay: <type> <slug>`.
