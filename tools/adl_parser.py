# Copyright 2024 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package adl_parser
#
# The module which parses the contents of an adl.xml file

# importing element tree
# under the alias of ET
import xml.etree.ElementTree as ET
import registerInfo
import utils
import config
import re
import os

## A dictionary that contains the environment variables listed inside config.txt
config_file = "config.txt"
llvm_config = "llvm_config.txt"
list_dir = list()
for fname in os.listdir("."):
    list_dir.append(fname)
if "tools" in list_dir:
    config_file = "./tools/config.txt"
    llvm_config = "./tools/llvm_config.txt"
config_variables = config.config_environment(config_file, llvm_config)


## Parsing and processing adl.xml file
#
# @param adl_name The name of the adl.xml file (configured inside config.txt)
# @return The register file dictionary (key = name of the regfile, value = ?)
def parse_adl(adl_name):
    # Passing the path of the
    # xml document to enable the
    # parsing process
    tree = ET.parse(adl_name)

    # getting the parent tag of
    # the xml document
    root = tree.getroot()
    registers = dict()

    for core in root.iter("cores"):
        for regclass in core.iter("regfile"):
            attributes = list()
            parameters = dict()
            entries = list()
            entries_synatx = list()
            syntax = list()
            debug_info = dict()
            enumerated_dict = dict()
            register_class = regclass.attrib["name"]
            for regfile in regclass:
                for regclassinfo in regfile:
                    parameters[regfile.tag] = regclassinfo.text
                    for attribute in regclassinfo.iter("attribute"):
                        if attribute[0].text is not None:
                            debug_info[regclassinfo.attrib["name"]] = attribute[0].text
                        attributes.append(attribute.attrib["name"])
                    if regfile.tag == "calling_convention":
                        enumerated_list = [
                            option[0].text for option in regclassinfo.iter("option")
                        ]
                        if regclassinfo.attrib != {}:
                            if (
                                regclassinfo.attrib["name"]
                                not in enumerated_dict.keys()
                            ):
                                enumerated_dict[
                                    regclassinfo.attrib["name"]
                                ] = enumerated_list
                            else:
                                enumerated_dict[
                                    regclassinfo.attrib["name"]
                                ] += enumerated_list
                    for attribute in regclassinfo.iter("entry"):
                        entries.append(attribute.attrib["name"])
                    for syntaxelem in regclassinfo.iter("syntax"):
                        syntax.append(syntaxelem[0].text)
                    parameters["calling_convention"] = enumerated_dict
                    parameters["attributes"] = attributes
                    parameters["entries"] = entries
                    parameters["syntax"] = syntax

            if register_class == "CSR":
                prefix = ""
                attributes = set(attributes)
                alignment = ""
                pseudo = ""
                debug = ""
                if "alignment" in parameters.keys():
                    alignment = parameters["alignment"]
                if "pseudo" in parameters.keys():
                    pseudo = parameters["pseudo"]
                if "debug" in parameters.keys():
                    debug = parameters["debug"].strip()
                calling_convention = parameters["calling_convention"]
                doc_info = parameters["doc"].strip()
                width = parameters["width"].strip()
                size = parameters["size"].strip()
                entries = entries
                syntax = syntax
                shared = parameters["shared"].strip()
                reginfo = registerInfo.RegisterCSR(
                    register_class,
                    doc_info,
                    width,
                    attributes,
                    size,
                    entries,
                    syntax,
                    prefix,
                    shared,
                    None,
                    None,
                    calling_convention,
                    pseudo,
                    debug,
                    alignment,
                )
                registers[register_class] = reginfo
                # print(registers[register_class])

            elif register_class == "GPR":
                attributes = set(attributes)
                pseudo = ""
                alignment = ""
                if "calling_convention" in parameters.keys():
                    calling_convention = parameters["calling_convention"]
                if "pseudo" in parameters.keys():
                    pseudo = parameters["pseudo"]
                if "alignment" in parameters.keys():
                    alignment = parameters["alignment"]
                doc_info = parameters["doc"].strip()
                width = parameters["width"].strip()
                size = parameters["size"].strip()
                prefix = parameters["prefix"].strip()
                shared = parameters["shared"].strip()
                for _, value in enumerate(debug_info.values()):
                    debug = str(value)
                reginfo = registerInfo.RegisterGPR(
                    register_class,
                    doc_info,
                    width,
                    attributes,
                    debug,
                    size,
                    prefix,
                    shared,
                    None,
                    None,
                    calling_convention,
                    pseudo,
                    alignment,
                )
                registers[register_class] = reginfo

            else:
                attributes = set(attributes)
                debug = ""
                prefix = ""
                reserved_mask = ""
                doc_info = ""
                pseudo = ""
                alignment = ""
                shared = ""
                if "alignment" in parameters.keys():
                    alignment = parameters["alignment"]
                if "calling_convention" in parameters.keys():
                    calling_convention = parameters["calling_convention"]
                if "pseudo" in parameters.keys():
                    pseudo = parameters["pseudo"]
                if "debug" in parameters.keys():
                    debug = parameters["debug"]
                for key in parameters.keys():
                    if key == "doc":
                        doc_info = parameters[key].strip()
                    elif key == "width":
                        width = parameters[key].strip()
                    elif key == "size":
                        size = parameters[key].strip()
                    elif key == "prefix":
                        prefix = parameters[key].strip()
                    elif key == "shared":
                        shared = parameters[key].strip()
                    elif key == "reserved_mask":
                        reserved_mask = parameters[key].strip()
                    entries = entries
                    syntax = syntax
                if debug == "":
                    for _, value in enumerate(debug_info.values()):
                        debug = str(value)
                reginfo = registerInfo.RegisterGeneric(
                    register_class,
                    doc_info,
                    width,
                    attributes,
                    size,
                    entries,
                    syntax,
                    debug,
                    prefix,
                    shared,
                    reserved_mask,
                    None,
                    None,
                    calling_convention,
                    pseudo,
                    alignment,
                )
                registers[register_class] = reginfo
                # print(registers[register_class])

        for regclass in core.iter("regs"):
            for regs in regclass:
                parameters = dict()
                attributes = list()
                debug_info = dict()
                entries = list()
                syntax = list()
                register_name = regs.attrib["name"]
                # print(regs.attrib['name'])
                # print(regs.tag, regs.attrib)
                for reg_info in regs:
                    for sub_reg_info in reg_info:
                        for attribute in sub_reg_info.iter("attribute"):
                            if "name" in sub_reg_info.attrib["name"]:
                                debug_info[sub_reg_info.attrib["name"]] = str(
                                    attribute[0].text
                                )
                            attributes.append(attribute.attrib["name"])
                    parameters[reg_info.tag] = sub_reg_info.text
                    parameters["attributes"] = attributes
                    registers[register_name] = parameters
                if bool(attributes):
                    attributes = set(attributes)
                if "calling_convention" in parameters.keys():
                    calling_convention = parameters["calling_convention"]
                if "pseudo" in parameters.keys():
                    pseudo = parameters["pseudo"]
                debug = ""
                prefix = ""
                reserved_mask = ""
                doc_info = ""
                size = ""
                shared = ""
                pseudo = ""
                for key in parameters.keys():
                    if key == "doc":
                        doc_info = parameters[key].strip()
                    elif key == "width":
                        width = parameters[key].strip()
                    elif key == "size":
                        size = parameters[key].strip()
                    elif key == "prefix":
                        prefix = parameters[key].strip()
                    elif key == "shared":
                        shared = parameters[key].strip()
                    elif key == "reserved_mask":
                        reserved_mask = parameters[key].strip()
                if bool(debug_info) is not False:
                    for _, value in enumerate(debug_info.values()):
                        debug = str(value)
                reginfo2 = registerInfo.RegisterGeneric(
                    register_name,
                    doc_info,
                    width,
                    attributes,
                    size,
                    entries,
                    syntax,
                    debug,
                    prefix,
                    shared,
                    reserved_mask,
                    None,
                    None,
                    calling_convention,
                    pseudo,
                    alignment,
                )
                registers[register_name] = reginfo2
    utils.remove_ignored_attrib_regs(registers)
    return registers


