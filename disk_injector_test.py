#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import struct
from subprocess import call
from virtualdiskinjector import *
import random
from time import sleep

md5_sum_fname = 'virtual_host_test_script/sdc_md5sum.txt'

def __main__():
    N_WRITES = 256
    SEED = 31337
    DISK_SIZE = 3*(2**30)
    SECTOR_SIZE = 512
    static_data = "C" * 32
    extending_data = "D" * 2**18
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
    #for ending, img_type in [('qcow2', 'qcow2'),
    #                         ('vdi', 'vdi'),
    #                         ('vmdk', 'vmdk'),
    #                         ('vhd', 'vpc')]:
    for ending, img_type in [('qcow2', 'qcow2')]:
        hiding_spaces_list = []
        r = random.Random(SEED)
        img_fname = '../data/test_images/test1.'+ending
        print ending
        # create 3GiB image
        call(["qemu-img", "create", "-f", img_type, img_fname, str(DISK_SIZE)])
        # run virtual_host_test_script/test_injection.py 
        # in qemu, write 256 ? Bs ?
        call(["qemu-system-x86_64", "--enable-kvm",
                "-hda", tester_disk_img,
                "-hdb", "fat:rw:virtual_host_test_script",
                "-hdc", img_fname])
        # identify spaces
        c = create_hider(img_fname)
        fixed_spaces = c.fixed_hiding_spaces()
        for space in fixed_spaces:
            hiding_spaces_list.append(space)
        print "Required space:", len(static_data)
        print "Fixed:", fixed_spaces
        extending_spaces = c.extending_hiding_spaces()
        for space in extending_spaces:
            hiding_spaces_list.append(space)
        hiding_spaces[img_type] = hiding_spaces_list
        print "Extending:", extending_spaces 
        call(['cp', img_fname, img_fname + '.orig'])
        c.hide_fixed(fixed_spaces[0][0], static_data)
        c.hide_extending(extending_spaces[0][0], extending_data)
        with open(img_fname, 'r') as f:
            f.seek(fixed_spaces[0][0])
            d1 = f.read(len(static_data))
            assert d1 == static_data
            f.seek(extending_spaces[0][0])
            d2 = f.read(len(extending_data))
            print "extending pre-check"
            # print d2
            assert d2 == extending_data
        # write 256 Bs
        call(['cp', img_fname, img_fname + '.bak'])
        # run virtual_host_test_script/test_injection.py 
        # for a second time, write 256 ? Bs ?
        call(["qemu-system-x86_64", "--enable-kvm",
                "-hda", tester_disk_img,
                "-hdb", "fat:rw:virtual_host_test_script",
                "-hdc", img_fname])

        # check the hidden data
        with open(img_fname, 'r') as f:
            f.seek(fixed_spaces[0][0])
            d1 = f.read(len(static_data))
            assert d1 == static_data
            f.seek(extending_spaces[0][0])
            d2 = f.read(len(extending_data))
            print "extending check"
            print d2
            assert d2 == extending_data
        os.unlink(md5_sum_fname)
        # c.hide_extending(fixed_spaces[0][0], data)
        # print unicode(c)
    print hiding_spaces

if __name__ == '__main__':
    __main__()
