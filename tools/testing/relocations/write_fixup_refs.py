# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
import logging
import shutil
from datetime import datetime
from tools.testing import utils
from tools.testing import parse


def generate_fixup_references() -> None:
    """Generate reference files for fixup tests."""
    logger = logging.getLogger(__name__)

    # Get command line arguments
    args = parse.parse_relocation_command_line_args()

    # Setup parsing context
    (
        instruction_map,
        instrfield_map,
        relocation_map,
        relocations_instructions_map,
        instruction_width_dict,
        instruction_syntaxName_dict,
        relocation_action_dict,
        relocation_abbrev_dict,
        relocation_field_width,
        relocation_dependency_dict,
        bit_endianness,
    ) = _setup_parsing_context(args)

    # Get directories
    tests_directory, references_directory = _get_directories(args)

    # Clean and recreate refs directory
    if os.path.exists(references_directory):
        shutil.rmtree(references_directory)
    os.makedirs(references_directory, exist_ok=True)

    # Process all test files
    for dirpath, dirnames, filenames in os.walk(tests_directory):
        for filename in filenames:
            if not filename.endswith(".asm"):
                continue

            test_asm_file_path = os.path.join(dirpath, filename)
            ref_asm_file_path = os.path.join(references_directory, filename)

            # Find relocation for this file
            relocation = None
            for reloc_name in relocations_instructions_map:
                if reloc_name in os.path.basename(test_asm_file_path):
                    relocation = reloc_name
                    break

            if not relocation:
                continue

            # Extract instruction name from filename
            instruction = (
                os.path.basename(test_asm_file_path)
                .split(f"{relocation}_")[1]
                .split(".asm")[0]
            )

            # Calculate references
            references_list = _calculate_references_for_file(
                test_asm_file_path,
                relocation,
                instruction,
                relocations_instructions_map,
                instruction_syntaxName_dict,
                instruction_width_dict,
                relocation_action_dict,
                relocation_abbrev_dict,
                relocation_field_width,
                relocation_dependency_dict,
                instruction_map,
                instrfield_map,
                logger,
            )

            # Write reference file
            _write_reference_file(
                ref_asm_file_path,
                references_list,
                instruction,
                instruction_width_dict,
                bit_endianness,
            )

            logger.debug(f"Generated fixup reference: {ref_asm_file_path}")


def _setup_parsing_context(args):
    """Parse ADL file and create all necessary mappings and dictionaries.

    Returns:
        tuple: (instruction_map, instrfield_map, relocation_map,
                relocations_instructions_map, instruction_width_dict,
                instruction_syntaxName_dict, relocation_action_dict,
                relocation_abbrev_dict, relocation_field_width,
                relocation_dependency_dict, bit_endianness)
    """
    cores = parse.get_cores_element(args.adl_file_path)

    # Parse ADL data
    all_instructions = parse.parse_instructions(cores)
    instrfields = parse.parse_instrfields(cores)
    relocations = parse.parse_relocations(cores)
    bit_endianness = parse.bit_endianness(cores)

    # Create mappings
    instruction_map = {instr.name: instr for instr in all_instructions}
    instrfield_map = {field.name: field for field in instrfields}
    relocation_map = {reloc.name: reloc for reloc in relocations}

    # Also map by syntax name
    for instr in all_instructions:
        syntax_name = instr.syntax.split()[0]
        if syntax_name not in instruction_map:
            instruction_map[syntax_name] = instr

    # Get relocation-instruction mapping
    relocations_instructions_map = utils.get_relocation_instruction_mapping(
        all_instructions, instrfields
    )

    # Build helper dictionaries
    instruction_width_dict = {
        name: instr.width for name, instr in instruction_map.items()
    }
    instruction_syntaxName_dict = {
        name: instr.syntax.split()[0] for name, instr in instruction_map.items()
    }

    # Build relocation helper dictionaries
    relocation_action_dict = {reloc.name: reloc.action for reloc in relocations}
    relocation_abbrev_dict = {
        reloc.name: reloc.abbrev for reloc in relocations if reloc.abbrev
    }
    relocation_field_width = {reloc.name: reloc.field_width for reloc in relocations}
    relocation_dependency_dict = {
        reloc.name: reloc.dependency for reloc in relocations if reloc.dependency
    }

    return (
        instruction_map,
        instrfield_map,
        relocation_map,
        relocations_instructions_map,
        instruction_width_dict,
        instruction_syntaxName_dict,
        relocation_action_dict,
        relocation_abbrev_dict,
        relocation_field_width,
        relocation_dependency_dict,
        bit_endianness,
    )


