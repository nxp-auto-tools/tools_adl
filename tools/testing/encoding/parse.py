# Copyright 2023-2025 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package parse
# The module for parsing and extracting information about instructions from adl

import xml.etree.ElementTree as ET
import re
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "./../../"))
import config


## Extract info about architecture and attributes
# @param adl_file Name of the adl file
# @return @b architecture-> Name of the architecture from adl
# @return @b attributes-> Attribute info for the current architecture
# @return @b mattrib-> Attributes passed as arguments in command line
def assembler_and_cmdLine_args(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    for cores in root.iter("cores"):
        for asm_config in cores.iter("asm_config"):
            architecture = asm_config.find("arch").find("str").text
            attributes = asm_config.find("attributes").find("str").text
            mattrib = asm_config.find("mattrib").find("str").text
            
    return architecture, attributes, mattrib

## Extract info about instructions and their operands
# @param adl_file Name of the adl file
# @return @b instr_op_dict-> A dictionary containing instructions as keys and a list of operands as values
# @return @b instr_name_syntaxName_dict-> A dictionary with instruction names as keys and their associated syntax name
# @return @b imm_width-> A dicitionary with all the immediates as keys and their corresponding width as value
# @return @b imm_shift-> A dicitionary with all the immediates as keys and their corresponding shift as value
# @return @b imm_signed-> A dicitionary with all the immediates as keys and a boolean value for being signed or not
# @return @b instr_field_value_dict-> A dictionary with instruction names as keys and a list of tuples as values. Each tuple represents a pair between field name and value.
def instructions_operands(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    # Get the path of the script
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    registers = list()
    model_only = list()
    ignored = list()
    only_take_attributes = list()
    imm_width = dict()
    imm_shift = dict()
    imm_signed = dict()
    instr_op_dict = dict()
    instr_name_syntaxName_dict = dict()
    instr_field_value_dict = dict()
    llvm_config_dict = config.config_environment(os.path.join(script_directory, "../../config.txt"), os.path.join(script_directory, "../../llvm_config.txt"))

    # select only desired attributes
    selected_keys = {key for key in llvm_config_dict.keys() if key.startswith('HasStd') and key.endswith('Extension')}

    for cores in root.iter("cores"):
        # extract all registers from adl
        for instrfield in cores.iter("instrfield"):
            for ref in instrfield.iter("ref"):
                if (ref.find("str").text is not None):
                    registers.append(instrfield.get("name"))
        # extract all immediates from adl with additional info
        for instrfield in cores.iter("instrfield"):
            immediate = instrfield.get("name")
            signed_text = "false"
            for width in instrfield.iter("width"):
                width_text = int(width.find("int").text)
            for shift in instrfield.iter("shift"):
                shift_text = int(shift.find("int").text)
                width_text += shift_text
            for signed in instrfield.iter("signed"):
                signed_text = signed.find("str").text

            imm_width[immediate] = width_text
            imm_shift[immediate] = shift_text
            imm_signed[immediate] = signed_text
        # check if the instruction is a pseudo instruction or has alias_action
        for instruction in cores.iter("instruction"):
            if (instruction.find("pseudo")) or (instruction.find("alias_action")):
                continue
            else:
                name = instruction.get("name")
                # get each instruction field name and value stored inside a list tuples as value of dict
                field_name_value = []
                for field in instruction.iter("field"):                
                    if (field.get("name") is not None):
                        field_name = field.get("name")
                        if(field.find("str") is not None):
                            field_value = field.find("str").text
                        else:
                            field_value = field.find("int").text
                        field_name_value.append((field_name, field_value))
                instr_field_value_dict[name] = field_name_value
                # get instruction instrfield name if the instruction is not alias or hint, else take syntax name
                for syntax in instruction.iter("syntax"):
                    syntax_text = str(syntax.find("str").text).split()
                    syntax_name = syntax_text[0]
                # check if the instruction is model_only
                for attribute in instruction.iter("attribute"):
                    if attribute.get("name") == "model_only":
                        model_only.append(instruction.get("name"))
                # check if the instruction is ignored
                for attribute in instruction.iter("attribute"):
                    if attribute.get("name") == "ignored":
                        ignored.append(instruction.get("name"))                
                # check if the instruction has one of the specified attributes    
                for attribute in instruction.iter("attribute"):
                    if any(attribute.get("name") == str.lower(llvm_config_dict[key]) for key in selected_keys):
                        only_take_attributes.append(instruction.get("name"))          
                # extract the syntax of the instruction
                for syntax in instruction.iter("syntax"):
                    syntax_text = str(syntax.find("str").text)

                # extract the operands from the syntax
                pattern_syntax = r'^([\w.]+)\s+(.*)$'
                match_1 = re.match(pattern_syntax, syntax_text)
                if match_1 is not None:
                    instr_name = match_1.group(1)
                    operands_syntax = match_1.group(2).split(',')
                else:
                    operands_syntax = []

                instr_op_dict[name] = operands_syntax
                instr_name_syntaxName_dict[name] = syntax_name

                # delete all model_only instructions
                for key in model_only:
                    if key in instr_op_dict:
                        del instr_op_dict[key]

                # delete all ignored instructions
                for key in ignored:
                    if key in instr_op_dict:
                        del instr_op_dict[key]

    # take only desired attributes
    filtered_instr_op_dict = {key: instr_op_dict[key] for key in only_take_attributes if key in instr_op_dict}
    instr_op_dict = filtered_instr_op_dict

    # search for all 'None' keys
    keys_to_remove = [key for key in imm_width.keys() if key is None]

    # eliminate 'None' key from dict
    for key in keys_to_remove:
        del imm_width[key]
        del imm_shift[key]
        del imm_signed[key]

    # add sign bit to unsigned instructions
    for key in imm_width:
        if key in imm_signed and imm_signed[key] != "true":
            imm_width[key] += 1
    return instr_op_dict, instr_name_syntaxName_dict, imm_width, imm_shift, imm_signed, instr_field_value_dict

## Extract info about the operands and their possbile values
# @param adl_file Name of the adl file
# @return @b final_op_val_dict-> A dictionary with all registers as keys and a list of their possible values 
# @return @b widths_dict-> A dictionary with all registers as keys and their width as value
# @return @b op_signExt_dict-> A dictionary containing all the registers with sign extension as keys and their sign extension value
def operands_values(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    registers = list()
    values = list()
    offsets = list()
    widths = list()
    op_val_dict = dict()
    name_value = dict()
    widths_dict = dict()
    op_signExt_dict = dict()
    instrfield_exvalues = dict()
    instrfield_optionName_dict= dict()
    instrfield_offset_dict = dict()
    instrfield_width_dict = dict()

    for cores in root.iter("cores"):
        for instrfield in cores.iter("instrfield"):
            values = []
            ex_values = []
            name_value = {}
            register = None
            offset = instrfield.find("offset/int").text
            width = instrfield.find("width/int").text
            # extract all registers from adl
            for enumerated in instrfield.iter("enumerated"):
                if (len(enumerated) > 0):
                    register = instrfield.get("name")
                    registers.append(instrfield.get("name"))
                    offsets.append(int(offset))
                    widths.append(int(width))
                    widths_dict[register] = width
            # extract the values for each operand
            for operand in instrfield.iter("option"):
                name = operand.get("name")
                value = operand.find("str").text
                if (value is not None) and (value != "reserved"):
                    name_value[name] = value
                    values.append(value)
            # search if any operand has excluded values
            for excluded_value in instrfield.iter("excluded_values"):
                for option in excluded_value.iter("option"):
                    value = option.find("str").text
                    ex_values.append(value)
            instrfield_exvalues[instrfield.get("name")] = ex_values
            # search for operands with sign extension
            for sign_extension in instrfield.iter("sign_extension"):
                name = instrfield.get("name")
                sign_ext = sign_extension.find("int").text
                op_signExt_dict[name] = sign_ext

            if register is not None:
                op_val_dict[register] = values
    
    # take the option names and offset and width values for each instrfield
    for cores in root.iter("cores"):
        for instrfield in cores.iter("instrfield"):
            instrfield_name = instrfield.get("name")
            option_name_list = []
            reg_value_list = []
            for enumerated in instrfield.iter("enumerated"):
                for option in enumerated.iter("option"):
                    if option.find("str").text is not None and option.find("str").text != "reserved":
                        option_name_list.append(option.get("name"))
                        reg_value_list.append(option.find("str").text)
            instrfield_optionName_dict[instrfield_name] = [(op_name, reg_val) for (op_name, reg_val) in zip(option_name_list, reg_value_list)]
            for offset in instrfield.iter("offset"):
                offset_value = offset.find("int").text
            instrfield_offset_dict[instrfield_name] = offset_value
            for width in instrfield.iter("width"):
                width_value = width.find("int").text
            instrfield_width_dict[instrfield_name] = width_value
    # take only register values between 'offset' and 'offset + 2*width - 1' 
    final_op_val_dict = {}
    for operand, tuples in instrfield_optionName_dict.items():
        offset = int(instrfield_offset_dict[operand])
        width = int(instrfield_width_dict[operand])
        if width == 0:
            final_op_val_dict[operand] = []
        else:
            filtered_symbols = [symbol for option_name, symbol in tuples if offset <= int(option_name) <= (offset + 2**width - 1)]
            final_op_val_dict[operand] = filtered_symbols

    # take only used registers based on op_val_dict
    for key in list(final_op_val_dict.keys()):
        if key not in op_val_dict:
            del final_op_val_dict[key]

    # eliminate the excluded values
    for key, ex_val in instrfield_exvalues.items():
        if key in final_op_val_dict:
            val = final_op_val_dict[key]

            if ex_val is not None and val is not None:
                final_op_val_dict[key] = [v for v in val if v not in ex_val]

    return final_op_val_dict, widths_dict, op_signExt_dict

## Creates two dictionaries which hold information about instructions with paired registers
# @param adl_file Name of the adl file
# @return @b instruction_register_pair_dict-> The dictionary that holds the instructions which have paired registers
# @return @b instrfield_optionName_dict-> A dictionary with instrfields as keys and a list of tuples as values (option_name - value)
def register_pairs(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    # parse the inputs and outputs of the instructions
    instruction_inputs_dict = {}
    instruction_outputs_dict = {}
    for cores in root.iter("cores"):
        for instruction in cores.iter("instruction"):
            instruction_name = instruction.get("name")
            inputs_list = []
            outputs_list = []
            for inputs in instruction.iter("inputs"):
                for string in inputs.iter("str"):
                    inputs_list.append(string.text)
            for outputs in instruction.iter("outputs"):
                for string in outputs.iter("str"):
                    outputs_list.append(string.text)    
            instruction_inputs_dict[instruction_name] = inputs_list
            instruction_outputs_dict[instruction_name] = outputs_list
    
    filtered_inputs_dict = {}
    filtered_outputs_dict = {}

    # take only register pairs
    for key, value in instruction_inputs_dict.items():
        for item in value:
            match = re.search(r'\(([^)]+)\)', item)
            if match:
                content_within_parentheses = match.group(1)
                parts = content_within_parentheses.split('+')
                if len(parts) == 2 and parts[1].strip().isdigit():
                    filtered_inputs_dict[key] = value
                    break
    # take only register pairs
    for key, value in instruction_outputs_dict.items():
        for item in value:
            match = re.search(r'\(([^)]+)\)', item)
            if match:
                content_within_parentheses = match.group(1)
                parts = content_within_parentheses.split('+')
                if len(parts) == 2 and parts[1].strip().isdigit():
                    filtered_outputs_dict[key] = value
                    break

    instruction_pair_info_dict = {**filtered_inputs_dict, **filtered_outputs_dict}
    instrfield_optionName_dict = {}

    # take the option names with their values for each instrfield
    for cores in root.iter("cores"):
        for instrfield in cores.iter("instrfield"):
            instrfield_name = instrfield.get("name")
            option_name_list = []
            reg_value_list = []
            for enumerated in instrfield.iter("enumerated"):
                for option in enumerated.iter("option"):
                    if option.find("str").text is not None and option.find("str").text != "reserved":
                        option_name_list.append(option.get("name"))
                        reg_value_list.append(option.find("str").text)
            instrfield_optionName_dict[instrfield_name] = [(op_name, reg_val) for (op_name, reg_val) in zip(option_name_list, reg_value_list)]
    
    # Create a new dictionary with the same keys as the original one and extract operands which have paired registers
    instruction_register_pair_dict = {}
    for key, value_list in instruction_pair_info_dict.items():
        extracted_elements = [item.split('(')[1].split(' + 1')[0] for item in value_list if '+ 1' in item]
        instruction_register_pair_dict[key] = extracted_elements
        
    return instruction_register_pair_dict, instrfield_optionName_dict

## Creates a dictionary with instructions as keys and their width as value and another where the base architecture is removed from attribute name
# @param adl_file Name of the adl file
# @return @b instruction_attribute_dict-> The dictionary which maps each instruction to their attributes
# @return @b new_instruction_attribute_dict-> The dictionary which maps each instruction to their attributes with their base arch removed
#
# Used generally for generating tests only for specific architectures
def instruction_attribute(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    # Get the path of the script
    script_directory = os.path.dirname(os.path.abspath(__file__))

    # A dictionary for the configuration environment
    llvm_config_dict = config.config_environment(os.path.join(script_directory, "../../config.txt"), os.path.join(script_directory, "../../llvm_config.txt"))
    
    base_architecture = llvm_config_dict["BaseArchitecture"]
    instruction_attribute_dict = dict()
    instruction_prefix_dict = dict()

    for cores in root.iter("cores"):
        for instruction in cores.iter("instruction"):
            attribute_list = []
            for attribute in instruction.iter("attribute"):
                attribute_list.append(attribute.get("name"))
            instruction_attribute_dict[instruction.get("name")] = attribute_list

    # Remove base_architecture string from all attributes            
    new_instruction_attribute_dict = {instruction: [attr[len(base_architecture):] if attr.startswith(base_architecture) else attr for attr in attributes] for instruction, attributes in instruction_attribute_dict.items()}

    return instruction_attribute_dict, new_instruction_attribute_dict