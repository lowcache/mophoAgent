# Phase 8: Laptop-Side Integration

**Target Agent:** Claude Code (laptop)
**Commit message:** `feat(laptop): NixOS module, mcp-gateway peer, proximity hooks, network routing`

---

## What You Are Building

The laptop-side of the phone agent integration. This is a NixOS module that:

1. Declares the phone as a known MCP gateway peer (via existing mcp-gateway)
2. Adds a systemd path unit that watches `~/ingest/staged/` on the phone over Tailscale
3. Adds niri lock/unlock hooks triggered by the phone's IMU proximity data
4. Adds net-gate microvm routing policy driven by the phone's modem state
5. Provides a `phone-agent` CLI tool for ad-hoc interaction

---

## Prerequisites

Phases 0-7 complete. The phone MCP server is running in Termux. Tailscale is working between phone and laptop.

---

## Where This Goes

In the **volnixos Nix flake** repo: https://github.com/lowcache/volnixos

```
volnixos/
├── flake.nix                             # MODIFIED: add phone-agent input
├── nixos/
│   ├── configuration.nix                 # MODIFIED: import phone-agent module
│   ├── phone-agent/
│   │   ├── default.nix                   # NEW: main module entry point
│   │   ├── mcp-gateway.nix               # NEW: MCP gateway peer config
│   │   ├── ingest-watcher.nix            # NEW: systemd path unit for staged files
│   │   ├── proximity.nix                 # NEW: niri lock/unlock hooks
│   │   ├── network-routing.nix           # NEW: net-gate routing from modem data
│   │   └── README.md                     # NEW: setup + phone-side bootstrap guide
└── docs/
    └── phone-agent.md                    # NEW: documentation
```

---

## Implementation Spec

### 1. NixOS Module Structure

**`nixos/phone-agent/default.nix`**

```nix
{ config, lib, pkgs, ... }:

let
  cfg = config.phone-agent;
in {
  options.phone-agent = {
    enable = lib.mkEnableOption "Phone agent (Galaxy S26 Ultra MCP integration)";
    
    phoneTailscaleIP = lib.mkOption {
      type = lib.types.str;
      default = "100.x.x.x";  # Set this after phone is on Tailscale
      description = "Tailscale IP of the phone MCP server";
    };

    enableProximityLock = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Enable phone-proximity-based laptop lock/unlock";
    };

    enableNetworkRouting = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Enable phone-modem-driven network routing policy";
    };

    enableIngestWatcher = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Watch ~/ingest/staged/ for new phone agent outputs";
    };
  };

  config = lib.mkIf cfg.enable {
    imports = [
      ./mcp-gateway.nix
      ./ingest-watcher.nix
      ./proximity.nix
      ./network-routing.nix
    ];
  };
}
```

### 2. MCP Gateway Registration

**`nixos/phone-agent/mcp-gateway.nix`**

Registers the phone MCP server as a known peer in the existing mcp-gateway.

```nix
{ config, lib, pkgs, ... }:

let
  cfg = config.phone-agent;
in {
  # This assumes mcp-gateway is already configured elsewhere in the flake.
  # The phone agent is added as an additional MCP node.

  # The exact integration depends on how mcp-gateway's configuration is structured.
  # Add a peer entry like:
  # phone-agent:
  #   transport: sse
  #   url: http://${cfg.phoneTailscaleIP}:8462/sse
  #   env:
  #     AUTH_TOKEN: "<bearer-token>"
  #   tools:
  #     - phone.*
}
```

**Note:** The exact mcp-gateway config format depends on the existing mcp-gateway setup in the flake. This file should:
1. Read the existing gateway config
2. Append the phone agent as a peer with `phone.*` tool namespace
3. Ensure tool namespacing doesn't conflict with existing tools

### 3. Ingest Watcher

**`nixos/phone-agent/ingest-watcher.nix`**

A systemd path unit that watches for new staged files from the phone.

