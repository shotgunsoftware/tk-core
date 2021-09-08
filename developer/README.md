# Shotgun Pipeline Toolkit Core API

## How to upgrade pyyaml

This package is a vendor widely used by `sgtk` to parse configuration files
in YAML format.

This package is shipped in source format, that means that only `*.py` are
included in `python/tank_vendor/yaml` for python versions 2.7 and 3.

If you need to upgrade this package you can use the script `upgrade_pyyaml.py`.

```shell
cd tk-core/developer
python upgrade_pyyaml.py
```
