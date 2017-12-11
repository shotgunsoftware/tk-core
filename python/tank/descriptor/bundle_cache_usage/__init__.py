from ... import LogManager
from ...util import LocalFileStorageManager

# Runtime options
USE_RELATIVE_PATH = False

# Debugging options
USE_PYDEVD = False
PYDEVD_INITIATED = False

# Debug logging options
DEBUG = False # master switch

USE_PRINT = True
LOG_GET_PATH = False
LOG_LOG_USAGE = False
LOG_THREADING = True
LOG_DESCRIPTOR_TYPE = False

# Worker class debug controls
LOG_WORKER = True
LOG_WORKER_HF = False
LOG_WORKER_THREADING = True

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
            s = "NICOLAS: " + message
            if USE_PRINT:
                print(s)
            else:
                bundle_cache_usage_logger.debug(s)

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
