# Copyright 2023-2025 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package generate_inst_tests
# Tests generation module
#
# Writes all tests cases for all instructions
import os
import glob
from datetime import datetime
import re
import sys
import utils
import parse

sys.path.append(os.path.join(os.path.dirname(__file__), "./../../"))
import config

## Writes all information about a test at the beginning of the file
def write_header():
    
    # Get the command line arguments
    adl_file_path, adl_file_name, cmd_extensions, output_dir, display_extenions = utils.cmd_args()

    # Get the path of the script
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    # A dictionary for the configuration environment
    llvm_config_dict = config.config_environment(os.path.join(script_directory, "../../config.txt"), os.path.join(script_directory, "../../llvm_config.txt"))

    # architecture and attributes
    architecture, attributes, mattrib = parse.assembler_and_cmdLine_args(adl_file_path)
    baseArchitecture = llvm_config_dict["BaseArchitecture"]

    # A dictionary with instructions and associated attribute prefixes
    instruction_attribute_dict, new_instruction_attribute_dict = parse.instruction_attribute(adl_file_path)

    # Split the keyword by the base architecture
    base_arch, extensions = attributes.split(baseArchitecture)

    # Split the extension by underscores in order to get extensions and versions
    extensions_and_versions = extensions.split('_')

    # Initialize a dictionary to map extensions to versions
    extension_versions_dict = {}

    # Iterate through the extensions and their versions
    for item in extensions_and_versions:
        # split the string when sequence <number>p<number> is found
        match = re.search(r'(\D+)(\d+p\d+)', item)
        if match:
            extension_versions_dict[match.group(1)] = match.group(2)

    instr_op_dict, instrName_syntaxName_dict, imm_width_dict, imm_shift_dict, imm_signed_dict, instr_field_value_dict = parse.instructions_operands(adl_file_path)

    # loop through the instructions dictionary
    for i, (instruction, operands) in enumerate(instr_op_dict.items()):
        # generate tests only for specific extensions
        if cmd_extensions is None or all(extension in cmd_extensions for extension in instruction_attribute_dict[instruction]):
            # create a folder for each instruction
            if cmd_extensions is not None:
                folder_name = os.path.join(output_dir, 'results_' + adl_file_name, "tests_" + '_'.join(cmd_extensions), f"{instruction}")
            else:
                folder_name = os.path.join(output_dir, 'results_' + adl_file_name, "tests_all", f"{instruction}")
            os.makedirs(folder_name)
            # create a file in the folder with the same name as the instruction
            file_name = os.path.join(folder_name, f"{instruction}.asm")
            with open(file_name, "w") as f:
                now = datetime.now()
                # write the data to the file
                f.write("Data:\n")
                f.write(f"#   Copyright (c) {now.strftime('%Y')} NXP\n")
                f.write("#   SPDX-License-Identifier: BSD-2-Clause\n")
                f.write('#   @file    %s' % adl_file_name + '\n')
                f.write('#   @version 1.0\n')
                f.write('#\n')
                f.write(
                    '#-----------------\n')
                f.write('# Date D/M/Y\n')
                f.write(f"# {now.strftime('%d-%m-%Y')}\n")
                f.write(
                    '#-----------------\n')
                f.write('#\n')
                f.write('# @test_id        %s' % adl_file_name + '\n')
                f.write('# @brief          Encode %s %s' %
                        (instrName_syntaxName_dict[instruction], ",".join(operands)) + '\n')
                f.write('# @details        Tests if each bit is encoded correctly for %s instruction' %
                        instruction + '\n')
                f.write('# @pre            Python 3.9+\n')
                f.write('# @test_level     Unit\n')
                f.write('# @test_type      Functional\n')
                f.write('# @test_technique Blackbox\n')
                f.write(
                    '# @pass_criteria  Run lit_references_tester.sh and then llvm-lit to see if all tests have passed!\n')
                f.write('# @test_method    Analysis of requirements\n')
                f.write('# @requirements   \"%s\" syntax and encoding from %s' % (
                    instruction, adl_file_name) + '\n')
                f.write('# @execution_type Automated\n')
                f.write('\n')
                f.write(f'// RUN: %asm -arch={architecture} -mattr="{mattrib}" %s -o %s.o -filetype=obj\n')
                f.write(f'// RUN: %readelf -x 2 %s.o | %filecheck reference.txt\n\n')
                f.write('\t.text\n')
                f.write('\t.attribute	4, 16\n')
                f.write(f'\t.attribute	5, "{baseArchitecture}i{extension_versions_dict["i"]}')
                for extension in new_instruction_attribute_dict[instruction]:
                    if extension in extension_versions_dict.keys() and extension != "i":
                        f.write(f'_{extension}{extension_versions_dict[extension]}')
                f.write(f'"\n')
                f.write(f'\t.globl {instruction}\n')
                f.write('\t.p2align	1\n')
                f.write(f'\t.type	{instruction},@function\n')
                f.close()

