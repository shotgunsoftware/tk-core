# # header
# coding: utf-8
# dd: 20241207

"""
this is a common setup.py for multiple packages, driven by the info in
__init__.py. If there is an issue with this in a particular package,
e.g. because of a change in Python, that issue might have been solved,
but not yet "percolated" into a new release of the package. (So don't
spent too much time debugging).
"""

# # __init__.py parser

import sys
import os
import datetime
from textwrap import dedent

sys.path = [path for path in sys.path if path not in [os.getcwd(), ""]]
import platform  # NOQA
import _ast as Ast  # NOQA
from ast import parse  # NOQA

from setuptools import setup, Extension, Distribution  # NOQA
from setuptools.command import install_lib  # NOQA
from setuptools.command.sdist import sdist as _sdist  # NOQA


if __name__ != '__main__':
    raise NotImplementedError('should never include setup.py')

# # definitions

full_package_name = None

open_kw = dict(encoding='utf-8')  # NOQA: C408

if os.environ.get('DVDEBUG', "") == "":

    def debug(*args, **kw):
        pass

else:

    def debug(*args, **kw):
        with open(os.environ['DVDEBUG'], 'a') as fp:
            kw1 = kw.copy()
            kw1['file'] = fp
            print('{:%Y-%d-%mT%H:%M:%S}'.format(datetime.datetime.now()), file=fp, end=' ')
            print(*args, **kw1)


# # default data

_setup_data = dict(
    supported=[(3, 9)],  # minimum non-EOL python
)


def literal_eval(node_or_string):
    """
    Safely evaluate an expression node or a string containing a Python
    expression.  The string or node provided may only consist of the following
    Python literal structures: strings, bytes, numbers, tuples, lists, dicts,
    sets, booleans, and None.

    Even when passing in Unicode, the resulting Str types parsed are 'str' in Python 2.
    I don't now how to set 'unicode_literals' on parse -> Str is explicitly converted.
    """
    if isinstance(node_or_string, str):
        node_or_string = parse(node_or_string, mode='eval')
    if isinstance(node_or_string, Ast.Expression):
        node_or_string = node_or_string.body
    else:
        raise TypeError('only string or AST nodes supported')

    def _convert(node):
        if isinstance(node, Ast.Constant):
            return node.value
        elif isinstance(node, Ast.Tuple):
            return tuple(map(_convert, node.elts))
        elif isinstance(node, Ast.List):
            return list(map(_convert, node.elts))
        elif isinstance(node, Ast.Set):
            return set(map(_convert, node.elts))
        elif isinstance(node, Ast.Dict):
            return {_convert(k): _convert(v) for k, v in zip(node.keys, node.values)}
        elif (
            isinstance(node, Ast.UnaryOp)
            and isinstance(node.op, (Ast.UAdd, Ast.USub))
            and isinstance(node.operand, (Ast.Num, Ast.UnaryOp, Ast.BinOp))
        ):  # NOQA
            operand = _convert(node.operand)
            if isinstance(node.op, Ast.UAdd):
                return +operand
            else:
                return -operand
        elif (
            isinstance(node, Ast.BinOp)
            and isinstance(node.op, (Ast.Add, Ast.Sub))
            and isinstance(node.right, (Ast.Num, Ast.UnaryOp, Ast.BinOp))
            and isinstance(node.left, (Ast.Num, Ast.UnaryOp, Ast.BinOp))
        ):  # NOQA
            left = _convert(node.left)
            right = _convert(node.right)
            if isinstance(node.op, Ast.Add):
                return left + right
            else:
                return left - right
        elif isinstance(node, Ast.Call):
            func_id = getattr(node.func, 'id', None)
            if func_id == 'dict':
                return {k.arg: _convert(k.value) for k in node.keywords}
            elif func_id == 'set':
                return set(_convert(node.args[0]))
            elif func_id == 'date':
                return datetime.date(*[_convert(k) for k in node.args])
            elif func_id == 'datetime':
                return datetime.datetime(*[_convert(k) for k in node.args])
        err = SyntaxError('malformed node or string: ' + repr(node))
        err.filename = '<string>'
        err.lineno = node.lineno
        err.offset = node.col_offset
        err.text = repr(node)
        err.node = node
        raise err

    return _convert(node_or_string)


