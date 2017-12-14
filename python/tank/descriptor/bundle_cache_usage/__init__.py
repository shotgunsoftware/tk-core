from ... import LogManager
from ...util import LocalFileStorageManager

# Debugging options
USE_PYDEVD = False
PYDEVD_INITIATED = False

# Debug logging options
DEBUG = False # master switch

USE_PRINT = False
LOG_GET_PATH = False
LOG_LOG_USAGE = False
LOG_THREADING = False
LOG_DESCRIPTOR_TYPE = False

# Worker class debug controls
LOG_WORKER = False
LOG_WORKER_HF = False
LOG_WORKER_THREADING = False

# Manager class debug controls
LOG_MANAGER = False

bundle_cache_usage_logger = LogManager.get_logger(__name__)

if USE_PYDEVD:
    if not PYDEVD_INITIATED:
        import sys
        sys.path.append("/Applications/PyCharm.app/Contents/debug-eggs/pycharm-debug.egg")
        import pydevd
        pydevd.settrace('localhost', port=7720, stdoutToServer=True, stderrToServer=True, suspend=True)
        PYDEVD_INITIATED = True

class BundleCacheUsageLogger(object):

    @classmethod
    def _debug(cls, message):
        if DEBUG:
            if USE_PRINT:
                print(message)
            else:
                bundle_cache_usage_logger.debug("NICOLAS: " + message)

    @classmethod
    def debug_db(cls, message):
        cls._debug(message)

    @classmethod
    def debug_db_inst(cls, message):
        cls._debug(message)

    @classmethod
    def debug_db_delete(cls, message):
        cls._debug(message)

    @classmethod
    def debug_db_hf(cls, message):
        cls._debug(message)

    @classmethod
    def debug_worker(cls, message):
        if LOG_WORKER:
            cls._debug(message)

    @classmethod
    def debug_worker_hf(cls, message):
        """ Log high frequency events """
        if LOG_WORKER_HF:
            cls._debug(message)

    @classmethod
    def debug_manager(cls, message):
        if LOG_MANAGER:
            ls._debug(message)

    @classmethod
    def debug_worker_threading(cls, message):
        if LOG_WORKER_THREADING:
            cls._debug("worker thread " + message)

    @classmethod
    def debug(cls, message):
        if DEBUG:
            cls._debug(message)

    @classmethod
    def error(cls, message):
        if DEBUG:
            cls._debug(message)

    @classmethod
    def exception(cls, exception):
        pass

    @classmethod
    def info(cls, message):
        pass


from manager import BundleCacheManager
import os

# TODO: Where should this be???
bundle_cache_root = os.path.join(
    LocalFileStorageManager.get_global_root(LocalFileStorageManager.CACHE),
    "bundle_cache"
)
bundle_cache_usage_mgr = BundleCacheManager(bundle_cache_root)
disable_tracking = True if os.environ.get('TK_BUNDLE_USAGE_TRACKING_DISABLE', None) else False
if disable_tracking:
    bundle_cache_usage_logger.info("TK_BUNDLE_USAGE_TRACKING_DISABLE true, bundle usage tracking disabled.")
else:
    # Check whether database is populated at all
    if bundle_cache_usage_mgr.get_bundle_count() == 0:
        bundle_cache_usage_logger.info("Bundle cache database is empty.")
        bundle_cache_usage_mgr.initial_populate()

