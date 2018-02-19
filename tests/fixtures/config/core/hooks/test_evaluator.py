# Copyright (c) 2018 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank import Hook


class TestEvaluator(Hook):
    
    def execute(self, setting, bundle_obj, extra_params, **kwargs):
        """
        Procedural settings evaluator.

        If applied to an env setting like this:

        > app_setting: hook:test_evaluator:foo:bar

        This hook will get called with the following syntax:

        setting='app_setting', bundle_obj=<the app>, extra_params=['foo', 'bar']

        :param str setting: The name of the setting for which we are evaluating.
        :param bundle_obj: The associated app, engine or framework object.
        :param extra_params: List of options passed from the setting. If the settings
            string is "hook:hook_name:foo:bar", extra_params would
            be ['foo', 'bar']

        returns: a value expected by the overridden setting.
        """

        # we expect the following setup in our test environment:
        #
        # test_str_evaluator: hook:test_evaluator
        # test_int_evaluator: hook:test_evaluator
        # test_simple_dictionary_evaluator: hook:test_evaluator:param

        if setting == "test_str_evaluator":
            return "string_value"
        if setting == "test_int_evaluator":
            return 1
        if setting == "test_simple_dictionary_evaluator":
            #
            # we are grabbing the value passed from the configuration
            # and passing it back. In this particular case, tests
            # are calling it with the following env config syntax:
            #
            # test_simple_dictionary_evaluator: hook:test_evaluator:param
            #
            # ...which will result in extra_params[0]=='param'
            #
            return {"test_str": extra_params[0], "test_int": 1}
