# Copyright 2023-2025 NXP
# SPDX-License-Identifier: BSD-2-Clause
# @package files
#
# The module which writes information about registers inside ReigsterInfo.td file
import math

import word2number.w2n
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
import random
import operator
import word2number
import pathlib

config_file = "config.txt"
llvm_config = "llvm_config.txt"
list_dir = list()
for fname in os.listdir("."):
    list_dir.append(fname)
config_file = os.path.dirname(__file__).replace("\\", "/") + "/" + "config.txt"
llvm_config = os.path.dirname(__file__).replace("\\", "/") + "/" + "llvm_config.txt"

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

## A dictionary which contains instruction fields for each register class 
reg_instrfields = dict()

## A dictionary which contains values available for instruction fields
instrfields_values = dict()

## A dictionary in which information generated about scheduling is gathered
scheduling_instr_info = dict()

## A dictionary containing scheduling tests structure for each instruction
scheduling_tests_struct = dict()

## A dictionary containing aliases based on the ABI for register classes 
alias_register_dict = dict()

## A dictionary containing instruction encodings used for sail description
instruction_encoding_dict = dict()

## A dictionary containing register usages for each scheduling tests for dependency
sched_app_regs_dep  = dict()

## A dictionary containing register usages for each scheduling tests 
sched_app_regs = dict()

# A dictionary containing special instruction latency and throughput information
aux_scheduling_table_param = dict()

# A global list to store memory operand registers
memory_operands_registers_list = list()

# A global list which store already printed extensions
attributes_list = list()

# A global list which store already printed extensions for intrinsics
attributes_list_intrinsics = list()

# Singleton list for generating operands
singleton_list = list()

# A dict containing instructions registers used
instruction_registers_used_ins = dict()

# A dict containing instructions registers used
instruction_registers_used_outs = dict()

# A dictionary containing a map between a register class and its width
register_classes_width = dict()

