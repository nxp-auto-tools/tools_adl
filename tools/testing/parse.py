# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from tools.testing import utils
from typing import List, Dict, Optional


def parse_extensions(extensions_list: str) -> List[str]:
    """
    Parse a comma-separated string of extensions into a list.

    Args:
        extensions_list: Comma-separated string of extension names

    Returns:
        List[str]: List of individual extension names
    """

    return extensions_list.split(",")


def parse_encoding_command_line_args() -> utils.EncodingCommandLineArgs:
    """
    Parse and validate command line arguments for the test generation tool.

    Returns:
        CommandLineArgs: Parsed command line arguments as a dataclass
    """
    default_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    parser = argparse.ArgumentParser(
        description="Generate encoding tests based on ADL file and extensions",
        usage="python make_test.py adl_file [--extension <comma-separated_list_of_extensions>] [-o, --output <output_directory>]",
    )
    parser.add_argument("adl_file", type=str, help="path to the adl xml file")
    parser.add_argument(
        "-e",
        "--extension",
        type=parse_extensions,
        help="comma-separated list of extensions",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=default_dir,
        help="create an output directory for specific extensions",
    )
    parser.add_argument(
        "--list", action="store_true", help="display the list of available extensions"
    )

    args = parser.parse_args()

    return utils.EncodingCommandLineArgs(
        adl_file_path=args.adl_file,
        adl_file_name=Path(args.adl_file).name.split(".")[0],
        extensions=args.extension,
        output_dir=args.output,
        display_extensions=args.list,
    )


def parse_relocation_command_line_args() -> utils.RelocationCommandLineArgs:
    """Parse command line arguments for relocation test generation."""
    default_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    parser = argparse.ArgumentParser(
        description="Generate relocation tests from ADL files",
        usage="python make_reloc.py adl_file symbol_max_value [--extension <comma-separated_list_of_extensions>] [-o, --output <output_directory>]",
    )

    parser.add_argument("adl_file", type=str, help="path to the adl xml file")

    parser.add_argument(
        "symbol_max_value",
        type=int,
        help="maximum value for symbol addresses in relocation tests",
    )
    parser.add_argument(
        "-e",
        "--extension",
        type=parse_extensions,
        help="comma-separated list of extensions",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=default_dir,
        help="create an output directory for specific extensions",
    )

    parser.add_argument(
        "--list", action="store_true", help="display the list of available extensions"
    )

    args = parser.parse_args()

    return utils.RelocationCommandLineArgs(
        adl_file_path=args.adl_file,
        symbol_max_value=args.symbol_max_value,
        adl_file_name=Path(args.adl_file).name.split(".")[0],
        extensions=args.extension,
        output_dir=args.output,
        display_extensions=args.list,
    )


def get_cores_element(adl_file: str) -> ET:
    """
    Parses an ADL XML file and retrieves the <cores> element.

    Args:
        adl_file (str): Path to the ADL XML file or a file-like object.

    Returns:
        xml.etree.ElementTree.Element: The <cores> element from the ADL file.

    Raises:
        ValueError: If the <cores> element is missing in the ADL file.
    """

    tree = ET.parse(adl_file)
    root = tree.getroot()

    cores = root.find("cores")
    if cores is None:
        raise ValueError("Missing <cores> element in ADL file")

    return cores


def bit_endianness(cores: ET) -> str:
    """
    Extract bit endianness configuration from the cores element.

    Args:
        cores: The <cores> XML element

    Returns:
        str: Endianness value ("little" or "big")
    """
    for bit_endianness in cores.iter("bit_endianness"):
        endianness = bit_endianness.find("str").text

    return endianness


def asm_config_info(cores: ET) -> tuple[str, str, str]:
    """
    Extracts architecture configuration information from the <cores> XML element.

    Iterates through all <asm_config> elements under the given <cores> element
    and retrieves the text content of the <arch>, <attributes>, and <mattrib> sub-elements.

    Args:
        cores (xml.etree.ElementTree.Element): The <cores> element containing <asm_config> children.

    Returns:
        tuple[str, str, str]: A tuple containing the architecture, attributes, and mattrib strings.

    Raises:
        ValueError: If any of the required sub-elements (<arch>, <attributes>, <mattrib>) are missing,
                    or if no <asm_config> element is found under <cores>.
    """
    for asm_config in cores.iter("asm_config"):
        architecture = asm_config.find("arch/str").text
        attributes = asm_config.find("attributes/str").text
        mattrib = asm_config.find("mattrib/str").text

        if None in (architecture, attributes, mattrib):
            raise ValueError(
                "Missing one of <arch>, <attributes>, or <mattrib> elements in <asm_config>"
            )

        return architecture, attributes, mattrib

    raise ValueError("No <asm_config> element found under <cores>")


