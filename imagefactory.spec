%if 0%{?fedora} >= 21 || 0%{?rhel} >= 7
%global use_systemd 1
%else
%global use_systemd 0
# This is, of course, not set in older RPMs and is needed below
%global _unitdir /usr/lib/systemd/system
%endif

Summary: System image generation tool
Name: imagefactory
Version: 1.1.16
Release: 1%{?dist}
Source0: http://repos.fedorapeople.org/repos/aeolus/imagefactory/%{version}/tarball/%{name}-%{version}.tar.gz
License: ASL 2.0
Group: Applications/System
URL: https://github.com/redhat-imaging/imagefactory
BuildArch: noarch
%if 0%{?rhel} == 6
ExcludeArch: i386 ppc64
%endif
Requires: python3-pycurl
Requires: python3-libguestfs
Requires: python3-zope-interface
Requires: python3-libxml2
Requires: python3-httplib2
Requires: python3-cherrypy
Requires: python3-oauth2
Requires: python3-libs
Requires: oz

%if %{use_systemd}
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
BuildRequires: systemd-units
%else
Requires(post): chkconfig
Requires(preun): chkconfig
# This is for /sbin/service
Requires(preun): initscripts
%endif


BuildRequires: python3
BuildRequires: python3-setuptools
BuildRequires: python3-rpm-macros
BuildRequires: python-rpm-macros
# TODO: Any changes to the _internal_ API must increment this version or, in 
#       the case of backwards compatible changes, add a new version (RPM 
#       allows multiple version "=" lines for the same package or 
#       pseudo-package name)
Provides: imagefactory-plugin-api = 1.0

%description
imagefactory allows the creation of system images for multiple virtualization
and cloud providers from a single template definition. See 
https://github.com/redhat-imaging/imagefactory for more information.

%prep
%setup -q

%build
%py3_build


%install
%py3_install


%{__install} -d %{buildroot}/%{_sysconfdir}/imagefactory/jeos_images
%{__install} -d %{buildroot}/%{_localstatedir}/lib/imagefactory/images
%{__install} -d %{buildroot}/%{_sysconfdir}/imagefactory/plugins.d
%{__install} -d %{buildroot}/%{_sysconfdir}/logrotate.d

%{__install} -m0600 conf/sysconfig/imagefactoryd %{buildroot}/%{_sysconfdir}/sysconfig/imagefactoryd
%{__install} -m0600 conf/logrotate.d/imagefactoryd %{buildroot}/%{_sysconfdir}/logrotate.d/imagefactoryd

# setup.py installs both of these which I suppose is OK
# delete the one we don't want here
%if %{use_systemd}
rm -f %{buildroot}/%{_initddir}/imagefactoryd
%else
rm -f %{buildroot}/%{_unitdir}/imagefactoryd.service
%endif

%if %{use_systemd}

%post
%systemd_post imagefactoryd.service

%preun
%systemd_preun imagefactoryd.service

%postun
%systemd_postun imagefactoryd.service

%else

%post
/sbin/chkconfig --add imagefactoryd

%preun
if [ $1 = 0 ] ; then
    /sbin/service imagefactoryd stop >/dev/null 2>&1
    /sbin/chkconfig --del imagefactoryd
fi

%endif

%files
%doc COPYING
%if %{use_systemd}
%{_unitdir}/imagefactoryd.service
%else
%{_initddir}/imagefactoryd
%endif
%config(noreplace) %{_sysconfdir}/imagefactory/imagefactory.conf
%config(noreplace) %{_sysconfdir}/sysconfig/imagefactoryd
%config(noreplace) %{_sysconfdir}/logrotate.d/imagefactoryd
%dir %attr(0755, root, root) %{_sysconfdir}/pki/imagefactory/
%dir %attr(0755, root, root) %{_sysconfdir}/imagefactory/jeos_images/
%dir %attr(0755, root, root) %{_sysconfdir}/imagefactory/plugins.d/
%dir %attr(0755, root, root) %{_localstatedir}/lib/imagefactory/images
%config %{_sysconfdir}/pki/imagefactory/cert-ec2.pem
%{python3_sitelib}/imgfac/*.py*
%{python3_sitelib}/imgfac/__pycache__/*.py*
%{python3_sitelib}/imgfac/rest
#%{python3_sitelib}/imgfac/picklingtools
%{python3_sitelib}/imagefactory-*.egg-info
%{_bindir}/imagefactory
%{_bindir}/imagefactoryd

%changelog
* Wed Dec 16 2020 Brendan Reilly <breilly@redhat.com> 1.1.16-1
- Replaced Thread.isAlive with Thread.is_alive (mnk@mnk.dk)

* Fri Jan 10 2020 Brendan Reilly <breilly@redhat.com> - 1.1.15-1
- Upstream release 1.1.15
  - improve handling of canceled builds

* Thu Jun 20 2019 Brendan Reilly <breilly@redhat.com> - 1.1.14-1
- Upstream release 1.1.14
  - make codebase python 3 compatible

* Tue Jun 26 2018 Brendan Reilly <breilly@redhat.com> - 1.1.11-1
- Upstream release 1.1.11
  - ovfcommon: supporting OVAs with subdirectories

* Tue May 31 2016 Ian McLeod <imcleod@redhat.com> - 1.1.9-1
- Upstream release 1.1.9
  - Add HyperV Vagrant support
  - enhance vSphere and VMWare Fusion support

* Thu Mar 17 2016 Ian McLeod <imcleod@redhat.com> - 1.1.8-2
- fix RHEL7 conditional for systemd unit file content

* Wed Mar 16 2016 Ian McLeod <imcleod@redhat.com> - 1.1.8-1
- Upstream release 1.1.8
- systemd support
- docker base image updates
- significant EC2 updates for regions and instance types
- VMWare fusion vagrant box support

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 1.1.7-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.1.7-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Wed Jan 7 2015 Ian McLeod <imcleod@redhat.com> - 1.1.7-1
- Upstream release 1.1.7
- Vagrant box support added to OVA plugin

* Mon Nov 24 2014 Ian McLeod <imcleod@redhat.com> - 1.1.6-2
- Assorted fixes and features to enable rpm-ostree-toolbox integration

* Tue Oct 21 2014 Ian McLeod <imcleod@redhat.com> -1.1.6-1
- Upstream 1.1.6 release

* Tue May 6 2014 Ian McLeod <imcleod@redhat.com> - 1.1.5-1
- Rebase with upstream
- Improved CLI parameter passing support

* Thu Jan 30 2014 Steve Loranz <sloranz@redhat.com> - 1.1.3-1
- Remove references to man directories. Documentation will be hosted @ imgfac.org.

* Thu Aug 15 2013 Ian McLeod <imcleod@redhat.com> - 1.1.3
- Rebase with upstream

* Thu Sep 15 2011 Ian McLeod <imcleod@redhat.com> - 0.6.1
- Update Oz requirement to 0.7.0 or later for new target-specific package config
- Update SPEC file to restart service after an install

* Mon Apr 04 2011 Chris Lalancette <clalance@redhat.com> - 0.1.6-1
- Initial spec file.
