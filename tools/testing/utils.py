# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from tools import config
from typing import List, Dict, Tuple, Optional


### Data Classes


@dataclass
class EnumOption:
    """Represents an enumerated option with a name-value pair."""

    name: str
    value: str


@dataclass
class InstrField:
    """Represents an instruction field with its encoding properties and constraints."""

    name: str
    ranges: List[List[int]] = field(default_factory=list)
    width: Optional[int] = None
    size: Optional[int] = None
    shift: Optional[int] = None
    offset: Optional[int] = None
    sign_extension: Optional[int] = None
    mask: Optional[str] = None
    enumerated: List[EnumOption] = field(default_factory=list)
    addr: Optional[str] = None
    display: Optional[str] = None
    type: Optional[str] = None
    ref: Optional[str] = None
    signed: Optional[str] = None
    reloc: List[str] = field(default_factory=list)


@dataclass
class Alias:
    """Represents an alias mapping for an instruction."""

    name: str
    fields: Dict[str, Optional[str]]


@dataclass
class Instruction:
    """Represents a machine instruction with metadata and structure."""

    name: str
    width: int
    syntax: str
    dsyntax: str
    attributes: List[str]
    fields: Optional[Dict[str, Optional[str]]]
    inputs: List[str]
    outputs: List[str]
    aliases: Optional[List[Alias]] = field(default_factory=list)
    excluded_values: Optional[Dict[str, Optional[str]]] = None


@dataclass
class Relocation:
    """Represents a relocation with its properties and encoding details."""

    name: str
    abbrev: str
    field_width: int
    pcrel: str
    value: int
    right_shift: int
    action: str
    directive: str
    dependency: List[str] = field(default_factory=list)


@dataclass
class EncodingCommandLineArgs:
    """Parsed command line arguments for the test generation tool."""

    adl_file_path: str
    adl_file_name: str
    extensions: list[str]
    output_dir: str
    display_extensions: bool


@dataclass
class RelocationCommandLineArgs:
    """Command line arguments for relocation test generation."""

    adl_file_path: str
    symbol_max_value: int
    adl_file_name: str
    extensions: list[str]
    output_dir: str
    display_extensions: bool


### Configuration

_llvm_config_cache = None


def load_llvm_config() -> Dict[str, str]:
    """
    Loads and caches the LLVM configuration environment.

    This function reads configuration files from the `tools` package directory:
    - `config.txt`
    - `llvm_config.txt`

    It uses a global cache to avoid reloading the configuration on subsequent calls.

    Returns:
        dict: A dictionary representing the LLVM configuration environment.

    Raises:
        FileNotFoundError: If the configuration files are not found.
    """
    global _llvm_config_cache
    if _llvm_config_cache is None:
        tools_pkg = files("tools")
        config_path = tools_pkg / "config.txt"
        llvm_config_path = tools_pkg / "llvm_config.txt"
        _llvm_config_cache = config.config_environment(
            str(config_path), str(llvm_config_path)
        )
    return _llvm_config_cache


### Instruction Processing


