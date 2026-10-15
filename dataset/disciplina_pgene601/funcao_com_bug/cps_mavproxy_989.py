class LogModule:
    def log_status(self, console=False):
        '''show download status'''
        if self.download_filename is None:
            print("No download")
            return
        dt = time.time() - self.download_start
        speed = os.path.getsize(self.download_filename) / (1000.0 * dt)
        m = self.entries.get(self.download_lognum, None)
        file_size = os.path.getsize(self.download_filename)
        if m is None:
            size = 0
            pct = 0
        else:
            size = m.size
            pct = (100.0*file_size)/size
        highest = 0
        if len(self.download_set):
            highest = max(self.download_set)
        diff = set(range(highest)).difference(self.download_set)
        status = "Downloading %s - %u/%u bytes %.1f%% %.1f kbyte/s (%u retries %u missing)" % (self.download_filename,
                                                                                            os.path.getsize(self.download_filename),
                                                                                        size,
                                                                                        pct,
                                                                                        speed,
                                                                                        self.retries,
                                                                                            len(diff))
        if console:
            self.console.set_status('LogDownload', status, row=4)
        else:
            print(status)
