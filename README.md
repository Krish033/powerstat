<div align="center">

<img src="data/icons/powerstats.svg" width="96" alt="PowerStats Logo"/>

# PowerStats

**High-Fidelity Power Diagnostics and Analytics for Linux**

[![Version](https://img.shields.io/badge/version-1.0.0-orange?style=flat-square)](https://github.com/powerstats/powerstats/releases/tag/v1.0.0)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://python.org)
[![GTK](https://img.shields.io/badge/GTK-4.0-green?style=flat-square)](https://gtk.org)
[![CI](https://img.shields.io/github/actions/workflow/status/powerstats/powerstats/ci.yml?branch=master&style=flat-square&label=CI)](https://github.com/powerstats/powerstats/actions)
[![Issues](https://img.shields.io/github/issues/powerstats/powerstats?style=flat-square)](https://github.com/powerstats/powerstats/issues)

*PowerStats is a native Linux application that explains your system's power consumption in plain human language — not raw telemetry.*

</div>

---

## The Philosophy: Interpretation > Data

Linux has process viewers, terminal tools, and telemetry dashboards. It does **not** have emotionally understandable system behavior analytics.

PowerStats refuses to be "another system monitor." Instead of showing that Firefox used 40% CPU, it explains **why that matters**: *"Prevented idle sleep 17 times — estimated 25–40 minutes of battery impact."*

> **Goal**: Build an addictive, trustworthy "Activity Monitor + Power Doctor" for Linux.

---

## Features

- **Async startup** — analytics data loads on a background thread; the UI is responsive immediately
- **Diagnostic Insights Feed** — contextual warnings for thermal spikes, background drain, and daily comparisons
- **Top Battery Culprits** — identifies the top 2 highest-drain apps with behavioral explanations
- **Three time views** — Last 24 Hours, Last 7 Days, Total Usage (12 months)
- **Interactive bar charts** — click any bar to filter the app list to that time bucket
- **Stacked charts** — Other Apps / System Apps / Background color-coded per bar
- **Battery Aging Forecast** — reads `upower` capacity to show percentage of original design capacity remaining
- **Thermal Impact** — per-app peak temperature tracking with severity levels (🧊 Cool → 🚨 Throttling)
- **Non-linear power math** — `pow(cpu_time, 1.4) × freq_scaling` for realistic exponential curves
- **Intel RAPL support** — exact microjoule readings from `/sys/class/powercap/intel-rapl/` when available
- **Power Modes** — Balanced / Quiet / Analyze / Battery Saver polling intervals
- **Force Stop** with safety guard — disabled for critical processes, confirmation dialog for user apps
- **Transparency Model** — dedicated page explaining 🟢 Hardware Measured / 🟡 Estimated / 🔴 Low Confidence
- **Decoupled daemon** — `powerstats.service` collects data every 10s independent of the UI
- **WAL journal mode** — eliminates SQLite lock contention between daemon writes and UI reads
- **Auto-pruning** — data older than 7 days is purged hourly; database never bloats

---

## Screenshots

> *Run the app and take screenshots here. Add them as `docs/screenshots/` in the repo.*

| Main Dashboard | App Details | Transparency Model |
|---|---|---|
| *screenshot* | *screenshot* | *screenshot* |

---

## Install

### System Requirements

| Dependency | Purpose | Installed automatically by `.deb`? |
|---|---|---|
| Python 3.10+ | Runtime | ✅ |
| GTK 4.0 + Libadwaita 1.x | UI framework | ✅ |
| `python3-gi`, `python3-gi-cairo` | Python GObject bindings | ✅ |
| `python3-psutil` | Process metrics | ✅ |
| `upower` | Battery hardware info | ✅ |

### Option 1 — Download `.deb` from GitHub Releases (Recommended)

> Tested on Debian 12, Ubuntu 22.04+, Linux Mint 21+, and any derivative.

**Step 1.** Download the latest `.deb` from the [Releases page](https://github.com/powerstats/powerstats/releases/latest):

```bash
wget https://github.com/powerstats/powerstats/releases/latest/download/powerstats_1.0.0_all.deb
```

**Step 2.** Install:

```bash
sudo dpkg -i powerstats_1.0.0_all.deb
```

**Step 3.** If dependency errors appear, fix them:

```bash
sudo apt --fix-broken install
```

**Step 4.** Launch PowerStats:

- Open your **Applications menu** → search "PowerStats"
- Or run: `powerstats`

The background daemon starts automatically on your next login. To start it immediately:

```bash
systemctl --user daemon-reload
systemctl --user enable --now powerstats.service
```

---

### Option 2 — Build from source

```bash
# 1. Install dependencies
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-psutil upower

# 2. Clone
git clone https://github.com/powerstats/powerstats.git
cd powerstats/powerstats-1.0.0

# 3. Install (system-wide, requires sudo)
sudo bash scripts/install.sh

# 4. Or install via Makefile
sudo make install
```

### Option 3 — Run directly (no install)

```bash
git clone https://github.com/powerstats/powerstats.git
cd powerstats/powerstats-1.0.0

# Start the daemon manually
python3 daemon.py &

# Launch the UI
python3 main.py
```

---

## Uninstall

### If installed via `.deb`

```bash
sudo dpkg -r powerstats
```

To also remove your local telemetry database:

```bash
rm -f ~/.local/share/powerstats.db
```

### If installed via `make install`

```bash
sudo make uninstall
```

---

## Usage

### Dashboard

The main window shows three time views selectable from the dropdown:

- **Last 24 Hours** — hourly buckets for the past 24 hours
- **Last 7 Days** — daily buckets for the past week
- **Total Usage** — monthly buckets for the past 12 months

Click any bar in the chart to filter the app list to that time period. Click again to deselect.

### App Details

Click any app row to see:
- Behavioral impact explanation
- Estimated battery savings range
- Thermal impact (peak temperature during execution)
- Timeline analysis graph for that specific app
- Process-level breakdown

### Power Modes

Change the daemon's polling aggressiveness from Settings:

| Mode | Interval | Use Case |
|---|---|---|
| Balanced | 10s | Default |
| Quiet | 30s | Low overhead |
| Analyze | 5s | High-resolution debugging |
| Battery Saver | 60s | Minimal daemon impact |

---

## Configuration

User configuration is stored at `~/.config/powerstats/config.json`:

```json
{
  "power_mode": 0
}
```

| Key | Values | Default | Description |
|---|---|---|---|
| `power_mode` | `0–3` | `0` | Daemon polling interval (Balanced/Quiet/Analyze/Battery Saver) |

---

## Architecture

```
powerstats-1.0.0/
├── main.py              # Adw.Application entry point, startup logging
├── version.py           # Central version + app metadata
├── window.py            # ActivityWindow — async data load, navigation
├── usage_view.py        # UsageView (scrolled, chart + lists)
├── app_details.py       # AppDetailsPage (timeline, force stop)
├── analytics_data.py    # SQLite queries, bucket logic, comparison/aging
├── daemon.py            # Background telemetry collector (systemd service)
├── data/
│   └── icons/           # SVG app icon + symbolic icon
├── packaging/
│   ├── powerstats.desktop
│   └── powerstats.service
└── tests/
    └── test_analytics.py
```

### Data Flow

```
daemon.py  ──(10s polling)──►  ~/.local/share/powerstats.db (WAL SQLite)
                                          │
analytics_data.py  ◄──── background thread in window.py
                                          │
                               GLib.idle_add ──► UI update on GTK main thread
```

### Power Score Formula

```
freq_scaling  = avg_cpu_freq_mhz / 1000.0
scaled_cpu    = cpu_delta_seconds × freq_scaling
cpu_score     = pow(scaled_cpu, 1.4) × 10.0
wakeup_score  = wakeup_delta × 0.005
io_score      = io_bytes_delta × 0.000001
gpu_score     = 15.0 if gpu_active else 0.0
power_score   = cpu_score + wakeup_score + io_score + gpu_score
```

---

## Performance Notes

| Optimization | Impact |
|---|---|
| Analytics loaded on background thread | Eliminates startup freeze |
| `GLib.idle_add` for UI update | Thread-safe GTK access |
| `PRAGMA journal_mode=WAL` | Concurrent daemon + UI access without locks |
| Hourly database pruning | Bounded DB size, fast queries |
| 3 composite indexes on SQLite | Sub-100ms UI queries on large datasets |
| `power_score > 0.5` threshold | Filters idle processes, reduces DB writes by ~60% |

---

## Building & Packaging

### Run from source

```bash
python3 main.py
```

### System install

```bash
sudo make install
sudo make uninstall
```

### Linting

```bash
make lint
# or individually:
python3 -m flake8 *.py --max-line-length=120
python3 -m isort --check-only *.py
```

### Tests

```bash
make test
# or:
python3 -m pytest tests/ -v --tb=short
```

---

## Troubleshooting

**App shows "Loading…" spinner forever**
```bash
# Check if daemon is running and DB is being created
systemctl --user status powerstats.service
ls -lh ~/.local/share/powerstats.db
```

**"No activity recorded" in all views**
The daemon needs at least 1 polling cycle (10 seconds) to write the first snapshot. Wait a few seconds and reopen the app.

**High background drain from `powerstats-daemon` itself**
Switch to "Battery Saver" mode in the Power Mode setting. This changes polling to 60s intervals.

**Intel RAPL data unavailable**
RAPL requires root access on most kernels. Without it, PowerStats uses the non-linear CPU heuristic automatically — no action needed.

**Daemon not starting after reboot**
```bash
systemctl --user daemon-reload
systemctl --user enable powerstats.service
systemctl --user start powerstats.service
```

---

## FAQ

**Q: Does PowerStats send any data to the internet?**  
A: No. All telemetry is stored locally in `~/.local/share/powerstats.db`. No network calls are made.

**Q: Why are the numbers "estimates" and not exact?**  
A: Exact hardware measurement requires Intel RAPL (needs elevated permissions on most systems). Without it, PowerStats uses a non-linear CPU/frequency heuristic. The "Transparency Model" page explains what confidence level your system uses.

**Q: Can I use it on AMD CPUs?**  
A: Yes. AMD systems fall back to heuristic mode. AMD P-State RAPL support is planned for v1.1.

**Q: How much battery does the daemon itself use?**  
A: Approximately 0.1–0.5% per hour in Balanced mode. Switch to Battery Saver for 60s polling.

**Q: Is Wayland supported?**  
A: Yes. The UI is a native GTK4/Libadwaita app. However, Wayland sandboxing intentionally hides some process visibility — those are marked as "Low Confidence" in the Transparency Model.

---

## Roadmap

- [ ] v1.1 — AMD RAPL support, multi-battery aggregation (BAT0+BAT1)
- [ ] v1.1 — Suspend/resume drift detection via `systemd-inhibit`
- [ ] v1.2 — DBus notification for severe thermal events
- [ ] v1.2 — Flatpak portal integration for improved process visibility
- [ ] v2.0 — GNOME Shell extension for menubar quick stats
- [ ] v2.0 — Historical battery cycle count tracking

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

- Bug reports: [GitHub Issues](https://github.com/powerstats/powerstats/issues) with the `bug` label
- Feature requests: [GitHub Issues](https://github.com/powerstats/powerstats/issues) with the `enhancement` label
- Security issues: See [SECURITY.md](SECURITY.md)

---

## License

PowerStats is licensed under the **GNU General Public License v3.0**.  
See [LICENSE](LICENSE) for the full text.

---

## Author

Built with ❤️ for the Linux community.

---

## Credits

- Built with [GTK 4](https://gtk.org) and [Libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/)
- Power data from [Intel RAPL](https://www.kernel.org/doc/html/latest/power/powercap/powercap.html) and [UPower](https://upower.freedesktop.org/)
- Process metrics via [psutil](https://github.com/giampaolo/psutil)
- Charts rendered with [pycairo](https://pycairo.readthedocs.io/)
