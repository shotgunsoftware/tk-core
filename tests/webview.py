#!/Applications/Shotgun.app/Contents/Frameworks/Python/bin/python


import sys
from PySide.QtCore import QObject, Slot, QEventLoop
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

class TemporaryEventLoop(QEventLoop):
    """
    Local event loop for the session token renewal. The return value of _exec()
    indicates what happen.
    """

    def __init__(self, app, parent=None):
        """
        Constructor
        """
        QEventLoop.__init__(self, parent)
        self._webView = app.view
        self._site = 'https://okr-staging.shotgunstudio.com'
        self._webView.loadFinished.connect(self._page_onFinished)
        # systray.login.connect(self._login)
        # systray.quit.connect(self._quit)

    def _page_onFinished(self):
        """
        Called when "Quit" is selected. Exits the loop.
        """
        url = self._webView.url().toString()
        print "=-=-=-=-=-=-=-=> _page_onFinished: %s" % url
        if url.startswith(self._site):
            self.exit(QtGui.QDialog.Accepted)
        # else:
        #     self.exit(QtGui.QDialog.Rejected)

    def exec_(self):
        """
        Execute the local event loop. If CmdQ was hit in the past, it will be handled just as if the
        user had picked the Quit menu.

        :returns: The exit code for the loop.
        """
        code = QEventLoop.exec_(self)
        # Somebody requested the app to close, so pretend the close menu was picked.
        print "code: %s" % code
        return code

class ConsolePrinter(QObject):
    def __init__(self, parent=None):
        super(ConsolePrinter, self).__init__(parent)

    @Slot(str)
    def text(self, message):
        print message

def _page_onFinished(self):
    print "_page_onFinished"

if __name__ == '__main__':
    app = QApplication(sys.argv)
    view = QWebView()
    frame = view.page().mainFrame()
    printer = ConsolePrinter()
    # view.setHtml(html)
    # frame.addToJavaScriptWindowObject('printer', printer)
    # frame.evaluateJavaScript("alert('Hello');")
    # frame.evaluateJavaScript("printer.text('Goooooooooo!');")
    view.loadFinished.connect(_page_onFinished)
    view.resize(50, 50)
    view.load('https://okr-staging.shotgunstudio.com')
    # view.show()
    app.view = view
    TemporaryEventLoop(app).exec_()
    # app.exec_()
