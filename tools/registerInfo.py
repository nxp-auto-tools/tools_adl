# Copyright 2023-2025 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package registerInfo
#
# The module in which register classes types are defined


## A base class that contains the main attributes of a register
#
class Register:
    ## The constructor
    def __init__(
        self, register_class, doc_info, width, attributes, size, shared, read, write
    ):
        ## @var register_class
        # The class of the register. It can be CSR, GPR or anything else
        self.register_class = register_class
        ## @var doc_info
        # It stores information about the register class
        self.doc_info = doc_info
        ## @var width
        # Stores information for register class width
        self.width = width
        ## @var attributes
        # Stores information for register class attributes
        self.attributes = attributes
        ## @var size
        # Stores information for register class size
        self.size = size
        ## @var shared
        # Stores information for register class shared
        self.shared = shared
        ## @var read
        # Stores information for register class read
        self.read = read
        ## @var write
        # Stores information for register class write
        self.write = write


## A class that extends the base class and has specific GPR register fields
#
class RegisterGPR(Register):
    ## The constructor
    def __init__(
        self,
        register_class,
        doc_info,
        width,
        attributes,
        debug,
        size,
        prefix,
        shared,
        read,
        write,
        calling_convention,
        pseudo,
        alignment,
    ):
        super().__init__(
            register_class, doc_info, width, attributes, size, shared, read, write
        )
        ## @var prefix
        # Stores information for register class prefix
        self.prefix = prefix
        ## @var debug
        # Stores information for register class debug
        self.debug = debug
        ## @var calling_convention
        # Stores information about calling convention
        self.calling_convention = calling_convention
        ## @var pseudo
        # Stores pseudo information for register class
        self.pseudo = pseudo
        ## @var alignment
        # The alignment in memory
        self.alignment = alignment


## A class that extends the base class and has specific CSR register fields
#
class RegisterCSR(Register):
    ## The constructor
    def __init__(
        self,
        register_class,
        doc_info,
        width,
        attributes,
        size,
        entries,
        syntax,
        prefix,
        shared,
        read,
        write,
        calling_convention,
        pseudo,
        debug,
        alignment,
    ):
        super().__init__(
            register_class, doc_info, width, attributes, size, shared, read, write
        )
        ## @var entries
        # Stores information for register class entries
        self.entries = entries
        ## @var syntax
        # Stores information for register class syntax
        self.syntax = syntax
        ## @var prefix
        # Stores information for register class prefix
        self.prefix = prefix
        ## @var calling_convention
        # Stores information about calling convention
        self.calling_convention = calling_convention
        ## @var pseudo
        # Stores pseudo information for register class
        self.pseudo = pseudo
        ## @var debug
        # Stores information for register class debug
        self.debug = debug
        ## @var alignment
        # The alignment in memory
        self.alignment = alignment


## A class that extends the base class and has additional attributes for all possible types of registers
#
class RegisterGeneric(Register):
    ## The constructor
    def __init__(
        self,
        register_class,
        doc_info,
        width,
        attributes,
        size,
        entries,
        syntax,
        debug,
        prefix,
        shared,
        reserved_mask,
        read,
        write,
        calling_convention,
        pseudo,
        alignment,
        alias_reg,
    ):
        super().__init__(
            register_class, doc_info, width, attributes, size, shared, read, write
        )
        ## @var prefix
        # Stores information for register class prefix
        self.prefix = prefix
        ## @var debug
        # Stores information for register class debug
        self.debug = debug
        ## @var entries
        # Stores information for register class entries
        self.entries = entries
        ## @var syntax
        # Stores information for register class syntax
        self.syntax = syntax
        ## @var reserved_mask
        # Stores information for register class reserved_mask
        self.reserved_mask = reserved_mask
        ## @var calling_convention
        # Stores information about calling convention
        self.calling_convention = calling_convention
        ## @var pseudo
        # Stores pseudo information for register class
        self.pseudo = pseudo
        ## @var alignment
        # The alignment in memory
        self.alignment = alignment
        ## @var alias_reg
        # Alias_reg contain the list of register aliases for a certain register
        self.alias_reg = alias_reg
