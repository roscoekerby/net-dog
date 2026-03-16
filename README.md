# NetDog 🐕

> Your loyal companion for sniffing out network issues.

A lightweight, always-on-top Windows desktop widget that monitors your network health in real time. Sits unobtrusively on your desktop showing live ping, packet loss, signal strength, and on-demand speed test results.

---

## Features

### Three View Modes

**Minimal** — ultra-compact HUD pill (no window chrome)
```
● 12ms · 52↓  11↑  ›
```
- Status dot (green/amber/red), ping in ms, download ↓ and upload ↑ in Mbps
- Click `›` to expand

**Compact** — dark card with key metrics
- Connection type & network name
- Ping, packet loss, signal strength
- Last speed test results (download / upload)

**Detailed** — full diagnostics
- All compact metrics plus local IP, public IP
- Live ping trend graph (filled area + smooth line)
- Speed test timestamp

Cycle between views by clicking the toggle button or right-clicking for the context menu.

---

### Network Monitoring
- **Ping** — 3 pings per cycle per target, reports the **median** (eliminates single-packet false spikes)
- **Packet loss** — tracked across all ping attempts, shown as a percentage with red/green colour coding
- **Signal strength** — WiFi dBm (converted from Windows percentage), colour-coded
- **Connection type** — WiFi / Ethernet / Disconnected
- **Public IP** — cached, refreshes every 5 minutes
- **netsh caching** — WiFi data cached for 10 seconds, eliminating redundant subprocess calls

### Speed Testing
- **On-demand** — click "Speed Test" button or right-click → Speed Test
- **Automatic** — runs silently every 15 minutes in the background
- Uses Cloudflare's speed test endpoints (no extra library needed)
- Results persist in the widget until the next test; timestamp shown in detailed view

### Stability
- **Thread watchdog** — monitoring thread is checked every 10 seconds and restarted automatically if it dies
- **Median ping** — 3× ping per target prevents false alerts from dropped packets
- **Cached subprocess calls** — netsh called once per 10s window, not twice per cycle

### Windows Auto-Start
Enable "Start with Windows" in Config → the app writes its own path to the Windows registry startup key. Re-applies on every launch so the path self-corrects after reinstalls. Only active when running as a built EXE.

---

## Running from Source

### Requirements
- Python 3.8+
- Dependencies:

```bash
pip install psutil requests
```

### Run
```bash
python netdog.py
```

---

## Building the EXE

### Quick build (recommended)
Double-click **`build.bat`** — it installs dependencies, cleans previous builds, and produces the EXE automatically.

### Manual build
```bash
pip install pyinstaller psutil requests pillow
pyinstaller NetDog.spec
```

Output: `dist\NetDog.exe`

The EXE is fully standalone — no Python installation required on the target machine.

> **Note:** Windows Defender may flag the EXE. This is a known PyInstaller false positive. Add an exclusion for the `dist\` folder in Windows Security if needed.

---

## Configuration

Right-click the widget → **Configuration**, or click the **Config** button.

| Setting | Default | Description |
|---|---|---|
| Ping Targets | 8.8.8.8, 1.1.1.1 | Hosts to ping each cycle |
| Ping Timeout | 3s | Per-ping timeout |
| Refresh Interval | 5s | How often to collect data |
| Opacity | 0.9 | Window transparency |
| Theme | Light | Light / Dark (UI chrome) |
| Default View | Compact | Starting view mode |
| Start with Windows | Off | Add to registry startup |

Config is saved to `~/.network_diagnostics_config.json`.

---

## Keyboard & Mouse

| Action | How |
|---|---|
| Drag window | Click and drag anywhere |
| Cycle view | Click toggle button (top-right) |
| Context menu | Right-click |
| Always on top | Right-click → Always on Top |
| Manual refresh | Right-click → Refresh Now, or Refresh button |
| Speed test | Right-click → Speed Test, or Speed Test button |
| Export data | Right-click → Export Data (saves `.txt` to Desktop) |
| Reset position | Right-click → Reset Position |

---

## Project Structure

```
net-dog/
├── netdog.py               # Main application (single file)
├── NetDog.spec             # PyInstaller build config
├── NetDog_icon_highres.ico # Application icon (multi-resolution)
├── build.bat               # One-click build script
├── BUILD.txt               # Build instructions
└── .planning/
    └── todos/              # GSD task tracking
```

---

## Tech Stack

| Component | Library |
|---|---|
| GUI | `tkinter` (stdlib) |
| System metrics | `psutil` |
| HTTP / speed test | `requests` |
| Ping / WiFi info | `subprocess` + Windows `netsh` |
| Auto-start | `winreg` (stdlib) |
| Build | `PyInstaller` |

---

## Status Colours

| Colour | Ping | Signal |
|---|---|---|
| 🟢 Green | < 50 ms | > -50 dBm |
| 🟡 Amber | 50–100 ms | -50 to -70 dBm |
| 🔴 Red | > 100 ms | < -70 dBm |

---

## License

MIT