## A function that parses and classifies aliases from instruction fields based on 'ref' tag
#
# @param adl_name The name of the adl.xml file (configured inside config.txt)
# @return The alias dictionary (key = name of regfile, value = another dictionary where (key = register name; value = alias name))
def get_alias_for_regs(adl_name):
    tree = ET.parse(adl_name)
    root = tree.getroot()
    alias_dict = dict()
    instrfield_dict = dict()
    instrfield_data = dict()
    for core in root.iter("cores"):
        for instr_field in core.iter("instrfield"):
            instruction_field = instr_field.attrib["name"]
            parameters = dict()
            enumerated_dict = dict()
            list_range = list()
            range_tuples = list()
            for instr in instr_field:
                for elem in instr:
                    parameters[instr.tag] = elem.text
                    if instr.tag == "bits":
                        for instr_bits in instr.iter("range"):
                            for index in range(len(instr_bits)):
                                list_range.append(instr_bits[index].text)
                                if len(list_range) >= 2:
                                    range_tuple = (list_range[0], list_range[1])
                                    if range_tuple not in range_tuples:
                                        range_tuples.append(range_tuple)
                                        list_range.clear()
                    enumerated_list = [option[0].text for option in elem.iter("option")]
                    if elem.attrib != {}:
                        if elem.attrib["name"] not in enumerated_dict.keys():
                            enumerated_dict[elem.attrib["name"]] = enumerated_list
                        else:
                            enumerated_dict[elem.attrib["name"]] += enumerated_list
                parameters["aliases"] = enumerated_dict
                list_tuples_range = list()
                for elem in range_tuples:
                    elem = list(elem)
                    list_tuples_range.append(elem)
                parameters["range"] = list_tuples_range
            instrfield_data[instruction_field] = parameters
            if "ref" in parameters.keys():
                alias_dict[parameters["ref"]] = parameters["aliases"]
                instrfield_dict[instruction_field] = parameters["aliases"]
    return alias_dict