def filter_instructions(
    instructions: List[Instruction],
    llvm_config_dict: Dict[str, str],
    target_extensions: Optional[List[str]] = None,
) -> List[Instruction]:
    """
    Filter instructions based on LLVM configuration, keeping only those with allowed extensions and without 'ignored' attribute.

    Args:
        instructions: List of instruction objects to filter
        llvm_config_dict: Dictionary containing LLVM configuration with extension settings
        target_extensions: Optional list of specific extensions to filter for (from -e flag)

    Returns:
        List[Instruction]: Filtered list of instructions that match the configuration
    """
    # Precompute allowed extension values from config (lowercased for case-insensitive match)
    allowed_attributes = {
        str(llvm_config_dict[attr]).lower()
        for attr in llvm_config_dict
        if attr.startswith("Has") and attr.endswith("Extension")
    }

    filtered_instructions = []
    for instr in instructions:
        # Find allowed attrs present in this instruction
        filtered_attrs = [
            attr for attr in instr.attributes if attr.lower() in allowed_attributes
        ]

        # Check if there is at least one allowed attribute and "ignored" is not in original attrs
        if filtered_attrs and "ignored" not in instr.attributes:
            # Additional filter: if target_extensions specified, only keep instructions with those extensions
            if target_extensions is not None:
                # Convert target extensions to lowercase for comparison
                target_extensions_lower = [ext.lower() for ext in target_extensions]

                # Check if instruction has any of the target extensions
                has_target_extension = any(
                    attr.lower() in target_extensions_lower for attr in instr.attributes
                )

                if not has_target_extension:
                    continue  # Skip this instruction

            # Create a new Instruction with filtered attributes
            filtered_instr = Instruction(
                name=instr.name,
                width=instr.width,
                syntax=instr.syntax,
                dsyntax=instr.dsyntax,
                attributes=filtered_attrs,
                fields=instr.fields,
                inputs=instr.inputs,
                outputs=instr.outputs,
                aliases=instr.aliases,
                excluded_values=instr.excluded_values,
            )
            filtered_instructions.append(filtered_instr)

    return filtered_instructions


def get_instruction_operands(instruction_syntax: str) -> List[str]:
    """
    Extract operand names from instruction syntax string.

    Args:
        instruction_syntax: The syntax string of an instruction (e.g., "add rd, rs1, rs2")

    Returns:
        List[str]: List of operand names found in the syntax
    """
    parts = instruction_syntax.split(maxsplit=1)
    if len(parts) == 1:
        return []

    operands_str = parts[1]

    # Extract all field-like words, including offsets
    operand_names = re.findall(r"[\w]+", operands_str)

    return operand_names


### Relocation Processing


def get_relocation_instruction_mapping(
    instructions: List[Instruction], instrfields: List[InstrField]
) -> Dict[str, List[str]]:
    """
    Create a mapping of relocation names to lists of instruction names that use them.
    Includes both regular instructions and their aliases.

    Args:
        instructions: List of instruction objects
        instrfields: List of instruction field objects

    Returns:
        Dict[str, List[str]]: Dictionary mapping relocation names to instruction names
    """
    reloc_instruction_map = {}

    # Create a mapping of instrfield names to their reloc values (now a list)
    instrfield_reloc_map = {}
    for instrfield in instrfields:
        if instrfield.reloc:  # If list is not empty
            instrfield_reloc_map[instrfield.name] = instrfield.reloc

    # For each instruction, check if any of its fields have relocations
    for instruction in instructions:
        if instruction.fields:  # Regular instruction (fields is not empty)
            # Get operands from the instruction syntax
            syntax_operands = get_instruction_operands(instruction.syntax)
            # Only include fields that appear in the syntax
            field_names = [f for f in instruction.fields.keys() if f in syntax_operands]

            # Check if any of these fields have relocations
            for field_name in field_names:
                if field_name in instrfield_reloc_map:
                    for reloc_name in instrfield_reloc_map[field_name]:
                        if reloc_name not in reloc_instruction_map:
                            reloc_instruction_map[reloc_name] = []
                        if instruction.name not in reloc_instruction_map[reloc_name]:
                            reloc_instruction_map[reloc_name].append(instruction.name)

        elif (
            instruction.aliases
        ):  # Alias instruction (fields is empty, but has aliases)
            # For alias instructions, check the syntax operands directly
            syntax_operands = get_instruction_operands(instruction.syntax)

            # Check if any syntax operand has relocations
            for operand in syntax_operands:
                if operand in instrfield_reloc_map:
                    for reloc_name in instrfield_reloc_map[operand]:
                        if reloc_name not in reloc_instruction_map:
                            reloc_instruction_map[reloc_name] = []
                        if instruction.name not in reloc_instruction_map[reloc_name]:
                            reloc_instruction_map[reloc_name].append(instruction.name)

    return reloc_instruction_map


