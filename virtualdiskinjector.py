#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import math
from construct import Struct, Value, Array, Switch, RepeatUntil, MetaArray,\
                      Rename, Subconstruct,\
                      OnDemandPointer, Embed, Anchor, Aligned,\
                      UBInt8, UBInt16, UBInt32, UBInt64, Byte,\
                      ULInt8, ULInt16, ULInt32, ULInt64,\
                      Bytes, String
# from construct.lib.py3compat import BytesIO
from file_insert_middle import insert_middle_inplace, insert_middle_copy


class Hider(object):
    """Base class for hiding data inside a virtual disk image"""
    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        return self.image_path + str(self.header)

    def parse_header(self):
        """parse the file header / footer"""
        self.header = None

    def __init__(self, image_path):
        self.image_path = image_path
        self.image_file = open(self.image_path, 'rb+')
        self.header = None
        self.parse_header()

    def __del__(self):
        self.image_file.close()

    def fixed_hiding_spaces(self):
        """return a list of (start, length) tuples where data may be hidden.
The size of the image will remain the same."""
        return []

    def extending_hiding_spaces(self):
        """return a list (start, length) tuples where data may be hidden.
The size of the image will increase.
length is None if the space available is 2**31 or greater"""
        # these locations can store arbitrary amounts of data
        return []

    def hide_fixed(self, start, data):
        """hide data without extending the virtual disk image.
Performs no checking but updates the neccessarry structures in the image."""
        self.image_file.seek(start)
        self.image_file.write(data)
        self.image_file.seek(0)
        self.parse_header()

    def hide_extending(self, start, data):
        """hide data by extending the virtual disk image.
Updates the neccessary structures in the image."""
        pass


def _hide_at_end(fname, data, cluster_size):
    file_size = os.path.getsize(fname)
    _insert_into_file(fname, file_size, data, cluster_size)


def _insert_into_file(fname, pos, data, alignment=1,
                      padding_char="\0", in_place=True):
    BLOCK_SIZE = 2**12
    end_of_data = pos + len(data)
    required_padding = (alignment - end_of_data) % alignment
    data = data + padding_char[0] * required_padding
    if in_place:
        insert_middle_inplace(fname, offset=pos, data=data,
                              block_size=BLOCK_SIZE)
    else:
        insert_middle_copy(fname, offset=pos, data=data,
                           block_size=BLOCK_SIZE)
    return len(data)


QCOW2HeaderExtension = \
    Struct("qcow2_header_extension",
           UBInt32("type"),
           UBInt32("length"),
           Aligned(UBInt8(""), 4)
          )


QCOW2Header = \
    Struct("qcow2_header",
           Bytes("magic", 4),
           # QCOW magic string ("QFI\xfb")
           UBInt32("version"),
           # Version number (valid values are 2 and 3)
           UBInt64("backing_file_offset"),
           # Offset into the image file at which the backing file name
           # is stored (NB: The string is not null terminated). 0 if the
           # image doesn't have a backing file.
           UBInt32("backing_file_size"),
           # Length of the backing file name in bytes. Must not be
           # longer than 1023 bytes. Undefined if the image doesn't have
           # a backing file.
           UBInt32("cluster_bits"),
           Value("cluster_size", lambda ctx: 1 << ctx.cluster_bits),
           # Number of bits that are used for addressing an offset
           # within a cluster (1 << cluster_bits is the cluster size).
           # Must not be less than 9 (i.e. 512 byte clusters).
           UBInt64("size"),
           # Virtual disk size in bytes
           UBInt32("crypt_method"),
           # 0 for no encryption
           # 1 for AES encryption
           UBInt32("l1_size"),
           # Number of entries in the active L1 table
           UBInt64("l1_table_offset"),
           # Offset into the image file at which the active L1 table
           # starts. Must be aligned to a cluster boundary.
           UBInt64("refcount_table_offset"),
           # Offset into the image file at which the refcount table
           # starts. Must be aligned to a cluster boundary.
           UBInt32("refcount_table_clusters"),
           # Number of clusters that the refcount table occupies
           UBInt32("nb_snapshots"),
           # Number of snapshots contained in the image
           UBInt64("snapshots_offset"),
           # Offset into the image file at which the snapshot table
           # starts. Must be aligned to a cluster boundary.
           Bytes("incompatible_features", 8),
           # Bitmask of incompatible features. An implementation must
           # fail to open an image if an unknown bit is set.
           #
           # Bit 0:      Dirty bit.  If this bit is set then refcounts
           #             may be inconsistent, make sure to scan L1/L2
           #             tables to repair refcounts before accessing the
           #             image.
           #
           # Bit 1:      Corrupt bit.  If this bit is set then any data
           #             structure may be corrupt and the image must not
           #             be written to (unless for regaining
           #             consistency).
           #
           # Bits 2-63:  Reserved (set to 0)
           Bytes("compatible_features", 8),
           # Bitmask of compatible features. An implementation can
           # safely ignore any unknown bits that are set.
           #
           # Bit 0:      Lazy refcounts bit.  If this bit is set then
           #             lazy refcount updates can be used.  This means
           #             marking the image file dirty and postponing
           #             refcount metadata updates.
           #
           # Bits 1-63:  Reserved (set to 0)
           Bytes("autoclear_features", 8),
           # Bitmask of auto-clear features. An implementation may only
           # write to an image with unknown auto-clear features if it
           # clears the respective bits from this field first.
           #
           # Bits 0-63:  Reserved (set to 0)
           UBInt32("refcount_order"),
           # Describes the width of a reference count block entry (width
           # in bits: refcount_bits = 1 << refcount_order). For version 2
           # images, the order is always assumed to be 4
           # (i.e. refcount_bits = 16).
           # This value may not exceed 6 (i.e. refcount_bits = 64).
           Value("refcount_bits", lambda ctx: 1 << ctx.refcount_order),
           Value("refcount_bytes", lambda ctx: 1 << (ctx.refcount_order - 3)),
           UBInt32("header_length"),
           # Length of the header structure in bytes. For version 2
           # images, the length is always assumed to be 72 bytes.
          )