```nix
{ config, lib, pkgs, ... }:

let
  phoneIngestDir = "${config.home.homeDirectory}/ingest/staged";
in {
  systemd.user = {
    services.phone-ingest-watcher = {
      Unit = {
        Description = "Watch phone agent ingest directory for new files";
      };
      Service = {
        Type = "oneshot";
        ExecStart = "${pkgs.bash}/bin/bash ${./scripts/ingest-watcher.sh}";
      };
    };

    paths.phone-ingest-watcher = {
      Unit = {
        Description = "Path watcher for phone agent ingest";
      };
      Path = {
        PathExistsGlob = "${phoneIngestDir}/*.json";
        Unit = "phone-ingest-watcher.service";
      };
      Install = {
        WantedBy = [ "default.target" ];
      };
    };
  };
}
```

**`scripts/ingest-watcher.sh`** (referenced above):

```bash
#!/usr/bin/env bash
# Process new staged files from the phone agent.
# Called by systemd path unit when new files appear in ~/ingest/staged/

set -euo pipefail

WATCH_DIR="$HOME/ingest/staged"
PROCESSED_DIR="$HOME/ingest/processed"  # Local copy, not phone's processed

for staged_file in "$WATCH_DIR"/*.json; do
    [ -f "$staged_file" ] || continue
    
    # Read the staged file to determine type
    TYPE=$(jq -r '.pipeline // "unknown"' "$staged_file")
    
    case "$TYPE" in
        audio_transcript)
            # Transcript arrived - move to local memd inbox or notify agent
            TARGET_DIR="$PROCESSED_DIR/transcripts"
            ;;
        image_ocr)
            TARGET_DIR="$PROCESSED_DIR/ocr"
            ;;
        share_extract)
            TARGET_DIR="$PROCESSED_DIR/summaries"
            ;;
        *)
            TARGET_DIR="$PROCESSED_DIR/other"
            ;;
    esac
    
    mkdir -p "$TARGET_DIR"
    mv "$staged_file" "$TARGET_DIR/"
    
    # Notify Claude Code agent (if running) via a trigger file or socket
    echo "Phone agent produced new $TYPE output: $(basename $staged_file)" \
        >> "$HOME/.local/share/phone-agent/new_ingest.log"
done
```

### 4. Proximity Hooks (niri lock/unlock)

**`nixos/phone-agent/proximity.nix`**

A daemon that periodically queries `phone.sensor.read_imu` on the phone and takes action based on the activity inference.

```nix
{ config, lib, pkgs, ... }:

let
  cfg = config.phone-agent;
  proximity-script = pkgs.writeShellScriptBin "phone-proximity-daemon" ''
    #!/usr/bin/env bash
    # Poll phone IMU every 5 seconds.
    # On "walking" or "in_pocket" transition from "on_desk" → lock laptop.
    # On "on_desk" transition from "walking" or "in_pocket" → unlock laptop.
    
    TOKEN=$(cat ~/.config/phone-agent/token)
    
    while true; do
        # Query phone IMU via MCP HTTP Client
        RESPONSE=$(python ~/.config/phone-agent/client.py --host ${cfg.phoneTailscaleIP} --port 8462 --token "$TOKEN" call "phone.sensor.read_imu" '{"sample_count":10}' 2>/dev/null)
        
        STATE=$(echo "$RESPONSE" | jq -r '.result.inference // "unknown"')
        
        case "$STATE" in
            walking|in_pocket)
                if [ "$PREV_STATE" = "on_desk" ] || [ "$PREV_STATE" = "stationary" ]; then
                    # User just walked away from desk → lock
                    if command -v niri &> /dev/null; then
                        niri msg action lock-screen
                    fi
                    logmsg "LOCK: activity changed $PREV_STATE → $STATE"
                fi
                ;;
            on_desk|stationary)
                if [ "$PREV_STATE" = "walking" ] || [ "$PREV_STATE" = "in_pocket" ]; then
                    # User just sat down at desk → unlock
                    if command -v niri &> /dev/null; then
                        niri msg action unlock-screen
                    fi
                    logmsg "UNLOCK: activity changed $PREV_STATE → $STATE"
                fi
                ;;
        esac
        
        PREV_STATE="$STATE"
        sleep 5
    done
  '';
in {
  systemd.user.services.phone-proximity-daemon = lib.mkIf cfg.enableProximityLock {
    Unit = {
      Description = "Phone proximity-based laptop lock/unlock daemon";
    };
    Service = {
      Type = "simple";
      ExecStart = "${proximity-script}/bin/phone-proximity-daemon";
      Restart = "on-failure";
      RestartSec = 10;
    };
    Install = {
      WantedBy = [ "default.target" ];
    };
  };
}
```

