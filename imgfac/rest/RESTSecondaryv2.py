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

import sys
sys.path.insert(1, '%s/imgfac/rest' % sys.path[0])

import logging
import os.path
import shutil
from bottle import *
import imgfac.rest.RESTtools as RESTtools
from imgfac.rest.OAuthTools import oauth_protect
from imgfac.BuildDispatcher import BuildDispatcher
from imgfac.SecondaryDispatcher import SecondaryDispatcher
from imgfac.PluginManager import PluginManager
from imgfac.PersistentImageManager import PersistentImageManager
from imgfac.Version import VERSION as VERSION
from imgfac.ApplicationConfiguration import ApplicationConfiguration

log = logging.getLogger(__name__)

rest_api = Bottle(catchall=True)
debug(True)

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

def log_request_nobody(f):
    def decorated_function(*args, **kwargs):
        if(ApplicationConfiguration().configuration['debug']):
            log.debug('Handling %s HTTP %s REQUEST for resource at %s - body not logged' % (request.headers.get('Content-Type'),
                                                                              request.method,
                                                                              request.path))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@rest_api.get('/imagefactory')
@log_request
def api_info():
    return {'name':'imagefactory_secondary', 'version':VERSION, 'api_version':'2.0'}

@rest_api.post('/imagefactory/image_body_upload/<upload_id>')
@log_request_nobody
#The ID itself is functioning as a shared secret available only to a client
#that successfully authenticated below.  The signature overhead for these files
#is large and in testing, the combined upload and verification time actually results
#in the client-produced signature becoming invalid due to timeout
#@oauth_protect
def do_body_upload(upload_id):

    try:
        log.debug("Incoming file upload request has files %s" % (request.files.keys()))
        request_copy = request.copy()
        new_body = request_copy.files.image_body.file
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=400, output='Incoming POST did not contain a file named image_body')

    try:
        target_image_uuid = SecondaryDispatcher().target_image_for_upload_uuid(upload_id)
        log.debug("Got target_image UUID of %s" % (target_image_uuid))
        if not target_image_uuid:
            log.debug("Failed to find target image for upload UUID of %s" % (upload_id))
            raise HTTPResponse(status=404, output='Upload ID %s not found' % (upload_id))
        target_image = PersistentImageManager.default_manager().image_with_id(target_image_uuid)
        if not target_image:
            raise HTTPResponse(status=404, output='No target_image with ID %s found' % (target_image_uuid))
        log.debug("Got actual target_image")
        SecondaryDispatcher().update_target_image_body(target_image, new_body)
    finally:
        pass
        # Bottle resets the connection if we don't do this
        #new_body.close()

    response.status=202
    return { "status_text": "Finished without an exception" }

@rest_api.get('/imagefactory/<image_collection>/<image_id>')
@rest_api.post('/imagefactory/<image_collection>/<image_id>')
@rest_api.get('/imagefactory/<image_collection>/<image_id>')
@rest_api.post('/imagefactory/<image_collection>/<image_id>')
@log_request
@oauth_protect
def operate_on_image_with_id(image_collection, image_id):
    log.debug("In the generic route (%s)" % request.method)
    image_type = image_collection[0:-1]

    if image_type not in [ 'target_image', 'provider_image' ]:
        raise HTTPResponse(status=500, output='Attempt to access invalid image type: %s' % image_type)

    if request.method == "GET":
        log.debug("In the generic GET")
	try:
	    image = PersistentImageManager.default_manager().image_with_id(image_id)
	    if(not image):
                log.error("Did search for image with id (%s) and got (%s)" % (image_id, image))
		raise HTTPResponse(status=404, output='No image found with id: %s' % (image_id))
            else:
                log.debug("Found image id (%s). Constructing response" % (image_id))
	    _type = type(image).__name__
	    _response = {'_type':_type,
			 'id':image.identifier,
			 'href':request.url}
	    for key in image.metadata():
		if key not in ('identifier', 'data', 'base_image_id', 'target_image_id'):
		    _response[key] = getattr(image, key, None)

	    api_url = '%s://%s/imagefactory' % (request.urlparts[0], request.urlparts[1])

	    if(_type == "TargetImage"):
		_objtype = 'target_image'
	    elif(_type == "ProviderImage"):
		_objtype = 'provider_image'
	    else:
		log.error("Returning HTTP status 500 due to unknown image type: %s" % _type)
		raise HTTPResponse(status=500, output='Bad type for found object: %s' % _type) 

            if _objtype != image_type:
                raise HTTPResponse(status=500, output='Requested image type %s got image of type %s' % (image_type, _objtype))

	    response.status = 200
	    return {_objtype:_response}
	except Exception as e:
	    log.exception(e)
	    raise HTTPResponse(status=500, output=e)

