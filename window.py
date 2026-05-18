import json
import logging
import os
import threading
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib

from usage_view import UsageView
from app_details import AppDetailsPage
from version import __version__
import analytics_data

log = logging.getLogger("powerstats.window")
_CONFIG_PATH = os.path.expanduser("~/.config/powerstats/config.json")

class ActivityWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("PowerStats")
        self._loading = True
        
        display = Gdk.Display.get_default()
        monitors = display.get_monitors()
        if monitors and monitors.get_n_items() > 0:
            monitor = monitors.get_item(0)
            geometry = monitor.get_geometry()
            width = int(geometry.width * 0.5)
            height = int(geometry.height * 0.8)
            self.set_default_size(width, height)
        else:
            self.set_default_size(1000, 800)

        self.analytics_data = None

        # NavigationView
        self.nav_view = Adw.NavigationView()
        self.set_content(self.nav_view)

        # Main Page
        self.main_page = Adw.NavigationPage(title="Battery Usage", tag="main")
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_page.set_child(main_box)
        
        # HeaderBar with proper title
        header = Adw.HeaderBar()
        self._window_title = Adw.WindowTitle(title="PowerStats", subtitle=f"v{__version__} — Loading…")
        header.set_title_widget(self._window_title)
        main_box.append(header)

        self._spinner = Gtk.Spinner()
        self._spinner.set_spinning(True)
        self._spinner.set_margin_top(48)
        self._spinner.set_halign(Gtk.Align.CENTER)
        self._spinner.set_valign(Gtk.Align.CENTER)
        main_box.append(self._spinner)

        top_clamp = Adw.Clamp()
        top_clamp.set_maximum_size(800)
        top_clamp.set_visible(False)
        main_box.append(top_clamp)
        
        top_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        top_clamp.set_child(top_content)

        # Settings / Info Group
        info_group = Adw.PreferencesGroup()
        info_group.set_margin_start(24)
        info_group.set_margin_end(24)
        info_group.set_margin_top(24)
        

        
        # Switch Row
        switch_row = Adw.ActionRow(title="Track Power Usage", subtitle="Collect power statistics in the background")
        power_switch = Gtk.Switch(active=True)
        power_switch.set_valign(Gtk.Align.CENTER)
        switch_row.add_suffix(power_switch)
        info_group.add(switch_row)
        
        # Power Modes (⭐ Feature)
        power_mode_row = Adw.ComboRow(title="Active Power Mode")
        power_mode_row.set_subtitle("Adjusts system performance and polling aggressiveness.")
        model = Gtk.StringList.new(["Balanced", "Quiet", "Analyze", "Battery Saver"])
        power_mode_row.set_model(model)
        
        try:
            with open(_CONFIG_PATH) as f:
                cfg = json.load(f)
                power_mode_row.set_selected(cfg.get("power_mode", 0))
        except Exception:
            pass
            
        power_mode_row.connect("notify::selected", self._on_power_mode_changed)
        info_group.add(power_mode_row)
        
        # Confidence & Transparency Button (⭐ Feature)
        transparency_btn = Gtk.Button(label="View Transparency Model")
        transparency_btn.set_halign(Gtk.Align.CENTER)
        transparency_btn.set_margin_top(12)
        transparency_btn.add_css_class("pill")
        transparency_btn.connect("clicked", self._on_transparency_clicked)
        info_group.add(transparency_btn)
        
        top_content.append(info_group)
        
        # Dropdown for timeframe
        dropdown_model = Gtk.StringList.new(["Last 24 Hours", "Last 7 Days", "Total Usage"])
        dropdown = Gtk.DropDown(model=dropdown_model)
        dropdown.set_halign(Gtk.Align.END)
        dropdown.set_margin_start(24)
        dropdown.set_margin_end(24)
        dropdown.set_margin_top(12)
        dropdown.set_margin_bottom(12)
        
        dropdown.connect("notify::selected-item", self._on_dropdown_changed)
        top_content.append(dropdown)

        # Stack for the timeframes (populated after async data load)
        self.stack = Adw.ViewStack()
        self.stack.set_vexpand(True)
        main_box.append(self.stack)

        # Add main page to nav view
        self.nav_view.add(self.main_page)

        # Lazy-load analytics data off the main thread
        self._top_clamp = top_clamp
        self._dropdown = dropdown
        threading.Thread(target=self._load_analytics_async, daemon=True).start()

    def _load_analytics_async(self) -> None:
        """Load analytics data on a background thread, then update UI on main thread."""
        log.info("Loading analytics data…")
        try:
            data = analytics_data.get_analytics_data()
        except Exception:
            log.exception("Failed to load analytics data")
            data = None
        GLib.idle_add(self._on_analytics_loaded, data)

    def _on_analytics_loaded(self, data: dict | None) -> None:
        """Called on the GTK main thread once data is ready."""
        self.analytics_data = data or {}
        self._spinner.set_spinning(False)
        self._spinner.set_visible(False)
        self._top_clamp.set_visible(True)
        self._window_title.set_subtitle(f"v{__version__} — Usage Monitor")
        log.info("Analytics data loaded, populating views")

        for view_name, view_data in self.analytics_data.items():
            if view_name in ["comparison", "aging_forecast"]:
                continue
            comp_text = self.analytics_data.get("comparison", "")
            aging_text = self.analytics_data.get("aging_forecast", "")
            view = UsageView(view_data, comp_text, aging_text)
            view.connect("app-clicked", self._on_app_clicked, view_data)
            self.stack.add_titled(view, view_name, view_name)

    def _on_dropdown_changed(self, dropdown, param):
        selected = dropdown.get_selected_item()
        if selected:
            name = selected.get_string()
            self.stack.set_visible_child_name(name)

    def _on_app_clicked(self, usage_view, session_data, day_data):
        # Push the detailed view onto the navigation stack
        details_page = AppDetailsPage(session_data, day_data)
        self.nav_view.push(details_page)

    def _on_power_mode_changed(self, combo_row, param) -> None:
        idx = combo_row.get_selected()
        os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
        try:
            with open(_CONFIG_PATH, "w") as f:
                json.dump({"power_mode": idx}, f)
        except Exception:
            log.warning("Failed to save power mode config")

    def _on_transparency_clicked(self, btn):
        page = Adw.NavigationPage(title="Transparency", tag="transparency")
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        box.append(header)
        
        clamp = Adw.Clamp()
        clamp.set_maximum_size(600)
        box.append(clamp)
        
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        content.set_margin_top(24)
        content.set_margin_bottom(24)
        content.set_margin_start(24)
        content.set_margin_end(24)
        clamp.set_child(content)
        
        title = Gtk.Label(label="Truth & Confidence Model", xalign=0.0)
        title.add_css_class("title-1")
        content.append(title)
        
        desc = Gtk.Label(label="PowerStats uses a hybrid attribution engine. We prioritize transparency over pretending our estimations are absolute hardware truths. Here is how we measure your system:", xalign=0.0)
        desc.set_wrap(True)
        content.append(desc)
        
        group = Adw.PreferencesGroup()
        
        r1 = Adw.ActionRow(title="🟢 Hardware Measured")
        r1.set_subtitle("PowerStats reads exact microjoule consumption directly from Intel RAPL or AMD P-State interfaces when root privileges are available.")
        r1.set_title_lines(1)
        r1.set_subtitle_lines(3)
        group.add(r1)
        
        r2 = Adw.ActionRow(title="🟡 Estimated (Non-Linear)")
        r2.set_subtitle("When hardware access is denied, we extrapolate power using an exponential math model based on CPU frequency scaling, core utilization, and active thermals.")
        r2.set_title_lines(1)
        r2.set_subtitle_lines(3)
        group.add(r2)
        
        r3 = Adw.ActionRow(title="🔴 Low Confidence")
        r3.set_subtitle("Wayland and Flatpak environments intentionally sandbox process visibility for privacy. In these cases, activity is heavily guessed based on general compositor load.")
        r3.set_title_lines(1)
        r3.set_subtitle_lines(3)
        group.add(r3)
        
        content.append(group)
        page.set_child(box)
        
        self.nav_view.push(page)