## Parses all instruction fields and takes the offset
#
# @param adl_name The name of the adl.xml file (configured inside config.txt)
# @return  A tuple of 2 dictionaries containing various instruction field information
def get_instrfield_offset(adl_name):
    tree = ET.parse(adl_name)
    root = tree.getroot()
    alias_dict = dict()
    instrfield_dict = dict()
    instrfield_data = dict()
    instrfield_data_ref = dict()
    instrfield_offset = dict()
    for core in root.iter("cores"):
        for instr_field in core.iter("instrfield"):
            instruction_field = instr_field.attrib["name"]
            # print(instruction_field)
            parameters = dict()
            enumerated_dict = dict()
            exclude_values = dict()
            for instr in instr_field:
                for elem in instr:
                    parameters[instr.tag] = elem.text
                    if instr.tag == "enumerated":
                        enumerated_list = [
                            option[0].text for option in elem.iter("option")
                        ]
                        if elem.attrib != {}:
                            if elem.attrib["name"] not in enumerated_dict.keys():
                                enumerated_dict[elem.attrib["name"]] = enumerated_list
                            else:
                                enumerated_dict[elem.attrib["name"]] += enumerated_list
                    if instr.tag == "excluded_values":
                        enumerated_list = [
                            option[0].text for option in elem.iter("option")
                        ]
                        if elem.attrib != {}:
                            if elem.attrib["name"] not in exclude_values.keys():
                                exclude_values[elem.attrib["name"]] = enumerated_list
                            else:
                                exclude_values[elem.attrib["name"]] += enumerated_list
                if instr.tag == "enumerated":
                    parameters["enumerated"] = enumerated_dict
                if instr.tag == "excluded_values":
                    parameters["excluded_values"] = exclude_values
            instrfield_data[instruction_field] = parameters
            if "ref" in parameters.keys():
                if "enumerated" in parameters.keys():
                    alias_dict[parameters["ref"]] = parameters["enumerated"]
                    instrfield_dict[instruction_field] = parameters["enumerated"]
    for key in instrfield_data.keys():
        if "ref" in instrfield_data[key].keys():
            instrfield_data_ref[key] = instrfield_data[key]
    instrfield_offset = utils.get_instrfield_offset(instrfield_data_ref)
    return instrfield_offset, instrfield_data_ref


