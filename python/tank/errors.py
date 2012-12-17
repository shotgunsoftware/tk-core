"""
Copyright (c) 2012 Shotgun Software, Inc
----------------------------------------------------

All custom exceptions that Tank emits are defined here.

"""


class TankError(Exception):
    """
    Exception that indicates an error has occurred.
    """
    pass

class TankEngineInitError(TankError):
    """
    Exception that indicates that an engine could not start up 
    """
    pass