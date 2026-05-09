import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.expanduser("~/.local/share/powerstats.db")

def get_analytics_data():
    now = datetime.now()
    cutoff_24h = now - timedelta(hours=24)
    
    # Return empty buckets if DB doesn't exist yet
    if not os.path.exists(DB_PATH):
        empty_buckets = {i: [] for i in range(24)}
        return {
            "Last 24 Hours": {"buckets": empty_buckets, "max_y": 10},
            "Total Usage": {"buckets": empty_buckets, "max_y": 10}
        }
        
    conn = sqlite3.connect(DB_PATH)
    
    # Safe schema migration for existing DBs to prevent UI crash if daemon hasn't updated it yet
    try:
        conn.execute('ALTER TABLE snapshots ADD COLUMN cpu_temp REAL')
        conn.execute('ALTER TABLE snapshots ADD COLUMN cpu_freq REAL')
        conn.commit()
    except sqlite3.OperationalError:
        pass
        
    c = conn.cursor()
    
    # We will build the Last 24 Hours buckets
    buckets_24h = {i: [] for i in range(24)}
    buckets_all = {i: [] for i in range(24)}
    
    # Session comparison (Today vs Yesterday)
    cutoff_48h = now - timedelta(hours=48)
    
    c.execute('''
        SELECT SUM(p.power_score)
        FROM snapshots s
        JOIN process_stats p ON s.id = p.snapshot_id
        WHERE s.timestamp >= ? AND s.timestamp < ?
    ''', (cutoff_48h, cutoff_24h))
    score_yesterday = c.fetchone()[0] or 0.0
    
    c.execute('''
        SELECT SUM(p.power_score)
        FROM snapshots s
        JOIN process_stats p ON s.id = p.snapshot_id
        WHERE s.timestamp >= ?
    ''', (cutoff_24h,))
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
        import subprocess
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
    
    # Query for the last 24 hours
    # Group by hour and PID
    query = '''
        SELECT 
            strftime('%H', s.timestamp) as hour,
            p.pid,
            p.name,
            p.username,
            SUM(p.power_score) as total_score,
            COUNT(DISTINCT p.snapshot_id) as snapshot_count,
            MAX(s.cpu_temp) as max_temp
        FROM snapshots s
        JOIN process_stats p ON s.id = p.snapshot_id
        WHERE s.timestamp >= ?
        GROUP BY hour, p.pid, p.name, p.username
    '''
    
    c.execute(query, (cutoff_24h,))
    rows = c.fetchall()
    
    def determine_icon(name):
        n = name.lower()
        if "firefox" in n or "isolated web" in n: return "firefox"
        if "slack" in n: return "slack"
        if "terminal" in n or "bash" in n or "zsh" in n: return "org.gnome.Terminal"
        if "code" in n or "vscode" in n: return "visual-studio-code"
        return "application-x-executable"
        
    for hour_str, pid, name, username, total_score, snapshot_count, max_temp in rows:
        h = int(hour_str)
        is_bg = username == 'root' or name.startswith('systemd') or name.startswith('gnome-')
        icon = determine_icon(name)
        dev = "System" if is_bg else "User Space"
        
        # Estimate duration mins based on snapshot count (approx 10s per snapshot in our current daemon config)
        # But if it's from the heuristics seed, snapshot count is exactly 1 per hour, so duration mins should just be an estimate
        # Let's say max 60 mins.
        duration = min(60, snapshot_count * 1) # This is a rough estimation for UI
        if duration < 1: duration = 1
        
        # Create UI session object
        session = {
            "name": name,
            "icon": icon,
            "opened_time": "N/A",
            "closed_time": "N/A",
            "start_time_dt": now.replace(hour=h, minute=0, second=0),
            "battery_usage": round(total_score, 2),
            "date": now.strftime("%B %d, %Y"),
            "updated_at": now.strftime("%I:%M %p"),
            "duration_mins": duration,
            "version": "1.0",
            "developer": dev,
            "installed_date": "N/A",
            "process_id": pid,
            "is_bg": is_bg,
            "max_temp": max_temp or 45.0
        }
        
        buckets_24h[h].append(session)
        buckets_all[h].append(session) # In a real app 'Total Usage' would be different, here we just copy for MVP
        
    conn.close()
    
    def finalize_buckets(buckets):
        max_y = 10
        for i in range(24):
            total_mins = sum(s["duration_mins"] for s in buckets[i])
            if total_mins > max_y: max_y = total_mins
        max_y = ((int(max_y) // 10) + 1) * 10
        return {"buckets": buckets, "max_y": max_y}
        
    return {
        "comparison": comparison_text,
        "aging_forecast": aging_forecast,
        "Last 24 Hours": finalize_buckets(buckets_24h),
        "Total Usage": finalize_buckets(buckets_all)
    }
