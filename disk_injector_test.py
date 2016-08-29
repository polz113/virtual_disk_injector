#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import struct
from subprocess import call
from virtualdiskinjector import *
import random
from time import sleep

md5_sum_fname = 'virtual_host_test_script/sdc_md5sum.txt'

def count_matches(s1, s2):
    n_ok = 0
    n_miss = 0
    result = []
    for i, val in enumerate(s1):
        if i > len(s2) - 1 or s2[i] != val:
            if n_ok > 0:
                result.append((n_ok, True))
                n_ok = 0
            n_miss += 1
        else:
            if n_miss > 0:
                result.append((n_miss, False))
                n_miss = 0
            n_ok += 1
    if n_miss > 0:
        result.append((n_miss, False))
    if n_ok > 0:
        result.append((n_ok, True))
    return result
    

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
        c = create_hider(img_fname)
        print "Initial"
        print "  A:", c.guest_data_offset(1534333117)
        print "  B:", c.guest_data_offset(2190361692)
        call(['cp', img_fname, img_fname + '.orig'])
        call(["qemu-system-x86_64", "--enable-kvm",
                "-hda", tester_disk_img,
                "-hdb", "fat:rw:virtual_host_test_script",
                "-hdc", img_fname])
        call(['cp', img_fname, img_fname + '.run1'])
        # identify spaces
        c = create_hider(img_fname)
        fixed_spaces = c.fixed_hiding_spaces()
        for space in fixed_spaces:
            hiding_spaces_list.append(space)
        print "Required space:", len(static_data)
        print "Fixed:", fixed_spaces
        extending_spaces = c.extending_hiding_spaces()
        print "cluster size:", c.header.cluster_size
        for space in extending_spaces:
            hiding_spaces_list.append(space)
        hiding_spaces[img_type] = hiding_spaces_list
        print "After first run"
        print "  A:", c.guest_data_offset(1534333117)
        print "  B:", c.guest_data_offset(2190361692)
        print "Extending:", extending_spaces
        print "before hiding:", os.stat(img_fname).st_size
        call(['cp', img_fname, img_fname + '.nohide'])
        c.hide_fixed(fixed_spaces[0][0], static_data)
        c.hide_extending(extending_spaces[0][0], extending_data)
        call(['cp', img_fname, img_fname + '.hide'])
        print "after hiding:", os.stat(img_fname).st_size
        with open(img_fname, 'r') as f:
            f.seek(fixed_spaces[0][0])
            d1 = f.read(len(static_data))
            assert d1 == static_data
            f.seek(extending_spaces[0][0])
            d2 = f.read(len(extending_data))
            print "extending pre-check"
            print "match:", count_matches(d2, extending_data)
            # print d2
            assert d2 == extending_data
        # write 256 Bs
        # run virtual_host_test_script/test_injection.py 
        # for a second time, write 256 ? Bs ?
        call(["qemu-system-x86_64", "--enable-kvm",
                "-hda", tester_disk_img,
                "-hdb", "fat:rw:virtual_host_test_script",
                "-hdc", img_fname])
        call(['cp', img_fname, img_fname + '.run2_hide'])
        call(['cp', img_fname + '.nohide', img_fname + '.run2_nohide'])
        call(["qemu-system-x86_64", "--enable-kvm",
                "-hda", tester_disk_img,
                "-hdb", "fat:rw:virtual_host_test_script",
                "-hdc", img_fname + '.run2_nohide'])
        c = create_hider(img_fname)
        print "After second run"
        print "  A:", c.guest_data_offset(1534333117)
        print "  B:", c.guest_data_offset(2190361692)
        # check the hidden data
        with open(img_fname, 'r') as f:
            f.seek(fixed_spaces[0][0])
            d1 = f.read(len(static_data))
            assert d1 == static_data
            f.seek(extending_spaces[0][0])
            d2 = f.read(len(extending_data))
            print "extending check"
            print "match:", count_matches(d2, extending_data)
            assert d2 == extending_data
        os.unlink(md5_sum_fname)
        # c.hide_extending(fixed_spaces[0][0], data)
        # print unicode(c)
    print hiding_spaces

if __name__ == '__main__':
    __main__()
