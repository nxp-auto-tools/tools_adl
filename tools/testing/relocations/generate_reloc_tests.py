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

sys.path.append("./../")
module_info = "info"
try:
    info = importlib.import_module(module_info)
except ImportError:
    print("Please run make_test.py first to generate the info module.")


## Function that creates the folder structure used to store relocations tests
def generate_file_structure():
    adl_file_path = sys.argv[1]

    relocations_instructions_dict = parse_reloc.relocations_instructions(
        adl_file_path,
        parse_reloc.operands_instructions(
            parse_reloc.instructions_operands(adl_file_path)
        ),
    )

    # check if the "tests" folder exists
    if os.path.exists("tests"):
        shutil.rmtree("tests")

    # create the "tests" folder
    os.makedirs("tests")

    # create a folder for each relocation
    for i, (relocation, instructions) in enumerate(
        relocations_instructions_dict.items()
    ):
        # create a folder for each instruction
        folder_name = os.path.join("tests", f"{relocation}")
        os.makedirs(folder_name)

        # create a file for each instruction
        for instruction in instructions:
            file_name = os.path.join(folder_name, f"{relocation}_{instruction}.asm")
            with open(file_name, "w") as f:
                f.close()
    return


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
        for i in range(0, 2 ** (int(symbol_max_value) - 1)):
            f.write(f"\t .global var{i}\n")
        f.close()
    return


## Function that generates labels used in relocations tests based on each operand width and shift info
def generate_labels():
    adl_file_path = sys.argv[1]
    current_dir = os.getcwd()
    dir_paths = glob.glob(current_dir + "/tests/*/", recursive=True)

    (
        reloc_operand_dict,
        operand_width_dict,
        operand_shift_dict,
    ) = parse_reloc.operands_width(
        adl_file_path,
        parse_reloc.operands_instructions(
            parse_reloc.instructions_operands(adl_file_path)
        ),
    )

    for i, (dir_path) in enumerate(dir_paths):
        components = dir_path.split(os.path.sep)
        for relocation, operand in reloc_operand_dict.items():
            if relocation in components:
                file_name = f"labels_{operand_width_dict[operand]}.s"
                file_path = os.path.join(dir_path, file_name)
                with open(file_path, "w") as f:
                    f.write(".section text\n")
                    f.write(f".org {hex(0)}\n")
                    f.write(f"\tL{0}:\n")
                    for i in range(
                        1,
                        int(operand_width_dict[operand]) - operand_shift_dict[operand],
                    ):
                        f.write(
                            f".org {hex(2**(i + int(operand_shift_dict[operand]) - 1))}\n"
                        )
                        f.write(f"\tL{i}:\n")
                    f.write(
                        f".org {hex(2**(int(operand_width_dict[operand] - 1)) - int(2**operand_shift_dict[operand]))}\n"
                    )
                    f.write(f"\tL{i+1}:\n")
                    f.close()
    return


