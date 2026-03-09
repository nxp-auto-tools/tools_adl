# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import logging
import shutil
from datetime import datetime
from tools.testing import utils
from tools.testing import parse


def generate_reloc_references() -> None:
    """
    Generate reference files for relocation tests.

    Reads test files and generates corresponding reference files with expected
    relocation output patterns for FileCheck validation.
    """
    logger = logging.getLogger(__name__)

    # Get command line arguments
    args = parse.parse_relocation_command_line_args()
    cores = parse.get_cores_element(args.adl_file_path)

    # Parse ADL data
    llvm_config = utils.load_llvm_config()

    # Parse all instructions first (before filtering)
    all_instructions = parse.parse_instructions(cores)

    # Filter instructions based on extensions
    instructions = utils.filter_instructions(
        all_instructions, llvm_config, args.extensions
    )

    relocations = parse.parse_relocations(cores)
    instrfields = parse.parse_instrfields(cores)

    # Create mappings
    instruction_map = {instr.name: instr for instr in instructions}
    relocation_map = {reloc.name: reloc for reloc in relocations}

    # Get relocation-instruction mapping from filtered instructions
    relocations_instructions_map = utils.get_relocation_instruction_mapping(
        instructions, instrfields
    )

    # Also get mapping from all instructions for dependency relocations
    all_relocations_instructions_map = utils.get_relocation_instruction_mapping(
        all_instructions, instrfields
    )

    # Collect all dependency relocations
    dependency_relocations = set()
    for reloc_name in relocations_instructions_map.keys():
        if reloc_name in relocation_map:
            reloc = relocation_map[reloc_name]
            if reloc.dependency:
                dependency_relocations.update(reloc.dependency)

    # Add dependency relocations to the mapping
    for dep_reloc_name in dependency_relocations:
        if dep_reloc_name not in relocations_instructions_map:
            if dep_reloc_name in all_relocations_instructions_map:
                relocations_instructions_map[dep_reloc_name] = (
                    all_relocations_instructions_map[dep_reloc_name]
                )
                logger.debug(
                    f"Added dependency relocation to mapping: {dep_reloc_name}"
                )

    # Update instruction_map to include instructions from dependency relocations
    for dep_reloc_name in dependency_relocations:
        if dep_reloc_name in all_relocations_instructions_map:
            for instr_name in all_relocations_instructions_map[dep_reloc_name]:
                # Find the instruction in all_instructions
                for instr in all_instructions:
                    if instr.name == instr_name:
                        # Add under the alias name
                        if instr_name not in instruction_map:
                            instruction_map[instr_name] = instr
                            logger.debug(
                                f"Added instruction '{instr_name}' for dependency relocation '{dep_reloc_name}'"
                            )

                        # Also add under the syntax name (first word of syntax)
                        syntax_name = instr.syntax.split()[0]
                        if (
                            syntax_name != instr_name
                            and syntax_name not in instruction_map
                        ):
                            instruction_map[syntax_name] = instr
                            logger.debug(
                                f"Added syntax name '{syntax_name}' for instruction '{instr_name}'"
                            )
                        break

    # Prepare output directory
    refs_dir = utils.prepare_reloc_refs_output_folder(
        args.output_dir, args.adl_file_name, args.extensions
    )

    # Clean and recreate refs directory
    if os.path.exists(refs_dir):
        shutil.rmtree(refs_dir)
    os.makedirs(refs_dir, exist_ok=True)

    # Get tests directory
    if args.extensions is not None:
        tests_dir = os.path.join(
            args.output_dir,
            f"reloc_results_{args.adl_file_name}",
            f"tests_{'_'.join(args.extensions)}",
        )
    else:
        tests_dir = os.path.join(
            args.output_dir, f"reloc_results_{args.adl_file_name}", "tests_all"
        )

    # Process all test files
    for dirpath, dirnames, filenames in os.walk(tests_dir):
        for filename in filenames:
            if filename.endswith(".asm") or filename.endswith(".s"):
                test_file_path = os.path.join(dirpath, filename)
                ref_file_path = os.path.join(refs_dir, filename)

                # Extract relocation name from directory
                relocation_name = os.path.basename(dirpath)

                if relocation_name not in relocation_map:
                    continue

                relocation = relocation_map[relocation_name]

                # Check if this is a data relocation (has directive)
                if relocation.directive:
                    _generate_data_relocation_reference(
                        test_file_path, ref_file_path, relocation
                    )
                else:
                    # Generate instruction relocation reference
                    _generate_instruction_relocation_reference(
                        test_file_path,
                        ref_file_path,
                        relocation,
                        instruction_map,
                        relocations_instructions_map,
                        relocation_map,
                    )

                logger.debug(f"Generated reference: {ref_file_path}")


