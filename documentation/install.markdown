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

<a id="distutils" />
## Installing via distutils

1. Get the imagefactory source tree.

    tarball:
    
        $ wget https://github.com/aeolusproject/imagefactory/tarball/master ; tar xvf master ; rm master

    git:

        $ git clone git://github.com/aeolusproject/imagefactory.git

1. Change to the `imagefactory` or the `aeolus-imagefactory-<commit>` directory.

        $ cd aeolusproject-imagefactory-d9ce32d

    or
    
        $ cd imagefactory

1. Install imagefactory core

        $ su -c "python setup.py install"

1. Change to the `imagefactory-plugins` directory

        $ cd imagefactory-plugins

1. Install the imagefactory plugins

        $ su -c "python setup.py install"
