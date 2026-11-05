# Regra none_guards_attribute. Origem: tm_real_10 (0ddf1474a20f): método chamado no fim de uma cadeia de campos, o último None.
from typing import Optional


class Collector:
    def latest(self) -> int:
        return 1


class State:
    def __init__(self) -> None:
        collector: Optional[Collector] = None
        if nondet_bool():
            collector = Collector()
        self.collector: Optional[Collector] = collector


class Scheduler:
    def __init__(self) -> None:
        self.state: State = State()


class Handler:
    def __init__(self) -> None:
        self.scheduler: Scheduler = Scheduler()


def get(handler: Handler) -> None:
    value = handler.scheduler.state.collector.latest()


get(Handler())
