# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package sail_converter
#
# Configuration file
# The module generates an XML file based on the Json version of the Sail model

# Configuration for register classes
# Each dictionary defines a register class

GPR = {
    'name': 'GPR',
    'description': 'The complete general-purpose register file. r0 always reads as 0.',
    'width': 32,
    'size': 32,
    'prefix': 'x',
    'shared': 0,
    'attributes': {
        'rv32i': '',
        'debug': '0'
    },
    'extensions': ['I'],
    'calling_convention': {
        # Define ranges for the calling convention
        # Format: (start_index, end_index, description)
        'ranges': [
            (0, 0, 'Hard_wired_zero'),
            (1, 1, 'Return_address'),
            (2, 2, 'Stack_pointer'),
            (3, 3, 'Global_pointer'),
            (4, 4, 'Thread_pointer'),
            (5, 5, 'Temporary'),
            (5, 5, 'Alternate_link_register'),  # X5 has two roles
            (6, 7, 'Temporary'),
            (8, 8, 'Saved_register'),
            (8, 8, 'Frame_pointer'),  # X8 has two roles
            (9, 9, 'Saved_register'),
            (10, 11, 'Function_arguments'),
            (10, 11, 'Return_values'),  # X10–X11 have two roles
            (12, 17, 'Function_arguments'),
            (18, 27, 'Saved_register'),
            (28, 31, 'Temporary')
        ]
    }
}


VR = {
    'name': 'VR',
    'description': 'The complete vector register file',
    'width': 32,
    'size': 32,
    'prefix': 'v',
    'shared': 0,
    'attributes': {
        'rv32i': '',
        'vector': '96'
    },
    'extensions': ['I'],
    'registers': {  # ADDED: explicitly define registers
        0: {'aliases': ['m0']},
        1: {'aliases': ['m1']},
        2: {'aliases': ['m2']},
        3: {'aliases': ['m3']},
        4: {'aliases': ['m4']},
        5: {'aliases': ['m5']},
        6: {'aliases': ['m6']},
        7: {'aliases': ['m7']},
        8: {'aliases': ['m8']},
        9: {'aliases': ['m9']},
        10: {'aliases': ['m10']},
        11: {'aliases': ['m11']},
        12: {'aliases': ['m12']},
        13: {'aliases': ['m13']},
        14: {'aliases': ['m14']},
        15: {'aliases': ['m15']},
        16: {'aliases': ['m16']},
        17: {'aliases': ['m17']},
        18: {'aliases': ['m18']},
        19: {'aliases': ['m19']},
        20: {'aliases': ['m20']},
        21: {'aliases': ['m21']},
        22: {'aliases': ['m22']},
        23: {'aliases': ['m23']},
        24: {'aliases': ['m24']},
        25: {'aliases': ['m25']},
        26: {'aliases': ['m26']},
        27: {'aliases': ['m27']},
        28: {'aliases': ['m28']},
        29: {'aliases': ['m29']},
        30: {'aliases': ['m30']},
        31: {'aliases': ['m31']},
    },
    'calling_convention': {
        # Define ranges for the calling convention
        # Format: (start_index, end_index, description)
        'ranges': [
            (0, 0, 'Temporary_0'),
            (1, 1, 'Temporary_1'),
            (2, 2, 'Temporary_2'),
            (3, 3, 'Temporary_3'),
            (4, 4, 'Temporary_4'),
            (5, 5, 'Temporary_5'),
            (6, 6, 'Temporary_6'),  
            (7, 7, 'Temporary_7'),
            (8, 31, 'Temporary')
        ]
    }
}

FPR = {
    'name': 'FPR',
    'description': 'The complete floating-point register file.',
    'width': 32,
    'size': 32,
    'prefix': 'f',
    'shared': 0,
    'debug': 0,
    'attributes': {
        'rv32f': ''
    },
    'extensions': ['F']
    # FPR does not have a calling convention in your example
}

CSR = {
    'name': 'CSR',
    'description': 'Control and Status Registers.',
    'width': 32,
    'size': 4096,
    'prefix': '',
    'shared': 0,
    'debug': 4096,
    'attributes': {
        'rv32i': ''
    },
    'extensions': ['I']
    # CSR does not have a calling convention
}

# Dictionary for special instruction attributes
SPECIAL_INSTRUCTION_ATTRIBUTES = {
    'jal': 'jump',
    'jalr': 'jump',
    'load' : 'load',
    'store': 'store',
    'v2dld': 'load',
    'v2dst': 'store',
    # ADDED: missing comma
    # You can add other special instructions here
    # 'instruction_name': 'attribute_name'
}

# List of instructions that will not be generated in XML
IGNORED_INSTRUCTIONS = [
    # Add here the names of the instructions you want to ignore
    'addw',
    'addiw',
    'remw',
    'subw',
    'sllw',
    'srlw',
    'sraw',
    'divw',
    'mulw',
    'fencei.reserved',
    'fence.reserved',
    'sfence.vma',
    'fence.tso',
    'sraiw',
    'srliw',
    'slliw',
    'c.ld', 
    'c.addiw', 
    'c.subw', 
    'c.andw', 
    'c.lwsp', 
    'c.ldsp', 
    'c.swsp', 
    'c.sdsp', 
    'c.lbu', 
    'c.lhu', 
    'c.lh',
    'c.sd', 
    'c.sb', 
    'c.sh', 
    'c.zext.b', 
    'c.sext.b', 
    'c.zext.h', 
    'c.sext.h', 
    'c.zext.w', 
    'c.not', 
    'c.mul',
    'c.fld',
    'c.fsd',
    'c.addw',
]

# ADDED: Dictionary for mapping special operands
SPECIAL_OPERAND_MAPPINGS = {
    'fence': {
        'pred': 'fence_prod',
        'succ': 'fence_succ'
    },
}