## This function parses all instruction fields and sort them based on their type: instruction fields
# with reference defined or imms/constants
# @param adl_name The name of the adl.xml file (configured inside config.txt)
# @return A tuple of 2 dictionaries which contain all instruction fields sorted on the criteria mention above
def get_instrfield_from_adl(adl_name):
    tree = ET.parse(adl_name)
    root = tree.getroot()
    instrfield_dict = dict()
    instrfield_data_ref = dict()
    instrfield_data_imm = dict()
    for core in root.iter("cores"):
        for instr_field in core.iter("instrfield"):
            instruction_field = instr_field.attrib["name"]
            parameters = dict()
            enumerated_dict = dict()
            list_range = list()
            range_tuples = list()
            for instr in instr_field:
                for elem in instr:
                    parameters[instr.tag] = elem.text
                    if instr.tag == "bits":
                        for instr_bits in instr.iter("range"):
                            for index in range(len(instr_bits)):
                                list_range.append(instr_bits[index].text)
                                if len(list_range) >= 2:
                                    range_tuple = (list_range[0], list_range[1])
                                    if range_tuple not in range_tuples:
                                        range_tuples.append(range_tuple)
                                        list_range.clear()
                    enumerated_list = [option[0].text for option in elem.iter("option")]
                    if elem.attrib != {}:
                        if elem.attrib["name"] not in enumerated_dict.keys():
                            enumerated_dict[elem.attrib["name"]] = enumerated_list
                        else:
                            enumerated_dict[elem.attrib["name"]] += enumerated_list
                parameters["aliases"] = enumerated_dict
                list_tuples_range = list()
                for elem in range_tuples:
                    elem = list(elem)
                    list_tuples_range.append(elem)
                parameters["range"] = list_tuples_range
            if "ref" in parameters.keys():
                instrfield_data_ref[instruction_field] = parameters
            else:
                instrfield_data_imm[instruction_field] = parameters
    return instrfield_data_imm, instrfield_data_ref


## This function parses all the instruction found in ADL file
#
# @param adl_name The name of the adl.xml file (configured inside config.txt)
# @return A tuple of a dictionary and a list. The dictionary contains all the instructions parsed from ADL file, while
# the list contains only the instructions which use registers and constants. Sorting_attributes list contains all the attributes
# found in instructions definitions from ADL file.
def parse_instructions_from_adl(adl_name):
    instrfield_imm = get_instrfield_from_adl(adl_name)[0]
    instrfield_ref = get_instrfield_from_adl(adl_name)[1]
    tree = ET.parse(adl_name)
    root = tree.getroot()
    instructions = dict()
    sorting_attributes = list()
    for core in root.iter("cores"):
        for instr in core.iter("instruction"):
            attributes = list()
            list_fields = list()
            instruction = instr.attrib["name"]
            parameters = dict()
            list_inputs = list()
            intrinsic_args_list = list()
            list_outputs = list()
            fields = dict()
            syntax_list = list()
            dsyntax_list = list()
            enumerated_dict = dict()
            args_dict = dict()
            intrinsic_parsed = False
            for instruction_info in instr:
                for elem in instruction_info:
                    parameters[instruction_info.tag] = elem.text
                    if instruction_info.tag == "syntax":
                        x = re.split(r"[, ]", elem.text)
                        syntax_list.extend(x)
                    if instruction_info.tag == "dsyntax":
                        x = re.split(r"[, ]", elem.text)
                        dsyntax_list.extend(x)
                    if instruction_info.tag == "inputs":
                        for instr_ins in instr.iter("inputs"):
                            for index in range(len(instr_ins)):
                                list_inputs.append(instr_ins[index].text)
                    if instruction_info.tag == "intrinsic_args":
                        for intrinsic_args in instr.iter("intrinsic_args"):
                            for index in range(len(intrinsic_args)):
                                if intrinsic_parsed is False:
                                    intrinsic_args_list.append(
                                        intrinsic_args[index].text
                                    )
                        intrinsic_parsed = True
                    if instruction_info.tag == "outputs":
                        for instr_outs in instr.iter("outputs"):
                            for index in range(len(instr_outs)):
                                list_outputs.append(instr_outs[index].text)
                    if instruction_info.tag == "excluded_values":
                        enumerated_list = [
                            option[0].text for option in elem.iter("option")
                        ]
                        if elem.attrib != {}:
                            if elem.attrib["name"] not in enumerated_dict.keys():
                                if len(enumerated_list) > 0:
                                    enumerated_dict[
                                        elem.attrib["name"]
                                    ] = enumerated_list
                            else:
                                if len(enumerated_list) > 0:
                                    enumerated_dict[
                                        elem.attrib["name"]
                                    ] += enumerated_list
                            parameters["excluded_values"] = enumerated_dict
                    if instruction_info.tag == "intrinsic_type":
                        args_list = [
                            option[0].text
                            for option in elem.iter("instrfield_intrinsic")
                        ]
                        if elem.attrib != {}:
                            if elem.attrib["name"] not in args_dict.keys():
                                if len(args_list) > 0:
                                    args_dict[elem.attrib["name"]] = args_list
                            else:
                                if len(args_list) > 0:
                                    args_dict[elem.attrib["name"]] += args_list
                            parameters["intrinsic_type"] = args_dict
                    for attribute in instruction_info.iter("attribute"):
                        if "name" in attribute.attrib.keys():
                            attributes.append(attribute.attrib["name"])
                    for field in instruction_info.iter("field"):
                        if "name" in field.attrib.keys():
                            if field[0].text is not None:
                                fields[field.attrib["name"]] = field[0].text
                            else:
                                if field.attrib["name"] in instrfield_ref.keys():
                                    fields[field.attrib["name"]] = "reg"
                                elif field.attrib["name"] in instrfield_imm.keys():
                                    fields[field.attrib["name"]] = "imm"
            list_fields.insert(len(list_fields), fields)
            parameters["syntax"] = syntax_list
            parameters["dsyntax"] = dsyntax_list
            parameters["attributes"] = list(set(attributes))
            for attribute in parameters["attributes"]:
                if attribute not in sorting_attributes:
                    sorting_attributes.append(attribute)
            parameters["fields"] = list(list_fields)
            parameters["intrinsic_args"] = list(intrinsic_args_list)
            parameters["inputs"] = list(set(list_inputs))
            parameters["outputs"] = list(set(list_outputs))
            if (
                config_variables["InstructionIgnoredAttrib"]
                not in parameters["attributes"]
            ):
                instructions[instruction] = parameters
    list_instructions_with_regs = list()
    list_instructions_imms = list()
    for key in instructions.keys():
        if (
            "imm" not in instructions[key]["fields"][0].values()
            and len(instructions[key]["fields"][0].values()) != 0
        ):
            list_instructions_with_regs.append(key)
        elif (
            "imm" in instructions[key]["fields"][0].values()
            and len(instructions[key]["fields"][0].values()) != 0
        ):
            list_instructions_imms.append(key)
    return (
        instructions,
        list_instructions_with_regs,
        list_instructions_imms,
        sorting_attributes,
    )


