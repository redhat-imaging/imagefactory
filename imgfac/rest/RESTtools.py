#
#   Copyright 2011 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http:/www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by icable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import logging
from imgfac.rest.bottle import *
from imgfac.ApplicationConfiguration import ApplicationConfiguration

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
        else:
            return dencode(request.forms)
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output=e)

def log_request(f):
    def decorated_function(*args, **kwargs):
        if(ApplicationConfiguration().configuration['debug']):
            log.debug('Handling %s HTTP %s REQUEST for resource at %s: %s' % (request.headers.get('Content-Type'),
                                                                              request.method,
                                                                              request.path,
                                                                              request.body.read()))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def check_accept_header(f):
    def decorated_function(*args, **kwargs):
        accept_header = request.get_header('Accept', None)
        if(accept_header and ('application/json' not in accept_header)):
            log.debug('Returning HTTP 406, unsupported response type: %s' % accept_header)
            raise HTTPResponse(status=406, output='Responses in %s are currently unsupported. Please try application/json or remove the Accept header from the request.' % accept_header)
        else:
            return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function