QCOW2DataCluster = \
    Array(lambda ctx: ctx._._.cluster_size,
          Byte("cluster_data"),
         )


QCOW2L2ClusterDescriptor = \
    Struct("l2_table",
           UBInt64("descriptor"),
           Value("offset", lambda ctx: ctx.descriptor & \
                 0b0000000111111111111111111111111111111111111111111111111000000000),
           OnDemandPointer(lambda ctx: ctx.offset, QCOW2DataCluster)
          )


QCOW2L2Table = \
    Array(lambda ctx: ctx._.cluster_size / 8,
          QCOW2L2ClusterDescriptor,
         )


QCOW2L1ClusterDescriptor = \
    Struct("l1_table",
           UBInt64("descriptor"),
           Value("offset", lambda ctx: ctx.descriptor & \
                 0b0000000111111111111111111111111111111111111111111111111000000000),
           OnDemandPointer(lambda ctx: ctx.offset, QCOW2L2Table)
          )


QCOW2RefcountBlock = \
    Array(lambda ctx: ctx._.cluster_size / ctx._.refcount_bytes,
          Switch("refcount_data", lambda ctx: ctx._.refcount_bits,
                 {
                     8: UBInt8("count"),
                     16: UBInt16("count"),  # this is the default
                     # 24: UBInt24("count"),
                     32: UBInt32("count"),
                     # 40: UBInt40("count"),
                     # 48: UBInt48("count"),
                     # 56: UBInt56("count"),
                     64: UBInt64("count"),
                 }
                )
         )


QCOW2RefcountTable = \
    Struct("refcount_table",
           UBInt64("descriptor"),
           Value("offset", lambda ctx: ctx.descriptor & \
                 0b0000000111111111111111111111111111111111111111111111111000000000),
           OnDemandPointer(lambda ctx: ctx.offset, QCOW2RefcountBlock)
          )

QCOW2File = \
    Struct("qcow2_file",
           Embed(QCOW2Header),
           RepeatUntil(lambda obj, ctx: obj.type == 0, QCOW2HeaderExtension),
           Anchor("end_of_extensions"),
           OnDemandPointer(lambda ctx: ctx.l1_table_offset,
                           Array(lambda ctx: ctx.l1_size,
                                 QCOW2L1ClusterDescriptor)
                          ),
           OnDemandPointer(lambda ctx: ctx.refcount_table_offset,
                           Array(lambda ctx:
                                 ctx.refcount_table_clusters*2**(ctx.cluster_bits - 8),
                                 QCOW2RefcountTable)
                          ),
           Anchor("end_of_refcount_table"),
          )


