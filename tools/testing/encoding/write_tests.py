# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause

import os
from datetime import datetime
from tools.testing import utils
from tools.testing import parse


def _write_header(
    instruction: utils.Instruction,
    architecture: str,
    mattrib: str,
    args: utils.EncodingCommandLineArgs,
    output_file: str,
):
    """
    Write the header section for a test file including copyright, metadata, and LLVM directives.

    Args:
        instruction: The Instruction object
        architecture: Target architecture string
        mattrib: Available mattrib extensions string
        args: Command line arguments object
        output_file: Path to the output file

    Returns:
        None
    """
    now = datetime.now()
    with open(output_file, "w") as f:
        f.write(f"Data:\n")
        f.write(f"# Copyright (c) 2023-{now.strftime('%Y')}\n")
        f.write(f"# SPDX-License-Identifier: BSD-2-Clause\n")
        f.write(f"#\n")
        f.write(f"# @file {args.adl_file_path}\n")
        f.write(f"# @version 0.5\n")
        f.write(f"#\n")
        f.write(f"#-----------------\n")
        f.write(f"# Date D/M/Y\n")
        f.write(f"# {now.strftime('%d-%m-%Y')}\n")
        f.write(f"#-----------------\n")
        f.write(f"#\n")
        f.write(f"# @test_id        {os.path.basename(output_file)}\n")
        f.write(f"# @brief          Encode {instruction.syntax}  \n")
        f.write(
            f"# @details        Tests if each bit is encoded correctly for {instruction.name} instruction\n"
        )
        f.write(f"# @pre            Python 3.9+\n")
        f.write(f"# @test_level     Unit\n")
        f.write(f"# @test_type      Functional\n")
        f.write(f"# @test_technique Blackbox\n")
        f.write(
            f"# @pass_criteria  Run llvm_lit_tester.sh and then llvm-lit to see if all tests have passed!\n"
        )
        f.write(f"# @test_method    Analysis of requirements\n")
        f.write(
            f"# @requirements   {instruction.name} syntax and encoding from {os.path.basename(args.adl_file_path)}\n"
        )
        f.write(f"# @execution_type Automated\n")
        f.write(f"\n")
        f.write(
            f"// RUN: %asm -arch={architecture} -mattr={utils.get_mattr_string(instruction.attributes, mattrib)} %s -o %s.o -filetype=obj\n"
        )
        f.write(f"// RUN: %readelf -x 2 %s.o | %filecheck reference.txt\n\n")
        f.write(f"\t.text\n")
        f.write(f"\t.attribute	4, 16\n")
        f.write(f"\t.globl {instruction.name}\n")
        f.write(f"\t.p2align	1\n")
        f.write(f"\t.type	{instruction.name},@function\n")
        f.write(f"\n")


def write_tests() -> None:
    """
    Generate encoding test cases for all instructions.

    Creates comprehensive test files by generating all possible operand value combinations
    for each instruction, writing assembly test cases that exercise different encoding scenarios.
    """
    args = parse.parse_encoding_command_line_args()
    llvm_config = utils.load_llvm_config()
    cores = parse.get_cores_element(args.adl_file_path)
    architecture, attributes, mattrib = parse.asm_config_info(cores)

    instructions = utils.filter_instructions(
        parse.parse_instructions(cores), llvm_config, args.extensions
    )
    instrfields = parse.parse_instrfields(cores)

    instrfield_map = {field.name: field for field in instrfields}

    for instruction in instructions:
        output_folder = utils.prepare_encoding_tests_output_folder(
            args.output_dir, args.adl_file_name, args.extensions, instruction.name
        )
        output_file = os.path.join(output_folder, f"{instruction.name}.asm")

        # Write header
        _write_header(instruction, architecture, mattrib, args, output_file)

        # Write test cases
        syntax_operands = utils.get_instruction_operands(instruction.syntax)
        operand_values = {}
        for operand_name in syntax_operands:
            instrfield = instrfield_map.get(operand_name)
            if instrfield is None:
                continue  # or raise error
            if instrfield.type == "regfile" or (
                instrfield.type == "imm" and instrfield.enumerated
            ):
                operand_values[operand_name] = utils.get_regfile_values(
                    instrfield, instruction, operand_name
                )
            elif instrfield.type == "imm":
                width = instrfield.width
                shift = instrfield.shift or 0  # default if not specified
                sign_extension = instrfield.sign_extension
                signed = instrfield.signed
                operand_values[operand_name] = utils.get_imm_values(
                    width,
                    shift,
                    sign_extension,
                    signed,
                    instruction.excluded_values,
                    operand_name,
                )
        # Now, for each operand, sweep through its possible values
        with open(output_file, "a") as f:
            # Build a default operand value mapping: for each operand, use its last value if available,
            # or the operand string itself if it's a fixed literal from the syntax.
            defaults = {
                op: (operand_values[op][-1] if op in operand_values else op)
                for op in syntax_operands
            }
            f.write(f"{instruction.name}:\n")
            # Iterate over each operand to sweep its possible values while keeping others at default
            for target_operand in syntax_operands:
                # Get the instrfield for this operand to find bit information
                instrfield = instrfield_map.get(target_operand)
                if instrfield:
                    # Calculate the number of bits for this operand
                    total_bits = (
                        sum(
                            range_vals[0] - range_vals[1] + 1
                            for range_vals in instrfield.ranges
                        )
                        if instrfield.ranges
                        else (instrfield.width or 0)
                    )

                    # Get the list of values for this operand
                    values_list = operand_values.get(target_operand, [target_operand])

                    # Print the testing information
                    f.write(
                        f"#Testing operand {target_operand} encoded on {total_bits} bits with {len(values_list)} values: {values_list}\n"
                    )
                else:
                    f.write(
                        f"#Testing operand {target_operand} with value {target_operand}\n"
                    )
                # Get the list of possible values for this operand, or just the operand string if none defined
                for value in operand_values.get(target_operand, [target_operand]):
                    # Copy defaults and replace current operand with the test value
                    current = defaults.copy()
                    current[target_operand] = value

                    # Build operand string in original syntax order
                    mnemonic = instruction.syntax.split()[0]
                    operands_str = utils.substitute_operand_values(
                        instruction.syntax, current
                    )
                    f.write(f"\t{mnemonic} {operands_str}\n")
                f.write("\n")
            f.write(f".{instruction.name}_end:\n")
            f.write(
                f"\t.size\t {instruction.name}, .{instruction.name}_end-{instruction.name}\n"
            )
    return
