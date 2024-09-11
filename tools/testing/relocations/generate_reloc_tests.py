# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package generate_reloc_tests
# Relocations tests generation module
#
# Generates relocations tests for all instructions
import importlib
import os
import glob
from datetime import datetime
import shutil
import re
import sys
import parse_reloc

sys.path.append(os.path.abspath('../encoding'))
sys.path.append(os.path.abspath('../..'))
import parse
module_info = "info"
try:
    info = importlib.import_module(module_info)
except ImportError:
    print('Please run make_test.py first to generate the info module.')


# Function that filters relocations instructions dictionary based on the instructions that are generated for encoding tests
# @return @b filtered_relocations_instructions-> Dictionary containing relocations and their corresponding instructions matching the ones from the encoding tests
def filter_relocations_instructions_dict():
    try:
        adl_file_path = sys.argv[1]
    except:
        raise ValueError("Please provide adl file as the 1st argument")
    
    relocations_instructions_dict = parse_reloc.relocations_instructions(adl_file_path, parse_reloc.operands_instructions(parse_reloc.instructions_operands(adl_file_path)))
    instruction_operands_dict = info.instructions

    filtered_relocations_instructions = {
    reloc: [instruction for instruction in instructions if instruction in instruction_operands_dict]
    for reloc, instructions in relocations_instructions_dict.items()
    if any(instruction in instruction_operands_dict for instruction in instructions)
    }

    return filtered_relocations_instructions           


## Searches for the next character after instruction name inside the name of the test file
# @param input_string Name of the test file
# @param substring Instruction name
# @return @b char_after_substring-> Next character after instruction name
#
# Additional check in order to take only relocations tests into consideration
def get_char_after_substring(input_string, substring):
    index = input_string.find(substring)
    if index != -1 and index + len(substring) < len(input_string):
        char_after_substring = input_string[index + len(substring)]
        return char_after_substring
    else:
        return None


## Searches for a substring between two separators (_ and .) in order to identify the instruction name
# @param string Name of the test file
# @param substring Separator (instruction name)
# @return @b match.group(0)-> Substring between two separators
def search_with_separators(string, substring):
    # Define the regular expression pattern with lookbehind and lookahead
    pattern = rf'(?<=[._]){re.escape(substring)}(?=[._])'
    
    # Use re.search to find a match
    match = re.search(pattern, string)
    
    if match:
        return match.group(0)
    else:
        return None


## Function that creates the folder structure used to store relocations tests
def generate_file_structure():
    
    relocations_instructions_dict = filter_relocations_instructions_dict()

    # check if the "tests" folder exists
    if os.path.exists("tests"):
        shutil.rmtree("tests")

    # create the "tests" folder
    os.makedirs("tests")

    # create a folder for each relocation
    for i, (relocation, instructions) in enumerate(relocations_instructions_dict.items()):
        # create a folder for each instruction
        folder_name = os.path.join("tests", f"{relocation}")
        os.makedirs(folder_name)

        # create a file for each instruction
        for instruction in instructions:
            # check if the relocation applies only to a subset of instructions          
            file_name = os.path.join(folder_name, f"{relocation}_{instruction}.s")
            with open(file_name, "w") as f:
                f.close()
    return


# Function that extracts the highest even value for pair instructions
# @param my_dict Dictionary containing the instructions and their corresponding tuples
# @param key Key used to extract the tuples
# @return @b max_tuples[-1][1]-> The second element of the last tuple with the maximum value
def extract_highest_even_value_for_pair_instructions(my_dict, key):
    # Check if the key exists in the dictionary
    if key in my_dict:
        # Get the list of tuples associated with the key
        tuples = my_dict[key]
        
        # Convert string numbers to integers for comparison
        even_tuples = [(int(t[0]), t[1]) for t in tuples if int(t[0]) % 2 == 0]
        
        # Check if there are any even tuples
        if even_tuples:
            # Find the maximum value
            max_value = max(x[0] for x in even_tuples)
            # Filter for tuples that have the maximum value
            max_tuples = [t for t in even_tuples if t[0] == max_value]
            # Return the second element of the last tuple with the maximum value
            return max_tuples[-1][1]
    
    # Return None if the key doesn't exist or no even tuples found
    return None


