# -*- coding: utf-8 -*-
# Copyright (c) 2015 Jason Power
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

""" This file creates a single CPU and a two-level cache system.
This script takes a single parameter which specifies a binary to execute.
If none is provided it executes 'hello' by default (mostly used for testing)

See Part 1, Chapter 3: Adding cache to the configuration script in the
learning_gem5 book for more information about this script.
This file exports options for the L1 I/D and L2 cache sizes.

IMPORTANT: If you modify this file, it's likely that the Learning gem5 book
           also needs to be updated. For now, email Jason <power.jg@gmail.com>

"""

# import the m5 (gem5) library created when gem5 is built
from random import SystemRandom
import m5
# import all of the SimObjects
from m5.objects import *

# Add the common scripts to our path
m5.util.addToPath('../')

# import the caches which we made
from caches import *

# import the SimpleOpts module
from common import SimpleOpts

# get ISA for the default binary to run. This is mostly for simple testing
isa = str(m5.defines.buildEnv['TARGET_ISA']).lower()

# Default to running 'hello', use the compiled ISA to find the binary
# grab the specific path to the binary
thispath = os.path.dirname(os.path.realpath(__file__))
# default_binary = os.path.join(thispath, '../../../',
#     'tests/test-progs/hello/bin/', isa, 'linux/hello')
default_binary = os.path.join('/home/xhc/vector_runahead/Runahead-master/benchmarks/cgo2017/program/randacc/bin/x86/randacc-no')

# Binary to execute
SimpleOpts.add_option("--binary", nargs='?', default=default_binary, help="Test binary")
# SimpleOpts.add_option("--binary_args", help="Arguments to the test binary", type=str)
SimpleOpts.add_option("--binary_args", help="Arguments to the test binary", type=str, default = '600000')
SimpleOpts.add_option("--mode", default='baseline', choices=['baseline', 'runahead', 'pre'], 
    help="Which implementstion of the o3 CPU should be run")
SimpleOpts.add_option("--rob_size", help="size of re-order buffer", default=192)
SimpleOpts.add_option("--sst_enabled", help="Specifies whether PRE uses SST", default=True)
SimpleOpts.add_option("--rrr_enabled", help="Specifies whether PRE uses RRR", default=True)
SimpleOpts.add_option("--exit_PRE_when_squash", help="Specifies whether CPU exits PRE mode upon a squash in the ROB", default=False)
SimpleOpts.add_option("--prdq_entries", help="Size of the Precise Register Deallocation Queue", default=192)
SimpleOpts.add_option("--sst_entries", help="Specifies the maximum extries of this SST", default=128)

# Finalize the arguments and grab the args so we can pass it on to our objects
args = SimpleOpts.parse_args()

# create the system we are going to simulate
system = System()

# Set the clock fequency of the system (and all of its children)
system.clk_domain = SrcClockDomain()
system.clk_domain.clock = '2.66GHz'
system.clk_domain.voltage_domain = VoltageDomain()

# Set up the system
system.mem_mode = 'timing'               # Use timing accesses
system.mem_ranges = [AddrRange('1024MB')] # Create an address range

# 03 out of order CPU
runahead = True if args.mode == 'runahead' else False
if args.mode == 'baseline':
    print('----------------baseline----------------\n')
    system.cpu = O3CPU()
elif args.mode == 'runahead':
    print('----------------runahead----------------\n')
    system.cpu = RunaheadO3CPU()
elif args.mode == 'pre':
    print('----------------PRE----------------\n')
    system.cpu = PreO3CPU()
    system.cpu.sst_enabled = args.sst_enabled
    system.cpu.rrr_enabled = args.rrr_enabled
    system.cpu.exit_PRE_when_squash = args.exit_PRE_when_squash
    system.cpu.prdqEntries = args.prdq_entries
    system.cpu.sstEntries = args.sst_entries

system.cpu.numROBEntries = args.rob_size
system.cpu.LQEntries = LQEntries
system.cpu.SQEntries = SQEntries
system.cpu.numIQEntries = numIQEntries
# system.cpu.branchPred = branchPred

# Create an L1 instruction and data cache
system.cpu.icache = L1ICache(args)
system.cpu.dcache = L1DCache(args)

# Connect the instruction and data caches to the CPU
system.cpu.icache.connectCPU(system.cpu)
system.cpu.dcache.connectCPU(system.cpu)

# Create a memory bus, a coherent crossbar, in this case
system.l2bus = L2XBar()

# Hook the CPU ports up to the l2bus
system.cpu.icache.connectBus(system.l2bus)
system.cpu.dcache.connectBus(system.l2bus)

# Create an L2 cache and connect it to the l2bus
system.l2cache = L2Cache(args)
system.l2cache.connectCPUSideBus(system.l2bus)

# Create a memory bus
system.membus = SystemXBar()

# Connect the L2 cache to the membus
system.l2cache.connectMemSideBus(system.membus)

# create the interrupt controller for the CPU
system.cpu.createInterruptController()

# For x86 only, make sure the interrupts are connected to the memory
# Note: these are directly connected to the memory bus and are not cached
if m5.defines.buildEnv['TARGET_ISA'] == "x86":
    system.cpu.interrupts[0].pio = system.membus.mem_side_ports
    system.cpu.interrupts[0].int_requestor = system.membus.cpu_side_ports
    system.cpu.interrupts[0].int_responder = system.membus.mem_side_ports

# Connect the system up to the membus
system.system_port = system.membus.cpu_side_ports

# Create a DDR3 memory controller
system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = DDR3_1600_8x8()
system.mem_ctrl.dram.range = system.mem_ranges[0]
system.mem_ctrl.port = system.membus.mem_side_ports

system.workload = SEWorkload.init_compatible(args.binary)

# Create a process for a simple "Hello World" application
process = Process()
# Set the command
# cmd is a list which begins with the executable (like argv)
if args.binary_args:
    cmd = [args.binary]
    cmd.extend(args.binary_args.split(','))
    print('cmd:', cmd)
    process.cmd = cmd
else:
    process.cmd = [args.binary]
# Set the cpu to use the process as its workload and create thread contexts
system.cpu.workload = process
system.cpu.createThreads()

# set up the root SimObject and start the simulation
root = Root(full_system = False, system = system)
# instantiate all of the objects we've created above
m5.instantiate()

print("Beginning simulation!")
exit_event = m5.simulate()
print('Exiting @ tick %i because %s' % (m5.curTick(), exit_event.getCause()))
