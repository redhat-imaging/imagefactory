
# Callable class that is used to launch a thread
import threading
import time
import logging
import httplib2
import json
import re
import base64

class CallbackWorker():

    def __init__(self, callback_url):
        # callback_url - the URL to which we will send the full object JSON for each STATUS update
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))        
        self.callback_queue = [ ]
        self.queue_lock = threading.BoundedSemaphore()
        self.queue_not_empty = threading.Event()
        self.httplib = httplib2.Http()
        # TODO: A more flexible approach than simply supporting basic auth embedded in the URL
        url_regex = r"^(\w*://)([^:/]+)(:)([^:/]+)(@)(.*)$"
        sr = re.search(url_regex, callback_url)
        if sr:
            self.callback_url = sr.group(1) + sr.group(6)
            auth = base64.encodestring( sr.group(2) + ':' + sr.group(4) )
            self.headers = {'content-type':'application/json', 'Authorization' : 'Basic ' + auth}
        else:
            self.callback_url = callback_url
            self.headers = {'content-type':'application/json'}
        self.shutdown = False

    def start(self):
        self.thread = threading.Thread(target=self)
        self.thread.start()
        return self.thread

    def shut_down(self, blocking=False):
        # At this point the caller has promised us that they will not enqueue anything else
        self.shutdown = True
        self.queue_lock.acquire()
        ### QUEUE LOCK ###
        # The queue cannot grow at this point
        # The worker thread at this point can be:
        # 1) Sleeping due to empty 
        # 2) Woken up but not yet acquired lock in _get_next_callback()
        # 3) Woken up and past QUEUE LOCK in _get_next_callback() (including remainder of main loop)
        #
        # We wish to avoid a situation where the worker thread lingers forever because it is sleeping
        # on an empty queue
        # In case 2 the queue may end up empty but that will be caught in the main loop
        # In case 3 the queue may already be empty but this _should_ always be caught by the main loop
        # Case 1 is only possible if the queue is already empty (I think)
        # So, here we check if the queue is empty and, if it is, we inaccurately set queue_not_empty
        # to wake up the worker thread.  _get_next_thing will detect this and fall through to the 
        # bottom of the main loop which will, in turn, break out and exit
        if len(self.callback_queue) == 0:
            self.queue_not_empty.set()
        self.queue_lock.release()
        if blocking:
            self.thread.join()

    def status_notifier(self, notification):
        image = notification.sender
        _type = type(image).__name__
        typemap = {"TargetImage": "target_image", "ProviderImage": "provider_image", "BaseImage": "base_image" }
        if not _type in typemap:
            raise Exception("Unmappable object type: %s" % _type)
        callback_body = { typemap[_type]: {'_type':_type,
                         'id':image.identifier} }
#                         'href':request.url}
        for key in image.metadata():
            if key not in ('identifier', 'data', 'base_image_id', 'target_image_id'):
                callback_body[typemap[_type]][key] = getattr(image, key, None)
        self._enqueue(callback_body)

    def _enqueue(self, status_update):
        # This is, in short, a request to enqueue a task
        if self.shutdown:
            raise Exception("Attempt made to add work to a terminating worker thread")
        self.queue_lock.acquire()
        ### QUEUE LOCK ###
        self.callback_queue.append(status_update)
        self.queue_not_empty.set()
        ### END QUEUE LOCK ###
        self.queue_lock.release()

    def _wait_for_callback(self):
        # Called at the start of the main loop if the queue is empty
        # self.queue_not_empty is set anytime an item is added to the queue
        # or if the shutdown method is called on an empty queue (which prevents us
        # waiting here forever)
        self.log.debug("Entering blocking non-empty queue call")
        self.queue_not_empty.wait()
        self.log.debug("Leaving blocking non-empty queue call")

    def _get_next_callback(self):
        self.queue_lock.acquire()
        ### QUEUE LOCK ###
        if len(self.callback_queue) == 0:
            # Can potentially happen if worker is shutdown without doing anything
            self.queue_lock.release()
            return None
        next_callback = self.callback_queue.pop(0)
        if len(self.callback_queue) == 0:
            self.queue_not_empty.clear()
        ### END QUEUE LOCK ###
        self.queue_lock.release()
        return next_callback

    def _do_next_callback(self):
        self._wait_for_callback()
        next_callback = self._get_next_callback()
        if next_callback:
            self.log.debug("Updated image is: (%s)" % (str(next_callback)))
            if self.callback_url == "debug":
                self.log.debug("Executing a debug callback - sleeping 5 seconds - no actual PUT sent")
                time.sleep(5)
            else:
                self.log.debug("PUTing update to URL (%s)" % (self.callback_url))
                try:
                    resp, content = self.httplib.request(self.callback_url, 
                                                         "PUT", body=json.dumps(next_callback), 
                                                         headers=self.headers )
                except Exception, e:
                    # We treat essentially every potential error here as non-fatal and simply move on to the next update
                    # TODO: Configurable retries?
                    self.log.debug("Caught exception (%s) when attempting to PUT callback - Ignoring" % (str(e)))

    def __call__(self):
        while True:
            self._do_next_callback()
            if self.shutdown and len(self.callback_queue) == 0:
                break
    
    

