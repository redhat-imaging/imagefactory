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

import sys
import traceback

sys.path.insert(1, '%s/imgfac/rest' % sys.path[0])

import logging
import os.path
from bottle import *
from imgfac.rest.RESTtools import *
from imgfac.rest.OAuthTools import oauth_protect
from imgfac.BuildDispatcher import BuildDispatcher
from imgfac.PluginManager import PluginManager
from imgfac.PersistentImageManager import PersistentImageManager
from imgfac.Version import VERSION as VERSION
from imgfac.picklingtools.xmldumper import *
from imgfac.Builder import Builder

log = logging.getLogger(__name__)

rest_api = Bottle(catchall=True)

IMAGE_TYPES = {'BaseImage': 'base_image', 'TargetImage': 'target_image', 'ProviderImage': 'provider_image',
               'base_images': 'BaseImage', 'target_images': 'TargetImage', 'provider_images': 'ProviderImage'}

def converted_response(resp_dict):
    if('xml' in request.get_header('Accept', '')):
        response.set_header('Content-Type', request.get_header('Accept', None))
        xml_options = XML_DUMP_STRINGS_AS_STRINGS | XML_DUMP_PRETTY | XML_DUMP_POD_LIST_AS_XML_LIST
        string_stream = cStringIO.StringIO()
        WriteToXMLStream(resp_dict, string_stream, options=xml_options)
        converted_response = string_stream.getvalue()
        return converted_response
    else:
        return resp_dict

@rest_api.get('/imagefactory')
@log_request
@check_accept_header
def api_info():
    return converted_response({'name':'imagefactory', 'version':VERSION, 'api_version':'2.0'})

@rest_api.get('/imagefactory/<image_collection>')
@rest_api.get('/imagefactory/base_images/<base_image_id>/<image_collection>')
@rest_api.get('/imagefactory/target_images/<target_image_id>/<image_collection>')
@log_request
@oauth_protect
@check_accept_header
def list_images(image_collection, base_image_id=None, target_image_id=None, list_url=None):
    try:
        _type = IMAGE_TYPES[image_collection]
        if _type:
            fetch_spec = {'type': _type}
            if base_image_id:
                fetch_spec['base_image_id'] = base_image_id
            if target_image_id:
                fetch_spec['target_image_id'] = target_image_id
        else:
            raise HTTPResponse(status=404, output='%s not found' % image_collection)

        fetched_images = PersistentImageManager.default_manager().images_from_query(fetch_spec)
        images = list()
        _url = list_url if list_url else request.url
        for image in fetched_images:
            resp_item = {image_collection[0:-1]:
                            {'_type':type(image).__name__,
                            'id':image.identifier,
                            'href':'%s/%s' % (_url, image.identifier)}
                        }
            images.append(resp_item)

        return converted_response({image_collection:images})
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output=e)

@rest_api.post('/imagefactory/<image_collection>')
@rest_api.post('/imagefactory/base_images/<base_image_id>/<image_collection>')
@rest_api.post('/imagefactory/base_images/<base_image_id>/target_images/<target_image_id>/<image_collection>')
@rest_api.post('/imagefactory/target_images/<target_image_id>/<image_collection>')
@log_request
@oauth_protect
@check_accept_header
def create_image(image_collection, base_image_id=None, target_image_id=None):
    try:
        image_type = image_collection[0:-1]
        content_type = request.headers.get('Content-Type')
        form_data = form_data_for_content_type(content_type)
        if(('application/x-www-form-urlencoded' in content_type) or ('multipart/form-data' in content_type)):
            request_data = form_data
        else:
            request_data = form_data.get(image_type)
        if(not request_data):
            raise HTTPResponse(status=400, output='%s not found in request.' % image_type)

        req_base_img_id = request_data.get('base_image_id')
        req_target_img_id = request_data.get('target_image_id')
        base_img_id = req_base_img_id if req_base_img_id else base_image_id
        target_img_id = req_target_img_id if req_target_img_id else target_image_id

        if(image_collection == 'base_images'):
            builder = BuildDispatcher().builder_for_base_image(template=request_data.get('template'),
                                                               parameters=request_data.get('parameters'))
            image = builder.base_image
        elif(image_collection == 'target_images'):
            builder = BuildDispatcher().builder_for_target_image(target=request_data.get('target'),
                                                                 image_id=base_img_id,
                                                                 template=request_data.get('template'),
                                                                 parameters=request_data.get('parameters'))
            image = builder.target_image
        elif(image_collection == 'provider_images'):
            _provider = request_data.get('provider')
            _credentials = request_data.get('credentials')
            _target = request_data.get('target')
            if(_provider and _credentials and _target):
                builder = BuildDispatcher().builder_for_provider_image(provider=_provider,
                                                                   credentials=_credentials,
                                                                   target=_target,
                                                                   image_id=target_img_id,
                                                                   template=request_data.get('template'),
                                                                   parameters=request_data.get('parameters'))
                image = builder.provider_image
            else:
                _credentials = 'REDACTED' if _credentials else None
                raise HTTPResponse(status=400, output="Missing key/value pair: provider(%s), credentials(%s), target(%s)" % (_provider, _credentials, _target))
        else:
            raise HTTPResponse(status=404, output="%s not found" % image_collection)

        _response = {'_type':type(image).__name__,
                     'id':image.identifier,
                     'href':'%s/%s' % (request.url, image.identifier)}
        for key in image.metadata():
            if key not in ('identifier', 'data'):
                _response[key] = getattr(image, key, None)

        response.status = 202
        return converted_response({image_collection[0:-1]:_response})
    except KeyError as e:
        log.exception(e)
        raise HTTPResponse(status=400, output='Missing value for key: %s' % e)
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output=e)

