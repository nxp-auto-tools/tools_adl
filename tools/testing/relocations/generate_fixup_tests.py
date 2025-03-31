# Copyright 2023-2025 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package generate_reloc_tests
# Relocations tests generation module
#
# Generates relocations tests for all instructions
import os
from datetime import datetime
import re
import sys
import shutil
import parse_reloc
import utils_reloc

sys.path.append(os.path.join(os.path.dirname(__file__), "../encoding/"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import config
import parse # type: ignore


def write_tests():

    # Get the command line arguments
    adl_file_path, adl_file_name, symbol_max_value, extension_list, output_dir, display_extensions = utils_reloc.cmd_args()

    # Get the path of the script
    script_directory = os.path.dirname(os.path.abspath(__file__))

    # Architecture and attributes
    llvm_config_dict = config.config_environment(os.path.join(script_directory, "../../config.txt"), os.path.join(script_directory, "../../llvm_config.txt"))
    architecture, attributes, mattrib = parse.assembler_and_cmdLine_args(adl_file_path)
    baseArchitecture = llvm_config_dict["BaseArchitecture"]

    # Split the keyword by the base architecture
    base_arch, extensions = attributes.split(baseArchitecture)

    # A dictionary with instructions and associated attribute prefixes
    instruction_attribute_dict, new_instruction_attribute_dict = parse.instruction_attribute(adl_file_path)

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

    # Begin test generation setup 
    instruction_attribute_dict, instruction_attribute_stripped_dict = parse.instruction_attribute(adl_file_path)
    instruction_operands_dict, instr_name_syntaxName_dict, imm_width_dict, imm_shift_dict, imm_signed_dict, instr_field_value_dict = parse.instructions_operands(adl_file_path)
    operand_values_dict, widths_dict, op_signExt_dict = parse.operands_values(adl_file_path)
    instruction_register_pair_dict, instrfield_optionName_dict = parse.register_pairs(adl_file_path)
    instruction_syntaxName_dict = parse_reloc.instructions_syntaxNames(adl_file_path)
    relocation_instructions_dict = parse_reloc.relocations_instructions(adl_file_path, parse_reloc.operands_instructions(parse_reloc.instructions_operands(adl_file_path)))
    relocation_instrfield_dict = parse_reloc.relocations_instrfields(adl_file_path, relocation_instructions_dict)
    relocation_abbrev_dict = parse_reloc.relocations_abbrevs(adl_file_path, relocation_instructions_dict)
    relocation_suffix_dict = parse_reloc.relocations_suffixes(adl_file_path, relocation_instructions_dict)
    relocation_dependency_dict = parse_reloc.relocations_dependencies(adl_file_path, relocation_instructions_dict)
    instrfield_width_dict = parse_reloc.instrfields_widths(adl_file_path, relocation_instrfield_dict)
    instrfield_shift_dict = parse_reloc.instrfields_shifts(adl_file_path, relocation_instrfield_dict)
    instrfield_signed_dict = parse_reloc.instrfields_signed(adl_file_path, relocation_instrfield_dict)
    final_width_dict = {key: int(instrfield_width_dict[key] + instrfield_shift_dict[key] + instrfield_signed_dict[key]) for key in instrfield_width_dict}
    relocation_pcrel_dict = parse_reloc.relocations_pcrel(adl_file_path)
    relocation_attributes_dict = parse_reloc.relocations_attributes(adl_file_path)
    relocation_action_dict = parse_reloc.relocations_action(adl_file_path)

    # Check if the output directory exists and refresh it
    if extension_list is not None:
        if os.path.exists(os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'tests_' + '_'.join(extension_list))):
            shutil.rmtree(os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'tests_' + '_'.join(extension_list)))
    else:
        if os.path.exists(os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'tests_all')):
            shutil.rmtree(os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'tests_all'))

    # Create a folder for each relocation
    for i, (relocation, instructions) in enumerate(relocation_instructions_dict.items()):
        # Check if relocation has fixup information
        if relocation in relocation_action_dict.keys():
            # Generate tests for specific extensions
            if extension_list is None or any(extension in extension_list for extension in relocation_attributes_dict[relocation]):
                # Create a folder for each instruction
                if extension_list is not None:
                    folder_name = os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'tests_' + '_'.join(extension_list), f"{relocation}")
                else:
                    folder_name = os.path.join(output_dir, 'fixup_results_' + adl_file_name, 'tests_all', f"{relocation}")               
                os.makedirs(folder_name)

                # Create a file for each instruction
                for instruction in instructions:
                    # Generate tests for specific extensions
                    if extension_list is None or any(extension in extension_list for extension in instruction_attribute_dict[instruction]):

                        # A list in which offsets are separated from immediates
                        operands_extended = instruction_operands_dict[instruction][:]

                        # Check if immediate has offset
                        for i in range(len(operands_extended)):
                            offset = re.findall(r'\((.*?)\)', operands_extended[i])
                            if offset:
                                operands_extended[i] = re.sub(
                                    r'\(.*?\)', '', operands_extended[i])
                                operands_extended.insert(i + 1, offset[0])

                        # Store offsets separately
                        offsets = []
                        for op in instruction_operands_dict[instruction]:
                            offset = re.search(r'\((.*?)\)', op)
                            if offset:
                                offsets.append(offset.group(1))

                        # A function that handles different types of operands (offsets, registers, immediates with or without abbreviations) for the Sym.Value case
                        def handle_operand_sym_value(op, label, abbrev, suffix):
                            # if operand has offset and it's a value from info dict put its value between ()
                            if op in offsets and op in operand_values_dict:
                                if instruction in instruction_register_pair_dict:
                                    return '(' + str(utils_reloc.extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0])) + ')'                                   
                                else:
                                    return '(' + str(operand_values_dict[op][-1]) + ')'
                            # if operands doen't have offset but it's a value from info dict take its register value
                            elif op in operand_values_dict:
                                if instruction in instruction_register_pair_dict:
                                    return str(utils_reloc.extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0]))  
                                else:
                                    return operand_values_dict[op][-1]
                            # if operand is an immediate generate values based on label
                            elif op in final_width_dict:
                                if abbrev:
                                    return '%' + abbrev + '(' + str(label) + ')'
                                elif suffix:
                                    return str(label) + suffix
                                else:
                                    return str(label)
                            else:
                                return op
                            
                        # A function that handles different types of operands (offsets, registers, immediates with or without abbreviations) for the Sym.Value case
                        def handle_operand_sym_value_dependency(op, label, abbrev, suffix):
                            # if operands doen't have offset but it's a value from info dict take its register value
                            if op in operand_values_dict:
                                if instruction in instruction_register_pair_dict:
                                    return str(utils_reloc.extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0]))
                                else:
                                    return operand_values_dict[op][-1]
                            # if operand is an immediate generate values based on label
                            elif op in final_width_dict:
                                if abbrev:
                                    return '%' + abbrev + '(' + str(label) + ')'
                                elif suffix:
                                    return str(label) + suffix
                                else:
                                    return str(label)
                            else:
                                return op
                            
                        # A function that handles different types of operands (offsets, registers, immediates with or without abbreviations) for the Addend case
                        def handle_operand_addend(op, label, abbrev, suffix, addend=None):
                            # if operand has offset and it's a value from info dict put its value between ()
                            if op in offsets and op in operand_values_dict:
                                if instruction in instruction_register_pair_dict:
                                    return '(' + str(utils_reloc.extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0])) + ')'
                                else:
                                    return '(' + str(operand_values_dict[op][-1]) + ')'
                            # if operands doen't have offset but it's a value from info dict take its register value
                            elif op in operand_values_dict:
                                if instruction in instruction_register_pair_dict:
                                    return str(utils_reloc.extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0]))
                                else:
                                    return operand_values_dict[op][-1]
                            # if operand is an immediate generate values based on label + addend
                            elif op in final_width_dict:
                                if addend is not None:
                                    if abbrev:
                                        return '%' + abbrev + '(' + str(label) + '+' + str(addend) + ')'
                                    elif suffix:
                                        return '(' + str(label) + '+' + str(addend) + ')' + suffix
                                    else:
                                        return '(' + str(label) + '+' + str(addend) + ')'
                                else:
                                    if abbrev:
                                        return '%' + abbrev + '(' + str(label) + ')'
                                    elif suffix:
                                        return str(label) + suffix
                                    else:
                                        return str(label)
                            else:
                                return op    
                                                                          
                        # Check if the relocation applies only to a subset of instructions          
                        file_name = os.path.join(folder_name, f"{relocation}_{instruction}.s")
                        with open(file_name, "w") as f:
                            now = datetime.now()
                            # Write the data to the file
                            f.write('Data:\n')
                            f.write(f"#   Copyright (c) {now.strftime('%Y')} NXP\n")
                            f.write("#   SPDX-License-Identifier: BSD-2-Clause\n")
                            f.write(f'#   @file    {relocation}_{instruction}.s\n')
                            f.write('#   @version 1.0\n')
                            f.write('#\n')
                            f.write(
                                '#-----------------\n')
                            f.write('# Date D/M/Y\n')
                            f.write(f"# {now.strftime('%d-%m-%Y')}\n")
                            f.write(
                                '#-----------------\n')
                            f.write('#\n')
                            f.write(f'# @test_id        {relocation}_{instruction}.s\n')
                            f.write('# @brief          Encode %s %s' %(instruction_syntaxName_dict[instruction], ",".join(instruction_operands_dict[instruction])) + '\n')
                            if relocation in relocation_dependency_dict:
                                    instruction_dep = relocation_instructions_dict[relocation_dependency_dict[relocation][0]][0]
                                    f.write('# @brief          Encode_dep %s %s' %(instruction_syntaxName_dict[instruction_dep], ",".join(instruction_operands_dict[instruction_dep])) + '\n')
                            f.write('# @details        Tests if the relocation for the source address is generated correctly\n')
                            f.write('# @pre            Python 3.9+\n')
                            f.write('# @test_level     Unit\n')
                            f.write('# @test_type      Functional\n')
                            f.write('# @test_technique Blackbox\n')
                            f.write(f'# @pass_criteria  Relocation {relocation} generated\n')
                            f.write('# @test_method    Analysis of requirements\n')
                            f.write('# @requirements   \"%s\" syntax and encoding from %s' % (instruction, adl_file_name) + '\n')
                            f.write('# @execution_type Automated\n')
                            f.write('\n')
                            if extension_list is not None:
                                extension_str = '_'.join(extension_list)
                                f.write(f'// RUN: %asm -I/{os.path.abspath(output_dir)}/fixup_results_{adl_file_name}/tests_{extension_str}/{relocation} -arch={architecture} -mattr="{mattrib}" %s -o %s.o -filetype=obj\n')
                                f.write(f'// RUN: %readelf -x 2 %s.o | %filecheck {os.path.abspath(output_dir)}/fixup_results_{adl_file_name}/references_tests/readelf/{os.path.basename(file_name)}.o.txt\n\n')
                            else:
                                f.write(f'// RUN: %asm -I/{os.path.abspath(output_dir)}/fixup_results_{adl_file_name}/tests_all/{relocation} -arch={architecture} -mattr="{mattrib}" %s -o %s.o -filetype=obj\n')
                                f.write(f'// RUN: %readelf -x 2 %s.o | %filecheck {os.path.abspath(output_dir)}/fixup_results_{adl_file_name}/references_tests/readelf/{os.path.basename(file_name)}.o.txt\n\n')
                            f.write('\t.text\n')
                            f.write('\t.attribute	4, 16\n')
                            f.write(f'\t.attribute	5, "{baseArchitecture}i{extension_versions_dict["i"]}_c{extension_versions_dict["c"]}')
                            for extension in new_instruction_attribute_dict[instruction]:
                                if extension in extension_versions_dict.keys() and extension != "i" and extension != "c":
                                    f.write(f'_{extension}{extension_versions_dict[extension]}')
                            f.write(f'"\n')
                            f.write(f'\t.globl {instruction}\n')
                            f.write('\t.p2align	1\n')
                            f.write(f'\t.type	{instruction},@function\n\n')
                            # Write labels
                            for i in range(1, int(final_width_dict[relocation_instrfield_dict[relocation]]) - instrfield_shift_dict[relocation_instrfield_dict[relocation]]):
                                if relocation not in relocation_dependency_dict:
                                    label = str(f'L{i}')
                                    f.write(f'{label}:\n')
                                    f.write("\tc.nop\n")
                            f.write(f'\n') 
                            # Write relocation dependencies                           
                            if relocation in relocation_dependency_dict:
                                f.write("#Add relocation dependencies\n")
                                for i in reversed(range(1, int(final_width_dict[relocation_instrfield_dict[relocation]]) - instrfield_shift_dict[relocation_instrfield_dict[relocation]])):
                                    label = str(f'L{i}')
                                    relocation_dep_list = relocation_dependency_dict[relocation]
                                    for relocation_dep in relocation_dep_list:
                                        op_values_dependency = []
                                        try:
                                            relocation_inst = relocation_instructions_dict[relocation_dep][0]
                                        except KeyError:
                                            "Relocation dependency not found in the dictionary. Make sure the dependency instruction in also generated for encoding tests."
                                        relocation_abbrev = relocation_abbrev_dict[relocation_dep]
                                        relocation_suffix = relocation_suffix_dict[relocation_dep] if relocation_dep in relocation_suffix_dict else None
                                        operands_extended_dependency = instruction_operands_dict[relocation_inst][:]
                                        for op in operands_extended_dependency:
                                            op_values_dependency.append(handle_operand_sym_value_dependency(op, label, relocation_abbrev, relocation_suffix))
                                        if not instruction_operands_dict[relocation_inst][-1].startswith('('):
                                            f.write(f'{label}:\n')
                                            f.write(f"\t{instruction_syntaxName_dict[relocation_inst]} {','.join(op_values_dependency)}\n")
                                        else:
                                            f.write(f'{label}:\n')
                                            f.write(f"\t{instruction_syntaxName_dict[relocation_inst]} {','.join(op_values_dependency[:-1])}{op_values_dependency[-1]}\n")
                                f.write('\n')                           
                            # Testing each bit for the Sym.Value
                            f.write("#Testing each bit for the Sym.Value field from the relocation section\n")
                            for i in reversed(range(1, int(final_width_dict[relocation_instrfield_dict[relocation]]) - instrfield_shift_dict[relocation_instrfield_dict[relocation]])):
                                label = str(f'L{i}')
                                op_values = []
                                abbrev = relocation_abbrev_dict[relocation] if relocation in relocation_abbrev_dict else None
                                suffix = relocation_suffix_dict[relocation] if relocation in relocation_suffix_dict else None
                                # Populate the list with the values of the operands
                                for op in operands_extended:
                                    op_values.append(handle_operand_sym_value(op, label, abbrev, suffix))
                                # Check if the operand has offset
                                if not offsets:
                                    f.write(f"\t{instruction_syntaxName_dict[instruction]} {','.join(op_values)}\n")
                                # if it does, concatenate last operand without comma
                                else:
                                    f.write(f"\t{instruction_syntaxName_dict[instruction]} {','.join(op_values[:-1])}{op_values[-1]}\n")    
                            # Testing each bit for the Addend field
                            f.write("\n#Testing each bit for the Addend field from the relocation section\n")
                            for i in reversed(range(1, int(final_width_dict[relocation_instrfield_dict[relocation]]) - instrfield_shift_dict[relocation_instrfield_dict[relocation]])):
                                label = str(f'L{i}') 
                                addend = hex(pow(2,i))                               
                                op_values = []
                                abbrev = relocation_abbrev_dict[relocation] if relocation in relocation_abbrev_dict else None
                                suffix = relocation_suffix_dict[relocation] if relocation in relocation_suffix_dict else None
                                # Populate the list with the values of the operands
                                for op in operands_extended:
                                    op_values.append(handle_operand_addend(op, label, abbrev, suffix, addend))
                                # Check if the operand has offset
                                if not offsets:
                                    f.write(f"\t{instruction_syntaxName_dict[instruction]} {','.join(op_values)}\n")
                                # if it does, concatenate last operand without comma
                                else:
                                    f.write(f"\t{instruction_syntaxName_dict[instruction]} {','.join(op_values[:-1])}{op_values[-1]}\n")                            
                            f.close()
    return