import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw

from window import ActivityWindow

class ActivityApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.example.PowerStats',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = ActivityWindow(application=self)
        win.present()

if __name__ == '__main__':
    app = ActivityApplication()
    app.run(sys.argv)
