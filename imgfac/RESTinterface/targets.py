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

from bottle import route, get, put, post, delete, request, abort

@get('/targets')
def list_targets():
    """
    TODO: Docstring for list_targets

    @return 200 OK: list of supported targets
            204 No Content
    """
    pass

@get('/targets/:target_id')
def target_detail(target_id):
    """
    TODO: Docstring for target_detail

    @param target_id TODO

    @return 200 OK: target detail
            404 Not Found: exception
    """
    pass

@get('/targets/:target_id/images')
def list_images(target_id):
    """
    TODO: Docstring for list_images

    @param target_id TODO

    @return 200 OK: list of images
            404 Not Found: exception
    """
    pass

@post('/targets/:target_id/images')
def create_target_image(target_id):
    """
    TODO: Docstring for create_target_image

    @param target_id TODO

    @return 202 Accepted: target image id
            400 Bad Request: exception
            404 Not Found: exception
    """
    pass

@delete('/targets/:target_id/images')
def delete_target_images(target_id):
    """
    TODO: Docstring for delete_target_images

    @param target_id TODO

    @return 501 Not Implemented
    """
    # TODO
    # 200 OK: deleted list
    # 401 Unauthorized: exception
    # 404 Not Found: exception
    # 500 Internal Server Error: exception
    pass

@get('/targets/:target_id/images/:image_id')
def target_image_detail(target_id, image_id):
    """
    TODO: Docstring for target_image_detail

    @param target_id TODO
    @param image_id TODO

    @return 200 OK: image detail
            404 Not Found: exception
    """
    pass

@delete('/targets/:target_id/images/:image_id')
def delete_target_image(target_id, image_id):
    """
    TODO: Docstring for delete_target_image

    @param target_id TODO
    @param image_id TODO

    @return 501 Not Implemented
    """
    # TODO
    # 204 No Content
    # 401 Unauthorized: exception
    # 404 Not Found: exception
    pass

@get('/targets/:target_id/providers')
def list_providers(target_id):
    """
    TODO: Docstring for list_providers

    @param target_id TODO

    @return 200 OK: list of known providers
            404 Not Found: exception
    """
    pass

@post('/targets/:target_id/providers')
def create_provider(target_id):
    """
    TODO: Docstring for create_provider

    @param target_id TODO

    @return 501 Not Implemented
    """
    # TODO
    # 200 OK: new provider detail
    # 400 Bad Request: exception
    # 404 Not Found: exception
    pass

@delete('/targets/:target_id/providers')
def delete_providers(target_id):
    """
    TODO: Docstring for delete_providers

    @param target_id TODO

    @return 501 Not Implemented
    """
    # TODO
    # 200 OK: deleted list
    # 401 Unauthorized: exception
    # 404 Not Found: exception
    # 500 Internal Server Error: exception
    pass

@get('/targets/:target_id/providers/:provider_id')
def provider_detail(target_id, provider_id):
    """
    TODO: Docstring for provider_detail

    @param target_id TODO
    @param provider_id TODO

    @return 200 OK: provider detail
            404 Not Found: exception
    """
    pass

@delete('/targets/:target_id/providers/:provider_id')
def delete_provider(target_id, provider_id):
    """
    TODO: Docstring for delete_provider

    @param target_id TODO
    @param provider_id TODO

    @return 501 Not Implemented
    """
    # TODO
    # 200 OK: deleted item
    # 401 Unauthorized: exception
    # 404 Not Found: exception
    pass

@get('/targets/:target_id/providers/:provider_id/images')
def list_provider_images(target_id, provider_id):
    """
    TODO: Docstring for list_provider_images

    @param target_id TODO
    @param provider_id TODO

    @return 200 OK: list of provider images
            404 Not Found: exception
    """
    pass

@post('/targets/:target_id/providers/:provider_id/images')
@post('/targets/:target_id/providers/:provider_id/images/:image_id')
def create_provider_image(target_id, provider_id, image_id=None):
    """
    TODO: Docstring for create_provider_image

    @param target_id TODO
    @param provider_id TODO

    @return 202 Accepted: provider image id
            400 Bad Request: exception
            404 Not Found: exception
    """
    pass

@delete('/targets/:target_id/providers/:provider_id/images')
@delete('/targets/:target_id/providers/:provider_id/images/:image_id')
def delete_provider_images(target_id, provider_id, image_id=None):
    """
    TODO: Docstring for delete_provider_images

    @param target_id TODO
    @param provider_id TODO
    @param image_id TODO

    @return 501 Not Implemented
    """
    # TODO
    # 200 OK: deleted list
    # 401 Unauthorized: exception
    # 404 Not Found: exception
    pass

@get('/targets/:target_id/providers/:provider_id/images/:image_id')
def provider_image_detail(target_id, provider_id, image_id):
    """
    TODO: Docstring for provider_image_detail

    @param target_id TODO
    @param provider_id TODO
    @param image_id TODO

    @return 200 OK: provider image detail
            404 Not Found: exception
    """
    pass

@get('/targets/:target_id/builders')
def list_builders(target_id):
    """
    TODO: Docstring for list_builders

    @param target_id TODO

    @return 200 OK: builder list
            400 Bad Request: exception
            404 Not Found: exception
    """
    pass

@get('/targets/:target_id/builders/:builder_id')
def builder_detail(target_id, builder_id):
    """
    TODO: Docstring for builder_detail

    @param target_id TODO
    @param builder_id TODO

    @return 200 OK: builder detail
            404 Not Found: exception
    """
    pass

@delete('/targets/:target_id/builders/:builder_id')
def stop_builder(target_id, builder_id):
    """
    TODO: Docstring for stop_builder

    @param target_id TODO
    @param builder_id TODO

    @return 501 Not Implemented
    """
    # TODO
    # 200 OK: status
    # 401 Unauthorized: exception
    # 404 Not Found: exception
    pass

@get('/targets/:target_id/builders/:builder_id/status')
def builder_status(target_id, builder_id):
    """
    TODO: Docstring for builder_status

    @param target_id TODO
    @param builder_id TODO

    @return 200 OK: status detail
            404 Not Found: exception
    """
    pass

# Things that are not allowed
@route('/targets', method=('PUT','POST','DELETE'))
@route('/targets/:target_id', method=('PUT','POST','DELETE'))
@put('/targets/:target_id/images')
@route('/targets/:target_id/images/:image_id', method=('PUT','POST'))
@put('/targets/:target_id/providers')
@route('/targets/:target_id/providers/:provider_id', method=('PUT','POST'))
@put('/targets/:target_id/providers/:provider_id/images')
@put('/targets/:target_id/providers/:provider_id/images/:image_id')
@route('/targets/:target_id/builders', method=('PUT','POST','DELETE'))
@route('/targets/:target_id/builders/:builder_id', method=('PUT','POST'))
@route('/targets/:target_id/builders/:builder_id/status', method=('PUT','POST','DELETE'))
def method_not_allowed():
    """
    Not allowed.  No plans to implement.

    @return 405 Method Not Allowed
    """
    pass
