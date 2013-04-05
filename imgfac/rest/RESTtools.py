#
#   Copyright 2011 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http:/www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import logging
from imgfac.ApplicationConfiguration import ApplicationConfiguration
from imgfac.rest.bottle import *
from imgfac.picklingtools.xmlloader import *

log = logging.getLogger(__name__)

def form_data_for_content_type(content_type):
    def dencode(a_dict, encoding='ascii'):
        new_dict = {}
        for k,v in a_dict.items():
            ek = k.encode(encoding)
            if(isinstance(v, unicode)):
                new_dict[ek] = v.encode(encoding)
            elif(isinstance(v, dict)):
                new_dict[ek] = dencode(v)
            else:
                new_dict[ek] = v
        return new_dict

    try:
        if(content_type.startswith('application/json')):
            return dencode(request.json)
        elif(content_type.startswith('application/xml') or content_type.startswith('text/xml')):
            xml_options = XML_LOAD_UNFOLD_ATTRS | XML_LOAD_NO_PREPEND_CHAR | XML_LOAD_EVAL_CONTENT
            return dencode(ReadFromXMLStream(request.body, xml_options))
        else:
            return dencode(request.forms)
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output=e)

def log_request(f):
    def decorated_function(*args, **kwargs):
        if(ApplicationConfiguration().configuration['debug']):
            request_body = request.body.read()
            if('credentials' in request_body):
                marker = 'provider_credentials'
                starting_index = request_body.find(marker)
                ending_index = request_body.rfind(marker) + len(marker)
                sensitive = request_body[starting_index:ending_index]
                request_body = request_body.replace(sensitive, 'REDACTED')
            log.debug('Handling %s HTTP %s REQUEST for resource at %s: %s' % (request.headers.get('Content-Type'),
                                                                              request.method,
                                                                              request.path,
                                                                              request_body))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def check_accept_header(f):
    def decorated_function(*args, **kwargs):
        accept_header = request.get_header('Accept', None)
        if(accept_header and (('*/*' not in accept_header) and ('application/json' not in accept_header) and ('xml' not in accept_header))):
            log.debug('Returning HTTP 406, unsupported response type: %s' % accept_header)
            raise HTTPResponse(status=406, output='Responses in %s are currently unsupported.' % accept_header)
        else:
            return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function
