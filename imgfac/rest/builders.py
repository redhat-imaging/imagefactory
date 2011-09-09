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


@get('/imagefactory/builders')
def list_():
    """
    TODO: Docstring for list_ 

    @return TODO
    """
    raise HTTPResponse(status=501)

@get('/imagefactory/builders/:builder_id')
def builder_detail(builder_id):
    """
    TODO: Docstring for builder_detail
    
    @param builder_id TODO 

    @return TODO
    """
    raise HTTPResponse(status=501)

@get('/imagefactory/builders/:builder_id/status')
def builder_status(builder_id):
    """
    TODO: Docstring for builder_status
    
    @param builder_id TODO 

    @return TODO
    """
    raise HTTPResponse(status=501)

# Things we have not yet implemented
@delete('/imagefactory/builders/:builder_id')
def method_not_implemented(**kw):
    """
    @return 501 Not Implemented
    """
    raise HTTPResponse(status=501)

# Things we don't plan to implement
@route('/imagefactory/builders', method=('PUT','POST','DELETE'))
@route('/imagefactory/builders/:builder_id', method=('PUT','POST'))
@route('/imagefactory/builders/:builder_id/status', method=('PUT','POST','DELETE'))
def method_not_allowed(**kw):
    """
    @return 405 Method Not Allowed
    """
    raise HTTPResponse(status=405)
