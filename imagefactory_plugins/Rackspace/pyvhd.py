#!/usr/bin/python
# encoding: utf-8
#
# Copyright (C) 2014 Ian McLeod <imcleod@redhat.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation;
# version 2.1 of the License.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# These routines produce a VHD image that is, as best I can tell, compatible
# with recent Xen code.  The original motivation for doing this was to upload
# images to the Rackspace cloud, but it may be useful in other contexts.
#
# The block allocation table map or "batmap" does not appear in the MS specs but
# is present in recent vhd-util code in the Xen upstream source.
#
# This creates the dynamic VHD format but does not make any attempt to detect
# large zereoed sections of disk.  As a result, the output is slightly larger
# than the input RAW file. 

import struct
import sys
import uuid
import math

def divro(num, den):
    # Divide always rounding up and returning an integer
    # Is there some nicer way to do this?
    return int(math.ceil((1.0*num)/(1.0*den)))

def vhd_checksum(string):
    # This is the checksum defined in the MS spec
    # sum up all bytes in the checked structure then take the ones compliment
    checksum = 0
    for byte in string:
        checksum += ord(byte)
    return (checksum ^ 0xFFFFFFFF)

def vhd_chs(size):
    # CHS calculation as defined by the VHD spec
    sectors = divro(size, SECTORSIZE)

    if sectors > (65535 * 16 * 255):
        sectors = 65535 * 16 * 255

    if sectors >= 65535 * 16 * 63:
        spt = 255
        cth = sectors / spt
        heads = 16
    else:
        spt = 17
        cth = sectors / spt
        heads = (cth + 1023) / 1024

        if heads < 4:
            heads = 4

        if (cth >= (heads * 1024)) or (heads > 16):
            spt = 31
            cth = sectors / spt
            heads = 16

        if cth >= (heads * 1024):
            spt = 63
            cth = sectors / spt
            heads = 16

    cylinders = cth / heads

    return (cylinders, heads, spt)

def zerostring(len):
    zs = ""
    for i in range(1, len):
        zs += '\0'
    return zs

# Header/Footer - From MS doco
# 512 bytes - early versions had a 511 byte footer for no obvious reason

#Cookie 8
#Features 4
#File Format Version 4
#Data Offset 8
#Time Stamp 4
#Creator Application 4
#Creator Version 4
#Creator Host OS 4
#Original Size 8
#Current Size 8
#Disk Geometry 4
# Disk Cylinders 2
# Disk Heads 1
# Disk Sectors 1
#Disk Type 4
#Checksum 4
#Unique Id 16
#Saved State 1
#Reserved 427

HEADER_FMT = ">8sIIQI4sIIQQHBBII16sB427s"

# Dynamic header
# 1024 bytes

#Cookie 8
#Data Offset 8
#Table Offset 8
#Header Version 4
#Max Table Entries 4
#Block Size 4
#Checksum 4
#Parent Unique ID 16
#Parent Time Stamp 4
#Reserved 4
#Parent Unicode Name 512
#Parent Locator Entry 1 24
#Parent Locator Entry 2 24
#Parent Locator Entry 3 24
#Parent Locator Entry 4 24
#Parent Locator Entry 5 24
#Parent Locator Entry 6 24
#Parent Locator Entry 7 24
#Parent Locator Entry 8 24
#Reserved 256

DYNAMIC_FMT = ">8sQQIIII16sII512s192s256s"

# BAT header 
# This is not in the Microsoft spec but is present in the Xen code
# This is a bitmap of the BAT where "1" indicates the BAT entry is valid
# and "0" indicates that it is unallocated.
#
# Cookie 8 - 'tdbatmap'
# batmap_offset 8 - byte offset to the BAT map
# batmap_size 4 - batmap size in sectors rounded up
# batmap_version 4 - 0x00010002 in vhd-util
# batmap_checksum 4 - 1's compliment of batmap itself

BAT_HDR_FMT = ">8sQIII"

VHD_BLOCKSIZE = 2 * 1024 * 1024 # Default blocksize 2 MB
SECTORSIZE = 512
VHD_BLOCKSIZE_SECTORS = VHD_BLOCKSIZE/SECTORSIZE
VHD_HEADER_SIZE = struct.calcsize(HEADER_FMT)
VHD_DYN_HEADER_SIZE = struct.calcsize(DYNAMIC_FMT)
SECTOR_BITMAP_SIZE = VHD_BLOCKSIZE / SECTORSIZE / 8
FULL_SECTOR_BITMAP = ""
for i in range(0,SECTOR_BITMAP_SIZE):
    FULL_SECTOR_BITMAP += chr(0xFF)
SECTOR_BITMAP_SECTORS = divro(SECTOR_BITMAP_SIZE, SECTORSIZE)
# vhd-util has a bug that pads an additional 7 sectors on to each bloc
# at the end.  I suspect this is due to miscalculating the size of the
# bitmap.  Specifically, forgetting to divide the number of bits by 8.
BLOCK_PAD_SECTORS = 7 # Bug for bug compat with vhd-util

