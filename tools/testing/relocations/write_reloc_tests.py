# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import logging
from datetime import datetime
from tools.testing import utils
from tools.testing import parse
from typing import List, Dict, Tuple, Optional


def _write_header(
    relocation: utils.Relocation,
    instruction_name: str,
    architecture: str,
    mattrib: str,
    args: utils.RelocationCommandLineArgs,
    output_file: str,
    instrfield_map: Optional[Dict[str, utils.InstrField]] = None,
):
    """
    Write the header section for a relocation test file including copyright, metadata, and LLVM directives.

    Args:
        relocation: The Relocation object
        instruction_name: The instruction name that uses this relocation (or directive name for data relocations)
        architecture: Target architecture string
        mattrib: Available mattrib extensions string
        args: Command line arguments object
        output_file: Path to the output file
        instrfield_map: Optional mapping of field names to InstrField objects (needed for instruction relocations)

    Returns:
        None
    """
    import logging

    logger = logging.getLogger(__name__)

    now = datetime.now()

    # Determine if this is a data relocation (directive starts with '.')
    is_data_relocation = instruction_name.startswith(".")

    logger.debug(f"Writing header for {relocation.name} - {instruction_name}")
    logger.debug(f"Is data relocation: {is_data_relocation}")
    logger.debug(f"Has dependency: {relocation.dependency}")
    logger.debug(f"Instrfield_map provided: {instrfield_map is not None}")

    # Calculate label file name for instruction relocations
    label_file_name = None
    if not is_data_relocation and instrfield_map:
        # Find the instrfield associated with this relocation
        for field_name, field in instrfield_map.items():
            if relocation.name in field.reloc:
                width = field.width or 0
                shift = field.shift or 0
                final_width = width + shift
                label_file_name = f"labels_{final_width}.inc"
                logger.debug(
                    f"Found instrfield {field_name} for relocation {relocation.name}"
                )
                logger.debug(f"Label file name: {label_file_name}")
                break

        if label_file_name is None:
            logger.warning(f"No instrfield found for relocation {relocation.name}")

    # Determine the reference file path based on extensions
    if args.extensions is not None:
        extension_str = "_".join(args.extensions)
        include_path = os.path.abspath(
            os.path.join(
                args.output_dir,
                f"reloc_results_{args.adl_file_name}",
                f"tests_{extension_str}",
                relocation.name,
            )
        )
        ref_path = os.path.abspath(
            os.path.join(
                args.output_dir,
                f"reloc_results_{args.adl_file_name}",
                f"refs_{extension_str}",
                os.path.basename(output_file),
            )
        )
    else:
        include_path = os.path.abspath(
            os.path.join(
                args.output_dir,
                f"reloc_results_{args.adl_file_name}",
                "tests_all",
                relocation.name,
            )
        )
        ref_path = os.path.abspath(
            os.path.join(
                args.output_dir,
                f"reloc_results_{args.adl_file_name}",
                "refs_all",
                os.path.basename(output_file),
            )
        )

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
        f.write(f"# @brief          Test relocation {relocation.name}\n")
        f.write(
            f"# @details        Tests if the relocation for the source address is generated correctly\n"
        )
        f.write(f"# @pre            Python 3.9+\n")
        f.write(f"# @test_level     Unit\n")
        f.write(f"# @test_type      Functional\n")
        f.write(f"# @test_technique Blackbox\n")
        f.write(f"# @pass_criteria  Run llvm-lit to see if all tests have passed!\n")
        f.write(f"# @test_method    Analysis of requirements\n")
        f.write(
            f"# @requirements   {relocation.name} relocation from {os.path.basename(args.adl_file_path)}\n"
        )
        f.write(f"# @execution_type Automated\n")
        f.write(f"\n")
        f.write(
            f'// RUN: %asm -I/{include_path} -arch={architecture} -mattr="{mattrib}" %s -o %s.o -filetype=obj\n'
        )
        f.write(f"// RUN: %readelf -r %s.o | %filecheck {ref_path}\n\n")

        # Include symbol and label files based on relocation type
        logger.debug(
            f"About to write includes - is_data: {is_data_relocation}, has_dep: {bool(relocation.dependency)}, label_file: {label_file_name}"
        )

        if is_data_relocation:
            # Data relocations only need symbol file
            logger.debug(f"Writing symbol include for data relocation")
            f.write(f'\t.include "sym{args.symbol_max_value}.inc"\n')
        else:
            # Instruction relocations need both symbol and label files (unless they have dependencies)
            if not relocation.dependency:
                logger.debug(
                    f"Writing symbol and label includes for instruction relocation without dependencies"
                )
                f.write(f'\t.include "sym{args.symbol_max_value}.inc"\n')
                if label_file_name:
                    f.write(f'\t.include "{label_file_name}"\n')
                else:
                    logger.warning(f"Label file name is None for {relocation.name}")
            else:
                logger.debug(
                    f"Skipping includes for instruction relocation with dependencies"
                )

        f.write(f"\t.text\n")
        f.write(f"\t.attribute	4, 16\n")
        f.write(f"\t.globl {instruction_name}\n")
        f.write(f"\t.p2align	1\n")
        f.write(f"\t.type	{instruction_name},@function\n")
        f.write(f"\n")
        f.close()


