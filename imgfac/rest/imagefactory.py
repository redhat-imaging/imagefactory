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

import sys
import logging
import oauth2 as oauth
from bottle import *
from traceback import *
from imgfac.BuildDispatcher import BuildDispatcher
from imgfac.JobRegistry import JobRegistry
from imgfac.ApplicationConfiguration import ApplicationConfiguration

log = logging.getLogger(__name__)

sys.path.append('%s/imgfac/rest' % sys.path[0])

rest_api = Bottle(catchall=False)

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
        req = oauth.Request.from_request(request.method,
                                         request.url,
                                         headers=auth_header,
                                         parameters=request.params)
        oauth_consumer = Consumer(request.params.get('oauth_consumer_key'))
        oauth_server.verify_request(req, oauth_consumer, None)
        return True
    except oauth.Error as e:
        log.exception(e)
        raise HTTPResponse(status=401, output=e)
    except KeyError as e:
        log.exception(e)
        raise HTTPResponse(status=400, output=e)
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output=e)

def oauth_protect(f):
    def decorated_function(*args, **kwargs):
        if(not ApplicationConfiguration().configuration['no_oauth']):
            validate_two_leg_oauth()
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@rest_api.get('/imagefactory')
def api_info():
    return {'name':'imagefactory', 'version':'1.0'}

@rest_api.post('/imagefactory/images')
@rest_api.put('/imagefactory/images/:image_id')
@oauth_protect
def build_image(image_id=None):
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

    if(template and targets):
        try:
            jobs = BuildDispatcher().build_image_for_targets(image_id, None, template, targets.split(','))
            if(image_id):
                base_url = request.url
            else:
                image_id = jobs[0].image_id
                base_url = '%s/%s' % (request.url, image_id)

            image = {'_type':'image','id':image_id,'href':base_url}
            build_id = jobs[0].build_id
            build = {'_type':'build',
                        'id':build_id,
                        'href':'%s/builds/%s' % (base_url, build_id)}
            target_images = []
            for job in jobs:
                target_image_id = job.new_image_id
                target_images.append({'_type':'target_image',
                                        'id':target_image_id,
                                        'href':'%s/builds/%s/target_images/%s' % (base_url, build_id, target_image_id)})
            build['target_images'] = target_images
            image['build'] = build

            response.status = 202
            return image
        except Exception as e:
            log.exception(e)
            raise HTTPResponse(status=500, output=e)

    elif(target_name and provider_name and target_identifier and image_descriptor):
        image_id = request.forms.get('image_id')
        build_id = request.forms.get('build_id')
        try:
            import_result = BuildDispatcher().import_image(image_id,
                                                            build_id,
                                                            target_identifier,
                                                            image_descriptor,
                                                            target_name,
                                                            provider_name)
            image_id = import_result[0]
            base_url = '%s/%s' % (request.url, image_id)
            image = {'_type':'image','id':image_id,'href':base_url}
            build_id = import_result[1]
            build = {'_type':'build',
                        'id':build_id,
                        'href':'%s/builds/%s' % (base_url, build_id)}
            target_image_id = import_result[2]
            target_image = {'_type':'target_image',
                            'id':target_image_id,
                            'href':'%s/builds/%s/target_images/%s' % (base_url, build_id, target_image_id)}
            provider_image_id = import_result[3]
            provider_image = {'_type':'provider_image',
                                'id':provider_image_id,
                                'href':'%s/builds/%s/target_images/%s/provider_images/%s' % (base_url, build_id, target_image_id, provider_image_id)}

            target_image['provider_images'] = (provider_image,)
            build['target_images'] = (target_image,)
            image['build'] = build

            response.status = 200
            return image
        except Exception as e:
            log.exception(e)
            raise HTTPResponse(status=500, output=e)
    else:
        raise HTTPResponse(status=400, output=help_txt)

@rest_api.post('/imagefactory/images/:image_id/builds/:build_id/target_image/:target_image_id/provider_images')
@oauth_protect
def push_image(image_id, build_id, target_image_id):
    provider = request.forms.get('provider')
    credentials = request.forms.get('credentials')

    if(provider and credentials and (len(provider.split(',')) == 1)):
        try:
            response.status = 202
            job = BuildDispatcher().push_image_to_providers(image_id, build_id, provider, credentials)[0]

            provider_image_id = job.new_image_id
            return {'_type':'provider_image',
                    'id':provider_image_id,
                    'href':'%s/%s' % (request.url, provider_image_id)}

        except Exception as e:
            log.exception(e)
            raise HTTPResponse(status=500, output=e)
    else:
        raise HTTPResponse(status=400, output='To push an image, a provider id and provider credentials must be supplied.')

