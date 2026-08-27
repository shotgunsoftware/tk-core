"""Local operations SDK for Autodesk Flow.

Subpackages:

- :mod:`adsk.flow.local.storage_manager` — uploads, downloads, and draft lifecycle
  (checkout → edit → publish).
"""

from . import storage_manager

__all__ = ["storage_manager"]
