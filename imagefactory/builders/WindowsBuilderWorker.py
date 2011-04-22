from httplib2 import Http
from urllib import urlencode
import libxml2
import time
import deltacloud
import re
import subprocess
import socket
import sys
import logging
from imagefactory.ImageFactoryException import ImageFactoryException

class WindowsBuilderWorker:
    def __init__(self, tdl, credentials, target):
        self.tdl = libxml2.parseDoc(tdl.xml)
        self.target = target
        self.provider_user = credentials['userid']
        self.provider_key = credentials['api-key']
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

    def create_provider_image(self):
        try:
            if self.target == 'rackspace':
                try:
                    self.deltacloud = deltacloud.Deltacloud('http://localhost:3001/api', self.provider_user, self.provider_key)
                    return self.create_instance(28,3)
                except:
                    raise ImageFactoryException("Could not connect to Deltacloud instance")
        except:
            raise ImageFactoryException("Invalid create image requested for target %s" % (self.target))

    def progress(self):
        sys.stdout.write('.')
        sys.stdout.flush()

    def create_instance(self,image_id,hwp_id):
        try:
            self.instance = self.deltacloud.create_instance(image_id, { 'hwp_id':hwp_id })
            self.instance_password = self.instance.password
        except:
            raise ImageFactoryException('Could not create the Windows instance in %s' %(self.target))
        print "Creating instance %s" % self.instance.name
        while True:
            instance_pool = self.deltacloud.instance(str(self.instance.id))
            if instance_pool.state == 'PENDING':
                self.progress()
                time.sleep(10)
            elif instance_pool.state != 'PENDING' and instance_pool.state != 'RUNNING':
                raise ImageFactoryException("Could not create instance, status returned  %s" % (instance_pool.state))
            else:
                self.instance=instance_pool
                self.log.info("Instance %s created" % (self.instance.name))
                break
        return self.customize()

    def execute_command(self, command):
        sub = subprocess.Popen(["winexe",
                                "-U", "Administrator%" + self.instance_password,
                                "//" + self.instance.public_addresses[0], "--runas=Administrator%" + self.instance_password, command],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        result = sub.communicate()
        retcode = sub.poll()

        return (result[0], result[1], retcode)

    def wait_for_boot(self):
        time.sleep(20)
        s = socket.socket()
        port = 445
        status = s.connect_ex((self.instance.public_addresses[0], port))
        self.log.debug("Waiting for instance %s to come online" % (self.instance.name))
        while status !=0:
            status = s.connect_ex((self.instance.public_addresses[0], port))
            self.progress()
            time.sleep(1)
        time.sleep(20)
        s.close()
        self.status = status

    def delete_temp(self):
        qstdout, qstderr, qretcode = self.execute_command('cmd.exe /c dir c:\\temp')
    if "File Not Found" not in qstderr:
           delstdout ,delstderr, delretcode =self.execute_command('cmd.exe /c rmdir /Q /S c:\\temp')
           if delretcode != 0 :
               self.log.warning('Failed to delete temp folder %s' % (delstderr))
               return

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
                    stdout, stderr, retcode = self.execute_command("cmd.exe /c net use \\\\"+samba_path+" "+samba_password+" "+"/u:"+samba_user+" "+"&"+" "+"xcopy"+" "+"\\\\"+samba_path+"\\\\"+package_file+" "+"c:\\temp\\"+" "+"/S"+" "+"/I"+" "+"/Y")
                    if retcode != 0:
                        if stderr:
                            self.log.warning('Failed to copy package %s with error %s' % (package_name, stderr))
                        else:
                            self.log.warning('Failed to copy package %s. Unknown error' % (package_name))
                            return

                    #running the installer for each package

                    print "Installing %s" % package_name
                    stdout, stderr, retcode = self.execute_command('cmd.exe /c c:\\temp\\'+package_file+' '+package_arguments)
                    if retcode != 0:
                        if stderr:
                            self.log.warning('Failed to install package %s with error %s' % (package_name, stderr))
                        else:
                            self.log.warning('Package %s exited with code %s' % (package_name, retcode))
            self.delete_temp()
                    continue

                else:
                    raise ImageFactoryException("Failed to identify the repo share, syntax may be wrong.")
        print "Generating ICICLE and Image"
        return self.generate_icicle_and_image()


    def generate_icicle_and_image(self):
        try:
            stdout, stderr, retcode = self.execute_command('cmd.exe /c cmd.exe /c wmic os get caption, version, osarchitecture, plusversionnumber, servicepackmajorversion, servicepackminorversion')
            array = stdout.split('\r\r\n')[1].strip().split('  ')
        except:
            raise ImageFactoryException('Could not retrieve OS information %s' %(stderr))
        components = []
        for item in array:
           if item:
              components.append(item.strip())
        os = components[0].strip()
        architecture = components[1].strip()
        spmajorver = components[2].strip()
        spminorver = components[3].strip()
        version = components[4].strip()

        try:
            stdout, stderr, retcode = self.execute_command('cmd.exe /c cmd.exe /c reg Query HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall /s /v DisplayName')
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

        icicle = str(doc)
        image = self.deltacloud.create_image(self.instance.id,{'name':self.instance.name})
        return icicle, image.id


