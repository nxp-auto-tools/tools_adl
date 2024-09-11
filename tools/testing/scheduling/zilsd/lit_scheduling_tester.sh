#!/bin/bash
# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

# 1. Copying lit.cfg file in the test folder
lit_cfg="./lit.cfg"
tests_dir="./tests"
tests_dir_dep="./tests_dependency"
echo "Copying lit.cfg file..."
cp "$lit_cfg" "$tests_dir"
cp "$lit_cfg" "$tests_dir_dep"
echo "Done."