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


import logging
import re
import uuid
import props
from imgfac.Singleton import Singleton
from imgfac.BuildJob import BuildJob

class JobRegistry(Singleton):

    jobs = props.prop("_jobs", "A dict of builder_id to BuildJob instances")

    def _singleton_init(self):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.jobs = {}

    def register(self, jobs):
        """
        TODO: Docstring for register
        
        @param jobs instance of BuildJob or list of BuildJobs
        """
        new_jobs = jobs if isinstance(jobs, (tuple,list)) else (jobs, )

        for job in new_jobs:
            if(isinstance(job, BuildJob)):
                self.jobs.update({job.new_image_id:job})
            else:
                self.log.error("Attempted to add object of type: %s" % type(job))

    def delete(self, job):
        """
        TODO: Docstring for delete
        
        @param job instance of BuildJob or uuid of a job
        """
        uuid_pattern = '([0-9a-f]{8})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})'
        regex = re.compile(uuid_pattern)
        match = regex.search(job)

        if(isinstance(job, str) and match):
            builder_id = job
        elif(isinstance(job, BuildJob)):
            builder_id = job.new_image_id
        elif(isinstance(job, uuid.UUID)):
            builder_id = str(job)
        else:
            raise ValueError("'job' must be an instance of BuildJob or the UUID of the builder")

        if(builder_id in self.jobs):
            del self.jobs[builder_id]
