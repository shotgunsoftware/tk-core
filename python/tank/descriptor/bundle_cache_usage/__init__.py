from ... import LogManager

# Debugging options
USE_PYDEVD_PYCHARM = False
USE_PYDEVD_LICLIPSE = False
PYDEVD_INITIATED = False

LOG_GET_PATH = False
LOG_LOG_USAGE = False
LOG_DESCRIPTOR_TYPE = False

bundle_cache_usage_logger = LogManager.get_logger(__name__)

if USE_PYDEVD_PYCHARM:
    if not PYDEVD_INITIATED:
        import sys
        sys.path.append("/Applications/PyCharm.app/Contents/debug-eggs/pycharm-debug.egg")
        import pydevd
        pydevd.settrace('localhost', port=7720, stdoutToServer=True, stderrToServer=True, suspend=True)
        PYDEVD_INITIATED = True

if USE_PYDEVD_LICLIPSE:
    if not PYDEVD_INITIATED:
        import sys
        sys.path.append("/Applications/LiClipse.app/Contents/Eclipse/plugins/org.python.pydev_6.2.0.201711281546/pysrc")
        import pydevd
        pydevd.settrace('localhost', port=5678, suspend=True, stdoutToServer=True, stderrToServer=True)
        PYDEVD_INITIATED = True


class BundleCacheUsageMyLogger(object):

    # Debug logging options
    DEBUG = False  # master switch

    USE_PRINT = True

    LOG_THREADING = True

    # Manager class debug controls
    LOG_MANAGER = True

    # Worker class debug controls
    LOG_WORKER = True
    LOG_WORKER_HF = True
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


