---
layout: page
title: user manual (plugins)
---

% IMAGEFACTORY PLUGIN REFERENCE(7) Version 1.0 - February 22, 2012

Image Factory offers the ability to extend the support for operating systems and cloud types beyond what is included in the official releases. This document describes how plugins are used as well as how developers can write their own custom plugins.

## Using ImageFactory Plugins

Image Factory installs the stock plugins in the Python site-packages directory. If plugins are installed in another location, the path must exist in the PYTHON_PATH environment variable.

A symlink from the directory `/etc/imagefactory/plugins.d` to the plugin's .info file indicates that Image Factory should use the plugin.

The structure of a plugin is generally:

        Example_ifplugin/
                        __init__.py
                        Example_ifplugin.info
                        ExampleMain.py
                        ...

## Writing ImageFactory Plugins

There are two requirements Image Factory plugins need to satisfy.

1. Assign delegate_class in the plugin's initializer.

2. Define plugin metadata in the plugin's info document.

### Assigning the delegate class

When Image Factory builds, pushes, or takes a snapshot of an image, delegation is used to allow a plugin to customize the operation. The plugin must specify what class Image Factory should use to instantiate a delegate object. This is done by assigning the class to `delegate_class`.

*Example-ifplugin/__init__.py:*  
 
        from ExampleMain import ExampleMain as delegate_class

In the example above, _ExampleMain_ is a class that implements some or all of the methods defined in the delegate interface of one of the plugin types such as [OS](https://github.com/aeolusproject/imagefactory/blob/master/imgfac/OSDelegate.py) 
or [Cloud](https://github.com/aeolusproject/imagefactory/blob/master/imgfac/CloudDelegate.py).

Here is what the module, ExampleMain.py, might contain.

*Example-ifplugin/ExampleMain.py:*
 
        import zope
        from imgfac.CloudDelegate import CloudDelegate
        class ExampleMain(object):
            zope.interface.implements(CloudDelegate)
            def builder_should_create_image(self, builder):
                # This is just an example, don't bother creating the image
                return False

### Plugin metadata

A plugin must include a JSON formatted metadata file named _plugin-name_.info. In the example above, this file would be named *Example-ifplugin.info*.

The contents of this file are:

+ **type** - Either `os` or `cloud`
+ **targets** - List of targets tuples.  
    *Ex - OS plugin*. `[["RHEL5", "U8", "x86_64"], ["Fedora", "16", None], ["Fedora", "17", "x86_64"]]`  
    *Ex - Cloud plugin*. `["vsphere4", "vsphere5"]`
+ **description** - A long string describing the plugin.
+ **maintainer** - A dictionary with the following keys:  
    - **name** - The name of the individual or organization maintaining this plugin.  
    - **email** - An email address for queries about the plugin.  
    - **url** - A URL for more information about the plugin.  
+ **version** - A short string identifying the version.
+ **license** - The license this plugin is released under.
