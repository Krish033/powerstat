import sys
import time
import logging
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw

from version import __app_id__, __app_name__, __version__

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("powerstats")

_t_start = time.monotonic()


class ActivityApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

    def do_activate(self) -> None:
        win = self.props.active_window
        if not win:
            from window import ActivityWindow
            win = ActivityWindow(application=self)
        win.present()
        log.info(
            "%s v%s ready in %.2fs",
            __app_name__,
            __version__,
            time.monotonic() - _t_start,
        )


if __name__ == "__main__":
    log.info("Starting %s v%s", __app_name__, __version__)
    app = ActivityApplication()
    app.run(sys.argv)