## This function will parsed all information about aliases from an ADL file given as parameter
#
# @param adl_name This argument represents the ADL file from which the information will be parsed
# @return The function will return the dictionary containing all information parsed from ADL file
def parse_instructions_aliases_from_adl(adl_name):
    instrfield_imm = get_instrfield_from_adl(adl_name)[0]
    instrfield_ref = get_instrfield_from_adl(adl_name)[1]
    tree = ET.parse(adl_name)
    root = tree.getroot()
    instructions_aliases = dict()
    for core in root.iter("cores"):
        for instr in core.iter("instruction"):
            attributes = list()
            aliases = list()
            list_fields = list()
            instruction = instr.attrib["name"]
            parameters = dict()
            list_inputs = list()
            list_outputs = list()
            fields = dict()
            syntax_list = list()
            dsyntax_list = list()
            miscs = dict()
            args_dict = dict()
            intrinsic_args_list = list()
            for instruction_info in instr:
                for elem in instruction_info:
                    parameters[instruction_info.tag] = elem.text
                    if instruction_info.tag == "syntax":
                        x = re.split(r"[, ]", elem.text)
                        syntax_list.extend(x)
                    if instruction_info.tag == "dsyntax":
                        x = re.split(r"[, ]", elem.text)
                        dsyntax_list.extend(x)
                    if instruction_info.tag == "inputs":
                        for instr_ins in instr.iter("inputs"):
                            for index in range(len(instr_ins)):
                                list_inputs.append(instr_ins[index].text)
                    if instruction_info.tag == "outputs":
                        for instr_outs in instr.iter("outputs"):
                            for index in range(len(instr_outs)):
                                list_outputs.append(instr_outs[index].text)
                    if instruction_info.tag == "intrinsic_args":
                        for intrinsic_args in instr.iter("intrinsic_args"):
                            for index in range(len(intrinsic_args)):
                                intrinsic_args_list.append(intrinsic_args[index].text)
                    for attribute in instruction_info.iter("attribute"):
                        if "name" in attribute.attrib.keys():
                            attributes.append(attribute.attrib["name"])
                    for alias in instruction_info.iter("alias"):
                        if "name" in alias.attrib.keys():
                            aliases.append(alias.attrib["name"])
                    if instruction_info.tag == "intrinsic_type":
                        args_list = [
                            option[0].text
                            for option in elem.iter("instrfield_intrinsic")
                        ]
                        if elem.attrib != {}:
                            if elem.attrib["name"] not in args_dict.keys():
                                if len(args_list) > 0:
                                    args_dict[elem.attrib["name"]] = args_list
                            else:
                                if len(args_list) > 0:
                                    args_dict[elem.attrib["name"]] += args_list
                            parameters["intrinsic_type"] = args_dict
                if instruction_info.tag == "aliases":
                    fields = {}
                    stack = [(instruction_info, fields)]
                    while stack:
                        elem, current_dict = stack.pop()
                        for child in elem:
                            if len(child) == 0:
                                current_dict[child.tag] = (
                                    child.text.strip() if child.text else ""
                                )
                            else:
                                if child.tag not in current_dict:
                                    current_dict[child.tag] = []
                                new_dict = {}
                                current_dict[child.tag].append(new_dict)
                                stack.append((child, new_dict))
                    for key, value in fields.items():
                        for item in value:
                            if "field" in item and "value" in item:
                                field_name = item["field"]
                                field_value = item["value"]
                                miscs[field_name] = field_value
                    for field in instruction_info.iter("field"):
                        if "name" in field.attrib.keys():
                            if field[0].text is not None:
                                fields[field.attrib["name"]] = field[0].text
                            else:
                                if field.attrib["name"] in instrfield_ref.keys():
                                    fields[field.attrib["name"]] = "reg"
                                elif field.attrib["name"] in instrfield_imm.keys():
                                    fields[field.attrib["name"]] = "imm"
            list_fields.insert(len(list_fields), fields)
            parameters["syntax"] = syntax_list
            parameters["dsyntax"] = dsyntax_list
            parameters["attributes"] = list(set(attributes))
            if len(aliases) > 0:
                parameters["aliases"] = list(set(aliases))
            parameters["fields"] = list(list_fields)
            parameters["inputs"] = list(set(list_inputs))
            parameters["outputs"] = list(set(list_outputs))
            parameters["intrinsic_args"] = list(set(intrinsic_args_list))
            if (
                config_variables["InstructionIgnoredAttrib"]
                not in parameters["attributes"]
            ):
                if "aliases" in parameters.keys():
                    instructions_aliases[instruction] = parameters
    return instructions_aliases


