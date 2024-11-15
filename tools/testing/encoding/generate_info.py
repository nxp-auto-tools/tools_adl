# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package generate_info
# Module for writing information inside info.py

import sys
import parse
import os

## Writes the information about instructions and operands in info.py
# @param file_name Name of the adl file
# @param instr_op_dict A dictionary with instructions as keys and a list of operands as values
# @param op_val_dict A dictionary with operands as keys and a list of values as their values
def generate_info_file(file_name, instr_op_dict, op_val_dict):

    adl_file_path = sys.argv[1]
    cmd_extensions = sys.argv[2]
    cmd_ext = cmd_extensions.split(",")

    # Get the path of the script
    script_directory = os.path.dirname(os.path.abspath(__file__))
    info_file_path = os.path.join(script_directory, file_name)

    # A dictionary with instructions and associated attribute prefixes
    instruction_attribute_dict, new_instruction_attribute_dict = parse.instruction_attribute(adl_file_path)

    f = open(info_file_path, "w")
    f.write("#Copyright 2024 NXP\n") 
    f.write("#SPDX-License-Identifier: BSD-2-Clause\n\n")
    # print the instructions - operands dictionary
    f.write("instructions = {\n")
    for i, (key, value) in enumerate(instr_op_dict.items()):
        # generate tests only for specific extensions
        if any(element in cmd_ext for element in instruction_attribute_dict[key]):
            if i == len(instr_op_dict) - 1:
                f.write(f"\t'{key}' : {value}\n")
            else:
                f.write(f"\t'{key}' : {value},\n")
    f.write("}\n\n")
    # print the operands - values dictionary
    f.write("operands = {\n")
    for i, (key, value) in enumerate(op_val_dict.items()):
        if i == len(op_val_dict) - 1:
            f.write(f"\t'{key}' : {value}\n")
        else:
            f.write(f"\t'{key}' : {value},\n")
    f.write("}")
    f.close()