## Function that generates symbols used in relocations tests
def generate_symbols():

    try:
        symbol_max_value = sys.argv[2]
    except:
        raise ValueError("Please provide symbol table max value as the 2nd argument")
    
    current_dir = os.getcwd()
    file_list = os.listdir(current_dir)
    
    for old_sym_file in file_list:
        if old_sym_file.startswith("sym") and old_sym_file.endswith(".inc"):
            os.remove(old_sym_file)

    file_name = os.path.join(current_dir, f"sym{symbol_max_value}.inc")

    with open(file_name, "w") as f:
        for i in range(0,2**(int(symbol_max_value) - 1)):
            f.write(f"\t .global var{i}\n")
        f.close()
    return


## Function that generates labels used in relocations tests based on each operand width and shift info
def generate_labels():

    try:
        adl_file_path = sys.argv[1]
    except:
        raise ValueError("Please provide adl file as the 1st argument")
    
    current_dir = os.getcwd()
    dir_paths = glob.glob(current_dir + '/tests/*/', recursive=True)

    relocation_instructions_dict = filter_relocations_instructions_dict()
    relocation_instrfield_dict = parse_reloc.relocations_instrfields(adl_file_path, relocation_instructions_dict)
    instrfield_width_dict = parse_reloc.instrfields_widths(adl_file_path, relocation_instrfield_dict)
    instrfield_shift_dict = parse_reloc.instrfields_shifts(adl_file_path, relocation_instrfield_dict)
    instrfield_signed_dict = parse_reloc.instrfields_signed(adl_file_path, relocation_instrfield_dict)
    final_width_dict = {key: int(instrfield_width_dict[key] + instrfield_shift_dict[key] + instrfield_signed_dict[key]) for key in instrfield_width_dict}

    for i, (dir_path) in enumerate(dir_paths):
        components = dir_path.split(os.path.sep)
        for relocation, operand in relocation_instrfield_dict.items():
            if relocation in components:
                file_name = f'labels_{final_width_dict[operand]}.asm'
                file_path = os.path.join(dir_path, file_name)
                with open(file_path, "w") as f:
                    f.write(".section text\n")
                    f.write(f".org {hex(0)}\n")
                    f.write(f"\tL{0}:\n")
                    for i in range(1, int(final_width_dict[operand]) - instrfield_shift_dict[operand]):
                        f.write(f".org {hex(2**(i + int(instrfield_shift_dict[operand]) - 1))}\n")
                        f.write(f"\tL{i}:\n")
                    f.write(f".org {hex(2**(int(final_width_dict[operand] - 1)) - int(2**instrfield_shift_dict[operand]))}\n")
                    f.write(f"\tL{i+1}:\n")
                    f.close()
    return


