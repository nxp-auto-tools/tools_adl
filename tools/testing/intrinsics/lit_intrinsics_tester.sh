#!/bin/bash
# Copyright 2024 NXP 
# SPDX-License-Identifier: BSD-2-Clause

# 1. Copying lit.cfg file in the test folder
lit_cfg="./lit.cfg"
tests_dir="./tests"
echo "Copying lit.cfg file..."
cp "$lit_cfg" "$tests_dir"
echo "Done."