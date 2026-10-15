class ReadDeviceInformationResponse:
    @classmethod
    def calculateRtuFrameSize(cls, buffer):
        """Calculate the size of the message

        :param buffer: A buffer containing the data that have been received.
        :returns: The number of bytes in the response.
        """
        size = 8  # skip the header information
        count = int(buffer[7])

        while count > 0:
            _, object_length = struct.unpack(">BB", buffer[size : size + 2])
            size += object_length + 2
            count -= 1
        return size + 2
