import os
import sys

def main():
    """
    Hardlinks everything into the temp folder, except git.
    """
    destination = sys.argv[1]
    source = os.path.abspath("..")

    for src_path, dirs, files in os.walk(source):
        # extract the path relative to the root of the repo
        sub_path = os.path.relpath(src_path, source)

        dst_folder = os.path.join(destination, sub_path)

        if sub_path.startswith(".git"):
            continue

        if not os.path.exists(dst_folder):
            os.makedirs(dst_folder)

        # Start linking the files into the destination
        for f in files:
            dst_file = os.path.join(dst_folder, f)
            src_file = os.path.join(src_path, f)

            # If the destination file doesn't exist, put it in place.
            if not os.path.exists(dst_file):
                os.link(src_file, dst_file)
                os.utime(src_file)


if __name__ == '__main__':
    main()