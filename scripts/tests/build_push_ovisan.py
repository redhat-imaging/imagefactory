#!/usr/bin/python
import cqpid
import os
from qmf2 import *
from time import *
import sys
import libxml2
import pycurl

def usage():
    print "Usage: Windows_Cloud_Test tdl.xml credentials.xml cloud_provider cloud_provider"
    print "*1st argument* - XML file, please see the TDL example for the XML structure"
    print "*2nd argument* - XML file, please see a credential example for the XML structurei"
    print "*3rd argument* - text cloud_provider"
    print "*4th* argument - text cloud_provider_region (in case the cloud provider doesn't support regions, supply the same value from 3rd argument)"
    print "example for Rackspace, which doesn't support multiple regions"
    print "Windows_Cloud_Test tdl.xml credentials.xml rackspace rackspace"
    print ""

class Error(Exception):
    def __init__(self,value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class iCurl:
   def __init__(self):
       self.contents = ''

   def body_callback(self, buf):
       self.contents = self.contents + buf 


if len(sys.argv) != 5:
    usage()
    raise Error ( "%s takes exactly 4 arguments, %s supplied" %(sys.argv[0], len(sys.argv)-1))

tdlfile = open(sys.argv[1], "r")

tdl = tdlfile.read()
credentials_file = open(sys.argv[2], "r")
credentials = credentials_file.read()

connection = cqpid.Connection("localhost")
connection.open()
session = ConsoleSession(connection)
session.open()
sleep(60)
agents = session.getAgents()
agent = agents[1]
factory = agent.query("{class:ImageFactory, package:'com.redhat.imagefactory'}")
fac = factory[0]

build = fac.image(tdl, sys.argv[3])
image_addr = DataAddr(build['build_adaptor'])
query = Query(image_addr)
#print query
images = agent.query(query)
#print images
buildobj = images[0]
#print buildobj
#print dir(buildobj)
#print buildobj.getProperties()
for i in range(1000):
  images = agent.query(query)
  buildobj = images[0]
  #print buildobj.status, buildobj.percent_complete, buildobj.image_id
  if buildobj.status == "COMPLETED":
    #print "Build complete!"
    break
  sleep(5)

sleep(10)

#print "Now we push the Image with ID: ", buildobj.image_id


push = fac.provider_image(str(buildobj.image_id), sys.argv[4], credentials)

push_addr = DataAddr(push['build_adaptor'])
query = Query(push_addr)

pushes = agent.query(query)
#print pushes
pushobj = pushes[0]
#print pushobj
#print dir(pushobj)
for i in range(1000):
    pushes = agent.query(query)
    pushobj = pushes[0]
    #print pushobj.status, pushobj.percent_complete, pushobj.image_id
    if pushobj.status == "COMPLETED":
      #print "Push complete!"
      break
    sleep(5)

provider_image_url = "http://localhost:9090/provider_images/%s/target_identifier" % pushobj.image_id

##print "Trying to grab provider ID from ", provider_image_url

#os.system("curl %s" % provider_image_url)

t = iCurl()
c = pycurl.Curl()
c.setopt(c.URL, provider_image_url)
c.setopt(c.WRITEFUNCTION, t.body_callback)
c.perform()
c.close()
result = t.contents

if result == 0:
    print "Failed"
else:
    print "Success"


session.close()
connection.close()

