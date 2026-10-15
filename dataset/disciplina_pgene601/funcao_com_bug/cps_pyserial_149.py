class FramedPacket:
    def data_received(self, data):
        """Find data enclosed in START/STOP, call handle_packet"""
        for byte in serial.iterbytes(data):
            if byte == self.START:
                self.in_packet = True
            elif byte == self.STOP:
                self.in_packet = False
                self.handle_packet(self.packet)
                del self.packet[:]
            elif self.in_packet:
                self.packet.append(byte)
            else:
                self.handle_out_of_packet_data(byte)
