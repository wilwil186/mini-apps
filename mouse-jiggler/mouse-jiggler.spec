%define name mouse-jiggler
%define version 1.0.0
%define release 1
%define arch noarch

Summary: Mouse jiggler — mueve el ratón automáticamente
Name: %{name}
Version: %{version}
Release: %{release}
License: MIT
Group: Applications/System
BuildArch: %{arch}
URL: https://github.com/wilson/mouse-jiggler
Source0: %{name}-%{version}.tar.gz
Requires: xdotool, xprintidle
Recommends: ydotool

%description
Evita que la pantalla se bloquee o el equipo se suspenda moviendo
el ratón solo cuando detecta inactividad real del usuario.
Soporta X11 (xdotool) y Wayland (ydotool).

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_sysconfdir}
mkdir -p %{buildroot}%{_mandir}/man1
mkdir -p %{buildroot}%{_unitdir}

install -m 0755 usr/bin/mouse-jiggler %{buildroot}%{_bindir}/mouse-jiggler
install -m 0644 etc/mouse-jiggler.conf %{buildroot}%{_sysconfdir}/mouse-jiggler.conf
install -m 0644 usr/share/man/man1/mouse-jiggler.1 %{buildroot}%{_mandir}/man1/mouse-jiggler.1
install -m 0644 lib/systemd/system/mouse-jiggler.service %{buildroot}%{_unitdir}/mouse-jiggler.service

%post
if [ -f /etc/mouse-jiggler.conf ]; then
    : # mantener configuración existente
else
    cat > /etc/mouse-jiggler.conf << 'EOF'
# mouse-jiggler configuration
INTERVAL=30
THRESHOLD=60
PIXELS=5
VERBOSE=false
EOF
fi

%preun
if command -v mouse-jiggler &>/dev/null; then
    mouse-jiggler stop 2>/dev/null || true
fi

%files
%{_bindir}/mouse-jiggler
%config(noreplace) %{_sysconfdir}/mouse-jiggler.conf
%{_mandir}/man1/mouse-jiggler.1*
%{_unitdir}/mouse-jiggler.service

%changelog
* Sun May 17 2026 wilson <wilson@localhost> 1.0.0-1
- Versión inicial