def matches_relocation_test_file(
    filename: str, relocation_name: str, instruction_name: str
) -> bool:
    """
    Check if a test filename matches the expected pattern for a relocation and instruction.

    Args:
        filename: The test file name
        relocation_name: Name of the relocation
        instruction_name: Name of the instruction

    Returns:
        bool: True if the filename matches the pattern
    """
    expected_pattern = f"{relocation_name}_{instruction_name}.asm"
    return filename == expected_pattern


### Value Generation


def is_pair_register(operand_name: str, instruction: Instruction) -> bool:
    """
    Check if a register operand is part of a pair register by looking for
    the same register appearing both normally and with +1 in inputs/outputs.

    Args:
        operand_name: The name of the operand to check
        instruction: The Instruction object containing inputs and outputs

    Returns:
        True if the register is a pair register, False otherwise
    """
    all_fields = instruction.inputs + instruction.outputs

    # Create regex patterns to match any register type with flexible spacing
    # Pattern for normal register: REGTYPE(operand_name)
    normal_pattern = rf"\w+\({re.escape(operand_name)}\)"

    # Pattern for pair register: REGTYPE(operand_name + 1) or REGTYPE(operand_name+1)
    pair_pattern = rf"\w+\({re.escape(operand_name)}\s*\+\s*1\)"

    has_normal = any(re.search(normal_pattern, field) for field in all_fields)
    has_pair = any(re.search(pair_pattern, field) for field in all_fields)

    return has_normal and has_pair


def get_regfile_values(
    instrfield: InstrField, instruction: Instruction, operand_name: str
) -> List[str]:
    """
    Get enumerated values for a regfile instrfield, filtered by offset/size and pair register constraints.

    Args:
        instrfield: The InstrField object containing enumerated options
        instruction: The Instruction object to check for pair register usage
        operand_name: The name of the operand

    Returns:
        List of enumerated values that fall within the valid range and constraints
    """
    if instrfield.offset is not None and instrfield.size is not None:
        # Calculate the valid range based on offset and size
        start_value = instrfield.offset
        end_value = instrfield.offset + (2**instrfield.size) - 1

        # Filter enumerated values to only include those in the valid range
        valid_values = []
        for option in instrfield.enumerated:
            try:
                # Convert the enumerated name to int to check if it's in range
                enum_int_value = int(option.name)
                if start_value <= enum_int_value <= end_value:
                    # Skip reserved values
                    if option.value.lower() == "reserved":
                        continue
                    # If it's a pair register, only include even values
                    if is_pair_register(operand_name, instruction):
                        if enum_int_value % 2 == 0:
                            valid_values.append(option.value)
                    else:
                        valid_values.append(option.value)
            except ValueError:
                # Skip if op.name is not a valid integer
                continue

        return valid_values
    else:
        # Fallback to all enumerated values if offset/size not defined
        all_values = [op.value for op in instrfield.enumerated]

        # Still check for pair register constraint even without offset/size
        if is_pair_register(operand_name, instruction):
            return [
                op.value
                for op in instrfield.enumerated
                if op.name.isdigit() and int(op.name) % 2 == 0
            ]
        else:
            return all_values


