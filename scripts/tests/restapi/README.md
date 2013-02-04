## Introduction

This is a testsuite for the imgfac v2 REST interface. You can launch the tests running `nosetest` from the root directory.

Before launching the tests, you can put your favourite template files in `tdls/`. This will execute a base_build for every TDL found in that directory and, for every TDL and every target defined in TARGETS, a target_build. Builds will be threaded and monitored concurrently.

If you configure imgfac with some `target_content.xml` and are executing the tests on the same system where imgfac is deployed, the testsuite will also compare for the installed/missing pacakges of every target_image by using libguestfs (that will need to mount the VM image, that's why).


## Tests setup

Options can be configured in `tests/config`. You'll want to set in there the URL of your imgfac v2 deployment, set to localhost by default. You can also set the URL by exporting the environment variable: `IMGFAC_URL` (eg. `export IMGFAC_URL=http://myimgfachost:8075/imagefactory`).

Notable options:
- TARGETS the list of providers you want to build your target_images for
- PROVIDERS the list of providers you want to push your images to (note that for this to work you'll need to provide credentials and definitions as per the examples in `providers/`)


## Requirements

- python-nose
- python-requests
- python-libguestfs


## Notes

Currently the tests performed over http REST **do not** support oauth nor ssl, so you'll have to disable that in imgfac.


### imgfac deployment

You can get a F17 system ready for testing with the latest version of imgfac v2 by installing a minimal fedora and then:

```
# wget http://repos.fedorapeople.org/repos/aeolus/imagefactory/testing/repos/fedora/imagefactory.repo -O /etc/yum.repos.d/imagefactory.repo

# yum install imagefactory imagefactory-plugins*
```

Then disable oauth and ssl:

```
# sed -i -e '/OPTIONS/s/^/#/' /etc/sysconfig/imagefactoryd

# echo 'OPTIONS="--debug --no_ssl --no_oauth"' >> /etc/sysconfig/imagefactoryd
```

Don't forget to disable the default firewall if you're not testing localhost, the Fedora default firewall prevents external systems from connecting to your 8075.