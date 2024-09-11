# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package parse_reloc
# The module for parsing and extracting information about relocations from adl

import sys
import re
import xml.etree.ElementTree as ET
from collections import defaultdict


## A function that generates a dictionary with all the instructions as keys and a list of their operands as values
# @param adl_file Name of the adl file
# @return @b instruction_operands_dict-> A dictionary containing instructions as keys and a list of operands as values
def instructions_operands(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instruction_operands_dict = {}
    # Iterate over all instructions and skip the ones that are pseudo, alias or have the attribute ignored
    for instruction in root.iter("instruction"):
        skip_instruction = False
        for attribute in instruction.iter("attribute"):
            if attribute.get("name") == "ignored":
                skip_instruction = True
                break
            if attribute.get("name") == "model_only":
                skip_instruction = True
                break
        if ((instruction.find("pseudo") is not None) or 
            (instruction.find("alias_action") is not None) or
            (skip_instruction is True)):
            continue

        syntax = instruction.find("syntax").find("str").text
        instruction_name = instruction.get("name")
        # Check if the instruction has no operands
        if len(syntax.split(' ')) == 1:
            instruction_operands_dict[instruction_name] = []
        else:
            operands = syntax.split(' ')[1].split(',')
            instruction_operands_dict[instruction_name] = operands

    # Sepparate the offset from the immediate in the operands list
    for instruction, operands in instruction_operands_dict.items():
        for operand in operands:
            match_offset = re.search(r'\((.*?)\)', operand)
             # Extract the offset within parentheses
            if match_offset is not None:
                offset = match_offset.group(1)
                # Remove the offset and keep only the immediate
                immediate = re.sub(r'\(.*?\)', '', operand).strip()
                # Remove the operand from the list
                operands.remove(operand)
                # Append the immediate and the offset to the list of operands
                operands.append(immediate)
                operands.append(offset)

    return instruction_operands_dict


## Reverses the previous instruction_operands_dict with operands as keys and a list of instructions as their values
# @param instruction_operands_dict A dictionary containing instructions as keys and a list of operands as values
# @return @b operand_instructions_dict-> A dictionary containing operands as keys and a list of instructions as values
def operands_instructions(instruction_operands_dict):

    operand_instructions_dict = defaultdict(list)

    for instruction, operands in instruction_operands_dict.items():
        for operand in operands:
            operand_instructions_dict[operand].append(instruction)

    return operand_instructions_dict
    

## Generates a dictionary with all the relocations as keys and a list of instructons as their values
# @param adl_file Name of the adl file
# @param operand_instructions_dict-> A dictionary containing operands as keys and a list of instructions as values
# @return A dictionary containing relocations as keys and a list of instructions as values
def relocations_instructions(adl_file, operand_instructions_dict):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    relocation_operand_dict = dict()
    relocation_instructions_dict = dict()

    for instrfield in root.iter("instrfield"):
        for reloc in instrfield.iter("reloc"):
            # Check if the operand is in the operand_instructions_dict and if it has a relocation
            if instrfield.get("name") in operand_instructions_dict.keys() and instrfield.find("reloc") is not None:
                relocations_list = instrfield.find("reloc").findall("str")
                for reloc in relocations_list:
                    relocation_operand_dict[reloc.text] = instrfield.get("name")

    # Extract associated relocations and instructions based on common operands
    for operand_i, instructions in operand_instructions_dict.items():
        for relocation, operand_r in relocation_operand_dict.items():
            if operand_i in relocation_operand_dict.values():
                relocation_instructions_dict[relocation] = operand_instructions_dict[operand_r]
    
    # Sort the instructions lists
    for relocation, instructions in relocation_instructions_dict.items():
        relocation_instructions_dict[relocation] = sorted(instructions)
    return dict(sorted(relocation_instructions_dict.items()))


## A function that generates a dictionary with all the relocations as keys and a list of their operands as values
# @param adl_file Name of the adl file
# @param relocation_instructions_dict A dictionary containing relocations as keys and a list of instructions as values
# @return A dictionary containing relocations as keys and a list of their operands as values
def relocations_instrfields(adl_file, relocation_instructions_dict):

    tree = ET.parse(adl_file)
    root = tree.getroot()

    relocation_instrfield_dict = dict()

    for instrfield in root.iter("instrfield"):
        for reloc in instrfield.iter("reloc"):
            reloc_list = instrfield.find("reloc").findall("str")
            for reloc in reloc_list:
                if reloc.text in relocation_instructions_dict.keys():
                    relocation_instrfield_dict[reloc.text] = instrfield.get("name")

    return relocation_instrfield_dict


## Generates a dictionary with all the relocations as keys and their abbreviations as values
# @param adl_file Name of the adl file
# @param reloc_instr_dict-> A dictionary containing relocations as keys and a list of instructions as values
# @return A dictionary with all the relocations as keys and their abbreviations as values
def relocations_abbrevs(adl_file, relocation_instructions_dict):

    tree = ET.parse(adl_file)
    root = tree.getroot()

    relocation_abbrev_dict = {}
    for relocations in root.iter("relocations"):
        for reloc,abbrev in zip(relocations.iter("reloc"), relocations.iter("abbrev")):
            reloc_name = reloc.get("name")
            abbrev_name = abbrev.find("str").text
            if reloc_name in relocation_instructions_dict.keys():
                relocation_abbrev_dict[reloc_name] = abbrev_name

    return dict(sorted(relocation_abbrev_dict.items()))


## Generates a dictionary with relocations that have a suffix
# @param adl_file Name of the adl file
# @param reloc_instr_dict-> A dictionary containing relocations as keys and a list of instructions as values
# @return A dictionary with only the relocations that have a suffix
def relocations_suffixes(adl_file, relocation_instructions_dict):
    
    tree = ET.parse(adl_file)
    root = tree.getroot()

    relocation_suffix_dict = {}
    for relocations in root.iter("relocations"):
        for reloc in relocations.iter("reloc"):
            if reloc.get("name") in relocation_instructions_dict.keys():
                suffix = reloc.find("suffix")
                if suffix is not None:
                    relocation_suffix_dict[reloc.get("name")] = suffix.find("str").text
    
    return dict(sorted(relocation_suffix_dict.items()))


## Generates a dictionary with all the instructions as keys and their syntax as values
# @param adl_file Name of the adl file
# @return A dictionary with all the instructions as keys and their syntax name as values
def instructions_syntaxNames(adl_file):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instruction_syntaxName_dict = {}

    for instruction in root.iter("instruction"):
        instruction_name = instruction.get("name")
        syntax = str(instruction.find("syntax").find("str").text).split()[0]
        instruction_syntaxName_dict[instruction_name] = syntax

    return instruction_syntaxName_dict


## Generates a dictionary with all the relocations as keys and a list of their dependencies as values
# @param adl_file Name of the adl file
# @param reloc_instr_dict-> A dictionary containing relocations as keys and a list of instructions as values
# @return A dictionary with all the relocations as keys and a list of their dependencies as values
def relocations_dependencies(adl_file, relocation_instructions_dict):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    relocation_dependency_dict = dict()
    for relocations in root.iter("relocations"):
        for reloc in relocations.iter("reloc"):
            # Check if the relocation is in the relocation_instructions_dict and if it has a dependency
            if reloc.get("name") in relocation_instructions_dict.keys() and reloc.find("dependency") is not None:
                dependencies = reloc.find("dependency").findall("str")
                dependencies_list = []
                for dependency in dependencies:
                    dependencies_list.append(dependency.text)
                relocation_dependency_dict[reloc.get("name")] = dependencies_list

    return relocation_dependency_dict


## A function that generates a dictionary with instrfield names as keys and their shift as values
# @param adl_file Name of the adl file
# @param relocation_instrfield_dict A dictionary containing relocations as keys and a list of their operands as values
# @return A dictionary containing instrfield names as keys and their shift as values
def instrfields_shifts(adl_file, relocation_instrfield_dict):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instrfield_shift_dict = dict()
    for instrfield in root.iter("instrfield"):
        if instrfield.get("name") in relocation_instrfield_dict.values():
            for shift in instrfield.iter("shift"):             
                instrfield_shift_dict[instrfield.get("name")] = int(shift.find("int").text)

    return instrfield_shift_dict


## A function that generates a dictionary with instrfield names as keys and their width as values
# @param adl_file Name of the adl file
# @param relocation_instrfield_dict A dictionary containing relocations as keys and a list of their operands as values
# @return A dictionary containing instrfield names as keys and their width as values
def instrfields_widths(adl_file, relocation_instrfield_dict):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instrfield_width_dict = dict()
    for instrfield in root.iter("instrfield"):
        if instrfield.get("name") in relocation_instrfield_dict.values():
            for width in instrfield.iter("width"):             
                instrfield_width_dict[instrfield.get("name")] = int(width.find("int").text)

    return instrfield_width_dict


## A function that generates a dictionary with instrfield names as keys and their signed attribute as values (1 if signed and 0 if unsigned)
# @param adl_file Name of the adl file
# @param relocation_instrfield_dict A dictionary containing relocations as keys and a list of their operands as values
# @return A dictionary containing instrfield names as keys and their signed attribute as values
def instrfields_signed(adl_file, relocation_instrfield_dict):
    tree = ET.parse(adl_file)
    root = tree.getroot()

    instrfield_signed_dict = dict()
    for instrfield in root.iter("instrfield"):
        if instrfield.get("name") in relocation_instrfield_dict.values():
            if instrfield.find("signed") is not None:
                instrfield_signed_dict[instrfield.get("name")] = 1
            else:
                instrfield_signed_dict[instrfield.get("name")] = 0

    return instrfield_signed_dict