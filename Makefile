DESTDIR ?=
PREFIX ?= /usr
SHARE_DIR = $(PREFIX)/share/powerstats
BIN_DIR = $(PREFIX)/bin
APP_DIR = $(PREFIX)/share/applications
SYSTEMD_DIR = $(PREFIX)/lib/systemd/user

all:
	@echo "Nothing to build. Use 'make install' to install."

install:
	@echo "Installing PowerStats to $(DESTDIR)$(PREFIX)..."
	install -d $(DESTDIR)$(SHARE_DIR)
	install -m 644 *.py $(DESTDIR)$(SHARE_DIR)
	
	install -d $(DESTDIR)$(BIN_DIR)
	echo "#!/bin/bash" > $(DESTDIR)$(BIN_DIR)/powerstats
	echo "python3 $(SHARE_DIR)/main.py \"\$$@\"" >> $(DESTDIR)$(BIN_DIR)/powerstats
	chmod +x $(DESTDIR)$(BIN_DIR)/powerstats
	
	install -d $(DESTDIR)$(APP_DIR)
	install -m 644 packaging/powerstats.desktop $(DESTDIR)$(APP_DIR)/powerstats.desktop
	
	install -d $(DESTDIR)$(SYSTEMD_DIR)
	install -m 644 packaging/powerstats.service $(DESTDIR)$(SYSTEMD_DIR)/powerstats.service
	
	@echo "Installation complete."
	@echo "To enable the daemon for the current user, run:"
	@echo "  systemctl --user daemon-reload"
	@echo "  systemctl --user enable --now powerstats.service"

uninstall:
	@echo "Removing PowerStats..."
	rm -rf $(SHARE_DIR)
	rm -f $(BIN_DIR)/powerstats
	rm -f $(APP_DIR)/powerstats.desktop
	rm -f $(SYSTEMD_DIR)/powerstats.service
	@echo "Uninstallation complete."
