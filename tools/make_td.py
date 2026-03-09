# Copyright 2023-2026 NXP
# SPDX-License-Identifier: BSD-2-Clause
## @package make_td
import sys
import os
import argparse

def make_td_function():
    """
    Calls the main module to execute all scripts required for generating
    the LLVM TableGen (.td) files.

    This function acts as a high-level wrapper that triggers the full
    generation pipeline, ensuring that all necessary components such as
    instruction formats, register definitions, intrinsics, scheduling
    models, and other TableGen artifacts are produced.

    Returns:
        None
    """
    list_dir = list()
    extension_command_line = ""
    output_dir = ""
    no_sail = ""
    target = ""
    if len(sys.argv) == 2:
        if "--target" in sys.argv[1]:
            target = sys.argv[1]
        if "--extension" in sys.argv[1]:
            extension_command_line = sys.argv[1]
        if "--output" in sys.argv[1]:
            output_dir = sys.argv[1]
        if "--no-sail" in sys.argv[1]:
            no_sail = True
    if len(sys.argv) == 3:
        if "--target" in sys.argv[2]:
            target = sys.argv[2]
        if "--extension" in sys.argv[2]:
            extension_command_line = sys.argv[2]
        if "--output" in sys.argv[2]:
            output_dir = sys.argv[2]
        if "--no-sail" in sys.argv[2]:
            no_sail = True
    if len(sys.argv) == 4:
        if "--target" in sys.argv[2]:
            target = sys.argv[2]
        if "--extension" in sys.argv[2]:
            extension_command_line = sys.argv[2]
        if "--output" in sys.argv[2]:
            output_dir = sys.argv[2]
        if "--no-sail" in sys.argv[2]:
            no_sail = True
        if "--target" in sys.argv[3]:
            target = sys.argv[3]
        if "--extension" in sys.argv[3]:
            extension_command_line = sys.argv[3]
        if "--output" in sys.argv[3]:
            output_dir = sys.argv[3]
        if "--no-sail" in sys.argv[3]:
            no_sail = True
    if len(sys.argv) == 5:
        if "--target" in sys.argv[2]:
            target = sys.argv[2]
        if "--extension" in sys.argv[2]:
            extension_command_line = sys.argv[2]
        if "--output" in sys.argv[2]:
            output_dir = sys.argv[2]
        if "--no-sail" in sys.argv[2]:
            no_sail = True
        if "--target" in sys.argv[3]:
            target = sys.argv[3]
        if "--extension" in sys.argv[3]:
            extension_command_line = sys.argv[3]
        if "--output" in sys.argv[3]:
            output_dir = sys.argv[3]
        if "--no-sail" in sys.argv[3]:
            no_sail = True
        if "--target" in sys.argv[4]:
            target = sys.argv[4]
        if "--extension" in sys.argv[4]:
            extension_command_line = sys.argv[4]
        if "--output" in sys.argv[4]:
            output_dir = sys.argv[4]
        if "--no-sail" in sys.argv[4]:
            no_sail = True
    if len(sys.argv) == 6:
        if "--target" in sys.argv[2]:
            target = sys.argv[2]
        if "--extension" in sys.argv[2]:
            extension_command_line = sys.argv[2]
        if "--output" in sys.argv[2]:
            output_dir = sys.argv[2]
        if "--no-sail" in sys.argv[2]:
            no_sail = True
        if "--target" in sys.argv[3]:
            target = sys.argv[3]
        if "--extension" in sys.argv[3]:
            extension_command_line = sys.argv[3]
        if "--output" in sys.argv[3]:
            output_dir = sys.argv[3]
        if "--no-sail" in sys.argv[3]:
            no_sail = True
        if "--target" in sys.argv[4]:
            target = sys.argv[4]
        if "--extension" in sys.argv[4]:
            extension_command_line = sys.argv[4]
        if "--output" in sys.argv[4]:
            output_dir = sys.argv[4]
        if "--no-sail" in sys.argv[4]:
            no_sail = True
        if "--target" in sys.argv[5]:
            target = sys.argv[5]
        if "--extension" in sys.argv[5]:
            extension_command_line = sys.argv[5]
        if "--output" in sys.argv[5]:
            output_dir = sys.argv[5]
        if "--no-sail" in sys.argv[5]:
            no_sail = True
    if output_dir != "":
        output_dir = os.path.join(output_dir,"TD")
    for fname in os.listdir("."):
        list_dir.append(fname)
    if "tools" in list_dir:
        if extension_command_line != "":
            if output_dir != "":
                if no_sail is True:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + extension_command_line + " " + output_dir + " " + "--no-sail=True")
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str) 
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + extension_command_line + " " + output_dir)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
            else:
                if no_sail is True:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + extension_command_line + " "+ "--no-sail=True")
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + extension_command_line)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
        else:
            if output_dir != "":
                if no_sail is True:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + output_dir + " " + "--no-sail=True")
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + output_dir)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
            else:
                if no_sail is True:
                    try:
                        print('ok')
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + "--no-sail=True")
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + target)
                    except:
                        print('ok')
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
    else:
        if extension_command_line != "":
            if output_dir != "":
                if no_sail is True:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + os.path.relpath(sys.argv[1], os.getcwd()) + " " + target + " " + extension_command_line + " " + output_dir + " " + "--no-sail=True")
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)    
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + os.path.relpath(sys.argv[1], os.getcwd()) + " " + target + " " + extension_command_line + " " + output_dir)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)     
            else:
                if no_sail is True:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + extension_command_line + " " + target + " " + "--no-sail=True")
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + extension_command_line)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
        else:
            if output_dir != "":
                if no_sail is True:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + output_dir + " " + "--no-sail=True")
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + output_dir)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
            else:
                if no_sail is True:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + " " + target + " " + "--no-sail=True")
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
                        parser.print_help(sys.stderr)
                        sys.exit(1)
                else:
                    try:
                        os.system("python3 "  + os.path.relpath(os.path.dirname(__file__).replace("\\", "/")) + "/" + "main.py" + " " + sys.argv[1] + target)
                    except:
                        print("No XML model is provided in the command line! Please run make_td.py with a proper XML file")
                        parser = argparse.ArgumentParser()
                        parser.add_argument("file", type=str)
                        parser.add_argument("--target", dest="target", type=str)
                        parser.add_argument("--extension", "-e", dest="extension", type=str)  # Elimină "="
                        parser.add_argument("--output", "-o", dest='output', type=str)
                        parser.add_argument("--no-sail", dest='no_sail', type=str)
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