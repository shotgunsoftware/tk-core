# -*- coding: utf-8 -*-
# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import tempfile
import json
import os
import sys

from unittest import TestCase
from sgtk.util import json as tk_json
from sgtk.util import pickle

from tank_vendor import six


class Impl:
    class SerializationTests(TestCase):
        """
        Ensures unserializing from file or a string will always yield
        str objects instead of unicode.
        """

        kanji = "漢字"

        dict_with_unicode = {
            kanji: [kanji, kanji, kanji],
            "number": 1,
            "boolean": True,
            "float": 1.5,
            "None": None,
        }

        def _value_to_string_to_value(self, value):
            """
            Dumps a value to a json formatted string and reloads it.

            :param value: Value to dump to a string.

            :returns: Value that was loaded back from the string.
            """
            return self.loads(self.dumps(value))

        def loads(self, data):
            return self.loader_module.loads(data)

        def load(self, fh):
            return self.loader_module.load(fh)

        def dumps(self, data):
            return self.dumper_module.dumps(data)

        def dump(self, data, fh):
            self.dumper_module.dump(data, fh)

        def _value_to_file_to_value(self, value):
            """
            Dumps a value to a json formatted file and reloads it.

            :param value: Value to dump to a file.

            :returns: Value that was loaded back from the file.
            """
            with tempfile.TemporaryFile(mode="{0}+".format(self.write_mode)) as fp:
                self.dump(value, fp)
                # Return at the beginning of the file so the load method can read
                # something.
                fp.seek(0)
                return self.load(fp)

        def _assert_no_unicode(self, value):
            """
            Ensures there is no unicode anywhere inside the value.

            Just make sure there the string "u'" is not in the original value. ;)
            """
            # Get the repr of the value. If there is a unicode string,
            # we'll get a u'value' somewhere in the output, which means
            # there is a unicode string.
            if "u'" in repr(value):
                raise Exception("unicode string found in %r" % value)

        def _assert_no_bytes(self, value):
            """
            Ensures there is no bytes anywhere inside the value.

            Just make sure there the string "b'" is not in the original value. ;)
            """
            # Get the repr of the value. If there is a bytes object,
            # we'll get a b'value' somewhere in the output, which means
            # it contains bytes.
            if "b'" in repr(value):
                raise Exception("bytes found in %r" % value)

        def test_repr_detection(self):
            """
            Ensures the unicode or bytes detection method actually works.
            """
            if six.PY2:
                self._assert_no_unicode({})
                self._assert_no_unicode(1)
                self._assert_no_unicode(False)
                self._assert_no_unicode(None)
                self._assert_no_unicode(self.kanji)
                self._assert_no_unicode({"k": "v"})

                with self.assertRaisesRegex(
                    Exception, "unicode string found in u'allo'"
                ):
                    self._assert_no_unicode(u"allo")
            elif six.PY3:
                self._assert_no_bytes({})
                self._assert_no_bytes(1)
                self._assert_no_bytes(False)
                self._assert_no_bytes(None)
                self._assert_no_bytes(self.kanji)
                self._assert_no_bytes({"k": "v"})

                with self.assertRaisesRegex(Exception, "bytes found in b'allo'"):
                    self._assert_no_bytes(b"allo")

        def test_scalar_values(self):
            """
            Ensures we can properly encode scalar values.
            """
            if six.PY2:
                # In the case of Python2, ensure that we get str instances back with
                # no unicode after loading.
                assertion = self._assert_no_unicode_after_load
            else:
                # For Python3 and above, ensure that no bytes objects are returned
                # after loading.
                assertion = self._assert_no_bytes_after_load

            # Integer
            assertion(1)
            # BigNum
            assertion(100000000000000000000000)
            # Floats
            assertion(1.0)
            # Booleans
            assertion(True)
            assertion(False)
            # None
            assertion(None)
            # Strings
            assertion("a")
            assertion(u"a")
            assertion(self.kanji)

        def test_array_values(self):
            """
            Ensure we can properly encode an array.
            """
            self._assert_no_unicode_after_load(
                [
                    1,
                    100000000000000000000000,
                    1.0,
                    True,
                    False,
                    None,
                    {"a": "b", u"c": u"d"},
                    "e",
                    u"f",
                ]
            )

        def test_dict_value(self):
            """
            Ensures we can properly encode a dictionary.
            """
            self._assert_no_unicode_after_load({})
            self._assert_no_unicode_after_load({"a": "b", u"c": u"d"})
            self._assert_no_unicode_after_load({"e": ["f"], u"g": [u"h"]})
            self._assert_no_unicode_after_load(
                {"i": [{"j": ["k"]}], u"l": [{u"m": [u"n"]}]}
            )

        def _assert_no_unicode_after_load(self, original_value):
            """
            Ensures the values are the same after the serialize/unserialize and that the
            strings are all str and not unicode objects.
            """
            # We need to test serialization to disk and to string for the input.
            for converter in [
                self._value_to_string_to_value,
                self._value_to_file_to_value,
            ]:
                converted_value = converter(original_value)

                self._assert_no_unicode(converted_value)
                self.assertEqual(original_value, converted_value)

        def _assert_no_bytes_after_load(self, original_value):
            """
            Ensures the values are the same after the serialize/unserialize and that the
            strings are all text and not binary.
            """
            # We need to test serialization to disk and to string for the input.
            for converter in [
                self._value_to_string_to_value,
                self._value_to_file_to_value,
            ]:
                converted_value = converter(original_value)

                self._assert_no_bytes(converted_value)
                self.assertEqual(original_value, converted_value)

        def test_reload_across_python_version(self):
            """
            Ensures reloading JSON written by any version of Python works in the current
            Python version.
            """
            with open(self.file_location(2, 7), "rb") as fh:
                self.assertEqual(self.load(fh), self.dict_with_unicode)

            with open(self.file_location(3, 7), "rb") as fh:
                self.assertEqual(self.load(fh), self.dict_with_unicode)

            with open(self.file_location(3, 9), "rb") as fh:
                self.assertEqual(self.load(fh), self.dict_with_unicode)

            with open(self.file_location(2, 7), "r{0}".format(self.mode)) as fh:
                self.assertEqual(self.loads(fh.read()), self.dict_with_unicode)

            with open(self.file_location(3, 7), "r{0}".format(self.mode)) as fh:
                self.assertEqual(self.loads(fh.read()), self.dict_with_unicode)

            with open(self.file_location(3, 9), "r{0}".format(self.mode)) as fh:
                self.assertEqual(self.loads(fh.read()), self.dict_with_unicode)

        fixtures_location = os.path.join(
            os.path.dirname(__file__), "..", "fixtures", "util_tests"
        )

        @classmethod
        def file_location(cls, python_major, python_minor):
            return os.path.join(
                cls.fixtures_location, cls.filename.format(python_major, python_minor)
            )


