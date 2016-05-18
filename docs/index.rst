Shotgun Pipeline Toolkit Core Reference, |release|
####################################################

Welcome to the Shotgun pipeline Toolkit developer and reference documentation.
Below you will find a detailed technical reference of all Toolkit Core APIs as well
as information useful for developers and engineers.

**Who is this documentation for?**

This documentation is intended for **Software Engineers or TDs** who
are either developing Toolkit Apps/Engines or doing advanced integration
of Toolkit into their pipeline and workflows.

**Accessing the Toolkit Core API**

As with all APIs, the Toolkit Core API is a combination of public interfaces
and internal logic. We refactor and evolve the Toolkit Core code on a regular
basis and this sometimes changes to the internal structure of the code.
We  recommend only accessing Toolkit via the methods
documented in this API reference. These form the official Toolkit Core API
and will always remain backwards compatible.

As a general rule, each package in the sgtk core API imports its
full public interface. This is to provide a cleaner interface and
make refactoring easier. We therefore recommend importing from the
package level whenever possible::

    # recommended and documented API access
    from sgtk.authentication import ShotgunAuthenticator

    # we recommend *avoiding* deeper, module level imports
    from sgtk.authentication.shotgun_authenticator import ShotgunAuthenticator




API Reference table of contents
----------------------------------------

.. toctree::
    :maxdepth: 2


    bootstrap
    core
    platform
    utils
    descriptor
    authentication

