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

import logging
from imgfac.rest.bottle import *

log = logging.getLogger(__name__)

def _form_data_for_content_type(content_type):
    def dencode(a_dict, encoding='ascii'):
        new_dict = {}
        for k,v in a_dict.items():
            ek = k.encode(encoding)
            if(isinstance(v, unicode)):
                new_dict[ek] = v.encode(encoding)
            elif(isinstance(v, dict)):
                new_dict[ek] = dencode(v)
            else:
                new_dict[ek] = v
        return new_dict

    try:
        if(content_type == 'application/json'):
            keys = request.json.keys()
            if(len(keys) == 1):
                request_data = request.json[keys[0]]
            else:
                request_data = request.json
        else:
            request_data = request.forms

        return dencode(request_data)
    except Exception as e:
        log.exception(e)
        raise HTTPResponse(status=500, output=e)
