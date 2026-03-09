# Copyright 2023-2025 NXP
# SPDX-License-Identifier: BSD-2-Clause


def sort_builtins(file_path):
    """
    Sorts the builtin definitions in alphabetical order and writes the
    sorted output to the specified file.

    Args:
        file_path (str): Path to the file in which the sorted builtin
            definitions will be written.

    Returns:
        str: The generated content containing all builtins sorted alphabetically.
    """
    with open(file_path) as f:
        content_list = f.readlines()

    import os

    # sort key function
    def get_rear(sub):
        index = -1
        while sub[index] != " ":
            index -= 1
        return sub[index:-1]

    # remove new line characters
    content_list = [x.strip() for x in content_list]
    sort_list = list()
    experimental_list = list()
    comments_list = list()
    def_list = list()
    undef_list = list()
    for line in content_list:
        if line.startswith("TARGET_BUILTIN"):
            if "experimental" not in line:
                sort_list.append(line)
            elif "experimental" in line:
                experimental_list.append(line)
        if line.startswith("//"):
            comments_list.append(line)
        if line.startswith("#undef"):
            undef_list.append(line)
        if line.startswith("#if") or line.startswith("#endif") or "define" in line:
            def_list.append(line)

    test_sort_list = sort_list.copy()
    sort_list.sort(key=get_rear)
    if test_sort_list == sort_list:
        return
    os.remove(file_path)
    f = open(file_path, "a")
    for line in comments_list:
        f.write(line)
        f.write("\n")
    f.write("\n")
    for line in def_list:
        f.write(line)
        f.write("\n")
    f.write("\n")
    for line in sort_list:
        f.write(line)
        f.write("\n")
    f.write("\n")
    for line in experimental_list:
        f.write(line)
        f.write("\n")
    f.write("\n")
    for line in undef_list:
        f.write(line)
        f.write("\n")
    f.close()


import sys

if __name__ == "__main__":
    sort_builtins(sys.argv[1])