## Writes all information about a test at the beginning of the file
def write_header():

    try:
        adl_file_path = sys.argv[1]
    except:
        raise ValueError("Please provide adl file as the 1st argument")
    
    try:
        symbol_max_value = sys.argv[2]
    except:
        raise ValueError("Please provide symbol table max value as the 2nd argument")
    
    llvm_config_dict = parse.load_config()

    # Architecture and attributes
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

    adl_file_name, adl_file_ext = os.path.splitext(
        os.path.basename(adl_file_path))
    current_dir = os.getcwd()
    file_paths = glob.glob(current_dir + '/tests/**/*.s', recursive=True)

    relocation_instructions_dict = filter_relocations_instructions_dict()
    relocation_dependency_dict = parse_reloc.relocations_dependencies(adl_file_path, relocation_instructions_dict)
    
    for relocation, instructions in relocation_instructions_dict.items():
            for instruction in instructions:
                for file_path in file_paths:
                    components = file_path.split(os.path.sep)
                    if f"{relocation}_{instruction}.s" in components:     
                        with open(file_path, "w") as f:
                            now = datetime.now()
                            # write the data to the file
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
                            f.write(f'# @brief          {relocation} relocation testing\n') 
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
                            if relocation not in relocation_dependency_dict.keys():
                                f.write(f'\t.include "sym{symbol_max_value}.inc"\n')
                            file_list = os.listdir(os.path.dirname(file_path))
                            for labels_table in file_list:
                                if labels_table.startswith("labels") and labels_table.endswith(".asm") and relocation not in relocation_dependency_dict.keys():
                                    f.write(f'\t.include "{labels_table}"\n')
                                    break
                            f.write('\t.text\n')
                            f.write('\t.attribute	4, 16\n')
                            f.write(f'\t.attribute	5, "{baseArchitecture}i{extension_versions_dict["i"]}')
                            for extension in new_instruction_attribute_dict[instruction]:
                                if extension in extension_versions_dict.keys() and extension != "i":
                                    f.write(f'_{extension}{extension_versions_dict[extension]}')
                            f.write(f'"\n')
                            f.write(f'\t.globl {instruction}\n')
                            f.write('\t.p2align	1\n')
                            f.write(f'\t.type	{instruction},@function\n\n')
                            f.close()


