"""
 -----------------------------------------------------------------------------
 Copyright (c) 2009-2024, Shotgun Software Inc.

 Redistribution and use in source and binary forms, with or without
 modification, are permitted provided that the following conditions are met:

  - Redistributions of source code must retain the above copyright notice, this
    list of conditions and the following disclaimer.

  - Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions and the following disclaimer in the documentation
    and/or other materials provided with the distribution.

  - Neither the name of the Shotgun Software Inc nor the names of its
    contributors may be used to endorse or promote products derived from this
    software without specific prior written permission.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import warnings
warnings.warn(
    "The 'sgutils' module, including the 'ensure_binary', 'ensure_str', "
    "and 'ensure_text' methods, is deprecated in FPTR and will be removed by "
    "the end of March 2026. "
    "Use the built-in str.encode() and/or bytes.decode() methods instead "
    "according to the expected data type.",
    DeprecationWarning,
    stacklevel=2,
)

def ensure_binary(s, encoding="utf-8", errors="strict"):
    """
    Coerce **s** to bytes.

      - `str` -> encoded to `bytes`
      - `bytes` -> `bytes`
    """
    warnings.warn(
        "The 'sgutils.ensure_binary' method is deprecated and will be "
        "removed by the end of March 2026.",
        DeprecationWarning,
        stacklevel=2,
    )

    if isinstance(s, str):
        return s.encode(encoding, errors)
    elif isinstance(s, bytes):
        return s
    else:
        raise TypeError(f"not expecting type '{type(s)}'")


def ensure_str(s, encoding="utf-8", errors="strict"):
    """Coerce *s* to `str`.

    - `str` -> `str`
    - `bytes` -> decoded to `str`
    """
    warnings.warn(
        "The 'sgutils.ensure_str' method is deprecated and will be "
        "removed by the end of March 2026.",
        DeprecationWarning,
        stacklevel=2,
    )

    if isinstance(s, str):
        return s

    elif isinstance(s, bytes):
        return s.decode(encoding, errors)

    raise TypeError(f"not expecting type '{type(s)}'")


# Alias for the deprecated `ensure_str` function, maintained for compatibility.
def ensure_text(*args, **kwargs):
    """
    Alias for the deprecated `ensure_str` function.
    This function is also deprecated and will be removed in a future version.
    """
    warnings.warn(
        "The 'sgutils.ensure_text' method is deprecated and will be "
        "removed by the end of March 2026.",
        DeprecationWarning,
        stacklevel=2,
    )

    return ensure_str(*args, **kwargs)
