from __future__ import print_function

import os
import sys
import subprocess
import shutil


def _needs_conversion(src, dst):
    return os.stat(src).st_mtime > os.stat(dst).st_mtime


def _skip_folder(src, ignored):
    for i in ignored:
        if i in src:
            return True
    return False

def _convert(dst):
    subprocess.check_call(["2to3", "-w", dst])


def _copy_file(src, dst):
    if "fixtures" in dst:
        os.link(src, dst)
    else:
        shutil.copyfile(src, dst)
    # Since this is a newly file, convert it.
    if os.path.splitext(src)[1] == ".py":
        _convert(dst)

def main():
    """
    Copies and converts Toolkit source code to the specified destination.
    """
    destination = sys.argv[1]
    ignored_folders = sys.argv[2:]
    source = os.path.abspath("..")

    for src_path, dirs, files in os.walk(source):
        # extract the path relative to the root of the repo
        sub_path = os.path.relpath(src_path, source)

        dst_folder = os.path.join(destination, sub_path)

        if _skip_folder(src_path, ignored_folders):
            continue

        if not os.path.exists(dst_folder):
            os.makedirs(dst_folder)

        # Start linking the files into the destination
        for f in files:
            dst_file = os.path.join(dst_folder, f)
            src_file = os.path.join(src_path, f)

            # If the destination file doesn't exist, put it in place.
            if not os.path.exists(dst_file):
                _copy_file(src_file, dst_file)

            # If the file is more recent, remove it and convert it.
            if _needs_conversion(src_file, dst_file):
                print("File '%s' was updated, copying to the conversion folder" %(src_file,))
                os.remove(dst_file)
                _copy_file(src_file, dst_file)


if __name__ == '__main__':
    main()