def _get_directories(args):
    """Get tests and references directories based on args.

    Returns:
        tuple: (tests_directory, references_directory)
    """
    if args.extensions is not None:
        tests_directory = os.path.join(
            args.output_dir,
            "fixup_results_" + args.adl_file_name,
            "tests_" + "_".join(args.extensions),
        )
        references_directory = os.path.join(
            args.output_dir,
            "fixup_results_" + args.adl_file_name,
            "refs_" + "_".join(args.extensions),
        )
    else:
        tests_directory = os.path.join(
            args.output_dir, "fixup_results_" + args.adl_file_name, "tests_all"
        )
        references_directory = os.path.join(
            args.output_dir, "fixup_results_" + args.adl_file_name, "refs_all"
        )

    return tests_directory, references_directory


def _parse_syntax_from_file(test_asm_file_path):
    """Extract syntax information from test assembly file.

    Returns:
        tuple: (syntax_instruction, syntax_operands, syntax_dep_instruction, syntax_dep_operands)
    """
    syntax_pattern = r"# @brief\s+Encode\s+(.+)$"
    syntax_dep_pattern = r"# @brief\s+Encode_dep\s+(.+)$"

    syntax_operands = None
    syntax_dep_operands = None
    syntax_dep_instruction = None
    syntax_instruction = None

    with open(test_asm_file_path, "r") as source_asm_file:
        # Match current instruction syntax
        for line in source_asm_file:
            match = re.match(syntax_pattern, line)
            if match:
                syntax_line = match.group(1).strip()
                syntax_line_parts = syntax_line.split()
                if len(syntax_line_parts) >= 2:
                    syntax_instruction = syntax_line_parts[0]
                    syntax_operands = syntax_line_parts[1]
                else:
                    syntax_instruction = syntax_line_parts[0]
                    syntax_operands = None
                break

        # Match dependency syntax
        source_asm_file.seek(0)
        for line in source_asm_file:
            match_dep = re.match(syntax_dep_pattern, line)
            if match_dep:
                syntax_dep_line = match_dep.group(1).strip()
                syntax_line_dep_parts = syntax_dep_line.split()
                if len(syntax_line_dep_parts) >= 2:
                    syntax_dep_instruction = syntax_line_dep_parts[0]
                    syntax_dep_operands = syntax_line_dep_parts[1]
                else:
                    syntax_dep_instruction = syntax_line_dep_parts[0]
                    syntax_dep_operands = None
                break

    return (
        syntax_instruction,
        syntax_operands,
        syntax_dep_instruction,
        syntax_dep_operands,
    )


def _build_label_address_dict(
    test_asm_file_path,
    relocation,
    relocation_action_dict,
    syntax_operands,
    instruction_width_dict,
):
    """Build dictionary mapping labels to their addresses."""
    label_address_dict = {}

    if "S" not in relocation_action_dict[relocation] or syntax_operands is None:
        return label_address_dict

    with open(test_asm_file_path, "r") as source_asm_file:
        current_address = 0
        instruction_lines = []

        for line in source_asm_file:
            stripped_line = line.strip()
            match = re.match(r"L(\d+):\s*", stripped_line)
            if match:
                symbol_label = f"L{match.group(1)}"
                for instr_line in instruction_lines:
                    prev_instruction = instr_line.split()
                    if (
                        prev_instruction
                        and prev_instruction[0] in instruction_width_dict
                    ):
                        current_address += (
                            int(instruction_width_dict[prev_instruction[0]]) / 8
                        )
                label_address_dict[symbol_label] = hex(int(current_address))
                instruction_lines = []
            else:
                if stripped_line:
                    instruction_lines.append(stripped_line)

    return label_address_dict


def _calculate_fixup_value(
    line,
    relocation,
    label_address_dict,
    relocation_action_dict,
    relocation_abbrev_dict,
    relocation_field_width,
    relocation_dependency_dict,
    test_asm_file_path,
    instruction_width_dict,
    instruction,
):
    """Calculate the fixup value for a given instruction line."""
    fixup_value = 0
    line_operands = line.split()[1] if len(line.split()) >= 2 else None

    if "S" not in relocation_action_dict[relocation] or line_operands is None:
        return fixup_value

    # Extract label
    label_match = re.search(r"L\d+", line)
    label = label_match.group(0) if label_match else None

    if label and label in label_address_dict:
        fixup_value += int(label_address_dict[label], 16)

    # Handle PC-relative
    if "P" in relocation_action_dict[relocation] and line_operands is not None:
        if relocation in relocation_dependency_dict:
            pcrel_value = int(
                _count_dep_pcrel(test_asm_file_path, line, instruction_width_dict)
            )
        else:
            pcrel_value = int(
                _count_pcrel(test_asm_file_path, line, instruction_width_dict)
            )
        fixup_value -= pcrel_value

        if (
            relocation in relocation_abbrev_dict
            and relocation_abbrev_dict[relocation] == "pcrel_hi"
        ):
            if fixup_value < pow(
                2,
                int(instruction_width_dict[instruction])
                - int(relocation_field_width[relocation]),
            ):
                fixup_value = 0

    # Handle addendum
    if "A" in relocation_action_dict[relocation] and line_operands is not None:
        match = re.search(r"\b(L\d+)([+\-]\s*0x[0-9a-fA-F]+)?", line)
        if match:
            addendum_value = match.group(2) if match.group(2) else hex(0)
            fixup_value += int(addendum_value, 16)

            if (
                relocation in relocation_abbrev_dict
                and relocation_abbrev_dict[relocation] == "pcrel_hi"
            ):
                if fixup_value < pow(
                    2,
                    int(instruction_width_dict[instruction])
                    - int(relocation_field_width[relocation]),
                ):
                    fixup_value = 0
                else:
                    fixup_value = fixup_value >> (
                        int(instruction_width_dict[instruction])
                        - int(relocation_field_width[relocation])
                    )

    return fixup_value


