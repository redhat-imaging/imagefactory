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

import sys
import libxml2
import logging
from threading import Thread, Lock
from imagefactory.builders import *
from imagefactory.Template import Template


class BuildDispatcher(object):
    
    @classmethod
    def builder_for_target_with_template(cls, target, template):
        log = logging.getLogger('%s.%s' % (__name__, cls.__name__))
        
        template_object = Template(template)
        
        builder_class = MockBuilder.MockBuilder
        if (target != "mock"): # If target is mock always run mock builder regardless of template
            parsed_doc = libxml2.parseDoc(template_object.xml)
            node = parsed_doc.xpathEval('/template/os/name')
            os_name = node[0].content
            class_name = "%sBuilder" % (os_name, )
            try:
                module_name = "imagefactory.builders.%s" % (class_name, )
                __import__(module_name)
                builder_class = getattr(sys.modules[module_name], class_name)
            except AttributeError, e:
                log.exception("CAUGHT EXCEPTION: %s \n Could not find builder class for %s, returning MockBuilder!", e, os_name)
        
        return builder_class(template_object, target)
    
    @classmethod
    def builder_thread_with_method(cls, builder, method_name, arg_dict={}, autostart=True):
        log = logging.getLogger('%s.%s' % (__name__, cls.__name__))
        
        thread_name = "%s.%s()" % (builder.image_id, method_name)
        # using args to pass the method we want to call on the target object.
        builder_thread = Thread(target = builder, name=thread_name, args=(method_name), kwargs=arg_dict)
        if(autostart):
            builder_thread.start()
        
        return builder_thread
    
