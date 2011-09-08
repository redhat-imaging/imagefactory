#
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

from bottle import *


@post('/targets/:target_name/providers/:provider_name/images')
def import_image(target_name, provider_name):
    """
    TODO: Docstring for import_image
    
    @param target_name TODO
    @param provider_name TODO 

    @return TODO
    """
    raise HTTPResponse(output='Method not implemented for %s' % request.fullpath, status=501)

# Things we have not yet implemented
@route('/targets', method=('GET'))
@route('/targets/:target_name', method=('GET'))
@route('/targets/:target_name/providers', method=('GET','POST','DELETE'))
@route('/targets/:target_name/providers/:provider_name', method=('GET','PUT','DELETE'))
def method_not_implemented(**kw):
    """
    @return 501 Not Implemented
    """
    raise HTTPResponse(output='Method not implemented for %s' % request.fullpath, status=501)

# Things we don't plan to implement
@route('/targets', method=('PUT','POST','DELETE'))
@route('/targets/:target_name', method=('PUT','POST','DELETE'))
@route('/targets/:target_name/providers', method=('PUT'))
@route('/targets/:target_name/providers/:provider_name', method=('POST'))
def method_not_allowed(**kw):
    """
    @return 405 Method Not Allowed
    """
    raise HTTPResponse(output='Method not allowed for %s' % request.fullpath, status=405)
