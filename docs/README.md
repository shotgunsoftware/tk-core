# Shotgun Pipeline Toolkit Documentation

This folder contains scripts to generate **API documentation** for the Shotgun Pipeline Toolkit. By using the `make_docs.py` script, Sphinx style documentation is generated in a standardized fashion.

## Generating docs for core

Execute the doc generation script and pass the version of core that you are generating docs for:

```
> python /path/to/tk-core/docs/make_docs.py --version=v0.16.65
```

Documentation will be generated in `/path/to/tk-core/docs/build`.

If you want to edit the core documentation, you'll find it in `/path/to/tk-core/docs/tk-core`.


## Generating docs for an app

For apps, engines and framework requiring API documentation, create a `docs` folder and add `.rst` files in that location as needed.


## Referencing other classes

The default doc generation setup includes resolving cross references so that your sphinx docstrings automatically links up with Python, PySide and Toolkit. Below is an example showing how this works:

```python
def example_method(self, parent, app, sg_model):
	"""
	Example docstring showing how to hyperlink to other APIs.
	    
	:param parent: Parent window to attach to.
	:type parent: :class:`~PySide.QtGui.QWidget`
	    
	:param app: Toolkit app to associate with 
	:type app: :class:`~sgtk.platform.Application`
	    
	:param sg_model: Overlay model to attach
	:type sg_model: :class:`~tk-framework-shotgunutils:shotgun_model.ShotgunOverlayModel` 
	"""
```

Note the use of the tilde-style syntax above -- this means that the short form `ShotgunOverlayModel` will be displayed in the generated documentation rather than `shotgun_model.ShotgunOverlayModel`.

If you are referencing classes or methods from other Toolkit frameworks, use the syntax `tk-framework-xyz:module.Class`. If you want to reference a Toolkit core method, you can reference `sgtk` directly.

