#
#   Copyright 2012 Red Hat, Inc.
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
from imgfac.rest.RESTtools import *
from imgfac.rest.OAuthTools import oauth_protect
from traceback import *

log = logging.getLogger(__name__)

rest_api = Bottle(catchall=True)

@rest_api.get('/imagefactory')
def api_info():
    # TODO: Change this so 'version' is pulled from Application
    return {'name':'imagefactory', 'version':'1.1','api_version':'2.0'}

@rest_api.get('/imagefactory/base_images')
@rest_api.get('/imagefactory/target_images')
@rest_api.get('/imagefactory/provider_images')
@rest_api.get('/imagefactory/base_images/:base_image_id/target_images')
@rest_api.get('/imagefactory/target_images/:target_image_id/provider_images')
@oauth_protect
def list_images(base_image_id=None, target_image_id=None):
    pass

@rest_api.post('/imagefactory/base_images')
@rest_api.post('/imagefactory/target_images')
@rest_api.post('/imagefactory/provider_images')
@rest_api.post('/imagefactory/base_images/:base_image_id/target_images')
@rest_api.post('/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images')
@rest_api.post('/imagefactory/target_images/:target_image_id/provider_images')
@oauth_protect
def create_image(base_image_id=None, target_image_id=None):
    pass

@rest_api.get('/imagefactory/base_images/:base_image_id')
@rest_api.get('/imagefactory/target_images/:target_image_id')
@rest_api.get('/imagefactory/provider_images/:provider_image_id')
@rest_api.get('/imagefactory/base_images/:base_image_id/target_images/:target_image_id')
@rest_api.get('/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images/:provider_image_id')
@oauth_protect
def image_with_id(base_image_id=None, target_image_id=None, provider_image_id=None):
    pass

# Things we have not yet implemented
@rest_api.delete('/imagefactory/base_images/:base_image_id')
@rest_api.delete('/imagefactory/target_images/:target_image_id')
@rest_api.delete('/imagefactory/provider_images/:provider_image_id')
@rest_api.get('/imagefactory/targets')
@rest_api.get('/imagefactory/targets/:target_id')
@rest_api.get('/imagefactory/targets/:target_id/providers')
@rest_api.get('/imagefactory/targets/:target_id/providers/:provider_id')
@rest_api.get('/imagefactory/jeos')
@rest_api.get('/imagefactory/jeos/:jeos_id')
@rest_api.get('/imagefactory/plugins')
@rest_api.get('/imagefactory/plugins/:plugin_id')
def method_not_implemented(**kw):
    """
    @return 501 Not Implemented
    """
    raise HTTPResponse(status=501)

# Things we don't plan to implement
@rest_api.route('/imagefactory', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/base_images', method=('PUT','DELETE'))
@rest_api.route('/imagefactory/base_images/:base_image_id', method=('PUT','POST'))
@rest_api.route('/imagefactory/target_images', method=('PUT','DELETE'))
@rest_api.route('/imagefactory/target_images/:target_image_id', method=('PUT','POST'))
@rest_api.route('/imagefactory/target_images/:target_image_id/provider_images', method=('PUT','DELETE'))
@rest_api.route('/imagefactory/provider_images', method=('PUT','DELETE'))
@rest_api.route('/imagefactory/provider_images/:provider_image_id', method=('PUT','POST'))
@rest_api.route('/imagefactory/base_images/:base_image_id/target_images', method=('PUT','DELETE'))
@rest_api.route('/imagefactory/base_images/:base_image_id/target_images/:target_image_id', method=('PUT','POST'))
@rest_api.route('/imagefactory/base_images/:base_image_id/target_images/:target_image_id/provider_images', method=('PUT','DELETE'))
@rest_api.route('/imagefactory/targets', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/targets/:target_id', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/targets/:target_id/providers', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/targets/:target_id/providers/:provider_id', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/jeos', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/jeos/:jeos_id', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/plugins', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/plugins/:plugin_id', method=('PUT','POST','DELETE'))
def method_not_allowed(**kw):
    """
    @return 405 Method Not Allowed
    """
    raise HTTPResponse(status=405)
