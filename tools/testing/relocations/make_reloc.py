# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package make_reloc
# The main module which generates relocations tests for all instructions
#
# Run this from the command line using "python make_reloc.py <adl_name> <number_for_symbol_table>"

import generate_reloc_tests
import generate_reloc_reference
import os
import utils_reloc
import shutil

## The main function that calls all the necessary functions for the build
def main():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    current_directory = os.getcwd()

    # Get the command line arguments
    adl_file_path, adl_file_name, symbol_max_value, output_dir = utils_reloc.cmd_args()

    # check if the output directory exists and refresh it
    if os.path.exists(os.path.join(output_dir, 'reloc_results_' + adl_file_name, 'tests')):
        shutil.rmtree(os.path.join(output_dir, 'reloc_results_' + adl_file_name, 'tests'))

    if os.path.exists(os.path.join(output_dir, 'reloc_results_' + adl_file_name, 'refs')):
        shutil.rmtree(os.path.join(output_dir, 'reloc_results_' + adl_file_name, 'refs'))
        
    # create the "tests" folder if it doesn't exist
    os.makedirs(os.path.join(output_dir, 'reloc_results_' + adl_file_name, 'tests'), exist_ok=True)

    # create the "refs" folder if it doesn't exist
    os.makedirs(os.path.join(output_dir, 'reloc_results_' + adl_file_name, 'refs'), exist_ok=True)

    # generate the relocations - instructions file structure
    generate_reloc_tests.generate_file_structure()
    # generate symbols table
    generate_reloc_tests.generate_symbols()
    # generate labels table
    generate_reloc_tests.generate_labels()
    # write header info
    generate_reloc_tests.write_header()
    # generate tests
    generate_reloc_tests.generate_relocations()
    # generate data relocations
    generate_reloc_tests.generate_data_relocations()
    # generate symbols table for data relocations
    generate_reloc_tests.generate_symbols()
    #generate references
    generate_reloc_reference.generate_reloc_reference()

if __name__ == "__main__":
    main()