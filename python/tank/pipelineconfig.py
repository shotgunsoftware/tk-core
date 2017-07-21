# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Encapsulates the pipeline configuration and helps navigate and resolve paths
across storages, configurations etc.
"""
import os
import glob
import cPickle as pickle

from tank_vendor import yaml

from .errors import TankError, TankUnreadableFileError
from .util.version import is_version_older
from . import constants
from .platform.environment import InstalledEnvironment, WritableEnvironment
from .util import shotgun, yaml_cache
from .util import ShotgunPath
from . import hook
from . import pipelineconfig_utils
from . import template_includes
from . import LogManager

from .descriptor import Descriptor, create_descriptor, descriptor_uri_to_dict

log = LogManager.get_logger(__name__)


class PipelineConfiguration(object):
    """
    Represents a pipeline configuration in Tank.

    Use the factory methods in pipelineconfig_factory
    to construct this object, do not create directly via the constructor.
    """

    def __init__(self, pipeline_configuration_path, descriptor=None):
        """
        Constructor. Do not call this directly, use the factory methods
        in pipelineconfig_factory.

        NOTE ABOUT SYMLINKS!

        The pipeline_configuration_path is always populated by the paths
        that were registered in shotgun, regardless of how the symlink setup
        is handled on the OS level.

        :param str pipeline_configuration_path: Path to the pipeline configuration on disk.
        :param descriptor: Descriptor that was used to create this pipeline configuration. 
            Defaults to ``None`` for backwards compatibility with Bootstrapper that only
            pass down one argument. Also this argument was passed down by cores from
            v0.18.72 to 0.18.94. The descriptor is now read from the disk inside
            pipeline_configuration.yml.
        :type descriptor: :class:`sgtk.descriptor.ConfigDescriptor`
        """
        self._pc_root = pipeline_configuration_path

        # validate that the current code version matches or is compatible with
        # the code that is locally stored in this config!!!!
        our_associated_api_version = self.get_associated_core_version()

        # and get the version of the API currently in memory
        current_api_version = pipelineconfig_utils.get_currently_running_api_version()
        
        if our_associated_api_version not in [None, "unknown", "HEAD"] and \
           is_version_older(current_api_version, our_associated_api_version):
            # currently running API is too old!
            current_api_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            
            # tell the user that their core is too old for this config
            #
            # this can happen if you are running a configuration but you are getting the core
            # API from somewhere else. For example, if you have added a core to your pythonpath
            # and then try to do sgtk_from_path("/path/to/pipeline/config") and that config
            # is using a more recent version of the core. 
            
            raise TankError("You are running Toolkit %s located in '%s'. The configuration you are "
                            "trying to use needs core version %s or higher. To fix this, "
                            "use the tank command (or Toolkit core API) located at '%s' "
                            "which is associated with this configuration." % (current_api_version, 
                                                                              current_api_path, 
                                                                              our_associated_api_version, 
                                                                              self.get_install_location()))            

        self._roots = pipelineconfig_utils.get_roots_metadata(self._pc_root)

        # get the project tank disk name (Project.tank_name),
        # stored in the pipeline config metadata file.
        pipeline_config_metadata = self._get_metadata()
        self._project_name = pipeline_config_metadata.get("project_name")
        self._project_id = pipeline_config_metadata.get("project_id")
        self._pc_id = pipeline_config_metadata.get("pc_id")
        self._plugin_id = pipeline_config_metadata.get("plugin_id")
        self._pc_name = pipeline_config_metadata.get("pc_name")
        self._published_file_entity_type = pipeline_config_metadata.get(
            "published_file_entity_type",
            "PublishedFile"
        )
        self._use_shotgun_path_cache = pipeline_config_metadata.get(
            "use_shotgun_path_cache",
            False
        )

        # figure out whether to use the bundle cache or the
        # local pipeline configuration 'install' cache
        if pipeline_config_metadata.get("use_bundle_cache"):
            # use bundle cache
            self._bundle_cache_root_override = None
        else:
            # use cache relative to core install
            self._bundle_cache_root_override = os.path.join(self.get_install_location(), "install")

        if pipeline_config_metadata.get("bundle_cache_fallback_roots"):
            self._bundle_cache_fallback_paths = pipeline_config_metadata.get("bundle_cache_fallback_roots")
        else:
            self._bundle_cache_fallback_paths = []

        # There are four ways this initializer can be invoked.
        #
        # 1) Classic: We're instantiated from sgtk_from_path with a single path.
        # 2) Bootstrap: path is set, descriptor is unset and no descriptor inside
        #    pipeline_configuration.yml
        # 3) Bootstrap: path is set, descriptor is set and no descriptor inside
        #    pipeline_configuration.yml
        # 4) Bootstrap, path is set, descriptor is set and descriptor inside
        #    pipeline_configuration.yml
        #
        # The correct way to handle all of this is to go from a descriptor string or dictionary and
        # instantiate the correct descriptor type.
        #
        # Note that since the boostapper can't tell if the pipeline configuration is going to use
        # the file to read the descriptor or not, it is always going to pass down the descriptor in
        # the arguments. We can however ignore that argument in favor of the descriptor on disk.

        descriptor_dict = pipeline_config_metadata.get("source_descriptor")
        # We'll first assume the pipeline configuration is not installed.
        is_installed = False

        # If there is a descriptor in the file (4), we know we're not installed and we're done!
        if descriptor_dict:
            # The bootstrapper wrote the descriptor in the pipeline_configuration.yml file, nothing
            # more needs to be done.
            pass
        # If there's nothing in the file, but we're being passed down something by the bootstrapper,
        # we should use it! (3)
        elif descriptor:
            # Up to 0.18.94, we could be passed in a descriptor pointing to what we now consider to
            # be an Descriptor.INSTALLED_CONFIG, but the API back then didn't make the distinction
            # and called it a Descriptor.CONFIG.

            # We will test to see if the path referred to by the descriptor is the same as the
            # current os path. If it is the same then the descriptor is an installed descriptor. If
            # it isn't then it must be pointing to something inside the bundle cache, which means it
            # isn't installed.
            if self._pc_root == descriptor.get_path():
                is_installed = True

            descriptor_dict = descriptor.get_dict()
        # Now we only have a path set. (1&2). We can't assume anything, but since all pipeline
        # configurations, cached or installed, have the same layout on disk, we'll assume that we're
        # in an installed one. Also, since installed configurations are a bit more lenient about
        # things like info.yml, its a great fit since there are definitely installed configurations
        # in the wild without an info.yml in their config folder.
        else:
            is_installed = True
            descriptor_dict = {
                "type": "path",
                "path": self._pc_root
            }

        descriptor = create_descriptor(
            shotgun.get_deferred_sg_connection(),
            Descriptor.INSTALLED_CONFIG if is_installed else Descriptor.CONFIG,
            descriptor_dict,
            self._bundle_cache_root_override,
            self._bundle_cache_fallback_paths
        )

        self._descriptor = descriptor

        #
        # Now handle the case of a baked and immutable configuration.
        #
        # In this case, Toolkit is always started via the bootstrap manager.
        # A baked config means that the configuration isn't entirely determined
        # from what is written into the pipeline configuration yaml file but that
        # certain values, such as the project id, are specified at runtime.
        #
        # Such values are determined by the bootstrap process and passed via an
        # environment variable which is probed and unpacked below.
        #
        if constants.ENV_VAR_EXTERNAL_PIPELINE_CONFIG_DATA in os.environ:
            try:
                external_data = pickle.loads(os.environ[constants.ENV_VAR_EXTERNAL_PIPELINE_CONFIG_DATA])
            except Exception, e:
                log.warning("Could not load external config data from: %s" % e)

            if "project_id" in external_data:
                self._project_id = external_data["project_id"]
                log.debug("%s: Setting project id to %s from external config data" % (self, self._project_id))

            if "project_name" in external_data:
                self._project_name = external_data["project_name"]
                log.debug("%s: Setting project name to %s from external config data" % (self, self._project_name))

            if "pipeline_config_id" in external_data:
                self._pc_id = external_data["pipeline_config_id"]
                log.debug("%s: Setting pipeline config id to %s from external config data" % (self, self._pc_id))

            if "pipeline_config_name" in external_data:
                self._pc_name = external_data["pipeline_config_name"]
                log.debug("%s: Setting pipeline config name to %s from external config data" % (self, self._pc_name))

            if "bundle_cache_paths" in external_data:
                self._bundle_cache_fallback_paths = external_data["bundle_cache_paths"]
                log.debug(
                    "%s: Setting bundle cache fallbacks to %s from external config data" % (self, self._bundle_cache_fallback_paths)
                )

        # Populate the global yaml_cache if we find a pickled cache on disk.
        # TODO: For immutable configs, move this into bootstrap
        self._populate_yaml_cache()

        # run init hook
        self.execute_core_hook_internal(constants.PIPELINE_CONFIGURATION_INIT_HOOK_NAME, parent=self)

    def __repr__(self):
        return "<Sgtk Configuration %s>" % self._pc_root

    ########################################################################################
    # handling pipeline config metadata
    
    def _get_metadata(self):
        """
        Loads the pipeline config metadata (the pipeline_configuration.yml) file from disk.
        
        :param pipeline_config_path: path to a pipeline configuration root folder
        :returns: deserialized content of the file in the form of a dict.
        """
    
        # now read in the pipeline_configuration.yml file
        cfg_yml = os.path.join(
            self.get_config_location(),
            "core",
            constants.PIPELINECONFIG_FILE
        )
    
        if not os.path.exists(cfg_yml):
            raise TankError("Configuration metadata file '%s' missing! "
                            "Please contact support." % cfg_yml)
    
        fh = open(cfg_yml, "rt")
        try:
            data = yaml.load(fh)
            if data is None:
                raise Exception("File contains no data!")
        except Exception, e:
            raise TankError("Looks like a config file is corrupt. Please contact "
                            "support! File: '%s' Error: %s" % (cfg_yml, e))
        finally:
            fh.close()
    
        return data
    
    def _update_metadata(self, updates):
        """
        Updates the pipeline configuration on disk with the passed in values.

        :param updates: Dictionary of values to update in the pipeline configuration
        """
        # get current settings
        curr_settings = self._get_metadata()
        
        # apply updates to existing cache
        curr_settings.update(updates)
        
        # write the record to disk
        pipe_config_sg_id_path = os.path.join(
            self.get_config_location(),
            "core",
            constants.PIPELINECONFIG_FILE
        )
        
        old_umask = os.umask(0)
        try:
            os.chmod(pipe_config_sg_id_path, 0666)
            # and write the new file
            fh = open(pipe_config_sg_id_path, "wt")
            # using safe_dump instead of dump ensures that we
            # don't serialize any non-std yaml content. In particular,
            # this causes issues if a unicode object containing a 7-bit
            # ascii string is passed as part of the data. in this case, 
            # dump will write out a special format which is later on 
            # *loaded in* as a unicode object, even if the content doesn't  
            # need unicode handling. And this causes issues down the line
            # in toolkit code, assuming strings:
            #
            # >>> yaml.dump({"foo": u"bar"})
            # "{foo: !!python/unicode 'bar'}\n"
            # >>> yaml.safe_dump({"foo": u"bar"})
            # '{foo: bar}\n'
            #            
            yaml.safe_dump(curr_settings, fh)
        except Exception, exp:
            raise TankError("Could not write to configuration file '%s'. "
                            "Error reported: %s" % (pipe_config_sg_id_path, exp))
        finally:
            fh.close()
            os.umask(old_umask)            

        self._project_id = curr_settings.get("project_id")
        self._pc_id = curr_settings.get("pc_id")
        self._pc_name = curr_settings.get("pc_name")

    def _populate_yaml_cache(self):
        """
        Loads pickled yaml_cache items if they are found and merges them into
        the global YamlCache.
        """
        cache_file = os.path.join(self._pc_root, "yaml_cache.pickle")
        if not os.path.exists(cache_file):
            return

        try:
            fh = open(cache_file, 'rb')
        except Exception, e:
            log.warning("Could not read yaml cache %s: %s" % (cache_file, e))
            return

        try:
            cache_items = pickle.load(fh)
            yaml_cache.g_yaml_cache.merge_cache_items(cache_items)
        except Exception, e:
            log.warning("Could not merge yaml cache %s: %s" % (cache_file, e))
        finally:
            fh.close()

        log.debug("Read %s items from yaml cache %s" % (len(cache_items), cache_file))


    ########################################################################################
    # general access and properties

    def get_path(self):
        """
        Returns the master root for this pipeline configuration
        """
        return self._pc_root

    def get_bundle_cache_fallback_paths(self):
        """
        Returns the list of bundle cache fallback location for this pipeline configuration.
        """
        return self._bundle_cache_fallback_paths

    def get_all_os_paths(self):
        """
        Returns the path to this config for all operating systems,
        as defined in the install_locations file.
        
        :returns: ShotgunPath
        """
        return pipelineconfig_utils.resolve_all_os_paths_to_config(self._pc_root)

    def get_name(self):
        """
        Returns the name of this PC.
        """
        return self._pc_name

    def is_auto_path(self):
        """
        Returns true if this config was set up with auto path mode.
        This method will connect to shotgun in order to determine the 
        auto path status.

        January 2016:
        DEPRECATED - DO NOT USE! At some stage this will be removed.

        :returns: boolean indicating auto path state
        """
        if self.is_unmanaged():
            # unmanaged configs introduced in core 0.18 means that
            # pipeline configurations now may not even have a
            # pipeline configuration entity in shotgun at all. This means
            # that the configuration is tracking a particular version of a
            # config directly, without any config settings anywhere.
            #
            return False

        sg = shotgun.get_sg_connection()
        data = sg.find_one(constants.PIPELINE_CONFIGURATION_ENTITY,
                           [["id", "is", self.get_shotgun_id()]],
                           ["linux_path", "windows_path", "mac_path"])

        if data is None:
            raise TankError("Cannot find a Pipeline configuration in Shotgun "
                            "that has id %s." % self.get_shotgun_id())

        def _is_empty(d):
            """
            Returns true if value is "" or None, False otherwise
            """
            if d is None or d == "":
                return True
            else:
                return False
        
        if _is_empty(data.get("linux_path")) and \
           _is_empty(data.get("windows_path")) and \
           _is_empty(data.get("mac_path")):
            # all three pipeline config fields are empty.
            # This means that we are running an auto path config
            return True
        
        else:
            return False

    def is_unmanaged(self):
        """
        Returns true if the configuration is unmanaged, e.g. it does not have a
        corresponding pipeline configuration in Shotgun.

        :return: boolean indicating if config is unmanaged
        """
        return self.get_shotgun_id() is None

    def is_localized(self):
        """
        Returns true if this pipeline configuration has its own Core
        
        :returns: boolean indicating if config is localized
        """
        return pipelineconfig_utils.is_localized(self._pc_root)

    def get_shotgun_id(self):
        """
        Returns the shotgun id for this PC.
        """
        return self._pc_id

    def get_plugin_id(self):
        """
        Returns the plugin id for this PC.
        For more information, see :meth:`~sgtk.bootstrap.ToolkitManager.plugin_id`.
        """
        return self._plugin_id

    def get_project_id(self):
        """
        Returns the shotgun id for the project associated with this PC.
        Can return None if the pipeline config represents the site and not a project.
        """
        return self._project_id

    def is_site_configuration(self):
        """
        Returns in the pipeline configuration is for the site configuration.

        :returns: True if this is a site configuration, False otherwise.
        """
        return self.get_project_id() is None

    def get_project_disk_name(self):
        """
        Returns the project name for the project associated with this PC.
        """
        return self._project_name

    def get_published_file_entity_type(self):
        """
        Returns the type of entity being used
        for the 'published file' entity
        """
        return self._published_file_entity_type

    def convert_to_site_config(self):
        """
        Converts the pipeline configuration into the site configuration.
        """
        self._update_metadata({"project_id": None})

    ########################################################################################
    # path cache

    def get_shotgun_path_cache_enabled(self):
        """
        Returns true if the shotgun path cache should be used.
        This should only ever return False for setups created before 0.15.
        All projects created with 0.14+ automatically sets this to true.
        """
        return self._use_shotgun_path_cache
    
    def turn_on_shotgun_path_cache(self):
        """
        Updates the pipeline configuration settings to have the shotgun based (v0.15+)
        path cache functionality enabled.
        
        Note that you need to force a full path sync once this command has been executed. 
        """
        
        if self.get_shotgun_path_cache_enabled():
            raise TankError("Shotgun based path cache already turned on!")
                
        self._update_metadata({"use_shotgun_path_cache": True})
        self._use_shotgun_path_cache = True

        
    ########################################################################################
    # storage roots related
        
    def get_local_storage_roots(self):
        """
        Returns local OS paths to all shotgun local storages used by toolkit. 
        Paths are validated and guaranteed not to be None.
        
        :returns: dictionary of storages, for example {"primary": "/studio", "textures": "/textures"}
        """
        proj_roots = {}

        for storage_name in self._roots:
            # get current os path
            local_root_path = self._roots[storage_name].current_os
            # validate it
            if local_root_path is None:
                raise TankError(
                    "Undefined toolkit storage! The local file storage '%s' is not defined for this "
                    "operating system! Please contact toolkit support." % storage_name)
            
            proj_roots[storage_name] = local_root_path

        return proj_roots
    
    def get_all_platform_data_roots(self):
        """
        Similar to get_data_roots but instead of returning the data roots for a single 
        operating system, the data roots for all operating systems are returned.
        
        The return structure is a nested dictionary structure, for example:

        {
         "primary": {"win32":  "z:\studio\my_project", 
                     "linux2": "/studio/my_project",
                     "darwin": "/studio/my_project"},
                     
         "textures": {"win32":  "z:\studio\my_project", 
                      "linux2": None,
                      "darwin": "/studio/my_project"},
        }
         
        The operating system keys are returned on sys.platform-style notation.
        If a data root has not been defined on a particular platform, None is 
        returned (see example above).

        @todo - refactor to use ShotgunPath

        :returns: dictionary of dictionaries. See above.
        """
        proj_roots = {}
        for storage_name in self._roots:
            # join the project name to the storage ShotgunPath
            project_path = self._roots[storage_name].join(self._project_name)
            # break out the ShotgunPath object in sys.platform style dict
            proj_roots[storage_name] = project_path.as_system_dict()

        return proj_roots
    
    def get_data_roots(self):
        """
        Returns a dictionary of all the data roots available for this PC,
        keyed by their storage name. Only returns paths for current platform.
        Paths are guaranteed to be not None.

        :returns: A dictionary keyed by storage name, for example
                  {"primary": "/studio/my_project", "textures": "/textures/my_project"}        
        """
        proj_roots = {}
        for storage_name in self._roots:
            # join the project name to the storage ShotgunPath
            project_path = self._roots[storage_name].join(self._project_name)
            # break out the ShotgunPath object in sys.platform style dict
            proj_roots[storage_name] = project_path.current_os

        return proj_roots

    def has_associated_data_roots(self):
        """
        Some configurations do not have a notion of a project storage and therefore
        do not have any storages defined. This flag indicates whether a configuration 
        has any associated data storages. 
        
        :returns: true if the configuration has a primary data root defined, false if not
        """
        return len(self.get_data_roots()) > 0
        
    def get_primary_data_root(self):
        """
        Returns the path to the primary data root for the current platform.
        For configurations where there is no roots defined at all, 
        an exception will be raised.
        
        :returns: str to local path on disk
        """
        if len(self.get_data_roots()) == 0:
            raise TankError("Your current pipeline configuration does not have any project data "
                            "storages defined and therefore does not have a primary project data root!")
         
        return self.get_data_roots().get(constants.PRIMARY_STORAGE_NAME)

    ########################################################################################
    # installation payload (core/apps/engines) disk locations

    def get_associated_core_version(self):
        """
        Returns the version string for the core api associated with this config.
        This method is 'forgiving' and in the case no associated core API can be 
        found for this pipeline configuration, None will be returned rather than 
        an exception raised. 

        :returns: version str e.g. 'v1.2.3', None if no version could be determined. 
        """
        associated_api_root = self.get_install_location()
        return pipelineconfig_utils.get_core_api_version(associated_api_root)

    def get_install_location(self):
        """
        Returns the core api install location associated with this pipeline configuration.

        Tries to resolve it via the explicit link which exists between
        the pipeline config and the its core. If this fails, it uses
        runtime introspection to resolve it.
        
        :returns: path string to the current core API install root location
        """
        core_api_root = pipelineconfig_utils.get_core_path_for_config(self._pc_root)

        if core_api_root is None:
            # lookup failed. fall back onto runtime introspection
            core_api_root = pipelineconfig_utils.get_path_to_current_core()
        
        return core_api_root

    def get_core_python_location(self):
        """
        Returns the python root for this install.
        
        :returns: path string
        """
        return os.path.join(self.get_install_location(), "install", "core", "python")

    ########################################################################################
    # descriptors and locations

    def execute_post_install_bundle_hook(self, bundle_path):
        """
        Executes a post install hook for a bundle.
        Some bundles come with an associated script that is meant
        to be executed after install. This method probes for such a script
        and in case it exists, executes it.

        :param bundle_path: Path to bundle (app/engine/framework)
        """
        post_install_hook_path = os.path.join(
            bundle_path,
            "hooks",
            constants.BUNDLE_POST_INSTALL_HOOK)

        if os.path.exists(post_install_hook_path):
            hook.execute_hook(
                post_install_hook_path,
                parent=None,
                pipeline_configuration=self.get_path(),
                path=bundle_path
            )

    def _preprocess_descriptor(self, descriptor_dict):
        """
        Preprocess descriptor dictionary to resolve config-specific
        constants and directives such as {PIPELINE_CONFIG}.

        :param descriptor_dict: Descriptor dict to operate on
        :returns: Descriptor dict with any directives resolved.
        """

        if descriptor_dict.get("type") == "dev":
            # several different path parameters are supported by the dev descriptor.
            # scan through all path keys and look for pipeline config token

            # platform specific resolve
            platform_key = ShotgunPath.get_shotgun_storage_key()
            if platform_key in descriptor_dict:
                descriptor_dict[platform_key] = descriptor_dict[platform_key].replace(
                    constants.PIPELINE_CONFIG_DEV_DESCRIPTOR_TOKEN,
                    self.get_path()
                )

            # local path resolve
            if "path" in descriptor_dict:
                descriptor_dict["path"] = descriptor_dict["path"].replace(
                    constants.PIPELINE_CONFIG_DEV_DESCRIPTOR_TOKEN,
                    self.get_path()
                )

        return descriptor_dict

    def _get_descriptor(self, descriptor_type, dict_or_uri, latest=False, constraint_pattern=None):
        """
        Constructs a descriptor object given a descriptor dictionary.

        :param descriptor_type: Descriptor type (APP, ENGINE, etc)
        :param dict_or_uri: Descriptor dict or uri
        :param latest: Resolve latest version of descriptor. This
                       typically requires some sort of remote lookup and may error
                       if the machine is not connected to the Internet.
        :param constraint_pattern: If resolve_latest is True, this pattern can be used to constrain
                               the search for latest to only take part over a subset of versions.
                               This is a string that can be on the following form:
                                    - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                                    - v0.12.x - get the highest v0.12 version
                                    - v1.x.x - get the highest v1 version
        :returns: Descriptor object
        """

        # note: certain legacy methods, for example how shotgun menu actions are cached
        # from the tank command, are not authenticated pathways. This is something we
        # ultimately need to more away from, ensuring that the system is fully authenticated
        # across the board. However, in the meantime, ensure that *basic* descriptor operations can
        # be accessed without having a valid shotgun connection by using a deferred shotgun API wrapper
        # rather than a wrapper that is initialized straight away. This ensures that a valid authentication
        # state in toolkit is not required until the connection is actually needed. In the case of descriptors,
        # a connection is typically only needed at download and when checking for latest. Path resolution
        # methods do not require a connection.
        sg_connection = shotgun.get_deferred_sg_connection()

        if isinstance(dict_or_uri, basestring):
            descriptor_dict = descriptor_uri_to_dict(dict_or_uri)
        else:
            descriptor_dict = dict_or_uri

        descriptor_dict = self._preprocess_descriptor(descriptor_dict)

        desc = create_descriptor(
            sg_connection,
            descriptor_type,
            descriptor_dict,
            self._bundle_cache_root_override,
            self._bundle_cache_fallback_paths,
            latest,
            constraint_pattern
        )

        return desc

    def get_app_descriptor(self, dict_or_uri):
        """
        Convenience method that returns a descriptor for the app
        that is associated with the given descriptor.
        
        :param dict_or_uri: Descriptor dictionary or uri
        :returns:           Descriptor object
        """
        return self._get_descriptor(Descriptor.APP, dict_or_uri)

    def get_engine_descriptor(self, dict_or_uri):
        """
        Convenience method that returns a descriptor for the engine
        that is associated with the given descriptor.
        
        :param dict_or_uri: Descriptor dictionary or uri
        :returns:        Descriptor object
        """
        return self._get_descriptor(Descriptor.ENGINE, dict_or_uri)

    def get_framework_descriptor(self, dict_or_uri):
        """
        Convenience method that returns a descriptor for the framework
        that is associated with the given descriptor.
        
        :param dict_or_uri: Descriptor dictionary or uri
        :returns:        Descriptor object
        """
        return self._get_descriptor(Descriptor.FRAMEWORK, dict_or_uri)

    def get_latest_app_descriptor(self, dict_or_uri):
        """
        Convenience method that returns the latest descriptor for the
        given app. The descriptor dictionary or uri does not have to contain
        any version information. This will be resolved as part of the call.
        Please note that this call may be slow as it will typically connect
        to an external source (git, toolkit app store etc) in order to determine
        which the most recent version is.

        :param dict_or_uri: Descriptor dictionary or uri
        :returns:           Descriptor object
        """
        return self._get_descriptor(Descriptor.APP, dict_or_uri, latest=True)

    def get_latest_engine_descriptor(self, dict_or_uri):
        """
        Convenience method that returns the latest descriptor for the
        given engine. The descriptor dictionary or uri does not have to contain
        any version information. This will be resolved as part of the call.
        Please note that this call may be slow as it will typically connect
        to an external source (git, toolkit app store etc) in order to determine
        which the most recent version is.

        :param dict_or_uri: Descriptor dictionary or uri
        :returns:        Descriptor object
        """
        return self._get_descriptor(Descriptor.ENGINE, dict_or_uri, latest=True)

    def get_latest_framework_descriptor(self, dict_or_uri, constraint_pattern=None):
        """
        Convenience method that returns the latest descriptor for the
        given framework. The descriptor dictionary or uri does not have to contain
        any version information. This will be resolved as part of the call.
        Please note that this call may be slow as it will typically connect
        to an external source (git, toolkit app store etc) in order to determine
        which the most recent version is.

        :param dict_or_uri: Descriptor dictionary or uri
        :param constraint_pattern: This pattern can be used to constrain
                                   the search for latest to only take part over a subset of versions.
                                   This is a string that can be on the following form:
                                        - v0.1.2, v0.12.3.2, v0.1.3beta - a specific version
                                        - v0.12.x - get the highest v0.12 version
                                        - v1.x.x - get the highest v1 version
        :returns:        Descriptor object
        """
        return self._get_descriptor(
            Descriptor.FRAMEWORK,
            dict_or_uri,
            latest=True,
            constraint_pattern=constraint_pattern
        )

    def get_configuration_descriptor(self):
        """
        Returns the :class:`~sgtk.descriptor.ConfigDescriptor` associated with
        the pipeline configuration.
        """
        return self._descriptor

    ########################################################################################
    # configuration disk locations

    def get_core_hooks_location(self):
        """
        Returns the path to the core hooks location
        
        :returns: path string
        """
        return os.path.join(self._pc_root, "config", "core", "hooks")

    def get_schema_config_location(self):
        """
        Returns the location of the folder schema
        
        :returns: path string
        """
        return os.path.join(self._pc_root, "config", "core", "schema")

    def get_config_location(self):
        """
        Returns the config folder for the project
        
        :returns: path string
        """
        return os.path.join(self._pc_root, "config")

    def get_hooks_location(self):
        """
        Returns the hooks folder for the project
        
        :returns: path string
        """
        return os.path.join(self._pc_root, "config", "hooks")

    def get_shotgun_menu_cache_location(self):
        """
        returns the folder where shotgun menu cache files 
        (used by the browser plugin and java applet) are stored.
        
        :returns: path string
        """
        return os.path.join(self._pc_root, "cache")

    ########################################################################################
    # configuration data access

    def get_environments(self):
        """
        Returns a list with all the environments in this configuration.
        """
        env_root = os.path.join(self._pc_root, "config", "env")
        env_names = []
        for f in glob.glob(os.path.join(env_root, "*.yml")):
            file_name = os.path.basename(f)
            (name, _) = os.path.splitext(file_name)
            env_names.append(name)
        return env_names

    def get_environment(self, env_name, context=None, writable=False):
        """
        Returns an environment object given an environment name.
        You can use the get_environments() method to get a list of
        all the environment names.
        
        :param env_name:    name of the environment to load
        :param context:     context to seed the environment with
        :param writable:    If true, a writable environment object will be 
                            returned, allowing a user to update it.
        :returns:           An environment object
        """        
        env_file = self.get_environment_path(env_name)
        EnvClass = WritableEnvironment if writable else InstalledEnvironment
        env_obj = EnvClass(env_file, self, context)
        return env_obj

    def get_environment_path(self, env_name):
        """
        Returns the path to the environment yaml file for the given
        environment name for this pipeline configuration.

        :param env_name:    The name of the environment.
        :returns:           String path to the environment yaml file.
        """
        return os.path.join(self._pc_root, "config", "env", "%s.yml" % env_name)
    
    def get_templates_config(self):
        """
        Returns the templates configuration as an object
        """
        templates_file = os.path.join(
            self._pc_root,
            "config",
            "core",
            constants.CONTENT_TEMPLATES_FILE,
        )

        try:
            data = yaml_cache.g_yaml_cache.get(templates_file, deepcopy_data=False) or {}
            data = template_includes.process_includes(templates_file, data)
        except TankUnreadableFileError:
            data = dict()

        return data

    ########################################################################################
    # helpers and internal

    def execute_core_hook_internal(self, hook_name, parent, **kwargs):
        """
        Executes an old-style core hook, passing it any keyword arguments supplied.
        
        Typically you don't want to execute this method but instead
        the tk.execute_core_hook method. Only use this one if you for 
        some reason do not have a tk object available.

        :param hook_name: Name of hook to execute.
        :param parent: Parent object to pass down to the hook
        :param **kwargs: Named arguments to pass to the hook
        :returns: Return value of the hook.
        """
        # first look for the hook in the pipeline configuration
        # if it does not exist, fall back onto core API default implementation.
        hook_folder = self.get_core_hooks_location()
        file_name = "%s.py" % hook_name
        hook_path = os.path.join(hook_folder, file_name)
        if not os.path.exists(hook_path):
            # no custom hook detected in the pipeline configuration
            # fall back on the hooks that come with the currently running version
            # of the core API.
            hooks_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
            hook_path = os.path.join(hooks_path, file_name)
        else:
            # some hooks are always custom. ignore those and log the rest.
            if (hasattr(parent, "log_metric") and
               hook_name not in constants.TANK_LOG_METRICS_CUSTOM_HOOK_BLACKLIST):

                # only log once since some custom hooks can be called many times
                action = "custom hook %s" % (hook_name,)
                parent.log_metric(action, log_once=True)

        try:
            return_value = hook.execute_hook(hook_path, parent, **kwargs)
        except:
            # log the full callstack to make sure that whatever the
            # calling code is doing, this error is logged to help
            # with troubleshooting and support
            log.exception("Exception raised while executing hook '%s'" % hook_path)
            raise

        return return_value

    def execute_core_hook_method_internal(self, hook_name, method_name, parent, **kwargs):
        """
        Executes a new style core hook, passing it any keyword arguments supplied.
        
        Typically you don't want to execute this method but instead
        the tk.execute_core_hook method. Only use this one if you for 
        some reason do not have a tk object available.

        :param hook_name: Name of hook to execute.
        :param method_name: Name of hook method to execute
        :param parent: Parent object to pass down to the hook
        :param **kwargs: Named arguments to pass to the hook
        :returns: Return value of the hook.
        """
        # this is a new style hook which supports an inheritance chain
        
        # first add the built-in core hook to the chain
        file_name = "%s.py" % hook_name
        hooks_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "hooks"))
        hook_paths = [os.path.join(hooks_path, file_name)]

        # the hook.method display name used when logging the metric
        hook_method_display = "%s.%s" % (hook_name, method_name)
        
        # now add a custom hook if that exists.
        hook_folder = self.get_core_hooks_location()        
        hook_path = os.path.join(hook_folder, file_name)
        if os.path.exists(hook_path):
            hook_paths.append(hook_path)
            if (hasattr(parent, 'log_metric') and
               hook_name not in constants.TANK_LOG_METRICS_CUSTOM_HOOK_BLACKLIST):

                # only log once since some custom hooks can be called many
                # times like cache_location.get_path_cache_path
                action = "custom hook method %s" % (hook_method_display,)
                parent.log_metric(action, log_once=True)

        try:
            return_value = hook.execute_hook_method(hook_paths, parent, method_name, **kwargs)
        except:
            # log the full callstack to make sure that whatever the
            # calling code is doing, this error is logged to help
            # with troubleshooting and support
            log.exception("Exception raised while executing hook '%s'" % hook_paths[-1])
            raise

        return return_value