def generate_symbols() -> None:
    """
    Generate symbol files used in relocation tests.
    Creates .inc files containing global symbol declarations for use in relocation testing.
    Removes old symbol files and creates new ones based on the symbol_max_value parameter.
    """
    logger = logging.getLogger(__name__)

    # Get the command line arguments using the new parser
    args = parse.parse_relocation_command_line_args()

    # Determine the base test directory path
    if args.extensions is not None:
        base_test_dir = os.path.join(
            args.output_dir,
            f"reloc_results_{args.adl_file_name}",
            f"tests_{'_'.join(args.extensions)}",
        )
    else:
        base_test_dir = os.path.join(
            args.output_dir, f"reloc_results_{args.adl_file_name}", "tests_all"
        )

    # Check if the base test directory exists
    if not os.path.exists(base_test_dir):
        logger.warning(f"Test directory does not exist: {base_test_dir}")
        return

    # Pre-generate symbol content once
    symbol_content = "".join(
        f"\t.global var{i}\n" for i in range(0, 2 ** (args.symbol_max_value - 1))
    )
    symbol_file_name = f"sym{args.symbol_max_value}.inc"

    def clean_old_symbols(directory: str) -> None:
        """Remove old symbol files from a directory."""
        if not os.path.exists(directory):
            return
        for item in os.listdir(directory):
            if item.startswith("sym") and item.endswith(".inc"):
                old_file_path = os.path.join(directory, item)
                os.remove(old_file_path)
                logger.debug(f"Removed old symbol file: {old_file_path}")

    def write_symbol_file(file_path: str) -> None:
        """Write symbol content to a file."""
        with open(file_path, "w") as f:
            f.write(symbol_content)

    # # Clean and create symbol file in base directory
    # clean_old_symbols(base_test_dir)
    # main_symbol_file = os.path.join(base_test_dir, symbol_file_name)
    # write_symbol_file(main_symbol_file)
    # logger.info(f"Created main symbol file: {main_symbol_file}")

    # Get all relocation directories and create symbol files
    relocation_dirs = [
        os.path.join(base_test_dir, d)
        for d in os.listdir(base_test_dir)
        if os.path.isdir(os.path.join(base_test_dir, d))
    ]

    for reloc_dir in relocation_dirs:
        clean_old_symbols(reloc_dir)
        reloc_symbol_file = os.path.join(reloc_dir, symbol_file_name)
        write_symbol_file(reloc_symbol_file)
        logger.debug(f"Created symbol file in: {reloc_symbol_file}")


