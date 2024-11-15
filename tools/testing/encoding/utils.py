# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package utils
# Utility functions for test generation
#
# This module contains utility functions for test generation
import os
import argparse


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

    script_directory = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(description="Generate encoding tests based on ADL file and extensions", usage="python make_test.py adl_file extensions [-o, --output <output_directory>]")
    parser.add_argument("adl_file", type=str, help="path to the adl xml file")
    parser.add_argument("extensions", type=str, help="extensions separated by comma")
    parser.add_argument("-o", "--output", type=str, default=script_directory, help="create an output directory for specific extensions")

    args = parser.parse_args()
    adl_file_path = args.adl_file
    adl_file_name = remove_all_extensions(adl_file_path)
    cmd_extensions = args.extensions.split(",")
    output_dir = args.output

    return adl_file_path, adl_file_name, cmd_extensions, output_dir