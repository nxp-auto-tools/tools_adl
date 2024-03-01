# Copyright 2024 NXP
# SPDX-License-Identifier: BSD-2-Clause

## @package parse_reloc
# The module for parsing and extracting information about relocations from adl

import sys
import xml.etree.ElementTree as ET
import re
import importlib
from collections import defaultdict

sys.path.append("./../")
module_info = "info"
try:
    info = importlib.import_module(module_info)
except ImportError:
    print("Please run make_test.py first to generate the info module.")


## A function that generates a dictionary with all the instructions as keys and a list of their operands as values
# @param adl_file Name of the adl file
# @return @b instr_op_dict-> A dictionary containing instructions as keys and a list of operands as values
def instructions_operands(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    model_only = list()
    ignored = list()
    instr_op_dict = dict()

    for cores in root.iter("cores"):
        # check if the instruction is a pseudo instruction or has alias_action
        for instruction in cores.iter("instruction"):
            if (instruction.find("pseudo")) or (instruction.find("alias_action")):
                continue
            else:
                name = instruction.get("name")
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
                # extract the syntax of the instruction
                for syntax in instruction.iter("syntax"):
                    syntax_text = str(syntax.find("str").text)

                # extract the operands from the syntax
                pattern_syntax = r"^([\w.]+)\s+(.*)$"
                match_1 = re.match(pattern_syntax, syntax_text)
                if match_1 is not None:
                    instr_name = match_1.group(1)
                    operands_syntax = match_1.group(2).split(",")
                else:
                    operands_syntax = []

                instr_op_dict[name] = operands_syntax

                # delete all model_only instructions
                for key in model_only:
                    if key in instr_op_dict:
                        del instr_op_dict[key]

                # delete all ignored instructions
                for key in ignored:
                    if key in instr_op_dict:
                        del instr_op_dict[key]

    # eliminate offsets from dict
    pattern = re.compile(r"\(.*?\)")
    for key, value in instr_op_dict.items():
        instr_op_dict[key] = [pattern.sub("", item) for item in value]

    return instr_op_dict


## Reverses the previous instr_op_dict with operands as keys and a list of instructions as their values
# @param instr_op_dict A dictionary containing instructions as keys and a list of operands as values
# @return @b op_instr_dict_updated-> A dictionary containing operands as keys and a list of instructions as values
def operands_instructions(instr_op_dict):
    op_instr_dict = defaultdict(list)

    for instruction, operands in instr_op_dict.items():
        for operand in operands:
            op_instr_dict[operand].append(instruction)

    op_instr_dict = dict(op_instr_dict)

    op_instr_dict_updated = dict()
    for key, value in op_instr_dict.items():
        if "(" in key and ")" in key:
            new_key = key.replace("(", "").replace(")", "")
            op_instr_dict_updated[new_key] = value
        else:
            op_instr_dict_updated[key] = value

    return op_instr_dict_updated


## Generates a dictionary with all the relocations as keys and a list of instructons as their values
# @param adl_file Name of the adl file
# @param op_instr_dict_updated-> A dictionary containing operands as keys and a list of instructions as values
# @return A dictionary containing relocations as keys and a list of instructions as values
def relocations_instructions(adl_file, op_instr_dict_updated):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    reloc_op_dict = dict()

    for cores in root.iter("cores"):
        # extract all registers with their relocations from adl
        for instrfield in cores.iter("instrfield"):
            for reloc in instrfield.iter("reloc"):
                if (
                    instrfield.get("name") in op_instr_dict_updated.keys()
                    and instrfield.find("reloc") is not None
                ):
                    name = instrfield.get("name")
                    for string in reloc.iter("str"):
                        relocation = string.text
                        reloc_op_dict[relocation] = name

    for cores in root.iter("cores"):
        # extract all registers without their relocations from adl -> just for printing purposes
        for instrfield2 in cores.iter("instrfield"):
            if (
                instrfield2.get("name") in op_instr_dict_updated.keys()
                and instrfield2.find("reloc") is not None
            ):
                name2 = instrfield2.get("name")

    # extract associated relocations and instructions based on common operands
    reloc_instr_dict = dict()
    for key1, value1 in op_instr_dict_updated.items():
        for key2, value2 in reloc_op_dict.items():
            if key1 in reloc_op_dict.values():
                reloc_instr_dict[key2] = op_instr_dict_updated[value2]

    # sort the instructions lists
    for reloc, instr in reloc_instr_dict.items():
        reloc_instr_dict[reloc] = sorted(instr)

    return dict(sorted(reloc_instr_dict.items()))


## Generates a dictionary with all the relocations as keys and their abbreviations as values
# @param adl_file Name of the adl file
# @param reloc_instr_dict-> A dictionary containing relocations as keys and a list of instructions as values
# @return A dictionary with all the relocations as keys and their abbreviations as values
def relocations_abbrev(adl_file, reloc_instr_dict):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    relocation_abbrev_dict = {}

    for cores in root.iter("cores"):
        for relocations in cores.iter("relocations"):
            for reloc, abbrev in zip(
                relocations.iter("reloc"), relocations.iter("abbrev")
            ):
                reloc_name = reloc.get("name")
                abbrev_name = abbrev.find("str").text
                if reloc_name in reloc_instr_dict.keys():
                    relocation_abbrev_dict[reloc_name] = abbrev_name

    return dict(sorted(relocation_abbrev_dict.items()))


## A function used to parse relevant information about operands for relocations generation
# @param adl_file Name of the adl file
# @param op_instr_dict_updated A dictionary containing operands as keys and a list of instructions as values
# @return @b reloc_op_dict-> A dictionary containing relocations as keys and a list of operands as values
# @return @b imm_width-> A dictionary containing immediates as keys and their width as values
# @return @b imm_shift-> A dictionary containing immediates as keys and their shift as values
def operands_width(adl_file, op_instr_dict_updated):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    reloc_op_dict = dict()
    imm_width = dict()
    imm_shift = dict()
    imm_signed = dict()

    for cores in root.iter("cores"):
        # extract all registers with their relocations from adl
        for instrfield in cores.iter("instrfield"):
            for reloc in instrfield.iter("reloc"):
                if (
                    instrfield.get("name") in op_instr_dict_updated.keys()
                    and instrfield.find("reloc") is not None
                ):
                    name = instrfield.get("name")
                    for string in reloc.iter("str"):
                        relocation = string.text
                        reloc_op_dict[relocation] = name
        # extract all immediates from adl with additional info
        for instrfield in cores.iter("instrfield"):
            immediate = instrfield.get("name")
            signed_text = "false"
            if immediate in reloc_op_dict.values():
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

        for key in imm_width:
            if key in imm_signed and imm_signed[key] != "true":
                imm_width[key] += 1

    return reloc_op_dict, imm_width, imm_shift