def parse_aliases(aliases_elem: ET) -> List[utils.Alias]:
    """
    Parse alias elements from an XML aliases container.

    Args:
        aliases_elem: XML element containing alias definitions

    Returns:
        List[Alias]: List of parsed alias objects
    """
    aliases = []

    for alias_elem in aliases_elem.findall("alias"):
        alias_name = alias_elem.get("name")
        fields = {}

        # Iterate over all descendants of <alias>
        for element in alias_elem.iter():
            field_elem = element.find("field/str")
            value_elem = element.find("value/int")
            if value_elem is None:
                value_elem = element.find("value/str")

            if field_elem is not None and field_elem.text:
                field = field_elem.text.strip()
                value = (
                    value_elem.text.strip()
                    if value_elem is not None and value_elem.text
                    else None
                )
                fields[field] = value

        alias = utils.Alias(name=alias_name, fields=fields)
        aliases.append(alias)

    return aliases


def parse_instructions(cores: ET) -> List[utils.Instruction]:
    """
    Parse instruction elements from the cores XML and create Instruction objects.

    Args:
        cores: The <cores> XML element containing instruction definitions

    Returns:
        List[Instruction]: List of parsed instruction objects
    """
    instructions = []

    for instruction in cores.iter("instruction"):
        name = instruction.get("name")

        width_elem = instruction.find("width/int")
        width = (
            int(width_elem.text) if width_elem is not None and width_elem.text else None
        )

        syntax_elem = instruction.find("syntax/str")
        syntax = syntax_elem.text.strip() if syntax_elem is not None else ""

        dsyntax_elem = instruction.find("dsyntax/str")
        dsyntax = dsyntax_elem.text.strip() if dsyntax_elem is not None else None

        # Multiple attributes under <attributes>
        attributes = []
        for attr_elem in instruction.findall("attributes/attribute"):
            attr_name = attr_elem.get("name")
            if attr_name:
                attributes.append(attr_name)

        # Fields: name and its value as string or int
        fields = {}
        for field_elem in instruction.findall("fields/field"):
            field_name = field_elem.get("name")
            if field_name:
                value = None
                value_elem = field_elem.find("int")
                if value_elem is None:
                    value_elem = field_elem.find("str")
                value = (
                    value_elem.text.strip()
                    if value_elem is not None and value_elem.text is not None
                    else None
                )
                fields[field_name] = value

        # Inputs and outputs
        inputs = [e.text.strip() for e in instruction.findall("inputs/str") if e.text]
        outputs = [e.text.strip() for e in instruction.findall("outputs/str") if e.text]

        # Check if instruction is alias
        aliases_elem = instruction.find("aliases")
        aliases = parse_aliases(aliases_elem) if aliases_elem is not None else None

        # Parse excluded_values
        excluded_values = {}
        excluded_values_elem = instruction.find("excluded_values")
        if excluded_values_elem is not None:
            for option_elem in excluded_values_elem.findall("option"):
                option_name = option_elem.get("name")
                if option_name:
                    str_elem = option_elem.find("str")
                    option_value = (
                        str_elem.text.strip()
                        if str_elem is not None and str_elem.text
                        else None
                    )
                    excluded_values[option_name] = option_value

        instructions.append(
            utils.Instruction(
                name=name,
                width=width,
                syntax=syntax,
                dsyntax=dsyntax,
                attributes=attributes,
                fields=fields,
                inputs=inputs,
                outputs=outputs,
                aliases=aliases,
                excluded_values=excluded_values,
            )
        )

    return instructions


