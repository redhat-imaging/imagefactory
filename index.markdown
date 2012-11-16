---
layout: default
title: tagline
section: home
---

### imagefactory makes cloud image creation easy

1. Add the yum repository:

        $ su -c "(cd /etc/yum.repos.d; wget http://repos.fedorapeople.org/repos/aeolus/imagefactory/testing/repos/fedora/imagefactory.repo)"

1. Install the packages:

        $ su -c "yum install imagefactory imagefactory-plugins \
        imagefactory-plugins-FedoraOS \
        imagefactory-plugins-OpenStackCloud \
        imagefactory-plugins-RHEVM \
        imagefactory-plugins-vSphere \
        imagefactory-plugins-EC2Cloud \
        imagefactory-plugins-EC2Cloud-JEOS-images"

1. Get a system template:

        $ wget https://raw.github.com/aeolusproject/imagefactory/gh-pages/documentation/tdl/f17_x86_64.tdl

1. Build the image:

        $ su -c "imagefactory target_image --template f17_x86_64.tdl ec2"

1. Create your EC2 credentials file:

        

1. This creates an image, customized for the target cloud, that can be pushed up for use:

        $ su -c "imagefactory provider_image --id <uuid_from_previous_step> ec2 us-east-1 ec2_credentials.xml"