# parses python ( "= dict( )" ) or ( "= {" )
def _package_data(fn):
    data = {}
    with open(fn, **open_kw) as fp:
        parsing = False
        lines = []
        for line in fp.readlines():
            if line.startswith('_package_data'):
                if 'dict(' in line:
                    parsing = 'python'
                    lines.append('dict(\n')
                elif line.endswith('= {\n'):
                    parsing = 'python'
                    lines.append('{\n')
                else:
                    raise NotImplementedError
                continue
            if not parsing:
                continue
            if parsing == 'python':
                if line.startswith(')') or line.startswith('}'):
                    lines.append(line)
                    try:
                        data = literal_eval("".join(lines))
                    except SyntaxError as e:
                        context = 2
                        from_line = e.lineno - (context + 1)
                        to_line = e.lineno + (context - 1)
                        w = len(str(to_line))
                        for index, line in enumerate(lines):
                            if from_line <= index <= to_line:
                                print(
                                    '{0:{1}}: {2}'.format(index, w, line).encode('utf-8'),
                                    end="",
                                )
                                if index == e.lineno - 1:
                                    print(
                                        '{0:{1}}  {2}^--- {3}'.format(
                                            ' ', w, ' ' * e.offset, e.node,
                                        ),
                                    )
                        raise
                    break
                lines.append(line)
            else:
                raise NotImplementedError
    return data


# make sure you can run "python ../some/dir/setup.py install"
pkg_data = _package_data(__file__.replace('setup.py', '__init__.py'))

exclude_files = ['setup.py']


# # helper
def _check_convert_version(tup):
    """Create a PEP 386 pseudo-format conformant string from tuple tup."""
    ret_val = str(tup[0])  # first is always digit
    next_sep = '.'  # separator for next extension, can be "" or "."
    nr_digits = 0  # nr of adjacent digits in rest, to verify
    post_dev = False  # are we processig post/dev
    for x in tup[1:]:
        if isinstance(x, int):
            nr_digits += 1
            if nr_digits > 2:
                raise ValueError('too many consecutive digits after ' + ret_val)
            ret_val += next_sep + str(x)
            next_sep = '.'
            continue
        first_letter = x[0].lower()
        next_sep = ""
        if first_letter in 'abcr':
            if post_dev:
                raise ValueError('release level specified after ' 'post/dev: ' + x)
            nr_digits = 0
            ret_val += 'rc' if first_letter == 'r' else first_letter
        elif first_letter in 'pd':
            nr_digits = 1  # only one can follow
            post_dev = True
            ret_val += '.post' if first_letter == 'p' else '.dev'
        else:
            raise ValueError('First letter of "' + x + '" not recognised')
    # .dev and .post need a number otherwise setuptools normalizes and complains
    if nr_digits == 1 and post_dev:
        ret_val += '0'
    return ret_val


version_info = pkg_data['version_info']
version_str = _check_convert_version(version_info)


class MyInstallLib(install_lib.install_lib):
    def install(self):
        fpp = pkg_data['full_package_name'].split('.')  # full package path
        full_exclude_files = [os.path.join(*(fpp + [x])) for x in exclude_files]
        alt_files = []
        outfiles = install_lib.install_lib.install(self)
        for x in outfiles:
            for full_exclude_file in full_exclude_files:
                if full_exclude_file in x:
                    os.remove(x)
                    break
            else:
                alt_files.append(x)
        return alt_files


class MySdist(_sdist):
    def initialize_options(self):
        _sdist.initialize_options(self)
        # failed expiriment, see pep 527, new uploads should be tar.gz or .zip
        # because of unicode_literals
        # self.formats = fmt if fmt else ['bztar']
        dist_base = os.environ.get('PYDISTBASE')
        fpn = getattr(getattr(self, 'nsp', self), 'full_package_name', None)
        if fpn and dist_base:
            print('setting  distdir {}/{}'.format(dist_base, fpn))
            self.dist_dir = os.path.join(dist_base, fpn)


# try except so this doesn't bomb when you don't have wheel installed, implies
# generation of wheels in ./dist
try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel  # NOQA

    class MyBdistWheel(_bdist_wheel):
        def initialize_options(self):
            _bdist_wheel.initialize_options(self)
            dist_base = os.environ.get('PYDISTBASE')
            fpn = getattr(getattr(self, 'nsp', self), 'full_package_name', None)
            if fpn and dist_base:
                print('setting  distdir {}/{}'.format(dist_base, fpn))
                self.dist_dir = os.path.join(dist_base, fpn)

    _bdist_wheel_available = True

