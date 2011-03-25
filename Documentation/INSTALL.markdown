# Installing Image Factory #

## via rpm ##
Installing from an rpm will install all dependencies needed by Image Factory.  For this reason, installing from rpm is the preferred method of installation.  There are two options for rpm installation.

* __yum__

    The Aeolus project has built rpms available via the testing [repository](http://repos.fedorapeople.org/repos/aeolus/packages-testing/).     
    After adding the appropriate `.repo` file to your `/etc/yum.repos.d` directory, installation is as easy as running: `yum install imagefactory`

* __local rpm__

    We have not yet established a download location for built packages.  Until that time, one can easily build the rpm from the source as described below.

__Creating an rpm:__     
After obtaining a copy of Image Factory from [source control](git://github.com/aeolusproject/image_factory.git), run: `setup.py bdist_rpm`      
A directory named `dist` will be created to store the newly built rpm.

## via setup.py ##
After obtaining a copy of Image Factory from [source control](git://github.com/aeolusproject/image_factory.git), run: `setup.py install`        
Be sure to have the dependencies described in the Image Factory [README](https://github.com/aeolusproject/image_factory/blob/master/README.markdown) configured.