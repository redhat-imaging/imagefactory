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
import threading
import subprocess
import hashlib
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

    # TODO: Get rid of these silly string templates and just use the json module and dicts
    #
    #       vbatts pointed out that creating these as string templates is kind of silly
    #       since we can just build them up as nested dicts and use json tools to create
    #       the required strings.  I originally used strings to ensure absolute fidelity to
    #       the observed docker output, but there's no real technical reason to do this

    docker_json_template_0_11_1 = """{{
  "id": "{idstring}",
  "comment": "{commentstring}",
  "created": "{createdtime}",
  "container_config": {{
    "Cmd": {cmd},
    "Env": {env},
    "Labels": {label},
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
        "Env": {env},
        "User": "",
        "CpuShares": 0,
        "AttachStdout": false,
        "NetworkDisabled": false,
        "WorkingDir": "",
        "Cmd": {cmd},
        "Labels": {label},
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

    docker_json_template_1_7_0 = """{{
    "Size": {size},
    "architecture": "{arch}",
    "comment": "{commentstring}",
    "config": {{
        "AttachStderr": false,
        "AttachStdin": false,
        "AttachStdout": false,
        "Cmd": {cmd},
        "Domainname": "",
        "Entrypoint": null,
        "Env": {env},
        "ExposedPorts": null,
        "Hostname": "",
        "Image": "",
        "Labels": {label},
        "MacAddress": "",
        "NetworkDisabled": false,
        "OnBuild": null,
        "OpenStdin": false,
        "StdinOnce": false,
        "Systemd": false,
        "Tty": false,
        "User": "",
        "VolumeDriver": "",
        "Volumes": null,
        "WorkingDir": ""
    }},
    "container_config": {{
        "AttachStderr": false,
        "AttachStdin": false,
        "AttachStdout": false,
        "Cmd": null,
        "Domainname": "",
        "Entrypoint": null,
        "Env": null,
        "ExposedPorts": null,
        "Hostname": "",
        "Image": "",
        "Labels": null,
        "MacAddress": "",
        "NetworkDisabled": false,
        "OnBuild": null,
        "OpenStdin": false,
        "StdinOnce": false,
        "Systemd": false,
        "Tty": false,
        "User": "",
        "VolumeDriver": "",
        "Volumes": null,
        "WorkingDir": ""
    }},
    "created": "{createdtime}",
    "docker_version": "1.7.0",
    "id": "{idstring}",
    "os": "{os}"
}}"""

    docker_json_template_1_10_1 = """{{
    "Size": {size},
    "architecture": "{arch}",
    "comment": "{commentstring}",
    "config": {{
        "AttachStderr": false,
        "AttachStdin": false,
        "AttachStdout": false,
        "Cmd": {cmd},
        "Domainname": "",
        "Entrypoint": null,
        "Env": {env},
        "ExposedPorts": null,
        "Hostname": "",
        "Image": "",
        "Labels": {label},
        "MacAddress": "",
        "NetworkDisabled": false,
        "OnBuild": null,
        "OpenStdin": false,
        "StdinOnce": false,
        "Systemd": false,
        "Tty": false,
        "User": "",
        "VolumeDriver": "",
        "Volumes": null,
        "WorkingDir": ""
    }},
    "container_config": {{
        "AttachStderr": false,
        "AttachStdin": false,
        "AttachStdout": false,
        "Cmd": null,
        "Domainname": "",
        "Entrypoint": null,
        "Env": null,
        "ExposedPorts": null,
        "Hostname": "",
        "Image": "",
        "Labels": null,
        "MacAddress": "",
        "NetworkDisabled": false,
        "OnBuild": null,
        "OpenStdin": false,
        "StdinOnce": false,
        "Systemd": false,
        "Tty": false,
        "User": "",
        "VolumeDriver": "",
        "Volumes": null,
        "WorkingDir": ""
    }},
    "created": "{createdtime}",
    "docker_version": "1.10.1",
    "id": "{idstring}",
    "os": "{os}"
}}"""

    docker_templates_dict = { "0.11.1": docker_json_template_0_11_1,
                          "1.0.0":  docker_json_template_1_0_0,
                          "1.7.0":  docker_json_template_1_7_0,
                          "1.10.1":  docker_json_template_1_10_1 }

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

    def _file_sha256(self, filename):
        f = open(filename, "rb")
        hasher = hashlib.sha256()
        while True:
            chunk = f.read(2**20)
            if not chunk:
                break
            hasher.update(chunk)
        f.close()
        return hasher.hexdigest()

    def builder_should_create_target_image(self, builder, target, image_id, template, parameters):
        self.log.debug("builder_should_create_target_image called for Docker plugin - doing all our work here then stopping the process")
        tdlobj = oz.TDL.TDL(xmlstring=template.xml, rootpw_required=self.app_config["tdl_require_root_pw"])
        # At this point our input base_image is available as builder.base_image.data
        # We simply mount it up in libguestfs and tar out the results as builder.target_image.data
        wrap_metadata = parameter_cast_to_bool(parameters.get('create_docker_metadata', True))
        compress_type = parameters.get('compress', None)
        if compress_type:
            if compress_type in self.compress_commands.keys():
                compress_command = self.compress_commands[compress_type]
            else:
                raise Exception("Passed unknown compression type (%s) for Docker plugin" % (compress_type))
        else:
            compress_command = None
        guestfs_handle = launch_inspect_and_mount(builder.base_image.data, readonly = True)
        storagedir = os.path.dirname(builder.target_image.data)

        # guestfs lets us mount locally via the API, which is cool, but requires that
        # we call a blocking function to activate the mount, which requires a thread
        # We also need a temp dir to mount it to - do our best to clean up when things
        # go wrong
        tempdir = None
        fuse_thread = None
        try:
            tempdir = tempfile.mkdtemp(dir=storagedir)
            self.log.debug("Mounting input image locally at (%s)" % (tempdir))
            guestfs_handle.mount_local(tempdir)
            def _run_guestmount(g):
                g.mount_local_run()
            self.log.debug("Launching mount_local_run thread")
            fuse_thread = threading.Thread(group=None, target=_run_guestmount, args=(guestfs_handle,))
            fuse_thread.start()
            self.log.debug("Creating tar of entire image")
            # NOTE - we used to capture xattrs here but have reverted the change for now
            #        as SELinux xattrs break things in unexpected ways and the tar feature
            #        to allow selective inclusion is broken
            # TODO: Follow up with tar maintainers and docker image creators to find out what
            #       if any xattrs we really need to capture here
            tarcmd = [ 'tar',  '-cf', builder.target_image.data, '-C', tempdir ]
            # User may pass in a comma separated list of additional options to the tar command
            tar_options = parameters.get('tar_options', None)
            if tar_options:
                tar_options_list=tar_options.split(',')
                for option in tar_options_list:
                    tarcmd.append(option.strip())
            # User may pass in a comma separated list of excludes to override this
            # Default to ./etc/fstab as many people have complained this does not belong in Docker images
            tar_excludes = parameters.get('tar_excludes', './etc/fstab').split(',')
            for exclude in tar_excludes:
                tarcmd.append('--exclude=%s' % (exclude.strip()))
            tarcmd.append('./')
            self.log.debug("Command: %s" % (str(tarcmd)))
            subprocess.check_call(tarcmd)
            if wrap_metadata:
                self.log.debug("Estimating size of tar contents to include in Docker metadata")
                size = 0
                for root, dirs, files in os.walk(tempdir):
                    for name in files:
                        fp = os.path.join(root,name)
                        if os.path.isfile(fp) and not os.path.islink(fp):
                            size += os.path.getsize(fp)
                self.log.debug("Total real file content size (%d)" % (size))
        except Exception, e:
            self.log.exception(e)
            raise
        finally:
            if tempdir:
                try:
                    subprocess.check_call( ['umount', '-f', tempdir] )
                    os.rmdir(tempdir)
                except Exception, e:
                    self.log.exception(e)
                    self.log.error("WARNING: Could not unmount guest at (%s) - may still be mounted" % (tempdir) )
            if fuse_thread:
                fuse_thread.join(30.0)
                if fuse_thread.isAlive():
                    self.log.error("Guestfs local mount thread is still active - FUSE filesystem still mounted at (%s)" % (tempdir) )

        if wrap_metadata:
            # Get any parameters and if they are not set, create our defaults
            # Docker image names should not have uppercase characters 
            # https://fedorahosted.org/cloud/ticket/131
            repository = parameters.get('repository',tdlobj.name).lower()
            tag = parameters.get('tag','latest')
            docker_image_id = parameters.get('docker_image_id', self._generate_docker_id())
            cmd = parameters.get('docker_cmd', 'null')
            env = parameters.get('docker_env', 'null')
            label = parameters.get('docker_label', 'null')
            rdict = { repository: { tag: docker_image_id } }
                       
            dockerversion = parameters.get('dockerversion', '0.11.1')
            if not dockerversion in self.docker_templates_dict:
                raise Exception("No docker JSON template available for specified docker version (%s)" % (dockerversion))
            docker_json_template=self.docker_templates_dict[dockerversion]

            arch = tdlobj.arch
            if arch == "x86_64":
                arch = "amd64"
            elif arch == "armv7hl":
                arch = "armhfp"
            tdict = { }
            tdict['commentstring'] = parameters.get('comment', 'Created by Image Factory')
            tdict['os'] = parameters.get('os', 'linux')
            tdict['createdtime'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            tdict['arch'] = arch
            tdict['idstring'] = docker_image_id
            tdict['cmd'] = cmd
            tdict['env'] = env
            tdict['label'] = label
            tdict['size'] = size

            image_json = docker_json_template.format(**tdict) 

            # v2 images
            # TODO: Something significantly less hacky looking.....
            if dockerversion == "1.10.1":
                shasum = self._file_sha256(builder.target_image.data)
                image_v2_config = json.loads(image_json)
                # The new top level JSON file is a light modification of the layer JSON
                del image_v2_config['Size']
                del image_v2_config['id']
                image_v2_config['history'] = [ { 'comment': image_v2_config['comment'],
                                               'created': image_v2_config['created'] } ]
                image_v2_config['rootfs'] = { 'diff_ids': [ "sha256:%s" % (shasum) ],
                                            'type': 'layers' }

                # Docker wants this config file to be named after its own sha256 sum
                image_v2_config_id = hashlib.sha256(json.dumps(image_v2_config)).hexdigest()

                image_v2_manifest = [ { "Config": "%s.json" % (image_v2_config_id),
                                        "Layers": [ "%s/layer.tar" % (docker_image_id) ],
                                        "RepoTags": [ "%s:%s" % (repository, tag) ] } ]

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

                if dockerversion == "1.10.1":
                    config_path = os.path.join(tempdir, '%s.json' % (image_v2_config_id))
                    config = open(config_path, "w")
                    json.dump(image_v2_config, config)
                    config.close()

                    manifest_path = os.path.join(tempdir, 'manifest.json')
                    manifest = open(manifest_path, "w")
                    json.dump(image_v2_manifest, manifest)
                    manifest.close()

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
                if dockerversion == "1.10.1":
                    outtar.add(config_path, arcname='%s.json' % (image_v2_config_id))
                    outtar.add(manifest_path, arcname='manifest.json')
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
