# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package generate_reference
# References generation module
#
# Generates references for all instructions encoding tests
import os
import re
import parse_reference
from datetime import datetime
import utils

## Writes the reference information for each instruction line inside each instruction test
# @param adl_file Name of the adl file
def generate_reference(adl_file):

    # Get the command line arguments
    adl_file_path, adl_file_name, cmd_extensions, output_dir = utils.cmd_args()

    # Define the paths to the "tests" and "references" directories
    tests_directory = os.path.join(output_dir, 'results_' + adl_file_name, "tests_" + '_'.join(cmd_extensions))
    references_directory = os.path.join(output_dir, 'results_' + adl_file_name, "refs_" + '_'.join(cmd_extensions))

    # Define a regular expression syntax_pattern to match the desired line
    syntax_pattern = r'# @brief\s+Encode\s+(.+)$'

    # A dictionary for mapping operands with the values from the assembly files
    operand_values_dict = dict() 

    # Dictionaries containing information for generating references
    instruction_fields_dict = parse_reference.instructions_fields(adl_file)
    instrfield_range_dict = parse_reference.instrfield_range(adl_file)
    instrfield_values_dict = parse_reference.instrfield_values(adl_file)
    instrfield_shift_dict = parse_reference.instrfield_shift(adl_file)
    instruction_width_dict = parse_reference.instruction_width(adl_file)
    bit_endianness = parse_reference.bit_endianness(adl_file)
    instruction_syntaxName_dict = parse_reference.instruction_syntaxName(adl_file)

    # Iterate through all directories and subdirectories under "tests_" directory
    for dirpath, dirnames, filenames in os.walk(tests_directory):
        for filename in filenames:
            if filename.endswith(".asm"):
                # Construct the full path to the source .asm file
                source_asm_file_path = os.path.join(dirpath, filename)

                # Construct the corresponding path in the "references" directory
                references_asm_file_path = os.path.join(references_directory, filename)

                # Extract the name of the instruction from the file path
                instruction_name = os.path.splitext(os.path.basename(source_asm_file_path))[0]

                # A regular expression to match instruction lines
                instruction_pattern = r'^\t' + re.escape(instruction_syntaxName_dict[instruction_name])

                # Open the source .asm file for reading
                with open(source_asm_file_path, 'r') as source_asm_file:

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

                    # Search for the line that matches the syntax_pattern
                    lines = source_asm_file.readlines()
                    # Use the regular expression to find matching lines
                    matching_lines = [line.strip() for line in lines if re.match(instruction_pattern, line)]
                    references_list = []
                    operand_values_dict = {}

                    for line in matching_lines:
                        # Split lines into instructions and operands
                        line_instruction_parts = line.split()
                        if len(line_instruction_parts) >= 2:
                            line_instruction = line_instruction_parts[0]
                            line_operands = line_instruction_parts[1]
                        else:
                            line_instruction = line_instruction_parts[0]
                            line_operands = None

                        syntax_operands_values = re.findall(r'[\w_]+', str(syntax_operands))
                        line_operands_values = re.findall(r'[-\w_]+', str(line_operands))
                        operand_values_dict = {key: value for key, value in zip(syntax_operands_values, line_operands_values)}
                        # Calculate reference for each instruction line
                        reference = 0
                        instruction_fields_info = instruction_fields_dict[syntax_instruction]
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
                                    if instrfield_value in instrfield_values_dict:
                                        for syntax_value, option_name in instrfield_values_dict[instrfield_value]:
                                            if operand_values_dict[instrfield_value] == syntax_value:
                                                # Registers
                                                result = mask & (int(option_name) << range[1])
                                    else:
                                        # Immediates
                                        shift = instrfield_shift_dict[instrfield]
                                        range_diff = int(range[0]) - int(range[1])
                                        if (i == 0):
                                            mask = ((default_mask << int(shift)) ^ (default_mask << (int(shift) + int(range_diff) + 1))) & 0xffffffff
                                            result = ((mask & (int(operand_values_dict[instrfield_value], 16))) >> int(shift)) << int(range[1])
                                            old_range_diff = int(range[0]) - int(range[1]) + int(shift)
                                        else:
                                            mask = ((default_mask << (int(old_range_diff) + 1)) ^ (default_mask << (int(old_range_diff) + 2 + int(range_diff)))) & 0xffffffff
                                            result = ((mask & (int(operand_values_dict[instrfield_value], 16))) >> (int(old_range_diff) + 1)) << int(range[1])
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

                # Write the matched line to the corresponding file in the "references" directory
                with open(references_asm_file_path, 'w') as references_asm_file:
                    now = datetime.now()
                    references_asm_file.write(f"# Copyright (c) {now.strftime('%Y')} NXP\n")
                    references_asm_file.write("# SPDX-License-Identifier: BSD-2-Clause\n\n")
                    # Check instruction width
                    if int(instruction_width_dict[instruction_name]) == 32:
                        for ref in references_list:
                            references_asm_file.write(f".word {hex(ref)}\n")
                    if int(instruction_width_dict[instruction_name]) == 16:
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
