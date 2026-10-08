# Distro install. NixOS uses the flake module instead.
# VERSION stays in step with pyproject.toml.

PREFIX ?= /usr
VERSION ?= 0.1.0

.PHONY: all test install uninstall dist

all:

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

install:
	install -d "$(DESTDIR)$(PREFIX)/bin"
	install -d "$(DESTDIR)$(PREFIX)/lib/retro-keys/retrokeys"
	install -d "$(DESTDIR)$(PREFIX)/lib/udev/rules.d"
	install -d "$(DESTDIR)$(PREFIX)/share/applications"
	install -d "$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps"
	install -m 0644 src/retrokeys/*.py "$(DESTDIR)$(PREFIX)/lib/retro-keys/retrokeys/"
	install -m 0755 packaging/retro-keys "$(DESTDIR)$(PREFIX)/bin/retro-keys"
	install -m 0644 udev/60-retro-keys.rules "$(DESTDIR)$(PREFIX)/lib/udev/rules.d/60-retro-keys.rules"
	install -m 0644 share/retro-keys.desktop "$(DESTDIR)$(PREFIX)/share/applications/online.meijokoen.RetroKeys.desktop"
	install -m 0644 share/retro-keys.svg "$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/online.meijokoen.RetroKeys.svg"

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)/bin/retro-keys"
	rm -rf "$(DESTDIR)$(PREFIX)/lib/retro-keys"
	rm -f "$(DESTDIR)$(PREFIX)/lib/udev/rules.d/60-retro-keys.rules"
	rm -f "$(DESTDIR)$(PREFIX)/share/applications/online.meijokoen.RetroKeys.desktop"
	rm -f "$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/online.meijokoen.RetroKeys.svg"

dist:
	mkdir -p dist
	git archive --format=tar.gz --prefix=retro-keys-$(VERSION)/ -o dist/retro-keys-$(VERSION).tar.gz HEAD