except ImportError:
    _bdist_wheel_available = False


class NameSpacePackager(object):
    def __init__(self, pkg_data):
        assert isinstance(pkg_data, dict)
        self._pkg_data = pkg_data
        self.full_package_name = self._pkg_data['full_package_name']
        self._split = None
        self._extra_packages = []
        self.depth = self.full_package_name.count('.')
        self.nested = self._pkg_data.get('nested', False)
        # if self.nested:
        #     NameSpaceInstaller.install_namespaces = lambda x: None
        self.command = None
        self.python_version()
        self._pkg = [None, None]  # required and pre-installable packages
        if sys.argv[0] == 'setup.py' and sys.argv[1] == 'install':
            debug('calling setup.py', sys.argv)
            if '-h' in sys.argv:
                pass
            elif '--single-version-externally-managed' not in sys.argv:
                if os.environ.get('READTHEDOCS', None) == 'True':
                    os.system('pip install .')
                    sys.exit(0)
                if not os.environ.get('RUAMEL_NO_PIP_INSTALL_CHECK', False):
                    print('error: you have to install with "pip install ."')
                    sys.exit(1)
        # If you only support an extension module on Linux, Windows thinks it
        # is pure. That way you would get pure python .whl files that take
        # precedence for downloading on Linux over source with compilable C code
        if self._pkg_data.get('universal'):
            Distribution.is_pure = lambda *args: True
        else:
            Distribution.is_pure = lambda *args: False
        for x in sys.argv:
            if x[0] == '-' or x == 'setup.py':
                continue
            self.command = x
            break

    @property
    def split(self):
        """split the full package name in list of compontents traditionally
        done by setuptools.find_packages. This routine skips any directories
        with __init__.py, for which the name starts with "_" or ".", or the
        __init__.py contains package data (indicating a subpackage)
        """
        skip = []
        if self._split is None:
            fpn = self.full_package_name.split('.')
            self._split = []
            while fpn:
                self._split.insert(0, '.'.join(fpn))
                fpn = fpn[:-1]
            for d in sorted(os.listdir('.')):
                if not os.path.isdir(d) or d == self._split[0] or d[0] in '._':
                    continue
                # prevent sub-packages in namespace from being included
                x = os.path.join(d, '__init__.py')
                if os.path.exists(x):
                    pd = _package_data(x)
                    if pd.get('nested', False):
                        skip.append(d)
                        continue
                    ep = self.full_package_name + '.' + d
                    self._split.append(ep)
                    self._extra_packages.append(ep)
        if skip:
            # this interferes with output checking
            # print('skipping sub-packages:', ', '.join(skip))
            pass
        return self._split

    @property
    def namespace_directories(self, depth=None):
        """return list of directories where the namespace should be created /
        can be found
        """
        res = []
        for index, d in enumerate(self.split[:depth]):
            # toplevel gets a dot
            if index > 0:
                d = os.path.join(*d.split('.'))
            res.append('.' + d)
        return res

    @property
    def package_dir(self):
        d = {
            # don't specify empty dir, clashes with package_data spec
            self.full_package_name: '.',
        }
        if 'extra_packages' in self._pkg_data:
            return d
        # if len(self.split) > 1:  # only if package namespace
        #     d[self.split[0]] = self.namespace_directories(1)[0]
        # print('d', d, os.getcwd())
        return d

    def python_version(self):
        supported = self._pkg_data.get('supported')
        if supported is None:
            return
        if len(supported) == 1:
            minimum = supported[0]
        else:
            for x in supported:
                if x[0] == sys.version_info[0]:
                    minimum = x
                    break
            else:
                return
        if sys.version_info < minimum:
            print('minimum python version(s): ' + str(supported))
            sys.exit(1)

    def check(self):
        # https://github.com/pypa/setuptools/issues/2355#issuecomment-685159580
        InstallationError = Exception
        # arg is either develop (pip install -e) or install
        if self.command not in ['install', 'develop']:
            return

        # if hgi and hgi.base are both in namespace_packages matching
        # against the top (hgi.) it suffices to find minus-e and non-minus-e
        # installed packages. As we don't know the order in namespace_packages
        # do some magic
        prefix = self.split[0]
        prefixes = {prefix, prefix.replace('_', '-')}
        for p in sys.path:
            if not p:
                continue  # directory with setup.py
            if os.path.exists(os.path.join(p, 'setup.py')):
                continue  # some linked in stuff might not be hgi based
            if not os.path.isdir(p):
                continue
            if p.startswith('/tmp/'):
                continue
            for fn in os.listdir(p):
                for pre in prefixes:
                    if fn.startswith(pre):
                        break
                else:
                    continue
                full_name = os.path.join(p, fn)
                # not in prefixes the toplevel is never changed from _ to -
                if fn == prefix and os.path.isdir(full_name):
                    # directory -> other, non-minus-e, install
                    if self.command == 'develop':
                        raise InstallationError(
                            'Cannot mix develop (pip install -e),\nwith '
                            'non-develop installs for package name {0}'.format(fn),
                        )
                elif fn == prefix:
                    raise InstallationError('non directory package {0} in {1}'.format(fn, p))
                for pre in [x + '.' for x in prefixes]:
                    if fn.startswith(pre):
                        break
                else:
                    continue  # hgiabc instead of hgi.
                if fn.endswith('-link') and self.command == 'install':
                    raise InstallationError(
                        'Cannot mix non-develop with develop\n(pip install -e)'
                        ' installs for package name {0}'.format(fn),
                    )

    def entry_points(self, script_name=None, package_name=None):
        """normally called without explicit script_name and package name
        the default console_scripts entry depends on the existence of __main__.py:
        if that file exists then the function main() in there is used, otherwise
        the in __init__.py.

        the _package_data entry_points key/value pair can be explicitly specified
        including a "=" character. If the entry is True or 1 the
        scriptname is the last part of the full package path (split on '.')
        if the ep entry is a simple string without "=", that is assumed to be
        the name of the script.
        """

        def pckg_entry_point(name):
            return '{0}{1}:main'.format(
                name, '.__main__' if os.path.exists('__main__.py') else "",
            )

        ep = self._pkg_data.get('entry_points', True)
        if isinstance(ep, dict):
            return ep
        if ep is None:
            return None
        if ep not in [True, 1]:
            if '=' in ep:
                # full specification of the entry point like
                # entry_points=['yaml = ruamel.yaml.cmd:main'],
                return {'console_scripts': [ep]}
            # assume that it is just the script name
            script_name = ep
        if package_name is None:
            package_name = self.full_package_name
        if not script_name:
            script_name = package_name.rsplit('.', 1)[-1]
        return {
            'console_scripts': [
                '{0} = {1}'.format(script_name, pckg_entry_point(package_name)),
            ],
        }

    @property
    def project_urls(self):
        ret_val = {}
        sp = self.full_package_name
        for ch in '_.':
            sp = sp.replace(ch, '-')
        base_url = self._pkg_data.get('url', 'https://sourceforge.net/p/{0}'.format(sp))
        if base_url[-1] != '/':
            base_url += '/'
        ret_val['Home'] = base_url
        if 'sourceforge.net' in base_url:
            ret_val['Source'] = base_url + 'code/ci/default/tree/'
            ret_val['Tracker'] = base_url + 'tickets/'
        assert self._pkg_data.get('read_the_docs') is None, "update pon data read_the_docs -> url_doc='https://domain/path/{pkgname}/'"  # NOQA
        url_doc = self._pkg_data.get('url_doc')
        if url_doc:
            ret_val['Documentation'] = url_doc.format(full_package_name=sp)
        return ret_val

    @property
    def author(self):
        return self._pkg_data['author']  # no get needs to be there

    @property
    def author_email(self):
        return self._pkg_data['author_email']  # no get needs to be there

    @property
    def license(self):
        """return the license field from _package_data, None means MIT"""
        lic = self._pkg_data.get('license')
        if lic is None:
            # lic_fn = os.path.join(os.path.dirname(__file__), 'LICENSE')
            # assert os.path.exists(lic_fn)
            return 'MIT license'
        return lic

    def has_mit_lic(self):
        return 'MIT' in self.license

    @property
    def description(self):
        return self._pkg_data['description']  # no get needs to be there

    @property
    def status(self):
        # αβ
        status = self._pkg_data.get('status', 'β').lower()
        if status in ['α', 'alpha']:
            return (3, 'Alpha')
        elif status in ['β', 'beta']:
            return (4, 'Beta')
        elif 'stable' in status.lower():
            return (5, 'Production/Stable')
        raise NotImplementedError

    @property
    def classifiers(self):
        """this needs more intelligence, probably splitting the classifiers from _pkg_data
        and only adding defaults when no explicit entries were provided.
        Add explicit Python versions in sync with tox.env generation based on python_requires?
        See comment develop
        """
        attr = '_' + sys._getframe().f_code.co_name
        if not hasattr(self, attr):
            setattr(self, attr, self._setup_classifiers())
        return getattr(self, attr)

    def _setup_classifiers(self):
        c = set([  # NOQA
                ('Development Status', '{0} - {1}'.format(*self.status)),
                ('Intended Audience', 'Developers'),
#               ('License', 'OSI Approved', ('MIT' if self.has_mit_lic() else 'Other/Proprietary') + ' License'),  # NOQA
                ('License', ('OSI Approved :: MIT' if self.has_mit_lic() else 'Other/Proprietary') + ' License'),  # NOQA
                ('Operating System', 'OS Independent'),
                ('Programming Language', 'Python'),
                ])
        for cl in self._pkg_data.get('classifiers', []):
            print('cltype', type(cl), repr(cl))
            if isinstance(cl, str):
                c.add((cl,))
            else:
                c.add(tuple(c))
        supported = self.supported[0]
        assert supported[0] == 3
        minor = supported[1]
        while minor <= 13:
            version = (supported[0], minor)
            c.add(tuple(['Programming Language', 'Python'] + list(version)))
            minor += 1
        ret_val = []
        for x in c:
            print('x', repr(x))
        prev = str
        for cl in sorted(c):
            if isinstance(cl, str):
                ret_val.append(cl)
                continue
            assert isinstance(cl, (tuple, list))
            line = ""
            for elem in cl:  # append the elements with appropriate separator
                next = type(elem)
                if line:
                    if prev is int and next is int:
                        line += '.'
                    else:
                        line += ' :: '
                line += str(elem)
                prev = next
            ret_val.append(line)
        return ret_val

    @property
    def keywords(self):
        return self._pkg_data.get('keywords', [])

    @property
    def install_requires(self):
        """list of packages required for installation"""
        return self._analyse_packages[0]

    @property
    def install_pre(self):
        """list of packages required for installation"""
        return self._analyse_packages[1]

    @property
    def _analyse_packages(self):
        """gather from configuration, names starting with * need
        to be installed explicitly as they are not on PyPI
        install_requires should be  dict, with keys 'any', 'py27' etc
        or a list (which is as if only 'any' was defined

        ToDo: update with: pep508 conditional dependencies
        """
        if self._pkg[0] is None:
            self._pkg[0] = []
            self._pkg[1] = []

        ir = self._pkg_data.get('install_requires')
        if ir is None:
            return self._pkg  # these will be both empty at this point
        if isinstance(ir, list):
            self._pkg[0] = ir
            return self._pkg
        # 'any' for all builds, 'py27' etc for specifics versions
        packages = ir.get('any', [])
        if isinstance(packages, str):
            packages = packages.split()  # assume white space separated string
        if self.nested:
            # parent dir is also a package, make sure it is installed (need its .pth file)
            parent_pkg = self.full_package_name.rsplit('.', 1)[0]
            if parent_pkg not in packages:
                packages.append(parent_pkg)
        implementation = platform.python_implementation()
        if implementation == 'CPython':
            pyver = 'py{0}{1}'.format(*sys.version_info)
        elif implementation == 'PyPy':
            pyver = 'pypy' if sys.version_info < (3,) else 'pypy3'
        elif implementation == 'Jython':
            pyver = 'jython'
        packages.extend(ir.get(pyver, []))
        for p in packages:
            # package name starting with * means use local source tree,  non-published
            # to PyPi or maybe not latest version on PyPI -> pre-install
            if p[0] == '*':
                p = p[1:]
                self._pkg[1].append(p)
            self._pkg[0].append(p)
        return self._pkg

    @property
    def extras_require(self):
        """dict of conditions -> extra packages informaton required for installation
        as of setuptools 33 doing `package ; python_version<=2.7' in install_requires
        still doesn't work

        https://www.python.org/dev/peps/pep-0508/
        https://wheel.readthedocs.io/en/latest/index.html#defining-conditional-dependencies
        https://hynek.me/articles/conditional-python-dependencies/
        """
        ep = self._pkg_data.get('extras_require')
        return ep

    # @property
    # def data_files(self):
    #     df = self._pkg_data.get('data_files', [])
    #     if self.has_mit_lic():
    #         df.append('LICENSE')
    #     if not df:
    #         return None
    #     return [('.', df)]

    @property
    def package_data(self):
        df = self._pkg_data.get('data_files', [])
        if self.has_mit_lic():
            # include the file
            df.append('LICENSE')
            # but don't install it
            exclude_files.append('LICENSE')
        if self._pkg_data.get('binary_only', False):
            exclude_files.append('__init__.py')
        debug('testing<<<<<')
        if 'Typing :: Typed' in self.classifiers:
            debug('appending')
            df.append('py.typed')
        pd = self._pkg_data.get('package_data', {})
        if df:
            pd[self.full_package_name] = df
        return pd

    @property
    def packages(self):
        # s = self.split
        s = [self._pkg_data['full_package_name']]
        return s + self.extra_packages

    @property
    def extra_packages(self):
        try:
            return self._pkg_data['extra_packages']
        except KeyError:
            _ = self.split
            return self._extra_packages

    @property
    def supported(self):
        return self._pkg_data.get('supported', _setup_data['supported'])

    @property
    def python_requires(self):
        return self._pkg_data.get('python_requires', f'>={".".join([str(x) for x in self.supported[0]])}')  # NOQA

    @property
    def ext_modules(self):
        """
        Check if all modules specified in the value for 'ext_modules' can be build.
        That value (if not None) is a list of dicts with 'name', 'src', 'lib'
        Optional 'test' can be used to make sure trying to compile will work on the host

        creates and return the external modules as Extensions, unless that
        is not necessary at all for the action (like --version)

        test existence of compiler by using export CC=nonexistent; export CXX=nonexistent
        """

        if hasattr(self, '_ext_modules'):
            return self._ext_modules
        if '--version' in sys.argv:
            return None
        if platform.python_implementation() == 'Jython':
            return None
        try:
            plat = sys.argv.index('--plat-name')
            if 'win' in sys.argv[plat + 1]:
                return None
        except ValueError:
            pass
        self._ext_modules = []
        no_test_compile = True
        if '--restructuredtext' in sys.argv:
            no_test_compile = True
        elif 'sdist' in sys.argv:
            no_test_compile = True
        if no_test_compile:
            for target in self._pkg_data.get('ext_modules', []):
                ext = Extension(
                    target['name'],
                    sources=[x for x in target['src']],  # NOQA
                    libraries=[x for x in target.get('lib')],  # NOQA
                )
                self._ext_modules.append(ext)
            return self._ext_modules
        # this used to use distutils

    @property
    def test_suite(self):
        return self._pkg_data.get('test_suite')

    def wheel(self, kw, setup):
        """temporary add setup.cfg if creating a wheel to include LICENSE file
        https://bitbucket.org/pypa/wheel/issues/47
        """
        if 'bdist_wheel' not in sys.argv:
            return False
        file_name = 'setup.cfg'
        if os.path.exists(file_name):  # add it if not in there?
            return False
        with open(file_name, 'w') as fp:
            if self._pkg_data.get('universal'):
                fp.write('[bdist_wheel]\nuniversal = 1\n')
        try:
            setup(**kw)
        except Exception:
            raise
        finally:
            os.remove(file_name)
        return True