## Writes all relocation tests cases for each instruction inside the assembly file
def generate_relocations():

    # Set all the needed variables
    try:
        adl_file_path = sys.argv[1]
    except:
        raise ValueError("Please provide adl file as the 1st argument")
    
    current_dir = os.getcwd()
    test_file_paths = glob.glob(current_dir + '/tests/**/*.s', recursive=True)
    label_file_paths = glob.glob(current_dir + '/tests/**/*.asm', recursive=True)
    sym_file_path = glob.glob(current_dir + '/*.inc', recursive=True)
    instruction_operands_dict = info.instructions
    operand_values_dict = info.operands
    instruction_register_pair_dict, instrfield_optionName_dict = parse.register_pairs(adl_file_path)
    instruction_syntaxName_dict = parse_reloc.instructions_syntaxNames(adl_file_path)
    relocation_instructions_dict = filter_relocations_instructions_dict()
    relocation_instrfield_dict = parse_reloc.relocations_instrfields(adl_file_path, relocation_instructions_dict)
    relocation_abbrev_dict = parse_reloc.relocations_abbrevs(adl_file_path, relocation_instructions_dict)
    relocation_suffix_dict = parse_reloc.relocations_suffixes(adl_file_path, relocation_instructions_dict)
    relocation_dependency_dict = parse_reloc.relocations_dependencies(adl_file_path, relocation_instructions_dict)
    instrfield_width_dict = parse_reloc.instrfields_widths(adl_file_path, relocation_instrfield_dict)
    instrfield_shift_dict = parse_reloc.instrfields_shifts(adl_file_path, relocation_instrfield_dict)
    instrfield_signed_dict = parse_reloc.instrfields_signed(adl_file_path, relocation_instrfield_dict)
    final_width_dict = {key: int(instrfield_width_dict[key] + instrfield_shift_dict[key] + instrfield_signed_dict[key]) for key in instrfield_width_dict}

    with open (sym_file_path[0], 'r') as f:
        sym_content = f.read()
        syms = re.findall(re.compile(r'\.global\s+(\w+)'), sym_content)

    # Collect all the info needed:
    for test_file in test_file_paths:
        for label_file in label_file_paths:
            labels = []
            with open (label_file, 'r') as f:
                label_content = f.read()
                labels = re.findall(r'\b(L\d+):', label_content)
                addends = re.findall(re.compile((r'\.org\s+(0x[0-9a-fA-F]+)')), label_content)
                f.close()
            for relocation, instructions in relocation_instructions_dict.items():
                for instruction in instructions:
                    char_after_substring = get_char_after_substring(test_file, instruction)
                    instruction_substring = search_with_separators(test_file, instruction)

                    # start instruction generation
                    if relocation in test_file and relocation in label_file and instruction == instruction_substring and char_after_substring == '.':
                        with open(test_file, 'a') as f:

                            # a list in which offsets are separated from immediates
                            operands_extended = instruction_operands_dict[instruction][:]

                            # check if immediate has offset
                            for i in range(len(operands_extended)):
                                offset = re.findall(r'\((.*?)\)', operands_extended[i])
                                if offset:
                                    operands_extended[i] = re.sub(
                                        r'\(.*?\)', '', operands_extended[i])
                                    operands_extended.insert(i + 1, offset[0])

                            # store offsets separately
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
                                        return '(' + str(extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0])) + ')'                                   
                                    else:
                                        return '(' + str(operand_values_dict[op][-1]) + ')'
                                # if operands doen't have offset but it's a value from info dict take its register value
                                elif op in operand_values_dict:
                                    if instruction in instruction_register_pair_dict:
                                        return str(extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0]))  
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
                                        return str(extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0]))
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
                                        return '(' + str(extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0])) + ')'
                                    else:
                                        return '(' + str(operand_values_dict[op][-1]) + ')'
                                # if operands doen't have offset but it's a value from info dict take its register value
                                elif op in operand_values_dict:
                                    if instruction in instruction_register_pair_dict:
                                        return str(extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0]))
                                    else:
                                        return operand_values_dict[op][-1]
                                # if operand is an immediate generate values based on label + addend
                                elif op in final_width_dict:
                                    if addend is not None:
                                        if abbrev:
                                            return '%' + abbrev + '(' + str(label) + ' + ' + str(addend) + ')'
                                        elif suffix:
                                            return '(' + str(label) + ' + ' + str(addend) + ')' + suffix
                                        else:
                                            return '(' + str(label) + ' + ' + str(addend) + ')'
                                    else:
                                        if abbrev:
                                            return '%' + abbrev + '(' + str(label) + ')'
                                        elif suffix:
                                            return str(label) + suffix
                                        else:
                                            return str(label)
                                else:
                                    return op
                                    
                            # A function that handles different types of operands (offsets, registers, immediates with or without abbreviations) for the Info case
                            def handle_operand_info(op, abbrev, suffix):
                                # if operand has offset and it's a value from info dict put its value between ()
                                if op in offsets and op in operand_values_dict:
                                    if instruction in instruction_register_pair_dict:
                                        return '(' + str(extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0])) + ')'
                                    else:
                                        return '(' + str(operand_values_dict[op][-1]) + ')'
                                # if operands doen't have offset but it's a value from info dict take its register value
                                elif op in operand_values_dict:
                                    if instruction in instruction_register_pair_dict:
                                        return str(extract_highest_even_value_for_pair_instructions(instrfield_optionName_dict, instruction_register_pair_dict[instruction][0]))
                                    else:
                                        return operand_values_dict[op][-1]
                                # if operand is an immediate generate values based on a global variable
                                elif op in final_width_dict:
                                    if abbrev:
                                        return '%' + abbrev + '(' + 'var' + str(2**i - 1) + ')'
                                    elif suffix:
                                        return 'var' + str(2**i - 1) + suffix
                                    else:
                                        return 'var' + str(2**i - 1)
                                else:
                                    return op
                                    
                            # Add dependencies for specific relocations 
                            if relocation in relocation_dependency_dict:
                                f.write("#Add relocation dependencies\n") 
                                for label in labels:
                                    relocation_dep_list = relocation_dependency_dict[relocation]
                                    f.write(f'{label}:\n')
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
                                            f.write(f"\t{instruction_syntaxName_dict[relocation_inst]} {','.join(op_values_dependency)}\n")
                                        else:
                                            f.write(f"\t{instruction_syntaxName_dict[relocation_inst]} {','.join(op_values_dependency[:-1])}{op_values_dependency[-1]}\n")
                                f.write("\n")

                            # Testing each bit for the Sym.Value
                            f.write("#Testing each bit for the Sym.Value field from the relocation section\n")
                            for label in labels:
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
                            for label, addend in zip(labels, addends):
                                op_values = []
                                abbrev = relocation_abbrev_dict[relocation] if relocation in relocation_abbrev_dict else None
                                suffix = relocation_suffix_dict[relocation] if relocation in relocation_suffix_dict else None

                                # Populate the list with the values of the operands
                                for op in operands_extended:
                                    op_values.append(handle_operand_addend(op, labels[0], abbrev, suffix, addend))
                                    
                                # Check if the operand has offset
                                if not offsets:
                                    f.write(f"\t{instruction_syntaxName_dict[instruction]} {','.join(op_values)}\n")
                                # if it does, concatenate last operand without comma
                                else:
                                    f.write(f"\t{instruction_syntaxName_dict[instruction]} {','.join(op_values[:-1])}{op_values[-1]}\n")
                                
                            # Testing each bit for the Info field (part1)
                            if relocation not in relocation_dependency_dict:
                                f.write("\n#Testing each bit for the Info field from the relocation section\n")
                                for i, label in enumerate(labels):
                                    label_numbers = list(range(0,len(labels)))
                                    op_values = []
                                    for op in operands_extended:
                                        if op in offsets and op not in operand_values_dict:
                                            op_values.append('(' + str(operand_values_dict[op][-1]) + ')')
                                        # if operand has offset and it's a value from dict put its value between ()
                                        elif op in offsets and op in operand_values_dict:
                                            op_values.append('(' + str(operand_values_dict[op][-1]) + ')')
                                        # if operand is a register take the value from the dict
                                        elif op in operand_values_dict:
                                            op_values.append(operand_values_dict[op][-1])
                                        # if operand is an immediate generate values based on label
                                        elif op in final_width_dict:
                                            # check if relocation has abbreviaton
                                            if relocation in relocation_abbrev_dict and relocation_abbrev_dict[relocation] is not None:
                                                    op_values.append('%' + relocation_abbrev_dict[relocation] + '(' 'L' + str(2**i - 1) + ')')
                                            elif relocation in relocation_suffix_dict and relocation_suffix_dict[relocation] is not None:
                                                    op_values.append('L' + str(2**i - 1) + relocation_suffix_dict[relocation])
                                            else:
                                                    op_values.append('L' + str(2**i - 1))
                                        else:
                                        # if operand not found in any dictionary use the operand name as its value
                                            op_values.append(op)
                                    # Check if the operand has offset
                                    if offsets == []:
                                        if (2**i - 1) in label_numbers:
                                            f.write(f"\t{instruction_syntaxName_dict[instruction]} {','.join(op_values)}\n")
                                    # if it does, concatenate last operand without comma
                                    else:
                                        if (2**i - 1) in label_numbers:
                                            f.write(f"\t{instruction_syntaxName_dict[instruction]} {','.join(op_values[:-1]) + '' + op_values[-1]}\n")

                            # Testing each bit for the Info field (part2)
                            if relocation not in relocation_dependency_dict:
                                for i, sym in enumerate(syms):
                                    if i > int(sys.argv[2]): break
                                    sym_numbers = list(range(0,len(syms)))
                                    op_values = []
                                    abbrev = relocation_abbrev_dict[relocation] if relocation in relocation_abbrev_dict else None
                                    suffix = relocation_suffix_dict[relocation] if relocation in relocation_suffix_dict else None 

                                    # Populate the list with the values of the operands
                                    for op in operands_extended:
                                        op_values.append(handle_operand_info(op, abbrev, suffix))

                                    # Check if the operand has offset
                                    if offsets == []:
                                        if (2**i - 1) in sym_numbers:
                                            f.write(f"\t{instruction_syntaxName_dict[instruction]} {','.join(op_values)}\n")
                                    # if it does, concatenate last operand without comma
                                    else:
                                        if (2**i - 1) in sym_numbers:
                                            f.write(f"\t{instruction_syntaxName_dict[instruction]} {','.join(op_values[:-1]) + '' + op_values[-1]}\n")
                        f.close()
    return