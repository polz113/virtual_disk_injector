#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import struct
from construct import *

class Hider():
    def __str__(self):
        return unicode(self).encode('utf-8')
    def __unicode__(self):
        return self.image_path + str(self.header)
    def parse_header(self):
        self.header = None
    def __init__(self, image_path):
        self.image_path = image_path
        self.parse_header()
    def fixed_hiding_spaces(self):
        """returns the places where data may be hidden without extending the image as a list of (start, length) tuples"""
        return []
    def extending_hiding_spaces(self):
        """returns the starts of places where data may be hidden but the file will have to be extended. Returns a list of (start, length) tuples where length is None if the space available is 2**31 or greater"""
        # these locations can store arbitrary amounts of data
        return []
    def hide_fixed(self, start, data):
        """hide the data without extending the virtual disk image. Performs no checking but updates the neccessarry structures in the image."""
        with open(self.image_path, 'a+') as f:
            f.seek(start)
            # f.write(data)    
    def hide_extending(self, start, data):
        """hide the data by extending the virtual disk image. Updates the neccessary structures in the image."""
        pass

def _hide_at_end(fname, data, clustersize):
    with open(fname, 'ab+') as f:
        f.seek(0, 2)
        print "Writing at", f.tell()
        f.write(data)
        final_size = f.tell()
        for r in xrange(0, (final_size + clustersize) % clustersize):
            # add padding to cluster size
            f.write("\0")

QCOW2HeaderExtension = Struct("qcow2_header_extension",
    UBInt32("type"),
    UBInt32("length"),
    Aligned(UBInt8(""), 4)
    
)

QCOW2Header = Struct("qcow2_header",
    Bytes("magic", 4),
    # QCOW magic string ("QFI\xfb")
    UBInt32("version"), 
    # Version number (valid values are 2 and 3)
    UBInt64("backing_file_offset"),
    #                Offset into the image file at which the backing file name
    #                is stored (NB: The string is not null terminated). 0 if the
    #                image doesn't have a backing file.
    UBInt32("backing_file_size"),
    #                Length of the backing file name in bytes. Must not be
    #                longer than 1023 bytes. Undefined if the image doesn't have
    #                a backing file.
    UBInt32("cluster_bits"),
    #                Number of bits that are used for addressing an offset
    #                within a cluster (1 << cluster_bits is the cluster size).
    #                Must not be less than 9 (i.e. 512 byte clusters).
    UBInt64("size"),
    #                Virtual disk size in bytes
    UBInt32("crypt_method"),
    #                0 for no encryption
    #                1 for AES encryption
    UBInt32("l1_size"),
    #                Number of entries in the active L1 table
    UBInt64("l1_table_offset"),
    #                Offset into the image file at which the active L1 table
    #                starts. Must be aligned to a cluster boundary.
    UBInt64("refcount_table_offset"),
    #                Offset into the image file at which the refcount table
    #                starts. Must be aligned to a cluster boundary.
    UBInt32("refcount_table_clusters"),
    #                Number of clusters that the refcount table occupies
    UBInt32("nb_snapshots"),
    #                Number of snapshots contained in the image
    UBInt64("snapshots_offset"),
    #                Offset into the image file at which the snapshot table
    #                starts. Must be aligned to a cluster boundary.
    Bytes("incompatible_features", 8),
    #                Bitmask of incompatible features. An implementation must
    #                fail to open an image if an unknown bit is set.
    #
    #                Bit 0:      Dirty bit.  If this bit is set then refcounts
    #                            may be inconsistent, make sure to scan L1/L2
    #                            tables to repair refcounts before accessing the
    #                            image.
    #
    #                Bit 1:      Corrupt bit.  If this bit is set then any data
    #                            structure may be corrupt and the image must not
    #                            be written to (unless for regaining
    #                            consistency).
    #
    #                Bits 2-63:  Reserved (set to 0)
    Bytes("compatible_features", 8),
    #                Bitmask of compatible features. An implementation can
    #                safely ignore any unknown bits that are set.
    #
    #                Bit 0:      Lazy refcounts bit.  If this bit is set then
    #                            lazy refcount updates can be used.  This means
    #                            marking the image file dirty and postponing
    #                            refcount metadata updates.
    #
    #                Bits 1-63:  Reserved (set to 0)
    Bytes("autoclear_features", 8),
    #                Bitmask of auto-clear features. An implementation may only
    #                write to an image with unknown auto-clear features if it
    #                clears the respective bits from this field first.
    #
    #                Bits 0-63:  Reserved (set to 0)
    UBInt32("refcount_order"),
    #                Describes the width of a reference count block entry (width
    #                in bits: refcount_bits = 1 << refcount_order). For version 2
    #                images, the order is always assumed to be 4
    #                (i.e. refcount_bits = 16).
    #                This value may not exceed 6 (i.e. refcount_bits = 64).
    UBInt32("header_length"),
    #                Length of the header structure in bytes. For version 2
    #                images, the length is always assumed to be 72 bytes.
)