def generate_labels() -> None:
    """
    Generate label files used in relocation tests based on operand width and shift info.
    Creates .asm files containing labels at specific addresses for relocation testing.
    """
    logger = logging.getLogger(__name__)

    # Get the command line arguments using the new parser
    args = parse.parse_relocation_command_line_args()
    cores = parse.get_cores_element(args.adl_file_path)

    # Parse required data
    instructions = utils.filter_instructions(
        parse.parse_instructions(cores), utils.load_llvm_config(), args.extensions
    )
    instrfields = parse.parse_instrfields(cores)

    # Create instrfield mapping for quick lookup
    instrfield_map = {field.name: field for field in instrfields}

    # Create relocation to instrfield mapping
    relocation_instrfield_dict = {}
    for instruction in instructions:
        if instruction.fields:
            # Regular instructions
            for field_name in instruction.fields.keys():
                if field_name in instrfield_map and instrfield_map[field_name].reloc:
                    for reloc_name in instrfield_map[field_name].reloc:
                        relocation_instrfield_dict[reloc_name] = field_name
        elif instruction.aliases:
            # Alias instructions - check syntax operands
            syntax_operands = utils.get_instruction_operands(instruction.syntax)
            for operand in syntax_operands:
                if operand in instrfield_map and instrfield_map[operand].reloc:
                    for reloc_name in instrfield_map[operand].reloc:
                        relocation_instrfield_dict[reloc_name] = operand

    # Calculate final widths for each instrfield (without signed addition)
    final_width_dict = {}
    for reloc_name, field_name in relocation_instrfield_dict.items():
        if field_name in instrfield_map:
            field = instrfield_map[field_name]
            width = field.width or 0
            shift = field.shift or 0
            final_width_dict[field_name] = width + shift  # Removed signed addition

    # Determine the base test directory path
    if args.extensions is not None:
        base_test_dir = os.path.join(
            args.output_dir,
            f"reloc_results_{args.adl_file_name}",
            f"tests_{'_'.join(args.extensions)}",
        )
    else:
        base_test_dir = os.path.join(
            args.output_dir, f"reloc_results_{args.adl_file_name}", "tests_all"
        )

    # Check if the base test directory exists
    if not os.path.exists(base_test_dir):
        logger.warning(f"Test directory does not exist: {base_test_dir}")
        return

    # Get all relocation directories
    relocation_dirs = [
        os.path.join(base_test_dir, d)
        for d in os.listdir(base_test_dir)
        if os.path.isdir(os.path.join(base_test_dir, d))
    ]

    for reloc_dir in relocation_dirs:
        dir_name = os.path.basename(reloc_dir)

        # Find the corresponding instrfield for this relocation
        if dir_name in relocation_instrfield_dict:
            field_name = relocation_instrfield_dict[dir_name]

            if field_name in final_width_dict and field_name in instrfield_map:
                field = instrfield_map[field_name]
                final_width = final_width_dict[field_name]
                shift = field.shift or 0

                # Generate label file
                file_name = f"labels_{final_width}.inc"
                file_path = os.path.join(reloc_dir, file_name)

                with open(file_path, "w") as f:
                    f.write(".section text\n")
                    f.write(f".org {hex(0)}\n")
                    f.write(f"\tL0:\n")

                    # Generate intermediate labels
                    for i in range(1, final_width - shift):
                        org_value = 2 ** (i + shift - 1)
                        f.write(f".org {hex(org_value)}\n")
                        f.write(f"\tL{i}:\n")

                    # Generate final label
                    final_org = 2 ** (final_width - 1) - 2**shift
                    f.write(f".org {hex(final_org)}\n")
                    f.write(f"\tL{i+1}:\n")

                logger.debug(f"Created label file: {file_path}")
            else:
                logger.warning(f"No width/shift info found for relocation {dir_name}")
        else:
            logger.debug(
                f"No instrfield mapping found for relocation directory: {dir_name}"
            )


