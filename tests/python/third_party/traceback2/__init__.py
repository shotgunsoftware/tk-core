"""Extract, format and print information about Python stack traces."""

import sys
import operator

import linecache2 as linecache
from six import u, PY2

__all__ = ['extract_stack', 'extract_tb', 'format_exception',
           'format_exception_only', 'format_list', 'format_stack',
           'format_tb', 'print_exc', 'format_exc', 'print_exception',
           'print_last', 'print_stack', 'print_tb',
           'clear_frames']

#
# Formatting and printing lists of traceback lines.
#

def print_list(extracted_list, file=None):
    """Print the list of tuples as returned by extract_tb() or
    extract_stack() as a formatted stack trace to the given file."""
    if file is None:
        file = sys.stderr
    for item in StackSummary.from_list(extracted_list).format():
        file.write(item)

def format_list(extracted_list):
    """Format a list of traceback entry tuples for printing.

    Given a list of tuples as returned by extract_tb() or
    extract_stack(), return a list of strings ready for printing.
    Each string in the resulting list corresponds to the item with the
    same index in the argument list.  Each string ends in a newline;
    the strings may contain internal newlines as well, for those items
    whose source text line is not None.
    """
    return StackSummary.from_list(extracted_list).format()

#
# Printing and Extracting Tracebacks.
#

def print_tb(tb, limit=None, file=None):
    """Print up to 'limit' stack trace entries from the traceback 'tb'.

    If 'limit' is omitted or None, all entries are printed.  If 'file'
    is omitted or None, the output goes to sys.stderr; otherwise
    'file' should be an open file or file-like object with a write()
    method.
    """
    print_list(extract_tb(tb, limit=limit), file=file)

def format_tb(tb, limit=None):
    """A shorthand for 'format_list(extract_tb(tb, limit))'."""
    return extract_tb(tb, limit=limit).format()

def extract_tb(tb, limit=None):
    """Return list of up to limit pre-processed entries from traceback.

    This is useful for alternate formatting of stack traces.  If
    'limit' is omitted or None, all entries are extracted.  A
    pre-processed stack trace entry is a quadruple (filename, line
    number, function name, text) representing the information that is
    usually printed for a stack trace.  The text is a string with
    leading and trailing whitespace stripped; if the source is not
    available it is None.
    """
    return StackSummary.extract(walk_tb(tb), limit=limit)

#
# Exception formatting and output.
#

_cause_message = (
    "\nThe above exception was the direct cause "
    "of the following exception:\n\n")

_context_message = (
    "\nDuring handling of the above exception, "
    "another exception occurred:\n\n")


def print_exception(etype, value, tb, limit=None, file=None, chain=True):
    """Print exception up to 'limit' stack trace entries from 'tb' to 'file'.

    This differs from print_tb() in the following ways: (1) if
    traceback is not None, it prints a header "Traceback (most recent
    call last):"; (2) it prints the exception type and value after the
    stack trace; (3) if type is SyntaxError and value has the
    appropriate format, it prints the line where the syntax error
    occurred with a caret on the next line indicating the approximate
    position of the error.
    """
    # format_exception has ignored etype for some time, and code such as cgitb
    # passes in bogus values as a result. For compatibility with such code we
    # ignore it here (rather than in the new TracebackException API).
    if file is None:
        file = sys.stderr
    for line in TracebackException(
            type(value), value, tb, limit=limit).format(chain=chain):
        file.write(line)


def format_exception(etype, value, tb, limit=None, chain=True):
    """Format a stack trace and the exception information.

    The arguments have the same meaning as the corresponding arguments
    to print_exception().  The return value is a list of strings, each
    ending in a newline and some containing internal newlines.  When
    these lines are concatenated and printed, exactly the same text is
    printed as does print_exception().
    """
    # format_exception has ignored etype for some time, and code such as cgitb
    # passes in bogus values as a result. For compatibility with such code we
    # ignore it here (rather than in the new TracebackException API).
    return list(TracebackException(
        type(value), value, tb, limit=limit).format(chain=chain))


def format_exception_only(etype, value):
    """Format the exception part of a traceback.

    The arguments are the exception type and value such as given by
    sys.last_type and sys.last_value. The return value is a list of
    strings, each ending in a newline.

    Normally, the list contains a single string; however, for
    SyntaxError exceptions, it contains several lines that (when
    printed) display detailed information about where the syntax
    error occurred.

    The message indicating which exception occurred is always the last
    string in the list.

    """
    return list(TracebackException(etype, value, None).format_exception_only())


# -- not offical API but folk probably use these two functions.

def _format_final_exc_line(etype, value):
    valuestr = _some_str(value)
    if value == 'None' or value is None or not valuestr:
        line = u("%s\n") % etype
    else:
        line = u("%s: %s\n") % (etype, valuestr)
    return line

