# Copyright 2023-2025 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package make_test
# The main module which generates tests for all instructions
#
# Run this from the command line using "python make_test.py <adl_name> <extension(s)>"
import os
import shutil
import sys
import generate_inst_tests
import generate_reference
import utils
import parse


## The main function that calls all the necessary functions for the build
#
# @note Extensions must be separated by comma
def main():
    # Get the command line arguments
    adl_file_path, adl_file_name, extension_list, output_dir, display_extensions = utils.cmd_args()

    # A dictionary with instructions and associated attribute prefixes
    instruction_attribute_dict, new_instruction_attribute_dict = parse.instruction_attribute(adl_file_path)

    # Check for invalid extensions
    if extension_list is not None:
        instruction_attribute_dict, new_instruction_attribute_dict = parse.instruction_attribute(adl_file_path)
        extension_error = [extension for extension in extension_list if not any(extension in attributes for attributes in instruction_attribute_dict.values())]
        if extension_error:
            sys.exit(f"Error: The following extensions were not found: {', '.join(extension_error)}")

    if display_extensions:
        sys.exit(f"Available extensions for instructions in this model: {list(dict.fromkeys(value for sublist in instruction_attribute_dict.values() for value in sublist))}")

    # check if the output directory exists and refresh it
    if extension_list is not None:
        if os.path.exists(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_' + '_'.join(extension_list))):
            shutil.rmtree(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_' + '_'.join(extension_list)))

        if os.path.exists(os.path.join(output_dir, 'results_' + adl_file_name, 'refs_' + '_'.join(extension_list))):
            shutil.rmtree(os.path.join(output_dir, 'results_' + adl_file_name, 'refs_' + '_'.join(extension_list)))
        # create the "tests" folder if it doesn't exist
        os.makedirs(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_' + '_'.join(extension_list)), exist_ok=True)
        
        # create the "references" folder if it doesn't exist
        os.makedirs(os.path.join(output_dir, 'results_' + adl_file_name, 'refs_' + '_'.join(extension_list)), exist_ok=True)
    else:
        if os.path.exists(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_all')):
            shutil.rmtree(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_all'))

        if os.path.exists(os.path.join(output_dir, 'results_' + adl_file_name, 'refs_all')):
            shutil.rmtree(os.path.join(output_dir, 'results_' + adl_file_name, 'refs_all'))

        # create the "tests" folder if it doesn't exist
        os.makedirs(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_all'), exist_ok=True)
        
        # create the "references" folder if it doesn't exist
        os.makedirs(os.path.join(output_dir, 'results_' + adl_file_name, 'refs_all'), exist_ok=True)


    # Generate instruction encoding tests
    generate_inst_tests.write_header()
    generate_inst_tests.generate_instructions()

    # Generate references
    generate_reference.generate_reference(adl_file_path)

if __name__ == "__main__":
    main()
