class FTPModule:
    def __init__(self, mpstate):
        super(FTPModule, self).__init__(mpstate, "ftp", public=True)
        self.add_command('ftp', self.cmd_ftp, "file transfer",
                         ["<list|get|rm|rmdir|rename|mkdir|crc|cancel|status>",
                          "set (FTPSETTING)",
                          "put (FILENAME) (FILENAME)"])
        self.ftp_settings = mp_settings.MPSettings(
            [('debug', int, 0),
             ('pkt_loss_tx', int, 0),
             ('pkt_loss_rx', int, 0),
             ('max_backlog', int, 5),
             ('burst_read_size', int, 110),
             ('write_size', int, 110),
             ('write_qsize', int, 5),
             ('retry_time', float, 0.5)])
        self.add_completion_function('(FTPSETTING)',
                                     self.ftp_settings.completion)
        self.seq = 0
        self.session = 0
        self.network = 0
        self.last_op = None
        self.fh = None
        self.filename = None
        self.callback = None
        self.callback_progress = None
        self.put_callback = None
        self.put_callback_progress = None
        self.total_size = 0
        self.read_gaps = []
        self.read_gap_times = {}
        self.last_gap_send = None
        self.read_retries = 0
        self.read_total = 0
        self.duplicates = 0
        self.last_read = None
        self.last_burst_read = None
        self.op_start = None
        self.dir_offset = 0
        self.last_op_time = time.time()
        self.rtt = 0.5
        self.reached_eof = False
        self.backlog = 0
        self.burst_size = self.ftp_settings.burst_read_size
        self.write_list = None
        self.write_block_size = 0
        self.write_acks = 0
        self.write_total = 0
        self.write_file_size = 0
        self.write_idx = 0
        self.write_recv_idx = -1
        self.write_pending = 0
        self.write_last_send = None

    def check_read_send(self):
        '''see if we should send another gap read'''
        if len(self.read_gaps) == 0:
            return
        g = self.read_gaps[0]
        now = time.time()
        dt = now - self.read_gap_times[g]
        if not self.reached_eof:
            # send gap reads once
            for g in self.read_gap_times.keys():
                if self.read_gap_times[g] == 0:
                    self.send_gap_read(g)
            return
        if self.read_gap_times[g] > 0 and dt > self.ftp_settings.retry_time:
            if self.backlog > 0:
                self.backlog -= 1
            self.read_gap_times[g] = 0

        if self.read_gap_times[g] != 0:
            # still pending
            return
        if not self.reached_eof and self.backlog >= self.ftp_settings.max_backlog:
            # don't fill queue too far until we have got past the burst
            return
        if now - self.last_gap_send < 0.05:
            # don't send too fast
            return
        self.send_gap_read(g)
