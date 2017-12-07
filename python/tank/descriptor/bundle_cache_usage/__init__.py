from ... import LogManager
from ...util import LocalFileStorageManager

DEBUG = True
DEBUG2 = True
USE_PRINT = False
USE_PYDEV = False

if not USE_PRINT:
    bundle_cache_usage_logger = LogManager.get_logger(__name__)

if USE_PYDEV:
    import sys
    sys.path.append("/Applications/PyCharm.app/Contents/debug-eggs/pycharm-debug.egg")
    import pydevd
    pydevd.settrace('localhost', port=7720, suspend=False)

class BundleCacheUsageLogger(object):

    @classmethod
    def debug(cls, message):
        if DEBUG:
            s = "NICOLAS: " + message
            if USE_PRINT: print(s)
            else: bundle_cache_usage_logger.debug(s)

    @classmethod
    def debug2(cls, message):
        if DEBUG2:
            s = "NICOLAS: " + message
            if USE_PRINT: print(s)
            else: bundle_cache_usage_logger.debug(s)

    @classmethod
    def error(cls, message):
        pass

    @classmethod
    def exception(cls, exception):
        pass

    @classmethod
    def info(cls, message):
        pass

#import sys
#sys.path.append("/Applications/PyCharm.app/Contents/debug-eggs/pycharm-debug.egg")
#import pydevd
#pydevd.settrace('localhost', port=7720, suspend=False)

from worker import BundleCacheUsageWorker

bundle_cache_root = LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE)
bundle_cache_usage_srv = BundleCacheUsageWorker(bundle_cache_root)
bundle_cache_usage_logger.debug("NICOLAS: bundle_cache_root=%s" % (bundle_cache_root))

bundle_cache_usage_srv.start()
