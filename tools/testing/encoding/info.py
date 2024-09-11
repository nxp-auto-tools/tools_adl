#Copyright 2024 NXP
#SPDX-License-Identifier: BSD-2-Clause

instructions = {
	'add' : ['rd', 'rs1', 'rs2'],
	'add_tprel' : ['rd', 'rs1', 'tp', 'imm_add_tprel'],
	'auipc' : ['rd', 'imm_u_pc'],
	'c.ld' : ['rdc_p', 'immd_cl(rs1c_p)'],
	'c.ldsp' : ['rx', 'immd_ci(sp)'],
	'c.sd' : ['rs2c_p', 'immd_cs(rs1c_p)'],
	'c.sdsp' : ['rs2c', 'immd_css(sp)'],
	'ld' : ['rd', 'imm_i(rs1)'],
	'lui' : ['rd', 'imm_u'],
	'sd' : ['rs2', 'imm_s(rs1)']
}

operands = {
	'rd' : ['zero', 'x0', 'ra', 'x1', 'sp', 'x2', 'gp', 'x3', 'tp', 'x4', 't0', 'x5', 't1', 'x6', 't2', 'x7', 's0', 'x8', 's1', 'x9', 'a0', 'x10', 'a1', 'x11', 'a2', 'x12', 'a3', 'x13', 'a4', 'x14', 'a5', 'x15', 'a6', 'x16', 'a7', 'x17', 's2', 'x18', 's3', 'x19', 's4', 'x20', 's5', 'x21', 's6', 'x22', 's7', 'x23', 's8', 'x24', 's9', 'x25', 's10', 'x26', 's11', 'x27', 't3', 'x28', 't4', 'x29', 't5', 'x30', 't6', 'x31'],
	'rx' : ['ra', 'x1', 'sp', 'x2', 'gp', 'x3', 'tp', 'x4', 't0', 'x5', 't1', 'x6', 't2', 'x7', 's0', 'x8', 'fp', 's1', 'x9', 'a0', 'x10', 'a1', 'x11', 'a2', 'x12', 'a3', 'x13', 'a4', 'x14', 'a5', 'x15', 'a6', 'x16', 'a7', 'x17', 's2', 'x18', 's3', 'x19', 's4', 'x20', 's5', 'x21', 's6', 'x22', 's7', 'x23', 's8', 'x24', 's9', 'x25', 's10', 'x26', 's11', 'x27', 't3', 'x28', 't4', 'x29', 't5', 'x30', 't6', 'x31'],
	'rdc_p' : ['s0', 'x8', 's1', 'x9', 'a0', 'x10', 'a1', 'x11', 'a2', 'x12', 'a3', 'x13', 'a4', 'x14', 'a5', 'x15'],
	'rs1' : ['zero', 'x0', 'ra', 'x1', 'sp', 'x2', 'gp', 'x3', 'tp', 'x4', 't0', 'x5', 't1', 'x6', 't2', 'x7', 's0', 'x8', 's1', 'x9', 'a0', 'x10', 'a1', 'x11', 'a2', 'x12', 'a3', 'x13', 'a4', 'x14', 'a5', 'x15', 'a6', 'x16', 'a7', 'x17', 's2', 'x18', 's3', 'x19', 's4', 'x20', 's5', 'x21', 's6', 'x22', 's7', 'x23', 's8', 'x24', 's9', 'x25', 's10', 'x26', 's11', 'x27', 't3', 'x28', 't4', 'x29', 't5', 'x30', 't6', 'x31'],
	'rs1c' : ['zero', 'x0', 'ra', 'x1', 'sp', 'x2', 'gp', 'x3', 'tp', 'x4', 't0', 'x5', 't1', 'x6', 't2', 'x7', 's0', 'x8', 's1', 'x9', 'a0', 'x10', 'a1', 'x11', 'a2', 'x12', 'a3', 'x13', 'a4', 'x14', 'a5', 'x15', 'a6', 'x16', 'a7', 'x17', 's2', 'x18', 's3', 'x19', 's4', 'x20', 's5', 'x21', 's6', 'x22', 's7', 'x23', 's8', 'x24', 's9', 'x25', 's10', 'x26', 's11', 'x27', 't3', 'x28', 't4', 'x29', 't5', 'x30', 't6', 'x31'],
	'rs1c_p' : ['s0', 'x8', 's1', 'x9', 'a0', 'x10', 'a1', 'x11', 'a2', 'x12', 'a3', 'x13', 'a4', 'x14', 'a5', 'x15'],
	'rs2' : ['zero', 'x0', 'ra', 'x1', 'sp', 'x2', 'gp', 'x3', 'tp', 'x4', 't0', 'x5', 't1', 'x6', 't2', 'x7', 's0', 'x8', 's1', 'x9', 'a0', 'x10', 'a1', 'x11', 'a2', 'x12', 'a3', 'x13', 'a4', 'x14', 'a5', 'x15', 'a6', 'x16', 'a7', 'x17', 's2', 'x18', 's3', 'x19', 's4', 'x20', 's5', 'x21', 's6', 'x22', 's7', 'x23', 's8', 'x24', 's9', 'x25', 's10', 'x26', 's11', 'x27', 't3', 'x28', 't4', 'x29', 't5', 'x30', 't6', 'x31'],
	'rs2c' : ['zero', 'x0', 'ra', 'x1', 'sp', 'x2', 'gp', 'x3', 'tp', 'x4', 't0', 'x5', 't1', 'x6', 't2', 'x7', 's0', 'x8', 's1', 'x9', 'a0', 'x10', 'a1', 'x11', 'a2', 'x12', 'a3', 'x13', 'a4', 'x14', 'a5', 'x15', 'a6', 'x16', 'a7', 'x17', 's2', 'x18', 's3', 'x19', 's4', 'x20', 's5', 'x21', 's6', 'x22', 's7', 'x23', 's8', 'x24', 's9', 'x25', 's10', 'x26', 's11', 'x27', 't3', 'x28', 't4', 'x29', 't5', 'x30', 't6', 'x31'],
	'rs2c_p' : ['s0', 'x8', 's1', 'x9', 'a0', 'x10', 'a1', 'x11', 'a2', 'x12', 'a3', 'x13', 'a4', 'x14', 'a5', 'x15']
}