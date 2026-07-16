# Laptop follow-ups on phone Phase-1 handoff (claude-laptop, 2026-07-15)

Actioned the four items surfaced by the phone's pulled relay/inbox notes
(commits through bdad36d). Phone is live testing Phase 1 (downloading models),
so no push from laptop — the memd curator commit and these notes stay local
until the phone yields the branch.

- **Phase-1 doc path fix (DONE, traces to D2).** `phase-1-npu-inference.md`
  used `~/.config/phone-agent/models/` in the Model File Sources block (mkdir +
  two wget targets) and `cd ~/.config/phone-agent` in the Test Procedure. Both
  contradict D2 (models root = `~/phone-agent/models/`; `.config/phone-agent/`
  is config+token only, code-in-config explicitly rejected) and the doc's own
  File Structure block. Fixed all four to `~/phone-agent/...`. Doc now grep-
  clean of `.config/phone-agent`.

- **Live :8462 server (item 3 — CORRECTED; PHONE/OPERATOR action).** Earlier
  read was "fix live, nothing owed." Phone screenshots (20:36) supersede that:
  the currently-running :8462 server predates the `~/phone-agent-runtime`
  rebuild and needs a **native relaunch with
  `LD_LIBRARY_PATH=$HOME/phone-agent-runtime/lib`** (+ `termux-wake-lock`) —
  the phone lists it as an operator TODO. The 6ef93cc bearer fix is in the code
  (verified on loopback:18462), but the running server is stale until that
  relaunch. Phone/operator action; not laptop-executable.

- **Native Termux launch gate (item 2 — PHONE/OPERATOR, in progress).** The
  Phase-1 entry gate (genuinely-native launch, not proot-parented:
  `cd ~/mophoAgent/phone-agent && .venv/bin/python main.py` from a native
  Termux session, ideally `termux-wake-lock`) is the operator run now underway
  as phone tests Phase 1. Not laptop-executable (bionic binaries). todo.md
  already tracks the prerequisite. No laptop action; watch relay for the
  gate-pass report.

- **Build landmines (item 1)** forwarded to
  `2026-07-15-termux-native-build-landmines.md` as requested by the relay note.