## Writes all information about a test at the beginning of the file
def write_header():
    adl_file_path = sys.argv[1]
    symbol_max_value = sys.argv[2]
    adl_file_name, adl_file_ext = os.path.splitext(os.path.basename(adl_file_path))
    current_dir = os.getcwd()
    file_paths = glob.glob(current_dir + "/tests/**/*.asm", recursive=True)

    relocations_instructions_dict = parse_reloc.relocations_instructions(
        adl_file_path,
        parse_reloc.operands_instructions(
            parse_reloc.instructions_operands(adl_file_path)
        ),
    )

    for relocation, instructions in relocations_instructions_dict.items():
        for instruction in instructions:
            for file_path in file_paths:
                components = file_path.split(os.path.sep)
                if f"{relocation}_{instruction}.asm" in components:
                    with open(file_path, "w") as f:
                        now = datetime.now()
                        # write the data to the file
                        f.write("Data:\n")
                        f.write(f"#   Copyright (c) {now.strftime('%Y')} NXP\n")
                        f.write("#   SPDX-License-Identifier: BSD-2-Clause\n")
                        f.write(f"#   @file    {relocation}_{instruction}.asm\n")
                        f.write("#   @version 1.0\n")
                        f.write("#\n")
                        f.write("#-----------------\n")
                        f.write("# Date D/M/Y\n")
                        f.write(f"# {now.strftime('%d-%m-%Y')}\n")
                        f.write("#-----------------\n")
                        f.write("#\n")
                        f.write(f"# @test_id        {relocation}_{instruction}.asm\n")
                        f.write(f"# @brief          {relocation} relocation testing\n")
                        f.write(
                            "# @details        Tests if the relocation for the source address is generated correctly\n"
                        )
                        f.write("# @pre            Python 3.9+\n")
                        f.write("# @test_level     Unit\n")
                        f.write("# @test_type      Functional\n")
                        f.write("# @test_technique Blackbox\n")
                        f.write(
                            f"# @pass_criteria  Relocation {relocation} generated\n"
                        )
                        f.write("# @test_method    Analysis of requirements\n")
                        f.write(
                            '# @requirements   "%s" syntax and encoding from %s'
                            % (instruction, adl_file_name)
                            + "\n"
                        )
                        f.write("# @execution_type Automated\n")
                        f.write("\n")
                        f.write(f'\t# .include "sym{symbol_max_value}.inc"\n')
                        file_list = os.listdir(os.path.dirname(file_path))
                        for labels_table in file_list:
                            if labels_table.startswith(
                                "labels"
                            ) and labels_table.endswith(".s"):
                                f.write(f'\t.include "{labels_table}"\n')
                                break
                        f.write("\t.text\n\n")
                        f.close()


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


