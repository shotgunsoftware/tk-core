# MOFA - fix for #30005

import os

from .. import LogManager
# from pmp.core import rdbg

log = LogManager.get_logger(__name__)


def fix_root_duplicate(tk, path):
    roots = tk.pipeline_configuration.get_all_platform_data_roots().get("primary")

    if not roots:
        log.debug("Cannot retrieve primary roots for configuration %s" %
                  tk.pipeline_configuration.get_path())
        return path

    # avoid shotgun and os.path "sanity" since it will remove multiple slashes
    # and we want to detect it here !
    # path = ShotgunPath.normalize(path)
    # path = os.path.normpath(path)
    current_os_sep = os.sep
    other_os_sep = "\\" if os.sep == "/" else "/"
    norm_path = path.replace(other_os_sep, current_os_sep)
    current_os_root = tk.pipeline_configuration.get_primary_data_root()

    print norm_path

    for platform, plat_root in roots.iteritems():
        os_sep = "\\" if platform == "win32" else "/"
        # split with a trailing slash to avoid confision with overlapping projects names
        split_path = norm_path.split(plat_root + os_sep)
        print split_path
        # at least two elements and the first one is not empty
        # we have a project root in the middle of our path ...
        if len(split_path) >= 2 and split_path[0]:
            # isolate the path after the "real" root
            relative_path = split_path[-1]
            # ensure we use a correct root for out platform
            # since it could come from an erroneous published file path
            # or location cache entry by the way
            new_path = current_os_sep.join([current_os_root, relative_path])
            # sanitize at the very end
            new_path = os.path.normpath(new_path)

            msg = "Caught root duplicate in {0}, fixed to {1}".format(path, new_path)
            # rdbg(msg)
            log.debug(msg)

            return new_path

    # msg = "Path root seem valid in {0}".format(path)
    # log.debug(msg)
    # rdbg(msg)

    # no duplicate detected, return as is
    return path
