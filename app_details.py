import io
import logging
import subprocess
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Adw, GdkPixbuf
from datetime import timedelta
import cairo

log = logging.getLogger("powerstats.app_details")

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
        toolbar.set_title_widget(Adw.WindowTitle(title=self.session.get("name", "App Details"), subtitle="Usage Details"))
        
        # Move Force Stop to top right
        self.btn_stop = Gtk.Button(icon_name="process-stop-symbolic")
        self.btn_stop.add_css_class("flat")
        self.btn_stop.set_tooltip_text("Force Stop Application")
        
        SAFE_NAMES = ["gnome-shell", "systemd", "xwayland", "pipewire", "pulseaudio", "networkmanager"]
        process_name = self.session.get("name", "").lower()
        is_critical = self.session.get("is_bg", False) or any(s in process_name for s in SAFE_NAMES)
        
        if is_critical:
            self.btn_stop.set_sensitive(False)
            self.btn_stop.set_tooltip_text("Safety feature: Critical processes cannot be force stopped.")
        else:
            self.btn_stop.add_css_class("destructive-action")
            self.btn_stop.connect("clicked", self._on_force_stop_clicked)
            
        toolbar.pack_end(self.btn_stop)
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
        insights_group = Adw.PreferencesGroup(title="Intelligent Insight")
        
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
        self.lbl_bat = Gtk.Label(label=f"{self.session['battery_usage']}")
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
        
        # Action Buttons removed for minimalism, Force Stop moved to toolbar
        pass
        
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
                    pid = self.session.get("process_id")
                    if pid:
                        subprocess.run(["kill", "-9", str(pid)], check=False)
                except Exception:
                    log.exception("Force stop failed for pid %s", self.session.get("process_id"))
                
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
            
            # Safely get bucket time range for display
            bucket_entries = self.day_data["buckets"][b_idx]
            bucket_start = None
            if bucket_entries:
                bucket_start = bucket_entries[0].get("start_time_dt")
            
            if bucket_start is not None:
                bucket_end = bucket_start + timedelta(hours=1)
                
                period_s = "AM" if bucket_start.hour < 12 else "PM"
                h_s = bucket_start.hour % 12 or 12
                
                period_e = "AM" if bucket_end.hour < 12 else "PM"
                h_e = bucket_end.hour % 12 or 12
                
                self.lbl_time.set_label(f"{usage_str} ({h_s:02d}:00 {period_s} - {h_e:02d}:00 {period_e})")
            else:
                label_text = self.day_data["labels"][b_idx] if b_idx < len(self.day_data["labels"]) else ""
                self.lbl_time.set_label(f"{usage_str} ({label_text})")
                
            self.lbl_bat.set_label(f"{round(total_bat, 1)}")
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
            self.lbl_bat.set_label(f"{round(self.session['battery_usage'], 1)}")
            self.lbl_up.set_label(self.session["updated_at"])


    def _build_app_graph(self):
        graph_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        buckets   = self.day_data["buckets"]
        num_buckets = len(buckets)
        app_name  = self.session["name"]
        cat       = self.session.get("category", "other_app")

        # Precompute per-bucket data
        self._app_graph_data = []
        app_max_y = 10
        for b_idx in range(num_buckets):
            app_sessions = [s for s in buckets[b_idx] if s["name"] == app_name]
            if app_sessions:
                dur = app_sessions[0]["duration_mins"]
                procs = app_sessions[0].get("processes", [])
                if dur > app_max_y:
                    app_max_y = dur
            else:
                dur = 0
                procs = []
            label_text = self.day_data["labels"][b_idx] if b_idx < len(self.day_data["labels"]) else ""
            show_label = not (num_buckets == 24 and b_idx % 4 != 0 and b_idx != 23)
            self._app_graph_data.append((dur, procs, label_text, show_label))

        self._app_max_y  = ((int(app_max_y) // 10) + 1) * 10
        self._app_cat    = cat
        self._num_buckets = num_buckets

        # Gtk.Picture fed from off-screen cairo.ImageSurface (bypasses gi._gi_cairo).
        self._chart_picture = Gtk.Picture()
        self._chart_picture.set_hexpand(True)
        self._chart_picture.set_size_request(-1, 220)
        self._chart_picture.set_can_shrink(True)
        self._chart_picture.set_keep_aspect_ratio(False)

        self._chart_render_w = 800
        self._chart_render_h = 220
        self._render_and_set_chart()

        click = Gtk.GestureClick.new()
        click.connect("pressed", self._on_chart_clicked)
        self._chart_picture.add_controller(click)

        graph_wrapper.append(self._chart_picture)

        # Legend below chart
        legend_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        legend_box.set_halign(Gtk.Align.CENTER)
        legend_box.set_margin_top(4)
        legend_box.set_margin_bottom(8)

        def add_legend_item(label, hex_color):
            item = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            dot = Gtk.Box()
            dot.set_size_request(12, 12)
            dot.set_valign(Gtk.Align.CENTER)
            css = Gtk.CssProvider()
            css.load_from_data(f".lgdot2{{background-color:{hex_color};border-radius:3px;}}".encode())
            dot.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            dot.add_css_class("lgdot2")
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("caption")
            lbl.add_css_class("dim-label")
            item.append(dot)
            item.append(lbl)
            legend_box.append(item)

        if cat == 'background':
            add_legend_item("Background Process", "#ffffff")
        elif cat == 'system_app':
            add_legend_item("System App", "#ffcc80")
        else:
            add_legend_item("User App", "#f57c00")
        graph_wrapper.append(legend_box)

        return graph_wrapper

    def _render_and_set_chart(self):
        """Render app timeline to ImageSurface -> PNG -> GdkPixbuf -> Gtk.Picture."""
        width  = self._chart_render_w
        height = self._chart_render_h

        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx  = cairo.Context(surf)

        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()

        y_axis_w  = 40
        x_label_h = 22
        pad_top   = 10
        pad_right = 6

        chart_x = y_axis_w
        chart_y = pad_top
        chart_w = max(1, width  - y_axis_w - pad_right)
        chart_h = max(1, height - x_label_h - pad_top)

        n     = self._num_buckets
        max_y = self._app_max_y or 1
        cat   = self._app_cat

        fg_r, fg_g, fg_b = 1.0, 1.0, 1.0
        grid_alpha  = 0.13
        label_alpha = 0.55

        if cat == 'background':
            bar_rgb = (0.88, 0.88, 0.88)
        elif cat == 'system_app':
            bar_rgb = (1.0, 0.8, 0.502)
        else:
            bar_rgb = (0.961, 0.486, 0.0)

        # Grid lines
        ctx.set_source_rgba(fg_r, fg_g, fg_b, grid_alpha)
        ctx.set_line_width(1.0)
        for frac in (1.0, 0.5, 0.0):
            y = chart_y + chart_h * (1.0 - frac)
            ctx.move_to(chart_x, y)
            ctx.line_to(chart_x + chart_w, y)
        ctx.stroke()

        # Y-axis labels
        ctx.set_source_rgba(fg_r, fg_g, fg_b, label_alpha)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(11)
        for frac, val in ((1.0, max_y), (0.5, max_y // 2), (0.0, 0)):
            text = f"{val}m"
            ext  = ctx.text_extents(text)
            y    = chart_y + chart_h * (1.0 - frac)
            ctx.move_to(y_axis_w - ext.width - 5, y + ext.height / 2)
            ctx.show_text(text)

        bar_total_w = chart_w / n if n > 0 else chart_w
        bar_w       = max(3, bar_total_w * 0.55)
        bar_gap     = (bar_total_w - bar_w) / 2

        for b_idx, (dur, procs, label_text, show_label) in enumerate(self._app_graph_data):
            bar_x = chart_x + b_idx * bar_total_w + bar_gap
            alpha = 0.25 if (self.current_selected_bucket is not None and b_idx != self.current_selected_bucket) else 1.0

            if dur > 0:
                ratio = min(1.0, dur / max_y)
                bar_h = ratio * chart_h
                r, g, b = bar_rgb
                ctx.set_source_rgba(r, g, b, alpha)
                ctx.rectangle(bar_x, chart_y + chart_h - bar_h, bar_w, bar_h)
                ctx.fill()
            else:
                ctx.set_source_rgba(fg_r, fg_g, fg_b, 0.08 * alpha)
                ctx.rectangle(bar_x, chart_y + chart_h - 2, bar_w, 2)
                ctx.fill()

            if show_label and label_text:
                ctx.set_source_rgba(fg_r, fg_g, fg_b, label_alpha)
                ctx.set_font_size(10)
                ext = ctx.text_extents(label_text)
                lx  = bar_x + bar_w / 2 - ext.width / 2
                ly  = chart_y + chart_h + x_label_h - 5
                ctx.move_to(lx, ly)
                ctx.show_text(label_text)

        buf = io.BytesIO()
        surf.write_to_png(buf)
        data = buf.getvalue()

        loader = GdkPixbuf.PixbufLoader.new_with_type('png')
        loader.write(data)
        loader.close()
        pb = loader.get_pixbuf()
        self._chart_picture.set_pixbuf(pb)

    def _on_chart_clicked(self, gesture, n_press, x, y):
        """Map click x-coordinate back to bucket index."""
        alloc = self._chart_picture.get_allocation()
        y_axis_w  = 40
        pad_right = 6
        chart_w   = max(1, alloc.width - y_axis_w - pad_right)
        n = self._num_buckets
        if n == 0: return
        bar_total_w = chart_w / n
        bx = x - y_axis_w
        if bx < 0 or bx > chart_w: return
        b_idx = max(0, min(n - 1, int(bx / bar_total_w)))

        if self.current_selected_bucket == b_idx:
            self.current_selected_bucket = None
        else:
            self.current_selected_bucket = b_idx

        self._render_and_set_chart()
        self._update_details()
