---
layout: page
section: documentation
title: Installation
---

<a id="rpm" />
## Installing via RPM

1. Add the imagefactory repository.

    Fedora:

        $ su -c "(cd /etc/yum.repos.d; wget http://repos.fedorapeople.org/repos/aeolus/imagefactory/testing/repos/fedora/imagefactory.repo)"

    RHEL:

        $ su -c "(cd /etc/yum.repos.d; wget http://repos.fedorapeople.org/repos/aeolus/imagefactory/testing/repos/rhel/imagefactory.repo)"

1. Install imagefactory and the plugins.

        $ su -c "yum install imagefactory imagefactory-plugins \
        imagefactory-plugins-EC2Cloud imagefactory-plugins-RHEVM \
        imagefactory-plugins-vSphere imagefactory-plugins-MockRPMBasedOS \
        imagefactory-plugins-EC2Cloud-JEOS-images \
        imagefactory-plugins-MockSphere imagefactory-plugins-OpenStackCloud \
        imagefactory-plugins-FedoraOS"

---

<a id="setuptools" />
## Installing via setuptools

This is currently being worked on. Please watch this space for more information soon.