## This function will parsed the information describing the registers containing subregisters. it saves the subregisters
# description for a register
#
# @param adl_name This argument represents the ADL file from which the information will be parsed
# @return The function will generate a dictionary containing all the information
def parse_registers_subregs(adl_name):
    tree = ET.parse(adl_name)
    root = tree.getroot()
    registers = dict()
    for core in root.iter("cores"):
        for register in core.iter("regfile"):
            xml_dict = {}
            register_name = register.attrib["name"]
            xml_dict["register_name"] = register_name
            for element in register:
                if element.tag == "doc":
                    xml_dict[element.tag] = element[0].text.strip()
                elif element.tag == "width":
                    xml_dict[element.tag] = int(element[0].text)
                elif element.tag == "fields":
                    fields_dict = {}
                    for field_element in element:
                        field_name = field_element.attrib["name"]
                        field_dict = {}
                        for sub_element in field_element:
                            if sub_element.tag == "doc":
                                field_dict[sub_element.tag] = sub_element[
                                    0
                                ].text.strip()
                            elif sub_element.tag == "bits":
                                bits_dict = {}
                                for sub_sub_element in sub_element:
                                    if sub_sub_element.tag == "range":
                                        values = [
                                            int(value.text) for value in sub_sub_element
                                        ]
                                        bits_dict[sub_sub_element.tag] = values
                                field_dict[sub_element.tag] = bits_dict
                        fields_dict[field_name] = field_dict
                    xml_dict[element.tag] = fields_dict
                elif element.tag == "attributes":
                    attributes_dict = {}
                    for attribute_element in element:
                        attribute_name = attribute_element.attrib["name"]
                        attribute_list = list()
                        for sub_element in attribute_element:
                            str_element = sub_element.find("str")
                            if str_element is not None:
                                attribute_list.append(sub_element.tag)
                        attributes_dict[attribute_name] = attribute_list
                    xml_dict[element.tag] = attributes_dict
                elif element.tag == "shared":
                    xml_dict[element.tag] = element.text
            registers[register_name] = xml_dict
    return registers


def parse_relocations(adl_name):
    tree = ET.parse(adl_name)
    root = tree.getroot()
    reloc_data = dict()
    for core in root.iter("cores"):
        for reloc_core in core.iter("relocations"):
            for instr_field in reloc_core.iter("reloc"):
                reloc_name = instr_field.attrib["name"]
                parameters = dict()
                for instr in instr_field:
                    for elem in instr:
                        parameters[instr.tag] = elem.text
                reloc_data[reloc_name] = parameters
    return reloc_data
