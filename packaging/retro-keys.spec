Name:           retro-keys
Version:        0.1.0
Release:        1%{?dist}
Summary:        Program 8BitDo Retro Keyboard Super Buttons
License:        GPL-3.0-or-later
URL:            https://github.com/timoteuszelle/retro-keys
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  make
BuildRequires:  python3
Requires:       python3 >= 3.11
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita >= 1.5
Requires:       adwaita-icon-theme
Requires:       systemd-udev

%description
Retro Keys stores a profile on an 8BitDo Retro Keyboard. A mapping is
one key, a modifier plus a key, or a macro. A Dual Super Buttons pad
can use any of the A, B, X, and Y jacks.

%prep
%autosetup -n %{name}-%{version}

%build

%install
make install DESTDIR=%{buildroot} PREFIX=%{_prefix}

%check
make test

%post
if [ -x /usr/bin/udevadm ]; then
    udevadm control --reload-rules || :
    udevadm trigger --subsystem-match=hidraw || :
fi

%postun
if [ -x /usr/bin/udevadm ]; then
    udevadm control --reload-rules || :
    udevadm trigger --subsystem-match=hidraw || :
fi

%files
%license LICENSE
%doc README.md
%{_bindir}/retro-keys
%{_prefix}/lib/retro-keys
%{_udevrulesdir}/60-retro-keys.rules
%{_datadir}/applications/online.meijokoen.RetroKeys.desktop
%{_datadir}/icons/hicolor/scalable/apps/online.meijokoen.RetroKeys.svg

%changelog
* Thu Oct 08 2026 Tim Oudesluijs-Zelle <tim@oudesluijszelle.nl> - 0.1.0-1
- Package Retro Keys for Fedora and RHEL.
