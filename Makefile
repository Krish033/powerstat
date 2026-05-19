DESTDIR ?=
PREFIX   ?= /usr
APP_ID   := io.github.powerstats.PowerStats

SHARE_DIR   = $(PREFIX)/share/powerstats
BIN_DIR     = $(PREFIX)/bin
APP_DIR     = $(PREFIX)/share/applications
SYSTEMD_DIR = $(PREFIX)/lib/systemd/user
ICON_DIR    = $(PREFIX)/share/icons/hicolor

VERSION := $(shell grep -Po '(?<=__version__ = ")[^"]+' version.py 2>/dev/null || echo "1.0.0")

PNG_SIZES := 16 22 24 32 48 64 128 256 512

.PHONY: all install uninstall icons lint test clean

all:
	@echo "PowerStats v$(VERSION)"
	@echo "Usage: make install | uninstall | lint | test | clean"

install:
	@echo "Installing PowerStats v$(VERSION) to $(DESTDIR)$(PREFIX)..."
	install -d $(DESTDIR)$(SHARE_DIR)
	install -m 644 *.py $(DESTDIR)$(SHARE_DIR)

	install -d $(DESTDIR)$(BIN_DIR)
	printf '#!/bin/sh\nexec python3 $(SHARE_DIR)/main.py "$$@"\n' > $(DESTDIR)$(BIN_DIR)/powerstats
	chmod +x $(DESTDIR)$(BIN_DIR)/powerstats

	install -d $(DESTDIR)$(APP_DIR)
	install -m 644 packaging/powerstats.desktop $(DESTDIR)$(APP_DIR)/$(APP_ID).desktop

	install -d $(DESTDIR)$(SYSTEMD_DIR)
	install -m 644 packaging/powerstats.service $(DESTDIR)$(SYSTEMD_DIR)/powerstats.service

	install -d $(DESTDIR)$(ICON_DIR)/scalable/apps
	install -m 644 assets/icons/powerstats.svg $(DESTDIR)$(ICON_DIR)/scalable/apps/$(APP_ID).svg
	install -d $(DESTDIR)$(ICON_DIR)/symbolic/apps
	install -m 644 assets/icons/powerstats-symbolic.svg $(DESTDIR)$(ICON_DIR)/symbolic/apps/$(APP_ID)-symbolic.svg
	$(foreach s,$(PNG_SIZES), \
		install -d $(DESTDIR)$(ICON_DIR)/$(s)x$(s)/apps; \
		install -m 644 assets/icons/powerstats-$(s).png $(DESTDIR)$(ICON_DIR)/$(s)x$(s)/apps/$(APP_ID).png;)
	install -d $(DESTDIR)$(PREFIX)/share/pixmaps
	install -m 644 assets/icons/powerstats-256.png $(DESTDIR)$(PREFIX)/share/pixmaps/powerstats.png
	-gtk-update-icon-cache -f -t $(DESTDIR)$(ICON_DIR) 2>/dev/null || true
	-update-desktop-database $(DESTDIR)$(APP_DIR) 2>/dev/null || true
	@echo "Installation complete."
	@echo "Enable the daemon with:"
	@echo "  systemctl --user daemon-reload"
	@echo "  systemctl --user enable --now powerstats.service"

uninstall:
	@echo "Removing PowerStats..."
	rm -rf $(DESTDIR)$(SHARE_DIR)
	rm -f  $(DESTDIR)$(BIN_DIR)/powerstats
	rm -f  $(DESTDIR)$(APP_DIR)/$(APP_ID).desktop
	rm -f  $(DESTDIR)$(SYSTEMD_DIR)/powerstats.service
	rm -f  $(DESTDIR)$(ICON_DIR)/scalable/apps/$(APP_ID).svg
	rm -f  $(DESTDIR)$(ICON_DIR)/symbolic/apps/$(APP_ID)-symbolic.svg
	$(foreach s,$(PNG_SIZES), rm -f $(DESTDIR)$(ICON_DIR)/$(s)x$(s)/apps/$(APP_ID).png;)
	rm -f  $(DESTDIR)$(PREFIX)/share/pixmaps/powerstats.png
	-gtk-update-icon-cache -f -t $(DESTDIR)$(ICON_DIR) 2>/dev/null || true
	@echo "Uninstallation complete."

icons:
	@echo "Generating PNG icons..."
	bash scripts/generate-icons.sh

lint:
	@echo "Running linters..."
	python3 -m flake8 analytics_data.py daemon.py version.py --max-line-length=120 --extend-ignore=E501
	python3 -m isort --check-only analytics_data.py daemon.py version.py

test:
	@echo "Running test suite..."
	python3 -m unittest tests/test_analytics.py -v

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/
