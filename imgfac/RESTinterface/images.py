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


@get('/images')
def list_images():
    """
    TODO: Docstring for list_images 

    @return 200 OK: image list
            204 No Content
    """
    pass

@get('/images/:image_id')
def image_detail(image_id):
    """
    TODO: Docstring for image_detail 

    @return 200 OK: build list
            404 Not Found: exception
    """
    pass

@post('/images')
@post('/images/:image_id')
def create_image(image_id):
    """
    TODO: Docstring for create_image

    @return 202 Accepted: image_id, build_id, target_ids
            400 Bad Request: exception
            404 Not Found: exception
    """
    pass

@delete('/images')
@delete('/images/:image_id')
def delete_images(image_id):
    """
    Planned for implementation.

    @return 501 Not Implemented
    """
    # TODO implement with the following return possibilities
    # 200 OK: deleted list
    # 401 Not Authorized: exception
    # 404 Not Found: exception
    # 500 Internal Server Error: exception
    pass

@post('/images/import')
@post('/images/:image_id/import')
@post('/images/:image_id/builds/:build_id/import')
def import_image(image_id, build_id=None):
    """
    TODO: Docstring for import_image 

    @return TODO
    """
    pass

@get('/images/:image_id/builds')
def list_builds():
    """
    TODO: Docstring for list_builds

    @return 200 OK: build list
            404 Not Found: exception
    """
    pass

@get('/images/:image_id/builds/:build_id')
def build_detail(image_id, build_id):
    """
    TODO: Docstring for build_detail 

    @return 200 OK: build list
            404 Not Found: exception
    """
    pass

@post('/images/:image_id/builds')
@route('/images/:image_id/builds/:build_id', method=('PUT','POST'))
def build_image(image_id, build_id=None):
    """
    TODO: Docstring for build_image
    
    @param image_id TODO
    @param build_id TODO

    @return 202 Accepted: build_id, target_id list
            400 Bad Request: exception
            404 Not Found: exception
    """
    pass

@delete('/images/:image_id/builds')
@delete('/images/:image_id/builds/:build_id')
def delete_builds(image_id, build_id=None):
    """
    Planned for implementation.

    @return 501 Not Implemented
    """
    # TODO implement with the following return possibilities
    # 200 OK: deleted list
    # 401 Not Authorized: exception
    # 404 Not Found: exception
    # 500 Internal Server Error: exception
    pass

# Things that are not allowed
@put('/images')
@put('/images/:image_id')
@put('/images/:image_id/builds')
@route('/images/import', method=('GET','PUT','DELETE'))
@route('/images/:image_id/import', method=('GET','PUT','DELETE'))
@route('/images/:image_id/builds/:build_id/import', method=('GET','PUT','DELETE'))
def method_not_allowed():
    """
    Not allowed.  No plans to implement.

    @return 405 Method Not Allowed
    """
    pass
