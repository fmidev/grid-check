%define distnum %(/usr/lib/rpm/redhat/dist.sh --distnum)

%define PACKAGENAME grid-check
Name:           %{PACKAGENAME}
Version:        20.5.14
Release:        1%{dist}.fmi
Summary:        grid-check application
Group:          Applications/System
License:        MIT
URL:            http://www.fmi.fi
Source0: 	%{name}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
Requires:       python3

%if %{defined el8}
Requires:	python3-numpy
Requires:	python3-dateutil
Requires:	python3-PyYAML
%else if %{defined el7}
Requires:	python36-numpy
Requires:	python36-dateutil
Requires:	python36-PyYAML
%endif

Provides:	grid-check.py

AutoReqProv: no

%global debug_package %{nil}

%description
grid-check tool does basic data quality checks to gridded fields (grib)

%prep
%setup -q -n "%{PACKAGENAME}"

%build

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p %{buildroot}/%{_bindir}
cp -a grid-check.py %{buildroot}/%{_bindir}/grid-check.py

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,0755)
%{_bindir}/grid-check.py

%changelog
* Thu May 14 2020 Mikko Partio <mikko.partio@fmi.fi> - 20.5.14-1.fmi
- Add support for lagging data
* Tue May 12 2020 Mikko Partio <mikko.partio@fmi.fi> - 20.5.12-1.fmi
- Many new features, backwards incompatible
* Wed May  6 2020 Mikko Partio <mikko.partio@fmi.fi> - 20.5.6-1.fmi
- Initial build