def parse_instrfields(cores: ET) -> List[utils.InstrField]:
    """
    Parse instruction field elements from the cores XML and create InstrField objects.

    Args:
        cores: The <cores> XML element containing instrfield definitions

    Returns:
        List[InstrField]: List of parsed instruction field objects
    """
    instrfields = []

    for field_elem in cores.iter("instrfield"):
        name = field_elem.get("name")

        # Ranges (multiple <range><int>...</int></range> pairs)
        ranges = []
        for range_elem in field_elem.findall("bits/range"):
            ints = [int(e.text) for e in range_elem.findall("int") if e.text]
            if ints:
                ranges.append(ints)

        # Int properties
        def get_int(tag):
            elem = field_elem.find(f"{tag}/int")
            return int(elem.text) if elem is not None and elem.text else None

        width = get_int("width")
        size = get_int("size")
        shift = get_int("shift")
        offset = get_int("offset")
        sign_extension = get_int("sign_extension")

        # String properties
        def get_str(tag):
            elem = field_elem.find(f"{tag}/str")
            return elem.text.strip() if elem is not None and elem.text else None

        mask = get_str("mask")
        addr = get_str("addr")
        display = get_str("display")
        type = get_str("type")
        ref = get_str("ref")
        signed = get_str("signed")

        # An instruction can generate multiple relocations
        reloc = []
        reloc_elem = field_elem.find("reloc")
        if reloc_elem is not None:
            for str_elem in reloc_elem.findall("str"):
                if str_elem.text:
                    reloc.append(str_elem.text.strip())

        # Enumerated options (if any)
        enumerated = []
        for opt_elem in field_elem.findall("enumerated/option"):
            opt_name = opt_elem.get("name")
            opt_value_elem = opt_elem.find("str")
            opt_value = (
                opt_value_elem.text.strip()
                if opt_value_elem is not None and opt_value_elem.text
                else None
            )
            enumerated.append(utils.EnumOption(name=opt_name, value=opt_value))

        instrfields.append(
            utils.InstrField(
                name=name,
                ranges=ranges,
                width=width,
                size=size,
                shift=shift,
                offset=offset,
                sign_extension=sign_extension,
                mask=mask,
                addr=addr,
                display=display,
                type=type,
                ref=ref,
                signed=signed,
                reloc=reloc,
                enumerated=enumerated,
            )
        )

    return instrfields


def parse_relocations(cores: ET) -> List[utils.Relocation]:
    """
    Parse relocation elements from the XML and create Relocation objects.

    Args:
        cores: The <cores> XML element containing relocation definitions

    Returns:
        List[Relocation]: List of parsed relocation objects
    """
    relocations = []

    relocations_elem = cores.find("relocations")
    if relocations_elem is None:
        # Try searching recursively in case it's nested deeper
        relocations_elem = cores.find(".//relocations")

    if relocations_elem is not None:
        for reloc_elem in relocations_elem.findall("reloc"):
            name = reloc_elem.get("name")

            # Parse abbrev
            abbrev_elem = reloc_elem.find("abbrev/str")
            abbrev = (
                abbrev_elem.text.strip()
                if abbrev_elem is not None and abbrev_elem.text
                else ""
            )

            # Parse field_width
            field_width_elem = reloc_elem.find("field_width/int")
            field_width = (
                int(field_width_elem.text)
                if field_width_elem is not None and field_width_elem.text
                else 0
            )

            # Parse pcrel
            pcrel_elem = reloc_elem.find("pcrel/str")
            pcrel = (
                pcrel_elem.text.strip()
                if pcrel_elem is not None and pcrel_elem.text
                else ""
            )

            # Parse value
            value_elem = reloc_elem.find("value/int")
            value = (
                int(value_elem.text)
                if value_elem is not None and value_elem.text
                else 0
            )

            # Parse right_shift
            right_shift_elem = reloc_elem.find("right_shift/int")
            right_shift = (
                int(right_shift_elem.text)
                if right_shift_elem is not None and right_shift_elem.text
                else 0
            )

            # Parse action and clean it
            action_elem = reloc_elem.find("action/str")
            action = ""
            if action_elem is not None and action_elem.text:
                # Remove braces, newlines, spaces, semicolons and extract only the calculation
                raw_action = action_elem.text.strip()
                # Remove outer braces
                raw_action = raw_action.strip("{}")
                # Split by lines and find the line with the calculation (contains '=')
                lines = raw_action.split("\n")
                for line in lines:
                    line = line.strip()
                    if "=" in line and "R" in line:
                        # Remove 'R = ' and trailing semicolon, then strip spaces
                        action = line.replace("R = ", "").rstrip(";").strip()
                        break

            # Parse directive
            directive_elem = reloc_elem.find("directive/str")
            directive = (
                directive_elem.text.strip()
                if directive_elem is not None and directive_elem.text
                else ""
            )

            # Parse dependency (list of strings)
            dependency = []
            dependency_elem = reloc_elem.find("dependency")
            if dependency_elem is not None:
                for str_elem in dependency_elem.findall("str"):
                    if str_elem.text:
                        dependency.append(str_elem.text.strip())

            relocations.append(
                utils.Relocation(
                    name=name,
                    abbrev=abbrev,
                    field_width=field_width,
                    pcrel=pcrel,
                    value=value,
                    right_shift=right_shift,
                    action=action,
                    directive=directive,
                    dependency=dependency,
                )
            )

    return relocations