## Writes all instruction tests cases for each type of operand
def generate_instructions():

    # Get the command line arguments
    adl_file_path, adl_file_name, cmd_extensions, output_dir, display_extensions = utils.cmd_args()
    
    instr_op_dict, instrName_syntaxName_dict, imm_width_dict, imm_shift_dict, imm_signed_dict, instr_field_value_dict = parse.instructions_operands(adl_file_path)
    op_val_dict, widths_dict, op_signExt_dict = parse.operands_values(adl_file_path)
    instruction_register_pair_dict, instrfield_optionName_dict = parse.register_pairs(adl_file_path)

    # A dictionary with instructions and associated attribute prefixes
    instruction_attribute_dict, new_instruction_attribute_dict = parse.instruction_attribute(adl_file_path)

    # Initialize an empty dictionary to convert instr_field_value_dict into a dict of dicts
    instrfield_value_double_dict = {}

    # Iterate through the original dictionary
    for key, tuples in instr_field_value_dict.items():
        # Initialize a new dictionary for each key
        new_dict = {}
        for operand, value in tuples:
            new_dict[operand] = value
        # Add the new dictionary as the value for the key in the result dictionary
        instrfield_value_double_dict[key] = new_dict

    # delete operand from immediates if you find it in op_val_dict
    for key in op_val_dict.keys():
        if key in imm_width_dict.keys() or key in imm_shift_dict:
            del imm_width_dict[key]
            del imm_shift_dict[key]

    if cmd_extensions is not None:
        file_paths = glob.glob(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_' + '_'.join(cmd_extensions), '**', '*.asm'), recursive=True)
    else:
        file_paths = glob.glob(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_all', '**', '*.asm'), recursive=True)

    for file_path in file_paths:
        path_components = file_path.split(os.path.sep)
        for instruction, operands in instr_op_dict.items():
            # generate tests only for specific extensions
            if instruction in path_components and (cmd_extensions is None or all(extension in cmd_extensions for extension in instruction_attribute_dict[instruction])):
                # case if instruction has no operands
                if operands == []:
                    with open(file_path, 'a') as f:
                        f.write(f'\n{instruction}:\n')
                        f.write(f"\n\t{instrName_syntaxName_dict[instruction]}\n")
                        f.write(f'.{instruction}_end:\n')
                        f.write(f'\t.size   {instruction}, .{instruction}_end-{instruction}')
                # case if instruction has only register operands
                elif all(op in op_val_dict for op in operands):
                    with open(file_path, 'a') as f:
                        f.write(f'\n{instruction}:')
                        # clear operands from dict of parentheses
                        for key in op_val_dict.keys():
                            op_val_dict[key] = [element.strip('()') for element in op_val_dict[key]] 
                        for i, operand in enumerate(operands):
                            other_operands = [op for op in operands if op != operand]
                            # check if instruction is hint
                            if '_hint' in instruction:
                                other_operand_values = [op_val_dict[op][0] for op in other_operands]
                            else:
                                other_operand_values = [op_val_dict[op][-1] for op in other_operands]
                            if operand in widths_dict.keys():
                                # check if any register operand is actually a constant value
                                found_constant = False                        
                                for tuple in instr_field_value_dict[instruction]:
                                        if tuple[0] == operand and tuple[1] != None:
                                            found_constant = True
                                            possible_value_1 = 2 * int(tuple[1])
                                            possible_value_2 = 2 * int(tuple[1]) + 2
                                # if it is, adjust the description of the operand
                                if found_constant:
                                    f.write(f"\n#Testing operand {operand} encoded on {widths_dict[operand]} bits with {len(op_val_dict[operand][possible_value_1:possible_value_2])} values: {op_val_dict[operand][possible_value_1:possible_value_2]}\n")
                                else:
                                    f.write(f"\n#Testing operand {operand} encoded on {widths_dict[operand]} bits with {len(op_val_dict[operand])} values: {op_val_dict[operand]}\n")
                            for j, value in enumerate(op_val_dict[operand]):
                                # check if any register operand is actually a constant value
                                found_constant = False
                                for tuple in instr_field_value_dict[instruction]:
                                        if tuple[0] == operand and tuple[1] != None: 
                                            value = op_val_dict[operand][2 * int(tuple[1])]
                                            found_constant = True
                                            break
                                instr_line = other_operand_values[:]
                                instr_line.insert(i, value)                           
                                f.write(f"\t{instrName_syntaxName_dict[instruction]} {','.join(instr_line)}\n") 

                                # if there is a register with constant value, take only the possible values  
                                if found_constant:
                                    value = op_val_dict[operand][2 * int(tuple[1]) + 1]
                                    instr_line = other_operand_values[:]
                                    instr_line.insert(i, value)
                                    f.write(f"\t{instrName_syntaxName_dict[instruction]} {','.join(instr_line)}\n")
                                    break
                        f.write(f'.{instruction}_end:\n')
                        f.write(
                            f'\t.size	{instruction}, .{instruction}_end-{instruction}')
                # case if instruction has immediates and immediates with offsets
                else:
                    with open(file_path, 'a') as f:
                        f.write(f'\n{instruction}:')               
                        # a list in which offsets are separated from immediates
                        operands_extended = operands[:]                
                        # check if immediate has offset
                        for i in range(len(operands_extended)):
                            offset = re.findall(r'\((.*?)\)', operands_extended[i])
                            if offset:
                                operands_extended[i] = re.sub(
                                    r'\(.*?\)', '', operands_extended[i])
                                operands_extended.insert(i + 1, offset[0])                
                        # store offsets separately
                        offsets = []
                        for op in operands:
                            offset = re.search(r'\((.*?)\)', op)
                            if offset:
                                offsets.append(offset.group(1))                
                        # clear operands from dict of parentheses
                        for key in op_val_dict.keys():
                            op_val_dict[key] = [element.strip(
                                '()') for element in op_val_dict[key]]                
                        # check operand type
                        for op in operands_extended:
                            # if operand has offset and it's NOT a value from dict put its name between ()
                            if op in offsets and op not in op_val_dict:
                                op_values = [op]
                                for i in range(len(op_values)):
                                    op_values[i] = '(' + str(op_values[i]) + ')'
                            # if operand has offset and it's a value from dict put its value between ()
                            elif op in offsets and op in op_val_dict:
                                # if operand has offset with paired values
                                if instruction in instruction_register_pair_dict and op in instruction_register_pair_dict[instruction]:
                                    pair_value_list = []
                                    for val_optName_tuple in instrfield_optionName_dict[op]:
                                        # take only even values
                                        if int(val_optName_tuple[0]) % 2 == 0:
                                            pair_value_list.append(val_optName_tuple[1])
                                    op_values = [value for value in pair_value_list if value in op_val_dict[op]]
                                else:
                                    op_values = op_val_dict[op]
                                for i in range(len(op_values)):
                                    op_values[i] = '(' + str(op_values[i]) + ')'
                            # if operand is a register and has paired values
                            elif op in op_val_dict and instruction in instruction_register_pair_dict and op in instruction_register_pair_dict[instruction]:
                                pair_value_list = []
                                for val_optName_tuple in instrfield_optionName_dict[op]:
                                    # take only even values
                                    if int(val_optName_tuple[0]) % 2 == 0:
                                        pair_value_list.append(val_optName_tuple[1])
                                op_values = [value for value in pair_value_list if value in op_val_dict[op]]
                            # if operand is just a simple register take the value from the dict
                            elif op in op_val_dict and instruction not in instruction_register_pair_dict:
                                # check if any register operand is actually a constant value
                                found_constant = False
                                for tuple in instr_field_value_dict[instruction]:
                                        if tuple[0] == op and tuple[1] != None:
                                            possible_value_1 = 2 * int(tuple[1])
                                            possible_value_2 = 2 * int(tuple[1]) + 2
                                            found_constant = True
                                # if there is a register with constant value, take only the possible values   
                                if found_constant:
                                    op_values = op_val_dict[op][possible_value_1:possible_value_2]
                                else:
                                # else take all values available
                                    op_values = op_val_dict[op]
                            # if operand is an immediate generate values based on its width
                            elif op in imm_width_dict:
                                width = imm_width_dict[op]
                                # if operand has sign extension, it has values in 2 separate intervals (2**(width-2) bcs the sign bit is included in width for this version)
                                if op in op_signExt_dict:
                                    # check if the operand is signed or not
                                    if imm_signed_dict[op] == 'true':
                                        op_values = [hex(2**(i + imm_shift_dict[op])) for i in range(
                                            0, width - imm_shift_dict[op] - 1)] + [hex(2**(width - 1) - 2**(imm_shift_dict[op]))]
                                        op_values += [hex(2**int(op_signExt_dict[op]) - 2**(width - 1)), hex(
                                            2**int(op_signExt_dict[op]) - 2**(imm_shift_dict[op]))]
                                    else:
                                        op_values = [hex(2**(i + imm_shift_dict[op])) for i in range(
                                            0, width - imm_shift_dict[op] - 2)] + [hex(2**(width - 2) - 2**(imm_shift_dict[op]))]
                                        op_values += [hex(2**int(op_signExt_dict[op]) - 2**(width - 2)), hex(
                                            2**int(op_signExt_dict[op]) - 2**(imm_shift_dict[op]))]
                                else:
                                    # check if any immediate operand is actually a constant value
                                    found_constant = False                        
                                    for tuple in instr_field_value_dict[instruction]:
                                            if tuple[0] == op and tuple[1] != None:
                                                found_constant = True
                                                possible_value = hex(int(tuple[1]))
                                    # if it is, take only the possible value
                                    if found_constant:
                                        op_values = [possible_value]
                                    # check if the immediate is signed in order to test the sign bit
                                    elif imm_signed_dict[op] == "true":
                                        width = imm_width_dict[op]
                                        op_values = [hex(2**(i + imm_shift_dict[op])) for i in range(0, width - imm_shift_dict[op] - 1)] + [hex(2**(width - 1) - 2**(imm_shift_dict[op]))] + [hex(~(2**(imm_shift_dict[op])) + 1)]     
                                    else:
                                        width = imm_width_dict[op]
                                        op_values = [hex(2**(i + imm_shift_dict[op])) for i in range(0, width - imm_shift_dict[op] - 1)] + [hex(2**(width - 1) - 2**(imm_shift_dict[op]))]
                            else:
                                # if operand not found in any dictionary use the operand name as its value
                                op_values = [op]
                            op_index = operands_extended.index(op)
                            fixed_operands = [f"({op_val_dict[x][0]})" if x in offsets and x in op_val_dict and '_hint' in instruction
                                            else f"({op_val_dict[x][-1]})" if x in offsets and x in op_val_dict and (int(instrfield_optionName_dict[x][-1][0]) % 2 == 0) and instruction in instruction_register_pair_dict
                                            else f"({op_val_dict[x][-3]})" if x in offsets and x in op_val_dict and (int(instrfield_optionName_dict[x][-1][0]) % 2 != 0) and instruction in instruction_register_pair_dict
                                            else f"({op_val_dict[x][-1]})" if x in offsets and x in op_val_dict
                                            else f"({x})" if x in offsets
                                            else op_val_dict[x][0] if x in op_val_dict and '_hint' in instruction
                                            else op_val_dict[x][-1] if x in op_val_dict and (int(instrfield_optionName_dict[x][-1][0]) % 2 == 0) and instruction in instruction_register_pair_dict
                                            else op_val_dict[x][-3] if x in op_val_dict and (int(instrfield_optionName_dict[x][-1][0]) % 2 != 0) and instruction in instruction_register_pair_dict
                                            else op_val_dict[x][-1] if x in op_val_dict
                                            else hex(2**(imm_width_dict[x] - 1) - 2**(imm_shift_dict[x])) if x in imm_width_dict and x in op_signExt_dict and imm_signed_dict[x] == "true"
                                            else hex(2**(imm_width_dict[x] - 2) - 2**(imm_shift_dict[x])) if x in imm_width_dict and x in op_signExt_dict
                                            else hex(int(instrfield_value_double_dict[instruction][x],16)) if x in imm_width_dict and instruction in instrfield_value_double_dict and x in instrfield_value_double_dict[instruction] and instrfield_value_double_dict[instruction][x] is not None
                                            else hex(2**(imm_width_dict[x] - 1) - 2**(imm_shift_dict[x])) if x in imm_width_dict
                                            else x for x in operands_extended if x != op]                    
                            # information displayed about each type of operand
                            if op in offsets:
                                # check if the offset is a paired register
                                if op in op_val_dict and instruction in instruction_register_pair_dict and op in instruction_register_pair_dict[instruction]:
                                    f.write(
                                        f"\n#Testing offset {op} encoded on {widths_dict[op]} bits with {len(op_values)} values: {op_values}\n")
                                elif op in op_val_dict:
                                    f.write(
                                        f"\n#Testing offset {op} encoded on {widths_dict[op]} bits with {len(op_val_dict[op])} values: {op_val_dict[op]}\n")
                                else:
                                    f.write(
                                        f"\n#Testing offset {op} with value {op}\n")
                            elif op in imm_width_dict:
                                if op in op_signExt_dict:
                                    if imm_signed_dict[op] == "true":
                                        f.write(
                                            f"\n#Testing each bit of {int(imm_width_dict[op])}-bit operand {op} extended to {op_signExt_dict[op]} bits in ranges: [{pow(2,imm_shift_dict[op])}, {pow(2, imm_width_dict[op] - 1) - 1}], [{hex(2**int(op_signExt_dict[op]) - 2**(imm_width_dict[op] - 1))}, {hex(2**int(op_signExt_dict[op]) - 2**(imm_shift_dict[op]))}]\n")
                                    else:
                                        f.write(
                                            f"\n#Testing each bit of {int(imm_width_dict[op]) - 1}-bit operand {op} extended to {op_signExt_dict[op]} bits in ranges: [{pow(2,imm_shift_dict[op])}, {pow(2, imm_width_dict[op] - 2) - 1}], [{hex(2**int(op_signExt_dict[op]) - 2**(imm_width_dict[op] - 2))}, {hex(2**int(op_signExt_dict[op]) - 2**(imm_shift_dict[op]))}]\n")
                                else:
                                    # check if any immediate operand is actually a constant value
                                    found_constant = False
                                    for tuple in instr_field_value_dict[instruction]:
                                            if tuple[0] == op and tuple[1] != None:
                                                possible_value = hex(int(tuple[1]))
                                                found_constant = True
                                    # if there is an immediate with constant value, take only the possible value   
                                    if found_constant:
                                        f.write(f"\n#Testing the only possible value of {imm_width_dict[op]}-bit operand {op}: {possible_value}\n")
                                    elif imm_signed_dict[op] == "true":
                                        f.write(f"\n#Testing each bit of {imm_width_dict[op]}-bit operand {op} in range [{pow(2,imm_shift_dict[op])}, {pow(2, imm_width_dict[op] - 1) - 2**(imm_shift_dict[op])}] and value {~(2**(imm_shift_dict[op]) + 1)} for sign bit\n")
                                    else:
                                        f.write(f"\n#Testing each bit of {imm_width_dict[op]}-bit operand {op} in range [{pow(2,imm_shift_dict[op])}, {pow(2, imm_width_dict[op] - 1) - 2**(imm_shift_dict[op])}]\n")
                            # check if the operand is a paired register
                            elif op in op_val_dict and instruction in instruction_register_pair_dict and op in instruction_register_pair_dict[instruction]:
                                f.write(f"\n#Testing operand {op} encoded on {widths_dict[op]} bits with {len(op_values)} values: {op_values}\n")
                            elif op in op_val_dict:
                                # check if any register operand is actually a constant value
                                found_constant = False
                                for tuple in instr_field_value_dict[instruction]:
                                        if tuple[0] == op and tuple[1] != None:
                                            found_constant = True
                                            possible_value_1 = 2 * int(tuple[1])
                                            possible_value_2 = 2 * int(tuple[1]) + 2
                                # if it is, adjust the description of the operand
                                if found_constant:
                                    f.write(f"\n#Testing operand {op} encoded on {widths_dict[op]} bits with {len(op_val_dict[op][possible_value_1:possible_value_2])} values: {op_val_dict[op][possible_value_1:possible_value_2]}\n")
                                else:
                                    f.write(f"\n#Testing operand {op} encoded on {widths_dict[op]} bits with {len(op_val_dict[op])} values: {op_val_dict[op]}\n")
                            else:
                                f.write(f"\n#Testing operand {op} with value {op}\n")                    
                            # check if the instruction has offset
                            if offsets == []:
                                for val in op_values:
                                    test_values = fixed_operands[:op_index] + \
                                        [val] + fixed_operands[op_index:]
                                    test_output = f"\t{instrName_syntaxName_dict[instruction]} {','.join(map(str, test_values))}\n"
                                    f.write(test_output)
                            else:
                                # if it does, concatenate last operand without comma
                                for val in op_values:
                                    test_values = fixed_operands[:op_index] + \
                                        [val] + fixed_operands[op_index:]
                                    # check if instruction is hint
                                    if '_hint' in instruction:
                                        test_output = f"\t{instrName_syntaxName_dict[instruction]} {','.join(map(str, test_values))}\n"
                                    else:
                                        test_output = f"\t{instruction} {','.join(map(str, test_values))}\n"
                                    f.write(test_output)
                        f.write(f'.{instruction}_end:\n')
                        f.write(f'\t.size   {instruction}, .{instruction}_end-{instruction}')