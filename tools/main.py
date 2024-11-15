# Copyright 2024 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package main
#
# The main module which must be run to generate all the td files
import adl_parser
import files
import config
import legalDisclaimer
import os
import sys
import argparse
import shutil
import make_td


## The main function that calls all the necessary functions for the build
#
# @note Only change the values in config.txt file when needed
def main():
    config_file = "config.txt"
    llvm_config = "llvm_config.txt"
    path = os.getcwd()
    list_dir = list()
    for fname in os.listdir("."):
        list_dir.append(fname)
    if "tools" in list_dir:
        config_file = "./tools/config.txt"
        llvm_config = "./tools/llvm_config.txt"
    config_variables = config.config_environment(config_file, llvm_config)
    f = open(config_file, "r")
    lines = f.readlines()
    line_copy = ""
    for line in lines:
        line_list = list(str(line).split(" "))
        if "ADLName" in line_list:
            if len(line_list) == 3:
                line_list.remove(line_list[2])
                line_list.append(sys.argv[1])
                line_copy = line_list
    f.close()
    content = ""
    for elem in range(len(line_copy) - 1):
        content += line_copy[elem]
        content += " "
    content += line_copy[len(line_copy) - 1]
    f = open(config_file, "w")
    f.write(lines[0])
    f.close()
    f = open(config_file, "a")
    for line in lines[1:]:
        line_list = list(str(line).split(" "))
        if "ADLName" in line_list:
            f.write(str(content))
            f.write("\n")
        else:
            f.write(line)
    f.close()
    config_variables = config.config_environment(config_file, llvm_config)
    instructions = adl_parser.parse_instructions_from_adl(config_variables["ADLName"])
    regclass = adl_parser.parse_adl(config_variables["ADLName"])
    alias_regs = adl_parser.get_alias_for_regs(config_variables["ADLName"])
    instrfield = adl_parser.get_instrfield_offset(config_variables["ADLName"])
    instrfield_offset = instrfield[0]
    instrfield_ref = instrfield[1]
    adl_parser.parse_instructions_from_adl(config_variables["ADLName"])
    if path.endswith("tools"):
        config_variables["RegisterInfoFile"] = (
            "." + config_variables["RegisterInfoFile"]
        )
        config_variables["InstructionInfoFile"] = (
            "." + config_variables["InstructionInfoFile"]
        )
        config_variables["InstructionFormatFile"] = (
            "." + config_variables["InstructionFormatFile"]
        )
        config_variables["InstructionFormatFile16"] = (
            "." + config_variables["InstructionFormatFile16"]
        )
        config_variables["InstructionAliases"] = (
            "." + config_variables["InstructionAliases"]
        )
        config_variables["OperandsFile"] = "." + config_variables["OperandsFile"]
        config_variables["OperandsFile16"] = "." + config_variables["OperandsFile16"]
        config_variables["CallingConventionFile"] = (
            "." + config_variables["CallingConventionFile"]
        )
        config_variables["RelocationFile"] = "." + config_variables["RelocationFile"]
    extensions_list = []
    output_dir = ""
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=str)
    parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
    parser.add_argument("--output", "-o", dest='output', type=str)
    args = parser.parse_args()
    if args.extension is None:
        extensions_list = []
    else:
        extensions = args.extension
        extensions = extensions.replace("'", "").replace("[", "").replace("]", "")
        extensions_list = extensions.split(",")
    output_dir = args.output
    output_dir_refresh = False
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["RegisterInfoFile"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                if os.path.exists(output_dir) is False:
                    os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['RegisterInfoFile'] = output_dir + file_name
        legalDisclaimer.get_copyright(config_variables["RegisterInfoFile"])
        legalDisclaimer.get_generated_file(config_variables["RegisterInfoFile"])
        files.generate_file(
            regclass,
            config_variables["RegisterInfoFile"],
            config_variables,
            alias_regs,
            instrfield_offset,
            instrfield_ref,
        )
        files.generate_accumulator_register(
            config_variables["RegisterInfoFile"],
            config_variables["RegAltNameIndex"],
            config_variables["RegisterClass"],
            config_variables["Namespace"],
        )
    else:
        if os.path.exists(config_variables["RegisterInfoFile"]):
            os.remove(config_variables["RegisterInfoFile"])
        legalDisclaimer.get_copyright(config_variables["RegisterInfoFile"])
        legalDisclaimer.get_generated_file(config_variables["RegisterInfoFile"])
        files.generate_file(
            regclass,
            config_variables["RegisterInfoFile"],
            config_variables,
            alias_regs,
            instrfield_offset,
            instrfield_ref,
        )
        files.generate_accumulator_register(
            config_variables["RegisterInfoFile"],
            config_variables["RegAltNameIndex"],
            config_variables["RegisterClass"],
            config_variables["Namespace"],
        )
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["ScheduleFileTable"])
        scheduling_table_dict = adl_parser.parse_sched_table_from_adl(config_variables["ADLName"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['ScheduleFileTable'] = output_dir + file_name
        config_variables['SchedulePath'] = output_dir
        files.generate_scheduling_table(config_variables["ScheduleFileTable"], config_variables['SchedulePath'])
    else:
        files.generate_scheduling_table(config_variables["ScheduleFileTable"], config_variables['SchedulePath'])
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["InstructionInfoFile"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['InstructionInfoFile'] = output_dir + file_name
        legalDisclaimer.get_copyright(config_variables["InstructionInfoFile"])
        legalDisclaimer.get_generated_file(config_variables["InstructionInfoFile"])
        files.generate_file_instructions(
            config_variables["InstructionInfoFile"], extensions_list
        )
    else:
        if os.path.exists(config_variables["InstructionInfoFile"]):
            os.remove(config_variables["InstructionInfoFile"])
        legalDisclaimer.get_copyright(config_variables["InstructionInfoFile"])
        legalDisclaimer.get_generated_file(config_variables["InstructionInfoFile"])
        files.generate_file_instructions(
            config_variables["InstructionInfoFile"], extensions_list
        )
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["InstructionFormatFile"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['InstructionFormatFile'] = output_dir + file_name
        legalDisclaimer.get_copyright(config_variables["InstructionFormatFile"])
        legalDisclaimer.get_generated_file(config_variables["InstructionFormatFile"])
        files.generate_instruction_format(config_variables["InstructionFormatFile"], config_variables["InstructionFormatFile"].replace(file_name, ""))
    else:
        if os.path.exists(config_variables["InstructionFormatFile"]):
            os.remove(config_variables["InstructionFormatFile"])
        legalDisclaimer.get_copyright(config_variables["InstructionFormatFile"])
        legalDisclaimer.get_generated_file(config_variables["InstructionFormatFile"])
        files.generate_instruction_format(config_variables["InstructionFormatFile"], config_variables["InstructionFormatFile"])
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["OperandsFile"])
        file_name_c = os.path.basename(config_variables["OperandsFile16"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['OperandsFile'] = output_dir + file_name
        config_variables['OperandsFile16'] = output_dir + file_name_c
        legalDisclaimer.get_copyright(config_variables["OperandsFile"])
        legalDisclaimer.get_generated_file(config_variables["OperandsFile"])
        legalDisclaimer.get_copyright(config_variables["OperandsFile16"])
        legalDisclaimer.get_generated_file(config_variables["OperandsFile16"])
        files.write_imms_classes(
            config_variables["OperandsFile"],
            config_variables["OperandsFile16"],
            files.instrfield_classes,
            adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0],
        )
    else:
        if os.path.exists(config_variables["OperandsFile"]):
            os.remove(config_variables["OperandsFile"])
        legalDisclaimer.get_copyright(config_variables["OperandsFile"])
        legalDisclaimer.get_generated_file(config_variables["OperandsFile"])
        if os.path.exists(config_variables["OperandsFile16"]):
            os.remove(config_variables["OperandsFile16"])
        legalDisclaimer.get_copyright(config_variables["OperandsFile16"])
        legalDisclaimer.get_generated_file(config_variables["OperandsFile16"])
        files.write_imms_classes(
            config_variables["OperandsFile"],
            config_variables["OperandsFile16"],
            files.instrfield_classes,
            adl_parser.parse_instructions_from_adl(config_variables["ADLName"])[0],
        )
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["InstructionInfoFile"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['InstructionInfoFile'] = output_dir + file_name
        adl_parser.parse_instructions_aliases_from_adl(config_variables["ADLName"])
        files.write_instructions_aliases(
            config_variables["InstructionInfoFile"], config_variables["InstructionInfoFile"], extensions_list
        )
    else:
        adl_parser.parse_instructions_aliases_from_adl(config_variables["ADLName"])
        files.write_instructions_aliases(
            config_variables["InstructionInfoFile"], config_variables["InstructionInfoFile"], extensions_list
        )
    adl_parser.parse_registers_subregs(config_variables["ADLName"])
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["CallingConventionFile"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['CallingConventionFile'] = output_dir + file_name
        legalDisclaimer.get_copyright(config_variables["CallingConventionFile"])
        legalDisclaimer.get_generated_file(config_variables["CallingConventionFile"])
        files.write_calling_convention(config_variables["CallingConventionFile"])
    else:
        if os.path.exists(config_variables["CallingConventionFile"]):
            os.remove(config_variables["CallingConventionFile"])
            legalDisclaimer.get_copyright(config_variables["CallingConventionFile"])
            legalDisclaimer.get_generated_file(config_variables["CallingConventionFile"])
        else:
            legalDisclaimer.get_copyright(config_variables["CallingConventionFile"])
            legalDisclaimer.get_generated_file(config_variables["CallingConventionFile"])
        files.write_calling_convention(config_variables["CallingConventionFile"])
    adl_parser.parse_relocations(config_variables["ADLName"])
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["RelocationFile"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['RelocationFile'] = output_dir + file_name
        legalDisclaimer.get_copyright(config_variables["RelocationFile"])
        legalDisclaimer.get_generated_file(config_variables["RelocationFile"])
        files.write_calling_convention(config_variables["RelocationFile"])
    else:
        if os.path.exists(config_variables["RelocationFile"]):
            os.remove(config_variables["RelocationFile"])
            legalDisclaimer.get_copyright(config_variables["RelocationFile"])
            legalDisclaimer.get_generated_file(config_variables["RelocationFile"])
        else:
            legalDisclaimer.get_copyright(config_variables["RelocationFile"])
            legalDisclaimer.get_generated_file(config_variables["RelocationFile"])
        files.generate_relocation_define(config_variables["RelocationFile"])
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["IntrinsicsFile"])
        builtin_file = os.path.basename(config_variables["BuiltinFile"])
        header_file = os.path.basename(config_variables["BuiltinHeader"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['IntrinsicsFile'] = output_dir + file_name
        config_variables['BuiltinFile'] = output_dir + builtin_file
        config_variables['BuiltinHeader'] = output_dir + header_file
        files.generate_intrinsics(config_variables["IntrinsicsFile"], extensions_list)
        files.generate_builtin(
            config_variables["BuiltinFile"],
            config_variables["BuiltinHeader"],
            extensions_list,
        )
    else:
        if os.path.exists(config_variables["IntrinsicsFile"]):
            os.remove(config_variables["IntrinsicsFile"])
        files.generate_intrinsics(config_variables["IntrinsicsFile"], extensions_list)
        files.generate_builtin(
            config_variables["BuiltinFile"],
            config_variables["BuiltinHeader"],
            extensions_list,
        )
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["MemoryOperand"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['MemoryOperand'] = output_dir + file_name
        files.generate_operand_mem_wrapper_class(config_variables["MemoryOperand"])
    else:
        files.generate_operand_mem_wrapper_class(config_variables["MemoryOperand"])
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["RegisterInfoFile"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['RegisterInfoFile'] = output_dir + file_name
        files.generate_register_pairs(config_variables["RegisterInfoFile"])
    else:
        files.generate_register_pairs(config_variables["RegisterInfoFile"])
    if output_dir != "" and output_dir is not None:
        include_path = os.path.abspath(output_dir).replace("\\","/")
        files.generate_intrinsic_tests(config_variables['TestIntrinsics'], include_path)
    else:
        include_path = os.path.abspath(os.path.dirname(config_variables['BuiltinHeader'])).replace("\\","/")
        files.generate_intrinsic_tests(config_variables['TestIntrinsics'], include_path)
    files.generate_sched_tests(config_variables["TestScheduling"])
    files.generate_scheduling_ref(config_variables["TestScheduling"])
    if output_dir != "" and output_dir is not None:
        file_name = os.path.basename(config_variables["SailDescription"])
        output_dir = os.path.abspath(output_dir).replace("\\","/")
        if output_dir.endswith("/") is False:
            output_dir += "/"
        if os.path.exists(output_dir):
            if output_dir_refresh is False:
                shutil.rmtree(output_dir, ignore_errors=True)    
                output_dir_refresh = True
                os.mkdir(output_dir)
        else:
            os.mkdir(output_dir)
            output_dir_refresh = True
        config_variables['SailDescription'] = output_dir + file_name
        files.generate_sail_description(config_variables["SailDescription"], extensions_list)
    else:
        files.generate_sail_description(config_variables["SailDescription"], extensions_list)
    del config_variables


if __name__ == "__main__":
    main()