QCOW2L1ClusterDescriptor = Struct("l1_cluster_descriptor",
    UBInt64("descriptor"),
    Field("offset", lambda ctx: ctx.descriptor & \
        0b0000000111111111111111111111111111111111111111111111111000000000)
)

QCOW2File = Struct("qcow2_file",
    Embed(QCOW2Header),
    RepeatUntil(lambda obj, ctx: obj.type==0, QCOW2HeaderExtension),
    Anchor("end_of_extensions"),
    Padding(lambda ctx: ctx.refcount_table_offset - ctx.end_of_extensions),
    MetaArray(lambda ctx: ctx.refcount_table_clusters*2**(ctx.cluster_bits + 3 - ctx.refcount_order), Byte("refcount_table")),
    Anchor("end_of_refcount_table"),
)

class QCOW2Hider(Hider):
    def parse_header(self):
        with open(self.image_path) as f:
            self.header = QCOW2File.parse_stream(f)
            self.clustersize = 1 << self.header.cluster_bits
        # print len(self.header.refcount_table)
    def fixed_hiding_spaces(self):
        start_of_backing_file = self.header.backing_file_offset
        if start_of_backing_file == 0:
            start_of_backing_file = self.header.refcount_table_offset
        return [(self.header.end_of_extensions, start_of_backing_file - self.header.end_of_extensions)]

    def extending_hiding_spaces(self):
        """returns the starts of places where data may be hidden but the file will have to be extended. Returns a list of (start, length) tuples where length is None if the space available is 2**31 or greater"""
        file_size = os.path.getsize(self.image_path)
        return [(file_size, None)]
        return []
    def hide_extending(self, start, data):
        """hide the data by extending the virtual disk image. Updates the neccessary structures in the image."""
        if start == os.path.getsize(self.image_path):
            _hide_at_end(self.image_path, data, self.clustersize)
        else:
            raise Exception("Unsupported place for extended hiding")


VDIHeader = Struct("vdi_header",
    String("text", 0x40),
    ULInt32("signature"),
    ULInt32("version"),
    ULInt32("header_size"),
    ULInt32("image_type"),
    ULInt32("image_flags"),
    String("description", 256),
    ULInt32("offset_bmap"),
    ULInt32("offset_data"),
    ULInt32("cylinders"),
    ULInt32("heads"),
    ULInt32("sectors"),
    ULInt32("sector_size"),
    ULInt32("unused1"),
    ULInt64("disk_size"),
    ULInt32("block_size"),
    ULInt32("block_extra"),
    ULInt32("blocks_in_image"),
    ULInt32("blocks_allocated"),
    String("uuid_image", 16),
    String("uuid_last_snap", 16),
    String("uuid_link", 16),
    String("uuid_parent", 16),
    Anchor("end_of_header_data"),
    Padding(7*8),
)

VDIFile = Struct("vdi_file",
    Embed(VDIHeader),
    Anchor("end_of_header"),
    Padding(lambda ctx:ctx.offset_bmap - ctx.end_of_header),
    MetaArray(lambda ctx:ctx.blocks_in_image, ULInt32("bmap")),
    Anchor("end_of_bmap"),
    Padding(lambda ctx:ctx.offset_data - ctx.end_of_bmap),
    Anchor("start_of_data")
)

class VDIHider(Hider):
    def parse_header(self):
        with open(self.image_path) as f:
            self.header = VDIFile.parse_stream(f)
            self.clustersize = self.header.block_size
    def fixed_hiding_spaces(self):
        # print self.header
        return [(self.header.end_of_header_data, self.header.offset_bmap - self.header.end_of_header_data),
            (self.header.end_of_bmap, self.header.start_of_data - self.header.end_of_bmap)]
    def extending_hiding_spaces(self):
        """returns the starts of places where data may be hidden but the file will have to be extended. Returns a list of (start, length) tuples where length is None if the space available is 2**31 or greater"""
        """returns the starts of places where data may be hidden but the file will have to be extended"""
        file_size = os.path.getsize(self.image_path)
        return [(file_size, None)]
    def hide_extending(self, start, data):
        """hide the data by extending the virtual disk image. Updates the neccessary structures in the image."""
        if start == os.path.getsize(self.image_path):
            _hide_at_end(self.image_path, data, self.clustersize)
        else:
            raise Exception("Unsupported place for extended hiding")

