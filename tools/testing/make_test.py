# Copyright 2024 NXP
# SPDX-License-Identifier: BSD-2-Clause

## @package make_test
# The main module which generates tests for all instructions
#
# Run this from the command line using "python make_test.py <adl_name> <extension(s)>"
import parse
import generate_info
import generate_inst_tests
import generate_reference
import sys
import os


## The main function that calls all the necessary functions for the build
#
# @note Extensions must be separated by comma
def main():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    current_directory = os.getcwd()

    # Check to see if the script is compiled from its directory
    if current_directory != script_directory:
        print("Please run this script from its directory.")
        exit(1)

    if len(sys.argv) > 2:
        adl_file = sys.argv[1]
        extensions = sys.argv[2]

        # Architecture and attributes
        architecture, attributes, mattrib = parse.assembler_and_cmdLine_args(adl_file)

        # Generate information -> info.py
        (
            instr_op_dict,
            instr_name_syntaxName_dict,
            imm_width_dict,
            imm_shift_dict,
            imm_signed_dict,
            instr_field_value_dict,
        ) = parse.instructions_operands(adl_file)
        op_val_dict, widths_dict, op_signExt_dict = parse.operands_values(adl_file)
        generate_info.generate_info_file("info.py", instr_op_dict, op_val_dict)

        # Generate instruction encoding tests
        generate_inst_tests.write_header()
        generate_inst_tests.generate_instructions()

        # Generate references
        generate_reference.generate_reference(adl_file)
    else:
        print(
            "Usage: python make_test.py <path_to_adl_xml_file> <extensions_separated_by_comma>"
        )


if __name__ == "__main__":
    main()
