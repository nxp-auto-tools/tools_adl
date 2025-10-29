# Copyright 2023-2025 NXP 
# SPDX-License-Identifier: BSD-2-Clause

## @package make_reloc
# The main module which generates relocations tests for all instructions
#
# Run this from the command line using "python make_reloc.py <adl_name> <number_for_symbol_table>"
import sys
import parse_reloc
import generate_reloc_tests
import generate_reloc_reference
import generate_fixup_tests
import generate_fixup_reference
import utils_reloc


## The main function that calls all the necessary functions for the build
def main():
    # Get the command line arguments
    adl_file_path, adl_file_name, symbol_max_value, extension_list, output_dir, display_extensions = utils_reloc.cmd_args()

    relocation_attributes_dict = parse_reloc.relocations_attributes(adl_file_path)
    relocation_attributes_dict = utils_reloc.set_available_extensions(relocation_attributes_dict)

    # Check for invalid extensions
    if extension_list is not None:
        extension_error = [extension for extension in extension_list if not any(extension in attributes for attributes in relocation_attributes_dict.values())]
        if extension_error:
            sys.exit(f"Error: The following extensions were not found: {', '.join(extension_error)}")
    
    if display_extensions:
        sys.exit(f"Available extensions for relocations in this model: {list(dict.fromkeys(value for sublist in relocation_attributes_dict.values() for value in sublist))}")

    # Generate the relocations - instructions file structure
    generate_reloc_tests.generate_file_structure()
    # Generate symbols table
    generate_reloc_tests.generate_symbols()
    # Generate labels table
    generate_reloc_tests.generate_labels()
    # Write header info
    generate_reloc_tests.write_header()
    # Generate relocation tests
    generate_reloc_tests.generate_relocations()
    # Generate data relocations
    generate_reloc_tests.generate_data_relocations()
    # Generate symbols table for data relocations
    generate_reloc_tests.generate_symbols()
    # Generate references
    generate_reloc_reference.generate_reloc_reference()
    # Generate fixup tests
    generate_fixup_tests.write_tests()
    # Generate fixup references
    generate_fixup_reference.write_reference()
    
if __name__ == "__main__":
    main()