
from tank.authentication.ui.qt_abstraction import QtGui

from tank.authentication.login_dialog import LoginDialog

QtGui.QApplication([])

dlg = LoginDialog(
    is_session_renewal=False,
    hostname=None,
    login=None,
    http_proxy=None,
    fixed_host=False,
)

dlg.result()
