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
    sixer_options = ["iteritems", "itervalues", "iterkeys", "itertools", "basestring", "six_moves", "urllib"]
    args = ["sixer", "-w", ",".join(sixer_options), dst]
    subprocess.check_call(args)

    two_to_three_options = " -f ".join(["-f import", "print", "numliterals", "except", "raise", "dict", "has_key", "types"]).split(" ")
    subprocess.check_call(["2to3", "-w"] + two_to_three_options + [dst])


def _copy_file(src, dst):
    if "fixtures" in dst:
        os.link(src, dst)
        return
    else:
        shutil.copyfile(src, dst)
        shutil.copymode(src, dst)
    # Since this is a newly file, convert it.
    if os.path.splitext(src)[1] == ".py":
        try:
            _convert(dst)
        except:
            bak = dst + ".bak"
            if os.path.exists(bak):
                os.remove(bak)
            shutil.copyfile(dst, bak)
            os.remove(dst)
            raise


def main():
    """
    Copies and converts Toolkit source code to the specified destination.
    """
    source = os.path.expanduser(sys.argv[1])
    destination = os.path.expanduser(sys.argv[2])
    ignored_folders = sys.argv[3:]

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
