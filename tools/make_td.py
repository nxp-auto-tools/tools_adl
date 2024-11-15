# Copyright 2024 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package make_td
import sys
import os


## This function calls the main module in order to run the scripts for generating td files
def make_td_function():
    list_dir = list()
    extension_command_line = ""
    output_dir = ""
    if len(sys.argv) == 3:
        if "--extension" in sys.argv[2]:
            extension_command_line = sys.argv[2]
        if "--output" in sys.argv[2]:
            output_dir = sys.argv[2]
    if len(sys.argv) == 4:
        extension_command_line = sys.argv[2]
        output_dir = sys.argv[3]
    for fname in os.listdir("."):
        list_dir.append(fname)
    if "tools" in list_dir:
        if extension_command_line != "":
            if output_dir != "":
                    os.system(
                    "python3 ./tools/main.py " + sys.argv[1] + " " + extension_command_line + " " + output_dir
                )
            else:
                os.system(
                    "python3 ./tools/main.py " + sys.argv[1] + " " + extension_command_line
                )
        else:
            if output_dir != "":
                os.system("python3 ./tools/main.py " + sys.argv[1] + " " + output_dir)
            else:
                os.system("python3 ./tools/main.py " + sys.argv[1])
    else:
        if extension_command_line != "":
            if output_dir != "":
                os.system("python3 ./main.py " + sys.argv[1] + " " + extension_command_line + " " + output_dir)        
            else:
                os.system("python3 ./main.py " + sys.argv[1] + " " + extension_command_line)
        else:
            if output_dir != "":
                os.system("python3 ./main.py " + sys.argv[1] + " " + output_dir)
            else:
                os.system("python3 ./main.py " + sys.argv[1])


if __name__ == "__main__":
    for fname in os.listdir("."):
        if fname.endswith(".td"):
            os.system("del *.td")
            break
    for fname in os.listdir("."):
        if fname.endswith(".def"):
            os.system("del *.def")
            break
    for fname in os.listdir("."):
        if fname.endswith(".h"):
            os.system("del *.h")
            break
    for fname in os.listdir("."):
        if fname.endswith(".h"):
            os.system("del *.sail")
            break
    make_td_function()
