import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Pango, GObject, Gdk

class UsageView(Gtk.ScrolledWindow):
    __gsignals__ = {
        'app-clicked': (GObject.SignalFlags.RUN_FIRST, None, (object,))
    }

    def __init__(self, data_set, comparison_text="", aging_forecast="", **kwargs):
        super().__init__(**kwargs)
        self.comparison_text = comparison_text
        self.aging_forecast = aging_forecast
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content_box.set_spacing(24)
        self.content_box.set_margin_top(24)
        self.content_box.set_margin_bottom(24)
        self.content_box.set_margin_start(24)
        self.content_box.set_margin_end(24)
        
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        clamp.set_child(self.content_box)
        self.set_child(clamp)
        
        self.data_set = data_set
        self.buckets = data_set["buckets"]
        self.max_y = data_set["max_y"]
        self.current_selected_bucket = None
        
        # 1. PRIMARY LAYER: Insights Feed
        self.insights_group = Adw.PreferencesGroup(title="🧠 Diagnostic Feed")
        self.content_box.append(self.insights_group)
        
        # 2. SECONDARY LAYER: Top Offenders
        self.culprits_group = Adw.PreferencesGroup(title="⚠️ Top Battery Offenders")
        self.content_box.append(self.culprits_group)
        
        # 3. TERTIARY LAYER: Graphs & Tech Details
        graph_header = Gtk.Label(label="Technical Telemetry", xalign=0.0)
        graph_header.add_css_class("heading")
        graph_header.set_margin_top(24)
        self.content_box.append(graph_header)
        
        self._build_graph()
        
        self.list_group = Adw.PreferencesGroup(title="Active Applications")
        self.content_box.append(self.list_group)
        
        self.bg_list_group = Adw.PreferencesGroup(title="System and Background Processes")
        self.bg_list_group.set_margin_top(24)
        self.content_box.append(self.bg_list_group)
        
        self._update_list(None)

    def _build_graph(self):
        # Confidence Indicator
        conf_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        conf_box.set_halign(Gtk.Align.END)
        conf_box.set_margin_bottom(12)
        conf_dot = Gtk.Label(label="🟡")
        conf_lbl = Gtk.Label(label="Confidence: Estimated")
        conf_lbl.add_css_class("caption")
        conf_lbl.add_css_class("dim-label")
        conf_box.append(conf_dot)
        conf_box.append(conf_lbl)
        
        info_btn = Gtk.MenuButton()
        info_btn.set_icon_name("dialog-information-symbolic")
        info_btn.add_css_class("flat")
        info_btn.set_tooltip_text("Truth Confidence Model:\n🟢 RAPL Hardware Measured: Exact hardware sensing.\n🟡 Estimated: Extrapolated from CPU frequency, load, & IO.\n🔴 Low Confidence: Wayland/Flatpak process isolation.")
        conf_box.append(info_btn)
        
        self.content_box.append(conf_box)
        
        master_graph_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        master_graph_box.set_size_request(-1, 200)
        
        y_axis_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        y_axis_box.set_valign(Gtk.Align.FILL)
        y_axis_box.set_vexpand(True)
        
        lbl_max = Gtk.Label(label=f"{self.max_y}m")
        lbl_max.add_css_class("caption")
        lbl_max.add_css_class("dim-label")
        lbl_max.set_valign(Gtk.Align.START)
        
        lbl_mid = Gtk.Label(label=f"{self.max_y // 2}m")
        lbl_mid.add_css_class("caption")
        lbl_mid.add_css_class("dim-label")
        lbl_mid.set_valign(Gtk.Align.CENTER)
        lbl_mid.set_vexpand(True)
        
        lbl_min = Gtk.Label(label="0m")
        lbl_min.add_css_class("caption")
        lbl_min.add_css_class("dim-label")
        lbl_min.set_valign(Gtk.Align.END)
        lbl_min.set_margin_bottom(24) 
        
        y_axis_box.append(lbl_max)
        y_axis_box.append(lbl_mid)
        y_axis_box.append(lbl_min)
        
        master_graph_box.append(y_axis_box)
        
        graph_area = Gtk.Overlay()
        graph_area.set_hexpand(True)
        
        grid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        grid_box.set_valign(Gtk.Align.FILL)
        grid_box.set_margin_bottom(24)
        
        top_line = Gtk.Box()
        top_line.set_size_request(-1, 1)
        top_line.add_css_class("grid-line")
        grid_box.append(top_line)
        
        spacer1 = Gtk.Box()
        spacer1.set_vexpand(True)
        grid_box.append(spacer1)
        
        mid_line = Gtk.Box()
        mid_line.set_size_request(-1, 1)
        mid_line.add_css_class("grid-line")
        grid_box.append(mid_line)
        
        spacer2 = Gtk.Box()
        spacer2.set_vexpand(True)
        grid_box.append(spacer2)
        
        bottom_line = Gtk.Box()
        bottom_line.set_size_request(-1, 1)
        bottom_line.add_css_class("grid-line")
        grid_box.append(bottom_line)
        
        graph_area.set_child(grid_box)
        
        bars_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bars_container.set_homogeneous(True)
        
        self.bars = []
        
        self.graph_css = Gtk.CssProvider()
        self.graph_css.load_from_data(b"""
            .bar-user { background-color: @accent_bg_color; border-radius: 2px 2px 0 0; transition: opacity 300ms ease-out; }
            .bar-bg { background-color: #ffb74d; border-radius: 0 0 2px 2px; transition: opacity 300ms ease-out; }
            .bar-bg-only { background-color: #ffb74d; border-radius: 2px 2px 0 0; transition: opacity 300ms ease-out; }
            .bar-empty { background-color: alpha(currentColor, 0.1); border-radius: 2px; transition: opacity 300ms ease-out; }
            .grid-line { background-color: alpha(currentColor, 0.1); }
        """)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.graph_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        for b_idx in range(24):
            bucket_sessions = self.buckets[b_idx]
            total_mins = sum(s["duration_mins"] for s in bucket_sessions)
            bg_mins = sum(s["duration_mins"] for s in bucket_sessions if s.get("is_bg", False))
            user_mins = total_mins - bg_mins
            
            bar_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            bar_wrapper.set_valign(Gtk.Align.END)
            
            click_gesture = Gtk.GestureClick.new()
            click_gesture.connect("pressed", self._on_bar_clicked, b_idx)
            bar_wrapper.add_controller(click_gesture)
            
            bar_stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            bar_stack.set_halign(Gtk.Align.CENTER)
            bar_stack.set_valign(Gtk.Align.END)
            bar_stack.set_size_request(10, -1)
            
            bg_ratio = bg_mins / self.max_y if self.max_y > 0 else 0
            user_ratio = user_mins / self.max_y if self.max_y > 0 else 0
            
            bg_height = int(150 * bg_ratio)
            user_height = int(150 * user_ratio)
            
            if user_height > 0:
                user_bar = Gtk.Box()
                user_bar.set_size_request(10, user_height)
                user_bar.add_css_class("bar-user")
                bar_stack.append(user_bar)
                
            if bg_height > 0:
                bg_bar = Gtk.Box()
                bg_bar.set_size_request(10, bg_height)
                if user_height > 0:
                    bg_bar.add_css_class("bar-bg")
                else:
                    bg_bar.add_css_class("bar-bg-only")
                bar_stack.append(bg_bar)
                
            if total_mins == 0:
                empty_bar = Gtk.Box()
                empty_bar.set_size_request(10, 2)
                empty_bar.add_css_class("bar-empty")
                bar_stack.append(empty_bar)
            
            hour_24 = b_idx
            period = "AM" if hour_24 < 12 else "PM"
            hour_12 = hour_24 % 12 or 12
            lbl = Gtk.Label(label=f"{hour_12}")
            lbl.add_css_class("caption")
            lbl.add_css_class("dim-label")
            
            if b_idx % 4 != 0: # Show every 4 hours for 24 buckets to be cleaner
                lbl.set_opacity(0.0)
            
            bar_wrapper.append(bar_stack)
            bar_wrapper.append(lbl)
            
            bars_container.append(bar_wrapper)
            self.bars.append((bar_wrapper, bar_stack))
            
        graph_area.add_overlay(bars_container)
        master_graph_box.append(graph_area)
        
        self.content_box.append(master_graph_box)
        
        # graph_desc = Gtk.Label(label="Graph displays total usage time in minutes per hour window. Light orange indicates background processes.", xalign=0.0)
        # graph_desc.add_css_class("caption")
        # graph_desc.add_css_class("dim-label")
        # graph_desc.set_margin_bottom(12)
        # self.content_box.append(graph_desc)
        
        # (Already handled by global provider)
        pass

    def _on_bar_clicked(self, gesture, n_press, x, y, b_idx):
        if self.current_selected_bucket == b_idx:
            self.current_selected_bucket = None
        else:
            self.current_selected_bucket = b_idx
            
        for i, (container, bar) in enumerate(self.bars):
            if self.current_selected_bucket is not None and i != self.current_selected_bucket:
                bar.set_opacity(0.3)
            else:
                bar.set_opacity(1.0)
                
        self._update_list(self.current_selected_bucket)

    # _build_list removed because UI was reordered in __init__

    def _update_list(self, b_idx):
        for row in getattr(self, 'current_list_rows', []):
            try: self.list_group.remove(row)
            except Exception: pass
            
        for row in getattr(self, 'current_bg_rows', []):
            try: self.bg_list_group.remove(row)
            except Exception: pass
                
        for row in getattr(self, 'current_culprit_rows', []):
            try: self.culprits_group.remove(row)
            except Exception: pass
            
        for row in getattr(self, 'current_insight_rows', []):
            try: self.insights_group.remove(row)
            except Exception: pass
                
        self.current_list_rows = []
        self.current_bg_rows = []
        self.current_culprit_rows = []
        self.current_insight_rows = []
            
        sessions_to_show = []
        if b_idx is not None:
            sessions_to_show = self.buckets[b_idx]
            h_start = b_idx
            h_end = (b_idx + 1) % 24
            self.list_group.set_title(f"Active Applications ({h_start:02d}:00 - {h_end:02d}:00)")
            self.bg_list_group.set_title(f"System and Background ({h_start:02d}:00 - {h_end:02d}:00)")
        else:
            self.list_group.set_title("Active Applications (All Time)")
            self.bg_list_group.set_title("System and Background (All Time)")
            for h in range(24):
                sessions_to_show.extend(self.buckets[h])
                
        app_aggregates = {}
        for s in sessions_to_show:
            name = s["name"]
            if name not in app_aggregates:
                app_aggregates[name] = s.copy()
            else:
                app_aggregates[name]["battery_usage"] += s["battery_usage"]
                app_aggregates[name]["duration_mins"] += s["duration_mins"]
                app_aggregates[name]["closed_time"] = s["closed_time"]
                app_aggregates[name]["max_temp"] = max(app_aggregates[name].get("max_temp", 0), s.get("max_temp", 0))
                
        unique_sessions = list(app_aggregates.values())
        for u in unique_sessions:
            u["battery_usage"] = round(u["battery_usage"], 1)
                
        # Sort by battery usage rather than just duration for impact
        unique_sessions.sort(key=lambda x: x["battery_usage"], reverse=True)
        
        if not unique_sessions:
            self.culprits_group.set_visible(False)
            self.insights_group.set_visible(False)
            lbl = Gtk.Label(label="No activity recorded.", margin_top=24, margin_bottom=24)
            lbl.add_css_class("dim-label")
            self.list_group.add(lbl)
            self.current_list_rows.append(lbl)
            return

        self.culprits_group.set_visible(True)
        self.insights_group.set_visible(True)
        
        # Populate Insights Feed
        insights_added = 0
        
        if not b_idx:
            if self.comparison_text:
                row = Adw.ActionRow(title="What Changed Today?")
                row.set_subtitle(self.comparison_text)
                icon = Gtk.Label(label="📊")
                icon.add_css_class("title-2")
                row.add_prefix(icon)
                self.insights_group.add(row)
                self.current_insight_rows.append(row)
                insights_added += 1
                
            if self.aging_forecast:
                row = Adw.ActionRow(title="Battery Aging Forecast")
                row.set_subtitle(self.aging_forecast)
                icon = Gtk.Label(label="🔋")
                icon.add_css_class("title-2")
                row.add_prefix(icon)
                self.insights_group.add(row)
                self.current_insight_rows.append(row)
                insights_added += 1
                
        bg_apps = [s for s in unique_sessions if s.get("is_bg")]
        if bg_apps and bg_apps[0]["battery_usage"] > 10.0:
            row = Adw.ActionRow(title=f"Background Activity Warning")
            row.set_subtitle(f"{bg_apps[0]['name']} drained {bg_apps[0]['battery_usage']}% while invisible.")
            icon = Gtk.Label(label="⚠️")
            icon.add_css_class("title-2")
            row.add_prefix(icon)
            self.insights_group.add(row)
            self.current_insight_rows.append(row)
            insights_added += 1
            
        hot_apps = [s for s in unique_sessions if s.get("max_temp", 0) >= 75.0]
        if hot_apps:
            row = Adw.ActionRow(title=f"Thermal Spike Detected")
            row.set_subtitle(f"{hot_apps[0]['name']} caused temperatures to reach {hot_apps[0]['max_temp']}°C.")
            icon = Gtk.Label(label="🔥")
            icon.add_css_class("title-2")
            row.add_prefix(icon)
            self.insights_group.add(row)
            self.current_insight_rows.append(row)
            insights_added += 1
            
        if insights_added == 0:
            row = Adw.ActionRow(title="System Optimal")
            row.set_subtitle("No severe thermal spikes or aggressive background drains detected.")
            icon = Gtk.Label(label="✨")
            icon.add_css_class("title-2")
            row.add_prefix(icon)
            self.insights_group.add(row)
            self.current_insight_rows.append(row)
        
        # Populate culprits (Top 1 or 2 high drain apps)
        culprits_added = 0
        for session in unique_sessions:
            if session.get("is_bg", False): 
                # Skip system background tasks for user actionable culprits unless it's insane
                if session["battery_usage"] < 20.0:
                    continue
            
            if culprits_added >= 2:
                break
                
            if session["battery_usage"] > 5.0: # threshold to be a culprit
                row = Adw.ActionRow(title=session["name"])
                
                # Human explanation insight
                insight = "High background drain" if session.get("is_bg") else "Preventing idle sleep and high CPU"
                row.set_subtitle(f"Insight: {insight} ({session['battery_usage']}%)")
                row.set_activatable(True)
                
                icon = Gtk.Image.new_from_icon_name(session["icon"])
                icon.set_icon_size(Gtk.IconSize.LARGE)
                row.add_prefix(icon)
                
                row.connect("activated", lambda r, s=session: self.emit('app-clicked', s))
                self.culprits_group.add(row)
                self.current_culprit_rows.append(row)
                culprits_added += 1
                
        if culprits_added == 0:
            self.culprits_group.set_visible(False)

        for session in unique_sessions:
            row = Adw.ActionRow()
            row.set_title(session["name"])
            
            mins = session.get("duration_mins", 1)
            h = mins // 60
            m = mins % 60
            hr_str = f"{h} hr " if h > 0 else ""
            m_str = f"{m} mins" if m > 0 else ""
            if not hr_str and not m_str: m_str = "1 min"
            usage_str = (hr_str + m_str).strip()
            
            row.set_subtitle(f"Usage: {usage_str} - Last active: {session['closed_time']}")
            row.set_activatable(True)
            
            icon = Gtk.Image.new_from_icon_name(session["icon"])
            icon.set_icon_size(Gtk.IconSize.LARGE)
            row.add_prefix(icon)
            
            power_label = Gtk.Label(label=f"{session['battery_usage']}%")
            power_label.set_valign(Gtk.Align.CENTER)
            power_label.add_css_class("dim-label")
            row.add_suffix(power_label)
            
            row.connect("activated", lambda r, s=session: self.emit('app-clicked', s))
            
            if session.get("is_bg", False):
                self.bg_list_group.add(row)
                self.current_bg_rows.append(row)
            else:
                self.list_group.add(row)
                self.current_list_rows.append(row)
