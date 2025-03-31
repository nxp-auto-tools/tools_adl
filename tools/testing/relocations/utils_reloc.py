# Copyright 2023-2025 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package utils
# Utility functions for relocations generation
#
# This module contains utility functions for relocations generation
import os
import sys
import argparse
import re
import parse_reloc
sys.path.append(os.path.join(os.path.dirname(__file__), "../encoding/"))
import utils

## Get the command line arguments
# @return @b adl_file_path The path to the adl xml file
# @return @b adl_file_name The name of the adl xml file without extensions
# @return @b symbol_max_value The integer value for symbol table
# @return @b extension Comma-separated list of extensions
# @return @b output_dir The output directory for relocations tests
def cmd_args():

    script_directory = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(description="Generate relocations tests based on ADL file and previously generated encoding tests", usage="python make_reloc.py adl_file symbol_max_value [--extension <comma-separated_list_of_extensions>] [-o, --output <output_directory>]")
    parser.add_argument("adl_file", type=str, help="path to the adl xml file")
    parser.add_argument("symbol_max_value", type=int, help="integer value for symbol table")
    parser.add_argument("--extension", type=parse_extensions, help="comma-separated list of extensions")
    parser.add_argument("-o", "--output", type=str, default=script_directory, help="create an output directory for relocations tests")
    parser.add_argument("--list", action="store_true", help="Display the list of available extensions")

    args = parser.parse_args()
    adl_file_path = args.adl_file
    adl_file_name = utils.remove_all_extensions(adl_file_path)
    symbol_max_value = args.symbol_max_value
    extension_list = args.extension
    output_dir = args.output
    display_extensions = args.list

    return adl_file_path, adl_file_name, symbol_max_value, extension_list, output_dir, display_extensions


## Split command line extensions
def parse_extensions(extensions_list):
    return extensions_list.split(',')


## Searches for the next character after instruction name inside the name of the test file
# @param input_string Name of the test file
# @param substring Instruction name
# @return @b char_after_substring-> Next character after instruction name
#
# Additional check in order to take only relocations tests into consideration
def get_char_after_substring(input_string, substring):
    index = input_string.find(substring)
    if index != -1 and index + len(substring) < len(input_string):
        char_after_substring = input_string[index + len(substring)]
        return char_after_substring
    else:
        return None


## Searches for a substring between two separators (_ and .) in order to identify the instruction name
# @param string Name of the test file
# @param substring Separator (instruction name)
# @return @b match.group(0)-> Substring between two separators
def search_with_separators(string, substring):
    # Define the regular expression pattern with lookbehind and lookahead
    pattern = rf'(?<=[._]){re.escape(substring)}(?=[._])'
    
    # Use re.search to find a match
    match = re.search(pattern, string)
    
    if match:
        return match.group(0)
    else:
        return None
    

# Function that extracts the highest even value for pair instructions
# @param my_dict Dictionary containing the instructions and their corresponding tuples
# @param key Key used to extract the tuples
# @return @b max_tuples[-1][1]-> The second element of the last tuple with the maximum value
def extract_highest_even_value_for_pair_instructions(my_dict, key):
    # Check if the key exists in the dictionary
    if key in my_dict:
        # Get the list of tuples associated with the key
        tuples = my_dict[key]
        
        # Convert string numbers to integers for comparison
        even_tuples = [(int(t[0]), t[1]) for t in tuples if int(t[0]) % 2 == 0]
        
        # Check if there are any even tuples
        if even_tuples:
            # Find the maximum value
            max_value = max(x[0] for x in even_tuples)
            # Filter for tuples that have the maximum value
            max_tuples = [t for t in even_tuples if t[0] == max_value]
            # Return the second element of the last tuple with the maximum value
            return max_tuples[-1][1]
    
    # Return None if the key doesn't exist or no even tuples found
    return None