class JSONTests(Impl.SerializationTests):

    # Parametrizes the tests from the base class.
    filename = "json_saved_with_python_{0}.{1}.json"
    mode = "t"
    write_mode = "wb" if six.PY2 else "wt"
    loader_module = tk_json
    dumper_module = json


class PickleTests(Impl.SerializationTests):

    # Parametrizes the tests from the base class.
    filename = "pickle_saved_with_python_{0}.{1}.pickle"
    mode = "b"
    write_mode = "wb"
    loader_module = pickle
    dumper_module = pickle

    # Derived class parameters.
    protocol_2_file_location = os.path.join(
        Impl.SerializationTests.fixtures_location,
        "pickled_saved_with_python_2_protocol_0.pickle",
    )

    def test_reload_protocol_2_pickle(self):
        with open(self.protocol_2_file_location, "rb") as fh:
            self.assertEqual(self.load(fh), self.dict_with_unicode)

        with open(self.protocol_2_file_location, "rb") as fh:
            self.assertEqual(self.loads(fh.read()), self.dict_with_unicode)


if __name__ == "__main__":
    # Generates the test files. From the folder this file is in run

    # PYTHONPATH=../../python python test_json_and_pickle.py
    # with python 2 and python 3 to generate the files.
    file_path = JSONTests.file_location(sys.version_info[0], sys.version_info[1])
    with open(file_path, "wt") as fh:
        json.dump(JSONTests.dict_with_unicode, fh, sort_keys=True)

    file_path = PickleTests.file_location(sys.version_info[0], sys.version_info[1])
    with open(file_path, "wb") as fh:
        pickle.dump(PickleTests.dict_with_unicode, fh)

    if six.PY2:
        # call directly the cPickle.dump method. Older Toolkit cores
        # would save pickles with protocol==2, so make sure we can
        # read those as well with the pickle module wrapper.
        import cPickle

        with open(PickleTests.protocol_2_file_location, "wb") as fh:
            cPickle.dump(PickleTests.dict_with_unicode, fh, protocol=2)
