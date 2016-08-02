.. currentmodule:: sgtk.descriptor

Descriptor API
########################################

Descriptors are used to describe a location of code or configuration.
They are used extensively by Toolkit and allow a user to configure and drive
Toolkit in a flexible fashion. Descriptors usually point at a remote location
and makes it easy to handle code transport from that location into a local cache.
Descriptors form the backbone for Shotgun deployment and installation. The following
example shows basic usage::

    import sgtk
    from sgtk.descriptor import Descriptor

    # first, authenticate our user
    sg_auth = sgtk.authentication.ShotgunAuthenticator()
    user = sg_auth.get_user()
    sg = user.create_sg_connection()

    # we are fetching v1.2.3 of the default config from the app store
    uri = "sgtk:descriptor:app_store?name=tk-config-default&version=v1.2.3"

    # create object
    desc = sgtk.descriptor.create_descriptor(sg, Descriptor.CONFIG, uri)

    # make sure this is cached locally on disk
    desc.ensure_local()

    # check if it is the latest version
    latest_desc = desc.find_latest_version()

    # see what core is needed for this config
    required_core_uri = desc.associated_core_descriptor

When descriptors serialized, they can have two different forms:

- A descriptor URI is a compact string representation, for example
  ``sgtk:descriptor:app_store?name=tk-config-default&version=v1.2.3``

- A descriptor dictionary contains the equivalent information in key-value pair form::

    {
        "type": "app_store",
        "version": "v1.2.3",
        "name": "tk-config-default"
    }

When a the payload of a descriptor is downloaded, it ends up by default in the *global bundle cache*.

.. note:: The global bundle cache can be found in the following locations:

    - Macosx: ``~/Library/Caches/Shotgun/bundle_cache``
    - Windows: ``%APPDATA%\Shotgun\Caches\bundle_cache``
    - Linux: ``~/.shotgun/caches/bundle_cache``

    Unless specified otherwise, this is the location where descriptors will be
    cached locally.

    Older versions of Toolkit Core (prior to v0.18) used to maintain a bundle cache
    in an ``install`` folder inside the pipeline configuration location.

In addition to the location above, you can specify additional folders where the
descriptor API will go and look for cached items. This is useful if you want to
pre-cache an environment for your studio or distribute a set of app and engine
versions as an installable package that require no further retrieval in order
to function.

Descriptor types
----------------------------------------

Several different descriptor types are supported by Toolkit:


- An **app_store** descriptor represents an item in the Toolkit App Store
- A **shotgun** descriptor represents an item stored in Shotgun
- A **git** descriptor represents a tag in a git repo sitory
- A **git_branch** descriptor represents a commit in a git branch
- A **path** descriptor represents a location on disk
- A **dev** descriptor represents a developer sandbox
- A **manual** descriptor gives raw access to the bundle caching structure

The descriptor API knows how to access and locally cache each of the types above.
You can control the location where the API caches items and supply additional lookup
locations if you want to pre-bake your own collection of caches.

App store
============

The Toolkit app store is used to release and distribute versions of Apps, Engines, Configs etc. that have been
tested and approved by Shotgun. App store descriptors should include a name and version token and
are on the following form::

    { type: app_store, name: tk-core, version: v12.3.4 }

Shotgun
============

Represents a Shotgun entity to which a payload has been attached.
This can be an attachment field on any entity. Typically it will be
a pipeline configuration. In that configuration, the descriptor represents
a 'cloud based configuration'. It could also be a custom entity or non-project
entity in the case you want to store a descriptor (app, engine or config)
that can be easily accessed from any project::

    {
        type: shotgun,
        entity_type: PipelineConfiguration,  # entity type
        name: primary,                       # name of the record in shotgun (e.g. 'code' field)
        project_id: 123,                     # optional project id. If omitted, name is assumed to be unique.
        field: sg_config,                    # attachment field where payload can be found
        version: 456                         # attachment id of particular attachment
    }

When the attachment field is updated, the attachment id (e.g. version field in the descriptor) changes, resulting in
a new descriptor. This can be used to determine the latest version for a Shotgun attachment descriptor.

Git and Git branch
=======================