def write_header() -> None:
    """
    Generate and write header sections for all relocation test files.

    Creates the initial header content including copyright, metadata, and LLVM directives
    for each relocation's test file. Handles both instruction-based relocations and
    data relocations (those with directives).
    """
    logger = logging.getLogger(__name__)

    args = parse.parse_relocation_command_line_args()
    llvm_config = utils.load_llvm_config()
    cores = parse.get_cores_element(args.adl_file_path)
    architecture, attributes, mattrib = parse.asm_config_info(cores)

    # Parse all instructions first (before filtering)
    all_instructions = parse.parse_instructions(cores)

    # Filter instructions based on extensions
    instructions = utils.filter_instructions(
        all_instructions, llvm_config, args.extensions
    )

    instrfields = parse.parse_instrfields(cores)
    relocations = parse.parse_relocations(cores)

    # Get relocation-instruction mapping using filtered instructions
    relocations_instructions_map = utils.get_relocation_instruction_mapping(
        instructions, instrfields
    )
    instrfield_map = {field.name: field for field in instrfields}

    # Filter relocations to only include those used by filtered instructions
    # Data relocations are only included if no extension flag is given
    filtered_relocations = []
    for relocation in relocations:
        # Include if it has associated instructions in the filtered set
        if relocation.name in relocations_instructions_map:
            filtered_relocations.append(relocation)
        # Or if it has a directive (data relocation) AND no extensions specified
        elif relocation.directive and args.extensions is None:
            filtered_relocations.append(relocation)

    for relocation in filtered_relocations:
        # Create output folder for this relocation
        relocation_folder = utils.prepare_reloc_tests_output_folder(
            args.output_dir, args.adl_file_name, args.extensions, relocation.name
        )

        # Check if this relocation has associated instructions
        if relocation.name in relocations_instructions_map:
            associated_instructions = relocations_instructions_map[relocation.name]

            # Create a test file for each instruction that uses this relocation
            for instruction_name in associated_instructions:
                test_file_name = f"{relocation.name}_{instruction_name}.asm"
                test_file_path = os.path.join(relocation_folder, test_file_name)

                logger.debug(
                    f"Writing header for {relocation.name} with instruction {instruction_name}"
                )
                logger.debug(f"Instrfield_map keys: {list(instrfield_map.keys())}")
                logger.debug(f"Relocation dependency: {relocation.dependency}")

                # Write the header for this relocation-instruction combination
                _write_header(
                    relocation,
                    instruction_name,
                    architecture,
                    mattrib,
                    args,
                    test_file_path,
                    instrfield_map,
                )
                logger.debug(f"Created instruction relocation header: {test_file_path}")

        # Check if this relocation has directives (data relocations)
        # Only process if no extensions specified
        if relocation.directive and args.extensions is None:
            test_file_name = f"{relocation.name}_{relocation.directive}.asm"
            test_file_path = os.path.join(relocation_folder, test_file_name)

            # Write the header for this data relocation
            # Use the directive as the "instruction_name" parameter
            _write_header(
                relocation,
                relocation.directive,
                architecture,
                mattrib,
                args,
                test_file_path,
                instrfield_map,
            )
            logger.debug(f"Created data relocation header: {test_file_path}")


def generate_data_relocations() -> None:
    """
    Generate relocation tests for data relocations.

    Appends test cases to existing header files for each relocation directive combination,
    including test cases using various symbol offsets.

    Note: This function assumes write_header() has already been called to create
    the initial header content for data relocation files.
    """
    logger = logging.getLogger(__name__)

    # Get the command line arguments using the new parser
    args = parse.parse_relocation_command_line_args()

    # Parse relocations from ADL file
    cores = parse.get_cores_element(args.adl_file_path)
    relocations = parse.parse_relocations(cores)

    # Process each relocation that has a directive
    for relocation in relocations:
        if not relocation.directive:
            continue

        # Get the relocation folder
        relocation_folder = utils.prepare_reloc_tests_output_folder(
            args.output_dir, args.adl_file_name, args.extensions, relocation.name
        )

        # Construct the file path
        file_name = f"{relocation.name}_{relocation.directive}.asm"
        file_path = os.path.join(relocation_folder, file_name)

        # Check if header file exists
        if not os.path.exists(file_path):
            logger.warning(
                f"Header file not found: {file_path}. Skipping data relocation generation."
            )
            continue

        # Append test cases to the existing header file
        with open(file_path, "a") as f:
            f.write("#Testing data relocation directives\n")

            # Generate test cases
            offset = 0x0
            for i in range(0, args.symbol_max_value):
                if relocation.directive == ".reloc":
                    symbol_index = int((2**i) - 1)
                    f.write(
                        f"\t{relocation.directive} {hex(offset)},{relocation.name},var{symbol_index}\n"
                    )
                    offset += 0x4
                else:
                    # TODO: add other directives
                    logger.warning(
                        f"Directive {relocation.directive} not yet implemented for {relocation.name}"
                    )
                    break


