# P4 verify battery green over tailnet — stabilization closed laptop-side

2026-07-16. Operator placed bearer token at `~/.config/phone-agent/token` on
volnix (64 bytes, mode 600); ran `phone-agent/scripts/verify.sh
http://100.101.229.9:8462` from volnix: **ALL PASS 5/5** (health 200,
bad-bearer 401, 7-tool tools/list, ping, embed 384-dim unit-norm) against the
supervised post-bootstrap server. Satisfies relay
`to-laptop/20260717-runtime-stabilization-done.md` ask #2. Relay confirmation
to-phone not yet filed (needs commit+push — pending user go-ahead). This
unblocks Phase 2 (capture tools).

## Infra state (volnix)

- `microvm@tailscale` was found inactive (lost at reboot); operator started it
  and flipped autostart=true in `~/.nix-config/nixos/vms.nix`; `make switch`
  pending after this session.
- Host route `100.64.0.0/10 via 192.168.101.2 dev vm-tailscale` re-added
  **manually** — still not declared in vms.nix (no `routes` stanza under
  `systemd.network.networks."11-tailscale-tap"`). Will vanish on next reboot
  unless declared. vms.nix still uncommitted (existing infra todo).
- P4 battery is a per-merge gate, so both gaps recur every reboot until the
  declarative fix lands.

## Todo deltas

- P0–P4 stabilization: complete (phone report + laptop tailnet confirmation).
- Phase 2 core tasks: unblocked once relay confirmation is filed.
