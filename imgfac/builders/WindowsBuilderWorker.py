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


from qpid.messaging import *
from qpid.util import URL
from httplib2 import Http
from urllib import urlencode
import libxml2
import re
import subprocess
import socket
import sys
import os
from time import *
import random
from tempfile import * 
import boto
from boto import ec2
from M2Crypto import BN, EVP, RSA, X509
import base64
import logging
from threading import Thread
from imgfac.ImageFactoryException import ImageFactoryException


       

class Threaded_create_instance(Thread):
   
    def __init__(self, ami_id, image_id, hwp_id, boto_connection):
        Thread.__init__(self)
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.ami_id = ami_id
        self.image_id = image_id
        self.hwp_id = hwp_id
        self.boto_connection = boto_connection
        
    def progress(self):
        sys.stdout.write('.')
        sys.stdout.flush()

    def run(self):
           
       # Create a use once WinRM security group
       factory_security_group_id = random.randrange(0, 9999999999)
       factory_security_group_name = "imagefactory-%s" % (factory_security_group_id, )
       factory_security_group_desc = "Temporary ImageFactory generated security group with WinRM access"
       self.log.debug("Creating temporary security group (%s)" % (factory_security_group_name))
       factory_security_group = self.boto_connection.create_security_group(factory_security_group_name, factory_security_group_desc)
       factory_security_group.authorize('tcp', 5985, 5986, '0.0.0.0/0')
       factory_security_group.authorize('tcp', 5672, 5672, '0.0.0.0/0')


       # Create keypair
       key_name = "imagefactory-%s" % (factory_security_group_id)
       key = self.boto_connection.create_key_pair(key_name)
       # Save it to a temp file
       key_file_object = NamedTemporaryFile()
       key_file_object.write(key.material)
       key_file_object.flush()
       key_file=key_file_object.name
       
       # Launch instance
       reservation = self.boto_connection.run_instances(self.ami_id, instance_type=self.hwp_id, key_name=key_name, security_groups = [ factory_security_group_name])
       
       if len(reservation.instances) != 1:
           self.status="FAILED"
           raise ImageFactoryException("run_instances did not result in the expected single instance - stopping")

       self.instance = reservation.instances[0]
       
       sleep(10)
       
       
       for i in range(300):
           self.log.debug("Waiting for EC2 %s to start: %d/300" % (self.instance, (i*10)))
           self.instance.update()
           self.progress()
           if self.instance.state == u'running':
               break
           sleep(1)

       if self.instance.state != u'running':
           self.status="FAILED"
           raise ImageFactoryException("Instance failed to start after 1200 seconds - stopping")
       
       
       # At this point we can get the instance address, but not the password
       self.instance_address = self.instance.ip_address
       
       
       # Wait 15 mins, until the password is available
       for j in range(90):
           self.log.debug("Waiting for the EC2 instance password to be available: %d/900" % (j*10))
           self.progress()
           instance_encrypted_password = base64.b64decode(self.boto_connection.get_password_data(self.instance.id).strip('\r\n') )
           if len(instance_encrypted_password) != 0:
               break
           sleep(10)
       if len(instance_encrypted_password) == 0:
           raise ImageFactoryException("Could not get instance %s password in 15 minutes - stopping" %(self.instance))


       # Now we can get the password and decrypt it using the certificate
       pk = RSA.load_key(key_file)
       self.instance_password = pk.private_decrypt(instance_encrypted_password, RSA.pkcs1_padding)
       
       #Amazon generates passwords containing special characters that windows it's interpreting, so we need to excape them with carret. This password will be used with winrs and winrm.
       ch = ['&','<','>','[',']','{','}','^','=',';','!','\'','+','`','~']
       self.escaped_instance_password = ''
       for i in self.instance_password:
               if i in ch:
                       self.escaped_instance_password += "^"
               self.escaped_instance_password += i

       self.log.info("Instance %s created" % (self.instance.id))
       
       return self.instance.id, self.instance_address, self.escaped_instance_password


