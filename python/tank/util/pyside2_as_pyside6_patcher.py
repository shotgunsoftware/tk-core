class PySide2asPySide6Patcher:
    @staticmethod
    def _patch_QtWebEngineCore(qt_webengine_core, classes):
        for cls in classes:
            setattr(qt_webengine_core, cls.__name__, cls)
        return qt_webengine_core
    
    @staticmethod
    def _patch_QtGui(qt_gui, classes):
        for cls in classes:
            setattr(qt_gui, cls.__name__, cls)
        return qt_gui