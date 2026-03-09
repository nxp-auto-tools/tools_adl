# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause

import logging
import os
import shutil
import sys
from tools.testing import parse
from tools.testing import utils
from tools.testing.encoding import write_refs
from tools.testing.encoding import write_tests


# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for verbose output
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """
    Main function that orchestrates the test generation process.
    Parses arguments, loads configurations, and generates encoding tests and references.
    """
    logger.info("Starting encoding test generation tool")

    try:
        args = parse.parse_encoding_command_line_args()
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

    # Prepare output directories
    if args.extensions is not None:
        test_dir = os.path.join(
            args.output_dir,
            f"results_{args.adl_file_name}",
            f"tests_{'_'.join(args.extensions)}",
        )
        ref_dir = os.path.join(
            args.output_dir,
            f"results_{args.adl_file_name}",
            f"refs_{'_'.join(args.extensions)}",
        )
    else:
        test_dir = os.path.join(
            args.output_dir, f"results_{args.adl_file_name}", "tests_all"
        )
        ref_dir = os.path.join(
            args.output_dir, f"results_{args.adl_file_name}", "refs_all"
        )

    logger.info("Preparing output directories.")
    for path in [test_dir, ref_dir]:
        if os.path.exists(path):
            logger.debug(f"Removing existing directory: {path}")
            shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)
        logger.debug(f"Created directory: {path}")

    logger.info("Starting encoding tests generation.")
    write_tests.write_tests()
    logger.info("Test generation completed.")

    logger.info("Starting refs generation.")
    write_refs.write_refs()
    logger.info("Refs generation completed.")

    logger.info("All operations completed successfully.")


if __name__ == "__main__":
    main()
