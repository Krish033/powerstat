import logging
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta

log = logging.getLogger("powerstats.analytics")

DB_PATH = os.path.expanduser("~/.local/share/powerstats.db")


def categorize_process(name, username):
    n = name.lower()
    # Background: root processes or systemd
    if username == 'root' or n.startswith('systemd'):
        return 'background'
    # System Apps: GNOME core apps
    if n.startswith('gnome-') or n in ['nautilus', 'evolution', 'totem', 'gedit', 'evince', 'adwaita']:
        return 'system_app'
    # Other: User-installed apps
    return 'other_app'


def get_analytics_data() -> dict:
    t0 = time.monotonic()
    now = datetime.now()
    cutoff_24h = now - timedelta(hours=24)

    # Return empty buckets if DB doesn't exist yet
    if not os.path.exists(DB_PATH):
        empty_buckets_24h = {i: [] for i in range(24)}
        empty_buckets_7d = {i: [] for i in range(7)}
        empty_buckets_12m = {i: [] for i in range(12)}
        return {
            "Last 24 Hours": {"buckets": empty_buckets_24h, "max_y": 10, "labels": [str(i) for i in range(24)]},
            "Last 7 Days": {"buckets": empty_buckets_7d, "max_y": 10, "labels": [str(i) for i in range(7)]},
            "Total Usage": {"buckets": empty_buckets_12m, "max_y": 10, "labels": [str(i) for i in range(12)]}
        }

    log.info("Loading analytics data from %s", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")

    # Safe schema migration for existing DBs
    try:
        conn.execute('ALTER TABLE snapshots ADD COLUMN cpu_temp REAL')
        conn.execute('ALTER TABLE snapshots ADD COLUMN cpu_freq REAL')
        conn.commit()
    except sqlite3.OperationalError:
        pass

    c = conn.cursor()

    # 1. Comparison logic (Today vs Yesterday)
    cutoff_48h = now - timedelta(hours=48)

    c.execute('''
        SELECT SUM(p.power_score)
        FROM snapshots s
        JOIN process_stats p ON s.id = p.snapshot_id
        WHERE s.timestamp >= ? AND s.timestamp < ?
    ''', (cutoff_48h.strftime("%Y-%m-%d %H:%M:%S"), cutoff_24h.strftime("%Y-%m-%d %H:%M:%S")))
    score_yesterday = c.fetchone()[0] or 0.0

    c.execute('''
        SELECT SUM(p.power_score)
        FROM snapshots s
        JOIN process_stats p ON s.id = p.snapshot_id
        WHERE s.timestamp >= ?
    ''', (cutoff_24h.strftime("%Y-%m-%d %H:%M:%S"),))
    score_today = c.fetchone()[0] or 0.0

    comparison_text = ""
    if score_yesterday > 0:
        diff = ((score_today - score_yesterday) / score_yesterday) * 100
        if diff > 0:
            comparison_text = f"System consumed {int(diff)}% more power today than yesterday."
        else:
            comparison_text = f"Battery lasted {int(abs(diff))}% longer today than yesterday."
    else:
        comparison_text = "Collecting baseline data for tomorrow's comparison..."

    aging_forecast = "Battery health data unavailable."
    try:
        out = subprocess.check_output(["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"], text=True)
        capacity = None
        for line in out.splitlines():
            if "capacity:" in line:
                capacity = float(line.split(":")[1].strip().replace("%", ""))
                break
        if capacity:
            degradation = round(100 - capacity, 1)
            aging_forecast = f"Battery capacity is {round(capacity, 1)}%. You have lost {degradation}% of original design capacity."
    except Exception:
        pass

    # 2. Last 24 Hours (Chronological)
    buckets_24h = {i: [] for i in range(24)}
    labels_24h = []
    for i in range(24):
        bucket_end = now - timedelta(hours=23 - i)
        bucket_start = bucket_end - timedelta(hours=1)
        if i % 4 == 0 or i == 23:
            labels_24h.append(bucket_start.strftime("%H:%M"))
        else:
            labels_24h.append("")

        # Get snapshot count and actual observed time span for duration accuracy
        bucket_start_str = bucket_start.strftime("%Y-%m-%d %H:%M:%S")
        bucket_end_str = bucket_end.strftime("%Y-%m-%d %H:%M:%S")
        c.execute('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM snapshots WHERE timestamp >= ? AND timestamp < ?', (bucket_start_str, bucket_end_str))
        snap_row = c.fetchone()
        total_snapshots = snap_row[0] or 1
        # Use actual observed span to prevent overcounting when daemon
        # hasn't been running for the full bucket period.
        # ROOT FIX: If daemon ran for 30 mins in a 60-min bucket and app
        # appeared in all snapshots, ratio=1.0 * 60 = 60 mins (WRONG).
        # With observed span: ratio=1.0 * 30 = 30 mins (CORRECT).
        if snap_row[1] and snap_row[2] and total_snapshots > 1:
            t_first = datetime.strptime(snap_row[1].split(".")[0], "%Y-%m-%d %H:%M:%S")
            t_last = datetime.strptime(snap_row[2].split(".")[0], "%Y-%m-%d %H:%M:%S")
            observed_minutes = max(1.0, (t_last - t_first).total_seconds() / 60.0)
        else:
            observed_minutes = (bucket_end - bucket_start).total_seconds() / 60.0

        query = '''
            SELECT
                p.pid, p.name, p.username,
                p.power_score,
                p.snapshot_id,
                s.cpu_temp
            FROM snapshots s
            JOIN process_stats p ON s.id = p.snapshot_id
            WHERE s.timestamp >= ? AND s.timestamp < ?
        '''
        c.execute(query, (bucket_start_str, bucket_end_str))
        rows = c.fetchall()

        # Group by name/username in Python to keep process details
        app_groups = {}
        for pid, name, username, power_score, sid, temp in rows:
            key = (name, username)
            if key not in app_groups:
                app_groups[key] = {
                    "pids": {pid: {"snapshots": set(), "score": 0.0}},
                    "all_snapshots": set(),
                    "max_temp": temp or 0.0
                }

            if pid not in app_groups[key]["pids"]:
                app_groups[key]["pids"][pid] = {"snapshots": set(), "score": 0.0}

            app_groups[key]["pids"][pid]["snapshots"].add(sid)
            app_groups[key]["pids"][pid]["score"] += power_score
            app_groups[key]["all_snapshots"].add(sid)
            if temp and temp > app_groups[key]["max_temp"]:
                app_groups[key]["max_temp"] = temp

        for (name, username), info in app_groups.items():
            cat = categorize_process(name, username)
            icon = determine_icon(name)

            # Wall-clock duration for the whole app (corrected for partial buckets)
            app_snapshot_count = len(info["all_snapshots"])
            app_duration = int((app_snapshot_count / total_snapshots) * observed_minutes)
            if app_duration < 1 and app_snapshot_count > 0:
                app_duration = 1

            # Individual process stats
            processes = []
            for pid, p_info in info["pids"].items():
                p_snapshot_count = len(p_info["snapshots"])
                p_duration = int((p_snapshot_count / total_snapshots) * observed_minutes)
                if p_duration < 1 and p_snapshot_count > 0:
                    p_duration = 1
                processes.append({
                    "pid": pid,
                    "duration_mins": p_duration,
                    "battery_usage": round(p_info["score"] / 1000.0, 2)
                })

            buckets_24h[i].append({
                "name": name, "icon": icon, "opened_time": "N/A", "closed_time": bucket_end.strftime("%I:%M %p"),
                "start_time_dt": bucket_start, "battery_usage": round(sum(p["battery_usage"] for p in processes), 2),
                "date": bucket_start.strftime("%B %d, %Y"),
                "duration_mins": app_duration, "process_id": processes[0]["pid"], "category": cat, "max_temp": info["max_temp"] or 45.0,
                "is_bg": cat == 'background', "updated_at": now.strftime("%I:%M %p"),
                "version": "1.0.0", "developer": "System Process" if cat != 'other_app' else "User App",
                "installed_date": "N/A", "processes": processes
            })

    # 3. Last 7 Days
    buckets_7d = {i: [] for i in range(7)}
    labels_7d = []
    for i in range(7):
        bucket_end = (now - timedelta(days=6 - i)).replace(hour=23, minute=59, second=59)
        bucket_start = bucket_end.replace(hour=0, minute=0, second=0)
        labels_7d.append(bucket_start.strftime("%a"))

        bucket_start_str = bucket_start.strftime("%Y-%m-%d %H:%M:%S")
        bucket_end_str = bucket_end.strftime("%Y-%m-%d %H:%M:%S")

        # Get snapshot count and actual observed span
        c.execute('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM snapshots WHERE timestamp >= ? AND timestamp < ?', (bucket_start_str, bucket_end_str))
        snap_row = c.fetchone()
        total_snapshots = snap_row[0] or 1
        if snap_row[1] and snap_row[2] and total_snapshots > 1:
            t_first = datetime.strptime(snap_row[1].split(".")[0], "%Y-%m-%d %H:%M:%S")
            t_last = datetime.strptime(snap_row[2].split(".")[0], "%Y-%m-%d %H:%M:%S")
            observed_minutes = max(1.0, (t_last - t_first).total_seconds() / 60.0)
        else:
            observed_minutes = 1440.0  # full day fallback

        query = '''
            SELECT
                p.name, p.username,
                SUM(p.power_score) as total_score,
                COUNT(DISTINCT p.snapshot_id) as snapshot_count,
                MAX(s.cpu_temp) as max_temp
            FROM snapshots s
            JOIN process_stats p ON s.id = p.snapshot_id
            WHERE s.timestamp >= ? AND s.timestamp < ?
            GROUP BY p.name, p.username
        '''
        c.execute(query, (bucket_start_str, bucket_end_str))
        rows = c.fetchall()
        for name, username, total_score, snapshot_count, max_temp in rows:
            cat = categorize_process(name, username)
            icon = determine_icon(name)

            duration = int((snapshot_count / total_snapshots) * observed_minutes)
            if duration < 1 and snapshot_count > 0:
                duration = 1

            buckets_7d[i].append({
                "name": name, "icon": icon, "closed_time": bucket_end.strftime("%B %d"),
                "start_time_dt": bucket_start,
                "battery_usage": round(total_score / 1000.0, 2), "duration_mins": duration, "category": cat,
                "max_temp": max_temp or 45.0, "is_bg": cat == 'background',
                "date": bucket_start.strftime("%B %d, %Y"), "updated_at": now.strftime("%I:%M %p"),
                "version": "1.0.0", "developer": "System Process" if cat != 'other_app' else "User App",
                "installed_date": "N/A", "processes": [{"pid": 0, "duration_mins": duration, "battery_usage": round(total_score / 1000.0, 2)}]
            })

    # 4. Total Usage (12 Months) — proper calendar month arithmetic
    buckets_12m = {i: [] for i in range(12)}
    labels_12m = []
    for i in range(12):
        months_ago = 11 - i
        target_month = now.month - months_ago
        target_year = now.year
        while target_month < 1:
            target_month += 12
            target_year -= 1

        bucket_start = datetime(target_year, target_month, 1)
        if target_month == 12:
            next_month_start = datetime(target_year + 1, 1, 1)
        else:
            next_month_start = datetime(target_year, target_month + 1, 1)
        bucket_end = next_month_start - timedelta(seconds=1)

        labels_12m.append(bucket_start.strftime("%b"))

        bucket_start_str = bucket_start.strftime("%Y-%m-%d %H:%M:%S")
        bucket_end_str = bucket_end.strftime("%Y-%m-%d %H:%M:%S")

        # Get snapshot count and actual observed span
        c.execute('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM snapshots WHERE timestamp >= ? AND timestamp < ?', (bucket_start_str, bucket_end_str))
        snap_row = c.fetchone()
        total_snapshots = snap_row[0] or 1
        if snap_row[1] and snap_row[2] and total_snapshots > 1:
            t_first = datetime.strptime(snap_row[1].split(".")[0], "%Y-%m-%d %H:%M:%S")
            t_last = datetime.strptime(snap_row[2].split(".")[0], "%Y-%m-%d %H:%M:%S")
            observed_minutes = max(1.0, (t_last - t_first).total_seconds() / 60.0)
        else:
            bucket_mins = int((bucket_end - bucket_start).total_seconds() / 60.0)
            observed_minutes = float(bucket_mins)

        query = '''
            SELECT
                p.name, p.username,
                SUM(p.power_score) as total_score,
                COUNT(DISTINCT p.snapshot_id) as snapshot_count,
                MAX(s.cpu_temp) as max_temp
            FROM snapshots s
            JOIN process_stats p ON s.id = p.snapshot_id
            WHERE s.timestamp >= ? AND s.timestamp < ?
            GROUP BY p.name, p.username
        '''
        c.execute(query, (bucket_start_str, bucket_end_str))
        rows = c.fetchall()
        for name, username, total_score, snapshot_count, max_temp in rows:
            cat = categorize_process(name, username)
            icon = determine_icon(name)

            duration = int((snapshot_count / total_snapshots) * observed_minutes)
            if duration < 1 and snapshot_count > 0:
                duration = 1

            buckets_12m[i].append({
                "name": name, "icon": icon, "closed_time": bucket_start.strftime("%B %Y"),
                "start_time_dt": bucket_start,
                "battery_usage": round(total_score / 1000.0, 2), "duration_mins": duration, "category": cat,
                "max_temp": max_temp or 45.0, "is_bg": cat == 'background',
                "date": bucket_start.strftime("%B %Y"), "updated_at": now.strftime("%I:%M %p"),
                "version": "1.0.0", "developer": "System Process" if cat != 'other_app' else "User App",
                "installed_date": "N/A", "processes": [{"pid": 0, "duration_mins": duration, "battery_usage": round(total_score / 1000.0, 2)}]
            })

    conn.close()
    log.info("Analytics query completed in %.2fs", time.monotonic() - t0)

    def finalize_buckets(buckets, labels):
        max_y = 10
        for i in range(len(buckets)):
            total_mins = sum(s["duration_mins"] for s in buckets[i])
            if total_mins > max_y:
                max_y = total_mins
        max_y = ((int(max_y) // 10) + 1) * 10
        return {"buckets": buckets, "max_y": max_y, "labels": labels}

    return {
        "comparison": comparison_text,
        "aging_forecast": aging_forecast,
        "Last 24 Hours": finalize_buckets(buckets_24h, labels_24h),
        "Last 7 Days": finalize_buckets(buckets_7d, labels_7d),
        "Total Usage": finalize_buckets(buckets_12m, labels_12m)
    }


def determine_icon(name):
    n = name.lower()
    if "firefox" in n or "isolated web" in n:
        return "firefox"
    if "slack" in n:
        return "slack"
    if "terminal" in n or "bash" in n or "zsh" in n:
        return "org.gnome.Terminal"
    if "code" in n or "vscode" in n:
        return "visual-studio-code"
    return "application-x-executable"
