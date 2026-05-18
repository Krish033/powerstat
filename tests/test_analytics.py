import unittest
import sqlite3
import os
import shutil
import sys
from datetime import datetime, timedelta
import analytics_data

class TestAnalytics(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_tmp"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir, exist_ok=True)
        self.db_path = os.path.join(self.test_dir, "test_powerstats.db")
        self.conn = sqlite3.connect(self.db_path)
        c = self.conn.cursor()
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
                power_score REAL
            )
        ''')
        self.conn.commit()
        
        self.original_db_path = analytics_data.DB_PATH
        analytics_data.DB_PATH = self.db_path

    def tearDown(self):
        self.conn.close()
        analytics_data.DB_PATH = self.original_db_path
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_get_analytics_data_empty(self):
        data = analytics_data.get_analytics_data()
        self.assertIn("Last 24 Hours", data)
        self.assertIn("Last 7 Days", data)
        self.assertIn("Total Usage", data)
        self.assertEqual(len(data["Last 24 Hours"]["buckets"]), 24)
        self.assertEqual(len(data["Last 7 Days"]["buckets"]), 7)
        self.assertEqual(len(data["Total Usage"]["buckets"]), 12)
        # Empty buckets should have max_y rounded up from 10 to 20 by finalize_buckets
        self.assertEqual(data["Last 24 Hours"]["max_y"], 20)

    def test_chronological_logic(self):
        now = datetime.now()
        c = self.conn.cursor()
        
        # Use timestamps clearly within the 24h window to avoid timing race
        ts_23h = (now - timedelta(hours=23, minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute('INSERT INTO snapshots (timestamp, rapl_ujoule, battery_rate) VALUES (?, ?, ?)', (ts_23h, 0, 0.0))
        sid1 = c.lastrowid
        c.execute('INSERT INTO process_stats (snapshot_id, name, username, power_score) VALUES (?, ?, ?, ?)', (sid1, "old-app", "user", 10.0))
        
        # Insert a snapshot for 5 minutes ago (safely within last bucket)
        ts_recent = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute('INSERT INTO snapshots (timestamp, rapl_ujoule, battery_rate) VALUES (?, ?, ?)', (ts_recent, 0, 0.0))
        sid2 = c.lastrowid
        c.execute('INSERT INTO process_stats (snapshot_id, name, username, power_score) VALUES (?, ?, ?, ?)', (sid2, "new-app", "user", 20.0))
        
        self.conn.commit()
        
        data = analytics_data.get_analytics_data()
        buckets = data["Last 24 Hours"]["buckets"]
        
        found_old = False
        found_new = False
        old_bucket_idx = None
        new_bucket_idx = None
        
        for bucket_idx in range(24):
            for s in buckets[bucket_idx]:
                if s["name"] == "old-app":
                    found_old = True
                    old_bucket_idx = bucket_idx
                if s["name"] == "new-app":
                    found_new = True
                    new_bucket_idx = bucket_idx
        
        self.assertTrue(found_old, "Old app should be found in the buckets")
        self.assertTrue(found_new, "New app should be found in the buckets")
        self.assertTrue(new_bucket_idx >= old_bucket_idx, "New app should be in same or later bucket than old app")

    def test_categorization(self):
        now = datetime.now()
        c = self.conn.cursor()
        ts = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute('INSERT INTO snapshots (timestamp, rapl_ujoule, battery_rate) VALUES (?, ?, ?)', (ts, 0, 0.0))
        sid = c.lastrowid
        
        c.execute('INSERT INTO process_stats (snapshot_id, name, username, power_score) VALUES (?, ?, ?, ?)', (sid, "systemd", "root", 10.0))
        c.execute('INSERT INTO process_stats (snapshot_id, name, username, power_score) VALUES (?, ?, ?, ?)', (sid, "gnome-shell", "user", 10.0))
        c.execute('INSERT INTO process_stats (snapshot_id, name, username, power_score) VALUES (?, ?, ?, ?)', (sid, "firefox", "user", 10.0))
        self.conn.commit()
        
        data = analytics_data.get_analytics_data()
        found_apps = {}
        for bucket_idx in range(24):
            bucket = data["Last 24 Hours"]["buckets"][bucket_idx]
            for s in bucket:
                found_apps[s["name"]] = s["category"]
        
        self.assertIn("systemd", found_apps)
        self.assertIn("gnome-shell", found_apps)
        self.assertIn("firefox", found_apps)
        self.assertEqual(found_apps["systemd"], "background")
        self.assertEqual(found_apps["gnome-shell"], "system_app")
        self.assertEqual(found_apps["firefox"], "other_app")

    def test_duration_calculation_partial_bucket(self):
        """Duration should not overcount when daemon hasn't run for full bucket."""
        now = datetime.now()
        c = self.conn.cursor()
        
        # Simulate daemon running for only 30 minutes in the current hour
        bucket_end = now
        bucket_start = bucket_end - timedelta(hours=1)
        
        # Insert snapshots covering only the last 30 minutes
        for mins_ago in range(0, 30, 5):
            ts = (now - timedelta(minutes=mins_ago)).strftime("%Y-%m-%d %H:%M:%S")
            c.execute('INSERT INTO snapshots (timestamp, rapl_ujoule, battery_rate) VALUES (?, ?, ?)', (ts, 0, 0.0))
            sid = c.lastrowid
            c.execute('INSERT INTO process_stats (snapshot_id, name, username, power_score) VALUES (?, ?, ?, ?)', (sid, "test-app", "user", 100.0))
        
        self.conn.commit()
        
        data = analytics_data.get_analytics_data()
        buckets = data["Last 24 Hours"]["buckets"]
        
        # Find test-app in the last bucket
        last_bucket = buckets[23]
        test_sessions = [s for s in last_bucket if s["name"] == "test-app"]
        self.assertTrue(len(test_sessions) > 0, "test-app should appear in the last bucket")
        
        duration = test_sessions[0]["duration_mins"]
        # With 6 snapshots over ~25 mins observed span, duration should be ~25 mins
        # NOT 60 mins (which was the old bug)
        self.assertLess(duration, 40, f"Duration {duration} should be < 40 mins (was the 60-min overcount bug)")
        self.assertGreater(duration, 10, f"Duration {duration} should be > 10 mins")

    def test_duration_calculation_full_bucket(self):
        """When daemon runs for the full hour, duration should be accurate."""
        now = datetime.now()
        c = self.conn.cursor()
        
        # Simulate daemon running for the full hour
        for mins_ago in range(0, 60, 10):
            ts = (now - timedelta(minutes=mins_ago)).strftime("%Y-%m-%d %H:%M:%S")
            c.execute('INSERT INTO snapshots (timestamp, rapl_ujoule, battery_rate) VALUES (?, ?, ?)', (ts, 0, 0.0))
            sid = c.lastrowid
            c.execute('INSERT INTO process_stats (snapshot_id, name, username, power_score) VALUES (?, ?, ?, ?)', (sid, "full-app", "user", 100.0))
        
        self.conn.commit()
        
        data = analytics_data.get_analytics_data()
        buckets = data["Last 24 Hours"]["buckets"]
        
        last_bucket = buckets[23]
        full_sessions = [s for s in last_bucket if s["name"] == "full-app"]
        self.assertTrue(len(full_sessions) > 0, "full-app should appear in the last bucket")
        
        duration = full_sessions[0]["duration_mins"]
        # With 6 snapshots over ~50 mins observed span, duration should be ~50 mins
        self.assertGreater(duration, 30, f"Duration {duration} should be > 30 mins for full bucket")

    def test_twelve_month_buckets(self):
        """12-month view should show correct month labels in chronological order."""
        now = datetime.now()
        c = self.conn.cursor()
        
        # Insert one snapshot in the current month
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        c.execute('INSERT INTO snapshots (timestamp, rapl_ujoule, battery_rate) VALUES (?, ?, ?)', (ts, 0, 0.0))
        sid = c.lastrowid
        c.execute('INSERT INTO process_stats (snapshot_id, name, username, power_score) VALUES (?, ?, ?, ?)', (sid, "monthly-app", "user", 100.0))
        self.conn.commit()
        
        data = analytics_data.get_analytics_data()
        labels = data["Total Usage"]["labels"]
        buckets = data["Total Usage"]["buckets"]
        
        self.assertEqual(len(labels), 12, "Should have 12 month labels")
        self.assertEqual(len(buckets), 12, "Should have 12 month buckets")
        
        # The last bucket (index 11) should be the current month
        expected_label = now.strftime("%b")
        self.assertEqual(labels[11], expected_label, f"Last label should be current month {expected_label}")
        
        # Current month bucket should contain our data
        current_month_bucket = buckets[11]
        monthly_sessions = [s for s in current_month_bucket if s["name"] == "monthly-app"]
        self.assertTrue(len(monthly_sessions) > 0, "monthly-app should appear in current month bucket")

    def test_start_time_dt_present(self):
        """All bucket entries should have start_time_dt for _update_details compatibility."""
        now = datetime.now()
        c = self.conn.cursor()
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        c.execute('INSERT INTO snapshots (timestamp, rapl_ujoule, battery_rate) VALUES (?, ?, ?)', (ts, 0, 0.0))
        sid = c.lastrowid
        c.execute('INSERT INTO process_stats (snapshot_id, name, username, power_score) VALUES (?, ?, ?, ?)', (sid, "check-app", "user", 100.0))
        self.conn.commit()
        
        data = analytics_data.get_analytics_data()
        
        # Check 24h view
        for bucket_idx in range(24):
            for s in data["Last 24 Hours"]["buckets"][bucket_idx]:
                self.assertIn("start_time_dt", s, f"24h bucket {bucket_idx} missing start_time_dt")
        
        # Check 7d view
        for bucket_idx in range(7):
            for s in data["Last 7 Days"]["buckets"][bucket_idx]:
                self.assertIn("start_time_dt", s, f"7d bucket {bucket_idx} missing start_time_dt")
        
        # Check 12m view
        for bucket_idx in range(12):
            for s in data["Total Usage"]["buckets"][bucket_idx]:
                self.assertIn("start_time_dt", s, f"12m bucket {bucket_idx} missing start_time_dt")

    def test_battery_usage_is_numeric(self):
        """battery_usage should be a numeric value (not a string with %)."""
        now = datetime.now()
        c = self.conn.cursor()
        ts = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute('INSERT INTO snapshots (timestamp, rapl_ujoule, battery_rate) VALUES (?, ?, ?)', (ts, 0, 0.0))
        sid = c.lastrowid
        c.execute('INSERT INTO process_stats (snapshot_id, name, username, power_score) VALUES (?, ?, ?, ?)', (sid, "num-app", "user", 1000.0))
        self.conn.commit()
        
        data = analytics_data.get_analytics_data()
        for bucket_idx in range(24):
            for s in data["Last 24 Hours"]["buckets"][bucket_idx]:
                if s["name"] == "num-app":
                    self.assertIsInstance(s["battery_usage"], (int, float))
                    self.assertAlmostEqual(s["battery_usage"], 1.0, places=1)
                    return
        self.fail("num-app not found in any bucket")

if __name__ == '__main__':
    unittest.main()