The ``git`` descriptor type is used to track git tags and typically used when you are tracking released
versions of something. You can use any syntax that git supports, with a path key containing the path
to the git repository::

    {type: git, path: /path/to/repo.git, version: v0.2.1}

    {type: git, path: user@remotehost:/path_to/repo.git, version: v0.1.0}

    {type: git, path: git://github.com/user/tk-multi-publish.git, version: v0.1.0}

    {type: git, path: https://github.com/user/tk-multi-publish.git, version: v0.1.0}

The latest version for a descriptor is determined by retrieving the list of tags for
the repository and comparing the version numbers in order to determine the highest one.
For this comparison, :py:class:`~distutils.version.LooseVersion` is used and we recommend
that version numbers follow the semantic versioning standard that can be found at http://semver.org.

The ``git_branch`` descriptor type is typically used during development and allows you to track
a commit in a particular branch::

    {type: git_branch, branch: master, path: /path/to/repo.git, version: 17fedd8}

    {type: git_branch, branch: master, path: user@remotehost:/path_to/repo.git, version: 17fedd8}

    {type: git_branch, branch: master, path: git://github.com/user/tk-multi-publish.git, version: 17fedd8}

    {type: git_branch, branch: master, path: https://github.com/user/tk-multi-publish.git, version: 17fedd8}

You can use both long and short hash formats for the version token. The latest version for a git_branch
descriptor is defined as the most recent commit for a given branch.

As shown in the examples above, the git descriptors handle both local and remote repositories.
They also handle private repositories in github, assuming that you have set up your ssh authentication
correctly. On Windows, it is recommended that you use forward slashes.

.. Note:: When using the git descriptor, you need to have the git executable in
          the ``PATH`` in order for the API to be able to do a latest check or
          app download. The git executable is, however, not needed during descriptor
          resolve and normal operation.


Path and Dev
=======================

Pointing Sgtk to an app that resides in the local file system is typically something you do when you do
development. This is when you use the ``dev`` descriptor::

    {
        type: dev,
        path: /path/to/app
    }

    {
        type: dev,
        path: ${HOME}/path/to/app
    }

    {
        type: dev,
        path: ~/path/to/app
    }

    {
        type: dev,
        windows_path: c:\path\to\app,
        linux_path: /path/to/app,
        mac_path: /path/to/app
    }

.. note:: The path and dev descriptors support environment variable resolution on the form ``${MYENVVAR}``
          as well as user directory resolution if the path starts with `~`.

Sometimes it can be handy to organize your development sandbox relative to a pipeline configuration.
If all developers in the studio share a convention where they for example have a ``dev`` folder inside
their pipeline configuration dev sandboxes, it becomes easy to exchange environment configs.
You can achieve this by using the special token ``{PIPELINE_CONFIG}`` which will resolve into the
local path to the pipeline configuration::

    {"type": "dev", "path": "{PIPELINE_CONFIG}/dev/tk-nuke-myapp"}

Since Sgtk does not know what version of the app is being run, it will return ``Undefined`` for
an app referenced using the dev type. Sometimes, especially when doing framework development,
it can be useful to be able to specify a version number. In that case, you can specify
a specific version number and Toolkit will associate this version number with the app::


    {"type": "dev", "path": "/path/to/app", "version": "v0.2.1"}


If you needed to point Toolkit at a path, but intend to use the setup for non-dev purposes, use a ``path``
descriptor rather than a dev descriptor. These have identical syntax.



Manual
=======================

Toolkit also provides a ``manual`` mode to make it easy to manage production installations of apps
and engines without any automation. When you use the manual descriptor, it is up to you to install the code in the right
location and no automated update checks will ever take place. The manual mode uses the following syntax::

    {"type": "manual", "name": "tk-nuke-publish", "version": "v0.5.0"}


It will look for the code in a `manual` folder in the bundle cache, so with the example above, Toolkit would look
for the code in the ``CACHE_ROOT/manual/tk-nuke-publish/v0.5.0`` folder.


API reference
----------------------------------------

Factory Methods
================================================

.. autofunction:: create_descriptor
.. autofunction:: descriptor_dict_to_uri
.. autofunction:: descriptor_uri_to_dict


AppDescriptor
================================================

.. autoclass:: AppDescriptor
    :inherited-members:
    :members:

EngineDescriptor
================================================

.. autoclass:: EngineDescriptor
    :inherited-members:
    :members:

FrameworkDescriptor
================================================

.. autoclass:: FrameworkDescriptor
    :inherited-members:
    :members:

ConfigDescriptor
================================================

.. autoclass:: ConfigDescriptor
    :inherited-members:
    :members:

CoreDescriptor
================================================

.. autoclass:: CoreDescriptor
    :inherited-members:
    :members:

Exceptions
================================================

.. autoclass:: TankAppStoreConnectionError
.. autoclass:: TankAppStoreError
.. autoclass:: TankDescriptorError