## Function for generating let content
#
# @param let_key Key of def method
# @param let_value Value of def method
# @return A string representing the method
def generate_let(let_key, let_value):
    content = "let " + let_key + " = " + let_value + " in \n"
    return content

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
    register_class_used = "RegisterClass"
    config_variables = config.config_environment(config_file, llvm_config)
    registers = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    
    comment = "//Register Class SP : Stack Pointer Register Class.\n"
    class_name = str.upper(class_name)
    class_name = class_name.replace("[", "")
    class_name = class_name.replace("]", "")
    class_name = class_name.replace('"', "")
    sp_key = ""
    for key in register_aliases.keys():
        if "sp" in str(register_aliases[key]):
            sp_key = key
    for key_reg in registers:
        if registers[key_reg].calling_convention is not None and sp_key.upper() in registers[key_reg].calling_convention:
            register_class_used = key_reg.upper() + "RegisterClass"
    if register_class_used == "RegisterClass":
        statement = (
            "def "
            + class_name
            + " : "
            + register_class_used + "<"
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
    else:
        statement = (
            "def "
            + class_name
            + " : "
            + register_class_used + "<("
        )
    content = "add" + " "
    register_classes_width[class_name] = width
    content += sp_key + ")>; {\n"
    let = "\tlet RegInfos = " + config_variables["XLenRI_key"] + ";\n"
    if register_class_used == "RegisterClass":
        def_class = comment + statement + content + let + "}"
    else:
        def_class = comment + statement + content
        def_class = def_class.strip("{\n")
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
def generate_register_class(class_name, register_size, subregs_enabled):
    size = int(math.log2(int(register_size)))
    class_name_list = list()
    if type(class_name) is dict:
        register_class_generated = ""
        for key in class_name.keys():
            if class_name not in class_name_list:
                class_name_list.append(class_name)
                class_statement = "class " + class_name[key] + "<"
                class_defined = ""
                if subregs_enabled is True:
                    parameters = (
                        "bits<"
                        + str(size)
                        + "> Enc, string n, list<Register> subregs, list<string> alt = []> : RegisterWithSubRegs<n, subregs> {\n"
                    )
                else:
                    parameters = (
                        "bits<"
                        + str(size)
                        + "> Enc, string n, list<string> alt = []> : Register<n> {\n"
                    )
                class_content = ""
                riscv_regclass = ""
                child_class = ""
                HWEncoding = "\tlet HWEncoding{" + str(size - 1) + "-" + str(0) + "} = Enc;\n"
                AltNames = "\tlet AltNames = alt;\n"
                class_content = class_content + HWEncoding + AltNames + "}"
                register_class_generated += class_statement + parameters + class_content + "\n"
                config_variables = config.config_environment(config_file, llvm_config)
                registers = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    else:
        class_statement = "class " + class_name + "<"
        class_defined = ""
        if subregs_enabled is True:
            parameters = (
                "bits<"
                + str(size)
                + "> Enc, string n, list<Register> subregs, list<string> alt = []> : RegisterWithSubRegs<n, subregs> {\n"
            )
        else:
            parameters = (
                "bits<"
                + str(size)
                + "> Enc, string n, list<string> alt = []> : Register<n> {\n"
            )
        class_content = ""
        riscv_regclass = ""
        child_class = ""
        HWEncoding = "\tlet HWEncoding{" + str(size - 1) + "-" + str(0) + "} = Enc;\n"
        AltNames = "\tlet AltNames = alt;\n"
        class_content = class_content + HWEncoding + AltNames + "}"
        register_class_generated = class_statement + parameters + class_content
        config_variables = config.config_environment(config_file, llvm_config)
        registers = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    return register_class_generated.rstrip("\n")

## Function to generate extended register classes for LLVM 19 
#
# It returns the definition for the register classes that are needed
def generate_register_classes_extended():
    config_variables = config.config_environment(config_file, llvm_config)
    registers = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    register_class_generated = ""
    riscv_regclass = ""
    class_defined = ""
    if 'RegisterClassChild' in config_variables.keys():
        class_name = config_variables['RegisterClassChild']['RegisterBaseClass']
        class_defined = "class " + config_variables['RegisterClassChild']['RegisterClassName'] + "<list<ValueType> regTypes, int align, dag regList>" + "\n"
        class_defined += " :" + class_name + "<" + "\"" + config_variables['RegisterClassChild']['Namespace'] + "\"" + ", regTypes, align, regList> {\n"
        for key_dict in config_variables['RegisterClassChild'].keys():
            if key_dict != "RegisterBaseClass" and key_dict != "RegisterClassName" and key_dict != "Namespace":
                if config_variables['RegisterClassChild'][key_dict].isdigit():
                    class_defined += "\tint " + key_dict + " = " + config_variables['RegisterClassChild'][key_dict] + ";\n"
                else:
                    class_defined += "\tlet " + key_dict + " = " + config_variables['RegisterClassChild'][key_dict].replace("\'", "") + ";\n"
        class_defined += " }\n"
    if 'RegisterClassChild' in config_variables.keys():
        class_name = config_variables['RegisterClassChild']['RegisterBaseClass']
        for register in registers.keys():
            for reg_class in config_variables['RegisterClassWrapper'].keys():
                if register == config_variables['RegisterClassWrapper'][reg_class]:
                    riscv_regclass += "class " + config_variables['RegisterClassWrapper'][reg_class] + "RegisterClass<dag regList>\n"
                    reg_class_name = re.sub(r'\d+', "", reg_class)
                    riscv_regclass += " :" + reg_class_name + "<[" + config_variables['XLenVT_key'] + ", " +  config_variables['XLenFVT_key'] + ", " + config_variables['XLenVT'] + "], " + registers[config_variables['RegisterClassWrapper'][reg_class].upper()].size + ", " + "regList> {\n"
                    riscv_regclass += "\tlet RegInfos = " + config_variables["XLenRI_key"] + ";\n"
                    riscv_regclass += "}\n"
    register_class_generated += "\n" + class_defined + "\n"
    if riscv_regclass != "":
        other_defs = generate_define("XLenRI", config_variables["XLenRIRegInfo"]) + "\n"
        other_defs += generate_define("XLenVT", config_variables["XLenVTValueType"]) + "\n"
        if other_defs not in register_class_generated:
            register_class_generated += other_defs
    register_class_generated += "\n" + riscv_regclass  + "\n"
    return register_class_generated
    

## Function for generating the GPR register file
#
# @param name Define abi
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
    let_name = ""
    config_variables = config.config_environment(config_file, llvm_config)
    if 'RegisterClassDisabledABI' in config_variables.keys():
        if reg_class.upper() not in config_variables['RegisterClassDisabledABI']:
            let_name = "let RegAltNameIndices = [" + name + "] in {\n"
    else:
        let_name = "let RegAltNameIndices = [" + name + "] in {\n"
    additional_register_classes = dict()
    subregs_def = ""
    registers_subregs = adl_parser.parse_registers_subregs(config_variables["ADLName"])
    list_subregs_alias = list()
    list_subregs = list()
    let_subregs = ""
    if "fields" in registers_subregs[reg_class.upper()].keys():
        fields = registers_subregs[reg_class.upper()]["fields"]
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
    instrfields_excluded_list = list()
    instrfields = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    for instrfield in instrfields:
        if 'ref' in instrfields[instrfield].keys():
            if instrfields[instrfield]['ref'] == reg_class.upper():
                if str(2 ** int(instrfields[instrfield]['width'])) != config_variables['LLVMRegBasicWidth']:
                    if int(instrfields[instrfield]['offset']) > 0:
                        index = 0
                        while index < int(instrfields[instrfield]['offset']):
                            if prefix.upper() + str(int(instrfields[instrfield]['offset']) + index) not in instrfields_excluded_list:
                                instrfields_excluded_list.append(prefix.upper() + str(int(instrfields[instrfield]['offset']) + index))
                            index += 1
    registers_classes = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    for i in range(size):
        calling_convention_name = ""
        cost_per_use = ""
        if dwarf_index != "":
            dwarf_index = int(dwarf_index)
        define_register = "def " + str.upper(prefix) + str(i) + " : "
        if str.upper(prefix) + str(i) in registers_classes[reg_class.upper()].calling_convention.keys():
            cc_value = registers_classes[reg_class.upper()].calling_convention[str.upper(prefix) + str(i)]
            for register_class in config_variables['RegisterAllocationOrder'].keys():
                if reg_class.upper() == register_class:
                    for cc_element in config_variables['RegisterAllocationOrder'][reg_class.upper()]:
                        if type(cc_element) == tuple:
                            if cc_element[0] in cc_value:
                                calling_convention_name = cc_element[0]
                                cost_per_use = ",".join(cc_element[1])
                                cost_per_use = str("[" + cost_per_use + "]")
                                break
        if (
            str.upper(reg_class) in alias_dict.keys()
            and str(i) in alias_dict[str.upper(reg_class)].keys()
        ):
            if (prefix + str(i)) in alias_dict[str.upper(reg_class)][str(i)]:
                alias_dict[str.upper(reg_class)][str(i)].remove(prefix + str(i))
            alias_register = alias_dict[str.upper(reg_class)][str(i)]
            alias = str(alias_dict[str.upper(reg_class)][str(i)])
            alias = alias.replace("'", '"')
            alias_register_dict[str.upper(prefix) + str(i)] = alias.split(", ")[0].replace("[\"", "").replace("\"]", "").replace("\"", "")
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
            if type(class_name) is dict:
                if reg_class.upper() in class_name.keys():
                    class_name = class_name[reg_class.upper()]
            register_class = ""
            if type(class_name) is not dict:
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
                if type(class_name) is not dict:
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
            if calling_convention_name != "" and cost_per_use != "":
                if str.upper(prefix) + str(i) not in instrfields_excluded_list:
                    register = "let CostPerUse = " + cost_per_use + " in {\n"
                    register += "\t\t" + define_register + register_class + dwarf_info + "\n"
                    register += "\t}"
                else:
                    register = define_register + register_class + dwarf_info
            else:
                if  registers_classes[reg_class.upper()].calling_convention[str.upper(prefix) + str(i)][0] == 'Hard_wired_zero':
                    register = "let isConstant = true in\n"
                    register += "\t"+define_register + register_class + dwarf_info
                else:
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
        registers_generated += "\t}"
        if let_name != "":
            registers_generated += "\n}"
    else:
        if let_name != "":
            registers_generated += "\n}"
    if subregs_def != "":
        registers_generated = subregs_def + registers_generated
    registers_define[reg_class] = registers
    return registers_generated, registers_aliases, additional_register_classes

## Function generating vector register
#
# It returns the defintion for vector register classes
def generate_vector_register():
    config_variables = config.config_environment(config_file, llvm_config)
    alias_regs = adl_parser.get_alias_for_regs(config_variables["ADLName"])
    registers = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    content_statement = ""
    vector_registers = list()
    statement = ""
    class_def = ""
    parameters = ""
    content_register = ""
    excluded_values = dict()
    instrfields = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    for instr in instructions.keys():
        if 'excluded_values' in instructions[instr].keys():
            excluded_values = instructions[instr]['excluded_values']
    excluded_values_dict = dict()
    for register in registers.keys():
        if len(excluded_values) > 0:
            for key in excluded_values.keys():
                if key in instrfields.keys():
                    if instrfields[key]['ref'].upper() == register:
                        excluded_values_dict[register+"No" + excluded_values[key][0].upper()] = excluded_values[key][0].upper()
    if 'VectorRegisterClass' in config_variables.keys():
        statement = "class " + config_variables['VectorRegisterClass']['ClassName'] + "<list<ValueType> regTypes, dag regList, int Vlmul>\n"
        class_def = " :" + config_variables['VectorRegisterClass']['ParentClass'] + "<regTypes, " + config_variables['VectorRegisterClass']['Width'] + ", regList> {\n"
        for element in config_variables['VectorRegisterClass'].keys():
            if element == 'Parameters':
                for param in config_variables['VectorRegisterClass']['Parameters'].split(","):
                    parameters += param.replace("[", "").replace("]", "") + ", "
            if element != 'ParentClass' and element != 'ClassName' and element != "Width" and element != "Parameters":
                content_statement += "\tlet " + element + " = " + config_variables['VectorRegisterClass'][element] + ";\n"
    for register in registers.keys():
        if 'vector' in registers[register].attributes:
            if utils.check_register_class_prefix(registers, register) is True:
                vector_registers = generate_registers_by_prefix(
                                config_variables["RegAltNameIndex"],
                                str.lower(register),
                                config_variables['RegisterClass'][register],
                                registers[register].prefix,
                                registers[register].debug,
                                int(registers[register].size),
                                alias_regs,
                            )
    for register in registers.keys():
        register_list = list()
        if 'vector' in registers[register].attributes:
            for order in config_variables['RegisterAllocationOrder'][register]:
                for reg in registers[register].calling_convention:
                    if registers[register].calling_convention[reg][0] == order:
                        register_list.append(reg)
            register_statement = "def " + register + " : " + config_variables['VectorRegisterClass']['ClassName'] + "<!listconcat(" + parameters.rstrip(", ") + "),\n"
            register_content = "\t(add (" + ""
            width = registers[register].width
            index_tab = 1
            index_row = 1
            for register in register_list:
                if index_row == 5:
                    index_row = 0
                if index_tab < 5:
                    if index_row == 0:
                        register_content += "\t"
                    register_content += register + ", "
                    index_tab += 1
                    index_row += 1
                if index_tab == 5:
                    register_content += "\n"
                    index_tab = 0
            content_register += register_statement + register_content.rstrip(", ") + ")), " + config_variables['VectorRegisterClass']['VLMulValue'] + ">;\n"
    if len(excluded_values_dict) > 0:
        for register in excluded_values_dict.keys():
            register_list = list()
            register_base = register.split("No")[0]
            if 'vector' in registers[register_base].attributes:
                for order in config_variables['RegisterAllocationOrder'][register_base]:
                    for reg in registers[register_base].calling_convention:
                        if registers[register_base].calling_convention[reg][0] == order:
                            if reg not in excluded_values_dict[register]:
                                register_list.append(reg)
                register_statement = "def " + register + " : " + config_variables['VectorRegisterClass']['ClassName'] + "<!listconcat(" + parameters.rstrip(", ") + "),\n"
                register_content = "\t(add (" + ""
                width = registers[register_base].width
                index_tab = 1
                index_row = 1
                for register_base_key in register_list:
                    if index_row == 5:
                        index_row = 0
                    if index_tab < 5:
                        if index_row == 0:
                            register_content += "\t"
                        register_content += register_base_key + ", "
                        index_tab += 1
                        index_row += 1
                    if index_tab == 5:
                        register_content += "\n"
                        index_tab = 0
                content_register += register_statement + register_content.rstrip(", ") + ")), " + config_variables['VectorRegisterClass']['VLMulValue'] + ">;\n"
    if content_statement != "":
        content_statement += "}\n"
    if content_register != "":
         content_register += "\n"
    if len(vector_registers) > 0:
        return vector_registers[0].replace("\t", "") + "\n" + statement + class_def + content_statement + content_register
    else:
        return ""
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
    let_name = ""
    if 'RegisterClassDisabledABI' in config_variables.keys():
        if reg_class.upper() not in config_variables['RegisterClassDisabledABI']:
            let_name = "let RegAltNameIndices = [" + name + "] in {\n"
    else:
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
                alias_register_dict[syntax[i]] = alias_print.split(", ")[0].replace("['", "").replace("']", "").replace("\"", "")
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
    if let_name != "":
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
    excluded_values
):
    config_variables = config.config_environment(config_file, llvm_config)
    registers_parsed = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    ref = class_name
    class_name_original = class_name
    register_class = ""
    register_class_defined = "RegisterClass"
    calling_convention_order = config_variables["RegisterAllocationOrder"]
    if offset != "0":
        class_name = class_name + "_" + offset
    if str(excluded_values).upper() in registers_list:
        class_name += "No" + str(excluded_values)
    if "alias" + class_name in config_variables.keys():
        class_name = config_variables["alias" + class_name]
    if 'RegisterClassWrapper' in config_variables.keys():
        for parent in  config_variables['RegisterClassWrapper'].keys():
            if class_name_original == config_variables['RegisterClassWrapper'][parent]:
                register_class_defined = parent.replace('RISCV', class_name_original)
                register_class_defined = re.sub(r"\d+", "", register_class_defined)
    if register_class_defined != "RegisterClass":
        statement = (
            "def "
            + class_name
            + " : "
            + register_class_defined + "<("
            + "\n"
            + "\t"
        )
    else:
        statement = (
            "def "
            + class_name
            + " : "
            + register_class_defined + "<"
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
    register_classes_width[class_name] = width
    content = "add" + " "
    register_allocation = ""
    first_dump = False
    index = 0
    first = int(offset)
    last = int(offset) + int(instrfield_width)
    if str(excluded_values).upper() in registers_list:
        registers_list.remove(str(excluded_values).upper())
    registers_list = registers_list[first:last]
    if len(calling_convention_order) == 0:
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
    else:
        for elem in calling_convention_order.keys():
            if ref == elem:
                for calling_convention_seq in calling_convention_order[ref]:
                    if type(calling_convention_seq) == tuple:
                        calling_convention_seq = calling_convention_seq[0]
                    index += 1
                    reg_list = ""
                    if registers_parsed[ref].calling_convention != {}:
                        for register in registers_parsed[ref].calling_convention.keys():
                            position = 0
                            if (
                                calling_convention_seq
                                in registers_parsed[ref].calling_convention[register]
                            ):
                                if index != len(calling_convention_order[ref]):
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
    register_allocation_copy = register_allocation
    register_allocation_copy = register_allocation_copy.replace("\n", "").replace("\t", "")
    list_values = register_allocation_copy.split(", ")
    if '' in list_values:
        list_values.remove('')
    if class_name not in instrfields_values.keys():
        instrfields_values[class_name] = list_values
    content += register_allocation.rstrip(", \n") + "\n\t)> {\n"
    let = "\tlet RegInfos = " + config_variables["XLenRI_key"] + ";\n"
    if register_class_defined == 'RegisterClass':
        def_class = statement + content + let + "}"
    else:
        def_class = statement + content
        def_class = def_class.strip("{\n")
        def_class = def_class.rstrip(" ")
        def_class = def_class + ";"
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
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    global register_classes
    additional_register_classes = dict()
    for key in regclass.keys():
        if 'vector' not in regclass[key].attributes:
            if utils.check_register_class_prefix(regclass, key) is True and key in config_variables["RegisterClass"].keys():
                additional_register_classes = generate_registers_by_prefix(
                    config_variables["RegAltNameIndex"],
                    str.lower(key),
                    config_variables["RegisterClass"][key],
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
                                    regclass[key].size,
                                    True,
                                )
                            )
                            f.write("\n")
                        f.write(
                            generate_register_class(
                                config_variables["RegisterClass"],
                                regclass[key].size,
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
                                    register_class_name, regclass[key].size, True
                                )
                            )
                            f.write("\n")
                        f.write(
                            generate_register_class(
                                config_variables["RegisterClass"],
                                regclass[key].size,
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
                                    register_class_name, regclass[key].size, True
                                )
                            )
                            f.write("\n")
                        register_class_name = config_variables["RegisterClass"] + key
                        register_class_name = register_class_name.replace("Reg", "")
                        register_class_name = register_class_name + "Reg"
                        f.write(
                            generate_register_class(
                                register_class_name, regclass[key].size, False
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
                                register_class_name, regclass[key].size, False
                            )
                        )
                        f.write("\n")
                        check_register_class_width.append(regclass[key].width)
    f.write(generate_let("FallbackRegAltNameIndex", config_variables['FallbackRegAltNameIndex']))
    f.write(generate_define(config_variables["RegAltNameIndex"], "RegAltNameIndex"))
    f.write("\n")
    register_pair_app_ins = dict()
    register_pair_app_outs = dict()
    instrfield_ref = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    for register in instrfield_ref:
        register_pair_app_ins[register] = int(0)
        register_pair_app_outs[register] = int(0)
    for instruction in instructions.keys():
        outs = str(instructions[instruction]["outputs"])
        ins = str(instructions[instruction]["inputs"])
        outs = re.split(r"[()]", outs)
        ins = re.split(r"[()]", ins)
        for element in ins:
            for instrfield in instrfield_ref:
                if instrfield == element.split(".")[0].rstrip(" "):
                    if register_pair_app_ins[instrfield] == 0:
                        register_pair_app_ins[instrfield] += 1
                        if instrfield not in ins:
                            ins.append(instrfield)
                    else:
                        element = element.replace(" ", "")
                        if "+1" in element:
                            register_pair_app_ins[instrfield] += 1
                            if instrfield not in ins:
                                ins.append(instrfield)
                else:
                    if instrfield == element.split(" ")[0].rstrip(" "):
                        element = element.replace(" ", "")
                        if "+1" in element:
                            register_pair_app_ins[instrfield] += 1
                            if instrfield not in ins:
                                ins.append(instrfield)
        ins.sort()
        outs_copy = outs.copy()
        outs_copy.sort()
        for element in outs_copy:
            for instrfield in instrfield_ref:
                if instrfield == element.split(".")[0].rstrip(" "):
                    if register_pair_app_outs[instrfield] == 0:
                        register_pair_app_outs[instrfield] += 1
                        if instrfield not in outs:
                            outs.append(instrfield)
                    else:
                        element = element.replace(" ", "")
                        if "+1" in element:
                            register_pair_app_outs[instrfield] += 1
                            if instrfield not in outs:
                                outs.append(instrfield)
                else:
                    if instrfield == element.split(" ")[0].rstrip(" "):
                        element = element.replace(" ", "")
                        if "+1" in element:
                            register_pair_app_outs[instrfield] += 1
                            if instrfield not in outs:
                                outs.append(instrfield)
        outs.sort()
    max_out = 0
    max_in = 0
    for element in register_pair_app_outs.keys():
        if register_pair_app_outs[element] > max_out:
            max_out = register_pair_app_outs[element]
    for element in register_pair_app_ins.keys():
        if register_pair_app_ins[element] > max_in:
            max_in = register_pair_app_ins[element]
    registers = adl_parser.get_alias_for_regs(config_variables["ADLName"])
    sub_reg_even = ""
    sub_reg_odd = ""
    if max_in > 1:
        for register in registers.keys():
            if 'SubReg_' + register.upper() + "_Even" in config_variables.keys():
                sub_reg_even = "def " + ("Sub_" + register.upper() + "_Even").lower() + " : " + config_variables['SubReg_' + register.upper() + "_Even"] + " {\n"
                sub_reg_even += "\t" + "let SubRegRanges = " + config_variables['SubReg_' + register.upper() + "_Even_HW"] + ";\n"
                sub_reg_even += "}\n" 
            if 'SubReg_' + register.upper() + "_Odd" in config_variables.keys():
                sub_reg_odd = "def " + ("Sub_" + register.upper() + "_Odd").lower() + " : " + config_variables['SubReg_' + register.upper() + "_Odd"] + " {\n"
                sub_reg_odd += "\t" + "let SubRegRanges = " + config_variables['SubReg_' + register.upper() + "_Odd_HW"] + ";\n"
                sub_reg_odd += "}\n" 
    elif max_out > 1:
        for register in registers.keys():
            if 'SubReg_' + register.upper() + "_Even" in config_variables.keys():
                sub_reg_even = "def " + ("Sub_" + register.upper() + "_Even").lower() + " : " + config_variables['SubReg_' + register.upper() + "_Even"] + " {\n"
                sub_reg_even += "\t" + "let SubRegRanges = " + config_variables['SubReg_' + register.upper() + "_Even_HW"] + ";\n"
                sub_reg_even += "}\n" 
            if 'SubReg_' + register.upper() + "_Odd" in config_variables.keys():
                sub_reg_odd = "def " + ("Sub_" + register.upper() + "_Odd").lower() + " : " + config_variables['SubReg_' + register.upper() + "_Odd"] + " {\n"
                sub_reg_odd += "\t" + "let SubRegRanges = " + config_variables['SubReg_' + register.upper() + "_Odd_HW"] + ";\n"
                sub_reg_odd += "}\n"
    if sub_reg_even != "":
        f.write(sub_reg_even)
        f.write("\n")
    if sub_reg_odd != "":
        f.write(sub_reg_odd)
    f.write("}\n")
    f.write(generate_register_classes_extended())
    f.write(generate_vector_register())
    f.write("\n")
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
        if 'vector' not in regclass[key].attributes:
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
                        if len(register_classes[elem_key]) > 0 and register_classes[elem_key][0] in instrfield_ref_dict.keys():
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
                            class_name = key
                            excluded_values = ""
                            if offset != "0":
                                class_name = class_name + "_" + offset
                            if str(excluded_values).upper() in registers_define[str.lower(key)]:
                                class_name += "No" + str(excluded_values)
                            if "alias" + class_name in config_variables.keys():
                                class_name = config_variables["alias" + class_name]
                            if class_name not in reg_instrfields.keys():
                                reg_instrfields[class_name] = sorted(list_instrfield_offset_cpy)
                    else:
                        if len(list_instrfield) != 0 and not (regclass[key].pseudo != ""):
                            f.write(
                                "//"
                                + "Instruction fields : "
                                + str(sorted(list_instrfield))
                            )
                            f.write("\n")
                            excluded_values = ""
                            class_name = key
                            if offset != "0":
                                class_name = class_name + "_" + offset
                            if str(excluded_values).upper() in registers_define[str.lower(key)]:
                                class_name += "No" + str(excluded_values)
                            if "alias" + class_name in config_variables.keys():
                                class_name = config_variables["alias" + class_name]
                            if class_name not in reg_instrfields.keys():
                                reg_instrfields[class_name] = sorted(list_instrfield)
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
                            class_name = key
                            excluded_values_value = excluded_values[instr_key][0]
                            if offset != "0":
                                class_name = class_name + "_" + offset
                            if str(excluded_values_value).upper() in registers_define[str.lower(key)]:
                                class_name += "No" + str(excluded_values_value)
                            if "alias" + class_name in config_variables.keys():
                                class_name = config_variables["alias" + class_name]
                            if class_name not in reg_instrfields.keys():
                                reg_instrfields[class_name] = sorted(list_instrfield)
                            if class_name not in reg_instrfields.keys():
                                reg_instrfields[class_name] = sorted(instr_key)
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
    extension_list
):
    config_variables = config.config_environment(config_file, llvm_config)
    instrfield_imm = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
    instrfield_ref = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    instrfield_data_ref = adl_parser.get_instrfield_offset(config_variables["ADLName"])[
        1
    ]
    registers = adl_parser.get_alias_for_regs(config_variables["ADLName"])
    regs_prefix = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    define = "def "
    content = ""
    sideEffects = False
    decoderNamespace = ""
    attributes = instructions[key]["attributes"]
    instruction_fixed = key
    attributes.sort()
    attributes_list_extension = list()
    attributes_list_instruction = list()
    predicate_checked = False
    rv_predicate = ""
    if "BaseArchitecture" in config_variables.keys():
        rv_predicate = "Is" + config_variables["BaseArchitecture"].upper()
    if len(extension_list) > 0:
        for extension in extension_list:
            for element in attributes:
                if (
                    "LLVMExt" + element.capitalize() in config_variables.keys()
                    and element == extension
                ):
                    attributes_list_extension.append(element)
                    break
    else:
        for element in attributes:
            if "LLVMExt" + element.capitalize() in config_variables.keys():
                attributes_list_extension.append(element)
    attributes_list_instruction = attributes_list_extension.copy()
    for element in attributes:
        if element not in attributes_list_extension:
            if "LLVMExt" + element.capitalize() in config_variables.keys():
                attributes_list_instruction.append(element)
    attributes_list_instruction.sort()
    predicates = "let Predicates = " + "["
    if rv_predicate != "":
        predicates += rv_predicate + ", "
    if rv_predicate != "":
        predicate_checked = True
    decoderNamespace_predicate = ""
    if len(attributes_list_instruction) > 0:
        for element in attributes_list_instruction:
            if config_variables["LLVMExt" + element.capitalize()] not in predicates:
                predicates += config_variables["LLVMExt" + element.capitalize()] + ", "
                predicate_checked = True
            if element.capitalize() in config_variables['DecoderNamespace'].keys() or element.lower() in config_variables['DecoderNamespace'].keys():
                decoderNamespace_predicate = config_variables['DecoderNamespace'][element.capitalize()]
    predicates = predicates.rstrip(", ")
    predicates += "] in {\n"
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
    if len(extension_list) > 0:
        for extension_elem in extension_list:
            for element in instructions[key]["attributes"]:
                if (
                    "LLVMExt" + element.capitalize() in config_variables.keys()
                    and element == extension_elem
                ):
                    file_name_extension = config_variables["LLVMExt" + element.capitalize()]
                    if file_name_extension + "Extension" in config_variables.keys():
                        extension = config_variables[file_name_extension + "Extension"]
                        break
    else:
        for element in instructions[key]["attributes"]:
            if "LLVMExt" + element.capitalize() in config_variables.keys():
                file_name_extension = config_variables["LLVMExt" + element.capitalize()]
                if file_name_extension + "Extension" in config_variables.keys():
                    extension = config_variables[file_name_extension + "Extension"]
                    break
    if "ExtensionPrefixed" in config_variables.keys():
        if extension.upper() in config_variables["ExtensionPrefixed"]:
            define += (
                extension.upper() + "_" + str(str(key).replace(".", "_")).upper() + " :"
            )
        elif extension.capitalize() in config_variables["ExtensionPrefixed"]:
            define += (
                extension.upper() + "_" + str(str(key).replace(".", "_")).upper() + " :"
            )
        else:
            attribute_checked = False
            for attribute in instructions[key]['attributes']:
                if attribute.capitalize() in config_variables["ExtensionPrefixed"]:
                    define += attribute.upper() + "_" + str(str(key).replace(".", "_")).upper() + " :"
                    attribute_checked = True
                    break
                elif attribute.upper() in config_variables["ExtensionPrefixed"]:
                    define += attribute.upper() + "_" + str(str(key).replace(".", "_")).upper() + " :"
                    attribute_checked = True
                    break
            if attribute_checked is False:
                define += str(str(key).replace(".", "_")).upper() + " :"
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
                        if ref is not None:
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
                                        if ref is not None:
                                            register_references.append(ref)
                                else:
                                    if "alias" + reg_key in config_variables.keys():
                                        ref = config_variables["alias" + reg_key]
                                        if ref not in register_references:
                                            if ref is not None:
                                                register_references.append(ref)
                            else:
                                if "alias" + reg_key in config_variables.keys():
                                    if (
                                        instrfield_ref[instrfield]["ref"]
                                        in "alias" + reg_key
                                    ):
                                        ref = config_variables["alias" + reg_key]
                                        if ref not in register_references:
                                            if ref is not None:
                                                register_references.append(ref)
                                        break
                        else:
                            ref = reg_key
                            if ref not in register_references:
                                if ref is not None:
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
                        elif instrfield in str(instructions[key]["outputs"]):
                            if instrfield not in regs_out:
                                regs_out.insert(len(regs_out), instrfield)
                                if instrfield in config_variables.keys():
                                    if (
                                        '"AliasImmClass"'
                                        in config_variables[instrfield].keys()
                                    ):
                                        instrfield_regs_outs.insert(
                                            len(instrfield_regs_outs),
                                            config_variables[instrfield][
                                                '"AliasImmClass"'
                                            ].replace('"', "")
                                            + ":"
                                            + "$"
                                            + instrfield,
                                        )
                                    else:
                                        if 'enumerated' in instrfield_imm[instrfield].keys():
                                                if len(instrfield_imm[instrfield]['enumerated'] > 0):
                                                    if 'ref' in instrfield_imm[instrfield].keys():
                                                        if instrfield_imm[instrfield]['ref'] != "":
                                                            instrfield_regs_outs.insert(
                                                                len(instrfield_regs_outs),
                                                                instr_key.lower() + ":" + "$" + instrfield,
                                                            )
                                else:
                                    if "nonzero" in ref_imm:
                                        if (
                                            "excluded_values"
                                            not in instructions[key].keys()
                                        ):
                                            ref_imm = ref_imm.replace("nonzero", "")
                                            if 'enumerated' in instrfield_imm[instrfield].keys():
                                                if len(instrfield_imm[instrfield]['enumerated'] > 0):
                                                    if 'ref' in instrfield_imm[instrfield].keys():
                                                        if instrfield_imm[instrfield]['ref'] != "":
                                                            instrfield_regs_outs.insert(
                                                                len(instrfield_regs_outs),
                                                                ref_imm + ":" + "$" + instrfield,
                                                            )
                                        else:
                                            if 'enumerated' in instrfield_imm[instrfield].keys():
                                                if len(instrfield_imm[instrfield]['enumerated'] > 0):
                                                    if 'ref' in instrfield_imm[instrfield].keys():
                                                        if instrfield_imm[instrfield]['ref'] != "":
                                                            instrfield_regs_outs.insert(
                                                                len(instrfield_regs_outs),
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
                                            if 'enumerated' in instrfield_imm[instrfield].keys():
                                                if len(instrfield_imm[instrfield]['enumerated'] > 0):
                                                    if 'ref' in instrfield_imm[instrfield].keys():
                                                        if instrfield_imm[instrfield]['ref'] != "":
                                                            instrfield_regs_outs.insert(
                                                                len(instrfield_regs_outs),
                                                                ref_imm + ":" + "$" + instrfield,
                                                            )
                                        else:
                                            if 'enumerated' in instrfield_imm[instrfield].keys():
                                                if len(instrfield_imm[instrfield]['enumerated'] > 0):
                                                    if 'ref' in instrfield_imm[instrfield].keys():
                                                        if instrfield_imm[instrfield]['ref'] != "":
                                                            instrfield_regs_outs.insert(
                                                                len(instrfield_regs_outs),
                                                                ref_imm + ":" + "$" + instrfield,
                                                            )
    outs = str(instructions[key]["outputs"])
    ins = str(instructions[key]["inputs"])
    outs = re.split(r"[()]", outs)
    ins = re.split(r"[()]", ins)
    memory_operand_registers = list()
    registers_parsed = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    register_pair_app_ins = dict()
    register_pair_app_outs = dict()
    for register in instrfield_ref:
        register_pair_app_ins[register] = int(0)
        register_pair_app_outs[register] = int(0)
    ins.sort()
    for element in ins:
        for instrfield in instrfield_ref:
            if instrfield == element.split(".")[0].rstrip(" "):
                if register_pair_app_ins[instrfield] == 0:
                    register_pair_app_ins[instrfield] += 1
                    if instrfield not in ins:
                        ins.append(instrfield)
                else:
                    element = element.replace(" ", "")
                    if "+1" in element:
                        register_pair_app_ins[instrfield] += 1
                        if instrfield not in ins:
                            ins.append(instrfield)
            else:
                if instrfield == element.split(" ")[0].rstrip(" "):
                    element = element.replace(" ", "")
                    if "+1" in element:
                        register_pair_app_ins[instrfield] += 1
                        if instrfield not in ins:
                            ins.append(instrfield)
    ins.sort()
    outs_copy = outs.copy()
    outs_copy.sort()
    for element in outs_copy:
        for instrfield in instrfield_ref:
            if instrfield == element.split(".")[0].rstrip(" "):
                if register_pair_app_outs[instrfield] == 0:
                    register_pair_app_outs[instrfield] += 1
                    if instrfield not in outs:
                        outs.append(instrfield)
                else:
                    element = element.replace(" ", "")
                    if "+1" in element:
                        register_pair_app_outs[instrfield] += 1
                        if instrfield not in outs:
                            outs.append(instrfield)
            else:
                if instrfield == element.split(" ")[0].rstrip(" "):
                    element = element.replace(" ", "")
                    if "+1" in element:
                        register_pair_app_outs[instrfield] += 1
                        if instrfield not in outs:
                            outs.append(instrfield)
    outs.sort()
    for element in syntax_elements:
        for immediate in instrfield_imm:
            if immediate in element:
                for register in instrfield_ref:
                    if register in element and register in ins:
                        memory_operand_registers.append(register)
                        memory_operands_registers_list.append(register)
    for element in ins:
        if element not in instrfield_ref:
            for register in instrfield_ref:
                if "enumerated" in instrfield_data_ref[register].keys() and element in instrfield_data_ref[register]["enumerated"].keys():
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
                                memory_operands_registers_list.append(index)
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
                            memory_operands_registers_list.append(register_used)
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
                            if ref is not None:
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
                            if ref is not None:
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
                            if ref is not None:
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
                            if ref is not None:
                                register_references.append(ref)
            if instrfield not in regs_out:
                regs_out.insert(len(regs_out), instrfield)
                instrfield_regs_outs.insert(
                    len(instrfield_regs_outs), ref + ":" + "$" + instrfield
                )
    for instrfield in ins:
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
                            instrfield in register_pair_app_ins.keys()
                            and register_pair_app_ins[instrfield] == 2
                        ) or (
                            instrfield in register_pair_app_ins.keys()
                            and register_pair_app_ins[instrfield]
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
                            if ref is not None:
                                register_references.append(ref)
                    else:
                        ref = reg_key
                        if (
                            instrfield in register_pair_app_ins.keys()
                            and register_pair_app_ins[instrfield] == 2
                        ) or (
                            instrfield in register_pair_app_ins.keys()
                            and register_pair_app_ins[instrfield]
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
                            if ref is not None:
                                register_references.append(ref)
            if instrfield not in regs_in:
                regs_in.insert(len(regs_out), instrfield)
                instrfield_regs_ins.insert(
                    len(instrfield_regs_ins), ref + ":" + "$" + instrfield
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
    for elem in instructions[key]["inputs"]:
        for regclass in register_classes:
            if regclass in elem:
                ins = re.split(r"[()]", elem)
                for elem_ins in ins:
                    if regclass in alias_dict.keys():
                        if elem_ins in alias_dict[regclass].keys():
                            reg_in = alias_dict[regclass][elem_ins]
                            reg_in = reg_in[0]
                            regs_in.insert(len(regs_in), reg_in)
                            if (
                                elem_ins in register_pair_app_ins.keys()
                                and register_pair_app_ins[elem_ins] == 2
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
                                    list_aux.append(reg_in)
                                    register_pairs[regclass] = list_aux
                                elif regclass in register_pairs.keys():
                                    list_aux = list()
                                    list_aux.extend(register_pairs[regclass])
                                    list_aux.append(reg_in)
                                    register_pairs[regclass] = list_aux
                                instrfield_regs_ins.insert(
                                    len(instrfield_regs_ins),
                                    regclass + ":" + "$" + reg_in,
                                )
                                decoderMethodRegs.append(reg_out)
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
                            if reg_out not in instrfield_imm.keys() and reg_out not in instrfield_ref.keys():
                                if reg_out.upper() in register_classes.keys():
                                    regclass =  reg_out.upper()
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
                                            ref_imm + ":" + "$" + syntax_element
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
                else:
                    if (
                        element.replace("[", "")
                        .replace("]", "")
                        .replace("'", "")
                        .replace(" ", "")
                        in instrfield_imm.keys()
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
                                        if register in instrfield_regs_ins_ord.keys():
                                            instrfield_regs_ins_ord.pop(register)
                                        index += 1
                                        exitValue = True
                                        break
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
                    if instrfield_regs_outs_ord[reg] in instrfield_regs_outs:
                        instrfield_regs_outs.remove(instrfield_regs_outs_ord[reg])
                        instrfield_regs_outs_ord[reg] = instrfield_regs_outs_ord[
                            reg
                        ].replace(aux, aux + "_wb")
                if instrfield_regs_outs_ord[reg] not in instrfield_regs_outs and instrfield_regs_outs_ord[reg] + "_wb" not in instrfield_regs_outs:
                    instrfield_regs_outs.append(instrfield_regs_outs_ord[reg])
                exitValue = True
    write_sched = ""
    read_sched = ""
    read_resource = False
    scheduling_table_dict = adl_parser.parse_sched_table_from_adl(config_variables["ADLName"])
    for sched_key in scheduling_table_dict.keys():
            for key_instr in scheduling_table_dict[sched_key].keys():
                if 'instruction_list' in scheduling_table_dict[sched_key][key_instr].keys():
                    if key in scheduling_table_dict[sched_key][key_instr]['instruction_list']:
                        if 'forwarding' in scheduling_table_dict[sched_key][key_instr].keys():
                            read_resource = True
                            break
    if key in scheduling_instr_info.keys():
        if 'write' in scheduling_instr_info[key].keys():
            write_sched = scheduling_instr_info[key]['write']
        if 'read' in scheduling_instr_info[key].keys():
            read_sched = scheduling_instr_info[key]['read']
        scheduling_list = list()
        for element in instrfield_regs_outs:
            register = element.split(":$")[1]
            if "_wb" in register:
                register = register.replace("_wb", "")
            if register in instrfield_ref.keys():
                scheduling_list.append(write_sched.replace("'", ""))
            elif register not in instrfield_ref.keys() and register not in instrfield_imm.keys():
                scheduling_list.append(write_sched.replace("'", ""))
        if 'store' in instructions[key]['attributes'] or 'branch' in instructions[key]['attributes']:
            scheduling_list.append(write_sched.replace("'", ""))
        index = 1
        first = False
        scheduling_original_list = list()
        scheduling_original_list = scheduling_list.copy()
        fixed_digit = list()
        fixed_digit = re.findall(r'\d+', read_sched)
        except_list = list()
        for element in instrfield_regs_ins:
            register = element.split(":$")[1]
            if register in instrfield_ref.keys():
                read_sched = re.sub(r"\_*\d*", "", read_sched)
                if read_sched.replace("'", "") in scheduling_original_list and read_resource is True:
                    if first is False:
                        scheduling_original_list.append(read_sched.replace("'", ""))
                        scheduling_list.remove(read_sched.replace("'", ""))
                        if 'store' in instructions[key]['attributes']:
                            if index == 1:
                                read_sched = "ReadStoreData"
                                scheduling_list.append(read_sched.replace("'", ""))
                                index += 1
                            if index == 2:
                                read_sched = "ReadMemBase"
                                scheduling_list.append(read_sched.replace("'", ""))
                                index += 1
                        else:
                            if len(fixed_digit) > 0:
                                read_sched += fixed_digit[0] + "_"
                            read_sched += str(index)
                            scheduling_list.append(read_sched.replace("'", ""))
                            index += 1
                            first = True
                            read_sched = re.sub(r"\_*\d*", "", read_sched)
                            if len(fixed_digit) > 0:
                                read_sched += fixed_digit[0] + "_"
                            read_sched += str(index)
                            scheduling_list.append(read_sched.replace("'", ""))
                            index += 1
                    else:
                        if 'store' in instructions[key]['attributes']:
                            if index == 1:
                                read_sched = "ReadStoreData"
                                scheduling_list.append(read_sched.replace("'", ""))
                                index += 1
                            if index == 2:
                                read_sched = "ReadMemBase"
                                scheduling_list.append(read_sched.replace("'", ""))
                                index += 1
                        else:
                            read_sched = re.sub(r"\_*\d*", "", read_sched)
                            scheduling_original_list.append(read_sched.replace("'", ""))
                            if len(fixed_digit) > 0:
                                read_sched += fixed_digit[0] + "_"
                            read_sched += str(index)
                            scheduling_list.append(read_sched.replace("'", ""))
                            index += 1
                else:
                    if 'store' in instructions[key]['attributes']:
                        if index == 1:
                            read_sched = "ReadStoreData"
                            scheduling_list.append(read_sched.replace("'", ""))
                            index += 1
                        if index == 2:
                            read_sched = "ReadMemBase"
                            scheduling_list.append(read_sched.replace("'", ""))
                            index += 1
                    else:
                        scheduling_list.append(read_sched.replace("'", ""))
                        scheduling_original_list.append(read_sched.replace("'", ""))
            else:
                for register_ref in registers_parsed.keys():
                    for input in instructions[key]['inputs']:
                        reg_found = input.replace(register_ref, "").replace("(", "").replace(")", "")
                        if register_ref in alias_dict.keys() and reg_found in alias_dict[register_ref].keys():
                            if register in alias_dict[register_ref][reg_found]:
                                if read_sched.replace("'", "") in scheduling_original_list and read_resource is True:
                                    if 'store' in instructions[key]['attributes']:
                                        if index == 1:
                                            read_sched = "ReadStoreData"
                                            scheduling_list.append(read_sched.replace("'", ""))
                                            index += 1
                                        if index == 2:
                                            read_sched = "ReadMemBase"
                                            scheduling_list.append(read_sched.replace("'", ""))
                                            index += 1
                                    else:
                                        if first is False:
                                            scheduling_original_list.append(read_sched.replace("'", ""))
                                            scheduling_list.remove(read_sched.replace("'", ""))
                                            if len(fixed_digit) > 0:
                                                read_sched += fixed_digit[0] + "_"
                                            read_sched += str(index)
                                            scheduling_list.append(read_sched.replace("'", ""))
                                            index += 1
                                            first = True
                                        else:
                                            scheduling_original_list.append(read_sched.replace("'", ""))
                                            if len(fixed_digit) > 0:
                                                read_sched += fixed_digit[0] + "_"
                                            read_sched += str(index)
                                            scheduling_list.append(read_sched.replace("'", ""))
                                            index += 1
                                else:
                                    if 'store' in instructions[key]['attributes']:
                                        if index == 1:
                                            read_sched = "ReadStoreData"
                                            scheduling_list.append(read_sched.replace("'", ""))
                                            index += 1
                                        if index == 2:
                                            read_sched = "ReadMemBase"
                                            scheduling_list.append(read_sched.replace("'", ""))
                                            index += 1
                                    else:
                                        scheduling_list.append(read_sched.replace("'", ""))
                                        scheduling_original_list.append(read_sched.replace("'", ""))
                        else: 
                            if 'store' not in instructions[key]['attributes']:
                                if register_ref in registers.keys():
                                    if reg_found.replace("?", "") in registers[register_ref].keys():
                                        if reg_found not in except_list:
                                            except_list.append(reg_found)
                                            scheduling_list.append(read_sched.replace("'", ""))
                                            scheduling_original_list.append(read_sched.replace("'", ""))
        schedule = str(scheduling_list).replace("'", "")
    instructions_parsed = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    for instruction in instructions_parsed.keys():
        if instruction == instruction_fixed:
            scheduling_list = list()
            if len(instrfield_regs_outs) == 0 and len(instrfield_regs_ins) == 0:
                if instruction in scheduling_instr_info.keys():
                    if 'write' in scheduling_instr_info[instruction].keys():
                        write_sched = scheduling_instr_info[instruction]['write']
                        scheduling_list.append(write_sched.replace("'", ""))
                    schedule = str(scheduling_list).replace("'", "")
            else:
                check = False
                for element in instrfield_regs_ins:
                    if element.split(":$")[1] in instrfield_ref.keys():
                        check = True
                if check is False:
                    if len(instrfield_regs_outs) == 0:
                        if instruction in scheduling_instr_info.keys():
                            if 'write' in scheduling_instr_info[instruction].keys():
                                write_sched = scheduling_instr_info[instruction]['write']
                                scheduling_list.append(write_sched.replace("'", ""))
                            schedule = str(scheduling_list).replace("'", "")
    instruction_registers_used_outs[key] = instrfield_regs_outs
    instrfield_regs_outs = str(instrfield_regs_outs)
    instrfield_regs_ins_list = instrfield_regs_ins
    instruction_registers_used_ins[key] = instrfield_regs_ins
    instrfield_regs_ins = str(instrfield_regs_ins)
    for reg in regs_in:
        if reg in regs_out:
            if reg in instrfield_ref.keys() or (reg not in instrfield_ref.keys() and reg not in instrfield_imm.keys()):
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
    instrfield_regs_ins_sorted = list()
    syntax = list()
    for element in instructions[key]['syntax']:
        if '(' in element:
            element_list = element.split("(")
            element_list.reverse()
            for elem in element_list:
                syntax.append(elem.replace(")", ""))
        else:
            if element != key:
                syntax.append(element)
            
    for element in syntax:
        for instrfield in instrfield_regs_ins_list:
            if element == instrfield.split('$')[1]:
                instrfield_regs_ins_sorted.append(instrfield)
    instrfield_regs_ins = str(instrfield_regs_ins_sorted)
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
    instruction_encoding_list = dict()
    for instrfield in instructions[key]["fields"][0].keys():
        if instrfield in instrfield_ref.keys():
            shift = "0"
            if "shift" in instrfield_ref[instrfield].keys():
                shift = instrfield_ref[instrfield]["shift"]
            size = int(instrfield_ref[instrfield]["size"])
            size = size - 1
            if 'jump' in instructions[key]["attributes"] or 'branch' in instructions[key]["attributes"]:
                size_first = size
            else:
                size_first = size + int(shift)
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
                        instruction_encoding_list[int(end)] = (
                            "let Inst{"
                            + end
                            + "-"
                            + start
                            + "} = "
                            + instrfield
                            + ";"
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
                        instruction_encoding_list[int(end)] = (
                            "let Inst{"
                            + end
                            + "-"
                            + start
                            + "} = "
                            + str(instructions[key]["fields"][0][instrfield])
                            + ";"
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
                    instruction_encoding_list[int(end)] = (
                        "let Inst{"
                        + end
                        + "-"
                        + start
                        + "} = "
                        + str(instructions[key]["fields"][0][instrfield])
                        + ";"
                    )
        elif instrfield in instrfield_imm.keys():
            shift = instrfield_imm[instrfield]["shift"]
            size = int(instrfield_imm[instrfield]["size"])
            size = size - 1
            if 'jump' in instructions[key]["attributes"] or 'branch' in instructions[key]["attributes"]:
                size_first = size
            else:
                size_first = size + int(shift)
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
                            instruction_encoding_list[int(end)] = (
                                "let Inst{"
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
                                + ";"
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
                            instruction_encoding_list[int(end)] = (
                                "let Inst{"
                                + end
                                + "-"
                                + start
                                + "} = "
                                + str(instructions[key]["fields"][0][instrfield])
                                + ";"
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
                        instruction_encoding_list[int(end)] = (
                            "let Inst{"
                            + end
                            + "-"
                            + start
                            + "} = "
                            + str(instructions[key]["fields"][0][instrfield])
                            + ";"
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
                        instruction_encoding_list[int(end)] = (
                            "let Inst{"
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
                            + ";"
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
                        instruction_encoding_list[int(end)] = (
                            "let Inst{"
                            + end
                            + "-"
                            + start
                            + "} = "
                            + str(instructions[key]["fields"][0][instrfield])
                            + ";"
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
                    instruction_encoding_list[int(end)] = (
                        "let Inst{"
                        + end
                        + "-"
                        + start
                        + "} = "
                        + str(instructions[key]["fields"][0][instrfield])
                        + ";"
                    )
    sorted_dict = dict(sorted(instruction_encoding_list.items(), key = lambda x: x[0], reverse = True))
    instruction_encoding_dict[key] = sorted_dict
    if 'branch' in instructions[key]["attributes"]:
        isBranch = "\tlet isBranch = 1;\n"
        isTerminator = "\tlet isTerminator = 1;\n"
        content = content + isBranch + isTerminator
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
                if key_decoder in config_variables["DecoderNamespace"].keys():
                    decoderNamespace = (
                        "let DecoderNamespace = "
                        + '"'
                        + config_variables["DecoderNamespace"][key_decoder]
                        + '"'
                    )        
    if decoderNamespace != "":
        content += "\n}"
    if predicate_checked is True:
        content += "\n}\n"
    decoderNamespace = decoderNamespace.rstrip(", ")
    if decoderNamespace != "":
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
            return predicates + decoderNamespace + def_let_sideEffectsLoadTrue + define + content
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
            return predicates + decoderNamespace + def_let_sideEffectsStoreTrue + define + content
        else:
            if "jump" in instructions[key]["attributes"]:
                def_let_sideEffects = "isCall = 1" + ", " + def_let_sideEffects
            if let_uses != "":
                def_let_sideEffects = let_uses + ", " + def_let_sideEffects
            if let_defs != "":
                def_let_sideEffects = let_defs + ", " + def_let_sideEffects
            def_let_sideEffects = "let " + def_let_sideEffects
            return predicates + decoderNamespace + def_let_sideEffects + define + content
    else:
        if "load" in instructions[key]["attributes"]:
            if "jump" in instructions[key]["attributes"]:
                def_let_sideEffectsLoad = "isCall = 1" + ", " + def_let_sideEffectsLoad
            if let_uses != "":
                def_let_sideEffectsLoad = let_uses + ", " + def_let_sideEffectsLoad
            if let_defs != "":
                def_let_sideEffectsLoad = let_defs + ", " + def_let_sideEffectsLoad
            def_let_sideEffectsLoad = "let " + def_let_sideEffectsLoad
            return predicates + decoderNamespace + def_let_sideEffectsLoad + define + content
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
            return predicates + decoderNamespace + def_let_sideEffectsStore + define + content
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
            return predicates + decoderNamespace + def_let_sideEffectsBasic + define + content
    


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
    legalDisclaimer.get_copyright(file_name)
    if len(extensions_list) > 0:
        sorting_attributes = extensions_list
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
                #legalDisclaimer.get_generated_file(file_name)
            else:
                file_name = file_name_cpy
            f = open(file_name, "a")
            if "BaseArchitecture" in config_variables.keys():
                rv_predicate = "Is" + config_variables["BaseArchitecture"].upper()
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
def generate_instruction_format(file_name, file_name_c):
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
            base_name = os.path.basename(config_variables["InstructionFormatFile"])
            file_name =  os.path.basename(config_variables["InstructionFormatFile" + width])
            file_name = file_name_c + file_name
            if os.getcwd().endswith("tools"):
                file_name = os.path.abspath(file_name)
            if os.path.exists(config_variables["InstructionFormatFile" + width]):
                os.remove(config_variables["InstructionFormatFile" + width])
            g = open(file_name, "a")
            legalDisclaimer.get_copyright(file_name)
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
    ImmLeaf = ""
    statement = ""
    sign_extension = ""
    decoderMethod = ""
    check_key = immediate_key
    for imm_key in instrfield_classes[key]:
        if imm_key == check_key:
            if imm_key in config_variables.keys():
                    for instuction_key in instructions.keys():
                        if imm_key in instructions[instuction_key]["fields"][0].keys():
                            if imm_key in config_variables.keys():
                                if '"OperandParser"' in config_variables[imm_key].keys():
                                    OperandParser = config_variables[imm_key]['"OperandParser"'].replace("\"", "")

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
                                        break
                                    else:
                                        if 'signed' in instrfield_imm[imm_key].keys():
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
                                            
                                else:
                                    if 'signed' in instrfield_imm[imm_key].keys():
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
                                        break
                                    else:
                                        if 'signed' in instrfield_imm[imm_key].keys():
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
                                else:
                                    if 'signed' in instrfield_imm[imm_key].keys():
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
                    if '"disableMCOperandPredicate"' not in config_variables[imm_key].keys():
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
                    if '"MCOperandPredicate"' in config_variables[imm_key].keys():
                        if '"disableMCOperandPredicate"' not in config_variables[imm_key].keys():
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

## A function that generates RISCVOp definition based on the LLVM requirements
#
# @return It returns the content for RISCVOp definition
def generate_riscv_operand():
    config_variables = config.config_environment(config_file, llvm_config)
    statement = "class RISCVOp<ValueType vt = " + config_variables['XLenVT_key'] + "> : Operand<vt> {\n"
    content = "\tlet OperandNamespace =" + "\"" + "RISCVOp" + "\"" + ";\n}"
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
    f.write(generate_riscv_operand())
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
    for key in instrfield_classes:
        for imm_key in instrfield_classes[key]:
            exitFor = False
            sameInstruction = False
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
                                    if key not in singleton_list:
                                        singleton_list.append(key)
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
                                    if key not in singleton_list:
                                        singleton_list.append(key)
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
    registers = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    instructions_aliases = adl_parser.parse_instructions_aliases_from_adl(
        config_variables["ADLName"]
    )
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])
    instrfield_ref = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    regfiles = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
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
    registers_ref = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
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
def write_instructions_aliases(file_name, file_name_c, extensions_list):
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
        if alias_dump is True and alias in instructions.keys():
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
                                        file_name_c
                                        .replace("_gen", "")
                                        .replace(".td", file_extension + "_gen" + ".td")
                                    )
                                else:
                                    new_file_name = file_name_c.replace(".td", file_extension + ".td")
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
                                    file_name_c
                                    .replace("_gen", "")
                                    .replace(".td", file_extension + "_gen" + ".td")
                                )
                            else:
                                new_file_name = file_name_c.replace(".td", file_extension + ".td")
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
    registers_parsed = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
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
    once_print = ""
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
                if 'load' in instructions[key]['attributes']:
                    instrinsic_attributes.append("IntrReadMem")
                elif 'store' in instructions[key]['attributes']:
                    instrinsic_attributes.append("")
                else:
                    instrinsic_attributes.append("IntrNoMem")
            else:
                instrinsic_attributes.append("IntrArgMemOnly")
            if intrinsic_sideEffect is True:
                instrinsic_attributes.append("IntrHasSideEffects")
            if len(operand_type) == 0:
                operand_type.append("llvm_void_ty")
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
                once_print = False
                if extension_checked == False:
                    list_dir = list()
                    for fname in os.listdir("."):
                        list_dir.append(fname)
                    if once_print is False:
                        if extension not in attributes_list_intrinsics:
                            legalDisclaimer.get_copyright(file_name_cpy)
                            once_print = True
                    f = open(file_name_cpy, "a")
                    f.write(statement)
                    f.write("\n")
                    f.close()
        if once_print is True:
            attributes_list_intrinsics.append(extension)
    attributes_list_intrinsics.clear()
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
        if len(operand_type) == 0:
            operand_type.append("llvm_void_ty")
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
            once_print = False
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
            if extension_checked == False:
                if once_print is False:
                    if extension not in attributes_list:
                        legalDisclaimer.get_copyright(file_name_cpy)
                        once_print = True
                f = open(file_name_cpy, "a")
                f.write(statement)
                f.write("\n")
                f.close()
        if once_print is True:
            attributes_list_intrinsics.append(extension)


## This function will generate the accumulator register definition
#
# @param file_name This parameter indicates the name for the in which the content will be written
# @param abi_name This parameter indicates ABI information needed for LLVM register definition
# @param register_class This parameter indicates what register class the accumulator belongs to
# @param namespace This parameter indicates the namespace needed for LLVM register definition
# @return The function will return the content as string
def generate_accumulator_register(file_name, abi_name, register_class, namespace):
    config_variables = config.config_environment(config_file, llvm_config)
    registers = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    define = ""
    content = ""
    f = open(file_name, "a")
    for key in registers.keys():
        if "accumulator" in registers[key].attributes:
            let_name = ""
            if 'RegisterClassDisabledABI' in config_variables.keys():
                if register_class.upper() not in config_variables['RegisterClassDisabledABI']:
                    let_name = "let RegAltNameIndices = [" + abi_name + "] in {\n"
            else:
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
            register_classes_width[key] =  registers[key].width
            statement += "\tlet Size = " + registers[key].size + ";" + "\n}"
            if let_name != "":
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
    registers = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    instrfields = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    instrfields_imm  = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
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
                ref = ""
                if len(instructions[key]["syntax"]) > 1:
                    if instructions[key]["syntax"][1] in instrfields.keys():
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
                                    if 'load' in instructions[instruction_key]['attributes']:
                                        if argument_list[1].replace(")", "") in memory_operands_registers_list:
                                            arguments += argument_list[0] + "Mem"
                                        else:
                                            arguments += argument_list[0]
                                    elif 'store' in instructions[instruction_key]['attributes']:
                                        if argument_list[1].replace(")", "") in memory_operands_registers_list:
                                            arguments += argument_list[0] + "Mem"
                                        else:
                                            arguments += argument_list[0]
                                    else:
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
                        if argument in instrfields_imm.keys():
                            if argument in config_variables["ImmediateOperands"]:
                                if "'AliasImmClass'" in config_variables[argument].keys():
                                    arguments_type = config_variables[argument]["'AliasImmClass'"].strip("\"")
                            else:
                                if 'signed' in instrfields_imm[argument].keys():
                                    arguments_type = 'simm' + instrfields_imm[argument]['width']
                                else:
                                    arguments_type = 'uimm' + instrfields_imm[argument]['width']
                            arguments += (
                                arguments_type + 
                                ":$"
                                + argument
                                + ", "
                            )
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
                                        if 'load' in instructions[instruction_key]['attributes']:
                                            if argument_list[1].replace(")", "") in memory_operands_registers_list:
                                                arguments += argument_list[0] + "Mem"
                                            else:
                                                arguments += argument_list[0]
                                        elif 'store' in instructions[instruction_key]['attributes']:
                                            if argument_list[1].replace(")", "") in memory_operands_registers_list:
                                                arguments += argument_list[0] + "Mem"
                                            else:
                                                arguments += argument_list[0]
                                        else:
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
                instrfield_destination = ""
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
                for instrfield in instructions[instruction_key]['outputs']:
                    if "(" in instrfield:
                        instrfield = instrfield.split("(")[1].replace(")", "").replace(" ", "")
                        if "+1" in instrfield:
                            instrfield_destination = instrfield.strip(" ").split("+")[0]
                            ref = instrfields[instrfield_destination]['ref']
                            register_classes_width[instrfields[instrfield_destination]['ref']+"P"] = 2 * int(registers[ref.upper()].width)
                            break
                if instrfield_destination in instrfields.keys():
                    return_class = str(instruction_registers_used_outs[instruction_key]).split("$")[0].replace(":", "").replace("[", "").replace("'", "")
                    if return_class in register_classes_width.keys():
                        return_type = "i" + str(register_classes_width[return_class])
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
                if return_type != "":
                    return_type += " "
                if syntax == "":
                    if arguments != "":
                        arguments = " " + str(instruction_registers_used_ins[instruction_key]).replace("[", "").replace("]", "").replace("'", "")
                    if extension in config_variables["ExtensionPrefixed"]:
                        if return_type != "":
                            statement = (
                                "def : "
                                + "Pat<("
                                + return_type
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
                                + instructions[key]["intrinsic"].replace(".", "_")
                                + arguments.rstrip(", ")
                                + "), ("
                                + key.upper().replace(".", "_")
                                + " "
                                + arguments.rstrip(", ")
                                + ")>;"
                            )
                    else:
                        if return_type != "":
                            statement = (
                                "def : "
                                + "Pat<("
                                + return_type
                                + "("
                                + instructions[key]["intrinsic"].replace(".", "_")
                                + arguments.rstrip(", ")
                                + ")), ("
                                + key.upper().replace(".", "_")
                                + ")>;"
                            )
                        else:
                            statement = (
                                "def : "
                                + "Pat<("
                                + return_type
                                + instructions[key]["intrinsic"].replace(".", "_")
                                + arguments.rstrip(", ")
                                + "), ("
                                + key.upper().replace(".", "_")
                                + " "
                                + arguments.rstrip(", ")
                                + ")>;"
                            )
                else:
                    if arguments != "":
                        arguments = " " + str(instruction_registers_used_ins[instruction_key]).replace("[", "").replace("]", "").replace("'", "")
                    if (
                        "ExtensionPrefixed" in config_variables.keys()
                        and extension in config_variables["ExtensionPrefixed"]
                    ):
                        if return_type != "":
                            statement = (
                                "def : "
                                + "Pat<("
                                + return_type
                                + "("
                                + instructions[key]["intrinsic"].replace(".", "_")
                                + arguments.rstrip(", ")
                                + ")), ("
                                + extension.upper()
                                + "_"
                                + key.upper().replace(".", "_")
                                + " "
                                + arguments.rstrip(", ")
                                + ")>;"
                            )
                        else:
                            statement = (
                                "def : "
                                + "Pat<("
                                + return_type
                                + instructions[key]["intrinsic"].replace(".", "_")
                                + arguments.rstrip(", ")
                                + "), ("
                                + key.upper().replace(".", "_")
                                + " "
                                + arguments.rstrip(", ")
                                + ")>;"
                            )
                    else:
                        if return_type != "":
                            statement = (
                                "def : "
                                + "Pat<("
                                + return_type
                                + "("
                                + instructions[key]["intrinsic"].replace(".", "_")
                                + arguments.rstrip(", ")
                                + ")), ("
                                + key.upper().replace(".", "_")
                                + " "
                                + arguments.rstrip(", ")
                                + ")>;"
                            )
                        else:
                            statement = (
                                "def : "
                                + "Pat<("
                                + return_type
                                + instructions[key]["intrinsic"].replace(".", "_")
                                + arguments.rstrip(", ")
                                + "), ("
                                + key.upper().replace(".", "_")
                                + " "
                                + arguments.rstrip(", ")
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
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    instrfields = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    instrfields_imm = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
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
        macro_info = ""
        statement = "def " + key.replace(".", "_") + " : "
        statement += "RISCVBuiltin<"
        if "generate_builtin" in instructions[key].keys():
            customize_name = instructions[key]["generate_builtin"]
        if "intrinsic" in instructions[key].keys():
            name_convention = "__builtin_riscv_" + key.lower().replace(".", "_")
        return_arg = ""
        if "generate_builtin" in instructions[key].keys():
            if "intrinsic_args" in instructions[key].keys():
                for element in instructions[key]["intrinsic_args"]:
                    if "(" in element and element.split("(")[1].rstrip(")") not in instrfields_imm.keys():
                        register = element.split("(")[1].replace(")", "")
                        if register in instrfields.keys():
                            if element in intrinsic_inputs:
                                if "signed" in instrfields[register].keys():
                                    if 'i32' in instructions[key]['intrinsic_type'][element][0]:
                                        operand_type += "int, "
                                        if (
                                            element in intrinsic_inputs
                                            and element in intrinsic_outputs
                                        ):
                                            operand_type += "int, "
                                    elif 'i64' in instructions[key]['intrinsic_type'][element][0]:
                                        operand_type += "uint64_t, "
                                        if (
                                            element in intrinsic_inputs
                                            and element in intrinsic_outputs
                                        ):
                                            operand_type += "uint64_t, "        
                                    elif 'ptr_ty' in instructions[key]['intrinsic_type'][element][0]:
                                        operand_type += "int32_t *, "
                                        if (
                                            element in intrinsic_inputs
                                            and element in intrinsic_outputs
                                        ):
                                            operand_type += "int32_t *, "
                                else:
                                    if 'i32' in instructions[key]['intrinsic_type'][element][0]:
                                        operand_type += "unsigned int, "
                                        if (
                                            element in intrinsic_inputs
                                            and element in intrinsic_outputs
                                        ):
                                            operand_type += "unsigned int, "
                                    elif 'ptr_ty' in instructions[key]['intrinsic_type'][element][0]:
                                        operand_type += "uint32_t *, "
                                        if (
                                            element in intrinsic_inputs
                                            and element in intrinsic_outputs
                                        ):
                                            operand_type += "uint32_t *, "
                                    elif 'i64' in instructions[key]['intrinsic_type'][element][0]:
                                        operand_type += "uint64_t, "
                                        if (
                                            element in intrinsic_inputs
                                            and element in intrinsic_outputs
                                        ):
                                            operand_type += "uint64_t, " 
                            if element in intrinsic_outputs:
                                if 'i32' in instructions[key]['intrinsic_type'][element][0]:
                                    if "signed" in instrfields[register].keys():
                                        return_arg += "int"
                                    else:
                                        return_arg += "unsigned int"
                                elif 'i64' in instructions[key]['intrinsic_type'][element][0]:
                                    if "signed" in instrfields[register].keys():
                                        return_arg += "uint64_t"
                                    else:
                                        return_arg += "uint64_t"
                            elif len(intrinsic_outputs) == 0:
                                return_arg += "void"
                    else:
                        if element in instrfields_imm.keys():
                            for output in intrinsic_outputs:
                                if element == output.split("(")[1].replace(")", ""):
                                    check = True
                                    if 'i32' in instructions[key]['intrinsic_type'][element][0]:
                                        if "signed" in instrfields_imm[element].keys():
                                            return_arg += "int"
                                        else:
                                            return_arg += "unsigned int"
                                    elif 'i64' in instructions[key]['intrinsic_type'][element][0]:
                                        if "signed" in instrfields_imm[element].keys():
                                            return_arg += "uint64_t uint64_t"
                                        else:
                                            return_arg += "unsigned uint64_t uint64_t"
                                    break
                                elif len(intrinsic_outputs) == 0:
                                    return_arg += "void"
                                    break
                                else:
                                    if 'i32' in instructions[key]['intrinsic_type'][element][0] or 'any_ty' in instructions[key]['intrinsic_type'][element][0]:
                                        if "signed" in instrfields_imm[element].keys():
                                            operand_type += "int,"
                                        else:
                                            operand_type += "unsigned int, "
                                    elif 'i64' in instructions[key]['intrinsic_type'][element][0]:
                                        if "signed" in instrfields_imm[element].keys():
                                            operand_type += "uint64_t uint64_t,"
                                        else:
                                            operand_type += "unsigned uint64_t uint64_t, "
                                    break
                                        
            else:
                continue
            statement += '\"' + return_arg + '(' + operand_type.rstrip(", ") + ')"' + ", "
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
                once_print = False
                once_print_header = False
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
            extension_builtin = ""
            if 'experimental' in instructions[key].keys():
                extension_builtin = "experimental-" + extension
            if extension != "":
                if extension_checked is False:
                    if extension_builtin != "":
                        statement += '"' + extension_builtin.lower() + '"' + ">;"
                    else:
                        statement += '"' + extension.lower() + '"' + ">;"
                    file_name_cpy = file_name
                    file_name_cpy = file_name_cpy.replace(".td", "")
                    file_name_cpy += extension + ".td"
                    header_name_cpy = header_name
                    header_name_cpy = header_name_cpy.replace(".h", "")
                    header_name_cpy += extension + ".h"
                    if once_print is False:
                        if extension not in attributes_list:
                            legalDisclaimer.get_copyright(file_name_cpy)
                            once_print = True
                    f = open(file_name_cpy, "a")
                    f.write(statement)
                    f.write("\n")
                    f.close()
                    if naming_definition != "":
                        if once_print_header is False:
                            if extension not in attributes_list:
                                legalDisclaimer.get_copyright(header_name_cpy)
                                once_print_header = True
                        g = open(header_name_cpy, "a")
                        g.write(naming_definition)
                        g.write("\n")
                        g.close()
                    if once_print_header is True and once_print is True:
                        attributes_list.append(extension)
                        
## This function will generate intrinsic tests for verifying and validating intrinsic usage
#
# @param include_path path to the location of builtin file that has to be included
# @return This function will return a folder containing a test for each intrinsic generated
def generate_intrinsic_tests(folder, include_path):
    include_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', include_path)
    config_variables = config.config_environment(config_file, llvm_config)
    tree = ET.parse(config_variables["ADLName"])
    root = tree.getroot()
    mattrib = ""
    architecture = ""
    attributes = ""
    extension = ""
    for cores in root.iter("cores"):
        for asm_config in cores.iter("asm_config"):
            architecture = asm_config.find("arch").find("str").text
            attributes = asm_config.find("attributes").find("str").text
            mattrib = asm_config.find("mattrib").find("str").text
    if mattrib is not None:
        mattrib = mattrib.replace("+", "").replace(",", "")
        mattrib =  attributes
        mattrib = mattrib + " -menable-experimental-extensions"
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
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    folder_name = folder
    list_dir = list()
    for fname in os.listdir("."):
        list_dir.append(fname)
    folder = folder_name.split("/")[0]
    path_dir = os.path.dirname(config_variables['TestIntrinsics'].replace(".", ""))
    path_abs = os.path.abspath('tools/').replace("\\", "/")
    path_dir = path_abs + path_dir
    folder_name = os.path.abspath(os.path.split(path_dir)[0])[0:] + "/" + os.path.basename(os.path.dirname(config_variables['TestIntrinsics']))
    folder_name = folder_name.replace("\\", "/")
    count = folder_name.count("tools/")
    if count > 1:
        folder_name = folder_name.replace("tools/", "", 1)
    folder_name = os.path.dirname(__file__).replace("\\", "/")
    if folder_name.endswith("/tests_intrinsics") is False:
        folder_name = folder_name + config_variables['TestIntrinsics'].replace(".", "") + "tests_intrinsics"
        if os.path.exists(folder_name) is False:
            os.makedirs(folder_name)
            os.chmod(folder_name, 0o777)
    if os.path.exists(folder_name):
        os.chmod(folder_name, 0o777)
        shutil.rmtree(folder_name, ignore_errors=True)
        os.makedirs(folder_name)
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
                    "#include " + '"' + include_path + "/" + header_name_cpy.rsplit("/")[-1] + '"' + "\n\n"
                )
            else:
                include_lib = (
                    "#include "
                    + '"'
                    + include_path + "/" + config_variables["BuiltinHeader"].rsplit("/")[-1]
                    + '"'
                    + "\n\n"
                )
            array_results = "int *results_" + customize_name.replace("__", "").replace(
                ".", "_"
            )
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
            legalDisclaimer.get_copyright(folder_name + "/" + file_name)
            f = open(folder_name + "/" + file_name, "a")
            f.write(
                include_lib
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
    f = open(file_name, "a")
    legalDisclaimer.get_copyright(file_name)
    f.write(content + definition)
    f.close()


## This function will generate register pairs
#
# @param file_name This parameter indicates the file in which the content will be written
# @return The function returns a file containing the definitions for register pairs
def generate_register_pairs(file_name):
    config_variables = config.config_environment(config_file, llvm_config)
    instrfield_data_ref = adl_parser.get_instrfield_offset(config_variables["ADLName"])[1]
    calling_convention_order = config_variables["RegisterAllocationOrder"]
    registers = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    calling_convention_pairs = dict()
    alias_dict = adl_parser.get_alias_for_regs(config_variables["ADLName"])
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
        for register_cc in calling_convention_order.keys():
            for calling_convention_seq in calling_convention_order[register_cc]:
                if type(calling_convention_seq) == tuple:
                    calling_convention_seq = calling_convention_seq[0]
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
    index_dummy = 0
    for register in registers.keys():
        register_pair_check = False
        for register_pair in register_pairs.keys():
            for element in register_pairs[register_pair]:
                if element in instrfield_data_ref.keys() and instrfield_data_ref[element]['ref'] == register.upper():
                    register_pair_check = True
                    break
        if register_pair_check is True:
            prefix = registers[register].prefix
            if registers[register].calling_convention is not None and prefix.upper() + str(index_dummy) in registers[register].calling_convention.keys():
                if registers[register].calling_convention[prefix.upper() + str(index_dummy)][0] == 'Hard_wired_zero':
                        if register in config_variables['RegisterClassWrapper']['RISCVRegisterClass']:
                            def_dummy_reg_pair = "def DUMMY_REG_PAIR_WITH_" + prefix.upper() + str(index_dummy) + " : RISCVReg<" + str(index_dummy) + ", " + "\"" + str(index_dummy) + "\"" + ">;\n"
                            def_add_dummy = "def " + register.upper() + "All : " + register.upper() + "RegisterClass<(\n"
                            def_add_dummy += "\tadd " + register.upper() + ", DUMMY_REG_PAIR_WITH_" + prefix.upper() + str(index_dummy) + "\n\t)>;\n"
                        else:
                            def_dummy_reg_pair = "def DUMMY_REG_PAIR_WITH_" + prefix.upper() + str(index_dummy) + " : RISCVReg<" + str(index_dummy) + ", " + "\"" + str(index_dummy) + "\"" + ">;\n"
                            def_add_dummy = "def " + register.upper() + "All : " + "RegisterClass<" + "\"" + config_variables['Namespace'] + "\"" + ", " + "[" + config_variables['XLenVT_key'] + "]" + ", " + config_variables['LLVMRegBasicWidth'] + ", " + "(\n"
                            def_add_dummy += "\tadd " + register.upper() + ", DUMMY_REG_PAIR_WITH_" + prefix.upper() + str(index_dummy) + "\n\t)> {\n"
                            def_add_dummy += "\tlet RegInfos = " + config_variables["XLenRI_key"] + ";\n"
                            def_add_dummy += "}"
    reg_pair_content = ""
    check_reg_pair = False
    for register in registers.keys():
        register_pair_check = False
        for register_pair in register_pairs.keys():
            for element in register_pairs[register_pair]:
                if element in instrfield_data_ref.keys() and instrfield_data_ref[element]['ref'] == register.upper():
                    register_pair_check = True
                    break
        if register_pair_check is True:
            check_register = False
            reg_pair_def = ""
            if 'RegisterClassDisabledABI' in config_variables.keys():
                if register.upper() not in config_variables['RegisterClassDisabledABI']:
                    reg_pair_def = "let RegAltNameIndices = [" + config_variables["RegAltNameIndex"] + "] in {\n"
            else:
                reg_pair_def = "let RegAltNameIndices = [" + config_variables["RegAltNameIndex"] + "] in {\n"
            if registers[register].prefix != "":
                prefix = registers[register].prefix
            for index in range(0, int(config_variables['LLVMRegBasicWidth']) - 1, 2):
                subreg_list = list()
                reg_odd = ""
                reg_even = ""
                alias = ""
                if registers[register].calling_convention is not None and prefix.upper() + str(index) in registers[register].calling_convention.keys():
                    if registers[register].calling_convention[prefix.upper() + str(index)][0] == 'Hard_wired_zero':
                        subreg_list.append(prefix.upper() + str(index))
                        reg_even = prefix.upper() + str(index)
                        reg_odd = prefix.upper() + str(index)
                        subreg_list.append("DUMMY_REG_PAIR_WITH_" + prefix.upper() + str(index))
                    else:
                        subreg_list.append(prefix.upper() + str(index))
                        reg_even = prefix.upper() + str(index)
                        subreg_list.append(prefix.upper() + str(index + 1))
                        reg_odd = prefix.upper() + str(index + 1)
                    elem_reg_key = str(index)
                    if alias == "":
                        if register in alias_dict.keys():
                            for ref_key in alias_dict[register].keys():
                                if ref_key == elem_reg_key:
                                    for key_reg in alias_dict[register][elem_reg_key]:
                                        if prefix not in key_reg:
                                            alias +=  "\"" + key_reg +  "\"" + ", "
                                    alias = alias.rstrip(", ")
                if reg_odd != "" and reg_even != "" and alias != "":
                    check_reg_pair = True
                    check_register = True
                    reg_pair_content += "\tdef " + reg_even + "_" + reg_odd + " : RISCVRegWithSubRegs<" + str(index) + ", " + "\"" +  reg_even + "\"" + ", " + str(subreg_list).replace("'", "") + ", " + "[" + alias + "]" + ">" + " {\n"
                    reg_pair_content += "\t\tlet SubRegIndices = [sub_gpr_even, sub_gpr_odd];\n"
                    reg_pair_content += "\t\tlet CoveredBySubRegs = 1;\n"
                    reg_pair_content += "\t}\n"
            if check_register is True:
                reg_pair_content += "}\n"
    f = open(file_name, "a")
    if check_reg_pair is True:
        f.write(def_dummy_reg_pair)
        f.write(def_add_dummy)
        f.write("\n")
        f.write(reg_pair_def)
        f.write(reg_pair_content)
        f.write("\n\n")
    f.close()
    register_pair_app_ins = dict()
    register_pair_app_outs = dict()
    instrfield_ref = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    max_out = 0
    max_in = 0
    for instruction in instructions.keys():
        for register in instrfield_ref:
            register_pair_app_ins[register] = int(0)
            register_pair_app_outs[register] = int(0)
        outs = str(instructions[instruction]["outputs"])
        ins = str(instructions[instruction]["inputs"])
        outs = re.split(r"[()]", outs)
        ins = re.split(r"[()]", ins)
        for element in ins:
            for instrfield in instrfield_ref:
                if instrfield == element.split(".")[0].rstrip(" "):
                    if register_pair_app_ins[instrfield] == 0:
                        register_pair_app_ins[instrfield] += 1
                        if instrfield not in ins:
                            ins.append(instrfield)
                    else:
                        element = element.replace(" ", "")
                        if "+1" in element:
                            register_pair_app_ins[instrfield] += 1
                            if instrfield not in ins:
                                ins.append(instrfield)
                else:
                    if instrfield == element.split(" ")[0].rstrip(" "):
                        element = element.replace(" ", "")
                        if "+1" in element:
                            register_pair_app_ins[instrfield] += 1
                            if instrfield not in ins:
                                ins.append(instrfield)
        ins.sort()
        outs_copy = outs.copy()
        outs_copy.sort()
        for element in outs_copy:
            for instrfield in instrfield_ref:
                if instrfield == element.split(".")[0].rstrip(" "):
                    if register_pair_app_outs[instrfield] == 0:
                        register_pair_app_outs[instrfield] += 1
                        if instrfield not in outs:
                            outs.append(instrfield)
                    else:
                        element = element.replace(" ", "")
                        if "+1" in element:
                            register_pair_app_outs[instrfield] += 1
                            if instrfield not in outs:
                                outs.append(instrfield)
                else:
                    if instrfield == element.split(" ")[0].rstrip(" "):
                        element = element.replace(" ", "")
                        if "+1" in element:
                            register_pair_app_outs[instrfield] += 1
                            if instrfield not in outs:
                                outs.append(instrfield)
        outs.sort()
        for element in register_pair_app_outs.keys():
            if register_pair_app_outs[element] > max_out:
                max_out = register_pair_app_outs[element]
        for element in register_pair_app_ins.keys():
            if register_pair_app_ins[element] > max_in:
                max_in = register_pair_app_ins[element]
        register_pair_app_outs.clear()
        register_pair_app_ins.clear()
    reg_pair_max = max(max_in, max_out)
    register_class_defined = ""
    registers = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    if 'RegisterClassChild' in config_variables.keys():
            if 'RegisterClassName' in config_variables['RegisterClassChild'].keys():
                register_class_defined = config_variables['RegisterClassChild']['RegisterClassName']
    if register_class_defined == "":
        for register in calling_convention_pairs.keys():
            value_type = "i" + str(2 ** (int(register_width) + reg_pair_max - 1))
            vector_type = "v" + str(reg_pair_max) + "i" + str(2 ** int(register_width))
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
                + value_type + ", "
                + vector_type
                + "]"
                + ", "
                + str(2 ** (int(register_width) + reg_pair_max - 1))
                + ", ("
                + "\n"
                + "\t"
            )
            content = "add" + " "
            position = 0
            for element in calling_convention_pairs[register]:
                pattern = r'[\d+\d*]'
                index = ""
                list_pattern = re.findall(pattern, element)
                index = "".join(list_pattern)
                if index != "":
                    first_index = index
                    if int(index) == 0: 
                        pair_element = element.replace(first_index, str(index))
                    else:
                        index = int(index) + 1
                        pair_element = element.replace(first_index, str(index))
                    content += element + "_" + pair_element + ", "
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
    else:
        for register in calling_convention_pairs.keys():
            value_type = "i" + str(2 ** (int(register_width) + reg_pair_max - 1))
            vector_type = "v" + str(reg_pair_max) + "i" + str(2 ** int(register_width))
            statement = (
                "def "
                + register
                + " : "
                + register_class_defined + "<"
                + "["
                + value_type + ", "
                + vector_type 
                + "]"
                + ", "
                + str(2 ** (int(register_width) + reg_pair_max - 1))
                + ", ("
                + "\n"
                + "\t"
            )
            content = "add" + " "
            position = 0
            for element in calling_convention_pairs[register]:
                pattern = r'[\d+\d*]'
                index = ""
                list_pattern = re.findall(pattern, element)
                index = "".join(list_pattern)
                if index != "":
                    first_index = index
                    if int(index) == 0: 
                        pair_element = element.replace(first_index, str(index))
                    else:
                        index = int(index) + 1
                        pair_element = element.replace(first_index, str(index))
                    content += element + "_" + pair_element + ", "
                    position += 1
                    if position % 4 == 0:
                        if position < len(calling_convention_pairs[register]):
                            content += "\n"
                        content += "\t"
            content = content.rstrip("\t")
            content = content.rstrip(", ")
            content += "\n\t)>;\n"
            let_reg_info = "let RegInfos = " + config_variables['RegInfosPair'] + ",\n"
            for register_class in registers.keys():
                if register_class in register:
                    if "P" in register:
                        register_class += "P"
                    let_decoder_namespace = "\tDecoderMethod =" + "\"Decode" + register + "RegisterClass\"" + " in \n"
                    break
            statement = let_reg_info + let_decoder_namespace + statement
            def_class = statement + content
            comment = "// Register Class " + register + " : Register Pair\n"
            def_class = comment + def_class
            f = open(file_name, "a")
            f.write(def_class)
            f.write("\n\n")
            f.close()

## Function which generates scheduling tests based on the information from scheduling table parsed from XML
#
# @param path string specifying the path to the actual folder in which tests will be generated
# @param extension_list list specifying which extensions are enabled by the user
# @return Scheduling tests for the instructions parsed from XML
def generate_sched_tests(path, extension_list):
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    scheduling_table_dict = adl_parser.parse_sched_table_from_adl(config_variables["ADLName"])
    instrfield_imm = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
    register_parsed = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    instrfields = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    instructions_aliases = adl_parser.parse_instructions_aliases_from_adl(
        config_variables["ADLName"]
    )
    instrfield_data_ref = adl_parser.get_instrfield_offset(config_variables["ADLName"])[1]
    folder_name = os.path.dirname(__file__).replace("\\", "/") + config_variables['TestScheduling'].replace(".", "")
    path = folder_name
    if path.endswith("/"):
        path = path + "tests"
    else:
        path = path + "/tests"
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
    if os.path.exists(path) is False:
        os.makedirs(path)
        os.chmod(path, 0o777)
    path_dependency = path.replace(os.path.basename(os.path.normpath(path)), os.path.basename(os.path.normpath(path)) + "_dependency/")                                   
    sched_parameters = adl_parser.parse_scheduling_model_params(config_variables['ADLName'])
    if os.path.exists(path_dependency):
        shutil.rmtree(path_dependency, ignore_errors=True)
    if not os.path.exists(path_dependency):
        os.makedirs(path_dependency)
        os.chmod(path_dependency, 0o777)
    for instr in instructions.keys():
        extension_checked = False
        scheduling_list_app = dict()
        scheduling_list_app_non = dict()
        scheduling_tests_list = list()
        scheduling_tests_list_dep = list()
        data_test = dict()
        test_content_display = ""
        test_content_display_non = ""
        for sched_key in scheduling_table_dict.keys():
            for key_instr in scheduling_table_dict[sched_key].keys():
                if 'instruction_list' in scheduling_table_dict[sched_key][key_instr].keys():
                    if 'latency' in scheduling_table_dict[sched_key][key_instr].keys():
                        for element in scheduling_table_dict[sched_key][key_instr]['instruction_list']:
                            if instr == element.lower() and 'aliases' not in instructions[instr].keys():
                                syntax = instructions[instr]['syntax']
                                while '' in syntax:
                                    syntax.remove('')
                                inputs = instructions[instr]['inputs']
                                outputs = instructions[instr]['outputs']
                                destination_reg = ""
                                destination_dependency = ""
                                destinations_list = list()
                                run_llvm_mca = "// RUN: %llvm-mca -mtriple=riscv32 -mattr="" -mcpu=" + sched_key + " " + "-timeline --timeline-max-cycles=0 -iterations=1"
                                run_compare = "// RUN: cat %s.txt | %filecheck %s\n"
                                destination_ref = ""
                                for index in range(0, 2):
                                    random.seed(len(instr) + index)
                                    sources_list = list()
                                    imms_list = list()
                                    sources_imms_list = list()
                                    destination_fixed = False
                                    source_field = ""
                                    for element in syntax[1:]:
                                        element_not_found = False
                                        if element_not_found is False:
                                            for output_element in outputs:
                                                if element in output_element:
                                                    if output_element not in inputs:
                                                        for key in reg_instrfields.keys():
                                                            if element in reg_instrfields[key]:
                                                                if destination_fixed is False:
                                                                    destination_field = key
                                                                    destination_fixed = True
                                                                    element_not_found = True
                                                                break
                                                        for register in register_parsed.keys():
                                                            if element in register_classes[register]:
                                                                if destination_field == "" and register_parsed[key].pseudo != "":
                                                                    destination_field = register_parsed[key].pseudo
                                                        if destination_field != "":
                                                            if len(instrfields_values[destination_field]) > 0:
                                                                destination_reg = random.choice(instrfields_values[destination_field])
                                                                numbers = re.findall(r'\d+\d*', destination_reg)
                                                                while "".join(numbers) != "" and int("".join(numbers)) % 2:
                                                                    destination_reg = random.choice(instrfields_values[destination_field])
                                                                    numbers = re.findall(r'\d+\d*', destination_reg)
                                                                alias = alias_register_dict[destination_reg]
                                                                destination_reg = alias
                                                                destinations_list.append(destination_reg)
                                                                destination_regclass = destination_field
                                                                if destination_dependency == "":
                                                                    destination_dependency = destination_reg
                                                                if index >= 1 and destination_dependency == destination_reg:
                                                                    destination_reg = random.choice(instrfields_values[destination_field])
                                                                    numbers = re.findall(r'\d+\d*', destination_reg)
                                                                    while "".join(numbers) != "" and int("".join(numbers)) % 2:
                                                                        destination_reg = random.choice(instrfields_values[destination_field])
                                                                        numbers = re.findall(r'\d+\d*', destination_reg)
                                                                    alias = alias_register_dict[destination_reg]
                                                                    destination_reg = alias
                                                                    destinations_list.append(destination_reg)
                                                                    destination_regclass = destination_field
                                                            break
                                        if element_not_found is False:
                                            for input_element in inputs:
                                                if element in input_element:
                                                    for key in reg_instrfields.keys():
                                                        if element in reg_instrfields[key]:
                                                            source_field = key
                                                            element_not_found = True
                                                            break
                                                    for register in register_parsed.keys():
                                                            if element in register_classes[register]:
                                                                if source_field == "":
                                                                    if register in register_parsed.keys() and register_parsed[register].pseudo != "":
                                                                        source_field = register_parsed[register].pseudo
                                                    if source_field in reg_instrfields.keys():
                                                        if len(instrfields_values[source_field]) > 0:
                                                            source_reg = random.choice(instrfields_values[source_field])
                                                            numbers = re.findall(r'\d+\d*', source_reg)
                                                            while "".join(numbers) != "" and int("".join(numbers)) % 2:
                                                                source_reg = random.choice(instrfields_values[source_field])
                                                                numbers = re.findall(r'\d+\d*', source_reg)
                                                            alias = alias_register_dict[source_reg]
                                                            source_reg = alias
                                                            if source_reg not in sources_list:
                                                                if source_reg != destination_reg and source_reg not in destinations_list:
                                                                    sources_list.append(source_reg.lower())
                                                                    break
                                                                else:
                                                                    source_reg = random.choice(instrfields_values[source_field])
                                                                    numbers = re.findall(r'\d+\d*', source_reg)
                                                                    while "".join(numbers) != "" and int("".join(numbers)) % 2:
                                                                        source_reg = random.choice(instrfields_values[source_field])
                                                                        numbers = re.findall(r'\d+\d*', source_reg)
                                                                    alias = alias_register_dict[source_reg]
                                                                    source_reg = alias
                                                                    if source_reg not in sources_list and source_reg not in destinations_list:
                                                                        sources_list.append(source_reg.lower())
                                                                        break
                                                            else:
                                                                source_reg = random.choice(instrfields_values[source_field])
                                                                numbers = re.findall(r'\d+\d*', source_reg)
                                                                while "".join(numbers) != "" and int("".join(numbers)) % 2:
                                                                    source_reg = random.choice(instrfields_values[source_field])
                                                                    numbers = re.findall(r'\d+\d*', source_reg)
                                                                alias = alias_register_dict[source_reg]
                                                                source_reg = alias
                                                                if source_reg != destination_reg and source_reg not in destinations_list:
                                                                    sources_list.append(source_reg.lower())
                                                                    break
                                                                else:
                                                                    source_reg = random.choice(instrfields_values[source_field])
                                                                    numbers = re.findall(r'\d+\d*', source_reg)
                                                                    while "".join(numbers) != "" and int("".join(numbers)) % 2:
                                                                        source_reg = random.choice(instrfields_values[source_field])
                                                                        numbers = re.findall(r'\d+\d*', source_reg)
                                                                    alias = alias_register_dict[source_reg]
                                                                    source_reg = alias
                                                                    if source_reg not in sources_list and source_reg not in destinations_list:
                                                                        sources_list.append(source_reg.lower())
                                                                        break
                                        if element_not_found is False:    
                                            for imm in instrfield_imm:
                                                if imm == element.split("(")[0]:
                                                    reg = element.replace(imm, "")
                                                    for input_element in inputs:
                                                        if reg.replace("(", "").replace(")", "") in input_element:
                                                            for key in reg_instrfields.keys():
                                                                if reg.replace("(", "").replace(")", "") in reg_instrfields[key]:
                                                                    source_field = key
                                                                    element_not_found = True
                                                                    break
                                                        else:
                                                            for instrfield in instrfields.keys():
                                                                for key_value in instrfields[instrfield]['aliases'].keys():
                                                                    if reg.replace("(", "").replace(")", "") in instrfields[instrfield]['aliases'][key_value]:
                                                                        source_field = key
                                                                        element_not_found = True
                                                                        break
                                                    if reg != "" and source_field != "":
                                                        if source_field in reg_instrfields.keys():
                                                            if len(instrfields_values[source_field]):
                                                                reg_value = random.choice(instrfields_values[source_field])
                                                                checked = False
                                                                for key in register_parsed.keys():
                                                                    prefix = register_parsed[key].prefix
                                                                    size = register_parsed[key].size
                                                                    offset = int(0)
                                                                    if reg.replace("(", "").replace(")", "") in instrfields.keys():
                                                                        offset = int(instrfields[reg.replace("(", "").replace(")", "")]['offset'])
                                                                        width = int(2 ** int(instrfields[reg.replace("(", "").replace(")", "")]['width']))
                                                                    index_reg = 0
                                                                    if prefix != "":
                                                                        if prefix.upper() in reg_value:
                                                                            register_value = reg_value.replace(prefix.upper(), "")
                                                                            while int(register_value) < offset or int(register_value) >= width + offset:
                                                                                reg_value = random.choice(instrfields_values[source_field])
                                                                                register_value = reg_value.replace(prefix.upper(), "")
                                                                            while checked is False and index_reg <= int(size):
                                                                                for input in inputs:
                                                                                    if key + "(" + str(register_value) + ")" in input:
                                                                                        reg_value = prefix.upper() + str(register_value)
                                                                                        checked = True
                                                                                        break
                                                                                else:
                                                                                    register_value = index_reg
                                                                                    index_reg += 1
                                                                alias = alias_register_dict[reg_value]
                                                                reg_value = alias
                                                                if instrfield_imm[imm]['shift'] != '0':
                                                                    imm_value = int(instrfield_imm[imm]['shift'])
                                                                    imm_value = 2 ** imm_value
                                                                    if 'one_extended' in instrfield_imm[imm].keys():
                                                                        if instrfield_imm[imm]['one_extended'] == 'true':
                                                                            imm_value = str("-" + str(imm_value))
                                                                        else:
                                                                            imm_value = (str(imm_value))
                                                                    else:
                                                                        imm_value = str(imm_value)
                                                                else:
                                                                    imm_value = str(2)
                                                                source_reg = element.replace(imm, imm_value).replace(reg, "(" + reg_value + ")")
                                                                if source_reg not in imms_list:
                                                                    if source_reg != destination_reg:
                                                                        imms_list.append(source_reg.lower())
                                                                    else:
                                                                        if len(instrfields_values[source_field]) > 0:
                                                                            source_reg = random.choice(instrfields_values[source_field])
                                                                            numbers = re.findall(r'\d+\d*', source_reg)
                                                                        while "".join(numbers) != "" and int("".join(numbers)) % 2:
                                                                            if len(instrfields_values[source_field]) > 0:
                                                                                source_reg = random.choice(instrfields_values[source_field])
                                                                                numbers = re.findall(r'\d+\d*', source_reg)
                                                                        alias = alias_register_dict[reg_value]
                                                                        source_reg = alias
                                                                        if source_reg not in imms_list:
                                                                            imms_list.append(source_reg.lower())
                                                                else:
                                                                    source_reg = random.choice(instrfields_values[source_field])
                                                                    numbers = re.findall(r'\d+\d*', source_reg)
                                                                    while "".join(numbers) != "" and int("".join(numbers)) % 2:
                                                                        if len(instrfields_values[source_field]) > 0:
                                                                            source_reg = random.choice(instrfields_values[source_field])
                                                                            numbers = re.findall(r'\d+\d*', source_reg)
                                                                    alias = alias_register_dict[reg_value]
                                                                    source_reg = alias
                                                                    if source_reg != destination_reg:
                                                                        imms_list.append(source_reg.lower())
                                                                    else:
                                                                        if len(instrfields_values[source_field]) > 0:
                                                                            source_reg = random.choice(instrfields_values[source_field])
                                                                            numbers = re.findall(r'\d+\d*', source_reg)
                                                                            while "".join(numbers) != "" and int("".join(numbers)) % 2:
                                                                                if len(instrfields_values[source_field]) > 0:
                                                                                    source_reg = random.choice(instrfields_values[source_field])
                                                                                    numbers = re.findall(r'\d+\d*', source_reg)
                                                                            alias = alias_register_dict[reg_value]
                                                                            source_reg = alias
                                                                            if source_reg not in imms_list:
                                                                                imms_list.append(source_reg.lower())
                                                    else:
                                                        if 'aliases' in instrfield_imm[imm].keys():
                                                            if instrfield_imm[imm]['aliases'] != {}:
                                                                for key in instrfield_imm[imm]['aliases'].keys():
                                                                    imms_list.append(instrfield_imm[imm]['aliases'][key][0])
                                                                    break
                                                            else:
                                                                if instrfield_imm[imm]['shift'] != '0':
                                                                    value = int(instrfield_imm[imm]['shift'])
                                                                    value = 2 ** value
                                                                    if 'one_extended' in instrfield_imm[imm].keys():
                                                                        if instrfield_imm[imm]['one_extended'] == 'true':
                                                                            imms_list.append(str("-" + str(value)))
                                                                        else:
                                                                            imms_list.append(str(value))
                                                                    else:
                                                                        imms_list.append(str(value))
                                                                else:
                                                                    imms_list.append(str(2))
                                        if element_not_found is False:
                                            if element not in outputs:
                                                if element not in instrfield_imm:
                                                    for key in reg_instrfields.keys():
                                                        for output in outputs:
                                                            if key in output:
                                                                register = output.split(key)[1]
                                                                prefix = register_parsed[key].prefix
                                                                if prefix != "":
                                                                    register = prefix + register.replace("(", "").replace(")", "").replace("?", "")
                                                                    if register.upper() in alias_register_dict:
                                                                        alias = alias_register_dict[register.upper()]
                                                                        if alias in syntax[1:]:
                                                                            destination_reg = alias
                                                                            break
                                        if element_not_found is False:
                                            if element not in inputs:
                                                if element not in instrfield_imm:
                                                    for key in reg_instrfields.keys():
                                                        for input in inputs:
                                                            if key in input:
                                                                register = input.split(key)[1]
                                                                prefix = register_parsed[key].prefix
                                                                if prefix != "":
                                                                    register = prefix + register.replace("(", "").replace(")", "").replace("?", "")
                                                                    if register.upper() in alias_register_dict:
                                                                        alias = alias_register_dict[register.upper()]
                                                                        if alias in syntax[1:]:
                                                                            if alias not in sources_list and alias != destination_reg and alias not in destinations_list:
                                                                                sources_list.append(alias)
                                                                                break
                                        for element in imms_list:
                                            if element not in sources_imms_list:
                                                sources_imms_list.append(element)
                                                imms_list = list()
                                            elif element in sources_imms_list:
                                                if len(sources_imms_list) < (len(syntax) -1):
                                                    sources_imms_list.append(element)
                                        for element in sources_list:
                                            if element not in sources_imms_list:
                                                sources_imms_list.append(element)
                                    test_started = False
                                    if destination_reg != "":
                                        for element_syntax in syntax[1:]:
                                            if element_syntax in instrfield_data_ref.keys():
                                                if 'enumerated' in instrfield_data_ref[element_syntax].keys():
                                                    for _ in instrfield_data_ref[element_syntax]['enumerated'].keys():
                                                        if destination_reg.lower() in instrfield_data_ref[element_syntax]['enumerated'][_]:
                                                            test_content = syntax[0] + " " + destination_reg.lower() + ", "
                                                            regex_content = syntax[0] + " " + r'{{\-*\{*[0-9]*[a-z]*\,*\(*[a-z]*[0-9]*\-*\+*\)*[a-z]*\}*}}' + ", "
                                                            test_started = True
                                                            break
                                            else:
                                                for input in inputs:
                                                    for register in register_parsed.keys():
                                                        if register.upper() in input:
                                                            input = input.replace(register.upper(), "")
                                                            input = input.replace("(", "").replace(")", "")
                                                            for _ in instrfield_data_ref.keys():
                                                                if 'enumerated' in instrfield_data_ref[_].keys():
                                                                    if input.strip("?") in instrfield_data_ref[_]['enumerated'].keys():
                                                                        if destination_reg.lower() in instrfield_data_ref[_]['enumerated'][input.strip("?")]:
                                                                            test_content = syntax[0] + " " + destination_reg.lower() + ", "
                                                                            regex_content = syntax[0] + " " + r'{{\-*\{*[0-9]*[a-z]*\,*\(*[a-z]*[0-9]*\-*\+*\)*[a-z]*\}*}}' + ", "
                                                                            test_started = True
                                                                            break
                                    else:
                                        test_content = syntax[0] + " "
                                        regex_content = syntax[0] + " "
                                    if test_started is False:
                                        test_content = syntax[0] + " "
                                        regex_content = syntax[0] + " "
                                    if index == 0:
                                        test_content_copy = test_content
                                    index_value = 0
                                    for element in syntax[1:]:
                                        if element in instrfield_imm.keys():
                                            for value in instrfield_imm[element]['aliases'].keys():
                                                if sources_imms_list[index_value] not in instrfield_imm[element]['aliases'][value]:
                                                    if len(sources_imms_list) > len(syntax[1:]):
                                                        sources_imms_list.remove(sources_imms_list[index_value])
                                                        break
                                            index_value += 1
                                    index_value = -1
                                    for element in syntax[1:]:
                                        if index_value < len(sources_imms_list)-1:
                                            index_value += 1
                                        check = False 
                                        if element in instrfield_imm.keys():
                                            value_replaced = ""
                                            for value in instrfield_imm[element]['aliases'].keys():
                                                index_replaced = random.choice(list(instrfield_imm[element]['aliases'].keys()))
                                                value_replaced = instrfield_imm[element]['aliases'][index_replaced][0]
                                                while value_replaced in sources_imms_list:
                                                    index_replaced = random.choice(list(instrfield_imm[element]['aliases'].keys()))
                                                    value_replaced = instrfield_imm[element]['aliases'][index_replaced][0]
                                            if len(instrfield_imm[element]['aliases'].values()) > 0:
                                                if sources_imms_list[index_value] and sources_imms_list[index_value] not in instrfield_imm[element]['aliases'].values():
                                                    if len(sources_imms_list) == len(syntax[1:]):
                                                        sources_imms_list.remove(sources_imms_list[index_value])
                                                        sources_imms_list.insert(index_value, value_replaced)
                                    test_content_elements = list()
                                    for source in sources_imms_list:
                                        test_content_elements.append(source)
                                        if "-" in source and source.replace("-", "+") in test_content_elements:
                                            source_reg = source.replace("-", "")
                                            test_content += source_reg + ", "
                                            test_content_elements.remove(source)
                                            test_content_elements.append(source_reg)
                                        elif "+" in source and source.replace("+", "-") in test_content_elements:
                                            source_reg = source.replace("+", "-")
                                            test_content += source_reg + ", "
                                            test_content_elements.remove(source)
                                            test_content_elements.append(source_reg)
                                        else:
                                            test_content += source + ", "
                                        if index > 0 and test_content_copy.split(",")[0].replace(instr, "").strip(" ") != "":
                                            if source == test_content_copy.split(",")[0].replace(instr, "").strip(" "):
                                                while source_reg == source:
                                                    if len(instrfields_values[source_field]) > 0:
                                                        source_reg = random.choice(instrfields_values[source_field])
                                                        alias = alias_register_dict[source_reg]
                                                        source_reg = alias
                                                        if "-" in source_reg:
                                                            if source_reg.replace("+", "-") in test_content_elements:
                                                                source_reg = source
                                                        elif "+" in source_reg:
                                                            if source_reg.replace("-", "+") in test_content_elements:
                                                                source_reg = source
                                                test_content = test_content.replace(source, source_reg)
                                        regex_content += r'{{\-*\{*[0-9]*[a-z]*\,*\(*[a-z]*[0-9]*\-*\+*\)*[a-z]*\}*}}' + ", "
                                    test_elements = test_content.rstrip(", ").split(" ")
                                    index_elem = -1
                                    while len(test_elements[1:]) < len(syntax[1:]) and index_elem < len(syntax[1:]):
                                        for element in syntax[1:]:
                                            index_elem += 1
                                            if element in instrfield_data_ref.keys():
                                                element_searched = random.choice(list(instrfield_data_ref[element]['enumerated'].values())[int(instrfield_data_ref[element]['offset']):])
                                                if len(element_searched) > 1:
                                                    prefix = register_parsed[instrfield_data_ref[element]['ref']].prefix
                                                    for element_found in element_searched:
                                                        if prefix in element_found:
                                                            prefix_elem = element_found
                                                            break
                                                    for element_found in element_searched:
                                                        if prefix not in element_found:
                                                            if element_found not in test_elements:
                                                                if len(test_elements[1:]) < len(syntax[1:]):
                                                                    code_element_found = re.sub(r'[a-z]+', '', prefix_elem)
                                                                    if code_element_found != '' and int(code_element_found) % 2 == 0 and element_found not in scheduling_list_app.keys():    
                                                                        test_elements.insert(index_elem+1, element_found)
                                                                        test_elements[0] = test_elements[0].replace(",", "")
                                                                        test_content = test_elements[0] + " " + ", ".join(test_elements[1:]).replace("'", "").replace("[", "").replace("]", "")
                                                                        test_content = test_content.rstrip(" ")
                                                                        regex_content += r'{{\-*\{*[0-9]*[a-z]*\,*\(*[a-z]*[0-9]*\-*\+*\)*[a-z]*\}*}}' + ", "
                                                                        scheduling_list_app[element_found] = 1
                                                                        break
                                    test_content = test_content.rstrip(", ")
                                    regex_content = regex_content.rstrip(", ")
                                    if instr.endswith(".s"):
                                        file_name = path + "/" + "test_" +  instr.replace(".s", "_s") + "_" + instr.replace(".s", "_s") + ".s"
                                    else:
                                        file_name = path + "/" + "test_" +  instr + "_" + instr + ".s"
                                    scheduling_tests_list.append(regex_content)
                                    if len(extension_list) > 0:
                                        for attrib in instructions[instr]['attributes']:
                                            if attrib in extension_list:
                                                extension_checked = True
                                                break
                                    else:
                                        extension_checked = True
                                    test_elements = test_content.split(",")
                                    index_elem_test = 0
                                    for element in test_elements:
                                        index_elem_test +=1
                                        if instr in element:
                                            element = element.replace(instr, "")
                                            element = element.strip(" ")
                                            for syntax_elem in syntax[1:]:
                                                if syntax_elem in instrfield_imm.keys():
                                                    if 'aliases' in instrfield_imm[syntax_elem].keys() and instrfield_imm[syntax_elem]['aliases'] != {}:
                                                        index_list = random.choice(list(instrfield_imm[syntax_elem]['aliases'].keys()))
                                                        if syntax[index_elem_test] in instrfield_data_ref.keys():
                                                            if 'ref' in instrfield_imm[syntax_elem].keys():
                                                                if instrfield_data_ref[syntax[index_elem_test]]['ref'] == instrfield_imm[syntax_elem]['ref']:
                                                                    test_content = test_content.replace(element, instrfield_imm[syntax_elem]['aliases'][index_list][0])
                                                        else:
                                                            if element in instrfield_imm[syntax_elem]['aliases'].values():
                                                                test_content = test_content.replace(element, instrfield_imm[syntax_elem]['aliases'][index_list][0])
                                                if 'latency' in scheduling_table_dict[sched_key][key_instr].keys():
                                                    latency = scheduling_table_dict[sched_key][key_instr]['latency']
                                                throughput_list = list()
                                                if syntax_elem in instrfield_imm.keys():
                                                    if 'aliases' in instrfield_imm[syntax_elem].keys() and instrfield_imm[syntax_elem]['aliases'] != {}:
                                                        index_list = random.choice(list(instrfield_imm[syntax_elem]['aliases'].keys()))
                                                        if 'sizeof(inputs)' in latency:
                                                            latency = latency.replace('sizeof(inputs)', str(len(instrfield_imm[syntax_elem]['aliases'][index_list][0].split(","))))
                                                            latency = eval(str(latency))
                                                        elif 'sizeof(outputs)' in latency:
                                                            latency = latency.replace('sizeof(outputs)', str(len(instrfield_imm[syntax_elem]['aliases'][index_list][0].split(","))))
                                                            latency = eval(str(latency))
                                                        for pipeline in scheduling_table_dict[sched_key][key_instr]['pipelines'].keys():
                                                            throughput = scheduling_table_dict[sched_key][key_instr]['pipelines'][pipeline]['throughput']
                                                            if 'sizeof(inputs)' in throughput:
                                                                throughput = throughput.replace('sizeof(inputs)', str(len(instrfield_imm[syntax_elem]['aliases'][index_list][0].split(","))))
                                                                throughput = eval(throughput)
                                                                throughput_list.append(str(throughput))
                                                            elif 'sizeof(outputs)' in throughput:
                                                                throughput = throughput.replace('sizeof(outputs)', str(len(instrfield_imm[syntax_elem]['aliases'][index_list][0].split(","))))
                                                                throughput = eval(throughput)
                                                                throughput_list.append(str(throughput))
                                                        if instr in aux_scheduling_table_param.keys():
                                                            if int(latency) >  int(aux_scheduling_table_param[instr]['latency']):
                                                                aux_scheduling_table_param[instr] = {'latency' : latency, 'throughput' : throughput_list}
                                                        else:
                                                            aux_scheduling_table_param[instr] = {'latency' : latency, 'throughput' : throughput_list}
                                    if extension_checked is True:
                                        file_name = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', file_name)
                                        f = open(file_name, "a")
                                        if index == 0:
                                            legalDisclaimer.get_copyright(file_name)
                                            f.write(run_llvm_mca + " " + "%s" + " &> %s.txt")
                                            f.write("\n")
                                            f.write(run_compare)
                                            f.write("\n\n")
                                        if ',,' in test_content:
                                            test_content = test_content.replace(",,", ",")
                                        f.write(test_content)
                                        test_content_display_non += test_content + "\n"
                                        f.write("\n")
                                        f.close()
                                    if index < 1:
                                        test_content_dep = test_content
                                        for source in test_content_dep.split(" ")[1:]:
                                            if re.sub(r'[0-9]+\(+\)*', '', source).replace(")", "").strip(", ") in scheduling_list_app.keys():
                                                value = scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', source).replace(")", "").strip(", ")]
                                                scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', source.replace(")", "")).strip(", ")] = value + 1
                                            else:
                                                
                                                scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', source).replace(")", "").strip(", ")] = 1
                                        regex_content_dep = regex_content
                                    else:
                                        destination_register = test_content_dep.split(",")[0].replace(instr, "")
                                        if destination_dependency != "":
                                            if len(sources_list) >= 1:
                                                if destination_regclass == source_field:
                                                    list_index = sources_imms_list.index(sources_list[-1])
                                                    sources_imms_list.remove(sources_list[-1])
                                                    sources_imms_list.insert(list_index, destination_register.lower())
                                                    if re.sub(r'[0-9]+\(+\)*', '', destination_register.lower()).replace(")", "").strip(", ") in scheduling_list_app.keys():
                                                        value = scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', destination_register.lower()).replace(")", "").strip(", ")]
                                                        scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', destination_register.lower()).replace(")", "").strip(", ")] = value + 1
                                                    else:
                                                        scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', destination_register.lower()).replace(")", "").strip(", ")] = 1
                                        test_started = False
                                        if destination_reg != "":
                                            for element_syntax in syntax[1:]:
                                                if element_syntax in instrfield_data_ref.keys():
                                                    if 'enumerated' in instrfield_data_ref[element_syntax].keys():
                                                        for _ in instrfield_data_ref[element_syntax]['enumerated'].keys():
                                                            if destination_reg.lower() in instrfield_data_ref[element_syntax]['enumerated'][_]:
                                                                test_content_dep = syntax[0] + " " + destination_reg.lower() + ", "
                                                                if re.sub(r'[0-9]+\(+\)*', '', destination_reg.lower()).replace(")", "").strip(", ") in scheduling_list_app.keys():
                                                                    value = scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', destination_reg.lower()).replace(")", "").strip(", ")]
                                                                    scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', destination_reg.lower()).replace(")", "").strip(", ")] = value + 1
                                                                else:
                                                                    scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', destination_reg.lower()).replace(")", "").strip(", ")] = 1
                                                                regex_content_dep = syntax[0] + " " + r'{{\-*\{*[0-9]*[a-z]*\,*\(*[a-z]*[0-9]*\-*\+*\)*[a-z]*\}*}}' + ", "
                                                                test_started = True
                                                                break
                                                else:
                                                    for input in inputs:
                                                        for register in register_parsed.keys():
                                                            if register.upper() in input:
                                                                input = input.replace(register.upper(), "")
                                                                input = input.replace("(", "").replace(")", "")
                                                                for _ in instrfield_data_ref.keys():
                                                                    if 'enumerated' in instrfield_data_ref[_].keys():
                                                                        if input.strip("?") in instrfield_data_ref[_]['enumerated'].keys():
                                                                            if destination_reg.lower() in instrfield_data_ref[_]['enumerated'][input.strip("?")]:
                                                                                test_content_dep = syntax[0] + " " + destination_reg.lower() + ", "
                                                                                if re.sub(r'[0-9]+\(+\)*', '', destination_reg.lower()).replace(")", "").strip(", ") in scheduling_list_app.keys():
                                                                                    value = scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', destination_reg.lower()).replace(")", "").strip(", ")]
                                                                                    scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', destination_reg.lower()).replace(")", "").strip(", ")] = value + 1
                                                                                else:
                                                                                    scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', destination_reg.lower()).replace(")", "").strip(", ")] = 1
                                                                                regex_content_dep = syntax[0] + " " + r'{{\-*\{*[0-9]*[a-z]*\,*\(*[a-z]*[0-9]*\-*\+*\)*[a-z]*\}*}}' + ", "
                                                                                test_started = True
                                                                                break        
                                        else:
                                            test_content_dep = syntax[0] + " "
                                            regex_content_dep = syntax[0] + " "
                                        if test_started is False:
                                            test_content_dep = syntax[0] + " "
                                            regex_content_dep = syntax[0] + " "
                                        fields = instructions[instr]['fields']
                                        inputs = instructions[instr]['inputs']
                                        for source in sources_imms_list:
                                            if destination_register not in source:
                                                if "(" in source:
                                                    for element in fields[0]:
                                                        check = True
                                                        if element in instrfields.keys():
                                                            for element_in in inputs:
                                                                if "(" in element_in:
                                                                    if element in element_in.split("(")[1].replace(")", "").replace(" ", "").replace("+1", ""):
                                                                        check = False
                                                                        break
                                                        if check is False:
                                                            if element in instrfields.keys():
                                                                check_instrfield = False
                                                                for elem in instructions[instr]['syntax']:
                                                                    for instrfield in instrfield_imm.keys():
                                                                        if instrfield in elem:
                                                                            if instrfield + "(" + element + ")" == elem:
                                                                                check_instrfield = True
                                                                                source = source.replace(source.split("(")[1], destination_register.strip(" ") + ")")
                                                                            else:
                                                                                check_instrfield = False
                                                                if check_instrfield is True:
                                                                    source = source.replace(source.split("(")[1], destination_register.strip(" ") + ")")
                                            test_content_dep += source + ", "
                                            if re.sub(r'[0-9]+\(+\)*', '', source).replace(")", "").strip(", ") in scheduling_list_app.keys():
                                                value = scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', source).replace(")", "").strip(", ")]
                                                scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', source).replace(")", "").strip(", ")] = value + 1
                                            else:
                                                scheduling_list_app[re.sub(r'[0-9]+\(+\)*', '', source).replace(")", "").strip(", ")] = 1
                                            regex_content_dep += r'{{\-*\{*[0-9]*[a-z]*\,*\(*[a-z]*[0-9]*\-*\+*\)*[a-z]*\}*}}' + ", "
                                        test_elements = test_content_dep.rstrip(", ").split(" ")
                                        index_elem = -1
                                        while len(test_elements[1:]) < len(syntax[1:]) and index_elem < len(syntax[1:]):
                                            for element in syntax[1:]:
                                                index_elem += 1
                                                if element in instrfield_data_ref.keys():
                                                    element_searched = random.choice(list(instrfield_data_ref[element]['enumerated'].values())[int(instrfield_data_ref[element]['offset']):])
                                                    if len(element_searched) > 1:
                                                        prefix = register_parsed[instrfield_data_ref[element]['ref']].prefix
                                                        for element_found in element_searched:
                                                            if prefix in element_found:
                                                                prefix_elem = element_found
                                                                break
                                                        for element_found in element_searched:
                                                            if prefix not in element_found:
                                                                if element_found not in test_elements:
                                                                    if len(test_elements[1:]) < len(syntax[1:]):
                                                                        code_element_found = re.sub(r'[a-z]+', '', prefix_elem)
                                                                        if code_element_found != '' and int(code_element_found) % 2 == 0 and element_found not in scheduling_list_app.keys():    
                                                                            test_elements.insert(index_elem+1, element_found)
                                                                            test_elements[0] = test_elements[0].replace(",", "")
                                                                            test_content_dep = test_elements[0] + " " + ", ".join(test_elements[1:]).replace("'", "").replace("[", "").replace("]", "")
                                                                            test_content_dep = test_content_dep.rstrip(" ")
                                                                            regex_content_dep += r'{{\-*\{*[0-9]*[a-z]*\,*\(*[a-z]*[0-9]*\-*\+*\)*[a-z]*\}*}}' + ", "
                                                                            scheduling_list_app[element_found] = 1
                                                                            break                  
                                        test_content_dep = test_content_dep.rstrip(", ")
                                        regex_content_dep = regex_content_dep.rstrip(", ")
                                    if instr.endswith(".s"):
                                        file_name_dep = path_dependency + "test_" +  instr.replace(".s", "_s") + "_" + instr.replace(".s", "_s") + ".s"
                                    else:
                                        file_name_dep = path_dependency + "test_" +  instr + "_" + instr + ".s"
                                    if extension_checked is True:
                                        f = open(file_name_dep, "a")
                                        if index == 0:
                                            legalDisclaimer.get_copyright(file_name_dep)
                                            f.write(run_llvm_mca + " " + "%s" + " &> %s.txt")
                                            f.write("\n")
                                            f.write(run_compare)
                                            f.write("\n\n")
                                        if ',,' in test_content_dep:
                                            test_content_dep = test_content_dep.replace(",,", ",")
                                        f.write(test_content_dep)
                                        test_content_display += test_content_dep + "\n"
                                        scheduling_tests_list_dep.append(regex_content_dep)
                                        f.write("\n")
                                        f.close()
        scheduling_list_app.clear()
        first = ""
        index = 0
        for element in test_content_display.split("\n"):
            registers = element.split(" ")[1: ]
            if index == 0:
                first = element.split(",")[0].replace(instr, "").strip(" ")
                first = first.strip("\n")
            for elem in element.split(",")[1:]:
                scheduling_list_app[elem.strip(" ")] = 1
            for reg in registers:
                reg = reg.strip(",").strip(" ").replace(instr, "").replace(")", "")
                reg = re.sub(r"\d+\(+", "", reg)
                if reg.isdigit() is False and len(instructions[instr]['syntax']) > 1:
                    destination = instructions[instr]['syntax'][1]
                    if destination in instrfield_data_ref.keys():
                        for instrfield_key in instrfield_data_ref[destination]['enumerated'].keys():
                            if reg in instrfield_data_ref[destination]['enumerated'][instrfield_key]:
                                ref = instrfield_data_ref[destination]['ref']
                                alias_reg = ''
                                if len(register_parsed[ref].alias_reg) > 0:
                                    alias_reg = register_parsed[ref].alias_reg[instrfield_key]
                                    alias_reg = alias_reg.split("#")[1]
                                    if reg not in scheduling_list_app.keys():
                                        if alias_reg != '' and alias_reg not in scheduling_list_app.keys():
                                            scheduling_list_app[reg] = 1
                                            scheduling_list_app[alias_reg] = 1
                                            break
                                        else:
                                            if alias_reg != '' and alias_reg in scheduling_list_app.keys():
                                                scheduling_list_app[reg] = 2
                                                scheduling_list_app[alias_reg] = 2
                                                break
                                else:
                                    if reg not in scheduling_list_app.keys():
                                        if first == reg:
                                            scheduling_list_app[reg] = 1
                                            break
                                    else:
                                        if first == reg:
                                            value = scheduling_list_app[reg]
                                            scheduling_list_app[reg] = value + 1
                                            break
                    else:
                        for _ in instrfield_data_ref.keys():
                            if 'enumerated' in instrfield_data_ref[_].keys():
                                for instrfield_key in instrfield_data_ref[_]['enumerated'].keys():
                                    if reg in instrfield_data_ref[_]['enumerated'][instrfield_key]:
                                        if reg == destination:
                                            if reg not in scheduling_list_app.keys():
                                                scheduling_list_app[reg] = 1
                                                break
                                            else:
                                                value = scheduling_list_app[reg]
                                                scheduling_list_app[reg] = value + 1
                                                break
            index += 1
        scheduling_list_app_non.clear()
        index = 0
        instrfield_data_ref = adl_parser.get_instrfield_offset(config_variables["ADLName"])[1]
        first = ""
        for element in test_content_display_non.split("\n"):
            registers = element.split(" ")[1: ]
            if index == 0:
                first = element.split(",")[0].replace(instr, "").strip(" ")
            for elem in element.split(",")[1:]:
                scheduling_list_app_non[elem.strip(" ")] = 1
            for reg in registers:
                reg = reg.strip(",").strip(" ").replace(instr, "").replace(")", "")
                reg = re.sub(r"\d+\(+", "", reg)
                if reg.isdigit() is False:
                    destination = instructions[instr]['syntax'][1]
                    if destination in instrfield_data_ref.keys():
                        for instrfield_key in instrfield_data_ref[destination]['enumerated'].keys():
                            if reg in instrfield_data_ref[destination]['enumerated'][instrfield_key]:
                                ref = instrfield_data_ref[destination]['ref']
                                alias_reg = ''
                                if len(register_parsed[ref].alias_reg) > 0:
                                    alias_reg = register_parsed[ref].alias_reg[instrfield_key]
                                    alias_reg = alias_reg.split("#")[1]
                                    if reg not in scheduling_list_app_non.keys():
                                        if alias_reg != '' and alias_reg not in scheduling_list_app_non.keys():
                                                scheduling_list_app_non[reg] = 1
                                                scheduling_list_app_non[alias_reg] = 1
                                                break
                                        else:
                                            if alias_reg != '' and alias_reg in scheduling_list_app_non.keys():
                                                    scheduling_list_app_non[reg] = 2
                                                    scheduling_list_app_non[alias_reg] = 2
                                                    break
                                else:
                                    if reg not in scheduling_list_app_non.keys():
                                        if first == reg:
                                            scheduling_list_app_non[reg] = 1
                                            break
                                    else:
                                        if first == reg:
                                            value = scheduling_list_app_non[reg]
                                            scheduling_list_app_non[reg] = value + 1
                                            break
                    else:
                        for _ in instrfield_data_ref.keys():
                            if 'enumerated' in instrfield_data_ref[_].keys():
                                for instrfield_key in instrfield_data_ref[_]['enumerated'].keys():
                                    if reg in instrfield_data_ref[_]['enumerated'][instrfield_key]:
                                        if first == destination:
                                            if reg not in scheduling_list_app_non.keys():
                                                scheduling_list_app_non[reg] = 1
                                                break
                                            else:
                                                value = scheduling_list_app_non[reg]
                                                scheduling_list_app_non[reg] = value + 1
                                                break
            index += 1
        data_test['data-dep'] = scheduling_tests_list_dep
        data_test['no-dep'] = scheduling_tests_list
        sched_app_regs[instr] = scheduling_list_app_non
        sched_app_regs_dep[instr] = scheduling_list_app
        scheduling_tests_struct[instr] = data_test
        
## Function which generates scheduling table description
#
# @file_name string specifying the name given to the file in which scheduling model is generated
# @schedule_file string specifying in which file the resources should be defined
# @return both files presented before with specific content
def generate_scheduling_table(file_name, schedule_file):
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    scheduling_table_dict = adl_parser.parse_sched_table_from_adl(config_variables["ADLName"])
    registers = adl_parser.get_alias_for_regs(config_variables["ADLName"])
    instructions_inputs_outputs = dict()
    latency_list = list()
    file_name = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', file_name)
    for key in instructions.keys():
        inputs_list = list()
        outputs_list = list()
        inputs_dict = dict()
        outputs_dict = dict()
        for register in instructions[key]['inputs']:
            for reg_key in registers.keys():
                if reg_key in register:
                    inputs_list.append(register)
        inputs_dict['inputs'] = inputs_list
        if key not in instructions_inputs_outputs.keys():
            instructions_inputs_outputs[key] = {}
        instructions_inputs_outputs[key].update(inputs_dict)
        for register in instructions[key]['outputs']:
            for reg_key in registers.keys():
                if reg_key in register:
                    outputs_list.append(register)
        outputs_dict['outputs'] = outputs_list
        if key not in instructions_inputs_outputs.keys():
            instructions_inputs_outputs[key] = {}
        instructions_inputs_outputs[key].update(outputs_dict)
    instrfield_ref = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    scheduling_instrfields_dict = dict()
    register_parsed = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    for instruction in instructions.keys():
        inputs = instructions[instruction]['inputs']
        list_instrfields = list()
        for input in inputs:
            check = False
            for instrfield in instrfield_ref.keys():
                x = re.search(instrfield_ref[instrfield]['ref'] + r"\(" + instrfield + r"\)", input.strip(" "))
                if x is not None:
                    list_instrfields.append(instrfield)
                    check = True
                    break
            if check is False:
                for instrfield in instrfield_ref.keys():
                    x = re.search(instrfield_ref[instrfield]['ref'] + r"\(+\w*\+*\d*\)\?*[a-z]*", input.strip(" "))
                    if x is not None:
                        input_elem = input.replace(instrfield_ref[instrfield]['ref'], "").replace("(", "").replace(")", "").replace("?", "").replace("/p", "")
                        prefix = register_parsed[instrfield_ref[instrfield]['ref']].prefix
                        if prefix.upper() + input_elem in alias_register_dict.keys():
                            if alias_register_dict[prefix.upper() + input_elem] in instructions[instruction]['syntax'][1:]:
                                list_instrfields.append(alias_register_dict[prefix.upper() + input_elem])
                                check = True
                                break
        if len(list_instrfields) > 0:
            scheduling_instrfields_dict[instruction] = list_instrfields
    for sched_key in scheduling_table_dict.keys():
        generate_schedule_definition_read = ""
        generate_schedule_definition_write= ""
        for key_instr in scheduling_table_dict[sched_key].keys():
            read_sched_enabled = False
            write_sched_enabled = False
            activate_load = False
            for key in instructions.keys():
                if 'instruction_list' in scheduling_table_dict[sched_key][key_instr].keys():
                    if key in scheduling_table_dict[sched_key][key_instr]['instruction_list']:
                        if len(instructions_inputs_outputs[key]['inputs']):
                            read_sched_enabled = True
                        if len(instructions_inputs_outputs[key]['outputs']):
                            write_sched_enabled = True
                        if 'branch' or 'store' in instructions[key]['attributes']:
                            write_sched_enabled = True
                        if 'load' in instructions[key]['attributes']:
                            activate_load = True
            scheduling_instr_res = dict()
            if write_sched_enabled is True:
                generate_schedule_definition_write += "def " + "Write" + key_instr + " :" + "SchedWrite;\n"
                scheduling_instr_res['write'] = "Write" + key_instr
            if read_sched_enabled is True:
                if activate_load is True:
                    if "def " + "Read" + "MemBase" + " :" + "SchedRead;\n" not in generate_schedule_definition_read:
                        generate_schedule_definition_read += "def " + "Read" + "MemBase" + " :" + "SchedRead;\n"
                    scheduling_instr_res['read'] = "Read" + "MemBase"
                else:
                    generate_schedule_definition_read += "def " + "Read" + key_instr + " :" + "SchedRead;\n"
                    scheduling_instr_res['read'] = "Read" + key_instr
            for key in instructions.keys():
                if 'instruction_list' in scheduling_table_dict[sched_key][key_instr].keys():
                    if key in scheduling_table_dict[sched_key][key_instr]['instruction_list']:
                        if key not in scheduling_instr_info.keys():
                            scheduling_instr_info[key] = scheduling_instr_res
        for sched_key in scheduling_table_dict.keys():
            for sched_class in scheduling_table_dict[sched_key].keys():
                generate_read = ""
                for instruction in scheduling_instrfields_dict.keys():
                    index = 1
                    if instruction in scheduling_table_dict[sched_key][sched_class]['instruction_list']:
                        if len(scheduling_instrfields_dict[instruction]) > 1:
                            for _ in scheduling_instrfields_dict[instruction]:
                                if len(re.findall(r'\d+', sched_class)) > 0:
                                    if read_sched_enabled is True:
                                        if 'store' in instructions[instruction]['attributes']:
                                            if index == 1:
                                                if "def " + "Read" + "StoreData" + " :" + "SchedRead;\n" not in generate_read:
                                                    generate_read += "def " + "Read" + "StoreData" + " :" + "SchedRead;\n"
                                                    index += 1
                                        else:
                                            if "def " + "Read" + sched_class + "_" + str(index) + " :" + "SchedRead;\n" not in generate_read:
                                                generate_read += "def " + "Read" + sched_class + "_" + str(index) + " :" + "SchedRead;\n"
                                                index += 1
                                else:
                                    if read_sched_enabled is True:
                                        if 'store' in instructions[instruction]['attributes']:
                                            if index == 1:
                                                if "def " + "Read" + "StoreData" + " :" + "SchedRead;\n" not in generate_read:
                                                    generate_read += "def " + "Read" + "StoreData" + " :" + "SchedRead;\n"
                                                    index += 1
                                        else:
                                            if "def " + "Read" + sched_class + str(index) + " :" + "SchedRead;\n" not in generate_read:
                                                generate_read += "def " + "Read" + sched_class + str(index) + " :" + "SchedRead;\n"
                                                index += 1
                        if generate_read != "":
                            if 'forwarding' in scheduling_table_dict[sched_key][sched_class].keys():
                                generate_schedule_definition_read = generate_schedule_definition_read.replace("def " + "Read" + sched_class + " :" + "SchedRead;\n", generate_read)                        
        f = open(file_name, "a")
        legalDisclaimer.get_copyright(file_name)
        f.write(generate_schedule_definition_write)
        f.write("\n\n")
        f.write(generate_schedule_definition_read)
        f.close()
        sched_parameters = adl_parser.parse_scheduling_model_params(config_variables['ADLName'])
        sched_statement = "def " + sched_key.upper() + "Model" + " : " + "SchedMachineModel "
        content = "{\n"
        load_latency_list = list()
        max_high_load_latency = list()
        for key in sched_parameters[sched_key].keys():
            if key != "FunctionalUnits" and key != "BufferSize":
                if sched_parameters[sched_key][key] is not None:
                    content += "\t" + "let " + key + " = " + str(sched_parameters[sched_key][key]) + ";\n"
        sched_model_define = "let SchedModel" + " = " + sched_key.upper() + "Model" + " in {\n"
        sched_model_content = ""
        buffersize_dict = dict()
        for parameter in sched_parameters[sched_key].keys():
            if parameter == 'FunctionalUnits':
                for funct_unit in sched_parameters[sched_key][parameter].keys():
                    buffersize_dict[funct_unit] = sched_parameters[sched_key][parameter][funct_unit]['BufferSize']
        inv_map = {}
        for k, v in buffersize_dict.items():
            inv_map[v] = inv_map.get(v, []) + [k]
        for unit in inv_map.keys():
            define_func_unit = ""
            for key in sched_parameters[sched_key].keys():
                if key == "FunctionalUnits":
                    for funct_unit in sched_parameters[sched_key][key].keys():
                        if funct_unit in inv_map[unit]:          
                            define_func_unit += "\tdef " + funct_unit + " : " + "ProcResource<" +  sched_parameters[sched_key][key][funct_unit]['proc_resources'] + ">;\n"
            sched_model_content += "let BufferSize = " + str(unit) + " in {\n"
            sched_model_content += define_func_unit + "}\n"
        sched_model_define += sched_model_content
        latency_list.sort()
        define_write_content = ""
        resource_cycle_list = dict()
        for sched_key in scheduling_table_dict.keys():
            for sched_class in scheduling_table_dict[sched_key].keys():
                define_write = ""
                for key in sched_parameters[sched_key].keys():
                    aux = list()
                    pipeline_list = list()
                    if 'pipelines' in scheduling_table_dict[sched_key][sched_class].keys():
                        for pipeline in scheduling_table_dict[sched_key][sched_class]['pipelines']:
                            pipeline_list.append(pipeline)
                    resource_cycle_list[sched_class] = pipeline_list
                    if key == "FunctionalUnits":
                        if 'pipelines' in scheduling_table_dict[sched_key][sched_class].keys():
                            for pipeline in scheduling_table_dict[sched_key][sched_class]['pipelines']:
                                if pipeline in scheduling_table_dict[sched_key][sched_class]['pipelines'].keys():
                                        define_write = "def : WriteRes<" + "Write" + sched_class + ", " + str(pipeline_list).replace("'", "") + ">;\n"
                        check = False
                        for element in resource_cycle_list.keys():
                            if element == sched_class:
                                for instruction in scheduling_table_dict[sched_key][element]['instruction_list']:
                                    if instruction in aux_scheduling_table_param.keys():
                                        if 'latency' in scheduling_table_dict[sched_key][element].keys():
                                            scheduling_table_dict[sched_key][element]['latency'] = aux_scheduling_table_param[instruction]['latency']
                                    if 'load' in instructions[instruction]['attributes']:
                                        if 'latency' in scheduling_table_dict[sched_key][element].keys():
                                            if str(scheduling_table_dict[sched_key][element]['latency']).isdigit():
                                                load_latency_list.append(int(scheduling_table_dict[sched_key][element]['latency']))
                                                max_high_load_latency.append(int(scheduling_table_dict[sched_key][element]['latency']))
                                if 'latency' in scheduling_table_dict[sched_key][element].keys():
                                    define_write = define_write.replace(";\n", "") + " {\n" + "\tlet Latency = " + str(scheduling_table_dict[sched_key][element]['latency']) + ";\n"
                                throughput_list = list()
                                acquire_list = list()
                                if 'pipelines' in scheduling_table_dict[sched_key][sched_class].keys():
                                    for pipeline in scheduling_table_dict[sched_key][element]['pipelines'].keys():
                                        if pipeline in scheduling_table_dict[sched_key][element]['pipelines'].keys():
                                            if pipeline in scheduling_table_dict[sched_key][element]['pipelines'].keys():
                                                if instruction in aux_scheduling_table_param.keys():
                                                    for elem_throughput in aux_scheduling_table_param[instruction]['throughput']:
                                                        scheduling_table_dict[sched_key][element]['pipelines'][pipeline]['throughput'] = elem_throughput
                                                if str(scheduling_table_dict[sched_key][element]['pipelines'][pipeline]['throughput']).isdigit():
                                                    throughput_list.append(int(scheduling_table_dict[sched_key][element]['pipelines'][pipeline]['throughput']))
                                    for pipeline in scheduling_table_dict[sched_key][element]['pipelines']:
                                        if 'acquire_at_cycles' in scheduling_table_dict[sched_key][element]['pipelines'][pipeline].keys():
                                            acquire_list.append(int(scheduling_table_dict[sched_key][element]['pipelines'][pipeline]['acquire_at_cycles']))
                                if 'pipelines' in scheduling_table_dict[sched_key][sched_class].keys():
                                    define_write += "\tlet ReleaseAtCycles = " + str(throughput_list).replace("'", "") + ";\n"
                                if len(acquire_list) > 0:
                                    define_write += "\tlet AcquireAtCycles = " + str(acquire_list).replace("'", "") + ";\n"
                                if 'single_issue' in scheduling_table_dict[sched_key][sched_class].keys():
                                     define_write += "\tlet SingleIssue = " + scheduling_table_dict[sched_key][sched_class]['single_issue'] + ";\n"
                                if 'num_micro_ops' in scheduling_table_dict[sched_key][sched_class].keys():
                                     define_write += "\tlet NumMicroOps = " + scheduling_table_dict[sched_key][sched_class]['num_micro_ops'] + ";\n"
                                if 'pipelines' in scheduling_table_dict[sched_key][sched_class].keys():
                                    define_write += "}\n"
                                check = True
                                break
                        if check is False:
                            if define_write != "":
                                define_write += "}\n"
                    if define_write != "":
                        define_write_content += define_write
        max_load_latency = ""
        max_high_latency = "" 
        if len(load_latency_list) > 0:
            max_load_latency = min(load_latency_list)
        if len(max_high_load_latency) > 0:
            max_high_latency = max(max_high_load_latency)
        if max_load_latency != "" and max_high_latency != "":
            content += "\t" + "let " + "LoadLatency" + " = " + str(max_load_latency) + ";\n"
            content += "\t" + "let " + "HighLatency" + " = " + str(max_high_latency) + ";\n"
        content += "}\n"
        define_read_content = ""
        class_parsed = list()
        class_dict = dict()      
        for sched_key in scheduling_table_dict.keys():
            for key_instr in scheduling_table_dict[sched_key].keys():
                if 'forwarding' in scheduling_table_dict[sched_key][key_instr].keys():
                    for element in scheduling_table_dict[sched_key][key_instr]['forwarding'].keys():
                        if element not in class_parsed:
                            if 'resource_list' in scheduling_table_dict[sched_key][key_instr]['forwarding'][element].keys() and len(scheduling_table_dict[sched_key][key_instr]['forwarding'][element]['resource_list']) > 0: 
                                class_resource = ""
                                resource_read_list = list() 
                                class_parsed.append(element)
                                if key_instr not in class_dict:
                                    class_dict[key_instr] = element
                                for resource in scheduling_table_dict[sched_key][key_instr]['forwarding'][element]['resource_list']:
                                    resource_read_list.append(resource)
                                class_resource = "class " + element + "<SchedRead read : ReadAdvance<read, " + scheduling_table_dict[sched_key][key_instr]['forwarding'][element]['value'] + ", " + str(resource_read_list).replace("'", "") + ">;\n"
                                define_read_content += class_resource + "\n"
        for sched_key in scheduling_table_dict.keys():
            for sched_class in scheduling_table_dict[sched_key].keys():
                if 'forwarding' in scheduling_table_dict[sched_key][sched_class].keys(): 
                    for element in scheduling_table_dict[sched_key][sched_class]['forwarding'].keys():  
                        if sched_class not in class_dict.keys():
                            for instruction in scheduling_instrfields_dict.keys():
                                index = 1
                                if instruction in scheduling_table_dict[sched_key][sched_class]['instruction_list']:
                                    if len(scheduling_instrfields_dict[instruction]) > 1:
                                        for _ in scheduling_instrfields_dict[instruction]:
                                            if 'store' in instructions[instruction]['attributes']:
                                                if index == 1:
                                                    define_read = "def : ReadAdvance<" + "Read" + "StoreData" + ", " + scheduling_table_dict[sched_key][sched_class]['forwarding'][element]['value'] + ">;\n"         
                                                    index += 1
                                                if index == 2:
                                                    define_read += "def : ReadAdvance<" + "Read" + "MemBase" + ", " + scheduling_table_dict[sched_key][sched_class]['forwarding'][element]['value'] + ">;\n"         
                                                    index += 1
                                                if define_read not in define_read_content:
                                                    define_read_content += define_read    
                                            else:
                                                if len(re.findall(r'\d+', sched_class)) > 0:
                                                    define_read = "def : ReadAdvance<" + "Read" + sched_class + "_" + str(index) + ", " + scheduling_table_dict[sched_key][sched_class]['forwarding'][element]['value'] + ">;\n"         
                                                else:
                                                    define_read = "def : ReadAdvance<" + "Read" + sched_class + str(index) + ", " + scheduling_table_dict[sched_key][sched_class]['forwarding'][element]['value'] + ">;\n"         
                                                index += 1
                                                if define_read not in define_read_content:
                                                    define_read_content += define_read
                                    else:
                                        if 'store' in instructions[instruction]['attributes']:
                                            define_read = "def : ReadAdvance<" + "Read" + "StoreData" + ", " + scheduling_table_dict[sched_key][sched_class]['forwarding'][element]['value'] + ">;\n"         
                                            define_read += "def : ReadAdvance<" + "Read" + "MemBase" + ", " + scheduling_table_dict[sched_key][sched_class]['forwarding'][element]['value'] + ">;\n"         
                                            if define_read not in define_read_content:
                                                define_read_content += define_read    
                                        else:
                                            define_read = "def : ReadAdvance<" + "Read" + sched_class + ", " + scheduling_table_dict[sched_key][sched_class]['forwarding'][element]['value'] + ">;\n"         
                                            if define_read not in define_read_content:
                                                define_read_content += define_read
                        else:
                            define_read = "def : " + class_dict[sched_class] + "<" + "Read" + sched_class +  scheduling_table_dict[sched_key][sched_class]['forwarding'][element]['id'] + ", " + scheduling_table_dict[sched_key][sched_class]['forwarding'][element]['value'] + ">;\n"
                            define_read_content += define_read
                            break
        define_read_content += "}"
        sched_file_name = schedule_file + "RISCVSched" + sched_key.upper() + ".td"
        sched_file_name = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', sched_file_name)
        f = open(sched_file_name, "a")
        legalDisclaimer.get_copyright(sched_file_name)
        f.write(sched_statement + content)
        f.write("\n")
        f.write(sched_model_define)
        f.write("\n")
        f.write(define_write_content)
        f.write("\n")
        f.write(define_read_content)
        f.close()
        
        
## Function which generates scheduling references for scheduling tests
#
# @param path string specifying the path to the actual folder in which the content will be written
# @param extension_list list specifying which extensions are enabled by the user
# @return scheduling references for generated tests
def generate_scheduling_ref(path, extension_list):
    config_variables = config.config_environment(config_file, llvm_config)
    scheduling_table_dict = adl_parser.parse_sched_table_from_adl(config_variables["ADLName"])
    sched_parameters = adl_parser.parse_scheduling_model_params(config_variables['ADLName'])
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    registers = adl_parser.get_alias_for_regs(config_variables["ADLName"])
    instrfield_data_ref = adl_parser.get_instrfield_offset(config_variables["ADLName"])[1]                       
    folder_name = os.path.dirname(__file__).replace("\\", "/") + config_variables['TestScheduling'].replace(".", "")
    path = folder_name
    if path.endswith("/"):
        path = path + "tests"
    else:
        path = path + "/tests"
    instructions_list_generated = list()
    path_dependency = path.replace(os.path.basename(os.path.normpath(path)), os.path.basename(os.path.normpath(path)) + "_dependency")
    for sched in scheduling_table_dict.keys():
        for sched_class in scheduling_table_dict[sched].keys():
            for key in scheduling_tests_struct.keys():
                extension_checked = False
                dual_issue_throughput_activated = False
                if len(scheduling_tests_struct[key]) > 0:
                    if 'instruction_list' in scheduling_table_dict[sched][sched_class].keys():
                        if key in scheduling_table_dict[sched][sched_class]['instruction_list']:
                            if 'latency' in scheduling_table_dict[sched][sched_class].keys():
                                inputs_list = list()
                                outputs_list = list()
                                for register in instructions[key]['inputs']:
                                    for reg_key in registers.keys():
                                        if reg_key in register:
                                            inputs_list.append(register)
                                for register in instructions[key]['outputs']:
                                    for reg_key in registers.keys():
                                        if reg_key in register:
                                            outputs_list.append(register)
                                if key in aux_scheduling_table_param.keys():
                                    scheduling_table_dict[sched][sched_class]['latency'] = aux_scheduling_table_param[key]['latency']
                                if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                    for pipeline in scheduling_table_dict[sched][sched_class]['pipelines'].keys():
                                        if key in aux_scheduling_table_param.keys():
                                            for elem_throughput in aux_scheduling_table_param[key]['throughput']:
                                                scheduling_table_dict[sched][sched_class]['pipelines'][pipeline]['throughput'] = elem_throughput
                                if 'latency' in scheduling_table_dict[sched][sched_class].keys():
                                    if str(scheduling_table_dict[sched][sched_class]['latency']).isdigit():
                                        latency = int(scheduling_table_dict[sched][sched_class]['latency'])
                                reference = ""
                                reference += ""
                                row1 = ""
                                row2 = ""
                                index = 0
                                reference += row1 + "\n" + row2 + "\n"
                                reference_old = row1 + "\n" + row2 + "\n"
                                test = ""
                                test_content_dep = ""
                                throughput = 0
                                if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                    for pipeline in scheduling_table_dict[sched][sched_class]['pipelines']:
                                        if str(scheduling_table_dict[sched][sched_class]['pipelines'][pipeline]['throughput']).isdigit():
                                            throughput += int(scheduling_table_dict[sched][sched_class]['pipelines'][pipeline]['throughput'])
                                for instruction in scheduling_tests_struct[key]['data-dep']:
                                    if key not in instructions_list_generated:
                                        instructions_list_generated.append(key)
                                    if index % 2 == 0 or index == 0:
                                        index = 0
                                        index_list = list()
                                        index_list.append(0)
                                        index_list.append(index)
                                        index_str = str(index_list).replace(" ", "")
                                        index_str += "     "
                                        timeline = "D"
                                        for _ in range(throughput - 1):
                                            timeline += "e"
                                        timeline += "E"
                                        index_str += timeline + "   " + instruction
                                        reference = ""
                                        reference += ""
                                        index = 0
                                        if index == 0 or index % 2 == 0:
                                            reference += "\n" + "// CHECK: " + len('-NEXT') * " " + index_str
                                        test += reference + "\n"
                                        timeline_ref = timeline
                                    else:
                                        index_list = list()
                                        index_list.append(0)
                                        index_list.append(index)
                                        index_str = str(index_list).replace(" ", "")
                                        index_str += "     "
                                        timeline_string = ""
                                        timeline_index = 0
                                        timeline_counter = 0
                                        timeline = ""
                                        if 'latency' in scheduling_table_dict[sched][sched_class].keys():
                                            if str(scheduling_table_dict[sched][sched_class]['latency']).isdigit():
                                                latency = int(int(int(scheduling_table_dict[sched][sched_class]['latency'])))
                                            if 'single_issue' in scheduling_table_dict[sched][sched_class].keys():
                                                dual_issue_throughput_activated = True
                                        if int(sched_parameters[sched]['IssueWidth']) > 1:
                                            for element in sched_app_regs_dep[key]:
                                                if sched_app_regs_dep[key][element] >= 2:
                                                    if element.isdigit() is False:
                                                        destination = instructions[key]['syntax'][1]
                                                        if destination in instrfield_data_ref.keys():
                                                            for instrfield_key in instrfield_data_ref[destination]['enumerated'].keys():
                                                                if element in instrfield_data_ref[destination]['enumerated'][instrfield_key]:
                                                                    dual_issue_throughput_activated = True
                                                                    break
                                                        else:
                                                            for _ in instrfield_data_ref.keys():
                                                                if 'enumerated' in instrfield_data_ref[_].keys():
                                                                    for instrfield_key in instrfield_data_ref[_]['enumerated'].keys():
                                                                        if element in instrfield_data_ref[_]['enumerated'][instrfield_key]:
                                                                            if instructions[key]['syntax'][1] == element:
                                                                                dual_issue_throughput_activated = True
                                                                                break
                                            if dual_issue_throughput_activated is True:
                                                if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                                    if len(scheduling_table_dict[sched][sched_class]['pipelines']) == 1:
                                                        throughput -= 1
                                        if dual_issue_throughput_activated is False:
                                            if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                                if len(scheduling_table_dict[sched][sched_class]['pipelines']) == 1:
                                                    if latency == throughput:
                                                        throughput -= 1
                                        while timeline_counter <= throughput:
                                            if throughput > 0 or (throughput == 0 and dual_issue_throughput_activated is True):
                                                if timeline_counter == 0:
                                                    timeline_string += "."
                                                    timeline_index += 1
                                                elif timeline_index < 5:
                                                    timeline_string += " "
                                                    timeline_index += 1
                                                elif timeline_index == 5:
                                                    timeline_string += "."
                                                    timeline_index = 1
                                                else:
                                                    timeline_index += 1
                                            timeline_counter += 1
                                        if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                            if len(scheduling_table_dict[sched][sched_class]['pipelines']) > 1:
                                                if dual_issue_throughput_activated is True:
                                                    if len(timeline_string) > throughput:
                                                        timeline_string = timeline_string[:-1]
                                                elif dual_issue_throughput_activated is False:
                                                    if len(timeline_string) >= throughput and timeline_string.endswith(" "):
                                                        timeline_string = timeline_string.rstrip(" ")
                                                        if throughput <= len(timeline_string):
                                                            diff = len(timeline_string) - throughput -1
                                                            if diff < 0:
                                                                diff = -1 * diff
                                                            timeline_string = timeline_string[:-diff]
                                                    else:
                                                        diff = len(timeline_string) - throughput -1
                                                        timeline_string = timeline_string[:-diff]
                                        if test != "":
                                            timeline += timeline_string
                                        timeline += "D"
                                        if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                            if len(scheduling_table_dict[sched][sched_class]['pipelines']) > 1:
                                                for _ in range(throughput - 1):
                                                    timeline += "e"
                                            else:
                                                for _ in range(throughput):
                                                    timeline += "e"
                                        timeline += "E"
                                        if int(sched_parameters[sched]['IssueWidth']) == 1:
                                            index_str += timeline + "   " + instruction
                                        elif int(sched_parameters[sched]['IssueWidth']) > 1:
                                            index_str += timeline + "   " + instruction
                                        timeline_string = ""
                                        timeline_index = 0
                                        timeline_counter = 0
                                        while timeline_counter <= throughput:
                                            if throughput > 0 or (throughput == 0 and dual_issue_throughput_activated is True):
                                                if len(timeline_ref + timeline_string) % 5 == 0:
                                                    if len(timeline_ref + timeline_string) > len(timeline_ref):
                                                        timeline_string += "."
                                                        timeline_index = 1
                                                    else:
                                                        timeline_string += " "
                                                        timeline_index += 1
                                                elif timeline_index < 5:
                                                    timeline_string += " "
                                                    timeline_index += 1
                                                elif timeline_index == 5:
                                                    timeline_string += "."
                                                    timeline_index = 1
                                                else:
                                                    timeline_index += 1
                                            timeline_counter += 1
                                        if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                            if len(scheduling_table_dict[sched][sched_class]['pipelines']) > 1:
                                                if dual_issue_throughput_activated is True:
                                                    while len(timeline_string) >= throughput:
                                                        timeline_string = timeline_string[:-1]
                                                    timeline_string += "."
                                                elif dual_issue_throughput_activated is False:
                                                    if len(timeline_string) >= throughput and timeline_string.endswith(" "):
                                                        timeline_string = timeline_string.rstrip(" ")
                                                        timeline_string += "."
                                                    else:
                                                        diff = len(timeline_string) - throughput -1
                                                        if diff < 0:
                                                            diff = -1 * diff
                                                        timeline_string = timeline_string[:-diff]
                                                        timeline_string += "."
                                        len_row1 = len(timeline)
                                        if int(sched_parameters[sched]['IssueWidth']) > 1:
                                                if timeline_string.endswith('.') is False:
                                                    if throughput > 0 or (throughput == 0 and dual_issue_throughput_activated is True):
                                                        timeline_string = timeline_string[:-1] + "."
                                                if len(timeline_ref) % 5 == 0 and timeline_ref.endswith(".") is False:
                                                    timeline_string = timeline_string.replace(timeline_string[0], ".", 1)
                                                test = test.replace(timeline_ref, timeline_ref + timeline_string)
                                                if index == 0:
                                                    index_str = "// CHECK: " + index_str
                                                elif index > 0:
                                                    index_str = "// CHECK-NEXT: " + index_str
                                                if index_str not in test:
                                                    test += index_str
                                        else:
                                            if timeline_string.endswith('.') is False:
                                                timeline_string = timeline_string[:-1] + "."
                                            if len(timeline_ref) % 5 == 0:
                                                timeline_string = "." + timeline_string[1:]
                                            if len(timeline_ref) % 5 == 0 and timeline_ref.endswith(".") is False:
                                                timeline_string = timeline_string.replace(timeline_string[0], ".", 1)
                                            test = test.replace(timeline_ref, timeline_ref + timeline_string)
                                            if index == 0:
                                                index_str = "// CHECK: " + index_str
                                            elif index > 0:
                                                index_str = "// CHECK-NEXT: " + index_str
                                            if index_str not in test:
                                                test += index_str
                                    index += 1
                                    if index % 2 == 0:
                                        indices = ""
                                        row1 = ""
                                        row2 = ""
                                        row2_checked = False
                                        row1_checked = False
                                        for digit in range(len_row1):
                                            indices += str(digit % 10)
                                        if len(indices) <= 10:
                                            if row2_checked is False:
                                                row2 += indices
                                                row2_checked = True
                                        elif len(indices) > 10:
                                            len_index = 10
                                            length = len(indices)
                                            last_limit = 0
                                            while length >= 0:
                                                if row2_checked is False:
                                                    limit = length - last_limit
                                                    if last_limit == 0:
                                                        row2 += indices[:len_index]
                                                        row1 += 10 * " "
                                                    else:
                                                        if limit > 10:
                                                            row2 += indices[last_limit:last_limit+10]
                                                            last_limit = last_limit + 10
                                                            row1 += 10 * " "
                                                        else:
                                                            row2 += indices[last_limit:length]
                                                            row1 += (length - last_limit) * " "
                                                    row2_checked = True
                                                    length -= len_index
                                                    last_limit = len_index
                                                elif row1_checked is False:
                                                    if length >= last_limit:
                                                        limit = length - last_limit
                                                    else:
                                                        last_limit = length
                                                        limit = last_limit
                                                    if limit > 10:
                                                        row1 += indices[last_limit:last_limit+10]
                                                        last_limit = last_limit + 10
                                                        row2 += 10 * " "
                                                    else:
                                                        row1 += indices[-last_limit:]
                                                        row2 += (last_limit) * " "
                                                    length -= len_index
                                                    row1_checked = True
                                                if row1_checked is True and row2_checked is True:
                                                    row2_checked = False
                                                    row1_checked = False
                                        if key.endswith(".s"):
                                            file_name = path_dependency + "/" + "test_" + key.replace(".s", "_s") + "_" + key.replace(".s", "_s") + ".s" 
                                        else:
                                            file_name = path_dependency + "/" + "test_" + key + "_" + key + ".s" 
                                        if len(extension_list) > 0:
                                            if extension_checked is False:
                                                for attrib in instructions[key]['attributes']:
                                                    if attrib in extension_list:
                                                        extension_checked = True
                                                        break
                                        else:
                                            extension_checked = True
                                        if extension_checked is True:
                                            f = open(file_name, "a")
                                            f.write(test + "\n")
                                            test_content_dep += test
                                            f.write("\n\n")
                                            f.close()
                                        test = ""
                                throughput = 0
                                dual_issue_throughput_activated = False
                                if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                    for pipeline in scheduling_table_dict[sched][sched_class]['pipelines']:
                                        if str(scheduling_table_dict[sched][sched_class]['pipelines'][pipeline]['throughput']).isdigit():
                                            throughput += int(scheduling_table_dict[sched][sched_class]['pipelines'][pipeline]['throughput'])
                                for instruction in scheduling_tests_struct[key]['no-dep']:
                                    if index % 2 == 0 or index == 0:
                                        for element in sched_app_regs[key]:
                                                    if sched_app_regs[key][element] >= 2:
                                                        if element.isdigit() is False:
                                                            destination = instructions[key]['syntax'][1]
                                                            if destination in instrfield_data_ref.keys():
                                                                for instrfield_key in instrfield_data_ref[destination]['enumerated'].keys():
                                                                    if element in instrfield_data_ref[destination]['enumerated'][instrfield_key]:
                                                                        dual_issue_throughput_activated = True
                                                                        break
                                                            else:
                                                                for _ in instrfield_data_ref.keys():
                                                                    if 'enumerated' in instrfield_data_ref[_].keys():
                                                                        for instrfield_key in instrfield_data_ref[_]['enumerated'].keys():
                                                                            if element in instrfield_data_ref[_]['enumerated'][instrfield_key]:
                                                                                dual_issue_throughput_activated = True
                                                                                break
                                        if dual_issue_throughput_activated is False:
                                            if 'latency' in scheduling_table_dict[sched][sched_class].keys():
                                                if latency == throughput:
                                                    if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                                        if len(scheduling_table_dict[sched][sched_class]['pipelines']) == 1:
                                                            if int(sched_parameters[sched]['IssueWidth']) > 1:
                                                                throughput -= 1
                                        index = 0
                                        index_list = list()
                                        index_list.append(0)
                                        index_list.append(index)
                                        index_str = str(index_list).replace(" ", "")
                                        index_str += "     "
                                        timeline = "D"
                                        for _ in range(throughput-1):
                                            timeline += "e"
                                        timeline += "E"
                                        index_str += timeline + "   " + instruction
                                        reference = ""
                                        reference += ""
                                        index = 0
                                        if index == 0 or index % 2 == 0:
                                            reference += "\n" + "// CHECK: " + len('-NEXT') * " " + index_str
                                        test += reference + "\n"
                                        timeline_ref = timeline
                                    else:
                                        index_list = list()
                                        index_list.append(0)
                                        index_list.append(index)
                                        index_str = str(index_list).replace(" ", "")
                                        index_str += "     "
                                        timeline_string = ""
                                        timeline_index = 0
                                        timeline_counter = 0
                                        timeline = ""
                                        while timeline_counter <= throughput:
                                            if timeline_counter == 0:
                                                timeline_string += "."
                                                timeline_index += 1
                                            elif timeline_index < 5:
                                                timeline_string += " "
                                                timeline_index += 1
                                            elif timeline_index == 5:
                                                timeline_string += "."
                                                timeline_index = 1
                                            else:
                                                timeline_index += 1
                                            timeline_counter += 1
                                        if len(timeline_string) > throughput:
                                            timeline_string = timeline_string[:-1]
                                            if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                                if len(scheduling_table_dict[sched][sched_class]['pipelines']) > 1:
                                                    for element in scheduling_table_dict[sched][sched_class]['pipelines'].keys():
                                                        if str(scheduling_table_dict[sched][sched_class]['pipelines'][element]['throughput']).isdigit():
                                                            if int(scheduling_table_dict[sched][sched_class]['pipelines'][element]['throughput']) != throughput:
                                                                timeline_string = timeline_string[:-int(scheduling_table_dict[sched][sched_class]['pipelines'][element]['throughput'])]
                                                                break
                                        if dual_issue_throughput_activated is False:
                                            if len(timeline_string) > throughput and throughput == 0:
                                                if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                                    if len(scheduling_table_dict[sched][sched_class]['pipelines']) > 1:
                                                        timeline_string = timeline_string[:-1]
                                        if test != "":
                                            timeline += timeline_string
                                        timeline += "D"
                                        for _ in range(throughput-1):
                                            timeline += "e"
                                        timeline += "E"
                                        if int(sched_parameters[sched]['IssueWidth']) == 1:
                                            index_str += timeline + "   " + instruction
                                        elif int(sched_parameters[sched]['IssueWidth']) > 1:
                                            if 'single_issue' in scheduling_table_dict[sched][sched_class].keys():
                                                if scheduling_table_dict[sched][sched_class]['single_issue'] == 'true':
                                                    index_str += timeline + "   " + instruction
                                            else:
                                                for element in sched_app_regs[key]:
                                                    if sched_app_regs[key][element] >= 2:
                                                        if element.isdigit() is False:
                                                            destination = instructions[key]['syntax'][1]
                                                            if destination in instrfield_data_ref.keys():
                                                                for instrfield_key in instrfield_data_ref[destination]['enumerated'].keys():
                                                                    if element in instrfield_data_ref[destination]['enumerated'][instrfield_key]:
                                                                        dual_issue_throughput_activated = True
                                                                        break
                                                            else:
                                                                for _ in instrfield_data_ref.keys():
                                                                    if 'enumerated' in instrfield_data_ref[_].keys():
                                                                        for instrfield_key in instrfield_data_ref[_]['enumerated'].keys():
                                                                            if element in instrfield_data_ref[_]['enumerated'][instrfield_key]:
                                                                                dual_issue_throughput_activated = True
                                                                                break
                                        if dual_issue_throughput_activated is False:
                                            if 'latency' in scheduling_table_dict[sched][sched_class].keys():
                                                if latency == throughput:
                                                    if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                                        if len(scheduling_table_dict[sched][sched_class]['pipelines']) == 1:
                                                            if int(sched_parameters[sched]['IssueWidth']) > 1:
                                                                throughput -= 1
                                        timeline_string = ""
                                        timeline_index = 0
                                        timeline_counter = 0
                                        while timeline_counter <= throughput:
                                            if len(timeline_ref + timeline_string) % 5 == 0:
                                                if len(timeline_ref + timeline_string) > len(timeline_ref):
                                                    timeline_string += "."
                                                    timeline_index = 1
                                                else:
                                                    timeline_string += " "
                                                    timeline_index += 1
                                            elif timeline_index < 5:
                                                timeline_string += " "
                                                timeline_index += 1
                                            elif timeline_index == 5:
                                                timeline_string += "."
                                                timeline_index = 1
                                            else:
                                                timeline_index += 1
                                            timeline_counter += 1
                                        if len(timeline_string) > throughput:
                                            timeline_string = timeline_string[:-1]
                                            if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                                if len(scheduling_table_dict[sched][sched_class]['pipelines']) > 1:
                                                    for element in scheduling_table_dict[sched][sched_class]['pipelines'].keys():
                                                        if str(scheduling_table_dict[sched][sched_class]['pipelines'][element]['throughput']).isdigit():
                                                            if int(scheduling_table_dict[sched][sched_class]['pipelines'][element]['throughput']) != throughput:
                                                                timeline_string = timeline_string[:-int(scheduling_table_dict[sched][sched_class]['pipelines'][element]['throughput'])]
                                                                break
                                        if dual_issue_throughput_activated is False:
                                            if len(timeline_string) > throughput and throughput == 0:
                                                if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                                    if len(scheduling_table_dict[sched][sched_class]['pipelines']) > 1:
                                                        timeline_string = timeline_string[:-1]
                                        if timeline_string.endswith(" ") and len(timeline_string) > throughput:
                                            timeline_string = timeline_string.rstrip(" ")
                                            timeline_string += "."
                                        if int(sched_parameters[sched]['IssueWidth']) > 1:
                                            if 'single_issue' not in scheduling_table_dict[sched][sched_class].keys():
                                                if dual_issue_throughput_activated is True:
                                                    if timeline_string.endswith('.') is False:
                                                        timeline_string = timeline_string[:-1] + "."
                                                        if len(timeline_ref) % 5 == 0 and timeline_ref.endswith(".") is False:
                                                            timeline_string = timeline_string.replace(timeline_string[0], ".", 1)
                                                        test = test.replace(timeline_ref, timeline_ref + timeline_string)
                                                index_str += timeline_ref
                                                if index == 0:
                                                    index_str = "// CHECK: " + index_str
                                                elif index > 0:
                                                    index_str = "// CHECK-NEXT: " + index_str
                                                if index_str not in test:
                                                    test += index_str + "   " + instruction
                                            elif dual_issue_throughput_activated is True:
                                                if timeline_string.endswith('.') is False:
                                                    timeline_string = timeline_string[:-1] + "."
                                                if len(timeline_ref) % 5 == 0 and timeline_ref.endswith(".") is False:
                                                    timeline_string = timeline_string.replace(timeline_string[0], ".", 1)
                                                test = test.replace(timeline_ref, timeline_ref + timeline_string)
                                                if index == 0:
                                                    index_str = "// CHECK: " + index_str
                                                elif index > 0:
                                                    index_str = "// CHECK-NEXT: " + index_str
                                                if index_str not in test:
                                                    test += index_str
                                            else:
                                                if timeline_string.endswith('.') is False:
                                                    if len(timeline_string) != 0 and throughput != 0:
                                                        timeline_string = timeline_string[:-1] + "."
                                                if len(timeline_ref) % 5 == 0 and timeline_ref.endswith(".") is False:
                                                    timeline_string = timeline_string.replace(timeline_string[0], ".", 1)
                                                test = test.replace(timeline_ref, timeline_ref + timeline_string)
                                                if index == 0:
                                                    index_str = "// CHECK: " + index_str
                                                elif index > 0:
                                                    index_str = "// CHECK-NEXT: " + index_str
                                                if index_str not in test:
                                                    test += index_str
                                        else:
                                            if timeline_string.endswith('.') is False:
                                                timeline_string = timeline_string[:-1] + "."
                                            if len(timeline_ref) % 5 == 0:
                                                timeline_string = "." + timeline_string[1:]
                                            if len(timeline_ref) % 5 == 0 and timeline_ref.endswith(".") is False:
                                                timeline_string = timeline_string.replace(timeline_string[0], ".", 1)
                                            test = test.replace(timeline_ref, timeline_ref + timeline_string)
                                            if index == 0:
                                                index_str = "// CHECK: " + index_str
                                            elif index > 0:
                                                index_str = "// CHECK-NEXT: " + index_str
                                            if index_str not in test:
                                                test += index_str
                                    len_row1 = len(timeline)
                                    index += 1
                                    if index % 2 == 0:
                                        indices = ""
                                        row1 = ""
                                        row2 = ""
                                        row2_checked = False
                                        row1_checked = False
                                        for digit in range(len_row1):
                                            indices += str(digit % 10)
                                        if len(indices) <= 10:
                                            if row2_checked is False:
                                                row2 += indices
                                                row2_checked = True
                                        elif len(indices) > 10:
                                            len_index = 10
                                            length = len(indices)
                                            last_limit = 0
                                            while length >= 0:
                                                if row2_checked is False:
                                                    limit = length - last_limit
                                                    if last_limit == 0:
                                                        row2 += indices[:len_index]
                                                        row1 += 10 * " "
                                                    else:
                                                        if limit > 10:
                                                            row2 += indices[last_limit:last_limit+10]
                                                            last_limit = last_limit + 10
                                                            row1 += 10 * " "
                                                        else:
                                                            row2 += indices[last_limit:length]
                                                            row1 += (length - last_limit) * " "
                                                    row2_checked = True
                                                    length -= len_index
                                                    last_limit = len_index
                                                elif row1_checked is False:
                                                    if length >= last_limit:
                                                        limit = length - last_limit
                                                    else:
                                                        last_limit = length
                                                        limit = last_limit
                                                    if limit > 10:
                                                        row1 += indices[last_limit:last_limit+10]
                                                        last_limit = last_limit + 10
                                                        row2 += 10 * " "
                                                    else:
                                                        row1 += indices[-last_limit:]
                                                        row2 += (last_limit) * " "
                                                    length -= len_index
                                                    row1_checked = True
                                                if row1_checked is True and row2_checked is True:
                                                    row2_checked = False
                                                    row1_checked = False
                                        if key.endswith(".s"):
                                            file_name = path + "/" + "test_" +  key.replace(".s", "_s") + "_" + key.replace(".s", "_s") + ".s" 
                                        else:
                                            file_name = path + "/" + "test_" +  key + "_" + key + ".s"
                                        if len(extension_list) > 0:
                                            if extension_checked is False:
                                                for attrib in instructions[key]['attributes']:
                                                    if attrib in extension_list:
                                                        extension_checked = True
                                                        break
                                        else:
                                            extension_checked = True
                                        if extension_checked is True:
                                            if 'single_issue' in scheduling_table_dict[sched][sched_class].keys():
                                                dual_issue_throughput_activated = True
                                            if dual_issue_throughput_activated is True:
                                                if 'pipelines' in scheduling_table_dict[sched][sched_class].keys():
                                                    if len(scheduling_table_dict[sched][sched_class]['pipelines']) == 1:
                                                        test = test_content_dep
                                            f = open(file_name, "a")
                                            f.write(test + "\n")
                                            f.write("\n\n")
                                            f.close()
                                        test = ""
    aliases = adl_parser.parse_instructions_aliases_from_adl(config_variables['ADLName'])
    for instruction in instructions:
        check = False      
        for element in extension_list:
            if element in instructions[instruction]['attributes']:
                if instruction not in instructions_list_generated and instruction not in aliases.keys():
                    print("Scheduling is not supported for instruction " + instruction)
                    break  
                                           
## Function which generates sail description for instructions defined in the XML given as input
#
# @param path string specifying the path to the folder in which the content will be written
# @param extension_list list specifying which extensions are enabled by the user
# @return Sail description for the instructions supported
def generate_sail_description(path, extensions_list):
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    instrfields = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[1]
    instrfield_imm = adl_parser.get_instrfield_from_adl(config_variables["ADLName"])[0]
    register_parsed = adl_parser.parse_registers_from_adl(config_variables["ADLName"])
    extension_set = ""
    xlen_set_arch = ""
    base_arch = ""
    if len(extensions_list) > 0:
        for element in extensions_list:
            for instr in instructions.keys():
                if element in instructions[instr]['attributes']:
                    file_name = path.replace("ext", element.lower())
                    if os.path.exists(file_name):
                        os.remove(file_name)
    else:
        for element in config_variables.keys():
            for instr in instructions.keys():
                if element.startswith("LLVMExt"):
                    if element.replace("LLVMExt", "").lower() in instructions[instr]['attributes']:
                        file_name = path.replace("ext", element.replace("LLVMExt", "").lower())
                        if os.path.exists(file_name):
                            os.remove(file_name)
    if len(extensions_list) > 0:
        for element in extensions_list:
            for instr in instructions.keys():
                if element in instructions[instr]['attributes']:
                    file_name = path.replace("ext", element.lower())
                    f = open(file_name, 'a')
                    legalDisclaimer.add_sail_license(file_name)
                    f.write("\n\n")
                    f.close()
                    break
    else:
        for element in config_variables.keys():
            for instr in instructions.keys():
                if element.startswith("LLVMExt"):
                    if element.replace("LLVMExt", "").lower() in instructions[instr]['attributes']:
                        file_name = path.replace("ext", element.replace("LLVMExt", "").lower())
                        file_name = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', file_name)
                        f = open(file_name, 'a')
                        legalDisclaimer.add_sail_license(file_name)
                        f.write("\n\n")
                        f.close()
                        break
    instruction_list_checked = list()
    if len(extensions_list) > 0:
        for element in extensions_list:
            sys_reg_list = list()
            for instr in instructions.keys():
                if element in instructions[instr]['attributes']:
                    for attribute in instructions[instr]['attributes']:
                        if "LLVMExt" + attribute.capitalize() in config_variables.keys():
                            if instr not in instruction_list_checked:
                                if attribute not in sys_reg_list:
                                    sys_reg_list.append(attribute)
                                    instruction_list_checked.append(instr)
                                else:
                                    instruction_list_checked.append(instr)
                                    for attribute in instructions[instr]['attributes']:
                                        if "LLVMExt" + attribute.capitalize() in config_variables.keys():
                                            if attribute not in sys_reg_list:
                                                sys_reg_list.append(attribute)
            if len(sys_reg_list) > 0:
                file_name = path.replace("ext", element)
                f = open(file_name, 'a')
                extension_set = element.replace("LLVMExt", "").capitalize()
                main_extension = extension_set
                instruction_extension_enum = "enum clause extension = " + "Ext_" + extension_set + "\n"
                if "BaseArchitecture" in config_variables.keys():
                    base_arch = [s for s in re.findall(r'\d+\d*', config_variables['BaseArchitecture'])]
                    instruction_extension_enum += "function clause extensionEnabled(" + "Ext_" + extension_set + ") = xlen == " + base_arch[0] + " & "
                if base_arch[0] == '32' and extension_set.lower() != 'rv32i':
                    instruction_extension_enum += "sys_enable_" + extension_set.lower() + "() & "
                for reg in sys_reg_list:
                    if reg == 'rv32c':
                        reg = 'zca'
                        instruction_extension_enum += "extensionEnabled(" + "Ext_" + reg.capitalize() + ") & "
                    elif base_arch[0] == '32' and reg != 'rv32i':
                        if reg != extension_set.lower():
                            instruction_extension_enum += "extensionEnabled(" + "Ext_" +  reg.capitalize() + ") & "
                instruction_extension_enum = instruction_extension_enum.rstrip(" & ")
                f.write(instruction_extension_enum)
                f.write("\n\n")
                f.close()
    else:
        for element in config_variables.keys():
            sys_reg_list = list()
            if element.startswith("LLVMExt"):
                for instr in instructions.keys():
                    if element.replace("LLVMExt", "").lower() in instructions[instr]['attributes']:
                        for attribute in instructions[instr]['attributes']:
                            if "LLVMExt" + attribute.capitalize() in config_variables.keys():
                                if instr not in instruction_list_checked:
                                    if attribute not in sys_reg_list:
                                        sys_reg_list.append(attribute)
                                        instruction_list_checked.append(instr)
                                    else:
                                        instruction_list_checked.append(instr)
                                        for attribute in instructions[instr]['attributes']:
                                            if "LLVMExt" + attribute.capitalize() in config_variables.keys():
                                                if attribute not in sys_reg_list:
                                                    sys_reg_list.append(attribute)
                if len(sys_reg_list) > 0:
                    file_name = path.replace("ext", element.replace("LLVMExt", "").lower())
                    file_name = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', file_name)
                    f = open(file_name, 'a')
                    extension_set = element.replace("LLVMExt", "").capitalize()
                    instruction_extension_enum = "enum clause extension = " + "Ext_" + extension_set + "\n"
                    if "BaseArchitecture" in config_variables.keys():
                        base_arch = [s for s in re.findall(r'\d+\d*', config_variables['BaseArchitecture'])]
                    instruction_extension_enum += "function clause extensionEnabled(" + "Ext_" + extension_set + ") = xlen == " + base_arch[0] + " & "
                    for reg in sys_reg_list:
                        if base_arch[0] == '32' and reg != 'rv32i':
                            if reg == 'rv32c':
                                reg = 'zca'
                            instruction_extension_enum += "sys_enable_" + reg + "()" + " & "
                    instruction_extension_enum = instruction_extension_enum.rstrip(" & ")
                    f.write(instruction_extension_enum)
                    f.write("\n\n")
                    f.close()
    instruction_parsed_and_printed = list()
    if "BaseArchitecture" in config_variables.keys():
        base_arch = [s for s in re.findall(r'\d+\d*', config_variables['BaseArchitecture'])]
    for instr in instructions.keys():
        if_activated = False
        if instr in instruction_encoding_dict.keys():
            prefixed = False
            prefix_attrib = ""
            for extension in extensions_list:
                if extension.capitalize() in config_variables['ExtensionPrefixed']:
                    if extension in instructions[instr]['attributes']:
                        prefixed = True
                        prefix_attrib = extension
                        break
            statement = "mapping clause encdec"
            reg_list = list()
            if_statement = "if "
            content = "<-> "
            if_statement_copy = if_statement
            if instructions[instr]['width'] != config_variables['LLVMStandardInstructionWidth']:
                statement += "_compressed"
            list_fields_instructions = list()
            if instr.lower().startswith("c."):
                if prefixed is True:
                    key = instr.lower().replace("c.", "c_")
                    key = prefix_attrib.upper() + "_" + key
                else:
                    key = instr.lower().replace("c.", "c_")
            else:
                if prefixed is True:
                    key = instr.lower()
                    key = prefix_attrib.upper() + "_" + key
                else:
                    key = instr.lower()
            statement += " = " + key.upper()
            attributes_list = instructions[instr]['attributes']
            for attribute in attributes_list:
                if "LLVMExt" + attribute.capitalize() in config_variables.keys():
                    if base_arch[0] == '32' and attribute != 'rv32i':
                        if attribute == 'rv32c':
                            attribute = 'zca'
                        if_statement += "extensionEnabled(" + "Ext_" + attribute.capitalize() + ")" + " & "
            if_statement += "xlen == " + base_arch[0]
            if if_statement.endswith(" & "):
                if_statement = if_statement.rstrip(" & ")
            if if_statement != if_statement_copy:
                for element in instruction_encoding_dict[instr].keys():
                    value = instruction_encoding_dict[instr][element].split("=")[1].strip(" ").replace(";", "")
                    if value in instrfields.keys() and value in instructions[instr]['fields'][0].keys():
                        if str(2 ** int(instrfields[value]['width'])) == config_variables['LLVMRegBasicWidth']:
                            content += "encdec_reg(" + value + ")" + " @ "
                        elif str(2 ** int(instrfields[value]['width'])) != config_variables['LLVMRegBasicWidth']:
                            content += "encdec_creg(" + value + ")" + " @ "
                        reg_list.append(value)
                    elif value.isdigit():
                        let_instr = instruction_encoding_dict[instr][element].split("=")[0]
                        let_instr = let_instr.replace("let Inst{", "")
                        let_instr = let_instr.replace("}", "")
                        end = let_instr.split("-")[0]
                        start = let_instr.split("-")[1]
                        index = int(end) - int(start) + 1
                        immediate_binary = bin(int(value))
                        immediate_binary = immediate_binary.replace("0b", "")
                        while len(immediate_binary) < index:
                            immediate_binary = '0' + immediate_binary
                        immediate_binary = '0b' + immediate_binary
                        content += immediate_binary + " @ "
                    else:
                        for imm in instrfield_imm.keys():
                            if imm == value.split("{")[0] and imm in instructions[instr]['fields'][0].keys():
                                if 'signed' not in instrfield_imm[imm].keys():
                                    imm_type = "i"
                                    end = value.split("-")[0]
                                    start = value.split("-")[1]
                                    end = end.replace(imm, "").replace("{", "")
                                    start = start.replace("}", "").replace(";", "")
                                    imm_type += end + "_" + start
                                    index = str(int(int(end) - int(start) + 1))
                                    list_fields_instructions.append(imm_type)
                                else:
                                    imm_type = "i"
                                    end = value.split("-")[0]
                                    start = value.split("-")[1]
                                    end = end.replace(imm, "").replace("{", "")
                                    start = start.replace("}", "").replace(";", "")
                                    imm_type += end + "_" + start
                                    index = str(int(int(end) - int(start) + 1))
                                    list_fields_instructions.append(imm_type)
                                content += imm_type + " : " + "bits(" + index + ") @ "
            list_fields_instructions = sorted(list_fields_instructions, key=lambda x: int(x.split('_')[0][1:]), reverse=True)
            statement += "("
            for element in list_fields_instructions:
                statement += element + " @ "
            if statement.endswith(" @ "):
                statement = statement.rstrip(" @ ")
                statement += ", "
            for element in reg_list:
                statement += element + ", "
            if statement.endswith(", "):
                statement = statement.rstrip(", ")
            statement += ")"
            if content.endswith(" @ "):
                content = content.rstrip(" @ ")
            statement_assembly = "mapping clause assembly"
            statement_assembly +=  " = " + key.upper()
            content_assembly = "<-> "
            content_assembly += "\"" + instr.lower() + "\"" + " ^ " + "spc()" + " ^ "
            index = len(instructions[instr]['syntax'])
            counter = 1
            reg_list_asm = list()
            for register in reg_list:
                for field in instructions[instr]['fields'][0].keys():
                    if field in instrfields.keys() and field == register:
                        if str(2 ** int(instrfields[field]['width'])) == config_variables['LLVMRegBasicWidth']:
                            content_assembly += "reg_name(" + field + ")"
                            reg_list_asm.append(field)
                        else:
                            content_assembly += "creg_name(" + field + ")"
                            reg_list_asm.append(field)
                        content_assembly += " ^ sep() ^ "
            for field in instructions[instr]['fields'][0].keys():
                    if field in instrfield_imm.keys() and instructions[instr]['fields'][0][field] == 'imm':
                        content_assembly += "hex_bits_" + str(int(instrfield_imm[field]['width']) + int(instrfield_imm[field]['shift']))  + "("
                        if 'signed' not in instrfield_imm[field].keys():
                            content_assembly += "imm"
                            reg_list_asm.insert(0, 'imm')
                        else:
                            content_assembly += "imm"
                            reg_list_asm.insert(0, 'imm')
                        if instrfield_imm[field]['shift'] != '0':
                            content_assembly += " @ " + '0b' + str('0' * int(instrfield_imm[field]['shift'])) + ")"
                        else:
                            content_assembly += ")"
                        content_assembly += " ^ sep() ^ "
            statement_assembly += "("
            for element in reg_list_asm:
                statement_assembly += element + ", "
            if statement_assembly.endswith(", "):
                statement_assembly = statement_assembly.rstrip(", ")
            statement_assembly += ")"
            function_clause = "function clause execute"
            function_clause += "(" + key.upper()
            statement_function = "("
            for element in reg_list_asm:
                statement_function += element + ", "
            if statement_function.endswith(", "):
                statement_function = statement_function.rstrip(", ")
            if content_assembly.endswith(" ^ sep() ^ "):
                content_assembly = content_assembly[:-len(" ^ sep() ^ ")]
            statement_function += ")"
            function_clause += statement_function + ")"
            function_clause += " = {\n"
            content_function = ""
            function_list = list()
            ast_clause_list = list()
            signed = False
            for field in instructions[instr]['fields'][0].keys():
                if field in instrfield_imm.keys() and instructions[instr]['fields'][0][field] == 'imm':
                    if instrfield_imm[field]['shift'] != '0':
                        if 'signed' not in instrfield_imm[field].keys():
                            content_function += "\tlet " + "imm_val" + " : " + "xlenbits" \
                    + " = "
                            content_function += 'zero_extend(' + 'imm' +  '@ ' + "0b" + str('0' * int(instrfield_imm[field]['shift'])) + ");\n"
                            function_list.append('imm')
                            ast_clause_list.append(field)
                            signed = False
                        else:
                            content_function += "\tlet " + "imm_val" + " : " + "xlenbits" \
                    + " = "
                            content_function += 'sign_extend(' + 'imm' +  '@ ' + "0b" + str('0' * int(instrfield_imm[field]['shift'])) + ");\n"
                            function_list.append('imm')
                            ast_clause_list.append(field)
                            signed = False
                    else:
                        if 'signed' in instrfield_imm[field].keys():
                            content_function += "\tlet " + "imm_val" + " : " + "xlenbits" \
                    + " = "
                            content_function += "sign_extend(" + 'imm' + ");\n"
                            function_list.append('imm')
                            ast_clause_list.append(field)
                            signed = True
                        else:
                            content_function += "\tlet " + "imm_val" \
                    + " = "
                            content_function += "imm;\n"
                            function_list.append('imm')
                            ast_clause_list.append(field)
            compressed_reg = False
            for field in instructions[instr]['fields'][0].keys():
                if field in instrfields.keys() and  str(instructions[instr]["fields"][0][field]) == "reg":
                    if 'load' in instructions[instr]['attributes'] or 'store' in instructions[instr]['attributes']:
                        if str(2 ** int(instrfields[field]['width'])) != config_variables['LLVMRegBasicWidth']:
                            compressed_reg = True
                            content_function += "\tlet " + field + "_idx" + " = "
                            content_function += "creg2reg_idx(" + field + ");\n"
                            function_list.append(field)
                            ast_clause_list.append(field)
                        elif str(2 ** int(instrfields[field]['width'])) == config_variables['LLVMRegBasicWidth']:
                            content_function += "\tlet " + field + "_val" + " = "
                            if instrfields[field]['ref'] == 'GPR':
                                content_function += "X(" + field + ");\n" 
                                function_list.append(field)
                                ast_clause_list.append(field)
                    else:
                        if str(2 ** int(instrfields[field]['width'])) == config_variables['LLVMRegBasicWidth']:
                            if instrfields[field]['ref'] == 'GPR':
                                if instrfields[field]['ref'] + "(" + field + ")" in instructions[instr]['inputs']:
                                    content_function += "\tlet " + field + "_val" + " = "
                                    content_function += "X(" + field + ");\n" 
                                elif instrfields[field]['ref'] + "(" + field + ")?" in instructions[instr]['inputs']:
                                    content_function += "\tlet " + field + "_val" + " = "
                                    content_function += "X(" + field + ");\n" 
                                function_list.append(field)
                                ast_clause_list.append(field)
                        else:
                            content_function += "\tlet " + field + "_idx" + " = "
                            content_function += "creg2reg_idx(" + field + ");\n"
                            if instrfields[field]['ref'] == 'GPR':
                                if instrfields[field]['ref'] + "(" + field + ")" in instructions[instr]['inputs']:
                                    compressed_reg = True
                                    content_function += "\tlet " + field + "_val" + " = "
                                    content_function += "X(" + field + "_idx" + ");\n" 
                                elif instrfields[field]['ref'] + "(" + field + ")?" in instructions[instr]['inputs']:
                                    compressed_reg = True
                                    content_function += "\tlet " + field + "_val" + " = "
                                    content_function += "X(" + field + "_idx" + ");\n" 
                                function_list.append(field)
                                ast_clause_list.append(field)
            destination = ""
            for input in instructions[instr]['inputs']:
                for register in register_parsed.keys():
                    if register in input:
                        element = input.replace(register, "").replace("(", "").replace(")", "")
                        prefix = register_parsed[register].prefix
                        end_mark = False
                        if prefix != "":
                            instrfield = prefix.upper() + element
                            if instrfield.endswith("?"):
                                instrfield = instrfield.rstrip("?")
                                end_mark = True
                            if instrfield in alias_register_dict.keys():
                                register_alias = alias_register_dict[instrfield]
                                if register == 'GPR':
                                    if register_alias not in function_list and register_alias not in ast_clause_list:
                                        content_function += "\tlet " + register_alias + "_val" + " = "
                                        content_function += "X(" + register_alias + ");\n" 
                                        function_list.append(register_alias)
                                        ast_clause_list.append(register_alias)
                                        instrfields[register_alias] = {}
                                        if end_mark is True:
                                            if register + "(" + element.rstrip("?") + ")?" in instructions[instr]['outputs']:
                                                destination = register_alias
                                        else:
                                            if register + "(" + element + ")" in instructions[instr]['outputs']:
                                                destination = register_alias
            for input in instructions[instr]['outputs']:
                for register in register_parsed.keys():
                    if register in input:
                        element = input.replace(register, "").replace("(", "").replace(")", "")
                        prefix = register_parsed[register].prefix
                        if prefix != "":
                            instrfield = prefix.upper() + element
                            if instrfield.endswith("?"):
                                instrfield = instrfield.rstrip("?")
                            if instrfield in alias_register_dict.keys():
                                register_alias = alias_register_dict[instrfield]
                                if register == 'GPR':
                                    if register_alias not in function_list and register_alias not in ast_clause_list:
                                        content_function += "\tlet " + register_alias + "_val" + " = "
                                        content_function += "X(" + register_alias + ");\n" 
                                        function_list.append(register_alias)
                                        ast_clause_list.append(register_alias)
                                        instrfields[register_alias] = {}
                                        destination = register_alias
            if 'load' in instructions[instr]['attributes']:
                action = instructions[instr]['action']
                line_list = action.split("\n")
                destination = ""
                destination_list = list()
                refs = dict()
                mem_values = dict()
                variable = list()
                index_var = 0
                destination_vars = dict()
                content_list = content_function.split("\n")
                line_index = 0
                condition = ""
                check_condition = True
                condition_dict = dict()
                condition_list = list()
                for line in line_list:
                    line_index += 1
                    source = ""
                    operator_sign = ""
                    line_copy = line
                    line = line.replace(" ", "")
                    right_exp = ""
                    if "=" in line:
                        right_exp = line.split("=")[1]
                    if line.startswith("if"):
                        condition = line_copy.replace("{", "")
                        while line_list[line_index].endswith("}") is False:
                            condition_list.append(line_list[line_index].replace(" ", ""))
                            line_index += 1
                    if len(condition_list) > 0 and condition != "":
                        condition_dict[condition.lstrip(" ")] = condition_list
                        condition_list = list()
                    if line.startswith("var"):
                        left_exp = line.split("=")[0].replace("var", "")
                        if left_exp != "":
                            variable.append(left_exp)
                        destination = left_exp
                        if destination not in destination_vars.keys():
                            destination_vars[destination] = ""
                    else:
                        left_exp = line.split("=")[0]
                        destination = left_exp
                    ref = ""
                    if 'Mem' in right_exp:
                        right_exp = right_exp.replace('Mem', "").replace("(", "").replace(")", "")
                        var = right_exp.split(",")[0].replace(";", "")
                        value = right_exp.split(",")[1].replace(";", "")
                        mem_values[var] = value
                    for register in register_parsed.keys():
                        if register in right_exp:
                            right_exp = right_exp.replace(register, "")
                            ref = register
                            break
                    right_op_checked = False
                    for instrfield in instrfields.keys():
                        if instrfield in right_exp:
                            if "(" + instrfield + ")" in right_exp:
                                right_exp = right_exp.replace("(" + instrfield + ")", "")
                                source = instrfield
                                right_op_checked = True
                    refs[ref] = source
                    for imm in instrfield_imm.keys():
                        if imm in right_exp:
                            right_exp = right_exp.replace(imm, "")
                            imm_value = imm
                            operator_sign = right_exp.replace(" ", "").replace(";", "")
                            right_op_checked = True
                    if right_op_checked is False:
                        if right_exp.replace(";", "") in variable:
                            destination_vars[right_exp] = ""
                    left_exp = left_exp.replace(";", "") 
                    for register in register_parsed.keys():
                        if register in left_exp:
                            left_exp = left_exp.replace(register, "")
                            ref = register
                            break
                    for instrfield in instrfields.keys():
                        if instrfield in left_exp:
                            if "(" + instrfield + ")" in left_exp:
                                left_exp = left_exp.replace("(" + instrfield + ")", "")
                                destination = instrfield
                                if destination not in destination_list:
                                    destination_list.append(destination)
                                    if right_op_checked is False:
                                        destination_vars[right_exp.replace(";", "").split(",")[0]] = destination
                            else:
                                if instrfield + "+1" in left_exp:
                                    left_exp = left_exp.replace("(" + instrfield + "+1" + ")", "")
                                    destination = instrfield + "+1"
                                    if destination not in destination_list:
                                        destination_list.append(destination)
                                        if right_op_checked is False:
                                            destination_vars[right_exp.replace(";", "").split(",")[0]] = destination
                    content_list_copy = content_list
                    for line_content in content_list:
                        if destination in instrfields.keys():
                            if destination + "_val" in line_content:
                                content_list_copy.remove(line_content)
                        if source in instrfields.keys():
                            if source + "_val" in line_content:
                                if len(variable) > 0 and variable[index_var] != "":
                                    content_list_copy.remove(line_content)
                                    line_content = line_content.replace(source + "_val", variable[index_var])
                                    line_content = line_content.replace(";", " + offset;\n")
                                    content_list_copy.append(line_content)
                        if len(variable) > 0:
                            if index_var < len(variable)-1:
                                index_var += 1
                index_var = 0
                while "" in content_list_copy:
                    content_list_copy.remove("")
                for line in content_list_copy:
                    if len(variable) > 0 and variable[0] not in line:
                        if "_idx" in line:
                            for instrfield in instrfields.keys():
                                if instrfield + "_idx" == line.split("=")[0].replace(" ", "").replace("\tlet", ""):
                                    if instrfields[instrfield]['ref'] == 'GPR':
                                        if instrfield not in destination_list:
                                            new_line = "\tlet " + variable[0] + " = " + "X(" + instrfield + "_idx" + ") + offset;"
                                            content_list_copy.append(new_line)
                        if source == "":
                            instrfield = line.split("=")[0].replace("\tlet", "").strip(" ")
                            if instrfield.replace("_val", "") in instrfields.keys():
                                for field in instructions[instr]['fields'][0]:
                                    if field in instrfield_imm.keys():
                                        new_line = line.replace(instrfield, variable[0]).replace(";", " + offset;")
                                        if line in content_list_copy:
                                            content_list_copy.remove(line)
                                            content_list_copy.append(new_line)
                content_new = "\n".join(content_list_copy)
                if "imm_val" in content_new:
                    content_new = content_new.replace("imm_val", "offset")
                if content_new.endswith("\n") is False:
                    content_new += "\n"
                p_address = ""
                if len(variable) > 0:
                    p_address = variable[index_var].replace('v', 'p')
                    virtual_address = variable[index_var]
                    content_new += "\tif xlen == 32 then\n"
                    if_activated = True
                    content_new += "\tif check_misaligned(" +  "virtaddr" + "(" + virtual_address + ")" + ", DOUBLE)\n"
                    content_new += "\tthen {handle_mem_exception(" + "virtaddr" + "(" + virtual_address + ")"  + ", E_Load_Addr_Align()); RETIRE_FAIL}\n"
                    content_new += "\telse match translateAddr(" + "virtaddr" + "(" + virtual_address + ")"  + ", Read(Data)) {\n"
                    content_new += "\tTR_Failure(e, _) => {handle_mem_exception(" + "virtaddr" + "(" + virtual_address + ")"  + ", e); RETIRE_FAIL},\n"
                    p_address = variable[index_var].replace('v', 'p')
                    virtual_address = variable[index_var]
                content_new += "\tTR_Address(" + p_address + ", _) =>\n"
                if  len(variable) > 0 and len(variable) - 1 > index_var:
                    index_var += 1
                if len(list(mem_values.keys())) > 0:
                    index = 0
                    key_mem = list(mem_values.keys())[index]
                    content_new += "\t\tmatch mem_read(Read(Data), " + p_address + ", " + mem_values[key_mem] + ", " + "false, false, false) {\n"
                if len(variable) > 0:
                    content_new += "\t\tOk(" + variable[index_var] + ") => {\n"
                if  len(variable) > 0 and len(variable) - 1 > index_var:
                    index_var += 1
                if len(list(mem_values.keys())) > 1:
                    index += 1
                    content_new += "\t\t\tmatch translateAddr(" + "virtaddr" + "(" + list(mem_values.keys())[index] + ")" + ", " + "Read(Data)) {\n"
                    content_new += "\t\t\tTR_Failure(e, _) => {handle_mem_exception(" + "virtaddr" + "(" + list(mem_values.keys())[index] + ")" + ", e); RETIRE_FAIL},\n"
                    p_shift_addr = list(mem_values.keys())[index].replace("v", "p")
                    key_mem = list(mem_values.keys())[index]
                    pattern = re.compile(r'[a-zA-Z0-9]*')
                    list_regex = pattern.findall(p_shift_addr)
                    while '' in list_regex:
                        list_regex.remove('')
                    p_shift_addr = str(list_regex[0]) + "_" + str(list_regex[1:]).replace("['", "").replace("']", "")
                    content_new += "\t\t\tTR_Address("  + p_shift_addr + ", _) =>\n"
                    content_new += "\t\t\t\tmatch mem_read(Read(Data), " + p_shift_addr + ", " + mem_values[key_mem] + ", false, false, false) {\n"
                if  len(variable) > 0:
                    content_new += "\t\t\t\tOk(" + variable[index_var] + ") => {\n"
                condition_line = list()
                for element in destination_list:
                    if element in instrfields.keys() and instrfields[element]['ref'] == 'GPR':
                        for key_var in destination_vars.keys():
                            if element == destination_vars[key_var]:
                                if str(2 ** int(instrfields[element]['width'])) != config_variables['LLVMRegBasicWidth']:
                                    condition_line.append(instrfields[element]['ref'] +"(" + element + ")=" + key_var + ";")
                                    break
                    else:
                        if "+1" in element:
                            if element.replace("+1", "") in instrfields.keys() and instrfields[element.replace("+1", "")]['ref'] == 'GPR':
                                for key_var in destination_vars.keys():
                                    if element == destination_vars[key_var]:
                                        if str(2 ** int(instrfields[element.replace("+1", "")]['width'])) != config_variables['LLVMRegBasicWidth']:
                                            condition_line.append(instrfields[element.replace("+1", "")]['ref'] +"(" + element + ")=" + key_var + ";")
                                            break
                for line in condition_line:
                    if condition != "" and condition in condition_dict.keys():
                        if line not in condition_dict[condition]:
                            check_condition = False
                if check_condition is True:
                    pattern = re.findall(r"\w+\d*\_*\w+", condition)
                    for instrfield in instrfields.keys():
                        for element in pattern:
                            if element == instrfield:
                                if str(2 ** int(instrfields[element]['width'])) != config_variables['LLVMRegBasicWidth']:
                                    condition = condition.replace(element, element + "_idx")
                                    condition = condition.replace(element, "encdec_creg(" + element + ")")
                                elif str(2 ** int(instrfields[element]['width'])) == config_variables['LLVMRegBasicWidth']:
                                    condition = condition.replace(element, "encdec_reg(" + element + ")")
                    pattern_digit = re.findall(r"\d+", condition)
                    if "(" in condition:
                        condition = condition.replace("(", "", 1)
                    if condition.rstrip(" \n").endswith(")"):
                        condition = condition[:-2]
                    if len(pattern_digit) > 0:
                        condition = condition.replace(pattern_digit[0], num2words.num2words(pattern_digit[0]) + "s()")
                    if condition != "":
                        content_new += "\t\t\t\t" + condition + " then {\n"
                for element in destination_list:
                    if element in instrfields.keys() and instrfields[element]['ref'] == 'GPR':
                        for key_var in destination_vars.keys():
                            if element == destination_vars[key_var]:
                                if str(2 ** int(instrfields[element]['width'])) != config_variables['LLVMRegBasicWidth']:
                                    content_new += "\t\t\t\t\tX(" + element + "_idx" + ") = " + "sign_extend(" + key_var + ");\n"
                                    break
                                else:
                                    content_new += "\t\t\t\t\tX(" + element + ") = " + "sign_extend(" + key_var + ");\n"
                                    break
                    else:
                        if "+1" in element:
                            if element.replace("+1", "") in instrfields.keys() and instrfields[element.replace("+1", "")]['ref'] == 'GPR':
                                for key_var in destination_vars.keys():
                                    if element == destination_vars[key_var]:
                                        if str(2 ** int(instrfields[element.replace("+1", "")]['width'])) != config_variables['LLVMRegBasicWidth']:
                                            element = "regidx_offset(" + element.replace("+1", "") + "_idx" + ", to_bits(" + str(math.log(int(config_variables['LLVMRegBasicWidth']), 2)).replace(".0", "") + ", " + "1))"
                                            content_new += "\t\t\t\t\tX(" + element + ") = " + "sign_extend(" + key_var + ")" + ";\n"
                                            break
                                        else:
                                            element = "regidx_offset(" + element.replace("+1", "") + ", to_bits(" + str(math.log(int(config_variables['LLVMRegBasicWidth']), 2)).replace(".0", "") + ", " + "1))"
                                            content_new += "\t\t\t\t\tX(" + element + ") = " + "sign_extend(" + key_var + ")" + ";\n"
                                            break
                if condition != "":
                  content_new += "\t\t\t\t\t};\n"   
                content_new += "\t\t\t\t\tRETIRE_SUCCESS\n"
                content_new += "\t\t\t\t},\n"
                if  len(variable) > 0:
                    content_new += "\t\t\t\tErr(e) => {handle_mem_exception(" + "virtaddr" + "(" + virtual_address + ")" + ", e); RETIRE_FAIL},\n"
                content_new += "\t\t\t}\n"
                content_new += "\t\t}\n"
                content_new += "\t},\n"
                if  len(variable) > 0:
                    content_new += "\tErr(e) => {handle_mem_exception(" + "virtaddr" + "(" + virtual_address + ")" + ", e); RETIRE_FAIL},\n"
                content_new += "\t},\n"
                content_new += "}\n"
                content_function = content_new
            elif 'store' in instructions[instr]['attributes']:
                action = instructions[instr]['action']
                line_list = action.split("\n")
                destination = ""
                destination_list = list()
                refs = dict()
                mem_values = dict()
                variable = list()
                index_var = 0
                destination_vars = dict()
                content_list = content_function.split("\n")
                condition_dict = dict()
                condition_list = list()
                line_index = 0
                for line in line_list:
                    line_index += 1
                    line_index_copy = line_index
                    source = ""
                    operator_sign = ""
                    line_copy = line
                    line = line.replace(" ", "")
                    right_exp = ""
                    if "=" in line:
                        right_exp = line.split("=")[1]
                    if line.startswith("if"):
                        condition = line_copy.replace("{", "")
                        while line_list[line_index_copy].endswith("}") is False:
                            condition_list.append(line_list[line_index_copy].replace(" ", ""))
                            line_index_copy += 1
                        if len(condition_list) > 0 and condition != "":
                            condition_dict[condition.lstrip(" ")] = condition_list
                            condition_list = list()
                    line_index_copy = line_index
                    if line.startswith("else"):
                        condition = line_copy.replace("{", "")
                        while line_list[line_index_copy].endswith("}") is False:
                            condition_list.append(line_list[line_index_copy].replace(" ", ""))
                            line_index_copy += 1
                        if len(condition_list) > 0 and condition != "":
                            condition_dict[condition.lstrip(" ")] = condition_list
                            condition_list = list()
                    if line.startswith("var"):
                        left_exp = line.split("=")[0].replace("var", "")
                        if left_exp != "":
                            variable.append(left_exp.replace(";", ""))
                    else:
                        left_exp = line.split("=")[0]
                    ref = ""
                    if 'Mem' in left_exp:
                        left_exp = left_exp.replace('Mem', "").replace("(", "").replace(")", "")
                        var = left_exp.split(",")[0].replace(";", "")
                        value = left_exp.split(",")[1].replace(";", "")
                        mem_values[var] = value
                    for register in register_parsed.keys():
                        if register in right_exp:
                            right_exp = right_exp.replace(register, "")
                            ref = register
                            break
                    right_op_checked = False
                    for instrfield in instrfields.keys():
                        if instrfield in right_exp:
                            if "(" + instrfield + ")" in right_exp:
                                right_exp = right_exp.replace("(" + instrfield + ")", "")
                                source = instrfield
                                right_op_checked = True
                    refs[ref] = source
                    for imm in instrfield_imm.keys():
                        if imm in right_exp:
                            right_exp = right_exp.replace(imm, "")
                            imm_value = imm
                            operator_sign = right_exp.replace(" ", "").replace(";", "")
                            right_op_checked = True
                    if right_op_checked is False:
                        if right_exp.replace(";", "") in variable:
                            destination_vars[right_exp] = ""
                    left_exp = left_exp.replace(";", "") 
                    for register in register_parsed.keys():
                        if register in left_exp:
                            left_exp = left_exp.replace(register, "")
                            ref = register
                            break
                    for instrfield in instrfields.keys():
                        if instrfield in left_exp:
                            if "(" + instrfield + ")" in left_exp:
                                left_exp = left_exp.replace("(" + instrfield + ")", "")
                                destination = instrfield
                                if destination not in destination_list:
                                    destination_list.append(destination)
                                    if right_op_checked is False:
                                        destination_vars[right_exp.replace(";", "").split(",")[0]] = destination
                            else:
                                if instrfield + "+1" in left_exp:
                                    left_exp = left_exp.replace("(" + instrfield + "+1" + ")", "")
                                    destination = instrfield + "+1"
                                    if destination not in destination_list:
                                        destination_list.append(destination)
                                        if right_op_checked is False:
                                            destination_vars[right_exp.replace(";", "").split(",")[0]] = destination
                    content_list_copy = content_list
                    for line_content in content_list:
                        if destination in instrfields.keys():
                            if destination + "_val" in line_content:
                                content_list_copy.remove(line_content)
                        if source in instrfields.keys():
                            if source + "_val" in line_content:
                                if len(variable) > 0 and variable[index_var] != "":
                                    content_list_copy.remove(line_content)
                                    line_content = line_content.replace(source + "_val", variable[index_var])
                                    line_content = line_content.replace(";", " + offset;\n")
                                    found = False
                                    for line_variable in content_list_copy:
                                        if variable[index_var] in line_variable:
                                            found = True
                                    if found is False:
                                        content_list_copy.append(line_content)
                        if len(variable) > 0:
                            first_reg = ""
                            for variable_elem in variable:
                                if variable_elem in line_content and variable_elem != variable[0]:
                                        content_list_copy.remove(line_content)       
                        if len(variable) > 0:
                            if index_var < len(variable)-1:
                                index_var += 1
                index_var = 0
                while "" in content_list_copy:
                    content_list_copy.remove("")
                variable_used = list()
                for line in content_list_copy:
                    if len(variable) > 0 and variable[0] not in line:
                        if "_idx" in line:
                            for instrfield in instrfields.keys():
                                if instrfield + "_idx" == line.split("=")[0].replace(" ", "").replace("\tlet", ""):
                                    if instrfields[instrfield]['ref'] == 'GPR':
                                        if instrfield not in destination_list:
                                            if variable[0] not in variable_used:
                                                new_line = "\tlet " + variable[0] + " = " + "X(" + instrfield + "_idx" + ") + offset;"
                                                content_list_copy.append(new_line)
                                                variable_used.append(variable[0])
                        if source == "":
                            instrfield = line.split("=")[0].replace("\tlet", "").strip(" ")
                            if instrfield.replace("_val", "") in instrfields.keys():
                                for field in instructions[instr]['fields'][0]:
                                    if field in instrfield_imm.keys():
                                        new_line = line.replace(instrfield, variable[0]).replace(";", " + offset;")
                                        if line in content_list_copy:
                                            content_list_copy.remove(line)
                                            content_list_copy.append(new_line)
                content_new = "\n".join(content_list_copy)
                if "imm_val" in content_new:
                    content_new = content_new.replace("imm_val", "offset")
                if content_new.endswith("\n") is False:
                    content_new += "\n"
                if len(variable) > 0:
                    p_address = variable[index_var].replace('v', 'p')
                    virtual_address = variable[index_var]
                    if_activated = True
                    content_new += "\tif xlen == 32 then\n"
                    content_new += "\tif check_misaligned(" + "virtaddr" + "(" + virtual_address + ")" + ", DOUBLE)\n"
                    content_new += "\tthen {handle_mem_exception(" + "virtaddr" + "(" + virtual_address + ")"  + ", E_SAMO_Addr_Align()); RETIRE_FAIL}\n"
                    content_new += "\telse match translateAddr(" +"virtaddr" + "(" + virtual_address + ")"  + ", Read(Data)) {\n"
                    content_new += "\tTR_Failure(e, _) => {handle_mem_exception(" + "virtaddr" + "(" + virtual_address + ")"  + ", e); RETIRE_FAIL},\n"
                content_new += "\tTR_Address(" + p_address + ", _) =>\n"
                if  len(variable) > 0 and len(variable) - 1 > index_var:
                    index_var += 1
                if len(list(mem_values.keys())) > 0:
                    index = 0
                    key_mem = list(mem_values.keys())[index]
                    content_new += "\t\tmatch mem_write_ea(" + p_address + ", " + mem_values[key_mem] + ", " + "false, false, false) {\n"
                if len(variable) > 0:
                    content_new += "\t\tOk(" + "_" + ") => {\n"
                    element_reg = ""
                    element_reg_dict = dict()
                    if index_var > 0:
                        for line_content in line_list:
                            if variable[index_var] in line_content:
                                if "="in line_content:
                                    right_op = line_content.split("=")[1]
                                for register in register_parsed.keys():
                                    if register in right_op:
                                        right_op = right_op.replace("(", "").replace(register, "").replace(")", "")
                                        if operator_sign in right_op:
                                            right_op = right_op.replace(operator_sign, "")
                                        for imm in instrfield_imm.keys():
                                            if imm in right_op:
                                                right_op = right_op.replace(imm, "").replace(";", "")
                                        right_op = right_op.replace(";", "").replace(" ", "")
                                        if register == 'GPR':
                                            if right_op in instrfields.keys() or right_op.replace("+1", "") in instrfields.keys():
                                                if str(2 ** int(instrfields[right_op.replace("+1", "")]['width'])) != config_variables['LLVMRegBasicWidth']:
                                                    if '+1' in right_op:
                                                        element_reg = "X(" + right_op.replace("+1", "") + "_idx" + "+1)"
                                                    else:
                                                        element_reg = "X(" + right_op + "_idx" + ")"
                                                else:
                                                    element_reg = "X(" + right_op + ")"
                                                element_reg_dict[variable[index_var]] = element_reg
                                                if  len(variable) > 0 and len(variable) - 1 > index_var:
                                                    index_var += 1
                        index_var = 1
                        if variable[index_var] in element_reg_dict.keys():
                            content_new += "\t\t\tlet " + variable[index_var] + " : MemoryOpResult(bool) = mem_write_value(" + p_address + ", " + mem_values[key_mem] + ", " + element_reg_dict[variable[index_var]] + ", " + "false, false, false) in\n"
                        content_new += "\t\t\tmatch result {\n"
                        content_new += "\t\t\t\tOk(true) =>{\n"
                if  len(variable) > 0 and len(variable) - 1 > index_var:
                    index_var += 1
                virtual_shift_address = ""
                if len(list(mem_values.keys())) > 1:
                    index += 1
                    content_new += "\t\t\t\tmatch translateAddr(" + "virtaddr" + "(" + list(mem_values.keys())[index] + ")" + ", " + "Write(Data)) {\n"
                    content_new += "\t\t\t\tTR_Failure(e, _) => {handle_mem_exception(" + "virtaddr" + "(" + list(mem_values.keys())[index] + ")" + ", e); RETIRE_FAIL},\n"
                    p_shift_addr = list(mem_values.keys())[index].replace("v", "p")
                    key_mem = list(mem_values.keys())[index]
                    pattern = re.compile(r'[a-zA-Z0-9]*')
                    list_regex = pattern.findall(p_shift_addr)
                    while '' in list_regex:
                        list_regex.remove('')
                    p_shift_addr = str(list_regex[0]) + "_" + str(list_regex[1:]).replace("['", "").replace("']", "")
                    virtual_shift_address = str(list_regex[0]).replace("p", "v") + "+" + str(list_regex[1:]).replace("['", "").replace("']", "")
                    content_new += "\t\t\t\tTR_Address("  + p_shift_addr + ", _) =>\n"
                    content_new += "\t\t\t\t\tmatch mem_write_ea(" + p_shift_addr + ", " + mem_values[key_mem] + ", false, false, false) {\n"
                    content_new += "\t\t\t\t\t\tOk(" + "_" + ") => {\n"
                    value_condition_checked = False
                    instrfield_set = ""
                    if len(condition_dict.keys()) > 0:
                        for condition_key in condition_dict.keys():
                            condition_line = condition_dict[condition_key][0]
                            if 'if' in condition_key:
                                condition_line = condition_line.replace(variable[index_var], "")
                                pattern = re.findall(r"\d+", condition_line)
                                pattern_instr = re.findall(r"\w+\d*\_*\w*", condition_key)
                                for instrfield in instrfields.keys():
                                    for key_pat in pattern_instr:
                                        if instrfield == key_pat:
                                            if key_pat in condition_key:
                                                if str(2 ** int(instrfields[key_pat]['width'])) != config_variables['LLVMRegBasicWidth']:
                                                    condition_key = condition_key.replace(key_pat, key_pat+"_idx")
                                                    condition_key = condition_key.replace(key_pat+"_idx", "encdec_creg("+key_pat+"_idx"+")")
                                                    break
                                                else:
                                                    condition_key = condition_key.replace(key_pat, "encdec_reg("+key_pat+")")
                                                    break
                                            elif key + "+1" in condition_key:
                                                if str(2 ** int(instrfields[key_pat]['width'])) != config_variables['LLVMRegBasicWidth']:
                                                    condition_key = condition_key.replace(key_pat + "+1", key_pat + "+1" +"_idx")
                                                    condition_key = condition_key.replace(key_pat + "+1" +"_idx", "encdec_creg("+key_pat + "+1" +"_idx"+")")
                                                    break
                                if "(" in condition_key:
                                    condition_key = condition_key.replace("(", "", 1)
                                if condition_key.rstrip(" \n").endswith(")"):
                                    condition_key = condition_key[:-2]
                                content_new += "\t\t\t\t\t\t\tlet value : xlenbits = " + condition_key.replace(pattern[0], num2words.num2words(pattern[0])).rstrip(" ") + "s()" + " then " + num2words.num2words(pattern[0]) + "s()" + " "
                            if 'else'  in condition_key:
                                for element in variable:
                                    if element  + "=" in condition_line:
                                        condition_line = condition_line.replace(element + "=", "")
                                if 'GPR' in condition_line:
                                    condition_line = condition_line.strip(";").replace('GPR', 'X')
                                    for instrfield in instrfields.keys():
                                        if "(" + instrfield + ")" in condition_line:
                                            instrfield_set = instrfield
                                            if str(2 ** int(instrfields[instrfield]['width'])) != config_variables['LLVMRegBasicWidth']:
                                                condition_line = condition_line.replace(instrfield, instrfield +"_idx")
                                        elif "(" + instrfield + "+1)" in condition_line:
                                            instrfield_set = instrfield
                                            if str(2 ** int(instrfields[instrfield]['width'])) != config_variables['LLVMRegBasicWidth']:
                                                condition_line = condition_line.replace(instrfield + "+1", instrfield + "+1" +"_idx")
                                condition_line = condition_line.replace(instrfield_set + "+1", "regidx_offset(" + instrfield_set + ", " + "to_bits(" + instrfields[instrfield_set]['width'] + ",1))")
                                content_new += condition_key + condition_line.strip(";") + " in" + "\n"
                                value_condition_checked = True
                    index_var = 0
                    if  len(variable) > 0 and len(variable) - 1 > index_var:
                        if index_var > 1:
                            if value_condition_checked is True:
                                content_new += "\t\t\t\t\t\t\tlet " + variable[index_var] + " : MemoryOpResult(bool) = mem_write_value(" + p_shift_addr + ", " + mem_values[key_mem] + ", " "value, " + "false, false, false) in\n"
                                content_new += "\t\t\t\t\t\t\tmatch " + variable[index_var] + " {\n"
                            else:
                                element_copy = element_reg_dict[variable[index_var]]
                                fixed_instrfield = ""
                                idx_enabled = False
                                if '+1' in element_copy:
                                    element_copy = element_copy.replace('+1', '')
                                if '_idx' in element_copy:
                                    element_copy = element_copy.replace("_idx", "")
                                    idx_enabled = True
                                element_copy_instrfield = element_copy.split("(")[1].replace(")", "")
                                for instrfield in instrfields.keys():
                                    if instrfield == element_copy_instrfield:
                                        fixed_instrfield = instrfield
                                        break
                                if idx_enabled is True:
                                    fixed_instrfield = element_copy_instrfield + "_idx"
                                if str(2 ** int(instrfields[element_copy_instrfield]['width'])) != config_variables['LLVMRegBasicWidth']:
                                    reg_function = element_copy.replace(element_copy_instrfield, "regidx_offset(" + fixed_instrfield + ", " + "to_bits(" + str(int(math.log2(int(config_variables['LLVMRegBasicWidth'])))) + ",1))")
                                else:
                                    reg_function = element_copy.replace(element_copy_instrfield, "regidx_offset(" + fixed_instrfield + ", " + "to_bits(" + instrfields[element_copy_instrfield]['width'] + ",1))")
                                content_new += "\t\t\t\t\t\t\tlet " + variable[index_var] + " : MemoryOpResult(bool) = mem_write_value(" + p_shift_addr + ", " + mem_values[key_mem] + ", " + reg_function + ", " + "false, false, false) in\n"
                                content_new += "\t\t\t\t\t\t\tmatch " + variable[index_var] + " {\n"
                        else:
                            while index_var <= 1:
                                index_var += 1
                            if index_var > 1:
                                if value_condition_checked is True:
                                    content_new += "\t\t\t\t\t\t\tlet " + variable[index_var] + " : MemoryOpResult(bool) = mem_write_value(" + p_shift_addr + ", " + mem_values[key_mem] + ", " "value, " + "false, false, false) in\n"
                                    content_new += "\t\t\t\t\t\t\tmatch " + variable[index_var] + " {\n"
                                else:
                                    element_copy = element_reg_dict[variable[index_var]]
                                    fixed_instrfield = ""
                                    idx_enabled = False
                                    if '+1' in element_copy:
                                        element_copy = element_copy.replace('+1', '')
                                    if '_idx' in element_copy:
                                        element_copy = element_copy.replace("_idx", "")
                                        idx_enabled = True
                                    element_copy_instrfield = element_copy.split("(")[1].replace(")", "")
                                    for instrfield in instrfields.keys():
                                        if instrfield == element_copy_instrfield:
                                            fixed_instrfield = instrfield
                                            break
                                    if idx_enabled is True:
                                        fixed_instrfield = element_copy_instrfield + "_idx"
                                    if str(2 ** int(instrfields[element_copy_instrfield]['width'])) != config_variables['LLVMRegBasicWidth']:
                                        reg_function = element_copy.replace(element_copy_instrfield, "regidx_offset(" + fixed_instrfield + ", " + "to_bits(" + str(int(math.log2(int(config_variables['LLVMRegBasicWidth'])))) + ",1))")
                                    else:
                                        reg_function = element_copy.replace(element_copy_instrfield, "regidx_offset(" + fixed_instrfield + ", " + "to_bits(" + instrfields[element_copy_instrfield]['width'] + ",1))")
                                    content_new += "\t\t\t\t\t\t\tlet " + variable[index_var] + " : MemoryOpResult(bool) = mem_write_value(" + p_shift_addr + ", " + mem_values[key_mem] + ", " + reg_function + ", " + "false, false, false) in\n"
                                    content_new += "\t\t\t\t\t\t\tmatch " + variable[index_var] + " {\n"
                index = 0
                if len(variable) > 0:
                    if virtual_shift_address != "":
                        content_new += "\t\t\t\t\t\t\t\tOk(true) => {RETIRE_SUCCESS},\n"
                        content_new += "\t\t\t\t\t\t\t\tOk(false) => {internal_error(__FILE__, __LINE__, \"" + instr.lower() + " failed\")},\n"
                        content_new += "\t\t\t\t\t\t\t\tErr(e) => {handle_mem_exception(" + "virtaddr" + "(" + virtual_shift_address + ")" + ", e); RETIRE_FAIL},\n"
                        content_new += "\t\t\t\t\t\t\t}\n"
                content_new += "\t\t\t\t\t},\n"
                if  len(variable) > 0:
                    content_new += "\t\t\t\tErr(e) => {handle_mem_exception(" + "virtaddr" + "(" + virtual_address + ")" + ", e); RETIRE_FAIL},\n"
                content_new += "\t\t\t\t}\n"
                content_new += "\t\t\t}\n"
                content_new += "\t\t\t},\n"
                if  len(variable) > 0:
                    index = 1
                    if len(list(mem_values.keys())) > index:
                        content_new += "\t\t\tOk(false) => {internal_error(__FILE__, __LINE__, \"" + instr.lower() + " failed\")},\n"
                        content_new += "\t\t\tErr(e) => {handle_mem_exception(" + "virtaddr" + "(" + list(mem_values.keys())[index] + ")" + ", e); RETIRE_FAIL},\n"
                content_new += "\t\t\t}\n"
                content_new += "\t\t},\n"
                if  len(variable) > 0:
                    content_new += "\t\tErr(e) => {handle_mem_exception(" + "virtaddr" + "(" + virtual_address + ")" + ", e); RETIRE_FAIL},\n"
                content_new += "\t\t},\n"
                content_new += "\t}\n"
                content_function = content_new
            else:
                action_parsed = instructions[instr]['action']
                regex = re.compile(r'(\w*\(+\w*\_*\d*\)+)=(\w*\(+\w*\_*\d*\)+)(.*[a-zA-Z]\(*[a-zA-Z0-9]*\_*\)*)(\(*\d*\,+\d*\)*)*')
                match = re.search(regex, action_parsed.replace(" ", ""))
                content_execute = ""
                content_execute_action = ""
                if match:
                    left = match.group(1)
                    right_op1 = match.group(2)
                    right_op2 = match.group(3)
                    index_values = match.group(4)
                    ref = ""
                    op1 = ""
                    op2 = ""
                    operator_sign = ""
                    for element in instructions[instr]['syntax']:
                        if element in instrfields.keys():
                            if 'ref' in instrfields[element].keys():
                                ref = instrfields[element]['ref']
                            if ref in left:
                                left = left.replace(ref, "").replace("(", "").replace(")", "")
                                if left in instrfields.keys():
                                    if str(instructions[instr]["fields"][0][left]) == "reg":
                                        if destination == "":
                                            destination = left
                            if ref in right_op2:
                                if op2 in instrfields.keys() or op2 in instrfield_imm.keys():
                                    op2 = right_op2.replace(ref, "").replace("(", "").replace(")", "")
                                if op2.startswith(element) is False:
                                    op2 = right_op2.replace(ref, "").replace("(", "").replace(")", "")
                                    operator_sign = op2.replace(element, "")
                                    op2 = op2.replace(operator_sign, "").replace("(", "").replace(")", "")
                            if ref == "":
                                for register in register_parsed.keys():
                                    op1 = right_op1.replace(register, "").replace("(", "").replace(")", "")
                                    prefix = register_parsed[register].prefix
                                    if prefix != "":
                                        element = prefix.upper() + op1.replace("?", "")
                                        if element.endswith("?"):
                                            element = element.rstrip("?")
                                        if element in alias_register_dict.keys():
                                            alias = alias_register_dict[element]
                                            op1 = alias
                            else:
                                if ref in right_op1:
                                    op1 = right_op1.replace(ref, "").replace("(", "").replace(")", "")
                                    op1 = op1.replace("?", "")
                                    if op1.isdigit:
                                        prefix = register_parsed[ref].prefix
                                        element = prefix.upper() + op1
                                        if element in alias_register_dict.keys():
                                            alias = alias_register_dict[element]
                                            op1 = alias
                        elif element in instrfield_imm.keys():
                            if right_op2.startswith(element) is False:
                                op2 = right_op2
                                operator_sign = op2.replace(element, "").replace("(", "").replace(")", "")
                                op2 = op2.replace(operator_sign, "").replace("(", "").replace(")", "")
                        index_values_first = ""
                        index_values_last = ""
                        if index_values is not None:
                            index_values_first = index_values.replace("(", "").replace(")", "").split(",")[0]
                            index_values_last = index_values.replace("(", "").replace(")", "").split(",")[1]
                    content_execute += "\tlet result : xlenbits = "
                    content_execute_action = False
                    function_call = False
                    if operator_sign.startswith("."):
                        operator_sign = operator_sign.replace(".", "")
                    regex = re.compile(r'[a-zA-Z]+')
                    if len(regex.findall(operator_sign)) > 0:
                        function_call = True
                    if function_call is True:
                        if op2 in instrfield_imm.keys():
                            content_execute_action = True
                            content_execute += operator_sign + "(" + op1 + "_val" + ", " + 'imm_val'
                        else:
                            content_execute_action = True
                            content_execute += operator_sign + "(" + op1 + "_val" + ", " + op2 + "_val"
                    else:
                        if op2 in instrfield_imm.keys():
                            content_execute_action = True
                            content_execute += op1 + "_val" + " " + operator_sign + " " + 'imm_val' + "\n"
                        else:
                            content_execute_action = True
                            content_execute += op1 + "_val" + " " + operator_sign + " " + op2 + "_val"
                    if function_call is True:
                        if index_values_first != "" and index_values_last != "":
                            content_execute_action = True
                            content_execute += "[" + index_values_first + ".." + index_values_last + "]" + ")\n"
                        else:
                            content_execute += ")\n"
                    else:
                        if index_values_first != "" and index_values_last != "":
                            content_execute_action = True
                            content_execute += "[" + index_values_first + ".." + index_values_last + "]"
                else:
                    action_parsed = instructions[instr]['action']
                    regex = re.compile(r'(\w*\(+\w*\_*\d*\)+)=(\w+\_*\(+)(\w+\(+)(\w+\_*)\,*(\w+\(*\d*\)*\)+)\,*(\d+\)*)([^a-zA-Z\d\s:])*(\w+)*')
                    match = re.search(regex, action_parsed.replace(" ", ""))
                    content_execute = ""
                    content_execute_action = ""
                    if match:
                        operator_sign = ''
                        right_operand = ''
                        left = match.group(1)
                        function1 = match.group(2)
                        function2 = match.group(3)
                        instrfield_used = match.group(4)
                        if match.group(7) is not None:
                            if match.group(7) != ";":
                                operator_sign = match.group(7)
                        if match.group(8) is not None:
                            right_operand = match.group(8)
                        for element in instructions[instr]['syntax']:
                            if element in instrfields.keys():
                                if 'ref' in instrfields[element].keys():
                                    ref = instrfields[element]['ref']
                                if ref in left:
                                    left = left.replace(ref, "").replace("(", "").replace(")", "")
                                    if left in instrfields.keys():
                                        if str(instructions[instr]["fields"][0][left]) == "reg":
                                            if destination == "":
                                                destination = left
                                content_list_aux = content_function.split("\n")
                                content_list_aux.remove('')
                                for line in content_list_aux:
                                    right_line = line.split("=")[1]
                                    if function1.lower().replace("(", "") == 'signextend':
                                        if "sign_extend" in right_line:
                                            if 'concat' == function2.replace("(", ""):
                                                value = match.group(5)
                                                value_index = value.split("(")[1].replace(")", "")
                                                value_number = word2number.w2n.word_to_num(value.split("(")[0])
                                                right_line_copy = right_line
                                                value_index = int(int(value_index) / 4)
                                                index = 0
                                                buffer_shift = ''
                                                for index in range(value_index):
                                                    buffer_shift += '0'
                                                    index += 1
                                                right_line = right_line.replace('imm', 'imm' + " @ " + '0x' + buffer_shift) 
                                                content_function = content_function.replace(right_line_copy, right_line)
                                        else:
                                            if 'concat' == function2.replace("(", ""):
                                                value = match.group(5)
                                                value_index = value.split("(")[1].replace(")", "")
                                                value_number = word2number.w2n.word_to_num(value.split("(")[0])
                                                right_line_copy = right_line
                                                value_index = int(int(value_index) / 4)
                                                index = 0
                                                buffer_shift = ''
                                                for index in range(value_index):
                                                    buffer_shift += '0'
                                                    index += 1
                                                right_line = right_line.replace('imm', 'sign_extend(imm' + " @ " + '0x' + buffer_shift + ")") 
                                                content_function = content_function.replace(right_line_copy, right_line)
                        content_execute += "\tlet result : xlenbits = "
                        if instrfield_used in instrfield_imm.keys():
                            content_execute_action = True
                            if operator_sign != '':
                                if right_operand != '':
                                    if right_operand == 'PC':
                                        right_operand = 'get_arch_pc()'
                                    content_execute += 'imm_val' + " " + operator_sign +  " " + right_operand + "\n" 
                                else:
                                    content_execute += 'imm_val' + "\n"
                            else:
                                content_execute += 'imm_val' + "\n"
                    else:
                        action_parsed = action_parsed.replace(" ", "")
                        action_parsed = action_parsed.split("\n")
                        action_parsed.remove('{'.strip(" "))
                        action_parsed.remove('}'.strip(" "))
                        condition = ""
                        result = ""
                        for line in action_parsed:
                            if line.startswith('if'):
                                condition += '\tif '
                                line = line.replace("if(", "")
                                line = line.strip(" ").replace("){", "")
                                for instrfield in instrfields.keys():
                                    if '(' + instrfield + ')' in line:
                                        if instrfields[instrfield]['ref'] in line:
                                            if instrfields[instrfield]['ref'] == 'GPR':
                                                line = line.replace(instrfields[instrfield]['ref'], "", 1).replace(instrfield, instrfield+"_val", 1).replace("(", "", 1).replace(")", "", 1)
                                copy_line = line
                                for instrfield in instrfields.keys():
                                    if instrfield + "_val" in copy_line:
                                        copy_line = copy_line.replace(instrfield + "_val", "")
                                if copy_line.startswith("if"):
                                    copy_line = copy_line.replace("if", "")
                                operand = copy_line.strip(" ")
                                operand_check = False
                                for instrfield in instrfields.keys():
                                    if 'signed' in operand:
                                        if operand == ".signedLT()":
                                            if ".signedLT(" + instrfield + "_val" + ")" in line:
                                                line = line.replace(".signedLT(" + instrfield + "_val" + ")", " <_s " + instrfield + "_val")
                                                operand_check = True
                                                break
                                        elif operand == ".signedGE()":
                                            if ".signedGE(" + instrfield + "_val" + ")" in line:
                                                line = line.replace(".signedGE(" + instrfield + "_val" + ")", " >=_s " + instrfield + "_val")
                                                operand_check = True
                                                break
                                    else:
                                        if ">=" + instrfield + "_val" in line:
                                            line = line.replace(">=" + instrfield + "_val", " >=" + "_u " + instrfield + "_val")
                                            operand_check = True
                                            break
                                        elif "<" + instrfield + "_val" in line:
                                            line = line.replace("<" + instrfield + "_val", " <" + "_u " + instrfield + "_val")
                                            operand_check = True
                                            break
                                if operand_check is False:
                                    line = line.replace(operand, " " + operand + " ")
                                pattern = re.findall(r'\s*\d+$', line.strip(" "))
                                if len(pattern) > 0:
                                    line = line.replace(pattern[0], " " + num2words.num2words(pattern[0]) + "s()")
                                condition += line
                            elif line.startswith('NIA'):
                                if "=" in line:
                                    result = line.split("NIA=")[1]
                            for instrfield in instrfield_imm.keys():
                                if "(" + instrfield + ")" in result:
                                    result = result.replace("(" + instrfield + ")", "imm_val")
                                    if 'sign_extend' in result:
                                        result = result.replace("sign_extend", "")
                                    break
                                else:
                                    if instrfield == result.strip(" ").strip(";"):
                                        result = result.replace(instrfield, "imm_val")
                                        break
                        content_execute += condition.rstrip(" ") + " then " + "{\n"
                        content_execute += "\t\tlet t : xlenbits = " + result + "\n"
                        if 'PC' in result:
                            content_execute += "\t\tset_next_pc(t);\n"
                        content_execute += "\t};\n"
                if content_execute_action is True and content_execute != "":
                    content_execute = content_execute.rstrip("\n")
                    content_execute = content_execute + " in" + "\n"
                if destination in instrfields.keys():
                    if 'ref' in instrfields[destination]:
                        ref = instrfields[destination]['ref']
                        if ref == 'GPR':
                            if compressed_reg is True:
                                content_execute += "\tX(" + destination + "_idx" + ") = result;\n"
                            else:
                                content_execute += "\tX(" + destination + ") = result;\n"
                    else:
                        content_execute += "\tX(" + destination + ") = result;\n"
                content_function += content_execute
                content_function += "\tRETIRE_SUCCESS\n"
            if if_activated is True:
                content_function += "\telse RETIRE_FAIL\n"
            content_function += "}"
            ast_clause = "union clause ast = " + key.upper() + " : " + "("
            for element in ast_clause_list:
                if element in instrfield_imm.keys():
                    ast_clause += "bits(" + str(int(instrfield_imm[element]['width'])) + ")"
                    ast_clause += ", "
                elif element in instrfields.keys():
                    if 'width' in instrfields[element].keys():
                        if str(2 ** int(instrfields[element]['width'])) != config_variables['LLVMRegBasicWidth']:
                            ast_clause += "cregidx" + ", "
                        else:
                            ast_clause += "regidx" + ", "
            if ast_clause.endswith(", "):
                ast_clause = ast_clause.rstrip(", ")
            ast_clause += ")"
            if len(extensions_list) > 0:
                for element in extensions_list:
                    if element in instructions[instr]['attributes']:
                        if instr not in instruction_parsed_and_printed:
                            instruction_parsed_and_printed.append(instr)
                            file_name = path.replace("ext", element.lower())
                            f = open(file_name, 'a')
                            f.write(ast_clause)
                            f.write("\n\n")
                            f.write(statement + "\n" + "\t" + if_statement + "\n" + content + "\n" + "\t" + if_statement)
                            f.write("\n\n")
                            f.write(function_clause + content_function + "\n")
                            f.write("\n")
                            f.write(statement_assembly + "\n" + "\t" + if_statement + "\n" + content_assembly + "\n" + "\t" + if_statement)
                            f.write("\n\n")
                            f.close()
            else:
                for element in config_variables.keys():
                    if element.startswith("LLVMExt"):
                        if element.replace("LLVMExt", "").lower() in instructions[instr]['attributes']:
                            if instr not in instruction_parsed_and_printed:
                                instruction_parsed_and_printed.append(instr)
                                file_name = path.replace("ext", element.replace("LLVMExt", "").lower())
                                file_name = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', file_name)
                                f = open(file_name, 'a')
                                f.write(ast_clause)
                                f.write("\n\n")
                                f.write(statement + "\n" + "\t" + if_statement + "\n" + content + "\n" + "\t" + if_statement)
                                f.write("\n\n")
                                f.write(function_clause + content_function + "\n")
                                f.write("\n")
                                f.write(statement_assembly + "\n" + "\t" + if_statement + "\n" + content_assembly + "\n" + "\t" + if_statement)
                                f.write("\n\n")
                                f.close()
                                
## This function generates the description for adding a new feature in LLVM project
#
# @param file_name Specifies the file in which the content will be generated
# @param extension_list Specifies the list of extensions enabled
# @return It returns the definition for a new feature                                 
def generate_extension_definition(file_name, extension_list):
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0]
    attributes = list()
    experimental_extensions = list()
    for key in instructions.keys():
        for attribute in instructions[key]['attributes']:
            if attribute not in attributes:
                attributes.append(attribute)
                if 'experimental' in instructions[key].keys():
                    experimental_extensions.append(attribute)
    extension_attributes = list()
    major_version = ""
    minor_version = ""
    description = ""
    f = open(file_name, "a")
    legalDisclaimer.get_copyright(file_name)
    for attribute in attributes:
        if "LLVMExt" + attribute.capitalize() in config_variables.keys():
            extension_attributes.append(attribute.capitalize())
    for extension in extension_attributes:
        statement = "def FeatureStdExt" + extension.capitalize() + " : \n"
        if attribute in experimental_extensions:
            statement += "\t\tRISCVExperimentalExtension<"
        else:
            statement += " RISCVExtension<"
        if extension.lower() == 'zma':
            description = "Zma Matrix Arithmetic"
            major_version = 1
            minor_version = 0
        statement += "\"" + extension.lower() + "\"" + ", " + str(major_version) + ", " + str(minor_version) + ", " + "\"" + description + "\"" + ">;\n"
        definition = " def HasStdExt" + extension.capitalize() + " : " + "Predicate<" + "\"" + "Subtarget->hasStdExt" + extension.capitalize() + "()" + "\">,\n"
        definition += "\t\tAssemblerPredicate<(all_of FeatureStdExt" + extension.capitalize() + "), " + "\"" + description +  "\"" + ">;\n" 
        if len(extension_list) > 0 and extension.lower() in extension_list:
            f.write(statement + definition)
        elif len(extension_list) == 0:
            f.write(statement + definition)
    f.close()