class TimeseriesGenerator:
    def __len__(self):
        return int(np.ceil(
            (self.end_index - self.start_index) /
            (self.batch_size * self.stride)))
