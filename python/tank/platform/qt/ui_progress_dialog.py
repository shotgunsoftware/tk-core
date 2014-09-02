# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'progress_dialog.ui'
#
# Created: Tue Sep  2 10:59:15 2014
#      by: pyside-uic 0.2.13 running on PySide 1.1.1
#
# WARNING! All changes made in this file will be lost!

from . import QtCore, QtGui

class Ui_ProgressDialog(object):
    def setupUi(self, ProgressDialog):
        ProgressDialog.setObjectName("ProgressDialog")
        ProgressDialog.resize(381, 104)
        self.horizontalLayout = QtGui.QHBoxLayout(ProgressDialog)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label = QtGui.QLabel(ProgressDialog)
        self.label.setText("")
        self.label.setPixmap(QtGui.QPixmap(":/Tank.Platform.Qt/sg_logo_80px.png"))
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.verticalLayout = QtGui.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.title = QtGui.QLabel(ProgressDialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.title.sizePolicy().hasHeightForWidth())
        self.title.setSizePolicy(sizePolicy)
        self.title.setObjectName("title")
        self.verticalLayout.addWidget(self.title)
        self.details = QtGui.QLabel(ProgressDialog)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.details.sizePolicy().hasHeightForWidth())
        self.details.setSizePolicy(sizePolicy)
        self.details.setObjectName("details")
        self.verticalLayout.addWidget(self.details)
        self.horizontalLayout.addLayout(self.verticalLayout)

        self.retranslateUi(ProgressDialog)
        QtCore.QMetaObject.connectSlotsByName(ProgressDialog)

    def retranslateUi(self, ProgressDialog):
        ProgressDialog.setWindowTitle(QtGui.QApplication.translate("ProgressDialog", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.title.setText(QtGui.QApplication.translate("ProgressDialog", "Title", None, QtGui.QApplication.UnicodeUTF8))
        self.details.setText(QtGui.QApplication.translate("ProgressDialog", "Details", None, QtGui.QApplication.UnicodeUTF8))

from . import resources_rc
