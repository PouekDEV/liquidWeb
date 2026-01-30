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
mkdir -p %{buildroot}%{_prefix}/lib/liquidWeb
mkdir -p %{buildroot}%{_unitdir}
mkdir -p %{buildroot}%{_sharedstatedir}/liquidWeb

install -Dm755 bin/frame-receiver %{buildroot}%{_prefix}/lib/liquidWeb/frame-receiver
install -Dm755 bin/hardware-server %{buildroot}%{_prefix}/lib/liquidWeb/hardware-server

cp -a integration-runner %{buildroot}%{_prefix}/lib/liquidWeb/

install -p -m 644 systemd/*.service %{buildroot}%{_unitdir}/
install -p -m 644 systemd/*.target  %{buildroot}%{_unitdir}/

%post
%systemd_post liquidWeb.target

%preun
%systemd_preun liquidWeb.target

%postun
%systemd_postun_with_restart liquidWeb.target

%files
%{_prefix}/lib/liquidWeb/
%{_unitdir}/liquidWeb.target
%{_unitdir}/liquidWeb-integration-runner.service
%{_unitdir}/liquidWeb-frame-receiver.service
%{_unitdir}/liquidWeb-hardware-server.service

%dir %attr(0755, liquidWeb, liquidWeb) %{_sharedstatedir}/liquidWeb
%ghost %attr(0644, liquidWeb, liquidWeb) %{_sharedstatedir}/liquidWeb/curves.json

%changelog
* Thu Jan 29 2026 PouekDEV <stuff@pouekdev.one> - 0.9.0-1
- Test