def get_imm_values(
    width: int,
    shift: int,
    sign_extension: int,
    signed: str,
    excluded_values: Optional[Dict[str, Optional[str]]] = None,
    operand_name: str = None,
) -> List[str]:
    """
    Generate test immediate values based on width, shift, signedness and sign extension.

    Args:
        width: Width of the immediate field in bits
        shift: Number of bits to shift the immediate value
        sign_extension: Sign extension bit position (optional)
        signed: String indicating if the immediate is signed ("true"/"false")
        excluded_values: Dictionary of operand names to excluded values (optional)
        operand_name: Name of the operand being processed (optional)

    Returns:
        List[str]: List of hexadecimal string values for testing
    """
    max_power = width + shift - 1
    values = []

    if signed == "true":
        # minimum negative value (two's complement)
        values.append(hex(-(2 ** (max_power))))

    values.append("0x0")

    # powers of two from shift to max_power
    for i in range(shift, max_power):
        values.append(hex(2**i))

    # maximum positive value
    values.append(hex(2**max_power - 2**shift))

    # Add sign extension values if sign_extension is not None
    if sign_extension is not None:
        # Values between (2^sign_ext - 2^(width-1)) and (2^sign_ext - 2^shift)
        start_val = 2**sign_extension - 2 ** (width - 1)
        end_val = 2**sign_extension - 2**shift

        # Add the boundary values if they're not already in the list
        existing_values = [int(v, 16) for v in values]

        if start_val not in existing_values:
            values.append(hex(start_val))
        if end_val not in existing_values:
            values.append(hex(end_val))

    # Filter out excluded values if specified
    if excluded_values and operand_name and operand_name in excluded_values:
        excluded_value = excluded_values[operand_name]
        if excluded_value is not None:
            # Convert excluded value to hex format for comparison
            if excluded_value.startswith("0x"):
                excluded_hex = excluded_value
            else:
                excluded_hex = hex(int(excluded_value))

            # Remove the excluded value if it exists in the list
            values = [v for v in values if v != excluded_hex]

    return values


def get_operand_values_for_instruction(
    instruction: Instruction,
    instrfield_map: Dict[str, InstrField],
    operands: List[str],
) -> Dict[str, str]:
    """
    Get the highest/last values for each operand in an instruction.

    Args:
        instruction: The Instruction object
        instrfield_map: Mapping of field names to InstrField objects
        operands: List of operand names

    Returns:
        Dict mapping operand names to their values
    """
    operand_values = {}

    for operand in operands:
        # For alias instructions, instruction.fields is empty, so just check instrfield_map
        # For regular instructions, check both
        if operand in instrfield_map:
            # Additional check: for regular instructions, verify the field is in instruction.fields
            if instruction.fields and operand not in instruction.fields:
                continue

            instrfield = instrfield_map[operand]

            # For regfile types, get the last enumerated value
            if instrfield.type == "regfile" and instrfield.enumerated:
                values = get_regfile_values(instrfield, instruction, operand)
                if values:
                    operand_values[operand] = values[-1]

            # For immediate types, we'll use placeholder since actual values depend on labels
            elif instrfield.type == "imm":
                operand_values[operand] = (
                    None  # Will be filled in during test generation
                )

    return operand_values


### Reference Calculation


def calculate_instruction_reference(
    fields, instrfield_map, current_line_operand_value_dict, is_alias=False
):
    """
    Calculate the reference value for an instruction based on its fields.

    Args:
        fields: Dictionary of field names to values
        instrfield_map: Dictionary mapping field names to instrfield objects
        current_line_operand_value_dict: Dictionary of operand values from current test line
        is_alias: Boolean indicating if this is for an alias instruction

    Returns:
        int: The calculated reference value
    """
    reference = 0
    old_range_diff = 0
    default_mask = 0xFFFFFFFF

    for field in reversed(fields):
        if field not in instrfield_map:
            continue  # Field not defined in ADL

        field_type = instrfield_map[field].type
        shift = instrfield_map[field].shift or 0
        ranges = instrfield_map[field].ranges

        for i, range_vals in enumerate(reversed(ranges)):
            # Create mask based on instrfield range
            mask_low = default_mask << int(range_vals[1])
            mask_high = default_mask << (int(range_vals[0]) + 1)
            mask = (mask_low ^ mask_high) & default_mask

            # Determine if this is a constant value
            field_value = fields[field]
            is_constant = False

            if is_alias:
                # For alias: check if field value is a constant (int or numeric string)
                is_constant = isinstance(field_value, int) or (
                    isinstance(field_value, str) and field_value.lstrip("-").isdigit()
                )
            else:
                # For regular instruction: constant if field_value is not None
                is_constant = field_value is not None

            if not is_constant:
                # Variable field - look up value from operand dict
                operand_key = field if not is_alias else field_value

                # Registers or register hybrids (e.g. fence)
                if field_type == "regfile" or (
                    field_type == "imm" and instrfield_map[field].enumerated
                ):
                    for enum in instrfield_map[field].enumerated:
                        if (
                            current_line_operand_value_dict.get(operand_key)
                            == enum.value
                        ):
                            result = mask & (int(enum.name) << range_vals[1] >> shift)
                            break
                    else:
                        result = 0
                # Immediates
                elif field_type == "imm":
                    range_diff = int(range_vals[0]) - int(range_vals[1])
                    operand_value = int(
                        current_line_operand_value_dict.get(operand_key, "0"), 16
                    )

                    if i == 0:
                        mask = (
                            (default_mask << shift)
                            ^ (default_mask << (shift + range_diff + 1))
                        ) & default_mask
                        result = ((mask & operand_value) >> shift) << range_vals[1]
                        old_range_diff = range_diff + shift
                    else:
                        mask = (
                            (default_mask << (old_range_diff + 1))
                            ^ (default_mask << (old_range_diff + 2 + range_diff))
                        ) & default_mask
                        result = (
                            (mask & operand_value) >> (old_range_diff + 1)
                        ) << range_vals[1]
                        old_range_diff += range_diff + 1
                else:
                    result = 0
            else:
                # Constants
                result = mask & (int(field_value) << range_vals[1])

            # Concatenate result
            reference |= result

    return reference