def generate_relocations() -> None:
    """
    Generate relocation test cases for instruction-based relocations.

    Creates test cases for each instruction that uses relocations, testing:
    - Sym.Value field (using labels)
    - Addend field (using label offsets)
    - Info field (using both labels and global symbols)

    Note: This function assumes write_header() and generate_labels() have already been called.
    """
    logger = logging.getLogger(__name__)

    # Get the command line arguments
    args = parse.parse_relocation_command_line_args()
    cores = parse.get_cores_element(args.adl_file_path)

    # Load LLVM configuration and parse ADL data
    llvm_config = utils.load_llvm_config()

    # Parse all instructions (before filtering)
    all_instructions = parse.parse_instructions(cores)

    # Filter instructions based on extensions
    instructions = utils.filter_instructions(
        all_instructions, llvm_config, args.extensions
    )

    instrfields = parse.parse_instrfields(cores)
    relocations = parse.parse_relocations(cores)

    # Create necessary mappings
    instrfield_map = {field.name: field for field in instrfields}
    relocation_map = {reloc.name: reloc for reloc in relocations}
    instruction_map = {instr.name: instr for instr in instructions}

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
    for instr in all_instructions:
        if instr.name not in instruction_map:
            # Check if this instruction is used by any dependency relocation
            for dep_reloc_name in dependency_relocations:
                if dep_reloc_name in all_relocations_instructions_map:
                    if instr.name in all_relocations_instructions_map[dep_reloc_name]:
                        instruction_map[instr.name] = instr
                        logger.debug(
                            f"Added instruction for dependency relocation: {instr.name}"
                        )
                        break

    # Get test file paths
    if args.extensions is not None:
        extension_str = "_".join(args.extensions)
        base_test_dir = os.path.join(
            args.output_dir,
            f"reloc_results_{args.adl_file_name}",
            f"tests_{extension_str}",
        )
    else:
        base_test_dir = os.path.join(
            args.output_dir, f"reloc_results_{args.adl_file_name}", "tests_all"
        )

    # Find all test files and label files
    import glob

    test_file_paths = glob.glob(
        os.path.join(base_test_dir, "**", "*.asm"), recursive=True
    )
    label_file_paths = glob.glob(
        os.path.join(base_test_dir, "**", "labels*.inc"), recursive=True
    )
    sym_file_paths = glob.glob(
        os.path.join(base_test_dir, "**", "*.inc"), recursive=True
    )

    # Read symbol file if it exists
    syms = []
    if sym_file_paths:
        with open(sym_file_paths[0], "r") as f:
            sym_content = f.read()
            syms = re.findall(r"\.global\s+(\w+)", sym_content)

    # Process each test file
    for test_file in test_file_paths:
        test_file_basename = os.path.basename(test_file)

        # Find matching label file
        matching_label_file = None
        for label_file in label_file_paths:
            if os.path.dirname(label_file) == os.path.dirname(test_file):
                matching_label_file = label_file
                break

        if not matching_label_file:
            continue

        # Read labels and addends from label file
        labels = []
        addends = []
        with open(matching_label_file, "r") as f:
            label_content = f.read()
            labels = re.findall(r"\b(L\d+):", label_content)
            addends = re.findall(r"\.org\s+(0x[0-9a-fA-F]+)", label_content)

        # Process each relocation and its instructions
        for relocation_name, instruction_names in relocations_instructions_map.items():
            if relocation_name not in relocation_map:
                continue

            relocation = relocation_map[relocation_name]

            for instruction_name in instruction_names:
                # Check if this test file matches the current relocation and instruction
                if not utils.matches_relocation_test_file(
                    test_file_basename, relocation_name, instruction_name
                ):
                    continue

                if instruction_name not in instruction_map:
                    logger.warning(
                        f"Instruction {instruction_name} not found in instruction_map for relocation {relocation_name}"
                    )
                    continue

                instruction = instruction_map[instruction_name]

                # Parse syntax to detect offset pattern: imm(rs)
                syntax_parts = instruction.syntax.split(maxsplit=1)
                if len(syntax_parts) < 2:
                    continue

                operands_str = syntax_parts[1]

                # Check if syntax contains offset pattern
                has_offset = bool(re.search(r"\w+\(\w+\)", operands_str))

                # Get operands (already separated by get_instruction_operands)
                operands = utils.get_instruction_operands(instruction.syntax)

                # Determine which operand is the offset base register
                offsets = []
                operands_extended = []

                if has_offset:
                    # Find the offset pattern in the original syntax
                    offset_match = re.search(r"(\w+)\((\w+)\)", operands_str)
                    if offset_match:
                        imm_operand = offset_match.group(1)
                        offset_operand = offset_match.group(2)
                        offsets.append(offset_operand)

                        # Build operands_extended with offset separated
                        for op in operands:
                            if op == imm_operand:
                                operands_extended.append(op)
                                # Add the offset operand right after the immediate
                                if offset_operand in operands:
                                    operands_extended.append(offset_operand)
                            elif op != offset_operand:
                                # Add other operands normally (skip offset since we already added it)
                                operands_extended.append(op)
                else:
                    # No offset pattern, use operands as-is
                    operands_extended = operands

                # Get operand values for this instruction
                operand_values = utils.get_operand_values_for_instruction(
                    instruction, instrfield_map, operands_extended
                )

                # Append test cases to the file
                with open(test_file, "a") as f:
                    _write_relocation_tests(
                        f,
                        instruction,
                        relocation,
                        operands_extended,
                        offsets,
                        labels,
                        addends,
                        syms,
                        operand_values,
                        instrfield_map,
                        relocation_map,
                        relocations_instructions_map,
                        instruction_map,
                        args.symbol_max_value,
                    )


