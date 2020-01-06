import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logger.setLevel(logging.INFO)

import os
import os.path
import shutil
import sys
import subprocess


def build(source_path, build_path, install_path, targets):

    def _deliver(src, dst, symlink=False):
        if not symlink:
            logger.info('Copying {} to {}'.format(src, dst))
            if os.path.isdir(src):
                if dst.endswith(os.sep):
                    basename = os.path.basename(src)
                    dst = os.path.join(dst, basename)
                shutil.copytree(src, dst)
            else:
                shutil.copy(src, dst)
        else:
            logger.info('Symlinking {} to {}'.format(src, dst))
            if dst.endswith(os.sep):
                basename = os.path.basename(src)
                dst = os.path.join(dst, basename)
            if sys.platform.startswith('win'):
                if os.path.isdir(src):
                    subprocess.call(['mklink', '/d', dst, src], shell=True)
                else:
                    subprocess.call(['mklink', dst, src], shell=True)
            else:
                os.symlink(src, dst)

    def _install():
        # check if argument "--symlink" presents
        symlink = False
        if int(os.environ["__PARSE_ARG_SYMLINK"]):
            symlink = True

        # check if argument "--current" presents
        build_current_folder = False

        files_to_ignore = ('build', 'package.py')

        # src = os.path.join(source_path, 'src')
        src = source_path

        if os.path.isdir(src):
            logger.info('Src:{}'.format(src))
            logger.info('Dst:{}'.format(install_path))
            for name in os.listdir(src):
                # skipping some hidden files(e.g. .git)
                if name.startswith('.') or name in files_to_ignore:
                    continue

                file_path = os.path.abspath(os.path.join(src, name))
                _deliver(file_path, os.path.join(install_path, ''), symlink)

        # package.py is to be copied to install path automatically by rez build system
        # _deliver(os.path.join(source_path, 'package.py'), install_path, symlink)
        
        # manage necessary files starts with '.'
        whitelist = []
        for f in whitelist:
            file_ = os.path.join(source_path, f)
            if os.path.isfile(file_):
                _deliver(file_, os.path.join(install_path, ''), symlink)


        if not build_current_folder:
            return

        # compose "current" path name
        duplicated_install_path = os.path.join(os.path.dirname(install_path),
                                               'current')

        # remove existing one
        # NOTE: functions on 'link' in python2.7 os module not working on windows
        if sys.platform.startswith('win'):
            if os.path.exists(duplicated_install_path):
                try:
                    os.rmdir(duplicated_install_path)
                except:
                    shutil.rmtree(duplicated_install_path)
        else:
            if os.path.islink(duplicated_install_path):
                os.unlink(duplicated_install_path)
            elif os.path.isdir(duplicated_install_path):
                shutil.rmtree(duplicated_install_path)

        if not os.path.isdir(os.path.dirname(duplicated_install_path)):
            os.makedirs(os.path.dirname(duplicated_install_path))


        if symlink:
            # the only use case is local testing for now
            _deliver(install_path, duplicated_install_path, symlink=True)
        elif not os.path.islink(install_path):
            # Only create "current" if installation is not a link.
            if sys.platform.startswith('linux'):
                logger.info(
                    'Symlink {} to {}'.format(install_path,
                                              duplicated_install_path))
                os.symlink(install_path, duplicated_install_path)
            else:
                logger.info(
                    'Copying {} to {}'.format(install_path,
                                              duplicated_install_path))
                shutil.copytree(install_path, duplicated_install_path)

    if "install" in (targets or []):
        _install()


# Below section is necessary for rez custom build system - custom.py,
# which executes build_command ("python {root}/rezbuild.py {install}") defined in package.py
if __name__ == '__main__':
    build(source_path=os.environ['REZ_BUILD_SOURCE_PATH'],
          build_path=os.environ['REZ_BUILD_PATH'],
          install_path=os.environ['REZ_BUILD_INSTALL_PATH'],
          targets=sys.argv[1:])
