# 🔋 PowerStats

**PowerStats** is a professional-grade native Linux application designed to explain system power consumption and application activity like a normal human. Built with **Python**, **GTK4**, and **Libadwaita**.

![PowerStats Dashboard](/home/krishna/.gemini/antigravity/brain/cf8bc3ac-7c61-41ff-95da-cf3194fdbd6c/powerstats_dashboard_mockup_1778298743555.png)

## 🎯 The Thesis: Humane Diagnostics over Raw Telemetry
Linux already has process viewers, terminal tools, and telemetry dashboards. It does *not* have emotionally understandable system behavior analytics. 

PowerStats refuses to be "another system monitor." Our core philosophy is **Interpretation > Data**. We don't just show that Firefox used 40% CPU; we explain *why* that matters (e.g., *"Prevented idle sleep 17 times"*). The goal is to build an addictive, trustworthy "Activity Monitor + Power Doctor."

---

## 📈 Current Project Status (V2 Production-Ready)

Technically, PowerStats is mature and architecturally excellent. We have successfully moved from a prototype to a resilient, self-cleaning background engine.

### ✅ What is Completed & Perfectly Working
*   **The Analytics Architecture:** A decoupled `powerstats.service` daemon collects system states every 10 seconds independently of the UI.
*   **Resilient SQLite Persistence:** Uses `PRAGMA journal_mode=WAL` to eliminate lock contention between daemon writes and UI reads. Auto-pruning guarantees the database never spirals out of control.
*   **Process Instability Safety:** The `/proc` parser assumes every process can die instantaneously, gracefully catching exceptions to prevent daemon crashes.
*   **Nonlinear Math Engine:** We dropped linear heuristics. A 10% CPU load at 4.5GHz generates an exponentially higher power score than 10% at 800MHz (using `pow(cpu_time, 1.4)` scaled by CPU frequency).
*   **Hardware Fallbacks:** Reads directly from Intel RAPL for actual CPU package microjoules, falling back gracefully via `PermissionError` handling if root access is denied.
*   **Safety First UI:** The "Force Stop" button is neutralized for critical system processes (`gnome-shell`, `systemd`). For user apps, it triggers a native GTK confirmation dialog.
*   **Top Battery Culprits:** The app actively highlights offending apps with insights (e.g., *"High background drain"*) rather than forcing the user to dig through a flat list.

---

## 🌫️ The Remaining Gray Areas (What's Next)

Despite architectural maturity, our UI still occasionally falls into the "developer bias" trap of valuing technical dashboards over narrative storytelling. These are the highest-priority areas for V3:

#### 1. The "Truth Confidence" Model
*   **The Problem:** We currently blend hardware measurements (RAPL) with inferred/estimated heuristics, but the UI doesn't strongly communicate uncertainty. Users unconsciously assume everything shown is exact truth.
*   **The Fix:** We need explicit visual badges (`🟢 Hardware Measured`, `🟡 Estimated`, `🔴 Low Confidence`) and a dedicated "Transparency" settings page to build absolute trust.

#### 2. Narrative "Insights Feed"
*   **The Problem:** The UI hierarchy is slightly flat. The drill-down currently overloads technical detail (PIDs, timestamps) before giving the user the human explanation.
*   **The Fix:** Create a central feed of "human explanation cards" (e.g., *🔥 Firefox caused thermal spikes during video playback*). The UI must be split so narrative insights visually dominate raw graphs.

#### 3. Overstated Estimated Savings
*   **The Problem:** Stating *"Closing Discord saves 38 minutes"* feels too certain and can become misleading with bursty workloads or thermal scaling.
*   **The Fix:** We must transition to ranges (e.g., *"Closing Discord may save 25-40 minutes"*) to feel inherently more trustworthy.

#### 4. Thermal & Battery Health Awareness
*   **The Problem:** Heat feels physical, and Linux users are deeply attached to battery degradation percentages.
*   **The Fix:** We already collect thermals, but we need a visible "Thermal Severity Ring" (Cool, Warm, Hot, Throttling) and a dedicated page tracking charge cycles and estimated capacity loss over time.

---

## 🚨 Hidden Architectural Dangers

As the app scales, we must aggressively defend against the inherent chaos of Linux desktop environments:

1.  **Suspend / Resume Drift:** When a laptop sleeps, timestamps drift, polling intervals break, and stale process deltas occur. The daemon needs explicit `systemd` sleep target hooks (or dbus listener) to prevent graph corruption.
2.  **Clock Changes & NTP:** If timezone changes, DST occurs, or manual clock edits happen, bucket logic will break. The backend must strictly migrate to internal monotonic clocks (`time.CLOCK_MONOTONIC`) and only use wall clocks for UI rendering.
3.  **Flatpak / Wayland Blindspots:** Wayland and Flatpaks intentionally hide process visibility and window states for privacy. Our attribution layer must build early portal integration or gracefully accept incomplete visibility without crashing.
4.  **GNOME Shell Reloads:** If a user restarts GNOME (`Alt+F2 -> r`), GTK apps often lose DBus session awareness and notifications fail. We must implement resilient DBus reconnections.
5.  **Hardware Edge-Cases (Multi-Battery):** Many enterprise Linux laptops (like ThinkPads) use dual batteries (`BAT0` and `BAT1`). UPower logic must handle cumulative multi-battery aggregation, not hardcoded paths.

---

## 🏁 Getting Started

Ensure you have the necessary GTK4 and Libadwaita libraries installed:

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
```

### 1. Start the Background Daemon
Install the background collector as a user systemd service so it runs persistently:
```bash
mkdir -p ~/.config/systemd/user/
cp powerstats.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now powerstats.service
```

### 2. Launch the UI
```bash
python3 main.py
```

---
_Created with ❤️ for the Linux Community._
