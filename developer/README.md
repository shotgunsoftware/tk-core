# Flow Production Tracking Core API

## How to upgrade pyyaml

This package is a vendor widely used by `sgtk` to parse configuration files
in YAML format.

This package is shipped in source format, that means that only `*.py` are
included in `python/tank_vendor/yaml`.

If you need to upgrade this package you can use the script `upgrade_pyyaml.py`.

```shell
cd tk-core/developer
python upgrade_pyyaml.py
```

## How to upgrade ruamel.yaml

Until version `0.10.10`, the contents of the library was located at `tank_vendor/ruamel_yaml`.
However, starting from `0.18.14`, we had to change it to `tank_vendor/ruamel/yaml`.

Just to confirm, the contents of the PIP package should be placed in `tank_vendor`.

```bash
pip install ruamel.yaml -t path/to/tank_vendor
```

Then, let's remove all undesired directories and files, just leave the `ruamel` directory.
We can automate this task later.

## The requirements.txt file

The file `developer/requirements.txt` is not used to install any packages,
however exists so that automated checks for CVEs in dependencies will know about
bundled packages in `python/tank_vendor`.

For this reason, it's important to add any newly bundled packages to this file,
and to keep the file up to date if the bundled version of a module changes.
