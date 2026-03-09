# Tools ADL Project


## Description

Tools-ADL is a suite of utilities designed to automatically generate target description files and encoding tests from an XML file. Specifically, Tools-ADL processes an XML file containing an ADL model for one or more RISC-V extensions and produces the target description files needed for LLVM compiler to support these new extensions. Instruction encoding, instruction scheduling, relocation tests are generated from the same model.

The generated files can be integrated into llvm-project (https://github.com/llvm/llvm-project - release/19.x) to add support for new RISC-V extensions.

The 32‑bit support was developed as part of the TRISTAN European project, CHIPS JU Contract no. 101095947.

This part of the work was also supported by a grant of the Ministry of Research, Innovation and Digitization, CNCS/CCCDI – UEFISCDI, project number PN-IV-P8-8.1-PME-2024-0026, within PNCDI IV.

The 64‑bit support was developed as part of the RIGOLETTO European project, CHIPS JU Contract no. 101194371.

Additional support for the 64‑bit work was provided through România UEFISCDI, Contract no. PN-IV-P8-8.1-PME-2025-0055.

## Requirements

- **python 3.10** or higher

### Optional Requirements

- **llvm-project** - integration and running test verification with llvm-lit
- **asciidoctor** - browser extension for Release Notes

## Installation

### Setting up a Virtual Environment

It is recommended to use a virtual environment to avoid conflicts with system packages:

```bash
python3 -m venv venv
```

Activate the virtual environment:

On Linux/macOS:
```bash
source venv/bin/activate
```

On Windows:
```bash
venv\Scripts\activate
```

### Installing the Package

For regular users:

```bash
pip install -e .
```

For developers (includes development dependencies):

```bash
pip install -e .[dev]
```

All required dependencies (numpy, num2words, word2number) will be installed automatically.

## Project Structure

```
tools-adl
|
| - demos                           // Example demos providing an overview of the main workflow and components
| - docs                            // Project documentation
| - examples                        // Generated target description files
|   |   | - sail                    // Sail description generated from ADL
|   |   | - TD                      // Target description files and other LLVM files generated for specific extensions          
| - models
|   | - adl                         // Parsed XML files for specific extensions			
| - tools                           // Target description and test generation tools
|   | - sail                        // Sail source and config files
|   | - testing                     // Tools used for tests generation
|   |    | - encoding               // Tools for generating encoding tests and references
|   |    | - intrinsics             // Generated intrinsics tests
|   |    | - relocations            // Tools for generating relocations tests and references
|   |    | - scheduling             // Generated scheduling tests
|   |    |   | - tests              // Tests using a diverse set of randomly chosen registers
|   |    |   | - tests_dependency   // Data dependency tests between the source and destination registers of the tested instructions
```
