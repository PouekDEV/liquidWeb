Name:           liquidWeb
Version:        0.9.0
Release:        1%{?dist}
Summary:        liquidWeb hardware integration stack

License:        GPL-3.0
URL:            https://github.com/PouekDEV/liquidWeb
Source0:        %{name}-%{version}.tar.gz

BuildArch:      x86_64
Requires:       systemd
Requires:       xorg-x11-server-Xvfb
Requires(pre):  shadow-utils

%description
Linux Kraken Elite 2023 LCD web integration displayer.
Services are managed via systemd using liquidWeb.target.

%prep
%autosetup

%pre
getent group liquidWeb >/dev/null || groupadd -r liquidWeb
getent passwd liquidWeb >/dev/null || \
    useradd -r -g liquidWeb -d /var/lib/liquidWeb -s /sbin/nologin \
    -c "liquidWeb system user" liquidWeb
exit 0

%build
# Nothing to build

%install
mkdir -p %{buildroot}/usr/lib/liquidWeb
mkdir -p %{buildroot}/usr/lib/systemd/system
mkdir -p %{buildroot}/var/lib/liquidWeb

install -Dm755 bin/frame-receiver %{buildroot}/usr/lib/liquidWeb/frame-receiver
install -Dm755 bin/hardware-server %{buildroot}/usr/lib/liquidWeb/hardware-server

cp -a integration-runner %{buildroot}/usr/lib/liquidWeb/

install -p -m 644 systemd/*.service %{buildroot}/usr/lib/systemd/system/
install -p -m 644 systemd/*.target  %{buildroot}/usr/lib/systemd/system/

%post
%systemd_post liquidWeb.target

%preun
%systemd_preun liquidWeb.target

%postun
%systemd_postun_with_restart liquidWeb.target

%files
/usr/lib/liquidWeb/frame-receiver
/usr/lib/liquidWeb/hardware-server
/usr/lib/liquidWeb/integration-runner/

/usr/lib/systemd/system/liquidWeb.target
/usr/lib/systemd/system/liquidWeb-integration-runner.service
/usr/lib/systemd/system/liquidWeb-frame-receiver.service
/usr/lib/systemd/system/liquidWeb-hardware-server.service

%dir %attr(0755, liquidWeb, liquidWeb) /var/lib/liquidWeb
%ghost %attr(0644, liquidWeb, liquidWeb) /var/lib/liquidWeb/curves.json

%changelog
* Thu Jan 29 2026 PouekDEV <stuff@pouekdev.one> - 0.9.0-1
- Test