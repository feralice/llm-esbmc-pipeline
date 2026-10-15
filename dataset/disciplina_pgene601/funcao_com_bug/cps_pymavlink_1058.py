class DFReader_binary:
    def init_arrays_fast(self, progress_callback=None):
        '''initialise arrays for fast recv_match(), but with Cython'''

        self._count = 0
        self.name_to_id = {}
        self.id_to_name = {}
        type_instances = {}

        data = memoryview(self.data_map)
        for f in self.formats.values():
            if f.name == 'FMT':
                fmt_fmt = f
                break
        fmt_type = fmt_fmt.type
        type_offset = -1
        size_offset = -1
        offset = 3 # Header length
        for i in range(len(fmt_fmt.columns)):
            format_spec = FORMAT_TO_STRUCT[fmt_fmt.format[i]][0]
            col_len = struct.calcsize(format_spec)
            if fmt_fmt.columns[i] == 'Type':
                type_offset = offset
                assert col_len == 1, "Unexpected format for FMT.Type"
            elif fmt_fmt.columns[i] == 'Length':
                size_offset = offset
                assert col_len == 1, "Unexpected format for FMT.Length"
            offset += col_len

        offsets = dfindexer.build_offsets(
            data,
            fmt_type,
            fmt_fmt.len,
            type_offset,
            size_offset,
            self.HEAD1,
            self.HEAD2,
            progress_callback=progress_callback
        )

        # Parse the FMT messages
        for ofs in offsets[fmt_type]:
            # Parse the FMT message
            body = data[ofs+3:ofs+fmt_fmt.len]
            elements = list(struct.unpack(fmt_fmt.msg_struct, body))
            ftype = elements[0]
            mfmt = DFFormat(
                ftype,
                null_term(elements[2]), elements[1],
                null_term(elements[3]), null_term(elements[4]),
                oldfmt=self.formats.get(ftype, None))
            self.formats[ftype] = mfmt
            self.name_to_id[mfmt.name] = mfmt.type
            self.id_to_name[mfmt.type] = mfmt.name

        # Parse the UNIT messages
        mtype = self.name_to_id['UNIT']
        fmt = self.formats[mtype]
        mlen = fmt.len
        for ofs in offsets[mtype]:
            body = data[ofs+3:ofs+mlen]
            if len(body)+3 < mlen:
                break
            elements = list(struct.unpack(fmt.msg_struct, body))
            self.unit_lookup[chr(elements[1])] = null_term(elements[2])

        # Parse the MULT messages
        mtype = self.name_to_id['MULT']
        fmt = self.formats[mtype]
        mlen = fmt.len
        for ofs in offsets[mtype]:
            body = data[ofs+3:ofs+mlen]
            if len(body)+3 < mlen:
                break
            elements = list(struct.unpack(fmt.msg_struct, body))
            # Even though the multiplier value is logged as a double, the
            # values in log files look to be single-precision values that have
            # been cast to a double.
            # To ensure that the values saved here can be used to index the
            # MULT_TO_PREFIX table, we round them to 7 significant decimal digits
            mult = float("%.7g" % (elements[2]))
            self.mult_lookup[chr(elements[1])] = mult

        # Parse the FMTU messages
        mtype = self.name_to_id['FMTU']
        fmt = self.formats[mtype]
        mlen = fmt.len
        for ofs in offsets[mtype]:
            body = data[ofs+3:ofs+mlen]
            if len(body)+3 < mlen:
                break
            elements = list(struct.unpack(fmt.msg_struct, body))
            ftype = int(elements[1])
            if ftype in self.formats:
                fmt2 = self.formats[ftype]
                if 'UnitIds' in fmt.colhash:
                    fmt2.set_unit_ids(null_term(elements[fmt.colhash['UnitIds']]), self.unit_lookup)
                if 'MultIds' in fmt.colhash:
                    fmt2.set_mult_ids(null_term(elements[fmt.colhash['MultIds']]), self.mult_lookup)

        # Parse the first 100 messages of each type to try to build the
        # messages dictionary. 100 was chosen as a reasonable heuristic to
        # catch every index value that might be in that message.
        for mtype in range(256):
            if mtype not in self.formats:
                continue
            fmt = self.formats[mtype]
            NMSG = 100 if fmt.instance_field is not None else 1
            for i in range(NMSG):
                if i >= len(offsets[mtype]):
                    break
                ofs = offsets[mtype][i]
                if self.formats[mtype].name not in self.messages:
                    self.offset = ofs
                    self._parse_next()
                if self.formats[mtype].instance_field is not None:
                    fmt = self.formats[mtype]
                    # see if we've has this instance value before
                    idata = data[ofs+3+fmt.instance_ofs:ofs+3+fmt.instance_ofs+fmt.instance_len]
                    if not mtype in type_instances:
                        type_instances[mtype] = set()
                    if not idata in type_instances[mtype]:
                        # its a new one, need to parse it so we have the complete set of instances
                        type_instances[mtype].add(idata)
                        self.offset = ofs
                        self._parse_next()

        self.offsets = offsets
        self.counts = [len(offsets[i]) for i in range(256)]
        self._count = sum(self.counts)
        self.offset = 0
