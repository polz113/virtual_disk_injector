#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import struct
from subprocess import call
from virtualdiskinjector import *
import random
from time import sleep

def __main__():
    N_WRITES = 256
    SEED = 31337
    DISK_SIZE = 3*(2**30)
    SECTOR_SIZE = 512
    data = """The woods are lovely, dark and deep
but I have promises to keep
and miles to go before I sleep.
"""
    """
Белеет парус одинокий
в тумане моря голубом
что ищет он в стране далёкой?
Что кинул он в краю родном?
    """
    free_space_summary = dict()
    for ending, img_type in [('qcow2', 'qcow2'),
                             ('vdi', 'vdi'),
                             ('vmdk', 'vmdk'),
                             ('vhd', 'vpc')]:
    # for ending in ['vhd']:
        r = random.Random(SEED)
        img_fname = '../data/test_images/test1.'+ending
        print ending
        # create 3GiB image
        call(["qemu-img", "create", "-f", img_type, img_fname, str(DISK_SIZE)])
        # write data
        sleep(2)
        print "attaching..."
        call(["qemu-nbd", "-c", "/dev/nbd0", img_fname])
        sleep(2)
        print "writing..."
        for i in xrange(N_WRITES):
            fpos = r.randint(0, DISK_SIZE-1)
            with open("/dev/nbd0", 'w') as f:
                f.seek(fpos)
                f.write('A')
        sleep(5)
        
        print "detaching..."
        call(["qemu-nbd", "-d", "/dev/nbd0"])
        sleep(5)
        # identify spaces
        c = create_hider(img_fname)
        fixed_spaces = c.fixed_hiding_spaces()
        print "Required space:", len(data)
        print "Fixed:", fixed_spaces
        extending_spaces = c.extending_hiding_spaces()
        print "Extending:", extending_spaces 
        c.hide_fixed(fixed_spaces[0][0], data)
        c.hide_extending(extending_spaces[0][0], 'D' * (2**24))
        print "Data hidden"
        # c.hide_extending(fixed_spaces[0][0], data)
        # print unicode(c)

if __name__ == '__main__':
    __main__()
