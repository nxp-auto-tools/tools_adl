# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package make_reloc
# The main module which generates relocations tests for all instructions
#
# Run this from the command line using "python make_reloc.py <adl_name> <number_for_symbol_table>"

import generate_reloc_tests
import os

## The main function that calls all the necessary functions for the build
def main():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    current_directory = os.getcwd()
    
    # check to see if the script is compiled from its directory
    if current_directory != script_directory:
        print("Please run this script from its directory.")
        exit(1)
    
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

if __name__ == "__main__":
    main()