# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import logging
import shutil
from datetime import datetime
from tools.testing import utils
from tools.testing import parse


def generate_fixup_tests() -> None:
    """
    Generate fixup test files for relocations.

    Creates test files that verify relocation fixup calculations by testing
    various symbol values and addends.
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
    instrfield_map = {field.name: field for field in instrfields}

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

    # DON'T add dependency relocations to relocations_instructions_map
    # They will be handled inside the test files, not as separate test files

    # But DO update instruction_map to include instructions from dependency relocations
    # so we can generate the dependency instructions inside the test files
    for dep_reloc_name in dependency_relocations:
        if dep_reloc_name in all_relocations_instructions_map:
            for instr_name in all_relocations_instructions_map[dep_reloc_name]:
                # Find the instruction in all_instructions
                for instr in all_instructions:
                    if instr.name == instr_name:
                        if instr_name not in instruction_map:
                            instruction_map[instr_name] = instr
                            logger.debug(
                                f"Added instruction '{instr_name}' for dependency relocation '{dep_reloc_name}'"
                            )

                        # Also add under the syntax name
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
    tests_dir = utils.prepare_fixup_tests_output_folder(
        args.output_dir, args.adl_file_name, args.extensions
    )

    # Clean and recreate tests directory
    if os.path.exists(tests_dir):
        shutil.rmtree(tests_dir)
    os.makedirs(tests_dir, exist_ok=True)

    # Get architecture info using existing functions
    architecture, attributes, mattrib = parse.asm_config_info(cores)
    base_arch = llvm_config.get("BaseArchitecture", "rv32")
    extension_versions = utils.get_extension_versions(attributes, base_arch)

    arch_info = {
        "architecture": architecture,
        "mattrib": mattrib,
        "base_arch": base_arch,
        "extension_versions": extension_versions,
    }

    # Generate tests ONLY for relocations in the filtered set (not dependencies)
    for reloc_name, instr_names in relocations_instructions_map.items():
        if reloc_name not in relocation_map:
            continue

        relocation = relocation_map[reloc_name]

        # Skip relocations without fixup action
        if not relocation.action:
            continue

        # Create directory for this relocation
        reloc_dir = os.path.join(tests_dir, reloc_name)
        os.makedirs(reloc_dir, exist_ok=True)

        # Generate test for each instruction
        for instr_name in instr_names:
            if instr_name not in instruction_map:
                continue

            instruction = instruction_map[instr_name]

            # Generate the test file
            _generate_fixup_test_file(
                reloc_dir,
                relocation,
                instruction,
                instrfield_map,
                instruction_map,
                relocation_map,
                all_relocations_instructions_map,  # Pass this for dependency lookup
                arch_info,
                args,
            )

            logger.debug(f"Generated fixup test: {reloc_name}/{instr_name}")


def _generate_fixup_test_file(
    output_dir: str,
    relocation: utils.Relocation,
    instruction: utils.Instruction,
    instrfield_map: dict,
    instruction_map: dict,
    relocation_map: dict,
    relocations_instructions_map: dict,
    arch_info: dict,
    args,
) -> None:
    """
    Generate a single fixup test file.

    Args:
        output_dir: Directory to write the test file
        relocation: The Relocation object
        instruction: The Instruction object
        instrfield_map: Mapping of instrfield names to InstrField objects
        instruction_map: Mapping of instruction names to Instruction objects
        relocation_map: Mapping of relocation names to Relocation objects
        relocations_instructions_map: Mapping of relocations to instructions
        arch_info: Architecture information dictionary
        args: Command line arguments
    """
    # Get the instrfield for this relocation
    instrfield = None

    if instruction.fields:
        # Regular instruction - check fields
        for field_name in instruction.fields.keys():
            if field_name in instrfield_map:
                field = instrfield_map[field_name]
                if field.reloc and relocation.name in field.reloc:
                    instrfield = field
                    break
    else:
        # Alias instruction - check syntax operands
        syntax_operands = utils.get_instruction_operands(instruction.syntax)
        for operand_name in syntax_operands:
            if operand_name in instrfield_map:
                field = instrfield_map[operand_name]
                if field.reloc and relocation.name in field.reloc:
                    instrfield = field
                    break

    if not instrfield:
        return

    # Calculate the number of test cases based on field width
    field_width = instrfield.width + instrfield.shift + (1 if instrfield.signed else 0)
    num_tests = field_width - instrfield.shift

    # Get syntax name
    syntax_name = instruction.syntax.split()[0]

    # Create test file
    test_file = os.path.join(output_dir, f"{relocation.name}_{instruction.name}.asm")

    with open(test_file, "w") as f:
        # Write header using utils function
        _write_header(
            f,
            relocation,
            instruction,
            syntax_name,
            arch_info,
            args,
            os.path.basename(test_file),
        )

        # Write labels
        _write_fixup_test_labels(
            f,
            num_tests,
            relocation,
            relocations_instructions_map,
            instruction_map,
            relocation_map,
            instrfield_map,
        )

        # Write Sym.Value tests
        _write_fixup_test_sym_value(
            f,
            num_tests,
            relocation,
            instruction,
            syntax_name,
            instrfield,
            instrfield_map,
        )

        # Write Addend tests
        _write_fixup_test_addend(
            f,
            num_tests,
            relocation,
            instruction,
            syntax_name,
            instrfield,
            instrfield_map,
        )


def _write_header(
    f,
    relocation: utils.Relocation,
    instruction: utils.Instruction,
    syntax_name: str,
    arch_info: dict,
    args: utils.RelocationCommandLineArgs,
    test_file_name: str,
) -> None:
    """
    Write the header section for a fixup test file including copyright, metadata, and LLVM directives.

    Args:
        f: File object to write to
        relocation: The Relocation object
        instruction: The Instruction object
        syntax_name: The syntax name of the instruction
        arch_info: Architecture information dictionary
        args: Command line arguments object
        test_file_name: Name of the test file

    Returns:
        None
    """
    now = datetime.now()
    f.write(f"Data:\n")
    f.write(f"# Copyright (c) 2023-{now.strftime('%Y')} NXP\n")
    f.write("# SPDX-License-Identifier: BSD-2-Clause\n")
    f.write(f"#   @file    {relocation.name}_{instruction.name}.s\n")
    f.write("#   @version 0.5\n")
    f.write("#\n")
    f.write("#-----------------\n")
    f.write("# Date D/M/Y\n")
    f.write(f"# {now.strftime('%d-%m-%Y')}\n")
    f.write("#-----------------\n")
    f.write("#\n")
    f.write(f"# @test_id        {relocation.name}_{instruction.name}.s\n")

    # Get operands string from syntax
    operands = utils.get_instruction_operands(instruction.syntax)
    operands_str = ",".join(operands)

    f.write(f"# @brief          Encode {syntax_name} {operands_str}\n")

    # Write dependency info if present - need to get the actual instruction syntax
    if relocation.dependency:
        # We need to import parse to get instruction info
        from tools.testing import parse

        # Parse instructions to get dependency instruction details
        cores = parse.get_cores_element(args.adl_file_path)
        all_instructions = parse.parse_instructions(cores)
        instrfields = parse.parse_instrfields(cores)

        # Create instruction map
        instruction_map = {instr.name: instr for instr in all_instructions}
        for instr in all_instructions:
            syntax_name_map = instr.syntax.split()[0]
            if syntax_name_map not in instruction_map:
                instruction_map[syntax_name_map] = instr

        # Get relocation-instruction mapping
        relocations_instructions_map = utils.get_relocation_instruction_mapping(
            all_instructions, instrfields
        )

        for dep_reloc_name in relocation.dependency:
            if dep_reloc_name in relocations_instructions_map:
                dep_instr_names = relocations_instructions_map[dep_reloc_name]
                if dep_instr_names:
                    dep_instr_name = dep_instr_names[0]
                    if dep_instr_name in instruction_map:
                        dep_instruction = instruction_map[dep_instr_name]
                        dep_syntax_name = dep_instruction.syntax.split()[0]
                        dep_operands = utils.get_instruction_operands(
                            dep_instruction.syntax
                        )
                        dep_operands_str = ",".join(dep_operands)
                        f.write(
                            f"# @brief          Encode_dep {dep_syntax_name} {dep_operands_str}\n"
                        )

    f.write("# @details        Tests if the relocation fixup is calculated correctly\n")
    f.write("# @pre            Python 3.9+\n")
    f.write("# @test_level     Unit\n")
    f.write("# @test_type      Functional\n")
    f.write("# @test_technique Blackbox\n")
    f.write(
        f"# @pass_criteria  Relocation {relocation.name} fixup calculated correctly\n"
    )
    f.write("# @test_method    Analysis of requirements\n")
    f.write(f'# @requirements   "{instruction.name}" syntax and encoding\n')
    f.write("# @execution_type Automated\n")
    f.write("\n")

    # Write RUN commands
    if args.extensions:
        ext_str = "_".join(args.extensions)
        tests_path = (
            f"fixup_results_{args.adl_file_name}/tests_{ext_str}/{relocation.name}"
        )
        refs_path = f"fixup_results_{args.adl_file_name}/references_tests/readelf"
    else:
        tests_path = f"fixup_results_{args.adl_file_name}/tests_all/{relocation.name}"
        refs_path = f"fixup_results_{args.adl_file_name}/references_tests/readelf"

    f.write(f"// RUN: %asm -I/{os.path.abspath(args.output_dir)}/{tests_path} ")
    f.write(f"-arch={arch_info['architecture']} -mattr=\"{arch_info['mattrib']}\" ")
    f.write("%s -o %s.o -filetype=obj\n")
    f.write(f"// RUN: %readelf -x 2 %s.o | %filecheck ")
    f.write(
        f"{os.path.abspath(args.output_dir)}/{refs_path}/{test_file_name}.o.txt\n\n"
    )

    # Write assembly directives
    f.write("\t.text\n")
    f.write("\t.attribute\t4, 16\n")
    f.write(f"\t.globl {instruction.name}\n")
    f.write("\t.p2align\t1\n")
    f.write(f"\t.type\t{instruction.name},@function\n\n")


def _write_fixup_test_labels(
    f,
    num_tests: int,
    relocation: utils.Relocation,
    relocations_instructions_map: dict,
    instruction_map: dict,
    relocation_map: dict,
    instrfield_map: dict,
) -> None:
    """Write label definitions for fixup tests."""
    # Write labels for non-dependency relocations
    if not relocation.dependency:
        for i in range(1, num_tests):
            f.write(f"L{i}:\n")
            f.write("\tc.nop\n")
        f.write("\n")

    # Write dependency instructions
    if relocation.dependency:
        f.write("#Add relocation dependencies\n")
        for i in reversed(range(1, num_tests)):
            label = f"L{i}"

            for dep_reloc_name in relocation.dependency:
                if dep_reloc_name not in relocations_instructions_map:
                    continue

                dep_instr_names = relocations_instructions_map[dep_reloc_name]
                if not dep_instr_names:
                    continue

                dep_instr_name = dep_instr_names[0]
                if dep_instr_name not in instruction_map:
                    continue

                dep_instruction = instruction_map[dep_instr_name]
                dep_relocation = relocation_map[dep_reloc_name]

                # Get syntax name
                dep_syntax = dep_instruction.syntax.split()[0]

                # Build operand string
                operand_str = _build_dependency_operand_string(
                    dep_instruction, dep_relocation, label, instrfield_map
                )

                f.write(f"{label}:\n")
                f.write(f"\t{dep_syntax} {operand_str}\n")

        f.write("\n")


def _write_fixup_test_sym_value(
    f,
    num_tests: int,
    relocation: utils.Relocation,
    instruction: utils.Instruction,
    syntax_name: str,
    instrfield: utils.InstrField,
    instrfield_map: dict,
) -> None:
    """Write test cases for Sym.Value field."""
    f.write("#Testing each bit for the Sym.Value field from the relocation section\n")

    for i in reversed(range(1, num_tests)):
        label = f"L{i}"
        operand_str = _build_operand_string(
            instruction, relocation, label, None, instrfield_map
        )
        f.write(f"\t{syntax_name} {operand_str}\n")

    f.write("\n")


def _write_fixup_test_addend(
    f,
    num_tests: int,
    relocation: utils.Relocation,
    instruction: utils.Instruction,
    syntax_name: str,
    instrfield: utils.InstrField,
    instrfield_map: dict,
) -> None:
    """Write test cases for Addend field."""
    f.write("#Testing each bit for the Addend field from the relocation section\n")

    for i in reversed(range(1, num_tests)):
        label = f"L{i}"
        addend = hex(pow(2, i))
        operand_str = _build_operand_string(
            instruction, relocation, label, addend, instrfield_map
        )
        f.write(f"\t{syntax_name} {operand_str}\n")


def _build_operand_string(
    instruction: utils.Instruction,
    relocation: utils.Relocation,
    label: str,
    addend: str = None,
    instrfield_map: dict = None,
) -> str:
    """
    Build the operand string for an instruction.

    Args:
        instruction: The Instruction object
        relocation: The Relocation object
        label: The label to use for relocatable operands
        addend: Optional addend value (hex string)
        instrfield_map: Mapping of instrfield names to InstrField objects

    Returns:
        Formatted operand string
    """
    # Get operands from syntax
    operands = utils.get_instruction_operands(instruction.syntax)
    operand_parts = []

    # Check if instruction has offset syntax (e.g., "imm(rs1)")
    has_offset = bool(re.search(r"\w+\(\w+\)", instruction.syntax))
    offset_operand = None

    if has_offset:
        # Extract the offset operand name from syntax
        offset_match = re.search(r"\((\w+)\)", instruction.syntax)
        if offset_match:
            offset_operand = offset_match.group(1)

    for operand_name in operands:
        # Skip offset operand - we'll add it with parentheses later
        if operand_name == offset_operand:
            continue

        # Check if this operand has the relocation
        has_reloc = False
        if instrfield_map and operand_name in instrfield_map:
            field = instrfield_map[operand_name]
            if field.reloc and relocation.name in field.reloc:
                has_reloc = True

        if has_reloc:
            # This is the relocatable operand
            if relocation.abbrev:
                if addend:
                    imm_part = f"%{relocation.abbrev}({label}+{addend})"
                else:
                    imm_part = f"%{relocation.abbrev}({label})"
            else:
                if addend:
                    imm_part = f"({label}+{addend})"
                else:
                    imm_part = label

            # If there's an offset, append it with parentheses
            if offset_operand:
                offset_value = _get_default_operand_value(
                    offset_operand, instruction, instrfield_map
                )
                operand_parts.append(f"{imm_part}({offset_value})")
            else:
                operand_parts.append(imm_part)
        else:
            # Regular operand - use default value
            operand_parts.append(
                _get_default_operand_value(operand_name, instruction, instrfield_map)
            )

    return ",".join(operand_parts)


def _build_dependency_operand_string(
    instruction: utils.Instruction,
    relocation: utils.Relocation,
    label: str,
    instrfield_map: dict,
) -> str:
    """Build operand string for dependency instructions."""
    operands = utils.get_instruction_operands(instruction.syntax)
    operand_parts = []

    # Check if instruction has offset syntax
    has_offset = bool(re.search(r"\w+\(\w+\)", instruction.syntax))
    offset_operand = None

    if has_offset:
        offset_match = re.search(r"\((\w+)\)", instruction.syntax)
        if offset_match:
            offset_operand = offset_match.group(1)

    for operand_name in operands:
        # Skip offset operand - we'll add it with parentheses later
        if operand_name == offset_operand:
            continue

        # Check if this operand has the relocation
        has_reloc = False
        if operand_name in instrfield_map:
            field = instrfield_map[operand_name]
            if field.reloc and relocation.name in field.reloc:
                has_reloc = True

        if has_reloc:
            if relocation.abbrev:
                imm_part = f"%{relocation.abbrev}({label})"
            else:
                imm_part = label

            # If there's an offset, append it with parentheses
            if offset_operand:
                offset_value = _get_default_operand_value(
                    offset_operand, instruction, instrfield_map
                )
                operand_parts.append(f"{imm_part}({offset_value})")
            else:
                operand_parts.append(imm_part)
        else:
            operand_parts.append(
                _get_default_operand_value(operand_name, instruction, instrfield_map)
            )

    return ",".join(operand_parts)


def _get_default_operand_value(
    operand_name: str, instruction: utils.Instruction, instrfield_map: dict = None
) -> str:
    """
    Get a default value for an operand.

    Args:
        operand_name: Name of the operand
        instruction: The Instruction object (for context)
        instrfield_map: Optional mapping of instrfield names to InstrField objects

    Returns:
        Default value string for the operand
    """
    # Check if it's a regfile type with enumerated values
    if instrfield_map and operand_name in instrfield_map:
        field = instrfield_map[operand_name]
        if field.type == "regfile" and field.enumerated:
            # Check if this is a pair register instruction
            if utils.is_pair_register(operand_name, instruction):
                # For pair registers, return the highest even register
                # Filter for even values and exclude x31
                even_values = []
                for enum_opt in field.enumerated:
                    try:
                        reg_num = int(enum_opt.name)
                        if reg_num % 2 == 0 and reg_num < 31:
                            even_values.append(enum_opt.value)
                    except ValueError:
                        continue

                if even_values:
                    return even_values[-1]  # Return highest even register (x30)

            # Return the last enumerated value for non-pair registers
            return field.enumerated[-1].value

    # For now, just return the operand name as placeholder
    return operand_name
