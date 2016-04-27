.. currentmodule:: sgtk.descriptor

Descriptor API
########################################

Descriptors are used to describe a location of code or configuration.
They are used extensively by toolkit and allow a user to configure and drive
toolkit in a flexible fashion. Descriptors usually point at a remote location
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
    required_core_uri = desc.get_associated_core_descriptor()

When descriptors serialized, they can have two different forms:

- A descriptor URI is a compact string representation, for example
 ``sgtk:descriptor:app_store?name=tk-config-default&version=v1.2.3``

- A descriptor dictionary contains the equivalent information in key-value pair form::

    {
        "type": "app_store",
        "version": "v1.2.3",
        "name": "tk-config-default"
    }

Several different descriptor types are supported by Toolkit:

- An **App Store** descriptor represents an item in the Toolkit App Store
- A **Shotgun** descriptor represents an item stored in Shotgun
- A **git** descriptor represents a tag in a git repository
- A **git_branch** descriptor represents a commit in a git branch
- A **path** descriptor represents a location on disk
- A **dev** descriptor represents a developer sandbox

The descriptor API knows how to access and locally cache each of the types above.
You can control the location where the API caches items and supply additional lookup
locations if you want to pre-bake your own collection of caches.


Descriptor resolve and management
----------------------------------------

.. autofunction:: create_descriptor
.. autofunction:: descriptor_dict_to_uri
.. autofunction:: descriptor_uri_to_dict


Descriptor Classes
----------------------------------------

.. autoclass:: AppDescriptor
    :inherited-members:
    :members:

.. autoclass:: EngineDescriptor
    :inherited-members:
    :members:

.. autoclass:: FrameworkDescriptor
    :inherited-members:
    :members:

.. autoclass:: ConfigDescriptor
    :inherited-members:
    :members:

.. autoclass:: CoreDescriptor
    :inherited-members:
    :members:

Descriptor Exceptions
----------------------------------------

.. autoclass:: TankAppStoreConnectionError
.. autoclass:: TankAppStoreError
.. autoclass:: TankDescriptorError
