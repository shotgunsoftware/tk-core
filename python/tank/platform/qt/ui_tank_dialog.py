# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'tank_dialog.ui'
#
# Created: Sun Jan 20 12:10:00 2013
#      by: pyside-uic 0.2.13 running on PySide 1.1.0
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_TankDialog(object):
    def setupUi(self, TankDialog):
        TankDialog.setObjectName("TankDialog")
        TankDialog.resize(726, 478)
        self.verticalLayout_3 = QtGui.QVBoxLayout(TankDialog)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.stackedWidget = QtGui.QStackedWidget(TankDialog)
        self.stackedWidget.setObjectName("stackedWidget")
        self.page = QtGui.QWidget()
        self.page.setObjectName("page")
        self.verticalLayout = QtGui.QVBoxLayout(self.page)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.top_group = QtGui.QGroupBox(self.page)
        self.top_group.setMinimumSize(QtCore.QSize(0, 45))
        self.top_group.setMaximumSize(QtCore.QSize(16777215, 45))
        self.top_group.setStyleSheet("#top_group {\n"
"background-image: url(:/Tank.Platform.Qt/bg.png); \n"
"border: none;\n"
"border-bottom:1px solid #606161\n"
"}\n"
"\n"
"")
        self.top_group.setTitle("")
        self.top_group.setFlat(False)
        self.top_group.setObjectName("top_group")
        self.horizontalLayout = QtGui.QHBoxLayout(self.top_group)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setContentsMargins(1, 1, 1, 1)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label_2 = QtGui.QLabel(self.top_group)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy)
        self.label_2.setText("")
        self.label_2.setPixmap(QtGui.QPixmap(":/Tank.Platform.Qt/tank_logo.png"))
        self.label_2.setObjectName("label_2")
        self.horizontalLayout.addWidget(self.label_2)
        self.label = QtGui.QLabel(self.top_group)
        self.label.setStyleSheet("color: white;\n"
"font-size: 20px;\n"
"margin-left: 5px;")
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.verticalLayout.addWidget(self.top_group)
        self.target = QtGui.QVBoxLayout()
        self.target.setSpacing(4)
        self.target.setObjectName("target")
        self.verticalLayout.addLayout(self.target)
        self.stackedWidget.addWidget(self.page)
        self.page_2 = QtGui.QWidget()
        self.page_2.setStyleSheet("")
        self.page_2.setObjectName("page_2")
        self.verticalLayout_5 = QtGui.QVBoxLayout(self.page_2)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.scrollArea = QtGui.QScrollArea(self.page_2)
        self.scrollArea.setStyleSheet("color: white;")
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollAreaWidgetContents = QtGui.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 685, 1188))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.verticalLayout_6 = QtGui.QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayout_6.setObjectName("verticalLayout_6")
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.label_3 = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.label_3.setMinimumSize(QtCore.QSize(128, 128))
        self.label_3.setMaximumSize(QtCore.QSize(128, 128))
        self.label_3.setText("")
        self.label_3.setPixmap(QtGui.QPixmap(":/Tank.Platform.Qt/default_app_icon_256.png"))
        self.label_3.setScaledContents(True)
        self.label_3.setAlignment(QtCore.Qt.AlignCenter)
        self.label_3.setObjectName("label_3")
        self.horizontalLayout_2.addWidget(self.label_3)
        self.verticalLayout_4 = QtGui.QVBoxLayout()
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.label_4 = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.label_4.setObjectName("label_4")
        self.verticalLayout_4.addWidget(self.label_4)
        self.label_5 = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.label_5.setObjectName("label_5")
        self.verticalLayout_4.addWidget(self.label_5)
        self.horizontalLayout_2.addLayout(self.verticalLayout_4)
        self.verticalLayout_6.addLayout(self.horizontalLayout_2)
        self.label_6 = QtGui.QLabel(self.scrollAreaWidgetContents)
        self.label_6.setWordWrap(True)
        self.label_6.setObjectName("label_6")
        self.verticalLayout_6.addWidget(self.label_6)
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.verticalLayout_5.addWidget(self.scrollArea)
        self.stackedWidget.addWidget(self.page_2)
        self.verticalLayout_3.addWidget(self.stackedWidget)

        self.retranslateUi(TankDialog)
        self.stackedWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(TankDialog)

    def retranslateUi(self, TankDialog):
        TankDialog.setWindowTitle(QtGui.QApplication.translate("TankDialog", "Dialog", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("TankDialog", "TextLabel", None, QtGui.QApplication.UnicodeUTF8))
        self.label_4.setText(QtGui.QApplication.translate("TankDialog", "Publish And Snapsho", None, QtGui.QApplication.UnicodeUTF8))
        self.label_5.setText(QtGui.QApplication.translate("TankDialog", "Publish And Snapsho", None, QtGui.QApplication.UnicodeUTF8))
        self.label_6.setText(QtGui.QApplication.translate("TankDialog", "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vestibulum ante mauris, imperdiet quis adipiscing tristique, viverra et leo. Nulla id arcu neque. Donec a orci nisi. Vestibulum pellentesque ligula eget arcu tempor eu ornare velit vulputate. Proin consequat arcu in justo cursus quis dapibus dolor suscipit. Sed volutpat purus et massa eleifend at facilisis risus ullamcorper. Cras ligula nunc, rhoncus nec hendrerit quis, bibendum quis lectus. Morbi a justo at orci dictum vestibulum. Cras tristique auctor viverra. In magna massa, bibendum vitae tempor sed, vehicula sit amet purus.\n"
"\n"
"Praesent orci elit, commodo bibendum congue ac, dictum sit amet justo. Nullam tempus porttitor libero, sit amet ullamcorper urna congue et. Sed vel leo quis tellus ullamcorper tincidunt vitae vitae risus. Donec commodo semper quam, quis porta mauris auctor id. Nunc molestie lectus ac justo tristique at laoreet arcu viverra. In erat lorem, mattis porta tempor vel, tincidunt eu dui. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Duis id tortor eget lorem auctor elementum. Suspendisse dignissim elit ut dui pharetra lobortis. Nam nec libero odio, ut placerat nulla. Nulla rutrum condimentum velit ut vulputate. Proin ullamcorper mi eu odio porta fringilla. Sed vitae euismod urna. Nulla ullamcorper, odio et aliquam ultrices, ligula augue ullamcorper tellus, sed sollicitudin neque odio ac lorem. Aliquam sollicitudin imperdiet vestibulum.Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vestibulum ante mauris, imperdiet quis adipiscing tristique, viverra et leo. Nulla id arcu neque. Donec a orci nisi. Vestibulum pellentesque ligula eget arcu tempor eu ornare velit vulputate. Proin consequat arcu in justo cursus quis dapibus dolor suscipit. Sed volutpat purus et massa eleifend at facilisis risus ullamcorper. Cras ligula nunc, rhoncus nec hendrerit quis, bibendum quis lectus. Morbi a justo at orci dictum vestibulum. Cras tristique auctor viverra. In magna massa, bibendum vitae tempor sed, vehicula sit amet purus.\n"
"\n"
"Praesent orci elit, commodo bibendum congue ac, dictum sit amet justo. Nullam tempus porttitor libero, sit amet ullamcorper urna congue et. Sed vel leo quis tellus ullamcorper tincidunt vitae vitae risus. Donec commodo semper quam, quis porta mauris auctor id. Nunc molestie lectus ac justo tristique at laoreet arcu viverra. In erat lorem, mattis porta tempor vel, tincidunt eu dui. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Duis id tortor eget lorem auctor elementum. Suspendisse dignissim elit ut dui pharetra lobortis. Nam nec libero odio, ut placerat nulla. Nulla rutrum condimentum velit ut vulputate. Proin ullamcorper mi eu odio porta fringilla. Sed vitae euismod urna. Nulla ullamcorper, odio et aliquam ultrices, ligula augue ullamcorper tellus, sed sollicitudin neque odio ac lorem. Aliquam sollicitudin imperdiet vestibulum.Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vestibulum ante mauris, imperdiet quis adipiscing tristique, viverra et leo. Nulla id arcu neque. Donec a orci nisi. Vestibulum pellentesque ligula eget arcu tempor eu ornare velit vulputate. Proin consequat arcu in justo cursus quis dapibus dolor suscipit. Sed volutpat purus et massa eleifend at facilisis risus ullamcorper. Cras ligula nunc, rhoncus nec hendrerit quis, bibendum quis lectus. Morbi a justo at orci dictum vestibulum. Cras tristique auctor viverra. In magna massa, bibendum vitae tempor sed, vehicula sit amet purus.\n"
"\n"
"Praesent orci elit, commodo bibendum congue ac, dictum sit amet justo. Nullam tempus porttitor libero, sit amet ullamcorper urna congue et. Sed vel leo quis tellus ullamcorper tincidunt vitae vitae risus. Donec commodo semper quam, quis porta mauris auctor id. Nunc molestie lectus ac justo tristique at laoreet arcu viverra. In erat lorem, mattis porta tempor vel, tincidunt eu dui. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Duis id tortor eget lorem auctor elementum. Suspendisse dignissim elit ut dui pharetra lobortis. Nam nec libero odio, ut placerat nulla. Nulla rutrum condimentum velit ut vulputate. Proin ullamcorper mi eu odio porta fringilla. Sed vitae euismod urna. Nulla ullamcorper, odio et aliquam ultrices, ligula augue ullamcorper tellus, sed sollicitudin neque odio ac lorem. Aliquam sollicitudin imperdiet vestibulum.Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vestibulum ante mauris, imperdiet quis adipiscing tristique, viverra et leo. Nulla id arcu neque. Donec a orci nisi. Vestibulum pellentesque ligula eget arcu tempor eu ornare velit vulputate. Proin consequat arcu in justo cursus quis dapibus dolor suscipit. Sed volutpat purus et massa eleifend at facilisis risus ullamcorper. Cras ligula nunc, rhoncus nec hendrerit quis, bibendum quis lectus. Morbi a justo at orci dictum vestibulum. Cras tristique auctor viverra. In magna massa, bibendum vitae tempor sed, vehicula sit amet purus.\n"
"\n"
"Praesent orci elit, commodo bibendum congue ac, dictum sit amet justo. Nullam tempus porttitor libero, sit amet ullamcorper urna congue et. Sed vel leo quis tellus ullamcorper tincidunt vitae vitae risus. Donec commodo semper quam, quis porta mauris auctor id. Nunc molestie lectus ac justo tristique at laoreet arcu viverra. In erat lorem, mattis porta tempor vel, tincidunt eu dui. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Duis id tortor eget lorem auctor elementum. Suspendisse dignissim elit ut dui pharetra lobortis. Nam nec libero odio, ut placerat nulla. Nulla rutrum condimentum velit ut vulputate. Proin ullamcorper mi eu odio porta fringilla. Sed vitae euismod urna. Nulla ullamcorper, odio et aliquam ultrices, ligula augue ullamcorper tellus, sed sollicitudin neque odio ac lorem. Aliquam sollicitudin imperdiet vestibulum.", None, QtGui.QApplication.UnicodeUTF8))

from . import resources_rc