### String Processing


def substitute_operand_values(syntax: str, operand_values: dict) -> str:
    """
    Substitute operand placeholders in instruction syntax with actual values.

    Args:
        syntax: The instruction syntax string
        operand_values: Dictionary mapping operand names to their values

    Returns:
        str: The syntax string with operands replaced by their values
    """
    return re.sub(
        r"\b[\w_]+\b",
        lambda m: str(operand_values.get(m.group(0), m.group(0))),
        syntax.split(maxsplit=1)[1],
    )


def get_extension_versions(attributes: str, base_arch: str) -> Dict[str, str]:
    """
    Extract extension versions from attributes string.

    Args:
        attributes: String containing architecture attributes
        base_arch: Base architecture name to split on

    Returns:
        Dict[str, str]: Dictionary mapping extension names to their versions
    """
    base_arch, extensions = attributes.split(base_arch)
    extensions_and_versions = extensions.split("_")

    extension_versions = {}
    for item in extensions_and_versions:
        match = re.search(r"(\D+)(\d+p\d+)", item)
        if match:
            extension_versions[match.group(1)] = match.group(2)
    return extension_versions


def get_mattr_string(instr_attributes: List[str], mattrib: str) -> str:
    """
    Convert instruction attributes into LLVM -mattr string format, filtering only those present in ADL mattrib.

    Args:
        instr_attributes: List of instruction attributes
        mattrib: String containing available mattrib extensions

    Returns:
        str: Comma-separated mattr string (e.g., "+m,+c")
    """
    mattr_extensions = []
    mattrib_entries = mattrib.split(",")

    for attr in instr_attributes:
        ext = attr.lower()
        if ext.startswith("rv32"):
            ext = ext[4:]

        # Check if this attribute exists in any mattrib entry (after removing experimental- prefix)
        for m in mattrib_entries:
            clean_m = m.lstrip("+").removeprefix("experimental-")
            if clean_m == ext:
                mattr_extensions.append(m)
                break  # Found match, stop checking others

    return ",".join(mattr_extensions)


### File Operations


def prepare_encoding_tests_output_folder(
    base_dir: str,
    adl_file_name: str,
    extensions: Optional[List[str]],
    instruction_name: str,
) -> str:
    """
    Create output folder structure for instruction tests.

    Args:
        base_dir: Base directory for output
        adl_file_name: Name of the ADL file (without extension)
        extensions: List of extensions or None for all extensions
        instruction_name: Name of the instruction

    Returns:
        str: Path to the created test output folder
    """
    if extensions is not None:
        folder = os.path.join(
            base_dir,
            f"results_{adl_file_name}",
            f"tests_{'_'.join(extensions)}",
            instruction_name,
        )
    else:
        folder = os.path.join(
            base_dir, f"results_{adl_file_name}", "tests_all", instruction_name
        )
    os.makedirs(folder, exist_ok=True)
    return folder