VMDKSparseHeader = Struct("vmdk_sparse_header",
    ULInt32("magicNumber"),
    ULInt32("version"),
    ULInt32("flags"),
    ULInt64("capacity"), # in sectors
    ULInt64("grainSize"), # in sectors
    ULInt64("descriptorOffset"), # in sectors
    ULInt64("descriptorSize"), # in sectors
    ULInt32("numGTEsPerGT"), 
    ULInt64("rgdOffset"), # in sectors
    ULInt64("gdOffset"), # in sectors
    ULInt64("overHead"), # in sectors
    ULInt8("uncleanShutdown"),
    ULInt8("singleEndLineChar"),
    ULInt8("nonEndLineChar"),
    ULInt8("doubleEndLineChar1"),
    ULInt8("doubleEndLineChar2"),
    ULInt16("compressAlgorithm"),
    Anchor("end_of_header_data"),
    Padding(433),
)

VMDKFile = Struct("vmdk_file",
    Embed(VMDKSparseHeader),
    String("descriptor", lambda ctx: ctx.descriptorSize * 512)
)

class VMDKHider(Hider):
    def parse_header(self):
        with open(self.image_path) as f:
            self.header = VMDKFile.parse_stream(f)
            self.clustersize = self.header.grainSize * 512
        # print self.header
    def fixed_hiding_spaces(self):
        return [(self.header.end_of_header_data, self.header.descriptorOffset * 512 - self.header.end_of_header_data)]
    def extending_hiding_spaces(self):
        """returns the starts of places where data may be hidden but the file will have to be extended. Returns a list of (start, length) tuples where length is None if the space available is 2**31 or greater"""
        """returns the starts of places where data may be hidden but the file will have to be extended"""
        file_size = os.path.getsize(self.image_path)
        return [(file_size, None)]
    def hide_extending(self, start, data):
        """hide the data by extending the virtual disk image. Updates the neccessary structures in the image."""
        if start == os.path.getsize(self.image_path):
            _hide_at_end(self.image_path, data, self.clustersize)
        else:
            raise Exception("Unsupported place for extended hiding")

class VHDChecksumCalculator(Subconstruct):
    def _build(self, obj, stream, context):
        # do something with obj
        checksum = 0
        p1 = stream.tell()
        obj.checksum = 0
        obj.footer_copy.checksum = 0
        self.subcon._build(obj, stream, context)
        s = self.subcon.build(obj)
        s = stream.getvalue()
        for c in s[0:obj.end_of_footer_copy]:
            obj.footer_copy.checksum += ord(c)
        obj.footer_copy.checksum = ~obj.footer_copy.checksum & 0xffffffff
        for c in s[obj.end_of_footer_copy:obj.end_of_header]:
            obj.checksum += ord(c)
        obj.checksum = ~obj.checksum & 0xffffffff
        #self.subcon._build(obj, stream, context)
        # print "new_header_checksum:", obj.checksum
        # print "new_footer_checksum:", obj.footer_copy.checksum
        stream.seek(p1)
        self.subcon._build(obj, stream, context)
        # no return value is necessary

VHDFooter = Struct("vhd_footer",
    String("cookie", 8),
    UBInt32("features"),
    UBInt32("file_format_version"),
    UBInt64("data_offset"),
    UBInt32("time_stamp"),
    String("creator_application", 4),
    UBInt32("creator_version"),
    String("creator_host_OS", 4),
    UBInt64("original_size"),
    UBInt64("current_size"),
    UBInt32("disk_geometry"),
    UBInt32("disk_type"),
    Anchor("before_footer_checksum"),
    UBInt32("checksum"),
    Anchor("after_footer_checksum"),
    String("uuid", 16),
    Byte("saved_state"),
    Anchor("end_of_footer_data"),
    Array(427, Byte("footer_padding")),    
)

VHDParentLocator = Struct("vhd_parent_locator",
    String("platform_code", 4),
    UBInt32("platform_data_space"),
    UBInt32("platform_data_length"),
    UBInt32("reserved"),
    UBInt64("platform_data_offset"),
)

VHDHeader = VHDChecksumCalculator(Struct("vhd_header",
    Rename("footer_copy", VHDFooter),
    Anchor("end_of_footer_copy"),
    String("cookie", 8),
    UBInt64("data_offset"),
    UBInt64("table_offset"),
    UBInt32("header_version"),
    UBInt32("max_table_entries"),
    UBInt32("block_size"),
    Anchor("before_header_checksum"),
    UBInt32("checksum"),
    Anchor("after_header_checksum"),
    String("parent_uuid", 16),
    UBInt32("parent_timestamp"),
    UBInt32("reserved"),
    Anchor("parent_info_start"),
    String("parent_unicode_name", 512),
    Array(8, VHDParentLocator),
    Anchor("end_of_header_data"),
    Array(256, Byte("header_padding")),
    Anchor("end_of_header"),
    MetaArray(lambda ctx: ctx.table_offset - ctx.end_of_header, Byte("padding_before_BAT")),
    Anchor("start_of_BAT"),
))

