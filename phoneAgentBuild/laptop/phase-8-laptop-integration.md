# Phase 8: Laptop-Side Integration

**Target Agent:** Claude Code (laptop)
**Commit message:** `feat(laptop): NixOS module, mcp-gateway peer, ingest sync, proximity lock, network routing`

---

## What You Are Building

The laptop-side of the phone agent integration. A NixOS module that:

1. Declares the phone as a known MCP gateway peer (HTTP MCP over Tailscale, port 8462 — no SSH, no stdio)
2. Runs an **ingest-sync** systemd timer that pulls staged files off the phone via `phone.ingest.list` / `phone.ingest.fetch` (D6) into the laptop's `~/ingest/staged/`
3. Runs a systemd **path unit** that processes locally-arrived staged files
4. Adds a niri **lock-only** hook driven by the phone's IMU activity (D7 — no programmatic unlock)
5. Adds net-gate microvm routing *policy* driven by the phone's modem/geofence state
6. Provides a `phone-agent` CLI over a shared curl helper

All phone connectivity is HTTP MCP to `http://<phoneTailscaleIP>:8462/mcp` with a bearer token read from a sops-nix secret. The phone holds no laptop keys; the laptop never SSHes the phone and never writes to the phone's filesystem.

---

## Prerequisites

Phases 0-7 complete. The phone MCP server is running in Termux (FastMCP Streamable HTTP on the phone's Tailscale IP:8462). Tailscale is working between phone and laptop.

---

## Where This Goes

In the **volnixos Nix flake** repo: https://github.com/lowcache/volnixos

```
volnixos/
├── flake.nix                             # MODIFIED: (only if packaging the module as an input)
├── nixos/
│   ├── configuration.nix                 # MODIFIED: import phone-agent module
│   ├── phone-agent/
│   │   ├── default.nix                   # NEW: options + top-level imports
│   │   ├── mcp-gateway.nix               # NEW: HTTP MCP peer registration
│   │   ├── ingest-sync.nix               # NEW: timer pulling staged files (D6)
│   │   ├── ingest-watcher.nix            # NEW: path unit for locally-arrived files
│   │   ├── proximity.nix                 # NEW: niri lock-only hook (D7)
│   │   ├── network-routing.nix           # NEW: net-gate routing policy from modem data
│   │   ├── scripts/
│   │   │   ├── phone-mcp-call.sh          # NEW: shared curl helper
│   │   │   └── ingest-watcher.sh          # NEW: local staged-file processor
│   │   └── README.md                     # NEW: setup + phone-side bootstrap pointer
└── docs/
    └── phone-agent.md                    # NEW: documentation
```

---

## Implementation Spec

### 0. Shared curl helper — `scripts/phone-mcp-call.sh`

Every laptop→phone interaction goes through this. No SSH, no per-call server spawn.

```bash
#!/usr/bin/env bash
# phone-mcp-call.sh TOOL [ARGS_JSON]
# Env: PHONE_IP (Tailscale IP), PHONE_PORT (default 8462), PHONE_TOKEN_FILE
set -euo pipefail
TOOL="$1"; ARGS="${2:-{}}"
PORT="${PHONE_PORT:-8462}"
TOKEN="$(cat "${PHONE_TOKEN_FILE:?set PHONE_TOKEN_FILE}")"

curl -sf --max-time "${PHONE_TIMEOUT:-10}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"${TOOL}\",\"arguments\":${ARGS}}}" \
  "http://${PHONE_IP}:${PORT}/mcp"
```

A `/health` reachability probe (`curl -sf http://$PHONE_IP:$PORT/health`) gates the timer/daemon so they no-op silently when the phone is offline.

### 1. NixOS Module — `phone-agent/default.nix`

`imports` is **top-level** (never inside `config = mkIf …`, which is an eval error). Each sub-feature file gates itself on its own `cfg.enable*` with `mkIf`.

```nix
{ config, lib, pkgs, ... }:
let cfg = config.phone-agent;
in {
  imports = [
    ./mcp-gateway.nix
    ./ingest-sync.nix
    ./ingest-watcher.nix
    ./proximity.nix
    ./network-routing.nix
  ];

  options.phone-agent = {
    enable = lib.mkEnableOption "Phone agent (Galaxy S26 Ultra MCP integration)";

    phoneTailscaleIP = lib.mkOption {
      type = lib.types.str;
      description = "Tailscale IP of the phone MCP server (from the Tailscale Android app).";
    };
    port = lib.mkOption { type = lib.types.port; default = 8462; };
    tokenFile = lib.mkOption {
      type = lib.types.path;
      example = "config.sops.secrets.\"phone-agent-token\".path";
      description = "Path to the bearer token file (sops-nix secret; never world-readable).";
    };
    ollamaHost = lib.mkOption {
      type = lib.types.str;
      default = "volnix";
      description = "Hostname the phone uses to reach this laptop's Ollama (documentation only).";
    };
    ingestDir = lib.mkOption {
      type = lib.types.str;
      default = "/home/lowcache/ingest";
      description = "Laptop-side ingest directory that mirrors staged phone output.";
    };

    enableIngestSync   = lib.mkOption { type = lib.types.bool; default = true; };
    enableIngestWatcher = lib.mkOption { type = lib.types.bool; default = true; };
    enableProximityLock = lib.mkOption {
      type = lib.types.bool; default = true;
      description = "Lock the laptop when the phone leaves the desk (lock only — no auto-unlock).";
    };
    enableNetworkRouting = lib.mkOption { type = lib.types.bool; default = false; };
  };

  # No `config` block here beyond assertions; feature config lives in the imported files.
  config = lib.mkIf cfg.enable {
    assertions = [{
      assertion = cfg.tokenFile != null;
      message = "phone-agent.tokenFile must be set (sops-nix secret path).";
    }];
  };
}
```

### 2. MCP Gateway Registration — `mcp-gateway.nix`

mcp-gateway's backend config is hand-edited YAML (`~/.config/mcp-gateway/gateway.yaml`), not nix-managed. So this file is mostly documentation plus an assertion; the laptop agent wires the actual entry into however the gateway config is managed on this host.

Target gateway entry (HTTP MCP backend):

```yaml
# ~/.config/mcp-gateway/gateway.yaml  (hand-edited)
backends:
  phone-agent:
    transport: http
    url: http://<phoneTailscaleIP>:8462/mcp
    headers:
      Authorization: "Bearer <token>"   # from phone-agent.tokenFile
    namespace: phone            # tools appear as phone.*
```

```nix
{ config, lib, ... }:
let cfg = config.phone-agent;
in {
  config = lib.mkIf cfg.enable {
    # gateway.yaml is hand-managed; surface the required values for the operator.
    environment.etc."phone-agent/gateway-peer.example.yaml".text = ''
      backends:
        phone-agent:
          transport: http
          url: http://${cfg.phoneTailscaleIP}:${toString cfg.port}/mcp
          # Authorization header value = "Bearer $(cat ${toString cfg.tokenFile})"
          namespace: phone
    '';
    warnings = lib.optional true
      "phone-agent: add the phone-agent backend to ~/.config/mcp-gateway/gateway.yaml (see /etc/phone-agent/gateway-peer.example.yaml).";
  };
}
```

### 3. Ingest Sync — `ingest-sync.nix` (the transfer mechanism, D6)

A user timer that pulls staged files off the phone. This is what actually moves data laptop-ward; nothing else does.

```nix
{ config, lib, pkgs, ... }:
let
  cfg = config.phone-agent;
  syncScript = pkgs.writeShellScript "phone-ingest-sync" ''
    set -euo pipefail
    export PHONE_IP=${cfg.phoneTailscaleIP} PHONE_PORT=${toString cfg.port}
    export PHONE_TOKEN_FILE=${toString cfg.tokenFile}
    call=${./scripts/phone-mcp-call.sh}
    dest="${cfg.ingestDir}/staged"; mkdir -p "$dest"

    # Skip silently if the phone is unreachable.
    curl -sf --max-time 3 "http://$PHONE_IP:$PHONE_PORT/health" >/dev/null || exit 0

    listing=$("$call" phone.ingest.list '{"since":null,"limit":50}')
    echo "$listing" | ${pkgs.jq}/bin/jq -c '.result.files[]?' | while read -r f; do
      name=$(echo "$f" | ${pkgs.jq}/bin/jq -r .name)
      want=$(echo "$f" | ${pkgs.jq}/bin/jq -r .sha256)
      [ -e "$dest/$name" ] && continue
      payload=$("$call" phone.ingest.fetch "{\"name\":\"$name\",\"delete_after\":true}")
      echo "$payload" | ${pkgs.jq}/bin/jq -r '.result.content_b64' | base64 -d > "$dest/.tmp.$name"
      got=$(sha256sum "$dest/.tmp.$name" | cut -d' ' -f1)
      if [ "$got" = "$want" ]; then mv "$dest/.tmp.$name" "$dest/$name";
      else rm -f "$dest/.tmp.$name"; echo "sha mismatch for $name" >&2; fi
    done
  '';
in {
  config = lib.mkIf (cfg.enable && cfg.enableIngestSync) {
    systemd.user.services.phone-ingest-sync = {
      Unit.Description = "Pull staged files from the phone agent (MCP ingest.list/fetch)";
      Service = { Type = "oneshot"; ExecStart = "${syncScript}"; };
    };
    systemd.user.timers.phone-ingest-sync = {
      Unit.Description = "Periodic phone ingest sync";
      Timer = { OnBootSec = "2min"; OnUnitActiveSec = "2min"; };
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
```

`phone.ingest.fetch` with `delete_after:true` moves the phone-side file to `~/ingest/delivered-staged/` (D6), so each file transfers once.

### 4. Ingest Watcher — `ingest-watcher.nix`

Path unit that fires when files land in the laptop's staged dir. NixOS `systemd.user.*` uses lowercase `serviceConfig`/`wantedBy` (this is a NixOS module, not home-manager).

```nix
{ config, lib, pkgs, ... }:
let cfg = config.phone-agent;
in {
  config = lib.mkIf (cfg.enable && cfg.enableIngestWatcher) {
    systemd.user.services.phone-ingest-watcher = {
      description = "Process staged phone-agent files";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${pkgs.bash}/bin/bash ${./scripts/ingest-watcher.sh} ${cfg.ingestDir}";
      };
    };
    systemd.user.paths.phone-ingest-watcher = {
      description = "Watch phone-agent staged dir";
      pathConfig = { PathExistsGlob = "${cfg.ingestDir}/staged/*.json"; Unit = "phone-ingest-watcher.service"; };
      wantedBy = [ "default.target" ];
    };
  };
}
```

`scripts/ingest-watcher.sh` (takes `$1 = ingestDir`):

```bash
#!/usr/bin/env bash
set -euo pipefail
INGEST_DIR="${1:?}"
WATCH_DIR="$INGEST_DIR/staged"
PROCESSED_DIR="$INGEST_DIR/processed"
for staged_file in "$WATCH_DIR"/*.json; do
    [ -f "$staged_file" ] || continue
    TYPE=$(jq -r '.pipeline // "unknown"' "$staged_file")
    case "$TYPE" in
        audio_transcript) TARGET="$PROCESSED_DIR/transcripts" ;;
        image_ocr)        TARGET="$PROCESSED_DIR/ocr" ;;
        share_extract)    TARGET="$PROCESSED_DIR/summaries" ;;
        *)                TARGET="$PROCESSED_DIR/other" ;;
    esac
    mkdir -p "$TARGET"; mv "$staged_file" "$TARGET/"
    echo "$(date -Iseconds) new $TYPE: $(basename "$staged_file")" \
        >> "$HOME/.local/share/phone-agent/new_ingest.log"
done
```

### 5. Proximity Hook (lock only) — `proximity.nix`

Polls `phone.sensor.read_imu` via the curl helper. Locks on desk-departure. **No unlock** (D7): programmatic unlock of a session locker is not supported and killing the locker is a security hole, not a feature.

```nix
{ config, lib, pkgs, ... }:
let
  cfg = config.phone-agent;
  daemon = pkgs.writeShellScriptBin "phone-proximity-daemon" ''
    export PHONE_IP=${cfg.phoneTailscaleIP} PHONE_PORT=${toString cfg.port}
    export PHONE_TOKEN_FILE=${toString cfg.tokenFile}
    call=${./scripts/phone-mcp-call.sh}
    log() { ${pkgs.util-linux}/bin/logger -t phone-proximity "$1"; }
    PREV=""
    while true; do
      curl -sf --max-time 3 "http://$PHONE_IP:$PHONE_PORT/health" >/dev/null || { sleep ${toString cfg.proximityIntervalSec}; continue; }
      R=$("$call" phone.sensor.read_imu '{"sample_count":10}' 2>/dev/null || echo '{}')
      STATE=$(echo "$R" | ${pkgs.jq}/bin/jq -r '.result.inference // "unknown"')
      case "$STATE" in
        walking|in_pocket)
          if [ "$PREV" = "on_desk" ] || [ "$PREV" = "stationary" ]; then
            command -v niri >/dev/null && niri msg action lock-screen
            log "LOCK: $PREV -> $STATE"
          fi ;;
      esac
      ${lib.optionalString cfg.allowUnlock ''
        # EXPERIMENTAL and disabled by default. There is no safe programmatic
        # unlock; this block intentionally does nothing but log intent.
        case "$STATE" in on_desk|stationary)
          [ "$PREV" = "walking" ] || [ "$PREV" = "in_pocket" ] && log "UNLOCK-INTENT (no-op): $PREV -> $STATE" ;;
        esac
      ''}
      PREV="$STATE"; sleep ${toString cfg.proximityIntervalSec}
    done
  '';
in {
  options.phone-agent = {
    proximityIntervalSec = lib.mkOption { type = lib.types.int; default = 5; };
    allowUnlock = lib.mkOption {
      type = lib.types.bool; default = false;
      description = "EXPERIMENTAL: no safe programmatic unlock exists; leaving this on only logs intent.";
    };
  };
  config = lib.mkIf (cfg.enable && cfg.enableProximityLock) {
    systemd.user.services.phone-proximity-daemon = {
      description = "Phone proximity-based laptop lock (lock only)";
      serviceConfig = { ExecStart = "${daemon}/bin/phone-proximity-daemon"; Restart = "on-failure"; RestartSec = 10; };
      wantedBy = [ "default.target" ];
    };
  };
}
```

### 6. Network Routing — `network-routing.nix`

Derives a routing *profile* from the phone's modem/geofence state and hands it off; it does **not** flush iptables or route through the phone. `[CEILING]:` writes a profile file + starts a hook unit only; net-gate wiring is deferred.

```nix
{ config, lib, pkgs, ... }:
let
  cfg = config.phone-agent;
  script = pkgs.writeShellScriptBin "phone-network-routing" ''
    export PHONE_IP=${cfg.phoneTailscaleIP} PHONE_PORT=${toString cfg.port}
    export PHONE_TOKEN_FILE=${toString cfg.tokenFile}
    call=${./scripts/phone-mcp-call.sh}
    R=$("$call" phone.sensor.read_modem '{}' 2>/dev/null || echo '{}')
    SSID=$(echo "$R" | ${pkgs.jq}/bin/jq -r '.result.ssid // "unknown"')
    case "$SSID" in
      "HomeWiFi"|"MyHomeNetwork") PROFILE=home ;;
      "CoffeeShop_WiFi"|"University_WiFi") PROFILE=untrusted ;;
      *) PROFILE=secure ;;
    esac
    dir=/run/user/$(id -u)/phone-agent; mkdir -p "$dir"
    echo "$PROFILE" > "$dir/network-profile"
    # [CEILING]: profile file + optional hook only; net-gate microvm wiring TBD.
    systemctl --user start "phone-network-profile@$PROFILE.service" 2>/dev/null || true
  '';
in {
  config = lib.mkIf (cfg.enable && cfg.enableNetworkRouting) {
    systemd.user.services.phone-network-routing = {
      description = "Derive network routing profile from phone modem state";
      serviceConfig = { Type = "oneshot"; ExecStart = "${script}/bin/phone-network-routing"; };
    };
  };
}
```

### 7. CLI Tool — `phone-agent`

Thin wrapper over the curl helper. No hardcoded IPs/tokens in the body — they come from the environment the Nix wrapper sets.

```bash
#!/usr/bin/env bash
# phone-agent <tool-name> [arguments-json]
set -euo pipefail
if [ $# -lt 1 ]; then
  echo "Usage: phone-agent <tool-name> [arguments-json]"
  echo "  phone-agent phone.system.ping"
  echo "  phone-agent phone.npu.transcribe '{\"audio_path\":\"/tmp/test.wav\"}'"
  exit 1
fi
exec phone-mcp-call.sh "$@" | jq .
```

Package it with `pkgs.writeShellScriptBin` wrapping `PHONE_IP`/`PHONE_PORT`/`PHONE_TOKEN_FILE` from the module options via `--set`.

---

## Setup Instructions (README.md content)

```markdown
# Phone Agent Setup

## Prerequisites
1. Install Termux + Termux:API + Shizuku on the S26 Ultra
2. Join both devices to the same Tailscale network
3. Build the phone MCP server on-device with Claude Code — see
   phoneAgentBuild/phone/PHONE-ENV.md (the phone repo is built there, not
   rsynced from the laptop)

## Laptop Setup (NixOS)
1. Import the phone-agent module in nixos/configuration.nix and set:
     phone-agent.enable = true;
     phone-agent.phoneTailscaleIP = "100.x.y.z";   # from Tailscale Android app
     phone-agent.tokenFile = config.sops.secrets."phone-agent-token".path;
   The token value must match ~/.config/phone-agent/token on the phone.
2. Rebuild: make switch
3. Test: phone-agent phone.system.ping

## Testing the connection
    curl -sf http://<phoneTailscaleIP>:8462/health
    phone-agent phone.sensor.read_imu
```

---

## Test Procedure

1. **NixOS build:** `make check && make build` — module evaluates and builds.
2. **MCP connectivity:** `phone-agent phone.system.ping` → `{"status":"ok",...}`.
3. **Ingest sync (end-to-end):** on the phone, run a capture that produces a staged transcript; within ~2min confirm `ingest-sync` fetched it into `~/ingest/staged/` with a matching sha256, the phone moved its copy to `delivered-staged/`, and the path unit moved the laptop file into `~/ingest/processed/transcripts/`.
4. **Proximity lock:** start `phone-proximity-daemon`; pick up the phone and walk → laptop locks within ~15s. (No unlock test — unlock is not implemented.)
5. **Network routing:** start `phone-network-routing`; change the phone's WiFi → `/run/user/$UID/phone-agent/network-profile` updates.
6. **Fail-closed:** with `tokenFile` pointing at a missing/empty secret, calls fail (401) and the timer no-ops rather than crashing.

---

## Acceptance Criteria

- [ ] NixOS module builds without errors on `make build`
- [ ] `phone-agent` CLI successfully calls phone MCP tools over HTTP (no SSH)
- [ ] `ingest-sync` timer pulls a staged file end-to-end with sha256 verification; phone-side copy is removed after delivery
- [ ] Ingest watcher path unit moves locally-arrived staged files into `processed/`
- [ ] Proximity daemon LOCKS the laptop when the phone leaves the desk (within ~15s)
- [ ] Network routing service writes the derived profile file based on phone modem state
- [ ] Missing/empty token fails closed (401) without crashing services
- [ ] All services survive `systemctl --user restart` and auto-start on boot

---

## Guardrails

- **Proximity lock is not a security boundary.** It's a convenience supplement to the existing screen-lock timeout. If the daemon fails, the timeout still locks. There is no auto-unlock.
- **Network routing never routes through the phone.** The phone is a *policy sensor*, not a network hop. The laptop routes directly or through the existing net-gate microvm; this phase only derives a profile.
- **Phone Tailscale IP is config, not code.** Set via `phone-agent.phoneTailscaleIP`. Tailscale IPs are stable per node key.
- **The bearer token is a secret.** It comes from a sops-nix secret via `tokenFile`; never commit it, never make it world-readable. The token guards the phone's MCP surface against anything else on the tailnet.
- **The channel is unidirectional for data.** Phone → laptop for ingest. The laptop only *calls tools*; it never writes to the phone's filesystem.

---

## Git Commit

```bash
git add -A
git commit -m "feat(laptop): NixOS module, mcp-gateway peer, ingest sync, proximity lock, network routing"
git tag phone-mcp-phase-8
```

Rollback: Remove `imports = [ ./phone-agent ];` from `nixos/configuration.nix`, revert the added files. `make switch` restores the previous state.
