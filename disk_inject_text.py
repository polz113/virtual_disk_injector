#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import struct
from virtualdiskinjector import *


def __main__():
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
    for ending in ['qcow2', 'vdi', 'vmdk', 'vhd']:
    # for ending in ['vhd']:
        print ending
        c = create_hider('test1.'+ending)
        fixed_spaces = c.fixed_hiding_spaces()
        print "Required space:", len(data)
        print "Fixed:", fixed_spaces 
        extending_spaces = c.extending_hiding_spaces()
        print "Extending:", extending_spaces 
        c.hide_fixed(fixed_spaces[0][0], data)
        print "Data hidden"
        # c.hide_extending(extending_spaces[0][0], 'D' * 100000) 
        # c.hide_extending(fixed_spaces[0][0], data)
        # print unicode(c)

if __name__ == '__main__':
    __main__()
