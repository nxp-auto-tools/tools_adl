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
    string = """// Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
// This file is generated, DO NOT EDIT IT DIRECTLY!\n\n
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
        else:
            f = open(filename, "w")
            f.write(string)
            f.close()
    else:
        f = open(filename, "w")
        f.write(string)
        f.close()

## A function that will return the string for determining its length
#
# @return It will return the strings
def get_copyright_len():
    string = """// Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
// This file is generated, DO NOT EDIT IT DIRECTLY!\n\n
"""
    return string


## A simple wrapper on top of a file
#
# @param filename The file it writes into
# @return A basic string
def get_generated_file(filename):
    string = """"""
    list_dir = list()
    for fname in os.listdir("."):
        list_dir.append(fname)
    if "tools" not in list_dir:
        if filename.startswith("./"):
            filename = "." + filename
            f = open(filename, "a")
            f.write(string)
            f.close()
        else:
            f = open(filename, "w")
            f.write(string)
            f.close()
    else:
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

def add_sail_license(filename):
    string = """/*=======================================================================================*/
/*  This Sail RISC-V architecture model, comprising all files and                        */
/*  directories except where otherwise noted is subject the BSD                          */
/*  two-clause license in https://github.com/riscv/sail-riscv/blob/master/LICENCE.                                              */
/*                                                                                       */
/*  SPDX-License-Identifier: BSD-2-Clause                                                */
/*=======================================================================================*/
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
        else:
            f = open(filename, "w")
            f.write(string)
            f.close()
    else:
        f = open(filename, "w")
        f.write(string)
        f.close()