@rest_api.get('/imagefactory/builders')
def list_builders():
    collection = {'_type':'builders','href':request.url}
    jobs = JobRegistry().jobs
    builders = []
    for builder_id in jobs.keys():
        job = jobs[builder_id]
        builders.append({'completed':job.percent_complete,
                         'status':job.status,
                         'operation':job.operation,
                         'target':job.target,
                         '_type':'builder',
                         'id':builder_id,
                         'href':'%s/%s' % (request.url, builder_id)})

    collection['builders'] = builders
    return collection

@rest_api.get('/imagefactory/builders/:builder_id')
@rest_api.get('/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id')
@rest_api.get('/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images/:provider_image_id')
def builder_detail(builder_id=None, image_id=None, build_id=None, target_image_id=None, provider_image_id=None):
    if(builder_id):
        _id = builder_id
        _type = 'builder'
    elif(target_image_id and provider_image_id):
        _id = provider_image_id
        _type = 'provider_image_status'
    elif(target_image_id):
        _id = target_image_id
        _type = 'target_image_status'
    else:
        response.status = 404
        return

    job = JobRegistry().jobs[_id]
    return {'completed':job.percent_complete,
            'status':job.status,
            'operation':job.operation,
            'target':job.target,
            'href':request.url,
            'id':_id,
            '_type':_type}

@rest_api.get('/imagefactory/builders/:builder_id/status')
@rest_api.get('/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/status')
@rest_api.get('/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images/:provider_image_id/status')
def builder_status(builder_id=None, image_id=None, build_id=None, target_image_id=None, provider_image_id=None):
    if(builder_id):
        _id = builder_id
        _type = 'builder_status'
    elif(target_image_id and provider_image_id):
        _id = provider_image_id
        _type = 'provider_image_status'
    elif(target_image_id):
        _id = target_image_id
        _type = 'target_image_status'
    else:
        response.status = 404
        return

    job = JobRegistry().jobs[_id]
    return {'_type':_type,
            'id':_id,
            'href':request.url,
            'status':job.status}

# Things we have not yet implemented
@rest_api.route('/imagefactory/images', method=('GET','DELETE'))
@rest_api.route('/imagefactory/images/:image_id', method=('GET','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds', method=('GET','POST','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id', method=('GET','PUT','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_images', method=('GET','POST','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id', method=('PUT','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images', method=('GET','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images/:provider_image_id', method=('PUT','DELETE'))
@rest_api.route('/imagefactory/targets', method=('GET'))
@rest_api.route('/imagefactory/targets/:target_name', method=('GET'))
@rest_api.route('/imagefactory/targets/:target_name/providers', method=('GET','POST','DELETE'))
@rest_api.route('/imagefactory/targets/:target_name/providers/:provider_name', method=('GET','PUT','DELETE'))
@rest_api.delete('/imagefactory/builders/:builder_id')
def method_not_implemented(**kw):
    """
    @return 501 Not Implemented
    """
    raise HTTPResponse(status=501)

# Things we don't plan to implement
@rest_api.route('/imagefactory/images', method=('PUT'))
@rest_api.route('/imagefactory/images/:image_id', method=('POST'))
@rest_api.route('/imagefactory/images/:image_id/builds', method=('PUT'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id', method=('POST'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_images', method=('PUT'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id', method=('POST'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images', method=('PUT'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_images/:target_image_id/provider_images/:provider_image_id', method=('POST'))
@rest_api.route('/imagefactory/targets', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/targets/:target_name', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/targets/:target_name/providers', method=('PUT'))
@rest_api.route('/imagefactory/targets/:target_name/providers/:provider_name', method=('POST'))
@rest_api.route('/imagefactory/builders', method=('PUT','POST','DELETE'))
@rest_api.route('/imagefactory/builders/:builder_id', method=('PUT','POST'))
@rest_api.route('/imagefactory/builders/:builder_id/status', method=('PUT','POST','DELETE'))
def method_not_allowed(**kw):
    """
    @return 405 Method Not Allowed
    """
    raise HTTPResponse(status=405)
