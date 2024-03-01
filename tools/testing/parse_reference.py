# Copyright 2024 NXP
# SPDX-License-Identifier: BSD-2-Clause

## @package parse_reference
# The module for parsing and extracting information necessary to construct instruction reference from adl

import xml.etree.ElementTree as ET
import sys
import parse


## Creates a dictionary with instructions as keys and a list of tuples with each field info as values
# @param adl_file Name of the adl file
# @return @b final_instruction_fields_dict-> The dictionary which maps each instruction to their field info
def instructions_fields(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instruction_fields_dict = dict()
    alias_fields_dict = dict()
    alias_instruction_dict = dict()
    instructions_field_value_tuple_list = list()
    aliases_field_value_tuple_list = list()

    (
        instr_op_dict,
        instr_name_syntaxName_dict,
        imm_width_dict,
        imm_shift_dict,
        imm_signed_dict,
        instr_field_value_dict,
    ) = parse.instructions_operands(adl_file)

    # Extract instructions that are NOT aliases with field information
    for cores in root.iter("cores"):
        for instruction in cores.iter("instruction"):
            if (
                instruction.get("name") in instr_op_dict
                and instruction.find("aliases") is None
            ):
                instructions_field_value_tuple_list = []
                for field in instruction.iter("field"):
                    if field.find("str") is not None:
                        if field.find("str").text is not None:
                            instructions_field_value_tuple_list.append(
                                (field.get("name"), field.find("str").text)
                            )
                        else:
                            instructions_field_value_tuple_list.append(
                                (field.get("name"), field.get("name"))
                            )
                    else:
                        instructions_field_value_tuple_list.append(
                            (field.get("name"), field.find("int").text)
                        )
                instruction_fields_dict[
                    instruction.get("name")
                ] = instructions_field_value_tuple_list

    # Extract instructions that are aliases with field information
    for cores in root.iter("cores"):
        for instruction in cores.iter("instruction"):
            if instruction.get("name") in instr_op_dict and instruction.find("aliases"):
                aliases_field_value_tuple_list = []
                for field, value in zip(
                    instruction.iter("field"), instruction.iter("value")
                ):
                    if value.find("str") is not None:
                        aliases_field_value_tuple_list.append(
                            (field.find("str").text, value.find("str").text)
                        )
                    else:
                        aliases_field_value_tuple_list.append(
                            (field.find("str").text, value.find("int").text)
                        )
                alias_fields_dict[
                    instruction.get("name")
                ] = aliases_field_value_tuple_list

    # Create a dict with only field names in order to delete duplicate field names
    alias_field_names_dict = {
        instruction: [t[0] for t in operand_value_tuples]
        for instruction, operand_value_tuples in alias_fields_dict.items()
    }

    # Create a dict with only duplicate field names for generatin fields with swapped values for aliases
    alias_duplicates_dict = {}
    for key, values in alias_field_names_dict.items():
        seen = set()  # Create a set to track seen values
        duplicates = []  # Create a list to store duplicate values
        for value in values:
            if value in seen and value not in duplicates:
                duplicates.append(value)
            seen.add(value)
        if duplicates:
            alias_duplicates_dict[key] = duplicates

    # Search if an alias has duplicate operands and if it does and one has value '0' then change that tuple with the other one, then swap values
    for key, special_operands in alias_duplicates_dict.items():
        if key in alias_fields_dict:
            tuples = alias_fields_dict[key]
            for idx, (operand, value) in enumerate(tuples):
                if operand in special_operands and value == "0":
                    for other_operand, other_value in tuples:
                        if other_operand == operand and other_value != "0":
                            # Swap the values and operands in the tuple
                            tuples[idx] = (other_value, operand)
                            break

    # Extract a separate dictionary with instructions and their aliases
    for cores in root.iter("cores"):
        for instruction in cores.iter("instruction"):
            if instruction.get("name") in instr_op_dict and instruction.find("aliases"):
                for alias in instruction.iter("alias"):
                    alias_instruction_dict[instruction.get("name")] = alias.get("name")

    # Initialize aliases_with_instruction_values_dict
    aliases_with_instruction_values_dict = {}

    # Iterate through alias_instruction_dict
    for alias, instruction in alias_instruction_dict.items():
        if instruction in instruction_fields_dict and alias in alias_fields_dict:
            instruction_tuples = instruction_fields_dict[instruction]
            alias_tuples = alias_fields_dict[alias]

            # Create a list to store swapped alias values
            swapped_alias_values = []

            for instruction_tuple in instruction_tuples:
                matching_alias_tuple = next(
                    (
                        alias_tuple
                        for alias_tuple in alias_tuples
                        if alias_tuple[0] == instruction_tuple[0]
                    ),
                    None,
                )
                if matching_alias_tuple:
                    swapped_alias_values.append(
                        (instruction_tuple[0], matching_alias_tuple[1])
                    )
                else:
                    swapped_alias_values.append(
                        (instruction_tuple[0], instruction_tuple[1])
                    )

            # Check if there are unmatched alias tuples
            unmatched_alias_tuples = [
                alias_tuple
                for alias_tuple in alias_tuples
                if all(
                    alias_tuple[0] != instr_tuple[0]
                    for instr_tuple in instruction_tuples
                )
            ]

            # Add unmatched alias tuples to swapped_alias_values
            swapped_alias_values.extend(unmatched_alias_tuples)

            aliases_with_instruction_values_dict[alias] = swapped_alias_values
        else:
            # Handle cases where either the instruction or alias is not found
            aliases_with_instruction_values_dict[alias] = []

    final_instruction_fields_dict = {
        **instruction_fields_dict,
        **aliases_with_instruction_values_dict,
    }
    final_instruction_fields_dict = {
        key: final_instruction_fields_dict[key]
        for key in sorted(final_instruction_fields_dict)
    }

    return final_instruction_fields_dict


## Creates a dictionary with operands as keys and their mask as value
# @param adl_file Name of the adl file
# @return @b instrfield_mask_dict-> The dictionary which maps each operand to their mask
def instrfield_mask(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instrfield_mask_dict = dict()

    for cores in root.iter("cores"):
        for instrfield in cores.iter("instrfield"):
            for mask in instrfield.iter("mask"):
                instrfield_mask_dict[instrfield.get("name")] = mask.find("str").text

    return instrfield_mask_dict


## Creates a dictionary with operands as keys and their range as value
# @param adl_file Name of the adl file
# @return @b instrfield_range_dict-> The dictionary which maps each operand to their range
def instrfield_range(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instrfield_range_dict = dict()
    range_list = list()

    for cores in root.iter("cores"):
        for instrfield in cores.iter("instrfield"):
            range_list = []
            for range in instrfield.iter("range"):
                int_elements = range.findall("int")
                range_tuple = tuple(int(element.text) for element in int_elements)
                range_list.append(range_tuple)
            instrfield_range_dict[instrfield.get("name")] = range_list

    return instrfield_range_dict


## Creates a dictionary with operands as keys and a list of possbile values as their value
# @param adl_file Name of the adl file
# @return @b instrfield_values_dict-> The dictionary which maps each operand to their values
def instrfield_values(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instrfield_values_dict = dict()
    option_name_value_list = list()

    for cores in root.iter("cores"):
        for instrfield in cores.iter("instrfield"):
            if instrfield.find("enumerated"):
                for enumerated in instrfield.iter("enumerated"):
                    option_name_value_list = []
                    for option in enumerated.iter("option"):
                        option_name_value_list.append(
                            (option.find("str").text, option.get("name"))
                        )
                    instrfield_values_dict[
                        instrfield.get("name")
                    ] = option_name_value_list

    return instrfield_values_dict


## Creates a dictionary with operands as keys and their shift as value
# @param adl_file Name of the adl file
# @return @b instrfield_shift_dict-> The dictionary which maps each operand to their shift
def instrfield_shift(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instrfield_shift_dict = dict()

    for cores in root.iter("cores"):
        for instrfield in cores.iter("instrfield"):
            for shift in instrfield.iter("shift"):
                instrfield_shift_dict[instrfield.get("name")] = shift.find("int").text

    return instrfield_shift_dict


## Function that returns the endianness of the extension
# @param adl_file Name of the adl file
# @return @b endianness-> The endianness of the extension
def bit_endianness(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    endianness = str()

    for cores in root.iter("cores"):
        for bit_endianness in cores.iter("bit_endianness"):
            endianness = bit_endianness.find("str").text

    return endianness


## Creates a dictionary with instructions as keys and their width as value
# @param adl_file Name of the adl file
# @return @b instruction_width_dict-> The dictionary which maps each instruction to their width
def instruction_width(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instruction_width_dict = dict()

    for cores in root.iter("cores"):
        for instruction in cores.iter("instruction"):
            for width in instruction.iter("width"):
                instruction_width_dict[instruction.get("name")] = width.find("int").text

    return instruction_width_dict


## Creates a dictionary with instructions as keys and their syntax name as value
# @param adl_file Name of the adl file
# @return @b instruction_syntaxName_dict-> The dictionary which maps each instruction to their syntax name
def instruction_syntaxName(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instruction_syntaxName_dict = dict()

    for cores in root.iter("cores"):
        for instruction in cores.iter("instruction"):
            for syntax in instruction.iter("syntax"):
                if "hint" in instruction.get("name"):
                    instruction_syntaxName_dict[instruction.get("name")] = (
                        syntax.find("str").text
                    ).split()[0]
                else:
                    instruction_syntaxName_dict[
                        instruction.get("name")
                    ] = instruction.get("name")

    return instruction_syntaxName_dict


adl_file = sys.argv[1]
instructions_fields(adl_file)
instrfield_mask(adl_file)
instrfield_range(adl_file)
instrfield_values(adl_file)
instrfield_shift(adl_file)
bit_endianness(adl_file)
instruction_width(adl_file)
instruction_syntaxName(adl_file)