#@rest_api.get('/imagefactory/<image_collection>')
#@rest_api.get('/imagefactory/target_images/<target_image_id>/<image_collection>')
#@log_request
#@oauth_protect
#def list_images(image_collection, base_image_id=None, target_image_id=None, list_url=None):
#    try:
#        fetch_spec = {}
#        if(image_collection == 'target_images'):
#            fetch_spec['type'] = 'TargetImage'
#        elif(image_collection == 'provider_images'):
#            fetch_spec['type'] = 'ProviderImage'
#            if target_image_id:
#                fetch_spec['target_image_id'] = target_image_id
#        else:
#            raise HTTPResponse(status=404, output='%s not found' % image_collection)
#
#        fetched_images = PersistentImageManager.default_manager().images_from_query(fetch_spec)
#        images = list()
#        _url = list_url if list_url else request.url
#        for image in fetched_images:
#            resp_item = {image_collection[0:-1]:
#                            {'_type':type(image).__name__,
#                            'id':image.identifier,
#                            'href':'%s/%s' % (_url, image.identifier)}
#                        }
#            images.append(resp_item)
#
#        return images
#    except Exception as e:
#        log.exception(e)
#        raise HTTPResponse(status=500, output=e)

#@rest_api.post('/imagefactory/target_images/<target_image_id>')
#@log_request
#@oauth_protect
#def clone_target_image(target_image_id):
    elif request.method == "POST":
        try:
	    if image_type == 'target_image':
		request_data = RESTtools.form_data_for_content_type(request.headers.get('Content-Type'))    

		(target_image, upload_id) = SecondaryDispatcher().prep_target_image_clone(request_data, image_id)

		_response = { }
		_response['target_image'] = {'_type':type(target_image).__name__,
					     'id':target_image.identifier,
					     'href':'%s' % (request.url)}
		for key in target_image.metadata():
		    if key not in ('identifier', 'data'):
			_response['target_image'][key] = getattr(target_image, key, None)
		
		if upload_id:
		    _response['upload_id'] = upload_id

		response.status = 202
		return _response
	    else:
		request_data = RESTtools.form_data_for_content_type(request.headers.get('Content-Type'))
		if(not request_data):
		    raise HTTPResponse(status=400, output='%s not found in request.' % (image_type))

		req_target_img_id = request_data.get('target_image_id')
		target_img_id = req_target_img_id if req_target_img_id else target_image_id

		builder = BuildDispatcher().builder_for_provider_image(provider=request_data.get('provider'),
								       credentials=request_data.get('credentials'),
								       target=request_data.get('target'),
								       image_id=target_img_id,
								       template=request_data.get('template'),
								       parameters=request_data.get('parameters'),
								       my_image_id=image_id)
		image = builder.provider_image

		_response = {'_type':type(image).__name__,
			     'id':image.identifier,
			     'href':'%s/%s' % (request.url, image.identifier)}
		for key in image.metadata():
		    if key not in ('identifier', 'data'):
			_response[key] = getattr(image, key, None)

		response.status = 202
		return {image_collection[0:-1]:_response}
        except Exception as e:
            log.exception(e)
	    raise HTTPResponse(status=500, output=e)
    else:
	raise HTTPResponse(status=405)

