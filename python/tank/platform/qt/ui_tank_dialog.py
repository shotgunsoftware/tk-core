# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'tank_dialog.ui'
#
#      by: pyside-uic 0.2.15 running on PySide 1.2.2
#
# WARNING! All changes made in this file will be lost!

from . import QtCore, QtGui

class Ui_TankDialog(object):
    def setupUi(self, TankDialog):
        TankDialog.setObjectName("TankDialog")
        TankDialog.resize(879, 551)
        TankDialog.setStyleSheet("")
        self.verticalLayout_3 = QtGui.QVBoxLayout(TankDialog)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.stackedWidget = QtGui.QStackedWidget(TankDialog)
        self.stackedWidget.setObjectName("stackedWidget")
        self.page_1 = QtGui.QWidget()
        self.page_1.setStyleSheet("")
        self.page_1.setObjectName("page_1")
        self.verticalLayout = QtGui.QVBoxLayout(self.page_1)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.top_group = QtGui.QGroupBox(self.page_1)
        self.top_group.setMinimumSize(QtCore.QSize(0, 45))
        self.top_group.setMaximumSize(QtCore.QSize(16777215, 45))
        self.top_group.setStyleSheet("#top_group {\n"
"background-color:  #2D2D2D;\n"
"border: none;\n"
"border-bottom:1px solid #202020;\n"
"}\n"
"")
        self.top_group.setTitle("")
        self.top_group.setFlat(False)
        self.top_group.setObjectName("top_group")
        self.horizontalLayout = QtGui.QHBoxLayout(self.top_group)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setContentsMargins(4, 0, 1, 1)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.tank_logo = QtGui.QLabel(self.top_group)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tank_logo.sizePolicy().hasHeightForWidth())
        self.tank_logo.setSizePolicy(sizePolicy)
        self.tank_logo.setText("")
        self.tank_logo.setPixmap(QtGui.QPixmap(":/Tank.Platform.Qt/tank_logo.png"))
        self.tank_logo.setObjectName("tank_logo")
        self.horizontalLayout.addWidget(self.tank_logo)
        self.label = QtGui.QLabel(self.top_group)
        self.label.setStyleSheet("/* want this stylesheet to apply to the label but not the tooltip */\n"
"QLabel{\n"
"    color: white;\n"
"    font-size: 20px;\n"
"    margin-left: 5px;\n"
"    font-family: \"Open Sans\";\n"
"    font-style: \"Regular\";\n"
"}")
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.lbl_context = QtGui.QLabel(self.top_group)
        self.lbl_context.setStyleSheet("/* want this stylesheet to apply to the label but not the tooltip */\n"
"QLabel { \n"
"    color: rgba(250,250,250,180);\n"
"    font-size: 11px;\n"
"    margin-right: 8px;\n"
"    font-family: \"Open Sans\";\n"
"    font-style: \"Regular\";\n"
"} \n"
"\n"
"\n"
"")
        self.lbl_context.setAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.lbl_context.setObjectName("lbl_context")
        self.horizontalLayout.addWidget(self.lbl_context)
        self.details = QtGui.QToolButton(self.top_group)
        self.details.setMinimumSize(QtCore.QSize(34, 34))
        self.details.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.details.setStyleSheet("QToolButton{\n"
"width: 12px;\n"
"height: 20px;\n"
"background-image: url(:/Tank.Platform.Qt/arrow.png);\n"
"border: none;\n"
"background-color: none;\n"
"}\n"
"\n"
"\n"
"QToolButton:hover{\n"
"background-image: url(:/Tank.Platform.Qt/arrow_hover.png);\n"
"}\n"
"\n"
"QToolButton:Pressed {\n"
"background-image: url(:/Tank.Platform.Qt/arrow_pressed.png);\n"
"}\n"
"")
        self.details.setText("")
        self.details.setAutoRaise(True)
        self.details.setObjectName("details")
        self.horizontalLayout.addWidget(self.details)
        self.verticalLayout.addWidget(self.top_group)
        self.target = QtGui.QVBoxLayout()
        self.target.setSpacing(4)
        self.target.setObjectName("target")
        self.verticalLayout.addLayout(self.target)
        self.stackedWidget.addWidget(self.page_1)
        self.page_2 = QtGui.QWidget()
        self.page_2.setStyleSheet("QWidget {\n"
"    font-family: \"Open Sans\";\n"
"    font-style: \"Regular\";\n"
"}")
        self.page_2.setObjectName("page_2")
        self.verticalLayout_2 = QtGui.QVBoxLayout(self.page_2)
        self.verticalLayout_2.setContentsMargins(1, 1, 1, 1)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.page_2_group = QtGui.QGroupBox(self.page_2)
        self.page_2_group.setMinimumSize(QtCore.QSize(0, 100))
        self.page_2_group.setStyleSheet("")
        self.page_2_group.setTitle("")
        self.page_2_group.setObjectName("page_2_group")
        self.horizontalLayout_2 = QtGui.QHBoxLayout(self.page_2_group)
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        spacerItem = QtGui.QSpacerItem(145, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.label_3 = QtGui.QLabel(self.page_2_group)
        self.label_3.setMinimumSize(QtCore.QSize(40, 0))
        self.label_3.setMaximumSize(QtCore.QSize(40, 16777215))
        self.label_3.setText("")
        self.label_3.setObjectName("label_3")
        self.horizontalLayout_2.addWidget(self.label_3)
        self.gradient = QtGui.QGroupBox(self.page_2_group)
        self.gradient.setMinimumSize(QtCore.QSize(11, 0))
        self.gradient.setMaximumSize(QtCore.QSize(11, 16777215))
        self.gradient.setStyleSheet("#gradient {\n"
"background-image: url(:/Tank.Platform.Qt/gradient.png); \n"
"border: none;\n"
"}")
        self.gradient.setTitle("")
        self.gradient.setObjectName("gradient")
        self.horizontalLayout_2.addWidget(self.gradient)
        self.scrollArea = QtGui.QScrollArea(self.page_2_group)
        self.scrollArea.setMinimumSize(QtCore.QSize(400, 0))
        self.scrollArea.setMaximumSize(QtCore.QSize(400, 16777215))
        self.scrollArea.setStyleSheet("/*\n"
"All labels inside this scroll area should be 12px font.\n"
"This is to avoid the UI looking different in different app like\n"
"maya and nuke which all use slightly different style sheets.\n"
" */\n"
"QLabel{\n"
"   font-size: 11px;\n"
"   margin-bottom: 8px\n"
"}\n"
"")
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollAreaWidgetContents = QtGui.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 383, 577))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.verticalLayout_4 = QtGui.QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.horizontalLayout_4 = QtGui.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.app_icon = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.app_icon.setMinimumSize(QtCore.QSize(64, 64))
        self.app_icon.setMaximumSize(QtCore.QSize(64, 64))
        self.app_icon.setText("")
        self.app_icon.setPixmap(QtGui.QPixmap(":/Tank.Platform.Qt/default_app_icon_256.png"))
        self.app_icon.setScaledContents(True)
        self.app_icon.setAlignment(QtCore.Qt.AlignCenter)
        self.app_icon.setObjectName("app_icon")
        self.horizontalLayout_4.addWidget(self.app_icon)
        self.verticalLayout_8 = QtGui.QVBoxLayout()
        self.verticalLayout_8.setSpacing(1)
        self.verticalLayout_8.setObjectName("verticalLayout_8")
        self.app_name = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.app_name.setStyleSheet("font-size: 16px;\n"
"")
        self.app_name.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.app_name.setObjectName("app_name")
        self.verticalLayout_8.addWidget(self.app_name)
        self.horizontalLayout_4.addLayout(self.verticalLayout_8)
        self.verticalLayout_4.addLayout(self.horizontalLayout_4)
        self.app_description = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.app_description.setMaximumSize(QtCore.QSize(350, 16777215))
        self.app_description.setWordWrap(True)
        self.app_description.setObjectName("app_description")
        self.verticalLayout_4.addWidget(self.app_description)
        self.app_tech_details = QtGui.QLabel(self.scrollAreaWidgetContents)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.app_tech_details.sizePolicy().hasHeightForWidth())
        self.app_tech_details.setSizePolicy(sizePolicy)
        self.app_tech_details.setMinimumSize(QtCore.QSize(0, 22))
        self.app_tech_details.setMaximumSize(QtCore.QSize(16777215, 22))
        self.app_tech_details.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignVCenter)
        self.app_tech_details.setWordWrap(True)
        self.app_tech_details.setObjectName("app_tech_details")
        self.verticalLayout_4.addWidget(self.app_tech_details)
        self.horizontalLayout_9 = QtGui.QHBoxLayout()
        self.horizontalLayout_9.setSpacing(2)
        self.horizontalLayout_9.setObjectName("horizontalLayout_9")
        self.btn_documentation = QtGui.QToolButton(self.scrollAreaWidgetContents)
        self.btn_documentation.setObjectName("btn_documentation")
        self.horizontalLayout_9.addWidget(self.btn_documentation)
        self.btn_support = QtGui.QToolButton(self.scrollAreaWidgetContents)
        self.btn_support.setObjectName("btn_support")
        self.horizontalLayout_9.addWidget(self.btn_support)
        spacerItem1 = QtGui.QSpacerItem(0, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_9.addItem(spacerItem1)
        self.verticalLayout_4.addLayout(self.horizontalLayout_9)
        self.label_5 = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.label_5.setStyleSheet("font-size: 16px;\n"
"margin-top: 30px;")
        self.label_5.setObjectName("label_5")
        self.verticalLayout_4.addWidget(self.label_5)
        self.line = QtGui.QFrame(self.scrollAreaWidgetContents)
        self.line.setFrameShape(QtGui.QFrame.HLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)
        self.line.setObjectName("line")
        self.verticalLayout_4.addWidget(self.line)
        self.app_work_area_info = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.app_work_area_info.setMaximumSize(QtCore.QSize(350, 16777215))
        self.app_work_area_info.setWordWrap(True)
        self.app_work_area_info.setObjectName("app_work_area_info")
        self.verticalLayout_4.addWidget(self.app_work_area_info)
        self.horizontalLayout_10 = QtGui.QHBoxLayout()
        self.horizontalLayout_10.setSpacing(2)
        self.horizontalLayout_10.setObjectName("horizontalLayout_10")
        self.btn_file_system = QtGui.QToolButton(self.scrollAreaWidgetContents)
        self.btn_file_system.setObjectName("btn_file_system")
        self.horizontalLayout_10.addWidget(self.btn_file_system)
        self.btn_shotgun = QtGui.QToolButton(self.scrollAreaWidgetContents)
        self.btn_shotgun.setObjectName("btn_shotgun")
        self.horizontalLayout_10.addWidget(self.btn_shotgun)
        spacerItem2 = QtGui.QSpacerItem(0, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout_10.addItem(spacerItem2)
        self.verticalLayout_4.addLayout(self.horizontalLayout_10)
        self.app_work_area_info_2 = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.app_work_area_info_2.setMaximumSize(QtCore.QSize(350, 16777215))
        self.app_work_area_info_2.setWordWrap(True)
        self.app_work_area_info_2.setObjectName("app_work_area_info_2")
        self.verticalLayout_4.addWidget(self.app_work_area_info_2)
        self.btn_reload = QtGui.QToolButton(self.scrollAreaWidgetContents)
        self.btn_reload.setObjectName("btn_reload")
        self.verticalLayout_4.addWidget(self.btn_reload)
        self.config_header = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.config_header.setStyleSheet("font-size: 16px;\n"
"margin-top: 30px;")
        self.config_header.setObjectName("config_header")
        self.verticalLayout_4.addWidget(self.config_header)
        self.config_line = QtGui.QFrame(self.scrollAreaWidgetContents)
        self.config_line.setFrameShape(QtGui.QFrame.HLine)
        self.config_line.setFrameShadow(QtGui.QFrame.Sunken)
        self.config_line.setObjectName("config_line")
        self.verticalLayout_4.addWidget(self.config_line)
        self.config_label = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.config_label.setMaximumSize(QtCore.QSize(350, 16777215))
        self.config_label.setWordWrap(True)
        self.config_label.setObjectName("config_label")
        self.verticalLayout_4.addWidget(self.config_label)
        self.config_layout = QtGui.QVBoxLayout()
        self.config_layout.setSpacing(20)
        self.config_layout.setObjectName("config_layout")
        self.verticalLayout_4.addLayout(self.config_layout)
        spacerItem3 = QtGui.QSpacerItem(328, 0, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout_4.addItem(spacerItem3)
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.horizontalLayout_2.addWidget(self.scrollArea)
        self.verticalLayout_2.addWidget(self.page_2_group)
        self.stackedWidget.addWidget(self.page_2)
        self.verticalLayout_3.addWidget(self.stackedWidget)

        self.retranslateUi(TankDialog)
        self.stackedWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(TankDialog)

    def retranslateUi(self, TankDialog):
        TankDialog.setWindowTitle(QtGui.QApplication.translate("TankDialog", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("TankDialog", "TextLabel", None, QtGui.QApplication.UnicodeUTF8))
        self.lbl_context.setToolTip(QtGui.QApplication.translate("TankDialog", "foo bar", None, QtGui.QApplication.UnicodeUTF8))
        self.lbl_context.setText(QtGui.QApplication.translate("TankDialog", "Current Work Area:\n"
"TextLabel", None, QtGui.QApplication.UnicodeUTF8))
        self.details.setToolTip(QtGui.QApplication.translate("TankDialog", "Click for App Details", None, QtGui.QApplication.UnicodeUTF8))
        self.app_name.setText(QtGui.QApplication.translate("TankDialog", "Publish And Snapshot", None, QtGui.QApplication.UnicodeUTF8))
        self.app_description.setText(QtGui.QApplication.translate("TankDialog", "Tools to see what is out of date in your scene etc etc.", None, QtGui.QApplication.UnicodeUTF8))
        self.app_tech_details.setText(QtGui.QApplication.translate("TankDialog", "tk-multi-snapshot, v1.2.3", None, QtGui.QApplication.UnicodeUTF8))
        self.btn_documentation.setText(QtGui.QApplication.translate("TankDialog", "Documentation", None, QtGui.QApplication.UnicodeUTF8))
        self.btn_support.setText(QtGui.QApplication.translate("TankDialog", "Help && Support", None, QtGui.QApplication.UnicodeUTF8))
        self.label_5.setText(QtGui.QApplication.translate("TankDialog", "Your Current Work Area", None, QtGui.QApplication.UnicodeUTF8))
        self.app_work_area_info.setText(QtGui.QApplication.translate("TankDialog", "TextLabel", None, QtGui.QApplication.UnicodeUTF8))
        self.btn_file_system.setText(QtGui.QApplication.translate("TankDialog", "Jump to File System", None, QtGui.QApplication.UnicodeUTF8))
        self.btn_shotgun.setText(QtGui.QApplication.translate("TankDialog", "Jump to Shotgun", None, QtGui.QApplication.UnicodeUTF8))
        self.app_work_area_info_2.setText(QtGui.QApplication.translate("TankDialog", "If you are making changes to configuration or code, use the reload button to quickly load your changes in without having to restart:", None, QtGui.QApplication.UnicodeUTF8))
        self.btn_reload.setText(QtGui.QApplication.translate("TankDialog", "Reload Engine and Apps", None, QtGui.QApplication.UnicodeUTF8))
        self.config_header.setText(QtGui.QApplication.translate("TankDialog", "Configuration", None, QtGui.QApplication.UnicodeUTF8))
        self.config_label.setText(QtGui.QApplication.translate("TankDialog", "Below is a list of all the configuration settings for this app, as defined in your environment file:", None, QtGui.QApplication.UnicodeUTF8))

from . import resources_rc
