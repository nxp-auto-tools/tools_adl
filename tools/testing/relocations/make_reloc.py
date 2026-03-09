# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause

import logging
import os
import shutil
import sys
from tools.testing import parse
from tools.testing import utils
from tools.testing.relocations import write_reloc_tests
from tools.testing.relocations import write_reloc_refs
from tools.testing.relocations import write_fixup_tests
from tools.testing.relocations import write_fixup_refs


# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for verbose output
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """
    Main function that orchestrates the test generation process.
    Parses arguments, loads configurations, and generates relocation tests and references.
    """
    logger = logging.getLogger(__name__)

    try:
        args = parse.parse_relocation_command_line_args()
        logger.info(f"Using ADL file: {args.adl_file_path}")
    except Exception as e:
        logger.error(f"Failed to parse command line arguments: {e}")
        sys.exit(1)

    try:
        cores = parse.get_cores_element(args.adl_file_path)
        logger.info("Parsed info from ADL file.")
    except Exception as e:
        logger.error(f"Failed to parse ADL file: {e}")
        sys.exit(1)

    try:
        instructions = utils.filter_instructions(
            parse.parse_instructions(cores), utils.load_llvm_config(), args.extensions
        )
        logger.info(f"Loaded {len(instructions)} instructions.")
    except Exception as e:
        logger.error(f"Failed to parse or filter instructions: {e}")
        sys.exit(1)

    # Extract available attributes for validation
    available_attributes = set(
        attr for instr in instructions for attr in instr.attributes
    )

    if args.extensions is not None:
        extension_error = [
            ext for ext in args.extensions if ext not in available_attributes
        ]
        if extension_error:
            logger.error(
                f"The following extensions were not found: {', '.join(extension_error)}"
            )
            sys.exit(1)
        logger.info(f"Filtering only for extensions: {', '.join(args.extensions)}")

    if args.display_extensions:
        logger.info("Displaying available extensions and exiting.")
        sys.exit(f"Available extensions: {sorted(available_attributes)}")

    # Check if any instructions use relocations
    instrfields = parse.parse_instrfields(cores)
    relocations_instructions_map = utils.get_relocation_instruction_mapping(
        instructions, instrfields
    )

    if not relocations_instructions_map:
        if args.extensions:
            logger.warning(
                f"No relocations found for extension(s): {', '.join(args.extensions)}. "
                "No test files will be generated."
            )
        else:
            logger.warning(
                "No relocations found in ADL file. No test files will be generated."
            )
        sys.exit(0)

    logger.info(f"Found {len(relocations_instructions_map)} relocations to test.")

    # Prepare output directories
    if args.extensions is not None:
        test_dir = os.path.join(
            args.output_dir,
            f"reloc_results_{args.adl_file_name}",
            f"tests_{'_'.join(args.extensions)}",
        )
        ref_dir = os.path.join(
            args.output_dir,
            f"reloc_results_{args.adl_file_name}",
            f"refs_{'_'.join(args.extensions)}",
        )
    else:
        test_dir = os.path.join(
            args.output_dir, f"reloc_results_{args.adl_file_name}", "tests_all"
        )
        ref_dir = os.path.join(
            args.output_dir, f"reloc_results_{args.adl_file_name}", "refs_all"
        )

    logger.info("Preparing output directories.")
    for path in [test_dir, ref_dir]:
        if os.path.exists(path):
            logger.debug(f"Removing existing directory: {path}")
            shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)
        logger.debug(f"Created directory: {path}")

    logger.info("Starting header generation.")
    write_reloc_tests.write_header()
    logger.info("Header data prepared.")

    logger.info("Starting symbols generation")
    write_reloc_tests.generate_symbols()
    logger.info("Symbols generation completed.")

    logger.info("Starting labels generation")
    write_reloc_tests.generate_labels()
    logger.info("Labels generation completed.")

    # Only generate data relocations if no extension flag is given
    if args.extensions is None:
        logger.info("Starting data relocations test generation")
        write_reloc_tests.generate_data_relocations()
        logger.info("Data relocations tests completed.")
    else:
        logger.info("Skipping data relocations (extension flag provided).")

    logger.info("Continue generating tests for the remaining relocations.")
    write_reloc_tests.generate_relocations()
    logger.info("Relocation test generation completed.")

    logger.info("Generate relocation references.")
    write_reloc_refs.generate_reloc_references()
    logger.info("Relocation references generation completed.")

    logger.info("Starting fixup test generation.")
    write_fixup_tests.generate_fixup_tests()
    logger.info("Fixup test generation completed.")

    logger.info("Starting fixup reference generation.")
    write_fixup_refs.generate_fixup_references()
    logger.info("Fixup reference generation completed.")

    logger.info("All operations completed successfully.")


if __name__ == "__main__":
    main()