def _some_str(value):
    try:
        if PY2:
            # If there is a working __unicode__, great.
            # Otherwise see if we can get a bytestring...
            # Otherwise we fallback to unprintable.
            try:
                return unicode(value)
            except:
                return "b%s" % repr(str(value))
        else:
            # For Python3, bytestrings don't implicit decode, so its trivial.
            return str(value)
    except:
        return '<unprintable %s object>' % type(value).__name__

# --

def _some_fs_str(value):
    """_some_str, but for filesystem paths."""
    if value is None:
        return None
    try:
        if type(value) is bytes:
            return value.decode(sys.getfilesystemencoding())
    except:
        pass
    return _some_str(value)


def print_exc(limit=None, file=None, chain=True):
    """Shorthand for 'print_exception(*sys.exc_info(), limit, file)'."""
    print_exception(*sys.exc_info(), limit=limit, file=file, chain=chain)

def format_exc(limit=None, chain=True):
    """Like print_exc() but return a string."""
    return "".join(format_exception(*sys.exc_info(), limit=limit, chain=chain))

def print_last(limit=None, file=None, chain=True):
    """This is a shorthand for 'print_exception(sys.last_type,
    sys.last_value, sys.last_traceback, limit, file)'."""
    if not hasattr(sys, "last_type"):
        raise ValueError("no last exception")
    print_exception(sys.last_type, sys.last_value, sys.last_traceback,
                    limit, file, chain)

#
# Printing and Extracting Stacks.
#

def print_stack(f=None, limit=None, file=None):
    """Print a stack trace from its invocation point.

    The optional 'f' argument can be used to specify an alternate
    stack frame at which to start. The optional 'limit' and 'file'
    arguments have the same meaning as for print_exception().
    """
    print_list(extract_stack(f, limit=limit), file=file)


def format_stack(f=None, limit=None):
    """Shorthand for 'format_list(extract_stack(f, limit))'."""
    return format_list(extract_stack(f, limit=limit))


def extract_stack(f=None, limit=None):
    """Extract the raw traceback from the current stack frame.

    The return value has the same format as for extract_tb().  The
    optional 'f' and 'limit' arguments have the same meaning as for
    print_stack().  Each item in the list is a quadruple (filename,
    line number, function name, text), and the entries are in order
    from oldest to newest stack frame.
    """
    stack = StackSummary.extract(walk_stack(f), limit=limit)
    stack.reverse()
    return stack


_identity = lambda:None
def clear_frames(tb):
    "Clear all references to local variables in the frames of a traceback."
    while tb is not None:
        try:
            getattr(tb.tb_frame, 'clear', _identity)()
        except RuntimeError:
            # Ignore the exception raised if the frame is still executing.
            pass
        tb = tb.tb_next


class FrameSummary:
    """A single frame from a traceback.

    - :attr:`filename` The filename for the frame.
    - :attr:`lineno` The line within filename for the frame that was
      active when the frame was captured.
    - :attr:`name` The name of the function or method that was executing
      when the frame was captured.
    - :attr:`line` The text from the linecache module for the
      of code that was running when the frame was captured.
    - :attr:`locals` Either None if locals were not supplied, or a dict
      mapping the name to the repr() of the variable.
    """

    __slots__ = ('filename', 'lineno', 'name', '_line', 'locals')

    def __init__(self, filename, lineno, name, lookup_line=True,
            locals=None, line=None):
        """Construct a FrameSummary.

        :param lookup_line: If True, `linecache` is consulted for the source
            code line. Otherwise, the line will be looked up when first needed.
        :param locals: If supplied the frame locals, which will be captured as
            object representations.
        :param line: If provided, use this instead of looking up the line in
            the linecache.
        """
        self.filename = filename
        self.lineno = lineno
        self.name = name
        self._line = line
        if lookup_line:
            self.line
        self.locals = \
            dict((k, repr(v)) for k, v in locals.items()) if locals else None

    def __eq__(self, other):
        return (self.filename == other.filename and
                self.lineno == other.lineno and
                self.name == other.name and
                self.locals == other.locals)

    def __getitem__(self, pos):
        return (self.filename, self.lineno, self.name, self.line)[pos]

    def __iter__(self):
        return iter([self.filename, self.lineno, self.name, self.line])

    def __repr__(self):
        return "<FrameSummary file {filename}, line {lineno} in {name}>".format(
            filename=self.filename, lineno=self.lineno, name=self.name)

    @property
    def line(self):
        if self._line is None:
            self._line = linecache.getline(self.filename, self.lineno).strip()
        return self._line


def walk_stack(f):
    """Walk a stack yielding the frame and line number for each frame.

    This will follow f.f_back from the given frame. If no frame is given, the
    current stack is used. Usually used with StackSummary.extract.
    """
    if f is None:
        f = sys._getframe().f_back.f_back
    while f is not None:
        yield f, f.f_lineno
        f = f.f_back


