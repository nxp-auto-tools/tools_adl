#!/bin/bash
# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

### TESTING DISASSEMBLER

# 0. Add paths for the triro assembler/disassembler
triro_assembler=$1
if [ ! -e "$triro_assembler" ]; then
	echo "Please add a correct triro assembler path: '$triro_assembler'!"
	return 1
fi

triro_disassembler=$2
if [ ! -e "$triro_disassembler" ]; then
	echo "Please add a correct triro assembler path: '$triro_disassembler'!"
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
find ./triro_tests/objdump -type f -name "*.asm" -exec rm {} \;
find ./triro_tests/objdump/elf -type f -name "*.o" -exec rm {} \;
find /triro_tests/objdump/elf/readelf -type f -name "*.txt" -exec rm {} \;
echo "Done."


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

if [ ! -d "triro_tests/objdump" ]; then
    # If not, create the directory
    mkdir "triro_tests/objdump"
    echo "Created directory: triro_tests/objdump"
fi

if [ ! -d "triro_tests/objdump/elf" ]; then
    # If not, create the directory
    mkdir "triro_tests/objdump/elf"
    echo "Created directory: triro_tests/objdump/elf"
fi

if [ ! -d "triro_tests/objdump/elf/readelf" ]; then
    # If not, create the directory
    mkdir "triro_tests/objdump/elf/readelf"
    echo "Created directory: triro_tests/objdump/elf/readelf"
fi

tests_path=tests/*/

# 1. Using the assembler to create obj files
echo "Creating object files..."
for dir in ${tests_path}; do

	dir_name=${dir%/}
	asm_file=$(find "$dir_name" -maxdepth 1 -type f -name '*.asm')

	$triro_assembler -arch=riscv32 $asm_file -M no-aliases -o triro_tests/$(basename ${dir_name}.o) --filetype=obj	
done
echo "Done."

# 2. Using readelf to create first output set
echo "Creating first set of readelf files..."
path_to_triro_tests=./triro_tests

triro_obj_files=($(find "$path_to_triro_tests" -maxdepth 1 -type f))

for i in "${!triro_obj_files[@]}"; do
	triro_obj_file="${triro_obj_files[i]}"
	$triro_readelf -x 2 $triro_obj_file > triro_tests/readelf/$(basename ${triro_obj_file}.txt)
done
echo "Done."

# 3. Using disassembler to revert back to asm files
echo "Disassembling obj files into asm files..."
path_to_triro_tests=./triro_tests

triro_obj_files=($(find "$path_to_triro_tests" -maxdepth 1 -type f))

for i in "${!triro_obj_files[@]}"; do
	triro_obj_file="${triro_obj_files[i]}"
	$triro_disassembler -d -M no-aliases $triro_obj_file > triro_tests/objdump/$(basename ${triro_obj_file}.asm)
done
echo "Done."

# 4. Adjusting the asm files
echo "Adjusting the asm files..."
path_to_triro_asm_files=./triro_tests/objdump

triro_asm_files=($(find "$path_to_triro_asm_files" -maxdepth 1 -type f))

for i in "${!triro_asm_files[@]}"; do
	triro_asm_file="${triro_asm_files[i]}"
	triro_backup_file="$triro_asm_file.bak"
	mv "$triro_asm_file" "$triro_backup_file"
	tail -n +7 "$triro_backup_file" | cut -d$'\t' -f2- | cut -d'<' -f1 | cut -d'>' -f2- > "$triro_asm_file"
	rm "$triro_backup_file"
done
echo "Done."

# 5. Reverting back to object files
echo "Reverting back to object files..."

for i in "${!triro_asm_files[@]}"; do
	triro_asm_file="${triro_asm_files[i]}"
	$triro_assembler -arch=riscv32 -mattr=+m,+c,+zilsd $triro_asm_file -M no-aliases -o triro_tests/objdump/elf/$(basename ${triro_asm_file}.o) --filetype=obj
done
echo "Done."

# 6. Using readelf to generate second text section

echo "Generating second text section using readelf..."
path_to_triro_elf=./triro_tests/objdump/elf

triro_elf_files=($(find "$path_to_triro_elf" -maxdepth 1 -type f))

for i in "${!triro_elf_files[@]}"; do
	triro_elf_file="${triro_elf_files[i]}"
	$triro_readelf -x 2 $triro_elf_file > triro_tests/objdump/elf/readelf/$(basename ${triro_elf_file}.txt)
done
echo "Done."

# 7. Comparing asm files

path_to_triro_readelf_1=./triro_tests/readelf
path_to_triro_readelf_2=./triro_tests/objdump/elf/readelf

files_path1=("$path_to_triro_readelf_1"/*)
files_path2=("$path_to_triro_readelf_2"/*)

# Declare an associative array to store file paths with the same prefix
declare -A file_map

echo "Comparing readelf text section before and after disassembly..."

# Iterate through the files in path2 and populate the file_map
for file_path2 in "${files_path2[@]}"; do
	
	# Ignore directories
	if [ -d "files_path2" ]; then
		continue
	fi
	
	# Extract the 3-character prefix from the file name in path2
	prefix=$(basename "$file_path2" | grep -oE '^[0-9]{3}')
	file_map["$prefix"]="$file_path2"
done

# Iterate through the files in path1 and compare them with corresponding files in path2
for file_path1 in "${files_path1[@]}"; do

	# Ignore directories
	if [ -d "files_path1" ]; then
		continue
	fi
		
	# Extract the 3-character prefix from the file name in path1
	prefix=$(basename "$file_path1" | grep -oE '^[0-9]{3}')
	file_path2="${file_map[$prefix]}"

	if [ -e "$file_path2" ]; then
		if cmp -s "$file_path1" "$file_path2"; then
			echo "Ok: $(basename "$file_path1") and $(basename "$file_path2") are the same"
		else
			echo "Not ok: $(basename "$file_path1") and $(basename "$file_path2") are NOT the same"
		fi
	else
		echo "Warning: No corresponding file found for $file_path1 in $path_to_triro_readelf_2."
	fi
done
