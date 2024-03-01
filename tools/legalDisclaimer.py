# Copyright 2024 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package legalDisclaimer
#
# The module which generates legal information about the current project
from datetime import date
import os


## A simple wrapper on top of a file
# It can add the copyright and "generated" comments
#
# @param filename The file it writes into
# @return The string representing copyright
def get_copyright(filename):
    string = """// Copyright 2024 NXP
// SPDX-License-Identifier: BSD-2-Clause
"""
    list_dir = list()
    for fname in os.listdir("."):
        list_dir.append(fname)
    if "tools" not in list_dir:
        if filename.startswith("./"):
            filename = "." + filename
    f = open(filename, "w")
    f.write(string)
    f.close()


## A function that will return the string for determining its length
#
# @return It will return the strings
def get_copyright_len():
    string = """// Copyright 2024 NXP
// SPDX-License-Identifier: BSD-2-Clause
"""
    return string


## A simple wrapper on top of a file
#
# @param filename The file it writes into
# @return A basic string
def get_generated_file(filename):
    string = """
// This file is generated, DO NOT EDIT IT DIRECTLY!\n
"""
    list_dir = list()
    for fname in os.listdir("."):
        list_dir.append(fname)
    if "tools" not in list_dir:
        if filename.startswith("./"):
            filename = "." + filename
    f = open(filename, "a")
    f.write(string)
    f.close()


## A function that will return the string for determining its length
#
# @return It will return the string
def get_generated_file_len():
    string = """
// This file is generated, DO NOT EDIT IT DIRECTLY!\n
"""
    return string