### 5. Network Routing

**`nixos/phone-agent/network-routing.nix`**

Periodically queries the phone's modem state and adjusts the net-gate microvm routing policy.

```nix
{ config, lib, pkgs, ... }:

let
  cfg = config.phone-agent;
  routing-script = pkgs.writeShellScriptBin "phone-network-routing" ''
    # This script is called by the Subconscious Scheduler task
    # "geofence_change_detect" when the phone detects a BSSID/geofence transition.
    
    # Query phone modem state via MCP HTTP Client
    TOKEN=$(cat ~/.config/phone-agent/token)
    RESPONSE=$(python ~/.config/phone-agent/client.py --host ${cfg.phoneTailscaleIP} --port 8462 --token "$TOKEN" call "phone.sensor.read_modem" '{}' 2>/dev/null)
    
    SSID=$(echo "$RESPONSE" | jq -r '.result.ssid // "unknown"')
    NETWORK_TYPE=$(echo "$RESPONSE" | jq -r '.result.network_type // "unknown"')
    
    case "$SSID" in
        "HomeWiFi"|"MyHomeNetwork")
            # Home network - direct routing
            ${pkgs.systemd}/bin/systemctl --user set-environment PHONE_NETWORK_PROFILE=home
            # Notify net-gate if running
            ssh -o ConnectTimeout=2 volnix-tailscale '
                # In net-gate microvm: switch to direct routing
                iptables -F && iptables -P ACCEPT
            ' 2>/dev/null || true
            ;;
        "CoffeeShop_WiFi"|"University_WiFi")
            # Untrusted network - route specific traffic through Tor net-gate
            ${pkgs.systemd}/bin/systemctl --user set-environment PHONE_NETWORK_PROFILE=untrusted
            ;;
        *)
            # Unknown WiFi or cellular - route everything through Tailscale + net-gate
            ${pkgs.systemd}/bin/systemctl --user set-environment PHONE_NETWORK_PROFILE=secure
            ;;
    esac
  '';
in {
  # This script is called by the phone agent's scheduler.
  # The phone-side "geofence_change_detect" task fires every 15 minutes
  # and calls this script via MCP if the geofence changed.
  
  # Additionally, expose a systemd service that can be triggered by a socket:
  systemd.user.services.phone-network-routing = lib.mkIf cfg.enableNetworkRouting {
    Unit = {
      Description = "Update network routing based on phone modem state";
    };
    Service = {
      Type = "oneshot";
      ExecStart = "${routing-script}/bin/phone-network-routing";
    };
  };
}
```

### 6. CLI Tool

**`scripts/phone-agent.sh`** — A simple CLI for ad-hoc interaction:

```bash
#!/usr/bin/env bash
# phone-agent CLI — interact with the phone MCP server from the laptop
# Usage: phone-agent <tool-name> [arguments-json]

PHONE_IP="100.x.x.x"  # Replace with actual phone Tailscale IP
TOKEN=$(cat ~/.config/phone-agent/token)

if [ $# -lt 1 ]; then
    echo "Usage: phone-agent <tool-name> [arguments-json]"
    echo "Example: phone-agent phone.sensor.read_imu"
    echo "         phone-agent phone.npu.transcribe '{\"audio_path\":\"/tmp/test.wav\"}'"
    exit 1
fi

TOOL_NAME="$1"
ARGUMENTS="${2:-{}}"

# Assuming a Python client script `client.py` handles the SSE connection
python ~/.config/phone-agent/client.py --host "$PHONE_IP" --port 8462 --token "$TOKEN" call "$TOOL_NAME" "$ARGUMENTS"
```

---

## Setup Instructions (README.md content)

