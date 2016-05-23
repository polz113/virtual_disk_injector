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
    data = "C" * 32
    """The woods are lovely, dark and deep
but I have promises to keep
and miles to go before I sleep.
"""
    """
Белеет парус одинокий
в тумане моря голубом
что ищет он в стране далёкой?
Что кинул он в краю родном?
    """
    hiding_spaces = dict()
    tester_disk_img = "../data/test_images/tester.vmdk"
    for ending, img_type in [('qcow2', 'qcow2'),
                             ('vdi', 'vdi'),
                             ('vmdk', 'vmdk'),
                             ('vhd', 'vpc')]:
    # for ending in ['vhd']:
        hiding_spaces_list = []
        r = random.Random(SEED)
        img_fname = '../data/test_images/test1.'+ending
        print ending
        # create 3GiB image
        call(["qemu-img", "create", "-f", img_type, img_fname, str(DISK_SIZE)])
        # write 256 As
        call(["qemu-system-x86_64", "--enable-kvm", "-hda", "tester.vmdk", "-hdb", img_fname])
        # identify spaces
        c = create_hider(img_fname)
        fixed_spaces = c.fixed_hiding_spaces()
        for space in fixed_spaces:
            hiding_spaces_list.append(space)
        print "Required space:", len(data)
        print "Fixed:", fixed_spaces
        extending_spaces = c.extending_hiding_spaces()
        for space in extending_spaces:
            hiding_spaces_list.append(space)
        hiding_spaces[img_type] = hiding_spaces_list
        print "Extending:", extending_spaces 
        c.hide_fixed(fixed_spaces[0][0], data)
        c.hide_extending(extending_spaces[0][0], 'D' * 1000000)
        print "Data hidden"
        # write 256 Bs
        call(["qemu-system-x86_64", "--enable-kvm", "-hda", "tester.vmdk", "-hdb", img_fname])
        # check the hidden data
        with open(img_fname, 'r') as f:
            f.seek(fixed_spaces[0][0])
            d1 = f.read(len(data))
            assert d1 == data
            f.seek(fixed_spaces[0][0])
            d2 = f.read(1000000)
            assert d2 == 'D' * 1000000
        # c.hide_extending(fixed_spaces[0][0], data)
        # print unicode(c)
    print hiding_spaces

if __name__ == '__main__':
    __main__()
