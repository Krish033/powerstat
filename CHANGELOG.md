# Changelog

All notable changes to **PowerStats** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Nothing yet.

---

## [1.0.0] - 2024-05-01

### Added
- **Async startup**: Analytics data is now loaded on a background thread via `GLib.idle_add`, eliminating the UI freeze on launch. A spinner is shown while data loads.
- **Structured logging**: All modules now use Python's `logging` framework with a consistent `%(asctime)s [%(levelname)s] %(name)s: %(message)s` format. Startup timing is logged at INFO level.
- **Central version module** (`version.py`): Single source of truth for `__version__`, `__app_id__`, `__app_name__`, etc. Version is displayed in the window subtitle.
- **Professional app icon**: New SVG icon (`data/icons/powerstats.svg`) with energetic orange/dark-slate palette. Includes a symbolic variant for GNOME panel/headerbar.
- **Transparency Model page**: "View Transparency Model" button opens a dedicated page explaining `🟢 Hardware Measured`, `🟡 Estimated`, and `🔴 Low Confidence` data sources.
- **Diagnostic Feed**: Main view includes an "Insights Feed" with contextual warnings (thermal spikes, background drain, battery aging forecast, daily comparisons).
- **Top Battery Culprits** section: Highlights the top 2 highest-drain applications with human-readable behavioral explanations.
- **Timeline Analysis graph** on app details page: Click-to-select bucket interaction with per-bucket usage breakdown.
- **Battery Aging Forecast**: Reads `upower` capacity data and displays percentage of original design capacity remaining.
- **Power Modes**: Combo row to switch between Balanced / Quiet / Analyze / Battery Saver polling intervals. Setting persisted to `~/.config/powerstats/config.json`.
- **Force Stop** with safety guard: Disabled for critical system processes (`gnome-shell`, `systemd`, `pipewire`, etc.). Confirmation dialog for user apps.
- **Non-linear power math engine**: `pow(cpu_time, 1.4) * freq_scaling_factor` for realistic exponential power curves.
- **Intel RAPL support**: Reads exact microjoule consumption from `/sys/class/powercap/intel-rapl/`, falls back gracefully without root.
- **Duration accuracy fix**: Observed time span used instead of full bucket width to prevent overcounting when daemon wasn't running for the entire bucket period.
- **WAL journal mode**: `PRAGMA journal_mode=WAL` eliminates lock contention between daemon writes and UI reads.
- **Database auto-pruning**: Data older than 7 days is purged every hour to prevent unbounded SQLite growth.
- **Cascading foreign keys**: `process_stats` entries are auto-deleted via `ON DELETE CASCADE` when their parent `snapshots` row is pruned.
- **Performance indexes**: `idx_snapshots_timestamp`, `idx_process_stats_snapshot_id`, `idx_process_stats_name` for fast UI queries.
- **systemd user service** (`packaging/powerstats.service`): Daemon runs persistently in the background with `Restart=on-failure`.
- **Tests** (`tests/test_analytics.py`): 7 unit tests covering empty DB, chronological buckets, categorization, partial/full bucket duration, 12-month labels, `start_time_dt` presence, and numeric battery usage.
- **GitHub community files**: `LICENSE` (GPL-3.0), `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue templates, PR template.
- **GitHub Actions CI** (`.github/workflows/`): lint, test, and release workflows.

### Changed
- App ID changed from `com.example.PowerStats` to `io.github.powerstats.PowerStats`.
- All inline `import json`, `import os`, `import subprocess` moved to module-level top-of-file imports.
- `Makefile` now supports `make lint`, `make test`, `make clean` targets and reads version dynamically.
- `.desktop` file updated with `GenericName`, `StartupWMClass`, and expanded `Keywords`.
- `packaging/powerstats.service` now logs to systemd journal with `SyslogIdentifier=powerstats-daemon`.
- README completely rewritten with professional structure, badges, architecture overview, and usage examples.

### Fixed
- `_on_power_mode_changed` no longer uses inline imports.
- `AppDetailsPage` header bar now shows the app name instead of "PowerStats" (which was confusing when viewing a specific app's details).

---

## [0.1.0] - 2024-01-15

### Added
- Initial prototype with basic process listing.
- SQLite persistence with manual snapshot collection.

[Unreleased]: https://github.com/powerstats/powerstats/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/powerstats/powerstats/releases/tag/v1.0.0
[0.1.0]: https://github.com/powerstats/powerstats/releases/tag/v0.1.0
