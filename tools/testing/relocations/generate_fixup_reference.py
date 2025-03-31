# Copyright 2023-2025 NXP 
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import sys
import utils_reloc
import parse_reloc
import shutil
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), "../encoding/"))
import parse_reference # type: ignore


## Function for identifying the value of the program counter after the first label definition for a target line
def count_pcrel(file_path, target_line_pattern, instruction_width_dict):
    with open(file_path, "r") as file:
        lines = file.readlines()

    label_found = False
    pcrel_value = 0

    for line in lines:
        stripped_line = line.strip()

        # Detect the first label definition (L<number>:)
        if not label_found and re.match(r"^L\d+:\s*$", stripped_line):
            label_found = True
            continue

        # Start counting instructions after the first label is found
        if label_found:            
            # Ignore additional label definitions
            if re.match(r"^L\d+:\s*$", stripped_line):
                continue  # Skip labels

            # Ignore empty lines and comments
            if stripped_line and not stripped_line.startswith("#"):
                line_instruction = stripped_line.split()[0]
                pcrel_value += int(instruction_width_dict[line_instruction])/8  # Count valid instructions

            # Stop when reaching the target line pattern
            if re.fullmatch(rf'{re.escape(target_line_pattern)}', stripped_line):
                line_instruction = stripped_line.split()[0]
                return pcrel_value - int(instruction_width_dict[line_instruction])/8  # Exclude the target line itself

    # If no label or target line is found, return 0
    return 0

## Function for storing the pcrel value of the first label use in case of dependency relocations
def count_dep_pcrel(file_path, target_line, instruction_width_dict):
    label_uses = {}
    instruction_offset = 0
    counting = False  # Flag to start counting after first label definition

    # Regex to match labels
    label_pattern = re.compile(r'\b(L\d+)\b')
    label_definition_pattern = re.compile(r'^L\d+:$')

    with open(file_path, "r") as file:
        lines = file.readlines()

    # Find first label definition and then count instructions
    for line in lines:
        stripped_line = line.strip()

        # Ignore empty and commented lines
        if not stripped_line or stripped_line.startswith(("#", "//")):
            continue

        # Detect first label definition and start counting after it
        if not counting and label_definition_pattern.match(stripped_line):
            counting = True
            continue  # Skip this label definition itself

        # If we haven't found the first label definition yet, keep looking
        if not counting:
            continue

        # Ignore standalone label definitions
        if label_definition_pattern.match(stripped_line):
            continue

        # Find labels used in instructions
        matches = label_pattern.findall(stripped_line)

        for label in matches:
            if label not in label_uses:
                label_uses[label] = instruction_offset  # Store first occurrence

        # Only increment if the line contains an actual instruction
        if re.search(r'\b[a-zA-Z]+\b', stripped_line):
            line_instruction = stripped_line.split()[0]
            instruction_offset += int(instruction_width_dict[line_instruction])/8

    # Extract the label from the target string
    target_matches = label_pattern.findall(target_line.strip())
    if target_matches:
        label = target_matches[0]  # Assuming only one label per line
        return label_uses.get(label, None)  # Return offset or None if not found
    
    return None  # Return None if no label is found in target_line


