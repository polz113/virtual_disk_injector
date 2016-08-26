#!/usr/bin/env python

import random
from subprocess import call, check_output
import hashlib
import os
import datetime

md5_sum_fname = "/mnt/test_script/sdc_md5sum.txt"
log_fname_format = "/mnt/test_script/log_{:0>3}.txt"
disc_fname = "/dev/sdc"
BLOCK_SIZE = 2**20 # 2**20
N_WRITES = 1 # *(2**4)
hash_fn = hashlib.md5

if hasattr(os, 'sync'):
    sync = os.sync
else:
    import ctypes
    libc = ctypes.CDLL("libc.so.6")
    def sync():
        libc.sync()

def find_free_log_fname():
    log_n = 1
    log_fname = log_fname_format.format(log_n)
    while os.path.isfile(log_fname):
        log_n += 1
        log_fname = log_fname_format.format(log_n)
    return log_fname

def log(s):
    with open(log_fname, "a") as f:
        print("log:" + s)
        f.write(s + "\n")
    sync()

def disc_hash(fname):
    h = hash_fn()
    with open(fname, 'r') as f:
        s = f.read(BLOCK_SIZE)
        while len(s):
            h.update(s)
            s = f.read(BLOCK_SIZE)
    return h.hexdigest()

def write_randomly(fname, n, s, r):    
    disc_size = int(check_output(["blockdev", "--getsize64", fname]))
    log("size:" + str(disc_size))
    with open(disc_fname, 'w') as f:
        for i in xrange(n):
            fpos = r.randint(0, disc_size-1)
            f.seek(fpos)
            f.write(s)
            log("wrote {} at {}".format(s, fpos))


log_fname = find_free_log_fname()
log("Run:" + datetime.datetime.now().isoformat())

try:
    with open(md5_sum_fname, "r") as f:
        hash_sum_str = f.read()
except Exception, e:
    log("Hash sum file missing")
    hash_sum_str = None
    
if hash_sum_str is None:
    r = random.Random(0xbadc0de)
    write_randomly(disc_fname, N_WRITES, 'A', r)

h = disc_hash(disc_fname)

if hash_sum_str is None:
    with open(md5_sum_fname, "w") as f:
        f.write(h)
    call(["poweroff"])
else:
    print "heeeere"
    s1 = str(h) + " ?= " + hash_sum_str
    print s1
    log(s1)
    r = random.Random(31337)
    write_randomly(disc_fname, N_WRITES, 'B', r)
    # os.unlink(md5_sum_fname)
    call(["poweroff"])
