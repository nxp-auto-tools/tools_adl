# Copyright 2023-2025 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package utils
# Utility functions for test generation
#
# This module contains utility functions for test generation
import os
import sys
import argparse
sys.path.append(os.path.join(os.path.dirname(__file__), "./../../"))
import config

## Remove all extensions from a file path
# @param file_path The file path to remove extensions from
# @return The file name without any extensions
def remove_all_extensions(file_path):
    file_name = os.path.basename(file_path)
    
    # Keep removing extensions until none remain
    while '.' in file_name:
        file_name = os.path.splitext(file_name)[0]
    
    return file_name

## Get the command line arguments
# @return @b adl_file_path The path to the adl xml file
# @return @b adl_file_name The name of the adl xml file without extensions
# @return @b cmd_extensions The extensions to generate tests for
# @return @b output_dir The output directory for the tests
def cmd_args():

    # Get the path of the script
    script_directory = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(description="Generate encoding tests based on ADL file and extensions", usage="python make_test.py adl_file [--extension <comma-separated_list_of_extensions>] [-o, --output <output_directory>]")
    parser.add_argument("adl_file", type=str, help="path to the adl xml file")
    parser.add_argument("--extension", type=parse_extensions, help="comma-separated list of extensions")
    parser.add_argument("-o", "--output", type=str, default=script_directory, help="create an output directory for specific extensions")
    parser.add_argument("--list", action="store_true", help="Display the list of available extensions")

    args = parser.parse_args()
    adl_file_path = args.adl_file
    adl_file_name = remove_all_extensions(adl_file_path)
    cmd_extensions = args.extension
    output_dir = args.output
    display_extensions = args.list

    return adl_file_path, adl_file_name, cmd_extensions, output_dir, display_extensions


## Split command line extensions
def parse_extensions(extensions_list):
    return extensions_list.split(',')


## Set available architectures
def set_available_extensions(instruction_attributes_dict):

    # Get the path of the script
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    # A dictionary for the configuration environment
    llvm_config_dict = config.config_environment(os.path.join(script_directory, "../../config.txt"), os.path.join(script_directory, "../../llvm_config.txt"))

    # Set available architectures
    available_architectures = list()
    for key, arch in llvm_config_dict.items():
        if key.startswith('HasStd') and key.endswith('Extension'):
            available_architectures.append(arch.lower())
    for instruction in instruction_attributes_dict.keys():
        instruction_attributes_dict[instruction] = [architecture for architecture in instruction_attributes_dict[instruction] if architecture in available_architectures]

    return instruction_attributes_dict