def _write_relocation_tests(
    f,
    instruction: utils.Instruction,
    relocation: utils.Relocation,
    operands_extended: List[str],
    offsets: List[str],
    labels: List[str],
    addends: List[str],
    syms: List[str],
    operand_values: Dict[str, str],
    instrfield_map: Dict[str, utils.InstrField],
    relocation_map: Dict[str, utils.Relocation],
    relocations_instructions_map: Dict[str, List[str]],
    instruction_map: Dict[str, utils.Instruction],
    symbol_max_value: int,
) -> None:
    """
    Write relocation test cases to a file.

    Args:
        f: File object to write to
        instruction: The Instruction object
        relocation: The Relocation object
        operands_extended: List of operands (with offsets separated)
        offsets: List of offset operands
        labels: List of label names
        addends: List of addend values
        syms: List of symbol names
        operand_values: Dictionary of operand values
        instrfield_map: Mapping of field names to InstrField objects
        relocation_map: Mapping of relocation names to Relocation objects
        relocations_instructions_map: Mapping of relocations to instructions
        symbol_max_value: Maximum symbol value from command line args
    """

    # Helper function to format operand value
    def format_operand(
        op: str, label: str = None, addend: str = None, sym: str = None
    ) -> str:
        """Format an operand value based on its type and context."""
        # If it's an offset operand
        if op in offsets:
            if op in operand_values and operand_values[op]:
                return f"({operand_values[op]})"
            else:
                return f"({op})"

        # If it's a register operand
        if op in operand_values and operand_values[op]:
            return operand_values[op]

        # If it's an immediate operand (has relocation)
        if op in instrfield_map and instrfield_map[op].reloc:
            if sym:
                # Use symbol
                if relocation.abbrev:
                    return f"%{relocation.abbrev}({sym})"
                else:
                    return sym
            elif label:
                # Use label
                if addend:
                    if relocation.abbrev:
                        return f"%{relocation.abbrev}({label} + {addend})"
                    else:
                        return f"({label} + {addend})"
                else:
                    if relocation.abbrev:
                        return f"%{relocation.abbrev}({label})"
                    else:
                        return label

        return op

    # Write weak labels if pcrel
    if relocation.pcrel == "true":
        for label in labels:
            f.write(f".weak {label}\n")
        f.write("\n")

    # Write dependencies if any
    if relocation.dependency:
        f.write("#Add relocation dependencies\n")
        for label in labels:
            f.write(f"{label}:\n")
            for dep_reloc_name in relocation.dependency:
                if dep_reloc_name in relocations_instructions_map:
                    # Get the first instruction associated with this dependency relocation
                    dep_instruction_name = relocations_instructions_map[dep_reloc_name][
                        0
                    ]
                    dep_relocation = relocation_map.get(dep_reloc_name)

                    # Get the actual dependency instruction object
                    dep_instruction = instruction_map.get(dep_instruction_name)
                    if not dep_instruction:
                        continue

                    # Get the dependency instruction's operands from its syntax
                    dep_operands_raw = utils.get_instruction_operands(
                        dep_instruction.syntax
                    )

                    # Separate offsets from operands for dependency instruction
                    dep_operands_extended = []
                    dep_offsets = []
                    for op in dep_operands_raw:
                        offset_match = re.search(r"\((.*?)\)", op)
                        if offset_match:
                            dep_offsets.append(offset_match.group(1))
                            dep_operands_extended.append(re.sub(r"\(.*?\)", "", op))
                            dep_operands_extended.append(offset_match.group(1))
                        else:
                            dep_operands_extended.append(op)

                    # Get operand values for dependency instruction
                    dep_operand_values = utils.get_operand_values_for_instruction(
                        dep_instruction, instrfield_map, dep_operands_extended
                    )

                    # Format dependency instruction operands
                    dep_abbrev = dep_relocation.abbrev if dep_relocation else None

                    def format_dep_operand(op: str) -> str:
                        """Format operand for dependency instruction."""
                        # If it's an offset operand
                        if op in dep_offsets:
                            if op in dep_operand_values and dep_operand_values[op]:
                                return f"({dep_operand_values[op]})"
                            else:
                                return f"({op})"

                        # If it's a register operand
                        if op in dep_operand_values and dep_operand_values[op]:
                            return dep_operand_values[op]

                        # If it's an immediate operand (has relocation)
                        if op in instrfield_map and instrfield_map[op].reloc:
                            if dep_abbrev:
                                return f"%{dep_abbrev}({label})"
                            else:
                                return label

                        return op

                    dep_values = [
                        format_dep_operand(op) for op in dep_operands_extended
                    ]

                    # Write the dependency instruction
                    if dep_offsets:
                        f.write(
                            f"\t{dep_instruction.syntax.split()[0]} {','.join(dep_values[:-1])}{dep_values[-1]}\n"
                        )
                    else:
                        f.write(
                            f"\t{dep_instruction.syntax.split()[0]} {','.join(dep_values)}\n"
                        )
        f.write("\n")

    # Test Sym.Value field
    f.write("#Testing each bit for the Sym.Value field from the relocation section\n")
    for label in labels:
        op_values = [format_operand(op, label=label) for op in operands_extended]

        if offsets:
            f.write(
                f"\t{instruction.syntax.split()[0]} {','.join(op_values[:-1])}{op_values[-1]}\n"
            )
        else:
            f.write(f"\t{instruction.syntax.split()[0]} {','.join(op_values)}\n")

    # Test Addend field
    f.write("\n#Testing each bit for the Addend field from the relocation section\n")
    for label, addend in zip(labels, addends):
        op_values = [
            format_operand(op, label=labels[0], addend=addend)
            for op in operands_extended
        ]

        if offsets:
            f.write(
                f"\t{instruction.syntax.split()[0]} {','.join(op_values[:-1])}{op_values[-1]}\n"
            )
        else:
            f.write(f"\t{instruction.syntax.split()[0]} {','.join(op_values)}\n")

    # Test Info field (only if no dependencies)
    if not relocation.dependency:
        f.write("\n#Testing each bit for the Info field from the relocation section\n")

        # Part 1: Using labels
        for i, label in enumerate(labels):
            label_name = f"L{2**i - 1}"
            if (2**i - 1) < len(labels):
                op_values = [
                    format_operand(op, label=label_name) for op in operands_extended
                ]

                if offsets:
                    f.write(
                        f"\t{instruction.syntax.split()[0]} {','.join(op_values[:-1])}{op_values[-1]}\n"
                    )
                else:
                    f.write(
                        f"\t{instruction.syntax.split()[0]} {','.join(op_values)}\n"
                    )

        # Part 2: Using symbols
        for i, sym in enumerate(syms):
            if i >= symbol_max_value:
                break
            if (2**i - 1) < len(syms):
                op_values = [format_operand(op, sym=sym) for op in operands_extended]

                if offsets:
                    f.write(
                        f"\t{instruction.syntax.split()[0]} {','.join(op_values[:-1])}{op_values[-1]}\n"
                    )
                else:
                    f.write(
                        f"\t{instruction.syntax.split()[0]} {','.join(op_values)}\n"
                    )
