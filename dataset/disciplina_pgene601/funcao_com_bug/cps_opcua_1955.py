class DataSetWriter:
    async def generate_uadp_dataset(self, pds: PublishedDataSet) -> UadpDataSetMessage:
        msg_cfg: UadpDataSetWriterMessageDataType = self._cfg.MessageSettings
        header = UadpDataSetMessageHeader(Valid=True)
        self._seq_no += 1
        if UadpDataSetMessageContentMask.MajorVersion in msg_cfg.DataSetMessageContentMask:
            header.CfgMajorVersion = pds.dataset._meta.ConfigurationVersion.MajorVersion
        if UadpDataSetMessageContentMask.MinorVersion in msg_cfg.DataSetMessageContentMask:
            header.CfgMinorVersion = pds.dataset._meta.ConfigurationVersion.MinorVersion
        if UadpDataSetMessageContentMask.PicoSeconds in msg_cfg.DataSetMessageContentMask:
            header.PicoSeconds = UInt16(0)  # Not supported
        if UadpDataSetMessageContentMask.SequenceNumber in msg_cfg.DataSetMessageContentMask:
            header.SequenceNo = UInt16(self._seq_no)
        if DataSetFieldContentMask.RawData in self._cfg.DataSetFieldContentMask:
            data, status, dt = await pds.get_source().get_raw()
            ds = UadpDataSetRaw(header, b"".join(data))
        elif self._cfg.DataSetFieldContentMask == DataSetFieldContentMask(0):
            data, status, dt = await pds.get_source().get_variant()
            ds = UadpDataSetVariant(header, data)
        else:
            status = DataSetFieldContentMask.StatusCode
            source = DataSetFieldContentMask.SourceTimestamp
            server = DataSetFieldContentMask.ServerTimestamp
            data = await pds.get_source().get_value(status, server, source)
            ds = UadpDataSetDataValue(header, data)
            dt = DateTime.now(timezone.utc)
            status = StatusCode(UInt32(status_codes.StatusCodes.Good))
        if UadpDataSetMessageContentMask.Status in msg_cfg.DataSetMessageContentMask:
            # per OPC UA v1.05, 7.2.4.5.4, Header.Status is the high word of a StatusCode
            ds.Header.Status = UInt16((status.value >> 16) & 0xFFFF)
        if UadpDataSetMessageContentMask.Timestamp in msg_cfg.DataSetMessageContentMask:
            ds.Header.Timestamp = dt
        return ds
