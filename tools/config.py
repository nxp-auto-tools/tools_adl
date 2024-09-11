# Copyright 2024 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package config
#
# The configuration module which parses the config.txt file
import re


## A function that parses each line from config.txt using regular expressions
#
# @param config_file The configuration file 'config.txt'
# @param llvm_file A file which contains the setup required by LLVM for proper functionality
# @return A dictionary where key and value are the contents of config.txt
def config_environment(config_file, llvm_file):
    config_vars = dict()
    configuration_file = open(config_file, "r")
    Lines = configuration_file.readlines()
    for line in Lines[1:]:
        if line == "\n":
            Lines.remove(line)
    for line in Lines[1:]:
        newline = line.strip()
        x = re.findall(
            '\.*[\#"a-z_A-Z0-9]*\/*\:*[\#"a-z_A-Z0-9]*\/*\.*[\#"a-z_A-Z0-9]*\/*\.*[\#"a-zA-z0-9\.]*',
            newline,
        )
        args = [elem.strip(" ") for elem in x if elem != ""]
        if args[0] == "ADLName":
            if len(args) > 2:
                args[1] = args[1] + str(args[2:][0])
        if args[0] == "IgnoredAttrib":
            ignored_attrib = list(args[1:])
            config_vars[args[0]] = ignored_attrib
        elif args[0] == "ApprovedImm":
            approved_imm = list(args[1:])
            config_vars[args[0]] = approved_imm
        elif args[0] == "IgnoredInstructions":
            ignored_inst = list(args[1:])
            config_vars[args[0]] = ignored_inst
        else:
            config_vars[args[0]] = args[1]
    configuration_file.close()
    configuration_file = open(llvm_file, "r")
    Lines = configuration_file.readlines()
    for line in Lines[1:]:
        if line == "\n":
            Lines.remove(line)
    for line in Lines[1:]:
        newline = line.strip()
        if newline.startswith("//"):
            continue
        x = re.findall(
                '\.*[\#"a-z_A-Z0-9]*\/*\:*[\#"a-z_A-Z0-9]*\/*\.*[\#"a-z_A-Z0-9]*\/*\.*[\#"a-zA-z0-9\.]*\/*[\-*a-zA-Z\/*]*',
            newline,
        )
        args = [elem.strip(" ") for elem in x if elem != ""]
        if args[0] == "XLenRI":
            x = re.findall("[A-Za-z0-9]*\<[0-9\,]*\>", newline)
            args_len = [elem for elem in x if elem != ""]
            config_vars[args[0]] = args_len[0]
        elif args[0] == "AsmString":
            regex = re.compile(r"[a-z_A-Z0-9]*[a-zA-Z0-9\ \#\ \"\\t\"\ \#\ a-zA-Z0-9]*")
            x = re.findall(regex, newline)
            args_len = [elem for elem in x if elem != ""]
            config_vars[args[0]] = str(args_len[1])
        elif args[0] == "ImmAsmOperandDiagnosticType":
            regex = re.compile(r"\![a-zA-Z0-9]*[()\"a-zA-Z0-9\, ]*")
            x = re.findall(regex, newline)
            args_len = [elem for elem in x if elem != ""]
            config_vars[args[0]] = str(args_len[0])
        elif args[0] == "CLUIImmAsmOperandDiagnosticType":
            regex = re.compile(r"\![a-zA-Z0-9]*[()\"a-zA-Z0-9\, ]*")
            x = re.findall(regex, newline)
            args_len = [elem for elem in x if elem != ""]
            config_vars[args[0]] = str(args_len[0])
        elif args[0] == "FENCEDecoderMethod":
            regex = re.compile(r"[a-zA-Z0-9<>]*")
            x = re.findall(regex, newline)
            args_len = [elem for elem in x if elem != ""]
            config_vars[args[0]] = str(args_len[1])
        elif args[0] == "LLVMOtherVTAttrib":
            vt_attrib = list(args[1:])
            config_vars[args[0]] = vt_attrib
        elif args[0] == "LLVMOtherVTReloc":
            vt_attrib = list(args[1:])
            config_vars[args[0]] = vt_attrib
        elif args[0] == "LLVMOperandTypeAttrib":
            operand_type = list(args[1:])
            config_vars[args[0]] = operand_type
        elif args[0] == "LLVMPrintMethodAttrib":
            print_method = list(args[1:])
            config_vars[args[0]] = print_method
        elif args[0] == "LLVMPrintMethodReloc":
            print_method = list(args[1:])
            config_vars[args[0]] = print_method
        elif args[0] == "LLVMOperandTypeReloc":
            operand_type = list(args[1:])
            config_vars[args[0]] = operand_type
        elif args[0] == "SImmAsmOperandParameters":
            operand_type = list(args[1:])
            config_vars[args[0]] = operand_type
        elif args[0] == "UImmAsmOperandParameters":
            operand_type = list(args[1:])
            config_vars[args[0]] = operand_type
        elif args[0] == "ImmAsmOperandParameters":
            operand_type = list(args[1:])
            config_vars[args[0]] = operand_type
        elif args[0] == "ImmAsmOperandName":
            operand_type = list(args[1:])
            config_vars[args[0]] = operand_type
        elif args[0] == "disableImmLeaf":
            disable_immLeaf = list(args[1:])
            config_vars[args[0]] = disable_immLeaf
        elif args[0] == "disableEncoderMethod":
            disable_encoder = list(args[1:])
            config_vars[args[0]] = disable_encoder
        elif args[0] == "PrintMethodKey":
            disable_encoder = list(args[1:])
            config_vars[args[0]] = disable_encoder
        elif args[0] == "ImmediateOperands":
            instruction_operands = list(args[1:])
            config_vars[args[0]] = instruction_operands
            for line in Lines[1:]:
                newline = line.strip()
                x = re.findall(
                    '[\#"a-z_A-Z0-9]*\:*[\#"a-z_A-Z0-9]*\.*[\#"a-z_A-Z0-9]*\.*[\#"a-zA-z0-9\.]*',
                    newline,
                )
                args = [elem.strip(" ") for elem in x if elem != ""]
                if args[0] in instruction_operands:
                    regex = re.compile(
                        r'[\#\"a-z_A-Z0-9.,*\<*\>*"]* *[\!*\#\"a-z_A-Z0-9,*\"*\)*][\!*\#\"(a-z_A-Z\<*\>*0-9\<*\>*,*\"*\)*\"]*\.*[\!*\#\"\<*\>*a-zA-z0-9,*]'
                    )
                    x = re.findall(regex, newline)
                    args_len = [elem for elem in x if elem != ""]
                    aux_dict = dict()
                    args_len = str(args_len).split(",")
                    args_len = (
                        str(args_len)
                        .replace("[", "")
                        .replace("]", "")
                        .replace("{", "")
                        .replace("}", "")
                        .replace("'", "")
                    )
                    args_len = (
                        str(args_len)
                        .replace("\\", "")
                        .replace('""', "")
                        .replace(" ", "")
                    )
                    args_len = list(args_len.split(","))
                    if "" in args_len:
                        args_len.remove("")
                    if '""' in args_len:
                        args_len.remove('""')
                    for index in range(len(args_len) - 1):
                        if "(" in args_len[index]:
                            if ")" in args_len[index + 1]:
                                args_len[index + 1] = args_len[index + 1].replace(
                                    '"', ""
                                )
                                args_len[index] += ", " + str(args_len[index + 1])
                                args_len[index + 1] = args_len[index + 1].replace(
                                    args_len[index + 1], ""
                                )
                    for index in range(len(args_len) - 1):
                        args_len[index] = args_len[index].replace(" ", "")
                    operand_type = args_len
                    index = 0
                    operand_type = operand_type[1:]
                    if len(operand_type) == 2:
                        aux_dict[operand_type[index]] = operand_type[index + 1]
                    index = 0
                    if len(operand_type) % 2 != 0:
                        while index < len(operand_type) - 2:
                            if '">' in operand_type[index + 2]:
                                aux_dict[operand_type[index]] = (
                                    operand_type[index + 1].replace('"', "")
                                    + ", "
                                    + operand_type[index + 2]
                                )
                                index += 3
                            else:
                                aux_dict[operand_type[index]] = operand_type[index + 1]
                                index += 2
                    index = 0
                    if len(operand_type) % 2 == 0:
                        while index < len(operand_type) - 1:
                            aux_dict[operand_type[index]] = operand_type[index + 1]
                            index += 2
                    if "" in aux_dict.keys():
                        del aux_dict[""]
                    for key, value in aux_dict.items():
                        key = key.replace("'", "")
                        value = value.replace("'", "")
                    config_vars[args[0]] = aux_dict
        elif args[0] == "LLVMVFlags":
            llvmvflags = list(args[1:])
            config_vars[args[0]] = llvmvflags
        elif args[0] == "ExtensionPrefixed":
            extension_prefix = list(args[1:])
            config_vars[args[0]] = extension_prefix
        elif args[0] == "basicDecodeMethod":
            llvmvflags = list(args[1:])
            config_vars[args[0]] = llvmvflags
        elif args[0] == "RegisterAllocationOrder":
            calling_convention = list()
            matches = re.findall(r"(\w+):\s*\[((?:\w+(?:,\s*)?)+)\](?:,\s*)?", newline)
            for key, values in matches:
                calling_convention.append(
                    {key: [value.strip() for value in re.findall(r"\w+", values)]}
                )
            config_vars[args[0]] = calling_convention
        elif args[0] == "CallingConventionAllocationOrder":
            calling_convention = list()
            matches = re.findall(r"(\w+):\s*\[((?:\w+(?:,\s*)?)+)\](?:,\s*)?", newline)
            for key, values in matches:
                calling_convention.append(
                    {key: [value.strip() for value in re.findall(r"\w+", values)]}
                )
            config_vars[args[0]] = calling_convention
        elif args[0] == "CallingConventionAllocationExcluded":
            calling_convention = list()
            matches = re.findall(r"(\w+):\s*\[((?:\w+(?:,\s*)?)+)\](?:,\s*)?", newline)
            for key, values in matches:
                calling_convention.append(
                    {key: [value.strip() for value in re.findall(r"\w+", values)]}
                )
            config_vars[args[0]] = calling_convention
        elif args[0] == "XLenVTValueType" or args[0] == "XLenRIRegInfo":
            lines = line.strip().split("\n")
            for line in lines:
                match = re.match(r"(\w+)\s*=\s*(.+)", line)
                if match:
                    key = match.group(1)
                    value = match.group(2)
                    config_vars[key] = value.strip()
        elif args[0] == "DecoderNamespace":
            decoder_namespace = dict()
            regex = re.compile(r'(\w+)=\s*(?:"([^"]*)"|(\S+))')
            line = line.split("=", 1)[1].replace("{", "").replace("}", "").strip(" ")
            match = re.findall(regex, line)
            match = (
                str(match)
                .replace("[", "")
                .replace("]", "")
                .replace("(", "")
                .replace(")", "")
                .replace("'", "")
                .split(",")
            )
            match_copy = match
            for element in match_copy:
                if element.isalpha() is False:
                    match.remove(element)
            index = 0
            while index < len(match) - 1:
                decoder_namespace[match[index].strip()] = match[index + 1].strip()
                index += 2
            config_vars[args[0]] = decoder_namespace
        else:
            if args[0] not in config_vars.keys():
                config_vars[args[0]] = args[1]
    configuration_file.close()
    return config_vars
