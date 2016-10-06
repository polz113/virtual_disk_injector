def insert_middle_inplace(fname, offset, data, block_size = 2**16):
    f_read = open(fname, 'rb')
    f_write = open(fname, 'rb+')
    to_insert = len(data)
    f_read.seek(0,2)
    read_pos = f_read.tell()
    last_read = read_pos
    read_pos = max(offset, read_pos - block_size)
    f_read.seek(read_pos)
    f_write.seek(read_pos + to_insert)
    while read_pos > offset:
        tmp = f_read.read(block_size)
        f_write.write(tmp)
        last_read = read_pos
        f_read.seek(max(0, last_read - block_size))
        # f_write.seek(max(0, -2 * block_size, 1))
        read_pos = f_read.tell()
        f_write.seek(read_pos + to_insert)
    overshoot = offset - read_pos
    f_read.seek(overshoot, 1)
    f_write.seek(overshoot, 1)
    read_pos = f_read.tell()
    left_to_read = last_read - read_pos
    #f_read.seek(-left_to_read, 1)
    tmp = f_read.read(left_to_read)
    #f_write.seek(-left_to_read, 1)
    f_write.write(tmp)
    f_write.seek(offset)
    f_write.write(data)
    f_read.close()
    f_write.close()
    
def insert_middle_copy(fname, data, offset, block_size = 2**16):
    t = tempfile.TemporaryFile()
    with open(fname, 'rb+') as f:
        f.seek(pos)
        while 1:
            tmp = f.read(block_size)
            if not tmp:
                break
            t.write(tmp)
        f.seek(pos)
        f.write(data)
        t.seek(0)
        while 1:
            tmp = t.read(block_size)
            if not tmp:
                break
            f.write(tmp)