@rest_api.get('/imagefactory/<collection_type>/<image_id>')
@rest_api.get('/imagefactory/base_images/<base_image_id>/<collection_type>/<image_id>')
@rest_api.get('/imagefactory/base_images/<base_image_id>/target_images/<target_image_id>/<collection_type>/<image_id>')
@rest_api.get('/imagefactory/target_images/<target_image_id>/<collection_type>/<image_id>')
@log_request
@oauth_protect
@check_accept_header
def image_with_id(collection_type, image_id, base_image_id=None, target_image_id=None, provider_image_id=None):
    try:
        img_class = IMAGE_TYPES[collection_type]
        if img_class:
            fetch_spec = {'type': img_class, 'identifier': image_id}
            try:
                image = PersistentImageManager.default_manager().images_from_query(fetch_spec)[0]
                _type = type(image).__name__
                _response = {'_type': _type,
                             'id': image.identifier,
                             'href': request.url}
                for key in image.metadata():
                    if key not in ('identifier', 'data', 'base_image_id', 'target_image_id'):
                        _response[key] = getattr(image, key, None)

                api_url = '%s://%s/imagefactory' % (request.urlparts[0], request.urlparts[1])

                if (_type == "BaseImage"):
                    _objtype = 'base_image'
                    _response['target_images'] = list_images('target_images',
                                                             base_image_id=image.identifier,
                                                             list_url='%s/target_images' % api_url)
                elif (_type == "TargetImage"):
                    _objtype = 'target_image'
                    base_image_id = image.base_image_id
                    if (base_image_id):
                        base_image_href = '%s/base_images/%s' % (api_url, base_image_id)
                        base_image_dict = {'_type': 'BaseImage', 'id': base_image_id, 'href': base_image_href}
                        _response['base_image'] = base_image_dict
                    else:
                        _response['base_image'] = None
                    _response['provider_images'] = list_images('provider_images',
                                                               target_image_id=image.identifier,
                                                               list_url='%s/provider_images' % api_url)
                elif (_type == "ProviderImage"):
                    _objtype = 'provider_image'
                    target_image_id = image.target_image_id
                    if (target_image_id):
                        target_image_href = '%s/target_images/%s' % (api_url, target_image_id)
                        target_image_dict = {'_type': 'TargetImage', 'id': target_image_id, 'href': target_image_href}
                        _response['target_image'] = target_image_dict
                    else:
                        _response['target_image'] = None
                else:
                    log.error("Returning HTTP status 500 due to unknown image type: %s" % _type)
                    raise HTTPResponse(status=500, output='Bad type for found object: %s' % _type)

                response.status = 200
                return converted_response({_objtype: _response})

            except IndexError as e:
                log.warning(e)
                raise HTTPResponse(status=404, output='No %s found with id: %s' % (img_class, image_id))
        else:
            raise HTTPResponse(status=404, output='Unknown resource type: %s' % collection_type)
    except KeyError as e:
        if collection_type == 'plugins':
            return get_plugins(plugin_id=image_id)
        else:
            log.exception(e)
            raise HTTPResponse(status=500, output=e)
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output=e)

