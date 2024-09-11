#!/bin/bash
# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

### TESTING RELOCATIONS

# 0. Add path for llvm assembler
llvm_assembler=$1
if [ ! -e "$llvm_assembler" ]; then
	echo "Please add a correct llvm assembler path: '$llvm_assembler'!"
	return 1
fi

llvm_readelf=$2
if [ ! -e "$llvm_readelf" ]; then
	echo "Please add a correct llvm readelf path: '$llvm_readelf'!"
	return 1
fi


# 1. Delete previous tests
if [ -d "obj_files" ]; then
	echo "Delete previous tests..."
	rm -rf ./obj_files/*
	echo "Done."
fi 


# 2. Check if tests output directory exists in the current directory
if [ ! -d "obj_files" ]; then
    # If not, create the directory
    mkdir "obj_files"
    echo "Created directory: obj_files"
	
fi

if [ ! -d "obj_files/readelf" ]; then
    # If not, create the directory
    mkdir "obj_files/readelf"
    echo "Created directory: obj_files/readelf"
fi


tests_path=tests/*/
include_file=(*.inc)

# 3. using the assembler to create obj files
echo "Creating object files..."
for dir in ${tests_path}; do
	original_dir="$(pwd)"
	dir_name=${dir%/}
	cp $include_file $dir_name
	cd "$dir_name"	
	asm_files=(*.s)
	mkdir ../../obj_files/$(basename ${dir})
	for asm_file in "${asm_files[@]}"; do
		$llvm_assembler -arch=riscv32 $asm_file -M no-aliases -o ../../obj_files/$(basename ${dir})/$(basename ${asm_file}.o) --filetype=obj
		#$llvm_assembler $asm_file -march=rv32imac -o ../../obj_files/$(basename ${dir})/$(basename ${asm_file}.o) # gcc compiler
	done
	cd "$original_dir"
done
echo "Done."


# 2. Using readelf to generate text section

object_files=$(find "obj_files" -type f -name *.o)
echo "Generating readelf dumps for relocation section..."
for obj_file in ${object_files[@]}; do
	$llvm_readelf -r $obj_file >& ./obj_files/readelf/$(basename ${obj_file}.txt)
done
echo "Done."