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

class Template(object):
    uuid_pattern = '([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})'

    identifier = props.prop("_identifier", "The identifier property.")
    url = props.prop("_url", "The url property.")
    xml = props.prop("_xml", "The xml property.")
    @property
    def name(self):
        """The property name"""
        return self._content_at_path('/template/name')
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
    @property
    def install_type(self):
        """The type of install ('url' or 'iso')"""
        result = libxml2.parseDoc(self.xml).xpathEval('/template/os/install')[0]
        if result:
            return result.prop('type')
        else:
            return None
    @property
    def install_url(self):
        """OS install URL"""
        return self._content_at_path('/template/os/install/url')
    @property
    def install_iso(self):
        """OS install ISO"""
        return self._content_at_path('/template/os/install/iso')
    @property
    def install_location(self):
        """Either OS install URL or ISO"""
        return self._content_at_path('/template/os/install/%s' % self.install_type)

    def __repr__(self):
        if(self.xml):
            return self.xml
        else:
            return super(Template, self).__repr__

    def _content_at_path(self, path):
        try:
            return libxml2.parseDoc(self.xml).xpathEval(path)[0].content
        except Exception as e:
            self.log.exception('Could not parse document for path (%s):\n%s' % (path, e))
            return None

    def __init__(self, template=None, uuid=None, url=None, xml=None):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

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

    def __string_is_xml_template(self, text):
        return (("<template" in text.lower()) and ("</template>" in text.lower()))

    def __abbreviated_template(self, template_string):
        lines = template_string.splitlines(True)
        if(len(lines) > 20):
            return "%s\n...\n...\n...\n%s" % ("".join(lines[0:10]), "".join(lines[-10:len(lines)]))
        else:
            return template_string
