Name:           liquidWeb
Version:        0.9.0
Release:        1%{?dist}
Summary:        liquidWeb hardware integration stack

License:        GPL-3.0
URL:            https://github.com/PouekDEV/liquidWeb
Source0:        %{name}-%{version}.tar.gz

BuildArch:      x86_64
Requires:       systemd

%description
Linux Kraken Elite 2023 LCD web integration displayer

Services are managed via systemd using liquidWeb.target.

%prep
%autosetup

%build
# Nothing to build

%install
# Create base dir
mkdir -p %{buildroot}/usr/lib/liquidWeb

# Binaries
install -Dm755 bin/frame-receiver %{buildroot}/usr/lib/liquidWeb/frame-receiver
install -Dm755 bin/hardware-server %{buildroot}/usr/lib/liquidWeb/hardware-server

# Electron app (directory)
cp -a integration-runner %{buildroot}/usr/lib/liquidWeb/

# systemd units
install -Dm644 systemd/*.service %{buildroot}/lib/systemd/system/
install -Dm644 systemd/*.target  %{buildroot}/lib/systemd/system/

%post
systemctl daemon-reload
systemctl enable liquidWeb.target || true

%preun
if [ $1 -eq 0 ]; then
    systemctl disable liquidWeb.target || true
    systemctl stop liquidWeb.target || true
fi

%postun
systemctl daemon-reload

%files
/usr/lib/liquidWeb/frame-receiver
/usr/lib/liquidWeb/hardware-server
/usr/lib/liquidWeb/integration-runner

/lib/systemd/system/liquidWeb.target
/lib/systemd/system/liquidWeb-integration-runner.service
/lib/systemd/system/liquidWeb-frame-receiver.service
/lib/systemd/system/liquidWeb-hardware-server.service

%changelog
* Wed Jan 29 2026 PouekDEV <stuff@pouekdev.one> - 0.9.0-1
- Test