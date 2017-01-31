import os
import optparse


from tank import LogManager
from tank.util import filesystem
from tank.platform import environment
from tank.descriptor import Descriptor, create_descriptor
from tank.authentication import ShotgunAuthenticator

logger = LogManager.get_logger("utils")


class OptionParserLineBreakingEpilog(optparse.OptionParser):
    """
    Subclassed version of the option parser that doesn't
    swallow white space in the epilog
    """
    def format_epilog(self, formatter):
        return self.epilog


def add_authentication_options(parser):
    """
    Adds authentication options to an option parser.

    :param parser: OptionParser to which authentication options will be added.
    """
    group = optparse.OptionGroup(
        parser,
        "Shotgun Authentication",
        "In order to download content from the Toolkit app store, the script will need to authenticate "
        "against any shotgun site. By default, it will use the toolkit authentication APIs stored "
        "credentials, and if such are not found, it will prompt for site, username and password."
    )

    group.add_option(
        "-s",
        "--shotgun-host",
        default=None,
        action="store",
        help="Shotgun host to authenticate with."
    )

    group.add_option(
        "-n",
        "--shotgun-script-name",
        default=None,
        action="store",
        help="Script to use to authenticate with the given host."
    )

    group.add_option(
        "-k",
        "--shotgun-script-key",
        default=None,
        action="store",
        help="Script key to use to authenticate with the given host."
    )

    parser.add_option_group(group)


def authenticate(options):
    """
    Authenticates using the command line arguments or user input.

    :param options: OptionParser instance with values shotgun_host, shotgun_script_key and shotgun_script_name

    :returns: An authenticated ShotgunUser instance.
    """
    # now authenticate to shotgun
    sg_auth = ShotgunAuthenticator()

    if options.shotgun_host:
        script_name = options.shotgun_script_name
        script_key = options.shotgun_script_key

        if script_name is None or script_key is None:
            logger.error("Need to provide, host, script name and script key! Run with -h for more info.")
            return 2

        logger.info("Connecting to %s using script user %s..." % (options.shotgun_host, script_name))
        return sg_auth.create_script_user(script_name, script_key, options.shotgun_host)

    else:
        # get user, prompt if necessary
        return sg_auth.get_user()


def _cache_descriptor(sg, desc_type, desc_dict, target_path):
    """
    Cache the given descriptor into a new bundle cache.

    :param sg: Shotgun API instance
    :param desc_type: Descriptor.ENGINE | Descriptor.APP | Descriptor.FRAMEWORK
    :param desc_dict: descriptor dict or uri
    :param target_path: bundle cache root to cache into
    """
    desc = create_descriptor(sg, desc_type, desc_dict, fallback_roots=[target_path])
    desc.ensure_local()
    desc_size_kb = filesystem.compute_folder_size(desc.get_path()) / 1024
    logger.info("Caching %s into plugin bundle cache (size %d KiB)" % (desc, desc_size_kb))
    if not desc._io_descriptor.is_immutable():
        logger.warning("Descriptor %r may not work for other users using the plugin!" % desc)
    desc.clone_cache(target_path)


def cache_apps(sg_connection, cfg_descriptor, bundle_cache_root):
    """
    Iterates over all environments within the given configuration descriptor
    and caches all items into the bundle cache root.

    :param sg_connection: Shotgun connection
    :param cfg_descriptor: Config descriptor
    :param bundle_cache_root: Root where to cache payload
    """
    # introspect the config and cache everything
    logger.info("Introspecting environments...")
    env_path = os.path.join(cfg_descriptor.get_path(), "env")

    # find all environment files
    env_filenames = []
    for filename in os.listdir(env_path):
        if filename.endswith(".yml"):
            # matching the env filter (or no filter set)
            logger.info("> found %s" % filename)
            env_filenames.append(os.path.join(env_path, filename))

    # traverse and cache
    for env_path in env_filenames:
        logger.info("Processing %s..." % env_path)
        env = environment.Environment(env_path)

        for eng in env.get_engines():
            # resolve descriptor and clone cache into bundle cache
            _cache_descriptor(
                sg_connection,
                Descriptor.ENGINE,
                env.get_engine_descriptor_dict(eng),
                bundle_cache_root
            )

            for app in env.get_apps(eng):
                # resolve descriptor and clone cache into bundle cache
                _cache_descriptor(
                    sg_connection,
                    Descriptor.APP,
                    env.get_app_descriptor_dict(eng, app),
                    bundle_cache_root
                )

        for framework in env.get_frameworks():
            _cache_descriptor(
                sg_connection,
                Descriptor.FRAMEWORK,
                env.get_framework_descriptor_dict(framework),
                bundle_cache_root
            )

    logger.info("Total size of bundle cache: %d KiB" % (filesystem.compute_folder_size(bundle_cache_root) / 1024))