def _process_instruction_line(
    line,
    syntax_operands,
    syntax_dep_operands,
    syntax_dep_instruction,
    relocation,
    relocation_dependency_dict,
    instrfield_map,
    fixup_value,
):
    """Process a single instruction line and build operand value dictionary."""
    line_instruction_parts = line.split()
    if len(line_instruction_parts) >= 2:
        line_instruction = line_instruction_parts[0]
        line_operands = line_instruction_parts[1]
    else:
        line_instruction = line_instruction_parts[0]
        line_operands = None

    syntax_operands_values = re.findall(r"[\w_]+", str(syntax_operands))
    line_operands_values = re.findall(r"(?<!%)\b[-\w_]+(?:\+\w+)?", str(line_operands))

    if relocation in relocation_dependency_dict:
        syntax_operands_dep_values = re.findall(r"[\w_]+", str(syntax_dep_operands))
        if syntax_dep_instruction and line_instruction in syntax_dep_instruction:
            operand_values_dict = {
                key: value
                for key, value in zip(syntax_operands_dep_values, line_operands_values)
            }
        else:
            operand_values_dict = {
                key: value
                for key, value in zip(syntax_operands_values, line_operands_values)
            }
    else:
        operand_values_dict = {
            key: value
            for key, value in zip(syntax_operands_values, line_operands_values)
        }

    # Build operand value dict with fixup value
    current_line_operand_value_dict = {}
    for key, value in operand_values_dict.items():
        if key in instrfield_map:
            field = instrfield_map[key]
            if field.type == "imm" and not field.enumerated:
                current_line_operand_value_dict[key] = hex(int(fixup_value))
            else:
                current_line_operand_value_dict[key] = value
        else:
            current_line_operand_value_dict[key] = value

    return current_line_operand_value_dict


def _calculate_references_for_file(
    test_asm_file_path,
    relocation,
    instruction,
    relocations_instructions_map,
    instruction_syntaxName_dict,
    instruction_width_dict,
    relocation_action_dict,
    relocation_abbrev_dict,
    relocation_field_width,
    relocation_dependency_dict,
    instruction_map,
    instrfield_map,
    logger,
):
    """Calculate all reference values for a test file."""
    # Find matching instruction lines
    matching_lines = []
    with open(test_asm_file_path, "r") as test_asm_file:
        for line in test_asm_file:
            stripped_line = line.lstrip()
            if (
                os.path.basename(os.path.dirname(test_asm_file_path))
                in relocations_instructions_map.keys()
            ):
                if line.startswith("\t") and any(
                    stripped_line.startswith(instr)
                    for instr in instruction_syntaxName_dict.keys()
                    | instruction_syntaxName_dict.values()
                ):
                    matching_lines.append(line.strip())

    # Parse syntax information
    syntax_instruction, syntax_operands, syntax_dep_instruction, syntax_dep_operands = (
        _parse_syntax_from_file(test_asm_file_path)
    )

    # Build label address dictionary
    label_address_dict = _build_label_address_dict(
        test_asm_file_path,
        relocation,
        relocation_action_dict,
        syntax_operands,
        instruction_width_dict,
    )

    # Calculate references for each line
    references_list = []
    for line in matching_lines:
        # Calculate fixup value
        fixup_value = _calculate_fixup_value(
            line,
            relocation,
            label_address_dict,
            relocation_action_dict,
            relocation_abbrev_dict,
            relocation_field_width,
            relocation_dependency_dict,
            test_asm_file_path,
            instruction_width_dict,
            instruction,
        )

        # Process instruction line
        line_instruction = line.split()[0]
        if line_instruction not in instruction_map:
            logger.warning(
                f"Instruction {line_instruction} not found in instruction_map"
            )
            continue

        instr_obj = instruction_map[line_instruction]
        is_alias = bool(instr_obj.aliases and not instr_obj.fields)

        # Get fields for encoding
        if is_alias:
            alias = instr_obj.aliases[0]
            base_instr_name = alias.name
            if base_instr_name in instruction_map:
                base_instr = instruction_map[base_instr_name]
                fields = base_instr.fields.copy() if base_instr.fields else {}
                fields.update(alias.fields)
            else:
                fields = {}
        else:
            fields = instr_obj.fields if instr_obj.fields else {}

        # Build operand value dictionary
        current_line_operand_value_dict = _process_instruction_line(
            line,
            syntax_operands,
            syntax_dep_operands,
            syntax_dep_instruction,
            relocation,
            relocation_dependency_dict,
            instrfield_map,
            fixup_value,
        )

        # Calculate reference
        reference = utils.calculate_instruction_reference(
            fields, instrfield_map, current_line_operand_value_dict, is_alias=is_alias
        )
        references_list.append(reference)

    return references_list


