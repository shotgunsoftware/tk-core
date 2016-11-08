#!/Applications/Shotgun.app/Contents/Frameworks/Python/bin/python


import sys
from PySide.QtCore import QObject, Slot
from PySide.QtGui import QApplication
from PySide.QtWebKit import QWebView

html = """
<html>
<body>
    <h1>Hello!</h1><br>
    <h2><a href="#" onclick="printer.text('Message from QWebView')">QObject Test</a></h2>
    <h2><a href="#" onclick="alert('Javascript works!')">JS test</a></h2>
</body>
</html>
"""

class ConsolePrinter(QObject):
    def __init__(self, parent=None):
        super(ConsolePrinter, self).__init__(parent)

    @Slot(str)
    def text(self, message):
        print message

if __name__ == '__main__':
    app = QApplication(sys.argv)
    view = QWebView()
    frame = view.page().mainFrame()
    printer = ConsolePrinter()
    view.setHtml(html)
    frame.addToJavaScriptWindowObject('printer', printer)
    frame.evaluateJavaScript("alert('Hello');")
    frame.evaluateJavaScript("printer.text('Goooooooooo!');")
    view.show()
    app.exec_()
