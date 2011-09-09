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

from bottle import *


# Things we have not yet implemented
@route('/imagefactory/targets', method=('GET'))
@route('/imagefactory/targets/:target_name', method=('GET'))
@route('/imagefactory/targets/:target_name/providers', method=('GET','POST','DELETE'))
@route('/imagefactory/targets/:target_name/providers/:provider_name', method=('GET','PUT','DELETE'))
def method_not_implemented(**kw):
    """
    @return 501 Not Implemented
    """
    raise HTTPResponse(status=501)

# Things we don't plan to implement
@route('/imagefactory/targets', method=('PUT','POST','DELETE'))
@route('/imagefactory/targets/:target_name', method=('PUT','POST','DELETE'))
@route('/imagefactory/targets/:target_name/providers', method=('PUT'))
@route('/imagefactory/targets/:target_name/providers/:provider_name', method=('POST'))
def method_not_allowed(**kw):
    """
    @return 405 Method Not Allowed
    """
    raise HTTPResponse(status=405)