def do_vhd_convert(infile, outfile):
    # infile - open file object containing raw input flie
    # outfile - open for writing file object to which output is written
    infile.seek(0,2)
    insize = infile.tell()
    infile.seek(0)

    bat_entries = divro(insize, VHD_BLOCKSIZE)
    # Block Allocation Table (BAT) size in sectors
    bat_sectors = divro(bat_entries*4, SECTORSIZE)

    # OK - cannot quite figure out why vhd-util adds more
    # pad than needed in some cases - I will just put the
    # first block safely past the batmap
    batmap_size_sectors = divro(divro(bat_entries,8),SECTORSIZE)
    first_block_sector = 3 + bat_sectors + 1 + batmap_size_sectors

    current_block_sector = first_block_sector
    total_block_sectors = SECTOR_BITMAP_SECTORS + VHD_BLOCKSIZE_SECTORS + BLOCK_PAD_SECTORS

    bat_values = [ ]
    for i in range(0,bat_entries):
	bat_values.append(current_block_sector)
	current_block_sector += total_block_sectors

    bat=""
    for sector in bat_values:
	bat += struct.pack(">I", ( sector ) )

    # The Xen code adds yet another sector map, this one of the BAT itself.
    # This converter code pre-allocates everything, so we just need a string
    # full of set bits of the correct size

    batmap=""
    for i in range(0,bat_entries/8):
	batmap += chr(0xFF)

    extra_bits = bat_entries % 8
    if extra_bits != 0:
	batmap += chr((0xFF << (8-extra_bits)) & 0xFF)

    cookie3 = "tdbatmap"
    # 3 sectors for the other headers plus one sector for this
    batmap_offset = (3 + bat_sectors + 1) * SECTORSIZE
    batmap_size = batmap_size_sectors
    batmap_version = 0x00010002 # from vhd-util
    batmap_checksum = vhd_checksum(batmap)

    batmap_vals = ( cookie3, batmap_offset, batmap_size, batmap_version, batmap_checksum)

    batmap_hdr = struct.pack(BAT_HDR_FMT, *batmap_vals)

    batmap_hdr_location = 3 + bat_sectors

    cookie = "conectix"
    features = 2 # Set by convention - means nothing
    fmt_version = 0x00010000
    data_offset = 512 # location of dynamic header
    # This is a problematic field - vhd-util interprets it as local
    # time and will reject images that have a stamp in the future
    # set it to 24 hours ago to be safe or EPOCH (zero) to be safer
    timestamp = 0 
    creator_app = "tap"
    creator_ver = 0x10003 # match vhd-util
    creator_os = 0 # match vhd-util
    orig_size = insize
    curr_size = insize
    (disk_c, disk_h, disk_s) = vhd_chs(curr_size)
    disk_type = 3 # Dynamic
    checksum = 0 # calculated later
    my_uuid = uuid.uuid4().get_bytes()
    saved_state= 0
    reserved = zerostring(427)

    header_vals =  [ cookie, features, fmt_version, data_offset, timestamp, 
    creator_app, creator_ver, creator_os, orig_size, curr_size, disk_c, disk_h,
    disk_s, disk_type, checksum, my_uuid, saved_state, reserved ]

    header = struct.pack(HEADER_FMT, *tuple(header_vals))

    checksum = vhd_checksum(header)

    header_vals[14] = checksum

    final_header = struct.pack(HEADER_FMT, *tuple(header_vals))

    cookie2 = "cxsparse"
    data_offset2 = 0xFFFFFFFFFFFFFFFF 
    table_offset = 1536
    header_version = 0x00010000 # match vhd-util
    max_table_entries = bat_entries
    block_size = VHD_BLOCKSIZE
    checksum2 = 0 # calculated later
    parent_uuid=zerostring(16)
    parent_timestamp = 0
    reserved2 = 0
    parent_name = zerostring(512)
    parent_locents = zerostring(192)
    reserved3 = zerostring(256)

    dyn_vals = [ cookie2, data_offset2, table_offset, header_version, 
    max_table_entries, block_size, checksum2, parent_uuid, parent_timestamp,
    reserved2, parent_name, parent_locents, reserved3 ]

    dyn_header = struct.pack(DYNAMIC_FMT, *tuple(dyn_vals))
    checksum2 = vhd_checksum(dyn_header)
    dyn_vals[6] = checksum2
    final_dyn_header = struct.pack(DYNAMIC_FMT, *tuple(dyn_vals))


    outfile.write(final_header)
    outfile.write(final_dyn_header)
    outfile.write(bat)
    outfile.seek(batmap_hdr_location * SECTORSIZE)
    outfile.write(batmap_hdr)
    outfile.seek(batmap_offset)
    outfile.write(batmap)

    for block_start in bat_values:
	outfile.seek(block_start * SECTORSIZE)
	outfile.write(FULL_SECTOR_BITMAP)
	outfile.seek( (SECTOR_BITMAP_SECTORS + block_start) * SECTORSIZE)
	outfile.write(infile.read(VHD_BLOCKSIZE))

    outfile.seek( (block_start + SECTOR_BITMAP_SECTORS + VHD_BLOCKSIZE_SECTORS) * SECTORSIZE)
    outfile.write(final_header)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print "usage: %s <raw_input_file> <vhd_output_file>" % sys.argv[0]
        sys.exit(1)
    infile = open(sys.argv[1], "r")
    outfile = open(sys.argv[2], "w")
    do_vhd_convert(infile, outfile)
    infile.close()
    outfile.close()
	

