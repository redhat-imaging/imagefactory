#!/usr/bin/env python
# encoding: utf-8

# Copyright (C) 2010-2011 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.  A copy of the GNU General Public License is
# also available at http://www.gnu.org/copyleft/gpl.html.

import logging
import httplib2
import re
import uuid
from imagefactory.ApplicationConfiguration import ApplicationConfiguration
from imagefactory.ImageWarehouse import ImageWarehouse

class Template(object):
    uuid_pattern = '([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})'
    
    # @classmethod
    # def fetch_template_with_id(cls, identifier):
    #     return cls(uuid)
    # 
    # @classmethod
    # def fetch_template_with_url(cls, url):
    #     return cls(url)
    # 
    
    # Properties
    def identifier():
        doc = "The identifier property."
        def fget(self):
            return self._identifier
        def fset(self, value):
            self._identifier = value
        def fdel(self):
            del self._identifier
        return locals()
    identifier = property(**identifier())
    
    def url():
        doc = "The url property."
        def fget(self):
            return self._url
        def fset(self, value):
            self._url = value
        def fdel(self):
            del self._url
        return locals()
    url = property(**url())
    
    def xml():
        doc = "The xml property."
        def fget(self):
            return self._xml
        def fset(self, value):
            self._xml = value
        def fdel(self):
            del self._xml
        return locals()
    xml = property(**xml())
    
    
    def __init__(self, template_string):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.warehouse = ImageWarehouse(ApplicationConfiguration().configuration["warehouse"])
        
        self.identifier = None
        self.url = None
        self.xml = None
        
        template_string_type = self.__template_string_type(template_string)
            
        if(template_string_type == "UUID"):
            self.identifier, self.xml = self.__fetch_template_for_uuid(template_string)
        elif(template_string_type == "URL"):
            self.url = template_string
            self.identifier, self.xml = self.__fetch_template_with_url(template_string)
        elif(template_string_type == "XML"):
            self.xml = template_string
        else:
            raise ValueError("'template_string' must be a UUID, URL, or XML document...")
    
    def __template_string_type(self, template_string):
        regex = re.compile(Template.uuid_pattern)
        match = regex.search(template_string)
        
        if(match):
            return "UUID"
        elif(template_string.lower().startswith("http")):
            return "URL"
        elif(("<template>" in template_string.lower()) and ("</template>" in template_string.lower())):
            return "XML"
        else:        
            raise ValueError("'template_string' must be a UUID, URL, or XML document...")
    
    def __fetch_template_for_uuid(self, uuid_string):
        template_id, xml_string, metadata = self.warehouse.template_with_id(uuid_string)
        if(xml_string and self.__string_is_xml_template(xml_string)):
            return uuid.UUID(uuid_string), xml_string
        else:
            template_id, xml_string = self.warehouse.template_for_image_id(uuid_string)
            if(template_id and xml_string and self.__string_is_xml_template(xml_string)):
                return uuid.UUID(template_id), xml_string
            else:
                raise RuntimeError("Unable to fetch a template given the uuid %s!  No template or image matches this uuid!" % (uuid_string, ))
    
    def __string_is_xml_template(self, text):
        return (("<template>" in text.lower()) and ("</template>" in text.lower()))
    
    def __fetch_template_with_url(self, url):
        regex = re.compile(Template.uuid_pattern)
        template_id = uuid.UUID(regex.search(url).group())
        response_headers, response = httplib2.Http().request(url, "GET", headers={'content-type':'text/plain'})
        if(response and self.__string_is_xml_template(response)):
            return template_id, response
        else:
            raise RuntimeError("Unable to fetch template from %s!" % (url, ))
    
