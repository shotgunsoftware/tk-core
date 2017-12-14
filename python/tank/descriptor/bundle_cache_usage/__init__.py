from ... import LogManager
from ...util import LocalFileStorageManager

# Debugging options
USE_PYDEVD = False
PYDEVD_INITIATED = False

LOG_GET_PATH = False
LOG_LOG_USAGE = False
LOG_DESCRIPTOR_TYPE = False

bundle_cache_usage_logger = LogManager.get_logger(__name__)

if USE_PYDEVD:
    if not PYDEVD_INITIATED:
        import sys
        sys.path.append("/Applications/PyCharm.app/Contents/debug-eggs/pycharm-debug.egg")
        import pydevd
        pydevd.settrace('localhost', port=7720, stdoutToServer=True, stderrToServer=True, suspend=True)
        PYDEVD_INITIATED = True


class BundleCacheUsageLogger(object):

    # Debug logging options
    DEBUG = True  # master switch

    USE_PRINT = True

    LOG_THREADING = False

    # Manager class debug controls
    LOG_MANAGER = True

    # Worker class debug controls
    LOG_WORKER = True
    LOG_WORKER_HF = False
    LOG_WORKER_THREADING = True

    @classmethod
    def _debug(cls, message):
        if cls.DEBUG:
            if cls.USE_PRINT:
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
        if cls.LOG_WORKER:
            cls._debug(message)

    @classmethod
    def debug_worker_hf(cls, message):
        """ Log high frequency events """
        if cls.LOG_WORKER_HF:
            cls._debug(message)

    @classmethod
    def debug_manager(cls, message):
        if cls.LOG_MANAGER:
            cls._debug(message)

    @classmethod
    def debug_worker_threading(cls, message):
        if cls.LOG_WORKER_THREADING:
            cls._debug("worker thread " + message)

    @classmethod
    def debug(cls, message):
        if cls.DEBUG:
            cls._debug(message)

    @classmethod
    def error(cls, message):
        if cls.DEBUG:
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

#TODO: need execute 'initial_populate' as early as possible, hit of pipeline configuration
# is occuring earlier than bootstrap.apps_cache
# Check whether database is populated at all
if not bundle_cache_usage_mgr.get_bundle_count():
    bundle_cache_usage_logger.debug("Bundle cache usage database is empty.")
    bundle_cache_usage_mgr.initial_populate()

