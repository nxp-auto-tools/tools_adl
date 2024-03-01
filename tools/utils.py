# Copyright 2024 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package utils
#
# Helper functions
import config
import os

## Remove all registers that contain one of ignored attributes defined in config.txt
#
# @param registers A dictionary containing the object information of the register files
# @return None
config_file = "config.txt"
llvm_config = "llvm_config.txt"
list_dir = list()
for fname in os.listdir("."):
    list_dir.append(fname)
if "tools" in list_dir:
    config_file = "./tools/config.txt"
    llvm_config = "./tools/llvm_config.txt"


## Remove all registers that are marked as 'ignored' based on the attributes
#
# @param register Dictionary containing all the registers
# @return None
def remove_ignored_attrib_regs(registers):
    config_variables = config.config_environment(config_file, llvm_config)
    delete = [
        key
        for key in registers.keys()
        if "CSRAttrib" in config_variables.keys()
        and config_variables["CSRAttrib"] in registers[key].attributes
    ]
    for key in delete:
        del registers[key]
    for attribute in config_variables["IgnoredAttrib"]:
        delete = [
            key for key in registers.keys() if attribute in registers[key].attributes
        ]
        for key in delete:
            del registers[key]


## Verifies if a register class has prefix or not
#
# @param regclass A dictionary containing the object information of the register files
# @param key The fields of a register file
# @return True/False
def check_register_class_prefix(regclass, key):
    if regclass[key].prefix == "":
        return False
    else:
        return True


## Takes the offset for an instruction field
#
# @param instrfield_data The data inside instrfield
# @return A dictionary containing tuples (width, offset, shift) based on 'ref' tag
def get_instrfield_offset(instrfield_data):
    instrfield_offset = dict()
    for key in instrfield_data.keys():
        ref = instrfield_data[key]["ref"]
        width = instrfield_data[key]["width"]
        offset = instrfield_data[key]["offset"]
        shift = instrfield_data[key]["shift"]
        element = (width, offset, shift)
        list_offset = list()
        list_offset.append(element)
        if ref not in instrfield_offset.keys():
            instrfield_offset[ref] = list_offset
        else:
            if element not in instrfield_offset[ref]:
                instrfield_offset[ref] += list_offset
    return instrfield_offset
