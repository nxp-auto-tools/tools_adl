# Copyright 2023-2025 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package make_td
import sys
import os
import argparse

## This function calls the main module in order to run the scripts for generating td files
def make_td_function():
    list_dir = list()
    extension_command_line = ""
    output_dir = ""
    no_sail = ""
    if len(sys.argv) == 3:
        if "--extension" in sys.argv[2]:
            extension_command_line = sys.argv[2]
        if "--output" in sys.argv[2]:
            output_dir = sys.argv[2]
        if "--no_sail" in sys.argv[2]:
            no_sail = True
    if len(sys.argv) == 4:
        if "--extension" in sys.argv[2]:
            extension_command_line = sys.argv[2]
        if "--output" in sys.argv[2]:
            output_dir = sys.argv[2]
        if "--extension" in sys.argv[3]:
            extension_command_line = sys.argv[3]
        if "--output" in sys.argv[3]:
            output_dir = sys.argv[3]
        if "--no_sail" in sys.argv[3]:
            no_sail = sys.argv[3]
    if len(sys.argv) == 5:
        extension_command_line = sys.argv[2]
        output_dir = sys.argv[3]
        no_sail = sys.argv[4]
    for fname in os.listdir("."):
        list_dir.append(fname)
    if "tools" in list_dir:
        if extension_command_line != "":
            if output_dir != "":
                if no_sail != "":
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + extension_command_line + " " + output_dir + " " + no_sail)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + extension_command_line + " " + output_dir)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
            else:
                if no_sail != "":
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + extension_command_line + " " + no_sail)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + extension_command_line)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
        else:
            if output_dir != "":
                if no_sail != "":
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + output_dir + " " + no_sail)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + output_dir)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
            else:
                if no_sail != "":
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + no_sail)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1])
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
    else:
        if extension_command_line != "":
            if output_dir != "":
                if no_sail != "":
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + os.path.relpath(sys.argv[1], os.getcwd()) + " " + extension_command_line + " " + output_dir + " " + no_sail)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)    
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + os.path.relpath(sys.argv[1], os.getcwd()) + " " + extension_command_line + " " + output_dir)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)     
            else:
                if no_sail != "":
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + extension_command_line + " " + no_sail)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + extension_command_line)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
        else:
            if output_dir != "":
                if no_sail != "":
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + output_dir + " " + no_sail)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + output_dir)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
            else:
                if no_sail != "":
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + no_sail)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1])
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)

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