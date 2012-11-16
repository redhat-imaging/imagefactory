#
#   Copyright 2012 Red Hat, Inc.
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
import oauth2 as oauth
from imgfac.rest.bottle import * 
from imgfac.ApplicationConfiguration import ApplicationConfiguration

log = logging.getLogger(__name__)

oauth_server = oauth.Server(signature_methods={'HMAC-SHA1':oauth.SignatureMethod_HMAC_SHA1()})

class Consumer(object):
    def __init__(self, key):
        consumers = ApplicationConfiguration().configuration['clients']
        self.key = key
        self.secret = consumers.get(key) if consumers else None

def validate_two_leg_oauth():
    try:
        auth_header_key = 'Authorization'
        auth_header = {}
        if auth_header_key in request.headers:
            auth_header.update({auth_header_key:request.headers[auth_header_key]})
        else:
            response.set_header('WWW-Authenticate', 'OAuth')
            raise HTTPResponse(status=401, output='Unauthorized: missing authorization')
        req = oauth.Request.from_request(request.method,
                                         request.url,
                                         headers=auth_header,
                                         parameters=request.params)
        oauth_consumer = Consumer(request.params['oauth_consumer_key'])
        oauth_server.verify_request(req, oauth_consumer, None)
        return True
    except AttributeError as e:
        log.debug('Returning HTTP 401 (Unauthorized: authorization failed) on exception: %s' % e)
        response.set_header('WWW-Authenticate', 'OAuth')
        raise HTTPResponse(status=401, output='Unauthorized: authorization failed')
    except Exception as e:
        log.exception('Returning HTTP 500 (OAuth validation failed) on exception: %s' % e)
        raise HTTPResponse(status=500, output='OAuth validation failed: %s' % e)

def oauth_protect(f):
    def decorated_function(*args, **kwargs):
        if(not ApplicationConfiguration().configuration['no_oauth']):
            validate_two_leg_oauth()
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

