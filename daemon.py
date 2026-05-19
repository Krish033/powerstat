import json
import logging
import math
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta

import psutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("powerstats.daemon")

DB_PATH = os.path.expanduser("~/.local/share/powerstats.db")
# Run pruning every 1 hour (360 loops * 10 seconds = 3600 seconds)
PRUNE_INTERVAL_LOOPS = 360


def setup_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # Critical: Use WAL mode to prevent SQLite lock contention between UI and Daemon
    conn.execute("PRAGMA journal_mode=WAL;")
    # Enable foreign keys for CASCADE DELETE
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            rapl_ujoule INTEGER,
            battery_rate REAL,
            cpu_temp REAL,
            cpu_freq REAL
        )
    ''')

    # Safe schema migration for existing DBs
    try:
        conn.execute('ALTER TABLE snapshots ADD COLUMN cpu_temp REAL')
        conn.execute('ALTER TABLE snapshots ADD COLUMN cpu_freq REAL')
    except sqlite3.OperationalError:
        pass
    c.execute('''
        CREATE TABLE IF NOT EXISTS process_stats (
            snapshot_id INTEGER,
            pid INTEGER,
            name TEXT,
            username TEXT,
            cpu_time REAL,
            wakeups INTEGER,
            disk_io INTEGER,
            gpu_usage INTEGER,
            power_score REAL,
            FOREIGN KEY(snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
        )
    ''')
    # Performance indexes — critical for UI query speed
    c.execute('CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_process_stats_snapshot_id ON process_stats(snapshot_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_process_stats_name ON process_stats(name)')
    conn.commit()
    return conn


def prune_database(conn) -> None:
    """Deletes data older than 7 days to prevent SQLite bloat."""
    log.info("Running database pruning (removing data > 7 days old)...")
    c = conn.cursor()
    cutoff = datetime.now() - timedelta(days=7)

    # We must manually delete child records if PRAGMA foreign_keys is acting up,
    # but we enabled it. We do it manually to be 100% safe.
    c.execute('''
        DELETE FROM process_stats
        WHERE snapshot_id IN (
            SELECT id FROM snapshots WHERE timestamp < ?
        )
    ''', (cutoff.strftime("%Y-%m-%d %H:%M:%S"),))

    c.execute('DELETE FROM snapshots WHERE timestamp < ?', (cutoff.strftime("%Y-%m-%d %H:%M:%S"),))

    # NOTE: VACUUM removed — it rewrites the entire DB file and causes
    # lock contention with the UI. SQLite reuses freed pages automatically.
    conn.commit()
    log.info("Pruning complete.")


def get_rapl_energy():
    try:
        with open('/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj', 'r') as f:
            return int(f.read().strip())
    except PermissionError:
        # Fallback: We don't have root permissions to read RAPL, so we will rely entirely on heuristics
        return 0
    except Exception:
        # Fallback: System might not have Intel RAPL
        return 0


def get_battery_rate():
    try:
        out = subprocess.check_output(['upower', '-i', '/org/freedesktop/UPower/devices/battery_BAT0'], stderr=subprocess.DEVNULL).decode()
        for line in out.split('\n'):
            if 'energy-rate:' in line:
                return float(line.split(':')[1].strip().split()[0])
    except Exception:
        pass
    return 0.0


def get_cpu_freq():
    try:
        freqs = []
        for f in os.listdir('/sys/devices/system/cpu/'):
            if f.startswith('cpu') and f[3:].isdigit():
                try:
                    with open(f'/sys/devices/system/cpu/{f}/cpufreq/scaling_cur_freq', 'r') as freq_file:
                        freqs.append(int(freq_file.read().strip()))
                except Exception:
                    continue
        if freqs:
            return sum(freqs) / len(freqs) / 1000.0  # MHz
    except Exception:
        pass
    return 1000.0


def get_cpu_temp():
    try:
        for tz in os.listdir('/sys/class/thermal/'):
            if tz.startswith('thermal_zone'):
                try:
                    with open(f'/sys/class/thermal/{tz}/type', 'r') as tf:
                        typ = tf.read().strip()
                        if 'x86_pkg_temp' in typ or 'cpu' in typ.lower() or 'acpitz' in typ:
                            with open(f'/sys/class/thermal/{tz}/temp', 'r') as temp_f:
                                return int(temp_f.read().strip()) / 1000.0
                except Exception:
                    continue
    except Exception:
        pass
    return 45.0


def run_daemon():
    conn = setup_db()
    c = conn.cursor()

    prev_state = {}
    prev_rapl = get_rapl_energy()
    loop_count = 0

    log.info("PowerStats Daemon running. High-fidelity data collection started...")
    while True:
        loop_count += 1
        if loop_count % PRUNE_INTERVAL_LOOPS == 0:
            prune_database(conn)

        timestamp = datetime.now()
        current_rapl = get_rapl_energy()
        bat_rate = get_battery_rate()
        cpu_temp = get_cpu_temp()
        avg_freq_mhz = get_cpu_freq()

        rapl_delta = current_rapl - prev_rapl if prev_rapl != 0 else 0
        if rapl_delta < 0:
            rapl_delta = current_rapl
        prev_rapl = current_rapl

        # We use a try-except to handle backwards compatibility if the ALTER TABLE failed for some reason
        try:
            c.execute('INSERT INTO snapshots (timestamp, rapl_ujoule, battery_rate, cpu_temp, cpu_freq) VALUES (?, ?, ?, ?, ?)',
                      (timestamp.strftime("%Y-%m-%d %H:%M:%S"), rapl_delta, bat_rate, cpu_temp, avg_freq_mhz))
        except sqlite3.OperationalError:
            c.execute('INSERT INTO snapshots (timestamp, rapl_ujoule, battery_rate) VALUES (?, ?, ?)',
                      (timestamp.strftime("%Y-%m-%d %H:%M:%S"), rapl_delta, bat_rate))
        snapshot_id = c.lastrowid

        current_state = {}
        # Iterate over all processes
        for p in psutil.process_iter(['pid', 'name', 'username']):
            try:
                with p.oneshot():
                    pid = p.info['pid']
                    name = p.info['name']
                    if not name:
                        continue

                    cpu = p.cpu_times().user + p.cpu_times().system
                    ctx = p.num_ctx_switches()
                    wakeups = ctx.voluntary + ctx.involuntary

                    # Disk IO isn't always available due to permissions
                    try:
                        io = p.io_counters()
                        disk = io.read_bytes + io.write_bytes
                    except psutil.AccessDenied:
                        disk = 0

                    gpu = 0
                    try:
                        maps = p.memory_maps()
                        if any('/dev/dri/' in m.path for m in maps):
                            gpu = 1
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass

                    current_state[pid] = {
                        'name': name,
                        'username': p.info['username'],
                        'cpu': cpu,
                        'wakeups': wakeups,
                        'disk': disk,
                        'gpu': gpu
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Processes disappear CONSTANTLY in Linux.
                continue

        for pid, stats in current_state.items():
            if pid in prev_state:
                prev = prev_state[pid]
                cpu_delta = max(0, stats['cpu'] - prev['cpu'])
                wakeup_delta = max(0, stats['wakeups'] - prev['wakeups'])
                io_delta = max(0, stats['disk'] - prev['disk'])
            else:
                cpu_delta = 0
                wakeup_delta = 0
                io_delta = 0

            # --- Advanced Non-Linear Math Engine ---

            # Non-linear scaling based on CPU frequency and load
            # A 5% load at 800MHz is vastly different than 5% at 4.5GHz
            freq_scaling_factor = avg_freq_mhz / 1000.0  # Normalize to ~1-4 scale
            scaled_cpu_time = cpu_delta * freq_scaling_factor

            # pow() to 1.4 creates realistic exponential power curves
            # (e.g. thermal boost costs exponentially more power than linear logic suggests)
            cpu_score = math.pow(scaled_cpu_time, 1.4) * 10.0

            # Wakeups prevent sleep states, incredibly impactful for battery
            wakeup_score = wakeup_delta * 0.005

            # Disk IO
            io_score = io_delta * 0.000001

            # GPU utilization is a massive static penalty if active
            gpu_score = 15.0 if stats['gpu'] else 0.0

            power_score = cpu_score + wakeup_score + io_score + gpu_score

            # Threshold to prevent DB spam for completely idle processes
            if power_score > 0.5:
                c.execute('''
                    INSERT INTO process_stats (snapshot_id, pid, name, username, cpu_time, wakeups, disk_io, gpu_usage, power_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (snapshot_id, pid, stats['name'], stats['username'], cpu_delta, wakeup_delta, io_delta, stats['gpu'], power_score))

        prev_state = current_state
        conn.commit()

        # Dynamically adjust polling speed based on Power Mode config
        sleep_time = 10
        try:
            with open(os.path.expanduser("~/.config/powerstats/config.json")) as f:
                cfg = json.load(f)
                mode = cfg.get("power_mode", 0)
                if mode == 1:
                    sleep_time = 30  # Quiet
                elif mode == 2:
                    sleep_time = 5  # Analyze
                elif mode == 3:
                    sleep_time = 60  # Battery Saver
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

        time.sleep(sleep_time)


if __name__ == '__main__':
    run_daemon()
