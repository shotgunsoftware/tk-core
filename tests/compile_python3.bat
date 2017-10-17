;; Copyright (c) 2017 Shotgun Software Inc.
;; 
;; CONFIDENTIAL AND PROPRIETARY
;; 
;; This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
;; Source Code License included in this distribution package. See LICENSE.
;; By accessing, using, copying or modifying this work you indicate your 
;; agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
;; not expressly granted therein are reserved by Shotgun Software Inc.

python.exe -m compileall ..\python\tank ..\python\sgtk run_tests.py run_integration_tests.py authentication_tests bootstrap_tests commands_tests core_tests deploy_tests descriptor_tests folder_tests platform_tests tank_test_tests util_tests python\tank_test 