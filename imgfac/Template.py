# encoding: utf-8

#   Copyright 2011 Red Hat, Inc.
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

import logging
import httplib2
import re
import os.path
import props
import libxml2
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.ImageWarehouse import ImageWarehouse

class Template(object):
    uuid_pattern = '([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})'

    identifier = props.prop("_identifier", "The identifier property.")
    url = props.prop("_url", "The url property.")
    xml = props.prop("_xml", "The xml property.")
    @property
    def os_name(self):
        """The property os_name"""
        return self._content_at_path('/template/os/name')
    @property
    def os_version(self):
        """The property os_version"""
        return self._content_at_path('/template/os/version')
    @property
    def os_arch(self):
        """The property os_arch"""
        return self._content_at_path('/template/os/arch')

    def __repr__(self):
        if(self.xml):
            return self.xml
        else:
            return super(Template, self).__repr__

    def _content_at_path(self, path):
        try:
            return libxml2.parseDoc(self.xml).xpath(path)[0].content
        except Exception as e:
            self.log.exception('Could not parse document for path (%s): %s\n%s' % (path, self.xml, e))
            return None

    def __init__(self, template=None, uuid=None, url=None, xml=None):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration["warehouse"])

        self.identifier = None
        self.url = None
        self.xml = None

        path = None
        if(template):
            template_string = str(template)
            template_string_type = self.__template_string_type(template_string)
            if(template_string_type == "UUID"):
                uuid = template_string
            elif(template_string_type == "URL"):
                url = template_string
            elif(template_string_type == "XML"):
                xml = template_string
            elif(template_string_type == "PATH"):
                path = template_string

        if(uuid):
            uuid_string = uuid
            self.identifier, self.xml = self.__fetch_template_for_uuid(uuid_string)
            if((not self.identifier) and (not self.xml)):
                raise RuntimeError("Could not create a template with the uuid %s" % (uuid, ))
        elif(url):
            self.url = url
            self.identifier, self.xml = self.__fetch_template_with_url(url)
        elif(xml):
            self.xml = xml
        elif(path):
            template_file = open(path, "r")
            file_content = template_file.read()
            template_file.close()
            if(self.__string_is_xml_template(file_content)):
                self.xml = file_content
            else:
                raise ValueError("File %s does not contain properly formatted template xml:\n%s" % (path, self.__abbreviated_template(file_content)))
        else:
            raise ValueError("'template' must be a UUID, URL, XML string or XML document path...")

    def __template_string_type(self, template_string):
        regex = re.compile(Template.uuid_pattern)
        match = regex.search(template_string)

        if(template_string.lower().startswith("http")):
            return "URL"
        elif(("<template" in template_string.lower()) and ("</template>" in template_string.lower())):
            return "XML"
        elif(match):
            return "UUID"
        elif(os.path.exists(template_string)):
            return "PATH"
        else:
            raise ValueError("'template_string' must be a UUID, URL, or XML document...\n--- TEMPLATE STRING ---\n%s\n-----------------" % (template_string, ))

    def __fetch_template_for_uuid(self, uuid_string):
        xml_string, metadata = self.warehouse.template_with_id(uuid_string)
        if(xml_string and self.__string_is_xml_template(xml_string)):
            return uuid_string, xml_string
        else:
            self.log.debug("Unable to fetch a valid template given template id %s:\n%s\nWill try fetching template id from a target image with this id..." % (uuid_string, self.__abbreviated_template(xml_string)))
            template_id, xml_string, metadata = self.warehouse.template_for_target_image_id(uuid_string)
            if(template_id and xml_string and self.__string_is_xml_template(xml_string)):
                return template_id, xml_string
            else:
                self.log.debug("Unable to fetch a valid template given a target image id %s:\n%s\n" % (uuid_string, self.__abbreviated_template(xml_string)))
                return None, None

    def __string_is_xml_template(self, text):
        return (("<template" in text.lower()) and ("</template>" in text.lower()))

    def __fetch_template_with_url(self, url):
        template_id = None
        regex = re.compile(Template.uuid_pattern)
        match = regex.search(url)

        if (match):
            template_id = match.group()

        if (not url.startswith(self.warehouse.url)):
            response_headers, response = httplib2.Http().request(url, "GET", headers={'content-type':'text/plain'})
        else:
            response_headers, response = self.warehouse.request(url, "GET")
        if(response and self.__string_is_xml_template(response)):
            return template_id, response
        else:
            raise RuntimeError("Recieved status %s fetching a template from %s!\n--- Response Headers:\n%s\n--- Response:\n%s" % (response_headers["status"], url, response_headers, response))

    def __abbreviated_template(self, template_string):
        lines = template_string.splitlines(True)
        if(len(lines) > 20):
            return "%s\n...\n...\n...\n%s" % ("".join(lines[0:10]), "".join(lines[-10:len(lines)]))
        else:
            return template_string