class QCOW2Hider(Hider):
    """Hide data in a QCOW2 (Qemu) virtual disk image"""

    def __del__(self):
        self.image_file.close()

    def parse_header(self):
        self.header = QCOW2File.parse_stream(self.image_file)
        self.cluster_size = self.header.cluster_size
        # print len(self.header.refcount_table)

    def fixed_hiding_spaces(self):
        """return a list of (start, length) tuples where data may be hidden.
The size of the image will remain the same."""
        start_of_backing_file = self.header.backing_file_offset
        if start_of_backing_file == 0:
            start_of_backing_file = self.header.refcount_table_offset
        return [(self.header.end_of_extensions,
                 start_of_backing_file - self.header.end_of_extensions)]

    def extending_hiding_spaces(self):
        """return a list (start, length) tuples where data may be hidden.
The size of the image will increase.
length is None if the space available is 2**31 or greater"""
        # these locations can store arbitrary amounts of data
        file_size = os.path.getsize(self.image_path)
        return [(file_size, None)]

    def _change_refcounts(self, start, length, ref_change):
        """correct the refcounts table.
currently does not yet grow refcount table."""
        header = self.header
        class Foo(object):
            """hack to force the header into QCOW2RefcountBlock"""
            _ = header
        ctx = Foo()
        offset = start - (start % self.cluster_size)
        if self.cluster_size % length != 0:
            length = (length / self.cluster_size + 1) * self.cluster_size
        old_refcount_table_index = None
        refcount_data = None
        while length > 0:
            refcount_table_index, refcount_block_index = self.refcount_index(offset)
            if refcount_table_index != old_refcount_table_index:
                if refcount_data is not None:
                    QCOW2RefcountBlock._build(refcount_data, self.image_file, ctx)
                refcount_table = self.header.refcount_table.value
                refcount_block = refcount_table[refcount_table_index]
                if refcount_block.offset == 0:
                    break
                self.image_file.seek(refcount_block.offset)
                refcount_data = refcount_block.refcount_data.value
            refcount_data[refcount_block_index] += ref_change
            length -= self.cluster_size
            offset += self.cluster_size
        if refcount_data is not None:
            QCOW2RefcountBlock._build(refcount_data, self.image_file, ctx)

    def hide_extending(self, start, data):
        """hide the data by extending the virtual disk image.
Updates the neccessary structures in the imagge."""
        if start == os.path.getsize(self.image_path):
            _hide_at_end(self.image_path, data, self.cluster_size)
            self._change_refcounts(start, len(data), +1)
        else:
            raise Exception("Unsupported place for extended hiding")

    def guest_data_offset(self, offset):
        """covert offset from the one visible to the VM to an offset in the image file"""
        ENTRY_SIZE = 8
        l2_entries = (self.cluster_size / ENTRY_SIZE)
        l2_index = (offset / self.cluster_size) % l2_entries
        l1_index = (offset / self.cluster_size) / l2_entries
        if not l1_index < self.header.l1_size-1:
            return None
        cluster_offset = \
            self.header.l1_table.value[l1_index].l2_table.value[l2_index].offset
        return cluster_offset + (offset % self.cluster_size)

    def refcount_index(self, offset):
        """return the refcount table and block indexes for VM-visible offset"""
        ENTRY_SIZE = 8
        refcount_block_entries = (self.cluster_size * ENTRY_SIZE / self.header.refcount_bits)
        refcount_block_index = (offset / self.cluster_size) % refcount_block_entries
        refcount_table_index = (offset / self.cluster_size) / refcount_block_entries
        return (refcount_table_index, refcount_block_index)

    def refcount_entry_offset(self, offset):
        """return the refcount entry offset in the image file"""
        table_index, block_index = self.refcount_index(offset)
        refcount_block_offset = self.header.refcount_table.value[table_index].offset
        return refcount_block_offset + block_index * self.header.refcount_bytes


VDIHeader = \
    Struct("vdi_header",
           String("text", 0x40),
           ULInt32("signature"),
           ULInt32("version"),
           ULInt32("header_size"),
           ULInt32("image_type"),
           ULInt32("image_flags"),
           String("description", 256),
           ULInt32("offset_bmap"),
           # OnDemandPointer(lambda ctx: ctx.offset_bmap, VDIBlockMap),
           ULInt32("offset_data"),
           # OnDemandPointer(lambda ctx: ctx.offset_data, VDIBlockMap),
           ULInt32("cylinders"),
           ULInt32("heads"),
           ULInt32("sectors"),
           ULInt32("sector_size"),
           ULInt32("unused1"),
           ULInt64("disk_size"),
           ULInt32("block_size"),
           Value("cluster_size", lambda ctx: ctx.block_size),
           ULInt32("block_extra"),
           ULInt32("blocks_in_image"),
           ULInt32("blocks_allocated"),
           String("uuid_image", 16),
           String("uuid_last_snap", 16),
           String("uuid_link", 16),
           String("uuid_parent", 16),
           Anchor("end_of_header_data"),
           Bytes("pad1", 7*8),
          )

