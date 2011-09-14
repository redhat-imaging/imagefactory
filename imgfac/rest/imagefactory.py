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
import sys
from traceback import *
from imgfac.BuildDispatcher import BuildDispatcher
from imgfac.JobRegistry import JobRegistry


rest_api = Bottle()

@rest_api.get('/imagefactory')
def api_info():
    """
    TODO: Docstring for api_info 

    @return TODO
    """
    return {'name':'imagefactory', 'version':'0.1'}

@rest_api.post('/imagefactory/images')
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
            return build_image()
        except Exception as e:
            response.status = 500
            return {'exception':e, 'traceback':format_tb(sys.exc_info()[2])}
    elif(target_name and provider_name and target_identifier and image_descriptor):
        try:
            import_result = BuildDispatcher().import_image(image_id,
                                                            build_id,
                                                            target_identifier,
                                                            image_descriptor,
                                                            target_name,
                                                            provider_name)
            response_body = {'image_id':import_result[0],
                                'build_id':import_result[1],
                                'target_image_id':import_result[2],
                                'provider_image_id':import_result[3]}
            return response_body
        except Exception as e:
            response.status = 500
            return {'exception':e, 'traceback':format_tb(sys.exc_info()[2])}
    else:
        response.status = 400
        return help_txt

@rest_api.put('/imagefactory/images/:image_id')
@rest_api.put('/imagefactory/images/:image_id/builds/:build_id')
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
        jobs = BuildDispatcher().build_image_for_targets(image_id, build_id, template, targets.split(','))
        response.status = 202
        return _response_body_for_jobs(jobs)
    except Exception as e:
        response.status = 500
        return {'exception':e, 'traceback':format_tb(sys.exc_info()[2])}

@rest_api.post('/imagefactory/images/:image_id/builds')
@rest_api.post('/imagefactory/images/:image_id/builds/:build_id')
def push_image(image_id, build_id=None):
    """
    TODO: Docstring for push_image
    
    @param image_id TODO
    @param build_id TODO

    @return TODO
    """
    providers = request.forms.get('providers')
    credentials = request.forms.get('credentials')

    if(providers and credentials):
        try:
            jobs = BuildDispatcher().push_image_to_providers(image_id, build_id, providers, credentials)
            response.status = 202
            return _response_body_for_jobs(jobs)
        except Exception as e:
            response.status = 500
            return {'exception':e, 'traceback':format_tb(sys.exc_info()[2])}
    else:
        response.status = 400
        return 'To push an image, a list of providers and credentials must be supplied.'

def _response_body_for_jobs(jobs):
    """
    TODO: Docstring for _response_body_for_jobs
    
    @param jobs List of BuildJob objects

    @return Dict with keys 'image_id', 'build_id', and 'builders'
    """
    response_body = {}
    response_body.update({'image_id':jobs[0].image_id,'build_id':jobs[0].build_id})
    builders = []
    for job in jobs:
        builder_id = job.new_image_id
        builder_url = '%s://%s%s/%s' % (request.urlparts[0], request.urlparts[1], builders_route, builder_id)
        builders.append({'target':job.target, 'id':builder_id, 'href':builder_url})
    response_body.update({'builders':builders})
    return response_body

# using this var for now since I cannot get Bottle.get_url() to work -sloranz 20110909
builders_route = '/imagefactory/builders'
@rest_api.get(builders_route)
def list_():
    """
    TODO: Docstring for list_ 

    @return TODO
    """
    response_body = {}
    jobs = JobRegistry().jobs

    for key in jobs.keys():
        job = jobs[key]
        response_body.update({key:{'completed':job.percent_complete, 'status':job.status, 'type':job.operation, 'target':job.target}})

    return response_body

@rest_api.route('/imagefactory/builders/:builder_id', name='builder_detail')
def builder_detail(builder_id):
    """
    TODO: Docstring for builder_detail
    
    @param builder_id TODO 

    @return TODO
    """
    job = JobRegistry().jobs[builder_id]
    return {'completed':job.percent_complete, 'status':job.status, 'type':job.operation, 'target':job.target}

@rest_api.route('/imagefactory/builders/:builder_id/status', name='builder_status')
def builder_status(builder_id):
    """
    TODO: Docstring for builder_status
    
    @param builder_id TODO 

    @return TODO
    """
    job = JobRegistry().jobs[builder_id]
    return job.status

# Things we have not yet implemented
@rest_api.route('/imagefactory/images', method=('GET','DELETE'))
@rest_api.route('/imagefactory/images/:image_id', method=('GET','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds', method=('GET','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id', method=('GET','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_image', method=('GET','PUT','POST','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_image/:target_image_id', method=('GET','PUT','POST','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_image/:target_image_id/provider_image', method=('GET','PUT','POST','DELETE'))
@rest_api.route('/imagefactory/images/:image_id/builds/:build_id/target_image/:target_image_id/provider_image/:provider_image_id', method=('GET','PUT','POST','DELETE'))
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
