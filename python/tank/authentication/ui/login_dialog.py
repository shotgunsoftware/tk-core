# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'login_dialog.ui'
##
## Created by: Qt User Interface Compiler version 5.15.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from .qt_abstraction import QtCore
from .qt_abstraction import QtGui


from .qt5_like_line_edit import Qt5LikeLineEdit
from .recent_box import RecentBox
from .aspect_preserving_label import AspectPreservingLabel

from . import resources_rc

class Ui_LoginDialog(object):
    def setupUi(self, LoginDialog):
        if not LoginDialog.objectName():
            LoginDialog.setObjectName(u"LoginDialog")
        LoginDialog.setWindowModality(QtCore.Qt.NonModal)
        LoginDialog.resize(364, 304)
        LoginDialog.setMinimumSize(QtCore.QSize(364, 296))
        LoginDialog.setStyleSheet(u"\n"
"QWidget\n"
"{\n"
"    background-color:  rgb(36, 39, 42);\n"
"    color: rgb(192, 192, 192);\n"
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
"QLineEdit, QComboBox\n"
"{\n"
"    background-color: rgb(29, 31, 34);\n"
"    border: 1px solid rgb(54, 60, 66);\n"
"    border-radius: 2px;\n"
"    padding: 5px;\n"
"     font-size: 12px;\n"
"}\n"
"\n"
"QComboBox\n"
"{\n"
"    margin-left: 3;\n"
"    margin-right: 3\n"
"}\n"
"\n"
"QComboBox:focus, QLineEdit:focus\n"
"{\n"
"    border: 1px solid rgb(48, 167, 227);\n"
"}\n"
"\n"
"QComboBox:drop-down:button {\n"
"    border: 1px solid rgb(54, 60, 66);\n"
"}\n"
"\n"
"QComboBox:down-arrow {\n"
"    image: url(:/shotgun_authentication/down-arrow.png);\n"
"\n"
"}\n"
"\n"
"QLineEdit:Disabled {\n"
"    backgr"
                        "ound-color: rgb(60, 60, 60);\n"
"    color: rgb(160, 160, 160);\n"
"}\n"
"\n"
"QComboBox::drop-down:disabled {\n"
"    border-width: 0px;\n"
"\n"
"}\n"
"\n"
"QComboBox::down-arrow:disabled {\n"
"    image: url(noimg); border-width: 0px;\n"
"}\n"
"\n"
"QComboBox::disabled {\n"
"    background-color: rgb(60, 60, 60);\n"
"    color: rgb(160, 160, 160);\n"
"}")
        LoginDialog.setModal(True)
        self.verticalLayout_2 = QtGui.QVBoxLayout(LoginDialog)
        self.verticalLayout_2.setContentsMargins(20, 20, 20, 20)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setSizeConstraint(QtGui.QLayout.SetMinAndMaxSize)
        self.logo = AspectPreservingLabel(LoginDialog)
        self.logo.setObjectName(u"logo")
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.logo.sizePolicy().hasHeightForWidth())
        self.logo.setSizePolicy(sizePolicy)
        self.logo.setMaximumSize(QtCore.QSize(250, 72))
        self.logo.setPixmap(QtGui.QPixmap(u":/shotgun_authentication/shotgun_logo_light_medium.png"))
        self.logo.setAlignment(QtCore.Qt.AlignCenter)
        self.logo.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)

        self.horizontalLayout.addWidget(self.logo)


        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.stackedWidget = QtGui.QStackedWidget(LoginDialog)
        self.stackedWidget.setObjectName(u"stackedWidget")
        self.stackedWidget.setMinimumSize(QtCore.QSize(324, 172))
        self.login_page = QtGui.QWidget()
        self.login_page.setObjectName(u"login_page")
        self.verticalLayout_3 = QtGui.QVBoxLayout(self.login_page)
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.credentials = QtGui.QWidget(self.login_page)
        self.credentials.setObjectName(u"credentials")
        self.credentials.setMinimumSize(QtCore.QSize(0, 126))
        self.verticalLayout_7 = QtGui.QVBoxLayout(self.credentials)
        self.verticalLayout_7.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.site = RecentBox(self.credentials)
        self.site.setObjectName(u"site")

        self.verticalLayout_7.addWidget(self.site)

        self.login = RecentBox(self.credentials)
        self.login.setObjectName(u"login")

        self.verticalLayout_7.addWidget(self.login)

        self.password = Qt5LikeLineEdit(self.credentials)
        self.password.setObjectName(u"password")
        self.password.setMinimumSize(QtCore.QSize(308, 0))
        self.password.setEchoMode(QtGui.QLineEdit.Password)

        self.verticalLayout_7.addWidget(self.password)

        self.message = QtGui.QLabel(self.credentials)
        self.message.setObjectName(u"message")
        sizePolicy1 = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.message.sizePolicy().hasHeightForWidth())
        self.message.setSizePolicy(sizePolicy1)
        self.message.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.message.setWordWrap(True)
        self.message.setMargin(4)

        self.verticalLayout_7.addWidget(self.message)

        self.verticalSpacer_3 = QtGui.QSpacerItem(20, 0, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)

        self.verticalLayout_7.addItem(self.verticalSpacer_3)


        self.verticalLayout_3.addWidget(self.credentials)

        self.button_layout = QtGui.QHBoxLayout()
        self.button_layout.setSpacing(10)
        self.button_layout.setObjectName(u"button_layout")
        self.button_layout.setContentsMargins(0, -1, -1, -1)
        self.links = QtGui.QVBoxLayout()
        self.links.setObjectName(u"links")
        self.forgot_password_link = QtGui.QLabel(self.login_page)
        self.forgot_password_link.setObjectName(u"forgot_password_link")
        self.forgot_password_link.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.forgot_password_link.setStyleSheet(u"QWidget\n"
"{\n"
"    color: rgb(192, 193, 195);\n"
"}")
        self.forgot_password_link.setTextFormat(QtCore.Qt.RichText)
        self.forgot_password_link.setMargin(4)
        self.forgot_password_link.setOpenExternalLinks(False)

        self.links.addWidget(self.forgot_password_link)


        self.button_layout.addLayout(self.links)

        self.sign_in_hspacer = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)

        self.button_layout.addItem(self.sign_in_hspacer)

        self.cancel = QtGui.QPushButton(self.login_page)
        self.cancel.setObjectName(u"cancel")
        self.cancel.setStyleSheet(u"")
        self.cancel.setAutoDefault(False)
        self.cancel.setFlat(True)

        self.button_layout.addWidget(self.cancel)

        self.sign_in = QtGui.QPushButton(self.login_page)
        self.sign_in.setObjectName(u"sign_in")
        self.sign_in.setStyleSheet(u"color: rgb(248, 248, 248);\n"
"background-color: rgb(35, 165, 225);")
        self.sign_in.setAutoDefault(True)
        self.sign_in.setFlat(True)

        self.button_layout.addWidget(self.sign_in)

        self.button_layout.setStretch(1, 1)

        self.verticalLayout_3.addLayout(self.button_layout)

        self.stackedWidget.addWidget(self.login_page)
        self._2fa_page = QtGui.QWidget()
        self._2fa_page.setObjectName(u"_2fa_page")
        self.verticalLayout_4 = QtGui.QVBoxLayout(self._2fa_page)
        self.verticalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.credentials_2 = QtGui.QWidget(self._2fa_page)
        self.credentials_2.setObjectName(u"credentials_2")
        self.credentials_2.setMinimumSize(QtCore.QSize(0, 133))
        self.horizontalLayout_2 = QtGui.QHBoxLayout(self.credentials_2)
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.label = QtGui.QLabel(self.credentials_2)
        self.label.setObjectName(u"label")
        self.label.setMinimumSize(QtCore.QSize(86, 0))
        self.label.setPixmap(QtGui.QPixmap(u":/google_authenticator/google_authenticator.png"))
        self.label.setAlignment(QtCore.Qt.AlignHCenter|QtCore.Qt.AlignTop)

        self.horizontalLayout_2.addWidget(self.label)

        self.widget_2 = QtGui.QWidget(self.credentials_2)
        self.widget_2.setObjectName(u"widget_2")
        self.verticalLayout = QtGui.QVBoxLayout(self.widget_2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self._2fa_message = QtGui.QLabel(self.widget_2)
        self._2fa_message.setObjectName(u"_2fa_message")
        sizePolicy1.setHeightForWidth(self._2fa_message.sizePolicy().hasHeightForWidth())
        self._2fa_message.setSizePolicy(sizePolicy1)
        self._2fa_message.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self._2fa_message.setWordWrap(True)
        self._2fa_message.setMargin(0)

        self.verticalLayout.addWidget(self._2fa_message)

        self._2fa_code = Qt5LikeLineEdit(self.widget_2)
        self._2fa_code.setObjectName(u"_2fa_code")

        self.verticalLayout.addWidget(self._2fa_code)

        self.invalid_code = QtGui.QLabel(self.widget_2)
        self.invalid_code.setObjectName(u"invalid_code")
        sizePolicy1.setHeightForWidth(self.invalid_code.sizePolicy().hasHeightForWidth())
        self.invalid_code.setSizePolicy(sizePolicy1)

        self.verticalLayout.addWidget(self.invalid_code)

        self.verticalSpacer_2 = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_2)


        self.horizontalLayout_2.addWidget(self.widget_2)


        self.verticalLayout_4.addWidget(self.credentials_2)

        self.button_layout_2 = QtGui.QHBoxLayout()
        self.button_layout_2.setSpacing(10)
        self.button_layout_2.setObjectName(u"button_layout_2")
        self.button_layout_2.setContentsMargins(0, -1, -1, -1)
        self.use_backup = QtGui.QPushButton(self._2fa_page)
        self.use_backup.setObjectName(u"use_backup")
        self.use_backup.setFlat(True)

        self.button_layout_2.addWidget(self.use_backup)

        self._2fa_hspacer = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)

        self.button_layout_2.addItem(self._2fa_hspacer)

        self.cancel_tfa = QtGui.QPushButton(self._2fa_page)
        self.cancel_tfa.setObjectName(u"cancel_tfa")
        self.cancel_tfa.setStyleSheet(u"")
        self.cancel_tfa.setAutoDefault(False)
        self.cancel_tfa.setFlat(True)

        self.button_layout_2.addWidget(self.cancel_tfa)

        self.verify_2fa = QtGui.QPushButton(self._2fa_page)
        self.verify_2fa.setObjectName(u"verify_2fa")
        self.verify_2fa.setMinimumSize(QtCore.QSize(65, 0))
        self.verify_2fa.setStyleSheet(u"color: rgb(248, 248, 248);\n"
"background-color: rgb(35, 165, 225);")
        self.verify_2fa.setAutoDefault(False)
        self.verify_2fa.setFlat(True)

        self.button_layout_2.addWidget(self.verify_2fa)


        self.verticalLayout_4.addLayout(self.button_layout_2)

        self.stackedWidget.addWidget(self._2fa_page)
        self.backup_page = QtGui.QWidget()
        self.backup_page.setObjectName(u"backup_page")
        self.verticalLayout_6 = QtGui.QVBoxLayout(self.backup_page)
        self.verticalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.credentials_3 = QtGui.QWidget(self.backup_page)
        self.credentials_3.setObjectName(u"credentials_3")
        self.credentials_3.setMinimumSize(QtCore.QSize(0, 133))
        self.horizontalLayout_3 = QtGui.QHBoxLayout(self.credentials_3)
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.label_2 = QtGui.QLabel(self.credentials_3)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setPixmap(QtGui.QPixmap(u":/backup_codes/backup_codes_light_bg.png"))
        self.label_2.setAlignment(QtCore.Qt.AlignHCenter|QtCore.Qt.AlignTop)

        self.horizontalLayout_3.addWidget(self.label_2)

        self.widget_4 = QtGui.QWidget(self.credentials_3)
        self.widget_4.setObjectName(u"widget_4")
        self.verticalLayout_5 = QtGui.QVBoxLayout(self.widget_4)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self._2fa_message_2 = QtGui.QLabel(self.widget_4)
        self._2fa_message_2.setObjectName(u"_2fa_message_2")
        sizePolicy1.setHeightForWidth(self._2fa_message_2.sizePolicy().hasHeightForWidth())
        self._2fa_message_2.setSizePolicy(sizePolicy1)
        self._2fa_message_2.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self._2fa_message_2.setWordWrap(True)
        self._2fa_message_2.setMargin(0)

        self.verticalLayout_5.addWidget(self._2fa_message_2)

        self.backup_code = Qt5LikeLineEdit(self.widget_4)
        self.backup_code.setObjectName(u"backup_code")

        self.verticalLayout_5.addWidget(self.backup_code)

        self.invalid_backup_code = QtGui.QLabel(self.widget_4)
        self.invalid_backup_code.setObjectName(u"invalid_backup_code")
        sizePolicy1.setHeightForWidth(self.invalid_backup_code.sizePolicy().hasHeightForWidth())
        self.invalid_backup_code.setSizePolicy(sizePolicy1)

        self.verticalLayout_5.addWidget(self.invalid_backup_code)

        self.verticalSpacer = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)

        self.verticalLayout_5.addItem(self.verticalSpacer)


        self.horizontalLayout_3.addWidget(self.widget_4)


        self.verticalLayout_6.addWidget(self.credentials_3)

        self.button_layout_3 = QtGui.QHBoxLayout()
        self.button_layout_3.setSpacing(10)
        self.button_layout_3.setObjectName(u"button_layout_3")
        self.button_layout_3.setContentsMargins(0, -1, -1, -1)
        self.use_app = QtGui.QPushButton(self.backup_page)
        self.use_app.setObjectName(u"use_app")
        self.use_app.setAutoDefault(False)
        self.use_app.setFlat(True)

        self.button_layout_3.addWidget(self.use_app)

        self.backup_hspacer = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)

        self.button_layout_3.addItem(self.backup_hspacer)

        self.cancel_backup = QtGui.QPushButton(self.backup_page)
        self.cancel_backup.setObjectName(u"cancel_backup")
        self.cancel_backup.setAutoDefault(False)
        self.cancel_backup.setFlat(True)

        self.button_layout_3.addWidget(self.cancel_backup)

        self.verify_backup = QtGui.QPushButton(self.backup_page)
        self.verify_backup.setObjectName(u"verify_backup")
        self.verify_backup.setMinimumSize(QtCore.QSize(65, 0))
        self.verify_backup.setStyleSheet(u"color: rgb(248, 248, 248);\n"
"background-color: rgb(35, 165, 225);")
        self.verify_backup.setAutoDefault(True)
        self.verify_backup.setFlat(True)

        self.button_layout_3.addWidget(self.verify_backup)


        self.verticalLayout_6.addLayout(self.button_layout_3)

        self.stackedWidget.addWidget(self.backup_page)

        self.verticalLayout_2.addWidget(self.stackedWidget)

        self.verticalLayout_2.setStretch(0, 1)

        self.retranslateUi(LoginDialog)
        self.cancel_tfa.clicked.connect(LoginDialog.reject)
        self.cancel_backup.clicked.connect(LoginDialog.reject)
        self.cancel.clicked.connect(LoginDialog.reject)

        self.stackedWidget.setCurrentIndex(0)
        self.sign_in.setDefault(True)
        self.verify_2fa.setDefault(True)
        self.verify_backup.setDefault(True)


        QtCore.QMetaObject.connectSlotsByName(LoginDialog)
    # setupUi

    def retranslateUi(self, LoginDialog):
        self.logo.setText("")