class TmpFiles:
    def __init__(self, pkg_data, py_project=True, keep=False):
        self._rm_after = []
        self._pkg_data = pkg_data
        self._py_project = py_project
        self._bdist_wheel = 'bdist_wheel' in sys.argv
        self._keep = keep

    def __enter__(self):
        self.bdist_wheel()
        self.py_project()

    def bdist_wheel(self):
        """pyproject doesn't allow for universal, so use setup.cfg if necessary
        """
        file_name = 'setup.cfg'
        if not self._bdist_wheel or os.path.exists(file_name):
            return
        if self._pkg_data.get('universal'):
            self._rm_after.append(file_name)
            with open(file_name, 'w') as fp:
                fp.write('[bdist_wheel]\nuniversal = 1\n')

    def py_project(self):
        """
        to prevent pip from complaining, or is it too late to create it from setup.py
        """
        file_name = 'pyproject.toml'
        if not self._py_project or os.path.exists(file_name):
            return
        self._rm_after.append(file_name)
        with open(file_name, 'w') as fp:
            fp.write(dedent("""\
            [build-system]
            requires = ["setuptools"]
            # test
            build-backend = "setuptools.build_meta"
            """))

    def __exit__(self, typ, value, traceback):
        if self._keep:
            return
        for p in self._rm_after:
            if not os.path.exists(p):
                print('file {} already removed'.format(p))
            else:
                os.unlink(p)


