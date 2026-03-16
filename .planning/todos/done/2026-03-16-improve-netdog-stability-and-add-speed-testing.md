---
created: 2026-03-16T16:08:07.290Z
title: Improve NetDog stability and add speed testing
area: general
files:
  - netdog.py
---

## Problem

NetDog has several stability issues that cause false alerts and UI jitter:
- Single ping per cycle causes false alarms on packet spikes
- Public IP fetched from api.ipify.org every 5s (unnecessary, can fail)
- `netsh` called every cycle (slow, causes UI jitter)
- Monitoring thread silently dies if it throws — UI freezes with stale data
- Download/upload speed fields are empty placeholders with no implementation

User shared a speedtest.net result and wants the app to be more stable and offer richer network insight comparable to what speedtest provides.

## Solution

**Stability fixes (quick wins):**
1. Ping 3x per cycle and use median to eliminate spike false alarms
2. Cache public IP for 60s, only refresh on network change
3. Cache netsh WiFi data for ~10s to reduce subprocess overhead
4. Add watchdog to restart monitoring thread on crash

**Speed testing:**
- Add on-demand speed test button using `speedtest-cli` Python library (~20s full test)
- Or quick throughput estimate: time download of small known file (~2s, can auto-run every N minutes)

**UI improvements:**
- Surface packet loss alongside ping (e.g., `12ms / 0%`)
- Show last speed test result persistently in compact/detailed view
