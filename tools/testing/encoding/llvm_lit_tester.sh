#!/bin/bash
# Copyright 2023-2025 NXP 
# SPDX-License-Identifier: BSD-2-Clause

# 0. Add path for llvm-assembler, llvm-readelf, tests_folder, refs_folder, and lit_cfg
llvm_assembler=$1
llvm_readelf=$2
tests_folder=$3
refs_folder=$4
lit_cfg=$5

if [ "$#" -ne 5 ]; then
    echo "Usage: $0 <llvm-assembler> <llvm-readelf> <tests_folder> <refs_folder> <lit_cfg>"
    return 1
fi


results_dir=$(dirname $tests_folder)
# 1. Check if tests output directory exists in the results directory
if [ -d "$results_dir/references_tests" ]; then
	echo "Delete previous tests..."
	find "$results_dir/references_tests" -type f -name "*.o" -exec rm {} \;
	find "$results_dir/references_tests/readelf" -type f -name "*.txt" -exec rm {} \;
else
    mkdir -p "$results_dir/references_tests/readelf"
    echo "Created directory: references_tests/readelf"
fi
echo "Done."


# 2. Using the assembler to create obj files for references
i=0
echo "Creating object files for references..."
for ref_file in "$refs_folder"/*; do
	$llvm_assembler -arch=riscv32 $ref_file -M no-aliases -o $results_dir/references_tests/$(basename ${ref_file}.o) --filetype=obj
	((i++))
done
echo "Done."


# 3. Using readelf to generate text section
path_to_ref_tests="$results_dir/references_tests"
ref_obj_files=($(find "$path_to_ref_tests" -maxdepth 1 -type f))
echo "Generating text section using readelf..."
for i in "${!ref_obj_files[@]}"; do
	ref_obj_file="${ref_obj_files[i]}"
	$llvm_readelf -x 2 $ref_obj_file > $results_dir/references_tests/readelf/$(basename ${ref_obj_file}.txt)
done
echo "Done."


# 4. Modify objdump files for llvm lit script
readelf_dir="$results_dir/references_tests/readelf"
echo "Modifying readelf files for llvm-lit script..."
# Check if the "readelf" directory exists
if [ -d "$readelf_dir" ]; then
    # Iterate through each text file in the "readelf" directory
    for file in "$readelf_dir"/*.txt; do
        # Check if the file is a regular file
        if [ -f "$file" ]; then
            # Delete the first line from the file
            sed -i '1d' "$file"
			# Remove the first and last column of each row using awk
            awk '{print $2, $3, $4, $5}' FS=" " OFS=" " "$file" > "$file.tmp" && mv "$file.tmp" "$file"
			# Add "//CHECK: " before each row
            sed -i 's/^/\/\/CHECK: /' "$file"
        fi
    done
else
    echo "Error: The 'readelf' directory does not exist."
fi
echo "Done."


# 5. Move the reference files to encoding tests directories
readelf_dir="$results_dir/references_tests/readelf"
echo "Moving references files to encoding tests directories..."
# Loop through each file in the files folder
for file_path in "$readelf_dir"/*.o.txt; do
    # Extract the base name of the file
	file_base_name=$(basename "$file_path" .asm.o.txt)
	# Find the matching folder in the folders folder
    matching_folder=$(find "$tests_folder" -type d -name "${file_base_name}" -print -quit)
    # If a matching folder is found, move the file into that folder and rename it to reference.txt
    if [ -n "$matching_folder" ]; then
        cp "$file_path" "$matching_folder/reference.txt"
    else
        echo "No matching folder found for $file_path"
    fi
done
echo "Done."