VDIDataBlock = Bytes("data", lambda ctx: ctx._.block_size)

VDIBlockPointer = \
    Struct("block_map",
           ULInt32("offset"),
           OnDemandPointer(lambda ctx: ctx.offset, VDIDataBlock),
          )

VDIBlockMap = \
    Array(lambda ctx: ctx.blocks_in_image,
          VDIBlockPointer,
         )

VDIFile = \
    Struct("vdi_file",
           Embed(VDIHeader),
           Anchor("end_of_header"),
           Bytes("pad2", lambda ctx: ctx.offset_bmap - ctx.end_of_header),
           VDIBlockMap,
           #MetaArray(lambda ctx:ctx.blocks_in_image, ULInt32("bmap")),
           Anchor("end_of_bmap"),
           Bytes("pad3", lambda ctx: ctx.offset_data - ctx.end_of_bmap),
           Anchor("start_of_data")
          )

class VDIHider(Hider):
    """Hide data in a VDI (VirtualBox) virtual disk image"""

    def parse_header(self):
        self.header = VDIFile.parse_stream(self.image_file)
        self.cluster_size = self.header.cluster_size

    def fixed_hiding_spaces(self):
        """return a list of (start, length) tuples where data may be hidden.
The size of the image will remain the same."""
        # print self.header
        return [(self.header.end_of_header_data,
                 self.header.offset_bmap - self.header.end_of_header_data),
                (self.header.end_of_bmap,
                 self.header.start_of_data - self.header.end_of_bmap)
               ]

    def extending_hiding_spaces(self):
        """return a list (start, length) tuples where data may be hidden.
The size of the image will increase.
length is None if the space available is 2**31 or greater"""
        # these locations can store arbitrary amounts of data
        file_size = os.path.getsize(self.image_path)
        return [(file_size, None)]

    def hide_extending(self, start, data):
        """hide the data by extending the virtual disk image.
Updates the neccessary structures in the image."""
        if start == os.path.getsize(self.image_path):
            _hide_at_end(self.image_path, data, self.cluster_size)
            self.header.blocks_allocated +=\
                int(math.ceil(1.0 * len(data) / self.cluster_size))
            self.image_file.seek(0)
            VDIHeader.build_stream(self.header, self.image_file)
            self.image_file.close()
            self.image_file = open(self.image_path, "rb+")
            self.parse_header()
        else:
            raise Exception("Unsupported place for extended hiding")

    def guest_data_offset(self, offset):
        """covert offset from the one visible to the VM to an offset in the image file"""
        table_offset = offset / self.header.block_size
        block_offset = self.header.block_map[table_offset].offset
        return block_offset + (offset % self.header.block_size)


VMDKSparseHeader = \
    Struct("vmdk_sparse_header",
           ULInt32("magicNumber"),
           ULInt32("version"),
           ULInt32("flags"),
           ULInt64("capacity"), # in sectors
           ULInt64("grainSize"), # in sectors
           Value("cluster_size", lambda ctx: ctx.grainSize * 512),
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
           Bytes("pad1", 433),
          )

VMDKDataBlock = Bytes("data", lambda ctx: ctx._.cluster_size)

VMDKBlockPointer = \
    Struct("block_map",
           ULInt32("offset"),
           OnDemandPointer(lambda ctx: ctx.offset, VMDKDataBlock),
          )

VMDKBlockMap = \
    Array(lambda ctx: ctx.blocks_in_image,
          VMDKBlockPointer,
         )

VMDKFile = \
    Struct("vmdk_file",
           Embed(VMDKSparseHeader),
           String("descriptor", lambda ctx: ctx.descriptorSize * 512)
          )

