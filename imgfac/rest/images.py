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
from imgfac.BuildDispatcher import BuildDispatcher


@post('/images')
def new_image():
    """
    TODO: Docstring for new_image 

    @return TODO
    """
    help_txt = """To build a new target image, supply a template and list of targets to build for.
    To import an image, supply target_name, provider_name, target_identifier, and image_descriptor."""
    # build image arguments
    template = request.forms.get('template')
    targets = request.forms.get('targets')
    # import image arguments
    target_name = request.forms.get('target_name')
    provider_name = request.forms.get('provider_name')
    target_identifier = request.forms.get('target_identifier')
    image_descriptor = request.forms.get('image_descriptor')
    image_id = request.forms.get('image_id')
    build_id = request.forms.get('build_id')

    if(template and targets):
        try:
            raise HTTPResponse(output='Method not implemented for %s' % request.fullpath, status=501)
        except Exception as e:
            raise HTTPError(exception=e)
    elif(target_name and provider_name and target_identifier and image_descriptor):
        try:
            raise HTTPResponse(output='Method not implemented for %s' % request.fullpath, status=501)
        except Exception as e:
            raise HTTPError(exception=e)
    else:
        raise HTTPError(code=400, output=help_txt)

@put('/images/:image_id')
@put('/images/:image_id/builds/:build_id')
def build_image(image_id=None, build_id=None):
    """
    TODO: Docstring for build_image
    
    @param image_id TODO
    @param build_id TODO

    @return TODO
    """
    template = request.forms.get('template')
    targets = request.forms.get('targets')

    try:
        raise HTTPResponse(output='Method not implemented for %s' % request.fullpath, status=501)
    except Exception as e:
        raise HTTPError(exception=e)

@post('/images/:image_id/builds')
@post('/images/:image_id/builds/:build_id')
def push_image(image_id, build_id=None):
    """
    TODO: Docstring for push_image
    
    @param image_id TODO
    @param build_id TODO

    @return TODO
    """
    providers = request.forms.get('providers')
    credentials = request.forms.get('credentials')

    try:
        raise HTTPResponse(output='Method not implemented for %s' % request.fullpath, status=501)
    except Exception as e:
        raise HTTPError(exception=e)

# Things we have not yet implemented
@route('/images', method=('GET','DELETE'))
@route('/images/:image_id', method=('GET','DELETE'))
@route('/images/:image_id/builds', method=('GET','DELETE'))
@route('/images/:image_id/builds/:build_id', method=('GET','DELETE'))
@route('/images/:image_id/builds/:build_id/target_images', method=('GET','PUT','POST','DELETE'))
@route('/images/:image_id/builds/:build_id/target_images/:target_image_id', method=('GET','PUT','POST','DELETE'))
@route('/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images', method=('GET','PUT','POST','DELETE'))
@route('/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images/:provider_image_id', method=('GET','PUT','POST','DELETE'))
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