def walk_tb(tb):
    """Walk a traceback yielding the frame and line number for each frame.

    This will follow tb.tb_next (and thus is in the opposite order to
    walk_stack). Usually used with StackSummary.extract.
    """
    while tb is not None:
        yield tb.tb_frame, tb.tb_lineno
        tb = tb.tb_next


class StackSummary(list):
    """A stack of frames."""

    @classmethod
    def extract(klass, frame_gen, limit=None, lookup_lines=True,
            capture_locals=False):
        """Create a StackSummary from a traceback or stack object.

        :param frame_gen: A generator that yields (frame, lineno) tuples to
            include in the stack.
        :param limit: None to include all frames or the number of frames to
            include.
        :param lookup_lines: If True, lookup lines for each frame immediately,
            otherwise lookup is deferred until the frame is rendered.
        :param capture_locals: If True, the local variables from each frame will
            be captured as object representations into the FrameSummary.
        """
        if limit is None:
            limit = getattr(sys, 'tracebacklimit', None)

        result = klass()
        fnames = set()
        for pos, (f, lineno) in enumerate(frame_gen):
            if limit is not None and pos >= limit:
                break
            co = f.f_code
            filename = co.co_filename
            name = co.co_name

            fnames.add(filename)
            linecache.lazycache(filename, f.f_globals)
            # Must defer line lookups until we have called checkcache.
            if capture_locals:
                f_locals = f.f_locals
            else:
                f_locals = None
            result.append(FrameSummary(
                filename, lineno, name, lookup_line=False, locals=f_locals))
        for filename in fnames:
            linecache.checkcache(filename)
        # If immediate lookup was desired, trigger lookups now.
        if lookup_lines:
            for f in result:
                f.line
        return result

    @classmethod
    def from_list(klass, a_list):
        """Create a StackSummary from a simple list of tuples.

        This method supports the older Python API. Each tuple should be a
        4-tuple with (filename, lineno, name, line) elements.
        """
        if isinstance(a_list, StackSummary):
            return StackSummary(a_list)
        result = StackSummary()
        for filename, lineno, name, line in a_list:
            result.append(FrameSummary(filename, lineno, name, line=line))
        return result

    def format(self):
        """Format the stack ready for printing.

        Returns a list of strings ready for printing.  Each string in the
        resulting list corresponds to a single frame from the stack.
        Each string ends in a newline; the strings may contain internal
        newlines as well, for those items with source text lines.
        """
        result = []
        for frame in self:
            row = []
            row.append(u('  File "{0}", line {1}, in {2}\n').format(
                _some_fs_str(frame.filename), frame.lineno, frame.name))
            if frame.line:
                row.append(u('    {0}\n').format(frame.line.strip()))
            if frame.locals:
                for name, value in sorted(frame.locals.items()):
                    row.append(u('    {name} = {value}\n').format(name=name, value=value))
            result.append(u('').join(row))
        return result


