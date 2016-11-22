#!/Applications/Shotgun.app/Contents/Frameworks/Python/bin/python
"""TBD."""

# Import Toolkit so we can access to Toolkit specific features.
from PySide import QtGui

# Import the ShotgunAuthenticator from the tank_vendor.shotgun_authentication
# module. This class allows you to authenticate either programmatically or, in this # noqa
# case, interactively.
from tank_vendor.shotgun_authentication import ShotgunAuthenticator
# from tank.authentication import interactive_authentication

# import sgtk
# import logging
# log = logging.getLogger('patate')
# loglevel = logging.DEBUG
# log.setLevel(loglevel)
# log_handler = logging.StreamHandler()
# log.addHandler(log_handler)

# sgtk.LogManager().initialize_base_file_handler("rv-patate")
# sgtk.LogManager().initialize_custom_handler(log_handler)
# log_handler.setLevel(loglevel)

# Instantiate the CoreDefaultsManager. This allows the ShotgunAuthenticator to
# retrieve the site, proxy and optional script_user credentials from shotgun.yml # noqa
# cdm = sgtk.util.CoreDefaultsManager()

# Instantiate the authenticator object, passing in the defaults manager.
# authenticator = ShotgunAuthenticator(cdm)
authenticator = ShotgunAuthenticator()

authenticator.clear_default_user()
app = QtGui.QApplication([])
user = authenticator.get_user()
print "User is '%s'" % user

defaultUser = authenticator.get_default_user()
print "DefaultUser is '%s'" % defaultUser

# # Tells Toolkit which user to use for connecting to Shotgun. Note that this should # noqa
# # always take place before creating a Sgtk instance.
# sgtk.set_authenticated_user(user)


authenticator.clear_default_user()
