import os
import re
import utils
import utils_reloc
import parse_reloc
import generate_reloc_tests
from datetime import datetime


def generate_reloc_reference():
    
    # Get the command line arguments
    adl_file_path, adl_file_name, symbol_max_value, output_dir = utils_reloc.cmd_args()

    # Define the paths to the "tests" and "references" directories
    tests_directory = os.path.join(output_dir, 'reloc_results_' + adl_file_name, 'tests')
    references_directory = os.path.join(output_dir, 'reloc_results_' + adl_file_name, 'refs')

    # Dictionaries containing information for generating references
    instruction_width_dict = parse_reloc.instructions_widths(adl_file_path)
    instruction_syntaxName_dict = parse_reloc.instructions_syntaxNames(adl_file_path)
    instruction_alias_dict = parse_reloc.instructions_aliases(adl_file_path)
    relocation_instructions_dict = generate_reloc_tests.filter_relocations_instructions_dict()
    relocation_value_dict = parse_reloc.relocations_values(adl_file_path)
    relocation_dependencies_dict = parse_reloc.relocations_dependencies(adl_file_path, relocation_instructions_dict)
    relocation_label_dict = parse_reloc.relocations_labels(adl_file_path)
    relocation_directives_dict = parse_reloc.relocations_directives(adl_file_path)

    # Iterate through all directories and subdirectories under "tests" directory
    for dirpath, dirnames, filenames in os.walk(tests_directory):
        for filename in filenames:
            if filename.endswith(".s"):
                # Construct the full path to the source .s file
                test_asm_file_path = os.path.join(dirpath, filename)

                # Construct the corresponding path in the "references" directory
                ref_asm_file_path = os.path.join(references_directory, filename)

                # Find the instruction lines in the .s file
                matching_lines = []
                with open(test_asm_file_path, 'r') as test_asm_file:
                    for line in test_asm_file:
                        stripped_line = line.lstrip()
                        # Check for instruction relocations
                        if os.path.basename(dirpath) in relocation_instructions_dict.keys():
                            if line.startswith('\t') and any(stripped_line.startswith(instruction) for instruction in instruction_syntaxName_dict.keys() | instruction_syntaxName_dict.values()):
                                matching_lines.append(line.strip())
                        # Check for data relocations
                        elif os.path.basename(dirpath) in relocation_label_dict.keys():
                            if line.startswith('\t') and any(stripped_line.startswith(directive) for directive in relocation_directives_dict[os.path.basename(dirpath)]):
                                matching_lines.append(line.strip())
                test_asm_file.close()

                # Write the information to the corresponding reference file
                with open(ref_asm_file_path, 'w') as ref_asm_file:
                    # Check instruction width
                    now = datetime.now()
                    ref_asm_file.write(f"# Copyright (c) {now.strftime('%Y')} NXP\n")
                    ref_asm_file.write("# SPDX-License-Identifier: BSD-2-Clause\n\n")

                    # Split the instruction line into tokens
                    separators_pattern = r'[ ,()]'
                    offset = 0
                    for line in matching_lines:
                        split_line = re.split(separators_pattern, line)  
                        # Start generating the references for the instructions                  
                        for instruction, width in instruction_width_dict.items():
                            # Check for instruction relocations
                            if instruction in split_line:
                                # Create a regex pattern to match the label and the variable
                                label_pattern = r'L\d+'
                                var_pattern = r'var\d+'
                                matching_label = next((label for label in split_line if re.match(label_pattern, label)), None)
                                matching_var = next((var for var in split_line if re.match(var_pattern, var)), None)
                                # Create a regex pattern to match the relocation and discard the instruction from the filename
                                for reloc in relocation_instructions_dict.keys():
                                    pattern = rf'({reloc})_.*\.s'
                                    # Check if the pattern matches the filename
                                    match = re.match(pattern, filename)
                                    if match:
                                        relocation = match.group(1)
                                # Check if the relocation uses a label
                                if matching_label in split_line:
                                    label_index = split_line.index(matching_label)
                                    # Check if it also has an addend
                                    if label_index + 2 < len(split_line) and split_line[label_index + 1] == '+':
                                        addend = split_line[label_index + 2][2:]
                                    else:
                                        addend = '0'
                                    # Check if the current instruction or the alias matches the relocation or it's a dependency
                                    if instruction in relocation_instructions_dict[relocation] or next((instr for instr, alias in instruction_alias_dict.items() if alias == instruction), None) in relocation_instructions_dict[relocation]:
                                        hex_offset = f"{int(offset):08x}"
                                        ref_asm_file.write(f'// CHECK: {hex_offset} {{{{.*}}}}{hex(int(relocation_value_dict[relocation]))[2:]} {relocation} {{{{.*}}}} {matching_label} + {addend}\n')
                                        offset += int(width)/8
                                    else:
                                        if relocation in relocation_dependencies_dict.keys():
                                            for relocation_dependency in relocation_dependencies_dict[relocation]:
                                                if instruction in relocation_instructions_dict[relocation_dependency]:
                                                    break
                                        hex_offset = f"{int(offset):08x}"
                                        ref_asm_file.write(f'// CHECK: {hex_offset} {{{{.*}}}}{hex(int(relocation_value_dict[relocation_dependency]))[2:]} {relocation_dependency} {{{{.*}}}} {matching_label} + {addend}\n')
                                        offset += int(width)/8                                  
                                # Check if the relocation uses a variable
                                if matching_var in split_line:
                                    addend = '0'
                                    # Check if the current instruction or the alias matches the relocation or it's a dependency
                                    if instruction or next((instr for instr, alias in instruction_alias_dict.items() if alias == instruction), None) in relocation_instructions_dict[relocation]:
                                        hex_offset = f"{int(offset):08x}"
                                        ref_asm_file.write(f'// CHECK: {hex_offset} {{{{.*}}}}{hex(int(relocation_value_dict[relocation]))[2:]} {relocation} {{{{.*}}}} {matching_var} + {addend}\n')
                                        offset += int(width)/8
                                    else:
                                        if relocation in relocation_dependencies_dict.keys():
                                            for relocation_dependency in relocation_dependencies_dict[relocation]:
                                                if instruction in relocation_instructions_dict[relocation_dependency]:
                                                    break
                                        hex_offset = f"{int(offset):08x}"
                                        ref_asm_file.write(f'// CHECK: {hex_offset} {{{{.*}}}}{hex(int(relocation_value_dict[relocation_dependency]))[2:]} {relocation_dependency} {{{{.*}}}} {matching_var} + {addend}\n')
                                        offset += int(width)/8
                        # Start generating data references
                        for relocation, directives in relocation_directives_dict.items():
                            if (relocation == os.path.basename(dirpath)) and any(directive in split_line for directive in directives):
                                for directive in directives:
                                    # Check for .reloc directive
                                    if directive in split_line and directive ==".reloc":
                                        offset = f"{int(split_line[1], 16):08x}"
                                        symbol = split_line[3]
                                        addend = '0'
                                        ref_asm_file.write(f'// CHECK: {offset} {{{{.*}}}}{hex(int(relocation_value_dict[relocation]))[2:]} {relocation} {{{{.*}}}} {symbol} + {addend}\n')
                                    #TODO Check for other directives
                                    else:
                                        continue
                ref_asm_file.close()