# call setup
def main():
    dump_kw = '--dump-kw'
    if dump_kw in sys.argv:
        import wheel
        import setuptools
        import pip

        print('python:    ', sys.version)
        print('pip:       ', pip.__version__)
        print('setuptools:', setuptools.__version__)
        print('wheel:     ', wheel.__version__)
    nsp = NameSpacePackager(pkg_data)
    nsp.check()
    # nsp.create_dirs()
    MySdist.nsp = nsp
    cmdclass = dict(install_lib=MyInstallLib, sdist=MySdist)  # NOQA: C408
    if _bdist_wheel_available:
        MyBdistWheel.nsp = nsp
        cmdclass['bdist_wheel'] = MyBdistWheel

    kw = dict(  # NOQA: C408
        name=nsp.full_package_name,
        metadata_version="1.0",
        version=version_str,
        packages=nsp.packages,
        python_requires=nsp.python_requires,
        project_urls=nsp.project_urls,
        author=nsp.author,
        author_email=nsp.author_email,
        cmdclass=cmdclass,
        package_dir=nsp.package_dir,
        entry_points=nsp.entry_points(),
        description=nsp.description,
        install_requires=nsp.install_requires,
        extras_require=nsp.extras_require,  # available since setuptools 18.0 / 2015-06
        license=nsp.license,
        classifiers=nsp.classifiers,
        keywords=nsp.keywords,
        package_data=nsp.package_data,
        ext_modules=nsp.ext_modules,
        test_suite=nsp.test_suite,
        zip_safe=False,
    )

    if '--version' not in sys.argv and ('--verbose' in sys.argv or dump_kw in sys.argv):
        for k in sorted(kw):
            v = kw[k]
            print('  "{0}": {1},'.format(k, repr(v)))
    # if '--record' in sys.argv:
    #     return
    if dump_kw in sys.argv:
        sys.argv.remove(dump_kw)
    if not os.environ.get('RUAMEL_NO_LONG_DESCRIPTION', False):
        for readme_file_name, readme_markup_type in [
            ('README.md', 'text/markdown; charset=UTF-8; variant=CommonMark'),
            ('README.rst', 'text/x-rst'),
        ]:
            try:
                kw['long_description'] = open(readme_file_name).read()
                kw['long_description_content_type'] = readme_markup_type
                break
            except FileNotFoundError:
                pass

    # if nsp.wheel(kw, setup):
    #     return
    with TmpFiles(pkg_data, keep=True):
        for x in ['-c', 'egg_info', '--egg-base', 'pip-egg-info']:
            if x not in sys.argv:
                break
        else:
            # we're doing a tox setup install any starred package by searching up the
            # source tree until you match your/package/name for your.package.name
            for p in nsp.install_pre:
                import subprocess

                # search other source
                setup_path = os.path.join(*p.split('.') + ['setup.py'])
                try_dir = os.path.dirname(sys.executable)
                while len(try_dir) > 1:
                    full_path_setup_py = os.path.join(try_dir, setup_path)
                    if os.path.exists(full_path_setup_py):
                        pip = sys.executable.replace('python', 'pip')
                        cmd = [pip, 'install', os.path.dirname(full_path_setup_py)]
                        # with open('/var/tmp/notice', 'a') as fp:
                        #     print('installing', cmd, file=fp)
                        subprocess.check_output(cmd)
                        break
                    try_dir = os.path.dirname(try_dir)
        setup(**kw)


main()