VHDFile = Struct("vhd_file",
    Embed(VHDHeader),
    # String("raw_bat", 8*1537)
    MetaArray(lambda ctx:ctx.max_table_entries, UBInt32("BAT")),
)



class VHDHider(Hider):
    def parse_header(self):
        with open(self.image_path) as f:
            self.header = VHDFile.parse_stream(f)
            self.clustersize = self.header.block_size
    def fixed_hiding_spaces(self):
        return[
            (self.header.footer_copy.end_of_footer_data,
                self.header.end_of_footer_copy - self.header.footer_copy.end_of_footer_data),
            (self.header.end_of_header_data, self.header.start_of_BAT - self.header.end_of_header_data)]
    def extending_hiding_spaces(self):
        """returns the starts of places where data may be hidden but the file will have to be extended. Returns a list of (start, length) tuples where length is None if the space available is 2**31 or greater"""
        # these locations can store arbitrary amounts of data
        file_size = os.path.getsize(self.image_path)
        footer_len = file_size % 512
        if footer_len == 0:
            footer_len = 512
        return [(file_size - footer_len, None)]
    def hide_fixed(self, start, data):
        """hide the data without extending the virtual disk image. Performs no checking but updates the neccessarry structures in the image."""
        # if the data is to be hidden in the footer copy, in the footer or in the header, checksums must be recalculated
        #    f.write(data)
        # re-read the footer copy and the header
        # re-calculate the checksum
        # write the footer, footer copy and the header
        if start < self.header.end_of_header:
            # print "old_header_checksumX:", header.checksum
            # print "old_footer_checksumX:", header.footer_copy.checksum
            s = VHDHeader.build(self.header)
            s1 = s[:start] + data + s[start+len(data):]
            new_header = VHDHeader.parse(s1)
            # this recalculates the checksums
            header_str = VHDHeader.build(new_header)
            # print "new_header_checksumX", new_new_header.checksum
            # print "new_footer_checksumX", new_new_header.footer_copy.checksum
            file_size = os.path.getsize(self.image_path)
            footer_len = file_size % 512
            if footer_len == 0:
                footer_len = 512
            with open(self.image_path, 'rb+') as f:
                f.seek(0)
                f.write(header_str)
                f.seek(-footer_len, 2)
                f.write(header_str[:footer_len])
            self.header = new_header
        with open(self.image_path, 'ab+') as f: 
            f.seek(start)
            f.write(data)

    def hide_extending(self, start, data):
        """hide the data by extending the virtual disk image. Updates the neccessary structures in the image."""
        file_size = os.path.getsize(self.image_path)
        footer_len = file_size % 512
        if footer_len == 0:
            footer_len = 512
        with open(self.image_path, 'rb') as f:
            f.seek(-footer_len, 2)
            original_footer_start = f.tell()
            footer = f.read()
        with open(self.image_path, 'ab+') as f: 
            f.seek(start)
            f.write(data)
            final_size = f.tell()
            for r in xrange(0, (final_size + self.clustersize) % self.clustersize):
                # add padding to cluster size
                f.write("\0")
            f.write(footer)
            
class RAWHider(Hider):
    def extending_hiding_spaces(self):
        """returns the starts of places where data may be hidden but the file will have to be extended. Returns a list of (start, length) tuples where length is None if the space available is 2**31 or greater"""
        # these locations can store arbitrary amounts of data
        st = os.stat(self.image_path)
        free_space = st.size % 512
        if free_space == 0:
            free_space = 511
        return [(st.size, free_space)]
    def hide_extending(self, start, data):
        if start == os.path.getsize(self.image_path):
            _hide_at_end(self.image_path, data, self.clustersize)
        else:
            raise Exception("Unsupported place for extended hiding")


def create_hider(src_fname, dst_fname=None, in_place=False):
    class_table = {
        '.vdi': VDIHider,
        '.vhd': VHDHider,
        '.vmdk': VMDKHider,
        '.qcow2': QCOW2Hider,
        '.raw': RAWHider,
    }
    basename, ending = os.path.splitext(src_fname)
    if dst_fname is None:
        if in_place:
            dst_fname = src_fname
        else:
            dst_fname = basename + '-watermark' + ending
    return class_table[ending.lower()](src_fname)

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
