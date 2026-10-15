class HistoryDict:
    async def read_node_history(self, node_id, start, end, nb_values):
        cont = None
        if node_id not in self._datachanges:
            logger.warning("Error attempt to read history for a node which is not historized")
            return [], cont
        else:
            if start is None:
                start = ua.get_win_epoch()
            if end is None:
                end = ua.get_win_epoch()
            if start == ua.get_win_epoch():
                results = [
                    dv
                    for dv in reversed(self._datachanges[node_id])
                    if start <= dv.SourceTimestamp
                ]
            elif end == ua.get_win_epoch():
                results = [dv for dv in self._datachanges[node_id] if start <= dv.SourceTimestamp]
            elif start > end:
                results = [
                    dv
                    for dv in reversed(self._datachanges[node_id])
                    if end <= dv.SourceTimestamp <= start
                ]

            else:
                results = [
                    dv for dv in self._datachanges[node_id] if start <= dv.SourceTimestamp <= end
                ]

            if nb_values and len(results) > nb_values:
                results = results[:nb_values]

            if len(results) > self.max_history_data_response_size:
                cont = results[self.max_history_data_response_size + 1].SourceTimestamp
                results = results[:self.max_history_data_response_size]
            return results, cont

    async def read_event_history(self, source_id, start, end, nb_values, evfilter):
        cont = None
        if source_id not in self._events:
            logger.warning(
                "Error attempt to read event history for node %s which does not historize events",
                source_id,
            )
            return [], cont
        else:
            if start is None:
                start = ua.get_win_epoch()
            if end is None:
                end = ua.get_win_epoch()
            if start == ua.get_win_epoch():
                results = [ev for ev in reversed(self._events[source_id]) if start <= ev.Time]
            elif end == ua.get_win_epoch():
                results = [ev for ev in self._events[source_id] if start <= ev.Time]
            elif start > end:
                results = [
                    ev for ev in reversed(self._events[source_id]) if end <= ev.Time <= start
                ]

            else:
                results = [ev for ev in self._events[source_id] if start <= ev.Time <= end]

            if nb_values and len(results) > nb_values:
                results = results[:nb_values]

            if len(results) > self.max_history_data_response_size:
                cont = results[self.max_history_data_response_size + 1].Time
                results = results[:self.max_history_data_response_size]
            return results, cont
