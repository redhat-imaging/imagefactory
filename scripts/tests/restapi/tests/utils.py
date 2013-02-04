# configuration management
import os
execfile(os.path.join(os.path.dirname(__file__),'config')) 

if 'IMGFAC_URL' in os.environ.keys():
  IMGFAC_URL = os.environ['IMGFAC_URL']

# actual utils code
import json
import time
import requests


def build_base(template):
  payload = {'base_image': {'template': template}}
  r = requests.post(IMGFAC_URL+BASE_IMAGE_ENDPOINT, data=json.dumps(payload), headers=REQUEST_HEADERS)
  imagejson = json.loads(r.text)
  return imagejson['base_image']

def get_base(imageid):
  r = requests.get(IMGFAC_URL+BASE_IMAGE_ENDPOINT+'/'+imageid, headers=REQUEST_HEADERS)
  imagejson = json.loads(r.text)
  return imagejson['base_image']

def wait_until_base_completes(imageid):
  currently = 'UNKNOWN'
  while currently not in ['COMPLETE', 'FAILED']:
    time.sleep(POLLING_INTERVAL)
    try:
      imagejson = get_base(imageid)
      currently = imagejson['status']
    except:
      currently = "FAILED"
  return currently

def build_target(template, target_provider):
  payload = {'target_image': {'target': target_provider, 'template': template}}
  r = requests.post(IMGFAC_URL+TARGET_IMAGE_ENDPOINT, data=json.dumps(payload), headers=REQUEST_HEADERS)
  imagejson = json.loads(r.text)
  return imagejson['target_image']

def get_target(imageid):
  r = requests.get(IMGFAC_URL+TARGET_IMAGE_ENDPOINT+'/'+imageid, headers=REQUEST_HEADERS)
  imagejson = json.loads(r.text)
  return imagejson['target_image']

def wait_until_target_completes(imageid):
  currently = 'UNKNOWN'
  while currently not in ['COMPLETE', 'FAILED']:
    time.sleep(POLLING_INTERVAL)
    try:
      imagejson = get_target(imageid)
      currently = imagejson['status']
    except:
      currently = "FAILED"
  return currently

def build_provider(template, provider, provider_definition, provider_credentials):
  payload = {'provider_image': {'target': provider, 'template': template, 'provider': provider_definition, 'credentials': provider_credentials}}
  if provider.lower() == 'ec2':
    payload = {'provider_image': {'target': provider, 'template': template, 'provider': provider_definition, 'credentials': provider_credentials, 'parameters': {'snapshot': True}}}
  r = requests.post(IMGFAC_URL+PROVIDER_IMAGE_ENDPOINT, data=json.dumps(payload), headers=REQUEST_HEADERS)
  imagejson = json.loads(r.text)
  return imagejson['provider_image']

def get_provider(imageid):
  r = requests.get(IMGFAC_URL+PROVIDER_IMAGE_ENDPOINT+'/'+imageid, headers=REQUEST_HEADERS)
  imagejson = json.loads(r.text)
  return imagejson['provider_image']

def wait_until_provider_completes(imageid):
  currently = 'UNKNOWN'
  while currently not in ['COMPLETE', 'FAILED']:
    time.sleep(POLLING_INTERVAL)
    try:
      imagejson = get_provider(imageid)
      currently = imagejson['status']
    except:
      currently = "FAILED"
  return currently

def get_root():
  r = requests.get(IMGFAC_URL, headers=REQUEST_HEADERS)
  return json.loads(r.text)

# code added for target_content.xml testing
import guestfs
import xml.etree.ElementTree as ET


def _compare_mps(a, b):
  if len(a[0]) > len(b[0]):
    return 1
  elif len(a[0]) == len(b[0]):
    return 0
  else:
    return -1

def list_installed_packages(imageid):
  # Gets the imageid imagefile location
  imgfac_config_file = open(IMGFAC_CONF).read()
  imgfac_conf = json.loads(imgfac_config_file)
  storage_path = imgfac_conf['image_manager_args']['storage_path']
  imgfile = imageid + ".body"
  imgfile_path = storage_path + "/" + imgfile
  # Create the guestfs object, attach the disk image and launch the back-end
  g = guestfs.GuestFS()
  g.add_drive(imgfile_path)
  g.launch()
  # Gets the operating systems root
  roots = g.inspect_os()
  # Assumes the first is the one we want to inspect
  root = roots[0]
  # Mount up the disks, like guestfish -i
  # Sort keys by length, shortest first, so that we end up
  # mounting the filesystems in the correct order
  mps = g.inspect_get_mountpoints(root)
  mps.sort(_compare_mps)
  for mp_dev in mps:
    g.mount_ro (mp_dev[1], mp_dev[0])
  apps = g.inspect_list_applications(root)
  # apps is a list of dicts, we extract app_name of every item
  pkgs = [d["app_name"] for d in apps]
  # Unmount everything
  g.umount_all()
  return pkgs

def list_expected_packages(target_provider):
  tree = ET.parse(IMGFAC_TCXML)
  rootel = tree.getroot()
  pkgsel = rootel.findall("./include[@target='" + target_provider + "']/packages/package")
  pkgs = []
  for pkg in pkgsel:
    pkgs.append(pkg.get("name"))
  return pkgs
