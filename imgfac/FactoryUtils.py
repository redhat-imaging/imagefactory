#!/usr/bin/python

# A set of helpful utility functions
# Avoid imports that are too specific to a given cloud or OS
# We want to allow people to import all of these
# Add logging option

import guestfs
import os
import re
from imgfac.ImageFactoryException import ImageFactoryException
import subprocess
import logging


def launch_inspect_and_mount(diskfile, readonly=False):
    g = guestfs.GuestFS()
    # Added to allow plugins that wish to inspect base images without modifying them
    # (once FINISHED images should never be changed)
    if readonly:
        g.add_drive_ro(diskfile)
    else:
        g.add_drive(diskfile)
    g.launch()
    return inspect_and_mount(g, diskfile=diskfile)

def inspect_and_mount(guestfs_handle, relative_mount="", diskfile='*unspecified*'):
    g = guestfs_handle
    # Breaking this out allows the EC2 cloud plugin to avoid duplicating this
    inspection = g.inspect_os()
    if len(inspection) == 0:
        raise Exception("Unable to find an OS on disk image (%s)" % (diskfile))
    if len(inspection) > 1:
        raise Exception("Found multiple OSes on disk image (%s)" % (diskfile))
    filesystems = g.inspect_get_mountpoints(inspection[0])
    fshash = { }
    for filesystem in filesystems:
        fshash[filesystem[0]] = filesystem[1]
 
    mountpoints = fshash.keys()
    # per suggestion in libguestfs doc - sort the mount points on length
    # simple way to ensure that mount points are present before a mount is attempted
    mountpoints.sort(key=len)
    for mountpoint in mountpoints:
        g.mount_options("", fshash[mountpoint], relative_mount + mountpoint)

    return g

def shutdown_and_close(guestfs_handle):
    shutdown_result = guestfs_handle.shutdown()
    guestfs_handle.close()
    if shutdown_result:
        raise Exception("Error encountered during guestfs shutdown - data may not have been written out")

def remove_net_persist(guestfs_handle):
    # In the cloud context we currently never need or want persistent net device names
    # This is known to break networking in RHEL/VMWare and could potentially do so elsewhere
    # Just delete the file to be safe
    g = guestfs_handle
    if g.is_file("/etc/udev/rules.d/70-persistent-net.rules"):
        g.rm("/etc/udev/rules.d/70-persistent-net.rules")

    # Also clear out the MAC address this image was bound to.
    g.aug_init("/", 0)
    # This silently fails, without an exception, if the HWADDR is already gone
    g.aug_rm("/files/etc/sysconfig/network-scripts/ifcfg-eth0/HWADDR")
    g.aug_save()
    g.aug_close()

def create_cloud_info(guestfs_handle, target):
    tmpl = 'CLOUD_TYPE="%s"\n' % (target)
    guestfs_handle.write("/etc/sysconfig/cloud-info", tmpl)

def subprocess_check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    process = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)

    stdout, stderr = process.communicate()
    retcode = process.poll()

    if retcode:
        cmd = ' '.join(*popenargs)
        raise ImageFactoryException("'%s' failed(%d): %s" % (cmd, retcode, stderr))
    return (stdout, stderr, retcode)

def subprocess_check_output_pty(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    (master, slave) = os.openpty()
    process = subprocess.Popen(stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, *popenargs, **kwargs)

    stdout, stderr = process.communicate()
    retcode = process.poll()

    os.close(slave)
    os.close(master)

    if retcode:
        cmd = ' '.join(*popenargs)
        raise ImageFactoryException("'%s' failed(%d): %s" % (cmd, retcode, stderr))
    return (stdout, stderr, retcode)

def ssh_execute_command(guestaddr, sshprivkey, command, timeout=10, user='root', prefix=None):
    """
    Function to execute a command on the guest using SSH and return the output.
    Modified version of function from ozutil to allow us to deal with non-root
    authorized users on ec2
    """
    # ServerAliveInterval protects against NAT firewall timeouts
    # on long-running commands with no output
    #
    # PasswordAuthentication=no prevents us from falling back to
    # keyboard-interactive password prompting
    #
    # -F /dev/null makes sure that we don't use the global or per-user
    # configuration files
    #
    # -t -t ensures we have a pseudo tty for sudo

    cmd = ["ssh", "-i", sshprivkey,
            "-F", "/dev/null",
            "-o", "ServerAliveInterval=30",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=" + str(timeout),
            "-o", "UserKnownHostsFile=/dev/null",
            "-t", "-t",
            "-o", "PasswordAuthentication=no"]

    if prefix:
        command = prefix + " " + command

    cmd.extend(["%s@%s" % (user, guestaddr), command])

    if(prefix == 'sudo'):
        return subprocess_check_output_pty(cmd)
    else:
        return subprocess_check_output(cmd)

def enable_root(guestaddr, sshprivkey, user, prefix):
    for cmd in ('mkdir /root/.ssh',
                'chmod 600 /root/.ssh',
                'cp /home/%s/.ssh/authorized_keys /root/.ssh' % user,
                'chmod 600 /root/.ssh/authorized_keys'):
        try:
            ssh_execute_command(guestaddr, sshprivkey, cmd, user=user, prefix=prefix)
            log = logging.getLogger(__name__)
            log.debug('Executing command on %s as %s: %s' % (guestaddr, user, cmd))
        except Exception as e:
            pass
    try:
        stdout, stderr, retcode = ssh_execute_command(guestaddr, sshprivkey, '/bin/id')
        if not re.search('uid=0', stdout):
            raise Exception('Running /bin/id on %s as root: %s' % (guestaddr, stdout))
    except Exception as e:
        raise ImageFactoryException('Transfer of authorized_keys to root from %s must have failed - Aborting - %s' % (user, e))

def disable_root(guestaddr, sshprivkey, user, prefix):
    for cmd in('rm -rf /root/.ssh'):
        try:
            ssh_execute_command(guestaddr, sshprivkey, cmd, user=user, prefix=prefix)
            log = logging.getLogger(__name__)
            log.debug('Executing command on %s as %s: %s' % (guestaddr, user, cmd))
        except Exception as e:
            pass

# Our generic "parameters" dict passed to the plugins may be derived from either
# real JSON or from individual parameters passed on the command line.  In the case
# of command line parameters, all dict values are strings.  Plugins that want to
# accept non-string parameters should be prepared to do a string conversion.

def parameter_cast_to_bool(ival):
    """
    Function to take an input that may be a string, an int or a bool
    If input is a string it is made lowecase
    Returns True if ival is boolean True, a non-zero integer, "Yes",
    "True" or "1"
    Returns False in ival is boolean False, zero, "No", "False" or "0"
    In all other cases, returns None
    """
    if type(ival) is bool:
        return ival
    if type(ival) is int:
        return bool(ival)
    if type(ival) is str:
        lower = ival.lower()
        if lower == 'no' or lower == 'false' or lower == '0':
            return False
        if lower == 'yes' or lower == 'true' or lower == '1':
            return True
    return None