class TracebackException:
    """An exception ready for rendering.

    The traceback module captures enough attributes from the original exception
    to this intermediary form to ensure that no references are held, while
    still being able to fully print or format it.

    Use `from_exception` to create TracebackException instances from exception
    objects, or the constructor to create TracebackException instances from
    individual components.

    - :attr:`__cause__` A TracebackException of the original *__cause__*.
    - :attr:`__context__` A TracebackException of the original *__context__*.
    - :attr:`__suppress_context__` The *__suppress_context__* value from the
      original exception.
    - :attr:`stack` A `StackSummary` representing the traceback.
    - :attr:`exc_type` The class of the original traceback.
    - :attr:`filename` For syntax errors - the filename where the error
      occured.
    - :attr:`lineno` For syntax errors - the linenumber where the error
      occured.
    - :attr:`text` For syntax errors - the text where the error
      occured.
    - :attr:`offset` For syntax errors - the offset into the text where the
      error occured.
    - :attr:`msg` For syntax errors - the compiler error message.
    """

    def __init__(self, exc_type, exc_value, exc_traceback, limit=None,
            lookup_lines=True, capture_locals=False, _seen=None):
        # NB: we need to accept exc_traceback, exc_value, exc_traceback to
        # permit backwards compat with the existing API, otherwise we
        # need stub thunk objects just to glue it together.
        # Handle loops in __cause__ or __context__.
        if _seen is None:
            _seen = set()
        _seen.add(exc_value)
        # Gracefully handle (the way Python 2.4 and earlier did) the case of
        # being called with no type or value (None, None, None).
        if (exc_value and getattr(exc_value, '__cause__', None) is not None
            and exc_value.__cause__ not in _seen):
            cause = TracebackException(
                type(exc_value.__cause__),
                exc_value.__cause__,
                exc_value.__cause__.__traceback__,
                limit=limit,
                lookup_lines=False,
                capture_locals=capture_locals,
                _seen=_seen)
        else:
            cause = None
        if (exc_value and getattr(exc_value, '__context__', None) is not None
            and exc_value.__context__ not in _seen):
            context = TracebackException(
                type(exc_value.__context__),
                exc_value.__context__,
                exc_value.__context__.__traceback__,
                limit=limit,
                lookup_lines=False,
                capture_locals=capture_locals,
                _seen=_seen)
        else:
            context = None
        self.__cause__ = cause
        self.__context__ = context
        self.__suppress_context__ = \
            getattr(exc_value, '__suppress_context__', False) if exc_value else False
        # TODO: locals.
        self.stack = StackSummary.extract(
            walk_tb(exc_traceback), limit=limit, lookup_lines=lookup_lines,
            capture_locals=capture_locals)
        self.exc_type = exc_type
        # Capture now to permit freeing resources: only complication is in the
        # unofficial API _format_final_exc_line
        self._str = _some_str(exc_value)
        if exc_type and issubclass(exc_type, SyntaxError):
            # Handle SyntaxError's specially
            self.filename = exc_value.filename
            self.lineno = str(exc_value.lineno)
            self.text = exc_value.text
            self.offset = exc_value.offset
            self.msg = exc_value.msg
        if lookup_lines:
            self._load_lines()

    @classmethod
    def from_exception(self, exc, *args, **kwargs):
        """Create a TracebackException from an exception.
        
        Only useful in Python 3 specific code.
        """
        return TracebackException(
            type(exc), exc, exc.__traceback__, *args, **kwargs)

    def _load_lines(self):
        """Private API. force all lines in the stack to be loaded."""
        for frame in self.stack:
            frame.line
        if self.__context__:
            self.__context__._load_lines()
        if self.__cause__:
            self.__cause__._load_lines()

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __str__(self):
        return self._str

    def format_exception_only(self):
        """Format the exception part of the traceback.

        The return value is a generator of strings, each ending in a newline.

        Normally, the generator emits a single string; however, for
        SyntaxError exceptions, it emites several lines that (when
        printed) display detailed information about where the syntax
        error occurred.

        The message indicating which exception occurred is always the last
        string in the output.
        """
        if self.exc_type is None:
            yield _format_final_exc_line(None, self._str)
            return

        stype = getattr(self.exc_type, '__qualname__', self.exc_type.__name__)
        smod = u(self.exc_type.__module__)
        if smod not in ("__main__", "builtins", "exceptions"):
            stype = smod + u('.') + stype

        if not issubclass(self.exc_type, SyntaxError):
            yield _format_final_exc_line(stype, self._str)
            return

        # It was a syntax error; show exactly where the problem was found.
        filename = _some_fs_str(self.filename) or u("<string>")
        lineno = str(self.lineno) or u('?')
        yield u('  File "{0}", line {1}\n').format(filename, lineno)

        badline = None
        if self.text is not None:
            if type(self.text) is bytes:
                # Not decoded - get the line via linecache which will decode
                # for us.
                if self.lineno:
                    badline = linecache.getline(filename, int(lineno))
                if not badline:
                    # But we can't for some reason, so fallback to attempting a
                    # u cast.
                    badline = u(self.text)
            else:
                badline = self.text
        offset = self.offset
        if badline is not None:
            yield u('    {0}\n').format(badline.strip())
            if offset is not None:
                caretspace = badline.rstrip('\n')
                offset = min(len(caretspace), offset) - 1
                caretspace = caretspace[:offset].lstrip()
                # non-space whitespace (likes tabs) must be kept for alignment
                caretspace = ((c.isspace() and c or ' ') for c in caretspace)
                yield u('    {0}^\n').format(''.join(caretspace))
        msg = self.msg or u("<no detail available>")
        yield u("{0}: {1}\n").format(stype, msg)

    def format(self, chain=True):
        """Format the exception.

        If chain is not *True*, *__cause__* and *__context__* will not be formatted.

        The return value is a generator of strings, each ending in a newline and
        some containing internal newlines. `print_exception` is a wrapper around
        this method which just prints the lines to a file.

        The message indicating which exception occurred is always the last
        string in the output.
        """
        if chain:
            if self.__cause__ is not None:
                for line in self.__cause__.format(chain=chain):
                    yield line
                yield _cause_message
            elif (self.__context__ is not None and
                not self.__suppress_context__):
                for line in self.__context__.format(chain=chain):
                    yield line
                yield _context_message
        yield u('Traceback (most recent call last):\n')
        for line in self.stack.format():
            yield line
        for line in self.format_exception_only():
            yield line