def _write_reference_file(
    ref_asm_file_path,
    references_list,
    instruction,
    instruction_width_dict,
    bit_endianness,
):
    """Write the reference file with proper formatting based on endianness."""
    with open(ref_asm_file_path, "w") as references_asm_file:
        now = datetime.now()
        references_asm_file.write(f"# Copyright (c) {now.strftime('%Y')} NXP\n")
        references_asm_file.write("# SPDX-License-Identifier: BSD-2-Clause\n\n")

        instr_width = int(instruction_width_dict[instruction])

        for ref in references_list:
            if instr_width == 32:
                if ref == 1:
                    ref_str = hex(ref)[2:]
                    length = len(ref_str)
                    if bit_endianness == "little":
                        formatted_ref = f"0x{ref_str[length-2:]},0x{'0' + ref_str[:length-2] if len(ref_str) > 2 else '0' + ref_str[:length-2]}"
                    else:  # big
                        formatted_ref = f"0x{'0' + ref_str[:length-2] if len(ref_str) > 2 else '0' + ref_str[:length-2]},0x{ref_str[length-2:]}"
                    references_asm_file.write(f".byte {formatted_ref}\n")
                else:
                    references_asm_file.write(f".word {hex(ref)}\n")

            elif instr_width == 16:
                ref_str = hex(ref)[2:]
                length = len(ref_str)
                if bit_endianness == "little":
                    formatted_ref = f"0x{ref_str[length-2:]},0x{'0' + ref_str[:length-2] if len(ref_str) > 2 else '0' + ref_str[:length-2]}"
                else:  # big
                    formatted_ref = f"0x{'0' + ref_str[:length-2] if len(ref_str) > 2 else '0' + ref_str[:length-2]},0x{ref_str[length-2:]}"
                references_asm_file.write(f".byte {formatted_ref}\n")


def _count_pcrel(file_path, target_line_pattern, instruction_width_dict):
    """Function for identifying the value of the program counter after the first label definition for a target line"""
    with open(file_path, "r") as file:
        lines = file.readlines()

    label_found = False
    pcrel_value = 0

    for line in lines:
        stripped_line = line.strip()

        if not label_found and re.match(r"^L\d+:\s*$", stripped_line):
            label_found = True
            continue

        if label_found:
            if re.match(r"^L\d+:\s*$", stripped_line):
                continue

            if stripped_line and not stripped_line.startswith("#"):
                line_instruction = stripped_line.split()[0]
                pcrel_value += int(instruction_width_dict[line_instruction]) / 8

            if re.fullmatch(rf"{re.escape(target_line_pattern)}", stripped_line):
                line_instruction = stripped_line.split()[0]
                return pcrel_value - int(instruction_width_dict[line_instruction]) / 8

    return 0


def _count_dep_pcrel(file_path, target_line, instruction_width_dict):
    """Function for storing the pcrel value of the first label use in case of dependency relocations"""
    label_uses = {}
    instruction_offset = 0
    counting = False

    label_pattern = re.compile(r"\b(L\d+)\b")
    label_definition_pattern = re.compile(r"^L\d+:$")

    with open(file_path, "r") as file:
        lines = file.readlines()

    for line in lines:
        stripped_line = line.strip()

        if not stripped_line or stripped_line.startswith(("#", "//")):
            continue

        if not counting and label_definition_pattern.match(stripped_line):
            counting = True
            continue

        if not counting:
            continue

        if label_definition_pattern.match(stripped_line):
            continue

        matches = label_pattern.findall(stripped_line)

        for label in matches:
            if label not in label_uses:
                label_uses[label] = instruction_offset

        if re.search(r"\b[a-zA-Z]+\b", stripped_line):
            line_instruction = stripped_line.split()[0]
            instruction_offset += int(instruction_width_dict[line_instruction]) / 8

    target_matches = label_pattern.findall(target_line.strip())
    if target_matches:
        label = target_matches[0]
        return label_uses.get(label, None)

    return None
