import sys

from PySide2 import QtWidgets




class MyProxyStyle(QtWidgets.QProxyStyle):
    def pixelMetric(self, metric, option=None, widget=None):
#         print(f"""MyProxyStyle::pixelMetric
#   {metric=}
#   {option=}
#   {widget=}""")
        r = super().pixelMetric(metric, option=option, widget=widget)
        if metric == QtWidgets.QStyle.PixelMetric.PM_MenuButtonIndicator:
            # r2 = 64
            r2 = r*2
        elif metric == QtWidgets.QStyle.PixelMetric.PM_ButtonIconSize:
            # r2 = 64
            r2 = r*2
        elif metric == QtWidgets.QStyle.PixelMetric.PM_ButtonDefaultIndicator:
            # r2 = 10
            r2 = r*2
        elif metric == QtWidgets.QStyle.PixelMetric.PM_DefaultFrameWidth:
            # r2 = 4
            r2 = r*2
        else:
            r2 = r

        #print("   =>", r, "set to", r2)
        # if isinstance(r, int):
        #     r = r*4
        #else:
        #    print(f"MyProxyStyle::pixelMetric {metric=} {option=} {widget=}=> {r=}")

        return r

    def sizeFromContents(self, *args, **kwargs):
        r = super().sizeFromContents(*args, **kwargs)
        print(f"""MyProxyStyle::sizeFromContents
  {args=}
  {kwargs=}
  {r=}
""")
        # if isinstance(r, QtCore.QSize): # does not work because a PySide2.QtCore.QSize and not  a Patch Qsize
        r.setWidth(r.width() * 2)
        r.setHeight(r.height() * 2)
        print("   override !!!!", r)

        return r




app = QtWidgets.QApplication(sys.argv)

print("Qapp::style:", QtWidgets.QApplication.style())
print()
proxy = MyProxyStyle() #QtWidgets.QApplication.style())
#QtWidgets.QApplication.setStyle(proxy)

dlg = QtWidgets.QDialog()
dlg.resize(424, 304)

vl = QtWidgets.QVBoxLayout(dlg)

l1 = QtWidgets.QLabel("Salut")
vl.addWidget(l1)

# m1
button_options = QtWidgets.QPushButton(dlg)
button_options.setText("Menu 1")

menu = QtWidgets.QMenu(button_options)
menu.addAction("Test1")
menu.addAction("Test2")

button_options.setMenu(menu)
vl.addWidget(button_options)


# m2
button_options = QtWidgets.QPushButton(dlg)
button_options.setText("Menu 2")
# button_options.setWeight(18)
fontD = button_options.font()
print("font:", button_options.font())

fontD.setPointSize(24)

menu = QtWidgets.QMenu(button_options)
menu.addAction("Test1")
menu.addAction("Test2")

button_options.setMenu(menu)
vl.addWidget(button_options)

button_options.setStyle(proxy)


dlg.exec_()
