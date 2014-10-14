#!/usr/bin/python
#
#   Copyright 2014 Red Hat, Inc.
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

import logging
import zope
import libxml2
import json
import os
import os.path
import struct
import subprocess
import datetime
import random
import shutil
import oz.TDL
import tempfile
import tarfile
from xml.etree.ElementTree import fromstring
from imgfac.Template import Template
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.BuildDispatcher import BuildDispatcher
from imgfac.ImageFactoryException import ImageFactoryException
from imgfac.CloudDelegate import CloudDelegate
from imgfac.FactoryUtils import launch_inspect_and_mount, shutdown_and_close, remove_net_persist, create_cloud_info, parameter_cast_to_bool

class Docker(object):
    zope.interface.implements(CloudDelegate)

    compress_commands = { "xz":    "xz -T 0 --stdout %s > %s",
                          "gzip":  "gzip -c %s > %s",
                          "bzip2": "bzip2 -c %s > %s" }

    # The templates below allow us to generate base images without a running docker locally

    # imcleod@redhat.com - 26-Aug-2014
    # We know of at least two different output JSON formats.  These relate to some JSON marshaling
    # changes in the docker 1.0.0 timeframe.  At the time of this comment, the upstream registry will
    # only accept the older 0.11.1 format which is what we default to.
    # Note that there is a separate "VERSION" file in each subdirectory.  As of this comment
    # that file always contains 1.0

    docker_json_template_0_11_1 = """{{
  "id": "{idstring}",
  "comment": "{commentstring}",
  "created": "{createdtime}",
  "container_config": {{
    "Cmd": null,
    "Env": null,
    "StdinOnce": false,
    "OpenStdin": false,
    "Tty": false,
    "ExposedPorts": null,
    "AttachStdin": false,
    "AttachStdout": false,
    "Image": "",
    "Volumes": null,
    "WorkingDir": "",
    "Entrypoint": null,
    "NetworkDisabled": false,
    "OnBuild": null,
    "CpuShares": 0,
    "MemorySwap": 0,
    "Memory": 0,
    "User": "",
    "Domainname": "",
    "Hostname": "",
    "AttachStderr": false,
    "PortSpecs": null
  }},
  "docker_version": "0.11.1",
  "architecture": "{arch}",
  "os": "{os}",
  "Size": {size}
}}"""


    docker_json_template_1_0_0 = """{{
    "Comment": "{commentstring}",
    "Container": "",
    "DockerVersion": "1.0.0",
    "Parent": "",
    "Author": "",
    "Os": "{os}",
    "Created": "{createdtime}",
    "Architecture": "{arch}",
    "ContainerConfig": {{
        "MemorySwap": 0,
        "Hostname": "",
        "Entrypoint": null,
        "PortSpecs": null,
        "Memory": 0,
        "OnBuild": null,
        "OpenStdin": false,
        "Cpuset": "",
        "Env": null,
        "User": "",
        "CpuShares": 0,
        "AttachStdout": false,
        "NetworkDisabled": false,
        "WorkingDir": "",
        "Cmd": null,
        "StdinOnce": false,
        "AttachStdin": false,
        "Volumes": null,
        "Tty": false,
        "AttachStderr": false,
        "Domainname": "",
        "Image": "",
        "ExposedPorts": null
    }}, 
    "Config": null,
    "Id": "{idstring}",
    "Size": {size}
}}
"""

    docker_templates_dict = { "0.11.1": docker_json_template_0_11_1,
                          "1.0.0":  docker_json_template_1_0_0 }

    def __init__(self):
        super(Docker, self).__init__()
        self.app_config = ApplicationConfiguration().configuration
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def activity(self, activity):
        # Simple helper function
        # Activity should be a one line human-readable string indicating the task in progress
        # We log it at DEBUG and also set it as the status_detail on our active image
        self.log.debug(activity)
        self.active_image.status_detail['activity'] = activity

    def push_image_to_provider(self, builder, provider, credentials, target, target_image, parameters):
        raise ImageFactoryException("Pushing not currently supported for Docker image builds")

    def snapshot_image_on_provider(self, builder, provider, credentials, template, parameters):
        # TODO: Implement snapshot builds
        raise ImageFactoryException("Snapshot builds not currently supported for Docker")

    def _generate_docker_id(self):
        # return a random 64 digit hex number
        did = ""
        for i in range(8):
            did += "%08x" % (random.randint(0, 2 ** 32))
        return did

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.debug("builder_should_create_target_image called for Docker plugin - doing all our work here then stopping the process")
        tdlobj = oz.TDL.TDL(xmlstring=template.xml, rootpw_required=self.app_config["tdl_require_root_pw"])
        if tdlobj.arch != "x86_64":
            raise Exception("Docker plugin currently supports only x86_64 images")
        # At this point our input base_image is available as builder.base_image.data
        # We simply mount it up in libguestfs and tar out the results as builder.target_image.data
        compress_type = parameters.get('compress', None)
        if compress_type:
            if compress_type in self.compress_commands.keys():
                compress_command = self.compress_commands[compress_type]
            else:
                raise Exception("Passed unknown compression type (%s) for Docker plugin" % (compress_type))
        else:
            compress_command = None
        guestfs_handle = launch_inspect_and_mount(builder.base_image.data, readonly = True)
        self.log.debug("Creating tar of root directory of input image %s saving as output image %s" % 
                       (builder.base_image.data, builder.target_image.data) )
        guestfs_handle.tar_out_opts("/", builder.target_image.data)
        wrap_metadata = parameter_cast_to_bool(parameters.get('create_docker_metadata', True))
        if wrap_metadata:
            # Get any parameters and if they are not set, create our defaults
            repository = parameters.get('repository',tdlobj.name)
            tag = parameters.get('tag','latest')
            docker_image_id = parameters.get('docker_image_id', self._generate_docker_id())
            rdict = { repository: { tag: docker_image_id } }
                       
            dockerversion = parameters.get('dockerversion', '0.11.1')
            if not dockerversion in self.docker_templates_dict:
                raise Exception("No docker JSON template available for specified docker version (%s)" % (dockerversion))
            docker_json_template=self.docker_templates_dict[dockerversion]

            tdict = { }
            tdict['commentstring'] = parameters.get('comment', 'Created by Image Factory')
            tdict['os'] = parameters.get('os', 'linux')
            tdict['createdtime'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            tdict['arch'] = "amd64"
            tdict['idstring'] = docker_image_id
	    size = 0
            self.log.debug("Reading raw tar file to generate unpacked size estimate")
            tar =  tarfile.open(builder.target_image.data, "r")
            try:
                for tarinfo in tar:
                    if tarinfo.isfile():
                        size += tarinfo.size
            finally:
                tar.close()
            tdict['size'] = size

            image_json = docker_json_template.format(**tdict) 

            # Create directory
            storagedir = os.path.dirname(builder.target_image.data)
            tempdir = None
            try:
                tempdir = tempfile.mkdtemp(dir=storagedir)
                self.log.debug("Creating docker image directory structure in (%s)" % (tempdir))

                repositories_path = os.path.join(tempdir,'repositories')
                repositories = open(repositories_path,"w")
                json.dump(rdict, repositories)
                repositories.close()

                imagedir = os.path.join(tempdir, docker_image_id)
                os.mkdir(imagedir)

                jsonfile_path = os.path.join(imagedir,'json')
                jsonfile = open(jsonfile_path,'w')
                jsonfile.write(image_json)
                jsonfile.close()

                versionfile_path = os.path.join(imagedir,'VERSION')
                versionfile = open(versionfile_path, 'w')
                # TODO - Track version developments and compatibility
                versionfile.write("1.0")
                versionfile.close()

                layerfile_path = os.path.join(imagedir,'layer.tar')
                shutil.move(builder.target_image.data, layerfile_path)

                outtar = tarfile.TarFile(name=builder.target_image.data, mode="w")
                # It turns out that in at least some configurations or versions, Docker will
                # complain if the repositories file is not the last file in the archive
                # we add our single image directory first and then the repositories file to
                # avoid this
                outtar.add(imagedir, arcname=docker_image_id)
                outtar.add(repositories_path, arcname='repositories')
                outtar.close()
            finally:
                if tempdir:
                    try:
                        shutil.rmtree(tempdir)
                    except:
                        self.log.warning("Error encountered when removing temp dir (%s) - may not have been deleted" % (tempdir))

        if compress_command:
            self.log.debug("Compressing tar file using %s" % (compress_type))
            rawimage =  builder.target_image.data
            compimage =  builder.target_image.data + ".tmp.%s" % (compress_type)
            result = subprocess.call(compress_command % ( rawimage, compimage), shell = True)
            if result:
                raise Exception("Compression of image failed")
            self.log.debug("Compression complete, replacing original")
            os.unlink(rawimage)
            os.rename(compimage, rawimage)
            self.log.debug("Done")
        return False

    def builder_will_create_target_image(self, builder, target, image_id, template, parameters):
        raise ImageFactoryException("builder_will_create_target_image called in Docker plugin - this should never happen")


    def builder_did_create_target_image(self, builder, target, image_id, template, parameters):
        raise ImageFactoryException("builder_did_create_target_image called in Docker plugin - this should never happen") 
