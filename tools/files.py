# Copyright 2024 NXP
# SPDX-License-Identifier: BSD-2-Clause
# @package files
#
# The module which writes information about registers inside ReigsterInfo.td file
import math
import utils
import config
import adl_parser
import re
import legalDisclaimer
import num2words
import os
import numpy as np
import shutil
import make_td
import xml.etree.ElementTree as ET

config_file = "config.txt"
llvm_config = "llvm_config.txt"
list_dir = list()
for fname in os.listdir("."):
    list_dir.append(fname)
if "tools" in list_dir:
    config_file = "./tools/config.txt"
    llvm_config = "./tools/llvm_config.txt"

## A dictionary where the key represents the register file and the value are the associated registers
registers_define = dict()

## A dictionary which contains all the register classes defined, including subclasses and all the instruction fields
# for a given register class
register_classes = dict()

## A dictionary which contains all the instruction fields classes that have to be defined in RISCVOperands.td together
# with all the instruction fields reference by a certain class.
instrfield_classes = dict()

## A dictionary which contains alias information which are used for developing
alias_instruction_syntax_dict = dict()

## A dictionary containing all instructions that have load/store attributes defined in the ADL file
instructions_load_store = dict()

## A dictionary which contains all the register references
register_references = list()

## A dictionary which contains all the register pairs generated
register_pairs = dict()


## Function for generating define content
#
# @param define_key Key of def method
# @param define_value Value of def method
# @return A string representing the method
def generate_define(define_key, define_value):
    content = "def " + define_key + " : " + define_value + ";"
    return content


## Function for generating the SP register class
#
# @param register_aliases A dictionary composed of registers and their aliases
# @param class_name Name of the register class
# @param namespace Core family identifier - i.e RISCV
# @param width Register width in bits
# @param XLenVT Register XLenVT value
# @param XLenRI Register XLenRI value
# @return The string representing SP register class from RegisterInfo.td
def generate_SP_register_class(
    register_aliases, class_name, namespace, width, XLenVT, XLenRI
):
    comment = "//Register Class SP : Stack Pointer Register Class.\n"
    config_variables = config.config_environment(config_file, llvm_config)
    class_name = str.upper(class_name)
    class_name = class_name.replace("[", "")
    class_name = class_name.replace("]", "")
    class_name = class_name.replace('"', "")
    sp_key = ""
    for key in register_aliases.keys():
        if "sp" in str(register_aliases[key]):
            sp_key = key
    statement = (
        "def "
        + class_name
        + " : "
        + "RegisterClass<"
        + '"'
        + namespace
        + '"'
        + ", "
        + "["
        + config_variables["XLenVT_key"]
        + "]"
        + ", "
        + width
        + ", ("
    )
    content = "add" + " "
    content += sp_key + ")> {\n"
    let = "\tlet RegInfos = " + config_variables["XLenRI_key"] + ";\n"
    def_class = comment + statement + content + let + "}"
    list_reg = list()
    register_alias_sp = register_aliases[sp_key]
    register_alias_sp = register_alias_sp.replace('["', "")
    register_alias_sp = register_alias_sp.replace('"]', "")
    list_reg.append(register_alias_sp)
    register_classes[class_name] = list_reg
    register_references.append(class_name)
    return def_class


## Function for generating namespace
#
# @param namespace Core family identifier - i.e RISCV
# @return The definition of the namespace
def generate_namespace(namespace):
    define_namespace = "let Namespace =" + ' "' + namespace + '" ' + "in { \n"
    return define_namespace


## Function for generating the namespace
#
# @param class_name Name of the register class
# @param register_width Register width in bits
# @param subregs_enabled Specifies if a register class implements subregs or not (True/False value accepted)
# @return The string representing register class definition from RegisterInfo.td
def generate_register_class(class_name, register_width, subregs_enabled):
    width = int(math.log2(int(register_width)))
    class_statement = "class " + class_name + "<"
    if subregs_enabled is True:
        parameters = (
            "bits<"
            + str(width)
            + "> Enc, string n, list<Register> subregs, list<string> alt = []> : RegisterWithSubRegs<n, subregs> {\n"
        )
    else:
        parameters = (
            "bits<"
            + str(width)
            + "> Enc, string n, list<string> alt = []> : Register<n> {\n"
        )
    class_content = ""
    HWEncoding = "\tlet HWEncoding{" + str(width - 1) + "-" + str(0) + "} = Enc;\n"
    AltNames = "\tlet AltNames = alt;\n"
    class_content = class_content + HWEncoding + AltNames + "}"
    register_class_generated = class_statement + parameters + class_content
    return register_class_generated


## Function for generating the GPR register file
#
# @param name Define name
# @param reg_class Name of the register class
# @param class_name Name of the register class
# @param prefix Register prefix value
# @param dwarf Register debug info
# @param size Register size in bits
# @param alias_dict A dictionary where each register has its alias associated
# @return A tuple composed of a string and a dictionary
def generate_registers_by_prefix(
    name, reg_class, class_name, prefix, dwarf, size, alias_dict
):
    let_name = "let RegAltNameIndices = [" + name + "] in {\n"
    additional_register_classes = dict()
    config_variables = config.config_environment(config_file, llvm_config)
    subregs_def = ""
    registers_subregs = adl_parser.parse_registers_subregs(config_variables["ADLName"])
    list_subregs_alias = list()
    list_subregs = list()
    let_subregs = ""
    if "fields" in registers_subregs[reg_class.upper()].keys():
        fields = registers_subregs[reg_class.upper()]["fields"]
        f = open(config_variables["RegisterInfoFile"], "a")
        class_definition = False
        for field_key in fields:
            if "bits" in fields[field_key].keys():
                range_list = fields[field_key]["bits"]["range"]
                range_list.sort()
                offset_subregs = range_list[0]
                size_subregs = range_list[1] - range_list[0] + 1
                dwarf_index = dwarf
                if offset_subregs == 0:
                    list_subregs_alias.append(field_key.lower() + "_sub")
                    subregs_def += (
                        "def "
                        + field_key.lower()
                        + "_sub"
                        + " : "
                        + "SubRegIndex<"
                        + str(size_subregs)
                        + ">;\n"
                    )
                else:
                    list_subregs_alias.append(field_key.lower() + "_sub")
                    subregs_def += (
                        "def "
                        + field_key.lower()
                        + "_sub"
                        + " : "
                        + "SubRegIndex<"
                        + str(size_subregs)
                        + ", "
                        + str(offset_subregs)
                        + ">;\n"
                    )
                subregs_definition = ""
                subregs_def += let_name
                if class_definition is False:
                    class_definition = True
                for i in range(size):
                    if dwarf_index != "":
                        dwarf_index = int(dwarf_index)
                    definition = (
                        "def " + prefix + str(i) + "_" + field_key.lower() + " : "
                    )
                    alias = '["' + prefix + str(i) + "_" + field_key.lower() + '"]'
                    register_class = (
                        class_name
                        + str(size_subregs)
                        + "<"
                        + str(i)
                        + ", "
                        + '"'
                        + prefix
                        + str(i)
                        + "_"
                        + field_key.lower()
                        + '"'
                        + ", "
                        + alias
                        + ">, "
                    )
                    dwarf_info = (
                        "DwarfRegNum<[" + str(dwarf_index).replace("'", "") + "]>;"
                    )
                    if dwarf_index != "":
                        dwarf_index += 1
                    subregs_definition += (
                        "\t" + definition + register_class + dwarf_info + "\n"
                    )
                    list_subregs.append(prefix + str(i) + "_" + field_key.lower())
                subregs_def += subregs_definition + "}\n"
                subregs_def += "\n"
                additional_register_classes[class_name + str(size_subregs)] = size
    dwarf_index = dwarf
    registers_generated = let_name
    registers = list()
    registers_aliases = dict()
    first_print = False
    for i in range(size):
        if dwarf_index != "":
            dwarf_index = int(dwarf_index)
        define_register = "def " + str.upper(prefix) + str(i) + " : "
        if (
            str.upper(reg_class) in alias_dict.keys()
            and str(i) in alias_dict[str.upper(reg_class)].keys()
        ):
            if (prefix + str(i)) in alias_dict[str.upper(reg_class)][str(i)]:
                alias_dict[str.upper(reg_class)][str(i)].remove(prefix + str(i))
            alias_register = alias_dict[str.upper(reg_class)][str(i)]
            alias = str(alias_dict[str.upper(reg_class)][str(i)])
            alias = alias.replace("'", '"')
            subreg_found = False
            subreg_list = list()
            for element in list_subregs:
                if (prefix + str(i)).lower() == element.split("_")[0]:
                    subreg_list.append(element)
                    subreg_found = True
            if (
                "RegisterClassSubRegs_" + reg_class.upper() in config_variables.keys()
                and len(list_subregs_alias) != 0
            ):
                class_name = config_variables[
                    "RegisterClassSubRegs_" + reg_class.upper()
                ]
            register_class = (
                class_name
                + "<"
                + str(i)
                + ", "
                + '"'
                + prefix
                + str(i)
                + '"'
                + ", "
                + str(subreg_list).replace("'", "")
                + ", "
                + alias
                + ">, "
            )
            if subreg_found is False:
                register_class = (
                    class_name
                    + "<"
                    + str(i)
                    + ", "
                    + '"'
                    + prefix
                    + str(i)
                    + '"'
                    + ", "
                    + alias
                    + ">, "
                )
            dwarf_info = "DwarfRegNum<[" + str(dwarf_index).replace("'", "") + "]>;"
            registers.append(str.upper(prefix) + str(i))
            if "sp" in alias:
                registers_aliases[str.upper(prefix) + str(i)] = alias
            register = define_register + register_class + dwarf_info
            if dwarf_index != "":
                dwarf_index += 1
            if len(list_subregs_alias) != 0:
                let_subregs = (
                    "let SubRegIndices = "
                    + str(list_subregs_alias).replace("'", "")
                    + " in {"
                )
            if let_subregs != "":
                if first_print is False:
                    registers_generated += (
                        "\t" + let_subregs + "\n" + "\t\t" + register + "\n"
                    )
                    first_print = True
                else:
                    registers_generated += "\t\t" + register + "\n"
            else:
                registers_generated += "\t" + register + "\n"
    if let_subregs != "":
        registers_generated += "\t}\n}"
    else:
        registers_generated += "\n}"
    if subregs_def != "":
        registers_generated = subregs_def + registers_generated
    registers_define[reg_class] = registers
    return registers_generated, registers_aliases, additional_register_classes


## Function for generating the CSR or other generic register file
#
# @param name Define name
# @param reg_class Register class name
# @param class_name Register type
# @param entry Register entry value
# @param syntax Register syntax value
# @param start_index Register start_index value
# @param alias_dict A dictionary where each register has its alias associated
# @return The string representing CSR or other generic register file
def generate_registers_by_name(
    name, reg_class, class_name, entry, syntax, start_index, alias_dict
):
    config_variables = config.config_environment(config_file, llvm_config)
    registers_subregs = adl_parser.parse_registers_subregs(config_variables["ADLName"])
    let_name = "let RegAltNameIndices = [" + name + "] in {\n"
    registers_generated = ""
    subregs_def = ""
    registers = list()
    regs_list = list()
    subregs_altname = dict()
    for i in range(len(entry)):
        if str(reg_class).upper() in alias_dict.keys():
            if entry[i] in alias_dict[str.upper(reg_class)].keys():
                alias_print = str(alias_dict[str.upper(reg_class)][entry[i]])
                if alias_print != "[None]":
                    alias = str(alias_dict[str.upper(reg_class)][entry[i]][0])
                    regs_list.append(alias)
    for i in range(len(entry)):
        list_subregs_alias = list()
        let_subregs = ""
        class_name_subregs = ""
        register_class = ""
        subregs = list()
        dwarf_index = int(start_index) + int(entry[i])
        list_size = 0
        if str(reg_class).upper() in alias_dict.keys():
            list_size = len(alias_dict[str.upper(reg_class)][entry[i]])
            alias_list = alias_dict[str.upper(reg_class)][entry[i]]
            alias_print = str(alias_dict[str.upper(reg_class)][entry[i]])
            if alias_print != "[None]":
                check = True
                alias = str(alias_dict[str.upper(reg_class)][entry[i]][0])
                alias = alias.replace("'", "")
                define_register = "def " + syntax[i] + " : "
                if list_size >= 1:
                    if alias.upper() in registers_subregs.keys():
                        if "fields" in registers_subregs[alias.upper()].keys():
                            fields = registers_subregs[alias.upper()]["fields"].keys()
                            for field in fields:
                                if field.lower() not in regs_list:
                                    check = False
                                    break
                            if check is True:
                                for key_alias in alias_dict[
                                    str.upper(reg_class)
                                ].keys():
                                    if alias_dict[str.upper(reg_class)][key_alias][
                                        0
                                    ] is not None and alias_dict[str.upper(reg_class)][
                                        key_alias
                                    ][
                                        0
                                    ].upper() in list(
                                        fields
                                    ):
                                        subregs.append(syntax[int(key_alias) - 1])
                                        subregs_altname[
                                            syntax[int(key_alias) - 1]
                                        ] = alias_dict[str.upper(reg_class)][key_alias][
                                            0
                                        ]
                                class_name_subregs = config_variables[
                                    "RegisterClassSubRegs_" + str(reg_class).upper()
                                ]
                    if class_name_subregs != "":
                        register_class = (
                            class_name_subregs
                            + "<"
                            + entry[i]
                            + ", "
                            + '"'
                            + alias
                            + '", '
                            + str(subregs).replace("'", "")
                            + ", "
                            + '["'
                            + alias
                            + '"]'
                            ">, "
                        )
                    else:
                        register_class = (
                            class_name
                            + "<"
                            + entry[i]
                            + ", "
                            + '"'
                            + alias
                            + '", '
                            + '["'
                            + alias
                            + '"]'
                            ">, "
                        )
                dwarf_info = "DwarfRegNum<[" + str(dwarf_index) + "]>;"
                registers.append(syntax[i])
                register = define_register + register_class + dwarf_info
                for subreg in subregs:
                    key_subreg = subregs_altname[subreg].upper()
                    range_list = registers_subregs[alias.upper()]["fields"][key_subreg][
                        "bits"
                    ]["range"]
                    range_list.sort()
                    offset_subregs = range_list[0]
                    size_subregs = range_list[1] - range_list[0] + 1
                    if offset_subregs == 0:
                        list_subregs_alias.append(key_subreg.lower() + "_sub")
                        subregs_def += (
                            "def "
                            + key_subreg.lower()
                            + "_sub"
                            + " : "
                            + "SubRegIndex<"
                            + str(size_subregs)
                            + ">;\n"
                        )
                    else:
                        list_subregs_alias.append(key_subreg.lower() + "_sub")
                        subregs_def += (
                            "def "
                            + key_subreg.lower()
                            + "_sub"
                            + " : "
                            + "SubRegIndex<"
                            + str(size_subregs)
                            + ", "
                            + str(offset_subregs)
                            + ">;\n"
                        )
                if len(list_subregs_alias) != 0:
                    let_subregs = (
                        "let SubRegIndices = "
                        + str(list_subregs_alias).replace("'", "")
                        + " in {"
                    )
                if let_subregs != "":
                    registers_generated += (
                        "\t" + let_subregs + "\n" + "\t\t" + register + "\n" + "\t}\n"
                    )
                else:
                    registers_generated += "\t" + register + "\n"
    registers_generated += "}"
    registers_define[reg_class] = registers
    return subregs_def + let_name + registers_generated


## Function for generating a register class
#
# @param class_name CSR GPR with their respective offsets
# @param config_variables  A dictionary where key and value are the contents of config_file
# @param namespace Core family identifier - i.e RISCV
# @param registers_list The list of registers inside a register file
# @param width Register width in bits
# @param XLenVT Register XLenVT value
# @param XLenRI Register XLenRI value
# @param offset Register offset value
# @param instrfield_width Register width from instrfield in bits
# @param shift Register shift value
# @param excluded_values Specifies if a register cannot take a certain value
# @return A register class
def define_register_class(
    class_name,
    config_variables,
    namespace,
    registers_list,
    width,
    XLenVT,
    XLenRI,
    offset,
    instrfield_width,
    shift,
    excluded_values,
):
    config_variables = config.config_environment(config_file, llvm_config)
    registers_parsed = adl_parser.parse_adl(config_variables["ADLName"])
    ref = class_name
    calling_convention_order = config_variables["RegisterAllocationOrder"]
    if offset != "0":
        class_name = class_name + "_" + offset
    if str(excluded_values).upper() in registers_list:
        class_name += "No" + str(excluded_values)
    if "alias" + class_name in config_variables.keys():
        class_name = config_variables["alias" + class_name]
    statement = (
        "def "
        + class_name
        + " : "
        + "RegisterClass<"
        + '"'
        + namespace
        + '"'
        + ", "
        + "["
        + config_variables["XLenVT_key"]
        + "]"
        + ", "
        + width
        + ", ("
        + "\n"
        + "\t"
    )
    content = "add" + " "
    register_allocation = ""
    first_dump = False
    index = 0
    first = int(offset)
    last = int(offset) + int(instrfield_width)
    if str(excluded_values).upper() in registers_list:
        registers_list.remove(str(excluded_values).upper())
    registers_list = registers_list[first:last]
    for elem in calling_convention_order:
        if ref in elem.keys():
            for calling_convention_seq in elem[ref]:
                index += 1
                reg_list = ""
                if registers_parsed[ref].calling_convention != {}:
                    for register in registers_parsed[ref].calling_convention.keys():
                        position = 0
                        if (
                            calling_convention_seq
                            in registers_parsed[ref].calling_convention[register]
                        ):
                            if index != len(elem[ref]):
                                if register in registers_list:
                                    reg_list += register + ", "
                                    position += 1
                            else:
                                if (
                                    position
                                    == len(
                                        registers_parsed[ref].calling_convention[
                                            register
                                        ]
                                    )
                                    - 1
                                ):
                                    if register in registers_list:
                                        if index >= first and index <= last:
                                            reg_list += register
                                else:
                                    if register in registers_list:
                                        if index >= first and index <= last:
                                            reg_list += register + ", "
                                            position += 1
                if first_dump is False:
                    if reg_list != "":
                        register_allocation += reg_list + "\n"
                        first_dump = True
                else:
                    if reg_list != "":
                        register_allocation += "\t" + reg_list + "\n"
        else:
            reg_list = ""
            index = 0
            first_dump = False
            for register in registers_list:
                if index < len(registers_list):
                    if index % 5 == 0 and index >= 1:
                        reg_list = reg_list + "\n"
                    if index % 5 == 0 and index >= 1:
                        reg_list += "\t"
                    reg_list += register + ", "
                    index += 1
                else:
                    reg_list += register
            register_allocation += reg_list.rstrip(", ") + "\n"
    content += register_allocation.rstrip(", \n") + "\n\t)> {\n"
    let = "\tlet RegInfos = " + config_variables["XLenRI_key"] + ";\n"
    def_class = statement + content + let + "}"
    return def_class


## Function that writes register specific content in RegisterInfo.td
#
# @param regclass Name of the register class
# @param file_name The files it writes into
# @param config_variables A dictionary where key and value are the contents of config_file
# @param alias_dict A dictionary where each register has its alias associated
# @param offset_dict A dictionary where each register file has its offset associated
# @param instrfield_ref_dict A dictionary that displays the fields of a register file
# @return The contents of RISCVRegisterInfo.td
def generate_file(
    regclass, file_name, config_variables, alias_dict, offset_dict, instrfield_ref_dict
):
    f = open(file_name, "a")
    global register_classes
    additional_register_classes = dict()
    for key in regclass.keys():
        if utils.check_register_class_prefix(regclass, key) is True:
            additional_register_classes = generate_registers_by_prefix(
                config_variables["RegAltNameIndex"],
                str.lower(key),
                config_variables["RegisterClass"],
                regclass[key].prefix,
                regclass[key].debug,
                int(regclass[key].size),
                alias_dict,
            )[2]
    check_register_class_width = list()
    f.write(generate_namespace(config_variables["Namespace"]))
    for elem in additional_register_classes.keys():
        f.write(generate_register_class(elem, additional_register_classes[elem], False))
        f.write("\n")
    instrfield_dict = dict()
    for key in regclass.keys():
        for instrfield_key in instrfield_ref_dict.keys():
            if instrfield_ref_dict[instrfield_key]["ref"] == key:
                instrfield_dict[key.upper()] = True
                regclass_alignment = regclass[key].width
                if int(regclass[key].width) != 2 ** int(
                    instrfield_ref_dict[instrfield_key]["width"]
                ):
                    regclass[key].width = str(
                        max(
                            int(regclass[key].width),
                            2 ** int(instrfield_ref_dict[instrfield_key]["width"]),
                        )
                    )
                    break
        if utils.check_register_class_prefix(regclass, key) is True:
            if len(check_register_class_width) == 0:
                if key in instrfield_dict.keys():
                    if instrfield_dict[key] is True and not (
                        regclass[key].pseudo != ""
                    ):
                        if (
                            "RegisterClassSubRegs_" + str(key).upper()
                            in config_variables.keys()
                        ):
                            register_class_name = config_variables[
                                "RegisterClassSubRegs_" + str(key).upper()
                            ]
                            f.write(
                                generate_register_class(
                                    register_class_name,
                                    regclass[key].width,
                                    True,
                                )
                            )
                            f.write("\n")
                        f.write(
                            generate_register_class(
                                config_variables["RegisterClass"],
                                regclass[key].width,
                                False,
                            )
                        )
                        f.write("\n")
                        check_register_class_width.append(regclass[key].width)
            elif regclass[key].width not in check_register_class_width:
                if key in instrfield_dict.keys():
                    if instrfield_dict[key] is True and not (
                        regclass[key].pseudo != ""
                    ):
                        if (
                            "RegisterClassSubRegs_" + str(key).upper()
                            in config_variables.keys()
                        ):
                            register_class_name = config_variables[
                                "RegisterClassSubRegs_" + str(key).upper()
                            ]
                            f.write(
                                generate_register_class(
                                    register_class_name, regclass[key].width, True
                                )
                            )
                            f.write("\n")
                        f.write(
                            generate_register_class(
                                config_variables["RegisterClass"],
                                regclass[key].width,
                                False,
                            )
                        )
                        f.write("\n")
                        check_register_class_width.append(regclass[key].width)
        else:
            if len(check_register_class_width) == 0:
                if key in instrfield_dict.keys():
                    if instrfield_dict[key] is True and not (
                        regclass[key].pseudo != ""
                    ):
                        if (
                            "RegisterClassSubRegs_" + str(key).upper()
                            in config_variables.keys()
                        ):
                            register_class_name = config_variables[
                                "RegisterClassSubRegs_" + str(key).upper()
                            ]
                            f.write(
                                generate_register_class(
                                    register_class_name, regclass[key].width, True
                                )
                            )
                            f.write("\n")
                        register_class_name = config_variables["RegisterClass"] + key
                        register_class_name = register_class_name.replace("Reg", "")
                        register_class_name = register_class_name + "Reg"
                        f.write(
                            generate_register_class(
                                register_class_name, regclass[key].width, False
                            )
                        )
                        f.write("\n")
                        check_register_class_width.append(regclass[key].width)
            elif regclass[key].size not in check_register_class_width:
                if key in instrfield_dict.keys():
                    if instrfield_dict[key] is True and not (
                        regclass[key].pseudo != ""
                    ):
                        register_class_name = config_variables["RegisterClass"] + key
                        register_class_name = register_class_name.replace("Reg", "")
                        register_class_name = register_class_name + "Reg"
                        f.write(
                            generate_register_class(
                                register_class_name, regclass[key].width, False
                            )
                        )
                        f.write("\n")
                        check_register_class_width.append(regclass[key].width)
    f.write(generate_define(config_variables["RegAltNameIndex"], "RegAltNameIndex"))
    f.write("\n}\n\n")
    f.write(generate_define("XLenRI", config_variables["XLenRIRegInfo"]))
    f.write("\n")
    f.write(generate_define("XLenVT", config_variables["XLenVTValueType"]))
    f.write("\n\n")
    list_instrfield_offset = dict()
    for key in regclass.keys():
        list_instrfield = list()
        register_aliases = dict()
        for instr_key in instrfield_ref_dict.keys():
            if instrfield_ref_dict[instr_key]["ref"] == key:
                if instrfield_ref_dict[instr_key]["offset"] == "0":
                    list_instrfield.append(instr_key)
                else:
                    if (
                        instrfield_ref_dict[instr_key]["offset"]
                        in list_instrfield_offset.keys()
                    ):
                        list_instrfield_offset[
                            instrfield_ref_dict[instr_key]["offset"]
                        ] += (instr_key + " ")
                    else:
                        list_instrfield_offset[
                            instrfield_ref_dict[instr_key]["offset"]
                        ] = (instr_key + " ")
            if instrfield_ref_dict[instr_key]["offset"] == "0":
                register_classes[key] = list_instrfield
    for key in regclass.keys():
        for regs in list_instrfield_offset.keys():
            elem = list_instrfield_offset[regs]
            elem = list(str(elem).split(" "))
            if "" in elem:
                elem.remove("")
            register_classes[key + "_" + regs] = elem
    for key in regclass.keys():
        list_instrfield = list()
        register_aliases = dict()
        for instr_key in instrfield_ref_dict.keys():
            if instrfield_ref_dict[instr_key]["ref"] == key:
                if instrfield_ref_dict[instr_key]["offset"] == "0":
                    list_instrfield.append(instr_key)
            if instrfield_ref_dict[instr_key]["offset"] == "0":
                register_classes[key] = list_instrfield
        if utils.check_register_class_prefix(regclass, key) is True:
            list_merged_instr = list()
            for elem_key in register_classes.keys():
                if elem_key not in regclass.keys():
                    if register_classes[elem_key][0] in instrfield_ref_dict.keys():
                        if (
                            instrfield_ref_dict[register_classes[elem_key][0]]["ref"]
                            == key
                        ):
                            list_merged_instr += register_classes[elem_key]
            for instr_key in instrfield_ref_dict.keys():
                if "excluded_values" in instrfield_ref_dict[instr_key].keys():
                    if len(list_merged_instr) != 0:
                        list_merged_instr.remove(instr_key)
            list_merged_instr += list_instrfield
            if len(list_merged_instr) != 0 and not (regclass[key].pseudo != ""):
                f.write("//" + "Register Class " + key + " : " + regclass[key].doc_info)
                f.write("\n")
                f.write(
                    "//" + "Instruction fields : " + str(sorted(set(list_merged_instr)))
                )
                f.write("\n")
                f.write("//" + "Attributes : " + str(sorted(regclass[key].attributes)))
                f.write("\n")
                f.write(
                    generate_registers_by_prefix(
                        config_variables["RegAltNameIndex"],
                        str.lower(key),
                        config_variables["RegisterClass"],
                        regclass[key].prefix,
                        regclass[key].debug,
                        int(regclass[key].size),
                        alias_dict,
                    )[0]
                )
                register_aliases = generate_registers_by_prefix(
                    config_variables["RegAltNameIndex"],
                    str.lower(key),
                    config_variables["RegisterClass"],
                    regclass[key].prefix,
                    regclass[key].debug,
                    int(regclass[key].size),
                    alias_dict,
                )[1]
                f.write("\n\n")
        else:
            list_merged_instr = list()
            for elem_key in register_classes.keys():
                if elem_key not in regclass.keys():
                    if register_classes[elem_key][0] in instrfield_ref_dict.keys():
                        if (
                            instrfield_ref_dict[register_classes[elem_key][0]]["ref"]
                            == key
                        ):
                            list_merged_instr += register_classes[elem_key]
            list_merged_instr += list_instrfield
            if len(list_merged_instr) != 0 and not (regclass[key].pseudo != ""):
                f.write("//" + "Register Class " + key + " : " + regclass[key].doc_info)
                f.write("\n")
                f.write("//" + "Instruction fields : " + str(sorted(list_merged_instr)))
                f.write("\n")
                f.write("//" + "Attributes : " + str(sorted(regclass[key].attributes)))
                f.write("\n")
                register_class_name = config_variables["RegisterClass"] + key
                register_class_name = register_class_name.replace("Reg", "")
                register_class_name = register_class_name + "Reg"
                f.write(
                    generate_registers_by_name(
                        config_variables["RegAltNameIndex"],
                        str.lower(key),
                        register_class_name,
                        regclass[key].entries,
                        regclass[key].syntax,
                        regclass[key].debug,
                        alias_dict,
                    )
                )
                f.write("\n\n")
        if key in offset_dict.keys():
            for elem in offset_dict[key]:
                instrfield_width = 2 ** int(elem[0])
                offset = elem[1]
                shift = elem[2]
                if offset != "0":
                    list_instrfield_offset = register_classes[key + "_" + offset]
                if offset != "0":
                    list_instrfield_offset_cpy = list_instrfield_offset.copy()
                    for instr_key in instrfield_ref_dict.keys():
                        if "excluded_values" in instrfield_ref_dict[instr_key].keys():
                            if instr_key in list_instrfield_offset:
                                list_instrfield_offset_cpy.remove(instr_key)
                                register_classes[
                                    key + "_" + offset
                                ] = list_instrfield_offset_cpy
                    if len(list_instrfield_offset_cpy) != 0 and not (
                        regclass[key].pseudo != ""
                    ):
                        f.write(
                            "//"
                            + "Instruction fields : "
                            + str(sorted(list_instrfield_offset_cpy))
                        )
                        f.write("\n")
                        f.write("//" + "Offset : " + str(offset))
                        f.write("\n")
                        f.write(
                            "//" + "Width : " + str(int(math.log2(instrfield_width)))
                        )
                        f.write("\n")
                else:
                    if len(list_instrfield) != 0 and not (regclass[key].pseudo != ""):
                        f.write(
                            "//"
                            + "Instruction fields : "
                            + str(sorted(list_instrfield))
                        )
                        f.write("\n")
                if (len(list_instrfield_offset) != 0 or len(list_instrfield) != 0) and (
                    not (regclass[key].pseudo != "")
                ):
                    f.write(
                        define_register_class(
                            key,
                            config_variables,
                            config_variables["Namespace"],
                            registers_define[str.lower(key)],
                            regclass_alignment,
                            config_variables["XLenVT"],
                            str(config_variables["XLenRI"]),
                            offset,
                            instrfield_width,
                            shift,
                            "",
                        )
                    )
                    f.write("\n\n")
        if config_variables["DefineSP"] == "True":
            for key_alias in register_aliases.keys():
                f.write(
                    generate_SP_register_class(
                        register_aliases,
                        str(register_aliases[key_alias]),
                        config_variables["Namespace"],
                        regclass_alignment,
                        config_variables["XLenVT"],
                        str(config_variables["XLenRI"]),
                    )
                )
                f.write("\n\n")
        for instr_key in instrfield_ref_dict.keys():
            if "excluded_values" in instrfield_ref_dict[instr_key].keys():
                if instrfield_ref_dict[instr_key]["ref"] == key:
                    excluded_values = instrfield_ref_dict[instr_key]["excluded_values"]
                    if len(instr_key) != 0 and not (regclass[key].pseudo != ""):
                        if offset != "0":
                            f.write("//" + "Instruction fields : " + str((instr_key)))
                            f.write("\n")
                            f.write(
                                "//"
                                + "Offset : "
                                + str(instrfield_ref_dict[instr_key]["offset"])
                            )
                            f.write("\n")
                            f.write(
                                "//"
                                + "Width : "
                                + str(2 ** int(instrfield_ref_dict[instr_key]["width"]))
                            )
                            f.write("\n")
                        offset = instrfield_ref_dict[instr_key]["offset"]
                        instrfield_width = 2 ** int(
                            instrfield_ref_dict[instr_key]["width"]
                        )
                        f.write(
                            define_register_class(
                                key,
                                config_variables,
                                config_variables["Namespace"],
                                registers_define[str.lower(key)],
                                regclass_alignment,
                                config_variables["XLenVT"],
                                str(config_variables["XLenRI"]),
                                offset,
                                instrfield_width,
                                shift,
                                excluded_values[instr_key][0],
                            )
                        )
                        f.write("\n\n")
    register_classes_copy = dict()
    for register in register_classes.keys():
        instrfield_list = list()
        for reg in instrfield_ref_dict.keys():
            if register.startswith(instrfield_ref_dict[reg]["ref"]) and "_" in register:
                if (
                    instrfield_ref_dict[reg]["offset"] != "0"
                    and instrfield_ref_dict[reg]["offset"] in register
                ):
                    instrfield_list.append(reg)
            if register == instrfield_ref_dict[reg]["ref"]:
                if instrfield_ref_dict[reg]["offset"] == "0":
                    instrfield_list.append(reg)
        register_classes_copy[register] = instrfield_list
    register_classes_copy["SP"] = "sp"
    register_classes = register_classes_copy.copy()
    f.close()


