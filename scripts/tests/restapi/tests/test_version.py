# loads tests config and utilities
import utils

# actual tests code
#import


def test_api_version():
  rootobject = utils.get_root()
  assert rootobject['api_version'] >= 2
