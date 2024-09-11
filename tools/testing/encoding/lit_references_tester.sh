#!/bin/bash
# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

# 0. Add path for llvm assembler and readelf
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

echo "Delete previous tests..."
find ./references_tests -type f -name "*.o" -exec rm {} \;
find ./references_tests/readelf -type f -name "*.txt" -exec rm {} \;
echo "Done."

# 1. Check if tests output directory exists in the current directory
if [ ! -d "references_tests" ]; then
    # If not, create the directory
    mkdir "references_tests"
    echo "Created directory: references_tests"
fi

if [ ! -d "references_tests/readelf" ]; then
    # If not, create the directory
    mkdir "references_tests/readelf"
    echo "Created directory: references_tests/readelf"
fi


# 2. Using the assembler to create obj files for references
i=0
references_path="./references"
echo "Creating object files for references..."
for ref_file in "$references_path"/*; do
	$llvm_assembler -arch=riscv32 $ref_file -M no-aliases -o references_tests/$(basename ${ref_file}.o) --filetype=obj
	((i++))
done
echo "Done."


# 3. Using readelf to generate text section
path_to_ref_tests="./references_tests"
ref_obj_files=($(find "$path_to_ref_tests" -maxdepth 1 -type f))
echo "Generating text section using readelf..."
for i in "${!ref_obj_files[@]}"; do
	ref_obj_file="${ref_obj_files[i]}"
	$llvm_readelf -x 2 $ref_obj_file > references_tests/readelf/$(basename ${ref_obj_file}.txt)
done
echo "Done."


# 4. Modify objdump files for llvm lit script
readelf_dir="./references_tests/readelf"
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
readelf_dir="./references_tests/readelf"
tests_dir="./tests"
echo "Moving references files to encoding tests directories..."
# Loop through each file in the files folder
for file_path in "$readelf_dir"/*.o.txt; do
    # Extract the base name of the file
    file_base_name=$(basename "$file_path" .asm.o.txt)

    # Find the matching folder in the folders folder
    matching_folder=$(find "$tests_dir" -type d -name "*_${file_base_name}" -print -quit)

    # If a matching folder is found, move the file into that folder and rename it to reference.txt
    if [ -n "$matching_folder" ]; then
        cp "$file_path" "$matching_folder/reference.txt"
    else
        echo "No matching folder found for $file_path"
    fi
done
echo "Done."


# 6. Copying lit.cfg files in each test folder
lit_cfg="./lit.cfg"
tests_dir="./tests"
echo "Copying lit.cfg files..."
for subfolder in "$tests_dir"/*; do
	if [[ -d "$subfolder" ]]; then
		cp "$lit_cfg" "$subfolder"
	fi
done
echo "Done."