## Function for generating the definition of an instruction
#
# @param instructions Dictionary containing all the instructions parsed from adl
# @param list_instructions List containing the name of the instructions that use only registers and constants
# @param key The name of the instruction for which this functions generates the definition
# @param width Width of the instruction parsed from ADL file
# @param schedule Schedule list
# @param hasImm It specifies if an instruction uses immediates or only registers and constants
# @param disableEncoding It specifies if an instruction should have this option enabled
# @param extension_list A list containing the extensions given by the user in the command line
# @return The content for the instruction definition
def generate_instruction_define(
    instructions,
    list_instructions,
    key,
    width,
    schedule,
    hasImm,
    disableEncoding,
    extension_list,
):
    config_variables = config.config_environment(config_file, llvm_config)
    instrfield_imm = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
    instrfield_ref = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    instrfield_data_ref = adl_parser.get_instrfield_offset(config_variables["ADLName"])[
        1
    ]
    registers = adl_parser.get_alias_for_regs(config_variables["ADLName"])
    regs_prefix = adl_parser.parse_adl(config_variables["ADLName"])
    define = "def "
    content = ""
    sideEffects = False
    decoderNamespace = ""
    attributes = instructions[key]["attributes"]
    attributes.sort()
    attributes_list_extension = ""
    attributes_list_instruction = list()
    for element in attributes:
        if len(extension_list) > 0:
            if (
                "LLVMExt" + element.capitalize() in config_variables.keys()
                and element in extension_list
            ):
                attributes_list_extension = element
                break
        else:
            if "LLVMExt" + element.capitalize() in config_variables.keys():
                attributes_list_extension = element
                break
    for element in attributes:
        if element != attributes_list_extension:
            if "LLVMExt" + element.capitalize() in config_variables.keys():
                attributes_list_instruction.append(element)
    predicates = "Predicates = " + "["
    predicate_checked = False
    decoderNamespace_predicate = ""
    if len(attributes_list_instruction) > 0:
        for element in attributes_list_instruction:
            predicates += config_variables["LLVMExt" + element.capitalize()] + ", "
            decoderNamespace_predicate = element.capitalize()
            predicate_checked = True
    predicates = predicates.rstrip(", ")
    predicates += "]"
    if "disassemble" in instructions[key]:
        if (
            instructions[key]["disassemble"] != "true"
            and instructions[key]["disassemble"] != "false"
        ):
            def_let_sideEffects = (
                "hasSideEffects = 1, mayLoad = 0, mayStore = 0" + " in\n"
            )
            def_let_sideEffectsBasic = (
                "hasSideEffects = 0, mayLoad = 0, mayStore = 0" + " in\n"
            )
            def_let_sideEffectsLoad = (
                "hasSideEffects = 0, mayLoad = 1, mayStore = 0" + " in\n"
            )
            def_let_sideEffectsStore = (
                "hasSideEffects = 0, mayLoad = 0, mayStore = 1" + " in\n"
            )
            def_let_sideEffectsLoadTrue = (
                "hasSideEffects = 1, mayLoad = 1, mayStore = 0" + " in\n"
            )
            def_let_sideEffectsStoreTrue = (
                "hasSideEffects = 1, mayLoad = 0, mayStore = 1, DecoderNamespace = "
                + " in\n"
            )
        else:
            def_let_sideEffects = "hasSideEffects = 1, mayLoad = 0, mayStore = 0 in\n"
            def_let_sideEffectsBasic = (
                "hasSideEffects = 0, mayLoad = 0, mayStore = 0 in\n"
            )
            def_let_sideEffectsLoad = (
                "hasSideEffects = 0, mayLoad = 1, mayStore = 0 in\n"
            )
            def_let_sideEffectsStore = (
                "hasSideEffects = 0, mayLoad = 0, mayStore = 1 in\n"
            )
            def_let_sideEffectsLoadTrue = (
                "hasSideEffects = 1, mayLoad = 1, mayStore = 0 in\n"
            )
            def_let_sideEffectsStoreTrue = (
                "hasSideEffects = 1, mayLoad = 0, mayStore = 1 in\n"
            )
    else:
        def_let_sideEffects = "hasSideEffects = 1, mayLoad = 0, mayStore = 0 in\n"
        def_let_sideEffectsBasic = "hasSideEffects = 0, mayLoad = 0, mayStore = 0 in\n"
        def_let_sideEffectsLoad = "hasSideEffects = 0, mayLoad = 1, mayStore = 0 in\n"
        def_let_sideEffectsStore = "hasSideEffects = 0, mayLoad = 0, mayStore = 1 in\n"
        def_let_sideEffectsLoadTrue = (
            "hasSideEffects = 1, mayLoad = 1, mayStore = 0 in\n"
        )
        def_let_sideEffectsStoreTrue = (
            "hasSideEffects = 1, mayLoad = 0, mayStore = 1 in\n"
        )
    if config_variables["sideEffectAttribute"] in instructions[key]["attributes"]:
        sideEffects = True
    if (
        config_variables["memorySynchronizationInstruction"]
        in instructions[key]["attributes"]
    ):
        sideEffects = True
    if (
        config_variables["sideEffectAttributeSpecific"]
        in instructions[key]["attributes"]
    ):
        sideEffects = True
    instrfield_regs_ins = list()
    instrfield_regs_outs = list()
    regs_in = list()
    regs_out = list()
    list_regs = list()
    ins_instruction = list()
    decoderMethodRegs = list()
    action = instructions[key]["action"]
    syntax_elements = instructions[key]["syntax"]
    syntax_elements = list(instructions[key]["syntax"])
    syntax_elements_cpy = syntax_elements.copy()
    extension = ""
    for element in instructions[key]["attributes"]:
        if len(extension_list) > 0:
            if (
                "LLVMExt" + element.capitalize() in config_variables.keys()
                and element in extension_list
            ):
                file_name_extension = config_variables["LLVMExt" + element.capitalize()]
                if file_name_extension + "Extension" in config_variables.keys():
                    extension = config_variables[file_name_extension + "Extension"]
                    break
        else:
            if "LLVMExt" + element.capitalize() in config_variables.keys():
                file_name_extension = config_variables["LLVMExt" + element.capitalize()]
                if file_name_extension + "Extension" in config_variables.keys():
                    extension = config_variables[file_name_extension + "Extension"]
                    break
    if "ExtensionPrefixed" in config_variables.keys():
        if extension in config_variables["ExtensionPrefixed"]:
            define += (
                extension.upper() + "_" + str(str(key).replace(".", "_")).upper() + " :"
            )
        elif len(attributes_list_instruction) > 0:
            for element in attributes_list_instruction:
                if element.capitalize() in config_variables["ExtensionPrefixed"]:
                    define += (
                        element.upper()
                        + "_"
                        + str(str(key).replace(".", "_")).upper()
                        + " :"
                    )
        else:
            define += str(str(key).replace(".", "_")).upper() + " :"
    if width == config_variables["LLVMStandardInstructionWidth"]:
        define += config_variables["InstructionClass"] + "<"
        decoderMethod = (
            "let DecoderMethod = " + '"' + config_variables["InstructionClass"]
        )
    else:
        if config_variables["InstructionClass"] + width in config_variables.values():
            define += config_variables["InstructionClass"] + width + "<"
            decoderMethod = (
                "let DecoderMethod = "
                + '"'
                + config_variables["InstructionClass"]
                + width
            )
    if key in list_instructions:
        for instrfield in instructions[key]["fields"][0].keys():
            if instrfield in instrfield_ref.keys():
                if str(instructions[key]["fields"][0][instrfield]) == "reg":
                    list_regs.append("$" + instrfield)
            elif instrfield in instrfield_imm.keys():
                if str(instructions[key]["fields"][0][instrfield]) == "imm":
                    list_regs.append("$" + instrfield)
    for instrfield in syntax_elements[1:]:
        if instrfield in instrfield_data_ref.keys():
            for reg_key in register_classes.keys():
                if reg_key in regs_prefix.keys() and regs_prefix[reg_key].pseudo != "":
                    ref = regs_prefix[reg_key].pseudo
                    if ref not in register_references:
                        register_references.append(ref)
                else:
                    if instrfield in register_classes[reg_key]:
                        if "alias" + reg_key in config_variables.keys():
                            if (
                                "excluded_values"
                                in instrfield_data_ref[instrfield].keys()
                            ):
                                if (
                                    "alias"
                                    + reg_key
                                    + "No"
                                    + instrfield_data_ref[instrfield][
                                        "excluded_values"
                                    ][instrfield][0]
                                    in config_variables.keys()
                                ):
                                    ref = config_variables[
                                        "alias"
                                        + reg_key
                                        + "No"
                                        + instrfield_data_ref[instrfield][
                                            "excluded_values"
                                        ][instrfield][0]
                                    ]
                                    if ref not in register_references:
                                        register_references.append(ref)
                                else:
                                    if "alias" + reg_key in config_variables.keys():
                                        ref = config_variables["alias" + reg_key]
                                        if ref not in register_references:
                                            register_references.append(ref)
                            else:
                                if "alias" + reg_key in config_variables.keys():
                                    if (
                                        instrfield_ref[instrfield]["ref"]
                                        in "alias" + reg_key
                                    ):
                                        ref = config_variables["alias" + reg_key]
                                        if ref not in register_references:
                                            register_references.append(ref)
                                        break
                        else:
                            ref = reg_key
                            if ref not in register_references:
                                register_references.append(ref)
                            break
            outs = str(instructions[key]["outputs"])
            ins = str(instructions[key]["inputs"])
            outs = re.split(r"[()]", outs)
            ins = re.split(r"[()]", ins)
            if instrfield in ins:
                decoderMethodRegs.append(instrfield)
            if instrfield in outs:
                decoderMethodRegs.append(instrfield)
        elif instrfield in instrfield_imm.keys():
            if instructions[key]["fields"][0][instrfield] == "imm":
                ins_instruction.insert(len(ins_instruction), instrfield)
            ref_imm = ""
            for instr_key in instrfield_classes.keys():
                if instrfield in instrfield_classes[instr_key]:
                    if (
                        instrfield_imm[instrfield]["width"] in str(instr_key).lower()
                    ) or (
                        str(
                            int(instrfield_imm[instrfield]["width"])
                            + int(instrfield_imm[instrfield]["shift"])
                        )
                        in str(instr_key).lower()
                    ):
                        ref_imm = str(instr_key).lower()
                    else:
                        ref_imm = str(instr_key).lower()
                        ref_split = re.split(r"[0-9]", ref_imm)
                        if int(instrfield_imm[instrfield]["shift"]) == 0:
                            ref_imm = ref_split[0] + instrfield_imm[instrfield]["width"]
                        else:
                            ref_imm = ref_split[0] + str(
                                int(instrfield_imm[instrfield]["width"])
                                + int(instrfield_imm[instrfield]["shift"])
                            )
                    if instrfield in instructions[key]["fields"][0].keys():
                        if instrfield in str(instructions[key]["inputs"]):
                            if instrfield not in regs_in:
                                regs_in.insert(len(regs_in), instrfield)
                                if instrfield in config_variables.keys():
                                    if (
                                        '"AliasImmClass"'
                                        in config_variables[instrfield].keys()
                                    ):
                                        instrfield_regs_ins.insert(
                                            len(instrfield_regs_ins),
                                            config_variables[instrfield][
                                                '"AliasImmClass"'
                                            ].replace('"', "")
                                            + ":"
                                            + "$"
                                            + instrfield,
                                        )
                                    else:
                                        instrfield_regs_ins.insert(
                                            len(instrfield_regs_ins),
                                            instr_key.lower() + ":" + "$" + instrfield,
                                        )
                                else:
                                    if "nonzero" in ref_imm:
                                        if (
                                            "excluded_values"
                                            not in instructions[key].keys()
                                        ):
                                            ref_imm = ref_imm.replace("nonzero", "")
                                            instrfield_regs_ins.insert(
                                                len(instrfield_regs_ins),
                                                ref_imm + ":" + "$" + instrfield,
                                            )
                                        else:
                                            instrfield_regs_ins.insert(
                                                len(instrfield_regs_ins),
                                                ref_imm + ":" + "$" + instrfield,
                                            )
                                    else:
                                        if (
                                            "excluded_values"
                                            in instructions[key].keys()
                                        ):
                                            ref_imm += "non" + str(
                                                num2words.num2words(
                                                    int(
                                                        instructions[key][
                                                            "excluded_values"
                                                        ][instrfield][0]
                                                    )
                                                )
                                            )
                                            instrfield_regs_ins.insert(
                                                len(instrfield_regs_ins),
                                                ref_imm + ":" + "$" + instrfield,
                                            )
                                        else:
                                            instrfield_regs_ins.insert(
                                                len(instrfield_regs_ins),
                                                ref_imm + ":" + "$" + instrfield,
                                            )
    outs = str(instructions[key]["outputs"])
    ins = str(instructions[key]["inputs"])
    outs = re.split(r"[()]", outs)
    ins = re.split(r"[()]", ins)
    memory_operand_registers = list()
    registers_parsed = adl_parser.parse_adl(config_variables["ADLName"])
    register_pair_app_ins = dict()
    register_pair_app_outs = dict()
    for register in instrfield_ref:
        register_pair_app_ins[register] = int(0)
        register_pair_app_outs[register] = int(0)
    ins.sort()
    for element in ins:
        for instrfield in instrfield_ref:
            if instrfield in element and instrfield in ins:
                if register_pair_app_ins[instrfield] == 0:
                    register_pair_app_ins[instrfield] += 1
                else:
                    element = element.replace(" ", "")
                    if "+1" in element:
                        register_pair_app_ins[instrfield] += 1
    outs_copy = outs.copy()
    outs_copy.sort()
    for element in outs_copy:
        for instrfield in instrfield_ref:
            if instrfield in element and instrfield in outs:
                if register_pair_app_outs[instrfield] == 0:
                    register_pair_app_outs[instrfield] += 1
                else:
                    element = element.replace(" ", "")
                    if "+1" in element:
                        register_pair_app_outs[instrfield] += 1
    for element in syntax_elements:
        for immediate in instrfield_imm:
            if immediate in element:
                for register in instrfield_ref:
                    if register in element and register in ins:
                        memory_operand_registers.append(register)
    for element in ins:
        if element not in instrfield_ref:
            for register in instrfield_ref:
                if element in instrfield_data_ref[register]["enumerated"].keys():
                    aux = instrfield_data_ref[register]["enumerated"][element]
                    for index in aux:
                        if (
                            index
                            != registers_parsed[
                                instrfield_data_ref[register]["ref"]
                            ].prefix
                            + element
                        ):
                            if index not in memory_operand_registers:
                                memory_operand_registers.append(index)
                                break
    action = action.replace("{", "").replace("}", "").replace("\n", "")
    action = action.lstrip(" ")
    action = action.rstrip(" ")
    register_used = ""
    action_list_lines = action.split(";")
    if "" in action_list_lines:
        action_list_lines.remove("")
    variable_used = ""
    for index in range(len(action_list_lines)):
        first_line = action_list_lines[index].split("=")
        if len(first_line) > 2:
            variable = first_line[0].lstrip(" ").rstrip(" ")
            register = first_line[1].lstrip(" ").rstrip(" ")
            if len(variable.split(" ")) > 2:
                variable_used = variable.split(" ")[1]
            register_used_list = register.split(" ")
            for element in register_used_list:
                if element in instrfield_ref:
                    register_used = element.lstrip("( ")
            if index + 1 < len(action_list_lines):
                index += 1
            if "Mem" in action_list_lines[index]:
                mem_list = action_list_lines[index].split("=")
                if "Mem" in mem_list[0]:
                    mem_variable = mem_list[0]
                else:
                    mem_variable = mem_list[1]
                if variable_used in mem_variable:
                    if register_used not in memory_operand_registers:
                        if register_used != "":
                            memory_operand_registers.append(register_used)
            break
    check_reference_pairs = list()
    ins.sort()
    for instrfield in ins:
        ref = ""
        if instrfield in instrfield_ref.keys():
            for reg_key in register_classes.keys():
                if instrfield in register_classes[reg_key]:
                    if "alias" + reg_key in config_variables.keys():
                        ref = config_variables["alias" + reg_key]
                        if (
                            instrfield in register_pair_app_ins.keys()
                            and register_pair_app_ins[instrfield] == 2
                        ) or (
                            instrfield in register_pair_app_outs.keys()
                            and register_pair_app_outs[instrfield]
                        ) == 2:
                            if "No" in ref:
                                ref_copy = ref
                                ref = ref.split("No", 1)[0]
                                rest = ref_copy.split("No", 1)[1]
                                ref += "P"
                                ref += "No" + rest
                                check_reference_pairs.append(ref)
                            else:
                                ref += "P"
                                check_reference_pairs.append(ref)
                            if ref not in register_pairs.keys():
                                list_aux = list()
                                list_aux.append(instrfield)
                                register_pairs[ref] = list_aux
                            elif ref in register_pairs.keys():
                                list_aux = list()
                                list_aux.extend(register_pairs[ref])
                                list_aux.append(instrfield)
                                register_pairs[ref] = list_aux
                        if "load" in instructions[key]["attributes"]:
                            if instrfield in memory_operand_registers:
                                ref += "Mem"
                        elif "store" in instructions[key]["attributes"]:
                            if instrfield in memory_operand_registers:
                                ref += "Mem"
                        if ref not in register_references:
                            register_references.append(ref)
                    else:
                        ref = reg_key
                        if (
                            instrfield in register_pair_app_ins.keys()
                            and register_pair_app_ins[instrfield] == 2
                        ) or (
                            instrfield in register_pair_app_outs.keys()
                            and register_pair_app_outs[instrfield]
                        ) == 2:
                            if "No" in ref:
                                ref_copy = ref
                                ref = ref.split("No", 1)[0]
                                rest = ref_copy.split("No", 1)[1]
                                ref += "P"
                                ref += "No" + rest
                                check_reference_pairs.append(ref)
                            else:
                                ref += "P"
                                check_reference_pairs.append(ref)
                            if ref not in register_pairs.keys():
                                list_aux = list()
                                list_aux.append(instrfield)
                                register_pairs[ref] = list_aux
                            elif ref in register_pairs.keys():
                                list_aux = list()
                                list_aux.extend(register_pairs[ref])
                                list_aux.append(instrfield)
                                register_pairs[ref] = list_aux
                        if "load" in instructions[key]["attributes"]:
                            if instrfield in memory_operand_registers:
                                ref += "Mem"
                        elif "store" in instructions[key]["attributes"]:
                            if instrfield in memory_operand_registers:
                                ref += "Mem"
                        if ref not in register_references:
                            register_references.append(ref)
            if instrfield not in regs_in:
                regs_in.insert(len(regs_in), instrfield)
                instrfield_regs_ins.insert(
                    len(instrfield_regs_ins), ref + ":" + "$" + instrfield
                )
    for instrfield in outs:
        ref = ""
        if instrfield in instrfield_ref.keys():
            for reg_key in register_classes.keys():
                if instrfield in register_classes[reg_key]:
                    if "alias" + reg_key in config_variables.keys():
                        if "excluded_values" in instrfield_data_ref[instrfield]:
                            for element in instrfield_data_ref[instrfield][
                                "excluded_values"
                            ].keys():
                                if (
                                    "alias"
                                    + reg_key
                                    + "No"
                                    + instrfield_data_ref[instrfield][
                                        "excluded_values"
                                    ][element][0]
                                    in config_variables.keys()
                                ):
                                    ref = config_variables[
                                        "alias"
                                        + reg_key
                                        + "No"
                                        + instrfield_data_ref[instrfield][
                                            "excluded_values"
                                        ][element][0]
                                    ]
                                    break
                        else:
                            ref = config_variables["alias" + reg_key]
                        if (
                            instrfield in register_pair_app_outs.keys()
                            and register_pair_app_outs[instrfield] == 2
                        ) or (
                            instrfield in register_pair_app_outs.keys()
                            and register_pair_app_outs[instrfield]
                        ) == 2:
                            if "No" in ref:
                                ref_copy = ref
                                ref = ref.split("No", 1)[0]
                                rest = ref_copy.split("No", 1)[1]
                                ref += "P"
                                ref += "No" + rest
                                check_reference_pairs.append(ref)
                            else:
                                ref += "P"
                                check_reference_pairs.append(ref)
                            if ref not in register_pairs.keys():
                                list_aux = list()
                                list_aux.append(instrfield)
                                register_pairs[ref] = list_aux
                            elif ref in register_pairs.keys():
                                list_aux = list()
                                list_aux.extend(register_pairs[ref])
                                list_aux.append(instrfield)
                                register_pairs[ref] = list_aux
                        if ref not in register_references:
                            register_references.append(ref)
                    else:
                        ref = reg_key
                        if (
                            instrfield in register_pair_app_outs.keys()
                            and register_pair_app_outs[instrfield] == 2
                        ) or (
                            instrfield in register_pair_app_outs.keys()
                            and register_pair_app_outs[instrfield]
                        ) == 2:
                            if "No" in ref:
                                ref_copy = ref
                                ref = ref.split("No", 1)[0]
                                rest = ref_copy.split("No", 1)[1]
                                ref += "P"
                                ref += "No" + rest
                                check_reference_pairs.append(ref)
                            else:
                                ref += "P"
                                check_reference_pairs.append(ref)
                            if ref not in register_pairs.keys():
                                list_aux = list()
                                list_aux.append(instrfield)
                                register_pairs[ref] = list_aux
                            elif ref in register_pairs.keys():
                                list_aux = list()
                                list_aux.extend(register_pairs[ref])
                                list_aux.append(instrfield)
                                register_pairs[ref] = list_aux
                        if ref not in register_references:
                            register_references.append(ref)
            if instrfield not in regs_out:
                regs_out.insert(len(regs_out), instrfield)
                instrfield_regs_outs.insert(
                    len(instrfield_regs_outs), ref + ":" + "$" + instrfield
                )
    alias_dict = adl_parser.get_alias_for_regs(config_variables["ADLName"])
    for elem in instructions[key]["inputs"]:
        for regclass in register_classes:
            if regclass in elem:
                ins = re.split(r"[()]", elem)
                for elem_ins in ins:
                    if regclass in alias_dict.keys():
                        if elem_ins in alias_dict[regclass].keys():
                            reg_in = alias_dict[regclass][elem_ins]
                            reg_in = reg_in[0]
                            regclass_cpy = ""
                            for register_new_class in register_classes.keys():
                                if reg_in in register_classes[register_new_class]:
                                    regclass_cpy = register_new_class
                            if regclass_cpy != "" and regclass_cpy != regclass:
                                exitValue = False
                                regs_in.insert(0, reg_in)
                                if "load" in instructions[key]["attributes"]:
                                    if regclass_cpy.lower() in memory_operand_registers:
                                        regclass_cpy += "Mem"
                                elif "store" in instructions[key]["attributes"]:
                                    if regclass_cpy.lower() in memory_operand_registers:
                                        regclass_cpy += "Mem"
                                if regclass_cpy not in register_references:
                                    register_references.append(regclass_cpy)
                                for reg in regs_in:
                                    if reg in instrfield_data_ref:
                                        exitValue = True
                                        instrfield_regs_ins.insert(
                                            len(instrfield_data_ref),
                                            regclass_cpy + ":" + "$" + reg_in,
                                        )
                                        decoderMethodRegs.append(reg_in)
                                        break
                                if exitValue is False:
                                    instrfield_regs_ins.insert(
                                        0, regclass_cpy + ":" + "$" + reg_in
                                    )
                                    decoderMethodRegs.append(reg_in)
                            else:
                                regs_in.insert(0, reg_in)
                                if "load" in instructions[key]["attributes"]:
                                    if regclass.lower() in memory_operand_registers:
                                        regclass += "Mem"
                                elif "store" in instructions[key]["attributes"]:
                                    if regclass.lower() in memory_operand_registers:
                                        regclass += "Mem"
                                if regclass not in register_references:
                                    register_references.append(regclass)
                                instrfield_regs_ins.insert(
                                    0, regclass + ":" + "$" + reg_in
                                )
                                decoderMethodRegs.append(reg_in)
    for elem in instructions[key]["outputs"]:
        for regclass in register_classes:
            if regclass in elem:
                outs = re.split(r"[()]", elem)
                for elem_outs in outs:
                    if regclass in alias_dict.keys():
                        if elem_outs in alias_dict[regclass].keys():
                            reg_out = alias_dict[regclass][elem_outs]
                            reg_out = reg_out[0]
                            regs_out.insert(len(regs_out), reg_out)
                            if (
                                elem_outs in register_pair_app_outs.keys()
                                and register_pair_app_outs[elem_outs] == 2
                            ):
                                if "No" in regclass:
                                    regclass_copy = regclass
                                    regclass = regclass.split("No", 1)[0]
                                    rest = regclass_copy.split("No", 1)[1]
                                    regclass += "P"
                                    regclass += "No" + rest
                                    check_reference_pairs.append(regclass)
                                else:
                                    regclass += "P"
                                    check_reference_pairs.append(regclass)
                            if regclass not in register_pairs.keys():
                                list_aux = list()
                                list_aux.append(reg_out)
                                register_pairs[regclass] = list_aux
                            elif regclass in register_pairs.keys():
                                list_aux = list()
                                list_aux.extend(register_pairs[regclass])
                                list_aux.append(reg_out)
                                register_pairs[regclass] = list_aux
                            instrfield_regs_outs.insert(
                                len(instrfield_regs_outs),
                                regclass + ":" + "$" + reg_out,
                            )
                            decoderMethodRegs.append(reg_out)
    syntax_elements_list = list()
    for instrfield in syntax_elements[1:]:
        skip_element = False
        syntax_elem = re.split(r"[()]", instrfield)
        for syntax_element in syntax_elem:
            if syntax_element in instrfield_imm.keys():
                ref_imm = ""
                for instr_key in instrfield_classes.keys():
                    instrfield_classes_list = instrfield_classes[instr_key].split(" ")
                    for element in instrfield_classes_list:
                        if syntax_element == element:
                            ref_imm = str(instr_key).lower()
                            break
                    if ref_imm != "":
                        if (
                            ref_imm + ":" + "$" + syntax_element
                            not in instrfield_regs_ins
                        ):
                            if syntax_element not in syntax_elements_list:
                                if ":" + "$" + syntax_element in instrfield_regs_ins:
                                    instrfield_regs_ins.remove(
                                        ":" + "$" + syntax_element
                                    )
                                    syntax_elements_list.append(syntax_element)
                                    for element in instrfield_regs_ins:
                                        if syntax_element in element:
                                            skip_element = True
                                            break
                                    if skip_element is False:
                                        instrfield_regs_ins.insert(
                                            len(instrfield_regs_ins),
                                            ref_imm + ":" + "$" + syntax_element,
                                        )
                                else:
                                    syntax_elements_list.append(syntax_element)
                                    for element in instrfield_regs_ins:
                                        if syntax_element in element:
                                            skip_element = True
                                            break
                                    if skip_element is False:
                                        instrfield_regs_ins.insert(
                                            len(instrfield_regs_ins),
                                            ref_imm + ":" + "$" + syntax_element,
                                        )
                            break
                    else:
                        if syntax_element in instructions[key]["fields"][0].keys():
                            if syntax_element not in regs_in:
                                if syntax_element in instructions[key]["outputs"]:
                                    if syntax_element not in regs_out:
                                        if instrfield in config_variables.keys():
                                            ref_imm = config_variables[instrfield][
                                                '"AliasImmClass"'
                                            ].replace('"', "")
                                        regs_out.insert(len(regs_out), syntax_element)
                                        instrfield_regs_outs.insert(
                                            len(instrfield_regs_outs),
                                            ref_imm + ":" + "$" + syntax_element,
                                        )
                                else:
                                    regs_in.insert(len(regs_in), syntax_element)
                                    if instrfield in config_variables.keys():
                                        if (
                                            '"AliasImmClass"'
                                            in config_variables[instrfield].keys()
                                        ):
                                            ref_imm = config_variables[instrfield][
                                                '"AliasImmClass"'
                                            ].replace('"', "")
                                    if (
                                        ref_imm + ":" + "$" + syntax_element
                                        not in instrfield_regs_ins
                                    ):
                                        instrfield_regs_ins.insert(
                                            len(instrfield_regs_ins),
                                            ref_imm + ":" + "$" + syntax_element,
                                        )
    for reg_pair in check_reference_pairs:
        if reg_pair not in register_pairs.keys():
            list_aux = list()
            list_aux.append(reg_pair)
            register_pairs[reg_pair] = list_aux
    for reg_pair in register_references:
        if "No" in reg_pair:
            aux = reg_pair.split("No")[0]
            if aux.endswith("P"):
                if reg_pair not in register_pairs.keys():
                    list_aux = list()
                    list_aux.append(reg_pair)
                    register_pairs[reg_pair] = list_aux
        else:
            if reg_pair.endswith("P"):
                aux = reg_pair[::-1].replace("P", "")
                if aux in register_references:
                    if reg_pair not in register_pairs.keys():
                        list_aux = list()
                        list_aux.append(reg_pair)
                        register_pairs[reg_pair] = list_aux

    constraint = ""
    disableEncodingLet = ""
    str_ins_instruction = str(ins_instruction)
    if str_ins_instruction != "[]":
        ins_instruction = re.split(r"[()]", str_ins_instruction)
    for imm_elem in ins_instruction:
        if imm_elem not in instrfield_regs_ins:
            imm_elem = imm_elem.replace("[", "")
            imm_elem = imm_elem.replace("]", "")
            imm_elem = imm_elem.replace("'", "")
    syntax_elements = syntax_elements[1:]
    aux = list()
    for elem in syntax_elements:
        x = re.split("[()]", elem)
        aux.extend(x)
    syntax_elements.extend(aux)
    uses_regs = list()
    defs_regs = list()
    alias_reg_dict = dict()
    for reg in regs_in:
        if reg not in syntax_elements:
            reg = str(reg).upper()
            for register in registers.keys():
                for alias in registers[register].keys():
                    if reg.lower() in registers[register][alias]:
                        prefix = regs_prefix[register].prefix
                        for each_alias in registers[register][alias]:
                            if prefix in each_alias:
                                uses_regs.append(str(each_alias).upper())
                                decoderMethodRegs.append(str(each_alias))
                            else:
                                alias_reg = str(each_alias).upper()
                            alias_reg_dict[alias_reg] = str(each_alias).upper()
                            decoderMethodRegs.append(str(each_alias))
    for reg in regs_out:
        if reg not in syntax_elements:
            reg = str(reg).upper()
            for register in registers.keys():
                for alias in registers[register].keys():
                    if reg.lower() in registers[register][alias]:
                        prefix = regs_prefix[register].prefix
                        for each_alias in registers[register][alias]:
                            if prefix in each_alias:
                                defs_regs.append(str(each_alias).upper())
                                decoderMethodRegs.append(str(each_alias))
                            else:
                                alias_reg = str(each_alias).upper()
                                decoderMethodRegs.append(str(each_alias))
                            alias_reg_dict[alias_reg] = str(each_alias).upper()
    regs_in_cpy = regs_in.copy()
    for reg in regs_in_cpy:
        if str(reg).upper() in alias_reg_dict.keys():
            regs_in.remove(reg)
        else:
            if str(reg).upper() in uses_regs:
                regs_in.remove(reg)
    regs_out_cpy = regs_out.copy()
    for reg in regs_out_cpy:
        if str(reg).upper() in alias_reg_dict.keys():
            regs_out.remove(reg)
        else:
            if str(reg).upper() in defs_regs:
                regs_out.remove(reg)
    let_uses = ""
    let_defs = ""
    if len(uses_regs) != 0:
        let_uses = "Uses = " + "[%s]" % ", ".join(map(str, sorted(set(uses_regs))))
    if len(defs_regs) != 0:
        let_defs = "Defs = " + "[%s]" % ", ".join(map(str, sorted(set(defs_regs))))
    instrfield_regs_ins_cpy = instrfield_regs_ins.copy()
    instrfield_regs_outs_cpy = instrfield_regs_outs.copy()
    for elem in instrfield_regs_ins_cpy:
        x = re.split(":", elem)
        x = x[1:]
        x = str(x).replace("$", "").replace("'", "").replace("[", "").replace("]", "")
        if x not in regs_in:
            if x not in instrfield_imm.keys():
                instrfield_regs_ins.remove(elem)
    for elem in instrfield_regs_outs_cpy:
        x = re.split(":", elem)
        x = x[1:]
        x = str(x).replace("$", "").replace("'", "").replace("[", "").replace("]", "")
        if x not in regs_out:
            instrfield_regs_outs.remove(elem)
    instrfield_regs_ins_copy = instrfield_regs_ins.copy()
    for elem in instrfield_regs_ins:
        x = re.split(":", elem)
        ref = x[0]
        x = x[1:]
        x = str(x).replace("$", "").replace("'", "").replace("[", "").replace("]", "")
        if str(x) in instrfield_imm.keys():
            if "excluded_values" not in instructions[key]:
                ref = ref.split("non")[0]
                instrfield_regs_ins_copy.remove(elem)
                instrfield_regs_ins_copy.append(ref + ":$" + x)
    instrfield_regs_ins = instrfield_regs_ins_copy.copy()
    instrfield_regs_outs_ord = dict()
    instrfield_regs_ins_ord = dict()
    dsyntax = str(instructions[key]["syntax"]).replace("(", ",").replace(")", "")
    dsyntax_list = dsyntax.split(",")[1:]
    index = 0
    instrfield_regs_outs.sort(reverse=True)
    for register in instrfield_regs_outs:
        exitValue = False
        exitValue2 = False
        for element in dsyntax_list:
            if exitValue is True:
                break
            if (
                element.replace("[", "")
                .replace("]", "")
                .replace("'", "")
                .replace(" ", "")
                in instrfield_ref.keys()
            ):
                for input_elem in instructions[key]["outputs"]:
                    if (
                        element.replace("[", "")
                        .replace("]", "")
                        .replace("'", "")
                        .replace(" ", "")
                        in input_elem
                    ):
                        if register not in instrfield_regs_outs_ord.values():
                            instrfield_regs_outs_ord[index] = register
                            index += 1
                            exitValue = True
                            break
            else:
                if "sp" in register:
                    instrfield_regs_outs_ord[index] = register
                    index += 1
                    exitValue = True

    for element in dsyntax_list:
        for register in instrfield_regs_ins:
            if (
                element.replace("[", "")
                .replace("]", "")
                .replace("'", "")
                .replace(" ", "")
                in register
            ):
                if (
                    element.replace("[", "")
                    .replace("]", "")
                    .replace("'", "")
                    .replace(" ", "")
                    in instrfield_ref.keys()
                ):
                    for input_elem in instructions[key]["inputs"]:
                        if (
                            element.replace("[", "")
                            .replace("]", "")
                            .replace("'", "")
                            .replace(" ", "")
                            in input_elem
                        ):
                            instrfield_regs_ins_ord[register] = "ref"
                            break
                else:
                    instrfield_regs_ins_ord[register] = "imm"
    instrfield_regs_outs.clear()
    instrfield_regs_ins.clear()
    for element in instrfield_regs_ins_ord.keys():
        if instrfield_regs_ins_ord[element] == "ref":
            instrfield_regs_ins.append(element)
        elif "sp" in element.lower():
            instrfield_regs_ins.append(element)
    for element in instrfield_regs_ins_ord.keys():
        if instrfield_regs_ins_ord[element] == "imm":
            if element not in instrfield_regs_ins:
                instrfield_regs_ins.append(element)
    for element in instrfield_regs_outs_ord.values():
        if element in instrfield_regs_ins_ord.keys():
            instrfield_regs_outs.append(element + "_wb")
        else:
            instrfield_regs_outs.append(element)
    exitValue = False
    for element in instrfield_regs_ins_ord.keys():
        if exitValue is True:
            break
        for reg in instrfield_regs_outs_ord.keys():
            if "sp" in element:
                aux = element.split(":$")[1]
                if "sp" in instrfield_regs_outs_ord[reg]:
                    instrfield_regs_outs.remove(instrfield_regs_outs_ord[reg])
                    instrfield_regs_outs_ord[reg] = instrfield_regs_outs_ord[
                        reg
                    ].replace(aux, aux + "_wb")
                    if instrfield_regs_outs_ord[reg] not in instrfield_regs_outs:
                        instrfield_regs_outs.append(instrfield_regs_outs_ord[reg])
                    exitValue = True
    instrfield_regs_outs = str(instrfield_regs_outs)
    instrfield_regs_ins = str(instrfield_regs_ins)
    for reg in regs_in:
        if reg in regs_out:
            reg_constraint = reg + "_wb"
            decoderMethodRegs.append(reg_constraint)
            regs_out.remove(reg)
            regs_out.append(reg_constraint)
            pattern = "$" + reg
            pattern_replace = "$" + reg_constraint
            if pattern not in instrfield_regs_outs:
                instrfield_regs_outs = instrfield_regs_outs.replace(
                    pattern, pattern_replace
                )
            constraint += (
                '\tlet Constraints = "'
                + "$"
                + reg
                + " = "
                + "$"
                + reg_constraint
                + '";\n'
            )
            if disableEncoding is True:
                disableEncodingLet += (
                    '\tlet DisableEncoding = "' + "$" + reg_constraint + '";'
                )
        if (
            "sideEffectInstrfield" in config_variables.keys()
            and reg == config_variables["sideEffectInstrfield"]
        ):
            sideEffects = True
    for reg in regs_out:
        if (
            "sideEffectInstrfield" in config_variables.keys()
            and reg == config_variables["sideEffectInstrfield"]
        ):
            sideEffects = True
    instrfield_regs_outs = instrfield_regs_outs.replace("[", "")
    instrfield_regs_outs = instrfield_regs_outs.replace("]", "")
    instrfield_regs_outs = instrfield_regs_outs.replace("'", "")
    instrfield_regs_ins = instrfield_regs_ins.replace("[", "")
    instrfield_regs_ins = instrfield_regs_ins.replace("]", "")
    instrfield_regs_ins = instrfield_regs_ins.replace("'", "")
    if len(list(instrfield_regs_outs)) > 0:
        define += "(outs " + str(instrfield_regs_outs) + "), "
    else:
        define += "(outs" + str(instrfield_regs_outs) + "), "
    if len(list(instrfield_regs_ins)) > 0:
        define += "(ins " + str(instrfield_regs_ins) + "), "
    else:
        define += "(ins" + str(instrfield_regs_ins) + "), "
    syntax = list()
    for elem in instructions[key]["dsyntax"]:
        if elem in instrfield_ref:
            syntax.append(elem)
        elif elem in instrfield_imm:
            syntax.append(elem)
        else:
            syntax.append(elem)
    if len(syntax) > 1:
        syntax = syntax[1:]
    else:
        syntax = ""
    if "load" in instructions[key]["attributes"]:
        instructions_load_store[key] = (
            str(instrfield_regs_outs) + ", " + str(instrfield_regs_ins)
        )
    if "store" in instructions[key]["attributes"]:
        instructions_load_store[key] = (
            str(instrfield_regs_outs) + ", " + str(instrfield_regs_ins)
        )
    syntax = str(syntax).replace("'", "")
    syntax = str(syntax).replace("[", "")
    syntax = syntax.replace("]", "")
    syntax = syntax.replace('"', "")
    syntax = syntax.replace(" ,", "")
    if instrfield_regs_outs != "" and instrfield_regs_ins != "":
        alias_instruction_syntax_dict[key] = (
            instrfield_regs_outs + ", " + instrfield_regs_ins
        )
    else:
        if instrfield_regs_outs == "":
            alias_instruction_syntax_dict[key] = instrfield_regs_ins
        elif instrfield_regs_ins == "":
            alias_instruction_syntax_dict[key] = instrfield_regs_outs
    if width == config_variables["LLVMStandardInstructionWidth"]:
        if hasImm is True:
            if "isBranch" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatB"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            elif "jump" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatJ"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            elif "u-type" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatU"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            elif "store" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatS"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            else:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatI"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
        else:
            if "isBranch" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatB"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            elif "jump" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatJ"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            elif "u-type" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatU"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            elif "store" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatS"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            else:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatR"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
    else:
        if hasImm is True:
            if "isBranch" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatCB"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            elif "store" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatCS"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            else:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatCI"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
        else:
            if "isBranch" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatCB"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            elif "store" in instructions[key]["attributes"]:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatCS"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
            else:
                define += (
                    '"'
                    + syntax_elements_cpy[0].lower()
                    + '"'
                    + ", "
                    + '"'
                    + str(syntax)
                    + '"'
                    + ", "
                    + "[], "
                    + config_variables["instructionFormatCR"]
                    + ">, "
                    + "Sched<"
                    + str(schedule)
                    + ">{\n"
                )
    for reg in list_regs:
        reg = reg.replace("$", "")
        if reg in instrfield_ref.keys():
            size = int(instrfield_ref[reg]["size"]) + int(instrfield_ref[reg]["shift"])
            content += "\tbits<" + str(size) + "> " + reg + ";\n"
        elif reg in instrfield_imm.keys():
            size = int(instrfield_imm[reg]["size"]) + int(instrfield_imm[reg]["shift"])
            content += "\tbits<" + str(size) + "> " + reg + ";\n"
    for instrfield in instructions[key]["fields"][0].keys():
        if instrfield in instrfield_ref.keys():
            shift = "0"
            if "shift" in instrfield_ref[instrfield].keys():
                shift = instrfield_ref[instrfield]["shift"]
            size = int(instrfield_ref[instrfield]["size"])
            size = size + int(shift) - 1
            size_first = size
            for index in range(len(instrfield_ref[instrfield]["range"])):
                end = str(instrfield_ref[instrfield]["range"][index][0])
                start = str(instrfield_ref[instrfield]["range"][index][1])
                if instrfield != "opcode" and instrfield != "op_c":
                    if instructions[key]["fields"][0][instrfield] == "reg":
                        content += (
                            "\tlet Inst{"
                            + end
                            + "-"
                            + start
                            + "} = "
                            + instrfield
                            + ";\n"
                        )
                    else:
                        content += (
                            "\tlet Inst{"
                            + end
                            + "-"
                            + start
                            + "} = "
                            + str(instructions[key]["fields"][0][instrfield])
                            + ";\n"
                        )
                else:
                    content += (
                        "\tlet Inst{"
                        + end
                        + "-"
                        + start
                        + "} = "
                        + str(instructions[key]["fields"][0][instrfield])
                        + ";\n"
                    )
        elif instrfield in instrfield_imm.keys():
            shift = instrfield_imm[instrfield]["shift"]
            size = int(instrfield_imm[instrfield]["size"])
            size = size + int(shift) - 1
            size_first = size
            if len(instrfield_imm[instrfield]["range"]) > 1:
                for index in range(len(instrfield_imm[instrfield]["range"])):
                    end = str(instrfield_imm[instrfield]["range"][index][0])
                    start = str(instrfield_imm[instrfield]["range"][index][1])
                    if instrfield != "opcode" and instrfield != "op_c":
                        if instructions[key]["fields"][0][instrfield] == "imm":
                            diff = int(end) - int(start)
                            size_last = size_first - diff
                            content += (
                                "\tlet Inst{"
                                + end
                                + "-"
                                + start
                                + "} = "
                                + instrfield
                                + "{"
                                + str(size_first)
                                + "-"
                                + str(size_last)
                                + "}"
                                + ";\n"
                            )
                            size_first = size_last - 1
                        else:
                            content += (
                                "\tlet Inst{"
                                + end
                                + "-"
                                + start
                                + "} = "
                                + str(instructions[key]["fields"][0][instrfield])
                                + ";\n"
                            )
                    else:
                        content += (
                            "\tlet Inst{"
                            + end
                            + "-"
                            + start
                            + "} = "
                            + str(instructions[key]["fields"][0][instrfield])
                            + ";\n"
                        )
            else:
                end = str(instrfield_imm[instrfield]["range"][0][0])
                start = str(instrfield_imm[instrfield]["range"][0][1])
                if instrfield != "opcode" and instrfield != "op_c":
                    if instructions[key]["fields"][0][instrfield] == "imm":
                        diff = int(end) - int(start)
                        size_last = size_first - diff
                        content += (
                            "\tlet Inst{"
                            + end
                            + "-"
                            + start
                            + "} = "
                            + instrfield
                            + "{"
                            + str(size_first)
                            + "-"
                            + str(size_last)
                            + "}"
                            + ";\n"
                        )
                        size_first = size_last - 1
                    else:
                        content += (
                            "\tlet Inst{"
                            + end
                            + "-"
                            + start
                            + "} = "
                            + str(instructions[key]["fields"][0][instrfield])
                            + ";\n"
                        )
                else:
                    content += (
                        "\tlet Inst{"
                        + end
                        + "-"
                        + start
                        + "} = "
                        + str(instructions[key]["fields"][0][instrfield])
                        + ";\n"
                    )
    content += constraint + disableEncodingLet + "\n"
    decoderMethodRegs = list(set(decoderMethodRegs))
    decoderMethod += "".join(map(str.capitalize, sorted(decoderMethodRegs))) + '"'
    if "_hint" in key:
        content += "\t" + decoderMethod + ";\n"
    content += "}"
    if decoderNamespace_predicate != "":
        decoderNamespace = (
            "let DecoderNamespace = " + '"' + decoderNamespace_predicate + '"'
        )
    else:
        if "DecoderNamespace" in config_variables.keys():
            if extension.capitalize() in config_variables["DecoderNamespace"].keys():
                decoderNamespace = (
                    "let DecoderNamespace = "
                    + '"'
                    + config_variables["DecoderNamespace"][extension.capitalize()]
                    + '"'
                )
            else:
                key_decoder = "Others"
                decoderNamespace = (
                    "let DecoderNamespace = "
                    + '"'
                    + config_variables["DecoderNamespace"][key_decoder]
                    + '"'
                )
    if predicate_checked is True:
        decoderNamespace += ", " + predicates
    if "isBranch" in instructions[key]["attributes"]:
        decoderNamespace += ", " + "isBranch = 1"
    if "isTerminator" in instructions[key]["attributes"]:
        decoderNamespace += ", " + " isTerminator = 1"
    if decoderNamespace != "":
        content += "\n}"
    decoderNamespace = decoderNamespace.rstrip(", ")
    decoderNamespace += " in {\n"
    if sideEffects is True:
        if "load" in instructions[key]["attributes"]:
            if "jump" in instructions[key]["attributes"]:
                def_let_sideEffectsLoadTrue = (
                    "isCall = 1" + ", " + def_let_sideEffectsLoadTrue
                )
            if let_uses != "":
                def_let_sideEffectsLoadTrue = let_uses + def_let_sideEffectsLoadTrue
            if let_defs != "":
                def_let_sideEffectsLoadTrue = let_defs + def_let_sideEffectsLoadTrue
            def_let_sideEffectsBasic = "let " + def_let_sideEffectsLoadTrue
            return decoderNamespace + def_let_sideEffectsLoadTrue + define + content
        elif "store" in instructions[key]["attributes"]:
            if "jump" in instructions[key]["attributes"]:
                def_let_sideEffectsStoreTrue = (
                    "isCall = 1" + ", " + def_let_sideEffectsStoreTrue
                )
            if let_uses != "":
                def_let_sideEffectsStoreTrue = (
                    let_uses + ", " + def_let_sideEffectsStoreTrue
                )
            if let_defs != "":
                def_let_sideEffectsStoreTrue = (
                    let_defs + ", " + def_let_sideEffectsStoreTrue
                )
            def_let_sideEffectsLoadTrue = "let " + def_let_sideEffectsLoadTrue
            return decoderNamespace + def_let_sideEffectsStoreTrue + define + content
        else:
            if "jump" in instructions[key]["attributes"]:
                def_let_sideEffects = "isCall = 1" + ", " + def_let_sideEffects
            if let_uses != "":
                def_let_sideEffects = let_uses + ", " + def_let_sideEffects
            if let_defs != "":
                def_let_sideEffects = let_defs + ", " + def_let_sideEffects
            def_let_sideEffects = "let " + def_let_sideEffects
            return decoderNamespace + def_let_sideEffects + define + content
    else:
        if "load" in instructions[key]["attributes"]:
            if "jump" in instructions[key]["attributes"]:
                def_let_sideEffectsLoad = "isCall = 1" + ", " + def_let_sideEffectsLoad
            if let_uses != "":
                def_let_sideEffectsLoad = let_uses + ", " + def_let_sideEffectsLoad
            if let_defs != "":
                def_let_sideEffectsLoad = let_defs + ", " + def_let_sideEffectsLoad
            def_let_sideEffectsLoad = "let " + def_let_sideEffectsLoad
            return decoderNamespace + def_let_sideEffectsLoad + define + content
        elif "store" in instructions[key]["attributes"]:
            if "jump" in instructions[key]["attributes"]:
                def_let_sideEffectsStore = (
                    "isCall = 1" + ", " + def_let_sideEffectsStore
                )
            if let_uses != "":
                def_let_sideEffectsStore = let_uses + ", " + def_let_sideEffectsStore
            if let_defs != "":
                def_let_sideEffectsStore = let_defs + ", " + def_let_sideEffectsStore
            def_let_sideEffectsStore = "let " + def_let_sideEffectsStore
            return decoderNamespace + def_let_sideEffectsStore + define + content
        else:
            if "jump" in instructions[key]["attributes"]:
                def_let_sideEffectsBasic = (
                    "isCall = 1" + ", " + def_let_sideEffectsBasic
                )
            if let_uses != "":
                def_let_sideEffectsBasic = let_uses + ", " + def_let_sideEffectsBasic
            if let_defs != "":
                def_let_sideEffectsBasic = let_defs + ", " + def_let_sideEffectsBasic
            def_let_sideEffectsBasic = "let " + def_let_sideEffectsBasic
            return decoderNamespace + def_let_sideEffectsBasic + define + content