def prepare_encoding_refs_output_folder(
    base_dir: str, adl_file_name: str, extensions: Optional[List[str]]
) -> str:
    """
    Create output folder structure for reference files.

    Args:
        base_dir: Base directory for output
        adl_file_name: Name of the ADL file (without extension)
        extensions: List of extensions or None for all extensions

    Returns:
        str: Path to the created reference output folder
    """
    if extensions is not None:
        folder = os.path.join(
            base_dir, f"results_{adl_file_name}", f"refs_{'_'.join(extensions)}"
        )
    else:
        folder = os.path.join(base_dir, f"results_{adl_file_name}", "refs_all")
    os.makedirs(folder, exist_ok=True)
    return folder


def prepare_reloc_tests_output_folder(
    base_dir: str,
    adl_file_name: str,
    extensions: Optional[List[str]],
    relocation_name: str,
) -> str:
    """
    Create output folder structure for relocation tests.

    Args:
        base_dir: Base directory for output
        adl_file_name: Name of the ADL file (without extension)
        extensions: List of extensions or None for all extensions
        relocation_name: Name of the relocation

    Returns:
        str: Path to the created relocation test output folder
    """
    if extensions is not None:
        folder = os.path.join(
            base_dir,
            f"reloc_results_{adl_file_name}",
            f"tests_{'_'.join(extensions)}",
            relocation_name,
        )
    else:
        folder = os.path.join(
            base_dir, f"reloc_results_{adl_file_name}", "tests_all", relocation_name
        )
    os.makedirs(folder, exist_ok=True)
    return folder


def prepare_reloc_refs_output_folder(
    base_dir: str, adl_file_name: str, extensions: Optional[List[str]]
) -> str:
    """
    Create output folder structure for relocation reference files.

    Args:
        base_dir: Base directory for output
        adl_file_name: Name of the ADL file (without extension)
        extensions: List of extensions or None for all extensions

    Returns:
        str: Path to the created relocation reference output folder
    """
    if extensions is not None:
        folder = os.path.join(
            base_dir, f"reloc_results_{adl_file_name}", f"refs_{'_'.join(extensions)}"
        )
    else:
        folder = os.path.join(base_dir, f"reloc_results_{adl_file_name}", "refs_all")
    os.makedirs(folder, exist_ok=True)
    return folder


def prepare_fixup_tests_output_folder(
    base_dir: str, adl_file_name: str, extensions: Optional[List[str]]
) -> str:
    """
    Create output folder structure for fixup tests.

    Args:
        base_dir: Base directory for output
        adl_file_name: Name of the ADL file (without extension)
        extensions: List of extensions or None for all extensions

    Returns:
        str: Path to the created fixup test output folder
    """
    if extensions is not None:
        folder = os.path.join(
            base_dir, f"fixup_results_{adl_file_name}", f"tests_{'_'.join(extensions)}"
        )
    else:
        folder = os.path.join(base_dir, f"fixup_results_{adl_file_name}", "tests_all")
    os.makedirs(folder, exist_ok=True)
    return folder


def prepare_fixup_refs_output_folder(
    base_dir: str, adl_file_name: str, extensions: Optional[List[str]]
) -> str:
    """
    Create output folder structure for fixup reference files.

    Args:
        base_dir: Base directory for output
        adl_file_name: Name of the ADL file (without extension)
        extensions: List of extensions or None for all extensions

    Returns:
        str: Path to the created fixup reference output folder
    """
    if extensions is not None:
        folder = os.path.join(
            base_dir,
            f"fixup_results_{adl_file_name}",
            f"refs_{'_'.join(extensions)}",
        )
    else:
        folder = os.path.join(base_dir, f"fixup_results_{adl_file_name}", "refs_all")
    os.makedirs(folder, exist_ok=True)
    return folder
