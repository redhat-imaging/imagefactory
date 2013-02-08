#!/usr/bin/python

# A set of helpful utility functions
# Avoid imports that are too specific to a given cloud or OS
# We want to allow people to import all of these
# Add logging option

import guestfs

def launch_inspect_and_mount(diskfile):
    g = guestfs.GuestFS()
    g.add_drive(diskfile)
    g.launch()
    return inspect_and_mount(g)

def inspect_and_mount(guestfs_handle, relative_mount=""):
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
