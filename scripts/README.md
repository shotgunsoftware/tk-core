# Shotgun Pipeline Toolkit Core API

## How to upgrade pyyaml

This package is a vendor widely used by `sgtk` to parse configuration files
in YAML format.

This package is shipped in source format, that means that only `*.py` are
included in `python/tank_vendor/yaml` for python versions 2.7 and 3.

If you need to upgrade this package you can use the script `upgrade_pyyaml.py`.

```shell
cd tk-core/scripts
python upgrade_pyyaml.py
```

After running the script the old `python/tank_vendor/yaml` will be moved to `python/tank_vendor/yaml.old`. 

**Note:** `python/tank_vendor/yaml.old` folder is included in `.gitignore` and won't be pushed to remote git repo. 