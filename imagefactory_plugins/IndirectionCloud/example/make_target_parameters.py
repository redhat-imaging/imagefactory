#!/usr/bin/python

import sys
import json


utility_tdl = open(sys.argv[1]).read()
utility_image = sys.argv[2]

parameters =  { "utility_image": utility_image, "utility_customizations": utility_tdl }

print json.dumps(parameters)