## Writes all relocation tests cases for each instruction inside the assembly file
def generate_relocations():
    adl_file_path = sys.argv[1]
    current_dir = os.getcwd()
    test_file_paths = glob.glob(current_dir + "/tests/**/*.asm", recursive=True)
    label_file_paths = glob.glob(current_dir + "/tests/**/*.s", recursive=True)
    sym_file_path = glob.glob(current_dir + "/*.inc", recursive=True)

    instruction_operands_dict = info.instructions
    operand_values_dict = info.operands
    relocation_instructions_dict = parse_reloc.relocations_instructions(
        adl_file_path,
        parse_reloc.operands_instructions(
            parse_reloc.instructions_operands(adl_file_path)
        ),
    )
    relocation_abbrev_dict = parse_reloc.relocations_abbrev(
        adl_file_path, relocation_instructions_dict
    )
    reloc_op_dict, imm_width_dict, imm_shift_dict = parse_reloc.operands_width(
        adl_file_path,
        parse_reloc.operands_instructions(
            parse_reloc.instructions_operands(adl_file_path)
        ),
    )

    with open(sym_file_path[0], "r") as f:
        sym_content = f.read()
        syms = re.findall(re.compile(r"\.global\s+(\w+)"), sym_content)

    # collect all the info needed:
    for test_file in test_file_paths:
        for label_file in label_file_paths:
            labels = []
            with open(label_file, "r") as f:
                label_content = f.read()
                labels = re.findall(r"\b(L\d+):", label_content)
                addends = re.findall(
                    re.compile((r"\.org\s+(0x[0-9a-fA-F]+)")), label_content
                )
                f.close()
            for relocation, instructions in relocation_instructions_dict.items():
                for instruction in instructions:
                    char_after_substring = get_char_after_substring(
                        test_file, instruction
                    )
                    # start instruction generation
                    if (
                        relocation in test_file
                        and relocation in label_file
                        and instruction in test_file
                        and char_after_substring == "."
                    ):
                        with open(test_file, "a") as f:
                            # a list in which offsets are separated from immediates
                            operands_extended = instruction_operands_dict[instruction][
                                :
                            ]

                            # check if immediate has offset
                            for i in range(len(operands_extended)):
                                offset = re.findall(r"\((.*?)\)", operands_extended[i])
                                if offset:
                                    operands_extended[i] = re.sub(
                                        r"\(.*?\)", "", operands_extended[i]
                                    )
                                    operands_extended.insert(i + 1, offset[0])

                            # store offsets separately
                            offsets = []
                            for op in instruction_operands_dict[instruction]:
                                offset = re.search(r"\((.*?)\)", op)
                                if offset:
                                    offsets.append(offset.group(1))

                            # clear operands from dict of parentheses
                            for key in operand_values_dict.keys():
                                operand_values_dict[key] = [
                                    element.strip("()")
                                    for element in operand_values_dict[key]
                                ]

                            # Testing each bit for the Sym.Value
                            f.write(
                                "#Testing each bit for the Sym.Value field from the relocation section\n"
                            )
                            for label in labels:
                                op_values = []
                                for op in operands_extended:
                                    if op in offsets and op not in operand_values_dict:
                                        op_values.append(
                                            "(" + str(operand_values_dict[op][-1]) + ")"
                                        )
                                    # if operand has offset and it's a value from dict put its value between ()
                                    elif op in offsets and op in operand_values_dict:
                                        op_values.append(
                                            "(" + str(operand_values_dict[op][-1]) + ")"
                                        )
                                    # if operand is a register take the value from the dict
                                    elif op in operand_values_dict:
                                        op_values.append(operand_values_dict[op][-1])
                                    # if operand is an immediate generate values based on label
                                    elif op in imm_width_dict:
                                        # check if relocation has abbreviaton
                                        if (
                                            relocation_abbrev_dict[relocation]
                                            is not None
                                        ):
                                            op_values.append(
                                                "%"
                                                + relocation_abbrev_dict[relocation]
                                                + "("
                                                + str(label)
                                                + ")"
                                            )
                                        else:
                                            op_values.append(label)
                                    else:
                                        # if operand not found in any dictionary use the operand name as its value
                                        op_values = [op]
                                # check if the instruction has offset
                                if offsets == []:
                                    f.write(f"\t{instruction} {','.join(op_values)}\n")
                                # if it does, concatenate last operand without comma
                                else:
                                    f.write(
                                        f"\t{instruction} {','.join(op_values[:-1]) + '' + op_values[-1]}\n"
                                    )

                            # Testing each bit for the Addend field
                            f.write(
                                "\n#Testing each bit for the Addend field from the relocation section\n"
                            )
                            for label, addend in zip(labels, addends):
                                op_values = []
                                for op in operands_extended:
                                    if op in offsets and op not in operand_values_dict:
                                        op_values.append(
                                            "(" + str(operand_values_dict[op][-1]) + ")"
                                        )
                                    # if operand has offset and it's a value from dict put its value between ()
                                    elif op in offsets and op in operand_values_dict:
                                        op_values.append(
                                            "(" + str(operand_values_dict[op][-1]) + ")"
                                        )
                                    # if operand is a register take the value from the dict
                                    elif op in operand_values_dict:
                                        op_values.append(operand_values_dict[op][-1])
                                    # if operand is an immediate generate values based on label
                                    elif op in imm_width_dict:
                                        # check if relocation has abbreviaton
                                        if (
                                            relocation_abbrev_dict[relocation]
                                            is not None
                                        ):
                                            op_values.append(
                                                "%"
                                                + relocation_abbrev_dict[relocation]
                                                + "("
                                                + str(labels[0])
                                                + " + "
                                                + str(addend)
                                                + ")"
                                            )
                                        else:
                                            op_values.append(
                                                "("
                                                + str(labels[0])
                                                + " + "
                                                + str(addend)
                                                + ")"
                                            )
                                    else:
                                        # if operand not found in any dictionary use the operand name as its value
                                        op_values = [op]
                                # check if the instruction has offset
                                if offsets == []:
                                    f.write(f"\t{instruction} {','.join(op_values)}\n")
                                # if it does, concatenate last operand without comma
                                else:
                                    f.write(
                                        f"\t{instruction} {','.join(op_values[:-1]) + '' + op_values[-1]}\n"
                                    )

                            # Testing each bit for the Info field (part1)
                            f.write(
                                "\n#Testing each bit for the Info field from the relocation section\n"
                            )
                            last_labels = []
                            for i, label in enumerate(labels):
                                label_numbers = list(range(0, len(labels)))
                                op_values = []
                                for op in operands_extended:
                                    if op in offsets and op not in operand_values_dict:
                                        op_values.append(
                                            "(" + str(operand_values_dict[op][-1]) + ")"
                                        )
                                    # if operand has offset and it's a value from dict put its value between ()
                                    elif op in offsets and op in operand_values_dict:
                                        op_values.append(
                                            "(" + str(operand_values_dict[op][-1]) + ")"
                                        )
                                    # if operand is a register take the value from the dict
                                    elif op in operand_values_dict:
                                        op_values.append(operand_values_dict[op][-1])
                                    # if operand is an immediate generate values based on label
                                    elif op in imm_width_dict:
                                        # check if relocation has abbreviaton
                                        if (
                                            relocation_abbrev_dict[relocation]
                                            is not None
                                        ):
                                            op_values.append(
                                                "%"
                                                + relocation_abbrev_dict[relocation]
                                                + "("
                                                "L" + str(2**i - 1) + ")"
                                            )
                                        else:
                                            op_values.append("L" + str(2**i - 1))
                                    else:
                                        # if operand not found in any dictionary use the operand name as its value
                                        op_values = [op]
                                if offsets == []:
                                    if (2**i - 1) in label_numbers:
                                        f.write(
                                            f"\t{instruction} {','.join(op_values)}\n"
                                        )
                                # if it does, concatenate last operand without comma
                                else:
                                    if (2**i - 1) in label_numbers:
                                        f.write(
                                            f"\t{instruction} {','.join(op_values[:-1]) + '' + op_values[-1]}\n"
                                        )

                            # Testing each bit for the Info field (part2)
                            for i, sym in enumerate(syms):
                                if i > int(sys.argv[2]):
                                    break
                                sym_numbers = list(range(0, len(syms)))
                                op_values = []
                                for op in operands_extended:
                                    if op in offsets and op not in operand_values_dict:
                                        op_values.append(
                                            "(" + str(operand_values_dict[op][-1]) + ")"
                                        )
                                    # if operand has offset and it's a value from dict put its value between ()
                                    elif op in offsets and op in operand_values_dict:
                                        op_values.append(
                                            "(" + str(operand_values_dict[op][-1]) + ")"
                                        )
                                    # if operand is a register take the value from the dict
                                    elif op in operand_values_dict:
                                        op_values.append(operand_values_dict[op][-1])
                                    # if operand is an immediate generate values based on label
                                    elif op in imm_width_dict:
                                        # check if relocation has abbreviaton
                                        if (
                                            relocation_abbrev_dict[relocation]
                                            is not None
                                        ):
                                            op_values.append(
                                                "%"
                                                + relocation_abbrev_dict[relocation]
                                                + "("
                                                "var" + str(2**i - 1) + ")"
                                            )
                                        else:
                                            op_values.append("var" + str(2**i - 1))
                                    else:
                                        # if operand not found in any dictionary use the operand name as its value
                                        op_values = [op]
                                if offsets == []:
                                    if (2**i - 1) in sym_numbers:
                                        f.write(
                                            f"\t{instruction} {','.join(op_values)}\n"
                                        )
                                # if it does, concatenate last operand without comma
                                else:
                                    if (2**i - 1) in sym_numbers:
                                        f.write(
                                            f"\t{instruction} {','.join(op_values[:-1]) + '' + op_values[-1]}\n"
                                        )
    return
