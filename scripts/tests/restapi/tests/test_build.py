# loads tests config and utilities
import utils

# actual tests code
import os
import Queue
import threading

base_built = {}
base_lock = threading.RLock()

target_built = {}
target_lock = threading.RLock()

provider_built = {}
provider_lock = threading.RLock()

def _assert_base_complete(tdlfile):
  imageid, imagestatus = base_built.get(tdlfile)
  assert imagestatus == 'COMPLETE'

def _build_base_from_queue(queue):
  global base_built
  while True:
    tdlfile = queue.get()
    template = open(tdlfile, 'r').read()
    imagejson = utils.build_base(template)
    imageid = imagejson['id']
    imagestatus = utils.wait_until_base_completes(imageid)
    with base_lock:
      base_built[tdlfile] = (imageid, imagestatus)
    queue.task_done()

def test_base_build():
  queue = Queue.Queue()
  for tdlfile in utils.TEMPLATE_FILES:
    queue.put(tdlfile)
  for i in range(utils.MAX_THREADS):
    t = threading.Thread(target=_build_base_from_queue, args=(queue,))
    t.daemon = True
    t.start()
  queue.join()
  for tdlfile in utils.TEMPLATE_FILES:
    yield _assert_base_complete, tdlfile

def _assert_target_complete(tdlfile, target_provider):
  imageid, imagestatus = target_built.get((tdlfile, target_provider))
  assert imagestatus == 'COMPLETE'

def _build_target_from_queue(queue):
  global target_built
  while True:
    tdlfile, target_provider = queue.get()
    template = open(tdlfile, 'r').read()
    imagejson = utils.build_target(template, target_provider)
    imageid = imagejson['id']
    imagestatus = utils.wait_until_target_completes(imageid)
    with target_lock:
      target_built[(tdlfile, target_provider)] = (imageid, imagestatus)
    queue.task_done()

def test_target_build():
  queue = Queue.Queue()
  for tdlfile in utils.TEMPLATE_FILES:
    for target_provider in utils.TARGETS:
      queue.put((tdlfile, target_provider))
  for i in range(utils.MAX_THREADS):
    t = threading.Thread(target=_build_target_from_queue, args=(queue,))
    t.daemon = True
    t.start()
  queue.join()
  for tdlfile in utils.TEMPLATE_FILES:
    for target_provider in utils.TARGETS:
      yield _assert_target_complete, tdlfile, target_provider

def _assert_provider_complete(tdlfile, target_provider):
  imageid, imagestatus = provider_built.get((tdlfile, target_provider))
  assert imagestatus == 'COMPLETE'

def _build_provider_from_queue(queue):
  global provider_built
  while True:
    tdlfile, provider = queue.get()
    template = open(tdlfile, 'r').read()
    provider_definition = open(utils.PROVIDERS_FILE_PATH+provider+'.json', 'r').read()
    provider_credentials = open(utils.PROVIDERS_FILE_PATH+provider+'_credentials.xml', 'r').read()
    imagejson = utils.build_provider(template, provider, provider_definition.strip(), provider_credentials)
    imageid = imagejson['id']
    imagestatus = utils.wait_until_provider_completes(imageid)
    with provider_lock:
      provider_built[(tdlfile, provider)] = (imageid, imagestatus)
    queue.task_done()

def test_provider_build():
  queue = Queue.Queue()
  for tdlfile in utils.TEMPLATE_FILES:
    for provider in utils.PROVIDERS:
      queue.put((tdlfile, provider))
  for i in range(utils.MAX_THREADS):
    t = threading.Thread(target=_build_provider_from_queue, args=(queue,))
    t.daemon = True
    t.start()
  queue.join()
  for tdlfile in utils.TEMPLATE_FILES:
    for provider in utils.PROVIDERS:
      yield _assert_provider_complete, tdlfile, provider

def _assert_target_content_installed(target_provider, imageid):
  expectedpkgs = utils.list_expected_packages(target_provider)
  imagepkgs = utils.list_installed_packages(imageid)
  for pkg in expectedpkgs:
    assert pkg in imagepkgs

def test_target_content():
  if utils.IMGFAC_URL.find("localhost") >= 0 and os.path.isfile(utils.IMGFAC_TCXML) and os.path.isfile(utils.IMGFAC_CONF):
    for target_imageid, target_imagestatus in target_built.itervalues():
      if target_imagestatus == 'COMPLETE':
        imagejson = utils.get_target(target_imageid)
        yield _assert_target_content_installed, imagejson['target'], target_imageid
  else:
    print "Skipping target images inspection: imgfac is not running locally? target_content.xml missing? imagefactory.conf misplaced?"