#if QT_CONFIG(accessibility)
        self.site.setAccessibleName(QtGui.QApplication.translate("LoginDialog", u"site", None, QtGui.QApplication.UnicodeUTF8))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(accessibility)
        self.login.setAccessibleName(QtGui.QApplication.translate("LoginDialog", u"login", None, QtGui.QApplication.UnicodeUTF8))
#endif // QT_CONFIG(accessibility)
#if QT_CONFIG(accessibility)
        self.password.setAccessibleName(QtGui.QApplication.translate("LoginDialog", u"password", None, QtGui.QApplication.UnicodeUTF8))
#endif // QT_CONFIG(accessibility)
        self.password.setPlaceholderText(QtGui.QApplication.translate("LoginDialog", u"password", None, QtGui.QApplication.UnicodeUTF8))
        self.message.setText(QtGui.QApplication.translate("LoginDialog", u"Please enter your credentials.", None, QtGui.QApplication.UnicodeUTF8))
        self.forgot_password_link.setText(QtGui.QApplication.translate("LoginDialog", u"<html><head/><body><p><a href=\"http://mystudio.shotgrid.autodesk.com/user/forgot_password\"><span style=\" text-decoration: underline; color:#c0c1c3;\">Forgot your password?</span></a></p></body></html>", None, QtGui.QApplication.UnicodeUTF8))
        self.cancel.setText(QtGui.QApplication.translate("LoginDialog", u"Cancel", None, QtGui.QApplication.UnicodeUTF8))
        self.sign_in.setText(QtGui.QApplication.translate("LoginDialog", u"Sign In", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText("")
        self._2fa_message.setText(QtGui.QApplication.translate("LoginDialog", u"Enter the code generated by the Google Authenticator or Duo Mobile app.", None, QtGui.QApplication.UnicodeUTF8))
#if QT_CONFIG(accessibility)
        self._2fa_code.setAccessibleName(QtGui.QApplication.translate("LoginDialog", u"2fa code", None, QtGui.QApplication.UnicodeUTF8))
#endif // QT_CONFIG(accessibility)
        self._2fa_code.setPlaceholderText(QtGui.QApplication.translate("LoginDialog", u"Enter code", None, QtGui.QApplication.UnicodeUTF8))
        self.invalid_code.setText("")
        self.use_backup.setText(QtGui.QApplication.translate("LoginDialog", u"Use backup code", None, QtGui.QApplication.UnicodeUTF8))
        self.cancel_tfa.setText(QtGui.QApplication.translate("LoginDialog", u"Cancel", None, QtGui.QApplication.UnicodeUTF8))
        self.verify_2fa.setText(QtGui.QApplication.translate("LoginDialog", u"Verify", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText("")
        self._2fa_message_2.setText(QtGui.QApplication.translate("LoginDialog", u"Please enter one of your backup codes.", None, QtGui.QApplication.UnicodeUTF8))
#if QT_CONFIG(accessibility)
        self.backup_code.setAccessibleName(QtGui.QApplication.translate("LoginDialog", u"backup code", None, QtGui.QApplication.UnicodeUTF8))
#endif // QT_CONFIG(accessibility)
        self.backup_code.setText("")
        self.backup_code.setPlaceholderText(QtGui.QApplication.translate("LoginDialog", u"Enter backup code", None, QtGui.QApplication.UnicodeUTF8))
        self.invalid_backup_code.setText("")
        self.use_app.setText(QtGui.QApplication.translate("LoginDialog", u"Use Google App", None, QtGui.QApplication.UnicodeUTF8))
        self.cancel_backup.setText(QtGui.QApplication.translate("LoginDialog", u"Cancel", None, QtGui.QApplication.UnicodeUTF8))
        self.verify_backup.setText(QtGui.QApplication.translate("LoginDialog", u"Verify", None, QtGui.QApplication.UnicodeUTF8))
        pass
    # retranslateUi