@rest_api.get('/imagefactory/base_images/<image_id>/raw_image')
@rest_api.get('/imagefactory/target_images/<image_id>/raw_image')
@rest_api.get('/imagefactory/provider_images/<image_id>/raw_image')
@rest_api.get('/imagefactory/base_images/<base_image_id>/target_images/<image_id>/raw_image')
@rest_api.get('/imagefactory/base_images/<base_image_id>/target_images/<target_image_id>/provider_images/<image_id>/raw_image')
@rest_api.get('/imagefactory/target_images/<target_image_id>/provider_images/<image_id>/raw_image')
@log_request
@oauth_protect
@check_accept_header
def get_image_file(image_id, base_image_id=None, target_image_id=None, provider_image_id=None):
    try:
        image = PersistentImageManager.default_manager().image_with_id(image_id)
        if(not image):
            raise HTTPResponse(status=404, output='No image found with id: %s' % image_id)
        path, filename = os.path.split(image.data)
        return static_file(filename, path, download=True)
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output=e)

@rest_api.delete('/imagefactory/<collection_type>/<image_id>')
@rest_api.delete('/imagefactory/base_images/<base_image_id>/<collection_type>/<image_id>')
@rest_api.delete('/imagefactory/base_images/<base_image_id>/target_images/<target_image_id>/<collection_type>/<image_id>')
@rest_api.delete('/imagefactory/target_images/<target_image_id>/<collection_type>/<image_id>')
@log_request
@oauth_protect
@check_accept_header
def delete_image_with_id(image_id, collection_type=None, base_image_id=None, target_image_id=None, provider_image_id=None):
    try:
        response.status = 204
        image = PersistentImageManager.default_manager().image_with_id(image_id)
        if(not image):
            raise HTTPResponse(status=404, output='No image found with id: %s' % image_id)
        image_class = type(image).__name__
        builder = Builder()
        content_type = request.headers.get('Content-Type')
        form_data = form_data_for_content_type(content_type)
        required_values = set(['provider', 'credentials', 'target'])

        if form_data:
            root_object = form_data.get(IMAGE_TYPES.get(image_class))
            if root_object and (type(root_object) is dict):
                request_data = root_object
            else:
                request_data = form_data

            if image_class == 'ProviderImage':
                missing_values = required_values.difference(request_data)
                if len(missing_values) > 0:
                    raise HTTPResponse(status=400, output='Missing required values: %s' % missing_values)

            builder.delete_image(provider=request_data.get('provider'),
                                 credentials=request_data.get('credentials'),
                                 target=request_data.get('target'),
                                 image_object=image,
                                 parameters=request_data.get('parameters'))
        else:
            if image_class == 'ProviderImage':
                raise HTTPResponse(status=400, output='Missing required values:%s' % required_values)
            else:
                builder.delete_image(provider=None, credentials=None, target=None, image_object=image, parameters=None)
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output=e)

@rest_api.get('/imagefactory/plugins')
@rest_api.get('/imagefactory/plugins/')
@rest_api.get('/imagefactory/plugins/<plugin_id>')
@log_request
@oauth_protect
@check_accept_header
def get_plugins(plugin_id=None):
    try:
        response.status = 200
        plugin_mgr = PluginManager()
        if(plugin_id):
            plugin = plugin_mgr.plugins[plugin_id].copy()
            plugin.update({'_type':'plugin',
                           'id':plugin_id,
                           'href':'%s/%s' % (request.url, plugin_id)})
            return converted_response(plugin)
        else:
            plugins = plugin_mgr.plugins.copy()
            for plugin in plugins:
                plugins[plugin].update({'_type':'plugin',
                                        'id':plugin,
                                        'href':'%s/%s' % (request.url, plugin)})
        return converted_response({'plugins':plugins.values()})
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output='%s %s' % (e, traceback.format_exc()))

@rest_api.get('/imagefactory/jeos')
@log_request
@check_accept_header
def get_jeos_config():
    try:
        jeos_confs = dict()
        jeos_conf_list = ApplicationConfiguration().configuration['jeos_config']
        for item in jeos_conf_list:
            jeos_confs[jeos_conf_list.index(item)] = item
        return converted_response(jeos_confs)
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output='%s %s' % (e, traceback.format_exc()))

@rest_api.get('/imagefactory/jeos/images')
@rest_api.get('/imagefactory/jeos/images/<jeos_id>')
@log_request
@check_accept_header
def get_jeos_info(jeos_id=None):
    try:
        if jeos_id:
            return HTTPResponse(status=501)

        response.status = 200
        return converted_response(ApplicationConfiguration().jeos_images)
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output='%s %s' % (e, traceback.format_exc()))

# Things we have not yet implemented
@rest_api.get('/imagefactory/targets')
@rest_api.get('/imagefactory/targets/<target_id>')
@rest_api.get('/imagefactory/targets/<target_id>/providers')
@rest_api.get('/imagefactory/targets/<target_id>/providers/<provider_id>')
@log_request
@check_accept_header
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
