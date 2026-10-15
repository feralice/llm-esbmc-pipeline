def _dump_signals(database: InternalDatabase, sort_signals: Callable[[list[Signal]], list[Signal]] | None) -> str:
    signal_dumps = []
    # SYM requires unique signals
    generated_signals = set()
    for message in database.messages:
        if sort_signals:
            signals = sort_signals(message.signals)
        else:
            signals = message.signals
        for signal in signals:
            if signal.name not in generated_signals:
                generated_signals.add(signal.name)
                signal_dumps.append(_dump_signal(signal))

    if signals:
        return '{SIGNALS}\n' + '\n'.join(signal_dumps)
    else:
        return ''