class VMDKHider(Hider):
    """Hide data in a VMDK (VMware) virtual disk image"""

    def parse_header(self):
        self.header = VMDKFile.parse_stream(self.image_file)
        self.cluster_size = self.header.cluster_size
        # print self.header

    def fixed_hiding_spaces(self):
        """return a list of (start, length) tuples where data may be hidden.
The size of the image will remain the same."""
        return [(self.header.end_of_header_data,
                 self.header.descriptorOffset * 512 - self.header.end_of_header_data)]

    def extending_hiding_spaces(self):
        """return a list (start, length) tuples where data may be hidden.
The size of the image will increase. length is None if the space available is 2**31 or greater"""
        # these locations can store arbitrary amounts of data
        file_size = os.path.getsize(self.image_path)
        return [(file_size, None)]

    def hide_extending(self, start, data):
        """hide the data by extending the virtual disk image.
Updates the neccessary structures in the image."""
        if start == os.path.getsize(self.image_path):
            _hide_at_end(self.image_path, data, self.cluster_size)
        else:
            raise Exception("Unsupported place for extended hiding")

    def guest_data_offset(self, offset):
        """covert offset from the one visible to the VM to an offset in the image file"""
        table_offset = offset / self.header.block_size
        block_offset = self.header.block_map[table_offset].offset
        return block_offset + (offset % self.header.block_size)


class VHDChecksumCalculator(Subconstruct):
    """Calculate checksums for VMDK (VMware) virtual disk image"""

    def _build(self, obj, stream, context):
        # do something with obj
        stream_pos_at_start = stream.tell()
        obj.checksum = 0
        obj.footer_copy.checksum = 0
        self.subcon._build(obj, stream, context)
        self.subcon.build(obj)
        header_data = stream.getvalue()
        for i in header_data[0:obj.end_of_footer_copy]:
            obj.footer_copy.checksum += ord(i)
        obj.footer_copy.checksum = ~obj.footer_copy.checksum & 0xffffffff
        for i in header_data[obj.end_of_footer_copy:obj.end_of_header]:
            obj.checksum += ord(i)
        obj.checksum = ~obj.checksum & 0xffffffff
        #self.subcon._build(obj, stream, context)
        # print "new_header_checksum:", obj.checksum
        # print "new_footer_checksum:", obj.footer_copy.checksum
        stream.seek(stream_pos_at_start)
        self.subcon._build(obj, stream, context)
        # no return value is necessary

