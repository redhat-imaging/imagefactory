% IMAGEFACTORY PLUGIN REFERENCE(7) Version 1.0 - February 22, 2012

Image Factory offers the ability to extend the support for operating systems and cloud types beyond what is included in the official releases. This document describes how plugins are used as well as how developers can write their own custom plugins.

## Using ImageFactory Plugins

---

TBD: imcleod drafting this section. To include location, naming, and config.

## Writing ImageFactory Plugins

---

There are two requirements Image Factory plugins need to satisfy.

1. Assign delegate_class in the plugin's initializer.

2. Define plugin metadata in the plugin's info document.

### Assigning the delegate class

When Image Factory builds, pushes, or takes a snapshot of an image, delegation is used to allow a plugin to customize the operation. The plugin must specify what class Image Factory should use to instantiate a delegate object. This is done by assigning the class to `delegate_class`.

> *example_plugin/__init__.py:*  
> 
        from ExampleMain import ExampleMain as delegate_class

In the example above, _ExampleMain_ is a class that implements some or all of the methods defined in the delegate interface of one of the plugin types such as [OS](https://github.com/aeolusproject/imagefactory/blob/master/imgfac/OSDelegate.py) 
or [Cloud](https://github.com/aeolusproject/imagefactory/blob/master/imgfac/CloudDelegate.py).

Here is what the module, ExampleMain.py, might contain.

> *example_plugin/ExampleMain.py:*
> 
        import zope
        from imgfac.CloudDelegate import CloudDelegate
        class ExampleMain(object):
            zope.interface.implements(CloudDelegate)
            def builder_should_create_image(self, builder):
                # This is just an example, don't bother creating the image
                return False

### Plugin metadata

A plugin must include a JSON formatted file named info.json. The contents of this file are:

+ name - A short string identifying the plugin.
+ description - A long string describing the plugin.
+ type - Either `os` or `cloud`
+ maintainer - A dictionary with the following keys:
    - name - The name of the individual or organization maintaining this plugin.
    - email - An email address for queries about the plugin.
    - url - A URL for more information about the plugin.
+ version - A short string identifying the version.
+ license - The license this plugin is released under.
+ targets - A dictionary
    - OS plugins use key/value pairs of os_name/version_list  
        Ex. "Fedora" : ["14", "15", "16"]
    - Cloud plugins use key/value pairs of cloud_name/types  
        Ex. "ec2" : ["upload", "snapshot"]
