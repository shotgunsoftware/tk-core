# Shotgun Pipeline Toolkit Documentation

This folder contains scripts to generate **API documentation** for the Shotgun Pipeline Toolkit. By using the `make_docs.py` script, Sphinx style documentation is generated in a standardized fashion.


## Generating docs for an app





For Apps, Frameworks and Engines, stored in Github, we recommend that user documentation is kept in the associated github wiki. For standard API documentation, for example for frameworks, this folder contains the necessary scripts and configuration needed to build a sphinx html repository 



## Referencing other classes

The defauly doc generation setup includes working cross references so that your sphinx docstrings can automatically link up with both Python, PySide and Toolkit. Below is an example showing how this works:

```python
def example_method(self, parent, app, sg_model):
	"""
	Example docstring showing how to hyperlink to other APIs.
	    
	:param parent: Parent window to attach to.
	:type parent: :class:`PySide.QtGui.QWidget`
	    
	:param app: Toolkit app to associate with 
	:type app: :class:`sgtk.platform.Application`
	    
	:param sg_model: Overlay model to attach
	:type sg_model: :class:`tk-framework-shotgunutils:shotgun_model.ShotgunOverlayModel` 
	"""
```

