# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
from datetime import datetime
from tools.testing import parse
from tools.testing import utils


def write_refs():
    """
    Generate reference files containing expected encoded values for instruction tests.

    Reads the generated test files, calculates the expected binary encoding for each
    test case, and writes reference files that can be used to validate the assembler output.
    """
    args = parse.parse_encoding_command_line_args()
    llvm_config = utils.load_llvm_config()
    cores = parse.get_cores_element(args.adl_file_path)

    # Parse ALL instructions first (before filtering to avoid alias errors)
    all_instructions = parse.parse_instructions(cores)

    # Create instruction_map from ALL instructions (not just filtered ones)
    instruction_map = {
        instruction.name: instruction for instruction in all_instructions
    }

    # Then filter for the specific extensions
    instructions = utils.filter_instructions(
        all_instructions, llvm_config, args.extensions
    )

    instrfields = parse.parse_instrfields(cores)
    instrfield_map = {field.name: field for field in instrfields}

    for instruction in instructions:
        test_output_folder = utils.prepare_encoding_tests_output_folder(
            args.output_dir, args.adl_file_name, args.extensions, instruction.name
        )
        test_output_file = os.path.join(test_output_folder, f"{instruction.name}.asm")
        ref_output_folder = utils.prepare_encoding_refs_output_folder(
            args.output_dir, args.adl_file_name, args.extensions
        )
        ref_output_file = os.path.join(ref_output_folder, f"{instruction.name}.asm")

        # Pattern to match instruction lines
        instruction_line_pattern = r"^\t" + re.escape(instruction.name)

        try:
            with open(test_output_file, "r") as f:

                # Find all test lines
                all_lines = f.readlines()
                test_lines = [
                    line.strip()
                    for line in all_lines
                    if re.match(instruction_line_pattern, line)
                ]

                # List to store references for each instruction test file
                references_list = []

                # For each test line, match the operand's name with its value
                for current_test_line in test_lines:
                    current_line_instruction_parts = current_test_line.split()
                    if len(current_line_instruction_parts) > 1:
                        current_line_instruction = current_line_instruction_parts[0]
                        current_line_operands = current_line_instruction_parts[1]
                    else:
                        current_line_instruction = current_line_instruction_parts[0]
                        current_line_operands = None

                    syntax_operands = re.findall(
                        r"[\w]+", str(instruction.syntax.split()[1])
                    )
                    current_line_operands_values = re.findall(
                        r"[-\w]+", str(current_line_operands)
                    )
                    current_line_operand_value_dict = {
                        key: value
                        for key, value in zip(
                            syntax_operands, current_line_operands_values
                        )
                    }
                    reference = 0

                    # Check if instruction is alias
                    if instruction.aliases is None:
                        # Calculate reference for regular instruction
                        reference = utils.calculate_instruction_reference(
                            instruction.fields,
                            instrfield_map,
                            current_line_operand_value_dict,
                            is_alias=False,
                        )
                        references_list.append(reference)
                    else:
                        # Alias instruction
                        for alias in instruction.aliases:
                            # Build full field set: alias fields override base instruction fields
                            alias_fields = instruction_map[alias.name].fields.copy()
                            alias_fields.update(alias.fields)

                            reference = utils.calculate_instruction_reference(
                                alias_fields,
                                instrfield_map,
                                current_line_operand_value_dict,
                                is_alias=True,
                            )
                            references_list.append(reference)
                f.close()
        except IOError as e:
            print(f"Error reading file {test_output_file}: {e}")
            continue

        # Write the matched line to the corresponding file in the "references" directory
        with open(ref_output_file, "w") as f:
            now = datetime.now()
            f.write(f"# Copyright (c) {now.strftime('%Y')} NXP\n")
            f.write("# SPDX-License-Identifier: BSD-2-Clause\n\n")
            # Check instruction width
            if int(instruction.width) == 32:
                for ref in references_list:
                    f.write(f".word {hex(ref)}\n")
            if int(instruction.width) == 16:
                # Check bit endianness
                if parse.bit_endianness(cores) == "little":
                    for ref in references_list:
                        ref = str(hex(ref))
                        ref = ref[2:]
                        # Determine the length of the hex number
                        length = len(ref)
                        # Move the last two bytes to the front and add '0x' as necessary
                        formatted_ref = (
                            "0x"
                            + ref[length - 2 :]
                            + ",0x"
                            + (
                                "0" + ref[: length - 2]
                                if len(ref) > 2
                                else "0" + ref[: length - 2]
                            )
                        )
                        f.write(f".byte {formatted_ref}\n")
                elif parse.bit_endianness(cores) == "big":
                    for ref in references_list:
                        ref = str(hex(ref))
                        ref = ref[2:]
                        # Determine the length of the hex number
                        length = len(ref)
                        # Format by splitting with a comma and adding '0x' as necessary
                        formatted_ref = (
                            "0x"
                            + (
                                "0" + ref[: length - 2]
                                if len(ref) > 2
                                else "0" + ref[: length - 2]
                            )
                            + ",0x"
                            + ref[length - 2 :]
                        )
                        f.write(f".byte {formatted_ref}\n")
            f.close()
