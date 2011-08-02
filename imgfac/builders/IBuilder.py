#
#   Copyright 2011 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import zope.interface
from zope.interface import Interface
from zope.interface import Attribute
from zope.interface import Invalid


def conforms_to_interface_invariant(obj):
    """Invariant method testing for mandatory aspects of the interface.
    Returns 'Invalid' exception if the implementing object does not conform."""
    try:
        getattr(obj, "template")
        getattr(obj, "target")
        getattr(obj, "target_id")
        getattr(obj, "provider")
        getattr(obj, "new_image_id")
        getattr(obj, "image")
        getattr(obj, "status")
        getattr(obj, "percent_complete")
        getattr(obj, "output_descriptor")
        getattr(obj, "delegate")
        getattr(obj, "build_image")
        getattr(obj, "abort")
        getattr(obj, "push_image")
    except AttributeError, e:
        raise Invalid(e)


class IBuilder(Interface):
    """The Builder interface provides guidance on attributes and methods
    that expected by Image Factory for objects that serve to build OS images."""
    # set the invariant checks
    zope.interface.invariant(conforms_to_interface_invariant)
    # attributes
    template = Attribute("""Template object created using the template string passed to the initializer. This string can be a UUID, URL, or XML document.""")
    target = Attribute("""The target backend the image is being built for.""")
    target_id = Attribute("""The unique handle or representation of the Replicated Image in the provider instance. For Amazon this will be an AMI. It's unclear what this might be on other providers.""")
    provider = Attribute("""Where the image is to be deployed / launched. (eg. ec2-us-west)""")
    new_image_id = Attribute("""A Universal Unique Identifier for the newly created target or provider image.""")
    image = Attribute("""Reference to the image file being built.""")
    status = Attribute("""Status of the image build process.""")
    percent_complete = Attribute("""Completion percentage for an image build in progress.""")
    output_descriptor = Attribute("""ICICLE document describing what was actually installed in the image.""")
    delegate = Attribute("""Object conforming to the BuilderDelegate interface.""")
    # methods
    def build_image(build_id=None):
        """Tell the builder to start building the image."""

    def abort():
        """Tell the builder to stop building the image."""

    def push_image(target_image_id, provider, credentials):
        """Deploy an image to the cloud provider."""
