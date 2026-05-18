import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Adw, Pango, GObject, Gdk, GdkPixbuf
import cairo
import io

class UsageView(Gtk.ScrolledWindow):
    __gsignals__ = {
        'app-clicked': (GObject.SignalFlags.RUN_FIRST, None, (object,))
    }

    def __init__(self, data_set, comparison_text="", aging_forecast="", **kwargs):
        super().__init__(**kwargs)
        self.comparison_text = comparison_text
        self.aging_forecast = aging_forecast
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
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
        self.labels = data_set.get("labels", [])
        self.max_y = data_set["max_y"]
        self.num_buckets = len(self.buckets)
        self.current_selected_bucket = None
        
        # 1. PRIMARY LAYER: Insights Feed
        self.insights_group = Adw.PreferencesGroup(title="Diagnostic Feed")
        self.content_box.append(self.insights_group)
        
        # 2. SECONDARY LAYER: Top Offenders
        self.culprits_group = Adw.PreferencesGroup(title="Top Battery Offenders")
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
        conf_box.set_margin_bottom(8)
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

        self.selected_bucket = None
        self.bars = []

        # Precompute per-bucket values for the draw callback
        self._graph_data = []
        for b_idx in range(self.num_buckets):
            bucket_sessions = self.buckets[b_idx]
            total_mins = sum(s["duration_mins"] for s in bucket_sessions)
            bg_mins = sum(s["duration_mins"] for s in bucket_sessions if s.get("category") == 'background')
            sys_mins = sum(s["duration_mins"] for s in bucket_sessions if s.get("category") == 'system_app')
            other_mins = max(0, total_mins - bg_mins - sys_mins)
            label_text = self.labels[b_idx] if b_idx < len(self.labels) else ""
            self._graph_data.append((bg_mins, sys_mins, other_mins, total_mins, label_text))

        # Gtk.Picture fed from an off-screen cairo.ImageSurface.
        # Avoids gi._gi_cairo bridge (not installed); renders entirely in pycairo.
        self._chart_picture = Gtk.Picture()
        self._chart_picture.set_hexpand(True)
        self._chart_picture.set_size_request(-1, 220)
        self._chart_picture.set_can_shrink(True)
        self._chart_picture.set_keep_aspect_ratio(False)

        # Render at a fixed logical size; picture scales it to fit
        self._chart_render_w = 800
        self._chart_render_h = 220
        self._render_and_set_chart()

        # Click handling
        click = Gtk.GestureClick.new()
        click.connect("pressed", self._on_chart_clicked)
        self._chart_picture.add_controller(click)

        self.content_box.append(self._chart_picture)

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
            css.load_from_data(f".lgdot{{background-color:{hex_color};border-radius:3px;}}".encode())
            dot.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            dot.add_css_class("lgdot")
            lbl = Gtk.Label(label=label)
            lbl.add_css_class("caption")
            lbl.add_css_class("dim-label")
            item.append(dot)
            item.append(lbl)
            legend_box.append(item)

        add_legend_item("Other Apps",  "#f57c00")
        add_legend_item("System Apps", "#e0e0e0")
        add_legend_item("Background",  "#ffcc80")
        self.content_box.append(legend_box)

    def _render_and_set_chart(self):
        """Render chart to ImageSurface, encode as PNG, load into GdkPixbuf, set on Picture."""
        width  = self._chart_render_w
        height = self._chart_render_h

        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx  = cairo.Context(surf)

        # Background: transparent
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()

        # Layout constants
        y_axis_w  = 40
        x_label_h = 22
        pad_top   = 10
        pad_right = 6

        chart_x = y_axis_w
        chart_y = pad_top
        chart_w = max(1, width  - y_axis_w - pad_right)
        chart_h = max(1, height - x_label_h - pad_top)

        n     = self.num_buckets
        max_y = self.max_y or 1

        # Theme: use light-on-dark defaults (matches Adwaita dark)
        fg_r, fg_g, fg_b = 1.0, 1.0, 1.0
        grid_alpha  = 0.13
        label_alpha = 0.55

        # Grid lines
        ctx.set_source_rgba(fg_r, fg_g, fg_b, grid_alpha)
        ctx.set_line_width(1.0)
        for frac in (1.0, 0.5, 0.0):
            y = chart_y + chart_h * (1.0 - frac)
            ctx.move_to(chart_x, y)
            ctx.line_to(chart_x + chart_w, y)
        ctx.stroke()

        # Y-axis labels
        def format_y(val):
            if val >= 60 and val % 60 == 0: return f"{val // 60}h"
            if val >= 60: return f"{val / 60:.1f}h"
            return f"{val}m"

        ctx.set_source_rgba(fg_r, fg_g, fg_b, label_alpha)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(11)
        for frac, val in ((1.0, max_y), (0.5, max_y // 2), (0.0, 0)):
            text = format_y(val)
            ext  = ctx.text_extents(text)
            y    = chart_y + chart_h * (1.0 - frac)
            ctx.move_to(y_axis_w - ext.width - 5, y + ext.height / 2)
            ctx.show_text(text)

        # Bar geometry
        bar_total_w = chart_w / n if n > 0 else chart_w
        bar_w       = max(3, bar_total_w * 0.55)
        bar_gap     = (bar_total_w - bar_w) / 2

        COLORS = {
            'other':  (0.961, 0.486, 0.0),
            'system': (0.878, 0.878, 0.878),
            'bg':     (1.0,   0.8,   0.502),
        }

        for b_idx, (bg_mins, sys_mins, other_mins, total_mins, label_text) in enumerate(self._graph_data):
            bar_x = chart_x + b_idx * bar_total_w + bar_gap

            total = bg_mins + sys_mins + other_mins
            if total > 0 and max_y > 0:
                bg_r    = min(1.0, bg_mins    / max_y)
                sys_r   = min(1.0, sys_mins   / max_y)
                other_r = min(1.0, other_mins / max_y)
                stack_r = bg_r + sys_r + other_r
                if stack_r > 1.0:
                    bg_r    /= stack_r
                    sys_r   /= stack_r
                    other_r /= stack_r
            else:
                bg_r = sys_r = other_r = 0.0

            alpha = 0.25 if (self.current_selected_bucket is not None and b_idx != self.current_selected_bucket) else 1.0

            cur_y = chart_y + chart_h
            for ratio, color_key in ((bg_r, 'bg'), (sys_r, 'system'), (other_r, 'other')):
                if ratio <= 0: continue
                seg_h = ratio * chart_h
                r, g, b = COLORS[color_key]
                ctx.set_source_rgba(r, g, b, alpha)
                ctx.rectangle(bar_x, cur_y - seg_h, bar_w, seg_h)
                ctx.fill()
                cur_y -= seg_h

            if total_mins == 0:
                ctx.set_source_rgba(fg_r, fg_g, fg_b, 0.08)
                ctx.rectangle(bar_x, chart_y + chart_h - 2, bar_w, 2)
                ctx.fill()

            if label_text:
                show = True
                if n == 24 and self._graph_data.index((bg_mins, sys_mins, other_mins, total_mins, label_text)) % 4 != 0:
                    show = b_idx == n - 1
                if show:
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
        """Map click x-coordinate back to bucket index using rendered dimensions."""
        alloc     = self._chart_picture.get_allocation()
        width     = alloc.width
        y_axis_w  = 40
        pad_right = 6
        chart_w   = max(1, width - y_axis_w - pad_right)
        n = self.num_buckets
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
        self._update_list(self.current_selected_bucket)


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
            label = self.labels[b_idx] if b_idx < len(self.labels) else str(b_idx)
            self.list_group.set_title(f"Active Applications ({label})")
            self.bg_list_group.set_title(f"System and Background ({label})")
        else:
            self.list_group.set_title("Active Applications (All Time)")
            self.bg_list_group.set_title("System and Background (All Time)")
            for h in range(self.num_buckets):
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
        
        if b_idx is None:
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
            row.set_subtitle(f"{bg_apps[0]['name']} has a high power score ({bg_apps[0]['battery_usage']}) while running in the background.")
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
                row.set_subtitle(f"Insight: {insight} (score: {session['battery_usage']})")
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
            
            power_label = Gtk.Label(label=f"{session['battery_usage']}")
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
