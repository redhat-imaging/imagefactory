# loads tests config and utilities
import utils

# actual tests code
import re
import random
import xml.etree.ElementTree as ET


def test_tdl_structure_validation():
  template = open(random.choice(utils.TEMPLATE_FILES), 'r').read()
  template = re.sub('<install', '<intall', template)
  imagejson = utils.build_base(template)
  imageid = imagejson['id']
  assert utils.wait_until_base_completes(imageid) == 'FAILED'

def test_tdl_content_validation():
  tree = ET.parse(random.choice(utils.TEMPLATE_FILES))
  roottag = tree.getroot()
  ostag = roottag.find('./os')
  rootpwtag = ostag.find('./rootpw')
  ostag.remove(rootpwtag)
  imagejson = utils.build_base(ET.tostring(roottag))
  imageid = imagejson['id']
  assert utils.wait_until_base_completes(imageid) == 'FAILED'
