# encoding: utf-8

#   Copyright 2016 Red Hat, Inc.
#
#   Original XML templated used to generate a portion of this code is
#   Copyright (C) 2016, Matt Wrock
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
#
#   The XML generator portion of this was derived from the hyperv OVA template
#   in Matt Wrock's <matt at mattwrock.com> packer templates repository here:
#
#   https://github.com/mwrock/packer-templates
#
#   Matt's project was also helpful in confirming some of the more obscure
#   details of how the HyperV metadata format encodes the creation date.

import sys
import lxml.etree
import codecs
import re
import datetime
import struct
import base64

class HyperVOVFDescriptor(object):
    def __init__(self,
                 ovf_name,
                 ovf_cpu_count,
                 ovf_memory_mb):
        self.ovf_name = ovf_name
        self.ovf_cpu_count = ovf_cpu_count
        self.ovf_memory_mb = ovf_memory_mb

    def generate_ovf_xml(self):

        # creation time is a base64 encoded representation of the number of ticks
        # since the epoch as calculated with UTC - newline terminated just for fun
        # In Windows, the epoch is January 1, 1601 and there are 10 million
        # ticks in a second
	windows_epoch = datetime.datetime(1600, 12, 31, 23, 59, 59, 0)
	utc = datetime.datetime.utcnow()
	creation_time_delta = utc - windows_epoch
        # the total_seconds() method is not in python 2.6 which we still try to support
	creation_time_seconds = long(creation_time_delta.seconds) + long(creation_time_delta.days) * 60*60*24
	creation_windows_ticks = creation_time_seconds * 10**7
	packed_ticks=struct.pack('>Q', creation_windows_ticks)
	encoded_ticks=base64.b64encode(packed_ticks)
        creation_time=encoded_ticks + '\n'

	el_0 = lxml.etree.Element('configuration')

	el_1 = lxml.etree.Element('_2497f4de-e9fa-4204-80e4-4b75c46419c0_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_2a34b1c2-fd73-4043-8a5b-dd2159bc743f_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_55225880-49c0-4438-9ce2-5a01402fd8cb_')

	el_2 = lxml.etree.Element('ChannelInstanceGuid')
	el_2.text = '{b57a8519-55d4-47aa-be66-018ecb6260ff}'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('ClusterMonitored')
	el_2.text = 'True'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('Connection')

	el_3 = lxml.etree.Element('AltPortName')
	el_3.text = 'Dynamic Ethernet Switch Port'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('AltSwitchName')
	el_3.text = 'Virtual External Switch'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('AuthorizationScope')
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('ChimneyOffloadWeight')
	el_3.text = '0'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('Feature_C885BFD1-ABB7-418F-8163-9F379C9F7166')

	el_4 = lxml.etree.Element('DisplayName')
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('Flags')
	el_4.text = '0'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('Setting_A0B25B27-C698-4120-AD49-4CBE3DC028C5')

	el_5 = lxml.etree.Element('Data')
	el_5.text = 'AAIAAGQAAAAAAAAAAQAAAAAAAAA='
	el_5.attrib['type'] = 'bytes'
	el_4.append(el_5)

	el_5 = lxml.etree.Element('Version')
	el_5.text = '256'
	el_5.attrib['type'] = 'integer'
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element('Settings')

	el_5 = lxml.etree.Element('Id')
	el_5.text = 'A0B25B27-C698-4120-AD49-4CBE3DC028C5'
	el_5.attrib['type'] = 'string'
	el_4.append(el_5)
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('Features')

	el_4 = lxml.etree.Element('Id')
	el_4.text = 'C885BFD1-ABB7-418F-8163-9F379C9F7166'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('HostResources')

	el_4 = lxml.etree.Element('HostResource')
	el_4.text = '438B7B13-6180-4155-B7BF-08709CCF234D'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('PoolId')
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('PreventIPSpoofing')
	el_3.text = 'False'
	el_3.attrib['type'] = 'bool'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('TestReplicaPoolId')
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('TestReplicaSwitchName')
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('FriendlyName')
	el_2.text = 'Network Adapter'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('IsConnected')
	el_2.text = 'True'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('MacAddress')
	el_2.text = '00-15-5D-01-07-DC'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('MacAddressIsStatic')
	el_2.text = 'False'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('PortName')
	el_2.text = '87279691-8C7B-4C18-A0CB-52B86BD450D5'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('SwitchName')
	el_2.text = '438B7B13-6180-4155-B7BF-08709CCF234D'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('VpciInstanceGuid')
	el_2.text = '{CAD85457-9B61-44A0-B29F-15AD80A59E19}'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_58f75a6d-d949-4320-99e1-a2a2576d581c_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '512'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_5ced1297-4598-4915-a5fc-ad21bb4d02a4_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_655bc5c5-a784-46b7-81bc-e26328f7eb0e_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '512'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_6c09bb55-d683-4da0-8931-c9bf705f6480_')

	el_2 = lxml.etree.Element('Enabled')
	el_2.text = 'False'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_6c5addb9-a11a-4e8e-84cb-e6208201db63_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '512'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_7d80d3db-61ee-4879-8879-5609f1100ad0_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '512'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('address')
	el_2.text = '5353,00000000,00'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_83f8638b-8dca-4152-9eda-2ca8b33039b4_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '1280'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('controller0')

	el_3 = lxml.etree.Element('drive0')

	el_4 = lxml.etree.Element('iops_limit')
	el_4.text = '0'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('iops_reservation')
	el_4.text = '0'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('pathname')
	el_4.text = 'C:\\dev\\vagrant\\factory\\.vagrant\\machines\\default\\hyperv\\disk.vhd'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('persistent_reservations_supported')
	el_4.text = 'False'
	el_4.attrib['type'] = 'bool'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('type')
	el_4.text = 'VHD'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('weight')
	el_4.text = '100'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('drive1')

	el_4 = lxml.etree.Element('pathname')
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('type')
	el_4.text = 'NONE'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('controller1')

	el_3 = lxml.etree.Element('drive0')

	el_4 = lxml.etree.Element('pathname')
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('type')
	el_4.text = 'ISO'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('drive1')

	el_4 = lxml.etree.Element('pathname')
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('type')
	el_4.text = 'NONE'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)
	el_2.append(el_3)
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_84eaae65-2f2e-45f5-9bb5-0e857dc8eb47_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_8e3a359f-559a-4b6a-98a9-1690a6100ed7_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '512'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('port0')

	el_3 = lxml.etree.Element('connection')
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('port1')

	el_3 = lxml.etree.Element('connection')
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_8f0d2762-0b00-4e04-af4f-19010527cb93_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('controller0')

	el_3 = lxml.etree.Element('drive0')

	el_4 = lxml.etree.Element('pathname')
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('type')
	el_4.text = 'VFD'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)
	el_2.append(el_3)
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_9f8233ac-be49-4c79-8ee3-e7e1985b2077_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_ac6b8dc1-3257-4a70-b1b2-a9c9215659ad_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '512'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('base_board')

	el_3 = lxml.etree.Element('serial_number')
	el_3.text = '1981-9952-3234-1295-3674-7651-98'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('bios_guid')
	el_2.text = '{7FFEE066-9755-4950-9A16-4C94AC67AD00}'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('bios_serial_number')
	el_2.text = '1981-9952-3234-1295-3674-7651-98'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('boot')

	el_3 = lxml.etree.Element('device0')
	el_3.text = 'Optical'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('device1')
	el_3.text = 'HardDrive'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('device2')
	el_3.text = 'Network'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('device3')
	el_3.text = 'Floppy'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('chassis')

	el_3 = lxml.etree.Element('asset_tag')
	el_3.text = '1981-9952-3234-1295-3674-7651-98'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('serial_number')
	el_3.text = '1981-9952-3234-1295-3674-7651-98'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('num_lock')
	el_2.text = 'False'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('pause_after_boot_failure')
	el_2.text = 'False'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('pxe_preferred_protocol')
	el_2.text = '4'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('secure_boot_enabled')
	el_2.text = 'False'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_d7a36e9b-9256-4f0d-be2c-3a13887f7b03_')

	el_2 = lxml.etree.Element('ChannelInstanceGuid')
	el_2.text = '{125506a8-a651-4852-87ad-3e7a29dd07fa}'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_de6cdc86-e1fb-4940-801b-c3c1a26c4da4_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_e51b7ef6-4a7f-4780-aaae-d4b291aacd2e_')

	el_2 = lxml.etree.Element('RtcDevice')

	el_3 = lxml.etree.Element('CmosUtcSkew')
	el_3.text = '-288005458208'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('_f3cf6965-e8d3-44a9-9b7d-a04245ea7525_')

	el_2 = lxml.etree.Element('VDEVVersion')
	el_2.text = '256'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('global_settings')

	el_2 = lxml.etree.Element('devices')

	el_3 = lxml.etree.Element('allow_reduced_fc_redundancy')
	el_3.text = 'False'
	el_3.attrib['type'] = 'bool'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('generation_id')
	el_3.text = 'fd66d6917bb7cdbf9a906875a3cf499b'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('storage_allow_full_scsi_command_set')
	el_3.text = 'False'
	el_3.attrib['type'] = 'bool'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('disk_merge_pending')
	el_2.text = 'False'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('metrics')

	el_3 = lxml.etree.Element('devicetype')

	el_4 = lxml.etree.Element('deviceinstance')

	el_5 = lxml.etree.Element('guid')
	el_5.text = 'B637F346-6A0E-4DEC-AF52-BD70CB80A21D'
	el_5.attrib['type'] = 'string'
	el_4.append(el_5)

	el_5 = lxml.etree.Element('metric')

	el_6 = lxml.etree.Element('enabled')
	el_6.text = 'False'
	el_6.attrib['type'] = 'bool'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('lastcomputedtime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('peaktime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('poolid')
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('resourcetypeid')
	el_6.text = 'B637F347-6A0E-4DEC-AF52-BD70CB80A21D'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('starttime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('typecode')
	el_6.text = '3F6F1051-C8FC-47EF-9821-C07240848748;0'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('value')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element('guid')
	el_4.text = 'B637F346-6A0E-4DEC-AF52-BD70CB80A21D'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('devicetype')

	el_4 = lxml.etree.Element('deviceinstance')

	el_5 = lxml.etree.Element('guid')
	el_5.text = '4764334D-E001-4176-82EE-5594EC9B530E'
	el_5.attrib['type'] = 'string'
	el_4.append(el_5)

	el_5 = lxml.etree.Element('metric')

	el_6 = lxml.etree.Element('enabled')
	el_6.text = 'False'
	el_6.attrib['type'] = 'bool'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('lastcomputedtime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('peaktime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('poolid')
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('resourcetypeid')
	el_6.text = '4764334E-E001-4176-82EE-5594EC9B530E'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('starttime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('typecode')
	el_6.text = '394DCE66-458F-4895-AE56-41D7C9602A49'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('value')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element('metric')

	el_6 = lxml.etree.Element('enabled')
	el_6.text = 'False'
	el_6.attrib['type'] = 'bool'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('lastcomputedtime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('peaktime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('poolid')
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('resourcetypeid')
	el_6.text = '4764334E-E001-4176-82EE-5594EC9B530E'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('starttime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('typecode')
	el_6.text = 'FF85EA46-9933-4436-BE5D-C96827399966'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('value')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element('metric')

	el_6 = lxml.etree.Element('enabled')
	el_6.text = 'False'
	el_6.attrib['type'] = 'bool'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('lastcomputedtime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('peaktime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('poolid')
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('resourcetypeid')
	el_6.text = '4764334E-E001-4176-82EE-5594EC9B530E'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('starttime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('typecode')
	el_6.text = '04BDF59E-580D-4441-8828-FFFE44472D2D'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('value')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element('guid')
	el_4.text = '4764334D-E001-4176-82EE-5594EC9B530E'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('devicetype')

	el_4 = lxml.etree.Element('deviceinstance')

	el_5 = lxml.etree.Element('guid')
	el_5.text = '83F8638B-8DCA-4152-9EDA-2CA8B33039B4'
	el_5.attrib['type'] = 'string'
	el_4.append(el_5)

	el_5 = lxml.etree.Element('metric')

	el_6 = lxml.etree.Element('enabled')
	el_6.text = 'False'
	el_6.attrib['type'] = 'bool'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('lastcomputedtime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('peaktime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('poolid')
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('resourcetypeid')
	el_6.text = '70BB60D2-A9D3-46AA-B654-3DE53004B4F8'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('starttime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('typecode')
	el_6.text = 'AD29978B-AAB6-44AE-81CD-0609BF929F18;0\\0\\L'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('value')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element('metric')

	el_6 = lxml.etree.Element('enabled')
	el_6.text = 'False'
	el_6.attrib['type'] = 'bool'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('lastcomputedtime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('peaktime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('poolid')
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('resourcetypeid')
	el_6.text = '70BB60D2-A9D3-46AA-B654-3DE53004B4F8'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('starttime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('typecode')
	el_6.text = 'A4BCA0D9-C27D-4BC8-A7E3-7ED13C89E373;0\\0\\L'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('value')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element('metric')

	el_6 = lxml.etree.Element('enabled')
	el_6.text = 'False'
	el_6.attrib['type'] = 'bool'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('lastcomputedtime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('peaktime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('poolid')
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('resourcetypeid')
	el_6.text = '70BB60D2-A9D3-46AA-B654-3DE53004B4F8'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('starttime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('typecode')
	el_6.text = '72544D55-3035-41DA-B9D7-6C5A39BF8F35;0\\0\\L'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('value')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element('metric')

	el_6 = lxml.etree.Element('enabled')
	el_6.text = 'False'
	el_6.attrib['type'] = 'bool'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('lastcomputedtime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('peaktime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('poolid')
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('resourcetypeid')
	el_6.text = '70BB60D2-A9D3-46AA-B654-3DE53004B4F8'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('starttime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('typecode')
	el_6.text = 'A9DFBC22-E05F-438D-9405-22E2078353D6;0\\0\\L'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('value')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)
	el_4.append(el_5)

	el_5 = lxml.etree.Element('metric')

	el_6 = lxml.etree.Element('enabled')
	el_6.text = 'False'
	el_6.attrib['type'] = 'bool'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('lastcomputedtime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('peaktime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('poolid')
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('resourcetypeid')
	el_6.text = '70BB60D2-A9D3-46AA-B654-3DE53004B4F8'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('starttime')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('typecode')
	el_6.text = '534FA8D7-9875-4FAB-BAA6-2424DF29B31E;0\\0\\L'
	el_6.attrib['type'] = 'string'
	el_5.append(el_6)

	el_6 = lxml.etree.Element('value')
	el_6.text = '0'
	el_6.attrib['type'] = 'integer'
	el_5.append(el_6)
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element('guid')
	el_4.text = '83F8638B-8DCA-4152-9EDA-2CA8B33039B4'
	el_4.attrib['type'] = 'string'
	el_3.append(el_4)
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('owner')

	el_3 = lxml.etree.Element('sid')
	el_3.text = 'S-1-5-21-805543585-96907229-3301423255-1001'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('power')

	el_3 = lxml.etree.Element('host_shutdown')

	el_4 = lxml.etree.Element('action')
	el_4.text = '1'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('host_startup')

	el_4 = lxml.etree.Element('action')
	el_4.text = '1'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('snapshots')

	el_3 = lxml.etree.Element('list')

	el_4 = lxml.etree.Element('size')
	el_4.text = '0'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('unexpected_termination')

	el_3 = lxml.etree.Element('action')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vhd_path_acled')
	el_2.text = 'True'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('manifest')

	el_2 = lxml.etree.Element('size')
	el_2.text = '13'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev001')

	el_3 = lxml.etree.Element('device')
	el_3.text = '58f75a6d-d949-4320-99e1-a2a2576d581c'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = '58F75A6D-D949-4320-99E1-A2A2576D581C'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft Synthetic Mouse'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev002')

	el_3 = lxml.etree.Element('device')
	el_3.text = '197f74e3-b84b-46de-8ae6-82f1cd181cdc'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = '197F74E3-B84B-46DE-8AE6-82F1CD181CDC'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft Synthetic Keyboard'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev003')

	el_3 = lxml.etree.Element('device')
	el_3.text = 'f3cf6965-e8d3-44a9-9b7d-a04245ea7525'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = 'F3CF6965-E8D3-44A9-9B7D-A04245EA7525'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft Synthetic Video'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev004')

	el_3 = lxml.etree.Element('device')
	el_3.text = 'bc12c717-8898-4688-8ee4-2cd14894f8ea'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = 'BC12C717-8898-4688-8EE4-2CD14894F8EA'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft Hyper-V Activation Component'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev005')

	el_3 = lxml.etree.Element('device')
	el_3.text = '6c09bb55-d683-4da0-8931-c9bf705f6480'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = '6C09BB55-D683-4DA0-8931-C9BF705F6480'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft Guest Interface Component'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev006')

	el_3 = lxml.etree.Element('device')
	el_3.text = '84eaae65-2f2e-45f5-9bb5-0e857dc8eb47'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = '84EAAE65-2F2E-45F5-9BB5-0E857DC8EB47'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft Heartbeat Component'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev007')

	el_3 = lxml.etree.Element('device')
	el_3.text = '2a34b1c2-fd73-4043-8a5b-dd2159bc743f'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = '2A34B1C2-FD73-4043-8A5B-DD2159BC743F'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft Key-Value Pair Exchange Component'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev008')

	el_3 = lxml.etree.Element('device')
	el_3.text = '9f8233ac-be49-4c79-8ee3-e7e1985b2077'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = '9F8233AC-BE49-4C79-8EE3-E7E1985B2077'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft Shutdown Component'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev009')

	el_3 = lxml.etree.Element('device')
	el_3.text = '2497f4de-e9fa-4204-80e4-4b75c46419c0'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = '2497F4DE-E9FA-4204-80E4-4B75C46419C0'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft Time Synchronization Component'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev010')

	el_3 = lxml.etree.Element('device')
	el_3.text = '5ced1297-4598-4915-a5fc-ad21bb4d02a4'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = '5CED1297-4598-4915-A5FC-AD21BB4D02A4'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft VSS Component'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev011')

	el_3 = lxml.etree.Element('device')
	el_3.text = '6c5addb9-a11a-4e8e-84cb-e6208201db63'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = '6C5ADDB9-A11A-4E8E-84CB-E6208201DB63'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Microsoft RDV Component'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev012')

	el_3 = lxml.etree.Element('device')
	el_3.text = '2fc216b0-d2e2-4967-9b6d-b8a5c9ca2778'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = '55225880-49C0-4438-9CE2-5A01402FD8CB'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Synthetic Ethernet Port'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vdev013')

	el_3 = lxml.etree.Element('device')
	el_3.text = 'd422512d-2bf2-4752-809d-7b82b5fcb1b4'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('flags')
	el_3.text = '1'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('instance')
	el_3.text = 'D7A36E9B-9256-4F0D-BE2C-3A13887F7B03'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('name')
	el_3.text = 'Synthetic SCSI Controller'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('version')
	el_2.text = '260'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('properties')

	el_2 = lxml.etree.Element('creation_time')
	el_2.text = creation_time
	el_2.attrib['type'] = 'bytes'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('global_id')
	el_2.text = '0AA394FA-7C4A-4070-BA32-773D43B28A68'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('highly_available')
	el_2.text = 'False'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('last_powered_off_time')
	el_2.text = '130599959406707888'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('last_powered_on_time')
	el_2.text = '130599954966442599'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('last_state_change_time')
	el_2.text = '130599962187797355'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('name')
	el_2.text = self.ovf_name
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('notes')
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('subtype')
	el_2.text = '0'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('type_id')
	el_2.text = 'Virtual Machines'
	el_2.attrib['type'] = 'string'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('version')
	el_2.text = '1280'
	el_2.attrib['type'] = 'integer'
	el_1.append(el_2)
	el_0.append(el_1)

	el_1 = lxml.etree.Element('settings')

	el_2 = lxml.etree.Element('global')

	el_3 = lxml.etree.Element('logical_id')
	el_3.text = '0AA394FA-7C4A-4070-BA32-773D43B28A68'
	el_3.attrib['type'] = 'string'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('memory')

	el_3 = lxml.etree.Element('bank')

	el_4 = lxml.etree.Element('dynamic_memory_enabled')
	el_4.text = 'False'
	el_4.attrib['type'] = 'bool'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('limit')
	el_4.text = '1048576'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('priority')
	el_4.text = '5000'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('reservation')
	el_4.text = '512'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('size')
	el_4.text = str(self.ovf_memory_mb)
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)

	el_4 = lxml.etree.Element('target_memory_buffer')
	el_4.text = '20'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('vnuma')

	el_4 = lxml.etree.Element('max_size_per_node')
	el_4.text = '6610'
	el_4.attrib['type'] = 'integer'
	el_3.append(el_4)
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('processors')

	el_3 = lxml.etree.Element('count')
	el_3.text = str(self.ovf_cpu_count)
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('features')

	el_4 = lxml.etree.Element('limit')
	el_4.text = 'False'
	el_4.attrib['type'] = 'bool'
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('limit')
	el_3.text = '100000'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('limit_cpuid')
	el_3.text = 'False'
	el_3.attrib['type'] = 'bool'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('reservation')
	el_3.text = '0'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)

	el_3 = lxml.etree.Element('vnuma')

	el_4 = lxml.etree.Element('count_per_node')

	el_5 = lxml.etree.Element('max')
	el_5.text = '4'
	el_5.attrib['type'] = 'integer'
	el_4.append(el_5)
	el_3.append(el_4)

	el_4 = lxml.etree.Element('node_per_socket')

	el_5 = lxml.etree.Element('max')
	el_5.text = '1'
	el_5.attrib['type'] = 'integer'
	el_4.append(el_5)
	el_3.append(el_4)
	el_2.append(el_3)

	el_3 = lxml.etree.Element('weight')
	el_3.text = '100'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('stopped_at_host_shutdown')
	el_2.text = 'False'
	el_2.attrib['type'] = 'bool'
	el_1.append(el_2)

	el_2 = lxml.etree.Element('topology')

	el_3 = lxml.etree.Element('low_mmio_gap_mb')
	el_3.text = '128'
	el_3.attrib['type'] = 'integer'
	el_2.append(el_3)
	el_1.append(el_2)

	el_2 = lxml.etree.Element('vnuma')

	el_3 = lxml.etree.Element('enabled')
	el_3.text = 'True'
	el_3.attrib['type'] = 'bool'
	el_2.append(el_3)
	el_1.append(el_2)
	el_0.append(el_1)

        # Return XML rendered as a utf-16 string with DOS style line endings
        # NOTE: in my experience lxml correctly puts a byte order mark (BOM) in the front of this string
	return lxml.etree.tostring(el_0, pretty_print=True, encoding="utf-16", standalone="yes").replace('\n\0','\r\0\n\0')