def _generate_instruction_relocation_reference(
    test_file_path: str,
    ref_file_path: str,
    relocation: utils.Relocation,
    instruction_map: dict,
    relocations_instructions_map: dict,
    relocation_map: dict,
) -> None:
    """
    Generate a reference file for instruction-based relocations.

    Args:
        test_file_path: Path to the test .asm file
        ref_file_path: Path to the output reference file
        relocation: The Relocation object for this test
        instruction_map: Mapping of instruction names to Instruction objects
        relocations_instructions_map: Mapping of relocations to instructions
        relocation_map: Mapping of relocation names to Relocation objects
    """
    # Read test file and extract instruction lines
    matching_lines = []
    with open(test_file_path, "r") as f:
        for line in f:
            stripped_line = line.lstrip()
            # Skip comments, directives, and labels
            if (
                stripped_line.startswith("#")
                or stripped_line.startswith("//")
                or stripped_line.startswith(".")
                or stripped_line.endswith(":")
                or not stripped_line
            ):
                continue

            # Check if line starts with tab (instruction line)
            if line.startswith("\t"):
                # Extract instruction name
                instr_name = stripped_line.split()[0]
                if instr_name in instruction_map:
                    matching_lines.append(line.strip())

    # Write reference file
    with open(ref_file_path, "w") as f:
        now = datetime.now()
        f.write(f"# Copyright (c) 2023-{now.strftime('%Y')}\n")
        f.write("# SPDX-License-Identifier: BSD-2-Clause\n\n")

        offset = 0
        for line in matching_lines:
            # Parse the instruction line
            tokens = re.split(r"[ ,()]+", line)
            instr_name = tokens[0]

            if instr_name not in instruction_map:
                continue

            instruction = instruction_map[instr_name]

            # Extract label or symbol from the line
            label_pattern = r"L\d+"
            var_pattern = r"var\d+"

            matching_label = next(
                (token for token in tokens if re.match(label_pattern, token)), None
            )
            matching_var = next(
                (token for token in tokens if re.match(var_pattern, token)), None
            )

            # Determine which relocation to use
            current_reloc = relocation
            actual_instruction = instruction

            # Check if this is a dependency instruction
            if relocation.dependency:
                # Check all dependencies to find which one this instruction belongs to
                for dep_reloc_name in relocation.dependency:
                    if dep_reloc_name in relocations_instructions_map:
                        # Direct name match
                        if instr_name in relocations_instructions_map[dep_reloc_name]:
                            current_reloc = relocation_map[dep_reloc_name]
                            break

                        # Check if instr_name is an alias of any instruction in this dependency
                        for dep_instr_name in relocations_instructions_map[
                            dep_reloc_name
                        ]:
                            if dep_instr_name in instruction_map:
                                dep_instruction = instruction_map[dep_instr_name]
                                # Check if dep_instruction has aliases
                                if dep_instruction.aliases:
                                    for alias in dep_instruction.aliases:
                                        # Check if the alias name matches the parsed instruction name
                                        if alias.name == instr_name:
                                            current_reloc = relocation_map[
                                                dep_reloc_name
                                            ]
                                            actual_instruction = dep_instruction
                                            break
                                if current_reloc != relocation:
                                    break
                        if current_reloc != relocation:
                            break

            # Generate CHECK line
            hex_offset = f"{offset:08x}"
            reloc_value_hex = f"{current_reloc.value:x}"

            # Determine symbol and addend
            if matching_label:
                symbol = matching_label
                # Check for addend (label + offset)
                if "+" in line:
                    # Extract addend value
                    addend_match = re.search(r"\+\s*(0x[0-9a-fA-F]+)", line)
                    if addend_match:
                        addend = addend_match.group(1)[2:]  # Remove '0x'
                    else:
                        addend = "0"
                else:
                    addend = "0"
            elif matching_var:
                symbol = matching_var
                addend = "0"
            else:
                # No relocation symbol found, skip
                offset += actual_instruction.width // 8
                continue

            f.write(
                f"// CHECK: {hex_offset} {{{{.*}}}}{reloc_value_hex} {current_reloc.name} {{{{.*}}}} {symbol} + {addend}\n"
            )
            offset += actual_instruction.width // 8


def _generate_data_relocation_reference(
    test_file_path: str, ref_file_path: str, relocation: utils.Relocation
) -> None:
    """
    Generate a reference file for data relocations (directives).

    Args:
        test_file_path: Path to the test .s file
        ref_file_path: Path to the output reference file
        relocation: The Relocation object for this test
    """
    # Read test file and extract directive lines
    matching_lines = []
    with open(test_file_path, "r") as f:
        for line in f:
            stripped_line = line.lstrip()
            # Check if line contains the directive
            if line.startswith("\t") and relocation.directive in stripped_line:
                matching_lines.append(line.strip())

    # Write reference file
    with open(ref_file_path, "w") as f:
        now = datetime.now()
        f.write(f"# Copyright (c) 2023-{now.strftime('%Y')}\n")
        f.write("# SPDX-License-Identifier: BSD-2-Clause\n\n")

        for line in matching_lines:
            # Parse the directive line
            tokens = re.split(r"[ ,]+", line)

            if relocation.directive == ".reloc":
                # Format: .reloc offset,relocation_name,symbol
                # tokens[0] = '.reloc'
                # tokens[1] = offset (hex)
                # tokens[2] = relocation name
                # tokens[3] = symbol

                if len(tokens) >= 4:
                    offset = tokens[1]
                    # Remove '0x' prefix if present
                    if offset.startswith("0x"):
                        offset = offset[2:]
                    # Ensure it's 8 characters with leading zeros
                    offset = f"{int(offset, 16):08x}"

                    symbol = tokens[3]
                    addend = "0"
                    reloc_value_hex = f"{relocation.value:x}"

                    f.write(
                        f"// CHECK: {offset} {{{{.*}}}}{reloc_value_hex} {relocation.name} {{{{.*}}}} {symbol} + {addend}\n"
                    )
            else:
                # TODO: Handle other directives
                pass