VHDFooter = \
    Struct("vhd_footer",
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

VHDParentLocator = \
    Struct("vhd_parent_locator",
           String("platform_code", 4),
           UBInt32("platform_data_space"),
           UBInt32("platform_data_length"),
           UBInt32("reserved"),
           UBInt64("platform_data_offset"),
          )

VHDParentDataCluster = \
    Array(lambda ctx: ctx._.cluster_size,
          Byte("cluster_data"),
         )

VHDDataBlock = \
    Struct("data_block",
           Bytes("bitmap", lambda ctx: ctx._.bitmap_size),
           Bytes("data", lambda ctx: ctx._.cluster_size)
          )

VHDBlockPointer = \
    Struct("block_map",
           UBInt32("sector_offset"),
           Value("offset", lambda ctx: ctx.sector_offset * 512),
           # OnDemandPointer(lambda ctx: ctx.offset, VHDDataBlock),
          )

VHDBlockMap = \
    Array(lambda ctx: ctx.max_table_entries,
          VHDBlockPointer,
         )

VHDHeader = \
    VHDChecksumCalculator(
        Struct("vhd_header",
               Rename("footer_copy", VHDFooter),
               Anchor("end_of_footer_copy"),
               String("cookie", 8),
               UBInt64("data_offset"),
               UBInt64("table_offset"),
               UBInt32("header_version"),
               UBInt32("max_table_entries"),
               UBInt32("block_size"),
               Value("cluster_size", lambda ctx: ctx.block_size),
               Value("bitmap_size",
                     lambda ctx: (ctx.block_size / (8 * 512) + 511) & ~511),
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
               MetaArray(lambda ctx: ctx.table_offset - ctx.end_of_header,
                         Byte("padding_before_BAT")),
               Anchor("start_of_BAT"),
               VHDBlockMap,
              )
        )

VHDFile = \
    Struct("vhd_file",
           Embed(VHDHeader),
           # String("raw_bat", 8*1537)
           # MetaArray(lambda ctx:ctx.max_table_entries, UBInt32("BAT")),
          )


class VHDHider(Hider):
    """Hide data in a VHD (Microsoft Virtual PC) virtual disk image"""

    def parse_header(self):
        self.image_file.seek(0)
        self.header = VHDFile.parse_stream(self.image_file)
        self.cluster_size = self.header.cluster_size

    def fixed_hiding_spaces(self):
        """return a list of (start, length) tuples where data may be hidden.
The size of the image will remain the same."""
        return [
            (self.header.footer_copy.end_of_footer_data,
             self.header.end_of_footer_copy - self.header.footer_copy.end_of_footer_data),
            (self.header.end_of_header_data,
             self.header.start_of_BAT - self.header.end_of_header_data)]

    def extending_hiding_spaces(self):
        """return a list (start, length) tuples where data may be hidden.
The size of the image will increase. length is None if the space available is 2**31 or greater"""
        # these locations can store arbitrary amounts of data
        spaces = []
        for i in self.header.block_map:
            if i.sector_offset != 2**32 - 1:
                spaces.append((i.offset, None))
        return spaces

    def hide_fixed(self, start, data):
        """hide the data without extending the virtual disk image.
Performs no checking but updates the neccessarry structures in the image."""
        # if the data is to be hidden in the footer copy,
        # in the footer or in the header, checksums must be recalculated
        # re-read the footer copy and the header
        # re-calculate the checksum
        # write the footer, footer copy and the header
        if start < self.header.end_of_header:
            # print "old_header_checksumX:", header.checksum
            # print "old_footer_checksumX:", header.footer_copy.checksum
            header_data = VHDHeader.build(self.header)
            new_header_data = header_data[:start] +\
                data +\
                header_data[start+len(data):]
            new_header = VHDHeader.parse(new_header_data)
            # this recalculates the checksums
            header_str = VHDHeader.build(new_header)
            # print "new_header_checksumX", new_new_header.checksum
            # print "new_footer_checksumX", new_new_header.footer_copy.checksum
            file_size = os.path.getsize(self.image_path)
            footer_len = file_size % 512
            if footer_len == 0:
                footer_len = 512
            self.image_file.seek(0)
            self.image_file.write(header_str)
            self.image_file.seek(-footer_len, 2)
            self.image_file.write(header_str[:footer_len])
            self.header = new_header
        self.image_file.seek(start)
        self.image_file.write(data)

    def hide_extending(self, start, data):
        """hide the data by extending the virtual disk image.
Updates the neccessary structures in the image."""
        if (len(data) % 512) != 0:
            data = data + "\0" * ((512 - len(data)) % 512)
        sector_len = len(data) / 512
        start_ok = False
        offsets = []
        sector_start = start / 512
        for i in self.header.block_map:
            sector_offset = i.sector_offset
            if sector_offset != 2**32-1 and sector_offset >= sector_start:
                if sector_offset == sector_start:
                    start_ok = True
                sector_offset += sector_len
            offsets.append(sector_offset)
        if not start_ok:
            raise Exception("Unsupported hiding place")
        _insert_into_file(self.image_path, start, data)
        block_map = Array(len(offsets),
                          UBInt32("sector_offset"))
        # print "offsets:", offsets
        self.image_file.seek(self.header.table_offset)
        block_map.build_stream(offsets, self.image_file)
        self.parse_header()
        # VHDBlockMap._build(self.header.block_map, self.image_file, self.header)

    def guest_data_offset(self, offset):
        """covert offset from the one visible to the VM to an offset in the image file"""
        pagetable_index = offset / self.header.block_size
        pageentry_index = (offset % self.header.block_size) / 512
        if pagetable_index >= self.header.max_table_entries or \
                self.header.block_map[pagetable_index] == 0xffffffff:
            return None
        bitmap_offset = 512 * self.header.block_map[pagetable_index].offset
        block_offset = bitmap_offset + self.header.bitmap_size + (512 * pageentry_index)
        return block_offset


class RAWHider(Hider):
    """Hide data in a raw image
Only appends up to 511B to the end of the file."""

    def extending_hiding_spaces(self):
        """return a list (start, length) tuples where data may be hidden.
The size of the image will increase.
length is None if the space available is 2**31 or greater"""
        # these locations can store arbitrary amounts of data
        status = os.stat(self.image_path)
        free_space = status.size % 512
        if free_space == 0:
            free_space = 511
        return [(status.size, free_space)]

    def hide_extending(self, start, data):
        if start == os.path.getsize(self.image_path):
            _hide_at_end(self.image_path, data, 1)
        else:
            raise Exception("Unsupported place for extended hiding")

    def guest_data_offset(self, offset):
        """simply return the offset"""
        return offset


def create_hider(src_fname, dst_fname=None, in_place=False):
    """returns the appropriate hider according to the file ending of a virtual disk image"""
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
