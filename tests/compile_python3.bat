:: Copyright (c) 2017 Shotgun Software Inc.
::
:: CONFIDENTIAL AND PROPRIETARY
::
:: This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
:: Source Code License included in this distribution package. See LICENSE.
:: By accessing, using, copying or modifying this work you indicate your
:: agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
:: not expressly granted therein are reserved by Shotgun Software Inc.

::
:: Allows to compile all the Toolkit source code with a Python executable. Due to limitations on
:: Windows, you need to make sure the python interpreter in your environment is a Python 3
:: interpreter in order to actually compile with Python 3.
::

python.exe -m compileall ..\python\tank
python.exe -m compileall *.py
python.exe -m compileall authentication_tests bootstrap_tests commands_tests core_tests deploy_tests descriptor_tests folder_tests platform_tests tank_test_tests util_tests python\tank_test