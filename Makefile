DESTDIR ?=
PREFIX   ?= /usr
APP_ID   := io.github.powerstats.PowerStats

SHARE_DIR   = $(PREFIX)/share/powerstats
BIN_DIR     = $(PREFIX)/bin
APP_DIR     = $(PREFIX)/share/applications
SYSTEMD_DIR = $(PREFIX)/lib/systemd/user
ICON_DIR    = $(PREFIX)/share/icons/hicolor

VERSION := $(shell python3 -c "import sys; sys.path.insert(0,'$(CURDIR)'); from version import __version__; print(__version__)" 2>/dev/null || echo "1.0.0")

.PHONY: all install uninstall lint test clean

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
	install -m 644 data/icons/powerstats.svg $(DESTDIR)$(ICON_DIR)/scalable/apps/$(APP_ID).svg
	install -d $(DESTDIR)$(ICON_DIR)/symbolic/apps
	install -m 644 data/icons/powerstats-symbolic.svg $(DESTDIR)$(ICON_DIR)/symbolic/apps/$(APP_ID)-symbolic.svg

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
	@echo "Uninstallation complete."

lint:
	@echo "Running linters..."
	python3 -m flake8 *.py --max-line-length=120 --extend-ignore=E501
	python3 -m isort --check-only *.py

test:
	@echo "Running test suite..."
	python3 -m pytest tests/ -v --tb=short

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/
