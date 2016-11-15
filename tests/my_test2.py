#!/Applications/Shotgun.app/Contents/Frameworks/Python/bin/python

# Import Toolkit so we can access to Toolkit specific features.
from PySide import QtGui, QtCore, QtWebKit
import atexit
import sgtk
import time

sgtk.LogManager().initialize_base_file_handler("patate")


# Import the ShotgunAuthenticator from the tank_vendor.shotgun_authentication
# module. This class allows you to authenticate either programmatically or, in this # noqa
# case, interactively.
from tank_vendor.shotgun_authentication import ShotgunAuthenticator
from tank.authentication import interactive_authentication

# Instantiate the CoreDefaultsManager. This allows the ShotgunAuthenticator to
# retrieve the site, proxy and optional script_user credentials from shotgun.yml # noqa
# cdm = sgtk.util.CoreDefaultsManager()

# Instantiate the authenticator object, passing in the defaults manager.
# authenticator = ShotgunAuthenticator(cdm)
authenticator = ShotgunAuthenticator()

# Optionally clear the current user if you've already logged in before.
authenticator.clear_default_user()

def shutdown():
    print "Exiting"
    authenticator.clear_default_user()

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

def renew_session():
    if (time.time() + 15) > user.impl.get_session_expiration():
        print "Renewing session"
        interactive_authentication.renew_session(user.impl, no_gui=True)
        print "Renewing session completed"

global_count = 0
def print_stuff():
    global global_count
    global_count += 1

    # Calling the Shotgun API
    last_stamp = int(time.time())
    sg.find('Project', [], ['id', 'name'])
    new_stamp = int(time.time())

    print "=> %d = %d" % (global_count, new_stamp - last_stamp)

if __name__ == '__main__':
    view = QtWebKit.QWebView()
    frame = view.page().mainFrame()

    view.load('https://google.com')
    view.show()
    app.view = view

    # timer1 = QtCore.QTimer()
    # timer1.timeout.connect(renew_session)
    # timer1.start(6000)

    timer2 = QtCore.QTimer()
    timer2.timeout.connect(print_stuff)
    timer2.start(500)


    app.exec_()

