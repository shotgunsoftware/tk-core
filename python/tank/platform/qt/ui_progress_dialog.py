# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'progress_dialog.ui'
#
# Created: Tue Sep  2 14:45:47 2014
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from . import QtCore, QtGui

class Ui_ProgressDialog(object):
    def setupUi(self, ProgressDialog):
        ProgressDialog.setObjectName("ProgressDialog")
        ProgressDialog.resize(418, 98)
        ProgressDialog.setStyleSheet("/* Style for the window itself */\n"
"#frame {\n"
"border-color: #30A7E3;\n"
"border-style: solid;\n"
"border-width: 2px;\n"
"}\n"
"\n"
"/* Style for the header text */\n"
"#title { \n"
"color: #30A7E3;\n"
"margin-top: 15px;\n"
"margin-bottom: 0px;\n"
"margin-left: 1px;\n"
"font-size: 16px;\n"
"font-weight: bold;\n"
"}\n"
"\n"
"/* Style for the details text */\n"
"#details { \n"
"margin-top: 1px;\n"
"margin-left: 3px;\n"
"margin-bottom: 0px;\n"
"font-size: 11px;\n"
"}\n"
"")
        self.horizontalLayout_2 = QtGui.QHBoxLayout(ProgressDialog)
        self.horizontalLayout_2.setSpacing(2)
        self.horizontalLayout_2.setContentsMargins(2, 2, 2, 2)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.frame = QtGui.QFrame(ProgressDialog)
        self.frame.setFrameShape(QtGui.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtGui.QFrame.Raised)
        self.frame.setObjectName("frame")
        self.horizontalLayout = QtGui.QHBoxLayout(self.frame)
        self.horizontalLayout.setSpacing(5)
        self.horizontalLayout.setContentsMargins(5, 5, 5, 5)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label = QtGui.QLabel(self.frame)
        self.label.setText("")
        self.label.setPixmap(QtGui.QPixmap(":/Tank.Platform.Qt/sg_logo_80px.png"))
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.title = QtGui.QLabel(self.frame)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.title.sizePolicy().hasHeightForWidth())
        self.title.setSizePolicy(sizePolicy)
        self.title.setObjectName("title")
        self.verticalLayout.addWidget(self.title)
        self.details = QtGui.QLabel(self.frame)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.details.sizePolicy().hasHeightForWidth())
        self.details.setSizePolicy(sizePolicy)
        self.details.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignTop)
        self.details.setWordWrap(True)
        self.details.setObjectName("details")
        self.verticalLayout.addWidget(self.details)
        self.horizontalLayout.addLayout(self.verticalLayout)
        self.horizontalLayout_2.addWidget(self.frame)

        self.retranslateUi(ProgressDialog)
        QtCore.QMetaObject.connectSlotsByName(ProgressDialog)

    def retranslateUi(self, ProgressDialog):
        ProgressDialog.setWindowTitle(QtGui.QApplication.translate("ProgressDialog", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.title.setText(QtGui.QApplication.translate("ProgressDialog", "Doing something, hang on!", None, QtGui.QApplication.UnicodeUTF8))
        self.details.setText(QtGui.QApplication.translate("ProgressDialog", "Lots of interesting details about what is going on", None, QtGui.QApplication.UnicodeUTF8))

from . import resources_rc
