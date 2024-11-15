# ADL-Tools Project


## Description

ADL-Tools is a suite of utilities designed to automatically generate target description files and encoding tests from an XML file. Specifically, ADL-Tools processes an XML file containing an ADL model for one or more RISC-V extensions and produces the essential .td files needed for a compiler to incorporate these new extensions. In essence, the XML-based ADL model is a critical component in this process, working in tandem with the ADL-Tools suite.

## Requirements

- Python 3.10 or higher
- 'numpy' package installed (pip install numpy)

## Installation

No installation is required; simply cloning the repository is sufficient.

## Project Structure

```
tools-adl
|
| - docs                            // Project documentation
| - examples                        // Generated target description files
|   | - sail                    // Sail description generated from ADL
|   | - TD                      // Target description files and other LLVM files generated for specific extensions          
| - models
|   | - adl                         // Parsed XML files for specific extensions				
| - tools                           // Target description and test generation tools
|   | - testing                     // Tools used for tests generation
|   |    | - encoding               // Tools for generating encoding tests and references
|   |    | - intrinsics             // Generated intrinsics tests
|   |    | - relocations            // Tools for generating relocations tests and references
|   |    | - scheduling             // Generated scheduling tests
|   |    |   | - tests              // Tests using a diverse set of randomly chosen registers (generated)
|   |    |   | - tests_dependecy    // Data dependency tests between the source and destination registers of the tested instructions (generated)
```
