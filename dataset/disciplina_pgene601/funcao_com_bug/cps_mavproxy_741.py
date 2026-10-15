class LogModule:
    def log_status(self, console=False):
        '''show download status'''
        if self.download_filename is None:
            print("No download")
            return
        dt = time.time() - self.download_start
        speed = os.path.getsize(self.download_filename) / (1000.0 * dt)
        m = self.entries.get(self.download_lognum, None)
        if m is None:
            size = 0
        else:
            size = m.size
        highest = max(self.download_set)
        diff = set(range(highest)).difference(self.download_set)

        status = "Downloading %s - %u/%u bytes %.1f kbyte/s (%u retries %u missing)" % (self.download_filename,
                                                                                        os.path.getsize(self.download_filename),
                                                                                        size,
                                                                                        speed,
                                                                                        self.retries,
                                                                                            len(diff))
        if console:
            self.console.set_status('LogDownload', status, row=4)
        else:
            print(status)
