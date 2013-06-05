#!/usr/bin/python
# This just wraps the kickstart file provided on the command line into JSON
# that can be passed to the factory via REST or the command line
# This is important since ks files typically have characters that may need
# to be escaped - even newlines need this

import sys
import json

kickstart = open(sys.argv[1]).read()

parameters =  { "install_script": kickstart, "generate_icicle": False }

print json.dumps(parameters)
