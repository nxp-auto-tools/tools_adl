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
import shutil
import utils


## The main function that calls all the necessary functions for the build
#
# @note Extensions must be separated by comma
def main():

    # Get the command line arguments
    adl_file_path, adl_file_name, cmd_extensions, output_dir = utils.cmd_args()

    # check if the output directory exists and refresh it
    if os.path.exists(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_' + '_'.join(cmd_extensions))):
        shutil.rmtree(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_' + '_'.join(cmd_extensions)))

    if os.path.exists(os.path.join(output_dir, 'results_' + adl_file_name, 'refs_' + '_'.join(cmd_extensions))):
        shutil.rmtree(os.path.join(output_dir, 'results_' + adl_file_name, 'refs_' + '_'.join(cmd_extensions)))

    # create the "tests" folder if it doesn't exist
    os.makedirs(os.path.join(output_dir, 'results_' + adl_file_name, 'tests_' + '_'.join(cmd_extensions)), exist_ok=True)
    
    # create the "references" folder if it doesn't exist
    os.makedirs(os.path.join(output_dir, 'results_' + adl_file_name, 'refs_' + '_'.join(cmd_extensions)), exist_ok=True)

    if len(sys.argv) > 2:

        # Architecture and attributes
        architecture, attributes, mattrib = parse.assembler_and_cmdLine_args(adl_file_path)
        
        # Generate information -> info.py
        instr_op_dict, instr_name_syntaxName_dict, imm_width_dict, imm_shift_dict, imm_signed_dict, instr_field_value_dict = parse.instructions_operands(adl_file_path)
        op_val_dict, widths_dict, op_signExt_dict = parse.operands_values(adl_file_path)
        generate_info.generate_info_file("info.py", instr_op_dict, op_val_dict)

        # Generate instruction encoding tests
        generate_inst_tests.write_header()
        generate_inst_tests.generate_instructions()

        # Generate references
        generate_reference.generate_reference(adl_file_path)
    else:
        print("Not enough arguments provided. Run 'python make_test.py -h' for help.")

if __name__ == "__main__":
    main()