```markdown
# Phone Agent Setup

## Prerequisites
1. Install Termux on the S26 Ultra
2. Install Shizuku and keep it running
3. Install Termux:API
4. Join both devices to the same Tailscale network

## Phone Setup
1. Copy `~/.config/phone-agent/` to the phone:
   ```bash
   rsync -avz ~/.config/phone-agent/ phone-tailscale-ip:~/.config/phone-agent/
   ```
2. On the phone, install dependencies:
   ```bash
   pkg install python uv
   cd ~/.config/phone-agent
   uv venv && uv sync
   ```
3. Download models:
   ```bash
   cd ~/.config/phone-agent/models/
   wget <model-urls>
   ```
4. Set up Automate flow to start the server on boot:
   - Import `mcp-server-start.flow`
   - Ensure Termux has notification access (for background execution)

5. Start the server:
   ```bash
   cd ~/.config/phone-agent && python main.py
   ```

## Laptop Setup (NixOS)
1. Add `phone-agent.enable = true;` to `nixos/configuration.nix`
2. Set `phone-agent.phoneTailscaleIP` to the phone's Tailscale IP
3. Copy the Bearer token from the phone to `~/.config/phone-agent/token`
4. Rebuild: `make switch`
5. Test: `phone-agent phone.sensor.read_imu`

## Testing the Connection
```bash
# From laptop, verify phone MCP server is reachable
python ~/.config/phone-agent/client.py --host phone-tailscale-ip --port 8462 --token $(cat ~/.config/phone-agent/token) list

# Test a sensor
phone-agent phone.sensor.read_imu
```
```

---

## Test Procedure

1. **NixOS build test:**
   ```bash
   make check  # Should pass
   make build  # Should build without errors
   ```

2. **MCP connectivity:**
   ```bash
   # From laptop, verify the phone MCP server responds
   phone-agent phone.system.ping
   ```
   → `{"status": "ok", "timestamp": "...", "uptime_sec": ...}`

3. **Ingest watcher:**
   - On the phone (or via CLI): `phone-agent phone.capture.audio '{"max_duration_sec":5}'`
   - Speak for 3 seconds
   - Wait for pipeline to complete
   - On the laptop: check `~/ingest/staged/` for the transcript file
   - Verify systemd path unit fires and moves it to `~/ingest/processed/`

4. **Proximity lock:**
   - Start proximity daemon: `systemctl --user start phone-proximity-daemon`
   - Place phone on desk → verify laptop is unlocked (if it was locked)
   - Pick up phone and walk away → verify laptop locks within 10 seconds
   - Return to desk, place phone down → verify laptop unlocks within 10 seconds

5. **Network routing:**
   - Enable network routing: `systemctl --user start phone-network-routing`
   - Change phone WiFi from home to cellular
   - Verify net-gate routing policy changes accordingly

---

## Acceptance Criteria

- [ ] NixOS module builds without errors on `make build`
- [ ] `phone-agent` CLI tool successfully calls phone MCP tools
- [ ] Ingest watcher systemd path unit detects new staged files and processes them
- [ ] Proximity daemon locks laptop when phone leaves desk (within 15s)
- [ ] Proximity daemon unlocks laptop when phone returns to desk (within 15s)
- [ ] Network routing service updates based on phone modem state
- [ ] All services survive `systemctl --user restart` and auto-start on boot

---

## Guardrails

- **Proximity lock is not a security boundary.** It's a convenience feature. If the proximity daemon fails, the laptop should fall back to the existing screen lock timeout. Proximity is a *supplement*, not a replacement.
- **Network routing never routes through the phone as a gateway.** The phone is a *policy sensor*, not a network hop. The laptop routes directly or through the existing net-gate microvm.
- **Phone Tailscale IP is hardcoded in the NixOS config.** Tailscale IPs are stable (they're based on the node key). If the phone is rebuilt, the IP stays the same unless the Tailscale identity is reset.
- **All SSH connections to the phone use SSH keys.** If the phone doesn't have the laptop's SSH key, add it to `~/.ssh/authorized_keys` on the phone. Password auth is not configured.
- **The ingest watcher is unidirectional.** Phone → laptop only. The laptop never writes to the phone's filesystem. All communication goes through MCP tools.

---

## Git Commit

```bash
git add -A
git commit -m "feat(laptop): NixOS module, mcp-gateway peer, proximity hooks, network routing"
git tag phone-mcp-phase-8
```

Rollback: Remove `imports = [ ./phone-agent ];` from `nixos/configuration.nix`, revert the added files. `make switch` restores the previous state.
