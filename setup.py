from distutils.core import setup
setup(
    name="sgtk",
    version="0.18",
    packages=[
        "sgtk",
        "tank",
        "tank.authentication",
        "tank.bootstrap",
        "tank.commands",
        "tank.deploy",
        "tank.descriptor",
        "tank.descriptor.io_descriptor",
        "tank.folder",
        "tank.platform",
        "tank.platform.qt",
        "tank.util",
        "tank_vendor",
        "tank_vendor.ruamel_yaml",
        "tank_vendor.shotgun_api3",
        "tank_vendor.shotgun_api3.lib",
        "tank_vendor.shotgun_api3.lib.httplib2",
        "tank_vendor.shotgun_authentication",
        "tank_vendor.yaml",
    ],
    package_data={
        "tank.descriptor": ["resources/*"],
        "tank.util": ["resources/*"],
        "tank.platform.qt" : [
            "*.png", "*.sh", "*.ui", "*.qrc", "*.css", "*.qpalette",
        ],
    },
    package_dir = {"": "python"}
)