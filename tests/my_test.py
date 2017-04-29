#!/Applications/Shotgun.app/Contents/Frameworks/Python/bin/python

"""My test file"""

# Import Toolkit so we can access to Toolkit specific features.
from PySide import QtGui
import atexit
import sgtk
import time

# Import the ShotgunAuthenticator from the tank_vendor.shotgun_authentication
# module. This class allows you to authenticate either programmatically or, in this # noqa
# case, interactively.
from tank_vendor.shotgun_authentication import ShotgunAuthenticator
from tank.authentication import interactive_authentication

# sgtk.LogManager().initialize_base_file_handler('my_script')
# sgtk.LogManager().initialize_custom_handler()
# sgtk.LogManager().global_debug = True

# Instantiate the CoreDefaultsManager. This allows the ShotgunAuthenticator to
# retrieve the site, proxy and optional script_user credentials from shotgun.yml # noqa
# cdm = sgtk.util.CoreDefaultsManager()

# Instantiate the authenticator object, passing in the defaults manager.
# authenticator = ShotgunAuthenticator(cdm)
authenticator = ShotgunAuthenticator()


# Optionally clear the current user if you've already logged in before.
# authenticator.clear_default_user()
def shutdown():
    """TBD."""
    print "Exiting"
    # authenticator.clear_default_user()


# Get an authenticated user. In this scenario, since we've passed in the
# CoreDefaultsManager, the code will first look to see if there is a script_user inside # noqa
# shotgun.yml. If there isn't, the user will be prompted for their username,
# password and optional 2-factor authentication code. If a QApplication is
# available, a UI will pop-up. If not, the credentials will be prompted
# on the command line. The user object returned encapsulates the login
# information.
atexit.register(shutdown)
app = QtGui.QApplication([])
user = authenticator.get_user()
# print "User is '%s'" % user

# Tells Toolkit which user to use for connecting to Shotgun. Note that this should # noqa
# always take place before creating a Sgtk instance.
sgtk.set_authenticated_user(user)

sg = user.create_sg_connection()
# print sg.find('Project', [], ['id', 'name'])
start_stamp = last_stamp = float(time.time())
for i in range(1, 501):
    new_stamp = float(time.time())
    delta = new_stamp - last_stamp
    last_stamp = new_stamp
    saml_expiration = user.impl.get_saml_expiration()
    print "-----> %d - %d - %d - %.3f" % (i, saml_expiration, saml_expiration - time.time(), delta)

    # if time.time() + 18 > user.impl.get_saml_claims_expiration():
    #     print "------- renewing session"
    #     interactive_authentication.renew_session(user.impl)
    # interactive_authentication.renew_session(user.impl)

    print "------- Before sg call"
    sg.find('Project', [], ['id', 'name'])
    # print "------- Before sleep"
    time.sleep(4)

print "Total: %d" % (last_stamp - start_stamp)

#
# Add your app code goes here...
#
# When you are done, you could optionally clear the current user. Doing so
# however, means that the next time the script is run, the user will be prompted # noqa
# for his or her credentials again. You should probably avoid doing this in
# order to provide a user experience that is as frictionless as possible.
# authenticator.clear_default_user()
