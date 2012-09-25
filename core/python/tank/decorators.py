"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------
"""
import warnings
import functools

def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    
    based on http://wiki.python.org/moin/PythonDecoratorLibrary
    """
    @functools.wraps(func)
    def new_func(*args, **kwargs):
        warnings.warn_explicit(
            "Call to deprecated function %(funcname)s." % {
                'funcname': func.__name__,
            },
            category=DeprecationWarning,
            filename=func.func_code.co_filename,
            lineno=func.func_code.co_firstlineno + 1
        )
        return func(*args, **kwargs)
    return new_func

def deprecated_in_version(version):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    
    based on http://wiki.python.org/moin/PythonDecoratorLibrary
    """
    def wraps(func):
        @functools.wraps(func)
        def new_func(*args, **kws):
            msg = ("Call to deprecated function %s.This function will be removed in Tank version %s"
                    % (func.__name__, version))
            warnings.warn_explicit(msg,
                                   category=DeprecationWarning,
                                   filename=func.func_code.co_filename,
                                   lineno=func.func_code.co_firstlineno + 1)
            return func(*args, **kws)
        new_func.func_name = func.func_name
        return new_func
    return wraps

