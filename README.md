# ADL-Tools Project


## Getting Started

ADL-Tools is a tool suite designed for automatically generating target description files and encoding tests 
using an XML file. 
Practically, ADL-Tools parses an XML file, which contains an ADL model for one or more RISC-V extensions, 
and generates all the necessary .td files required by a compiler to integrate these new extensions. 
In simpler terms, the ADL represented as an XML file is crucial in this process, 
alongside the actual tools used.

## Project Structure

```
tools-adl
|
| - demos
| - docs                               //This folder contains the documentation
| - examples                          // This folder will contain the target description files generated
|   | - examples
|   |   | - TD
|   |   |   | - rv32i                // This folder will contain target description files and other LLVM files generated
| - models
|   | - adl
|   |   | - rv32i                  //This folder contains the XML file that will be parsed
| - tools                         // This folder contains target description and test generation tools
|   | - testing                  // This folder contains all tests generated and also the tools used for tests generation
|   |    | - intrinsics         // This folder contains intrinsic tests generated
|   |    |   | - tests
|   |    | - references       // This content contains testing references
|   |    | - relocations     // This folder contains relocations tests
|   |    | - tests          // This folder contains tests for each instruction generated
```
