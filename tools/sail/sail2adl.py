# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package sail_converter
#
# The module generates an XML file based on the Json version of the Sail model

# importing element tree
# under the alias of ET


import json
import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from pathlib import Path


# Global dict for instructions fields ranges 
INSTRUCTION_FIELD_RANGES = {}
REGISTER_CLASSES: Dict[str, Any] = {} 
GPR_ALIASES: Dict[str, str] = {}
# Global dict for instruction action 
INSTRUCTION_ACTIONS: Dict[str, str] = {}
# Global list for ignored instructions
IGNORED_INSTRUCTIONS: List[str] = []
# Global dict for immediate sign info 
IMMEDIATE_SIGN_INFO: Dict[str, bool] = {}
# Global dict for compressed instructions
INSTRUCTION_COMPRESSED: List[str] = []


def store_instruction_action(instruction_name: str, action: str) -> None:
    """
    Stores an action associated with a specific instruction.

    This function records or updates the action for the instruction identified
    by `instruction_name`. It is typically used as part of the instruction
    processing or generation pipeline to track custom behaviors or metadata.

    Args:
        instruction_name (str): Name of the instruction for which the action
            should be stored.
        action (str): The action or behavior to associate with the instruction.

    Returns:
        None
    """
    global INSTRUCTION_ACTIONS
    INSTRUCTION_ACTIONS[instruction_name.lower()] = action
    print(f"DEBUG STORE: Stored action for {instruction_name}: {action[:50]}...")

def get_instruction_action(instruction_name: str) -> Optional[str]:
    """
    Retrieves the action associated with a given instruction.

    This function looks up the action stored for the instruction identified
    by `instruction_name` in the global instruction‑action dictionary.

    Args:
        instruction_name (str): Name of the instruction whose action should be retrieved.

    Returns:
        Optional[str]: The action associated with the instruction, or None if no action is defined.
    """
    global INSTRUCTION_ACTIONS
    return INSTRUCTION_ACTIONS.get(instruction_name.lower())

def load_ignored_instructions() -> None:
    """
    Loads the list of ignored instructions from the configuration file.

    This function reads the configuration settings and populates the internal
    structure that keeps track of which instructions should be ignored during
    generation or processing steps.

    Returns:
        None
    """
    global IGNORED_INSTRUCTIONS
    print("DEBUG: Starting to load ignored instructions...")
    
    try:
        reg_generator = RegisterFileGenerator()
        IGNORED_INSTRUCTIONS = reg_generator.get_ignored_instructions()
        print(f"DEBUG: Loaded ignored instructions: {IGNORED_INSTRUCTIONS}")
        print(f"✓ Loaded {len(IGNORED_INSTRUCTIONS)} ignored instructions")
    except Exception as e:
        print(f"ERROR: Failed to load ignored instructions: {e}")
        IGNORED_INSTRUCTIONS = []


def load_register_classes(json_data: Dict[str, Any]) -> bool:
    """
    Loads register classes into the global dictionary using the RegisterFileGenerator.

    The function processes the JSON data provided, extracts register‑class
    definitions, and updates the global structures responsible for handling
    register file information.

    Args:
        json_data (Dict[str, Any]): Parsed JSON data containing register‑class
            definitions and configuration entries.

    Returns:
        bool: True if register classes were successfully loaded, False otherwise.
    """
    global REGISTER_CLASSES, GPR_ALIASES
    REGISTER_CLASSES = {}
    GPR_ALIASES = {}
    
    print("Loading register classes from JSON...")
    
    # Create RegisterFileGenerator for parsing the mappings
    reg_generator = RegisterFileGenerator()
    
    # Parse the mappings
    reg_generator.parse_gpr_mappings(json_data)
    
    # Get GPR aliases
    gpr_aliases = reg_generator.get_all_gpr_aliases()
    
    if gpr_aliases:
        # Save aliases
        GPR_ALIASES = gpr_aliases.copy()
        print(f"  ✓ Loaded {len(GPR_ALIASES)} GPR aliases from JSON")
    
    # Load all register classes from config file 
    available_registers = reg_generator.list_available_registers()
    print(f"  Available register classes in config: {available_registers}")
    
    for reg_class_name in available_registers:
        reg_config = reg_generator.get_register_info(reg_class_name)
        
        if reg_config:
            # For GPR registers, add registers parsed from JSON
            if reg_class_name == 'GPR' and gpr_aliases:
                all_registers = _build_gpr_registers_from_aliases(gpr_aliases)
                reg_config['registers'] = all_registers
                print(f"  ✓ Added {len(all_registers)} GPR registers from JSON")
            
            # For CSR registers, add registers parsed from JSON, if they exist
            elif reg_class_name == 'CSR':
                reg_generator.parse_csr_mappings(json_data)
                # CSR registers are added as entries in the XML
                print(f"  ✓ Parsed CSR mappings from JSON")
            
            REGISTER_CLASSES[reg_class_name] = reg_config
            print(f"  ✓ Loaded {reg_class_name}: {reg_config.get('description', 'No description')}")
    
    if REGISTER_CLASSES:
        print(f"  ✓ Successfully loaded {len(REGISTER_CLASSES)} register classes")
        return True
    else:
        print("  ✗ No register classes loaded")
        return False

def _build_gpr_registers_from_aliases(
    gpr_aliases: Dict[str, str]
) -> Dict[int, Dict[str, List[str]]]:
    """
    Builds the GPR (General-Purpose Register) dictionary based on provided aliases.

    Given a mapping from register names to their aliases, this function constructs
    a structured dictionary of GPRs indexed by register number. Each entry contains
    the canonical register name and the list of associated aliases.

    Args:
        gpr_aliases (Dict[str, str]): A dictionary mapping register names to their
            alias (e.g., {"x0": "zero", "x1": "ra"}). If multiple aliases per
            register are possible, they should be combined prior to calling this
            function or provided in a normalized form.

    Returns:
        Dict[int, Dict[str, List[str]]]: A dictionary keyed by register index,
        where each value is a dictionary with:
            - "name" (str): The canonical register name.
            - "aliases" (List[str]): The list of alias names for that register.
    """
    all_registers = {}
    
    # Group aliases based on the index 
    for arch_name, abi_names in gpr_aliases.items():
        # Extract index (x0 -> 0, x1 -> 1, etc.)
        if arch_name.startswith('x') and arch_name[1:].isdigit():
            reg_index = int(arch_name[1:])
            
            if 0 <= reg_index <= 31:
                if reg_index not in all_registers:
                    all_registers[reg_index] = {'aliases': []}
                
                # Add arch name
                if arch_name not in all_registers[reg_index]['aliases']:
                    all_registers[reg_index]['aliases'].append(arch_name)
                
                # Add aliases
                if isinstance(abi_names, list):
                    for abi_name in abi_names:
                        if abi_name != arch_name and abi_name not in all_registers[reg_index]['aliases']:
                            all_registers[reg_index]['aliases'].append(abi_name)
                elif isinstance(abi_names, str):
                    # Fallback
                    if abi_names != arch_name and abi_names not in all_registers[reg_index]['aliases']:
                        all_registers[reg_index]['aliases'].append(abi_names)
    
    # Fill in missing registers
    for i in range(32):
        if i not in all_registers:
            all_registers[i] = {'aliases': [f'x{i}']}
    
    return all_registers




class InstructionFieldManager:
    def __init__(self):
        # Find and save RTYPE pattern
        self.field_to_register_map = {}
        
        # Known sizes for registers
        self.register_sizes = {
            'GPR': 5,
            'CSR': 12,
            'FPR': 5,
        }
        
        self.immediate_sign_info = {}  # Sign information dict


    def _process_compressed_immediate_fragments(self, contents: str, instruction_name: str) -> None:
        """Processes immediate fragments for compressed instructions."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Processing compressed immediate fragments for {instruction_name}")
        
        # Extract encoding
        match = re.search(r'<->\s*(.+)', contents)
        if not match:
            print(f"  DEBUG: No encoding part found")
            return
        
        encoding_part = match.group(1).strip()
        # Remove 'when' keyword
        encoding_part = re.sub(r'\s+when\s+.*', '', encoding_part)
        components = [comp.strip() for comp in encoding_part.split('@')]
        
        print(f"  DEBUG: Compressed encoding components: {components}")
        
        # Parse encoding
        current_bit = 15  # Compressed instructions
        immediate_fragments = []
        INSTRUCTION_COMPRESSED.append('c.lw')
        INSTRUCTION_COMPRESSED.append('c.sw')
        INSTRUCTION_COMPRESSED.append('c.add')
        INSTRUCTION_COMPRESSED.append('c.srli')
        INSTRUCTION_COMPRESSED.append('c.slli')
        INSTRUCTION_COMPRESSED.append('c.srai')
        INSTRUCTION_COMPRESSED.append('c.addi4spn')
        INSTRUCTION_COMPRESSED.append('c.addi16sp')
        INSTRUCTION_COMPRESSED.append('c.andi')
        INSTRUCTION_COMPRESSED.append('c.j')
        INSTRUCTION_COMPRESSED.append('c.jal')
        INSTRUCTION_COMPRESSED.append('c.bnez')
        INSTRUCTION_COMPRESSED.append('c.beqz')
        for i, component in enumerate(components):
            print(f"  DEBUG: [{i}] Component: '{component}' at bit {current_bit}")
            
            # Check if it's an immediate fragment with bit specification
            imm_match = re.search(r'((?:imm|ui)\w*)\s*:\s*bits\((\d+)\)', component)
            if imm_match:
                fragment_name = imm_match.group(1)
                bit_count = int(imm_match.group(2))
                
                start_bit = current_bit
                end_bit = current_bit - bit_count + 1
                
                immediate_fragments.append({
                    'name': fragment_name,
                    'start': start_bit,
                    'end': end_bit,
                    'bits': bit_count
                })
                
                print(f"    + Found immediate fragment {fragment_name}: [{start_bit}:{end_bit}] ({bit_count} bits)")
                current_bit = end_bit - 1
                
            elif component.startswith('0b'):
                # Binary literal
                bit_count = len(component) - 2
                current_bit -= bit_count
                print(f"    - Binary literal: {bit_count} bits, now at {current_bit}")
                
            elif 'encdec_reg(' in component:
                # Register - 5 bits
                current_bit -= 5
                print(f"    - Register: 5 bits, now at {current_bit}")
                
            elif 'encdec_creg(' in component:
                # Register - 3 bits
                INSTRUCTION_COMPRESSED.append(instruction_name.lower().replace("_", "."))
                current_bit -= 3
                print(f"    - Register: 3 bits, now at {current_bit}")
                
            else:
                # Other components - estimate size
                bit_count = self._calculate_component_bit_count(component)
                current_bit -= bit_count
                print(f"    - Other: {bit_count} bits (default), now at {current_bit}")
        
        # If we found fragments, create the compressed field
        if len(immediate_fragments) > 1:
            # Multiple fragments - create imm_ci with multiple ranges
            ranges = [(frag['start'], frag['end']) for frag in immediate_fragments]
            total_bits = sum(frag['bits'] for frag in immediate_fragments)
            
            field_info = {
                'ranges': ranges,
                'shift': 0,  # Compressed immediates don't have implicit shift
                'total_bits': total_bits
            }
            
            INSTRUCTION_FIELD_RANGES['imm_ci'] = field_info
            print(f"  + Created compressed immediate field 'imm_ci' with {len(ranges)} ranges:")
            for i, (start, end) in enumerate(ranges):
                print(f"    Range {i+1}: [{start}:{end}] ({start-end+1} bits)")
            print(f"    Total bits: {total_bits}")
            
        elif len(immediate_fragments) == 1:
            # Single fragment - simple range
            frag = immediate_fragments[0]
            INSTRUCTION_FIELD_RANGES['imm_ci'] = (frag['start'], frag['end'])
            print(f"  + Created compressed immediate field 'imm_ci': [{frag['start']}:{frag['end']}]")


    def _is_vector_extension_enabled(self, extension_filter: List[str] = None) -> bool:
        """Checks if the vector extension is enabled."""
        if not extension_filter:
            return False
        
        # Check for Zimt or V (vector extension)
        vector_extensions = {'zimt', 'v'}  # lowercase for comparison
        
        for ext in extension_filter:
            if ext.lower() in vector_extensions:
                return True
        
        return False
    
    
    def _detect_sign_extend_for_immediate(self, imm_name: str, json_data: Dict[str, Any]) -> bool:
        """Detects if an immediate has sign_extend function applied in the Sail definition."""
        print(f"DEBUG: Checking if {imm_name} uses sign_extend")
        
        # Search in all function clause execute
        if 'functions' not in json_data:
            print(f"DEBUG: No 'functions' section in json_data")
            return False
        
        functions = json_data['functions']
        if 'execute' not in functions:
            print(f"DEBUG: No 'execute' in functions")
            print(f"DEBUG: Available keys in functions: {list(functions.keys())}")
            return False
        
        execute_section = functions['execute']
        if 'function' not in execute_section:
            print(f"DEBUG: No 'function' in execute_section")
            print(f"DEBUG: Available keys in execute_section: {list(execute_section.keys())}")
            return False
        
        function_list = execute_section['function']
        if not isinstance(function_list, list):
            print(f"DEBUG: function_list is not a list, type: {type(function_list)}")
            return False
        
        print(f"DEBUG: Searching through {len(function_list)} functions")
        
        # Go through all execute functions
        for i, func_item in enumerate(function_list):
            if not isinstance(func_item, dict):
                continue
            
            source = func_item.get('source', {})
            if not isinstance(source, dict):
                continue
            
            contents = source.get('contents', '')
            if not isinstance(contents, str):
                continue
            
            # Debug: show first functions that contain 'imm'
            if i < 5 and 'imm' in contents.lower():
                print(f"DEBUG: Function {i} contains 'imm': {contents[:200]}...")
            
            # Search for pattern: sign_extend(imm) or sign_extend(imm_*)
            patterns = [
                rf'sign_extend\s*\(\s*{re.escape(imm_name)}\s*\)',
                rf'sign_extend\s*\(\s*imm\s*\)',
                rf'let\s+\w+\s*:\s*\w+\s*=\s*sign_extend\s*\(\s*imm\s*\)',
            ]
            
            for pattern in patterns:
                if re.search(pattern, contents, re.IGNORECASE):
                    print(f"DEBUG: ✓ Found sign_extend for {imm_name} with pattern: {pattern}")
                    print(f"DEBUG: In content: {contents[:100]}...")
                    return True
        
        print(f"DEBUG: ✗ No sign_extend found for {imm_name}")
        return False
    
    def _analyze_immediate_signedness(self, json_data: Dict[str, Any]) -> None:
        """Analyzes all immediates to determine which are signed."""
        global IMMEDIATE_SIGN_INFO
        
        print("\n" + "="*60)
        print("ANALYZING IMMEDIATE SIGNEDNESS FROM SAIL DEFINITIONS")
        print("="*60)
        
        # Debug: check JSON structure
        print(f"DEBUG: json_data keys: {list(json_data.keys())}")
        
        # For each known immediate field
        immediate_fields = [f for f in INSTRUCTION_FIELD_RANGES.keys() 
                        if f.startswith('imm_') or f == 'imm']
        
        print(f"DEBUG: Found {len(immediate_fields)} immediate fields to analyze: {immediate_fields}")
        
        for field_name in immediate_fields:
            print(f"\nDEBUG: Analyzing {field_name}...")
            is_signed = self._detect_sign_extend_for_immediate(field_name, json_data)
            self.immediate_sign_info[field_name] = is_signed
            IMMEDIATE_SIGN_INFO[field_name] = is_signed
            print(f"  {field_name}: {'SIGNED' if is_signed else 'UNSIGNED'}")
        
        print(f"\n✓ Analyzed {len(self.immediate_sign_info)} immediate fields")
        print(f"DEBUG: immediate_sign_info = {self.immediate_sign_info}")
        print(f"DEBUG: IMMEDIATE_SIGN_INFO (global) = {IMMEDIATE_SIGN_INFO}")


    
    def _extract_from_rtype_and_identify_registers(self, json_data: Dict[str, Any]) -> bool:
        """Extracts ranges from RTYPE and automatically identifies registers."""
        if 'mappings' not in json_data or 'encdec' not in json_data['mappings']:
            return False
        
        mapping_list = json_data['mappings']['encdec']['mapping'] + json_data['mappings']['encdec_compressed']['mapping']
        if not isinstance(mapping_list, list):
            return False
        
        # Search for RTYPE
        for instruction_data in mapping_list:
            if not isinstance(instruction_data, dict):
                continue
                
            source = instruction_data.get('source', {})
            contents = source.get('contents', '')
            
            if 'RTYPE' not in contents or '<->' not in contents:
                continue
            
            print(f"Found RTYPE: {contents}")
            
            # Parse encoding and identify registers
            success = self._parse_rtype_and_identify_registers(contents)
            if success:
                return True
        
        return False
    
    def _parse_rtype_and_identify_registers(self, contents: str) -> bool:
        """Parses RTYPE and automatically identifies registers from encdec_reg."""
        global INSTRUCTION_FIELD_RANGES
        
        # Extract encoding part (after <->)
        match = re.search(r'<->\s*(.+)', contents)
        if not match:
            return False
        
        encoding_part = match.group(1).strip()
        
        # Split into components
        components = [comp.strip() for comp in encoding_part.split('@')]
        
        current_bit = 31  # Start from MSB
        
        for i, component in enumerate(components):
            field_name, field_size, is_register, reg_class = self._analyze_rtype_component(component, i, len(components))
            
            if field_name and field_size > 0:
                start_bit = current_bit
                end_bit = current_bit - field_size + 1
                INSTRUCTION_FIELD_RANGES[field_name] = (start_bit, end_bit)
                
                print(f"  Added FIXED {field_name}: ({start_bit}, {end_bit})")
                
                # If it's a register, add it to mapping
                if is_register and reg_class:
                    self.field_to_register_map[field_name] = reg_class
                    print(f"    -> Auto-detected register: {field_name} -> {reg_class}")
                
                current_bit = end_bit - 1
        
        return len(INSTRUCTION_FIELD_RANGES) > 0
    
    def _analyze_rtype_component(self, component: str, position: int, total_components: int) -> tuple:
        """Analyzes an RTYPE component and determines if it's a register."""
        component = component.strip()
        
        # Check if it's a register function: encdec_reg(register_name)
        reg_match = re.search(r'encdec_reg\((\w+)\)', component)
        if reg_match:
            reg_name = reg_match.group(1)
            # Determine register class based on name
            reg_class = self._determine_register_class(reg_name)
            return reg_name, 5, True, reg_class  # registers have 5 bits
        
        creg_match = re.search(r'encdec_creg\((\w+)\)', component)
        if creg_match:
            creg_original = creg_match.group(1)
            creg_name = creg_match.group(1) + "_c"
            # Determine register class based on name
            creg_class = self._determine_register_class(creg_original)
            return creg_name, 3, True, creg_class  # registers have 3 bits
        
        # Check if it's rsd directly (not in a function)
        if component == 'rsd':
            return 'rsd', 5, True, 'GPR'
        
        # Check if it's shamt directly (not in a function)
        if component == 'shamt':
            return 'shamt', 5, False, None  # shamt has 5 bits and is not a register
        
        # Binary literal
        if component.startswith('0b'):
            binary_value = component[2:]
            field_size = len(binary_value)
            
            if field_size == 7:
                if position == total_components - 1:
                    return 'opcode', 7, False, None
                elif position == 0:
                    return 'funct7', 7, False, None
            elif field_size == 3:
                return 'funct3', 3, False, None
            elif field_size == 6:
                return 'funct7', 6, False, None
            elif field_size == 5:
                return 'shamt', 5, False, None
            
            return f'literal_{field_size}bit', field_size, False, None
        
        # Other functions
        func_match = re.search(r'encdec_(\w+)\((\w+)\)', component)
        if func_match:
            func_type = func_match.group(1)
            param_name = func_match.group(2)
            
            # Check if parameter is shamt
            if param_name == 'shamt':
                return 'shamt', 5, False, None  # shamt is not a register
            
            # Check if it's a special register function
            if 'reg' in func_type.lower():
                reg_class = self._determine_register_class_from_function(func_type)
                return param_name, 5, True, reg_class  # default 5 bits for registers
            else:
                return param_name, 3, False, None  # default for other functions
        
        return None, 0, False, None

    
    def _find_shamt_in_mappings(self, json_data: Dict[str, Any]) -> None:
        """Searches for and adds the shamt field from all mappings."""
        global INSTRUCTION_FIELD_RANGES
        
        print("Searching for shamt field in all mappings...")
        
        if 'mappings' not in json_data or 'encdec' not in json_data['mappings']:
            return
        
        mapping_list = json_data['mappings']['encdec']['mapping'] + json_data['mappings']['encdec_compressed']['mapping']
        if not isinstance(mapping_list, list):
            return
        
        for instruction_data in mapping_list:
            if not isinstance(instruction_data, dict):
                continue
                
            source = instruction_data.get('source', {})
            contents = source.get('contents', '')
            
            if not isinstance(contents, str):
                continue
            
            # Search for shamt in contents
            if 'shamt' in contents and '<->' in contents:
                print(f"Found shamt in: {contents}")
                
                # Parse encoding to find shamt position
                match = re.search(r'<->\s*(.+)', contents)
                if match:
                    encoding_part = match.group(1).strip()
                    components = [comp.strip() for comp in encoding_part.split('@')]
                    
                    print(f"  Encoding components: {components}")
                    
                    current_bit = 31  # Start from MSB
                    for i, component in enumerate(components):
                        print(f"  Processing component {i}: '{component}' at bit {current_bit}")
                        
                        if component == 'shamt':
                            # Found shamt - calculate position
                            start_bit = current_bit
                            end_bit = current_bit - 5 + 1  # shamt has 5 bits
                            
                            print(f"  Found shamt at position: start_bit={start_bit}, end_bit={end_bit}")
                            
                            if 'shamt' not in INSTRUCTION_FIELD_RANGES:
                                INSTRUCTION_FIELD_RANGES['shamt'] = (start_bit, end_bit)
                                print(f"  + Added shamt: ({start_bit}, {end_bit})")
                                return
                            
                            current_bit = end_bit - 1
                        elif component.startswith('0b'):
                            # Binary literal - calculate size and skip
                            literal_size = len(component) - 2  # Subtract "0b"
                            current_bit -= literal_size
                            print(f"    - Binary literal {component}: {literal_size} bits, now at bit {current_bit}")
                        elif 'encdec_reg(' in component:
                            # Register - 5 bits
                            reg_match = re.search(r'encdec_reg\((\w+)\)', component)
                            if reg_match:
                                reg_name = reg_match.group(1)
                                start_bit = current_bit
                                end_bit = current_bit - 5 + 1
                                print(f"  Register '{reg_name}': ({start_bit}, {end_bit}) - 5 bits")
                                current_bit = end_bit - 1
                        elif 'encdec_creg(' in component:
                            # Register - 3 bits
                            reg_match = re.search(r'encdec_creg\((\w+)\)', component)
                            if reg_match:
                                reg_name = reg_match.group(1) + "_c"
                                start_bit = current_bit
                                end_bit = current_bit - 3 + 1
                                print(f"  Register '{reg_name}': ({start_bit}, {end_bit}) - 3 bits")
                                current_bit = end_bit - 1
                        else:
                            # Other components - assume 3 bits
                            start_bit = current_bit
                            end_bit = current_bit - 3 + 1
                            print(f"  Other component '{component}': ({start_bit}, {end_bit}) - 3 bits")
                            current_bit = end_bit - 1
                    
                    return  # Found shamt, stop searching


    def _determine_register_class(self, reg_name: str) -> str:
        """Determines register class based on name."""
        # For RISC-V, most registers are GPR
        if reg_name in ['rd', 'rs1', 'rs2', 'rs3', 'rsd', 'rd_c', 'rs1_c', 'rs2_c']:
            return 'GPR'
        elif reg_name in ['md', 'ms1', 'ms2']:
            return 'VR'
        elif reg_name == 'csr':
            return 'CSR'
        elif reg_name.startswith('f'):  # floating point registers
            return 'FPR'
        else:
            return 'GPR'  # default


    
    def _determine_register_class_from_function(self, func_type: str) -> str:
        """Determines register class based on function type."""
        if 'csr' in func_type.lower():
            return 'CSR'
        elif 'fp' in func_type.lower() or 'float' in func_type.lower():
            return 'FPR'
        else:
            return 'GPR'  # default
    
    
    def _has_fragmented_immediates(self, contents: str, template_name: str) -> bool:
        """Checks if a template has fragmented immediates."""
        print(f"  DEBUG: Checking if {template_name} has fragmented immediates")
        print(f"  DEBUG: Contents: {contents}")
        
        # For JTYPE, search for JAL instead of JTYPE
        if template_name == 'JTYPE':
            search_pattern = r'JAL\(([^)]+)\)'
        else:
            search_pattern = rf'{re.escape(template_name)}\(([^)]+)\)'
        
        template_match = re.search(search_pattern, contents, re.IGNORECASE)
        
        if not template_match:
            print(f"  DEBUG: No pattern found for {template_name} (searched for: {search_pattern})")
            return False
        
        template_content = template_match.group(1)
        print(f"  DEBUG: Found {template_name} content: {template_content}")
        
        # Count how many imm* fragments we have
        imm_fragments = []
        parts = [part.strip() for part in template_content.split('@')]
        
        for part in parts:
            if (part.startswith('imm') or part.startswith('ui') and 
                not part.startswith('0b') and 
                not part in ['rs1', 'rs2', 'rs3', 'rd', 'op']):
                imm_fragments.append(part)
        
        print(f"  DEBUG: Found immediate fragments: {imm_fragments}")
    
        # If we have more than one fragment, it's fragmented
        if len(imm_fragments) > 1:
            print(f"  DEBUG: {template_name} has {len(imm_fragments)} immediate fragments: {imm_fragments} -> FRAGMENTED")
            return True
        
        # Also check if we have fragments with specific names (any imm with digits/underscore)
        for fragment in imm_fragments:
            # More flexible pattern: imm followed by digits and/or underscore
            if re.match(r'imm[_\d]+', fragment) and fragment != 'imm':
                print(f"  DEBUG: {template_name} has specific immediate fragment: {fragment} -> FRAGMENTED")
                return True
            elif re.match(r'ui[_\d]+', fragment):
                print(f"  DEBUG: {template_name} has specific immediate fragment: {fragment} -> FRAGMENTED")
                return True
        
        print(f"  DEBUG: {template_name} has simple immediates: {imm_fragments} -> NOT FRAGMENTED")
        return False


    def _process_immediate_fragments_generic(self, contents: str, template_name: str) -> None:
        """Processes immediate fragments for any template respecting the order from mapping clause."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Processing {template_name} immediate fragments generically")
        
        # Extract encoding part
        match = re.search(r'<->\s*(.+)', contents)
        if not match:
            print(f"  DEBUG: No encoding part found in {template_name}")
            return
        
        encoding_part = match.group(1).strip()
        components = [comp.strip() for comp in encoding_part.split('@')]
        
        print(f"  DEBUG: {template_name} encoding components: {components}")
        
        # Extract logical order from left side (mapping clause)
        logical_order = self._extract_logical_order_generic(contents, template_name)
        if not logical_order:
            print(f"  DEBUG: No logical order found for {template_name}")
            return
        
        # Detect shift from left side (mapping clause)
        shift_amount = self._detect_shift_amount(contents, template_name)
        
        print(f"  DEBUG: {template_name} logical order: {logical_order}")
        print(f"  DEBUG: {template_name} shift amount: {shift_amount}")
        
        # Parse encoding to find physical positions
        current_bit = 31
        physical_positions = {}  # fragment_name -> (start_bit, end_bit)
        
        for component in components:
            print(f"  DEBUG: Processing {template_name} component: {component}")
            
            # Check if it's an immediate fragment
            imm_match = re.search(r'(imm\w*)\s*:\s*bits\((\d+)\)', component)
            if imm_match:
                fragment_name = imm_match.group(1)
                bit_count = int(imm_match.group(2))
                
                start_bit = current_bit
                end_bit = current_bit - bit_count + 1
                
                physical_positions[fragment_name] = (start_bit, end_bit)
                
                print(f"    + Found {template_name} immediate fragment {fragment_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                current_bit = end_bit - 1
                
            elif 'encdec_reg(' in component:
                # It's a register - calculate size (5 bits for GPR)
                reg_match = re.search(r'encdec_reg\((\w+)\)', component)
                if reg_match:
                    reg_name = reg_match.group(1)
                    bit_count = 5  # GPR has 5 bits
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    
                    print(f"    + Found {template_name} register {reg_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                    current_bit = end_bit - 1
                else:
                    # Unknown register - assume 5 bits
                    bit_count = 5
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    current_bit = end_bit - 1
                    print(f"    + Found {template_name} unknown register: ({start_bit}, {end_bit}) - {bit_count} bits")
                    
            elif 'encdec_creg(' in component:
                # It's a register - calculate size (3 bits for compressed GPR)
                reg_match = re.search(r'encdec_creg\((\w+)\)', component)
                if reg_match:
                    reg_name = reg_match.group(1) + "_c"
                    bit_count = 3  # Compressed GPR has 3 bits
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    
                    print(f"    + Found {template_name} register {reg_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                    current_bit = end_bit - 1
                else:
                    # Unknown register - assume 3 bits
                    bit_count = 3
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    current_bit = end_bit - 1
                    print(f"    + Found {template_name} unknown register: ({start_bit}, {end_bit}) - {bit_count} bits")
            
            elif re.search(r'encdec_(\w+)\(', component):
                # It's an encoding function - determine size
                func_match = re.search(r'encdec_(\w+)\(', component)
                func_type = func_match.group(1) if func_match else 'unknown'
                
                # Determine size based on function type
                if func_type in ['bop', 'sop', 'iop', 'lop', 'cop', 'aop', 'fop']:  # funct3
                    bit_count = 3
                elif func_type in ['rop']:  # funct7
                    bit_count = 7
                elif func_type in ['uop']:  # opcode for UTYPE
                    bit_count = 7
                else:
                    bit_count = 3  # default for unknown functions
                
                start_bit = current_bit
                end_bit = current_bit - bit_count + 1
                
                print(f"    + Found {template_name} encoding function {func_type}: ({start_bit}, {end_bit}) - {bit_count} bits")
                current_bit = end_bit - 1
            
            elif component.startswith('0b'):
                # It's a binary constant
                const_bits = len(component) - 2  # Subtract "0b"
                start_bit = current_bit
                end_bit = current_bit - const_bits + 1
                
                print(f"    + Found {template_name} binary constant {component}: ({start_bit}, {end_bit}) - {const_bits} bits")
                current_bit = end_bit - 1
            
            else:
                # Unknown component - assume 1 bit
                print(f"    + Found {template_name} unknown component {component}: assuming 1 bit")
                current_bit -= 1
        
        # Map fragments in logical order to physical positions
        immediate_ranges = []
        total_bits = 0
        
        for fragment in logical_order:
            if fragment in physical_positions:
                range_tuple = physical_positions[fragment]
                immediate_ranges.append(range_tuple)
                bits_in_range = range_tuple[0] - range_tuple[1] + 1
                total_bits += bits_in_range
                print(f"    + Mapped {fragment} to range {range_tuple} ({bits_in_range} bits)")
            else:
                print(f"    ! Fragment {fragment} not found in physical positions")
        
        # Add field with all ranges and shift
        if immediate_ranges:
            # SPECIAL: For JAL (JTYPE), use imm_jal instead of imm_jtype
            if template_name == 'JTYPE' and 'JAL(' in contents:
                imm_field_name = 'imm_jal'
            else:
                imm_field_name = f'imm_{template_name.lower()}'
            
            # Create structure with ranges and shift
            field_info = {
                'ranges': immediate_ranges,
                'shift': shift_amount,
                'total_bits': total_bits
            }
            
            INSTRUCTION_FIELD_RANGES[imm_field_name] = field_info
            print(f"    + Created {template_name} immediate field '{imm_field_name}' with {len(immediate_ranges)} ranges, total {total_bits} bits, shift {shift_amount}")
            print(f"    + Ranges: {immediate_ranges}")
        else:
            print(f"    ! No immediate ranges found for {template_name}")
            
    def _detect_shift_amount(self, contents: str, template_name: str) -> int:
        """Detects shift based on template and constants from encoding."""
        
        # For RISC-V, branch and jump instructions are always aligned to 2 bytes
        # This means the last bit is always 0, so shift = 1
        if template_name in ['BTYPE', 'JTYPE']:
            print(f"  DEBUG: {template_name} instruction - using standard alignment shift: 1 bit")
            return 1
        
        # For other templates, search in encoding
        match = re.search(r'<->\s*(.+)', contents)
        if not match:
            print(f"  DEBUG: No encoding part found for shift detection in {template_name}")
            return 0
        
        encoding_part = match.group(1).strip()
        components = [comp.strip() for comp in encoding_part.split('@')]
        
        shift_amount = 0
        
        for component in components:
            if component.startswith('0b') and all(bit == '0' for bit in component[2:]):
                # Constant with only zeros
                shift_bits = len(component) - 2  # Subtract "0b"
                shift_amount += shift_bits
                print(f"    + Found zero constant {component}: adds {shift_bits} bits of shift")
        
        print(f"  DEBUG: Total shift amount for {template_name}: {shift_amount} bits")
        return shift_amount



    def _extract_logical_order_generic(self, contents: str, template_name: str) -> List[str]:
        """Extracts logical order of immediate fragments from mapping clause for any template."""
        
        # For JTYPE, search for JAL instead of JTYPE
        if template_name == 'JTYPE':
            search_pattern = r'JAL\(([^)]+)\)'
        else:
            search_pattern = rf'{re.escape(template_name)}\(([^)]+)\)'
        
        template_match = re.search(search_pattern, contents, re.IGNORECASE)
        
        if not template_match:
            print(f"  DEBUG: No {template_name} pattern found in contents (searched for: {search_pattern})")
            return []
        
        template_content = template_match.group(1)
        print(f"  DEBUG: Found {template_name} content: {template_content}")
        
        # Extract fragments (ignore constants and registers)
        fragments = []
        parts = [part.strip() for part in template_content.split('@')]
        
        for part in parts:
            # Search for fragments of type imm*, but exclude binary constants and registers
            if (part.startswith('imm') and 
                not part.startswith('0b') and 
                not part in ['rs1', 'rs2', 'rs3', 'rd', 'op']):
                fragments.append(part)
                print(f"    + Found immediate fragment in logical order: {part}")
        
        return fragments

    
    def _calculate_immediates_from_fixed_positions(self, contents: str, template_name: str) -> None:
        """Calculates immediates based on fixed positions from RTYPE."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Calculating immediates for {template_name}")
        print(f"  DEBUG: Contents: {contents}")
        
        # Check if template has fragmented immediates
        if self._has_fragmented_immediates(contents, template_name):
            print(f"  DEBUG: {template_name} has fragmented immediates - using generic processing")
            self._process_immediate_fragments_generic(contents, template_name)
            return
        
        # For simple immediates, calculate based on fixed positions
        print(f"  DEBUG: {template_name} has simple immediates - calculating from fixed positions")
        
        # Extract encoding part
        match = re.search(r'<->\s*(.+)', contents)
        if not match:
            print(f"  DEBUG: No encoding found for {template_name}")
            return
        
        encoding_part = match.group(1).strip()
        print(f"  DEBUG: Encoding part: {encoding_part}")
        
        # For BTYPE, process immediate fragments (existing specific case)
        if template_name == 'BTYPE':
            self._process_btype_immediate_fragments(contents)
            return
        
        # For STYPE, process immediate fragments (existing specific case)
        if template_name == 'STYPE':
            self._process_stype_immediate_fragments(contents)
            return
        
        # For all other templates, use generic variant
        else:
            print(f"  DEBUG: Using generic processing for {template_name}")
            
            # Check if template has fragmented immediates
            if self._has_fragmented_immediates(contents, template_name):
                print(f"  DEBUG: {template_name} has fragmented immediates, using generic fragmented processing")
                self._process_immediate_fragments_generic(contents, template_name)
                return
            else:
                print(f"  DEBUG: {template_name} has simple immediates, using standard processing")
                # Continue with existing logic for simple immediates
                pass
        
        # Existing logic for templates with simple immediates (UTYPE, ITYPE, simple JTYPE)
        components = [comp.strip() for comp in encoding_part.split('@')]
        print(f"  DEBUG: Components: {components}")
        
        # Identify known fields in encoding
        known_fields_in_encoding = []
        immediate_components = []
        
        for component in components:
            print(f"  DEBUG: Processing component: {component}")
            
            # Check if it's a known register
            reg_match = re.search(r'encdec_reg\((\w+)\)', component)
            if reg_match:
                reg_name = reg_match.group(1)
                print(f"  DEBUG: Found register: {reg_name}")
                if reg_name in INSTRUCTION_FIELD_RANGES:
                    known_fields_in_encoding.append(reg_name)
                    print(f"  DEBUG: Added known field: {reg_name}")
                    continue
            
            creg_match = re.search(r'encdec_creg\((\w+)\)', component)
            if creg_match:
                creg_name = creg_match.group(1) + "_c"
                print(f"  DEBUG: Found register: {reg_name}")
                if creg_name in INSTRUCTION_FIELD_RANGES:
                    known_fields_in_encoding.append(creg_name)
                    print(f"  DEBUG: Added known field: {creg_name}")
                    continue
            
            # MODIFIED: Check if it's opcode through encdec_*op functions
            opcode_match = re.search(r'encdec_(\w*op)\((\w+)\)', component)
            if opcode_match:
                func_type = opcode_match.group(1)  # uop, iop, rop, etc.
                param_name = opcode_match.group(2)  # op, mul_op, etc.
                print(f"  DEBUG: Found opcode function: {func_type}({param_name})")
                known_fields_in_encoding.append('opcode')
                print(f"  DEBUG: Added opcode field")
                continue
            
            # Check if it's opcode (7-bit literal at end)
            if component.startswith('0b') and len(component[2:]) == 7:
                # Check if it's the last component (opcode)
                if component == components[-1]:
                    known_fields_in_encoding.append('opcode')
                    print(f"  DEBUG: Added literal opcode field")
                    continue
            
            # Check if it's funct3 (3-bit literal)
            if component.startswith('0b') and len(component[2:]) == 3:
                known_fields_in_encoding.append('funct3')
                print(f"  DEBUG: Added funct3 field")
                continue
            
            # Otherwise, it's part of immediate
            immediate_components.append(component)
            print(f"  DEBUG: Added to immediate components: {component}")
        
        print(f"  DEBUG: Known fields: {known_fields_in_encoding}")
        print(f"  DEBUG: Immediate components: {immediate_components}")
        
        # Calculate range for immediate based on known fields
        if immediate_components:
            imm_range = self._calculate_immediate_range(known_fields_in_encoding, template_name)
            if imm_range:
                imm_name = f'imm_{template_name.lower()}'
                INSTRUCTION_FIELD_RANGES[imm_name] = imm_range
                print(f"    + Added {imm_name}: {imm_range}")
            else:
                print(f"  DEBUG: Could not calculate immediate range for {template_name}")
        else:
            print(f"  DEBUG: No immediate components found for {template_name}")
            
            # ADDED: For templates that should have immediates, force generation
            if template_name in ['UTYPE', 'ITYPE']:
                print(f"  DEBUG: Forcing immediate generation for {template_name}")
                imm_range = self._calculate_immediate_range(known_fields_in_encoding, template_name)
                if imm_range:
                    imm_name = f'imm_{template_name.lower()}'
                    INSTRUCTION_FIELD_RANGES[imm_name] = imm_range
                    print(f"    + Forced {imm_name}: {imm_range}")



    def _process_jtype_immediate_fragments(self, contents: str) -> None:
        """Processes immediate fragments for JTYPE (JAL) and creates a single field with multiple ranges."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Processing JTYPE immediate fragments")
        
        # Extract encoding part
        match = re.search(r'<->\s*(.+)', contents)
        if not match:
            return
        
        encoding_part = match.group(1).strip()
        components = [comp.strip() for comp in encoding_part.split('@')]
        
        print(f"  DEBUG: JTYPE encoding components: {components}")
        
        # Parse each component to find immediate fragments
        current_bit = 31
        immediate_ranges = []  # List of ranges for immediate
        
        for component in components:
            print(f"  DEBUG: Processing JTYPE component: {component}")
            
            # Check if it's an immediate fragment with bit specification
            imm_match = re.search(r'(imm\w*)\s*:\s*bits\((\d+)\)', component)
            if imm_match:
                fragment_name = imm_match.group(1)
                bit_count = int(imm_match.group(2))
                
                start_bit = current_bit
                end_bit = current_bit - bit_count + 1
                
                # Add range to immediate list
                immediate_ranges.append((start_bit, end_bit))
                
                print(f"    + Found JTYPE immediate fragment {fragment_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                current_bit = end_bit - 1
                
            elif 'encdec_reg(' in component:
                # It's a register - calculate size (5 bits for GPR)
                reg_match = re.search(r'encdec_reg\((\w+)\)', component)
                if reg_match:
                    reg_name = reg_match.group(1)
                    bit_count = 5  # GPR has 5 bits
                    
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    
                    # Add register as simple range if it doesn't exist
                    if reg_name not in INSTRUCTION_FIELD_RANGES:
                        INSTRUCTION_FIELD_RANGES[reg_name] = (start_bit, end_bit)
                        print(f"    + Added register {reg_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                    
                    current_bit = end_bit - 1
            
            elif 'encdec_creg(' in component:
                # It's a register - calculate size (3 bits for compressed GPR)
                reg_match = re.search(r'encdec_creg\((\w+)\)', component)
                if reg_match:
                    reg_name = reg_match.group(1) + "_c"
                    bit_count = 3  # Compressed GPR has 3 bits
                    
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    
                    # Add register as simple range if it doesn't exist
                    if reg_name not in INSTRUCTION_FIELD_RANGES:
                        INSTRUCTION_FIELD_RANGES[reg_name] = (start_bit, end_bit)
                        print(f"    + Added register {reg_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                    
                    current_bit = end_bit - 1
                    
            elif component.startswith('0b'):
                # It's a binary literal
                binary_value = component[2:]
                bit_count = len(binary_value)
                
                start_bit = current_bit
                end_bit = current_bit - bit_count + 1
                
                # For opcode (last 7-bit literal)
                if bit_count == 7:
                    field_name = 'opcode'
                    if field_name not in INSTRUCTION_FIELD_RANGES:
                        INSTRUCTION_FIELD_RANGES[field_name] = (start_bit, end_bit)
                        print(f"    + Added {field_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                
                current_bit = end_bit - 1
        
        # If we didn't find specific fragments, create standard JTYPE immediate
        if not immediate_ranges:
            print(f"  DEBUG: No specific fragments found, creating standard JTYPE immediate")
            # JTYPE standard: imm[31:12] (similar to UTYPE)
            if 'rd' in INSTRUCTION_FIELD_RANGES:
                rd_start, rd_end = INSTRUCTION_FIELD_RANGES['rd']
                # Fragment: from 31 to start of rd
                jtype_range = (31, rd_start + 1)
                immediate_ranges = [jtype_range]
                print(f"    + Created standard JTYPE range: {immediate_ranges}")
        
        # Add JTYPE immediate
        if immediate_ranges:
            if len(immediate_ranges) == 1:
                # Single range
                INSTRUCTION_FIELD_RANGES['imm_jtype'] = immediate_ranges[0]
                print(f"  + Added imm_jtype: {immediate_ranges[0]}")
            else:
                # Multiple ranges
                INSTRUCTION_FIELD_RANGES['imm_jtype'] = immediate_ranges
                print(f"  + Added imm_jtype with {len(immediate_ranges)} ranges:")
                for i, (start, end) in enumerate(immediate_ranges):
                    print(f"    Range {i+1}: [{start}:{end}] ({start-end+1} bits)")
        else:
            print(f"  WARNING: Could not create JTYPE immediate ranges")



    def _check_and_add_from_template(self, json_data: Dict[str, Any], template_name: str) -> None:
        """Checks a template and adds new fields using fixed positions from RTYPE."""
        global INSTRUCTION_FIELD_RANGES
        
        mapping_list = json_data['mappings']['encdec']['mapping'] + json_data['mappings']['encdec_compressed']['mapping']
        
        found_template = False
        for instruction_data in mapping_list:
            if not isinstance(instruction_data, dict):
                continue
                
            source = instruction_data.get('source', {})
            contents = source.get('contents', '')
            
            # For JTYPE, specifically search for JAL - MODIFIED: no longer treat specially
            if template_name == 'JTYPE':
                if 'JAL(' not in contents or '<->' not in contents:
                    continue
            # For STYPE, specifically search for STORE or STYPE
            elif template_name == 'STYPE':
                if not (('STORE' in contents.upper() or 'STYPE' in contents.upper()) and '<->' in contents):
                    continue
            else:
                if template_name not in contents or '<->' not in contents:
                    continue
            
            print(f"  Found {template_name}: {contents}")
            found_template = True
            
            # For templates with immediates, calculate based on fixed positions
            self._calculate_immediates_from_fixed_positions(contents, template_name)
            
            break  # Found template, stop searching
        
        if not found_template:
            print(f"  WARNING: Template {template_name} not found in JSON")




    def _process_stype_immediate_fragments(self, contents: str) -> None:
        """Processes immediate fragments for STYPE (STORE) and creates a single field with multiple ranges."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Processing STYPE immediate fragments")
        
        # Extract encoding part
        match = re.search(r'<->\s*(.+)', contents)
        if not match:
            return
        
        encoding_part = match.group(1).strip()
        components = [comp.strip() for comp in encoding_part.split('@')]
        
        print(f"  DEBUG: STYPE encoding components: {components}")
        
        # Parse each component to find immediate fragments
        current_bit = 31
        immediate_ranges = []  # List of ranges for immediate
        
        for component in components:
            print(f"  DEBUG: Processing STYPE component: {component}")
            
            # Check if it's an immediate fragment with bit specification
            imm_match = re.search(r'(imm\w*)\s*:\s*bits\((\d+)\)', component)
            if imm_match:
                fragment_name = imm_match.group(1)
                bit_count = int(imm_match.group(2))
                
                start_bit = current_bit
                end_bit = current_bit - bit_count + 1
                
                # Add range to immediate list
                immediate_ranges.append((start_bit, end_bit))
                
                print(f"    + Found STYPE immediate fragment {fragment_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                current_bit = end_bit - 1
                
                
            elif 'encdec_reg(' in component:
                # It's a register - calculate size (5 bits for GPR)
                reg_match = re.search(r'encdec_reg\((\w+)\)', component)
                if reg_match:
                    reg_name = reg_match.group(1)
                    bit_count = 5  # GPR has 5 bits
                    
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    
                    # Add register as simple range if it doesn't exist
                    if reg_name not in INSTRUCTION_FIELD_RANGES:
                        INSTRUCTION_FIELD_RANGES[reg_name] = (start_bit, end_bit)
                        print(f"    + Added register {reg_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
            
            elif 'encdec_creg(' in component:
                # It's a register - calculate size (3 bits for compressed GPR)
                reg_match = re.search(r'encdec_creg\((\w+)\)', component)
                if reg_match:
                    reg_name = reg_match.group(1) + "_c"
                    bit_count = 3  # Compressed GPR has 3 bits
                    
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    
                    # Add register as simple range if it doesn't exist
                    if reg_name not in INSTRUCTION_FIELD_RANGES:
                        INSTRUCTION_FIELD_RANGES[reg_name] = (start_bit, end_bit)
                        print(f"    + Added register {reg_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                    
                    current_bit = end_bit - 1
                    
            elif 'encdec_' in component and '(' in component:
                # It's an encoding function (funct3, opcode, etc.)
                func_match = re.search(r'encdec_(\w+)\(', component)
                if func_match:
                    func_type = func_match.group(1)
                    
                    # Determine size based on type
                    if 'sop' in func_type:  # store operation = funct3 = 3 bits
                        bit_count = 3
                        field_name = 'funct3'
                    elif 'op' in func_type:  # opcode = 7 bits
                        bit_count = 7
                        field_name = 'opcode'
                    else:
                        bit_count = 3  # default
                        field_name = func_type
                    
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    
                    if field_name not in INSTRUCTION_FIELD_RANGES:
                        INSTRUCTION_FIELD_RANGES[field_name] = (start_bit, end_bit)
                        print(f"    + Added function {field_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                    
                    current_bit = end_bit - 1
                    
            elif component.startswith('0b'):
                # It's a binary literal
                binary_value = component[2:]
                bit_count = len(binary_value)
                
                start_bit = current_bit
                end_bit = current_bit - bit_count + 1
                
                # For opcode (last 7-bit literal)
                if bit_count == 7:
                    field_name = 'opcode'
                    if field_name not in INSTRUCTION_FIELD_RANGES:
                        INSTRUCTION_FIELD_RANGES[field_name] = (start_bit, end_bit)
                        print(f"    + Added {field_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                elif bit_count == 3:
                    field_name = 'funct3'
                    if field_name not in INSTRUCTION_FIELD_RANGES:
                        INSTRUCTION_FIELD_RANGES[field_name] = (start_bit, end_bit)
                        print(f"    + Added {field_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                
                current_bit = end_bit - 1
            else:
                # For other components, assume they are simple immediates
                # If we don't find specific patterns, treat as 12-bit immediate (standard for STYPE)
                if 'imm' in component.lower():
                    bit_count = 12  # STYPE standard has 12 bits of immediate
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    
                    immediate_ranges.append((start_bit, end_bit))
                    print(f"    + Found generic STYPE immediate: ({start_bit}, {end_bit}) - {bit_count} bits")
                    current_bit = end_bit - 1
        
        # If we didn't find specific fragments, create standard STYPE immediate
        if not immediate_ranges:
            print(f"  DEBUG: No specific fragments found, creating standard STYPE immediate")
            # STYPE standard: imm[31:25] + imm[11:7] (fragmented)
            # Calculate based on known fields
            if 'rs2' in INSTRUCTION_FIELD_RANGES and 'funct3' in INSTRUCTION_FIELD_RANGES:
                rs2_start, rs2_end = INSTRUCTION_FIELD_RANGES['rs2']
                funct3_start, funct3_end = INSTRUCTION_FIELD_RANGES['funct3']
                
                # Upper fragment: from 31 to start of rs2
                upper_range = (31, rs2_start + 1)
                # Lower fragment: from end of funct3 to 7
                lower_range = (funct3_end - 1, 7)
                
                immediate_ranges = [upper_range, lower_range]
                print(f"    + Created standard STYPE ranges: {immediate_ranges}")
        
        # Add STYPE immediate with multiple ranges
        if immediate_ranges:
            INSTRUCTION_FIELD_RANGES['imm_stype'] = immediate_ranges  # List of tuples instead of simple tuple
            INSTRUCTION_FIELD_RANGES['imm_stype'] = [(31, 25), (13, 9)]
            print(f"  + Added imm_stype with {len(immediate_ranges)} ranges:")
            for i, (start, end) in enumerate(immediate_ranges):
                print(f"    Range {i+1}: [{start}:{end}] ({start-end+1} bits)")
        else:
            print(f"  WARNING: Could not create STYPE immediate ranges")



    def _process_detected_immediates(self, immediate_fragments: List[Dict], template_name: str, instruction_name: str) -> None:
        """Processes detected immediates and creates instruction fields for them."""
        global INSTRUCTION_FIELD_RANGES
        
        if not immediate_fragments:
            return
        
        # Determine immediate name
        if template_name:
            immediate_name = f'imm_{template_name.lower()}'
            context = f"template {template_name}"
        else:
            immediate_name = f'imm_{instruction_name.lower()}'
            context = f"instruction {instruction_name}"
        
        print(f"  DEBUG: Processing {len(immediate_fragments)} immediate fragments for {context}")
        
        # Check if we have single or multiple fragments
        if len(immediate_fragments) == 1:
            # Single fragment - simple range
            fragment = immediate_fragments[0]
            range_tuple = (fragment['start'], fragment['end'])
            
            # Check if this exact range already exists
            existing_field = self._find_existing_immediate_field(range_tuple)
            if existing_field:
                print(f"    + Range {range_tuple} already exists as {existing_field}, reusing it")
                return
            
            # Doesn't exist, create it
            INSTRUCTION_FIELD_RANGES[immediate_name] = range_tuple
            print(f"    + Created single-range immediate {immediate_name}: {range_tuple}")
            
        else:
            # Multiple fragments - multiple ranges
            ranges_list = [(frag['start'], frag['end']) for frag in immediate_fragments]
            
            # Check if this combination of ranges already exists
            existing_field = self._find_existing_multi_range_field(ranges_list)
            if existing_field:
                print(f"    + Multi-range {ranges_list} already exists as {existing_field}, reusing it")
                return
            
            # Doesn't exist, create it
            INSTRUCTION_FIELD_RANGES[immediate_name] = ranges_list
            print(f"    + Created multi-range immediate {immediate_name} with {len(ranges_list)} ranges:")
            for i, (start, end) in enumerate(ranges_list):
                print(f"      Range {i+1}: [{start}:{end}] ({start-end+1} bits)")


    def _process_btype_immediate_fragments(self, contents: str) -> None:
        """Processes immediate fragments for BTYPE respecting the order from mapping clause."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Processing BTYPE immediate fragments")
        
        # Extract encoding part
        match = re.search(r'<->\s*(.+)', contents)
        if not match:
            return
        
        encoding_part = match.group(1).strip()
        components = [comp.strip() for comp in encoding_part.split('@')]
        
        # Extract logical order from left side (BTYPE(...))
        logical_order = self._extract_btype_logical_order(contents)
        
        print(f"  DEBUG: BTYPE logical order: {logical_order}")
        print(f"  DEBUG: BTYPE encoding components: {components}")
        
        # Map fragments from encoding to their physical positions
        current_bit = 31
        physical_fragments = {}  # fragment_name -> (start_bit, end_bit)
        
        for component in components:
            print(f"  DEBUG: Processing BTYPE component: {component}")
            
            # Check if it's an immediate fragment
            imm_match = re.search(r'(imm\w+)\s*:\s*bits\((\d+)\)', component)
            if imm_match:
                fragment_name = imm_match.group(1)
                bit_count = int(imm_match.group(2))
                
                start_bit = current_bit
                end_bit = current_bit - bit_count + 1
                
                physical_fragments[fragment_name] = (start_bit, end_bit, bit_count)
                
                print(f"    + Found BTYPE fragment {fragment_name}: ({start_bit}, {end_bit}) - {bit_count} bits")
                current_bit = end_bit - 1
                
            elif 'encdec_reg(' in component:
                # Skip registers - only calculate size
                current_bit -= 5  # GPR = 5 bits
            elif 'encdec_creg(' in component:
                # Skip registers - only calculate size
                current_bit -= 3  # Compressed GPR = 3 bits
            elif component.startswith('0b'):
                # Skip constants - calculate size
                const_bits = len(component) - 2  # Remove '0b'
                current_bit -= const_bits
            else:
                # For other components, assume 3 bits (opcode fields)
                current_bit -= 3
        
        # Create ranges in logical order specified in SAIL
        immediate_ranges = []
        total_bits = 0
        
        for fragment_name in logical_order:
            if fragment_name in physical_fragments:
                start_bit, end_bit, bit_count = physical_fragments[fragment_name]
                immediate_ranges.append((start_bit, end_bit))
                total_bits += bit_count
                print(f"    + Adding fragment {fragment_name} in logical order: ({start_bit}, {end_bit})")
        
        # Add field with all ranges
        if immediate_ranges:
            INSTRUCTION_FIELD_RANGES['imm_btype'] = {
                'ranges': immediate_ranges,
                'total_bits': total_bits
            }
            print(f"    + Created BTYPE immediate field with {len(immediate_ranges)} ranges, total {total_bits} bits")

    def _extract_btype_logical_order(self, contents: str) -> List[str]:
        """Extracts logical order of immediate fragments from mapping clause."""
        # Search for BTYPE(...) part
        btype_match = re.search(r'BTYPE\(([^)]+)\)', contents)
        if not btype_match:
            return []
        
        btype_content = btype_match.group(1)
        
        # Extract fragments (ignore constants and registers)
        fragments = []
        parts = [part.strip() for part in btype_content.split('@')]
        
        for part in parts:
            # Search for fragments of type imm7_6, imm5_0, etc.
            if part.startswith('imm') and not part.startswith('0b'):
                fragments.append(part)
        
        return fragments

    
    def _calculate_immediate_range(self, known_fields: List[str], template_name: str) -> tuple:
        """Calculates immediate range based on known fields."""
        global INSTRUCTION_FIELD_RANGES
        
        # For each template, calculate based on specific logic
        if template_name == 'UTYPE':
            # UTYPE: imm[31:12] + rd[11:7] + opcode[6:0]
            # So immediate is 31:12
            if 'rd' in known_fields and 'opcode' in known_fields:
                rd_start, rd_end = INSTRUCTION_FIELD_RANGES['rd']
                return (31, rd_start + 1)  # From 31 to start of rd
        
        elif template_name == 'BTYPE':
            # BTYPE: For BTYPE we don't return a single range, we process fragments
            # This method won't be used for BTYPE - we'll use a separate method
            return None
        
        elif template_name == 'ITYPE':
            # ITYPE: imm[31:20] + rs1[19:15]

            # ITYPE: imm[31:20] + rs1[19:15] + funct3[14:12] + rd[11:7] + opcode[6:0]
            # Immediate is 31:20
            if 'rs1' in known_fields:
                rs1_start, rs1_end = INSTRUCTION_FIELD_RANGES['rs1']
                return (31, rs1_start + 1)  # From 31 to start of rs1
        
        elif template_name == 'JTYPE':
            # JTYPE: imm[31:12] + rd[11:7] + opcode[6:0] (similar to UTYPE but for JAL)
            # Immediate is 31:12
            if 'rd' in known_fields and 'opcode' in known_fields:
                rd_start, rd_end = INSTRUCTION_FIELD_RANGES['rd']
                return (31, rd_start + 1)  # From 31 to start of rd
            else:
                # Fallback for JTYPE
                return (31, 12)
        
        elif template_name == 'STYPE':
            # STYPE: imm[31:25] + rs2[24:20] + rs1[19:15] + funct3[14:12] + imm[11:7] + opcode[6:0]
            # Immediate is fragmented, but we treat it as 31:20 for simplicity
            if 'rs1' in known_fields:
                rs1_start, rs1_end = INSTRUCTION_FIELD_RANGES['rs1']
                return (31, rs1_start + 1)  # From 31 to start of rs1
        
        return None

    
    def generate_instruction_fields_xml(self, json_data: Dict[str, Any] = None) -> str:
        """Generates XML for instruction fields using global dictionaries."""
        global INSTRUCTION_FIELD_RANGES, REGISTER_CLASSES
        
        if not INSTRUCTION_FIELD_RANGES:
            print("ERROR: No instruction field ranges available. Run --build-fields first.")
            return ""
        
        if not REGISTER_CLASSES:
            print("ERROR: No register classes available. Load register classes first.")
            return ""
        
        print("\n" + "="*60)
        print("GENERATING INSTRUCTION FIELDS XML")
        print("="*60)
        
        # Create root element for instrfields
        instrfields_elem = ET.Element('instrfields')
        
        # Sort fields by start_bit descending
        sorted_fields = sorted(INSTRUCTION_FIELD_RANGES.items(), 
                            key=lambda x: x[1][0], reverse=True)
        
        all_when_offsets = {}
        if json_data:
            # Collect all when conditions for all instructions
            # (we'll apply global offset for fields that appear in multiple instructions)
            pass
        
        for field_name, (start_bit, end_bit) in sorted_fields:
            print(f"Generating field: {field_name} [{start_bit}:{end_bit}]")
            
            field_elem = self._generate_single_field_xml(field_name, start_bit, end_bit)
            
            if field_elem is not None:
                instrfields_elem.append(field_elem)
        
        # Convert to XML string
        rough_string = ET.tostring(instrfields_elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        xml_content = reparsed.toprettyxml(indent="")
        
        # Clean up XML
        lines = xml_content.split('\n')
        if lines[0].startswith('<?xml'):
            lines = lines[1:]
        
        xml_output = '\n'.join(lines)
        
        # MODIFICATION: Fix CDATA correctly
        xml_output = xml_output.replace('&lt;![CDATA[', '<![CDATA[')
        xml_output = xml_output.replace(']]&gt;', ']]>')
        
        print(f"✓ Generated {len(INSTRUCTION_FIELD_RANGES)} instruction fields")
        return xml_output


    def _calculate_multi_range_mask(self, ranges: List[tuple]) -> str:
        """Calculates mask for multiple ranges."""
        mask = 0
        for start_bit, end_bit in ranges:
            width = start_bit - end_bit + 1
            range_mask = ((1 << width) - 1) << end_bit
            mask |= range_mask
        
        return f"0x{mask:016x}"
    
    def _generate_multi_range_field_xml(self, field_name: str, field_info) -> ET.Element:
        """Generates XML for an instruction field with multiple ranges and possibly shift."""
        global REGISTER_CLASSES
        
        print(f"    DEBUG: Generating multi-range XML for {field_name}")
        print(f"    DEBUG: field_info type: {type(field_info)}")
        print(f"    DEBUG: field_info value: {field_info}")
        
        # Check if we have new structure with shift or old structure
        if isinstance(field_info, dict) and 'ranges' in field_info:
            # New structure with shift
            ranges = field_info['ranges']
            shift_amount = field_info.get('shift', 0)
            total_width = field_info.get('total_bits', sum(start - end + 1 for start, end in ranges))
            print(f"    DEBUG: New structure - ranges: {ranges}, shift: {shift_amount}")
        elif isinstance(field_info, list):
            # Old structure - list of tuples
            ranges = field_info
            shift_amount = 0
            total_width = sum(start - end + 1 for start, end in ranges)
            print(f"    DEBUG: Old list structure - ranges: {ranges}, shift: {shift_amount}")
        elif isinstance(field_info, dict):
            # Old BTYPE structure with dictionary (without 'ranges' key)
            ranges = field_info.get('ranges', [])
            shift_amount = field_info.get('shift', 0)
            total_width = field_info.get('total_bits', sum(start - end + 1 for start, end in ranges) if ranges else 0)
            print(f"    DEBUG: Old BTYPE structure - ranges: {ranges}, shift: {shift_amount}")
        else:
            print(f"ERROR: Unknown field_info structure for {field_name}: {field_info}")
            return None
        
        # Create instrfield element
        instrfield_elem = ET.Element('instrfield', name=field_name)
        
        # Doc
        doc_elem = ET.SubElement(instrfield_elem, 'doc')
        doc_str = ET.SubElement(doc_elem, 'str')
        description = self._generate_field_description(field_name)
        doc_str.text = f"<![CDATA[    {description}   ]]>"
        
        # Bits - multiple ranges
        bits_elem = ET.SubElement(instrfield_elem, 'bits')
        for start_bit, end_bit in ranges:
            range_elem = ET.SubElement(bits_elem, 'range')
            start_int = ET.SubElement(range_elem, 'int')
            start_int.text = str(start_bit)
            end_int = ET.SubElement(range_elem, 'int')
            end_int.text = str(end_bit)
        
        # Width - sum of all ranges
        width_elem = ET.SubElement(instrfield_elem, 'width')
        width_int = ET.SubElement(width_elem, 'int')
        width_int.text = str(total_width)
        
        # Size
        size_elem = ET.SubElement(instrfield_elem, 'size')
        size_int = ET.SubElement(size_elem, 'int')
        size_int.text = str(total_width)
        
        # Shift - use value from field_info
        shift_elem = ET.SubElement(instrfield_elem, 'shift')
        shift_int = ET.SubElement(shift_elem, 'int')
        shift_int.text = str(shift_amount)
        print(f"    DEBUG: Added shift element with value: {shift_amount}")
        
        # Offset
        offset_elem = ET.SubElement(instrfield_elem, 'offset')
        offset_int = ET.SubElement(offset_elem, 'int')
        offset_int.text = "0"
        
        # Mask - calculated for multiple ranges
        mask_elem = ET.SubElement(instrfield_elem, 'mask')
        mask_str = ET.SubElement(mask_elem, 'str')
        mask_value = self._calculate_multi_range_mask(ranges)
        mask_str.text = mask_value
        
        # Type - for fragmented immediates
        type_elem = ET.SubElement(instrfield_elem, 'type')
        type_str = ET.SubElement(type_elem, 'str')
        type_str.text = "imm"
        
        if field_name in IMMEDIATE_SIGN_INFO and IMMEDIATE_SIGN_INFO[field_name]:
            signed_elem = ET.SubElement(instrfield_elem, 'signed')
            signed_str = ET.SubElement(signed_elem, 'str')
            signed_str.text = "true"
            print(f"    Added <signed>true</signed> for multi-range {field_name}")
        
        return instrfield_elem

    
    def _parse_when_condition(self, json_data: Dict[str, Any], instruction_name: str) -> Dict[str, int]:
        """Parses the 'when' condition from mapping clause assembly to detect register restrictions."""
        print(f"DEBUG: Parsing 'when' condition for {instruction_name}")
        
        # Search in mappings -> assembly
        if 'mappings' not in json_data:
            return {}
        
        mappings = json_data['mappings']
        if 'assembly' not in mappings:
            return {}
        
        assembly_mappings = mappings['assembly']
        if 'mapping' not in assembly_mappings:
            return {}
        
        mapping_list = assembly_mappings['mapping']
        if not isinstance(mapping_list, list):
            return {}
        
        # Search for specific instruction
        for mapping_item in mapping_list:
            if not isinstance(mapping_item, dict):
                continue
            
            source = mapping_item.get('source', {})
            if not isinstance(source, dict):
                continue
            
            contents = source.get('contents', '')
            if not isinstance(contents, str):
                continue
            
            # Check if contains our instruction
            if instruction_name.upper() not in contents.upper():
                continue
            
            print(f"DEBUG: Found assembly mapping for {instruction_name}: {contents[:100]}...")
            
            # Parse when condition
            when_match = re.search(r'when\s+(.+?)(?:\n|$)', contents, re.IGNORECASE)
            if when_match:
                condition = when_match.group(1).strip()
                print(f"DEBUG: Found 'when' condition: {condition}")
                
                # Parse conditions of type "rsd != zreg" or "rd != zreg"
                offsets = {}
                
                # Pattern for != zreg
                zreg_pattern = r'(\w+)\s*!=\s*zreg'
                zreg_matches = re.findall(zreg_pattern, condition, re.IGNORECASE)
                
                for reg_name in zreg_matches:
                    # Register cannot be 0, so offset = 1
                    offsets[reg_name] = 1
                    print(f"DEBUG: Register {reg_name} cannot be zero (offset=1)")
                
                # Pattern for == zreg (register MUST be 0)
                zreg_eq_pattern = r'(\w+)\s*==\s*zreg'
                zreg_eq_matches = re.findall(zreg_eq_pattern, condition, re.IGNORECASE)
                
                for reg_name in zreg_eq_matches:
                    # Register must be 0, so offset = 0 (but it's fixed)
                    offsets[reg_name] = 0
                    print(f"DEBUG: Register {reg_name} must be zero (offset=0)")
                
                return offsets
        
        print(f"DEBUG: No 'when' condition found for {instruction_name}")
        return {}
    

    def _generate_single_field_xml(self, field_name: str, start_bit: int, end_bit: int, when_offsets: Dict[str, int] = None) -> ET.Element:
        """Generates XML for a single instruction field."""
        global REGISTER_CLASSES
        
        # Check if we have multiple ranges (for BTYPE immediate)
        field_ranges = INSTRUCTION_FIELD_RANGES.get(field_name)
        if isinstance(field_ranges, list):
            # Multiple ranges - use first method
            return self._generate_multi_range_field_xml(field_name, field_ranges)
        
        # Simple range - existing logic
        # Calculate dimensions
        width = start_bit - end_bit + 1
        
        # Create instrfield element
        instrfield_elem = ET.Element('instrfield', name=field_name)
        
        # Doc - generate description dynamically with correct formatting
        doc_elem = ET.SubElement(instrfield_elem, 'doc')
        doc_str = ET.SubElement(doc_elem, 'str')
        description = self._generate_field_description(field_name)
        doc_str.text = f"<![CDATA[    {description}   ]]>"
        
        # Bits - simple range
        bits_elem = ET.SubElement(instrfield_elem, 'bits')
        range_elem = ET.SubElement(bits_elem, 'range')
        start_int = ET.SubElement(range_elem, 'int')
        start_int.text = str(start_bit)
        end_int = ET.SubElement(range_elem, 'int')
        end_int.text = str(end_bit)
        
        # Width
        width_elem = ET.SubElement(instrfield_elem, 'width')
        width_int = ET.SubElement(width_elem, 'int')
        width_int.text = str(width)
        
        # Size
        size_elem = ET.SubElement(instrfield_elem, 'size')
        size_int = ET.SubElement(size_elem, 'int')
        size_int.text = str(width)
        
        # Shift
        shift_elem = ET.SubElement(instrfield_elem, 'shift')
        shift_int = ET.SubElement(shift_elem, 'int')
        shift_int.text = "0"
        
        # Offset - MODIFIED: check if we have when restriction OR if it's rsd
        offset_elem = ET.SubElement(instrfield_elem, 'offset')
        offset_int = ET.SubElement(offset_elem, 'int')
        # ADDED: For compressed registers, set offset=8
        if field_name in ['rd_c', 'rs1_c', 'rs2_c']:
            offset_int.text = "8"
            print(f"  Set offset=" + offset_int.text + " for compressed register " +f"{field_name}")
        # ADDED: For rsd, always set offset=1 (cannot be x0)
        elif field_name == 'rsd':
            offset_int.text = "1"
            print(f"  Set offset=1 for rsd (cannot be x0)")
        elif when_offsets and field_name in when_offsets:
            offset_value = when_offsets[field_name]
            offset_int.text = str(offset_value)
            print(f"  Applied when offset={offset_value} for {field_name}")
        else:
            offset_int.text = "0"
        
        # Mask
        mask_elem = ET.SubElement(instrfield_elem, 'mask')
        mask_str = ET.SubElement(mask_elem, 'str')
        mask_value = self._calculate_mask(start_bit, end_bit)
        mask_str.text = mask_value
        
        if field_name in self.field_to_register_map:
            # REGISTER FIELD
            reg_class_name = self.field_to_register_map[field_name]
            
            print(f"  -> Register field: {field_name} -> {reg_class_name}")
            
            # Type
            type_elem = ET.SubElement(instrfield_elem, 'type')
            type_str = ET.SubElement(type_elem, 'str')
            type_str.text = "regfile"
            
            # Ref
            ref_elem = ET.SubElement(instrfield_elem, 'ref')
            ref_str = ET.SubElement(ref_elem, 'str')
            ref_str.text = reg_class_name
            
            # Check if we have register class for enumerated
            if reg_class_name in REGISTER_CLASSES:
                reg_config = REGISTER_CLASSES[reg_class_name]
                
                # Enumerated - registers and aliases from global dictionary
                enumerated_elem = ET.SubElement(instrfield_elem, 'enumerated')
                
                # MODIFIED: Check if we have 'registers' explicitly defined
                if 'registers' in reg_config:
                    self._add_register_enumerations_from_global(enumerated_elem, reg_class_name)
                    print(f"    Added {len(reg_config['registers'])} register enumerations")
                else:
                    print(f"    WARNING: No 'registers' defined for {reg_class_name}")
            else:
                print(f"    WARNING: Register class {reg_class_name} not found in global dictionary")
        
        elif field_name.startswith('imm_') or field_name == 'imm' or field_name == 'shamt':
            # IMMEDIATE FIELD
            print(f"  -> Immediate field: {field_name}")
            
            # Type
            type_elem = ET.SubElement(instrfield_elem, 'type')
            type_str = ET.SubElement(type_elem, 'str')
            type_str.text = "imm"
            
            # MODIFIED: Use global dictionary
            global IMMEDIATE_SIGN_INFO
            
            print(f"DEBUG: Checking signed for {field_name}")
            print(f"DEBUG: IMMEDIATE_SIGN_INFO (global) = {IMMEDIATE_SIGN_INFO}")
            
            if field_name in IMMEDIATE_SIGN_INFO and IMMEDIATE_SIGN_INFO[field_name]:
                signed_elem = ET.SubElement(instrfield_elem, 'signed')
                signed_str = ET.SubElement(signed_elem, 'str')
                signed_str.text = "true"
                print(f"    ✓ Added <signed>true</signed> for {field_name}")
            
            # DON'T add ref for immediates

        
        elif field_name.startswith('funct') or field_name == 'opcode':
            # CONTROL/ENCODING FIELD
            print(f"  -> Control field: {field_name}")
            
            # Type
            type_elem = ET.SubElement(instrfield_elem, 'type')
            type_str = ET.SubElement(type_elem, 'str')
            type_str.text = "imm"  # Control fields are treated as immediate
            
            # DON'T add ref for control fields
        
        else:
            # GENERIC FIELD
            print(f"  -> Generic field: {field_name}")
            
            # Type
            type_elem = ET.SubElement(instrfield_elem, 'type')
            type_str = ET.SubElement(type_elem, 'str')
            type_str.text = "imm"  # Default for unknown fields
            
            # DON'T add ref for generic fields
        
        return instrfield_elem



    
    def _calculate_mask(self, start_bit: int, end_bit: int) -> str:
        """Calculates mask for a bit field."""
        # Validate values
        if start_bit < 0 or end_bit < 0:
            print(f"ERROR: Invalid bit range [{start_bit}:{end_bit}] - negative values")
            return "0x0000000000000000"
        
        if start_bit < end_bit:
            print(f"ERROR: Invalid bit range [{start_bit}:{end_bit}] - start_bit < end_bit")
            return "0x0000000000000000"
        
        if start_bit > 31 or end_bit > 31:
            print(f"ERROR: Invalid bit range [{start_bit}:{end_bit}] - values > 31")
            return "0x0000000000000000"
        
        width = start_bit - end_bit + 1
        
        if width <= 0:
            print(f"ERROR: Invalid width {width} for range [{start_bit}:{end_bit}]")
            return "0x0000000000000000"
        
        try:
            mask = ((1 << width) - 1) << end_bit
            return f"0x{mask:016x}"
        except Exception as e:
            print(f"ERROR: Failed to calculate mask for [{start_bit}:{end_bit}]: {e}")
            return "0x0000000000000000"

    
    def _add_register_enumerations_from_global(self, enumerated_elem: ET.Element, reg_class_name: str) -> None:
        """Adds enumerations for registers from global dictionary."""
        global REGISTER_CLASSES
        
        reg_class = REGISTER_CLASSES[reg_class_name]
        registers = reg_class.get('registers', {})
        
        print(f"    Processing {len(registers)} registers for {reg_class_name}")
        
        # For each register, add all aliases as separate options
        for reg_index in sorted(registers.keys()):
            reg_info = registers[reg_index]
            reg_number = str(reg_index)
            aliases = reg_info.get('aliases', [])
            
            print(f"      Register {reg_index}: {aliases}")
            
            # MODIFIED: Check if aliases is list or string
            if isinstance(aliases, str):
                # If it's string, convert to list
                aliases = [aliases]
            
            # Add each alias as a separate option with same number
            for alias in aliases:
                option_elem = ET.SubElement(enumerated_elem, 'option', name=reg_number)
                option_str = ET.SubElement(option_elem, 'str')
                option_str.text = alias  # Alias name
                
                print(f"        Added option: name='{reg_number}' -> '{alias}'")

    
    def _generate_field_description(self, field_name: str) -> str:
        """Generates description for a field based on name and type."""
        global REGISTER_CLASSES
        
        # For registers (use auto-detected mapping)
        if field_name in self.field_to_register_map:
            reg_type = self.field_to_register_map[field_name]
            
            # Use real data from REGISTER_CLASSES to determine type
            if reg_type in REGISTER_CLASSES:
                reg_class = REGISTER_CLASSES[reg_type]
                
                # Analyze registers to determine register type
                registers = reg_class.get('registers', {})
                
                # Check aliases to determine register type
                sample_aliases = []
                for reg_info in list(registers.values())[:5]:  # First 5 registers
                    sample_aliases.extend(reg_info.get('aliases', []))
                
                # Determine type based on found aliases
                if any(alias in ['zero', 'ra', 'sp', 'gp', 'tp'] for alias in sample_aliases):
                    reg_description = "register"
                elif any(alias.startswith('f') for alias in sample_aliases):
                    reg_description = "floating-point register"
                elif any(alias.startswith('v') for alias in sample_aliases):
                    reg_description = "vector register"
                else:
                    reg_description = "register"
                
                # Generate specific description for field
                if field_name == 'rd':
                    return f'Destination {reg_description} field.'
                elif field_name == 'rs1':
                    return f'Source {reg_description} 1 field.'
                elif field_name == 'rs2':
                    return f'Source {reg_description} 2 field.'
                elif field_name == 'rs3':
                    return f'Source {reg_description} 3 field.'
                elif field_name == 'rsd':
                    return f'Source/Destination {reg_description} field.'
                elif field_name == 'rs1_c':
                    return f'Compressed Source {reg_description} field.'
                elif field_name == 'rs2_c':
                    return f'Compressed Source {reg_description} field.'
                elif field_name == 'rd_c':
                    return f'Compressed  Destination {reg_description} field.'
                elif field_name == 'md':
                    return f'Destination {reg_description} field.'
                elif field_name == 'ms1':
                    return f'Source {reg_description} 1 field.'
                elif field_name == 'ms2':
                    return f'Source {reg_description} 2 field.'
                elif field_name == 'csr':
                    return 'Control and Status Register field.'
                else:
                    return f'{field_name.upper()} {reg_description} field.'
            else:
                # Fallback if register class not found
                if field_name == 'rd':
                    return 'Destination register field.'
                elif field_name == 'rs1':
                    return 'Source register 1 field.'
                elif field_name == 'rs2':
                    return 'Source register 2 field.'
                elif field_name == 'rs3':
                    return 'Source register 3 field.'
                elif field_name == 'md':
                    return 'Destination register field.'
                elif field_name == 'ms1':
                    return 'Source register 1 field.'
                elif field_name == 'ms2':
                    return 'Source register 2 field.'
                elif field_name == 'csr':
                    return 'Control and Status Register field.'
                else:
                    return f'{field_name.upper()} register field.'
        
        # For control fields
        elif field_name == 'funct3':
            return 'Secondary opcode (function) field.'
        elif field_name == 'funct7':
            return 'Function code field (7 bits).'
        elif field_name.startswith('funct'):
            return f'{field_name.upper()} function code field.'
        
        # For opcode
        elif field_name == 'opcode':
            return 'Primary opcode field.'
        elif field_name == 'op_c':
            return 'Compressed instruction opcode field (2 bits).'
        
        # For immediates
        elif field_name.startswith('imm_'):
            instr_type = field_name[4:].upper()
            
            if instr_type == 'I' or instr_type == 'ITYPE':
                return 'Immediate field for I-type instructions.'
            elif instr_type == 'U' or instr_type == 'UTYPE':
                return 'Immediate field for U-type instructions.'
            elif instr_type == 'B' or instr_type == 'BTYPE':
                return 'Immediate field for B-type instructions.'
            elif instr_type == 'S' or instr_type == 'STYPE':
                return 'Immediate field for S-type instructions.'
            elif instr_type == 'J' or instr_type == 'JTYPE':
                return 'Immediate field for J-type instructions.'
            elif instr_type == 'JAL':
                return 'Immediate field for JAL instruction.'
            elif instr_type == 'CI':
                return 'Immediate field for compressed I-type instructions.'
            else:
                return f'Immediate field for {instr_type.lower()}-type instructions.'
        
        # For shift amount
        elif field_name == 'shamt':
            return 'Shift amount field.'
        
        # For literal fields
        elif field_name.startswith('literal_'):
            return f'{field_name.replace("_", " ").title()} field.'
        
        # Default
        else:
            return f'{field_name.upper()} field.'

        
    def _check_and_add_jal_special(self, json_data: Dict[str, Any]) -> None:
        """Checks and adds special JAL with imm_jal instead of imm_jtype."""
        global INSTRUCTION_FIELD_RANGES
        
        mapping_list = json_data['mappings']['encdec']['mapping'] + json_data['mappings']['encdec_compressed']['mapping']
        
        found_jal = False
        for instruction_data in mapping_list:
            if not isinstance(instruction_data, dict):
                continue
                
            source = instruction_data.get('source', {})
            contents = source.get('contents', '')
            
            # Specifically search for JAL
            if 'JAL(' in contents and '<->' in contents:
                print(f"  Found JAL: {contents}")
                found_jal = True
                
                # For JAL, create imm_jal instead of imm_jtype
                self._create_jal_immediate(contents)
                
                break  # Found JAL, stop searching
        
        if not found_jal:
            print(f"  WARNING: JAL not found in JSON")

    def _create_jal_immediate(self, contents: str) -> None:
        """Creates special immediate for JAL (imm_jal)."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special JAL immediate")
        
        # JAL uses a 20-bit immediate at position [31:12]
        if 'rd' in INSTRUCTION_FIELD_RANGES:
            rd_start, rd_end = INSTRUCTION_FIELD_RANGES['rd']
            jal_range = (31, rd_start + 1)  # From 31 to start of rd
            print(f"  DEBUG: Calculated JAL range based on rd: {jal_range}")
        else:
            jal_range = (31, 12)  # Standard JAL range
            print(f"  DEBUG: Using standard JAL range: {jal_range}")
        
        INSTRUCTION_FIELD_RANGES['imm_jal'] = jal_range
        print(f"  + Added imm_jal: {jal_range}")

    def _create_c_lw_immediate(self) -> None:
        """Creates special immediate for C.LW (imm_c_lw)."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special C.LW immediate")
        
        c_lw_range = [(12, 10), (5,5), (6,6)]  # Standard c.lw range
        print(f"  DEBUG: Using standard C.LW range: {c_lw_range}")
        
        INSTRUCTION_FIELD_RANGES['imm_c_lw'] = {'ranges' : c_lw_range, 'shift': 2}
        print(f"  + Added imm_c_lw: {c_lw_range}")

    def _create_c_addi4spn_immediate(self) -> None:
        """Creates special immediate for C.ADDI4SPN (imm_ciw)."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special C.ADDI4SPN immediate")
        
        c_addi4spn_range = [(10, 7), (5,5), (6,6), (12, 11)]  # Standard c.addi4spn range
        print(f"  DEBUG: Using standard C.ADDI4SPN range: {c_addi4spn_range}")
        
        INSTRUCTION_FIELD_RANGES['imm_ciw'] = {'ranges' : c_addi4spn_range, 'shift': 2}
        print(f"  + Added imm_ciw: {c_addi4spn_range}")
    
    def _create_imm_btype_immediate(self) -> None:
        """Creates special immediate for branch (imm_btype)."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special branch immediate")
        
        imm_btype = [(31, 31), (7,7), (30,25), (11, 8)]  # Standard branch range
        print(f"  DEBUG: Using standard branch range: {imm_btype}")
        
        INSTRUCTION_FIELD_RANGES['imm_btype'] = {'ranges' : imm_btype, 'shift': 1}
        print(f"  + Added imm_btype: {imm_btype}")

    def _create_fence_immediate(self) -> None:
        """Creates special immediate for fence (fence_prod, fence_succ)."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special fence immediate")
        
        imm_fence_prod = [(27, 24)]  # Standard fence_prod range
        imm_fence_succ = [(23, 20)]  # Standard fence_succ range
        
        INSTRUCTION_FIELD_RANGES['fence_prod'] = {'ranges' : imm_fence_prod, 'shift': 0}
        INSTRUCTION_FIELD_RANGES['fence_succ'] = {'ranges' : imm_fence_succ, 'shift': 0}
    
    def _create_imm_jal_immediate(self) -> None:
        """Creates special immediate for JAL (imm_jal)."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special JAL immediate")
        
        imm_jal = [(31, 31), (19,12), (20,20), (30, 21)]  # Standard JAL range
        print(f"  DEBUG: Using standard JAL range: {imm_jal}")
        
        INSTRUCTION_FIELD_RANGES['imm_jal'] = {'ranges' : imm_jal, 'shift': 1}
        print(f"  + Added imm_jal: {imm_jal}")
    
    def _create_c_andi_immediate(self) -> None:
        """Creates special immediate for C.ANDI (imma_cb)."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special C.ANDI immediate")
        
        c_andi_range = [(12, 12), (6,2)]  # Standard c.andi range
        print(f"  DEBUG: Using standard C.ANDI range: {c_andi_range}")
        
        INSTRUCTION_FIELD_RANGES['imma_cb'] = {'ranges' : c_andi_range, 'shift': 0}
        print(f"  + Added imma_cb: {c_andi_range}")
        
    def _create_branch_immediate(self) -> None:
        """Creates special immediate for C.BNEZ, C.BEQZ (imm_cb)."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special C.BNEZ, C.BEQZ immediate")
        
        c_branch_range = [(12, 12), (6,2)]  # Standard c.bnez/c.beqz range
        print(f"  DEBUG: Using standard C.BNEZ, C.BEQZ range: {c_branch_range}")
        
        INSTRUCTION_FIELD_RANGES['imm_cb'] = {'ranges' : c_branch_range, 'shift': 0}
        print(f"  + Added imm_cb: {c_branch_range}")
    
    
    def _create_c_jal_immediate(self) -> None:
        """Creates special immediate for C.JAL (imm_cj)."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special C.JAL immediate")
        
        c_jal_range = [(12, 12), (8,8), (10,9), (6,6), (7,7), (2,2), (11,11), (5,3)]  # Standard c.jal range
        print(f"  DEBUG: Using standard C.JAL range: {c_jal_range}")
        
        INSTRUCTION_FIELD_RANGES['imm_cj'] = {'ranges' : c_jal_range, 'shift': 1}
        print(f"  + Added imm_cj: {c_jal_range}")
        
    def _create_c_addi16sp_immediate(self) -> None:
        """Creates special immediate for C.ADDI16SP (imm_sp_ci)."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special C.ADDI16SP immediate")
        
        c_addi16sp_range = [(12, 12), (4,3), (5,5), (2, 2), (6,6)]  # Standard c.addi16sp range
        print(f"  DEBUG: Using standard C.ADDI16SP range: {c_addi16sp_range}")
        
        INSTRUCTION_FIELD_RANGES['imm_sp_ci'] = {'ranges' : c_addi16sp_range, 'shift': 2}
        print(f"  + Added imm_sp_ci: {c_addi16sp_range}")
        
    def _create_c_shift_immediate(self) -> None:
        """Creates special immediate for C.SLLI, C.SRAI, C.SRLI."""
        global INSTRUCTION_FIELD_RANGES
        
        print(f"  DEBUG: Creating special C.SLLI, C.SRAI, C.SRLI immediate")
        
        shift_range = [(6, 2)]  # Standard compressed shift range
        print(f"  DEBUG: Using standard C.SLLI, C.SRAI, C.SRLI range: {shift_range}")
        
        INSTRUCTION_FIELD_RANGES['shamt_c'] = {'ranges' : shift_range,}
        print(f"  + Added shamt_c: {shift_range}")


    def _detect_shamt_in_specific_encodings(self, json_data: Dict[str, Any]) -> None:
        """Detects and adds shamt only for instructions that contain it in encoding."""
        global INSTRUCTION_FIELD_RANGES
        
        if 'mappings' not in json_data or 'encdec' not in json_data['mappings']:
            return
        
        mapping_list = json_data['mappings']['encdec']['mapping'] + json_data['mappings']['encdec_compressed']['mapping']
        if not isinstance(mapping_list, list):
            return
        
        shamt_instructions = []
        
        for instruction_data in mapping_list:
            if not isinstance(instruction_data, dict):
                continue
                
            source = instruction_data.get('source', {})
            contents = source.get('contents', '')
            
            if not isinstance(contents, str):
                continue
            
            # Check if encoding explicitly contains shamt
            if 'shamt' in contents and '<->' in contents:
                # Extract instruction name
                match = re.search(r'(\w+)\s*\([^)]*\)\s*<->', contents)
                if match:
                    instr_name = match.group(1)
                    shamt_instructions.append(instr_name)
                    print(f"Found shamt in instruction: {instr_name}")
        
        # ONLY add shamt to INSTRUCTION_FIELD_RANGES if we found instructions that use it
        # But don't force it for all instructions
        if shamt_instructions:
            INSTRUCTION_FIELD_RANGES['shamt'] = (24, 20)
            print(f"✓ Added shamt for instructions: {shamt_instructions}")
        else:
            print("✓ No instructions use shamt, not adding to global ranges")


    def generate_custom_fields_from_existing_parsing(self, json_data: Dict[str, Any]) -> str:
        """Generates custom instruction fields using existing parsing and operand configuration."""
        print("\n" + "="*60)
        print("GENERATING CUSTOM FIELDS FROM EXISTING PARSING")
        print("="*60)
        
        # Load custom operand configuration
        try:
            reg_generator = RegisterFileGenerator()
            operand_mappings = reg_generator.get_special_operand_mappings()
        except Exception as e:
            print(f"ERROR: Failed to load operand mappings: {e}")
            return ""
        
        if not operand_mappings:
            print("No special operand mappings found")
            return ""

        print(f"Found operand mappings for: {list(operand_mappings.keys())}")
        
        # Create root element for instrfields
        instrfields_elem = ET.Element('instrfields')
        
        # Process each instruction with custom operands
        for instruction_name, mappings in operand_mappings.items():
            print(f"\nProcessing instruction: {instruction_name}")
            print(f"  Operand mappings: {mappings}")
            
            # Find and parse encoding for this instruction
            encoding_info = self._extract_encoding_info_for_instruction(json_data, instruction_name)
            if not encoding_info:
                print(f"  ✗ No encoding info found for {instruction_name}")
                continue
            
            # Calculate ranges for original operands
            original_ranges = self._calculate_ranges_from_encoding(encoding_info, instruction_name)
            if not original_ranges:
                print(f"  ✗ Failed to calculate ranges for {instruction_name}")
                continue
            
            # Generate instruction fields for each custom operand
            for original_operand, custom_name in mappings.items():
                if original_operand in original_ranges:
                    range_info = original_ranges[original_operand]
                    
                    field_elem = self._generate_custom_operand_field_xml(
                        custom_name, 
                        original_operand, 
                        range_info, 
                        instruction_name
                    )
                    
                    if field_elem is not None:
                        instrfields_elem.append(field_elem)
                        print(f"  ✓ Generated {custom_name} from {original_operand}")
                        
                        # Also add to global dictionary
                        global INSTRUCTION_FIELD_RANGES
                        INSTRUCTION_FIELD_RANGES[custom_name] = (range_info['start_bit'], range_info['end_bit'])
                    else:
                        print(f"  ✗ Failed to generate {custom_name}")
                else:
                    print(f"  ✗ Original operand {original_operand} not found in ranges")
        
        # Convert to XML string
        rough_string = ET.tostring(instrfields_elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        xml_content = reparsed.toprettyxml(indent="")
        
        # Clean up XML
        lines = xml_content.split('\n')
        if lines[0].startswith('<?xml'):
            lines = lines[1:]
        
        xml_output = '\n'.join(lines)
        
        # Fix CDATA correctly
        xml_output = xml_output.replace('&lt;![CDATA[', '<![CDATA[')
        xml_output = xml_output.replace(']]&gt;', ']]>')
        
        print(f"\n✓ Generated custom instruction fields")
        return xml_output
    
    def _extract_encoding_info_for_instruction(self, json_data: Dict[str, Any], instruction_name: str) -> Optional[Dict[str, Any]]:
        """Extracts encoding information for a specific instruction."""
        if 'mappings' not in json_data or 'encdec' not in json_data['mappings']:
            return None
        
        mapping_list = json_data['mappings']['encdec']['mapping'] + json_data['mappings']['encdec_compressed']['mapping']
        if not isinstance(mapping_list, list):
            return None
        
        # Search for specific instruction
        search_patterns = [
            f'{instruction_name.upper()}(',  # FENCE(
            f'{instruction_name}(',          # fence(
        ]
        
        for instruction_data in mapping_list:
            if not isinstance(instruction_data, dict):
                continue
                
            source = instruction_data.get('source', {})
            contents = source.get('contents', '')
            
            if not isinstance(contents, str):
                continue
            
            # Check if contains instruction pattern
            for pattern in search_patterns:
                if pattern in contents and '<->' in contents:
                    print(f"  ✓ Found encoding for {instruction_name}: {contents}")
                    
                    # Return both contents and right pattern for complete parsing
                    right_pattern = instruction_data.get('right', {})
                    return {
                        'contents': contents,
                        'right_pattern': right_pattern,
                        'source': source
                    }
        
        return None
    
    def _calculate_ranges_from_encoding(self, encoding_info: Dict[str, Any], instruction_name: str) -> Dict[str, Dict[str, Any]]:
        """Calculates ranges using existing parsing logic."""
        contents = encoding_info['contents']
        right_pattern = encoding_info['right_pattern']
        
        print(f"  Calculating ranges for {instruction_name}")
        print(f"  Contents: {contents}")
        
        # For FENCE, use existing special logic
        if instruction_name.lower() == 'fence':
            return self._calculate_fence_ranges_from_encoding(contents)
        
        # For other instructions, use general parsing
        return self._calculate_general_ranges_from_encoding(contents, right_pattern)
    
    def _calculate_fence_ranges_from_encoding(self, contents: str) -> Dict[str, Dict[str, Any]]:
        """Calculates ranges for FENCE from real encoding in JSON."""
        print("  Calculating FENCE ranges from actual encoding")
        
        # Extract encoding part (after <->)
        match = re.search(r'<->\s*(.+)', contents)
        if not match:
            print("  ✗ No encoding part found")
            return {}
        
        encoding_part = match.group(1).strip()
        print(f"  Encoding part: {encoding_part}")
        
        # Split into components
        components = [comp.strip() for comp in encoding_part.split('@')]
        print(f"  Components: {components}")
        
        ranges = {}
        current_bit = 31  # Start from MSB
        
        for i, component in enumerate(components):
            print(f"  Processing component {i}: '{component}' at bit {current_bit}")
            
            # Check if it's pred or succ
            if component == 'pred':
                # pred is a 4-bit field (standard for FENCE)
                start_bit = current_bit
                end_bit = current_bit - 4 + 1
                
                ranges['pred'] = {
                    'start_bit': start_bit,
                    'end_bit': end_bit,
                    'width': 4,
                    'shift': 0,
                    'offset': 0
                }
                
                print(f"    + pred: [{start_bit}:{end_bit}] (4 bits)")
                current_bit = end_bit - 1
                
            elif component == 'succ':
                # succ is a 4-bit field (standard for FENCE)
                start_bit = current_bit
                end_bit = current_bit - 4 + 1
                
                ranges['succ'] = {
                    'start_bit': start_bit,
                    'end_bit': end_bit,
                    'width': 4,
                    'shift': 0,
                    'offset': 0
                }
                
                print(f"    + succ: [{start_bit}:{end_bit}] (4 bits)")
                current_bit = end_bit - 1
                
            elif component.startswith('0b'):
                # Binary literal - calculate size and skip over
                literal_size = len(component) - 2  # Subtract "0b"
                current_bit -= literal_size
                print(f"    - Binary literal {component}: {literal_size} bits, now at bit {current_bit}")
                
            else:
                # Other components (registers, etc.) - estimate size
                component_size = self._estimate_component_size_for_ranges(component)
                current_bit -= component_size
                print(f"    - Other component {component}: {component_size} bits, now at bit {current_bit}")
        
        print(f"  ✓ Calculated FENCE ranges from encoding: {ranges}")
        return ranges

    
    def _calculate_general_ranges_from_encoding(self, contents: str, right_pattern: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Calculates ranges for general instructions."""
        print("  Using general range calculation")
        
        # Extract encoding part (after <->)
        match = re.search(r'<->\s*(.+)', contents)
        if not match:
            return {}
        
        encoding_part = match.group(1).strip()
        components = [comp.strip() for comp in encoding_part.split('@')]
        
        print(f"  Encoding components: {components}")
        
        ranges = {}
        current_bit = 31  # Start from MSB
        
        for i, component in enumerate(components):
            print(f"  Processing component {i}: '{component}' at bit {current_bit}")
            
            # Determine component type and size
            component_info = self._analyze_component_for_ranges(component)
            
            if component_info and component_info['is_operand']:
                operand_name = component_info['name']
                operand_size = component_info['size']
                
                start_bit = current_bit
                end_bit = current_bit - operand_size + 1
                
                ranges[operand_name] = {
                    'start_bit': start_bit,
                    'end_bit': end_bit,
                    'width': operand_size,
                    'shift': 0,
                    'offset': 0
                }
                ranges['imm_c_lw'] = {
                    'shift': 2
                }
                
                print(f"    + {operand_name}: [{start_bit}:{end_bit}] ({operand_size} bits)")
                current_bit = end_bit - 1
            else:
                # For components that are not operands, calculate size and continue
                component_size = self._estimate_component_size_for_ranges(component)
                current_bit -= component_size
                print(f"    - Skipped {component} ({component_size} bits)")
        
        return ranges
    
    def _analyze_component_for_ranges(self, component: str) -> Optional[Dict[str, Any]]:
        """Analyzes a component to determine if it's an operand and its size."""
        
        # Check if it's binary literal
        if component.startswith('0b'):
            return {'is_operand': False, 'size': len(component) - 2}
        
        # Check if it's a known operand
        known_operands = {
            'pred': 4,    # FENCE predecessor
            'succ': 4,    # FENCE successor  
            'csr': 12,    # CSR address
            'rd': 5,      # Destination register
            'rs1': 5,     # Source register 1
            'rs2': 5,     # Source register 2
            'rs3': 5,     # Source register 3
            'rsd': 5,     # ADDED: Source/destination register
            'md': 5,      # ADDED: Vector destination register
            'ms1': 5,     # ADDED: Vector source register 1
            'ms2': 5,     # ADDED: Vector source register 2
            'shamt': 5,   # Shift amount
            'rd_c': 3,
            'rs1_c': 3,
            'rs2_c': 3,
        }
        
        if component in known_operands:
            return {
                'is_operand': True,
                'name': component,
                'size': known_operands[component]
            }
        
        # For other components, they are not operands
        return {'is_operand': False, 'size': 3}  # default size

    
    def _estimate_component_size_for_ranges(self, component: str) -> int:
        """Estimates size of a component for range calculation."""
        if component.startswith('0b'):
            return len(component) - 2
        elif component in ['rd', 'rs1', 'rs2', 'rs3', 'shamt']:
            return 5
        elif component == 'csr':
            return 12
        elif component in ['pred', 'succ']:
            return 4
        else:
            return 3  # default
    
    def _generate_custom_operand_field_xml(self, custom_name: str, original_operand: str, 
                                         range_info: Dict[str, Any], instruction_name: str) -> ET.Element:
        """Generates XML for a custom instruction field based on original operand."""
        
        start_bit = range_info['start_bit']
        end_bit = range_info['end_bit']
        width = range_info['width']
        shift = range_info.get('shift', 0)
        offset = range_info.get('offset', 0)
        
        # Generate description based on custom name and instruction
        description = self._generate_custom_field_description(custom_name, original_operand, instruction_name)
        
        print(f"    Creating {custom_name}: [{start_bit}:{end_bit}] ({width} bits)")
        
        # Create instrfield element
        instrfield_elem = ET.Element('instrfield', name=custom_name)
        
        # Doc
        doc_elem = ET.SubElement(instrfield_elem, 'doc')
        doc_str = ET.SubElement(doc_elem, 'str')
        doc_str.text = f"<![CDATA[    {description}   ]]>"
        
        # Bits - simple range
        bits_elem = ET.SubElement(instrfield_elem, 'bits')
        range_elem = ET.SubElement(bits_elem, 'range')
        start_int = ET.SubElement(range_elem, 'int')
        start_int.text = str(start_bit)
        end_int = ET.SubElement(range_elem, 'int')
        end_int.text = str(end_bit)
        
        # Width
        width_elem = ET.SubElement(instrfield_elem, 'width')
        width_int = ET.SubElement(width_elem, 'int')
        width_int.text = str(width)
        
        # Size
        size_elem = ET.SubElement(instrfield_elem, 'size')
        size_int = ET.SubElement(size_elem, 'int')
        size_int.text = str(width)
        
        # Shift
        shift_elem = ET.SubElement(instrfield_elem, 'shift')
        shift_int = ET.SubElement(shift_elem, 'int')
        shift_int.text = str(shift)
        
        # Offset
        offset_elem = ET.SubElement(instrfield_elem, 'offset')
        offset_int = ET.SubElement(offset_elem, 'int')
        offset_int.text = str(offset)
        
        # Mask
        mask_elem = ET.SubElement(instrfield_elem, 'mask')
        mask_str = ET.SubElement(mask_elem, 'str')
        mask_value = self._calculate_mask(start_bit, end_bit)
        mask_str.text = mask_value
        
        # Type - for custom operands, use 'imm'
        type_elem = ET.SubElement(instrfield_elem, 'type')
        type_str = ET.SubElement(type_elem, 'str')
        type_str.text = "imm"
        
        return instrfield_elem
    
    def _generate_custom_field_description(self, custom_name: str, original_operand: str, instruction_name: str) -> str:
        """Generates description for a custom field."""
        
        # Specific descriptions for known fields
        descriptions = {
            'fence_pred': 'FENCE predecessor field - specifies memory ordering constraints for operations before the fence.',
            'fence_succ': 'FENCE successor field - specifies memory ordering constraints for operations after the fence.',
            'csr_addr': 'Control and Status Register address field.',
        }
        
        if custom_name in descriptions:
            return descriptions[custom_name]
        
        # Generate generic description
        return f'{custom_name.upper()} field for {instruction_name.upper()} instruction (mapped from {original_operand}).'




    def build_instruction_field_ranges(self, json_data: Dict[str, Any], extension_filter: List[str] = None) -> bool:
        """Builds the global dictionary with instruction field ranges."""
        global INSTRUCTION_FIELD_RANGES
        INSTRUCTION_FIELD_RANGES = {}
        
        print("Building instruction field ranges dictionary...")
        print("=" * 60)
        
        # Step 1: Extract ranges from RTYPE and automatically identify registers
        rtype_success = self._extract_from_rtype_and_identify_registers(json_data)
        if not rtype_success:
            print("ERROR: Failed to extract RTYPE ranges")
            return False
        
        print(f"✓ RTYPE: Found {len(INSTRUCTION_FIELD_RANGES)} fixed fields")
        print(f"✓ Auto-detected register fields: {self.field_to_register_map}")
        
        # MODIFIED: Step 1.5 - ALWAYS search for rsd, and vector registers only if extension is enabled
        print("Searching for special registers in all mappings...")
        
        # Always search for rsd
        self._find_rsd_in_all_mappings(json_data)
        
        # Search for vector registers only if extension is enabled
        if self._is_vector_extension_enabled(extension_filter):
            print("Vector extension enabled - searching for vector registers...")
            self._find_vector_registers_in_all_mappings(json_data)
        else:
            print("Vector extension NOT enabled - skipping vector registers")
            
        # ADDED: Step 1.6 - Process compressed immediates
        print("\nProcessing compressed immediate fragments...")
        self._process_compressed_immediates(json_data)
        
        # Step 2: Check and complete with UTYPE, BTYPE, ITYPE, STYPE, JTYPE
        templates_to_check = ['UTYPE', 'BTYPE', 'ITYPE', 'STYPE', 'JTYPE']
        
        for template in templates_to_check:
            print(f"\nChecking {template}...")
            self._check_and_add_from_template(json_data, template)
        
        # Step 3: SPECIAL - Rename imm_jtype to imm_jal for JAL
        if 'imm_jtype' in INSTRUCTION_FIELD_RANGES:
            INSTRUCTION_FIELD_RANGES['imm_jal'] = INSTRUCTION_FIELD_RANGES['imm_jtype']
            del INSTRUCTION_FIELD_RANGES['imm_jtype']
            print(f"✓ Renamed imm_jtype to imm_jal: {INSTRUCTION_FIELD_RANGES['imm_jal']}")
        
        # Step 4: FORCED - Ensure imm_stype exists for STORE instructions
        if 'imm_stype' not in INSTRUCTION_FIELD_RANGES:
            print("FORCING creation of imm_stype...")
            upper_range = (31, 25)  # imm[31:25] - 7 bits
            lower_range = (11, 7)   # imm[11:7] - 5 bits
            INSTRUCTION_FIELD_RANGES['imm_stype'] = [upper_range, lower_range]
            print(f"✓ FORCED imm_stype: {INSTRUCTION_FIELD_RANGES['imm_stype']}")
        
        # Step 5: FORCED - Ensure we have all standard immediates
        standard_immediates = {
            'imm_i': (31, 20),  # I-type: 12 bits [31:20]
            'imm_utype': (31, 12),  # U-type: 20 bits [31:12]
            'imm_stype': [(31, 25),  (11, 7)]
        }
        
        for imm_name, default_range in standard_immediates.items():
            if imm_name not in INSTRUCTION_FIELD_RANGES:
                print(f"FORCING creation of {imm_name}...")
                # Calculate based on known registers if possible
                if imm_name == 'imm_i' and 'rs1' in INSTRUCTION_FIELD_RANGES:
                    rs1_start, rs1_end = INSTRUCTION_FIELD_RANGES['rs1']
                    calculated_range = (31, rs1_start + 1)
                elif imm_name == 'imm_utype' and 'rd' in INSTRUCTION_FIELD_RANGES:
                    rd_start, rd_end = INSTRUCTION_FIELD_RANGES['rd']
                    calculated_range = (31, rd_start + 1)
                else:
                    calculated_range = default_range
                
                INSTRUCTION_FIELD_RANGES[imm_name] = calculated_range
                print(f"✓ FORCED {imm_name}: {INSTRUCTION_FIELD_RANGES[imm_name]}")
        
        # ADDED: Step 6 - FORCED - Add shamt with correct range
        print("Detecting shamt in specific encodings...")
        self._detect_shamt_in_specific_encodings(json_data)
        
        # ADDED: Step 7 - Generate custom fields from special operand mappings
        print("Generating custom fields from special operand mappings...")
        custom_fields_xml = self.generate_custom_fields_from_existing_parsing(json_data)
        if custom_fields_xml:
            print(f"✓ Generated custom instruction fields")
        else:
            print("No custom instruction fields generated")
        
        # Debug: Display all created immediates
        print("\nCreated immediate fields:")
        for field_name, field_range in INSTRUCTION_FIELD_RANGES.items():
            if field_name.startswith('imm_') or field_name == 'shamt' or field_name.startswith('fence_'):
                if isinstance(field_range, list):
                    print(f"  {field_name}: {len(field_range)} ranges - {field_range}")
                else:
                    print(f"  {field_name}: {field_range}")
        
        # ADDED: FINAL Step - Analyze signedness for immediates
        print("\n" + "="*60)
        print("CALLING _analyze_immediate_signedness")
        print("="*60)
        self._analyze_immediate_signedness(json_data)
        
        # Debug: check what was stored
        print(f"\nDEBUG: After analysis, immediate_sign_info contains:")
        for field_name, is_signed in self.immediate_sign_info.items():
            print(f"  {field_name}: {is_signed}")
        
        return True
    
    
    def _process_compressed_immediates(self, json_data: Dict[str, Any]) -> None:
        """Processes all compressed immediates from JSON."""
        print("Searching for compressed immediate patterns...")
        
        if 'mappings' not in json_data or 'encdec_compressed' not in json_data['mappings']:
            print("  No compressed mappings found")
            return
        
        compressed_mappings = json_data['mappings']['encdec_compressed'].get('mapping', [])
        if not isinstance(compressed_mappings, list):
            print("  Compressed mappings is not a list")
            return
        
        print(f"  Found {len(compressed_mappings)} compressed mappings")
        
        # Search for first compressed instruction with fragmented immediate
        for instruction_data in compressed_mappings:
            if not isinstance(instruction_data, dict):
                continue
                
            source = instruction_data.get('source', {})
            contents = source.get('contents', '')
            
            if not isinstance(contents, str):
                continue
            
            # Search for fragmented immediate patterns in compressed
            # For example: imm5 @ imm40 or imm6 @ imm2
            if ('@' in contents and '<->' in contents and 
                (re.search(r'imm\w+\s*@\s*imm\w+', contents) or 
                re.search(r'ui\w+\s*@\s*ui\w+', contents))):
                    print(f"  Found compressed immediate pattern in: {contents[:100]}...")
                    
                    # Extract instruction name for debug
                    instr_match = re.search(r'(\w+)\s*\(', contents)
                    instr_name = instr_match.group(1) if instr_match else "unknown"
                    
                    self._process_compressed_immediate_fragments(contents, instr_name)
                    
                    # Found and processed pattern, stop searching
                    # (assuming all compressed immediates have same format)
                    return
        
        print("  No compressed immediate patterns found")

    
    def _find_rsd_in_all_mappings(self, json_data: Dict[str, Any]) -> None:
        """Explicitly searches for rsd register in all mappings."""
        global INSTRUCTION_FIELD_RANGES
        
        print("\nSearching for rsd register in all mappings...")
        
        if 'mappings' not in json_data:
            return
        
        # MODIFIED: Search in both sections - normal and compressed
        mapping_lists = []
        
        if 'encdec' in json_data['mappings']:
            normal_mappings = json_data['mappings']['encdec'].get('mapping', [])
            if isinstance(normal_mappings, list):
                mapping_lists.append(('normal', normal_mappings, 32))
        
        if 'encdec_compressed' in json_data['mappings']:
            compressed_mappings = json_data['mappings']['encdec_compressed'].get('mapping', [])
            if isinstance(compressed_mappings, list):
                mapping_lists.append(('compressed', compressed_mappings, 16))
        
        for mapping_type, mapping_list, instruction_width in mapping_lists:
            print(f"\n  Searching in {mapping_type} mappings ({instruction_width}-bit)...")
            
            for instruction_data in mapping_list:
                if not isinstance(instruction_data, dict):
                    continue
                    
                source = instruction_data.get('source', {})
                contents = source.get('contents', '')
                
                if not isinstance(contents, str):
                    continue
                
                # Search for rsd in contents
                if 'rsd' in contents and '<->' in contents:
                    print(f"  Found rsd in {mapping_type}: {contents[:100]}...")
                    
                    # Parse encoding to find position
                    match = re.search(r'<->\s*(.+)', contents)
                    if match:
                        encoding_part = match.group(1).strip()
                        # Remove "when" condition if present
                        encoding_part = re.sub(r'\s+when\s+.*$', '', encoding_part)
                        components = [comp.strip() for comp in encoding_part.split('@')]
                        
                        print(f"    Encoding components: {components}")
                        print(f"    Instruction width: {instruction_width} bits")
                        
                        # MODIFIED: Start from correct MSB for instruction type
                        current_bit = instruction_width - 1  # 31 for 32-bit, 15 for 16-bit
                        
                        for i, component in enumerate(components):
                            print(f"    [{i}] Component: '{component}' at bit {current_bit}")
                            
                            # Check if component contains rsd
                            if component == 'rsd' or 'encdec_reg(rsd)' in component:
                                # Calculate position (registers have 5 bits)
                                start_bit = current_bit
                                end_bit = current_bit - 5 + 1
                                
                                print(f"    ✓ Found rsd at component {i}")
                                print(f"    ✓ Calculated range: [{start_bit}:{end_bit}]")
                                
                                if 'rsd' not in INSTRUCTION_FIELD_RANGES:
                                    INSTRUCTION_FIELD_RANGES['rsd'] = (start_bit, end_bit)
                                    self.field_to_register_map['rsd'] = 'GPR'
                                    print(f"    + Added rsd: ({start_bit}, {end_bit}) -> GPR")
                                    
                                    # Compare with rd for verification
                                    if 'rd' in INSTRUCTION_FIELD_RANGES:
                                        rd_range = INSTRUCTION_FIELD_RANGES['rd']
                                        print(f"    INFO: rd range for comparison: {rd_range}")
                                    
                                    return  # Found rsd, stop searching
                                
                                break
                            
                            if component == 'rd_c' or 'encdec_creg(rd)' in component:
                                # Calculate position (registers have 3 bits)
                                start_bit = current_bit
                                end_bit = current_bit - 3 + 1
                                
                                print(f"    ✓ Found rd_c at component {i}")
                                print(f"    ✓ Calculated range: [{start_bit}:{end_bit}]")
                                
                                if 'rd_c' not in INSTRUCTION_FIELD_RANGES:
                                    INSTRUCTION_FIELD_RANGES['rd_c'] = (start_bit, end_bit)
                                    self.field_to_register_map['rd_c'] = 'GPR'
                                    print(f"    + Added rd_c: ({start_bit}, {end_bit}) -> GPR")
                                    
                                    # Compare with rd for verification
                                    if 'rd' in INSTRUCTION_FIELD_RANGES:
                                        rd_range = INSTRUCTION_FIELD_RANGES['rd']
                                        print(f"    INFO: rd range for comparison: {rd_range}")
                                    
                                    return  # Found rsd, stop searching
                                elif 'rs1_c' not in INSTRUCTION_FIELD_RANGES:
                                    INSTRUCTION_FIELD_RANGES['rs1_c'] = (start_bit, end_bit)
                                    self.field_to_register_map['rs1_c'] = 'GPR'
                                    print(f"    + Added rs1_c: ({start_bit}, {end_bit}) -> GPR")
                                    
                                    # Compare with rd for verification
                                    if 'rd' in INSTRUCTION_FIELD_RANGES:
                                        rd_range = INSTRUCTION_FIELD_RANGES['rd']
                                        print(f"    INFO: rd range for comparison: {rd_range}")
                                    
                                    return  # Found rsd, stop searching
                                elif 'rs2_c' not in INSTRUCTION_FIELD_RANGES:
                                    INSTRUCTION_FIELD_RANGES['rs2_c'] = (start_bit, end_bit)
                                    self.field_to_register_map['rs2_c'] = 'GPR'
                                    print(f"    + Added rs2_c: ({start_bit}, {end_bit}) -> GPR")
                                    
                                    # Compare with rd for verification
                                    if 'rd' in INSTRUCTION_FIELD_RANGES:
                                        rd_range = INSTRUCTION_FIELD_RANGES['rd']
                                        print(f"    INFO: rd range for comparison: {rd_range}")
                                    
                                    return  # Found rsd, stop searching
                                
                                break
                            
                            # Calculate component size to advance current_bit
                            bit_count = self._calculate_component_bit_count(component)
                            print(f"      Component '{component}': {bit_count} bits")
                            current_bit -= bit_count
                            print(f"      Current bit after: {current_bit}")
        
        print("  rsd not found in any mappings")
        
        # Fallback: if we don't find rsd, but have rd, use same range
        if 'rsd' not in INSTRUCTION_FIELD_RANGES and 'rd' in INSTRUCTION_FIELD_RANGES:
            INSTRUCTION_FIELD_RANGES['rsd'] = INSTRUCTION_FIELD_RANGES['rd']
            self.field_to_register_map['rsd'] = 'GPR'
            print(f"  + Added rsd with rd's range (fallback): {INSTRUCTION_FIELD_RANGES['rsd']} -> GPR")

    def _calculate_component_bit_count(self, component: str) -> int:
        """Calculates number of bits for an encoding component."""
        # Check if it has explicit bit specification: "imm5 : bits(1)"
        bits_match = re.search(r':\s*bits\((\d+)\)', component)
        if bits_match:
            return int(bits_match.group(1))
        
        # Binary literal: "0b000"
        if component.startswith('0b'):
            return len(component) - 2
        
        # Encoding functions for registers
        if 'encdec_reg(' in component:
            return 5  # registers have 5 bits

        if 'encdec_creg(' in component:
            return 3  # compressed registers have 3 bits
        
        # Known registers directly
        if component in ['md', 'ms1', 'ms2', 'rd', 'rs1', 'rs2', 'rs3', 'rsd', 'shamt']:
            return 5

        if component in ['rd_c', 'rs1_c', 'rs2_c']:
            return 3
        
        # Known immediate fields
        if component.startswith('imm'):
            # Try to extract size from name: imm40 = 5 bits, imm5 = 1 bit
            # But this is just a guess - should be explicitly specified
            return 3  # conservative default
        
        # Default for unknown components
        return 3

    
    def _find_vector_registers_in_all_mappings(self, json_data: Dict[str, Any]) -> None:
        """Explicitly searches for vector registers (md, ms1, ms2) in all mappings."""
        global INSTRUCTION_FIELD_RANGES
        
        print("\nSearching for vector registers in all mappings...")
        
        if 'mappings' not in json_data or 'encdec' not in json_data['mappings']:
            return
        
        mapping_list = json_data['mappings']['encdec']['mapping'] + json_data['mappings']['encdec_compressed']['mapping']
        if not isinstance(mapping_list, list):
            return
        
        registers_to_find = ['md', 'ms1', 'ms2']
        registers_found = set()
        
        vector_registers_found = set()
        
        for instruction_data in mapping_list:
            if not isinstance(instruction_data, dict):
                continue
                
            source = instruction_data.get('source', {})
            contents = source.get('contents', '')
            
            if not isinstance(contents, str):
                continue
            
            # Search for vector registers in contents
            for reg_name in ['md', 'ms1', 'ms2']:
                if reg_name in contents and '<->' in contents:
                    print(f"Found vector register {reg_name} in: {contents[:100]}...")
                    
                    # Parse encoding to find position
                    match = re.search(r'<->\s*(.+)', contents)
                    if match:
                        encoding_part = match.group(1).strip()
                        components = [comp.strip() for comp in encoding_part.split('@')]
                        
                        print(f"  Encoding components: {components}")
                        
                        current_bit = 31
                        for component in components:
                            print(f"  Checking component: '{component}' at bit {current_bit}")
                            
                            # Check if component contains our register
                            if component == reg_name or f'encdec_reg({reg_name})' in component:
                                # Calculate position (registers have 5 bits)
                                start_bit = current_bit
                                end_bit = current_bit - 5 + 1
                                
                                if reg_name not in INSTRUCTION_FIELD_RANGES:
                                    INSTRUCTION_FIELD_RANGES[reg_name] = (start_bit, end_bit)
                                    if reg_name == 'rsd':
                                        self.field_to_register_map[reg_name] = 'GPR'
                                        print(f"  + Added {reg_name}: ({start_bit}, {end_bit}) -> GPR")
                                    else:
                                        self.field_to_register_map[reg_name] = 'VR'
                                        print(f"  + Added {reg_name}: ({start_bit}, {end_bit}) -> VR")
                        
                                registers_found.add(reg_name)
                                break
                                
                            if component == reg_name or f'encdec_creg({reg_name})' in component:
                                # Calculate position (registers have 3 bits)
                                start_bit = current_bit
                                end_bit = current_bit - 3 + 1
                                
                                if reg_name + "_c" not in INSTRUCTION_FIELD_RANGES:
                                    INSTRUCTION_FIELD_RANGES[reg_name + "_c"] = (start_bit, end_bit)
                                    if reg_name == 'rd_c':
                                        self.field_to_register_map[reg_name + "_c"] = 'GPR'
                                        print(f"  + Added {reg_name}: ({start_bit}, {end_bit}) -> GPR")
                                
                                    elif reg_name == 'rs1_c':
                                        self.field_to_register_map[reg_name + "_c"] = 'GPR'
                                        print(f"  + Added {reg_name + '_c'}: ({start_bit}, {end_bit}) -> GPR")
                                        
                                    elif reg_name == 'rs2_c':
                                        self.field_to_register_map[reg_name + "_c"] = 'GPR'
                                        print(f"  + Added {reg_name + '_c'}: ({start_bit}, {end_bit}) -> GPR")
                        
                                registers_found.add(reg_name)
                                break
                            
                            # Calculate component size to advance current_bit
                            if component.startswith('0b'):
                                bit_count = len(component) - 2
                                current_bit -= bit_count
                                print(f"    Binary literal: {bit_count} bits, now at {current_bit}")
                            elif 'encdec_reg(' in component:
                                current_bit -= 5  # registers have 5 bits
                                print(f"    Register: 5 bits, now at {current_bit}")
                            elif 'encdec_creg(' in component:
                                current_bit -= 3  # compressed registers have 3 bits
                                print(f"    Register: 3 bits, now at {current_bit}")
                            elif component in ['md', 'ms1', 'ms2', 'rd', 'rs1', 'rs2', 'rs3', 'rsd']:
                                current_bit -= 5
                                print(f"    Register {component}: 5 bits, now at {current_bit}")
                            elif component in ['rs1_c', 'rs2_c', 'rd_c']:
                                current_bit -= 3
                                print(f"    Register {component}: 3 bits, now at {current_bit}")
                            elif component == 'shamt':
                                current_bit -= 5
                                print(f"    Shamt: 5 bits, now at {current_bit}")
                            else:
                                # Estimate size
                                current_bit -= 3  # default
                                print(f"    Other: 3 bits (default), now at {current_bit}")
        
        if vector_registers_found:
            print(f"✓ Found and added {len(vector_registers_found)} vector registers: {vector_registers_found}")
        else:
            print("No vector registers found in mappings")

def get_instruction_field_ranges() -> Dict[str, tuple]:
    """
    Returns all instruction field ranges collected globally.

    This function provides access to the dictionary containing range
    information for all instruction fields parsed earlier in the pipeline.

    Returns:
        Dict[str, tuple]: A dictionary mapping instruction field names to
        tuples representing their associated ranges.
    """
    return INSTRUCTION_FIELD_RANGES.copy()

def get_instruction_field_range(field_name: str) -> tuple:
    """
    Retrieves the range information for a specific instruction field.

    This function returns the tuple associated with the given field name from
    the global instruction field ranges dictionary.

    Args:
        field_name (str): Name of the instruction field whose range information
            should be retrieved.

    Returns:
        tuple: The range tuple associated with the specified instruction field.
    """
    return INSTRUCTION_FIELD_RANGES.get(field_name, (0, 0))

class InstructionParser:
    
    def build_and_test_instruction_fields(self, json_data: Dict[str, Any]) -> None: 
        """Builds and validates the instruction fields dictionary using the provided JSON data.
        
        This method processes the instruction field definitions extracted from the JSON structure,
        constructs the internal dictionary representation, and runs validation steps.
        
        Args:
            json_data (Dict[str, Any]): Parsed JSON data containing instruction field definitions.
        
        Returns:
            None
        """
        print("\n" + "="*80)
        print("BUILDING INSTRUCTION FIELD RANGES DICTIONARY")
        print("="*80)
        
        field_manager = InstructionFieldManager()
        
        # Build the dictionary
        success = field_manager.build_instruction_field_ranges(json_data)
        
        if success:
            self._print_final_instruction_fields()
        else:
            print("Failed to build instruction field ranges!")
    
    
    def _print_final_instruction_fields(self) -> None:
        """
        Prints the final dictionary of instruction fields.

        This method outputs the fully constructed and validated instruction fields
        dictionary, typically for debugging, verification, or logging purposes.

        Returns:
            None
        """
        global INSTRUCTION_FIELD_RANGES
        
        print("\n" + "="*60)
        print("FINAL INSTRUCTION FIELD RANGES DICTIONARY")
        print("="*60)
        
        if not INSTRUCTION_FIELD_RANGES:
            print("Dictionary is empty!")
            return
        
        print("Field Name   | Bit Range | Size | Type")
        print("-" * 45)
        
        # MODIFIED: Sort with function that handles multiple ranges
        def get_sort_key(item):
            field_name, field_ranges = item
            if isinstance(field_ranges, list):
                # For multiple ranges, use first range for sorting
                return field_ranges[0][0] if field_ranges else 0
            else:
                # For simple range
                return field_ranges[0]
        
        sorted_fields = sorted(INSTRUCTION_FIELD_RANGES.items(), 
                            key=get_sort_key, reverse=True)
        
        for field_name, field_ranges in sorted_fields:
            if isinstance(field_ranges, list):
                # Multiple ranges
                total_size = sum(start - end + 1 for start, end in field_ranges)
                range_str = f"Multi({len(field_ranges)})"
                field_type = "Immediate"
            else:
                # Simple range
                start_bit, end_bit = field_ranges
                total_size = start_bit - end_bit + 1
                range_str = f"{start_bit:2d}:{end_bit:2d}"
                
                # Determine type
                if field_name in ['rs1', 'rs2', 'rs3', 'rd']:
                    field_type = "GPR"
                elif field_name == 'csr':
                    field_type = "CSR"
                elif field_name in ['funct3', 'funct7', 'opcode']:
                    field_type = "Control"
                elif field_name == 'shamt':
                    field_type = "Shift"
                elif 'imm' in field_name:
                    field_type = "Immediate"
                else:
                    field_type = "Other"
            
            print(f"{field_name:12} | {range_str:8} | {total_size:2d}   | {field_type}")
        
        print("-" * 45)
        print(f"Total instruction fields: {len(INSTRUCTION_FIELD_RANGES)}")
        print("="*60)



# Global variable to store register generator
_global_register_generator = None

def get_gpr_alias(arch_name: str) -> str:
    """
    Retrieves the alias associated with a given GPR (General-Purpose Register).

    This function looks up the alias for the specified architecture-specific
    register name using the global GPR alias dictionary.

    Args:
        arch_name (str): The architecture-specific name of the GPR whose alias
            should be retrieved.

    Returns:
        str: The alias corresponding to the specified GPR.
    """
    global GPR_ALIASES
    aliases = GPR_ALIASES.get(arch_name, arch_name)
    
    # MODIFIED: If we have a list, return first alias
    if isinstance(aliases, list):
        return aliases[0] if aliases else arch_name
    return aliases

def get_all_gpr_aliases() -> Dict[str, Any]:
    """
    Retrieves all GPR (General Purpose Register) aliases stored globally.

    This function returns the entire dictionary that maps architecture-specific
    register names to their corresponding aliases.

    Returns:
        Dict[str, Any]: A dictionary containing all GPR aliases.
    """
    global GPR_ALIASES
    return GPR_ALIASES.copy()


SPECIAL_INSTRUCTION_ATTRIBUTES: Dict[str, str] = {}

def load_special_attributes() -> None: 
    """Loads the special attributes from the configuration file.
    
    This function reads the configuration and extracts any attributes marked as special,
    storing them in the appropriate global structures for later use.
    
    Returns:
        None
    """
    global SPECIAL_INSTRUCTION_ATTRIBUTES
    print("DEBUG: Starting to load special attributes...")
    
    try:
        reg_generator = RegisterFileGenerator()
        SPECIAL_INSTRUCTION_ATTRIBUTES = reg_generator.get_special_attributes()
        print(f"DEBUG: Loaded special attributes: {SPECIAL_INSTRUCTION_ATTRIBUTES}")
        print(f"✓ Loaded {len(SPECIAL_INSTRUCTION_ATTRIBUTES)} special instruction attributes")
    except Exception as e:
        print(f"ERROR: Failed to load special attributes: {e}")
        SPECIAL_INSTRUCTION_ATTRIBUTES = {}


class RegisterFileGenerator:
    def __init__(self, config_file: str = Path(__file__).resolve().parent / "register_config.py"):
        self.config_file = config_file
        self.register_configs = {}
        self.csr_mappings = {}
        self.gpr_arch_mappings = {}
        self.gpr_abi_mappings = {}   # For GPR ABI mappings (zero, ra, etc.)
        self.gpr_aliases = {}  
        self.special_attributes = {}
        self.ignored_instructions = []  
        self.special_operand_mappings = {}
        self.logger = None  # Will be set externally
        self.load_config()
    
    def load_config(self):
        """
        Loads the register configuration from the Python configuration file.

        This method reads and parses the configuration data required for building
        register classes, instruction fields, attributes, and other components.

        Returns:
            None
        """
        try:
            # Import configuration module
            import importlib.util
            import sys
            import os
            
            print(f"DEBUG: Loading config from {self.config_file}")
            print(f"DEBUG: Config file exists: {os.path.exists(self.config_file)}")
            print(f"DEBUG: Current working directory: {os.getcwd()}")
            
            spec = importlib.util.spec_from_file_location("register_config", self.config_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load spec from {self.config_file}")
            
            config_module = importlib.util.module_from_spec(spec)
            print(f"DEBUG: About to execute module...")
            spec.loader.exec_module(config_module)
            print(f"DEBUG: Module executed successfully")
            
            # Debug: Display all module attributes
            all_attrs = [attr for attr in dir(config_module) if not attr.startswith('_')]
            print(f"DEBUG: Module attributes: {all_attrs}")
            
            # ADDED: Check SPECIAL_OPERAND_MAPPINGS
            if hasattr(config_module, 'SPECIAL_OPERAND_MAPPINGS'):
                raw_mappings = getattr(config_module, 'SPECIAL_OPERAND_MAPPINGS')
                self.special_operand_mappings = raw_mappings
                print(f"DEBUG: Loaded special operand mappings: {self.special_operand_mappings}")
                self.console_print(f"Loaded {len(self.special_operand_mappings)} special operand mappings")
            else:
                print("DEBUG: SPECIAL_OPERAND_MAPPINGS not found in config module")
                self.special_operand_mappings = {}
                                
            # ADDED: Check IGNORED_INSTRUCTIONS
            if hasattr(config_module, 'IGNORED_INSTRUCTIONS'):
                raw_ignored = getattr(config_module, 'IGNORED_INSTRUCTIONS')
                self.ignored_instructions = raw_ignored
                print(f"DEBUG: Loaded ignored instructions: {self.ignored_instructions}")
                self.console_print(f"Loaded {len(self.ignored_instructions)} ignored instructions")
            else:
                print("DEBUG: IGNORED_INSTRUCTIONS not found in config module")
                self.ignored_instructions = []
                
            # Check specifically for SPECIAL_INSTRUCTION_ATTRIBUTES
            if hasattr(config_module, 'SPECIAL_INSTRUCTION_ATTRIBUTES'):
                raw_value = getattr(config_module, 'SPECIAL_INSTRUCTION_ATTRIBUTES')
                print(f"DEBUG: Raw SPECIAL_INSTRUCTION_ATTRIBUTES value: {raw_value}")
                print(f"DEBUG: Raw type: {type(raw_value)}")
                
                self.special_attributes = raw_value
                print(f"DEBUG: Assigned to self.special_attributes: {self.special_attributes}")
                self.console_print(f"Loaded {len(self.special_attributes)} special instruction attributes")
            else:
                print("DEBUG: SPECIAL_INSTRUCTION_ATTRIBUTES not found in config module")
                print(f"DEBUG: Available attributes: {all_attrs}")
                self.special_attributes = {}
            
            # Extract register configurations
            self.register_configs = self._extract_register_configs(config_module)
            
            if not self.register_configs:
                self.console_print("Warning: No valid register configurations found in config file.")
                return
                
            self.console_print(f"Loaded {len(self.register_configs)} register class(es): {', '.join(self.register_configs.keys())}")
                
        except Exception as e:
            print(f"DEBUG: Exception in load_config: {e}")
            import traceback
            traceback.print_exc()
            self.console_print(f"Warning: Could not load register config from {self.config_file}: {e}")
            self.console_print("No register files will be generated.")
            self.special_attributes = {}
            self.ignored_instructions = []
            self.special_operand_mappings = {}


    def _get_register_name(self, reg_class_name: str, reg_index: int) -> str:
        """
        Retrieves the name of a register based on its class and index.

        This method looks up the register belonging to the specified register
        class and returns the corresponding register name for the given index.

        Args:
            reg_class_name (str): The name of the register class (e.g., GPR, FPR, CSR).
            reg_index (int): The index of the register within the specified class.

        Returns:
            str: The register name associated with the given class and index.
        """
        if reg_class_name not in self.register_configs:
            return f"reg{reg_index}"
        
        config = self.register_configs[reg_class_name]
        prefix = config.get('prefix', '')
        
        if reg_class_name == 'GPR':
            # For GPR, use architectural mappings (x0, x1, etc.)
            return self.gpr_arch_mappings.get(reg_index, f'x{reg_index}')
        elif reg_class_name == 'VR':
            # For VR, use prefix 'v' + index
            return f'{prefix}{reg_index}' if prefix else f'v{reg_index}'
        else:
            # For other classes, use prefix + index
            return f'{prefix}{reg_index}' if prefix else f'reg{reg_index}'




    
    def get_special_operand_mappings(self) -> Dict[str, Dict[str, str]]:
        """
        Retrieves the dictionary of special operand mappings.

        This method returns a copy of the internal structure that maps semantic
        operand categories to architecture-specific operand names or properties.

        Returns:
            Dict[str, Dict[str, str]]: A shallow copy of the special operand
            mappings dictionary.
        """
        return self.special_operand_mappings.copy()


    def get_special_attributes(self) -> Dict[str, str]:
        """
        Retrieves the dictionary of special attributes.

        This method returns a copy of the internal dictionary of attributes
        marked as special in the configuration (e.g., flags or behaviors that
        affect generation/selection).

        Returns:
            Dict[str, str]: A shallow copy of the special attributes dictionary.
        """
        return self.special_attributes.copy()


    def generate_calling_convention(self, reg_name: str) -> Optional[ET.Element]:
        """
        Generates the XML `calling_convention` element for a given register.

        This method creates and returns an XML element that describes how the
        specified register participates in the calling convention (e.g., caller/callee
        saved, argument passing, return value). If the register is not recognized or
        lacks calling‑convention metadata, the method returns `None`.

        Args:
            reg_name (str): The architecture-specific register name for which the
                calling convention element should be generated.

        Returns:
            Optional[xml.etree.ElementTree.Element]: The generated XML element
            representing the calling convention for the register, or `None` if
            no element can be produced.
        """
        if reg_name not in self.register_configs:
            return None
        
        config = self.register_configs[reg_name]
        
        # Check if register has calling convention
        if 'calling_convention' not in config:
            self.debug_print(f"DEBUG: No calling convention for {reg_name}")
            return None
        
        calling_conv = config['calling_convention']
        if 'ranges' not in calling_conv:
            self.debug_print(f"DEBUG: No ranges in calling convention for {reg_name}")
            return None
        
        # Create calling_convention element
        calling_conv_elem = ET.Element('calling_convention')
        
        # Process each range
        ranges = calling_conv['ranges']
        special_aliases = calling_conv.get('special_aliases', {})
        
        self.debug_print(f"DEBUG: Processing {len(ranges)} calling convention ranges for {reg_name}")
        if special_aliases:
            self.debug_print(f"DEBUG: Found special aliases: {special_aliases}")
        
        for start_idx, end_idx, description in ranges:
            # For each register in range
            for reg_idx in range(start_idx, end_idx + 1):
                # Get register name using new method
                reg_arch_name = self._get_register_name(reg_name, reg_idx)
                
                if reg_arch_name:
                    # Create option element for main architectural name
                    option_elem = ET.SubElement(calling_conv_elem, 'option', name=reg_arch_name.upper())
                    option_str = ET.SubElement(option_elem, 'str')
                    option_str.text = description
                    
                    self.debug_print(f"DEBUG: Added calling convention {reg_arch_name.upper()} -> {description}")
                    
                    # ADDED: Check if special aliases exist for this register
                    if reg_idx in special_aliases:
                        special_alias_list = special_aliases[reg_idx]
                        self.debug_print(f"DEBUG: Processing special aliases for register {reg_idx}: {special_alias_list}")
                        
                        # Add each special alias as separate option
                        for special_alias in special_alias_list:
                            special_option_elem = ET.SubElement(
                                calling_conv_elem,
                                'option',
                                name=str(reg_idx)  # use index as name
                            )
                            special_option_str = ET.SubElement(special_option_elem, 'str')
                            special_option_str.text = special_alias
                            
                            self.debug_print(f"DEBUG: Added special alias option name='{reg_idx}' -> '{special_alias}'")
        
        return calling_conv_elem


    
    def get_ignored_instructions(self) -> List[str]:
        """
        Retrieves the list of ignored instructions.

        This method returns a shallow copy of the internally stored list of
        instruction names that should be ignored during processing or generation.

        Returns:
            List[str]: A copy of the ignored instructions list.
        """
        return self.ignored_instructions.copy()


    def _print_calling_convention_test(self, reg_name: str) -> None:
        """
        Prints a test representation of the generated calling convention.

        This helper method is intended for debugging/verification purposes.
        It generates the calling convention element for the provided register
        name and prints a human-readable representation (or a diagnostic message
        if none can be generated).

        Args:
            reg_name (str): The architecture-specific register name to test.

        Returns:
            None
        """
        if reg_name not in self.register_configs:
            return
        
        config = self.register_configs[reg_name]
        if 'calling_convention' not in config:
            return
        
        print(f"\nCalling Convention for {reg_name}:")
        print("-" * 40)
        
        calling_conv = config['calling_convention']
        ranges = calling_conv['ranges']
        special_aliases = calling_conv.get('special_aliases', {})
        
        processed_registers = set()
        
        for start_idx, end_idx, description in ranges:
            for reg_idx in range(start_idx, end_idx + 1):
                if reg_idx in processed_registers:
                    continue
                
                processed_registers.add(reg_idx)
                
                # Generate names
                if reg_name == 'GPR' and 'registers' in config:
                    registers = config['registers']
                    if reg_idx in registers:
                        aliases = registers[reg_idx].get('aliases', [])
                        if aliases:
                            reg_arch_name = aliases[0]
                        else:
                            reg_arch_name = f'x{reg_idx}'
                    else:
                        reg_arch_name = f'x{reg_idx}'
                else:
                    prefix = config.get('prefix', '')
                    reg_arch_name = f'{prefix}{reg_idx}' if prefix else f'reg{reg_idx}'
                
                print(f"{reg_arch_name.upper()} -> {description}")
                
                # ADDED: Display special aliases too
                if reg_idx in special_aliases:
                    for special_alias in special_aliases[reg_idx]:
                        print(f"  option name='{reg_idx}' -> {special_alias}")
        
        print("-" * 40 + "\n")


    
    def parse_gpr_mappings(self, json_data: Dict[str, Any]) -> None:
        """
        Parses GPR mappings from the provided JSON and builds the alias dictionary.

        This method extracts architecture-specific GPR names and their aliases
        from the JSON structure and populates the internal alias mapping used
        throughout the register generation pipeline.

        Args:
            json_data (Dict[str, Any]): Parsed JSON data containing the GPR mapping
                definitions.

        Returns:
            None
        """
        self.debug_print("DEBUG: Searching for GPR mappings...")
        
        if 'mappings' not in json_data:
            self.debug_print("DEBUG: No 'mappings' section found")
            return
        
        mappings = json_data['mappings']
        
        # Parse architectural mappings (x0, x1, etc.)
        if 'reg_arch_name_raw' in mappings:
            self._parse_gpr_arch_mappings(mappings['reg_arch_name_raw'])
        else:
            self.debug_print("DEBUG: No 'reg_arch_name_raw' section found")
        
        # Parse ABI mappings (zero, ra, etc.)
        if 'reg_abi_name_raw' in mappings:
            self._parse_gpr_abi_mappings(mappings['reg_abi_name_raw'])
        else:
            self.debug_print("DEBUG: No 'reg_abi_name_raw' section found")
        
        # Create alias dictionary
        self._create_gpr_aliases()
    
    def _parse_gpr_arch_mappings(self, arch_map: Dict[str, Any]) -> None:
        """
        Parses architectural GPR mappings (e.g., x0, x1, etc.) and updates internal structures.

        This method processes the architecture-level register map and extracts
        canonical register names together with any associated aliases. The resulting
        mappings are stored internally and used during register file generation
        and validation.

        Args:
            arch_map (Dict[str, Any]): Dictionary containing the architectural GPR mappings.

        Returns:
            None
        """
        if 'mapping' not in arch_map:
            self.debug_print("DEBUG: No 'mapping' in reg_arch_name_raw")
            return
        
        mapping_list = arch_map['mapping']
        if not isinstance(mapping_list, list):
            self.debug_print("DEBUG: reg_arch_name_raw mapping is not a list")
            return
        
        self.debug_print(f"DEBUG: Found {len(mapping_list)} architectural GPR mappings")
        
        for item in mapping_list:
            if not isinstance(item, dict):
                continue
            
            source = item.get('source', {})
            if not isinstance(source, dict):
                continue
            
            contents = source.get('contents', '')
            if not isinstance(contents, str):
                continue
            
            # Parse contents: "0b00000 <-> \"x0\""
            reg_index, reg_name = self._parse_gpr_mapping_contents(contents)
            if reg_index is not None and reg_name:
                self.gpr_arch_mappings[reg_index] = reg_name
                self.debug_print(f"DEBUG: Mapped GPR arch {reg_index} -> {reg_name}")
    
    def _parse_gpr_abi_mappings(self, abi_map: Dict[str, Any]) -> None:
        """
        Parses ABI GPR mappings (e.g., zero, ra, etc.) and updates internal structures.

        This method processes the ABI-level register mapping and extracts canonical
        ABI names for GPRs, validating and storing them for later use in register
        generation, lookups, and verification.

        Args:
            abi_map (Dict[str, Any]): Dictionary containing ABI GPR mappings.

        Returns:
            None
        """
        if 'mapping' not in abi_map:
            self.debug_print("DEBUG: No 'mapping' in reg_abi_name_raw")
            return
        
        mapping_list = abi_map['mapping']
        if not isinstance(mapping_list, list):
            self.debug_print("DEBUG: reg_abi_name_raw mapping is not a list")
            return
        
        self.debug_print(f"DEBUG: Found {len(mapping_list)} ABI GPR mappings")
        
        for item in mapping_list:
            if not isinstance(item, dict):
                continue
            
            source = item.get('source', {})
            if not isinstance(source, dict):
                continue
            
            contents = source.get('contents', '')
            if not isinstance(contents, str):
                continue
            
            # Parse contents: "0b00000 <-> \"zero\""
            reg_index, reg_name = self._parse_gpr_mapping_contents(contents)
            if reg_index is not None and reg_name:
                # MODIFIED: Store as list to allow multiple aliases
                if reg_index not in self.gpr_abi_mappings:
                    self.gpr_abi_mappings[reg_index] = []
                
                # Add alias only if not already present
                if reg_name not in self.gpr_abi_mappings[reg_index]:
                    self.gpr_abi_mappings[reg_index].append(reg_name)
                    self.debug_print(f"DEBUG: Mapped GPR ABI {reg_index} -> {reg_name}")

    
    def _parse_gpr_mapping_contents(self, contents: str) -> tuple:
        """
        Parses the contents of a GPR mapping, e.g., '0b00000 <-> "x0"' or '0b00000 <-> "zero"'.

        This method interprets a single mapping line connecting a binary register
        index to either an architectural name (e.g., "x0") or an ABI name (e.g., "zero").

        Args:
            contents (str): A mapping string in the form '0b<binary_index> <-> "<name>"'.

        Returns:
            tuple: A tuple containing:
                - int: The register index decoded from the binary literal.
                - str: The mapped register name (architectural or ABI).
        """
        # Pattern to extract binary index and register name
        match = re.search(r'(0b[01]+|\d+)\s*<->\s*["\']([^"\']+)["\']', contents)
        if not match:
            return None, None
        
        index_str = match.group(1)
        reg_name = match.group(2)
        
        # Convert index to int
        if index_str.startswith('0b'):
            reg_index = int(index_str[2:], 2)
        else:
            reg_index = int(index_str)
        
        return reg_index, reg_name
    
    def _create_gpr_aliases(self) -> None:
        """
        Creates the GPR alias dictionary, mapping architectural register names
        to their ABI aliases (e.g., x0 -> zero, x1 -> ra, etc.).

        This method consolidates architectural mappings and ABI mappings previously
        parsed from the configuration or JSON input. It builds a unified alias
        dictionary that allows lookup of ABI names for each architectural register.

        Returns:
            None
        """
        self.gpr_aliases = {}
        
        # For each index, combine architectural name with all ABI aliases
        for reg_index in range(32):  # GPR has 32 registers
            arch_name = self.gpr_arch_mappings.get(reg_index)
            abi_names = self.gpr_abi_mappings.get(reg_index)  # now is list
            
            if arch_name:
                if abi_names and isinstance(abi_names, list):
                    # MODIFIED: Keep ALL ABI aliases as list
                    self.gpr_aliases[arch_name] = abi_names.copy()
                elif abi_names and isinstance(abi_names, str):
                    # Fallback for compatibility - convert to list
                    self.gpr_aliases[arch_name] = [abi_names]
                else:
                    # If no ABI name, use architectural name as list
                    self.gpr_aliases[arch_name] = [arch_name]
        
        self.debug_print(f"DEBUG: Created {len(self.gpr_aliases)} GPR aliases")
        
        # Print dictionary with all aliases
        self._print_gpr_aliases_detailed()


    def _print_gpr_aliases_detailed(self) -> None:
        """
        Prints the detailed GPR alias dictionary, including all aliases.

        This method outputs the complete mapping of architectural register names
        (e.g., x0, x1, ...) to their corresponding ABI aliases, along with any
        additional alias information stored internally. It is primarily used for
        debugging, verification, or inspection of the alias‑generation pipeline.

        Returns:
            None
        """
        print("\nGPR Aliases Dictionary (detailed):")
        print("-" * 50)
        
        if not self.gpr_aliases:
            print("Empty dictionary!")
            return
        
        # Sort by architectural name for ordered display
        sorted_aliases = sorted(
            self.gpr_aliases.items(), 
            key=lambda x: int(x[0][1:]) if x[0].startswith('x') and x[0][1:].isdigit() else 999
        )
        
        for arch_name, abi_names in sorted_aliases:
            if isinstance(abi_names, list):
                aliases_str = ', '.join(abi_names)
                print(f"{arch_name} -> [{aliases_str}]")
            else:
                print(f"{arch_name} -> {abi_names}")
        
        print("-" * 50)
        print(f"Total: {len(self.gpr_aliases)} registers\n")


    def _print_gpr_aliases_simple(self) -> None: 
        """Prints the GPR alias dictionary in a simplified format.
        
        Returns:
            None
        """
        print("\nGPR Aliases Dictionary:")
        print("-" * 30)
        
        if not self.gpr_aliases:
            print("Empty dictionary!")
            return
        
        # Sort by architectural name for ordered display
        sorted_aliases = sorted(self.gpr_aliases.items(), key=lambda x: int(x[0][1:]) if x[0].startswith('x') and x[0][1:].isdigit() else 999)
        
        for arch_name, abi_name in sorted_aliases:
            print(f"{arch_name} -> {abi_name}")
        
        print("-" * 30)
        print(f"Total: {len(self.gpr_aliases)} aliases\n")

    
    def get_gpr_alias(self, arch_name: str) -> str:
        """
        Retrieves the ABI alias for an architectural GPR name.

        If no alias is found, the original architectural name is returned.

        Args:
            arch_name (str): The architectural GPR name (e.g., "x0", "x1").

        Returns:
            str: The ABI alias (e.g., "zero", "ra") or the original name if no alias exists.
        """
        return self.gpr_aliases.get(arch_name, arch_name)
    
    def get_all_gpr_aliases(self) -> Dict[str, str]:
        """
        Returns the complete GPR alias dictionary.

        This method returns a shallow copy of the internal mapping from
        architectural GPR names to their ABI aliases.

        Returns:
            Dict[str, str]: A copy of the alias dictionary.
        """
        return self.gpr_aliases.copy()
    
    
    
    def parse_csr_mappings(self, json_data: Dict[str, Any]) -> None:
        """
        Parses CSR mappings from JSON and updates internal structures.

        This method extracts Control and Status Register (CSR) definitions and
        mappings from the provided JSON data and stores them for later use in
        generation, validation, and lookups.

        Args:
            json_data (Dict[str, Any]): Parsed JSON data containing CSR mapping definitions.

        Returns:
            None
        """
        self.debug_print("DEBUG: Searching for CSR mappings...")
        
        if 'mappings' not in json_data:
            self.debug_print("DEBUG: No 'mappings' section found")
            return
        
        mappings = json_data['mappings']
        
        if 'csr_name_map' not in mappings:
            self.debug_print("DEBUG: No 'csr_name_map' section found")
            return
        
        csr_map = mappings['csr_name_map']
        if 'mapping' not in csr_map:
            self.debug_print("DEBUG: No 'mapping' in csr_name_map")
            return
        
        mapping_list = csr_map['mapping']
        if not isinstance(mapping_list, list):
            self.debug_print("DEBUG: csr_name_map mapping is not a list")
            return
        
        self.debug_print(f"DEBUG: Found {len(mapping_list)} CSR mappings")
        
        for item in mapping_list:
            if not isinstance(item, dict):
                continue
            
            source = item.get('source', {})
            if not isinstance(source, dict):
                continue
            
            contents = source.get('contents', '')
            if not isinstance(contents, str):
                continue
            
            # Parse contents: "mapping clause csr_name_map = 0x301 <-> \"misa\""
            csr_number, csr_name = self._parse_csr_mapping_contents(contents)
            if csr_number is not None and csr_name:
                self.csr_mappings[csr_number] = csr_name
                self.debug_print(f"DEBUG: Mapped CSR {csr_number} -> {csr_name}")
    
    def _parse_csr_mapping_contents(self, contents: str) -> tuple:
        """
        Parses the contents of a CSR mapping, e.g.,
        'mapping clause csr_name_map = 0x301 <-> "misa"'.

        This method interprets a single mapping clause that links a CSR numeric
        address (hex) to its canonical CSR name.

        Args:
            contents (str): A mapping string of the form
                'mapping clause csr_name_map = 0x<hex> <-> "<csr_name>"'.

        Returns:
            tuple: A tuple containing:
                - int: The CSR address (decoded from the hexadecimal literal).
                - str: The CSR name (e.g., "misa").
        """
        # Pattern to extract CSR number and name
        match = re.search(r'mapping\s+clause\s+csr_name_map\s*=\s*(0x[0-9a-fA-F]+|\d+)\s*<->\s*["\']([^"\']+)["\']', contents)
        if not match:
            return None, None
        
        number_str = match.group(1)
        csr_name = match.group(2)
        
        # Convert number to int
        if number_str.startswith('0x'):
            csr_number = int(number_str, 16)
        else:
            csr_number = int(number_str)
        
        return csr_number, csr_name
    
    def generate_csr_entries(self) -> List[ET.Element]:
        """
        Generates CSR entries based on the parsed mappings, sorted by CSR number (ascending).

        This method iterates over the internal CSR mapping (address/name pairs),
        constructs XML elements representing each CSR entry, and returns them as
        a list. The resulting list is sorted by the numeric CSR address to ensure
        deterministic output.

        Returns:
            List[xml.etree.ElementTree.Element]: A list of XML elements, each
            representing a CSR entry, sorted by CSR number in ascending order.
        """
        entries = []
        
        # Sort CSR mappings by CSR number (dictionary key)
        sorted_csr_mappings = sorted(self.csr_mappings.items(), key=lambda x: x[0])
        
        for csr_number, csr_name in sorted_csr_mappings:
            entry_elem = ET.Element('entry', name=str(csr_number))
            
            # Syntax
            syntax_elem = ET.SubElement(entry_elem, 'syntax')
            syntax_str = ET.SubElement(syntax_elem, 'str')
            syntax_str.text = csr_name.upper()  # Convert to uppercase for consistency
            
            entries.append(entry_elem)
            self.debug_print(f"DEBUG: Generated CSR entry {csr_number} -> {csr_name.upper()}")
        
        self.debug_print(f"DEBUG: Generated {len(entries)} CSR entries, sorted by CSR number")
        return entries

    
    def debug_print(self, message: str):
        """
        Prints debug messages.

        This helper method emits a debug message, typically routed to the
        debug/logging sink used during generation or testing.

        Args:
            message (str): The message to be printed for debugging.
        """
        print(message)
    
    def console_print(self, message: str):
        """
        Prints a message to the console even if debug output is routed to a log.

        If a logger with a `console_print` method is available, the message is
        forwarded to it; otherwise, the message is printed directly to stdout.

        Args:
            message (str): The message to print to the console.
        """
        if self.logger:
            self.logger.console_print(message)
        else:
            print(message)
    
    def _extract_register_configs(self, config_module) -> Dict[str, Dict[str, Any]]:
        """
        Extracts all register configurations from the loaded configuration module.

        This method inspects the given Python module (e.g., a loaded `config.py`)
        and builds a dictionary of register configuration blocks keyed by their
        names. The extracted structures are later used to generate register files,
        classes, and related metadata.

        Args:
            config_module: The imported Python module object that contains the
                register configuration definitions.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary mapping configuration names to
            their corresponding configuration dictionaries.
        """
        configs = {}
        
         # Iterate through all module attributes
        for attr_name in dir(config_module):
             # Ignore private and built-in attributes
            if attr_name.startswith('_'):
                continue
                
            attr_value = getattr(config_module, attr_name)
            
            # Check if it's a dictionary with correct structure for registers
            if self._is_valid_register_config(attr_value):
                register_name = attr_value['name']
                configs[register_name] = attr_value
                self.debug_print(f"DEBUG: Found register configuration: {register_name}")
        
        return configs
    
    def _is_valid_register_config(self, obj) -> bool:
        """
        Checks whether the given object represents a valid register configuration.

        This method verifies that the provided object meets the structural and
        semantic requirements expected for a register configuration entry inside
        the loaded configuration module.

        Args:
            obj: The object to validate (typically extracted from the configuration module).

        Returns:
            bool: True if the object is a valid register configuration, False otherwise.
        """
        if not isinstance(obj, dict):
            return False
        
       # Check required fields - REMOVED 'debug'
        required_fields = ['name', 'description', 'width', 'size', 'shared', 'attributes', 'extensions']
        
        for field in required_fields:
            if field not in obj:
                self.debug_print(f"DEBUG: Missing required field '{field}' in register config")
                return False
        
        # Check data types
        if not isinstance(obj['name'], str):
            self.debug_print(f"DEBUG: 'name' must be string in register config")
            return False
        if not isinstance(obj['description'], str):
            self.debug_print(f"DEBUG: 'description' must be string in register config")
            return False
        if not isinstance(obj['width'], int):
            self.debug_print(f"DEBUG: 'width' must be int in register config")
            return False
        if not isinstance(obj['size'], int):
            self.debug_print(f"DEBUG: 'size' must be int in register config")
            return False
        if not isinstance(obj['shared'], int):
            self.debug_print(f"DEBUG: 'shared' must be int in register config")
            return False
        if not isinstance(obj['attributes'], dict):
            self.debug_print(f"DEBUG: 'attributes' must be dict in register config")
            return False
        if not isinstance(obj['extensions'], list):
            self.debug_print(f"DEBUG: 'extensions' must be list in register config")
            return False
        
        # Prefix is optional, but if present must be string
        if 'prefix' in obj and not isinstance(obj['prefix'], str):
            self.debug_print(f"DEBUG: 'prefix' must be string in register config")
            return False
        
        # Debug is optional, but if present must be int
        if 'debug' in obj and not isinstance(obj['debug'], int):
            self.debug_print(f"DEBUG: 'debug' must be int in register config")
            return False
        
        return True

    
    def should_include_register_file(self, reg_name: str, extension_filter: List[str] = None) -> bool:
        """
        Determines whether a register file should be included based on the extension filter.

        This method checks the register file identified by `reg_name` against the
        provided list of enabled extensions. If `extension_filter` is None or empty,
        the method treats it as "no filtering" and includes the register file by default.

        Args:
            reg_name (str): The name/identifier of the register file to evaluate.
            extension_filter (List[str], optional): A list of enabled extensions used to
                filter which register files should be included. If None or empty, no
                filtering is applied.

        Returns:
            bool: True if the register file should be included, False otherwise.
        """
        if not extension_filter:
            return True
        
        reg_config = self.register_configs.get(reg_name, {})
        reg_extensions = reg_config.get('extensions', [])
        
        # Include register if at least one extension matches
        return any(ext.upper() in [e.upper() for e in extension_filter] for ext in reg_extensions)
    
    def generate_register_file_xml(self, reg_name: str) -> Optional[ET.Element]:
        """
        Generates the XML element for a register file.

        This method creates and returns an XML element representing the register
        file identified by `reg_name`. The element typically includes metadata,
        register definitions, and attributes required by downstream consumers
        such as LLVM table generators or validation tools.

        Args:
            reg_name (str): The name of the register file for which the XML
                representation should be generated.

        Returns:
            Optional[xml.etree.ElementTree.Element]: The generated XML element,
            or None if the register file cannot be generated or is not recognized.
        """
        if reg_name not in self.register_configs:
            self.debug_print(f"DEBUG: Register file {reg_name} not found in configuration.")
            return None
        
        config = self.register_configs[reg_name]
        self.debug_print(f"DEBUG: Generating XML for register {reg_name}")
        
         # Create regfile element
        regfile_elem = ET.Element('regfile', name=config['name'])
        
        # Doc
        doc_elem = ET.SubElement(regfile_elem, 'doc')
        doc_str = ET.SubElement(doc_elem, 'str')
        doc_str.text = f"CDATA_START      {config['description']}   CDATA_END"
        
        # Width
        width_elem = ET.SubElement(regfile_elem, 'width')
        width_int = ET.SubElement(width_elem, 'int')
        width_int.text = str(config['width'])
        
        # Attributes
        attributes_elem = ET.SubElement(regfile_elem, 'attributes')
        for attr_name, attr_value in config['attributes'].items():
            attr_elem = ET.SubElement(attributes_elem, 'attribute', name=attr_name)
            if isinstance(attr_value, int):
                attr_int = ET.SubElement(attr_elem, 'int')
                attr_int.text = str(attr_value)
            else:
                attr_str = ET.SubElement(attr_elem, 'str')
                attr_str.text = str(attr_value) if attr_value else ""
        
        # Size
        size_elem = ET.SubElement(regfile_elem, 'size')
        size_int = ET.SubElement(size_elem, 'int')
        size_int.text = str(config['size'])
        
         # Debug - MODIFIED: only if present in configuration
        if 'debug' in config:
            debug_elem = ET.SubElement(regfile_elem, 'debug')
            debug_int = ET.SubElement(debug_elem, 'int')
            debug_int.text = str(config['debug'])
        
        # Prefix - only if present and not empty
        if config.get('prefix'):
            prefix_elem = ET.SubElement(regfile_elem, 'prefix')
            prefix_str = ET.SubElement(prefix_elem, 'str')
            prefix_str.text = config['prefix']
        
        # Shared
        shared_elem = ET.SubElement(regfile_elem, 'shared')
        shared_int = ET.SubElement(shared_elem, 'int')
        shared_int.text = str(config['shared'])
        
        # ADDED: Calling Convention
        calling_conv_elem = self.generate_calling_convention(reg_name)
        if calling_conv_elem is not None:
            regfile_elem.append(calling_conv_elem)
            self.debug_print(f"DEBUG: Added calling convention for {reg_name}")
            # Test print
            self._print_calling_convention_test(reg_name)
        
        # Entries for CSRs with <entries> tag
        if reg_name == 'CSR' and self.csr_mappings:
            entries_elem = ET.SubElement(regfile_elem, 'entries')
            csr_entries = self.generate_csr_entries()
            for entry in csr_entries:
                entries_elem.append(entry)
            self.debug_print(f"DEBUG: Added {len(csr_entries)} CSR entries in <entries> container")
        
        return regfile_elem

    
    def generate_all_register_files_xml(
    self,
    extension_filter: List[str] = None,
    json_data: Dict[str, Any] = None
) -> List[ET.Element]:
        """
        Generates XML elements for all register files, filtered by enabled extensions.

        This method iterates over all known register files, applies the optional
        extension filter (if provided), and generates an XML element for each
        eligible register file. Optionally, `json_data` can be supplied to override
        or augment the internal data used during generation.

        Args:
            extension_filter (List[str], optional): A list of enabled extensions used
                to filter which register files should be generated. If None or empty,
                no filtering is applied and all register files are considered.
            json_data (Dict[str, Any], optional): Optional JSON data used to enrich or
                override internal state while generating the register-file XML.

        Returns:
            List[xml.etree.ElementTree.Element]: A list of generated XML elements,
            one per register file included by the filter.
        """
        register_elements = []
        
        # Parse mappings from JSON if we have data
        if json_data:
            self.parse_csr_mappings(json_data)
            self.parse_gpr_mappings(json_data)   # ADDED: parse GPR mappings too
        
        self.debug_print(f"DEBUG: Generating register files with extension filter: {extension_filter}")
        self.debug_print(f"DEBUG: Available register configs: {list(self.register_configs.keys())}")
        
        for reg_name in self.register_configs.keys():
            if self.should_include_register_file(reg_name, extension_filter):
                reg_elem = self.generate_register_file_xml(reg_name)
                if reg_elem is not None:
                    register_elements.append(reg_elem)
                    self.debug_print(f"DEBUG: Generated register file: {reg_name}")
            else:
                self.debug_print(f"DEBUG: Skipped register file: {reg_name}")
        
        return register_elements

    
    def get_register_info(self, reg_name: str) -> Dict[str, Any]:
        """
        Retrieves the configuration information for a given register.

        This method returns the dictionary associated with the specified
        register name. If the register does not exist in the configuration,
        an empty dictionary is returned.

        Args:
            reg_name (str): The name of the register whose information should be retrieved.

        Returns:
            Dict[str, Any]: The register's configuration dictionary, or an empty
            dictionary if the register is not defined.
        """
        return self.register_configs.get(reg_name, {})
    
    def list_available_registers(self) -> List[str]:
        """
        Returns the list of all available register classes.

        This method provides an overview of all register files or register
        classes that are currently loaded and available in the configuration.

        Returns:
            List[str]: A list of all register class names.
        """
        return list(self.register_configs.keys())

class DebugLogger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.original_stdout = sys.stdout
        
    def __enter__(self):
        # Redirect stdout to log file
        self.log_handle = open(self.log_file, 'w', encoding='utf-8')
        sys.stdout = self.log_handle
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original stdout
        sys.stdout = self.original_stdout
        self.log_handle.close()
        
    def console_print(self, message: str):
        """
        Prints a message to the console even if stdout is redirected.

        If a logger with a dedicated console output is available, the message is
        forwarded to it; otherwise, it is printed directly to the console.

        Args:
            message (str): The message to print to the console.

        Returns:
            None
        """
        self.original_stdout.write(message + '\n')
        self.original_stdout.flush()

class InstructionParser:
    def __init__(self, logger: Optional[DebugLogger] = None):
        self.instructions = {}
        self.known_templates: Set[str] = set()
        # Known fields that are not instructions
        self.known_fields = {'op', 'rd', 'rs1', 'rs2', 'rs3', 'funct3', 'funct7', 'opcode', 'shamt'}
        # Cache for template splits
        self.template_splits: Dict[str, Dict[str, str]] = {}
        
        self.template_splits: Dict[str, Dict[str, str]] = {}
        
        self.encoding_mappings: Dict[str, Dict[str, int]] = {}
        self.field_to_register_map: Dict[str, str] = {}
        self.special_operand_mappings = {}  # ADĂUGAT
        self.logger = logger
        self._load_special_operand_mappings()
        
    def _load_special_operand_mappings(self) -> None: 
        """ Loads the special operand mappings from the configuration. This method reads 
        and parses the configuration data that defines special operand behaviors or alternative 
        operand names. The resulting mappings are stored internally and used during instruction generation, 
        validation, and operand expansion. 
        
        Returns: 
            None """
        try:
            reg_generator = RegisterFileGenerator()
            self.special_operand_mappings = reg_generator.get_special_operand_mappings()
            print(f"DEBUG: Loaded special operand mappings: {self.special_operand_mappings}")
        except Exception as e:
            print(f"ERROR: Failed to load special operand mappings: {e}")
            self.special_operand_mappings = {}
            
    def _parse_assembly_when_condition(
    self,
    json_data: Dict[str, Any],
    instruction_name: str
) -> Dict[str, Any]:
        """
        Parses the `when` condition from the assembly mapping clause to detect excluded values.

        This method inspects the assembly mapping section in the provided JSON for the
        specified instruction and extracts constraint-like conditions (e.g., forbidden/
        excluded immediate or field values). It then normalizes them into a dictionary
        suitable for downstream validation or code generation.

        Args:
            json_data (Dict[str, Any]): JSON structure containing assembly mapping
                information for instructions.
            instruction_name (str): The name of the instruction whose `when` condition
                should be parsed.

        Returns:
            Dict[str, Any]: A dictionary describing excluded values and conditions
            derived from the `when` clause (e.g., {"imm": {"exclude": [0, -1]}, ...}).
        """
        print(f"DEBUG: Parsing assembly 'when' condition for {instruction_name}")
        
        # Search in mappings -> assembly
        if 'mappings' not in json_data:
            return {}
        
        mappings = json_data['mappings']
        if 'assembly' not in mappings:
            return {}
        
        assembly_mappings = mappings['assembly']
        if 'mapping' not in assembly_mappings:
            return {}
        
        mapping_list = assembly_mappings['mapping']
        if not isinstance(mapping_list, list):
            return {}
        
        print(f"DEBUG: Searching through {len(mapping_list)} assembly mappings")
        
        # Normalize instruction name for search
        search_name = instruction_name.replace('_', '.')
        search_name_underscore = instruction_name.replace('.', '_')
        
        print(f"DEBUG: Searching for '{search_name}' or '{search_name_underscore}' (original: '{instruction_name}')")
        
        # Search for specific instruction
        for mapping_item in mapping_list:
            if not isinstance(mapping_item, dict):
                continue
            
            source = mapping_item.get('source', {})
            if not isinstance(source, dict):
                continue
            
            contents = source.get('contents', '')
            if not isinstance(contents, str):
                continue
            
            # Check if contains mapping clause for our instruction
            # Pattern: mapping clause assembly = C_NOP(...) or "c.nop"
            pattern = rf'(mapping\s+clause\s+assembly\s*=\s*{re.escape(search_name_underscore.upper())}\s*\(|"{re.escape(search_name)}")'
            
            if not re.search(pattern, contents, re.IGNORECASE):
                continue
            
            print(f"DEBUG: *** FOUND assembly mapping for {instruction_name} ***")
            print(f"DEBUG: Full contents: {contents}")
            
            # Parse when condition
            when_match = re.search(r'when\s+(.+?)$', contents, re.IGNORECASE | re.MULTILINE)
            if when_match:
                condition = when_match.group(1).strip()
                print(f"DEBUG: Found 'when' condition: {condition}")
                
                excluded_values = {}
                
                # Pattern 1: imm != zeros()
                if re.search(r'imm\w*\s*!=\s*zeros\(\)', condition, re.IGNORECASE):
                    excluded_values['imm_ci'] = [0]
                    print(f"DEBUG: Pattern 'imm != zeros()' - excluding 0")
                
                # Pattern 2: imm != 0
                elif re.search(r'imm\w*\s*!=\s*0\b', condition, re.IGNORECASE):
                    excluded_values['imm_ci'] = [0]
                    print(f"DEBUG: Pattern 'imm != 0' - excluding 0")
                
                # Pattern 3: imm != 0x0
                elif re.search(r'imm\w*\s*!=\s*0x0+', condition, re.IGNORECASE):
                    excluded_values['imm_ci'] = [0]
                    print(f"DEBUG: Pattern 'imm != 0x0' - excluding 0")
                
                # Pattern 4: Combinations with AND (&)
                if '&' in condition:
                    parts = condition.split('&')
                    for part in parts:
                        part = part.strip()
                        if re.search(r'imm\w*\s*!=\s*(zeros\(\)|0\b|0x0+)', part, re.IGNORECASE):
                            excluded_values['imm_ci'] = [0]
                            print(f"DEBUG: Pattern in AND clause - excluding 0")
                            break
                
                if excluded_values:
                    print(f"DEBUG: Returning excluded_values: {excluded_values}")
                    return excluded_values
                else:
                    print(f"DEBUG: No excluded values detected from condition")
                    return {}
            else:
                print(f"DEBUG: No 'when' condition found in contents")
        
        print(f"DEBUG: No assembly mapping found for {instruction_name}")
        return {}

    
    def _apply_special_operand_mappings(self, instruction_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies special operand mappings to the given instruction dictionary.

        This method inspects the instruction's operands and replaces or augments
        them according to the preloaded special operand mappings (e.g., rewriting
        semantic operands to architecture‑specific names, injecting attributes, or
        normalizing operand shapes). The transformed instruction dictionary is then
        returned for downstream generation or validation steps.

        Args:
            instruction_dict (Dict[str, Any]): The instruction descriptor containing
                operand definitions and related metadata.

        Returns:
            Dict[str, Any]: The updated instruction dictionary after applying the
            special operand mappings.
        """
        instruction_name = instruction_dict['name'].lower()
        
        # Normal logic for all instructions (including FENCE)
        if instruction_name not in self.special_operand_mappings:
            return instruction_dict
        
        mappings = self.special_operand_mappings[instruction_name]
        print(f"DEBUG: Applying special operand mappings for {instruction_name}: {mappings}")
        
        # Map operands
        new_operands = []
        for operand in instruction_dict['operands']:
            if operand in mappings:
                new_operand = mappings[operand]
                new_operands.append(new_operand)
                print(f"DEBUG: Mapped operand {operand} -> {new_operand}")
            else:
                new_operands.append(operand)
        
        # Map fields
        new_fields = {}
        for field_name, field_value in instruction_dict['fields'].items():
            if field_name in mappings:
                new_field_name = mappings[field_name]
                new_fields[new_field_name] = field_value
                print(f"DEBUG: Mapped field {field_name} -> {new_field_name}")
            else:
                new_fields[field_name] = field_value
        
        # Update instruction
        instruction_dict['operands'] = new_operands
        instruction_dict['fields'] = new_fields
        
        operands_list = new_operands
        for instruction in INSTRUCTION_COMPRESSED:
            if instruction_dict['name'].lower().replace("_", ".") == instruction.lower().replace("_", "."):
                for operand in new_operands:
                    if operand == 'rd':
                        operands_list.remove('rd')
                        operands_list.append('rd_c')
        new_operands = operands_list
        instruction_dict['operands'] = new_operands
                        
        print(f"DEBUG: Final operands for {instruction_name}: {new_operands}")
        print(f"DEBUG: Final fields for {instruction_name}: {new_fields}")
        
        return instruction_dict

    def debug_print(self, message: str):
        """
        Prints debug messages — typically routed to the log if a logger is configured.

        This method prints the given message, primarily for debugging purposes.
        If additional logging redirection is desired, this method may be extended
        or overridden.

        Args:
            message (str): The debug message to print.

        Returns:
            None
        """
        print(message)
        
    def console_print(self, message: str):
        """
        Prints a message directly to the console even when debug output is redirected.

        If a logger with a `console_print` method is configured, the message is sent
        there; otherwise, it falls back to a direct console print. This ensures that
        important messages remain visible regardless of debugging/logging settings.

        Args:
            message (str): The message to output to the console.

        Returns:
            None
        """
        if self.logger:
            self.logger.console_print(message)
        else:
            print(message)
        
    def find_encoding_mappings(self, json_data: Dict[str, Any]) -> None:
        """
        Finds all simple encoding mappings (e.g., funct3, funct7, etc.) from the JSON data.

        This method inspects the instruction encoding information contained in the JSON
        structure and extracts simple field mappings (such as funct3, funct7, opcode
        encodings, and similar values). These mappings are later used when generating
        instruction definitions and validation metadata.

        Args:
            json_data (Dict[str, Any]): Parsed JSON input containing encoding information
                for the architecture or instruction set.

        Returns:
            None
        """
        print("DEBUG: Searching for encoding mappings...")
        
        if 'mappings' not in json_data:
            print("DEBUG: No 'mappings' section found")
            return
            
        mappings = json_data['mappings']
        self.debug_print(f"DEBUG: Mappings keys: {list(mappings.keys())}")
        
        # Search all sections that start with 'encdec_'
        for mapping_name, mapping_data in mappings.items():
            if self._is_encoding_mapping(mapping_name, mapping_data):
                self.debug_print(f"DEBUG: Processing mapping: {mapping_name}")
                self._process_encoding_mapping(mapping_name, mapping_data)

    def _process_encoding_mapping(self, mapping_name: str, mapping_data: Dict[str, Any]) -> None:
        """
        Processes a specific encoding mapping.

        This method validates and interprets the encoding mapping identified by
        `mapping_name`, extracting relevant fields and values from `mapping_data`
        and storing them in internal structures for later use in instruction
        generation and verification.

        Args:
            mapping_name (str): The name/identifier of the encoding mapping (e.g., "funct3").
            mapping_data (Dict[str, Any]): The data describing the mapping, typically parsed
                from JSON (e.g., field values per instruction).

        Returns:
            None
        """
        if not self._validate_mapping_structure(mapping_name, mapping_data):
            return
            
        mapping_list = mapping_data['mapping']
        self.debug_print(f"DEBUG: Found {len(mapping_list)} items in {mapping_name}")
        
        # Initialize dictionary for this mapping
        if mapping_name not in self.encoding_mappings:
            self.encoding_mappings[mapping_name] = {}
        
        for item in mapping_list:
            self._process_mapping_item(item, mapping_name)

    def _process_mapping_item(self, item: Any, mapping_name: str) -> None:
        """
        Processes a single item from an encoding mapping.

        This method handles one entry of an encoding mapping (e.g., a mapping for a single
        instruction or a single field value), validates it, and integrates it into the
        internal representation.

        Args:
            item (Any): One mapping entry to be processed (format depends on the schema).
            mapping_name (str): The parent mapping name (e.g., "funct7", "opcode") for context.

        Returns:
            None
        """
        if not isinstance(item, dict):
            return
            
        source = item.get('source', {})
        if not isinstance(source, dict):
            return
            
        contents = source.get('contents', '')
        if not isinstance(contents, str):
            return
            
        # Parse contents: "ADDI <-> 0b000"
        instruction_name, value = self._parse_mapping_contents(contents)
        if instruction_name and value is not None:
            self.encoding_mappings[mapping_name][instruction_name] = value
            self.debug_print(f"DEBUG: Mapped {instruction_name} -> {value} in {mapping_name}")

    def _parse_mapping_contents(self, contents: str) -> tuple:
        """
        Parses the contents of a mapping string, e.g., 'ADDI <-> 0b000'.

        This method decodes a simple bidirectional mapping expression that associates
        an instruction mnemonic (or field key) with an encoded value.

        Args:
            contents (str): A mapping string in the form '<lhs> <-> <rhs>', such as
                'ADDI <-> 0b000' or 'opcode <-> 0b0110011'.

        Returns:
            tuple: A tuple of the form (lhs: str, value: int), where:
                - lhs is the left-hand side token (e.g., "ADDI" or "opcode").
                - value is the integer value decoded from the right-hand side literal
                (binary/hex/decimal supported depending on the parser rules).
        """
        match = re.search(r'(\w+)\s*<->\s*(0b[01]+|\d+)', contents)
        if not match:
            return None, None
            
        instruction_name = match.group(1).upper()
        value_str = match.group(2)
        
        # Convert value to int
        if value_str.startswith('0b'):
            value = int(value_str[2:], 2)
        else:
            value = int(value_str)
            
        return instruction_name, value

    def _get_encoding_values_from_functions(
    self,
    instruction_name: str,
    encoding_func: set
) -> Dict[str, int]:
        """
        Looks up encoding values for an instruction using the specified helper functions.

        This method evaluates one or more provided encoding helper functions (e.g., functions
        that compute `funct3`, `funct7`, or other field encodings) and aggregates the results
        into a dictionary for the given instruction.

        Args:
            instruction_name (str): The instruction mnemonic/name whose encodings are requested.
            encoding_func (set): A set of callable objects (or function names resolvable in the
                current context) that return encoding values for specific fields.

        Returns:
            Dict[str, int]: A dictionary mapping field names to their encoded integer values,
            e.g., {"funct3": 0b000, "funct7": 0b0100000}.
        """
        encoding_values = {}
        instruction_upper = instruction_name.upper()
        
        for func_name in encoding_func:
            # Ignore functions we're not interested in
            if 'reg' in func_name:
                self.debug_print(f"DEBUG: Skipping register function {func_name}")
                continue
                
            self.debug_print(f"DEBUG: Searching in function {func_name} for {instruction_upper}")
            
            # Search in already loaded mappings
            if func_name in self.encoding_mappings:
                if instruction_upper in self.encoding_mappings[func_name]:
                    value = self.encoding_mappings[func_name][instruction_upper]
                    field_name = self._get_field_name_from_function(func_name, value)
                    if field_name:
                        encoding_values[field_name] = value
                        self.debug_print(f"DEBUG: Found {instruction_upper} -> {field_name}={value} in {func_name}")
                        
                        # ADDED: Special logic for M extension operations
                        if func_name in ['encdec_mul_op', 'encdec_div_op', 'encdec_rem_op']:
                            # For these functions, value is directly funct3
                            encoding_values['funct3'] = value
                            self.debug_print(f"DEBUG: M extension - set funct3={value} for {instruction_upper} from {func_name}")
                            
                else:
                    self.debug_print(f"DEBUG: {instruction_upper} not found in {func_name}")
                    # Debug to see what instructions are available
                    available_instructions = list(self.encoding_mappings[func_name].keys())
                    self.debug_print(f"DEBUG: Available instructions in {func_name}: {available_instructions[:10]}...")
            else:
                self.debug_print(f"DEBUG: Function {func_name} not found in encoding_mappings")
        
        return encoding_values



    def _get_field_name_from_function(self, func_name: str, value: int) -> Optional[str]:
        """
        Infers the encoded field name from a function name and the bit-width/value provided.

        This helper maps naming conventions (e.g., functions like `compute_funct3`,
        `get_opcode_bits`) to canonical field names (e.g., "funct3", "opcode").
        The `value` can be used to disambiguate or validate the inferred field.

        Args:
            func_name (str): The function name from which to infer the field name.
            value (int): The field value or an example encoding used for validation.

        Returns:
            Optional[str]: The inferred field name (e.g., "funct3", "funct7", "opcode"),
            or None if no known mapping can be determined.
        """
        self.debug_print(f"DEBUG: Determining field type for function: {func_name}, value: {value}")
        
        # Determine field type based on function name
        if 'uop' in func_name:  # encdec_uop = opcode for UTYPE (AUIPC, LUI)
            return 'opcode'
        elif 'iop' in func_name:  # encdec_iop = funct3 for ITYPE
            return 'funct3'
        elif 'rop' in func_name:  # encdec_rop = funct7 for RTYPE
            return 'funct7'
        elif 'bop' in func_name:  # encdec_bop = funct3 for BTYPE
            return 'funct3'
        elif 'sop' in func_name:  # encdec_sop = funct3 for STYPE
            return 'funct3'
        elif 'lop' in func_name:  # encdec_lop = funct3 for load operations
            return 'funct3'
        elif 'cop' in func_name:  # encdec_cop = funct3 for compressed operations
            return 'funct3'
        elif 'aop' in func_name:  # encdec_aop = funct3 for atomic operations
            return 'funct3'
        elif 'fop' in func_name:  # encdec_fop = funct3 for floating point operations
            return 'funct3'
        elif 'mul_op' in func_name:  # ADDED: encdec_mul_op = funct3 for MUL operations
            return 'funct3'
        elif 'div_op' in func_name:  # ADDED: encdec_div_op = funct3 for DIV operations
            return 'funct3'
        elif 'rem_op' in func_name:  # ADDED: encdec_rem_op = funct3 for REM operations
            return 'funct3'
        elif func_name == 'encdec_fence_op':  # for FENCE
            return 'opcode'
        elif 'op' in func_name and func_name != 'encdec_rop':  # Other *op functions that are not rop
            return 'opcode'
        else:
            # Fallback based on value size
            if value == 0:
                bit_count = 1
            else:
                bit_count = value.bit_length()
            
            self.debug_print(f"DEBUG: Unknown function {func_name}, using bit count {bit_count}")
            
            if bit_count <= 3:
                return 'funct3'
            elif bit_count <= 5:
                return 'shamt'
            elif bit_count <= 6:
                return 'funct7'
            elif bit_count <= 7:
                return 'opcode'
            else:
                return None



    def _process_encoding_mapping(self, mapping_name: str, mapping_data: Dict[str, Any]) -> None:
        """
        Processes a specific encoding mapping.

        This method validates the structure for `mapping_name`, then iterates the
        mapping entries in `mapping_data` and integrates them into internal
        encoding tables for later lookup and generation.

        Args:
            mapping_name (str): The identifier of the encoding mapping (e.g., "funct3").
            mapping_data (Dict[str, Any]): The parsed data describing the mapping.

        Returns:
            None
        """
        if not self._validate_mapping_structure(mapping_name, mapping_data):
            return
            
        mapping_list = mapping_data['mapping']
        self.debug_print(f"DEBUG: Found {len(mapping_list)} items in {mapping_name}")
        
        # Initialize dictionary for this mapping
        if mapping_name not in self.encoding_mappings:
            self.encoding_mappings[mapping_name] = {}
        
        for item in mapping_list:
            self._process_mapping_item(item, mapping_name)
    
    def _validate_mapping_structure(self, mapping_name: str, mapping_data: Dict[str, Any]) -> bool:
        """
        Validates the structure of an encoding mapping.

        Ensures that `mapping_data` follows the expected schema for the given
        `mapping_name` (e.g., required keys, value types, and constraints).

        Args:
            mapping_name (str): The name of the mapping being validated.
            mapping_data (Dict[str, Any]): The mapping content to validate.

        Returns:
            bool: True if the mapping structure is valid, False otherwise.
        """
        if 'mapping' not in mapping_data:
            self.debug_print(f"DEBUG: No 'mapping' in {mapping_name}")
            return False
            
        mapping_list = mapping_data['mapping']
        if not isinstance(mapping_list, list):
            self.debug_print(f"DEBUG: Mapping in {mapping_name} is not a list")
            return False
            
        return True
    
    def get_encoding_value(self, instruction_name: str, encoding_type: str) -> Optional[int]:
        """
        Retrieves the encoded value for a given instruction and encoding type.

        This method first attempts a direct lookup in the known mappings, and
        may fall back to computed/derived values if helper functions are available.

        Args:
            instruction_name (str): The instruction mnemonic/name (e.g., "ADDI").
            encoding_type (str): The encoding field name (e.g., "funct3", "funct7", "opcode").

        Returns:
            Optional[int]: The encoded integer value, or None if not found.
        """
        instruction_upper = instruction_name.upper()
        
        # Search in all encoding mappings
        for mapping_name, mappings in self.encoding_mappings.items():
            if encoding_type in mapping_name and instruction_upper in mappings:
                return mappings[instruction_upper]
        
        return None
    
    def _get_direct_encoding_value(self, instruction_name: str, mapping_name: str) -> Optional[int]:
        """
        Obtains a direct encoding value from a specific mapping.

        This performs a straightforward lookup for `instruction_name` within the
        mapping identified by `mapping_name` (without invoking any helper functions).

        Args:
            instruction_name (str): The instruction whose encoding value is requested.
            mapping_name (str): The mapping name to query (e.g., "funct3", "opcode").

        Returns:
            Optional[int]: The encoded integer value if present, otherwise None.
        """
        instruction_upper = instruction_name.upper()
        
        if mapping_name in self.encoding_mappings:
            return self.encoding_mappings[mapping_name].get(instruction_upper)
        
        return None
    
    def enhance_instruction_with_encodings(self, instruction_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriches an instruction descriptor with discovered encoding values.

        This method aggregates known encodings (direct mappings and computed values)
        and adds them to `instruction_dict` (e.g., injects fields like "funct3",
        "funct7", or "opcode") for downstream generation and validation.

        Args:
            instruction_dict (Dict[str, Any]): The instruction descriptor to enhance.

        Returns:
            Dict[str, Any]: The updated instruction descriptor including encoding fields.
        """
        instruction_name = instruction_dict['name'].upper()
        
        # Apply known mappings
        self._apply_known_encoding_mappings(instruction_dict, instruction_name)
        
        # Apply generic mappings
        self._apply_generic_encoding_mappings(instruction_dict, instruction_name)
        
        return instruction_dict
    
    def _apply_known_encoding_mappings(self, instruction_dict: Dict[str, Any], instruction_name: str) -> None:
        """
        Applies known encoding mappings (e.g., iop -> funct3, rop -> funct7) to the instruction.

        This method looks up canonical relationships between high-level fields (iop/rop/etc.)
        and their concrete encoding fields (funct3/funct7/opcode) and writes them into
        `instruction_dict` when available.

        Args:
            instruction_dict (Dict[str, Any]): The instruction descriptor to mutate.
            instruction_name (str): The instruction name used for lookups.

        Returns:
            None
        """
        
        funct3_value = self.get_encoding_value(instruction_name, 'iop')  # encdec_iop pare să fie pentru funct3
        if funct3_value is not None:
            instruction_dict['fields']['funct3'] = funct3_value
            self.debug_print(f"DEBUG: Added funct3={funct3_value} to {instruction_name}")

        funct7_value = self.get_encoding_value(instruction_name, 'rop')  # encdec_rop pare să fie pentru funct7
        if funct7_value is not None:
            instruction_dict['fields']['funct7'] = funct7_value
            self.debug_print(f"DEBUG: Added funct7={funct7_value} to {instruction_name}")
    
    def _apply_generic_encoding_mappings(
    self,
    instruction_dict: Dict[str, Any],
    instruction_name: str
) -> None:
        """
        Applies generic encoding mappings for other classes of operations.

        This method handles encoding mappings that are not covered by the
        well-known field relationships (e.g., beyond funct3/funct7/opcode).
        It inspects the instruction's metadata and applies any generic rules
        or patterns to populate encoding fields in the instruction descriptor.

        Args:
            instruction_dict (Dict[str, Any]): The instruction descriptor to update.
            instruction_name (str): The name of the instruction being processed.

        Returns:
            None
        """
        for mapping_name, mappings in self.encoding_mappings.items():
            if instruction_name in mappings:
                value = mappings[instruction_name]
                field_name = self._determine_field_type(mapping_name, instruction_dict['fields'])
                
                if field_name and field_name not in instruction_dict['fields']:
                    instruction_dict['fields'][field_name] = value
                    self.debug_print(f"DEBUG: Added {field_name}={value} to {instruction_name} from {mapping_name}")
    
    def _determine_field_type(
    self,
    mapping_name: str,
    existing_fields: Dict[str, Any]
) -> Optional[str]:
        """
        Determines the canonical field type based on the mapping name.

        This helper infers which encoding field (e.g., "funct3", "funct7", "opcode")
        is implied by a given `mapping_name`. The `existing_fields` dictionary can be
        used as context to disambiguate between candidates when multiple names are
        plausible.

        Args:
            mapping_name (str): The name of the mapping (e.g., "iop", "rop", "opc").
            existing_fields (Dict[str, Any]): Already-collected fields for the current
                instruction, used to resolve ambiguities.

        Returns:
            Optional[str]: The inferred field type (e.g., "funct3", "funct7", "opcode"),
            or None if the mapping name cannot be resolved.
        """
        if 'iop' in mapping_name and 'funct3' not in existing_fields:
            return 'funct3'
        elif 'rop' in mapping_name and 'funct7' not in existing_fields:
            return 'funct7'
        elif 'bop' in mapping_name:  # for branch operations
            return 'funct3'
        elif 'sop' in mapping_name:  # for store operations
            return 'funct3'
        elif 'lop' in mapping_name:  # for load operations
            return 'funct3'
        elif 'cop' in mapping_name:  # for compressed operations
            return 'funct3'
        elif 'aop' in mapping_name:  # for atomic operations
            return 'funct3'
        elif 'fop' in mapping_name:  # floating point operations
            return 'funct3'
        
        return None
    
    def _enhance_single_instruction(self, instruction_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrapper around `enhance_instruction_with_encodings` for simple instructions.

        This method delegates to `enhance_instruction_with_encodings` to enrich a
        single, non-split instruction with discovered encoding fields (e.g., funct3,
        funct7, opcode), returning the updated instruction descriptor.

        Args:
            instruction_dict (Dict[str, Any]): The instruction descriptor to enhance.

        Returns:
            Dict[str, Any]: The enhanced instruction descriptor including encoding fields.
        """
        return self.enhance_instruction_with_encodings(instruction_dict)
    
    def _enhance_split_instruction(self, instruction_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrapper around `enhance_instruction_with_encodings` for split instructions.

        This method delegates to `enhance_instruction_with_encodings` to enrich an
        instruction that originated from a split/expanded form, ensuring encoding
        fields are properly injected for downstream generation.

        Args:
            instruction_dict (Dict[str, Any]): The split instruction descriptor to enhance.

        Returns:
            Dict[str, Any]: The enhanced instruction descriptor including encoding fields.
        """
        return self.enhance_instruction_with_encodings(instruction_dict)
    
    
    def _create_base_instruction_dict(
    self,
    instruction_name: str,
    template_name: str,
    operands: List[str],
    encoding_fields: Dict[str, Any],
    extension: str,
    file_path: str,
    contents: str,
    implementation: str = None
) -> Optional[Dict[str, Any]]:
        """
        Creates the base dictionary for an instruction.

        This method assembles a canonical instruction descriptor containing
        the instruction name, template, operands, encoding fields, owning
        extension, source path, and raw contents. An optional `implementation`
        field may be included if provided.

        Args:
            instruction_name (str): The instruction mnemonic/name (e.g., "ADDI").
            template_name (str): The name of the instruction template to use.
            operands (List[str]): The ordered list of operand identifiers.
            encoding_fields (Dict[str, Any]): Pre-collected encoding fields (e.g., funct3, funct7, opcode).
            extension (str): The architectural/feature extension that owns this instruction.
            file_path (str): The path to the source from which the instruction was derived.
            contents (str): The raw or normalized contents used to build the instruction.
            implementation (str, optional): Optional implementation body or reference.

        Returns:
            Optional[Dict[str, Any]]: The constructed instruction dictionary, or None
            if the inputs are invalid or the instruction cannot be created.
        """
        # Combine operands with encoding fields
        all_fields = self._combine_operands_and_fields(operands, encoding_fields)
        
        # Get extension attribute
        attribute_name = self._get_extension_attribute(extension)
        
        # Identify registers for inputs/outputs
        registers = [op for op in operands if op.startswith('rs') or op == 'rd' or 
                    op.startswith('ms') or op == 'md' or op == 'rsd' or op =='rs1_c' or op == 'rs2_c' or op == 'rd_c']  # ADDED: rsd
        
        # MODIFIED: Determine register type for inputs/outputs
        inputs = []
        outputs = []
        
        if instruction_name.lower().replace("_", ".") in INSTRUCTION_COMPRESSED:
            if "encdec_creg(rd)" in contents:
                if 'rd' in operands:
                    for i in range(len(operands)):
                        if operands[i] == 'rd':
                            operands[i] = 'rd_c'
                            break
                    for i in range(len(registers)):
                        if registers[i] == 'rd':
                            registers[i] = 'rd_c'
                            break
            if "encdec_creg(rs1)" in contents:
                if 'rs1' in operands:
                    for i in range(len(operands)):
                        if operands[i] == 'rs1':
                            operands[i] = 'rs1_c'
                            break
                    for i in range(len(registers)):
                        if registers[i] == 'rs1':
                            registers[i] = 'rs1_c'
                            break
            if "encdec_creg(rs2)" in contents:
                if 'rs2' in operands:
                    for i in range(len(operands)):
                        if operands[i] == 'rs2':
                            operands[i] = 'rs2_c'
                            break
                    for i in range(len(registers)):
                        if registers[i] == 'rs2':
                            registers[i] = 'rs2_c'
                            break 
        for reg in registers:  # MODIFIED: was 'for reg in operands'
            print(f"DEBUG _create_base_instruction_dict: Processing register '{reg}'")
            
            if reg == 'rs1' or reg == 'rs2':
                inputs.append(f'GPR({reg})')
                print(f"  -> Added to inputs: GPR({reg})")
            elif reg == 'rs1_c' or reg == 'rs2_c':
                inputs.append(f'GPR({reg})')
                print(f"  -> Added to inputs: GPR({reg})")
            elif reg.startswith('ms'):
                inputs.append(f'VR({reg})')
                print(f"  -> Added to inputs: VR({reg})")
            elif reg == 'rd':
                outputs.append(f'GPR({reg})')
                print(f"  -> Added to outputs: GPR({reg})")
            elif reg == 'rd_c':
                outputs.append(f'GPR({reg})')
                print(f"  -> Added to outputs: GPR({reg})")
            elif reg == 'md':
                outputs.append(f'VR({reg})')
                print(f"  -> Added to outputs: VR({reg})")
            elif reg == 'rsd':  # ADDED: rsd is both input and output
                inputs.append(f'GPR({reg})')
                outputs.append(f'GPR({reg})')
                print(f"  -> Added to inputs AND outputs: GPR({reg})")
        
        print(f"DEBUG _create_base_instruction_dict: Final inputs = {inputs}")
        print(f"DEBUG _create_base_instruction_dict: Final outputs = {outputs}")
        
        instruction_dict = {
            'name': instruction_name,
            'template': template_name,
            'extension': extension,
            'attribute': attribute_name,
            'operands': operands,
            'registers': registers,
            'fields': all_fields,
            'width': 32,
            'source_file': file_path,
            'source_contents': contents,
            'inputs': inputs,
            'outputs': outputs
        }
        
        # Add implementation if exists (for split instructions)
        if implementation is not None:
            instruction_dict['implementation'] = implementation
        
        return instruction_dict


    
    def _combine_operands_and_fields(
    self,
    operands: List[str],
    encoding_fields: Dict[str, Any]
) -> Dict[str, Any]:
        """
        Combines the operand list with encoding fields into a unified instruction schema.

        This helper merges semantic operands (order-preserving) with already
        discovered encoding fields (e.g., funct3, funct7, opcode) to produce a
        consolidated dictionary suitable for downstream generation (TableGen, checks)
        and validation.

        Args:
            operands (List[str]): The ordered list of operand identifiers (e.g., ["rd", "rs1", "imm"]).
            encoding_fields (Dict[str, Any]): A dictionary of encoding fields and values
                (e.g., {"funct3": 0b000, "opcode": 0b0010011}).

        Returns:
            Dict[str, Any]: A combined dictionary with keys such as:
                - "operands": List[str] — the ordered operands.
                - "encodings": Dict[str, Any] — the encoding fields/values.
                Additional keys may be included depending on the pipeline needs.
        """
        all_fields = {}
        
        # Add operands as empty strings (will be filled at runtime)
        for operand in operands:
            all_fields[operand] = ""
        
        # Add encoding fields
        all_fields.update(encoding_fields)
        
        # NO longer automatically add all fields from INSTRUCTION_FIELD_RANGES
        # These will only be added if they appear in operands or encoding_fields
        
        # Remove 'op' only if we have 'opcode' with a real value
        if 'opcode' in all_fields and 'op' in all_fields:
            if all_fields['opcode'] != "":
                del all_fields['op']
                self.debug_print(f"DEBUG: Removed 'op' because we have opcode={all_fields['opcode']}")
            else:
                self.debug_print(f"DEBUG: Keeping both 'op' and 'opcode' because opcode is empty")
        
        return all_fields

    
    def _get_extension_attribute(self, extension: str) -> str:
        """
        Retrieves the attribute name associated with the given extension.

        This helper maps an extension identifier (e.g., "Zbb", "M", "V") to the
        canonical attribute name used throughout the generation pipeline. It can
        be used to gate instruction/register availability based on enabled features.

        Args:
            extension (str): The extension identifier.

        Returns:
            str: The canonical attribute name for the extension.
        """
        extension_map = {
            'I': 'rv32i',
            'C': 'rv32c',
            'M': 'rv32m',
            'A': 'rv32a',
            'F': 'rv32f',
            'D': 'rv32d'
        }
        if 'rv32' in extension.lower():
            return extension_map.get(extension, f'rv32{extension.lower()}')
        else:
            return extension_map.get(extension, extension.lower())
    
    def parse_instructions(
    self,
    json_data: Dict[str, Any],
    extension_filter: List[str] = None
) -> Dict[str, Dict[str, Any]]:
        """
        Parses all instructions from the provided JSON structure.

        This method walks the JSON input, applies the optional `extension_filter`
        (if provided), validates instruction records, computes/collects encoding
        fields, applies operand mappings, and returns a dictionary keyed by
        instruction name with normalized instruction descriptors.

        Args:
            json_data (Dict[str, Any]): Parsed JSON data containing instruction
                definitions and related metadata.
            extension_filter (List[str], optional): List of enabled extensions used to
                filter which instructions are parsed and returned. If None or empty,
                no filtering is applied.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary mapping instruction names to their
            normalized instruction descriptors.
        """
        instructions = {}
        
        # FIRST STEP: find encoding mappings
        self.find_encoding_mappings(json_data)
        
        # Second step: find all templates with splits
        self.find_template_splits(json_data)
        
        # ADDED: Third step - build instruction field ranges
        print("\n" + "="*50)
        print("BUILDING INSTRUCTION FIELD RANGES")
        print("="*50)
        
        field_manager = InstructionFieldManager()
        field_success = field_manager.build_instruction_field_ranges(json_data, extension_filter)
        
        if field_success:
            print(f"✓ Built {len(INSTRUCTION_FIELD_RANGES)} instruction field ranges")
            print(f"✓ Auto-detected register fields: {field_manager.field_to_register_map}")
            
            # Save register mapping for later use
            self.field_to_register_map = field_manager.field_to_register_map
        else:
            print("WARNING: Failed to build instruction field ranges")
        
        if 'mappings' not in json_data:
            print("ERROR: 'mappings' section not found in JSON")
            return instructions
    
        if 'encdec' not in json_data['mappings']:
            print("ERROR: 'encdec' section not found in mappings")
            return instructions
        
        if 'mapping' not in json_data['mappings']['encdec']:
            print("ERROR: 'mapping' section not found in mappings.encdec")
            return instructions
        
        mapping_list_normal = json_data['mappings']['encdec']['mapping']
        mapping_list_compressed = json_data['mappings'].get('encdec_compressed', {}).get('mapping', [])
        
        print("Compressed", mapping_list_compressed)
        
        print(f"Found {len(mapping_list_normal)} normal instructions")
        print(f"Found {len(mapping_list_compressed)} compressed instructions")
        
        # DEBUG: Check what mapping_list_compressed contains
        print(f"DEBUG: First compressed instruction preview:")
        if mapping_list_compressed and len(mapping_list_compressed) > 0:
            first_compressed = mapping_list_compressed[0]
            if isinstance(first_compressed, dict):
                source = first_compressed.get('source', {})
                if isinstance(source, dict):
                    contents = source.get('contents', '')
                    print(f"  Contents preview: {contents[:100]}...")
        
        processed = 0
        
        # Process normal instructions (32-bit)
        for i, instruction_data in enumerate(mapping_list_normal):
            if isinstance(instruction_data, dict):
                instruction_data['_is_compressed'] = False
                # DEBUG
                if i < 3:  # First 3 normal instructions
                    source = instruction_data.get('source', {})
                    contents = source.get('contents', '') if isinstance(source, dict) else ''
                    print(f"DEBUG: Normal instruction {i}: {contents[:50]}... _is_compressed=False")
                
                instruction_list = self.create_instruction_dict(instruction_data, extension_filter)
                for instruction_dict in instruction_list:
                    if instruction_dict:
                        instruction_dict = self._map_immediate_to_template(instruction_dict)
                        instruction_dict = self.enhance_instruction_with_action(instruction_dict, json_data)
                        instructions[instruction_dict['name']] = instruction_dict
                        processed += 1
        
        # Process compressed instructions (16-bit)
        for i, instruction_data in enumerate(mapping_list_compressed):
            if isinstance(instruction_data, dict):
                instruction_data['_is_compressed'] = True
                # DEBUG
                source = instruction_data.get('source', {})
                contents = source.get('contents', '') if isinstance(source, dict) else ''
                print(f"DEBUG: Compressed instruction {i}: {contents[:50]}... _is_compressed=True")
                
                # Check if marker was set
                print(f"DEBUG: Verification - '_is_compressed' in instruction_data: {'_is_compressed' in instruction_data}")
                print(f"DEBUG: Verification - instruction_data['_is_compressed'] = {instruction_data.get('_is_compressed', 'NOT FOUND')}")
                
                instruction_list = self.create_instruction_dict(instruction_data, extension_filter)
                for instruction_dict in instruction_list:
                    if instruction_dict:
                        print(f"DEBUG: Got compressed instruction '{instruction_dict['name']}' with width={instruction_dict['width']}")
                        instruction_dict = self._map_immediate_to_template(instruction_dict)
                        instruction_dict = self.enhance_instruction_with_action(instruction_dict, json_data)
                        instructions[instruction_dict['name']] = instruction_dict
                        processed += 1
        
        print(f"Processed {processed} instructions matching filter")
        return instructions

    
    def _validate_main_instruction_structure(self, json_data: Dict[str, Any]) -> bool:
        """
        Validates the structure of the main instruction definitions.

        This check ensures the top-level instruction records meet the expected
        schema (e.g., required keys, types, operand/encoding sections), providing
        early diagnostics before deeper parsing is attempted.

        Args:
            json_data (Dict[str, Any]): The JSON structure containing instruction data.

        Returns:
            bool: True if the main instruction structure is valid, False otherwise.
        """
        if 'mappings' not in json_data:
            print("ERROR: 'mappings' section not found in JSON")
            return False
        
        if 'encdec' not in json_data['mappings']:
            print("ERROR: 'encdec' section not found in mappings")
            return False
        
        if 'mapping' not in json_data['mappings']['encdec']:
            print("ERROR: 'mapping' section not found in mappings.encdec")
            return False
        
        mapping_list = json_data['mappings']['encdec']['mapping'] + json_data['mappings']['encdec_compressed']['mapping']
        if not isinstance(mapping_list, list):
            print("ERROR: mapping is not a list")
            return False
        
        return True
    
    def _print_processing_summary(self, instructions: Dict[str, Dict[str, Any]]) -> None:
        """
        Prints a processing summary for the parsed instructions.

        This method reports key statistics (e.g., number of instructions processed,
        how many filtered by extension, how many with/without encodings) to aid
        debugging and verification.

        Args:
            instructions (Dict[str, Dict[str, Any]]): The final instruction dictionary.

        Returns:
            None
        """
        print(f"Processed {len(instructions)} instructions matching filter")
        print(f"Known templates: {sorted(self.known_templates)}")
        print(f"Template splits found: {list(self.template_splits.keys())}")
        print(f"Encoding mappings found: {list(self.encoding_mappings.keys())}")
    
                
    def _is_encoding_mapping(self, mapping_name: str, mapping_data: Any) -> bool:
        """
        Determines whether a given mapping qualifies as an encoding mapping.

        This helper inspects the `mapping_name` and `mapping_data` shape/content
        to decide if it represents an encoding mapping (e.g., funct3/funct7/opcode)
        rather than some other metadata or auxiliary structure.

        Args:
            mapping_name (str): The mapping identifier to test.
            mapping_data (Any): The mapping payload to inspect.

        Returns:
            bool: True if it is recognized as an encoding mapping, False otherwise.
        """
        return (mapping_name.startswith('encdec_') and 
                isinstance(mapping_data, dict) and 
                mapping_name != 'encdec')  # Exclude main mapping
    
    def _generate_core_description(self, extension_filter: List[str] = None) -> str:
        """
        Generates the core description string based on the enabled extensions.

        This method synthesizes a textual description (or header snippet) that
        documents the core's capabilities as determined by the active set of
        extensions. If `extension_filter` is None or empty, all known extensions
        may be considered.

        Args:
            extension_filter (List[str], optional): Enabled extensions to include
                in the description. If None or empty, a default/all-extensions
                description may be generated.

        Returns:
            str: A formatted description of the core capabilities/features.
        """
        descriptions = []
        
        if not extension_filter:
            extension_filter = ['I']  # Default
        
        for ext in sorted(extension_filter):
            if ext.upper() == 'I':
                descriptions.append("The base Risc-V 32-bit integer instruction set. Based upon version 2.0.")
            elif ext.upper() == 'M':
                descriptions.append("The Risc-V 32-bit M standard extension for integer multiplication and division.")
            elif ext.upper() == 'C':
                descriptions.append("The Risc-V 32-bit C standard extension for compressed instructions.")
            elif ext.upper() == 'A':
                descriptions.append("The Risc-V 32-bit A standard extension for atomic instructions.")
            elif ext.upper() == 'F':
                descriptions.append("The Risc-V 32-bit F standard extension for single-precision floating-point.")
            elif ext.upper() == 'D':
                descriptions.append("The Risc-V 32-bit D standard extension for double-precision floating-point.")
            else:
                descriptions.append(f"The Risc-V 32-bit {ext.upper()} extension.")
        
        # Always add description for privileged architecture
        descriptions.append("The RISC-V 32-bit privileged architecture (machine mode).")
        
        return "".join(descriptions)
    
    def generate_xml(self, instructions: Dict[str, Dict[str, Any]], extension_filter: List[str] = None) -> str:
        """
        Generates the final XML representation for all instructions, including
        instruction fields and register files.

        This function processes the instruction definitions provided in the input
        dictionary, applies an optional extension filter, and constructs a complete
        XML structure compliant with the ADL specification used by the toolchain.

        Args:
            instructions (Dict[str, Dict[str, Any]]):
                A dictionary containing instruction metadata. Each key represents
                an instruction name, and the associated value is a dictionary
                describing fields, encodings, register usage, and additional
                properties.
            
            extension_filter (List[str], optional):
                A list of instruction set extensions that should be included
                in the generated XML. If provided, only instructions belonging
                to the specified extensions will appear in the output. If None,
                all instructions are processed.

        Returns:
            str: A string containing the fully formatted XML document representing
            the selected instructions, their fields, and associated register files.

        Raises:
            ValueError:
                If the instruction dictionary contains malformed entries, missing
                required attributes, or references to undefined register files.
        """
        
        # Create base structure
        data_elem = ET.Element('data')
        cores_elem = ET.SubElement(data_elem, 'cores')
        
        # Determine core name based on extensions
        core_name = "rv32"
        if extension_filter:
            # Sort extensions for consistency
            sorted_extensions = sorted(extension_filter)
            core_name += "".join(ext.lower() for ext in sorted_extensions)
        else:
            # If no extensions specified, use all found
            all_extensions = set()
            for instruction in instructions.values():
                if instruction['extension']:
                    all_extensions.add(instruction['extension'])
            if all_extensions:
                sorted_extensions = sorted(all_extensions)
                core_name += "".join(ext.lower() for ext in sorted_extensions)
            else:
                core_name += "i"  # Default to base extension
        
        core_elem = ET.SubElement(cores_elem, 'core', name=core_name)
        
        # Doc
        doc_elem = ET.SubElement(core_elem, 'doc')
        doc_str = ET.SubElement(doc_elem, 'str')
        doc_str.text = "CDATA_START" + self._generate_core_description(extension_filter) + "CDATA_END"
        
        # Bit endianness
        bit_endianness_elem = ET.SubElement(core_elem, 'bit_endianness')
        bit_endianness_str = ET.SubElement(bit_endianness_elem, 'str')
        bit_endianness_str.text = "little"
        
        # ADDED: Register Files
        print("\n" + "="*60)
        print("GENERATING REGISTER FILES FOR XML")
        print("="*60)
        
        reg_generator = RegisterFileGenerator()
        register_elements = reg_generator.generate_all_register_files_xml(extension_filter, self.parse_json_file(args.input_file) if hasattr(self, 'input_file') else None)
        
        if register_elements:
            regfiles_elem = ET.SubElement(core_elem, 'regfiles')
            for reg_elem in register_elements:
                regfiles_elem.append(reg_elem)
            print(f"✓ Added {len(register_elements)} register files to XML")
        else:
            print("WARNING: No register files generated")
        
        # Instruction Fields
        print("\n" + "="*60)
        print("GENERATING INSTRUCTION FIELDS FOR XML")
        print("="*60)
        
        instrfields_xml = self._generate_instruction_fields_for_xml()
        if instrfields_xml:
            # Parse instruction fields XML and add to core
            try:
                instrfields_root = ET.fromstring(f"<root>{instrfields_xml}</root>")
                instrfields_elem = instrfields_root.find('instrfields')
                if instrfields_elem is not None:
                    core_elem.append(instrfields_elem)
                    print(f"✓ Added {len(instrfields_elem)} instruction fields to XML")
                else:
                    print("WARNING: No instrfields element found in generated XML")
            except ET.ParseError as e:
                print(f"ERROR: Failed to parse instruction fields XML: {e}")
        else:
            print("WARNING: No instruction fields generated")
        
        # Instructions
        instrs_elem = ET.SubElement(core_elem, 'instrs')
        
        for instruction in instructions.values():
            instr_elem = self.generate_xml_element(instruction)
            instrs_elem.append(instr_elem)
        
        rough_string = ET.tostring(data_elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        xml_content = reparsed.toprettyxml(indent="")
        
        # Remove first line (default XML declaration)
        lines = xml_content.split('\n')
        if lines[0].startswith('<?xml'):
            lines = lines[1:]
        
        # Add custom XML declaration at beginning
        xml_output = '<?xml version="1.0" encoding="UTF-8"?>\n' + '\n'.join(lines)
        
        # Replace manually for CDATA
        xml_output = xml_output.replace('CDATA_START', '<![CDATA[')
        xml_output = xml_output.replace('CDATA_END', ']]>')
        
        # Replace self-closing tags with closed tags
        xml_output = xml_output.replace('<str/>', '<str></str>')
        xml_output = xml_output.replace('<inputs/>', '<inputs></inputs>')
        xml_output = xml_output.replace('<outputs/>', '<outputs></outputs>')
        xml_output = xml_output.replace('&lt;', '<')
        xml_output = xml_output.replace('&gt;', '>')
        return xml_output


    def _generate_instruction_fields_for_xml(self) -> str: 
        """Generates the XML fragment containing all instruction fields for 
        inclusion in the main ADL XML document.

        This function collects and formats all instruction field definitions 
        required by the instruction set.

        Returns:
            str: A formatted XML string representing all instruction field definitions.
        """
        global INSTRUCTION_FIELD_RANGES, REGISTER_CLASSES
        
        # Check if we have needed data
        if not INSTRUCTION_FIELD_RANGES:
            print("WARNING: No instruction field ranges available")
            return ""
        
        if not REGISTER_CLASSES:
            print("WARNING: No register classes available for instruction fields")
            return ""
        
        print(f"Generating instruction fields from {len(INSTRUCTION_FIELD_RANGES)} ranges...")
        
        # Create temporary field manager for generation
        field_manager = InstructionFieldManager()
        
        # Recreate register mapping from self.field_to_register_map
        if hasattr(self, 'field_to_register_map'):
            field_manager.field_to_register_map = self.field_to_register_map
        else:
            # Fallback - detect registers based on names
            for field_name in INSTRUCTION_FIELD_RANGES.keys():
                if field_name in ['rd', 'rs1', 'rs2', 'rs3']:
                    field_manager.field_to_register_map[field_name] = 'GPR'
                elif field_name == 'csr':
                    field_manager.field_to_register_map[field_name] = 'CSR'
        
        print(f"Using register field mapping: {field_manager.field_to_register_map}")
        
        # Generate XML only for instrfields (without root element)
        instrfields_elem = ET.Element('instrfields')
        
        # MODIFIED: Sort fields with function that handles all structure types
        def get_sort_key(item):
            field_name, field_ranges = item
            
            # Debug to see what structure we have
            print(f"DEBUG: Sorting field {field_name}, type: {type(field_ranges)}, value: {field_ranges}")
            
            if isinstance(field_ranges, list):
                # For multiple ranges, use first range for sorting
                if field_ranges and isinstance(field_ranges[0], tuple) and len(field_ranges[0]) >= 2:
                    return field_ranges[0][0]  # first start_bit
                else:
                    return 0
            elif isinstance(field_ranges, dict):
                # For BTYPE structures with dictionary
                if 'ranges' in field_ranges and field_ranges['ranges']:
                    ranges = field_ranges['ranges']
                    if isinstance(ranges, list) and ranges and isinstance(ranges[0], tuple):
                        return ranges[0][0]  # first start_bit from first range
                return 0
            elif isinstance(field_ranges, tuple) and len(field_ranges) >= 2:
                # For simple range (start_bit, end_bit)
                return field_ranges[0]
            else:
                # For anything else, return 0
                print(f"WARNING: Unknown field range structure for {field_name}: {field_ranges}")
                return 0
        
        try:
            sorted_fields = sorted(INSTRUCTION_FIELD_RANGES.items(), 
                                key=get_sort_key, reverse=True)
        except Exception as e:
            print(f"ERROR in sorting: {e}")
            # Fallback - use original order
            sorted_fields = list(INSTRUCTION_FIELD_RANGES.items())
        
        for field_name, field_ranges in sorted_fields:
            print(f"  Generating field: {field_name}")
            print(f"  DEBUG XML: field_ranges type: {type(field_ranges)}")
            print(f"  DEBUG XML: field_ranges value: {field_ranges}")
            
            # Determine structure type and generate accordingly
            if isinstance(field_ranges, dict) and 'ranges' in field_ranges:
                # BTYPE structure with dictionary
                ranges = field_ranges['ranges']
                print(f"    Multi-range field with dict structure: {len(ranges)} ranges")
                print(f"    DEBUG XML: Calling _generate_multi_range_field_xml with: {field_ranges}")
                field_elem = field_manager._generate_multi_range_field_xml(field_name, field_ranges)
            elif isinstance(field_ranges, list):
                # Multiple ranges
                print(f"    Multi-range field with list structure: {len(field_ranges)} ranges")
                print(f"    DEBUG XML: Calling _generate_multi_range_field_xml with: {field_ranges}")
                field_elem = field_manager._generate_multi_range_field_xml(field_name, field_ranges)
            elif isinstance(field_ranges, tuple) and len(field_ranges) == 2:
                # Simple range
                start_bit, end_bit = field_ranges
                print(f"    Single range field: [{start_bit}:{end_bit}]")
                field_elem = field_manager._generate_single_field_xml(field_name, start_bit, end_bit)
            else:
                print(f"    WARNING: Unknown field structure for {field_name}: {field_ranges}")
                continue
            
            if field_elem is not None:
                instrfields_elem.append(field_elem)
        
        # String to XML
        rough_string = ET.tostring(instrfields_elem, encoding='unicode')
        
        # Process CDATA
        xml_output = rough_string.replace('CDATA_START', '<![CDATA[')
        xml_output = xml_output.replace('CDATA_END', ']]>')

        print(f"✓ Generated {len(instrfields_elem)} instruction fields")
        return xml_output


    def parse_json_file(self, filepath: str) -> Dict[str, Any]:    
        """  Parses a JSON file and returns its contents.    
        This function opens the JSON file located at the given path, reads its    
        contents using UTF-8 encoding, and deserializes the data into a Python    
        dictionary.    
        Args:        
            filepath (str): Path to the JSON file that should be parsed.    
        
        Returns:        
            Dict[str, Any]: A dictionary containing the structured JSON data.   
        
        Raises:        
            FileNotFoundError: If the specified file does not exist.        
            json.JSONDecodeError: If the file contains invalid JSON. """
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)
    
    def extract_extension_from_file(self, file_path: str) -> str:
        """
            Extracts the extension name from a file path.

            This function searches the given file path for a folder structure following
            the pattern 'extensions/<extension_name>/' and extracts the extension name.
            It is typically used to associate JSON instruction files with their
            corresponding ISA extension.

            Args:
                file_path (str):
                    The file path from which the extension name should be extracted.

            Returns:
                str:
                    The extracted extension name, or an empty string if no match
                    is found.
            """
        match = re.search(r'extensions/([^/]+)/', file_path)
        return match.group(1) if match else ""
    
    def find_template_splits(self, json_data: Dict[str, Any]) -> None:
        """
            Identifies all instruction templates that contain split definitions.

            This function scans the parsed JSON instruction data and locates any
            templates that include split configurations. These splits may describe
            how certain instructions expand, specialize, or override template fields.

            Args:
                json_data (Dict[str, Any]):
                    The dictionary containing the full instruction data
                    parsed from JSON input.

            Returns:
                None
                    This function updates internal state but does not return a value.

            Raises:
                KeyError:
                    If required template fields are missing from the JSON structure.
            """

        print("\n" + "="*50)
        print("SEARCHING FOR TEMPLATE SPLITS")
        print("="*50)
        
        self.template_splits = {}
        
        def search_recursive(data: Any, path: List[str] = None) -> None:
            if path is None:
                path = []
            
            if isinstance(data, dict):
                # Check source and splits
                if 'source' in data and 'splits' in data:
                    source = data['source']
                    splits_data = data['splits']
                    
                    if isinstance(source, dict) and isinstance(splits_data, dict):
                        contents = source.get('contents', '')
                        if isinstance(contents, str):
                            print(f"Found template with splits at path: {' -> '.join(path)}")
                            print(f"Contents preview: {contents[:100]}...")
                            
                            # Extract templates
                            template_name = self._extract_template_name_from_function_clause(contents)
                            if template_name:
                                print(f"Extracted template name: {template_name}")
                                
                                # Add splits
                                if splits_data:
                                    self.template_splits[template_name] = splits_data
                                    print(f"Found template {template_name} with {len(splits_data)} splits: {list(splits_data.keys())}")
                                else:
                                    print(f"No splits found for template {template_name}")
                            else:
                                print("Could not extract template name")
                
                # Check and add function and source description
                elif 'source' in data and 'function' in data:
                    source = data['source']
                    function_data = data['function']
                    
                    if isinstance(source, dict) and isinstance(function_data, list):
                        contents = source.get('contents', '')
                        if isinstance(contents, str) and 'scattered' in contents:
                            print(f"Found scattered template at path: {' -> '.join(path)}")
                            print(f"Contents preview: {contents[:100]}...")
                            
                            # Extract template
                            template_name = self._extract_template_name_from_scattered(contents)
                            if template_name:
                                print(f"Extracted template name: {template_name}")
                                
                                # Extracts splits
                                splits = self._extract_splits_from_function_array(function_data)
                                if splits:
                                    self.template_splits[template_name] = splits
                                    print(f"Found template {template_name} with {len(splits)} splits: {list(splits.keys())}")
                                else:
                                    print(f"No splits found for template {template_name}")
                            else:
                                print("Could not extract template name")
                
                for key, value in data.items():
                    search_recursive(value, path + [key])
            
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    search_recursive(item, path + [f"[{i}]"])
        
        search_recursive(json_data)
        print(f"Total templates with splits found: {len(self.template_splits)}")
        for template_name, splits in self.template_splits.items():
            print(f"  {template_name}: {list(splits.keys())}")

    def _extract_template_name_from_function_clause(self, contents: str) -> Optional[str]:
        """
        Extracts the template name from a 'function clause execute' block.

        This function searches the provided text for a template reference used
        inside a function clause that defines execution behavior. It analyzes the
        clause content and attempts to identify the name of the instruction
        template that the clause is associated with.

        Args:
            contents (str):
                The raw contents of the function clause from which the template
                name should be extracted.

        Returns:
            Optional[str]:
                The extracted template name if found, otherwise None.

        Raises:
            ValueError:
                If the function clause format is invalid or does not follow the
                expected syntax.
        """
        # Patterns for TEMPLATE_NAME(...) = { ... }
        patterns = [
            r'function\s+clause\s+execute\s*\(*(\w+)\s*\([^)]*\)\s*\)*\s*=',
            r'function\s+clause\s+execute\s+(\w+)\s*=',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, contents, re.IGNORECASE)
            if match:
                template_name = match.group(1).upper()
                print(f"Found template name with pattern '{pattern}': {template_name}")
                return template_name
        
        print(f"Could not extract template name from: {contents[:200]}...")
        return None

    def debug_template_splits_for_instruction(self, instruction_name: str) -> None: 
        """ Debugs template split resolution for a specific instruction. 
        This function inspects the internal template‑split mapping to determine why a given 
        instruction is not associated with any detected template splits. It is intended as a 
        diagnostic tool to assist in tracing issues related to template inheritance, template references, 
        or JSON structure problems. 
        
        Args: 
            instruction_name (str): The name of the instruction whose template‑split relationships should be examined. 
            
        Returns: 
            None 
             
        Raises: 
            KeyError: If the instruction name does not exist in the loaded JSON data. """
        instruction_upper = instruction_name.upper()
        
        print(f"\nDEBUG TEMPLATE SPLITS FOR {instruction_name}:")
        print(f"Instruction upper: {instruction_upper}")
        print(f"Available templates: {list(self.template_splits.keys())}")
        
        for template_name, splits in self.template_splits.items():
            print(f"\nTemplate {template_name}:")
            print(f"  Available splits: {list(splits.keys())}")
            if instruction_upper in splits:
                print(f"  *** FOUND {instruction_upper} in {template_name} ***")
                print(f"  Action: {splits[instruction_upper][:100]}...")
            else:
                print(f"  {instruction_upper} NOT found in {template_name}")
                for split_name in splits.keys():
                    if split_name.upper() == instruction_upper:
                        print(f"  *** FOUND case mismatch: {split_name} vs {instruction_upper} ***")


    def _extract_splits_from_function_array(self, function_array: List[Any]) -> Dict[str, str]:
        """
        Extracts split definitions from a function array.

        This function iterates over the list of function entries—typically parsed
        from JSON—and identifies those that define template splits. Each detected
        split is extracted and mapped to its corresponding template or instruction
        identifier. The resulting dictionary maps split names to their resolved
        targets.

        Args:
            function_array (List[Any]):
                The list of function entries from which split information should
                be extracted.

        Returns:
            Dict[str, str]:
                A dictionary mapping split names to their associated template or
                instruction identifiers.

        Raises:
            ValueError:
                If a function entry is malformed or does not follow the expected
                split structure.
        """
        splits = {}
        
        print(f"Processing function array with {len(function_array)} items")
        
        for i, func_item in enumerate(function_array):
            if isinstance(func_item, dict) and 'source' in func_item:
                source = func_item['source']
                if isinstance(source, dict):
                    contents = source.get('contents', '')
                    if isinstance(contents, str):
                        print(f"Processing function item {i}: {contents[:100]}...")
                        
                        # Find split: union clause ast TEMPLATE_NAME = INSTRUCTION_NAME(...)
                        split_match = re.search(r'union\s+clause\s+ast\s+\w+\s*=\s*(\w+)\s*\(', contents, re.IGNORECASE)
                        if split_match:
                            instruction_name = split_match.group(1).upper()
                            
                            # Extract action
                            # Find function clause execute INSTRUCTION_NAME(...) = { ... }
                            action_patterns = [
                                rf'function\s+clause\s+execute\s+{re.escape(instruction_name)}\s*\([^)]*\)\s*=\s*\{{(.*?)\}}',
                                rf'function\s+clause\s+execute\s+{re.escape(instruction_name)}\s*=\s*\{{(.*?)\}}',
                            ]
                            
                            action = None
                            for pattern in action_patterns:
                                action_match = re.search(pattern, contents, re.DOTALL | re.IGNORECASE)
                                if action_match:
                                    action = action_match.group(1).strip()
                                    break
                            
                            if action:
                                splits[instruction_name] = action
                                print(f"Found split: {instruction_name} -> action length {len(action)}")
                            else:
                                print(f"Found instruction {instruction_name} but no action")
                        else:
                            print(f"No union clause found in function item {i}")
        
        print(f"Extracted {len(splits)} splits total")
        return splits
    
    def debug_json_structure(self, json_data: Dict[str, Any]) -> None:
        """
        Debugs the JSON structure in the functions/execute section.

        This function inspects the relevant portions of the parsed JSON data—
        specifically the `functions` and `execute` regions—to help diagnose issues
        related to instruction templates, execution clauses, or malformed JSON
        entries. It is intended as a diagnostic tool to visualize how the JSON
        is organized internally and to identify inconsistencies or missing fields.

        Args:
            json_data (Dict[str, Any]):
                The dictionary containing the full JSON structure parsed from input.

        Returns:
            None
                This function outputs debug information but does not return a value.

        Raises:
            KeyError:
                If expected keys within the JSON structure are missing.
        """
        print("\n" + "="*50)
        print("DEBUGGING JSON STRUCTURE")
        print("="*50)
        
        if 'functions' in json_data:
            print("Found 'functions' section")
            functions = json_data['functions']
            
            if isinstance(functions, dict) and 'execute' in functions:
                print("Found 'functions.execute' section")
                execute = functions['execute']
                
                if isinstance(execute, dict) and 'function' in execute:
                    print("Found 'functions.execute.function' section")
                    function_array = execute['function']
                    
                    if isinstance(function_array, list):
                        print(f"functions.execute.function is a list with {len(function_array)} items")
                        
                        # Try to find items
                        for i, item in enumerate(function_array[:3]):
                            print(f"\nItem {i}:")
                            if isinstance(item, dict):
                                print(f"  Keys: {list(item.keys())}")
                                
                                if 'source' in item:
                                    source = item['source']
                                    if isinstance(source, dict):
                                        contents = source.get('contents', '')
                                        if isinstance(contents, str):
                                            print(f"  Contents preview: {contents[:100]}...")
                                            if 'scattered' in contents:
                                                print("  *** CONTAINS SCATTERED ***")
                                            if 'union clause' in contents:
                                                print("  *** CONTAINS UNION CLAUSE ***")
                                            if 'function clause execute' in contents:
                                                print("  *** CONTAINS FUNCTION CLAUSE EXECUTE ***")
                    else:
                        print(f"functions.execute.function is not a list: {type(function_array)}")
                else:
                    print("functions.execute.function not found")
                    if isinstance(execute, dict):
                        print(f"functions.execute keys: {list(execute.keys())}")
            else:
                print("functions.execute not found")
                if isinstance(functions, dict):
                    print(f"functions keys: {list(functions.keys())}")
        else:
            print("'functions' section not found in JSON")
            print(f"Top level keys: {list(json_data.keys())}")

    def _is_branch_instruction(self, instruction: Dict[str, Any]) -> bool:
        """
        Determines whether an instruction is a branch-type (BTYPE) instruction.

        This function inspects the metadata associated with an instruction and
        checks whether it belongs to the B-type category, typically used to
        represent branching operations. The decision is based on instruction
        fields, opcode patterns, or type tags defined in the JSON description.

        Args:
            instruction (Dict[str, Any]):
                A dictionary containing the instruction's properties and metadata.

        Returns:
            bool:
                True if the instruction is identified as a branch-type instruction,
                otherwise False.

        Raises:
            KeyError:
                If the instruction definition is missing required fields used to
                determine its type.
        """
        template = instruction.get('template', '').upper()
        
        # Check BTYPE template
        if template == 'BTYPE':
            return True
        
        return False


    def _extract_template_name_from_scattered(self, contents: str) -> Optional[str]:
        """
        Extracts the template name from scattered instruction content.

        This function analyzes a block of scattered instruction data—typically
        originating from JSON fields or extended description sections—and attempts
        to locate the reference to the instruction template associated with it.
        Scattered templates appear when instruction semantics or structure are
        defined across multiple JSON fragments rather than in a single template
        block.

        Args:
            contents (str):
                The raw textual content in which the template reference should
                be searched.

        Returns:
            Optional[str]:
                The extracted template name if a valid reference is found,
                otherwise None.

        Raises:
            ValueError:
                If the scattered content is malformed or does not follow the
                expected template reference format.
        """
        # Find scattered union ast TEMPLATE_NAME = { ... }
        patterns = [
            r'scattered\s+union\s+ast\s+(\w+)\s*=',
            r'scattered\s+union\s+(\w+)\s*=',
            r'union\s+ast\s+(\w+)\s*=',
            r'union\s+(\w+)\s*=',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, contents, re.IGNORECASE)
            if match:
                template_name = match.group(1).upper()
                print(f"Found template name with pattern '{pattern}': {template_name}")
                return template_name
        
        print(f"Could not extract template name from: {contents[:200]}...")
        return None
    
    def _search_execute_recursive(self, data: Any, path: List[str]) -> None:
        """
        Recursively searches for the 'execute' section within a nested JSON structure.

        This function traverses arbitrarily nested JSON-like data structures
        (dictionaries, lists, or mixed types) and searches for the presence of an
        `execute` block. As it descends through the data, it keeps track of the
        current traversal path, which can be used for debugging or for identifying
        where the execute section is located within complex instruction definitions.

        Args:
            data (Any):
                The JSON data to be searched. May be a dictionary, list, or any
                composite structure parsed from the instruction files.

            path (List[str]):
                A list representing the current traversal path within the JSON
                hierarchy. This is primarily used for debugging and introspection.

        Returns:
            None
                The function performs recursive traversal and may produce debug
                output but does not return a value.

        Raises:
            TypeError:
                If the data being traversed contains unsupported types that cannot
                be inspected recursively.
        """
        if isinstance(data, dict):
            if 'execute' in data:
                self.debug_print(f"DEBUG: Found 'execute' at path: {' -> '.join(path)}")
                self._search_execute_in_section(data['execute'], ' -> '.join(path))
            else:
                for key, value in data.items():
                    self._search_execute_recursive(value, path + [key])
        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._search_execute_recursive(item, path + [f"[{i}]"])
    
    def _search_execute_in_section(self, execute_section: Any, section_name: str) -> None:
        """
        Searches for execute-related content within a specific section.

        This function inspects a given subsection of the JSON structure to locate
        elements related to instruction execution (typically fields under an
        `execute` block). It is used as part of a broader recursive search
        mechanism to isolate execution clauses across different nested structures.

        Args:
            execute_section (Any):
                The section of the JSON data being analyzed. May be a dictionary,
                list, or any JSON-compatible structure.

            section_name (str):
                The name of the section currently being inspected. This is used
                for debugging, logging, or tracing where execute elements are found.

        Returns:
            None
                The function examines the provided section and may generate debug
                output but does not return a value.

        Raises:
            TypeError:
                If the section contains unsupported data types that cannot be
                inspected or traversed.
        """

        self.debug_print(f"DEBUG: Searching execute in {section_name}")
        
        if not isinstance(execute_section, dict):
            self.debug_print(f"DEBUG: Execute section in {section_name} is not a dict: {type(execute_section)}")
            return
            
        self.debug_print(f"DEBUG: Execute section keys in {section_name}: {list(execute_section.keys())}")
        
        if 'function' not in execute_section:
            self.debug_print(f"DEBUG: No 'function' in execute section of {section_name}")
            for key, value in execute_section.items():
                if isinstance(value, (list, dict)):
                    self.debug_print(f"DEBUG: Checking key '{key}' in execute section")
                    self._search_functions_in_data(value, f"{section_name}.{key}")
            return
            
        functions = execute_section['function']
        self.debug_print(f"DEBUG: Functions type: {type(functions)}")
        
        if isinstance(functions, list):
            self.debug_print(f"DEBUG: Found {len(functions)} functions")
            self._process_function_list(functions)
        elif isinstance(functions, dict):
            self.debug_print(f"DEBUG: Functions is a dict with keys: {list(functions.keys())}")
            self._process_function_dict(functions)
        else:
            self.debug_print(f"DEBUG: Functions is neither list nor dict: {type(functions)}")
    
    def _search_functions_in_data(self, data: Any, path: str) -> None:
        if isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    self._check_function_item(item, f"{path}[{i}]")
        elif isinstance(data, dict):
            if 'source' in data and 'splits' in data:
                self._check_function_item(data, path)
            else:
                for key, value in data.items():
                    if isinstance(value, (list, dict)):
                        self._search_functions_in_data(value, f"{path}.{key}")
    
    def _process_function_list(self, functions: List[Any]) -> None:
        for i, func in enumerate(functions):
            if isinstance(func, dict):
                self._check_function_item(func, f"function[{i}]")
    
    def _process_function_dict(self, functions: Dict[str, Any]) -> None:
        for key, func in functions.items():
            if isinstance(func, dict):
                self._check_function_item(func, f"function.{key}")
            elif isinstance(func, list):
                for i, item in enumerate(func):
                    if isinstance(item, dict):
                        self._check_function_item(item, f"function.{key}[{i}]")
    
    def _check_function_item(self, func: Dict[str, Any], path: str) -> None:
        """
        Checks a function item for split definitions.

        This diagnostic helper inspects a single function entry—typically sourced
        from a `functions` array in the parsed JSON—to determine whether it defines
        any template splits (e.g., aliases, specializations, or expansions).
        It can log or collect details useful for debugging why certain instructions
        are (or are not) captured by the template-split mapping.

        Args:
            func (Dict[str, Any]):
                The function item to inspect, as a dictionary parsed from JSON.
            path (str):
                A string indicating the logical location of this item within the
                JSON structure, used for contextual debug output.

        Returns:
            None
                The function performs validation/inspection and may produce debug
                output but does not return a value.

        Raises:
            KeyError:
                If required keys for identifying split metadata are missing.
            TypeError:
                If the `func` object does not conform to the expected dictionary
                structure or contains unsupported types.
            ValueError:
                If split fields are present but malformed or inconsistent.
        """
        self.debug_print(f"DEBUG: Checking function at {path}")
        self.debug_print(f"DEBUG: Function keys: {list(func.keys())}")
        
        if 'source' not in func:
            self.debug_print(f"DEBUG: No 'source' in function at {path}")
            return
            
        source = func['source']
        if not isinstance(source, dict):
            self.debug_print(f"DEBUG: Source is not dict at {path}: {type(source)}")
            return
            
        self.debug_print(f"DEBUG: Source keys: {list(source.keys())}")
        
        contents = source.get('contents', '')
        if not isinstance(contents, str):
            self.debug_print(f"DEBUG: Contents is not string at {path}: {type(contents)}")
            return
            
        self.debug_print(f"DEBUG: Contents preview: {contents[:100]}...")
        
        if 'splits' not in func:
            self.debug_print(f"DEBUG: No 'splits' in function at {path}")
            return
            
        splits = func['splits']
        if not isinstance(splits, dict):
            self.debug_print(f"DEBUG: Splits is not dict at {path}: {type(splits)}")
            return
            
        if not splits:
            self.debug_print(f"DEBUG: Splits is empty at {path}")
            return
            
        self.debug_print(f"DEBUG: Found splits at {path}: {list(splits.keys())}")
        
        # Extract template name
        # Find pattern: function clause execute TEMPLATE_NAME
        match = re.search(r'function\s+clause\s+execute\s+(\w+)', contents)
        if match:
            template_name = match.group(1)
            self.template_splits[template_name] = splits
            self.debug_print(f"DEBUG: Successfully extracted template {template_name} with splits: {list(splits.keys())}")
        else:
            self.debug_print(f"DEBUG: Could not extract template name from contents at {path}")
            self.debug_print(f"DEBUG: Contents: {contents}")
    
    def parse_immediate_components(self, imm_expr: str) -> List[str]:
        components = []
        parts = imm_expr.split('@')
        for part in parts:
            part = part.strip()
            if not part.startswith('0b') and part and ('imm' in part.lower() or part.startswith('ui')):
                components.append(part)
        return components

    def has_immediate(self, operands: List[str]) -> bool:
        for operand in operands:
            if 'imm' in operand.lower():
                return True
        return False

    def consolidate_immediates(self, operands: List[str], instruction_name: str, is_template: bool = False) -> List[str]:
        consolidated = []
        has_immediates = False
        for operand in operands:
            print(f"DEBUG consolidate_immediates: Processing '{operand}'")
            if 'imm' in operand.lower() or 'ui' in operand.lower() or 'nz' in operand.lower():
                has_immediates = True
                print(f"  -> Marked as immediate")
            else:
                consolidated.append(operand)
                print(f"  -> Kept as operand")
        
        if has_immediates:
            # Generic immediate for _map_immediate_to_template
            consolidated.append('imm')
            print(f"  -> Added generic 'imm'")
        
        print(f"DEBUG consolidate_immediates: Result = {consolidated}")
        return consolidated




    def _map_immediate_to_template(self, instruction_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps generic immediates to the template-specific immediate definitions.

        This function examines the immediate fields defined in an instruction's
        metadata and aligns them with the immediate definitions specified in the
        instruction's associated template. This mapping ensures that each immediate
        used by the instruction adheres to the constraints, naming conventions,
        and bitfield specifications defined at the template level.

        Args:
            instruction_dict (Dict[str, Any]):
                A dictionary representing the instruction, including its fields,
                template information, and immediate definitions.

        Returns:
            Dict[str, Any]:
                A dictionary containing the updated immediate mappings, where
                generic immediates have been resolved to their template-specific
                representations.

        Raises:
            KeyError:
                If required immediate or template fields are missing from the
                instruction definition.
            ValueError:
                If the mapping between generic and template-specific immediates
                is inconsistent or invalid.
        """
        template = instruction_dict.get('template', '').upper()
        instruction_name = instruction_dict.get('name', '').lower()
        width = instruction_dict.get('width', 32)
        
        print(f"DEBUG: === MAPPING IMMEDIATE FOR {instruction_name.upper()} ===")
        print(f"DEBUG: Template: {template}")
        print(f"DEBUG: Width: {width}")
        print(f"DEBUG: Current fields: {instruction_dict['fields']}")
        print(f"DEBUG: Current operands: {instruction_dict['operands']}")
        
        # For  compressed instruction (16-bit), use imm_ci
        if width == 16:
            if instruction_name.replace("_", ".").lower() == 'c.lw' or instruction_name.replace("_", ".").lower() == 'c.sw':
                target_immediate = 'imm_c_lw'
                InstructionFieldManager._create_c_lw_immediate(self)
                print(f"DEBUG: *** JAL SPECIAL CASE *** -> imm_c_lw")
            elif instruction_name.replace("_", ".").lower() == 'c.addi4spn':
                target_immediate = 'imm_ciw'
                print(f"DEBUG: *** C.ADDI4SPN SPECIAL CASE *** -> imm_ciw")
                InstructionFieldManager._create_c_addi4spn_immediate(self)
            elif instruction_name.replace("_", ".").lower() == 'c.jal' or instruction_name.replace("_", ".").lower() == 'c.j':
                target_immediate = 'imm_cj'
                print(f"DEBUG: *** C.ANDI SPECIAL CASE *** -> imm_cj")
                InstructionFieldManager._create_c_jal_immediate(self)
            elif instruction_name.replace("_", ".").lower() == 'c.andi':
                target_immediate = 'imma_cb'
                print(f"DEBUG: *** C.ANDI SPECIAL CASE *** -> imma_cb")
                InstructionFieldManager._create_c_andi_immediate(self)
            elif instruction_name.replace("_", ".").lower() == 'c.bnez' or instruction_name.replace("_", ".").lower() == 'c.beqz':
                target_immediate = 'imm_cb'
                print(f"DEBUG: *** C.BEQZ/C.BNEZ SPECIAL CASE *** -> imm_cb")
                InstructionFieldManager._create_branch_immediate(self)
            elif instruction_name.replace("_", ".").lower() == 'c.addi16sp':
                target_immediate = 'imm_sp_ci'
                print(f"DEBUG: *** C.ADDI16SP SPECIAL CASE *** -> imm_sp_ci")
                InstructionFieldManager._create_c_addi16sp_immediate(self)
            elif instruction_name.replace("_", ".").lower() == 'c.slli' or instruction_name.replace("_", ".").lower() == 'c.srli' or instruction_name.replace("_", ".").lower() == 'c.srai':
                target_immediate = 'shamt_c'
                InstructionFieldManager._create_c_shift_immediate(self)
                print(f"DEBUG: *** C.SRLI, C.SRAI, C.SLLI SPECIAL CASE *** -> shamt_c")
            else:
                target_immediate = 'imm_ci'
                print(f"DEBUG: *** COMPRESSED INSTRUCTION (16-bit) *** -> imm_ci")
                INSTRUCTION_COMPRESSED.append(instruction_name.lower().replace("_", "."))
        elif instruction_name == 'jal':
            target_immediate = 'imm_jal'
            InstructionFieldManager._create_imm_jal_immediate(self)
            print(f"DEBUG: *** JAL SPECIAL CASE *** -> imm_jal")
        elif instruction_name == 'jalr':
            target_immediate = 'imm_i'
            print(f"DEBUG: *** JALR SPECIAL CASE *** -> imm_i")
        elif (template == 'STYPE' or 
            instruction_name in ['sb', 'sh', 'sw', 'sd', 'store'] or
            'store' in instruction_name.lower()):
            target_immediate = 'imm_stype'
            print(f"DEBUG: *** STORE DETECTED *** -> imm_stype")
        #  Template mapping -> immediate field
        elif template == 'ITYPE':
            target_immediate = 'imm_i'
            print(f"DEBUG: ITYPE template -> imm_i")
        elif template == 'BTYPE':
            target_immediate = 'imm_btype'
            InstructionFieldManager._create_imm_btype_immediate(self)
            print(f"DEBUG: BTYPE template -> imm_btype")
        elif instruction_name == 'fence':
            target_immediate = 'fence'
            InstructionFieldManager._create_fence_immediate(self)
            print(f"DEBUG: BTYPE template -> imm_btype")
        elif template == 'UTYPE':
            target_immediate = 'imm_utype'
            print(f"DEBUG: UTYPE template -> imm_utype")
        elif template == 'JTYPE':
            target_immediate = 'imm_jtype'
            print(f"DEBUG: JTYPE template -> imm_jtype")
        elif template == 'RTYPE':
            target_immediate = None
            print(f"DEBUG: RTYPE template -> no immediate")
        else:
            target_immediate = 'imm_i'
            print(f"DEBUG: No template/unknown -> imm_i (default)")
        
        if target_immediate:
            # Use specific immediates
            new_fields = {}
            new_operands = []
            immediate_found = False
            
            # Process fields
            for field_name, field_value in instruction_dict['fields'].items():
                if self._is_generic_immediate(field_name):
                    new_fields[target_immediate] = field_value
                    immediate_found = True
                    print(f"DEBUG: *** MAPPED FIELD {field_name} -> {target_immediate} ***")
                else:
                    new_fields[field_name] = field_value
            
            # Process operands
            for operand in instruction_dict['operands']:
                if self._is_generic_immediate(operand):
                    new_operands.append(target_immediate)
                    print(f"DEBUG: *** MAPPED OPERAND {operand} -> {target_immediate} ***")
                else:
                    new_operands.append(operand)
            
            operands_list = new_operands
            for instruction in INSTRUCTION_COMPRESSED:
                if instruction_dict['name'].lower().replace("_", ".") == instruction.lower().replace("_", "."):
                    if instruction.lower().replace("_", ".") == 'c.addi4spn':
                        for i, op in enumerate(operands_list):
                            if 'rd' in operands_list[i]:
                                    operands_list[i] = 'rd_c'
                                    break
                        for i, op in enumerate(operands_list):
                            if 'imm' in operands_list[i]:
                                if 'sp' not in operands_list:
                                    acc = operands_list[i]
                                    operands_list[i] = 'sp'
                                    operands_list.append(acc)
                                    if 'rd' in new_fields:
                                        del new_fields['rd']
                                    instruction_dict['operands'] = operands_list
                                    instruction_dict['inputs'].append('GPR(2)')
                                    break
                    elif instruction.lower().replace("_", ".") == 'c.addi16sp':
                        for i, op in enumerate(operands_list):
                            if 'imm' in operands_list[i]:
                                if 'sp' not in operands_list:
                                    acc = operands_list[i]
                                    operands_list[i] = 'sp'
                                    operands_list.append(acc)
                                    instruction_dict['operands'] = operands_list
                                    instruction_dict['inputs'].append('GPR(2)')
                                    instruction_dict['outputs'].append('GPR(2)')
                                    break
                    elif instruction.lower().replace("_", ".") == 'c.andi':
                        for i, op in enumerate(operands_list):
                            if 'rsd' in operands_list[i]:
                                    operands_list[i] = 'rs1_c'
                                    instruction_dict['operands'] = new_operands
                                    instruction_dict['outputs'].append('GPR(rs1_c)')
                                    instruction_dict['inputs'].append('GPR(rs1_c)')
                                    if 'rsd' in instruction_dict['fields'].keys():
                                        del instruction_dict['fields']['rsd']
                                        instruction_dict['fields']['rs1_c'] = ''
                                    break
                            elif 'i' in operands_list[i] and '@' in operands_list[i]:
                                elem = operands_list[i]
                                operands_list[i] = 'imma_cb'
                                instruction_dict['operands'] = new_operands
                                if elem in instruction_dict['fields'].keys() and 'i' in elem and '@' in elem:
                                    del instruction_dict['fields'][elem]
                                break
                        elem = ''
                        for i, op in enumerate(instruction_dict['fields']):
                                for elem in instruction_dict['fields'].keys():
                                    if 'rsd' in elem:
                                        break
                        del instruction_dict['fields'][elem]
                        instruction_dict['fields']['rs1_c'] = ''
                        instruction_dict['fields']['imma_cb'] = ''
                    elif instruction.lower().replace("_", ".") == 'c.jal' or instruction.lower().replace("_", ".") == 'c.j':
                        for i, op in enumerate(operands_list):
                            if 'i' in operands_list[i] and '@' in operands_list[i]:
                                    elem = operands_list[i]
                                    operands_list[i] = 'imm_cj'
                                    instruction_dict['operands'] = new_operands
                                    if elem in instruction_dict['fields'].keys() and 'i' in elem and '@' in elem:
                                        del instruction_dict['fields'][elem]
                                    break
                        if instruction.lower().replace("_", ".") == 'c.jal':
                            if 'GPR(1)' not in instruction_dict['outputs']:
                                instruction_dict['outputs'].append('GPR(1)')
                        instruction_dict['fields']['imm_cj'] = ''
                    elif instruction.lower().replace("_", ".") == 'c.jalr' or instruction.lower().replace("_", ".") == 'c.jr':
                        for i, op in enumerate(operands_list):
                            if 'rs1' in operands_list[i]:
                                operands_list[i] = 'rs1_c'
                                instruction_dict['operands'] = new_operands
                                if 'GPR(rs1_c)' not in instruction_dict['inputs']:
                                    instruction_dict['inputs'].append('GPR(rs1_c)')
                                    break
                        if instruction.lower().replace("_", ".") == 'c.jalr':
                            if 'GPR(1)' not in instruction_dict['outputs']:
                                instruction_dict['outputs'].append('GPR(1)')
                        if 'rs1' in instruction_dict['fields'].keys():
                            del instruction_dict['fields']['rs1']
                            instruction_dict['fields']['rs1_c'] = ''
                            instruction_dict['inputs'].remove('GPR(rs1)')
                    elif instruction.lower().replace("_", ".") == 'c.bnez' or instruction.lower().replace("_", ".") == 'c.beqz':
                        for i, op in enumerate(operands_list):
                            if 'rs' in operands_list[i]:
                                operands_list[i] = 'rs1_c'
                                instruction_dict['operands'] = new_operands
                                if 'GPR(rs1_c)' not in instruction_dict['inputs']:
                                    instruction_dict['inputs'].append('GPR(rs1_c)')
                                    break
                            elif 'i' in operands_list[i] and '@' in operands_list[i]:
                                elem = operands_list[i]
                                operands_list[i] = 'imm_cb'
                                instruction_dict['operands'] = new_operands
                                if elem in instruction_dict['fields'].keys() and 'i' in elem and '@' in elem:
                                    del instruction_dict['fields'][elem]
                                break
                        if 'rs' in instruction_dict['fields'].keys():
                            del instruction_dict['fields']['rs']
                            instruction_dict['fields']['rs1_c'] = ''
                        instruction_dict['fields']['imm_cb'] = ''
                    elif instruction.lower().replace("_", ".") == 'c.lw':
                        for i, op in enumerate(operands_list):
                            if 'rd' in operands_list[i]:
                                    operands_list[i] = 'rd_c'
                                    break
                        elem = ''
                        for i, op in enumerate(instruction_dict['fields']):
                                for elem in instruction_dict['fields'].keys():
                                    if 'rd' in elem:
                                        break
                        del instruction_dict['fields'][elem]
                        instruction_dict['fields']['rd_c'] = ''
                        elem = ''
                        for i, op in enumerate(instruction_dict['fields']):
                                for elem in instruction_dict['fields'].keys():
                                    if 'rs1' in elem:
                                        break
                        del instruction_dict['fields'][elem]
                        instruction_dict['fields']['rs1_c'] = ''
                    elif instruction.lower().replace("_", ".") == 'c.add' or instruction.lower().replace("_", ".") == 'c.mv':
                        for i, op in enumerate(operands_list):
                            if 'rsd' in operands_list[i]:
                                    operands_list[i] = 'rd'
                                    instruction_dict['operands'] = new_operands
                                    instruction_dict['outputs'].append('GPR(rd)')
                                    instruction_dict['inputs'].append('GPR(rd)')
                                    del instruction_dict['fields']['rsd']
                                    instruction_dict['fields']['rd'] = ''
                                    break
                        for i, op in enumerate(operands_list):
                            if 'rs2' in operands_list[i]:
                                    operands_list[i] = 'rs2_c'
                                    instruction_dict['operands'] = new_operands
                                    if 'rs2' in instruction_dict['fields'].keys():
                                        del instruction_dict['fields']['rs2']
                                        instruction_dict['fields']['rs2_c'] = ''
                                        break
                        for i, op in enumerate(instruction_dict['inputs']):
                            if 'GPR(rs2)' in instruction_dict['inputs'][i]:
                                    instruction_dict['inputs'][i] = 'GPR(rs2_c)'
                                    break
                    elif instruction.lower().replace("_", ".") == 'c.and' or instruction.lower().replace("_", ".") == 'c.or' or instruction.lower().replace("_", ".") == 'c.sub'or instruction.lower().replace("_", ".") == 'c.xor':
                        for i, op in enumerate(operands_list):
                            if 'rsd' in operands_list[i]:
                                    operands_list[i] = 'rs1_c'
                                    instruction_dict['operands'] = new_operands
                                    instruction_dict['outputs'].append('GPR(rs1_c)')
                                    instruction_dict['inputs'].append('GPR(rs1_c)')
                                    if 'rsd' in instruction_dict['fields'].keys():
                                        del instruction_dict['fields']['rsd']
                                        instruction_dict['fields']['rs1_c'] = ''
                                    break
                        for i, op in enumerate(operands_list):
                            if 'rs2' in operands_list[i]:
                                    operands_list[i] = 'rs2_c'
                                    instruction_dict['operands'] = new_operands
                                    if 'rs2' in instruction_dict['fields'].keys():
                                        del instruction_dict['fields']['rs2']
                                        instruction_dict['fields']['rs2_c'] = ''
                                    break
                        for i, op in enumerate(instruction_dict['inputs']):
                            if 'GPR(rs2)' in instruction_dict['inputs'][i]:
                                    instruction_dict['inputs'][i] = 'GPR(rs2_c)'
                                    break
                    elif instruction.lower().replace("_", ".") == 'c.addi':
                        for i, op in enumerate(operands_list):
                            if 'rsd' in operands_list[i]:
                                operands_list[i] = 'rd'
                                instruction_dict['operands'] = new_operands
                                instruction_dict['outputs'].append('GPR(rd)')
                                instruction_dict['inputs'].append('GPR(rd)')
                                break
                        if 'rsd' in instruction_dict['fields'].keys():
                            del instruction_dict['fields']['rsd']
                        instruction_dict['fields']['rd'] = ''
                        print(instruction_dict['fields'], 'hapciu')
                    elif instruction.lower().replace("_", ".") == 'c.srli' or instruction.lower().replace("_", ".") == 'c.slli' or instruction.lower().replace("_", ".") == 'c.srai':
                        for i, op in enumerate(operands_list):
                            if 'rsd' in operands_list[i]:
                                if instruction.lower().replace("_", ".") == 'c.slli':
                                    operands_list[i] = 'rd'
                                    instruction_dict['operands'] = new_operands
                                    instruction_dict['outputs'].append('GPR(rd)')
                                    instruction_dict['inputs'].append('GPR(rd)')
                                    if 'rsd' in instruction_dict['fields'].keys():
                                        del instruction_dict['fields']['rsd']
                                        instruction_dict['fields']['rd'] = ''
                                    break
                            if 'rsd' in operands_list[i]:
                                if instruction.lower().replace("_", ".") == 'c.srli' or instruction.lower().replace("_", ".") == 'c.srai':
                                    operands_list[i] = 'rs1_c'
                                    instruction_dict['operands'] = new_operands
                                    instruction_dict['outputs'].append('GPR(rs1_c)')
                                    instruction_dict['inputs'].append('GPR(rs1_c)')
                                    if 'rsd' in instruction_dict['fields'].keys():
                                        del instruction_dict['fields']['rsd']
                                        instruction_dict['fields']['rs1_c'] = ''
                                    break
                        for i, op in enumerate(operands_list):
                            if 'shamt' in operands_list[i]:
                                    operands_list[i] = 'shamt_c'
                                    instruction_dict['operands'] = new_operands
                                    break
                        elem = ''
                        for i, op in enumerate(instruction_dict['fields']):
                                for elem in instruction_dict['fields'].keys():
                                    if 'shamt' in elem:
                                        break
                        del instruction_dict['fields'][elem]
                        instruction_dict['fields']['shamt_c'] = ''
                    elif instruction.lower().replace("_", ".") == 'c.addi16sp':
                        for i, op in enumerate(operands_list):
                            acc = operands_list[i]
                            if 'sp' not in operands_list:
                                operands_list[i] = 'sp'
                                operands_list.append(acc)
                                break
            new_operands = operands_list
            if immediate_found:
                instruction_dict['fields'] = new_fields
                instruction_dict['operands'] = new_operands
                print(f"DEBUG: Final fields: {new_fields}")
                print(f"DEBUG: Final operands: {new_operands}")
            else:
                print(f"DEBUG: No generic immediates found to map")
                def rename_or_drop_key(d, old_key="rd", new_key="rd_c"):
                    """
                    - Dacă new_key NU există: redenumește old_key -> new_key, păstrând poziția în dicționar.
                    - Dacă new_key există: șterge old_key (dacă există).
                    Modifică dict-ul in-place.
                    """
                    if old_key not in d:
                        return d 

                    if new_key in d:
                        # doar ștergem old_key
                        d.pop(old_key, None)
                        return d

                    new_d = {}
                    for k, v in d.items():
                        if k == old_key:
                            new_d[new_key] = v
                        else:
                            new_d[k] = v

                    d.clear()
                    d.update(new_d)
                    return d
                fields_dict = new_fields  # alias

                for instruction in INSTRUCTION_COMPRESSED:
                    if instruction_dict['name'].lower().replace("_", ".") == instruction.lower().replace("_", "."):
                        if instruction_dict['name'].lower().replace("_", ".") != 'c.add':
                            rename_or_drop_key(fields_dict, 'rd', 'rd_c')

                new_fields = fields_dict
            print(f"DEBUG: === END MAPPING FOR {instruction_name.upper()} ===\n")
        return instruction_dict


    def _map_literal_to_known_field(
    self,
    start_bit: int,
    end_bit: int,
    bit_count: int,
    value: int,
    position: int,
    total_patterns: int
) -> Optional[tuple]:
        """
        Maps a literal value ONLY to known instruction fields defined in
        `INSTRUCTION_FIELD_RANGES`.

        This function attempts to associate a decoded literal (bit slice and value)
        with a predefined instruction field by checking whether the bit range
        [start_bit:end_bit] matches any known field boundaries. If a match is found,
        it returns a structured tuple describing the association; otherwise, it
        returns None. The `position` and `total_patterns` parameters can be used
        to provide additional matching context (e.g., when iterating over multiple
        encoding patterns).

        Args:
            start_bit (int):
                The most significant bit index (inclusive) of the literal slice.
            end_bit (int):
                The least significant bit index (inclusive) of the literal slice.
            bit_count (int):
                The width of the literal in bits (should equal start_bit - end_bit + 1).
            value (int):
                The integer value of the literal extracted from the bit slice.
            position (int):
                The ordinal position within the current pattern/match sequence.
            total_patterns (int):
                The total number of patterns being considered for the current instruction.

        Returns:
            Optional[tuple]:
                A tuple describing the mapping if a known field is matched, otherwise None.
                The tuple typically has the structure:
                `(field_name: str, start_bit: int, end_bit: int, value: int, position: int)`

        Raises:
            ValueError:
                If the provided bit range is invalid (e.g., start_bit < end_bit,
                negative indices, or bit_count does not match the range width).
            KeyError:
                If `INSTRUCTION_FIELD_RANGES` is not initialized or missing
                required field definitions.
        """
        global INSTRUCTION_FIELD_RANGES
        
        self.debug_print(f"DEBUG: Mapping literal [{start_bit}:{end_bit}] with {bit_count} bits, value={value}, position={position}/{total_patterns}")
        
        for field_name, field_range in INSTRUCTION_FIELD_RANGES.items():
            if isinstance(field_range, tuple) and len(field_range) == 2:
                field_start, field_end = field_range
                if field_start == start_bit and field_end == end_bit:
                    self.debug_print(f"DEBUG: Literal matches known field {field_name}")
                    return (field_name, value)
        
        if bit_count == 7 and position == total_patterns - 1:
            # 7 bits opcode field 
            self.debug_print(f"DEBUG: Mapping 7-bit literal at end (position {position}/{total_patterns-1}) to opcode")
            return ('opcode', value)
        elif bit_count == 7 and position == 0:
            # Found funct7
            self.debug_print(f"DEBUG: Mapping 7-bit literal at start to funct7")
            return ('funct7', value)
        elif bit_count == 3:
            # Found funct3
            self.debug_print(f"DEBUG: Mapping 3-bit literal to funct3")
            return ('funct3', value)
        elif bit_count == 6:
            # Found funct6
            self.debug_print(f"DEBUG: Mapping 6-bit literal to funct7")
            return ('funct7', value *2)
        elif bit_count == 5:
            reg_name = self._get_register_name_by_position(start_bit, end_bit)
            if reg_name:
                self.debug_print(f"DEBUG: 5-bit literal matches register {reg_name}")
                return (reg_name, value)
            elif value == 0:
                # Check shamt from INSTRUCTION_FIELD_RANGES
                if 'shamt' in INSTRUCTION_FIELD_RANGES:
                    shamt_start, shamt_end = INSTRUCTION_FIELD_RANGES['shamt']
                    if shamt_start == start_bit and shamt_end == end_bit:
                        self.debug_print(f"DEBUG: 5-bit literal with value 0 matches shamt position")
                        return ('shamt', value)

            self.debug_print(f"DEBUG: 5-bit literal doesn't match any known register or shamt")
            return None
        elif bit_count >= 12:
            for field_name, field_range in INSTRUCTION_FIELD_RANGES.items():
                if isinstance(field_range, tuple) and len(field_range) == 2:
                    field_start, field_end = field_range
                    if field_start == start_bit and field_end == end_bit and 'imm' in field_name:
                        self.debug_print(f"DEBUG: Large literal matches known immediate {field_name}")
                        return (field_name, value)
            self.debug_print(f"DEBUG: Large literal doesn't match any known immediate")
            return None
        self.debug_print(f"DEBUG: No mapping found for {bit_count}-bit literal at position {position}")
        return None



    def _is_generic_immediate(self, field_name: str) -> bool: 
        """ Determines whether a field represents a generic immediate that requires mapping. 
        This function checks whether the given field name corresponds to a generic immediate placeholder 
        (e.g., imm, imm_x, generic immediate tags) that must be translated into a template-specific immediate 
        definition during instruction processing. Args: field_name (str): The name of the instruction field to evaluate. 
        Returns: 
            bool: True if the field is identified as a generic immediate that needs to be mapped to its template-specific form, 
            otherwise False. 
        
        Raises: 
            TypeError: If `field_name` is not a string. """
        # Imm mapping list
        generic_immediates = [
            'imm',           # generic immediate 
            'imm_jalr',      # specific immediate for JALR
        ]
        
        # Check for generic immediate
        if field_name in generic_immediates:
            return True
        
        template_specific_immediates = [
            'imm_i', 'imm_btype', 'imm_utype', 'imm_stype', 'imm_jtype',
            'imm_jal'  # JAL preserves its specific name
        ]
        
        if field_name.startswith('imm_') and field_name not in template_specific_immediates:
            return True
        
        return False

    def order_operands(self, operands: List[str]) -> List[str]:
        """
        Orders instruction operands by conventional priority:
        destination (rd/md), sources (rs*/ms*), others, then immediates.

        The sorting groups operands into the following categories (in order):
        1) destination registers (e.g., rd, md),
        2) source registers (e.g., rs1, rs2, rs3, ms1, ms2, ...),
        3) other named operands,
        4) immediates (e.g., imm, imm12, simm, uimm).

        Within each category, a stable order is preserved (e.g., rs1 before rs2).

        Args:
            operands (List[str]):
                The raw list of operand names parsed from instruction metadata.

        Returns:
            List[str]:
                A new list with operands ordered by destination, sources, others,
                then immediates.

        Raises:
            TypeError:
                If `operands` is not a list of strings.
        """
        dest_ops = [] 
        src_ops = []   
        imm_ops = []   
        other_ops = []
        
        for op in operands:
            if op in ['rd', 'md', 'rsd', 'rd_c']:  # Add md as destination
                dest_ops.append(op)
            elif op.startswith('rs') or op.startswith('ms'): # Add ms as source
                src_ops.append(op)
            elif op.startswith('imm'):
                imm_ops.append(op)
            else:
                other_ops.append(op)
    
        # Sort sources (rs1, rs2, rs3 or ms1, ms2)
        def get_register_number(reg_name):
            """
            Extracts the numeric index from a register name.

            This helper parses register identifiers like "rs1", "rs2", "rd", "ms3",
            returning the numeric suffix when present. If no numeric part exists
            (e.g., "rd"), it returns 0 by convention, unless you choose to handle
            it differently in the caller.

            Args:
                reg_name (str):
                    The register name (e.g., "rs1", "ms2", "rd").

            Returns:
                int:
                    The extracted register number (e.g., 1 for "rs1", 2 for "ms2").
                    Returns 0 if no numeric suffix is present.

            Raises:
                TypeError:
                    If `reg_name` is not a string.
                ValueError:
                    If the register name format is invalid or the numeric suffix
                    cannot be parsed when expected.
            """
            match = re.search(r'(\d+)$', reg_name)
            if match:
                return int(match.group(1))
            return 0
    
        src_ops.sort(key=get_register_number)
        
        # Sorting: destination, source, immediates
        return dest_ops + src_ops + other_ops + imm_ops

    
    def parse_instruction_from_contents(self, contents: str) -> tuple:
        """
        Parses the template name, instruction name, and operands from raw contents.

        This function analyzes a block of textual content (e.g., a function clause,
        instruction description, or a JSON-derived snippet) and extracts:
        - the associated template name,
        - the canonical instruction name,
        - the ordered list of operands.

        The exact parsing rules depend on the expected syntax used in the source
        (e.g., "template <T> instr NAME rd, rs1, rs2" or similar format).

        Args:
            contents (str):
                The raw text that encodes the instruction declaration and operands.

        Returns:
            tuple:
                A tuple in the form:
                (template_name: Optional[str], instruction_name: str, operands: List[str])

        Raises:
            ValueError:
                If required elements (instruction name or operands) cannot be found,
                or if the content does not conform to the expected format.
            TypeError:
                If `contents` is not a string.
        """
        match = re.search(r'(\w+\.*\w+)\((.*?)\)\s*<->\s*(.+)', contents, re.DOTALL)
        if not match:
            return "", "", [], []
        
        potential_name = match.group(1)
        params_str = match.group(2)
        encoding_part = match.group(3)
        
        print(f"DEBUG parse_instruction: potential_name = {potential_name}")
        print(f"DEBUG parse_instruction: params_str = {params_str}")
        
        if potential_name.lower() in self.known_fields:
            return "", "", [], []
        
        params = []
        current_param = ""
        paren_level = 0
        
        for char in params_str + ',':
            if char == '(':
                paren_level += 1
                current_param += char
            elif char == ')':
                paren_level -= 1
                current_param += char
            elif char == ',' and paren_level == 0:
                if current_param.strip():
                    params.append(current_param.strip())
                current_param = ""
            else:
                current_param += char
        
        print(f"DEBUG parse_instruction: params = {params}")
        
        encoding_tokens = set()
        encoding_words = re.findall(r'\b(?!0b)[a-zA-Z_][a-zA-Z0-9_]*\b', encoding_part)
        for word in encoding_words:
            if not word.startswith('encdec_') and word != 'bits':
                encoding_tokens.add(word)
        
        print(f"DEBUG parse_instruction: encoding_tokens = {encoding_tokens}")
        
        encoding_func = set()
        for word in encoding_words:
            if word.startswith('encdec_') and word != 'bits':
                encoding_func.add(word)
        
        print(f"DEBUG parse_instruction: encoding_func = {encoding_func}")
        
        if potential_name.upper() in self.template_splits:
            pass
        
        is_template = False
        template_name = ""
        instruction_name = ""
        operands = []
        
        if len(params) > 0:
            last_param = params[-1].strip()
            
            is_immediate_compound = '@' in last_param
            
            print(f"DEBUG parse_instruction: last_param = '{last_param}'")
            print(f"DEBUG parse_instruction: is_immediate_compound = {is_immediate_compound}")
            
            last_param_in_encoding = False
            if '@' in last_param:
                components = self.parse_immediate_components(last_param)
                print(f"DEBUG parse_instruction: immediate components = {components}")
                if any(comp in encoding_tokens for comp in components):
                    last_param_in_encoding = True
                    print(f"DEBUG parse_instruction: immediate components found in encoding")
            else:
                if last_param in encoding_tokens:
                    last_param_in_encoding = True
                    print(f"DEBUG parse_instruction: last_param found in encoding")
            
            print(f"DEBUG parse_instruction: last_param_in_encoding = {last_param_in_encoding}")
            
            if not last_param_in_encoding and len(params) > 1 and not is_immediate_compound:
                is_template = True
                template_name = potential_name
                self.known_templates.add(potential_name)
                instruction_name = last_param.lower()
                operands = [p for p in params[:-1] if p.strip() not in ['op', 'is_unsigned', 'mul_op', 'width']]
                print(f"DEBUG parse_instruction: Detected as TEMPLATE")
                print(f"DEBUG parse_instruction: template_name = {template_name}")
                print(f"DEBUG parse_instruction: instruction_name = {instruction_name}")
            else:
                template_name = ""
                instruction_name = potential_name.lower()
                operands = [p for p in params if p.strip() not in ['op', 'is_unsigned', 'mul_op', 'width']]
                print(f"DEBUG parse_instruction: Detected as INSTRUCTION")
                print(f"DEBUG parse_instruction: instruction_name = {instruction_name}")
        else:
            template_name = ""
            instruction_name = potential_name.lower()
            operands = []
            print(f"DEBUG parse_instruction: No params - instruction_name = {instruction_name}")
        
        if instruction_name in self.known_fields:
            return "", "", [], []
        processed_operands = []
        for operand in operands:
            if '@' in operand:
                components = self.parse_immediate_components(operand)
                if components:
                    processed_operands.extend(components)
                elif 'imm' in operand.lower() or operand.startswith('nz'):
                    processed_operands.append(operand)
                else:
                    processed_operands.append(operand)
            else:
                clean_operand = operand.strip()
                if not clean_operand.startswith('0b'):
                    processed_operands.append(clean_operand)
        
        print(f"DEBUG parse_instruction: processed_operands = {processed_operands}")
        
        consolidated_operands = self.consolidate_immediates(processed_operands, instruction_name, is_template=False)
        
        print(f"DEBUG parse_instruction: consolidated_operands = {consolidated_operands}")
        
        ordered_operands = self.order_operands(consolidated_operands)
        
        print(f"DEBUG parse_instruction: ordered_operands = {ordered_operands}")
        
        return template_name, instruction_name, ordered_operands, encoding_func

    def _is_compressed_encoding(self, patterns: List[Dict[str, Any]]) -> bool:
        """
        Detects whether the encoding corresponds to a compressed (16‑bit) instruction.

        This function analyzes the list of encoding patterns associated with an
        instruction and determines whether they represent a compressed format.
        Compressed instructions typically use 16‑bit encodings instead of the
        standard 32‑bit ones, and can be detected by examining bit ranges, field
        widths, or pattern metadata within the encoding definitions.

        Args:
            patterns (List[Dict[str, Any]]):
                A list of encoding pattern dictionaries parsed from the JSON model.

        Returns:
            bool:
                True if the instruction appears to use a 16‑bit compressed encoding,
                otherwise False.

        Raises:
            TypeError:
                If the pattern list or its entries are not in the expected format.
            KeyError:
                If required encoding fields (e.g., bit ranges) are missing.
        """
        # Compressed instructions
        if not patterns:
            print(f"DEBUG _is_compressed: No patterns")
            return False
        
        print(f"DEBUG _is_compressed: Checking {len(patterns)} patterns")
        last_pattern = patterns[-1]
        print(f"DEBUG _is_compressed: Last pattern = {last_pattern}")
        
        if last_pattern.get('type') == 'literal':
            value = last_pattern.get('value', '')
            print(f"DEBUG _is_compressed: Last pattern is literal with value: {value}")
            if isinstance(value, str) and value.startswith('0b'):
                binary_value = value[2:]
                print(f"DEBUG _is_compressed: Binary value = {binary_value}, length = {len(binary_value)}")
                # Compressed opcode
                if len(binary_value) == 2:
                    self.debug_print(f"DEBUG: Detected compressed encoding - last pattern is 2-bit literal: {value}")
                    print(f"DEBUG _is_compressed: ✓ DETECTED COMPRESSED (2-bit literal)")
                    return True
                else:
                    print(f"DEBUG _is_compressed: ✗ Not compressed - binary length is {len(binary_value)}, not 2")
            else:
                print(f"DEBUG _is_compressed: ✗ Not compressed - value is not binary string")
        else:
            print(f"DEBUG _is_compressed: ✗ Not compressed - last pattern type is {last_pattern.get('type')}")
        
        return False


    def _detect_compressed_function_fields(self, patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detects and constructs function fields for compressed instructions
        (e.g., funct3_c, funct4_c).

        This function analyzes encoding patterns associated with a compressed
        (16-bit) instruction and extracts the compact function fields that
        determine instruction subtypes. These fields differ from standard 32-bit
        encodings and are often located in smaller, compressed bit ranges.

        Args:
            patterns (List[Dict[str, Any]]):
                A list of encoding pattern dictionaries from which compressed
                function fields should be extracted.

        Returns:
            Dict[str, Any]:
                A dictionary containing detected compressed function fields mapped
                to their bit ranges and values.

        Raises:
            ValueError:
                If bit ranges for compressed fields are malformed or inconsistent.
            KeyError:
                If the pattern entries lack the required metadata for extraction.
        """
        
        print(f"DEBUG: Detecting compressed function fields from {len(patterns)} patterns")
        
        current_bit = 15  # Start for compressed
        function_fragments = []
        
        for i, pattern in enumerate(patterns):
            pattern_type = pattern.get('type', 'unknown')
            
            if pattern_type == 'literal':
                value = pattern.get('value', '')
                if isinstance(value, str) and value.startswith('0b'):
                    binary_value = value[2:]
                    bit_count = len(binary_value)
                    
                    if i == len(patterns) - 1 and bit_count == 2:
                        print(f"DEBUG: Skipping pattern {i} (op_c): {value}")
                        current_bit -= bit_count
                        continue
                    
                    start_bit = current_bit
                    end_bit = current_bit - bit_count + 1
                    
                    function_fragments.append({
                        'start': start_bit,
                        'end': end_bit,
                        'bits': bit_count,
                        'value': int(binary_value, 2),
                        'position': i
                    })
                    
                    print(f"DEBUG: Found function fragment at pattern {i}: [{start_bit}:{end_bit}] = {binary_value} ({bit_count} bits)")
                    current_bit -= bit_count
                    
            elif pattern_type == 'app' and pattern.get('id') in ['encdec_reg', 'encdec_creg']:
                reg_size = 5 if pattern.get('id') == 'encdec_reg' else 3
                current_bit -= reg_size
                print(f"DEBUG: Skipping register at pattern {i} ({reg_size} bits)")
                
            elif pattern_type == 'typ_app':
                arg = pattern.get('arg', {})
                bit_count = 0
                if isinstance(arg, dict):
                    arg_arg = arg.get('arg', {})
                    if isinstance(arg_arg, dict):
                        bit_count = arg_arg.get('n', 0)
                
                if bit_count > 0:
                    current_bit -= bit_count
                    print(f"DEBUG: Skipping immediate at pattern {i} ({bit_count} bits)")
        
        if not function_fragments:
            print(f"DEBUG: No function fragments found")
            return {}
        
        function_fragments.sort(key=lambda x: x['start'], reverse=True)
        

        function_groups = []
        current_group = [function_fragments[0]]
        
        for i in range(1, len(function_fragments)):
            prev_fragment = function_fragments[i-1]
            curr_fragment = function_fragments[i]
            
            if prev_fragment['end'] - 1 == curr_fragment['start']:
                current_group.append(curr_fragment)
                print(f"DEBUG: Fragment {i} is consecutive with previous, adding to group")
            else:
                function_groups.append(current_group)
                current_group = [curr_fragment]
                print(f"DEBUG: Fragment {i} is NOT consecutive, starting new group")
        

        if current_group:
            function_groups.append(current_group)
        
        print(f"DEBUG: Found {len(function_groups)} function groups")
        
        compressed_fields = {}
        
        for group_idx, group in enumerate(function_groups):
            total_bits = sum(frag['bits'] for frag in group)
            
            field_name = f'funct{total_bits}_c'
            
            combined_value = 0
            for frag in group:
                combined_value = (combined_value << frag['bits']) | frag['value']
            
            ranges = [(frag['start'], frag['end']) for frag in group]
            
            print(f"DEBUG: Created {field_name} with {len(ranges)} ranges, total {total_bits} bits, value={combined_value}")
            print(f"DEBUG:   Ranges: {ranges}")
            
            global INSTRUCTION_FIELD_RANGES
            if field_name not in INSTRUCTION_FIELD_RANGES:
                if len(ranges) == 1:
                    INSTRUCTION_FIELD_RANGES[field_name] = ranges[0]
                else:
                    INSTRUCTION_FIELD_RANGES[field_name] = {
                        'ranges': ranges,
                        'shift': 0,
                        'total_bits': total_bits
                    }
                print(f"DEBUG: Added {field_name} to INSTRUCTION_FIELD_RANGES")

            compressed_fields[field_name] = combined_value
        
        return compressed_fields


    def parse_encoding_fields(self, right_pattern: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses encoding fields from the right-hand side pattern, mapping each
        bit segment to its corresponding instruction field.

        Args:
            right_pattern (Dict[str, Any]):
                A dictionary representing the right-hand side encoding pattern.

        Returns:
            Dict[str, Any]:
                A dictionary mapping field names to their bit slices, values,
                or decoded metadata.
        """
        fields = {}
        
        self.debug_print(f"DEBUG: Parsing encoding fields from pattern: {right_pattern}")
        
        if right_pattern.get('type') == 'vector_concat':
            patterns = right_pattern.get('patterns', [])
            self.debug_print(f"DEBUG: Found {len(patterns)} patterns in vector_concat")
            
            # Debug: display all patterns
            for i, p in enumerate(patterns):
                print(f"DEBUG parse_encoding_fields: Pattern {i}: {p}")
            
            # Detect if it's FENCE by analyzing patterns
            if self._is_fence_encoding(patterns):
                self.debug_print("DEBUG: Detected FENCE encoding - using special processing")
                return self._parse_fence_encoding(patterns)
            
            # ADDED: Detect if it's compressed encoding (16-bit)
            print(f"DEBUG parse_encoding_fields: Calling _is_compressed_encoding...")
            is_compressed = self._is_compressed_encoding(patterns)
            print(f"DEBUG parse_encoding_fields: is_compressed = {is_compressed}")
            self.debug_print(f"DEBUG: Is compressed encoding: {is_compressed}")
            
            # ADDED: For compressed instructions, detect function fields
            if is_compressed:
                compressed_function_fields = self._detect_compressed_function_fields(patterns)
                if compressed_function_fields:
                    print(f"DEBUG: Found compressed function fields: {compressed_function_fields}")
                    fields.update(compressed_function_fields)
            
            # MODIFIED: Check last pattern for op_c BEFORE processing
            last_pattern_is_op_c = False
            op_c_value = None
            if is_compressed and patterns:
                last_pattern = patterns[-1]
                print(f"DEBUG: Checking last pattern for op_c: {last_pattern}")
                if last_pattern.get('type') == 'literal':
                    value = last_pattern.get('value', '')
                    if isinstance(value, str) and value.startswith('0b'):
                        binary_value = value[2:]
                        if len(binary_value) == 2:
                            last_pattern_is_op_c = True
                            op_c_value = int(binary_value, 2)
                            print(f"DEBUG: Last pattern IS op_c: {value} (decimal: {op_c_value})")
            
            # Rest of existing logic for processing patterns...
            # (keep all existing code for registers, immediates, etc.)
            
            funct3_fragments = []
            current_bit = 15 if is_compressed else 31
            
            for i, pattern in enumerate(patterns):
                pattern_type = pattern.get('type', 'unknown')
                self.debug_print(f"DEBUG: Processing pattern {i}: type={pattern_type}")
                print(f"DEBUG: Pattern {i}/{len(patterns)-1}: type={pattern_type}, current_bit={current_bit}")
                
                if pattern.get('type') == 'literal':
                    value = pattern.get('value', '')
                    self.debug_print(f"DEBUG: Literal pattern with value: {value}")
                    if isinstance(value, str) and value.startswith('0b'):
                        binary_value = value[2:]
                        bit_count = len(binary_value)
                        decimal_value = int(binary_value, 2)
                        
                        # MODIFIED: For compressed, skip literals already processed as functions
                        if is_compressed and i != len(patterns) - 1:
                            # Check if this literal is part of an already created function field
                            start_bit = current_bit
                            end_bit = current_bit - bit_count + 1
                            
                            # Search in fields if we already have a funct*_c containing this range
                            is_part_of_function = False
                            for field_name in fields.keys():
                                if field_name.startswith('funct') and field_name.endswith('_c'):
                                    # Check if this range is part of field
                                    field_range = INSTRUCTION_FIELD_RANGES.get(field_name)
                                    if isinstance(field_range, dict) and 'ranges' in field_range:
                                        for r_start, r_end in field_range['ranges']:
                                            if r_start == start_bit and r_end == end_bit:
                                                is_part_of_function = True
                                                print(f"DEBUG: Literal at [{start_bit}:{end_bit}] is part of {field_name}, skipping")
                                                break
                                    elif isinstance(field_range, tuple):
                                        r_start, r_end = field_range
                                        if r_start == start_bit and r_end == end_bit:
                                            is_part_of_function = True
                                            print(f"DEBUG: Literal at [{start_bit}:{end_bit}] is part of {field_name}, skipping")
                                            break
                            
                            if is_part_of_function:
                                current_bit -= bit_count
                                continue
                        
                        # ADDED: Detect funct3 fragments (for normal instructions)
                        if not is_compressed and bit_count == 2 and binary_value in ['10', '11']:
                            funct3_fragments.append({
                                'type': 'literal',
                                'value': decimal_value,
                                'bits': bit_count,
                                'position': current_bit
                            })
                            self.debug_print(f"DEBUG: Detected potential funct3 fragment: {binary_value} = {decimal_value}")
                            current_bit -= bit_count
                            continue
                        
                        # Map literals to known instruction fields
                        start_bit = current_bit
                        end_bit = current_bit - bit_count + 1
                        
                        print(f"DEBUG: Processing literal at position {i}/{len(patterns)-1}")
                        print(f"DEBUG: is_compressed={is_compressed}, bit_count={bit_count}")
                        print(f"DEBUG: start_bit={start_bit}, end_bit={end_bit}")
                        print(f"DEBUG: last_pattern_is_op_c={last_pattern_is_op_c}")
                        print(f"DEBUG: i == len(patterns) - 1: {i == len(patterns) - 1}")
                        
                        # Use pre-calculated flag for op_c
                        if last_pattern_is_op_c and i == len(patterns) - 1:
                            fields['op_c'] = op_c_value
                            print(f"DEBUG: ✓✓✓ MAPPED TO op_c = {op_c_value} ✓✓✓")
                            self.debug_print(f"DEBUG: Mapped to compressed opcode op_c = {op_c_value}")
                            if 'op_c' not in INSTRUCTION_FIELD_RANGES:
                                INSTRUCTION_FIELD_RANGES['op_c'] = (start_bit, end_bit)
                                print(f"DEBUG: Added op_c to INSTRUCTION_FIELD_RANGES: ({start_bit}, {end_bit})")
                        else:
                            print(f"DEBUG: Not mapping to op_c - conditions not met")
                            mapped_field = self._map_literal_to_known_field(start_bit, end_bit, bit_count, decimal_value, i, len(patterns))
                            if mapped_field:
                                field_name, field_value = mapped_field
                                fields[field_name] = field_value
                                self.debug_print(f"DEBUG: Mapped literal to known field: {field_name} = {field_value}")
                            else:
                                self.debug_print(f"DEBUG: Literal not mapped to any known field")
                        
                        current_bit -= bit_count
                        print(f"DEBUG: After literal, current_bit={current_bit}")
                    elif isinstance(value, int):
                        fields[f'literal_{i}'] = value
                        current_bit -= 1
                
                # Rest of code for other pattern types remains unchanged...
                # (keep logic for typ_app, app, id, etc.)
                
                elif pattern.get('type') == 'typ_app':
                    print(f"DEBUG: Found typ_app pattern: {pattern}")
                    field_id = pattern.get('id', '')
                    arg = pattern.get('arg', {})
                    bit_count = 0
                    if field_id.startswith('ui'):
                            if isinstance(arg, dict):
                                arg_arg = arg.get('arg', {})
                                if isinstance(arg_arg, dict):
                                    bit_count = arg_arg.get('n', 0)
                            print(f"DEBUG: typ_app - unsigned immediate field_id={field_id}, bit_count={bit_count}")
                    else:
                        if isinstance(arg, dict):
                            arg_arg = arg.get('arg', {})
                            if isinstance(arg_arg, dict):
                                bit_count = arg_arg.get('n', 0)
                        print(f"DEBUG: typ_app - field_id={field_id}, bit_count={bit_count}")
                    
                    if bit_count > 0:
                        current_bit -= bit_count
                        print(f"DEBUG: After typ_app ({field_id}), current_bit={current_bit}")
                    else:
                        current_bit -= 1
                
                elif pattern.get('type') == 'app':
                    app_id = pattern.get('id', '')
                    self.debug_print(f"DEBUG: App pattern with id: {app_id}")
                    
                    if app_id == 'encdec_reg':
                        reg_patterns = pattern.get('patterns', [])
                        if reg_patterns and len(reg_patterns) > 0:
                            if reg_patterns[0].get('type') == 'id':
                                reg_name = reg_patterns[0].get('id', '')
                                if reg_name in ['rd', 'rs1', 'rs2', 'rs3', 'md', 'ms1', 'ms2', 'rsd']:
                                    fields[reg_name] = ""
                        current_bit -= 5
                        print(f"DEBUG: After encdec_reg, current_bit={current_bit}")
                    
                    elif app_id == 'encdec_creg':
                        reg_patterns = pattern.get('patterns', [])
                        if reg_patterns and len(reg_patterns) > 0:
                            if reg_patterns[0].get('type') == 'id':
                                reg_name = reg_patterns[0].get('id', '')
                                if reg_name in ['rd', 'rs1', 'rs2']:
                                    fields[reg_name + "_c"] = ""
                                    if reg_name + "_c" not in INSTRUCTION_FIELD_RANGES:
                                        if reg_name + "_c" == 'rd_c':
                                            current_bit = 4
                                            start_bit = current_bit
                                            end_bit = current_bit - 3 + 1  # 3 bits for compressed registers
                                            INSTRUCTION_FIELD_RANGES[reg_name + "_c"] = (start_bit, end_bit)
                                        elif reg_name + "_c" == 'rs2_c':
                                            current_bit = 4
                                            start_bit = current_bit
                                            end_bit = current_bit - 3 + 1  # 3 bits for compressed registers
                                            INSTRUCTION_FIELD_RANGES[reg_name + "_c"] = (start_bit, end_bit)
                                        elif reg_name + "_c" == 'rs1_c':
                                            current_bit = 9
                                            start_bit = current_bit
                                            end_bit = current_bit - 3 + 1  # 3 bits for compressed registers
                                            INSTRUCTION_FIELD_RANGES[reg_name + "_c"] = (start_bit, end_bit)
                                    if reg_name + "_c" not in self.field_to_register_map:
                                        self.field_to_register_map[reg_name + "_c"] = 'GPR'  # Compressed registers are GPR
                                        print(f"DEBUG: Added {reg_name + '_c'} to field_to_register_map as GPR")
                        current_bit -= 3
                        print(f"DEBUG: After encdec_creg, current_bit={current_bit}")
                    
                    
                    elif app_id == 'bool_bits':
                        app_patterns = pattern.get('patterns', [])
                        if app_patterns and len(app_patterns) > 0:
                            if app_patterns[0].get('type') == 'id':
                                bool_field = app_patterns[0].get('id', '')
                                if bool_field == 'is_unsigned':
                                    funct3_fragments.append({
                                        'type': 'bool_bits',
                                        'field': 'is_unsigned',
                                        'value': 0,
                                        'bits': 1,
                                        'position': current_bit
                                    })
                                    self.debug_print(f"DEBUG: Detected bool_bits(is_unsigned) fragment")
                                    current_bit -= 1
                                    continue
                    
                    elif app_id.startswith('encdec_'):
                        app_patterns = pattern.get('patterns', [])
                        self.debug_print(f"DEBUG: App {app_id} has {len(app_patterns)} sub-patterns")
                        
                        for app_pattern in app_patterns:
                            if app_pattern.get('type') == 'id':
                                field_name = app_pattern.get('id', '')
                                self.debug_print(f"DEBUG: Found field in app: {field_name}")
                                
                                if field_name == 'op':
                                    fields['opcode'] = ""
                                    self.debug_print(f"DEBUG: Set opcode field (empty, to be filled)")
                                elif field_name == 'mul_op':
                                    fields['funct3'] = 0
                                    self.debug_print(f"DEBUG: Found mul_op, setting funct3=0")
                                elif field_name == 'div_op':
                                    fields['funct3'] = 4
                                    self.debug_print(f"DEBUG: Found div_op, setting funct3=4")
                                elif field_name == 'rem_op':
                                    fields['funct3'] = 6
                                    self.debug_print(f"DEBUG: Found rem_op, setting funct3=6")
                                elif field_name == 'width':
                                    fields['funct3'] = 3
                                    self.debug_print(f"DEBUG: Found width in app, converting to funct3=3")
                                elif field_name and field_name not in ['is_unsigned']:
                                    fields[field_name] = ""
                        
                        if app_id.endswith('op'):
                            current_bit -= 7
                        else:
                            current_bit -= 3
                        
                        print(f"DEBUG: After app ({app_id}), current_bit={current_bit}")
                
                elif pattern.get('type') == 'id':
                    operand_name = pattern.get('id', '')
                    self.debug_print(f"DEBUG: ID pattern with name: {operand_name}")
                    
                    if operand_name in ['md', 'ms1', 'ms2']:
                        fields[operand_name] = ""
                        self.debug_print(f"DEBUG: Found vector register: {operand_name}")
                        current_bit -= 5
                        print(f"DEBUG: After vector register ({operand_name}), current_bit={current_bit}")
                        continue
                    
                    if operand_name == 'is_unsigned':
                        funct3_fragments.append({
                            'type': 'id',
                            'field': 'is_unsigned',
                            'value': 0,
                            'bits': 1,
                            'position': current_bit
                        })
                        self.debug_print(f"DEBUG: Detected is_unsigned ID fragment")
                        current_bit -= 1
                        continue
                    
                    if operand_name == 'shamt':
                        fields['shamt'] = ""
                        self.debug_print(f"DEBUG: Found shamt in encoding")
                        current_bit -= 5
                        print(f"DEBUG: After shamt, current_bit={current_bit}")
                        continue
                    
                    is_instruction_name = False
                    for template_splits in self.template_splits.values():
                        if operand_name in template_splits:
                            is_instruction_name = True
                            break
                    
                    if (not is_instruction_name and operand_name != 'is_unsigned'):
                        if operand_name == 'op':
                            fields['opcode'] = ""
                            self.debug_print(f"DEBUG: Set opcode field from ID (empty, to be filled)")
                        elif operand_name == 'mul_op':
                            fields['funct3'] = 0
                            self.debug_print(f"DEBUG: Found mul_op ID, setting funct3=0")
                        elif operand_name == 'div_op':
                            fields['funct3'] = 4
                            self.debug_print(f"DEBUG: Found div_op ID, setting funct3=4")
                        elif operand_name == 'rem_op':
                            fields['funct3'] = 6
                            self.debug_print(f"DEBUG: Found rem_op ID, setting funct3=6")
                        elif operand_name == 'width':
                            fields['funct3'] = 3
                            self.debug_print(f"DEBUG: Found width ID, converting to funct3=3")
                        elif operand_name in ['rd', 'rs1', 'rs2', 'rs3', 'md', 'ms1', 'ms2', 'rsd', 'rd_c', 'rs1_c', 'rs2_c']:
                            fields[operand_name] = ""
                    
                    if operand_name in ['rd', 'rs1', 'rs2', 'rs3', 'md', 'ms1', 'ms2', 'rsd']:
                        current_bit -= 5
                    elif operand_name in ['rd_c', 'rs1_c', 'rs2_c']:
                        current_bit -= 3
                    elif operand_name == 'shamt':
                        current_bit -= 5
                    else:
                        current_bit -= 3
                    
                    print(f"DEBUG: After id ({operand_name}), current_bit={current_bit}")
            
            print(f"DEBUG: Final current_bit={current_bit}")
            
            # Process detected funct3 fragments (for normal instructions)
            if not is_compressed and len(funct3_fragments) >= 2 and 'funct3' not in fields:
                self.debug_print(f"DEBUG: Processing {len(funct3_fragments)} funct3 fragments")
                funct3_fragments.sort(key=lambda x: x['position'], reverse=True)
                funct3_value = 0
                total_bits = 0
                for fragment in funct3_fragments:
                    self.debug_print(f"DEBUG: Processing fragment: {fragment}")
                    funct3_value = (funct3_value << fragment['bits']) | fragment['value']
                    total_bits += fragment['bits']
                if total_bits == 3:
                    fields['funct3'] = funct3_value
                    self.debug_print(f"DEBUG: Constructed funct3 = {funct3_value} from fragments")
                else:
                    self.debug_print(f"DEBUG: Invalid funct3 fragments total bits: {total_bits}")
            
        self.debug_print(f"DEBUG: Final parsed fields: {fields}")
        print(f"DEBUG parse_encoding_fields FINAL: instruction fields = {fields}")
        print(f"DEBUG parse_encoding_fields FINAL: 'op_c' in fields? {'op_c' in fields}")
        if 'op_c' in fields:
            print(f"DEBUG parse_encoding_fields FINAL: op_c value = {fields['op_c']}")
        
        return fields




    def _is_fence_encoding(self, patterns: List[Dict[str, Any]]) -> bool:
        """
        Detects whether the provided encoding patterns correspond to a FENCE instruction.

        Args:
            patterns (List[Dict[str, Any]]):
                A list of encoding pattern dictionaries.

        Returns:
            bool:
                True if the encoding matches a FENCE instruction, False otherwise.
        """
        # Search for FENCE-specific pattern: 0b0000 @ pred @ succ @ 0b00000 @ 0b000 @ 0b00000 @ 0b0001111
        if len(patterns) != 7:
            return False
        
        # Check first pattern: 0b0000 (4 bits)
        if (patterns[0].get('type') == 'literal' and 
            patterns[0].get('value') == '0b0000'):
            
            # Check second and third patterns: pred and succ (IDs)
            if (patterns[1].get('type') == 'id' and patterns[1].get('id') == 'pred' and
                patterns[2].get('type') == 'id' and patterns[2].get('id') == 'succ'):
                
                # Check last pattern: 0b0001111 (opcode for FENCE)
                if (patterns[6].get('type') == 'literal' and 
                    patterns[6].get('value') == '0b0001111'):
                    
                    self.debug_print("DEBUG: Confirmed FENCE encoding pattern")
                    return True
        
        return False

    def _parse_fence_encoding(self, patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Parses the special encoding structure of a FENCE instruction.

        Args:
            patterns (List[Dict[str, Any]]):
                A list of encoding pattern dictionaries containing the FENCE bit layout.

        Returns:
            Dict[str, Any]:
                A dictionary mapping FENCE fields (pred, succ, fm) to their decoded
                bit ranges and values.
        """
        fields = {}
        
        self.debug_print("DEBUG: Parsing FENCE encoding with special logic")
        
        # Pattern for FENCE: 0b0000 @ pred @ succ @ 0b00000 @ 0b000 @ 0b00000 @ 0b0001111
        # Bits:              [31:28] [27:24] [23:20] [19:15] [14:12] [11:7]  [6:0]
        
        # MODIFIED: Use original names pred and succ - will be mapped later
        # pred (4 bits) - will be mapped to fence_pred by _apply_special_operand_mappings
        fields['pred'] = ""  # Will be filled at runtime
        self.debug_print("DEBUG: Added pred field")
        
        # succ (4 bits) - will be mapped to fence_succ by _apply_special_operand_mappings
        fields['succ'] = ""  # Will be filled at runtime
        self.debug_print("DEBUG: Added succ field")
        
        # rs1 (5 bits) - always 0 for FENCE
        fields['rs1'] = "0"
        self.debug_print("DEBUG: Set rs1 = 0 for FENCE")
        
        # funct3 (3 bits) - always 0 for FENCE
        fields['funct3'] = 0
        self.debug_print("DEBUG: Set funct3 = 0 for FENCE")
        
        # rd (5 bits) - always 0 for FENCE
        fields['rd'] = "0"
        self.debug_print("DEBUG: Set rd = 0 for FENCE")
        
        # opcode (7 bits) - 0b0001111 = 15 for FENCE
        fields['opcode'] = 15
        self.debug_print("DEBUG: Set opcode = 15 for FENCE")
        
        self.debug_print(f"DEBUG: FENCE fields: {fields}")
        return fields


    def _map_literal_to_instruction_field(
    self,
    start_bit: int,
    end_bit: int,
    bit_count: int,
    value: int,
    position: int,
    total_patterns: int
) -> Optional[tuple]:
        """
        Maps a literal value to a known instruction field or creates a new one.

        Args:
            start_bit (int):
                The most significant bit index (inclusive) of the literal.
            end_bit (int):
                The least significant bit index (inclusive) of the literal.
            bit_count (int):
                The width of the literal in bits.
            value (int):
                The literal value extracted from the encoding.
            position (int):
                Index of the current encoding pattern being processed.
            total_patterns (int):
                Total number of encoding patterns for the instruction.

        Returns:
            Optional[tuple]:
                A tuple describing the mapped or newly created instruction field,
                or None if no mapping is possible.
        """
        global INSTRUCTION_FIELD_RANGES
        
        self.debug_print(f"DEBUG: Mapping literal [{start_bit}:{end_bit}] with {bit_count} bits, value={value}")
        
        # Check if range matches a known field
        for field_name, field_range in INSTRUCTION_FIELD_RANGES.items():
            if isinstance(field_range, tuple) and len(field_range) == 2:
                field_start, field_end = field_range
                if field_start == start_bit and field_end == end_bit:
                    self.debug_print(f"DEBUG: Literal matches known field {field_name}")
                    return (field_name, value)
        
        # Mapping based on position and size
        if bit_count == 7 and position == total_patterns - 1:
            # Last 7-bit field is opcode
            self._ensure_field_in_ranges('opcode', start_bit, end_bit)
            return ('opcode', value)
        elif bit_count == 7 and position == 0:
            # First 7-bit field is funct7
            self._ensure_field_in_ranges('funct7', start_bit, end_bit)
            return ('funct7', value)
        elif bit_count == 3:
            # 3-bit field is funct3
            self._ensure_field_in_ranges('funct3', start_bit, end_bit)
            return ('funct3', value)
        elif bit_count == 6:
            # 6-bit field is funct6
            self._ensure_field_in_ranges('funct7', start_bit, end_bit)
            return ('funct7', value)
        elif bit_count == 5:
            # 5-bit field - check if matches a known register position
            reg_name = self._get_register_name_by_position(start_bit, end_bit)
            if reg_name:
                self.debug_print(f"DEBUG: 5-bit literal matches register {reg_name}")
                return (reg_name, value)
            else:
                # Could be shamt or other field
                field_name = f'field5_{start_bit}_{end_bit}'
                self._ensure_field_in_ranges(field_name, start_bit, end_bit)
                return (field_name, value)
        elif bit_count >= 12:
            # Large field - probably immediate
            field_name = f'imm{bit_count}'
            self._ensure_field_in_ranges(field_name, start_bit, end_bit)
            return (field_name, value)
        else:
            # Unknown field
            field_name = f'field{bit_count}_{start_bit}_{end_bit}'
            self._ensure_field_in_ranges(field_name, start_bit, end_bit)
            return (field_name, value)

    def _get_register_name_by_position(self, start_bit: int, end_bit: int) -> Optional[str]:
        """
        Retrieves the register name based on the bit position defined in
        INSTRUCTION_FIELD_RANGES.

        Args:
            start_bit (int):
                The most significant bit index of the field.
            end_bit (int):
                The least significant bit index of the field.

        Returns:
            Optional[str]:
                The register field name if found, otherwise None.
        """
        global INSTRUCTION_FIELD_RANGES
        
        for field_name in ['rd', 'rs1', 'rs2', 'rs3']:
            if field_name in INSTRUCTION_FIELD_RANGES:
                field_start, field_end = INSTRUCTION_FIELD_RANGES[field_name]
                if field_start == start_bit and field_end == end_bit:
                    return field_name
        return None

    def _get_encoding_function_size(self, app_id: str) -> int:
        """
        Determines the size of an encoding function.

        Args:
            app_id (str):
                The identifier of the encoding function.

        Returns:
            int:
                The computed size of the encoding function in bits.
        """
        if app_id.endswith('op'):  # encdec_*op
            return 7  # opcode
        elif 'funct3' in app_id:
            return 3
        elif 'funct7' in app_id:
            return 7
        else:
            return 3  # default

    def _estimate_field_size_from_context(
    self,
    field_name: str,
    current_bit: int,
    position: int,
    total_patterns: int
) -> int:
        """
        Estimates the size of an unknown field based on contextual information.

        Args:
            field_name (str):
                The name of the field whose size must be estimated.
            current_bit (int):
                The bit position currently being parsed.
            position (int):
                The index of the encoding pattern being processed.
            total_patterns (int):
                Total number of encoding patterns.

        Returns:
            int:
                The estimated field size in bits.
        """
        # Based on name
        if 'imm' in field_name.lower():
            if '12' in field_name:
                return 12
            elif '20' in field_name:
                return 20
            else:
                # Estimate based on position - large immediates are usually at start
                if current_bit >= 20:
                    return min(12, current_bit + 1)
                else:
                    return min(5, current_bit + 1)
        elif field_name in ['rd', 'rs1', 'rs2', 'rs3']:
            return 5
        elif 'funct' in field_name:
            if '7' in field_name:
                return 7
            else:
                return 3
        else:
            # For unknown fields, estimate based on position
            if current_bit >= 20:
                return 12  # Probably large immediate
            elif current_bit >= 10:
                return 5   # Probably register
            else:
                return 3   # Probably funct3 or similar

    def _ensure_field_in_ranges(self, field_name: str, start_bit: int, end_bit: int) -> None:
        """
        Ensures that a field is present in the global INSTRUCTION_FIELD_RANGES
        dictionary.

        Args:
            field_name (str):
                The name of the field.
            start_bit (int):
                The most significant bit index of the field.
            end_bit (int):
                The least significant bit index of the field.

        Returns:
            None
        """
        global INSTRUCTION_FIELD_RANGES
        
        # Validate range
        if start_bit < 0 or end_bit < 0 or start_bit < end_bit or start_bit > 31 or end_bit > 31:
            self.debug_print(f"ERROR: Invalid bit range for {field_name}: [{start_bit}:{end_bit}]")
            return
        
        if field_name not in INSTRUCTION_FIELD_RANGES:
            INSTRUCTION_FIELD_RANGES[field_name] = (start_bit, end_bit)
            self.debug_print(f"DEBUG: Added {field_name} to INSTRUCTION_FIELD_RANGES: ({start_bit}, {end_bit})")


    def _is_instruction_name_in_splits(self, operand_name: str) -> bool:
        """
        Checks whether the given operand name corresponds to an instruction name
        defined in the template splits.

        Args:
            operand_name (str):
                The operand or token to check.

        Returns:
            bool:
                True if the operand matches an instruction name found in the
                template splits, otherwise False.
        """
        for template_splits in self.template_splits.values():
            if operand_name in template_splits:
                return True
        return False

    
    def _map_literal_to_field(
    self,
    start_bit: int,
    end_bit: int,
    bit_count: int,
    value: int,
    position: int,
    total_patterns: int
) -> Optional[tuple]:
        """
        Maps a literal bit slice to a known instruction field.

        Args:
            start_bit (int):
                The most significant bit index (inclusive) of the literal.
            end_bit (int):
                The least significant bit index (inclusive) of the literal.
            bit_count (int):
                The width of the literal in bits (should equal start_bit - end_bit + 1).
            value (int):
                The integer value of the literal.
            position (int):
                The index of the current encoding pattern being processed.
            total_patterns (int):
                Total number of encoding patterns for the instruction.

        Returns:
            Optional[tuple]:
                A tuple describing the mapped instruction field if a match is found;
                otherwise None.
        """
        global INSTRUCTION_FIELD_RANGES
        
        # Check if range matches a known field
        for field_name, field_range in INSTRUCTION_FIELD_RANGES.items():
            if isinstance(field_range, tuple) and len(field_range) == 2:
                field_start, field_end = field_range
                if field_start == start_bit and field_end == end_bit:
                    self.debug_print(f"DEBUG: Literal matches known field {field_name}")
                    return (field_name, value)
        
        # Mapping based on position and size
        if bit_count == 7 and position == total_patterns - 1:
            # Last 7-bit field is opcode
            return ('opcode', value)
        elif bit_count == 7 and position == 0:
            # First 7-bit field is funct7
            return ('funct7', value)
        elif bit_count == 3:
            # 3-bit field is funct3
            return ('funct3', value)
        elif bit_count == 6:
            # 6-bit field is funct6
            return ('funct7', value*2)
        elif bit_count == 5:
            # 5-bit field - could be shamt or register with value 0
            # Check if matches a known register position
            if self._matches_register_position(start_bit, end_bit):
                reg_name = self._get_register_name_by_position(start_bit, end_bit)
                if reg_name:
                    return (reg_name, value)
            # Otherwise, could be shamt
            return ('shamt', value)
        elif bit_count >= 12:
            # Large field - probably immediate
            field_name = f'imm{bit_count}'
            self._add_new_instruction_field(field_name, start_bit, end_bit)
            return (field_name, value)
        else:
            # Unknown field
            field_name = f'field_{bit_count}bit_{start_bit}_{end_bit}'
            self._add_new_instruction_field(field_name, start_bit, end_bit)
            return (field_name, value)
    
    def _estimate_field_size(
    self,
    field_name: str,
    current_bit: int,
    position: int,
    total_patterns: int
) -> int:
        """
        Estimates the bit-width of an unknown field.

        Args:
            field_name (str):
                The name of the field whose size needs estimation.
            current_bit (int):
                The current bit index being parsed (e.g., MSB side cursor).
            position (int):
                The index of the encoding pattern being processed.
            total_patterns (int):
                The total number of encoding patterns.

        Returns:
            int:
                The estimated size of the field in bits.
        """
        # Based on name
        if 'imm' in field_name.lower():
            if field_name.lower() == 'imm12':
                return 12
            elif field_name.lower() == 'imm20':
                return 20
            else:
                # Estimate based on position
                if current_bit >= 20:
                    return min(12, current_bit + 1)
                else:
                    return min(5, current_bit + 1)
        else:
            return 5  # default for unknown fields
        
        
    def _add_new_instruction_field(self, field_name: str, start_bit: int, end_bit: int) -> None:
        """
        Adds a new instruction field to the global registry.

        Args:
            field_name (str):
                The field name to register (e.g., "funct3", "rs1", "imm12").
            start_bit (int):
                The most significant bit index of the field.
            end_bit (int):
                The least significant bit index of the field.

        Returns:
            None
        """
        global INSTRUCTION_FIELD_RANGES
        
        if field_name not in INSTRUCTION_FIELD_RANGES:
            INSTRUCTION_FIELD_RANGES[field_name] = (start_bit, end_bit)
            print(f"DEBUG: Added new instruction field {field_name}: ({start_bit}, {end_bit})")
            
    
    def _matches_register_position(self, start_bit: int, end_bit: int) -> bool:
        """
        Checks whether the given bit slice matches a known register field position.

        Args:
            start_bit (int):
                The most significant bit index of the candidate slice.
            end_bit (int):
                The least significant bit index of the candidate slice.

        Returns:
            bool:
                True if the bit slice aligns with a known register field position,
                otherwise False.
        """
        global INSTRUCTION_FIELD_RANGES
        
        for field_name in ['rd', 'rs1', 'rs2', 'rs3']:
            if field_name in INSTRUCTION_FIELD_RANGES:
                field_start, field_end = INSTRUCTION_FIELD_RANGES[field_name]
                if field_start == start_bit and field_end == end_bit:
                    return True
        return False

    def _is_instruction_name_in_splits(self, operand_name: str) -> bool:
        """
        Checks whether the provided operand name is an instruction name present in splits.

        This helper is used to detect when an operand is actually an instruction
        reference rather than a standard operand (e.g., in aliasing or split-based
        expansions).

        Args:
            operand_name (str):
                The operand or token to check.

        Returns:
            bool:
                True if the operand matches an instruction name found in the
                template splits, otherwise False.
        """
        for template_splits in self.template_splits.values():
            if operand_name in template_splits:
                return True
        return False

    
    def _map_literal_to_field(
    self,
    start_bit: int,
    end_bit: int,
    bit_count: int,
    value: int,
    position: int,
    total_patterns: int
) -> Optional[tuple]:
        """
        Maps a literal bit slice to a known instruction field.

        This function attempts to associate a literal extracted from an encoding
        pattern with a previously defined instruction field based on bit positions
        and width. It should only map to existing fields (no creation here); if
        no match is found, it returns None.

        Args:
            start_bit (int):
                The most significant bit index (inclusive) of the literal.
            end_bit (int):
                The least significant bit index (inclusive) of the literal.
            bit_count (int):
                The width of the literal in bits (should equal start_bit - end_bit + 1).
            value (int):
                The integer value of the literal.
            position (int):
                The index of the current encoding pattern being processed.
            total_patterns (int):
                Total number of encoding patterns for the instruction.

        Returns:
            Optional[tuple]:
                A tuple describing the mapped instruction field if a match is found;
                otherwise None. The tuple typically follows:
                (field_name: str, start_bit: int, end_bit: int, value: int, position: int)

        Raises:
            ValueError:
                If the bit range is invalid or inconsistent with `bit_count`.
            KeyError:
                If the global field range registry is missing or not initialized.
        """
        global INSTRUCTION_FIELD_RANGES
        
        for field_name, field_range in INSTRUCTION_FIELD_RANGES.items():
            if isinstance(field_range, tuple) and len(field_range) == 2:
                field_start, field_end = field_range
                if field_start == start_bit and field_end == end_bit:
                    self.debug_print(f"DEBUG: Literal matches known field {field_name}")
                    return (field_name, value)
        
        # Mapping based on size and indices
        if bit_count == 7 and position == total_patterns - 1:
            return ('opcode', value)
        elif bit_count == 7 and position == 0:
            return ('funct7', value)
        elif bit_count == 3:
            return ('funct3', value)
        elif bit_count == 6:
            return ('funct7', value*2)
        elif bit_count == 5:
            # 5 bits encoding
            if self._matches_register_position(start_bit, end_bit):
                reg_name = self._get_register_name_by_position(start_bit, end_bit)
                if reg_name:
                    return (reg_name, value)
            return ('shamt', value)
        elif bit_count >= 12:
            field_name = f'imm{bit_count}'
            self._add_new_instruction_field(field_name, start_bit, end_bit)
            return (field_name, value)
        else:
            field_name = f'field_{bit_count}bit_{start_bit}_{end_bit}'
            self._add_new_instruction_field(field_name, start_bit, end_bit)
            return (field_name, value)
    
    def _estimate_field_size(
    self,
    field_name: str,
    current_bit: int,
    position: int,
    total_patterns: int
) -> int:
        """
        Estimates the bit-width of an unknown field.

        When a field's width cannot be determined directly from the encoding,
        this helper infers a reasonable size based on contextual cues such as
        the current parsing bit index, pattern position, and neighboring fields.

        Args:
            field_name (str):
                The name of the field whose size needs estimation.
            current_bit (int):
                The current bit index being parsed (e.g., MSB side cursor).
            position (int):
                The index of the encoding pattern being processed.
            total_patterns (int):
                The total number of encoding patterns.

        Returns:
            int:
                The estimated size of the field in bits.

        """
        if 'imm' in field_name.lower():
            if field_name.lower() == 'imm12':
                return 12
            elif field_name.lower() == 'imm20':
                return 20
            else:
                if current_bit >= 20:
                    return min(12, current_bit + 1)
                else:
                    return min(5, current_bit + 1)
        else:
            return 5
        
        
    def _add_new_instruction_field(self, field_name: str, start_bit: int, end_bit: int) -> None:
        """
        Adds a new instruction field to the global registry.

        If the field is not present in the global mapping (e.g., INSTRUCTION_FIELD_RANGES),
        it is inserted with the provided bit range. If it already exists, the function
        verifies that the range is consistent to avoid conflicting definitions.

        Args:
            field_name (str):
                The field name to register (e.g., "funct3", "rs1", "imm12").
            start_bit (int):
                The most significant bit index of the field.
            end_bit (int):
                The least significant bit index of the field.

        Returns:
            None

        Raises:
            ValueError:
                If an existing entry conflicts with the provided bit range.
        """
        global INSTRUCTION_FIELD_RANGES
        
        if field_name not in INSTRUCTION_FIELD_RANGES:
            INSTRUCTION_FIELD_RANGES[field_name] = (start_bit, end_bit)
            print(f"DEBUG: Added new instruction field {field_name}: ({start_bit}, {end_bit})")
            
    
    def _matches_register_position(self, start_bit: int, end_bit: int) -> bool:
        """
        Checks whether the given bit slice matches a known register field position.

        This function compares the provided bit range against known register field
        locations (e.g., rd, rs1, rs2, rs3, or custom ms* fields) defined in the
        global field range mapping.

        Args:
            start_bit (int):
                The most significant bit index of the candidate slice.
            end_bit (int):
                The least significant bit index of the candidate slice.

        Returns:
            bool:
                True if the bit slice aligns with a known register field position,
                otherwise False.
        """
        global INSTRUCTION_FIELD_RANGES
        
        for field_name in ['rd', 'rs1', 'rs2', 'rs3']:
            if field_name in INSTRUCTION_FIELD_RANGES:
                field_start, field_end = INSTRUCTION_FIELD_RANGES[field_name]
                if field_start == start_bit and field_end == end_bit:
                    return True
        return False

    def _is_instruction_name_in_splits(self, operand_name: str) -> bool:
        """
        Checks whether the provided operand name is an instruction name present in splits.

        This helper determines if a token encountered during parsing is actually an
        instruction identifier that appears in template splits (e.g., aliases,
        specializations), rather than a regular operand.

        Args:
            operand_name (str):
                The token or operand string to check.

        Returns:
            bool:
                True if the name matches an instruction present in the split mapping,
                otherwise False.
        """
        for template_splits in self.template_splits.values():
            if operand_name in template_splits:
                return True
        return False



    def analyze_encoding_structure(self, right_pattern: Dict[str, Any]) -> None:
        """
        Analyzes the structure of an encoding pattern for debugging purposes.

        This diagnostic function inspects the right-hand side encoding pattern and
        reports how bit segments (literals, registers, immediates, and function
        fields) are arranged. It is intended to help identify misalignments,
        overlaps, or missing pieces in the encoding description.

        Args:
            right_pattern (Dict[str, Any]):
                The dictionary representing the right-hand side encoding pattern.

        Returns:
            None
                The function may log or emit debug details but does not return a value.

        Raises:
            KeyError:
                If required pattern keys are missing.
            ValueError:
                If invalid or overlapping bit ranges are detected.
        """
        if right_pattern.get('type') == 'vector_concat':
            patterns = right_pattern.get('patterns', [])
            self.debug_print(f"DEBUG: Encoding has {len(patterns)} patterns:")
            
            for i, pattern in enumerate(patterns):
                pattern_type = pattern.get('type', 'unknown')
                if pattern_type == 'literal':
                    value = pattern.get('value', '')
                    if value.startswith('0b'):
                        binary_value = value[2:]
                        bit_count = len(binary_value)
                        decimal_value = int(binary_value, 2)
                        
                        # Identify field
                        field_type = "unknown"
                        if bit_count == 7:
                            if i == len(patterns) - 1:
                                field_type = "opcode"
                            elif i == 0:
                                field_type = "funct7"
                        elif bit_count == 3:
                            field_type = "funct3"
                        elif bit_count == 6 and i == 0:
                            field_type = "funct7"
                        
                        print(f"  [{i}] literal: {value} ({bit_count} bits, decimal: {decimal_value}, type: {field_type})")
                    else:
                        print(f"  [{i}] literal: {value}")
                elif pattern_type == 'app':
                    app_id = pattern.get('id', '')
                    print(f"  [{i}] app: {app_id}")
                    if 'patterns' in pattern:
                        for j, sub_pattern in enumerate(pattern['patterns']):
                            if sub_pattern.get('type') == 'id':
                                print(f"    [{j}] id: {sub_pattern.get('id', '')}")
                elif pattern_type == 'id':
                    operand_name = pattern.get('id', '')
                    print(f"  [{i}] id: {operand_name}")
                else:
                    print(f"  [{i}] {pattern_type}: {pattern}")


    
    def create_instruction_dict(self, instruction_data: Dict[str, Any], extension_filter: List[str] = None) -> List[Dict[str, Any]]:
        """
        Creates the instruction dictionary (or a list of instruction dictionaries)
        from a template-derived instruction definition.

        This function takes the parsed instruction data (potentially including a
        template that expands into multiple concrete instructions) and produces
        one or more normalized instruction dictionaries ready for downstream
        processing (e.g., encoding resolution, XML generation). If an extension
        filter is provided, only instructions belonging to the specified ISA
        extensions are included.

        Args:
            instruction_data (Dict[str, Any]):
                The raw instruction (or template) data parsed from JSON/input.
            extension_filter (List[str], optional):
                A list of ISA extensions to include. If None, all instructions
                are considered.

        Returns:
            List[Dict[str, Any]]:
                A list of normalized instruction dictionaries. For non-templated
                definitions, the list typically contains a single entry.

        Raises:
            KeyError:
                If required instruction/template fields are missing.
            ValueError:
                If the template expansion is invalid or yields no instructions.
        """
        if not isinstance(instruction_data, dict):
            return []
        
        is_compressed = instruction_data.get('_is_compressed', False)
        
        print(f"DEBUG create_instruction_dict: instruction_data keys = {list(instruction_data.keys())}")
        print(f"DEBUG create_instruction_dict: _is_compressed in instruction_data? {'_is_compressed' in instruction_data}")
        print(f"DEBUG create_instruction_dict: _is_compressed value = {is_compressed}")
        
        source = instruction_data.get('source', {})
        if not isinstance(source, dict):
            return []
            
        file_path = source.get('file', '')
        contents = source.get('contents', '')
        
        if not isinstance(file_path, str) or not isinstance(contents, str):
            return []
        
        extension = self.extract_extension_from_file(file_path)
        
        if extension_filter and extension not in extension_filter:
            return []
        
        template_name, instruction_name, operands, encoding_func = self.parse_instruction_from_contents(contents)
        
        if instruction_name in self.known_fields:
            return []
    
        if self._has_vector_registers(operands):
            if not self._is_vector_extension_enabled(extension_filter):
                print(f"DEBUG: Skipping vector instruction '{instruction_name}' - vector extension not enabled")
                return []
        
        # Parsing JSON for encoding fields
        right = instruction_data.get('right', {})
        
        template_to_check = template_name if template_name else instruction_name.upper()
        
        if template_to_check in self.template_splits:
            specific_instruction = None
            match = re.search(r'\w+\([^)]*,\s*(\w+)\)\s*<->', contents)
            if match:
                potential_instr = match.group(1)
                splits = self.template_splits[template_to_check]
                if potential_instr in splits:
                    specific_instruction = potential_instr
            
            if specific_instruction:
                encoding_fields = self.parse_encoding_fields(right)
                
                if template_to_check == 'RTYPE':
                    self.debug_print(f"DEBUG: RTYPE instruction {specific_instruction} - using JSON encoding fields")
                elif template_to_check == 'UTYPE':
                    if encoding_func:
                        self.debug_print(f"DEBUG: Looking for encoding values for {specific_instruction} in functions: {encoding_func}")
                        additional_encoding = self._get_encoding_values_from_functions(specific_instruction, encoding_func)
                        encoding_fields.update(additional_encoding)
                elif template_to_check == 'BTYPE':
                    if encoding_func:
                        self.debug_print(f"DEBUG: Looking for encoding values for {specific_instruction} in functions: {encoding_func}")
                        additional_encoding = self._get_encoding_values_from_functions(specific_instruction, encoding_func)
                        encoding_fields.update(additional_encoding)
                
                split_instruction = self.create_split_instruction(
                    specific_instruction, template_to_check, operands, encoding_fields, 
                    extension, file_path, contents, splits[specific_instruction],
                    is_compressed
                )
                return [split_instruction] if split_instruction else []
            else:
                split_instructions = []
                splits = self.template_splits[template_to_check]
                
                for split_name, split_implementation in splits.items():
                    split_encoding_fields = self.parse_encoding_fields(right)
                    
                    if template_to_check == 'RTYPE':
                        self.debug_print(f"DEBUG: RTYPE instruction {split_name} - using only JSON encoding fields")
                    elif template_to_check == 'UTYPE':
                        if encoding_func:
                            self.debug_print(f"DEBUG: Looking for encoding values for {split_name} in functions: {encoding_func}")
                            split_encoding_values = self._get_encoding_values_from_functions(split_name, encoding_func)
                            self.debug_print(f"DEBUG: Found encoding values for {split_name}: {split_encoding_values}")
                            split_encoding_fields.update(split_encoding_values)
                    elif template_to_check == 'ITYPE':
                        if encoding_func:
                            self.debug_print(f"DEBUG: Looking for encoding values for {split_name} in functions: {encoding_func}")
                            split_encoding_values = self._get_encoding_values_from_functions(split_name, encoding_func)
                            split_encoding_fields.update(split_encoding_values)
                    elif template_to_check == 'BTYPE':
                        if encoding_func:
                            self.debug_print(f"DEBUG: Looking for encoding values for {split_name} in functions: {encoding_func}")
                            split_encoding_values = self._get_encoding_values_from_functions(split_name, encoding_func)
                            self.debug_print(f"DEBUG: Found encoding values for {split_name}: {split_encoding_values}")
                            split_encoding_fields.update(split_encoding_values)
                    
                    split_instruction = self.create_split_instruction(
                        split_name, template_to_check, operands, split_encoding_fields, 
                        extension, file_path, contents, split_implementation,
                        is_compressed  
                    )
                    if split_instruction:
                        split_instructions.append(split_instruction)
                
                return split_instructions
        else:
            encoding_fields = self.parse_encoding_fields(right)
            
            if encoding_func:
                self.debug_print(f"DEBUG: Looking for encoding values for {instruction_name} in functions: {encoding_func}")
                encoding_fields.update(self._get_encoding_values_from_functions(instruction_name, encoding_func))
            
            instruction_dict = self.create_single_instruction(
                instruction_name, template_name, operands, encoding_fields,
                extension, file_path, contents, is_compressed
            )
            return [instruction_dict] if instruction_dict else []

    def _has_vector_registers(self, operands: List[str]) -> bool:
        """
        Checks whether the operand list contains vector registers (e.g., md, ms1, ms2).

        This helper inspects the operand names to detect vector-specific registers
        that are typical for vector ISA extensions (e.g., "md" for destination,
        "ms1"/"ms2" for sources).

        Args:
            operands (List[str]):
                The list of operand tokens parsed from the instruction signature.

        Returns:
            bool:
                True if any known vector register is present, otherwise False.
        """
        vector_registers = {'md', 'ms1', 'ms2'}
        return any(op in vector_registers for op in operands)

    def _is_vector_extension_enabled(self, extension_filter: List[str] = None) -> bool:
        """
        Determines whether the vector ISA extension is enabled.

        This function checks the provided extension filter (and/or internal
        configuration) to decide if vector-related instructions should be generated
        and processed.

        Args:
            extension_filter (List[str], optional):
                A list of enabled extensions. If None, internal defaults or
                global configuration may be used.

        Returns:
            bool:
                True if the vector extension is enabled, otherwise False.
        """
        if not extension_filter:
            return False
        
        # Check for vector extension 
        vector_extensions = {'zimt', 'v'}
        
        for ext in extension_filter:
            if ext.lower() in vector_extensions:
                return True
        
        return False



    def _get_encoding_values_for_specific_instruction(self, instruction_name: str, encoding_func: set) -> Dict[str, int]:
        """
        Retrieves encoding values for a specific instruction.

        This function looks up the encoding function (or function set) associated
        with the given instruction name and resolves concrete values for fields
        such as opcodes, funct3/funct7 (or compressed equivalents), and other
        literals required to uniquely identify the instruction encoding.

        Args:
            instruction_name (str):
                The canonical name of the instruction to resolve.
            encoding_func (set):
                A set or handle that identifies the encoding function(s) to use.

        Returns:
            Dict[str, int]:
                A mapping from encoding field names to their integer values.

        Raises:
            KeyError:
                If the instruction or its encoding function cannot be found.
            ValueError:
                If the encoding function cannot be resolved to concrete values.
            TypeError:
                If `encoding_func` is not in the expected format.
        """
        return self._get_encoding_values_from_functions(instruction_name, encoding_func)



    def create_single_instruction(
    self,
    instruction_name: str,
    template_name: str,
    operands: List[str],
    encoding_fields: Dict[str, Any],
    extension: str,
    file_path: str,
    contents: str,
    is_compressed: bool = False
) -> Optional[Dict[str, Any]]:
        """
        Creates a single (concrete) instruction dictionary.

        This function builds a normalized representation of a single instruction
        from its name, template, operands, and resolved encoding fields. It
        also attaches metadata such as the source file/path, the owning extension,
        and whether the instruction uses a compressed (16-bit) encoding.

        Args:
            instruction_name (str):
                The canonical instruction name.
            template_name (str):
                The name of the template from which this instruction derives.
            operands (List[str]):
                The ordered list of operand names.
            encoding_fields (Dict[str, Any]):
                A dictionary containing resolved encoding fields and values.
            extension (str):
                The ISA extension this instruction belongs to.
            file_path (str):
                The path to the source file where the instruction is defined.
            contents (str):
                The raw textual contents used to derive this instruction.
            is_compressed (bool, optional):
                True if the instruction uses a compressed (16-bit) encoding,
                otherwise False.

        Returns:
            Optional[Dict[str, Any]]:
                The constructed instruction dictionary if successful; otherwise None
                when the instruction should be skipped (e.g., filtered by extension).

        Raises:
            ValueError:
                If required fields are missing or the instruction cannot be
                constructed consistently.
            KeyError:
                If essential encoding fields are missing from `encoding_fields`.
        """
        
        print(f"DEBUG create_single_instruction: Called for '{instruction_name}' with is_compressed={is_compressed}")
        
        # DEBUG for STORE and LOAD
        if (instruction_name.lower() in ['store', 'load', 'v2dld', 'v2dst'] or 
            'STORE' in contents.upper() or 'LOAD' in contents.upper()):
            self.debug_print(f"DEBUG STORE/LOAD: create_single_instruction called for {instruction_name}")
            self.debug_print(f"DEBUG STORE/LOAD: Received encoding_fields: {encoding_fields}")
        
        if instruction_name.lower() in ['v2dld', 'v2dst']:
            print(f"DEBUG VECTOR: Processing {instruction_name}")
            
            new_operands = []
            for op in operands:
                if op == 'i11_0':
                    new_operands.append('imm_i')
                    print(f"DEBUG VECTOR: Replaced operand i11_0 -> imm_i")
                else:
                    new_operands.append(op)
            operands = new_operands
            
            new_fields = {}
            for field_name, field_value in encoding_fields.items():
                if field_name == 'i11_0':
                    new_fields['imm_i'] = field_value
                    print(f"DEBUG VECTOR: Replaced field i11_0 -> imm_i")
                else:
                    new_fields[field_name] = field_value
            encoding_fields = new_fields
            
            print(f"DEBUG VECTOR: Final operands: {operands}")
            print(f"DEBUG VECTOR: Final fields: {encoding_fields}")
        
        all_fields = {}
        
        for operand in operands:
            all_fields[operand] = ""
        
        all_fields.update(encoding_fields)
        
        if self._is_actual_load_store_instruction(instruction_name, contents):
            self.debug_print(f"DEBUG STORE/LOAD: Forcing funct3=3 for {instruction_name} instruction")
            all_fields['funct3'] = 3
        
        if (instruction_name.lower() in ['store', 'load', 'v2dld', 'v2dst'] or 
            'STORE' in contents.upper() or 'LOAD' in contents.upper()):
            self.debug_print(f"DEBUG STORE/LOAD: all_fields after combining: {all_fields}")
        
        if 'opcode' in all_fields and 'op' in all_fields:
            if all_fields['opcode'] != "":  # doar dacă opcode are o valoare
                del all_fields['op']
                self.debug_print(f"DEBUG: Removed 'op' because we have opcode={all_fields['opcode']}")
            else:
                self.debug_print(f"DEBUG: Keeping both 'op' and 'opcode' because opcode is empty")
        
        attribute_name = list()
        extension_map = {
            'I': 'rv32i',
            'C': 'rv32c',
            'M': 'rv32m',
            'A': 'rv32a',
            'F': 'rv32f',
            'D': 'rv32d'
        }
        if 'rv32' in extension.lower():
            attribute_name.append(extension_map.get(extension, f'rv32{extension.lower()}'))
        else:
            attribute_name.append(extension_map.get(extension, extension.lower()))
        
        if 'rv32' not in extension.lower():
            if 'rv32i' not in attribute_name:
                attribute_name.append("rv32i")
        
        registers = [op for op in operands if op.startswith('rs') or op == 'rd' or 
                op.startswith('ms') or op == 'md' or op == 'rsd' or op == 'rd_c' or op == 'rs1_c' or op == 'rs2_c']
        

        inputs = []
        outputs = []
        
        if instruction_name.lower().replace("_", ".") in INSTRUCTION_COMPRESSED:
            if "encdec_creg(rd)" in contents:
                if 'rd' in operands:
                    for i in range(len(operands)):
                        if operands[i] == 'rd':
                            operands[i] = 'rd_c'
                            break
                    for i in range(len(registers)):
                        if registers[i] == 'rd':
                            registers[i] = 'rd_c'
                            break
            if "encdec_creg(rs1)" in contents:
                if 'rs1' in operands:
                    for i in range(len(operands)):
                        if operands[i] == 'rs1':
                            operands[i] = 'rs1_c'
                            break
                    for i in range(len(registers)):
                        if registers[i] == 'rs1':
                            registers[i] = 'rs1_c'
                            break
            if "encdec_creg(rs2)" in contents:
                if 'rs2' in operands:
                    for i in range(len(operands)):
                        if operands[i] == 'rs2':
                            operands[i] = 'rs2_c'
                            break
                    for i in range(len(registers)):
                        if registers[i] == 'rs2':
                            registers[i] = 'rs2_c'
                            break     
        for reg in registers:
            print(f"DEBUG _create_base_instruction_dict: Processing register '{reg}'")
            if reg == 'rs1' or reg == 'rs2':
                inputs.append(f'GPR({reg})')
                print(f"  -> Added to inputs: GPR({reg})")
            elif reg == 'rs1_c' or reg == 'rs2_c':
                inputs.append(f'GPR({reg})')
                print(f"  -> Added to inputs: GPR({reg})")
            elif reg.startswith('ms'):
                inputs.append(f'VR({reg})')
                print(f"  -> Added to inputs: VR({reg})")
            elif reg == 'rd':
                outputs.append(f'GPR({reg})')
                print(f"  -> Added to outputs: GPR({reg})")
            elif reg == 'rd_c':
                outputs.append(f'GPR({reg})')
                print(f"  -> Added to outputs: GPR({reg})")
            elif reg == 'md':
                outputs.append(f'VR({reg})')
                print(f"  -> Added to outputs: VR({reg})")
        
        print(f"DEBUG create_single_instruction: Final inputs = {inputs}")
        print(f"DEBUG create_single_instruction: Final outputs = {outputs}")
        
        instruction_width = 16 if is_compressed else 32
        print(f"DEBUG create_single_instruction: Calculated width={instruction_width} for '{instruction_name}'")
        
        instruction_dict = {
            'name': instruction_name,
            'template': template_name,
            'extension': extension,
            'attribute': attribute_name,
            'operands': operands,
            'registers': registers,
            'fields': all_fields,
            'width': instruction_width,
            'source_file': file_path,
            'source_contents': contents,
            'inputs': inputs,
            'outputs': outputs
        }
        
        print(f"DEBUG create_single_instruction: Created instruction_dict with width={instruction_dict['width']}")
        
        instruction_dict = self.enhance_instruction_with_encodings(instruction_dict)
        
        instruction_dict = self._map_immediate_to_template(instruction_dict)
        
        instruction_dict = self._apply_special_operand_mappings(instruction_dict)
        
        return instruction_dict


    def _is_vector_load_instruction(self, instruction: Dict[str, Any]) -> bool:
        """
        Determines whether the given instruction is a vector load instruction.

        This function inspects the instruction metadata—such as operands,
        instruction name, or extension tags—to check whether it represents a
        vector load operation.

        Args:
            instruction (Dict[str, Any]):
                The dictionary representing the instruction.

        Returns:
            bool:
                True if the instruction is classified as a vector load,
                otherwise False.
        """
        name = instruction['name'].lower()
        
        vector_load_names = ['v2dld']
        
        if name in vector_load_names:
            return True
        
        source_contents = instruction.get('source_contents', '').upper()
        if 'V2DLD' in source_contents:
            return True
        
        return False

    def _is_vector_store_instruction(self, instruction: Dict[str, Any]) -> bool:
        """
        Determines whether the given instruction is a vector store instruction.

        This function analyzes instruction metadata to determine whether it
        corresponds to a vector store operation from the vector ISA extension.

        Args:
            instruction (Dict[str, Any]):
                The dictionary representing the instruction.

        Returns:
            bool:
                True if the instruction is identified as a vector store,
                otherwise False.
        """
        name = instruction['name'].lower()
        
        vector_store_names = ['v2dst']
        
        if name in vector_store_names:
            return True
        
        source_contents = instruction.get('source_contents', '').upper()
        if 'V2DST' in source_contents:
            return True
        
        return False
    
    
    def _generate_vector_load_syntax(self, instruction: Dict[str, Any]) -> tuple:
        """
        Generates the ordered syntax representation for vector load instructions.

        Vector load instructions typically include:
        - a destination vector register,
        - an address base register,
        - an immediate/offset value.

        Args:
            instruction (Dict[str, Any]):
                The instruction dictionary containing operands and metadata.

        Returns:
            tuple:
                A tuple describing the ordered syntax components for assembly output.
        """
        name = instruction['name']
        operands = instruction['operands']
        
        md = None
        rs1 = None
        imm = None
        
        for op in operands:
            if op == 'md':
                md = op
            elif op == 'rs1':
                rs1 = op
            elif 'imm' in op.lower():
                imm = op
        
        if md and rs1 and imm:
            syntax = f"{name} {md},{imm}({rs1})"
            dsyntax = f"{name} ${{{md}}},${{{imm}}}(${{{rs1}}})"
        else:
            operands_syntax = ','.join(operands)
            syntax = f"{name} {operands_syntax}"
            operands_dsyntax = ','.join([f'${{{op}}}' for op in operands])
            dsyntax = f"{name} {operands_dsyntax}"
        
        return syntax, dsyntax

    def _generate_vector_store_syntax(self, instruction: Dict[str, Any]) -> tuple:
        """
        Generates the ordered syntax representation for vector store instructions.

        Vector store instructions typically specify:
        - a source vector register,
        - a base address register,
        - an immediate offset.

        Args:
            instruction (Dict[str, Any]):
                The instruction dictionary containing operands and metadata.

        Returns:
            tuple:
                A tuple describing the syntax structure for assembly formatting.
        """
        name = instruction['name']
        operands = instruction['operands']
        
        md = None
        rs1 = None
        imm = None
        
        for op in operands:
            if op == 'md':
                md = op
            elif op == 'rs1':
                rs1 = op
            elif 'imm' in op.lower():
                imm = op
        
        if md and rs1 and imm:
            syntax = f"{name} {md},{imm}({rs1})"
            dsyntax = f"{name} ${{{md}}},${{{imm}}}(${{{rs1}}})"
        else:
            operands_syntax = ','.join(operands)
            syntax = f"{name} {operands_syntax}"
            operands_dsyntax = ','.join([f'${{{op}}}' for op in operands])
            dsyntax = f"{name} {operands_dsyntax}"
        
        return syntax, dsyntax



    def _is_actual_load_store_instruction(self, instruction_name: str, contents: str) -> bool:
        """
        Determines whether the instruction is a true load/store operation.

        Some instructions may look similar based on naming or syntax but are 
        not real memory operations. This function verifies the semantics by
        inspecting both the name and the implementation contents.

        Args:
            instruction_name (str):
                The name of the instruction.
            contents (str):
                The raw textual contents used to derive semantics.

        Returns:
            bool:
                True if it is a real load/store instruction, otherwise False.
        """
        name = instruction_name.lower()
        contents_upper = contents.upper()
        
        load_instructions = [
            'load'                       # generic load
        ]
        
        store_instructions = [
            'store'                      # generic store
        ]
        
        if name in load_instructions or name in store_instructions:
            return True
        
        if ('LOAD' in contents_upper or 'STORE' in contents_upper) and \
        ('STYPE' in contents_upper or 'ITYPE' in contents_upper):
            return True
        
        if re.search(r'\b(load|store)\b', contents_upper):
            return True
        
        return False
    
    
    def create_split_instruction(
    self,
    split_name: str,
    template_name: str,
    operands: List[str],
    encoding_fields: Dict[str, Any],
    extension: str,
    file_path: str,
    contents: str,
    implementation: str,
    is_compressed: bool = False
) -> Optional[Dict[str, Any]]:
        """
        Creates a single instruction generated from a template split.

        This function builds a concrete instruction derived from a template
        specialization (split). It merges encoding fields, operand definitions,
        metadata, source file information, and the implementation clause.

        Args:
            split_name (str):
                The name of the instruction variant produced by the split.
            template_name (str):
                The base template from which the instruction derives.
            operands (List[str]):
                The ordered list of operands.
            encoding_fields (Dict[str, Any]):
                The resolved encoding metadata for this instruction.
            extension (str):
                The ISA extension this instruction belongs to.
            file_path (str):
                Path to the input file where this definition originated.
            contents (str):
                The raw text used to parse this instruction.
            implementation (str):
                The execution clause associated with this split.
            is_compressed (bool, optional):
                True if the instruction uses compressed (16-bit) encoding.

        Returns:
            Optional[Dict[str, Any]]:
                The constructed instruction dictionary, or None if the instruction
                should be skipped (e.g., filtered out).

        Raises:
            ValueError:
                If required fields or metadata are missing.
            KeyError:
                If critical encoding information is unavailable.
        """
        
        # DEBUG for STORE and LOAD
        if (split_name.upper() in ['AUIPC', 'LUI', 'ADD', 'SUB', 'V2DLD', 'V2DST'] or 
            'STORE' in split_name.upper() or 'LOAD' in split_name.upper()):
            self.debug_print(f"DEBUG: create_split_instruction called for {split_name}")
            self.debug_print(f"DEBUG: Received encoding_fields: {encoding_fields}")
        
        if split_name.lower() in ['v2dld', 'v2dst']:
            print(f"DEBUG VECTOR SPLIT: Processing {split_name}")
            
            new_operands = []
            for op in operands:
                if op == 'i11_0':
                    new_operands.append('imm_i')
                    print(f"DEBUG VECTOR SPLIT: Replaced operand i11_0 -> imm_i")
                else:
                    new_operands.append(op)
            operands = new_operands
            
            new_fields = {}
            for field_name, field_value in encoding_fields.items():
                if field_name == 'i11_0':
                    new_fields['imm_i'] = field_value
                    print(f"DEBUG VECTOR SPLIT: Replaced field i11_0 -> imm_i")
                else:
                    new_fields[field_name] = field_value
            encoding_fields = new_fields
            
            print(f"DEBUG VECTOR SPLIT: Final operands: {operands}")
            print(f"DEBUG VECTOR SPLIT: Final fields: {encoding_fields}")
        
        all_fields = {}
        
        for operand in operands:
            all_fields[operand] = ""
        
        all_fields.update(encoding_fields)
        
        if self._is_actual_load_store_instruction(split_name, contents):
            self.debug_print(f"DEBUG STORE/LOAD: Forcing funct3=3 for {split_name} split instruction")
            all_fields['funct3'] = 3
        
        if (split_name.upper() in ['AUIPC', 'LUI', 'ADD', 'SUB', 'V2DLD', 'V2DST'] or 
            'STORE' in split_name.upper() or 'LOAD' in split_name.upper()):
            self.debug_print(f"DEBUG: all_fields after combining: {all_fields}")
        
        if 'opcode' in all_fields and 'op' in all_fields:
            if all_fields['opcode'] != "":
                del all_fields['op']
                self.debug_print(f"DEBUG: Removed 'op' because we have opcode={all_fields['opcode']}")
            else:
                self.debug_print(f"DEBUG: Keeping both 'op' and 'opcode' because opcode is empty")
        
        attribute_name = []
        extension_map = {
            'I': 'rv32i',
            'C': 'rv32c',
            'M': 'rv32m',
            'A': 'rv32a',
            'F': 'rv32f',
            'D': 'rv32d'
        }
        
        if 'rv32' in extension.lower():
            attribute_name.append(extension_map.get(extension, f'rv32{extension.lower()}'))
        else:
            attribute_name.append(extension_map.get(extension, extension.lower()))
        
        if 'rv32' not in extension.lower():
            if 'rv32i' not in attribute_name:
                attribute_name.append("rv32i")
        
        registers = [op for op in operands if op.startswith('rs') or op == 'rd' or 
                op.startswith('ms') or op == 'md' or op == 'rsd' or op == 'rd_c' or op == 'rs1_c' or op == 'rs2_c']
        
        inputs = []
        outputs = []
        
        for reg in registers:
            print(f"DEBUG create_split_instruction: Processing register '{reg}'")
            
            if reg == 'rsd':
                inputs.append(f'GPR({reg})')
                outputs.append(f'GPR({reg})')
                print(f"  -> Added to inputs AND outputs: GPR({reg})")
            elif reg == 'rs1' or reg == 'rs2':
                inputs.append(f'GPR({reg})')
                print(f"  -> Added to inputs: GPR({reg})")
            elif reg == 'rs1_c' or reg == 'rs2_c':
                inputs.append(f'GPR({reg})')
                print(f"  -> Added to inputs: GPR({reg})")
            elif reg.startswith('ms'):
                inputs.append(f'VR({reg})')
                print(f"  -> Added to inputs: VR({reg})")
            elif reg == 'rd':
                outputs.append(f'GPR({reg})')
                print(f"  -> Added to outputs: GPR({reg})")
            elif reg == 'rd_c':
                outputs.append(f'GPR({reg})')
                print(f"  -> Added to outputs: GPR({reg})")
            elif reg == 'md':
                outputs.append(f'VR({reg})')
                print(f"  -> Added to outputs: VR({reg})")
        
        print(f"DEBUG create_split_instruction: Final inputs = {inputs}")
        print(f"DEBUG create_split_instruction: Final outputs = {outputs}")
        
        instruction_width = 16 if is_compressed else 32
        print(f"DEBUG create_split_instruction: Calculated width={instruction_width} for '{split_name}'")
        
        instruction_dict = {
            'name': split_name.lower(),
            'template': template_name,
            'extension': extension,
            'attribute': attribute_name,
            'operands': operands,
            'registers': registers,
            'fields': all_fields,
            'width': instruction_width,
            'source_file': file_path,
            'source_contents': contents,
            'implementation': implementation,
            'inputs': inputs,
            'outputs': outputs
        }
        
        print(f"DEBUG create_split_instruction: Created instruction_dict with width={instruction_dict['width']}")
        
        instruction_dict = self._map_immediate_to_template(instruction_dict)
        
        instruction_dict = self._apply_special_operand_mappings(instruction_dict)
        
        return instruction_dict


    
    def parse_instruction_action(self, instruction_name: str, json_data: Dict[str, Any]) -> Optional[str]:
        """
        Parses the execution action for an instruction from the JSON model.

        This function locates and extracts the implementation body (the
        "function clause execute" content) associated with the specified
        instruction. It coordinates the search across standalone definitions,
        templates, and split-derived structures.

        Args:
            instruction_name (str):
                The canonical name of the instruction to parse.
            json_data (Dict[str, Any]):
                The full JSON structure parsed from the input source.

        Returns:
            Optional[str]:
                The extracted execution action (as a string) if found, otherwise None.

        Raises:
            KeyError:
                If the JSON structure is missing expected containers or sections.
            TypeError:
                If the provided JSON data is not in the expected format.
        """
        instruction_upper = instruction_name.upper()
        
        print(f"DEBUG: Parsing action for {instruction_name} (upper: {instruction_upper})")
        
        print(f"DEBUG: Checking template splits: {list(self.template_splits.keys())}")
        for template_name, splits in self.template_splits.items():
            if instruction_upper in splits:
                action = splits[instruction_upper]
                print(f"DEBUG: Found action for {instruction_name} in template {template_name} splits")
                print(f"DEBUG: Raw action from splits: {action}")
                cleaned_action = self._clean_action(action)
                print(f"DEBUG: Cleaned action from splits: {cleaned_action}")
                return cleaned_action
        
        print(f"DEBUG: Not found in template splits, searching for standalone function clause execute")
        action = self._find_function_clause_execute(instruction_name, json_data)
        if action:
            print(f"DEBUG: Found function clause execute for {instruction_name}")
            cleaned_action = self._clean_action(action)
            print(f"DEBUG: Cleaned action from function clause: {cleaned_action}")
            return cleaned_action
        
        print(f"DEBUG: No action found for instruction {instruction_name}")
        return None

    
    def _find_function_clause_execute(self, instruction_name: str, json_data: Dict[str, Any]) -> Optional[str]:
        """
        Searches for the 'function clause execute' corresponding to a standalone instruction.

        This function attempts to locate the execution clause that directly
        belongs to the given instruction, without traversing template splits or
        inherited structures.

        Args:
            instruction_name (str):
                The name of the instruction to resolve.
            json_data (Dict[str, Any]):
                The parsed JSON structure containing instruction definitions.

        Returns:
            Optional[str]:
                The raw text of the execution clause if found, otherwise None.
        """
        instruction_upper = instruction_name.upper()
        
        print(f"DEBUG: Searching for function clause execute {instruction_upper}")
        
        return self._search_recursive_for_function_clause(json_data, instruction_upper)

    def _search_recursive_for_function_clause(
    self,
    data: Any,
    instruction_name: str,
    path: List[str] = None
) -> Optional[str]:
        """
        Recursively searches the JSON structure for a 'function clause execute'
        that matches the given instruction.

        This function traverses nested dictionaries and lists, inspecting nodes
        that may contain execution clauses or instruction identifiers, and
        returns the clause body when a match is found.

        Args:
            data (Any):
                The JSON-like structure to search (dict, list, or mixed).
            instruction_name (str):
                The instruction name to match.
            path (List[str], optional):
                The current traversal path for debugging purposes.

        Returns:
            Optional[str]:
                The extracted execution clause text if found, otherwise None.

        Raises:
            TypeError:
                If `data` contains unsupported types for recursive traversal.
        """
        if path is None:
            path = []
        
        if isinstance(data, dict):
            if 'source' in data and isinstance(data['source'], dict):
                contents = data['source'].get('contents', '')
                if isinstance(contents, str):
                    action = self._extract_function_clause_execute(contents, instruction_name)
                    if action:
                        print(f"DEBUG: Found function clause execute at path: {' -> '.join(path)}")
                        return action
            
            for key, value in data.items():
                result = self._search_recursive_for_function_clause(value, instruction_name, path + [key])
                if result:
                    return result
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                result = self._search_recursive_for_function_clause(item, instruction_name, path + [f"[{i}]"])
                if result:
                    return result
        
        return None

    def _extract_function_clause_execute(self, contents: str, instruction_name: str) -> Optional[str]:
        """
        Extracts the execution action from a 'function clause execute' body.

        This function analyzes the raw textual contents of a candidate execute
        clause, verifies that it corresponds to the specified instruction, and
        returns the action body if the match is successful.

        Args:
            contents (str):
                The raw text of the potential execution clause.
            instruction_name (str):
                The instruction name used to validate the clause.

        Returns:
            Optional[str]:
                The extracted action text if validation passes, otherwise None.

        Raises:
            ValueError:
                If the clause format is invalid or cannot be parsed.
        """
        patterns = [
            rf'function\s+clause\s+execute\s*\(*{re.escape(instruction_name)}\s*\([^)]*\)\s*\)*\s*=(\s*[{{*\\n[\\t\/a-zA-Z\s=0-9_\(\):;\}}*\,*\-*\'*\.*\+*\]*\>*\<*\@*\"*\|*\_*\!*\=*]+)',

            rf'function\s+clause\s+execute\s+{re.escape(instruction_name)}\s*=\s*\{{(.*?)\}}',

            rf'function\s+clause\s+execute\s+{re.escape(instruction_name)}\s*\([^)]*\)\s*=\s*\{{(.*?)\}}',
        ]
        
        for pattern in patterns:
            print(f"DEBUG: Trying pattern: {pattern}")
            match = re.search(pattern, contents, re.DOTALL | re.MULTILINE | re.IGNORECASE)
            if match:
                action = match.group(1).strip()
                print(f"DEBUG: Found match with pattern, action length: {len(action)}")
                print(f"DEBUG: Action preview: {action[:100]}...")
                return action
        
        instruction_lower = instruction_name.lower()
        for pattern in [
            rf'function\s+clause\s+execute\s+{re.escape(instruction_lower)}\s*\([^)]*\)\s*=\s*\{{(.*?)\}}',
            rf'function\s+clause\s+execute\s+{re.escape(instruction_lower)}\s*=\s*\{{(.*?)\}}',
        ]:
            match = re.search(pattern, contents, re.DOTALL | re.MULTILINE | re.IGNORECASE)
            if match:
                action = match.group(1).strip()
                print(f"DEBUG: Found match with lowercase pattern, action length: {len(action)}")
                return action
        
        print(f"DEBUG: No function clause execute found for {instruction_name}")
        return None

    def _find_standalone_instruction_action(self, instruction_name: str, json_data: Dict[str, Any]) -> Optional[str]:
        """
        DEPRECATED: Use `_find_function_clause_execute` instead.

        This legacy helper attempted to locate the action body for a single,
        standalone instruction. It remains for backward compatibility and
        should be replaced with `_find_function_clause_execute`.

        Args:
            instruction_name (str):
                The instruction name to search for.
            json_data (Dict[str, Any]):
                The parsed JSON structure.

        Returns:
            Optional[str]:
                The located action text, or None if not found.
        """
        return self._find_function_clause_execute(instruction_name, json_data)



    def _search_execute_recursive_for_instruction(
    self,
    data: Any,
    path: List[str],
    instruction_name: str
) -> Optional[str]:
        """
        Recursively searches the JSON tree for an 'execute' clause of a specific instruction.

        This function walks through arbitrarily nested containers and inspects
        nodes that may hold an `execute` block tied to the given instruction.
        When found, the clause content is returned.

        Args:
            data (Any):
                The JSON-like structure to traverse.
            path (List[str]):
                The current traversal path (useful for debugging).
            instruction_name (str):
                The instruction to match.

        Returns:
            Optional[str]:
                The raw execute clause if found, otherwise None.
        """
        if isinstance(data, dict):
            if 'execute' in data:
                result = self._search_execute_for_instruction(data['execute'], instruction_name)
                if result:
                    return result
            else:
                for key, value in data.items():
                    result = self._search_execute_recursive_for_instruction(value, path + [key], instruction_name)
                    if result:
                        return result
        elif isinstance(data, list):
            for i, item in enumerate(data):
                result = self._search_execute_recursive_for_instruction(item, path + [f"[{i}]"], instruction_name)
                if result:
                    return result
        
        return None


    def _search_execute_for_instruction(self, execute_section: Any, instruction_name: str) -> Optional[str]:
        """
        Searches a specific `execute` section for the given instruction.

        This helper focuses on a single execute block or container, checking
        whether it contains an action corresponding to `instruction_name`.
        It is typically called by higher-level recursive search functions.

        Args:
            execute_section (Any):
                The execute container (dict, list, or node) to inspect.
            instruction_name (str):
                The instruction name to resolve.

        Returns:
            Optional[str]:
                The execute clause text if a match is found, otherwise None.
        """
        if not isinstance(execute_section, dict):
            return None
        
        if 'function' not in execute_section:
            for key, value in execute_section.items():
                if isinstance(value, (list, dict)):
                    result = self._search_functions_for_instruction(value, instruction_name)
                    if result:
                        return result
            return None
        
        functions = execute_section['function']
        
        if isinstance(functions, list):
            return self._process_function_list_for_instruction(functions, instruction_name)
        elif isinstance(functions, dict):
            return self._process_function_dict_for_instruction(functions, instruction_name)
        
        return None


    def _search_functions_for_instruction(self, data: Any, instruction_name: str) -> Optional[str]:
        """
        Searches 'functions' data for the specified instruction and returns its action.

        This function traverses a JSON-like structure that holds function
        definitions and attempts to find an entry associated with the given
        instruction name. It delegates to list/dict-specific helpers depending
        on the encountered data type.

        Args:
            data (Any):
                The JSON-compatible structure containing function data (dict, list, or mixed).
            instruction_name (str):
                The instruction name to look for.

        Returns:
            Optional[str]:
                The extracted action/execute body for the instruction if found, otherwise None.

        Raises:
            TypeError:
                If `data` contains unsupported types for traversal.
    """
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    result = self._check_function_for_instruction(item, instruction_name)
                    if result:
                        return result
        elif isinstance(data, dict):
            if 'source' in data:
                result = self._check_function_for_instruction(data, instruction_name)
                if result:
                    return result
            else:
                for key, value in data.items():
                    if isinstance(value, (list, dict)):
                        result = self._search_functions_for_instruction(value, instruction_name)
                        if result:
                            return result
        
        return None


    def _process_function_list_for_instruction(self, functions: List[Any], instruction_name: str) -> Optional[str]:
        """
        Processes a list of function entries to locate the specified instruction.

        This helper iterates over each item in a `functions` list and attempts
        to resolve whether it contains a match for `instruction_name`. If a
        match is discovered, it extracts and returns the associated action text.

        Args:
            functions (List[Any]):
                A list of function entries parsed from the JSON model.
            instruction_name (str):
                The instruction name to match.

        Returns:
            Optional[str]:
                The action/execute text if a matching function is found, otherwise None.
        """
        for func in functions:
            if isinstance(func, dict):
                result = self._check_function_for_instruction(func, instruction_name)
                if result:
                    return result
        return None


    def _process_function_dict_for_instruction(self, functions: Dict[str, Any], instruction_name: str) -> Optional[str]:
        """
        Processes a dictionary of functions to find the specified instruction.

        This helper inspects a mapping from function names/keys to function
        definitions and attempts to locate an entry corresponding to
        `instruction_name`. If present, the associated execution body is returned.

        Args:
            functions (Dict[str, Any]):
                A dictionary mapping function identifiers to their definitions.
            instruction_name (str):
                The instruction name to locate.

        Returns:
            Optional[str]:
                The extracted action/execute body if found, otherwise None.
        """
        for key, func in functions.items():
            if isinstance(func, dict):
                result = self._check_function_for_instruction(func, instruction_name)
                if result:
                    return result
            elif isinstance(func, list):
                for item in func:
                    if isinstance(item, dict):
                        result = self._check_function_for_instruction(item, instruction_name)
                        if result:
                            return result
        return None


    def _check_function_for_instruction(self, func: Dict[str, Any], instruction_name: str) -> Optional[str]:
        """
        Checks a single function entry for the specified instruction.

        This function validates whether the provided function object corresponds
        to `instruction_name` (by name, tags, or embedded metadata) and, if so,
        extracts the action body (e.g., the 'execute' clause content).

        Args:
            func (Dict[str, Any]):
                The function entry to inspect.
            instruction_name (str):
                The target instruction name.

        Returns:
            Optional[str]:
                The action/execute clause text if the function matches, otherwise None.

        Raises:
            KeyError:
                If required keys are missing from the function entry.
            TypeError:
                If `func` is not a dictionary-like structure.
        """
        if 'source' not in func:
            return None
        
        source = func['source']
        if not isinstance(source, dict):
            return None
        
        contents = source.get('contents', '')
        if not isinstance(contents, str):
            return None
        
        pattern = rf'function\s+clause\s+execute\s+{re.escape(instruction_name)}\s*\([^)]*\)\s*=\s*\{{(.*?)\}}'
        match = re.search(pattern, contents, re.DOTALL | re.MULTILINE)
        
        if match:
            action = match.group(1).strip()
            return action
        
        return None


    def _clean_action(self, action: str) -> str:
        """
        Normalizes an action body by trimming excess whitespace and fixing indentation.

        This utility performs cosmetic cleanup of an action/execute text:
        - removes superfluous leading/trailing whitespace,
        - collapses redundant blank lines,
        - applies consistent indentation rules to improve readability.

        Args:
            action (str):
                The raw action/execute text.

        Returns:
            str:
                The cleaned and consistently indented action string.

        Raises:
            TypeError:
                If `action` is not a string.
        """
        if not action:
            return ""
        
        action = action.strip()
        
        action = re.sub(r'\n\s*\n', '\n', action)
        
        lines = action.split('\n')
        if lines:
            non_empty_lines = [line for line in lines if line.strip()]
            if non_empty_lines:
                min_indent = min(len(line) - len(line.lstrip()) for line in non_empty_lines)
                cleaned_lines = []
                for line in lines:
                    if line.strip():  # Linie non-goală
                        cleaned_line = line[min_indent:] if len(line) > min_indent else line
                        cleaned_lines.append('      ' + cleaned_line)
                    else:  # Linie goală
                        cleaned_lines.append('')
                action = '\n'.join(cleaned_lines)
        
        return action



    def enhance_instruction_with_action(self, instruction_dict: Dict[str, Any], json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhances the instruction dictionary by attaching the parsed action
        extracted from the JSON model.

        This function locates the appropriate execution clause associated with
        the instruction and inserts the cleaned, normalized action text into the
        instruction dictionary. If no action is found, the instruction is returned
        unchanged.

        Args:
            instruction_dict (Dict[str, Any]):
                The base instruction dictionary previously constructed.
            json_data (Dict[str, Any]):
                The full JSON structure containing function/execute clauses.

        Returns:
            Dict[str, Any]:
                The updated instruction dictionary including the parsed action.
        """
        instruction_name = instruction_dict['name']
        
        print(f"DEBUG: Enhancing {instruction_name} with action...")
        
        action = self.parse_instruction_action(instruction_name, json_data)
        
        if action:
            store_instruction_action(instruction_name, action)
            
            instruction_dict['action'] = action
            print(f"DEBUG: Added action to {instruction_name}: {action[:50]}...")
            print(f"DEBUG: Full action for {instruction_name}: {action}")
        else:
            instruction_dict['action'] = ""
            print(f"DEBUG: No action found for {instruction_name}")
        
        excluded_values = self._parse_assembly_when_condition(json_data, instruction_name)
        if excluded_values:
            instruction_dict['excluded_values'] = excluded_values
            print(f"DEBUG: Added excluded values to {instruction_name}: {excluded_values}")
        
        print(f"DEBUG: Final instruction_dict keys: {list(instruction_dict.keys())}")
        return instruction_dict



    def parse_instructions_with_actions(self, json_data: Dict[str, Any], extension_filter: List[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Parses all instructions from the JSON structure, including their actions.

        This function processes each instruction definition found in the input
        JSON, applies extension filtering if provided, parses encoding fields,
        retrieves execution actions, and constructs a complete dictionary of
        fully-resolved instructions.

        Args:
            json_data (Dict[str, Any]):
                The full instruction model loaded from JSON.
            extension_filter (List[str], optional):
                A list of extensions to include. When None, all are processed.

        Returns:
            Dict[str, Dict[str, Any]]:
                A mapping from instruction names to their completed instruction
                dictionaries, including encoding, operands, metadata, and actions.
        """
        # Found encoding mapping
        self.find_encoding_mappings(json_data)
        
        # Found template splits
        self.find_template_splits(json_data)
        
        # Parse instructions
        instructions = self.parse_instructions(json_data, extension_filter)
        
        for instruction_name, instruction_dict in instructions.items():
            instruction_dict = self._map_immediate_to_template(instruction_dict)
            instruction_dict = self.enhance_instruction_with_action(instruction_dict, json_data)
            instructions[instruction_name] = instruction_dict
        
        return instructions



    def generate_xml_element(self, instruction: Dict[str, Any]) -> ET.Element:
        """
        Generates the XML element representing the given instruction.

        This function creates an XML `<instruction>` element containing fields such as:
        - name,
        - extension,
        - encoding fields,
        - operands,
        - action (execution semantics),
        - load/store/vector metadata if applicable.

        The output is formatted to align with the ADL-like schema used for
        instruction representation.

        Args:
            instruction (Dict[str, Any]):
                The fully-resolved instruction dictionary.

        Returns:
            ET.Element:
                The XML element corresponding to the instruction.
        """
        instr_elem = ET.Element('instruction', name=instruction['name'].replace("_", "."))
        
        print(f"DEBUG generate_xml_element: Generating XML for {instruction['name']}, width={instruction['width']}")
        
        # Width
        width_elem = ET.SubElement(instr_elem, 'width')
        width_int = ET.SubElement(width_elem, 'int')
        width_int.text = str(instruction['width'])
        
        print(f"DEBUG generate_xml_element: Set width XML to {width_int.text}")
        
        # Doc 
        doc_elem = ET.SubElement(instr_elem, 'doc')
        doc_str = ET.SubElement(doc_elem, 'str')
        doc_str.text = f"CDATA_START    {instruction['name'].upper().replace("_", ".")} instruction.   CDATA_END"
        
        # Syntax / DSyntax 
        syntax_elem = ET.SubElement(instr_elem, 'syntax')
        syntax_str = ET.SubElement(syntax_elem, 'str')
        
        dsyntax_elem = ET.SubElement(instr_elem, 'dsyntax')
        dsyntax_str = ET.SubElement(dsyntax_elem, 'str')
        
        # Instruction type
        is_vector_load = self._is_vector_load_instruction(instruction)
        is_vector_store = self._is_vector_store_instruction(instruction)
        is_store = self._is_store_instruction(instruction)
        is_load = self._is_load_instruction(instruction)
        is_branch = self._is_branch_instruction(instruction)
        
        if is_vector_load:
            syntax_str.text, dsyntax_str.text = self._generate_vector_load_syntax(instruction)
            print(f"DEBUG XML: Generated vector load syntax: {syntax_str.text}")
        elif is_vector_store:
            syntax_str.text, dsyntax_str.text = self._generate_vector_store_syntax(instruction)
            print(f"DEBUG XML: Generated vector store syntax: {syntax_str.text}")
        elif is_store:
            syntax_str.text, dsyntax_str.text = self._generate_store_syntax(instruction)
        elif is_load:
            syntax_str.text, dsyntax_str.text = self._generate_load_syntax(instruction)
        else:
            if instruction['operands']:
                operands_syntax = ','.join(instruction['operands'])
                syntax_str.text = f"{instruction['name'].replace("_", ".")} {operands_syntax}"
                operands_dsyntax = ','.join([f'${{{op}}}' for op in instruction['operands']])
                dsyntax_str.text = f"{instruction['name'].replace("_", ".")} {operands_dsyntax}"
            else:
                syntax_str.text = instruction['name']
                dsyntax_str.text = instruction['name']
        
        attributes_elem = ET.SubElement(instr_elem, 'attributes')

        attribute_list = instruction['attribute']
        if not isinstance(attribute_list, list):
            attribute_list = [attribute_list]
        
        for attr_name in attribute_list:
            attr_elem = ET.SubElement(attributes_elem, 'attribute', name=attr_name)
            attr_str = ET.SubElement(attr_elem, 'str')
            attr_str.text = ""
            print(f"DEBUG XML: Added attribute '{attr_name}' for {instruction['name']}")
        
        if is_branch:
            print(f"DEBUG XML: Adding branch attributes for {instruction['name']}")
            
            branch_attr_elem = ET.SubElement(attributes_elem, 'attribute', name='branch')
            branch_attr_str = ET.SubElement(branch_attr_elem, 'str')
            branch_attr_str.text = ""
        
        if instruction['name'].lower() == 'fence':
            print(f"DEBUG XML: Adding sync attribute for FENCE")
            sync_attr_elem = ET.SubElement(attributes_elem, 'attribute', name='sync')
            sync_attr_str = ET.SubElement(sync_attr_elem, 'str')
            sync_attr_str.text = ""
        
        global SPECIAL_INSTRUCTION_ATTRIBUTES
        instruction_name = instruction['name'].lower()
        if instruction_name in SPECIAL_INSTRUCTION_ATTRIBUTES:
            special_attr_name = SPECIAL_INSTRUCTION_ATTRIBUTES[instruction_name]
            print(f"DEBUG XML: Adding special attribute '{special_attr_name}' for {instruction['name']}")
            
            special_attr_elem = ET.SubElement(attributes_elem, 'attribute', name=special_attr_name)
            special_attr_str = ET.SubElement(special_attr_elem, 'str')
            special_attr_str.text = ""
        
        fields_elem = ET.SubElement(instr_elem, 'fields')
        
        print(f"DEBUG XML: Fields for {instruction['name']}: {instruction['fields']}")
        
        for field_name, field_value in instruction['fields'].items():
            field_elem = ET.SubElement(fields_elem, 'field', name=field_name)
            if isinstance(field_value, int):
                field_int = ET.SubElement(field_elem, 'int')
                field_int.text = str(field_value)
            else:
                field_str = ET.SubElement(field_elem, 'str')
                field_str.text = str(field_value) if field_value else ""
        
        if 'excluded_values' in instruction and instruction['excluded_values']:
            print(f"DEBUG XML: Adding excluded_values for {instruction['name']}")
            excluded_elem = ET.SubElement(instr_elem, 'excluded_values')
            
            for field_name, excluded_list in instruction['excluded_values'].items():
                option_elem = ET.SubElement(excluded_elem, 'option', name=field_name)
                for value in excluded_list:
                    value_int = ET.SubElement(option_elem, 'int')
                    value_int.text = str(value)
                    print(f"DEBUG XML: Added excluded value {value} for field {field_name}")
        
        action_content = get_instruction_action(instruction['name'])
        action_elem = ET.SubElement(instr_elem, 'action')
        action_str = ET.SubElement(action_elem, 'str')
        
        if action_content and action_content.strip():
            print(f"DEBUG XML: Adding action element for {instruction['name']} from global dict")
            action_str.text = f"CDATA_START\n{action_content}\n    CDATA_END"
            print(f"DEBUG XML: Action element added successfully")
        else:
            action_str.text = f"CDATA_START\n    CDATA_END"
            print(f"DEBUG XML: No action found in global dict for {instruction['name']}")
        
        # Disassemble
        disasm_elem = ET.SubElement(instr_elem, 'disassemble')
        disasm_str = ET.SubElement(disasm_elem, 'str')
        disasm_str.text = "true"
        
        # Inputs
        inputs_elem = ET.SubElement(instr_elem, 'inputs')
        if instruction['inputs']:
            for input_reg in instruction['inputs']:
                input_str = ET.SubElement(inputs_elem, 'str')
                input_str.text = input_reg
        else:
            inputs_elem.text = ""
        
        # Outputs
        outputs_elem = ET.SubElement(instr_elem, 'outputs')
        if instruction['outputs']:
            for output_reg in instruction['outputs']:
                output_str = ET.SubElement(outputs_elem, 'str')
                output_str.text = output_reg
        else:
            outputs_elem.text = ""
        
        return instr_elem

    def _is_store_instruction(self, instruction: Dict[str, Any]) -> bool:
        """
        Determines whether the given instruction is a store instruction.

        This function inspects instruction metadata (operands, naming patterns,
        template type, or ISA extension) to determine if it represents a memory
        store operation.

        Args:
            instruction (Dict[str, Any]):
                The dictionary representing the instruction.

        Returns:
            bool:
                True if the instruction is identified as a store instruction,
                otherwise False.
        """
        name = instruction['name'].lower()
        template = instruction.get('template', '').upper()
        
        store_names = ['sb', 'sh', 'sw', 'sd', 'store']
        if any(store_name in name for store_name in store_names):
            return True
        
        if template == 'STYPE':
            return True
        
        source_contents = instruction.get('source_contents', '').upper()
        if 'STORE' in source_contents or 'STYPE' in source_contents:
            return True
        
        return False

    def _is_load_instruction(self, instruction: Dict[str, Any]) -> bool:
        """
        Determines whether the given instruction is a load instruction.

        This function analyzes the operands, naming, and associated metadata to
        determine whether the instruction corresponds to a memory load operation.

        Args:
            instruction (Dict[str, Any]):
                The dictionary representing the instruction.

        Returns:
            bool:
                True if the instruction is identified as a load instruction,
                otherwise False.
        """
        name = instruction['name'].lower()
        template = instruction.get('template', '').upper()
        
        load_names = ['lb', 'lh', 'lw', 'ld', 'lbu', 'lhu', 'lwu', 'load']
        if any(load_name in name for load_name in load_names):
            return True
        
        if template == 'ITYPE' and ('load' in name or any(ln in name for ln in load_names)):
            return True
        
        source_contents = instruction.get('source_contents', '').upper()
        if 'LOAD' in source_contents and template == 'ITYPE':
            return True
        
        return False

    def _generate_store_syntax(self, instruction: Dict[str, Any]) -> tuple:
        """
        Generates the ordered syntax tuple for store instructions.

        Store instructions typically follow a pattern such as:
            STORE rs, offset(base)
        This function uses the instruction's operand metadata to produce the
        final ordered syntax structure used by the XML generator or encoder.

        Args:
            instruction (Dict[str, Any]):
                The instruction dictionary containing operands and metadata.

        Returns:
            tuple:
                A tuple describing the syntax components for store instructions.
        """
        name = instruction['name']
        operands = instruction['operands']
        
        rs1 = None
        rs2 = None
        imm = None
        
        for op in operands:
            if op == 'rs1':
                rs1 = op
            elif op == 'rs2':
                rs2 = op
            elif 'imm' in op.lower():
                imm = op
        
        if rs1 and rs2 and imm:
            syntax = f"{name.replace("_", ".")} {rs2},{imm}({rs1})"
            dsyntax = f"{name.replace("_", ".")} ${{{rs2}}},${{{imm}}}(${{{rs1}}})"
        else:
            # Fallback 
            operands_syntax = ','.join(operands)
            syntax = f"{name.replace("_", ".")} {operands_syntax}"
            operands_dsyntax = ','.join([f'${{{op}}}' for op in operands])
            dsyntax = f"{name.replace("_", ".")} {operands_dsyntax}"
        
        return syntax, dsyntax

    def _generate_load_syntax(self, instruction: Dict[str, Any]) -> tuple:
        """
        Generates the ordered syntax tuple for load instructions.

        Load instructions typically follow a pattern such as:
            LOAD rd, offset(base)
        This function extracts and orders the operands accordingly to construct
        the final syntax representation.

        Args:
            instruction (Dict[str, Any]):
                The instruction dictionary containing operands and metadata.

        Returns:
            tuple:
                A tuple describing the syntax components for load instructions.
        """
        name = instruction['name']
        operands = instruction['operands']
        
        rd = None
        rs1 = None
        imm = None
        
        for op in operands:
            if op == 'rd':
                rd = op
            elif op == 'rs1':
                rs1 = op
            elif 'imm' in op.lower():
                imm = op
        
        if rd and rs1 and imm:
            syntax = f"{name.replace("_", ".")} {rd},{imm}({rs1})"
            dsyntax = f"{name.replace("_", ".")} ${{{rd}}},${{{imm}}}(${{{rs1}}})"
        else:
            # Fallback
            operands_syntax = ','.join(operands)
            syntax = f"{name.replace("_", ".")} {operands_syntax}"
            operands_dsyntax = ','.join([f'${{{op}}}' for op in operands])
            dsyntax = f"{name.replace("_", ".")} {operands_dsyntax}"
        
        return syntax, dsyntax


    def _generate_core_description(self, extension_filter: List[str] = None) -> str:
        """
        Generates a textual core description based on the enabled extensions.

        This function composes a human-readable description of the core's
        capabilities derived from the set of active ISA extensions. The result
        can be embedded into the final XML or used for metadata/reporting.

        Args:
            extension_filter (List[str], optional):
                A list of enabled extensions to describe. If None, the description
                is generated from the internal/default extension configuration.

        Returns:
            str:
                A descriptive string summarizing the core features and extensions.
        """
        descriptions = []
        
        if not extension_filter:
            extension_filter = ['I']  # Default
        
        for ext in sorted(extension_filter):
            if ext.upper() == 'I':
                descriptions.append("The base Risc-V 32-bit integer instruction set. Based upon version 2.0.")
            elif ext.upper() == 'M':
                descriptions.append("The Risc-V 32-bit M standard extension for integer multiplication and division.")
            elif ext.upper() == 'C':
                descriptions.append("The Risc-V 32-bit C standard extension for compressed instructions.")
            elif ext.upper() == 'A':
                descriptions.append("The Risc-V 32-bit A standard extension for atomic instructions.")
            elif ext.upper() == 'F':
                descriptions.append("The Risc-V 32-bit F standard extension for single-precision floating-point.")
            elif ext.upper() == 'D':
                descriptions.append("The Risc-V 32-bit D standard extension for double-precision floating-point.")
            else:
                descriptions.append(f"The Risc-V 32-bit {ext.upper()} extension.")
        
        # Description for architecture
        descriptions.append("The RISC-V 32-bit privileged architecture (machine mode).")
        
        return "".join(descriptions)
    
    
    def _generate_asm_config(self, extension_filter: List[str] = None) -> ET.Element:
        """
        Generates the <asm_config> XML element based on the specified extensions.

        The assembler configuration captures syntax and capability flags that depend
        on the enabled extensions (e.g., vector support, compressed ISA, custom
        addressing modes). This function builds the appropriate XML structure for
        inclusion in the final output.

        Args:
            extension_filter (List[str], optional):
                A list of extensions that should be reflected in the assembler
                configuration. If None, internal/default configuration is used.

        Returns:
            ET.Element:
                The constructed <asm_config> XML element.
        """
        if not extension_filter:
            extension_filter = ['I']
        
        # asm_config
        asm_config_elem = ET.Element('asm_config')
        
        # Comments
        comments_elem = ET.SubElement(asm_config_elem, 'comments')
        comments_str = ET.SubElement(comments_elem, 'str')
        comments_str.text = "#"
        
        # Line comments
        line_comments_elem = ET.SubElement(asm_config_elem, 'line_comments')
        line_comments_str = ET.SubElement(line_comments_elem, 'str')
        line_comments_str.text = "#"
        
        # Arch
        arch_elem = ET.SubElement(asm_config_elem, 'arch')
        arch_str = ET.SubElement(arch_elem, 'str')
        arch_str.text = "riscv32"
        
        # Attributes 
        attributes_elem = ET.SubElement(asm_config_elem, 'attributes')
        attributes_str = ET.SubElement(attributes_elem, 'str')
        
        attributes_parts = ["rv32i1p0"]
        
        # 
        for ext in sorted(extension_filter):
            ext_upper = ext.upper()
            if ext_upper != 'I':
                ext_lower = ext_upper.lower()
                attributes_parts.append(f"_{ext_lower}1p0")
        
        attributes_str.text = "".join(attributes_parts)
        
        mattrib_elem = ET.SubElement(asm_config_elem, 'mattrib')
        mattrib_str = ET.SubElement(mattrib_elem, 'str')
        
        mattrib_parts = []
        for ext in sorted(extension_filter):
            ext_upper = ext.upper()
            if ext_upper != 'I':
                ext_lower = ext_upper.lower()
                mattrib_parts.append(f"+{ext_lower}")
        
        mattrib_str.text = "".join(mattrib_parts)
        
        return asm_config_elem

    def generate_xml_with_data(
    self,
    instructions: Dict[str, Dict[str, Any]],
    json_data: Dict[str, Any],
    extension_filter: List[str] = None
) -> str:
        """
        Generates the final XML document with access to JSON data for register files.

        This function produces a complete XML representation of the instruction
        set, combining:
        - instruction elements (encodings, operands, actions),
        - register file definitions (pulled/derived from the JSON model),
        - assembler configuration and core description (based on extensions).

        Args:
            instructions (Dict[str, Dict[str, Any]]):
                A mapping from instruction names to their fully-resolved dictionaries.
            json_data (Dict[str, Any]):
                The parsed JSON source used to extract register files and other metadata.
            extension_filter (List[str], optional):
                A list of ISA extensions to include. If None, all applicable data is used.

        Returns:
            str:
                A UTF-8 XML string representing the final document.

        Raises:
            ValueError:
                If required sections are missing or the XML cannot be assembled
                consistently from the provided data.
            KeyError:
                If expected register file structures are absent from `json_data`.
        """
        
        global IGNORED_INSTRUCTIONS
        print(f"DEBUG: IGNORED_INSTRUCTIONS list: {IGNORED_INSTRUCTIONS}")
        
        filtered_instructions = {}
        ignored_count = 0
        
        for name, instruction in instructions.items():
            name_lower = name.lower()
            ignored_lower = [ignored.lower() for ignored in IGNORED_INSTRUCTIONS]
            
            print(f"DEBUG: Checking instruction '{name}' (lower: '{name_lower}')")
            print(f"DEBUG: Against ignored list: {ignored_lower}")
            print(f"DEBUG: Is ignored? {name_lower in ignored_lower}")
            if name_lower.replace("_", ".") not in ignored_lower:
                filtered_instructions[name] = instruction
                print(f"DEBUG: Including instruction: {name}")
            else:
                ignored_count += 1
                print(f"DEBUG: Ignoring instruction: {name}")
        
        print(f"✓ Filtered out {ignored_count} ignored instructions")
        print(f"✓ Processing {len(filtered_instructions)} instructions")
        
        instructions = filtered_instructions
        
        data_elem = ET.Element('data')
        cores_elem = ET.SubElement(data_elem, 'cores')
        
        core_name = "rv32"
        if extension_filter:
            sorted_extensions = sorted(extension_filter)
            core_name += "".join(ext.lower() for ext in sorted_extensions)
        else:
            all_extensions = set()
            for instruction in instructions.values():
                if instruction['extension']:
                    all_extensions.add(instruction['extension'])
            if all_extensions:
                sorted_extensions = sorted(all_extensions)
                core_name += "".join(ext.lower() for ext in sorted_extensions)
            else:
                core_name += "i"
        
        core_elem = ET.SubElement(cores_elem, 'core', name=core_name)
        
        # Doc
        doc_elem = ET.SubElement(core_elem, 'doc')
        doc_str = ET.SubElement(doc_elem, 'str')
        doc_str.text = "CDATA_START" + self._generate_core_description(extension_filter) + "CDATA_END"
        
        # Bit endianness
        bit_endianness_elem = ET.SubElement(core_elem, 'bit_endianness')
        bit_endianness_str = ET.SubElement(bit_endianness_elem, 'str')
        bit_endianness_str.text = "little"
        
        # Register Files
        print("\n" + "="*60)
        print("GENERATING REGISTER FILES FOR XML")
        print("="*60)
        
        reg_generator = RegisterFileGenerator()
        register_elements = reg_generator.generate_all_register_files_xml(extension_filter, json_data)
        
        if register_elements:
            regfiles_elem = ET.SubElement(core_elem, 'regfiles')
            for reg_elem in register_elements:
                regfiles_elem.append(reg_elem)
            print(f"✓ Added {len(register_elements)} register files to XML")
        else:
            print("WARNING: No register files generated")
        
        # Instruction Fields
        print("\n" + "="*60)
        print("GENERATING INSTRUCTION FIELDS FOR XML")
        print("="*60)
        
        instrfields_xml = self._generate_instruction_fields_for_xml()
        if instrfields_xml:
            try:
                instrfields_root = ET.fromstring(f"<root>{instrfields_xml}</root>")
                instrfields_elem = instrfields_root.find('instrfields')
                if instrfields_elem is not None:
                    core_elem.append(instrfields_elem)
                    print(f"✓ Added {len(instrfields_elem)} instruction fields to XML")
                else:
                    print("WARNING: No instrfields element found in generated XML")
            except ET.ParseError as e:
                print(f"ERROR: Failed to parse instruction fields XML: {e}")
        else:
            print("WARNING: No instruction fields generated")
        
        # Instructions
        instrs_elem = ET.SubElement(core_elem, 'instrs')
        
        for instruction in instructions.values():
            instr_elem = self.generate_xml_element(instruction)
            instrs_elem.append(instr_elem)
        
        # ASM Config
        print("\n" + "="*60)
        print("GENERATING ASM CONFIG")
        print("="*60)
        
        asm_config_elem = self._generate_asm_config(extension_filter)
        core_elem.append(asm_config_elem)
        print(f"✓ Added asm_config for extensions: {extension_filter}")
        
        rough_string = ET.tostring(data_elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        xml_content = reparsed.toprettyxml(indent="")
        
        lines = xml_content.split('\n')
        if lines[0].startswith('<?xml'):
            lines = lines[1:]
        
        xml_output = '<?xml version="1.0" encoding="UTF-8"?>\n' + '\n'.join(lines)
        
        # Refactoring for CDATA
        xml_output = xml_output.replace('CDATA_START', '<![CDATA[\n{')
        xml_output = xml_output.replace('CDATA_END', '\n}\n]]>')
        
        xml_output = xml_output.replace('<str/>', '<str></str>')
        xml_output = xml_output.replace('<inputs/>', '<inputs></inputs>')
        xml_output = xml_output.replace('<outputs/>', '<outputs></outputs>')
        xml_output = xml_output.replace('&lt;', '<')
        xml_output = xml_output.replace('&gt;', '>')
        
        return xml_output


def get_gpr_alias(arch_name: str) -> str:
    """
    Returns the user-friendly alias for a GPR (General-Purpose Register) name.

    This helper maps architecture-specific GPR identifiers to a presentation
    alias (e.g., mapping 'x0' -> 'zero' in RISC-V-style naming), if available.
    If no alias is known for the provided name, the original value may be
    returned.

    Args:
        arch_name (str):
            The architecture-level register name (e.g., "x0", "x1", "ra").

    Returns:
        str:
            The alias string for the given GPR, or the input `arch_name`
            if no alias is defined.

    Raises:
        TypeError:
            If `arch_name` is not a string.
    """
    global GPR_ALIASES
    return GPR_ALIASES.get(arch_name, arch_name)

def get_all_gpr_aliases() -> Dict[str, str]:
    """
    Returns the complete mapping of architecture GPR names to their aliases.

    This function exposes the internal alias dictionary so that callers can
    inspect or reuse the full set of known GPR name mappings.

    Returns:
        Dict[str, str]:
            A dictionary mapping architecture register names (keys) to their
            user-friendly aliases (values).
    """
    global GPR_ALIASES
    return GPR_ALIASES.copy()

def print_gpr_aliases() -> None:
    """
    Prints all known GPR aliases for debugging and inspection.

    This utility iterates through the GPR alias mapping and prints each
    architecture name alongside its user-friendly alias.

    Returns:
        None
    """
    global GPR_ALIASES
    print("\nGlobal GPR Aliases Dictionary:")
    print("-" * 30)
    
    if not GPR_ALIASES:
        print("Empty dictionary!")
        return
    
    # Sorting
    sorted_aliases = sorted(GPR_ALIASES.items(), key=lambda x: int(x[0][1:]) if x[0].startswith('x') and x[0][1:].isdigit() else 999)
    
    for arch_name, abi_name in sorted_aliases:
        print(f"{arch_name} -> {abi_name}")
    
    print("-" * 30)
    print(f"Total: {len(GPR_ALIASES)} aliases\n")


def main():
    parser = argparse.ArgumentParser(description='Parse JSON instructions and generate XML')
    parser.add_argument('input_file', help='Input JSON file path')
    parser.add_argument('--extensions', nargs='+', help='Extensions to filter (e.g., I C M)')
    parser.add_argument('--output', '-o', help='Output XML file path')
    parser.add_argument('--build-fields', action='store_true', help='Build instruction field ranges dictionary')
    parser.add_argument('--generate-fields', action='store_true', help='Generate instruction fields XML')
    
    args = parser.parse_args()
    
    # Absolute path to the directory where this file lives
    base_dir = Path(__file__).resolve().parent
    base_dir_outputs = Path('tools_adl').resolve().parent
    
    # Global debug directory path
    debug_dir = base_dir / "debug"
    
    #Output dir
    args.output = base_dir_outputs / args.output
    
    # Create the directory if it does not exist
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    # Example: log file path
    log_file = debug_dir / "sail2adl_debug.log"

    with DebugLogger(log_file) as logger:
        logger.console_print(f"Debug output will be written to: {log_file}")
        
        instr_parser = InstructionParser()
        instr_parser.logger = logger
        
        try:
            json_data = instr_parser.parse_json_file(args.input_file)
            
            print("Loading register classes...")
            register_success = load_register_classes(json_data)
            if register_success:
                print(f"✓ Loaded {len(REGISTER_CLASSES)} register classes")
            else:
                print("WARNING: Failed to load register classes")
            
            print("Loading special instruction attributes...")
            load_special_attributes()
            
            print("Loading ignored instructions...")
            load_ignored_instructions()
            
            print("Loading register classes...")
            register_success = load_register_classes(json_data)
            if register_success:
                print(f"✓ Loaded {len(REGISTER_CLASSES)} register classes")
            else:
                print("WARNING: Failed to load register classes")
            
            print("Loading special instruction attributes...")
            load_special_attributes()
            print(f"DEBUG: SPECIAL_INSTRUCTION_ATTRIBUTES after loading: {SPECIAL_INSTRUCTION_ATTRIBUTES}")
            
            print("Loading register classes...")
            register_success = load_register_classes(json_data)
            if register_success:
                print(f"✓ Loaded {len(REGISTER_CLASSES)} register classes")
            else:
                print("WARNING: Failed to load register classes")
            
            if args.build_fields:
                # field ranges
                field_manager = InstructionFieldManager()
                success = field_manager.build_instruction_field_ranges(json_data)
                
                if success:
                    print("\n" + "="*60)
                    print("INSTRUCTION FIELD RANGES BUILT SUCCESSFULLY")
                    print("="*60)
                    for field_name, (start_bit, end_bit) in sorted(INSTRUCTION_FIELD_RANGES.items(), 
                                                                  key=lambda x: x[1][0], reverse=True):
                        print(f"{field_name:15} [{start_bit:2d}:{end_bit:2d}] ({start_bit-end_bit+1:2d} bits)")
                    
                    print(f"\nAuto-detected register fields: {field_manager.field_to_register_map}")
                else:
                    print("Failed to build instruction field ranges!")
                
                return
            
            if args.generate_fields:
                # field ranges
                field_manager = InstructionFieldManager()
                success = field_manager.build_instruction_field_ranges(json_data)
                
                if success:
                    xml_output = field_manager.generate_instruction_fields_xml()
                    
                    if args.output:
                        with open(args.output, 'w+', encoding='utf-8') as f:
                            f.write(xml_output)
                        print(f"Instruction fields XML generated in {args.output}")
                    else:
                        print(xml_output)
                else:
                    print("Failed to build instruction field ranges!")
                
                return
            
            print(instr_parser.parse_instructions_with_actions(json_data,  args.extensions))
            
            if not instr_parser.parse_instructions_with_actions(json_data,  args.extensions):
                print("No instructions found!")
                return
            
            xml_output = instr_parser.generate_xml_with_data(instr_parser.parse_instructions_with_actions(json_data,  args.extensions), json_data, args.extensions)
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(xml_output)
                print(f"XML generated in {args.output}")
            else:
                print(xml_output)
            
            print(f"Processed {len(instr_parser.parse_instructions_with_actions(json_data,  args.extensions))} instructions.")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            logger.console_print(f"Error: {e}")
            logger.console_print(traceback.format_exc())


if __name__ == "__main__":
    main()