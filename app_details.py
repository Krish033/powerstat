import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

class AppDetailsPage(Adw.NavigationPage):
    def __init__(self, session_data, day_data, **kwargs):
        super().__init__(title="PowerStats", tag="app_details", **kwargs)
        
        self.session = session_data
        self.day_data = day_data
        self.current_selected_bucket = None
        self.bars = []
        
        # Main Layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Toolbar
        toolbar = Adw.HeaderBar()
        toolbar.set_title_widget(Adw.WindowTitle(title="PowerStats", subtitle="Usage Monitor"))
        main_box.append(toolbar)
        
        # Content Box
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        content.set_margin_start(24)
        content.set_margin_end(24)
        
        # Header (Icon and Name)
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        header_box.set_halign(Gtk.Align.CENTER)
        
        icon = Gtk.Image.new_from_icon_name(self.session["icon"])
        icon.set_pixel_size(64)
        
        title = Gtk.Label(label=self.session["name"])
        title.add_css_class("title-1")
        
        header_box.append(icon)
        header_box.append(title)
        content.append(header_box)
        
        # 1. PRIMARY LAYER: Human Insights
        insights_group = Adw.PreferencesGroup(title="💡 Intelligent Insight")
        
        row_insight = Adw.ActionRow(title="Behavioral Impact")
        insight_text = "High background drain" if self.session.get("is_bg") else "Preventing idle sleep and high CPU"
        row_insight.set_subtitle(insight_text)
        insights_group.add(row_insight)
        
        if not self.session.get("is_bg", False) and self.session.get("battery_usage", 0) > 1.0:
            row_savings = Adw.ActionRow(title="Estimated Savings")
            saved_mins_low = int(self.session.get("battery_usage", 0) * 1.5)
            saved_mins_high = int(self.session.get("battery_usage", 0) * 3.0)
            row_savings.set_subtitle(f"Closing this application may save {saved_mins_low} - {saved_mins_high} minutes of battery life.")
            insights_group.add(row_savings)
            
        row_thermal = Adw.ActionRow(title="Thermal Impact")
        temp = self.session.get("max_temp", 45.0)
        if temp < 55:
            thermal_status = "🧊 Cool"
        elif temp < 75:
            thermal_status = "🟡 Warm"
        elif temp < 85:
            thermal_status = "🔥 Hot"
        else:
            thermal_status = "🚨 Thermally Throttling"
            
        row_thermal.set_subtitle(f"{thermal_status} ({temp}°C peak during execution)")
        insights_group.add(row_thermal)

        content.append(insights_group)
        
        # 2. SECONDARY LAYER: Impact Timeline (Graph)
        self.graph_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.graph_box.set_margin_top(12)
        content.append(self.graph_box)
        
        lbl_graph_title = Gtk.Label(label="Timeline Analysis", xalign=0.0)
        lbl_graph_title.add_css_class("heading")
        lbl_graph_title.set_margin_bottom(12)
        self.graph_box.append(lbl_graph_title)
        
        self.graph_box.append(self._build_app_graph())
        
        # Session Details List
        details_group = Adw.PreferencesGroup(title="Usage Details")
        
        # Date
        row_date = Adw.ActionRow(title="Date")
        self.lbl_date = Gtk.Label(label=self.session["date"])
        row_date.add_suffix(self.lbl_date)
        details_group.add(row_date)
        
        # Time
        row_time = Adw.ActionRow(title="Time Active")
        mins = self.session.get("duration_mins", 1)
        h = mins // 60
        m = mins % 60
        hr_str = f"{h} hr " if h > 0 else ""
        m_str = f"{m} mins" if m > 0 else ""
        if not hr_str and not m_str: m_str = "1 min"
        usage_str = (hr_str + m_str).strip()
        self.lbl_time = Gtk.Label(label=usage_str)
        row_time.add_suffix(self.lbl_time)
        details_group.add(row_time)
        
        # Battery
        row_bat = Adw.ActionRow(title="Battery Used")
        self.lbl_bat = Gtk.Label(label=f"{self.session['battery_usage']}%")
        row_bat.add_suffix(self.lbl_bat)
        details_group.add(row_bat)
        
        # Last Updated
        row_up = Adw.ActionRow(title="Last Updated At")
        self.lbl_up = Gtk.Label(label=self.session["updated_at"])
        row_up.add_suffix(self.lbl_up)
        details_group.add(row_up)
        
        content.append(details_group)
            
        # Advanced App Info
        advanced_group = Adw.PreferencesGroup(title="Advanced App Info")
        
        # Version
        row_version = Adw.ActionRow(title="Version")
        row_version.add_suffix(Gtk.Label(label=self.session.get("version", "1.0.0")))
        advanced_group.add(row_version)
        
        # Developer
        row_dev = Adw.ActionRow(title="Developer")
        row_dev.add_suffix(Gtk.Label(label=self.session.get("developer", "Unknown")))
        advanced_group.add(row_dev)
        
        # Installed
        row_inst = Adw.ActionRow(title="Installed On")
        row_inst.add_suffix(Gtk.Label(label=self.session.get("installed_date", "Unknown")))
        advanced_group.add(row_inst)
        
        # Process ID
        row_pid = Adw.ActionRow(title="Last Process ID")
        row_pid.add_suffix(Gtk.Label(label=str(self.session.get("process_id", "N/A"))))
        advanced_group.add(row_pid)
        
        content.append(advanced_group)
        
        # Action Buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        action_box.set_halign(Gtk.Align.CENTER)
        
        btn_opt = Gtk.Button(label="Optimize Battery")
        btn_opt.add_css_class("suggested-action")
        btn_opt.add_css_class("pill")
        
        btn_stop = Gtk.Button(label="Force Stop")
        
        # Force-Stop Safety Mechanism
        SAFE_NAMES = ["gnome-shell", "systemd", "xwayland", "pipewire", "pulseaudio", "networkmanager"]
        process_name = self.session.get("name", "").lower()
        is_critical = self.session.get("is_bg", False) or any(s in process_name for s in SAFE_NAMES)
        
        if is_critical:
            btn_stop.set_sensitive(False)
            btn_stop.set_tooltip_text("Safety feature: Critical system processes cannot be force stopped.")
        else:
            btn_stop.add_css_class("destructive-action")
            btn_stop.connect("clicked", self._on_force_stop_clicked)
            
        btn_stop.add_css_class("pill")
        
        action_box.append(btn_opt)
        action_box.append(btn_stop)
        
        content.append(action_box)
        
        # Wrap in ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        clamp.set_child(content)
        scrolled.set_child(clamp)
        
        main_box.append(scrolled)
        
        self.set_child(main_box)

    def _on_force_stop_clicked(self, button):
        dialog = Adw.MessageDialog(
            heading="Force Stop Application?",
            body=f"Are you sure you want to force stop {self.session.get('name')}?\nUnsaved data may be lost and the application will terminate immediately.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("stop", "Force Stop")
        dialog.set_response_appearance("stop", Adw.ResponseAppearance.DESTRUCTIVE)
        
        def on_response(dlg, response):
            if response == "stop":
                try:
                    import subprocess
                    pid = self.session.get("process_id")
                    if pid:
                        subprocess.run(["kill", "-9", str(pid)])
                except Exception:
                    pass
                
        dialog.connect("response", on_response)
        
        parent = self.get_root()
        if parent:
            dialog.set_transient_for(parent)
        dialog.present()

    def _update_details(self):
        if self.current_selected_bucket is not None:
            b_idx = self.current_selected_bucket
            app_sessions = [s for s in self.day_data["buckets"][b_idx] if s["name"] == self.session["name"]]
            
            total_bat = sum(s["battery_usage"] for s in app_sessions)
            total_mins = sum(s["duration_mins"] for s in app_sessions)
            
            h = total_mins // 60
            m = total_mins % 60
            hr_str = f"{h} hr " if h > 0 else ""
            m_str = f"{m} mins" if m > 0 else ""
            if not hr_str and not m_str: m_str = "0 mins"
            usage_str = (hr_str + m_str).strip()
            
            hour_start = b_idx
            hour_end = (b_idx + 1) % 24
            
            period_s = "AM" if hour_start < 12 else "PM"
            h_s = hour_start % 12 or 12
            
            period_e = "AM" if hour_end < 12 else "PM"
            h_e = hour_end % 12 or 12
            
            self.lbl_time.set_label(f"{usage_str} ({h_s:02d}:00 {period_s} - {h_e:02d}:00 {period_e})")
            self.lbl_bat.set_label(f"{round(total_bat, 1)}%")
            self.lbl_up.set_label("-")
            
        else:
            mins = self.session.get("duration_mins", 1)
            h = mins // 60
            m = mins % 60
            hr_str = f"{h} hr " if h > 0 else ""
            m_str = f"{m} mins" if m > 0 else ""
            if not hr_str and not m_str: m_str = "1 min"
            usage_str = (hr_str + m_str).strip()
            self.lbl_time.set_label(usage_str)
            self.lbl_bat.set_label(f"{round(self.session['battery_usage'], 1)}%")
            self.lbl_up.set_label(self.session["updated_at"])

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
                
        self._update_details()

    def _build_app_graph(self):
        graph_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        master_graph_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        master_graph_box.set_size_request(-1, 150)
        
        buckets = self.day_data["buckets"]
        app_max_y = 10
        for b_idx in range(24):
            val = sum(s["duration_mins"] for s in buckets[b_idx] if s["name"] == self.session["name"])
            if val > app_max_y: app_max_y = val
            
        app_max_y = ((int(app_max_y) // 10) + 1) * 10
        
        y_axis_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        y_axis_box.set_valign(Gtk.Align.FILL)
        y_axis_box.set_vexpand(True)
        
        lbl_max = Gtk.Label(label=f"{app_max_y}m")
        lbl_max.add_css_class("caption")
        lbl_max.add_css_class("dim-label")
        lbl_max.set_valign(Gtk.Align.START)
        
        lbl_mid = Gtk.Label(label=f"{app_max_y // 2}m")
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
        
        for _ in range(3):
            line = Gtk.Box()
            line.set_size_request(-1, 1)
            line.add_css_class("grid-line")
            grid_box.append(line)
            if _ < 2:
                spacer = Gtk.Box()
                spacer.set_vexpand(True)
                grid_box.append(spacer)
        
        graph_area.set_child(grid_box)
        
        bars_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bars_container.set_homogeneous(True)
        
        for b_idx in range(24):
            app_usage_mins = sum(s["duration_mins"] for s in buckets[b_idx] if s["name"] == self.session["name"])
            
            bar_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            bar_wrapper.set_valign(Gtk.Align.END)
            
            click_gesture = Gtk.GestureClick.new()
            click_gesture.connect("pressed", self._on_bar_clicked, b_idx)
            bar_wrapper.add_controller(click_gesture)
            
            bar = Gtk.Box()
            bar.set_halign(Gtk.Align.CENTER)
            
            ratio = app_usage_mins / app_max_y if app_max_y > 0 else 0
            height = max(4, int(150 * ratio)) if app_usage_mins > 0 else 4
            bar.set_size_request(8, height)
            
            css_provider = Gtk.CssProvider()
            if app_usage_mins > 0:
                if self.session.get("is_bg", False):
                    bg_color = "#ffb74d"
                else:
                    bg_color = "@accent_bg_color"
            else:
                bg_color = "@insensitive_bg_color"
                
            css_provider.load_from_data(f".barcolor {{ background-color: {bg_color}; border-radius: 2px 2px 0 0; transition: all 0.2s; }} .grid-line {{ background-color: alpha(@borders, 0.5); }}".encode())
            bar.get_style_context().add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            bar.add_css_class("barcolor")
            
            hour_24 = b_idx
            period = "AM" if hour_24 < 12 else "PM"
            hour_12 = hour_24 % 12 or 12
            lbl = Gtk.Label(label=f"{hour_12}")
            lbl.add_css_class("caption")
            lbl.add_css_class("dim-label")
            if b_idx % 2 != 0: lbl.set_opacity(0.0)
            
            bar_wrapper.append(bar)
            bar_wrapper.append(lbl)
            bars_container.append(bar_wrapper)
            
            self.bars.append((bar_wrapper, bar))
            
        graph_area.add_overlay(bars_container)
        master_graph_box.append(graph_area)
        
        css = Gtk.CssProvider()
        css.load_from_data(b".grid-line { background-color: alpha(currentColor, 0.1); }")
        grid_box.get_first_child().get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        graph_wrapper.append(master_graph_box)
        
        # graph_desc = Gtk.Label(label="Graph displays total usage time in minutes per hour window for this application.", xalign=0.0)
        # graph_desc.add_css_class("caption")
        # graph_desc.add_css_class("dim-label")
        # graph_desc.set_margin_bottom(12)
        # graph_wrapper.append(graph_desc)
        
        return graph_wrapper
