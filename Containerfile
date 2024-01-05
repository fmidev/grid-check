FROM rockylinux/rockylinux:9

RUN rpm -ivh https://download.fmi.fi/smartmet-open/rhel/9/x86_64/smartmet-open-release-latest-9.noarch.rpm \
             https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm && \
    dnf -y install dnf-plugins-core && \
    dnf config-manager --setopt="epel.exclude=eccodes*" --save && \
    dnf -y update && \
    dnf -y install git eccodes grid-check && \
    dnf -y clean all

#RUN git clone https://github.com/fmidev/grid-check.git

#WORKDIR /grid-check

#ENV PATH /grid-check:$PATH

#RUN python3.11 -m pip --no-cache-dir install -r requirements.txt && \
#    python3.11 -m pip --no-cache-dir install s3cmd && \
#    sed -i 's/python3/python3.11/' grid-check.py
