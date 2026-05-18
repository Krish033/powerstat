---
name: Bug Report
about: Report a bug or unexpected behavior in PowerStats
title: "[BUG] "
labels: bug
assignees: ''
---

## Bug Description
<!-- A clear and concise description of the bug -->

## Steps to Reproduce
1. 
2. 
3. 

## Expected Behavior
<!-- What you expected to happen -->

## Actual Behavior
<!-- What actually happened -->

## Screenshots
<!-- If applicable, add screenshots -->

## Environment
- **PowerStats Version**: <!-- run `python3 -c "from version import __version__; print(__version__)"` -->
- **OS / Distro**: <!-- e.g. Ubuntu 24.04, Fedora 40 -->
- **Desktop Environment**: <!-- e.g. GNOME 46, KDE 6 -->
- **Python Version**: <!-- run `python3 --version` -->
- **GTK Version**: <!-- run `python3 -c "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk; print(Gtk.get_major_version(), Gtk.get_minor_version())"` -->

## Daemon Logs
<!-- run: journalctl --user -u powerstats.service -n 50 --no-pager -->
```
paste logs here
```

## Additional Context
<!-- Any other relevant information -->
