# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'login_dialog.ui'
#
#      by: pyside-uic 0.2.15 running on PySide 1.2.2
#
# WARNING! All changes made in this file will be lost!

from .qt_abstraction import QtCore, QtGui

class Ui_LoginDialog(object):
    def setupUi(self, LoginDialog):
        LoginDialog.setObjectName("LoginDialog")
        LoginDialog.setWindowModality(QtCore.Qt.NonModal)
        LoginDialog.resize(374, 324)
        LoginDialog.setStyleSheet("QWidget\n"
"{\n"
"    background-color:  rgb(36, 39, 42);\n"
"    color: rgb(192, 193, 195);\n"
"    selection-background-color: rgb(168, 123, 43);\n"
"    selection-color: rgb(230, 230, 230);\n"
"    font-size: 11px;\n"
"}\n"
"\n"
"QPushButton\n"
"{\n"
"    background-color: transparent;\n"
"    border-radius: 2px;\n"
"    padding: 8px;\n"
"    padding-left: 15px;\n"
"    padding-right: 15px;\n"
"}\n"
"\n"
"QLineEdit\n"
"{\n"
"    background-color: rgb(29, 31, 34);\n"
"    border: 1px solid rgb(54, 60, 66);\n"
"    border-radius: 2px;\n"
"    padding: 5px;\n"
"    font-size: 12px;\n"
"}\n"
"\n"
"QLineEdit:focus\n"
"{\n"
"    border: 1px solid rgb(48, 167, 227);\n"
"\n"
"}")
        LoginDialog.setModal(True)
        self.verticalLayout_2 = QtGui.QVBoxLayout(LoginDialog)
        self.verticalLayout_2.setContentsMargins(20, 20, 20, 20)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setSizeConstraint(QtGui.QLayout.SetMinAndMaxSize)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.logo = AspectPreservingLabel(LoginDialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.logo.sizePolicy().hasHeightForWidth())
        self.logo.setSizePolicy(sizePolicy)
        self.logo.setMaximumSize(QtCore.QSize(250, 150))
        self.logo.setText("")
        self.logo.setAlignment(QtCore.Qt.AlignCenter)
        self.logo.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        self.logo.setObjectName("logo")
        self.horizontalLayout.addWidget(self.logo)
        self.verticalLayout_2.addLayout(self.horizontalLayout)
        self.site = QtGui.QLineEdit(LoginDialog)
        self.site.setMinimumSize(QtCore.QSize(308, 0))
        self.site.setObjectName("site")
        self.verticalLayout_2.addWidget(self.site)
        self.login = QtGui.QLineEdit(LoginDialog)
        self.login.setMinimumSize(QtCore.QSize(308, 0))
        self.login.setObjectName("login")
        self.verticalLayout_2.addWidget(self.login)
        self.password = QtGui.QLineEdit(LoginDialog)
        self.password.setMinimumSize(QtCore.QSize(308, 0))
        self.password.setEchoMode(QtGui.QLineEdit.Password)
        self.password.setObjectName("password")
        self.verticalLayout_2.addWidget(self.password)
        self.message = QtGui.QLabel(LoginDialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.message.sizePolicy().hasHeightForWidth())
        self.message.setSizePolicy(sizePolicy)
        self.message.setText("")
        self.message.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.message.setWordWrap(True)
        self.message.setMargin(4)
        self.message.setObjectName("message")
        self.verticalLayout_2.addWidget(self.message)
        self.button_layout = QtGui.QHBoxLayout()
        self.button_layout.setSpacing(10)
        self.button_layout.setContentsMargins(5, -1, -1, -1)
        self.button_layout.setObjectName("button_layout")
        spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.button_layout.addItem(spacerItem)
        self.cancel = QtGui.QPushButton(LoginDialog)
        self.cancel.setStyleSheet("")
        self.cancel.setAutoDefault(False)
        self.cancel.setFlat(True)
        self.cancel.setObjectName("cancel")
        self.button_layout.addWidget(self.cancel)
        self.sign_in = QtGui.QPushButton(LoginDialog)
        self.sign_in.setStyleSheet("color: rgb(248, 248, 248);\n"
"background-color: rgb(35, 165, 225);")
        self.sign_in.setAutoDefault(False)
        self.sign_in.setDefault(True)
        self.sign_in.setFlat(True)
        self.sign_in.setObjectName("sign_in")
        self.button_layout.addWidget(self.sign_in)
        self.button_layout.setStretch(0, 1)
        self.verticalLayout_2.addLayout(self.button_layout)
        self.verticalLayout_2.setStretch(0, 1)

        self.retranslateUi(LoginDialog)
        QtCore.QMetaObject.connectSlotsByName(LoginDialog)

    def retranslateUi(self, LoginDialog):
        self.site.setPlaceholderText(QtGui.QApplication.translate("LoginDialog", "example.shotgunstudio.com", None, QtGui.QApplication.UnicodeUTF8))
        self.login.setPlaceholderText(QtGui.QApplication.translate("LoginDialog", "login", None, QtGui.QApplication.UnicodeUTF8))
        self.password.setPlaceholderText(QtGui.QApplication.translate("LoginDialog", "password", None, QtGui.QApplication.UnicodeUTF8))
        self.cancel.setText(QtGui.QApplication.translate("LoginDialog", "Cancel", None, QtGui.QApplication.UnicodeUTF8))
        self.sign_in.setText(QtGui.QApplication.translate("LoginDialog", "Sign In", None, QtGui.QApplication.UnicodeUTF8))

from .aspect_preserving_label import AspectPreservingLabel
from . import resources_rc
