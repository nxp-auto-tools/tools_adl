# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package utils
#
# Helper functions
import config
import os

"""
Remove all registers that contain one of ignored attributes defined in config.txt

Args:
    registers A dictionary containing the object information of the register files
Returns:
    None
"""
config_file = "config.txt"
llvm_config = "llvm_config.txt"
list_dir = list()
for fname in os.listdir("."):
    list_dir.append(fname)
config_file = os.path.dirname(__file__).replace("\\", "/") + "/" + "config.txt"
llvm_config = os.path.dirname(__file__).replace("\\", "/") + "/" + "llvm_config.txt"


def remove_ignored_attrib_regs(registers):
    """
    Removes all registers that are marked as 'ignored' based on their attributes.

    This function iterates over the register definitions and filters out any
    register entry explicitly marked with an attribute such as 'ignored',
    effectively cleaning the register set before further processing.

    Args:
        registers (dict): Dictionary containing all register definitions.

    Returns:
        None
    """
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


def check_register_class_prefix(regclass, key):
    """
    Checks whether a register class has a prefix defined.

    The function inspects the data associated with a specific register file
    (identified by `key`) inside the `regclass` dictionary and determines
    whether a prefix attribute is present.

    Args:
        regclass (dict): Dictionary containing the object information for all
            register files.
        key (str): Identifier for the register file whose prefix should be checked.

    Returns:
        bool: True if the register class has a prefix, False otherwise.
    """
    if regclass[key].prefix == "":
        return False
    else:
        return True


def get_instrfield_offset(instrfield_data):
    """
    Extracts offset‑related information for an instruction field.

    Based on the contents of the `instrfield_data` structure, this function
    parses the `ref` tag and returns a dictionary where each key corresponds
    to a referenced field, and each value is a tuple containing:
        - width
        - offset
        - shift

    Args:
        instrfield_data (dict | Any): Data structure containing the instruction
            field information, typically parsed from XML.

    Returns:
        dict: A dictionary mapping field names to tuples of the form
            (width, offset, shift).
    """
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