@rest_api.delete('/imagefactory/target_images/<image_id>')
@rest_api.delete('/imagefactory/provider_images/<image_id>')
@log_request
@oauth_protect
def delete_image_with_id(image_id, base_image_id=None, target_image_id=None, provider_image_id=None):
    try:
        image = PersistentImageManager.default_manager().image_with_id(image_id)
        if(not image):
            raise HTTPResponse(status=404, output='No image found with id: %s' % image_id)
        builder = Builder()
        builder.delete_image(provider=request_data.get('provider'),
                             credentials=request_data.get('credentials'),
                             target=request_data.get('target'),
                             image_object=image,
                             parameters=request_data.get('parameters'))
        response.status = 204
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output=e)

@rest_api.get('/imagefactory/plugins')
@rest_api.get('/imagefactory/plugins/')
@rest_api.get('/imagefactory/plugins/<plugin_id>')
@log_request
@oauth_protect
def get_plugins(plugin_id=None):
    try:
        response.status = 200
        plugin_mgr = PluginManager()
        if(plugin_id):
            plugin = plugin_mgr.plugins[plugin_id].copy()
            plugin.update({'_type':'plugin',
                           'id':plugin_id,
                           'href':'%s/%s' % (request.url, plugin_id)})
            return plugin
        else:
            plugins = plugin_mgr.plugins.copy()
            for plugin in plugins:
                plugins[plugin].update({'_type':'plugin',
                                        'id':plugin,
                                        'href':'%s/%s' % (request.url, plugin)})
        return {'plugins':plugins.values()}
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output='%s %s' % (e, traceback.format_exc()))

# Things we have not yet implemented
@rest_api.get('/imagefactory/targets')
@rest_api.get('/imagefactory/targets/<target_id>')
@rest_api.get('/imagefactory/targets/<target_id>/providers')
@rest_api.get('/imagefactory/targets/<target_id>/providers/<provider_id>')
@rest_api.get('/imagefactory/jeos')
@rest_api.get('/imagefactory/jeos/<jeos_id>')
@log_request
def method_not_implemented(**kw):
    """
    @return 501 Not Implemented
    """
    raise HTTPResponse(status=501)

# Things we don't plan to implement
#@rest_api.route('/imagefactory', method=('PUT','POST','DELETE'))
#@rest_api.route('/imagefactory/base_images', method=('PUT','DELETE'))
#@rest_api.route('/imagefactory/base_images/<base_image_id>', method=('PUT','POST'))
#@rest_api.route('/imagefactory/target_images', method=('PUT','DELETE'))
#@rest_api.route('/imagefactory/target_images/<target_image_id>', method=('PUT','POST'))
#@rest_api.route('/imagefactory/target_images/<target_image_id>/provider_images', method=('PUT','DELETE'))
#@rest_api.route('/imagefactory/provider_images', method=('PUT','DELETE'))
#@rest_api.route('/imagefactory/provider_images/<provider_image_id>', method=('PUT','POST'))
#@rest_api.route('/imagefactory/base_images/<base_image_id>/target_images', method=('PUT','DELETE'))
#@rest_api.route('/imagefactory/base_images/<base_image_id>/target_images/<target_image_id>', method=('PUT','POST'))
#@rest_api.route('/imagefactory/base_images/<base_image_id>/target_images/<target_image_id>/provider_images', method=('PUT','DELETE'))
#@rest_api.route('/imagefactory/targets', method=('PUT','POST','DELETE'))
#@rest_api.route('/imagefactory/targets/<target_id>', method=('PUT','POST','DELETE'))
#@rest_api.route('/imagefactory/targets/<target_id>/providers', method=('PUT','POST','DELETE'))
#@rest_api.route('/imagefactory/targets/<target_id>/providers/<provider_id>', method=('PUT','POST','DELETE'))
#@rest_api.route('/imagefactory/jeos', method=('PUT','POST','DELETE'))
#@rest_api.route('/imagefactory/jeos/<jeos_id>', method=('PUT','POST','DELETE'))
#@rest_api.route('/imagefactory/plugins', method=('PUT','POST','DELETE'))
#@rest_api.route('/imagefactory/plugins/<plugin_id>', method=('PUT','POST','DELETE'))
#def method_not_allowed(**kw):
#    """
#    @return 405 Method Not Allowed
#    """
#    raise HTTPResponse(status=405)