class WindowsBuilderWorker:
    def __init__(self, tdl, credentials, target, proxy_ami_id):
        self.tdl = libxml2.parseDoc(tdl.xml)
        self.target = target
        self.provider_user = credentials['userid']
        self.provider_key = credentials['api-key']
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.proxy_ami_id = proxy_ami_id

    def progress(self):
        sys.stdout.write('.')
        sys.stdout.flush()
       
    def create_provider_image(self):
        try:
           ec2region = ec2.get_region(self.target['host'], aws_access_key_id=self.provider_user, aws_secret_access_key=self.provider_key)
           self.boto = ec2region.connect(aws_access_key_id=self.provider_user, aws_secret_access_key=self.provider_key)
           proxy = Threaded_create_instance(self.proxy_ami_id, image_id=self.target['host'], hwp_id='t1.micro', boto_connection=self.boto )
           instance = Threaded_create_instance(ami_id=self.target[self.tdl.xpathEval("/template/os/arch")[0].content], image_id=self.target['host'], hwp_id='t1.micro', boto_connection=self.boto) 
           
           proxy.start()
           instance.start()

           proxy.join()
           instance.join()

           self.proxy_id, self.proxy_address, self.proxy_password = proxy.instance.id, proxy.instance_address, proxy.instance_password  
           self.instance_id, self.instance_address, self.instance_password = instance.instance.id, instance.instance_address, instance.instance_password

           return self.customize()


        except:
            raise ImageFactoryException("Invalid create image requested for target %s" % (self.target))
    



    def connect_to_proxy(self):
        try:
            self.connection = Connection(self.proxy_address, username='Administrator', password=self.proxy_password)
            self.connection.open()
            self.session = self.connection.session(str(uuid4()))

            self.sender = self.session.sender("amq.topic")
            self.receiver = self.session.receiver('reply-%s; {create:always, delete:always}' % self.session.name)
        except:
            raise ImageFactoryException('Could not connect to proxy')

    def execute_command(self, command):
        if len(command) == 0:
            self.log.debug("Command is empty")
        command ="winrs -r:"+self.instance_address+" -u:Administrator -p:"+self.instance_password+" \""+ command+"\"" 
        msg = Message(base64.b64encode(command))
        msg.reply_to = 'reply-%s' % self.session.name
        self.sender.send(msg)
        message = self.receiver.fetch()
        retcode = base64.b64decode(message.properties["retcode"])
        stderr = base64.b64decode(message.properties["stderr"])
        stdout = base64.b64decode(message.content)
        self.session.acknowledge()
        return (stdout, int(retcode), stderr)

        
    def wait_for_boot(self):
        s = socket.socket()
        port = 5985 
        self.log.debug("Waiting for instance %s to come online" % (self.instance_id))
        for k in range(300):
            self.log.debug("Waiting for the instance to become fully accessible %d/300" % (k*10))
            status = s.connect_ex((self.instance_address, port))
            self.progress()
            if status == 0:
                s.close()
                self.connect_to_proxy()
                self.test_winrm()
                self.status = status
                print
                break
            sleep(1)

    def test_winrm(self):
        winrm_command, retcode, stderr = self.execute_command("dir c:\\")
        while retcode != 0 and stderr:
            winrm_command, retcode, stderr = self.execute_command("dir c:\\")
            sleep(5)

    def delete_temp(self):
        stdout, retcode, stderr = self.execute_command("dir c:\\temp")
        if not stderr:
           delstdout, retcode, stderr =self.execute_command("rmdir /Q /S c:\\temp")
           if retcode != 0:
               self.log.warning('Failed to delete temp folder %s' % (delstdout))

    def customize(self):
        if not self.tdl.xpathEval("/template/packages/package") or not self.tdl.xpathEval("/template/packages"):
            self.log.info("No additional packages to install, skipping customization")
            return
        else:
            # wait for machine to boot
            self.wait_for_boot()

            # delete the c:\temp folder
            self.delete_temp()


            for item in self.tdl.xpathEval("/template/packages/package"):
                repo_name = item.xpathEval("repo")[0].xpathEval("@name")[0].content
                repo_share = self.tdl.xpathEval("/template/repos/repo[@name='"+repo_name+"']")[0].xpathEval("@url")[0].content
                matches = re.match(r'^smb:\/\/(.*):(.*)@(.*)$', repo_share)
                if matches:
                    samba_user =  matches.groups()[0]
                    samba_password = matches.groups()[1]
                    samba_path = matches.groups()[2]
                    package_name =  item.xpathEval("name")[0].content
                    package_file = item.xpathEval("file")[0].content
                    package_arguments = item.xpathEval("arguments")[0].content
                    #extracting the samba server name
                    matches2  = re.match(r'^(.*)', samba_path)
                    samba_server = matches2.groups()[0]

                    # wait for machine to boot
                    self.wait_for_boot()

                    # copy package to c:\temp

                    print "Copying package %s" % package_name
                    stdout, retcode, stderr = self.execute_command("cmd.exe /c net use \\\\"+samba_path+" "+samba_password+" "+"/u:"+samba_user+" "+"&"+" "+"xcopy"+" "+"\\\\"+samba_path+"\\"+package_file+" "+"c:\\temp\\"+" "+"/S"+" "+"/I"+" "+"/Y")
                    if retcode != 0 and 'The command completed successfully' not in stdout:
                        if stderr:
                            self.log.warning('Failed to copy package %s with error %s' % (package_name, stderr))
                        else:
                            self.log.warning('Failed to copy package %s. Error %s' % (package_name, stdout))
                            return

                    #running the installer for each package
                    
                    sleep(2)

                    print "Installing %s" % package_name
                    stdout, retcode, stderr = self.execute_command("cmd.exe /c c:\\temp\\"+package_file+" "+package_arguments)
                    if retcode != 0 and retcode != -2144108526 and retcode != -2144108250:
                        if stderr:
                            self.log.warning("Failed to install package %s with error %s %s" % (package_name, stderr, retcode))
                        else:
                            self.log.info("Package %s exited with code %s" % (package_name, retcode))
                    continue

                else:
                    raise ImageFactoryException("Failed to identify the repo share, syntax may be wrong.")

        # Configuring EC2Service to set a random password at next boot
        stdout, retcode, stderr = self.execute_command(r'powershell.exe -executionpolicy Bypass . {$a = Get-Content "${env:ProgramFiles}\\Amazon\\Ec2ConfigService\\Settings\\config.xml";$a[5] = $a[5].Replace(\"Disabled\", \"Enabled\"); Set-Content "${env:ProgramFiles}\\Amazon\\Ec2ConfigService\\Settings\\config.xml" $a}')
        if retcode != 0:
            raise ImageFactoryException("Failed to configure EC2Service.")

        print "Generating ICICLE"
        self.delete_temp()
        return self.generate_icicle()


    def generate_icicle(self):
        try:
            stdout, retcode, stderr = self.execute_command('cmd.exe /c  wmic os get caption, version, osarchitecture, plusversionnumber, servicepackmajorversion, servicepackminorversion /format:csv')
            components = filter(None, ((filter(None, stdout.split('\n\n'))[-1]).split(',')))
        except:
            raise ImageFactoryException('Could not retrieve OS information %s' %(stderr))

        os = components[0]
        architecture = components[1]
        spmajorver = components[2]
        spminorver = components[3]
        version = components[4]

        try:
            stdout, retcode, stderr = self.execute_command('cmd.exe /c reg Query HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall /s /v DisplayName')
            lines= stdout.splitlines()
        except:
            raise ImageFactoryException('Could not retrieve installed packages %s' %(stderr))
        items = set()
        for line in lines:
            line = line.strip()
            if line.startswith("DisplayName"):
               items.add(line.split('    ')[2])

        packages = []
        for item in items:
            packages.append(item)
        packages.sort()

        doc = libxml2.newDoc("v1.0")
        root = doc.newChild(None, "image", None)
        root.newChild(None, "OS", os)
        root.newChild(None, "architecture", architecture)
        root.newChild(None, "version", version)
        root.newChild(None, "servicepackmajorversion", spmajorver)
        root.newChild(None, "servicepackminorversion", spminorver)
        child = root.newChild(None, "packages", None)
        for item in packages:
            child.newChild(None, "package", item)

        self.icicle = str(doc)
        print "Generating Image"
        return self.create_image()

    def create_image(self):
       
        image_name = self.boto.create_image(self.instance_id, self.instance_id)
        image_obj = self.boto.get_image(image_name)
        for i in range(60):
           self.log.debug = "Waiting for the image to be saved %d/600" %(i*10)
           image_status = image_obj.update()
           self.progress()
           if image_status == u'available':
            print
            break
           sleep(10)
            
        self.terminate_instance()
        return self.icicle, image_name, self.instance_id

    def terminate_instance(self):
        try:
            self.boto.terminate_instances(str(self.instance_id))
            self.boto.terminate_instances(str(self.proxy_id))
        except:
            raise ImageFactoryException('Could not terminate instance %s' %(self.instance.id))


