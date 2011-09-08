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


# Things we have not yet implemented
@route('/images', method=('GET','DELETE'))
@route('/images/:image_id', method=('GET','DELETE'))
@route('/images/:image_id/builds', method=('GET','DELETE'))
@route('/images/:image_id/builds/:build_id', method=('GET','DELETE'))
def method_not_implemented(**kw):
    """
    @return 501 Not Implemented
    """
    raise HTTPResponse(output='Method not implemented for %s' % request.fullpath, status=501)

# Things we don't plan to implement
@route('/images', method=('PUT'))
@route('/images/:image_id', method=('POST'))
@route('/images/:image_id/builds', method=('PUT'))
def method_not_allowed(**kw):
    """
    @return 405 Method Not Allowed
    """
    raise HTTPResponse(output='Method not allowed for %s' % request.fullpath, status=405)
