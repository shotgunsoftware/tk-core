# -*- coding: utf-8 -*-

name = 'tk_core'

version = "0.19.10"

requires = []

tools = []

build_command = "python {root}/rezbuild.py {install}"


def commands():
    env.PEARL_TK_CORE_LOCATION = "{root}"
    env.PYTHONPATH.append("{root}/python")
    env.PATH.append("{root}/scripts")
    env.SGTK_CORE_LOCATION = '{root}'
    env.SGTK_CORE_LOCATION = "{root}"



format_version = 2
