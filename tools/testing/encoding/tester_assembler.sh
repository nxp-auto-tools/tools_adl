#!/bin/bash
# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

### TESTING ASSEMBLER

# 0. Add paths for the llvm/triro assemblers and create destination directories
llvm_assembler=$1
if [ ! -e "$llvm_assembler" ]; then
	echo "Please add a correct llvm assembler path: '$llvm_assembler'!"
	return 1
fi

triro_assembler=$2
if [ ! -e "$triro_assembler" ]; then
	echo "Please add a correct triro assembler path: '$triro_assembler'!"
	return 1
fi

triro_readelf=$3
if [ ! -e "$triro_readelf" ]; then
	echo "Please add a correct triro readelf path: '$triro_readelf'!"
	return 1
fi

echo "Delete previous tests..."
find ./triro_tests -type f -name "*.o" -exec rm {} \;
find ./triro_tests/readelf -type f -name "*.txt" -exec rm {} \;
find ./llvm_tests -type f -name "*.o" -exec rm {} \;
find ./llvm_tests/readelf -type f -name "*.txt" -exec rm {} \;
echo "Done."

if [ ! -d "llvm_tests" ]; then
    # If not, create the directory
    mkdir "llvm_tests"
    echo "Created directory: llvm_tests"
fi

if [ ! -d "llvm_tests/readelf" ]; then
    # If not, create the directory
    mkdir "llvm_tests/readelf"
    echo "Created directory: llvm_tests/readelf"
fi

if [ ! -d "triro_tests" ]; then
    # If not, create the directory
    mkdir "triro_tests"
    echo "Created directory: triro_tests"
fi

if [ ! -d "triro_tests/readelf" ]; then
    # If not, create the directory
    mkdir "triro_tests/readelf"
    echo "Created directory: triro_tests/readelf"
fi


tests_path=tests/*/

# 1. Using the assembler to create obj files

echo "Creating object files..."
for dir in ${tests_path}; do

	dir_name=${dir%/}
	asm_file=$(find "$dir_name" -maxdepth 1 -type f -name '*.asm')

	$llvm_assembler -arch=riscv32 -mattr=+m,+c $asm_file -M no-aliases -o llvm_tests/$(basename ${dir_name}.o) --filetype=obj
	$triro_assembler -arch=riscv32 -mattr=+m,+c $asm_file -M no-aliases -o triro_tests/$(basename ${dir_name}.o) --filetype=obj
	
done
echo "Done."

# 2. Using readelf to generate text section

echo "Generating text section using readelf..."
path_to_llvm_tests=./llvm_tests
path_to_triro_tests=./triro_tests

llvm_obj_files=($(find "$path_to_llvm_tests" -maxdepth 1 -type f))
triro_obj_files=($(find "$path_to_triro_tests" -maxdepth 1 -type f))

for i in "${!llvm_obj_files[@]}"; do
	llvm_obj_file="${llvm_obj_files[i]}"
	$triro_readelf -x 2 $llvm_obj_file > llvm_tests/readelf/$(basename ${llvm_obj_file}.txt)
done

for j in "${!triro_obj_files[@]}"; do
	triro_obj_file="${triro_obj_files[j]}"
	$triro_readelf -x 2 $triro_obj_file > triro_tests/readelf/$(basename ${triro_obj_file}.txt)
done
echo "Done."

# 3. Comparing text section

path_to_llvm_readelf_files=./llvm_tests/readelf
path_to_triro_readelf_files=./triro_tests/readelf

echo "Comparing text section..."
for file1 in "$path_to_triro_readelf_files"/*
do

	file2="$path_to_llvm_readelf_files/$(basename "$file1")"
	if cmp -s "$file1" "$file2"; then
		echo "Ok: $(basename "$file1") and $(basename "$file2") are the same"
	else
		echo "Not ok: $(basename "$file1") and $(basename "$file2") are NOT the same"
	fi
done
echo "Done."