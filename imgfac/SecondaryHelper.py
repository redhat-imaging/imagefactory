# encoding: utf-8

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

import oauth2 as oauth
#from imgfac.ApplicationConfiguration import ApplicationConfiguration
#import socks
import logging
import pycurl
import httplib2
import urllib
import urllib2
import requests
import json
from oauth_hook import OAuthHook

class SecondaryHelper(object):

    def __init__(self, oauth=False, key = None, secret = None, proxy = False, proxy_host = None, proxy_port = None, 
                 base_url = None):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))

        self.oauth = oauth
        self.key = key
        self.secret = secret
        if proxy:
            self.proxies = { "http": "%s:%s" % (proxy_host, proxy_port),
                             "https": "%s:%s" % (proxy_host, proxy_port) }
        else:
            self.proxies = None
        self.base_url = base_url

    def request(self, url, method, body = None, content_type = 'text/plain', files = None):

        if self.oauth:
            oauth_hook = OAuthHook(consumer_key=self.key, consumer_secret=self.secret, header_auth = True)
            hooks = { 'pre_request': oauth_hook }
        else:
            hooks = { }

        try:
            headers = { }
            headers['content-type'] = content_type
            if method == "GET":
                response = requests.get(url, proxies=self.proxies, verify=False)
            elif method == "POST":
                response = requests.post(url, data=body, headers = headers, hooks=hooks, proxies=self.proxies, verify=False)
            elif method == "POSTFILE":
                response = requests.post(url, files=files, hooks = hooks, verify=False)
            elif method == "PUT":
                response = requests.put(url, data=body, headers=headers, proxies=self.proxies)
            else:
                raise Exception("Unable to process HTTP method (%s)" % (method) )

            response_body = response.content
            response_json = response.json
            response_headers = response.headers
            if response_json:
                self.log.debug("Response JSON attribute exists and is (%s)" % (response_json))
                self.log.debug("Response BODY attribute is (%s)" % (response_body))
            status = response.status_code
            # Log additional detail if the HTTP resonse code is abnormal
            if(399 < status < 600):
                self.log.debug("HTTP request to (%s) returned status (%d) with message: %s" % (url, status, response_body))
            return (response_headers, response_body)
        except Exception, e:
            raise Exception("Problem encountered trying to execute HTTP request to (%s). Please check that your target service is running and reachable.\nException text: %s" % (url, e))

    def _http_get_json(self, path):
        result = self._http_get(path)
        self.log.debug("Got result (%s) attempting to decode as JSON" % (result))
        return json.loads(result)

    def _http_get(self, path):
        self.log.debug("Doing GET from path (%s)" % (path))
        return self.request(self.base_url + path, 'GET')[1]

    def _http_post_json(self, path, body):
        return json.loads(self._http_post(path, json.dumps(body), 'application/json'))

    def _http_post(self, path, body, content_type):
        self.log.debug("Doing POST to path (%s) with body (%s) and content type (%s)" % (path, body, content_type))
        return self.request(self.base_url + path, 'POST', body, content_type)[1]

    def _http_post_files(self, path, files):
        self.log.debug("Doing POST of file to path (%s) with files (%s)" % (path, files.keys()))
        return self.request(self.base_url + path, 'POSTFILE', files=files)

    def _http_put(self, path, body = None):
        self.log.debug("Doing PUT to path (%s) with body (%s)" (path, body))
        return self.request(self.base_url +  path, 'PUT', body)[1]