def write_reference():
    # Get the command line arguments
    adl_file_path, adl_file_name, symbol_max_value, extension_list, output_dir, display_extensions = utils_reloc.cmd_args()

    # Refresh output directory and define the paths to the "tests" and "references" directories
    if extension_list is not None:
        tests_directory = os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'tests_' + '_'.join(extension_list))
        references_directory = os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'refs_' + '_'.join(extension_list))
        if os.path.exists(references_directory):
            shutil.rmtree(references_directory)
        os.makedirs(os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'refs_' + '_'.join(extension_list)), exist_ok=True)

    else:
        tests_directory = os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'tests_all')
        references_directory = os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'refs_all')
        if os.path.exists(references_directory):
            shutil.rmtree(references_directory)
        os.makedirs(os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'refs_all'), exist_ok=True)

    # Define a regular expression syntax_pattern to match the desired line
    syntax_pattern = r'# @brief\s+Encode\s+(.+)$'
    syntax_dep_pattern = r'# @brief\s+Encode_dep\s+(.+)$'

    # A dictionary for mapping operands with the values from the assembly files
    operand_values_dict = dict() 

    # Dictionaries containing information for generating references
    instruction_fields_dict = parse_reference.instructions_fields(adl_file_path)
    instruction_syntaxName_dict = parse_reference.instruction_syntaxName(adl_file_path)
    instrfield_range_dict = parse_reference.instrfield_range(adl_file_path)
    instrfield_values_dict = parse_reference.instrfield_values(adl_file_path)
    instrfield_shift_dict = parse_reference.instrfield_shift(adl_file_path)
    instruction_width_dict = parse_reference.instruction_width(adl_file_path)
    relocation_instructions_dict = parse_reloc.relocations_instructions(adl_file_path, parse_reloc.operands_instructions(parse_reloc.instructions_operands(adl_file_path)))
    relocation_dependency_dict = parse_reloc.relocations_dependencies(adl_file_path,relocation_instructions_dict)
    relocation_abbrev_dict = parse_reloc.relocations_abbrevs(adl_file_path, relocation_instructions_dict)
    relocation_field_width = parse_reloc.relocations_field_widths(adl_file_path)
    relocation_action_dict = parse_reloc.relocations_action(adl_file_path)
    bit_endianness = parse_reference.bit_endianness(adl_file_path)

    # Iterate through all directories and subdirectories under "tests_" directory
    for dirpath, dirnames, filenames in os.walk(tests_directory):
        for filename in filenames:
            if filename.endswith(".s"):
                # Construct the full path to the source .s file
                test_asm_file_path = os.path.join(dirpath, filename)
                # print(test_asm_file_path)
                # Construct the corresponding path in the "references" directory
                ref_asm_file_path = os.path.join(references_directory, filename)

                # Store current relocation
                relocation = None
                for reloc in relocation_instructions_dict:
                    if reloc in os.path.basename(test_asm_file_path):
                        relocation = reloc
                        break

                # Store current instruction
                instruction = os.path.basename(test_asm_file_path).split(f'{relocation}_')[1].split('.s')[0]

                # Find the instruction lines in the .s file
                matching_lines = []
                with open(test_asm_file_path, 'r') as test_asm_file:
                    for line in test_asm_file:
                        stripped_line = line.lstrip()
                        # Check for instruction relocations
                        if os.path.basename(dirpath) in relocation_instructions_dict.keys():
                            if line.startswith('\t') and any(stripped_line.startswith(instruction) for instruction in instruction_syntaxName_dict.keys() | instruction_syntaxName_dict.values()):
                                matching_lines.append(line.strip())
                test_asm_file.close()

                # Match instruction and operands from syntax line in order to match them with each instruction line
                with open(test_asm_file_path, 'r') as source_asm_file:
                    # Match current instruction syntax
                    for line in source_asm_file:
                        match = re.match(syntax_pattern, line)
                        if match:
                            # Split syntax into instruction and operands
                            syntax_line = match.group(1).strip()  # Remove leading/trailing spaces
                            syntax_line_parts = syntax_line.split()
                            if len(syntax_line_parts) >=2:
                                syntax_instruction = syntax_line_parts[0]
                                syntax_operands = syntax_line_parts[1]
                            else:
                                syntax_instruction = syntax_line_parts[0]
                                syntax_operands = None
                            break
                    # Match relocation dependecy instruction syntax
                    for line in source_asm_file:
                        match_dep = re.match(syntax_dep_pattern, line)
                        if match_dep:
                            # Split syntax into instruction and operands
                            syntax_dep_line = match_dep.group(1).strip()  # Remove leading/trailing spaces
                            syntax_line_dep_parts = syntax_dep_line.split()
                            if len(syntax_line_dep_parts) >=2:
                                syntax_dep_instruction = syntax_line_dep_parts[0]
                                syntax_dep_operands = syntax_line_dep_parts[1]
                            else:
                                syntax_dep_instruction = syntax_line_dep_parts[0]
                                syntax_dep_operands = None
                            break
                    source_asm_file.seek(0)

                    # Check each label address and store them in a dictionary 
                    if 'S' in relocation_action_dict[relocation] and syntax_operands is not None:
                        label_address_dict = {}
                        current_address = 0  # Starting address
                        instruction_lines = []  # Store instructions between labels
                        for line in source_asm_file:
                            stripped_line = line.strip()
                            # Match label definitions (e.g., L1:)
                            match = re.match(r'L(\d+):\s*', stripped_line)
                            if match:
                                symbol_label = f'L{match.group(1)}'
                                # Process stored instruction lines before this label
                                for instr_line in instruction_lines:
                                    prev_instruction = instr_line.split()
                                    if prev_instruction and prev_instruction[0] in instruction_width_dict:
                                        current_address += int(instruction_width_dict[prev_instruction[0]]) / 8
                                # Store the computed address for this label
                                label_address_dict[symbol_label] = hex(int(current_address))
                                # Reset instruction storage after encountering a new label
                                instruction_lines = []
                            else:
                                # Store non-empty, non-label lines (potential instructions)
                                if stripped_line:
                                    instruction_lines.append(stripped_line)
                        source_asm_file.seek(0)

                    # Start encoding calculus line by line
                    references_list = []
                    operand_values_dict = {}
                    for line in matching_lines:
                        line_instruction_parts = line.split()
                        # Split lines into instructions and operands
                        if len(line_instruction_parts) >= 2:
                            line_instruction = line_instruction_parts[0]
                            line_operands = line_instruction_parts[1]
                        else:
                            line_instruction = line_instruction_parts[0]
                            line_operands = None
                        syntax_operands_values = re.findall(r'[\w_]+', str(syntax_operands))
                        line_operands_values = re.findall(r'(?<!%)\b[-\w_]+(?:\+\w+)?', str(line_operands))
                        if relocation in relocation_dependency_dict:
                            syntax_operands_dep_values = re.findall(r'[\w_]+', str(syntax_dep_operands))
                            if line_instruction in syntax_dep_instruction:
                                operand_values_dict = {key: value for key, value in zip(syntax_operands_dep_values, line_operands_values)}
                            else:
                                operand_values_dict = {key: value for key, value in zip(syntax_operands_values, line_operands_values)}
                        else:
                            operand_values_dict = {key: value for key, value in zip(syntax_operands_values, line_operands_values)}

                        # Extract the label in the form L<number> from the target line pattern
                        label_match = re.search(r"L\d+", line)
                        if not label_match:
                            label = None
                        else:
                            label = label_match.group(0)

                        # Fixup calculus
                        fixup_value = 0
                        if 'S' in relocation_action_dict[relocation] and line_operands is not None:
                            fixup_value += int(label_address_dict[label],16)  
                            # Check for pc relative
                            if 'P' in relocation_action_dict[relocation] and line_operands is not None:
                                if relocation in relocation_dependency_dict:
                                    pcrel_value = int(count_dep_pcrel(test_asm_file_path, line, instruction_width_dict))
                                else:
                                    pcrel_value = int(count_pcrel(test_asm_file_path, line, instruction_width_dict))
                                fixup_value -= pcrel_value
                                # In case of pcrel_hi check only the 20 upper bits
                                if relocation_abbrev_dict[relocation] == "pcrel_hi":
                                    if fixup_value < pow(2, int(instruction_width_dict[instruction]) - int(relocation_field_width[relocation])):
                                        fixup_value = 0       
                            # Check for addendum
                            if 'A' in relocation_action_dict[relocation] and line_operands is not None:
                                match = re.search(r"\b(L\d+)([+\-]\s*0x[0-9a-fA-F]+)?", line)
                                if match:
                                    addendum_label = match.group(1)
                                    addendum_value = match.group(2) if match.group(2) else hex(0)
                                    fixup_value += int(addendum_value,16)
                                    # In case of pcrel_hi check only the 20 upper bits
                                    if relocation_abbrev_dict[relocation] == "pcrel_hi":
                                        if fixup_value < pow(2, int(instruction_width_dict[instruction]) - int(relocation_field_width[relocation])):
                                            fixup_value = 0
                                        else:
                                            fixup_value  = fixup_value >> (int(instruction_width_dict[instruction]) - int(relocation_field_width[relocation]))

                        # Calculate reference for each instruction line
                        reference = 0
                        fixup_value = hex(int(fixup_value))
                        instruction_fields_info = instruction_fields_dict[line_instruction]
                        for item in reversed(instruction_fields_info):
                            default_mask = 0xffffffff
                            instrfield, instrfield_value = item
                            old_range_diff = 0
                            # Intrfields with multiple ranges
                            for i, range in enumerate(reversed(instrfield_range_dict[instrfield])):
                                # Create mask based on instrfield range
                                mask_low = default_mask << int(range[1])
                                mask_high = default_mask << (int(range[0]) + 1)
                                mask = (mask_low ^ mask_high) & 0xffffffff
                                if instrfield_value in operand_values_dict:
                                    # Registers
                                    if instrfield_value in instrfield_values_dict:
                                        for syntax_value, option_name in instrfield_values_dict[instrfield_value]:
                                            if operand_values_dict[instrfield_value] == syntax_value:
                                                result = mask & (int(option_name) << range[1])
                                    # Immediates
                                    else:
                                        shift = instrfield_shift_dict[instrfield]
                                        range_diff = int(range[0]) - int(range[1])
                                        if (i == 0):
                                            mask = ((default_mask << int(shift)) ^ (default_mask << (int(shift) + int(range_diff) + 1))) & 0xffffffff
                                            result = ((mask & (int(fixup_value, 16))) >> int(shift)) << int(range[1])
                                            old_range_diff = int(range[0]) - int(range[1]) + int(shift)
                                        else:
                                            mask = ((default_mask << (int(old_range_diff) + 1)) ^ (default_mask << (int(old_range_diff) + 2 + int(range_diff)))) & 0xffffffff                               
                                            result = ((mask & (int(fixup_value, 16))) >> (int(old_range_diff) + 1)) << int(range[1])
                                            old_range_diff += (range_diff + 1)                  
                                else:
                                    # Constants
                                    if instrfield_value in instrfield_range_dict:
                                        result = result
                                    else:
                                        result = mask & (int(instrfield_value) << range[1])
                                # Concatenate the result (OR)
                                reference = reference | result
                        references_list.append(reference)
                test_asm_file.close()

                # Write the matched line to the corresponding file in the "references" directory
                with open(ref_asm_file_path, 'w') as references_asm_file:
                    now = datetime.now()
                    references_asm_file.write(f"# Copyright (c) {now.strftime('%Y')} NXP\n")
                    references_asm_file.write("# SPDX-License-Identifier: BSD-2-Clause\n\n")
                    # Check instruction width
                    if int(instruction_width_dict[instruction]) == 32:
                        if bit_endianness == "little":
                            for ref in references_list:
                                if ref == 1: # Check for 'nop' instructions
                                    ref = str(hex(ref))
                                    ref = ref[2:]
                                    # Determine the length of the hex number
                                    length = len(ref)
                                    # Move the last two bytes to the front and add '0x' as necessary
                                    formatted_ref = '0x' + ref[length-2:] + ',0x' + ('0' + ref[:length-2] if len(ref) > 2 else '0' + ref[:length-2])
                                    references_asm_file.write(f".byte {formatted_ref}\n")
                                else:
                                    references_asm_file.write(f".word {hex(ref)}\n")
                        if bit_endianness == "big":
                            for ref in references_list:
                                if ref == 1: # Check for 'nop' instructions
                                    ref = str(hex(ref))
                                    ref = ref[2:]
                                    # Determine the length of the hex number
                                    length = len(ref)
                                    # Format by splitting with a comma and adding '0x' as necessary
                                    formatted_ref = '0x' + ('0' + ref[:length-2] if len(ref) > 2 else '0' + ref[:length-2]) + ',0x' + ref[length-2:]
                                    references_asm_file.write(f".byte {formatted_ref}\n")
                            else:
                                references_asm_file.write(f".word {hex(ref)}\n")
                    if int(instruction_width_dict[instruction]) == 16:
                        # Check bit endianness
                        if bit_endianness == "little":
                            for ref in references_list:
                                ref = str(hex(ref))
                                ref = ref[2:]
                                # Determine the length of the hex number
                                length = len(ref)
                                # Move the last two bytes to the front and add '0x' as necessary
                                formatted_ref = '0x' + ref[length-2:] + ',0x' + ('0' + ref[:length-2] if len(ref) > 2 else '0' + ref[:length-2])
                                references_asm_file.write(f".byte {formatted_ref}\n")
                        if bit_endianness == "big":
                            for ref in references_list:
                                ref = str(hex(ref))
                                ref = ref[2:]
                                # Determine the length of the hex number
                                length = len(ref)
                                # Format by splitting with a comma and adding '0x' as necessary
                                formatted_ref = '0x' + ('0' + ref[:length-2] if len(ref) > 2 else '0' + ref[:length-2]) + ',0x' + ref[length-2:]
                                references_asm_file.write(f".byte {formatted_ref}\n")
                    pass