## This function writes the definition in a RISCVInstrInfo.td file for each instruction parsed from ADL
#
# @param file_name ADL file name parsed for gathering all information
# @param extensions_list A list containing all the extensions given by the user in the command line
# @return The content of RISCVInstrInfo.td
def generate_file_instructions(file_name, extensions_list):
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[
        0
    ]
    list_instructions_with_regs = adl_parser.parse_instructions_from_adl(
        config_variables["ADLName"]
    )[1]
    list_instructions_with_imms = adl_parser.parse_instructions_from_adl(
        config_variables["ADLName"]
    )[2]
    instrfield_imm = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
    instruction_map = dict()
    for instruction in instructions.keys():
        instruction_map[instruction] = False
    file_name_cpy = file_name
    sorting_attributes = adl_parser.parse_instructions_from_adl(
        config_variables["ADLName"]
    )[3]
    sorting_attributes_copy = sorting_attributes.copy()
    if len(extensions_list) > 0:
        for element in sorting_attributes_copy:
            if element not in extensions_list:
                sorting_attributes.remove(element)
    sorting_attributes.sort()
    for attribute in sorting_attributes:
        changed_file_name = False
        if "LLVMExt" + str(attribute).capitalize() not in config_variables.keys():
            f = open(file_name, "a")
            for key in instructions.keys():
                if "ignored" not in instructions[key]["attributes"]:
                    for attribute in instructions[key]["attributes"]:
                        if attribute == config_variables["LLVMPrivilegedAttributes"]:
                            if (
                                instruction_map[key] is False
                                and attribute in instructions[key]["attributes"]
                            ):
                                instruction_map[key] = True
                                if key in list_instructions_with_regs:
                                    hasImm = False
                                    if (
                                        key
                                        not in config_variables["IgnoredInstructions"]
                                    ):
                                        disableEncoding = True
                                        f.write(
                                            "//===----------------------------------------------------------------------===//\n"
                                        )
                                        f.write("// Privileged instructions\n")
                                        f.write(
                                            "//===----------------------------------------------------------------------===//\n"
                                        )
                                        f.write(
                                            generate_instruction_define(
                                                instructions,
                                                list_instructions_with_regs,
                                                key,
                                                instructions[key]["width"],
                                                [],
                                                hasImm,
                                                disableEncoding,
                                                extensions_list,
                                            )
                                        )
                                        f.write("\n")
                                        if generate_pattern_for_instructions(key) != "":
                                            f.write(
                                                generate_pattern_for_instructions(key)
                                            )
                                            f.write("\n\n")
                                        else:
                                            f.write("\n")
                                elif key in list_instructions_with_imms:
                                    hasImm = True
                                    if "pseudo" not in instructions[key].keys():
                                        for field in instructions[key]["fields"][
                                            0
                                        ].keys():
                                            if (
                                                instructions[key]["fields"][0][field]
                                                == "imm"
                                            ):
                                                if (
                                                    key
                                                    not in config_variables[
                                                        "IgnoredInstructions"
                                                    ]
                                                ):
                                                    instr_field_size = instrfield_imm[
                                                        field
                                                    ]["size"]
                                                    if (
                                                        "signed"
                                                        in instrfield_imm[field].keys()
                                                    ):
                                                        if (
                                                            instrfield_imm[field][
                                                                "signed"
                                                            ]
                                                            == "true"
                                                        ):
                                                            if (
                                                                instrfield_imm[field][
                                                                    "shift"
                                                                ]
                                                                != "0"
                                                            ):
                                                                if (
                                                                    "one_extended"
                                                                    in instrfield_imm[
                                                                        field
                                                                    ].keys()
                                                                ):
                                                                    instr_field_classname = (
                                                                        "simm"
                                                                        + str(
                                                                            int(
                                                                                instr_field_size
                                                                            )
                                                                            + int(
                                                                                instrfield_imm[
                                                                                    field
                                                                                ][
                                                                                    "shift"
                                                                                ]
                                                                            )
                                                                            + 1
                                                                        )
                                                                        + "_lsb"
                                                                    )
                                                                    for _ in range(
                                                                        int(
                                                                            instrfield_imm[
                                                                                field
                                                                            ][
                                                                                "shift"
                                                                            ]
                                                                        )
                                                                    ):
                                                                        instr_field_classname += (
                                                                            "0"
                                                                        )
                                                                    instr_field_classname += (
                                                                        "_neg"
                                                                    )
                                                                else:
                                                                    instr_field_classname = (
                                                                        "simm"
                                                                        + str(
                                                                            int(
                                                                                instr_field_size
                                                                            )
                                                                            + int(
                                                                                instrfield_imm[
                                                                                    field
                                                                                ][
                                                                                    "shift"
                                                                                ]
                                                                            )
                                                                        )
                                                                        + "_Lsb"
                                                                    )
                                                                for _ in range(
                                                                    int(
                                                                        instrfield_imm[
                                                                            field
                                                                        ]["shift"]
                                                                    )
                                                                ):
                                                                    instr_field_classname += (
                                                                        "0"
                                                                    )
                                                                if (
                                                                    "excluded_values"
                                                                    in instructions[
                                                                        key
                                                                    ].keys()
                                                                ):
                                                                    for elem in range(
                                                                        len(
                                                                            instructions[
                                                                                key
                                                                            ][
                                                                                "excluded_values"
                                                                            ][
                                                                                field
                                                                            ]
                                                                        )
                                                                    ):
                                                                        instr_field_classname += (
                                                                            "Non"
                                                                            + str(
                                                                                num2words.num2words(
                                                                                    int(
                                                                                        instructions[
                                                                                            key
                                                                                        ][
                                                                                            "excluded_values"
                                                                                        ][
                                                                                            field
                                                                                        ][
                                                                                            elem
                                                                                        ]
                                                                                    )
                                                                                )
                                                                            ).capitalize()
                                                                        )
                                                            else:
                                                                if (
                                                                    "one_extended"
                                                                    in instrfield_imm[
                                                                        field
                                                                    ].keys()
                                                                ):
                                                                    instr_field_classname = (
                                                                        "simm"
                                                                        + str(
                                                                            int(
                                                                                instr_field_size
                                                                            )
                                                                            + int(
                                                                                instrfield_imm[
                                                                                    field
                                                                                ][
                                                                                    "shift"
                                                                                ]
                                                                            )
                                                                            + 1
                                                                        )
                                                                        + "_neg"
                                                                    )
                                                                else:
                                                                    instr_field_classname = "simm" + str(
                                                                        int(
                                                                            instr_field_size
                                                                        )
                                                                        + int(
                                                                            instrfield_imm[
                                                                                field
                                                                            ][
                                                                                "shift"
                                                                            ]
                                                                        )
                                                                    )
                                                                if (
                                                                    "excluded_values"
                                                                    in instructions[
                                                                        key
                                                                    ].keys()
                                                                ):
                                                                    for elem in range(
                                                                        len(
                                                                            instructions[
                                                                                key
                                                                            ][
                                                                                "excluded_values"
                                                                            ][
                                                                                field
                                                                            ]
                                                                        )
                                                                    ):
                                                                        instr_field_classname += (
                                                                            "Non"
                                                                            + str(
                                                                                num2words.num2words(
                                                                                    int(
                                                                                        instructions[
                                                                                            key
                                                                                        ][
                                                                                            "excluded_values"
                                                                                        ][
                                                                                            field
                                                                                        ][
                                                                                            elem
                                                                                        ]
                                                                                    )
                                                                                )
                                                                            ).capitalize()
                                                                        )
                                                            if (
                                                                instr_field_classname
                                                                in instrfield_classes.keys()
                                                            ):
                                                                instrfield_classes[
                                                                    instr_field_classname
                                                                ] += (field + " ")
                                                            elif (
                                                                instr_field_classname
                                                                not in instrfield_classes.keys()
                                                            ):
                                                                instrfield_classes[
                                                                    instr_field_classname
                                                                ] = (field + " ")
                                                    else:
                                                        if (
                                                            instrfield_imm[field][
                                                                "shift"
                                                            ]
                                                            != "0"
                                                        ):
                                                            if (
                                                                "one_extended"
                                                                in instrfield_imm[
                                                                    field
                                                                ].keys()
                                                            ):
                                                                instr_field_classname = (
                                                                    "uimm"
                                                                    + str(
                                                                        int(
                                                                            instr_field_size
                                                                        )
                                                                        + int(
                                                                            instrfield_imm[
                                                                                field
                                                                            ][
                                                                                "shift"
                                                                            ]
                                                                        )
                                                                        + 1
                                                                    )
                                                                    + "_lsb"
                                                                    + "_neg"
                                                                )
                                                            else:
                                                                instr_field_classname = (
                                                                    "uimm"
                                                                    + str(
                                                                        int(
                                                                            instr_field_size
                                                                        )
                                                                        + int(
                                                                            instrfield_imm[
                                                                                field
                                                                            ][
                                                                                "shift"
                                                                            ]
                                                                        )
                                                                    )
                                                                    + "_lsb"
                                                                )
                                                            for _ in range(
                                                                int(
                                                                    instrfield_imm[
                                                                        field
                                                                    ]["shift"]
                                                                )
                                                            ):
                                                                instr_field_classname += (
                                                                    "0"
                                                                )
                                                            if (
                                                                "excluded_values"
                                                                in instructions[
                                                                    key
                                                                ].keys()
                                                            ):
                                                                for elem in range(
                                                                    len(
                                                                        instructions[
                                                                            key
                                                                        ][
                                                                            "excluded_values"
                                                                        ][
                                                                            field
                                                                        ]
                                                                    )
                                                                ):
                                                                    instr_field_classname += (
                                                                        "Non"
                                                                        + str(
                                                                            num2words.num2words(
                                                                                int(
                                                                                    instructions[
                                                                                        key
                                                                                    ][
                                                                                        "excluded_values"
                                                                                    ][
                                                                                        field
                                                                                    ][
                                                                                        elem
                                                                                    ]
                                                                                )
                                                                            )
                                                                        ).capitalize()
                                                                    )
                                                        else:
                                                            if (
                                                                "one_extended"
                                                                in instrfield_imm[
                                                                    field
                                                                ].keys()
                                                            ):
                                                                instr_field_classname = (
                                                                    "uimm"
                                                                    + str(
                                                                        int(
                                                                            instr_field_size
                                                                        )
                                                                        + int(
                                                                            instrfield_imm[
                                                                                field
                                                                            ][
                                                                                "shift"
                                                                            ]
                                                                        )
                                                                        + 1
                                                                    )
                                                                    + "_neg"
                                                                )
                                                            else:
                                                                instr_field_classname = "uimm" + str(
                                                                    int(
                                                                        instr_field_size
                                                                    )
                                                                    + int(
                                                                        instrfield_imm[
                                                                            field
                                                                        ]["shift"]
                                                                    )
                                                                )
                                                            if (
                                                                "excluded_values"
                                                                in instructions[
                                                                    key
                                                                ].keys()
                                                            ):
                                                                for elem in range(
                                                                    len(
                                                                        instructions[
                                                                            key
                                                                        ][
                                                                            "excluded_values"
                                                                        ][
                                                                            field
                                                                        ]
                                                                    )
                                                                ):
                                                                    instr_field_classname += (
                                                                        "Non"
                                                                        + str(
                                                                            num2words.num2words(
                                                                                int(
                                                                                    instructions[
                                                                                        key
                                                                                    ][
                                                                                        "excluded_values"
                                                                                    ][
                                                                                        field
                                                                                    ][
                                                                                        elem
                                                                                    ]
                                                                                )
                                                                            )
                                                                        ).capitalize()
                                                                    )
                                                        if (
                                                            instr_field_classname
                                                            in instrfield_classes.keys()
                                                        ):
                                                            instrfield_classes[
                                                                instr_field_classname
                                                            ] += (field + " ")
                                                        elif (
                                                            instr_field_classname
                                                            not in instrfield_classes.keys()
                                                        ):
                                                            instrfield_classes[
                                                                instr_field_classname
                                                            ] = (field + " ")
                                                    disableEncoding = True
                                        f.write(
                                            generate_instruction_define(
                                                instructions,
                                                list_instructions_with_imms,
                                                key,
                                                instructions[key]["width"],
                                                [],
                                                hasImm,
                                                disableEncoding,
                                                extensions_list,
                                            )
                                        )
                                        f.write("\n")
                                        if generate_pattern_for_instructions(key) != "":
                                            f.write(
                                                generate_pattern_for_instructions(key)
                                            )
                                            f.write("\n\n")
                                        else:
                                            f.write("\n")
            f.close()
        elif "LLVMExt" + str(attribute).capitalize() in config_variables.keys():
            if (
                config_variables["LLVMExt" + str(attribute).capitalize()] + "Extension"
                in config_variables.keys()
            ):
                generated = False
                file_name = file_name_cpy
                file_name = str(file_name).split(".td")
                file_name = (
                    file_name[0]
                    + config_variables[
                        config_variables["LLVMExt" + str(attribute).capitalize()]
                        + "Extension"
                    ]
                )
                if "_gen" in file_name:
                    file_name = file_name.replace("_gen", "")
                    generated = True
                if generated is True:
                    file_name = file_name + "_gen" + ".td"
                else:
                    file_name = file_name + ".td"
                changed_file_name = True
            if changed_file_name is True:
                if os.path.exists(file_name):
                    os.remove(file_name)
                legalDisclaimer.get_copyright(file_name)
                legalDisclaimer.get_generated_file(file_name)
            else:
                file_name = file_name_cpy
            f = open(file_name, "a")
            rv_predicate = "Is" + config_variables["BaseArchitecture"].upper()
            if (
                rv_predicate
                != config_variables["LLVMExt" + str(attribute).capitalize()]
            ):
                f.write(
                    "let Predicates = ["
                    + rv_predicate
                    + ", "
                    + config_variables["LLVMExt" + str(attribute).capitalize()]
                    + "] in {\n"
                )
            else:
                f.write(
                    "let Predicates = ["
                    + config_variables["LLVMExt" + str(attribute).capitalize()]
                    + "] in {\n"
                )
            f.write("\n")
            for key in instructions.keys():
                if "ignored" not in instructions[key]["attributes"]:
                    if (
                        instruction_map[key] is False
                        and attribute in instructions[key]["attributes"]
                    ):
                        instruction_map[key] = True
                        if key in list_instructions_with_regs:
                            hasImm = False
                            if key not in config_variables["IgnoredInstructions"]:
                                disableEncoding = True
                                f.write(
                                    generate_instruction_define(
                                        instructions,
                                        list_instructions_with_regs,
                                        key,
                                        instructions[key]["width"],
                                        [],
                                        hasImm,
                                        disableEncoding,
                                        extensions_list,
                                    )
                                )
                                f.write("\n")
                                if generate_pattern_for_instructions(key) != "":
                                    f.write(generate_pattern_for_instructions(key))
                                    f.write("\n\n")
                                else:
                                    f.write("\n")
                        elif key in list_instructions_with_imms:
                            hasImm = True
                            if "pseudo" not in instructions[key].keys():
                                for field in instructions[key]["fields"][0].keys():
                                    if instructions[key]["fields"][0][field] == "imm":
                                        if (
                                            key
                                            not in config_variables[
                                                "IgnoredInstructions"
                                            ]
                                        ):
                                            instr_field_size = instrfield_imm[field][
                                                "size"
                                            ]
                                            if "signed" in instrfield_imm[field].keys():
                                                if (
                                                    instrfield_imm[field]["signed"]
                                                    == "true"
                                                ):
                                                    if (
                                                        instrfield_imm[field]["shift"]
                                                        != "0"
                                                    ):
                                                        if (
                                                            "one_extended"
                                                            in instrfield_imm[
                                                                field
                                                            ].keys()
                                                        ):
                                                            instr_field_classname = (
                                                                "simm"
                                                                + str(
                                                                    int(
                                                                        instr_field_size
                                                                    )
                                                                    + int(
                                                                        instrfield_imm[
                                                                            field
                                                                        ]["shift"]
                                                                    )
                                                                    + 1
                                                                )
                                                                + "_lsb"
                                                            )
                                                            for _ in range(
                                                                int(
                                                                    instrfield_imm[
                                                                        field
                                                                    ]["shift"]
                                                                )
                                                            ):
                                                                instr_field_classname += (
                                                                    "0"
                                                                )
                                                            instr_field_classname += (
                                                                "_neg"
                                                            )
                                                        else:
                                                            instr_field_classname = (
                                                                "simm"
                                                                + str(
                                                                    int(
                                                                        instr_field_size
                                                                    )
                                                                    + int(
                                                                        instrfield_imm[
                                                                            field
                                                                        ]["shift"]
                                                                    )
                                                                )
                                                                + "_Lsb"
                                                            )
                                                            for _ in range(
                                                                int(
                                                                    instrfield_imm[
                                                                        field
                                                                    ]["shift"]
                                                                )
                                                            ):
                                                                instr_field_classname += (
                                                                    "0"
                                                                )
                                                        if (
                                                            "excluded_values"
                                                            in instructions[key].keys()
                                                        ):
                                                            for elem in range(
                                                                len(
                                                                    instructions[key][
                                                                        "excluded_values"
                                                                    ][field]
                                                                )
                                                            ):
                                                                instr_field_classname += (
                                                                    "Non"
                                                                    + str(
                                                                        num2words.num2words(
                                                                            int(
                                                                                instructions[
                                                                                    key
                                                                                ][
                                                                                    "excluded_values"
                                                                                ][
                                                                                    field
                                                                                ][
                                                                                    elem
                                                                                ]
                                                                            )
                                                                        )
                                                                    ).capitalize()
                                                                )
                                                    else:
                                                        if (
                                                            "one_extended"
                                                            in instrfield_imm[
                                                                field
                                                            ].keys()
                                                        ):
                                                            instr_field_classname = (
                                                                "simm"
                                                                + str(
                                                                    int(
                                                                        instr_field_size
                                                                    )
                                                                    + int(
                                                                        instrfield_imm[
                                                                            field
                                                                        ]["shift"]
                                                                    )
                                                                    + 1
                                                                )
                                                            )
                                                        else:
                                                            instr_field_classname = (
                                                                "simm"
                                                                + str(
                                                                    int(
                                                                        instr_field_size
                                                                    )
                                                                    + int(
                                                                        instrfield_imm[
                                                                            field
                                                                        ]["shift"]
                                                                    )
                                                                )
                                                            )
                                                        if (
                                                            "excluded_values"
                                                            in instructions[key].keys()
                                                        ):
                                                            for elem in range(
                                                                len(
                                                                    instructions[key][
                                                                        "excluded_values"
                                                                    ][field]
                                                                )
                                                            ):
                                                                instr_field_classname += (
                                                                    "Non"
                                                                    + str(
                                                                        num2words.num2words(
                                                                            int(
                                                                                instructions[
                                                                                    key
                                                                                ][
                                                                                    "excluded_values"
                                                                                ][
                                                                                    field
                                                                                ][
                                                                                    elem
                                                                                ]
                                                                            )
                                                                        )
                                                                    ).capitalize()
                                                                )
                                                    if (
                                                        instr_field_classname
                                                        in instrfield_classes.keys()
                                                    ):
                                                        instrfield_classes[
                                                            instr_field_classname
                                                        ] += (field + " ")
                                                    elif (
                                                        instr_field_classname
                                                        not in instrfield_classes.keys()
                                                    ):
                                                        instrfield_classes[
                                                            instr_field_classname
                                                        ] = (field + " ")
                                            else:
                                                if (
                                                    instrfield_imm[field]["shift"]
                                                    != "0"
                                                ):
                                                    instr_field_classname = (
                                                        "uimm"
                                                        + str(
                                                            int(instr_field_size)
                                                            + int(
                                                                instrfield_imm[field][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + "_lsb"
                                                    )
                                                    for _ in range(
                                                        int(
                                                            instrfield_imm[field][
                                                                "shift"
                                                            ]
                                                        )
                                                    ):
                                                        instr_field_classname += "0"
                                                    if (
                                                        "excluded_values"
                                                        in instructions[key].keys()
                                                    ):
                                                        for elem in range(
                                                            len(
                                                                instructions[key][
                                                                    "excluded_values"
                                                                ][field]
                                                            )
                                                        ):
                                                            instr_field_classname += (
                                                                "Non"
                                                                + str(
                                                                    num2words.num2words(
                                                                        int(
                                                                            instructions[
                                                                                key
                                                                            ][
                                                                                "excluded_values"
                                                                            ][
                                                                                field
                                                                            ][
                                                                                elem
                                                                            ]
                                                                        )
                                                                    )
                                                                ).capitalize()
                                                            )
                                                else:
                                                    instr_field_classname = (
                                                        "uimm"
                                                        + str(
                                                            int(instr_field_size)
                                                            + int(
                                                                instrfield_imm[field][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                    )
                                                    if (
                                                        "excluded_values"
                                                        in instructions[key].keys()
                                                    ):
                                                        for elem in range(
                                                            len(
                                                                instructions[key][
                                                                    "excluded_values"
                                                                ][field]
                                                            )
                                                        ):
                                                            instr_field_classname += (
                                                                "Non"
                                                                + str(
                                                                    num2words.num2words(
                                                                        int(
                                                                            instructions[
                                                                                key
                                                                            ][
                                                                                "excluded_values"
                                                                            ][
                                                                                field
                                                                            ][
                                                                                elem
                                                                            ]
                                                                        )
                                                                    )
                                                                ).capitalize()
                                                            )
                                                if (
                                                    instr_field_classname
                                                    in instrfield_classes.keys()
                                                ):
                                                    if field in config_variables.keys():
                                                        if (
                                                            instrfield_classes[
                                                                instr_field_classname
                                                            ]
                                                            in config_variables.keys()
                                                        ):
                                                            for (
                                                                elem
                                                            ) in instrfield_classes[
                                                                instr_field_classname
                                                            ]:
                                                                if (
                                                                    elem.strip(" ")
                                                                    in config_variables.keys()
                                                                ):
                                                                    if (
                                                                        config_variables[
                                                                            field.strip(
                                                                                " "
                                                                            )
                                                                        ]
                                                                        != config_variables[
                                                                            elem.strip(
                                                                                " "
                                                                            )
                                                                        ]
                                                                    ):
                                                                        instrfield_classes[
                                                                            instr_field_classname
                                                                            + "_"
                                                                            + field
                                                                        ] = (
                                                                            field + " "
                                                                        )
                                                        else:
                                                            instrfield_classes[
                                                                instr_field_classname
                                                                + "_"
                                                                + field
                                                            ] = (field + " ")
                                                    else:
                                                        instrfield_classes[
                                                            instr_field_classname
                                                        ] += (field + " ")
                                                elif (
                                                    instr_field_classname
                                                    not in instrfield_classes.keys()
                                                ):
                                                    if (
                                                        instr_field_classname
                                                        + "_"
                                                        + field
                                                        in instrfield_classes.keys()
                                                    ):
                                                        if (
                                                            field
                                                            not in instrfield_classes[
                                                                instr_field_classname
                                                                + "_"
                                                                + field
                                                            ]
                                                        ):
                                                            instrfield_classes[
                                                                instr_field_classname
                                                            ] = (field + " ")
                                                    else:
                                                        if (
                                                            field
                                                            not in config_variables.keys()
                                                        ):
                                                            instrfield_classes[
                                                                instr_field_classname
                                                            ] = (field + " ")
                                                        else:
                                                            instrfield_classes[
                                                                instr_field_classname
                                                                + "_"
                                                                + field
                                                            ] = (field + " ")
                                            disableEncoding = True
                                f.write(
                                    generate_instruction_define(
                                        instructions,
                                        list_instructions_with_imms,
                                        key,
                                        instructions[key]["width"],
                                        [],
                                        hasImm,
                                        disableEncoding,
                                        extensions_list,
                                    )
                                )
                                f.write("\n")
                                if generate_pattern_for_instructions(key) != "":
                                    f.write(generate_pattern_for_instructions(key))
                                    f.write("\n\n")
                                else:
                                    f.write("\n")
            f.write("}")
            f.write("\n\n")
            f.close()
    for key in instrfield_classes.keys():
        list_instrs = instrfield_classes[key].split(" ")
        list_instrs.remove("")
        list_instrs = set(list_instrs)
        instrfield_classes.update({key: list(list_instrs)})


## This function generates the definition for all instruction classes
#
# @param classname The name given to the instruction class generated
# @param namespace The namespace used parsed from config_file
# @param asmstring The AsmString used parsed from config_file
# @param tsflags_first The range limit for TSFlags parsed from config_file
# @param tsflags_last The range limit for TSFlags parsed from config_file
# @param opcode The opcode width parsed from ADL file
# @param opcode_first The range limit for opcode parsed from ADL file
# @param opcode_last The range limit for opcode parsed from ADL file
# @param width Width of the instructions defined in this instruction class
# @param constraint_class Constraint used in LLVM
# @param constraint_prefix Constraint prefix used in LLVM
# @param constraint_value Constraint value used in LLVM
# @param tsflags_last_constraint The range limit for TSFlags when constraints are defined, parsed from config_file
# @param tsflags_first_constraint The range limit for TSFlags when constraints are defined, parsed from config_file
# @return The content for any instruction class definition
def generate_define_instruction_class(
    classname,
    namespace,
    asmstring,
    tsflags_first,
    tsflags_last,
    opcode,
    opcode_first,
    opcode_last,
    width,
    constraint_class,
    constraint_prefix,
    constraint_value,
    tsflags_last_constraint,
    tsflags_first_constraint,
):
    config_variables = config.config_environment(config_file, llvm_config)
    statement = (
        "class "
        + classname
        + "<dag outs, dag ins, string opcodestr, string argstr, list<dag> pattern, InstFormat format> : "
    )
    statement += "Instruction {\n"
    content = ""
    content += "\tfield bits<" + width + "> Inst;\n"
    content += "\tbits<" + width + "> SoftFail = 0;\n"
    content += "\tlet Size = " + str(int(int(width) / 8)) + ";\n"
    content += "\tbits<" + opcode + "> Opcode = 0;\n"
    content += "\tlet Inst{" + opcode_last + "-" + opcode_first + "} = Opcode;\n"
    content += "\tlet Namespace = " + '"' + namespace + '";\n'
    content += "\tdag OutOperandList = outs;\n"
    content += "\tdag InOperandList = ins;\n"
    content += "\tlet AsmString = " + asmstring + ";\n"
    content += "\tlet Pattern = pattern;\n"
    content += (
        "\tlet TSFlags{" + tsflags_last + "-" + tsflags_first + "} = format.Value;\n"
    )
    if width == config_variables["LLVMStandardInstructionWidth"]:
        content += (
            "\t"
            + namespace
            + constraint_class
            + " "
            + constraint_prefix
            + constraint_class
            + " = "
            + constraint_value
            + ";\n"
        )
        content += (
            "\tlet TSFlags{"
            + tsflags_last_constraint
            + "-"
            + tsflags_first_constraint
            + "} = "
            + constraint_prefix
            + constraint_class
            + ".Value;\n"
        )
    LLVMVFlags = ""
    for flag in config_variables["LLVMVFlags"]:
        start = config_variables[flag + "TSFlagsStart"]
        end = config_variables[flag + "TSFlagsEnd"]
        length = int(start) - int(end) + 1
        if length > 1:
            defition = (
                "\tbits<"
                + str(length)
                + "> "
                + flag
                + " = "
                + config_variables[flag]
                + ";\n"
            )
            tsflags_definition = (
                "\tlet TSFlags{" + start + "-" + end + "} = " + flag + ";\n"
            )
        else:
            defition = "\tbit " + flag + " = " + config_variables[flag] + ";\n"
            tsflags_definition = "\tlet TSFlags{" + start + "} = " + flag + ";\n"
        LLVMVFlags += defition + tsflags_definition
    return statement + content + LLVMVFlags + "}"


## This function generates instruction format definition used in LLVM
#
# @param instruction_format The name of the instruction format class parsed from config_file
# @param width The width used for instruction class definition parsed from config_file
# @param InstructionFormatR Instruction format based on instruction class width
# @param InstructionFormatCR Instruction format based on instruction class width
# @param InstructionFormatI Instruction format based on instruction class type and width
# @param InstructionFormatCI Instruction format based on instruction class type and width
# @return Content of instruction format definition added to RISCVInstructionFormats.td file
def generate_instruction_format_define(
    instruction_format,
    width,
    InstructionFormatR,
    InstructionFormatCR,
    InstructionFormatI,
    InstructionFormatCI,
):
    statement = "class " + instruction_format + "<bits<" + width + "> val>{\n"
    content = "\tbits<" + width + "> Value = val;\n"
    content += "}\n"
    content += "def " + InstructionFormatR + " : InstFormat<1>;\n"
    content += "def " + InstructionFormatI + " : InstFormat<3>;\n"
    content += "def " + InstructionFormatCR + " : InstFormat<8>;\n"
    content += "def " + InstructionFormatCI + " : InstFormat<9>; \n"
    return statement + content


## This function generates a constraints class used in LLVM
#
# @param namespace The namaspace used, parsed from config_file
# @param class_constraint_name The name given to the constraint class defined parsed from config_file
# @param width The width parsed from config_file
# @return The content of the constraint class definition
def generate_riscv_vconstraint_class(namespace, class_constraint_name, width):
    statement = (
        "class " + namespace + class_constraint_name + "<bits<" + width + "> val> {\n"
    )
    content = "\tbits<" + width + "> Value = val;"
    content += "\n}"
    return statement + content


## This function generates a constraint definition
#
# @param namespace The namaspace used, parsed from config_file
# @param class_constraint_name The name given to the constraint class defined parsed from config_file
# @param constraint_value The type of constraint applied parsed from config_file
# @param value The value used in constraint definition parsed from config_file
# @return The content of the constraint definition
def generate_constraint_define(
    namespace, class_constraint_name, constraint_value, value
):
    content = (
        "def "
        + constraint_value
        + " : "
        + namespace
        + class_constraint_name
        + "<"
        + value
        + ">;\n"
    )
    return content


## This function generates the RISCVInstrFormats.td file
#
# @param file_name ADL file which is parsed for gathering all information needed
# @return The content of RISCVInstrFormats.td file
def generate_instruction_format(file_name):
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[
        0
    ]
    list_instructions_with_regs = adl_parser.parse_instructions_from_adl(
        config_variables["ADLName"]
    )[1]
    list_instructions_with_imms = adl_parser.parse_instructions_from_adl(
        config_variables["ADLName"]
    )[2]
    instruction_width_list = list()
    instrfield_imm = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
    instruction_opcode = dict()
    for key in instructions.keys():
        if key in list_instructions_with_regs:
            if instructions[key]["width"] not in instruction_width_list:
                instruction_width_list.append(instructions[key]["width"])
                instruction_opcode_dict = dict()
                for instrfield in instructions[key]["fields"][0].keys():
                    if "opcode" == instrfield:
                        instruction_opcode_dict[
                            instrfield_imm[instrfield]["width"]
                        ] = instrfield_imm[instrfield]["range"]
                        instruction_opcode[
                            instructions[key]["width"]
                        ] = instruction_opcode_dict
                for instrfield in instructions[key]["fields"][0].keys():
                    if "op_c" == instrfield:
                        instruction_opcode_dict[
                            instrfield_imm[instrfield]["width"]
                        ] = instrfield_imm[instrfield]["range"]
                        instruction_opcode[
                            instructions[key]["width"]
                        ] = instruction_opcode_dict
        elif key in list_instructions_with_imms:
            if instructions[key]["width"] not in instruction_width_list:
                instruction_width_list.append(instructions[key]["width"])
                instruction_opcode_dict = dict()
                for instrfield in instructions[key]["fields"][0].keys():
                    if "opcode" == instrfield:
                        instruction_opcode_dict[
                            instrfield_imm[instrfield]["width"]
                        ] = instrfield_imm[instrfield]["range"]
                        instruction_opcode[
                            instructions[key]["width"]
                        ] = instruction_opcode_dict
                for instrfield in instructions[key]["fields"][0].keys():
                    if "op_c" == instrfield:
                        instruction_opcode_dict[
                            instrfield_imm[instrfield]["width"]
                        ] = instrfield_imm[instrfield]["range"]
                        instruction_opcode[
                            instructions[key]["width"]
                        ] = instruction_opcode_dict
    f = open(file_name, "a")
    f.write(
        generate_instruction_format_define(
            config_variables["InstructionFormat"],
            str(int(math.log2(int(config_variables["LLVMStandardInstructionWidth"])))),
            config_variables["instructionFormatR"],
            config_variables["instructionFormatCR"],
            config_variables["instructionFormatI"],
            config_variables["instructionFormatCI"],
        )
    )
    f.write("\n\n")
    f.write(
        generate_riscv_vconstraint_class(
            config_variables["Namespace"],
            config_variables["LLVMConstraintName"],
            config_variables["LLVMConstraintClassWidth"],
        )
    )
    f.write("\n")
    f.write(
        generate_constraint_define(
            config_variables["Namespace"],
            config_variables["LLVMConstraintName"],
            config_variables["LLVMConstraintValues"],
            config_variables["LLVMNoConstraintValue"],
        )
    )
    f.write("\n")
    for width in instruction_opcode.keys():
        if width == config_variables["LLVMStandardInstructionWidth"]:
            opcode = list(instruction_opcode[width].keys())
            opcode_range = list(instruction_opcode[width].values())
            for index in opcode_range:
                f.write(
                    generate_define_instruction_class(
                        config_variables["InstructionClass"],
                        config_variables["Namespace"],
                        config_variables["AsmString"],
                        config_variables["TSFlagsLast"],
                        config_variables["TSFlagsFirst"],
                        opcode[0],
                        index[0][1],
                        index[0][0],
                        width,
                        config_variables["LLVMConstraintName"],
                        config_variables["LLVMConstraintRiscVPrefix"],
                        config_variables["LLVMConstraintValues"],
                        config_variables["TSFlagsFirstConstraint"],
                        config_variables["TSFlagsLastConstraint"],
                    )
                )
                f.write("\n\n")
        else:
            file_name = config_variables["InstructionFormatFile" + width]
            if os.getcwd().endswith("tools"):
                file_name = "." + file_name
            if os.path.exists(config_variables["InstructionFormatFile" + width]):
                os.remove(config_variables["InstructionFormatFile" + width])
            g = open(file_name, "a")
            legalDisclaimer.get_copyright(file_name)
            legalDisclaimer.get_generated_file(file_name)
            opcode = list(instruction_opcode[width].keys())
            opcode_range = list(instruction_opcode[width].values())
            for index in opcode_range:
                g.write(
                    generate_define_instruction_class(
                        config_variables["InstructionClassC"],
                        config_variables["Namespace"],
                        config_variables["AsmString"],
                        config_variables["TSFlagsLast"],
                        config_variables["TSFlagsFirst"],
                        opcode[0],
                        index[0][1],
                        index[0][0],
                        width,
                        config_variables["LLVMConstraintName"],
                        config_variables["LLVMConstraintRiscVPrefix"],
                        config_variables["LLVMConstraintValues"],
                        config_variables["TSFlagsFirstConstraint"],
                        config_variables["TSFlagsLastConstraint"],
                    )
                )
                g.write("\n\n")
            g.close()
    f.close()


## This functions generates definitions types for immediates that are used in instructions.
# The result will be generated as string and passed to another function which will perform the writting action in file.
#
# @param key The name name of the immediate type which has to be defined
# @param instructions A dictionary which contains all the instructions parsed from ADL file
# @param immediate_key A guard to check if the immediate we are about to generate is the correct one
# @return The definition for a certain immediate type
def generate_imms_class(key, instructions, immediate_key):
    config_variables = config.config_environment(config_file, llvm_config)
    instrfield_imm = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
    namespace = config_variables["Namespace"]
    OperandParser = "Operand<XLenVT>"
    statement = ""
    sign_extension = ""
    decoderMethod = ""
    check_key = immediate_key
    for imm_key in instrfield_classes[key]:
        if imm_key == check_key:
            if int(instrfield_imm[imm_key]["shift"]) != 0:
                for instuction_key in instructions.keys():
                    if imm_key in instructions[instuction_key]["fields"][0].keys():
                        if "excluded_values" in instructions[instuction_key].keys():
                            for elem in range(
                                len(
                                    instructions[instuction_key]["excluded_values"][
                                        imm_key
                                    ]
                                )
                            ):
                                if "signed" in instrfield_imm[imm_key].keys():
                                    if (
                                        "sign_extension"
                                        in instrfield_imm[imm_key].keys()
                                    ):
                                        start = "0b"
                                        end = "0b"
                                        for _ in range(
                                            8,
                                            int(
                                                instrfield_imm[imm_key][
                                                    "sign_extension"
                                                ]
                                            ),
                                        ):
                                            start += "1"
                                            end += "1"
                                        start += "11100000"
                                        end += "11111111"
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && (isInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) - 1
                                            )
                                            + ">(Imm) || (Imm >= "
                                            + start
                                            + ") && (Imm <= "
                                            + end
                                            + ");}]>"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) - 1
                                            )
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm) || (Imm >= "
                                            + start
                                            + ") && (Imm <= "
                                            + end
                                            + ");"
                                        )
                                    elif (
                                        "one_extended" in instrfield_imm[imm_key].keys()
                                    ):
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) + 1
                                            )
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm) && Imm < 0;"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) + 1
                                            )
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm) && Imm < 0;}]> "
                                        )
                                    else:
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedInt<"
                                            + instrfield_imm[imm_key]["size"]
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm);"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedInt<"
                                            + instrfield_imm[imm_key]["size"]
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm);}]> "
                                        )
                                else:
                                    if (
                                        "sign_extension"
                                        in instrfield_imm[imm_key].keys()
                                    ):
                                        start = "0b"
                                        end = "0b"
                                        for _ in range(
                                            8,
                                            int(
                                                instrfield_imm[imm_key][
                                                    "sign_extension"
                                                ]
                                            ),
                                        ):
                                            start += "1"
                                            end += "1"
                                        start += "11100000"
                                        end += "11111111"
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedUInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) - 1
                                            )
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm);"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedUInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) - 1
                                            )
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm) || (Imm >= "
                                            + start
                                            + ") && (Imm <= "
                                            + end
                                            + ");"
                                        )
                                    elif (
                                        "one_extended" in instrfield_imm[imm_key].keys()
                                    ):
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedUInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) + 1
                                            )
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm) && Imm < 0;"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedUInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) + 1
                                            )
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm) && Imm < 0;}]> "
                                        )
                                    else:
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedUInt<"
                                            + instrfield_imm[imm_key]["size"]
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm);"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isShiftedUInt<"
                                            + instrfield_imm[imm_key]["size"]
                                            + ", "
                                            + instrfield_imm[imm_key]["shift"]
                                            + ">(Imm);}]> "
                                        )
                            break
                        else:
                            if "signed" in instrfield_imm[imm_key].keys():
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    start = "0b"
                                    end = "0b"
                                    for _ in range(
                                        8,
                                        int(instrfield_imm[imm_key]["sign_extension"]),
                                    ):
                                        start += "1"
                                        end += "1"
                                    start += "11100000"
                                    end += "11111111"
                                    return_value = (
                                        "return (Imm != "
                                        + instructions[instuction_key][
                                            "excluded_values"
                                        ][imm_key][elem]
                                        + ") && (isInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) - 1)
                                        + ">(Imm) || (Imm >= "
                                        + start
                                        + ") && (Imm <= "
                                        + end
                                        + ");"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isShiftedInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) - 1)
                                        + ", "
                                        + instrfield_imm[imm_key]["shift"]
                                        + ">(Imm) || (Imm >= "
                                        + start
                                        + ") && Imm <= "
                                        + end
                                        + ");}]>"
                                    )
                                elif "one_extended" in instrfield_imm[imm_key].keys():
                                    return_value = (
                                        "return isShiftedInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) + 1)
                                        + ", "
                                        + instrfield_imm[imm_key]["shift"]
                                        + ">(Imm) && Imm < 0;"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isShiftedInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) + 1)
                                        + ", "
                                        + instrfield_imm[imm_key]["shift"]
                                        + ">(Imm) && Imm < 0;}]> "
                                    )
                                else:
                                    return_value = (
                                        "return isShiftedInt<"
                                        + instrfield_imm[imm_key]["size"]
                                        + ", "
                                        + instrfield_imm[imm_key]["shift"]
                                        + ">(Imm);"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isShiftedInt<"
                                        + instrfield_imm[imm_key]["size"]
                                        + ", "
                                        + instrfield_imm[imm_key]["shift"]
                                        + ">(Imm);}]> "
                                    )
                                break
                            else:
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    start = "0b"
                                    end = "0b"
                                    for _ in range(
                                        8,
                                        int(instrfield_imm[imm_key]["sign_extension"]),
                                    ):
                                        start += "1"
                                        end += "1"
                                    start += "11100000"
                                    end += "11111111"
                                    return_value = (
                                        "return (Imm != "
                                        + instructions[instuction_key][
                                            "excluded_values"
                                        ][imm_key][elem]
                                        + ") && (isInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) - 1)
                                        + ">(Imm) || (Imm >= "
                                        + start
                                        + ") && (Imm <= "
                                        + end
                                        + ");"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isShiftedUInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) - 1)
                                        + ", "
                                        + instrfield_imm[imm_key]["shift"]
                                        + ">(Imm) || (Imm >= "
                                        + start
                                        + ") && (Imm <= "
                                        + end
                                        + ");}]>"
                                    )
                                elif "one_extended" in instrfield_imm[imm_key].keys():
                                    return_value = (
                                        "return isShiftedUInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) + 1)
                                        + ", "
                                        + instrfield_imm[imm_key]["shift"]
                                        + ">(Imm) && Imm < 0;"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isShiftedUInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) + 1)
                                        + ", "
                                        + instrfield_imm[imm_key]["shift"]
                                        + ">(Imm) && Imm < 0;}]> "
                                    )
                                else:
                                    return_value = (
                                        "return isShiftedUInt<"
                                        + instrfield_imm[imm_key]["size"]
                                        + ", "
                                        + instrfield_imm[imm_key]["shift"]
                                        + ">(Imm);"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isShiftedUInt<"
                                        + instrfield_imm[imm_key]["size"]
                                        + ", "
                                        + instrfield_imm[imm_key]["shift"]
                                        + ">(Imm);}]> "
                                    )
                                break
            else:
                for instuction_key in instructions.keys():
                    if imm_key in instructions[instuction_key]["fields"][0].keys():
                        if "excluded_values" in instructions[instuction_key].keys():
                            for elem in range(
                                len(
                                    instructions[instuction_key]["excluded_values"][
                                        imm_key
                                    ]
                                )
                            ):
                                if "signed" in instrfield_imm[imm_key].keys():
                                    if (
                                        "sign_extension"
                                        in instrfield_imm[imm_key].keys()
                                    ):
                                        start = "0b"
                                        end = "0b"
                                        for _ in range(
                                            8,
                                            int(
                                                instrfield_imm[imm_key][
                                                    "sign_extension"
                                                ]
                                            ),
                                        ):
                                            start += "1"
                                            end += "1"
                                        start += "11100000"
                                        end += "11111111"
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && (isInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) - 1
                                            )
                                            + ">(Imm) || (Imm >= "
                                            + start
                                            + ") && (Imm <= "
                                            + end
                                            + "));"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) - 1
                                            )
                                            + ">(Imm) || (Imm >= "
                                            + start
                                            + ") && (Imm <= "
                                            + end
                                            + ");}]> "
                                        )
                                    elif (
                                        "one_extended" in instrfield_imm[imm_key].keys()
                                    ):
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && (isInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) + 1
                                            )
                                            + ">(Imm) && Imm < 0);"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) + 1
                                            )
                                            + ">(Imm) && Imm < 0;}]> "
                                        )
                                        break
                                    else:
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && (isInt<"
                                            + instrfield_imm[imm_key]["size"]
                                            + ">(Imm));"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isInt<"
                                            + instrfield_imm[imm_key]["size"]
                                            + ">(Imm);}]> "
                                        )
                                else:
                                    if (
                                        "sign_extension"
                                        in instrfield_imm[imm_key].keys()
                                    ):
                                        start = "0b"
                                        end = "0b"
                                        for _ in range(
                                            8,
                                            int(
                                                instrfield_imm[imm_key][
                                                    "sign_extension"
                                                ]
                                            ),
                                        ):
                                            start += "1"
                                            end += "1"
                                        start += "11100000"
                                        end += "11111111"
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && (isUInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) - 1
                                            )
                                            + ">(Imm) || (Imm >= "
                                            + start
                                            + ") && (Imm <= "
                                            + end
                                            + "));"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isUInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) - 1
                                            )
                                            + ">(Imm) || (Imm >= "
                                            + start
                                            + ") && (Imm <= "
                                            + end
                                            + ");}]> "
                                        )
                                    elif (
                                        "one_extended" in instrfield_imm[imm_key].keys()
                                    ):
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && (isUInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) + 1
                                            )
                                            + ">(Imm) && Imm < 0);"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isUInt<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"]) + 1
                                            )
                                            + ">(Imm) && Imm < 0;}]> "
                                        )
                                        break
                                    else:
                                        return_value = (
                                            "return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && (isUInt<"
                                            + instrfield_imm[imm_key]["size"]
                                            + ">(Imm));"
                                        )
                                        ImmLeaf = (
                                            "ImmLeaf<XLenVT, "
                                            + "[{return (Imm != "
                                            + instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key][elem]
                                            + ") && isUInt<"
                                            + instrfield_imm[imm_key]["size"]
                                            + ">(Imm);}]> "
                                        )
                            break
                        else:
                            if "signed" in instrfield_imm[imm_key].keys():
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    start = "0b"
                                    end = "0b"
                                    for _ in range(
                                        8,
                                        int(instrfield_imm[imm_key]["sign_extension"]),
                                    ):
                                        start += "1"
                                        end += "1"
                                    start += "11100000"
                                    end += "11111111"
                                    return_value = (
                                        "return (Imm != "
                                        + instructions[instuction_key][
                                            "excluded_values"
                                        ][imm_key][elem]
                                        + ") && (isInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) - 1)
                                        + ">(Imm) || (Imm >= "
                                        + start
                                        + ") && (Imm <= "
                                        + end
                                        + "));"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) - 1)
                                        + ">(Imm) || (Imm >= "
                                        + start
                                        + ") && (Imm <= "
                                        + end
                                        + ");}]> "
                                    )
                                    break
                                elif "one_extended" in instrfield_imm[imm_key].keys():
                                    return_value = (
                                        "return isInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) + 1)
                                        + ">(Imm) && Imm < 0;"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) + 1)
                                        + ">(Imm) && Imm < 0;}]> "
                                    )
                                    break
                                else:
                                    return_value = (
                                        "return isInt<"
                                        + instrfield_imm[imm_key]["size"]
                                        + ">(Imm);"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isInt<"
                                        + instrfield_imm[imm_key]["size"]
                                        + ">(Imm);}]> "
                                    )
                                    break
                            else:
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    start = "0b"
                                    end = "0b"
                                    for _ in range(
                                        8,
                                        int(instrfield_imm[imm_key]["sign_extension"]),
                                    ):
                                        start += "1"
                                        end += "1"
                                    start += "11100000"
                                    end += "11111111"
                                    return_value = (
                                        "return (isUInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) - 1)
                                        + ">(Imm) || (Imm >= "
                                        + start
                                        + ") && (Imm <= "
                                        + end
                                        + "));"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isUInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) - 1)
                                        + ">(Imm) || (Imm >= "
                                        + start
                                        + ") && (Imm <= "
                                        + end
                                        + ");}]> "
                                    )
                                    break
                                elif "one_extended" in instrfield_imm[imm_key].keys():
                                    return_value = (
                                        "return isInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) + 1)
                                        + ">(Imm) && Imm < 0;"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isInt<"
                                        + str(int(instrfield_imm[imm_key]["size"]) + 1)
                                        + ">(Imm) && Imm < 0;}]> "
                                    )
                                    break
                                else:
                                    return_value = (
                                        "return isUInt<"
                                        + instrfield_imm[imm_key]["size"]
                                        + ">(Imm);"
                                    )
                                    ImmLeaf = (
                                        "ImmLeaf<XLenVT, "
                                        + "[{return isUInt<"
                                        + instrfield_imm[imm_key]["size"]
                                        + ">(Imm);}]> "
                                    )
                                    break
    if "Non" in key:
        for instruction in instructions.keys():
            imm_class = instrfield_classes[key][0]
            if imm_class in instructions[instruction]["fields"][0].keys():
                instruction_key = instruction
                if "excluded_values" in instructions[instruction_key].keys():
                    if (
                        "Imm != "
                        + str(
                            instructions[instruction_key]["excluded_values"][imm_class][
                                0
                            ]
                        )
                        not in ImmLeaf
                    ):
                        ImmLeaf = ImmLeaf.replace(
                            "return",
                            "return ("
                            + "Imm != "
                            + str(
                                instructions[instruction_key]["excluded_values"][
                                    imm_class
                                ][0]
                            )
                            + ") && ",
                        )
    for imm_key in instrfield_classes[key]:
        if imm_key == check_key:
            if imm_key in config_variables.keys():
                if '"AliasImmClass"' in config_variables[imm_key].keys():
                    for instuction_key in instructions.keys():
                        if imm_key in instructions[instuction_key]["fields"][0].keys():
                            if '"disableImmLeaf"' in config_variables[imm_key].keys():
                                if "reloc" in instrfield_imm[imm_key].keys():
                                    reloc = instrfield_imm[imm_key]["reloc"]
                                    for elem in config_variables["LLVMOtherVTAttrib"]:
                                        if (
                                            reloc
                                            in config_variables["LLVMOtherVTReloc"]
                                            or elem
                                            in instructions[instuction_key][
                                                "attributes"
                                            ]
                                        ):
                                            OperandParser = (
                                                "Operand<"
                                                + config_variables["LLVMOtherVTValue"]
                                                + ">"
                                            )
                                            break
                                statement = (
                                    "def "
                                    + config_variables[imm_key][
                                        '"AliasImmClass"'
                                    ].replace('"', "")
                                    + " : "
                                    + OperandParser
                                    + " {\n"
                                )
                                break
                            else:
                                statement = (
                                    "def "
                                    + config_variables[imm_key][
                                        '"AliasImmClass"'
                                    ].replace('"', "")
                                    + " : "
                                    + OperandParser
                                    + ", "
                                    + ImmLeaf
                                    + " {\n"
                                )
                                break
    aliasEnabled = False
    one_extended = ""
    if statement == "":
        forLoop = False
        for instruction_key in instructions.keys():
            for imm_key in instrfield_classes[key]:
                if imm_key == check_key:
                    reloc = ""
                    if "reloc" in instrfield_imm[imm_key].keys():
                        reloc = instrfield_imm[imm_key]["reloc"]
                    if "one_extended" in instrfield_imm[imm_key].keys():
                        one_extended = instrfield_imm[imm_key]["one_extended"]
                    if imm_key in instructions[instruction_key]["fields"][0]:
                        for elem in config_variables["LLVMOtherVTAttrib"]:
                            if (
                                elem in instructions[instruction_key]["attributes"]
                                or reloc in config_variables["LLVMOtherVTReloc"]
                            ):
                                if (
                                    instructions[instruction_key]["width"]
                                    != config_variables["LLVMStandardInstructionWidth"]
                                ):
                                    OperandParser = (
                                        "Operand<"
                                        + config_variables["LLVMOtherVTValue"]
                                        + ">"
                                    )
                                    if imm_key in config_variables.keys():
                                        if (
                                            '"disableImmLeaf"'
                                            not in config_variables[imm_key].keys()
                                        ):
                                            aliasEnabled = True
                                            if (
                                                "one_extended"
                                                in instrfield_imm[imm_key].keys()
                                            ):
                                                if (
                                                    '"AliasImmClass"'
                                                    in config_variables[imm_key].keys()
                                                ):
                                                    statement = (
                                                        "def "
                                                        + config_variables[imm_key][
                                                            '"AliasImmClass"'
                                                        ].replace('"', "")
                                                        + " : "
                                                        + OperandParser
                                                        + ", "
                                                        + ImmLeaf
                                                        + "{\n"
                                                    )
                                                    forLoop = True
                                                else:
                                                    statement = (
                                                        "def "
                                                        + str(key).lower()
                                                        + " : "
                                                        + OperandParser
                                                        + ", "
                                                        + ImmLeaf
                                                        + "{\n"
                                                    )
                                                    forLoop = True
                                            else:
                                                if (
                                                    '"AliasImmClass"'
                                                    in config_variables[imm_key].keys()
                                                ):
                                                    statement = (
                                                        "def "
                                                        + config_variables[imm_key][
                                                            '"AliasImmClass"'
                                                        ].replace('"', "")
                                                        + " : "
                                                        + OperandParser
                                                        + ", "
                                                        + ImmLeaf
                                                        + "{\n"
                                                    )
                                                    forLoop = True
                                                else:
                                                    statement = (
                                                        "def "
                                                        + str(key).lower()
                                                        + " : "
                                                        + OperandParser
                                                        + ", "
                                                        + ImmLeaf
                                                        + "{\n"
                                                    )
                                                    forLoop = True
                                            break
                                    else:
                                        if (
                                            "one_extended"
                                            in instrfield_imm[imm_key].keys()
                                        ):
                                            statement = (
                                                "def "
                                                + str(key).lower()
                                                + ""
                                                + " : "
                                                + OperandParser
                                                + ", "
                                                + ImmLeaf
                                                + "{\n"
                                            )
                                            forLoop = True
                                        else:
                                            statement = (
                                                "def "
                                                + str(key).lower()
                                                + " : "
                                                + OperandParser
                                                + ", "
                                                + ImmLeaf
                                                + "{\n"
                                            )
                                            forLoop = True
                                        break
                                else:
                                    OperandParser = (
                                        "Operand<"
                                        + config_variables["LLVMOtherVTValue"]
                                        + ">"
                                    )
                                    if imm_key in config_variables.keys():
                                        if (
                                            '"disableImmLeaf"'
                                            not in config_variables[imm_key].keys()
                                        ):
                                            aliasEnabled = True
                                            if (
                                                "one_extended"
                                                in instrfield_imm[imm_key].keys()
                                            ):
                                                if (
                                                    '"AliasImmClass"'
                                                    in config_variables[imm_key].keys()
                                                ):
                                                    statement = (
                                                        "def "
                                                        + config_variables[imm_key][
                                                            '"AliasImmClass"'
                                                        ].replace('"', "")
                                                        + ""
                                                        + " : "
                                                        + OperandParser
                                                        + ", "
                                                        + ImmLeaf
                                                        + "{\n"
                                                    )
                                                    forLoop = True
                                                else:
                                                    statement = (
                                                        "def "
                                                        + str(key).lower()
                                                        + ""
                                                        + " : "
                                                        + OperandParser
                                                        + ", "
                                                        + ImmLeaf
                                                        + "{\n"
                                                    )
                                                    forLoop = True
                                            else:
                                                if (
                                                    '"AliasImmClass"'
                                                    in config_variables[imm_key].keys()
                                                ):
                                                    statement = (
                                                        "def "
                                                        + config_variables[imm_key][
                                                            '"AliasImmClass"'
                                                        ].replace('"', "")
                                                        + " : "
                                                        + OperandParser
                                                        + ", "
                                                        + ImmLeaf
                                                        + " {\n"
                                                    )
                                                    forLoop = True
                                                else:
                                                    statement = (
                                                        "def "
                                                        + str(key).lower()
                                                        + ""
                                                        + " : "
                                                        + OperandParser
                                                        + ", "
                                                        + ImmLeaf
                                                        + "{\n"
                                                    )
                                                    forLoop = True
                                            break
                                    else:
                                        if (
                                            "one_extended"
                                            in instrfield_imm[imm_key].keys()
                                        ):
                                            statement = (
                                                "def "
                                                + str(key).lower()
                                                + ""
                                                + " : "
                                                + OperandParser
                                                + ", "
                                                + ImmLeaf
                                                + "{\n"
                                            )
                                            forLoop = True
                                        else:
                                            statement = (
                                                "def "
                                                + str(key).lower()
                                                + " : "
                                                + OperandParser
                                                + ImmLeaf
                                                + "{\n"
                                            )
                                            forLoop = True
                                            break
            if forLoop is True:
                break
        if one_extended == "":
            for imm_key in instrfield_classes[key]:
                if imm_key == check_key:
                    if "one_extended" in instrfield_imm[imm_key].keys():
                        one_extended = instrfield_imm[imm_key]["one_extended"]
        if forLoop is False:
            for imm_key in instrfield_classes[key]:
                if imm_key == check_key:
                    if imm_key in config_variables.keys():
                        aliasEnabled = True
                        if '"disableImmLeaf"' in config_variables[imm_key].keys():
                            if (
                                config_variables[imm_key]['"disableImmLeaf"']
                                == '"True"'
                            ):
                                if one_extended != "":
                                    if (
                                        '"AliasImmClass"'
                                        in config_variables[imm_key].keys()
                                    ):
                                        statement = (
                                            "def "
                                            + config_variables[imm_key][
                                                '"AliasImmClass"'
                                            ].replace('"', "")
                                            + ""
                                            + " : "
                                            + OperandParser
                                            + " {\n"
                                        )
                                    else:
                                        statement = (
                                            "def "
                                            + str(key).lower()
                                            + ""
                                            + " : "
                                            + OperandParser
                                            + "{\n"
                                        )
                                else:
                                    if (
                                        '"AliasImmClass"'
                                        in config_variables[imm_key].keys()
                                    ):
                                        statement = (
                                            "def "
                                            + config_variables[imm_key][
                                                '"AliasImmClass"'
                                            ].replace('"', "")
                                            + " : "
                                            + OperandParser
                                            + " {\n"
                                        )
                                    else:
                                        statement = (
                                            "def "
                                            + str(key).lower()
                                            + ""
                                            + " : "
                                            + OperandParser
                                            + "{\n"
                                        )
                        else:
                            if one_extended != "":
                                if (
                                    '"AliasImmClass"'
                                    in config_variables[imm_key].keys()
                                ):
                                    statement = (
                                        "def "
                                        + config_variables[imm_key][
                                            '"AliasImmClass"'
                                        ].replace('"', "")
                                        + ""
                                        + " : "
                                        + OperandParser
                                        + ", "
                                        + ImmLeaf
                                        + "{\n"
                                    )
                                else:
                                    statement = (
                                        "def "
                                        + str(key).lower()
                                        + ""
                                        + " : "
                                        + OperandParser
                                        + ", "
                                        + ImmLeaf
                                        + "{\n"
                                    )
                            else:
                                if (
                                    '"AliasImmClass"'
                                    in config_variables[imm_key].keys()
                                ):
                                    statement = (
                                        "def "
                                        + config_variables[imm_key][
                                            '"AliasImmClass"'
                                        ].replace('"', "")
                                        + " : "
                                        + OperandParser
                                        + ", "
                                        + ImmLeaf
                                        + "{\n"
                                    )
                                else:
                                    statement = (
                                        "def "
                                        + str(key).lower()
                                        + ""
                                        + " : "
                                        + OperandParser
                                        + ", "
                                        + ImmLeaf
                                        + "{\n"
                                    )
                    else:
                        if one_extended != "":
                            statement = (
                                "def "
                                + str(key).lower()
                                + ""
                                + " : "
                                + OperandParser
                                + ", "
                                + ImmLeaf
                                + "{ \n"
                            )
                        else:
                            statement = (
                                "def "
                                + str(key).lower()
                                + " : "
                                + OperandParser
                                + ", "
                                + ImmLeaf
                                + "{ \n"
                            )
    content = ""
    size = ""
    for imm_key in instrfield_classes[key]:
        if imm_key == check_key:
            if imm_key in config_variables.keys():
                for instuction_key in instructions.keys():
                    if imm_key in instructions[instuction_key]["fields"][0].keys():
                        if "signed" in instrfield_imm[imm_key].keys():
                            if "sign_extension" in instrfield_imm[imm_key].keys():
                                if str(imm_key) in config_variables.keys():
                                    if (
                                        '"ParserMatchClass"'
                                        in config_variables[str(imm_key)].keys()
                                    ):
                                        if "\tlet ParserMatchClass = " not in content:
                                            content += (
                                                "\tlet ParserMatchClass = "
                                                + config_variables[imm_key][
                                                    '"ParserMatchClass"'
                                                ]
                                                + ";\n"
                                            )
                                    break
                                else:
                                    if "\tlet ParserMatchClass = " not in content:
                                        content += (
                                            "\tlet ParserMatchClass = SImmAsmOperand<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"])
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            + ", "
                                            + '"'
                                            + str(instuction_key).upper()
                                            + '"'
                                            + ">;\n"
                                        )
                                        size = str(
                                            int(instrfield_imm[imm_key]["size"])
                                            - 1
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        break
                            else:
                                if str(imm_key) in config_variables.keys():
                                    if (
                                        '"ParserMatchClass"'
                                        in config_variables[str(imm_key)].keys()
                                    ):
                                        if "\tlet ParserMatchClass = " not in content:
                                            content += (
                                                "\tlet ParserMatchClass = "
                                                + config_variables[str(imm_key)][
                                                    '"ParserMatchClass"'
                                                ].strip('"')
                                                + ";\n"
                                            )
                                else:
                                    if "\tlet ParserMatchClass = " not in content:
                                        content += (
                                            "\tlet ParserMatchClass = SImmAsmOperand<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"])
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            + ", "
                                            + '"'
                                            + str(instuction_key).upper()
                                            + '"'
                                            + ">;\n"
                                        )
                                        size = str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        break
                        else:
                            if "sign_extension" in instrfield_imm[imm_key].keys():
                                if str(imm_key) in config_variables.keys():
                                    if (
                                        '"ParserMatchClass"'
                                        in config_variables[str(imm_key)].keys()
                                    ):
                                        if "\tlet ParserMatchClass = " not in content:
                                            content += (
                                                "\tlet ParserMatchClass = "
                                                + config_variables[str(imm_key)][
                                                    '"ParserMatchClass"'
                                                ].strip('"')
                                                + ";\n"
                                            )
                                    else:
                                        if "\tlet ParserMatchClass = " not in content:
                                            content += (
                                                "\tlet ParserMatchClass = UImmAsmOperand<"
                                                + str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                                + ">;\n"
                                            )
                                            size = str(
                                                int(instrfield_imm[imm_key]["size"])
                                                - 1
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                    break
                                else:
                                    if "\tlet ParserMatchClass = " not in content:
                                        content += (
                                            "\tlet ParserMatchClass = UImmAsmOperand<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"])
                                                - 1
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            + ">;\n"
                                        )
                                        size = str(
                                            int(instrfield_imm[imm_key]["size"])
                                            - 1
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        break
                            else:
                                if str(imm_key) in config_variables.keys():
                                    if "\tlet ParserMatchClass = " not in content:
                                        if (
                                            '"ParserMatchClass"'
                                            in config_variables[str(imm_key)].keys()
                                        ):
                                            content += (
                                                "\tlet ParserMatchClass = "
                                                + config_variables[str(imm_key)][
                                                    '"ParserMatchClass"'
                                                ].strip('"')
                                                + ";\n"
                                            )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = UImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        break
                                else:
                                    if "\tlet ParserMatchClass = " not in content:
                                        content += (
                                            "\tlet ParserMatchClass = UImmAsmOperand<"
                                            + str(
                                                int(instrfield_imm[imm_key]["size"])
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            + ">;\n"
                                        )
                                        size = str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        break
    for imm_key in instrfield_classes[key]:
        if imm_key == check_key:
            if "signed" in instrfield_imm[imm_key].keys():
                for instuction_key in instructions.keys():
                    if imm_key in instructions[instuction_key]["fields"][0].keys():
                        if "excluded_values" in instructions[instuction_key].keys():
                            if instrfield_imm[imm_key]["shift"] == "0":
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    for elem in range(
                                        len(
                                            instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key]
                                        )
                                    ):
                                        if str(imm_key) in config_variables.keys():
                                            if (
                                                '"ParserMatchClass"'
                                                in config_variables[str(imm_key)].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = "
                                                        + config_variables[
                                                            str(imm_key)
                                                        ]['"ParserMatchClass"'].strip(
                                                            '"'
                                                        )
                                                        + ";\n"
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = SImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = SImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + "Non"
                                                    + str(
                                                        num2words.num2words(
                                                            int(
                                                                instructions[
                                                                    instuction_key
                                                                ]["excluded_values"][
                                                                    imm_key
                                                                ][
                                                                    elem
                                                                ]
                                                            )
                                                        )
                                                    ).capitalize()
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                    break
                                else:
                                    for elem in range(
                                        len(
                                            instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key]
                                        )
                                    ):
                                        if str(imm_key) in config_variables.keys():
                                            if (
                                                '"ParserMatchClass"'
                                                in config_variables[str(imm_key)].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = "
                                                        + config_variables[
                                                            str(imm_key)
                                                        ]['"ParserMatchClass"'].strip(
                                                            '"'
                                                        )
                                                        + ";\n"
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = SImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = SImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + "Non"
                                                    + str(
                                                        num2words.num2words(
                                                            int(
                                                                instructions[
                                                                    instuction_key
                                                                ]["excluded_values"][
                                                                    imm_key
                                                                ][
                                                                    elem
                                                                ]
                                                            )
                                                        )
                                                    ).capitalize()
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                    break
                            else:
                                text = "Lsb"
                                for _ in range(int(instrfield_imm[imm_key]["shift"])):
                                    text += "0"
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    for elem in range(
                                        len(
                                            instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key]
                                        )
                                    ):
                                        if str(imm_key) in config_variables.keys():
                                            if (
                                                '"ParserMatchClass"'
                                                in config_variables[str(imm_key)].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = "
                                                        + config_variables[
                                                            str(imm_key)
                                                        ]['"ParserMatchClass"'].strip(
                                                            '"'
                                                        )
                                                        + ";\n"
                                                    )
                                            else:
                                                if (
                                                    "one_extended"
                                                    in instrfield_imm[imm_key].keys()
                                                ):
                                                    if (
                                                        "\tlet ParserMatchClass = "
                                                        not in content
                                                    ):
                                                        content += (
                                                            "\tlet ParserMatchClass = SImmAsmOperand<"
                                                            + str(
                                                                int(
                                                                    instrfield_imm[
                                                                        imm_key
                                                                    ]["size"]
                                                                )
                                                                + int(
                                                                    instrfield_imm[
                                                                        imm_key
                                                                    ]["shift"]
                                                                )
                                                            )
                                                            + ", "
                                                            + '"'
                                                            + text
                                                            + "Neg"
                                                            + "Non"
                                                            + str(
                                                                num2words.num2words(
                                                                    int(
                                                                        instructions[
                                                                            instuction_key
                                                                        ][
                                                                            "excluded_values"
                                                                        ][
                                                                            imm_key
                                                                        ][
                                                                            elem
                                                                        ]
                                                                    )
                                                                )
                                                            ).capitalize()
                                                            + '"'
                                                            + ">;\n"
                                                        )
                                                        size = str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            - 1
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                else:
                                                    if (
                                                        "\tlet ParserMatchClass = "
                                                        not in content
                                                    ):
                                                        content += (
                                                            "\tlet ParserMatchClass = SImmAsmOperand<"
                                                            + str(
                                                                int(
                                                                    instrfield_imm[
                                                                        imm_key
                                                                    ]["size"]
                                                                )
                                                                + int(
                                                                    instrfield_imm[
                                                                        imm_key
                                                                    ]["shift"]
                                                                )
                                                            )
                                                            + ", "
                                                            + '"'
                                                            + text
                                                            + "Non"
                                                            + str(
                                                                num2words.num2words(
                                                                    int(
                                                                        instructions[
                                                                            instuction_key
                                                                        ][
                                                                            "excluded_values"
                                                                        ][
                                                                            imm_key
                                                                        ][
                                                                            elem
                                                                        ]
                                                                    )
                                                                )
                                                            ).capitalize()
                                                            + '"'
                                                            + ">;\n"
                                                        )
                                                        size = str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            - 1
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                        else:
                                            if (
                                                "one_extended"
                                                in instrfield_imm[imm_key].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = SImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Neg"
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = SImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            - 1
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                    break
                                else:
                                    for elem in range(
                                        len(
                                            instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key]
                                        )
                                    ):
                                        if str(imm_key) in config_variables.keys():
                                            if (
                                                '"ParserMatchClass"'
                                                in config_variables[str(imm_key)].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = "
                                                        + config_variables[
                                                            str(imm_key)
                                                        ]['"ParserMatchClass"'].strip(
                                                            '"'
                                                        )
                                                        + ";\n"
                                                    )
                                            else:
                                                if (
                                                    "one_extended"
                                                    in instrfield_imm[imm_key].keys()
                                                ):
                                                    if (
                                                        "\tlet ParserMatchClass = "
                                                        not in content
                                                    ):
                                                        content += (
                                                            "\tlet ParserMatchClass = SImmAsmOperand<"
                                                            + str(
                                                                int(
                                                                    instrfield_imm[
                                                                        imm_key
                                                                    ]["size"]
                                                                )
                                                                + int(
                                                                    instrfield_imm[
                                                                        imm_key
                                                                    ]["shift"]
                                                                )
                                                            )
                                                            + ", "
                                                            + '"'
                                                            + text
                                                            + "Neg"
                                                            + "Non"
                                                            + str(
                                                                num2words.num2words(
                                                                    int(
                                                                        instructions[
                                                                            instuction_key
                                                                        ][
                                                                            "excluded_values"
                                                                        ][
                                                                            imm_key
                                                                        ][
                                                                            elem
                                                                        ]
                                                                    )
                                                                )
                                                            ).capitalize()
                                                            + '"'
                                                            + ">;\n"
                                                        )
                                                        size = str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                else:
                                                    if (
                                                        "\tlet ParserMatchClass = "
                                                        not in content
                                                    ):
                                                        content += (
                                                            "\tlet ParserMatchClass = SImmAsmOperand<"
                                                            + str(
                                                                int(
                                                                    instrfield_imm[
                                                                        imm_key
                                                                    ]["size"]
                                                                )
                                                                + int(
                                                                    instrfield_imm[
                                                                        imm_key
                                                                    ]["shift"]
                                                                )
                                                            )
                                                            + ", "
                                                            + '"'
                                                            + text
                                                            + "Non"
                                                            + str(
                                                                num2words.num2words(
                                                                    int(
                                                                        instructions[
                                                                            instuction_key
                                                                        ][
                                                                            "excluded_values"
                                                                        ][
                                                                            imm_key
                                                                        ][
                                                                            elem
                                                                        ]
                                                                    )
                                                                )
                                                            ).capitalize()
                                                            + '"'
                                                            + ">;\n"
                                                        )
                                                        size = str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            - 1
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                        else:
                                            if (
                                                "one_extended"
                                                in instrfield_imm[imm_key].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = SImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Neg"
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = SImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                    break
                        else:
                            if instrfield_imm[imm_key]["shift"] == "0":
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    if str(imm_key) in config_variables.keys():
                                        if (
                                            '"ParserMatchClass"'
                                            in config_variables[str(imm_key)].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = "
                                                    + config_variables[str(imm_key)][
                                                        '"ParserMatchClass"'
                                                    ].strip('"')
                                                    + ";\n"
                                                )
                                        break
                                    else:
                                        if "\tlet ParserMatchClass = " not in content:
                                            content += (
                                                "\tlet ParserMatchClass = SImmAsmOperand<"
                                                + str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                                + ">;\n"
                                            )
                                            size = str(
                                                int(instrfield_imm[imm_key]["size"])
                                                - 1
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            break
                                else:
                                    if str(imm_key) in config_variables.keys():
                                        if (
                                            '"ParserMatchClass"'
                                            in config_variables[str(imm_key)].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = "
                                                    + config_variables[str(imm_key)][
                                                        '"ParserMatchClass"'
                                                    ].strip('"')
                                                    + ";\n"
                                                )
                                        break
                                    else:
                                        if "\tlet ParserMatchClass = " not in content:
                                            content += (
                                                "\tlet ParserMatchClass = SImmAsmOperand<"
                                                + str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                                + ">;\n"
                                            )
                                            size = str(
                                                int(instrfield_imm[imm_key]["size"])
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            break
                            else:
                                text = "Lsb"
                                for _ in range(int(instrfield_imm[imm_key]["shift"])):
                                    text += "0"
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    if str(imm_key) in config_variables.keys():
                                        if (
                                            '"ParserMatchClass"'
                                            in config_variables[str(imm_key)].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = "
                                                    + config_variables[str(imm_key)][
                                                        '"ParserMatchClass"'
                                                    ].strip('"')
                                                    + ";\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        else:
                                            if (
                                                "one_extended"
                                                in instrfield_imm[imm_key].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = SImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                            + 1
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Neg"
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = SImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                            + 1
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Neg"
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )

                                        break
                                    else:
                                        if (
                                            "one_extended"
                                            in instrfield_imm[imm_key].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = SImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                        + 1
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + text
                                                    + "Neg"
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = SImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + text
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        break
                                else:
                                    if str(imm_key) in config_variables.keys():
                                        if (
                                            '"ParserMatchClass"'
                                            in config_variables[str(imm_key)].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = "
                                                    + config_variables[str(imm_key)][
                                                        '"ParserMatchClass"'
                                                    ].strip('"')
                                                    + ";\n"
                                                )
                                            size = str(
                                                int(instrfield_imm[imm_key]["size"])
                                                - 1
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            break
                                        else:
                                            if (
                                                "one_extended"
                                                in instrfield_imm[imm_key].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = SImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                            + 1
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Neg"
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = SImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                    else:
                                        if (
                                            "one_extended"
                                            in instrfield_imm[imm_key].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = SImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                        + 1
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + text
                                                    + "Neg"
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = SImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + text
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        break
                break
            else:
                for instuction_key in instructions.keys():
                    if imm_key in instructions[instuction_key]["fields"][0].keys():
                        if "excluded_values" in instructions[instuction_key].keys():
                            if instrfield_imm[imm_key]["shift"] == "0":
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    for elem in range(
                                        len(
                                            instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key]
                                        )
                                    ):
                                        if str(imm_key) in config_variables.keys():
                                            if (
                                                '"ParserMatchClass"'
                                                in config_variables[str(imm_key)].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = "
                                                        + config_variables[
                                                            str(imm_key)
                                                        ]['"ParserMatchClass"'].strip(
                                                            '"'
                                                        )
                                                        + ";\n"
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = UImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            - 1
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = UImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + "Non"
                                                    + str(
                                                        num2words.num2words(
                                                            int(
                                                                instructions[
                                                                    instuction_key
                                                                ]["excluded_values"][
                                                                    imm_key
                                                                ][
                                                                    elem
                                                                ]
                                                            )
                                                        )
                                                    ).capitalize()
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                    break
                                else:
                                    for elem in range(
                                        len(
                                            instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key]
                                        )
                                    ):
                                        if str(imm_key) in config_variables.keys():
                                            if (
                                                '"ParserMatchClass"'
                                                in config_variables[str(imm_key)].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = "
                                                        + config_variables[
                                                            str(imm_key)
                                                        ]['"ParserMatchClass"'].strip(
                                                            '"'
                                                        )
                                                        + ";\n"
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = UImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = UImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + "Non"
                                                    + str(
                                                        num2words.num2words(
                                                            int(
                                                                instructions[
                                                                    instuction_key
                                                                ]["excluded_values"][
                                                                    imm_key
                                                                ][
                                                                    elem
                                                                ]
                                                            )
                                                        )
                                                    ).capitalize()
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                    break
                            else:
                                text = "Lsb"
                                for _ in range(int(instrfield_imm[imm_key]["shift"])):
                                    text += "0"
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    for elem in range(
                                        len(
                                            instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key]
                                        )
                                    ):
                                        if str(imm_key) in config_variables.keys():
                                            if (
                                                '"ParserMatchClass"'
                                                in config_variables[str(imm_key)].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = "
                                                        + config_variables[
                                                            str(imm_key)
                                                        ]['"ParserMatchClass"'].strip(
                                                            '"'
                                                        )
                                                        + ";\n"
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = UImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                            + 1
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                        else:
                                            if (
                                                "one_extended"
                                                in instrfield_imm[imm_key].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = UImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            - 1
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                            + 1
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Neg"
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = UImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            - 1
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                    break
                                else:
                                    for elem in range(
                                        len(
                                            instructions[instuction_key][
                                                "excluded_values"
                                            ][imm_key]
                                        )
                                    ):
                                        if str(imm_key) in config_variables.keys():
                                            if (
                                                '"ParserMatchClass"'
                                                in config_variables[str(imm_key)].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = "
                                                        + config_variables[
                                                            str(imm_key)
                                                        ]['"ParserMatchClass"'].strip(
                                                            '"'
                                                        )
                                                        + ";\n"
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = UImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                            + 1
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                        else:
                                            if (
                                                "one_extended"
                                                in instrfield_imm[imm_key].keys()
                                            ):
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = UImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                            + 1
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Neg"
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                            else:
                                                if (
                                                    "\tlet ParserMatchClass = "
                                                    not in content
                                                ):
                                                    content += (
                                                        "\tlet ParserMatchClass = UImmAsmOperand<"
                                                        + str(
                                                            int(
                                                                instrfield_imm[imm_key][
                                                                    "size"
                                                                ]
                                                            )
                                                            + int(
                                                                instrfield_imm[imm_key][
                                                                    "shift"
                                                                ]
                                                            )
                                                        )
                                                        + ", "
                                                        + '"'
                                                        + text
                                                        + "Non"
                                                        + str(
                                                            num2words.num2words(
                                                                int(
                                                                    instructions[
                                                                        instuction_key
                                                                    ][
                                                                        "excluded_values"
                                                                    ][
                                                                        imm_key
                                                                    ][
                                                                        elem
                                                                    ]
                                                                )
                                                            )
                                                        ).capitalize()
                                                        + '"'
                                                        + ">;\n"
                                                    )
                                                    size = str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                    break
                        else:
                            if instrfield_imm[imm_key]["shift"] == "0":
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    if str(imm_key) in config_variables.keys():
                                        if (
                                            '"ParserMatchClass"'
                                            in config_variables[str(imm_key)].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = "
                                                    + config_variables[str(imm_key)][
                                                        '"ParserMatchClass"'
                                                    ].strip('"')
                                                    + ";\n"
                                                )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = UImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        break
                                    else:
                                        if "\tlet ParserMatchClass = " not in content:
                                            content += (
                                                "\tlet ParserMatchClass = UImmAsmOperand<"
                                                + str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                                + ">;\n"
                                            )
                                            size = str(
                                                int(instrfield_imm[imm_key]["size"])
                                                - 1
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            break
                                else:
                                    if (
                                        str(imm_key).replace(".", "").upper()
                                        in config_variables.keys()
                                    ):
                                        if (
                                            '"ParserMatchClass"'
                                            in config_variables[str(imm_key)].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = "
                                                    + config_variables[str(imm_key)][
                                                        '"ParserMatchClass"'
                                                    ].strip('"')
                                                    + ";\n"
                                                )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = UImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        break
                                    else:
                                        if "\tlet ParserMatchClass = " not in content:
                                            content += (
                                                "\tlet ParserMatchClass = UImmAsmOperand<"
                                                + str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                                + ">;\n"
                                            )
                                            size = str(
                                                int(instrfield_imm[imm_key]["size"])
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            break
                            else:
                                text = "Lsb"
                                for _ in range(int(instrfield_imm[imm_key]["shift"])):
                                    text += "0"
                                if "sign_extension" in instrfield_imm[imm_key].keys():
                                    if str(imm_key) in config_variables.keys():
                                        if (
                                            '"ParserMatchClass"'
                                            in config_variables[str(imm_key)].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = "
                                                    + config_variables[str(imm_key)][
                                                        '"ParserMatchClass"'
                                                    ].strip('"')
                                                    + ";\n"
                                                )
                                            size = str(
                                                int(instrfield_imm[imm_key]["size"])
                                                - 1
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                        else:
                                            content += (
                                                "\tlet ParserMatchClass = UImmAsmOperand<"
                                                + str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                    + 1
                                                )
                                                + ", "
                                                + '"'
                                                + text
                                                + '"'
                                                + ">;\n"
                                            )
                                            size = str(
                                                int(instrfield_imm[imm_key]["size"])
                                                - 1
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )

                                        break
                                    else:
                                        if (
                                            "one_extended"
                                            in instrfield_imm[imm_key].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = UImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                        + 1
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + text
                                                    + "Neg"
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = UImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        - 1
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + text
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        break
                                else:
                                    if str(imm_key) in config_variables.keys():
                                        if (
                                            '"ParserMatchClass"'
                                            in config_variables[str(imm_key)].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = "
                                                    + config_variables[str(imm_key)][
                                                        '"ParserMatchClass"'
                                                    ].strip('"')
                                                    + ";\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    - 1
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                                break
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = UImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                        + 1
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + text
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                    else:
                                        if (
                                            "one_extended"
                                            in instrfield_imm[imm_key].keys()
                                        ):
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = UImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                        + 1
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + text
                                                    + "Neg"
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        else:
                                            if (
                                                "\tlet ParserMatchClass = "
                                                not in content
                                            ):
                                                content += (
                                                    "\tlet ParserMatchClass = UImmAsmOperand<"
                                                    + str(
                                                        int(
                                                            instrfield_imm[imm_key][
                                                                "size"
                                                            ]
                                                        )
                                                        + int(
                                                            instrfield_imm[imm_key][
                                                                "shift"
                                                            ]
                                                        )
                                                    )
                                                    + ", "
                                                    + '"'
                                                    + text
                                                    + '"'
                                                    + ">;\n"
                                                )
                                                size = str(
                                                    int(instrfield_imm[imm_key]["size"])
                                                    + int(
                                                        instrfield_imm[imm_key]["shift"]
                                                    )
                                                )
                                        break
                break
    forLoop = False
    if "Non" in key:
        for instruction in instructions.keys():
            imm_class = instrfield_classes[key][0]
            if imm_class in instructions[instruction]["fields"][0].keys():
                instruction_key = instruction
                if "excluded_values" in instructions[instruction_key].keys():
                    if (
                        "Non"
                        + str(
                            num2words.num2words(
                                str(
                                    instructions[instruction_key]["excluded_values"][
                                        imm_class
                                    ][0]
                                )
                            )
                        ).capitalize()
                        not in content
                    ):
                        content = content.replace(
                            ">",
                            ", "
                            + '"'
                            + "Non"
                            + str(
                                num2words.num2words(
                                    str(
                                        instructions[instruction_key][
                                            "excluded_values"
                                        ][imm_class][0]
                                    )
                                )
                            ).capitalize()
                            + '"'
                            + ">",
                        )
    for instruction_key in instructions.keys():
        for imm_key in instrfield_classes[key]:
            if imm_key == check_key:
                reloc = ""
                if "reloc" in instrfield_imm[imm_key].keys():
                    reloc = instrfield_imm[imm_key]["reloc"]
                if imm_key in instructions[instruction_key]["fields"][0]:
                    for elem in config_variables["LLVMPrintMethodAttrib"]:
                        if (
                            elem in instructions[instruction_key]["attributes"]
                            or reloc in config_variables["LLVMPrintMethodReloc"]
                        ):
                            content += (
                                '\tlet PrintMethod = "'
                                + config_variables["LLVMPrintMethodValue"]
                                + '";\n'
                            )
                            forLoop = True
                            break
        if forLoop is True:
            break
    encoderMethod = ""
    for instruction_key in instructions.keys():
        for imm_key in instrfield_classes[key]:
            if imm_key == check_key:
                reloc = ""
                if imm_key in instructions[instruction_key]["fields"][0]:
                    if str(imm_key) in config_variables.keys():
                        if '"EncoderMethod"' in config_variables[str(imm_key)].keys():
                            encoderMethod = (
                                "\tlet EncoderMethod = "
                                + config_variables[str(imm_key)]['"EncoderMethod"']
                                + ";\n"
                            )
                        elif (
                            '"DisableEncoderMethod"'
                            in config_variables[str(imm_key)].keys()
                        ):
                            if (
                                config_variables[str(imm_key)]['"DisableEncoderMethod"']
                                == '"True"'
                            ):
                                encoderMethod = False
    if encoderMethod == "" and encoderMethod is not False:
        encoderMethod = (
            "\tlet EncoderMethod = "
            + config_variables["GenericOperand"]['"EncoderMethod"']
            + ";\n"
        )
    if encoderMethod != "" and encoderMethod is not False:
        content += encoderMethod
    for imm_key in instrfield_classes[key]:
        if imm_key == check_key:
            if str(imm_key).lower() in config_variables.keys():
                if '"PrintMethod"' in config_variables[imm_key].keys():
                    content += (
                        "\tlet PrintMethod = "
                        + config_variables[imm_key]['"PrintMethod"']
                        + ";\n"
                    )
                    break
    for imm_key in instrfield_classes[key]:
        if imm_key == check_key:
            if "signed" in instrfield_imm[imm_key].keys():
                if instrfield_imm[imm_key]["signed"] == "true":
                    if "sign_extension" in instrfield_imm[imm_key].keys():
                        for instruction in instructions.keys():
                            if imm_key in instructions[instruction]["fields"][0]:
                                if imm_key in config_variables.keys():
                                    if (
                                        '"DecoderMethod"'
                                        in config_variables[imm_key].keys()
                                    ):
                                        content += (
                                            "\tlet DecoderMethod = "
                                            + config_variables[imm_key][
                                                '"DecoderMethod"'
                                            ]
                                            + ";\n"
                                        )
                                        decoderMethod = (
                                            "\tlet DecoderMethod = "
                                            + config_variables[imm_key][
                                                '"DecoderMethod"'
                                            ]
                                            + ";\n"
                                        )
                                    else:
                                        content += (
                                            '\tlet DecoderMethod = "decodeSImmOperand<'
                                            + str(
                                                int(instrfield_imm[imm_key]["size"])
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            + '>";\n'
                                        )
                                        decoderMethod = (
                                            '\tlet DecoderMethod = "decodeSImmOperand<'
                                            + str(
                                                int(instrfield_imm[imm_key]["size"])
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            + '>";\n'
                                        )
                                    break
                                else:
                                    content += (
                                        '\tlet DecoderMethod = "decodeSImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        + '>";\n'
                                    )
                                    decoderMethod = (
                                        '\tlet DecoderMethod = "decodeSImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        + '>";\n'
                                    )
                                    break
                        break
                    else:
                        for instruction in instructions.keys():
                            if imm_key in instructions[instruction]["fields"][0]:
                                if imm_key in config_variables.keys():
                                    if (
                                        '"DecoderMethod"'
                                        in config_variables[imm_key].keys()
                                    ):
                                        content += (
                                            "\tlet DecoderMethod = "
                                            + config_variables[imm_key][
                                                '"DecoderMethod"'
                                            ]
                                            + ";\n"
                                        )
                                        decoderMethod = (
                                            "\tlet DecoderMethod = "
                                            + config_variables[imm_key][
                                                '"DecoderMethod"'
                                            ]
                                            + ";\n"
                                        )
                                    else:
                                        content += (
                                            '\tlet DecoderMethod = "decodeSImmOperand<'
                                            + str(
                                                int(instrfield_imm[imm_key]["size"])
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            + '>";\n'
                                        )
                                        decoderMethod = (
                                            '\tlet DecoderMethod = "decodeSImmOperand<'
                                            + str(
                                                int(instrfield_imm[imm_key]["size"])
                                                + int(instrfield_imm[imm_key]["shift"])
                                            )
                                            + '>";\n'
                                        )
                                    break
                                else:
                                    content += (
                                        '\tlet DecoderMethod = "decodeSImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        + '>";\n'
                                    )
                                    decoderMethod = (
                                        '\tlet DecoderMethod = "decodeSImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        + '>";\n'
                                    )
                                    break
                        break
            else:
                if "sign_extension" in instrfield_imm[imm_key].keys():
                    for instruction in instructions.keys():
                        if imm_key in instructions[instruction]["fields"][0]:
                            if imm_key in config_variables.keys():
                                if (
                                    '"DecoderMethod"'
                                    in config_variables[imm_key].keys()
                                ):
                                    content += (
                                        "\tlet DecoderMethod = "
                                        + config_variables[imm_key]['"DecoderMethod"']
                                        + ";\n"
                                    )
                                    decoderMethod = (
                                        "\tlet DecoderMethod = "
                                        + config_variables[imm_key]['"DecoderMethod"']
                                        + ";\n"
                                    )
                                else:
                                    content += (
                                        '\tlet DecoderMethod = "decodeUImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        + '>";\n'
                                    )
                                    decoderMethod = (
                                        '\tlet DecoderMethod = "decodeUImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        + '>";\n'
                                    )
                                break
                            else:
                                content += (
                                    '\tlet DecoderMethod = "decodeUImmOperand<'
                                    + str(
                                        int(instrfield_imm[imm_key]["size"])
                                        + int(instrfield_imm[imm_key]["shift"])
                                    )
                                    + '>";\n'
                                )
                                decoderMethod = (
                                    '\tlet DecoderMethod = "decodeUImmOperand<'
                                    + str(
                                        int(instrfield_imm[imm_key]["size"])
                                        + int(instrfield_imm[imm_key]["shift"])
                                    )
                                    + '>";\n'
                                )
                                break
                    break
                else:
                    for instruction in instructions.keys():
                        if imm_key in instructions[instruction]["fields"][0]:
                            if imm_key in config_variables.keys():
                                if (
                                    '"DecoderMethod"'
                                    in config_variables[imm_key].keys()
                                ):
                                    content += (
                                        "\tlet DecoderMethod = "
                                        + config_variables[imm_key]['"DecoderMethod"']
                                        + ";\n"
                                    )
                                    decoderMethod = (
                                        "\tlet DecoderMethod = "
                                        + config_variables[imm_key]['"DecoderMethod"']
                                        + ";\n"
                                    )
                                else:
                                    content += (
                                        '\tlet DecoderMethod = "decodeUImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        + '>";\n'
                                    )
                                    decoderMethod = (
                                        '\tlet DecoderMethod = "decodeUImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        + '>";\n'
                                    )
                                break
                            else:
                                if "one_extended" in instrfield_imm[imm_key].keys():
                                    content += (
                                        '\tlet DecoderMethod = "decodeUImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                            + 1
                                        )
                                        + '>";\n'
                                    )
                                    decoderMethod = (
                                        '\tlet DecoderMethod = "decodeUImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                            + 1
                                        )
                                        + '>";\n'
                                    )
                                else:
                                    content += (
                                        '\tlet DecoderMethod = "decodeUImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        + '>";\n'
                                    )
                                    decoderMethod = (
                                        '\tlet DecoderMethod = "decodeUImmOperand<'
                                        + str(
                                            int(instrfield_imm[imm_key]["size"])
                                            + int(instrfield_imm[imm_key]["shift"])
                                        )
                                        + '>";\n'
                                    )
                                break
                    break
    if "Non" in key:
        for instruction in instructions.keys():
            imm_class = instrfield_classes[key][0]
            if imm_class in instructions[instruction]["fields"][0].keys():
                instruction_key = instruction
                if "excluded_values" in instructions[instruction_key].keys():
                    if (
                        "Imm != "
                        + str(
                            instructions[instruction_key]["excluded_values"][imm_class][
                                0
                            ]
                        )
                        not in return_value
                    ):
                        return_value = return_value.replace(
                            "return",
                            "return (Imm != "
                            + str(
                                instructions[instruction_key]["excluded_values"][
                                    imm_class
                                ][0]
                            )
                            + ") &&",
                        )
    for imm_key in instrfield_classes[key]:
        if imm_key == check_key:
            if imm_key in config_variables.keys():
                if '"DisableEncoderMethod"' not in config_variables[imm_key].keys():
                    content += "\tlet MCOperandPredicate = [{\n"
                    content += "\t\tint64_t Imm;\n"
                    content += "\t\tif (MCOp.evaluateAsConstantImm(Imm))\n"
                    if int(instrfield_imm[imm_key]["shift"]) != 0:
                        content += "\t\t\t" + return_value + "\n"
                    else:
                        if "signed" in instrfield_imm[imm_key].keys():
                            if instrfield_imm[imm_key]["signed"] == "true":
                                content += "\t\t\t" + return_value + "\n"
                        else:
                            content += "\t\t\t" + return_value + "\n"
                    content += "\t\treturn MCOp.isBareSymbolRef();\n"
                    content += "\t}];\n"
                    break
            else:
                if imm_key not in config_variables["ImmediateOperands"]:
                    content += "\tlet MCOperandPredicate = [{\n"
                    content += "\t\tint64_t Imm;\n"
                    content += "\t\tif (MCOp.evaluateAsConstantImm(Imm))\n"
                    if int(instrfield_imm[imm_key]["shift"]) != 0:
                        content += "\t\t\t" + return_value + "\n"
                    else:
                        if "signed" in instrfield_imm[imm_key].keys():
                            if instrfield_imm[imm_key]["signed"] == "true":
                                content += "\t\t\t" + return_value + "\n"
                        else:
                            content += "\t\t\t" + return_value + "\n"
                    content += "\t\treturn MCOp.isBareSymbolRef();\n"
                    content += "\t}];\n"
                    break
    if int(instrfield_imm[imm_key]["shift"]) == 0:
        if "nonzero" not in statement and "Imm != 0" not in ImmLeaf:
            for instruction in instructions.keys():
                if imm_key in instructions[instruction]["fields"][0]:
                    if (
                        instructions[instruction]["width"]
                        == config_variables["LLVMStandardInstructionWidth"]
                    ):
                        if imm_key in config_variables.keys():
                            if (
                                '"disableOperandType"'
                                in config_variables[imm_key].keys()
                            ):
                                if (
                                    config_variables[imm_key]['"disableOperandType"']
                                    != '"True"'
                                ):
                                    content += (
                                        '\tlet OperandType = "OPERAND_'
                                        + str(key.split("_")[0]).upper()
                                        + '";\n'
                                    )
                            else:
                                content += (
                                    '\tlet OperandType = "OPERAND_'
                                    + str(key.split("_")[0]).upper()
                                    + '";\n'
                                )
                            if (
                                '"disableOperandNamespace"'
                                in config_variables[imm_key].keys()
                            ):
                                if (
                                    config_variables[imm_key][
                                        '"disableOperandNamespace"'
                                    ]
                                    != '"True"'
                                ):
                                    content += (
                                        '\tlet OperandNamespace = "'
                                        + namespace
                                        + 'Op";\n'
                                    )
                            else:
                                content += (
                                    '\tlet OperandNamespace = "' + namespace + 'Op";\n'
                                )
                        else:
                            content += (
                                '\tlet OperandType = "OPERAND_'
                                + str(key.split("_")[0]).upper()
                                + '";\n'
                            )
                            content += (
                                '\tlet OperandNamespace = "' + namespace + 'Op";\n'
                            )
                        break
    if "nonzero" not in statement and "Imm != 0" not in ImmLeaf:
        statement = str(statement).replace("(Imm != 0) && ", "")
        content = str(content).replace(', "NonZero"', "")
    if "nonzero" not in statement and aliasEnabled is False and "Imm != 0" in ImmLeaf:
        statement = str(statement).replace("(Imm != 0) && ", "")
        content = str(content).replace("(Imm != 0) && ", "")
        content = str(content).replace(', "NonZero"', "")
    forLoop = False
    for instruction_key in instructions.keys():
        for imm_key in instrfield_classes[key]:
            if imm_key == check_key:
                reloc = ""
                if "reloc" in instrfield_imm[imm_key].keys():
                    reloc = instrfield_imm[imm_key]["reloc"]
                if imm_key in instructions[instruction_key]["fields"][0]:
                    for elem in config_variables["LLVMOperandTypeAttrib"]:
                        if (
                            elem in instructions[instruction_key]["attributes"]
                            or reloc in config_variables["LLVMOperandTypeReloc"]
                        ):
                            if imm_key in config_variables.keys():
                                if (
                                    '"disableOperandType"'
                                    in config_variables[imm_key].keys()
                                ):
                                    if (
                                        config_variables[imm_key][
                                            '"disableOperandType"'
                                        ]
                                        != '"True"'
                                    ):
                                        content += (
                                            '\tlet OperandType = "'
                                            + config_variables["LLVMOperandTypeValue"]
                                            + '";\n'
                                        )
                                else:
                                    content += (
                                        '\tlet OperandType = "'
                                        + config_variables["LLVMOperandTypeValue"]
                                        + '";\n'
                                    )
                            else:
                                content += (
                                    '\tlet OperandType = "'
                                    + config_variables["LLVMOperandTypeValue"]
                                    + '";\n'
                                )
                            decoderMethodCopy = decoderMethod
                            for elem in config_variables["basicDecodeMethod"]:
                                if elem in decoderMethod:
                                    decoderMethod = decoderMethod.replace(elem, elem)
                                    content = content.replace(
                                        decoderMethodCopy, decoderMethod
                                    )
                            forLoop = True
                            break
        if forLoop is True:
            break
    content += "}"
    return statement + content


## A function which writes in a file the content for an immediate type which is used in instructions
#
# @param filename The name for the file in which the function will write the content
# @param filenameC The name for the file in which the function will write the content for compressed
# @param instrfield_classes The immediate types which have to be defined
# @param instructions A dictionary which contains all the instructions parsed from ADL file
# @return It writes in a file the content generated by the called function (generate_imms_class)
def write_imms_classes(filename, filenameC, instrfield_classes, instructions):
    this_instructions = instructions
    f = open(filename, "a")
    g = open(filenameC, "a")
    config_variables = config.config_environment(config_file, llvm_config)
    instrfield_imm = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
    namespace = config_variables["Namespace"]
    OperandParser = "Operand<XLenVT> "
    statement = ""
    ImmAsmOperand = (
        "class ImmAsmOperand <"
        + config_variables["ImmAsmOperandParameters"][0].replace("_", " ")
        + ", "
        + config_variables["ImmAsmOperandParameters"][1].replace("_", " ")
        + ", "
        + config_variables["ImmAsmOperandParameters"][2].replace("_", " ")
        + "> : AsmOperandClass {\n"
    )
    ImmAsmOperand += (
        "\tlet Name = "
        + config_variables["ImmAsmOperandName"][0]
        + ' # "Imm" # '
        + config_variables["ImmAsmOperandName"][1]
        + " # "
        + config_variables["ImmAsmOperandName"][2]
        + ";\n"
    )
    ImmAsmOperand += (
        "\tlet RenderMethod = "
        + '"'
        + config_variables["ImmAsmOperandRenderMethod"]
        + '"'
        + ";\n"
    )
    ImmAsmOperand += (
        "\tlet DiagnosticType = "
        + config_variables["ImmAsmOperandDiagnosticType"]
        + ";\n"
    )
    ImmAsmOperand += "}"
    SImmAsmOperand = (
        "class SImmAsmOperand<"
        + str(config_variables["SImmAsmOperandParameters"][0]).replace("_", " ")
        + ", "
        + str(config_variables["SImmAsmOperandParameters"][1]).replace("_", " ")
        + '= "">'
        + "\n"
    )
    SImmAsmOperand += '\t:ImmAsmOperand<"S", width, suffix> {'
    SImmAsmOperand += "\n}"
    UImmAsmOperand = (
        "class UImmAsmOperand<"
        + str(config_variables["UImmAsmOperandParameters"][0]).replace("_", " ")
        + ", "
        + str(config_variables["UImmAsmOperandParameters"][1]).replace("_", " ")
        + '= "">'
        + "\n"
    )
    UImmAsmOperand += '\t:ImmAsmOperand<"U", width, suffix> {'
    UImmAsmOperand += "\n}"
    f.write(ImmAsmOperand)
    f.write("\n\n")
    f.write(SImmAsmOperand)
    f.write("\n\n")
    f.write(UImmAsmOperand)
    f.write("\n\n")
    dumped_info = list()
    buffer = ""
    for key in instrfield_classes:
        for imm_key in instrfield_classes[key]:
            content_dumped = False
            for instruction in instructions.keys():
                if imm_key in instructions[instruction]["fields"][0].keys():
                    already_printed = False
                    define_content = ""
                    if str(imm_key) in config_variables.keys():
                        if '"DefineOperand"' in config_variables[str(imm_key)].keys():
                            define_content = (
                                "def "
                                + config_variables[str(imm_key)][
                                    '"DefineOperand"'
                                ].replace('"', "")
                                + " : "
                            )
                            if str(imm_key) in config_variables.keys():
                                if (
                                    '"OperandClass"'
                                    in config_variables[str(imm_key)].keys()
                                ):
                                    if (
                                        "<"
                                        in config_variables[str(imm_key)][
                                            '"OperandClass"'
                                        ]
                                    ):
                                        define_content += config_variables[
                                            str(imm_key)
                                        ]['"OperandClass"']
                                    else:
                                        define_content += config_variables[
                                            str(imm_key)
                                        ]['"OperandClass"'].replace('"', "")
                                else:
                                    define_content += "ImmAsmOperand"
                            define_content += " {\n"
                            if str(imm_key) in config_variables.keys():
                                if (
                                    '"ImmAsmOperandName"'
                                    in config_variables[str(imm_key)].keys()
                                ):
                                    define_content += (
                                        "\tlet Name = "
                                        + config_variables[str(imm_key)][
                                            '"ImmAsmOperandName"'
                                        ]
                                        + ";\n"
                                    )
                            if str(imm_key) in config_variables.keys():
                                if (
                                    '"ImmAsmOperandRenderMethod"'
                                    in config_variables[str(imm_key)].keys()
                                ):
                                    define_content += (
                                        "\tlet RenderMethod = "
                                        + config_variables[str(imm_key)][
                                            '"ImmAsmOperandRenderMethod"'
                                        ]
                                        + ";\n"
                                    )
                            if str(imm_key) in config_variables.keys():
                                if (
                                    '"ImmAsmOperandDiagnosticType"'
                                    in config_variables[str(imm_key)].keys()
                                ):
                                    define_content += (
                                        "\tlet DiagnosticType = "
                                        + config_variables[str(imm_key)][
                                            '"ImmAsmOperandDiagnosticType"'
                                        ]
                                        + ";\n"
                                    )
                            if str(imm_key) in config_variables.keys():
                                if (
                                    '"ParserMethod"'
                                    in config_variables[str(imm_key)].keys()
                                ):
                                    define_content += (
                                        "\tlet ParserMethod = "
                                        + config_variables[str(imm_key)][
                                            '"ParserMethod"'
                                        ]
                                        + ";\n"
                                    )
                            define_content += "}\n"
                            if define_content in dumped_info:
                                content_dumped = True
                            else:
                                dumped_info.append(define_content)
                            if already_printed is False:
                                if content_dumped is False:
                                    if (
                                        instructions[instruction]["width"]
                                        == config_variables[
                                            "LLVMStandardInstructionWidth"
                                        ]
                                    ):
                                        f.write(define_content)
                                        f.write("\n")
                                        already_printed = True
                                    else:
                                        g.write(define_content)
                                        g.write("\n")
                                        already_printed = True
        exitFor = False
        sameInstruction = False
        for imm_key in instrfield_classes[key]:
            if exitFor is False:
                for instuction_key in instructions.keys():
                    if sameInstruction is False:
                        if imm_key in instructions[instuction_key]["fields"][0].keys():
                            if (
                                instructions[instuction_key]["width"]
                                == config_variables["LLVMStandardInstructionWidth"]
                            ):
                                content_generated = generate_imms_class(
                                    key, this_instructions, imm_key
                                )
                                if content_generated not in buffer:
                                    f.write(
                                        generate_imms_class(
                                            key, this_instructions, imm_key
                                        )
                                    )
                                    f.write("\n\n")
                                    exitFor = True
                                    sameInstruction = True
                                    buffer += content_generated
                                break
                            else:
                                content_generated = generate_imms_class(
                                    key, this_instructions, imm_key
                                )
                                if content_generated not in buffer:
                                    g.write(
                                        generate_imms_class(
                                            key, this_instructions, imm_key
                                        )
                                    )
                                    g.write("\n\n")
                                    exitFor = True
                                    sameInstruction = True
                                    buffer += content_generated
                                break
    f.close()
    g.close()


## This function generates instruction alias content based on the information parsed from ADL
#
# @param key This argument represents the alias which will be generated
# @return The function will return a generated content representing the alias definition
def generate_instruction_alias(key):
    config_variables = config.config_environment(config_file, llvm_config)
    define = "def"
    registers = adl_parser.parse_adl(config_variables["ADLName"])
    instructions_aliases = adl_parser.parse_instructions_aliases_from_adl(
        config_variables["ADLName"]
    )
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])
    instrfield_ref = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    regfiles = adl_parser.parse_adl(config_variables["ADLName"])
    alias_regs = adl_parser.get_alias_for_regs(config_variables["ADLName"])
    alias_regs_copy = alias_regs.copy()
    for key_reg in alias_regs.keys():
        if key_reg not in registers.keys():
            del alias_regs_copy[key_reg]
    alias_regs = alias_regs_copy
    statement = ""
    dsyntax = ""
    instruction_dsyntax = ""
    dsyntax = '"' + key
    instruction_dsyntax = "("
    dsyntax_list = instructions_aliases[key]["dsyntax"][1:]
    if len(dsyntax_list) > 1:
        for elem in range(len(dsyntax_list) - 1):
            dsyntax += " "
            dsyntax += dsyntax_list[elem] + ","
    elif len(dsyntax_list) == 1:
        dsyntax += " "
        dsyntax += dsyntax_list[0]
    if len(dsyntax_list) > 1:
        dsyntax += (
            " "
            + instructions_aliases[key]["dsyntax"][
                len(instructions_aliases[key]["dsyntax"]) - 1
            ]
        )
    dsyntax += '"'
    statement += "InstAlias<" + dsyntax + ", "
    alias = str(instructions_aliases[key]["aliases"][0])
    instruction_dsyntax += str(instructions[0][alias]["dsyntax"][0]).upper() + " "
    if "." in instruction_dsyntax:
        instruction_dsyntax = instruction_dsyntax.replace(".", "_")
    misc_value = dict()
    values = ""
    sources_dict = dict()
    if "sources" in instructions_aliases[key]["fields"][0]["alias"][0].keys():
        if len(instructions_aliases[key]["fields"][0]["alias"][0]["sources"]) >= 1:
            if (
                "source"
                in instructions_aliases[key]["fields"][0]["alias"][0]["sources"][
                    0
                ].keys()
            ):
                for field in instructions_aliases[key]["fields"][0]["alias"][0][
                    "sources"
                ][0]["source"]:
                    for dict_key in field["field"][0].keys():
                        sources_dict[field["field"][0][dict_key]] = ""
                    for dict_key in field["value"][0].keys():
                        sources_dict[field["field"][0][dict_key]] = field["value"][0][
                            dict_key
                        ]
    if "miscs" in instructions_aliases[key]["fields"][0]["alias"][0].keys():
        values = instructions_aliases[key]["fields"][0]["alias"][0]["miscs"]
    key_value = ""
    key_pair = ""
    if values != "\n" and values != "":
        for index in range(len(values[0]["misc"])):
            value = values[0]["misc"][index]
            for element in value.keys():
                for index_aux in range(len(value[element])):
                    if element == "field":
                        for key_element in value[element][index_aux].keys():
                            key_pair = value[element][index_aux][key_element]
                            break
                    else:
                        for key_element in value[element][index_aux].keys():
                            key_value = value[element][index_aux][key_element]
                            break
            misc_value[key_pair] = key_value
    field = ""
    field_values = dict()
    for key_elem in misc_value.keys():
        field_values[key_elem] = misc_value[key_elem]
    alias_instruction_syntax_dict_copy = ""
    alias_cpy = list()
    if alias in alias_instruction_syntax_dict.keys():
        alias_cpy = list(alias_instruction_syntax_dict[alias].split(","))
        alias_instruction_syntax_dict_copy = alias_instruction_syntax_dict[alias]
    registers = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    registers_ref = adl_parser.parse_adl(config_variables["ADLName"])
    for source in sources_dict.keys():
        for element in alias_instruction_syntax_dict_copy.split(","):
            element = element.strip(" ")
            element = element.split(":$")
            if len(element) > 1:
                if source == element[1]:
                    alias_instruction_syntax_dict_copy = (
                        alias_instruction_syntax_dict_copy.replace(
                            element[0] + ":$" + element[1],
                            element[0] + ":$" + sources_dict[element[1]],
                            1,
                        )
                    )
                    break
                elif sources_dict[source] == element[1]:
                    alias_instruction_syntax_dict_copy = (
                        alias_instruction_syntax_dict_copy.replace(
                            element[0] + ":$" + source,
                            element[0] + ":$" + element[1],
                            1,
                        )
                    )
                    break
    for element in alias_instruction_syntax_dict_copy.split(","):
        if "_wb" in element.strip(" "):
            alias_instruction_syntax_dict_copy = (
                alias_instruction_syntax_dict_copy.replace(element, "")
            )
    for field in field_values.keys():
        for element in alias_cpy:
            if "_wb" not in element:
                if field in element:
                    element = element.strip(" ")
                    if field_values[field] != "":
                        if field in registers:
                            for regclass in register_classes.keys():
                                if field in register_classes[regclass]:
                                    if regclass in registers_ref.keys():
                                        register_ref = registers_ref[regclass].prefix
                                    if register_ref == "":
                                        register_ref = regclass.upper()
                                    field_values[field] = str(
                                        register_ref + field_values[field]
                                    ).upper()
                            alias_instruction_syntax_dict_copy = (
                                alias_instruction_syntax_dict_copy.replace(
                                    element, field_values[field], 1
                                )
                            )
    alias_instruction_syntax_list_copy = alias_instruction_syntax_dict_copy.split(",")
    alias_instruction_syntax_list = alias_instruction_syntax_dict_copy
    for field in field_values.keys():
        field_check = False
        for element in alias_instruction_syntax_list_copy:
            element = element.strip(" ")
            element = element.split(":$")
            if len(element) > 1:
                if element[0] not in register_classes.keys():
                    for regclass in register_classes.keys():
                        if field in register_classes[regclass]:
                            if field == element[0]:
                                alias_instruction_syntax_list = (
                                    alias_instruction_syntax_list.replace(
                                        element[0], regclass
                                    )
                                )
                            if element[1] in instrfield_ref:
                                alias_instruction_syntax_list = (
                                    alias_instruction_syntax_list.replace(
                                        element[1], field
                                    )
                                )
                            if field in field_values.keys():
                                if regclass in registers_ref.keys():
                                    register_ref = registers_ref[regclass].prefix
                                if element[0] == regclass:
                                    alias_instruction_syntax_list = (
                                        alias_instruction_syntax_list.replace(
                                            regclass + ":$" + field,
                                            register_ref.upper() + field_values[field],
                                        )
                                    )
                                else:
                                    if register_ref.upper() not in field_values[field]:
                                        alias_instruction_syntax_list = (
                                            alias_instruction_syntax_list.replace(
                                                element[0] + ":$" + field,
                                                register_ref.upper()
                                                + field_values[field],
                                            )
                                        )
                                    else:
                                        alias_instruction_syntax_list = (
                                            alias_instruction_syntax_list.replace(
                                                element[0] + ":$" + field,
                                                field_values[field],
                                            )
                                        )
                                field_check = True
                        else:
                            if field_values[field] != field:
                                if field_check is False:
                                    alias_instruction_syntax_list = (
                                        alias_instruction_syntax_list.replace(
                                            element[0] + ":$" + field,
                                            field_values[field],
                                        )
                                    )
    alias_instruction_syntax_list_copy = alias_instruction_syntax_list.split(",")
    for element in alias_instruction_syntax_list_copy:
        if "_wb" in element.strip(" "):
            alias_instruction_syntax_list = alias_instruction_syntax_list.replace(
                element.strip(" ") + ", ", ""
            )
    alias_instruction_syntax_list_copy = alias_instruction_syntax_list.split(",")
    for element in alias_instruction_syntax_list_copy:
        for key_for in alias_regs.keys():
            for key_pair in misc_value.keys():
                if utils.check_register_class_prefix(regfiles, key_for) is False:
                    for value in alias_regs[key_for].keys():
                        if str(key_for + value).upper() == element.strip(" "):
                            alias_instruction_syntax_list = (
                                alias_instruction_syntax_list.replace(
                                    element.strip(" "),
                                    alias_regs[key_for][value][0].upper(),
                                )
                            )
    if "" in alias_instruction_syntax_list.split(","):
        alias_instruction_syntax_list.split(",").remove("")
        instruction_dsyntax += alias_instruction_syntax_list
    else:
        instruction_dsyntax += alias_instruction_syntax_list
    if ",," in instruction_dsyntax:
        instruction_dsyntax = instruction_dsyntax.replace(",,", ",")
    if " ," in instruction_dsyntax:
        instruction_dsyntax = instruction_dsyntax.replace(" ,", "")
    statement += instruction_dsyntax + ")"
    statement += ">;"
    return define + " : " + statement


## This function will write the content for each alias generated in a specific file
#
# @param file_name The parameter represents the file in which the content will be written
# @param extensions_list This list contains the extensions for which the instrinsics will be generated. If empty, all extensions will be generated
# @return This function will return a file which contains all the information about aliases
def write_instructions_aliases(file_name, extensions_list):
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[
        0
    ]
    instructions_aliases = adl_parser.parse_instructions_aliases_from_adl(
        config_variables["ADLName"]
    )
    section_delimiter = "//===---------------------------------------------------------------------===//\n"
    section_delimiter += "// Aliases\n"
    section_delimiter += "//===---------------------------------------------------------------------===//\n"
    section_delimiter_dump = dict()
    for key in instructions_aliases.keys():
        alias = str(instructions_aliases[key]["aliases"][0])
        attribute_check = instructions_aliases[key]["attributes"]
        alias_dump = True
        for alias_attribute in attribute_check:
            if alias_attribute in config_variables["IgnoredAttrib"]:
                alias_dump = False
                break
        if alias_dump is True:
            for attribute in instructions[alias]["attributes"]:
                if len(extensions_list) > 0:
                    if attribute in extensions_list:
                        if (
                            "LLVMExt" + str(attribute).capitalize()
                            in config_variables.keys()
                        ):
                            extension = "LLVMExt" + str(attribute).capitalize()
                            if (
                                config_variables[extension] + "Extension"
                                in config_variables.keys()
                            ):
                                file_extension = config_variables[
                                    config_variables[extension] + "Extension"
                                ]
                                generated = False
                                if "_gen" in config_variables["InstructionInfoFile"]:
                                    generated = True
                                if generated is True:
                                    new_file_name = (
                                        config_variables["InstructionInfoFile"]
                                        .replace("_gen", "")
                                        .replace(".td", file_extension + "_gen" + ".td")
                                    )
                                else:
                                    new_file_name = config_variables[
                                        "InstructionInfoFile"
                                    ].replace(".td", file_extension + ".td")
                                if os.getcwd().endswith("tools") is True:
                                    new_file_name = "." + new_file_name
                                f = open(new_file_name, "a")
                                if new_file_name not in section_delimiter_dump.keys():
                                    f.write(section_delimiter)
                                    section_delimiter_dump[new_file_name] = True
                                f.write(generate_instruction_alias(key))
                                f.write("\n")
                                if generate_pattern_for_instructions(key) != "":
                                    f.write(generate_pattern_for_instructions(key))
                                    f.write("\n")
                                f.close()
                            else:
                                f = open(file_name, "a")
                                if file_name not in section_delimiter_dump.keys():
                                    f.write(section_delimiter)
                                    section_delimiter_dump[file_name] = True
                                f.write(generate_instruction_alias(key))
                                f.write("\n")
                                if generate_pattern_for_instructions(key) != "":
                                    f.write(generate_pattern_for_instructions(key))
                                    f.write("\n")
                                f.close()
                else:
                    if (
                        "LLVMExt" + str(attribute).capitalize()
                        in config_variables.keys()
                    ):
                        extension = "LLVMExt" + str(attribute).capitalize()
                        if (
                            config_variables[extension] + "Extension"
                            in config_variables.keys()
                        ):
                            file_extension = config_variables[
                                config_variables[extension] + "Extension"
                            ]
                            generated = False
                            if "_gen" in config_variables["InstructionInfoFile"]:
                                generated = True
                            if generated is True:
                                new_file_name = (
                                    config_variables["InstructionInfoFile"]
                                    .replace("_gen", "")
                                    .replace(".td", file_extension + "_gen" + ".td")
                                )
                            else:
                                new_file_name = config_variables[
                                    "InstructionInfoFile"
                                ].replace(".td", file_extension + ".td")
                            if os.getcwd().endswith("tools") is True:
                                new_file_name = "." + new_file_name
                            f = open(new_file_name, "a")
                            if new_file_name not in section_delimiter_dump.keys():
                                f.write(section_delimiter)
                                section_delimiter_dump[new_file_name] = True
                            f.write(generate_instruction_alias(key))
                            f.write("\n")
                            if generate_pattern_for_instructions(key) != "":
                                f.write(generate_pattern_for_instructions(key))
                                f.write("\n")
                            f.close()
                        else:
                            f = open(file_name, "a")
                            if file_name not in section_delimiter_dump.keys():
                                f.write(section_delimiter)
                                section_delimiter_dump[file_name] = True
                            f.write(generate_instruction_alias(key))
                            f.write("\n")
                            if generate_pattern_for_instructions(key) != "":
                                f.write(generate_pattern_for_instructions(key))
                                f.write("\n")
                            f.close()


## A function which generates calling convention information required by LLVM
#
# @param file_name The parameter indicates the file in which the content will be written
# @return This function will return calling convention information
def write_calling_convention(file_name):
    config_variables = config.config_environment(config_file, llvm_config)
    f = open(file_name, "a")
    content = ""
    statement = ""
    registers_parsed = adl_parser.parse_adl(config_variables["ADLName"])
    register_allocation_ref = ""
    if "CallingConventionAllocationOrder" in config_variables.keys():
        calling_convention = config_variables["CallingConventionAllocationOrder"]
        calling_convention_excluded = config_variables[
            "CallingConventionAllocationExcluded"
        ]
        for element in calling_convention:
            for key in element.keys():
                statement = "def " + key + " : " + "CalleeSavedRegs <(\n"
                content = "\tadd "
                register_list = list()
                for register in element[key]:
                    register_allocation_ref = config_variables[key + "_" + "Ref"]
                    if register_allocation_ref in registers_parsed.keys():
                        for reg_cc in registers_parsed[
                            register_allocation_ref
                        ].calling_convention.keys():
                            if (
                                register
                                in registers_parsed[
                                    register_allocation_ref
                                ].calling_convention[reg_cc]
                            ):
                                if reg_cc not in register_list:
                                    register_list.append(reg_cc)
                index = 0
                for elem_reg in register_list:
                    if index % 5 == 0 and index > 0:
                        index += 1
                        content += "\n"
                        if content.endswith("\n"):
                            content = content + "\t"
                        content += elem_reg + ", "
                    else:
                        index += 1
                        content += elem_reg + ", "
            f.write(statement + content.strip(", ") + "\n)>;")
            f.write("\n\n")
        content = ""
        statement = ""
        for element in calling_convention_excluded:
            for key in element.keys():
                statement = "def " + key + " : " + "CalleeSavedRegs <(\n"
                content = "\tadd "
                register_list = list()
                register_allocation_ref = config_variables[key + "_" + "Ref"]
                if register_allocation_ref in registers_parsed.keys():
                    for reg_cc in registers_parsed[
                        register_allocation_ref
                    ].calling_convention.keys():
                        for register in registers_parsed[
                            register_allocation_ref
                        ].calling_convention[reg_cc]:
                            if register not in element[key]:
                                if reg_cc not in register_list:
                                    register_list.append(reg_cc)
                index = 0
                for elem_reg in register_list:
                    if index % 5 == 0 and index > 0:
                        index += 1
                        content += "\n"
                        if content.endswith("\n"):
                            content = content + "\t"
                        content += elem_reg + ", "
                    else:
                        index += 1
                        content += elem_reg + ", "
            f.write(statement + content.strip(", ") + "\n)>;")
            f.write("\n\n")
    f.close()


## This function will generate relocations definitions
#
# @param file_name This parameter indicates the file in which the content will be written
# @return The function will return the content generated as strings
def generate_relocation_define(file_name):
    f = open(file_name, "a")
    config_variables = config.config_environment(config_file, llvm_config)
    relocations = adl_parser.parse_relocations(config_variables["ADLName"])
    statement = ""
    for key in relocations.keys():
        statement += (
            "ELF_RELOC(" + key.upper() + ", " + relocations[key]["value"] + ")\n"
        )
    f.write(statement)
    f.close()


## This function will generate intrinsics for the instructions defined in the ADL file parsed
#
# @param file_name This parameter indicates the file in which the instrinsics will be generated
# @param extensions_list This list contains the extensions for which the instrinsics will be generated. If empty, all extensions are used.
# @return This function will return the definitions for intrinsics
def generate_intrinsics(file_name, extensions_list):
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[
        0
    ]
    immediates = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    immediates_imm = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
    aliases = adl_parser.parse_instructions_aliases_from_adl(
        config_variables["ADLName"]
    )
    for key in instructions.keys():
        if key not in aliases.keys():
            statement = ""
            if "intrinsic" in instructions[key].keys():
                statement = (
                    "def " + instructions[key]["intrinsic"].replace(".", "_") + " : "
                )
            operands_list = list()
            operand_type = list()
            instrinsic_attributes = list()
            intrinsic_sideEffect = False
            intrinsic_noMem = False
            generate_builtin = False
            if "intrinsic_args" in instructions[key].keys():
                if "intrinsic_type" in instructions[key].keys():
                    for imm_key in instructions[key]["intrinsic_args"]:
                        function_checked = False
                        for elem in instructions[key]["inputs"]:
                            if imm_key in elem:
                                function_checked = True
                                operands_list.append(
                                    instructions[key]["intrinsic_type"][imm_key][0]
                                )
                        for elem in instructions[key]["outputs"]:
                            if imm_key in elem:
                                function_checked = True
                                operand_type.append(
                                    instructions[key]["intrinsic_type"][imm_key][0]
                                )
                        if function_checked is False:
                            operands_list.append(
                                instructions[key]["intrinsic_type"][imm_key][0]
                            )
                    if (
                        config_variables["sideEffectAttribute"]
                        in instructions[key]["attributes"]
                    ):
                        intrinsic_sideEffect = True
                    elif (
                        config_variables["sideEffectAttributeSpecific"]
                        in instructions[key]["attributes"]
                    ):
                        intrinsic_sideEffect = True
                    elif (
                        config_variables["memorySynchronizationInstruction"]
                        in instructions[key]["attributes"]
                    ):
                        intrinsic_sideEffect = True
                    elif (
                        "sideEffectInstrfield" in config_variables.keys()
                        and config_variables["sideEffectInstrfield"]
                        in instructions[key]["fields"][0].keys()
                    ):
                        intrinsic_sideEffect = True
            if "load" or "store" not in instructions[key]["attributes"]:
                if "input_mems" and "output_mems" in instructions[key].keys():
                    intrinsic_noMem = False
                else:
                    intrinsic_noMem = True
            if intrinsic_noMem is True:
                instrinsic_attributes.append("IntrNoMem")
            else:
                instrinsic_attributes.append("IntrArgMemOnly")
            if intrinsic_sideEffect is True:
                instrinsic_attributes.append("IntrHasSideEffects")
            if statement != "":
                name_convention = "__builtin_riscv_" + key.lower().replace(".", "_")
                statement += (
                    "Intrinsic<"
                    + str(operand_type).replace("'", "")
                    + ", "
                    + str(operands_list).replace("'", "")
                    + ", "
                    + str(instrinsic_attributes).replace("'", "")
                    + ">"
                    + ", "
                    + "ClangBuiltin<"
                    + '"'
                    + name_convention
                    + '"'
                    + ">;"
                )
                extension = ""
                for element in instructions[key]["attributes"]:
                    extension_checked = False
                    if len(extensions_list) > 0:
                        if element not in extensions_list:
                            extension_checked = True
                            break
                        else:
                            if (
                                "LLVMExt" + element.capitalize()
                                in config_variables.keys()
                            ):
                                file_name_extension = config_variables[
                                    "LLVMExt" + element.capitalize()
                                ]
                                if (
                                    file_name_extension + "Extension"
                                    in config_variables.keys()
                                ):
                                    extension = config_variables[
                                        file_name_extension + "Extension"
                                    ]
                                    break
                                elif (
                                    "HasStd" + element.capitalize() + "Extension"
                                    in config_variables.keys()
                                ):
                                    extension = config_variables[
                                        "HasStd" + element.capitalize() + "Extension"
                                    ]
                                    break
                    else:
                        if "LLVMExt" + element.capitalize() in config_variables.keys():
                            file_name_extension = config_variables[
                                "LLVMExt" + element.capitalize()
                            ]
                            if (
                                file_name_extension + "Extension"
                                in config_variables.keys()
                            ):
                                extension = config_variables[
                                    file_name_extension + "Extension"
                                ]
                                break
                            elif (
                                "HasStd" + element.capitalize() + "Extension"
                                in config_variables.keys()
                            ):
                                extension = config_variables[
                                    "HasStd" + element.capitalize() + "Extension"
                                ]
                                break
                file_name_cpy = file_name
                generated = False
                if "_gen" in file_name_cpy:
                    generated = True
                    file_name_cpy = file_name_cpy.replace("_gen", "")
                if extension != "":
                    if generated is True:
                        file_name_cpy = (
                            file_name_cpy.replace(".td", "")
                            + extension
                            + "_gen"
                            + ".td"
                        )
                    else:
                        file_name_cpy = (
                            file_name_cpy.replace(".td", "") + extension + ".td"
                        )
                if file_name_cpy != file_name:
                    if file_name_cpy not in os.listdir("."):
                        legalDisclaimer.get_copyright(file_name_cpy)
                        legalDisclaimer.get_generated_file(file_name_cpy)
                if extension_checked == False:
                    list_dir = list()
                    for fname in os.listdir("."):
                        list_dir.append(fname)
                    if "tools" not in list_dir:
                        if file_name_cpy.startswith("./"):
                            file_name_cpy = "." + file_name_cpy
                    f = open(file_name_cpy, "a")
                    f.write(statement)
                    f.write("\n")
                    f.close()
    for alias in aliases.keys():
        statement = ""
        if "intrinsic" in aliases[alias].keys():
            statement = "def " + aliases[alias]["intrinsic"] + " : "
        operands_list = list()
        operand_type = list()
        instrinsic_attributes = list()
        intrinsic_sideEffect = False
        intrinsic_noMem = False
        generate_builtin = False
        if "intrinsic_args" in aliases[alias].keys():
            if "intrinsic_type" in aliases[alias].keys():
                for imm_key in aliases[alias]["intrinsic_args"]:
                    function_checked = False
                    for elem in aliases[alias]["inputs"]:
                        if imm_key in elem:
                            operands_list.append(
                                aliases[alias]["intrinsic_type"][imm_key][0]
                            )
                    for elem in aliases[alias]["outputs"]:
                        if imm_key in elem:
                            operand_type.append(
                                aliases[alias]["intrinsic_type"][imm_key][0]
                            )
                    if function_checked is False:
                        operands_list.append(
                            aliases[alias]["intrinsic_type"][imm_key][0]
                        )
                if (
                    config_variables["sideEffectAttribute"]
                    in aliases[alias]["attributes"]
                ):
                    intrinsic_sideEffect = True
                elif (
                    config_variables["sideEffectAttributeSpecific"]
                    in aliases[alias]["attributes"]
                ):
                    intrinsic_sideEffect = True
                elif (
                    config_variables["memorySynchronizationInstruction"]
                    in aliases[alias]["attributes"]
                ):
                    intrinsic_sideEffect = True
                elif (
                    config_variables["sideEffectInstrfield"]
                    in aliases[alias]["fields"][0].keys()
                    or config_variables["sideEffectInstrfield"]
                    in aliases[alias]["syntax"]
                ):
                    intrinsic_sideEffect = True
        if "load" or "store" not in instructions[key]["attributes"]:
            if "input_mems" and "output_mems" in instructions[key].keys():
                intrinsic_noMem = False
            else:
                intrinsic_noMem = True
        if intrinsic_noMem is True:
            instrinsic_attributes.append("IntrNoMem")
        if intrinsic_sideEffect is True:
            instrinsic_attributes.append("IntrHasSideEffects")
        if statement != "":
            name_convention = "__builtin_riscv_" + key.lower()
            statement += (
                "Intrinsic<"
                + str(operand_type).replace("'", "")
                + ", "
                + str(operands_list).replace("'", "")
                + ", "
                + str(instrinsic_attributes).replace("'", "")
                + ">"
                + ", "
                + "ClangBuiltin<"
                + '"'
                + name_convention
                + '"'
                + ">;"
            )
            extension = ""
            for element in instructions[key]["attributes"]:
                extension_checked = False
                if len(extensions_list) > 0:
                    if element not in extensions_list:
                        extension_checked = True
                        break
                    else:
                        if "LLVMExt" + element.capitalize() in config_variables.keys():
                            file_name_extension = config_variables[
                                "LLVMExt" + element.capitalize()
                            ]
                            if (
                                file_name_extension + "Extension"
                                in config_variables.keys()
                            ):
                                extension = config_variables[
                                    file_name_extension + "Extension"
                                ]
                                break
                            elif (
                                "HasStd" + element.capitalize() + "Extension"
                                in config_variables.keys()
                            ):
                                extension = config_variables[
                                    "HasStd" + element.capitalize() + "Extension"
                                ]
                                break
                else:
                    if "LLVMExt" + element.capitalize() in config_variables.keys():
                        file_name_extension = config_variables[
                            "LLVMExt" + element.capitalize()
                        ]
                        if file_name_extension + "Extension" in config_variables.keys():
                            extension = config_variables[
                                file_name_extension + "Extension"
                            ]
                            break
                        elif (
                            "HasStd" + element.capitalize() + "Extension"
                            in config_variables.keys()
                        ):
                            extension = config_variables[
                                "HasStd" + element.capitalize() + "Extension"
                            ]
                            break
            generated = False
            if extension != "":
                file_name_cpy = file_name
                if "_gen" in file_name_cpy:
                    file_name_cpy = file_name_cpy.replace("_gen", "")
                    generated = True
                if generated is True:
                    file_name_cpy = (
                        file_name_cpy.replace(".td", "") + extension + "_gen" + ".td"
                    )
                else:
                    file_name_cpy = file_name_cpy.replace(".td", "") + extension + ".td"
            if file_name_cpy != file_name:
                if file_name_cpy not in os.listdir("."):
                    legalDisclaimer.get_copyright(file_name_cpy)
                    legalDisclaimer.get_generated_file(file_name_cpy)
            if extension_checked == False:
                f = open(file_name, "a")
                f.write(statement)
                f.write("\n")
                f.close()


## This function will generate the accumulator register definition
#
# @param file_name This parameter indicates the name for the in which the content will be written
# @param abi_name This parameter indicates ABI information needed for LLVM register definition
# @param register_class This parameter indicates what register class the accumulator belongs to
# @param namespace This parameter indicates the namespace needed for LLVM register definition
# @return The function will return the content as string
def generate_accumulator_register(file_name, abi_name, register_class, namespace):
    config_variables = config.config_environment(config_file, llvm_config)
    registers = adl_parser.parse_adl(config_variables["ADLName"])
    define = ""
    content = ""
    f = open(file_name, "a")
    for key in registers.keys():
        if "accumulator" in registers[key].attributes:
            let_name = "let RegAltNameIndices = [" + abi_name + "] in {\n"
            for index in range(len(registers[key].entries)):
                define += (
                    "\tdef "
                    + registers[key].syntax[index]
                    + " : "
                    + register_class
                    + ", "
                    + "<"
                    + registers[key].entries[index]
                    + ", "
                    + '"'
                    + str(registers[key].syntax[index]).lower()
                    + '"'
                    + ", "
                    + '["'
                    + str(registers[key].syntax[index]).lower()
                    + '"]'
                    + ", "
                    + "DwarfRegNum<["
                    + registers[key].debug
                    + "]>;"
                )
                content += "add" + " " + registers[key].syntax[index]
            if content != "":
                content += "\n\t)"
            statement = (
                "def "
                + key
                + " : "
                + "RegisterClass<"
                + '"'
                + namespace
                + '"'
                + ", "
                + "["
                + config_variables["XLenVT_key"]
                + "]"
                + ", "
                + registers[key].width
                + ", (\n"
                + "\t"
                + content
                + "> {\n"
            )
            statement += "\tlet Size = " + registers[key].size + ";" + "\n}"
            if define != "":
                define += "\n}"
            f.write(statement)
            f.write("\n\n")
            f.write(let_name + define)
    f.close()


## This function will generate a pattern for a given instrunction
#
# @param instruction_key This parameter indicates the instruction for which the pattern is generated
# @return The function will return the pattern for the instruction given as string
def generate_pattern_for_instructions(instruction_key):
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[
        0
    ]
    instrfields = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    for key in instructions.keys():
        intrinsic_outputs = list()
        intrinsic_inputs = list()
        for element in instructions[key]["outputs"]:
            if "(" in element:
                new_element = element.split(")")[0]
                new_element += ")"
                intrinsic_outputs.append(new_element)
        for element in instructions[key]["inputs"]:
            if "(" in element:
                new_element = element.split(")")[0]
                new_element += ")"
                intrinsic_inputs.append(new_element)
        statement = ""
        if key == instruction_key:
            syntax = ""
            arguments = ""
            if "intrinsic" in instructions[key].keys():
                for element in instructions[key]["syntax"][2:]:
                    if element != "":
                        syntax += "$" + element + ", "
                ref = instrfields[instructions[key]["syntax"][1]]["ref"]
                if (
                    ref + "(" + instructions[key]["syntax"][1] + ")"
                    in intrinsic_outputs
                    and ref + "(" + instructions[key]["syntax"][1] + ")"
                    in intrinsic_inputs
                ):
                    if instructions[key]["syntax"][1] != "":
                        syntax_cpy = syntax
                        syntax = "$" + instructions[key]["syntax"][1] + ", "
                        syntax += syntax_cpy
                for argument in instructions[key]["intrinsic_args"]:
                    if argument in intrinsic_inputs and argument in intrinsic_outputs:
                        argument_list = argument.split("(")
                        if len(argument_list) > 1:
                            if argument_list[1].replace(")", "") in instrfields.keys():
                                if (
                                    argument_list[0]
                                    == instrfields[argument_list[1].replace(")", "")][
                                        "ref"
                                    ]
                                ):
                                    arguments += argument_list[0]
                                    arguments += (
                                        ":$" + argument_list[1].replace(")", "") + ", "
                                    )

                            else:
                                if (
                                    argument_list[1].replace(")", "")
                                    in config_variables.keys()
                                ):
                                    if (
                                        '"AliasImmClass"'
                                        in config_variables[
                                            argument_list[1].replace(")", "")
                                        ].keys()
                                    ):
                                        arguments += (
                                            config_variables[
                                                argument_list[1].replace(")", "")
                                            ]['"AliasImmClass"'].replace('"', "")
                                            + ":$"
                                            + argument_list[1].replace(")", "")
                                            + ", "
                                        )

                        else:
                            if argument_list[0] in config_variables.keys():
                                if (
                                    '"AliasImmClass"'
                                    in config_variables[argument_list[0]].keys()
                                ):
                                    arguments += (
                                        config_variables[argument_list[0]][
                                            '"AliasImmClass"'
                                        ].replace('"', "")
                                        + ":$"
                                        + argument_list[0]
                                        + ", "
                                    )
                    else:
                        if argument not in intrinsic_outputs:
                            argument_list = argument.split("(")
                            if len(argument_list) > 1:
                                if (
                                    argument_list[1].replace(")", "")
                                    in instrfields.keys()
                                ):
                                    if (
                                        argument_list[0]
                                        == instrfields[
                                            argument_list[1].replace(")", "")
                                        ]["ref"]
                                    ):
                                        arguments += argument_list[0]
                                        arguments += (
                                            ":$"
                                            + argument_list[1].replace(")", "")
                                            + ", "
                                        )

                                else:
                                    if (
                                        argument_list[1].replace(")", "")
                                        in config_variables.keys()
                                    ):
                                        if (
                                            '"AliasImmClass"'
                                            in config_variables[
                                                argument_list[1].replace(")", "")
                                            ].keys()
                                        ):
                                            arguments += (
                                                config_variables[
                                                    argument_list[1].replace(")", "")
                                                ]['"AliasImmClass"'].replace('"', "")
                                                + ":$"
                                                + argument_list[1].replace(")", "")
                                                + ", "
                                            )

                            else:
                                if argument_list[0] in config_variables.keys():
                                    if (
                                        '"AliasImmClass"'
                                        in config_variables[argument_list[0]].keys()
                                    ):
                                        arguments += (
                                            config_variables[argument_list[0]][
                                                '"AliasImmClass"'
                                            ].replace('"', "")
                                            + ":$"
                                            + argument_list[0]
                                            + ", "
                                        )
                if key != "wfi":
                    for index in range(len(instructions[instruction_key]["outputs"])):
                        if "(" in str(instructions[instruction_key]["outputs"][index]):
                            if (
                                str(instructions[instruction_key]["outputs"][index])
                                .split("(")[1]
                                .endswith(")")
                            ):
                                instrfield_destination = (
                                    str(instructions[instruction_key]["outputs"][index])
                                    .split("(")[1]
                                    .replace(")", "")
                                )
                                break
                            else:
                                instrfield_destination = (
                                    str(instructions[instruction_key]["outputs"][index])
                                    .split("(")[1]
                                    .split(")")[0]
                                )
                                break
                else:
                    instrfield_destination = ""
                return_type = ""
                if instrfield_destination in instrfields.keys():
                    return_type = "i" + str(
                        2 ** int(instrfields[instrfield_destination]["width"])
                    )
                    extension = ""
                for element in instructions[key]["attributes"]:
                    if "LLVMExt" + element.capitalize() in config_variables.keys():
                        file_name_extension = config_variables[
                            "LLVMExt" + element.capitalize()
                        ]
                        if file_name_extension + "Extension" in config_variables.keys():
                            extension = config_variables[
                                file_name_extension + "Extension"
                            ]
                            break
                        elif (
                            "HasStd" + element.capitalize() + "Extension"
                            in config_variables.keys()
                        ):
                            extension = config_variables[
                                "HasStd" + element.capitalize() + "Extension"
                            ]
                            break
                if syntax == "":
                    if arguments != "":
                        arguments = " " + arguments
                    if extension in config_variables["ExtensionPrefixed"]:
                        statement = (
                            "def : "
                            + "Pat<("
                            + return_type
                            + " "
                            + "("
                            + instructions[key]["intrinsic"].replace(".", "_")
                            + arguments.rstrip(", ")
                            + ")), ("
                            + extension.upper()
                            + "_"
                            + key.upper().replace(".", "_")
                            + ")>;"
                        )
                    else:
                        statement = (
                            "def : "
                            + "Pat<("
                            + return_type
                            + " "
                            + "("
                            + instructions[key]["intrinsic"].replace(".", "_")
                            + arguments.rstrip(", ")
                            + ")), ("
                            + key.upper().replace(".", "_")
                            + ")>;"
                        )
                else:
                    if arguments != "":
                        arguments = " " + arguments
                    if (
                        "ExtensionPrefixed" in config_variables.keys()
                        and extension in config_variables["ExtensionPrefixed"]
                    ):
                        statement = (
                            "def : "
                            + "Pat<("
                            + return_type
                            + " "
                            + "("
                            + instructions[key]["intrinsic"].replace(".", "_")
                            + arguments.rstrip(", ")
                            + ")), ("
                            + extension.upper()
                            + "_"
                            + key.upper().replace(".", "_")
                            + " "
                            + syntax.rstrip(", ")
                            + ")>;"
                        )
                    else:
                        statement = (
                            "def : "
                            + "Pat<("
                            + return_type
                            + " "
                            + "("
                            + instructions[key]["intrinsic"].replace(".", "_")
                            + arguments.rstrip(", ")
                            + ")), ("
                            + key.upper().replace(".", "_")
                            + " "
                            + syntax.rstrip(", ")
                            + ")>;"
                        )
            return statement


## This function will generate builtin definitions and also a header for defining name convention for builtin definitions
#
# @param file_name This parameter indicates the file which will contain builtin definitions
# @param header_name This parameter indicates the header which will be included for activating naming convention
# @param extensions_list This parameter indicates is a list containing the extensions that the user wants to use. If empty, all extensions are used
# @return The function will write the content for builtin definitions in 2 files as presented before
def generate_builtin(file_name, header_name, extensions_list):
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[
        0
    ]
    instrfields = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    for key in instructions.keys():
        intrinsic_outputs = list()
        intrinsic_inputs = list()
        for element in instructions[key]["outputs"]:
            new_element = element.split(")")[0]
            new_element += ")"
            intrinsic_outputs.append(new_element)
        for element in instructions[key]["inputs"]:
            new_element = element.split(")")[0]
            new_element += ")"
            intrinsic_inputs.append(new_element)
        operand_type = ""
        name_convention = ""
        customize_name = ""
        macro_info = "nc"
        statement = "TARGET_BUILTIN("
        if "generate_builtin" in instructions[key].keys():
            customize_name = instructions[key]["generate_builtin"]
        if "intrinsic" in instructions[key].keys():
            name_convention = "__builtin_riscv_" + key.lower().replace(".", "_")
            statement += name_convention + ", "
        else:
            continue
        if "intrinsic_args" in instructions[key].keys():
            for element in instructions[key]["intrinsic_args"]:
                if "(" in element:
                    register = element.split("(")[1].replace(")", "")
                    if register in instrfields.keys():
                        if "signed" in instrfields[register].keys():
                            operand_type += "Si"
                            if (
                                element in intrinsic_inputs
                                and element in intrinsic_outputs
                            ):
                                operand_type += "Si"
                        else:
                            operand_type += "Ui"
                            if (
                                element in intrinsic_inputs
                                and element in intrinsic_outputs
                            ):
                                operand_type += "Ui"
        else:
            continue
        statement += '"' + operand_type + '"' + ", "
        statement += '"' + macro_info + '"' + ", "
        extension = ""
        naming_definition = ""
        character = "a"
        index = 0
        list_args = list()
        list_args_naming_conv = list()
        if customize_name != "":
            for argument in instructions[key]["intrinsic_args"]:
                if argument in intrinsic_inputs and argument in intrinsic_outputs:
                    list_args.append(chr(ord(character) + index))
                    list_args_naming_conv.append(
                        "(" + chr(ord(character) + index) + ")"
                    )
                    index += 1
                else:
                    if argument not in intrinsic_outputs:
                        list_args.append(chr(ord(character) + index))
                        list_args_naming_conv.append(
                            "(" + chr(ord(character) + index) + ")"
                        )
                        index += 1
            naming_definition = (
                "#define "
                + customize_name.replace(".", "_")
                + str(list_args).replace("[", "(").replace("]", ")").replace("'", "")
                + " "
                + name_convention
                + str(list_args_naming_conv)
                .replace("[", "(")
                .replace("]", ")")
                .replace("'", "")
            )
        for element in instructions[key]["attributes"]:
            extension_checked = False
            if len(extensions_list) != 0 and element not in extensions_list:
                extension_checked = True
                break
            else:
                if "LLVMExt" + element.capitalize() in config_variables.keys():
                    file_name_extension = config_variables[
                        "LLVMExt" + element.capitalize()
                    ]
                    if file_name_extension + "Extension" in config_variables.keys():
                        extension = config_variables[file_name_extension + "Extension"]
                        break
                    elif (
                        "HasStd" + element.capitalize() + "Extension"
                        in config_variables.keys()
                    ):
                        extension = config_variables[
                            "HasStd" + element.capitalize() + "Extension"
                        ]
                        break
        if extension != "":
            if extension_checked is False:
                statement += '"' + extension.lower() + '"' + ")"
                file_name_cpy = file_name
                file_name_cpy = file_name_cpy.replace(".def", "")
                file_name_cpy += extension + ".def"
                header_name_cpy = header_name
                header_name_cpy = header_name_cpy.replace(".h", "")
                header_name_cpy += extension + ".h"
                if file_name_cpy != file_name:
                    if file_name_cpy not in os.listdir("."):
                        legalDisclaimer.get_copyright(file_name_cpy)
                        legalDisclaimer.get_generated_file(file_name_cpy)
                if header_name_cpy != header_name:
                    if header_name_cpy not in os.listdir("."):
                        legalDisclaimer.get_copyright(header_name_cpy)
                        legalDisclaimer.get_generated_file(header_name_cpy)
                list_dir = list()
                for fname in os.listdir("."):
                    list_dir.append(fname)
                if "tools" not in list_dir:
                    if file_name_cpy.startswith("./"):
                        file_name_cpy = "." + file_name_cpy
                f = open(file_name_cpy, "a")
                f.write(statement)
                f.write("\n")
                f.close()
                list_dir = list()
                for fname in os.listdir("."):
                    list_dir.append(fname)
                if "tools" not in list_dir:
                    if header_name_cpy.startswith("./"):
                        header_name_cpy = "." + header_name_cpy
                if naming_definition != "":
                    g = open(header_name_cpy, "a")
                    g.write(naming_definition)
                    g.write("\n")
                    g.close()


## This function will generate intrinsic tests for verifying and validating intrinsic usage
#
# @return This function will return a folder containing a test for each intrinsic generated
def generate_intrinsic_tests():
    config_variables = config.config_environment(config_file, llvm_config)
    tree = ET.parse(config_variables["ADLName"])
    root = tree.getroot()
    mattrib = ""
    architecture = ""
    attributes = ""
    for cores in root.iter("cores"):
        for asm_config in cores.iter("asm_config"):
            architecture = asm_config.find("arch").find("str").text
            attributes = asm_config.find("attributes").find("str").text
            mattrib = asm_config.find("mattrib").find("str").text
    if mattrib is not None:
        mattrib = mattrib.replace("+", "").replace(",", "")
        mattrib = "rv32i" + mattrib
    else:
        mattrib = ""
    architecture = architecture
    command1 = (
        "// RUN: %clang --target="
        + architecture
        + " -march="
        + mattrib
        + " %s -S -o %s.s\n"
    )
    command2 = "// RUN: cat %s.s | %filecheck %s\n\n"
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[
        0
    ]
    folder_name = config_variables["TestIntrinsics"]
    list_dir = list()
    legal_disclaimer = """// Copyright 2024 NXP
// SPDX-License-Identifier: BSD-2-Clause"""
    for fname in os.listdir("."):
        list_dir.append(fname)
    if "tools" not in list_dir:
        config_variables["TestIntrinsics"] = config_variables["TestIntrinsics"].replace(
            "/tools", ""
        )
    folder = folder_name.split("/")[0]
    if folder.isalpha() == False:
        folder_name.split("/")[1]
    if 'tools' in list_dir:
        list_dir_aux = list()
        folder_name += "/tests"
        for fname in os.listdir(config_variables["TestIntrinsics"]):
            list_dir_aux.append(fname)
        if 'tests' in list_dir_aux:
            shutil.rmtree(config_variables["TestIntrinsics"] + '/tests')
        os.mkdir(folder_name)
    else:
        list_dir_aux = list()
        folder_name += "/tests"
        for fname in os.listdir(config_variables["TestIntrinsics"]):
            list_dir_aux.append(fname)
        if 'tests' in list_dir_aux:
            shutil.rmtree(config_variables["TestIntrinsics"] + '/tests')
        os.mkdir("." + folder_name)
    for key in instructions.keys():
        character = "int *values_set"
        character2 = "*values_set"
        character3 = "a{{[0-9]}}"
        list_args = list()
        list_args2 = list()
        list_args3 = list()
        intrinsic_outputs = list()
        intrinsic_inputs = list()
        for element in instructions[key]["outputs"]:
            new_element = element.split(")")[0]
            new_element += ")"
            intrinsic_outputs.append(new_element)
        for element in instructions[key]["inputs"]:
            new_element = element.split(")")[0]
            new_element += ")"
            intrinsic_inputs.append(new_element)
        index = 1
        for argument in instructions[key]["intrinsic_args"]:
            if argument in intrinsic_inputs and argument in intrinsic_outputs:
                list_args.append(character + str(index))
                list_args2.append(character2 + str(index))
                index += 1
            else:
                if argument not in intrinsic_outputs:
                    list_args.append(character + str(index))
                    list_args2.append(character2 + str(index))
                    index += 1
            list_args3.append(character3)
        command3 = (
            "// CHECK: "
            + key.lower()
            + " "
            + str(list_args3).replace("[", "", 1).replace("'", "")
        )
        command3 = "".join(command3.rsplit("]", 1)) + "\n"
        customize_name = ""
        if "generate_builtin" in instructions[key].keys():
            customize_name = instructions[key]["generate_builtin"]
        if customize_name != "":
            statement = ""
            content = ""
            for element in instructions[key]["attributes"]:
                if "LLVMExt" + element.capitalize() in config_variables.keys():
                    file_name_extension = config_variables[
                        "LLVMExt" + element.capitalize()
                    ]
                    if file_name_extension + "Extension" in config_variables.keys():
                        extension = config_variables[file_name_extension + "Extension"]
                        break
                    elif (
                        "HasStd" + element.capitalize() + "Extension"
                        in config_variables.keys()
                    ):
                        extension = config_variables[
                            "HasStd" + element.capitalize() + "Extension"
                        ]
                        break
            if extension != "":
                header_name_cpy = config_variables["BuiltinHeader"]
                header_name_cpy = header_name_cpy.replace(".h", "")
                header_name_cpy += extension + ".h"
                include_lib = (
                    "#include " + '"' + header_name_cpy.rsplit("/")[-1] + '"' + "\n\n"
                )
            else:
                include_lib = (
                    "#include "
                    + '"'
                    + config_variables["BuiltinHeader"].rsplit("/")[-1]
                    + '"'
                    + "\n\n"
                )
            array_set1 = "int *values_set1"
            array_set2 = "int *values_set2"
            array_results = "int *results_" + customize_name.replace("__", "").replace(
                ".", "_"
            )
            set1_content = "*values_set1"
            set2_content = "*values_set2"
            results_content = "*results_" + customize_name.replace("__", "").replace(
                ".", "_"
            )
            statement += (
                "void do_"
                + customize_name.replace("__", "").replace(".", "_")
                + "("
                + str(list_args).replace("[", "").replace("]", "").replace("'", "")
                + ", "
                + array_results
                + ") {\n"
            )
            content += (
                "\t"
                + results_content
                + " = "
                + customize_name.replace(".", "_")
                + "("
                + str(list_args2).replace("[", "").replace("]", "").replace("'", "")
                + ");\n"
            )
            content += "}\n"
            file_name = (
                "test_" + customize_name.replace("__", "").replace(".", "_") + ".c"
            )
            if 'tools' not in list_dir:
                folder_name = "." + folder_name
            f = open(folder_name + "/" + file_name, "a")
            f.write(
                legal_disclaimer
                + "\n"
                + include_lib
                + command1
                + command2
                + statement
                + content
                + command3
            )
            f.close()


## This function will generate a register memory operand wrapper required by LLVM 17
#
# @param file_name This parameter indicates the file in which the definitions will be generated
# @return The function will generated the definition mapping the register classes to the corresponding memory operand wrapper
def generate_operand_mem_wrapper_class(file_name):
    content = ""
    content += "class MemOperand<RegisterClass regClass> : RegisterOperand<regClass>{\n"
    content += '\tlet OperandType = "OPERAND_MEMORY";\n'
    content += "}\n"
    definition = ""
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[
        0
    ]
    list_ref = list()
    check_list = list()
    for key in instructions.keys():
        if key in instructions_load_store.keys():
            list_ref = instructions_load_store[key].split(", ")
            for element in list_ref:
                if element.split(":$")[0] in register_references:
                    if "Mem" in element:
                        if element.split(":$")[0] not in check_list:
                            definition += (
                                "def "
                                + element.split(":$")[0]
                                + " : MemOperand<"
                                + element.split(":$")[0].replace("Mem", "")
                                + ">;\n"
                            )
                            check_list.append(element.split(":$")[0])
    list_dir = list()
    for fname in os.listdir("."):
        list_dir.append(fname)
    if "tools" not in list_dir:
        if file_name.startswith("./"):
            file_name = "." + file_name
    f = open(file_name, "a")
    legalDisclaimer.get_copyright(file_name)
    legalDisclaimer.get_generated_file(file_name)
    f.write(content + definition)
    f.close()


## This function will generate register pairs
#
# @param file_name This parameter indicates the file in which the content will be written
# @return The function returns a file containing the definitions for register pairs
def generate_register_pairs(file_name):
    config_variables = config.config_environment(config_file, llvm_config)
    instrfield_data_ref = adl_parser.get_instrfield_offset(config_variables["ADLName"])[
        1
    ]
    calling_convention_order = config_variables["RegisterAllocationOrder"]
    registers = adl_parser.parse_adl(config_variables["ADLName"])
    calling_convention_pairs = dict()
    for register in register_pairs.keys():
        register_width = ""
        register_offset = ""
        calling_convention_ref = ""
        width = ""
        offset = ""
        ref = ""
        for element in register_pairs[register]:
            if element in instrfield_data_ref.keys():
                width = instrfield_data_ref[element]["width"]
                offset = instrfield_data_ref[element]["offset"]
                ref = instrfield_data_ref[element]["ref"]
            if register_width == "":
                register_width = width
            elif register_width != "" and register_width != width:
                print("Instrfields have different width values for same regfile!")
                break
            if register_offset == "":
                register_offset = offset
            elif register_offset != "" and register_offset != offset:
                print("Instrfields have different offset values for same regfile!")
                break
            if calling_convention_ref == "" and element in instrfield_data_ref.keys():
                calling_convention_ref = instrfield_data_ref[element]["ref"]
            elif calling_convention_ref != "" and calling_convention_ref != ref:
                print("Instrfields have different ref values!")
                break
        first = 0
        last = 0
        if register_offset != "":
            first = int(register_offset)
            last = int(register_offset) + (2 ** int(register_width))
        for register_cc in calling_convention_order:
            if calling_convention_ref in register_cc.keys():
                for calling_convention_seq in register_cc[calling_convention_ref]:
                    if registers[calling_convention_ref].calling_convention != {}:
                        index = -1
                        for element in registers[
                            calling_convention_ref
                        ].calling_convention.keys():
                            index += 1
                            if (
                                calling_convention_seq
                                in registers[calling_convention_ref].calling_convention[
                                    element
                                ]
                            ):
                                if register not in calling_convention_pairs.keys():
                                    if index >= first and index < last:
                                        if index % 2 == 0:
                                            list_aux = list()
                                            list_aux.append(element)
                                            calling_convention_pairs[
                                                register
                                            ] = list_aux
                                else:
                                    if index >= first and index < last:
                                        if index % 2 == 0:
                                            list_aux = list()
                                            list_aux.extend(
                                                calling_convention_pairs[register]
                                            )
                                            list_aux.append(element)
                                            calling_convention_pairs[
                                                register
                                            ] = list_aux
    for register in calling_convention_pairs.keys():
        statement = (
            "def "
            + register
            + " : "
            + "RegisterClass<"
            + '"'
            + config_variables["Namespace"]
            + '"'
            + ", "
            + "["
            + config_variables["XLenVT_key"]
            + "]"
            + ", "
            + str(2 ** int(register_width))
            + ", ("
            + "\n"
            + "\t"
        )
        content = "add" + " "
        position = 0
        for element in calling_convention_pairs[register]:
            content += element + "_PD" + ", "
            position += 1
            if position % 4 == 0:
                if position < len(calling_convention_pairs[register]):
                    content += "\n"
                content += "\t"
        content = content.rstrip("\t")
        content = content.rstrip(", ")
        content += "\n\t)> {\n"
        let = "\tlet RegInfos = " + config_variables["XLenRI_key"] + ";\n"
        def_class = statement + content + let + "}"
        comment = "// Register Class " + register + " : Register Pair\n"
        def_class = comment + def_class
        f = open(file_name, "a")
        f.write(def_class)
        f.write("\n\n")
        f.close()
