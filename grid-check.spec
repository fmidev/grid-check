%if !0%{?version:1}
%define version 22.5.31
%endif

%if !0%{?release:1}
%define release 1
%endif

%define distnum %(/usr/lib/rpm/redhat/dist.sh --distnum)

%if %{distnum} == 8
%define python python3.11
%else
%define python python3.11
%endif

Name:           grid-check
Version:        %{version}
Release:        %{release}%{dist}.fmi
Summary:        grid-check application
Group:          Applications/System
License:        MIT
URL:            http://www.fmi.fi
Source0: 	%{name}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildRequires:	redhat-rpm-config
BuildRequires:	%{python}
Requires:	%{python}
Requires:	%{python}-numpy
Requires:	%{python}-pyyaml

Provides:	grid-check.py

AutoReqProv: no

%global debug_package %{nil}
%global __brp_mangle_shebangs %{nil}

%description
grid-check tool does basic data quality checks to gridded fields (grib)

%prep
%setup -q -n "grid-check"

%build

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p %{buildroot}/%{_bindir} %{buildroot}/%{_libdir}/python3.11/site-packages/grid-check
cp -va grid-check.py %{buildroot}/%{_bindir}/grid-check.py
cp -var src/* %{buildroot}/%{_libdir}/python3.11/site-packages/

%clean
rm -rf %{buildroot}

%post
echo 'Some python libraries need to be installed manually with pip.' > /dev/stderr
echo 'Run python3.11 -m pip install eccodes pydash fsspec s3fs' > /dev/stderr

%files
%defattr(-,root,root,0755)
%{_bindir}/grid-check.py
%{_libdir}/python3.11/site-packages/grid_check/

%changelog
* Tue May 31 2022 Mikko Partio <mikko.partio@fmi.fi> - 22.5.31-1.fmi
- New release
* Thu May 14 2020 Mikko Partio <mikko.partio@fmi.fi> - 20.5.14-1.fmi
- Add support for lagging data
* Tue May 12 2020 Mikko Partio <mikko.partio@fmi.fi> - 20.5.12-1.fmi
- Many new features, backwards incompatible
* Wed May  6 2020 Mikko Partio <mikko.partio@fmi.fi> - 20.5.6-1.fmi
- Initial build
