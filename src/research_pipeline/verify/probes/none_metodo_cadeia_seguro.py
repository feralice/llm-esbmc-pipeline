# Regra none_guards_attribute. Gêmeo seguro de none_metodo_cadeia: o ramo não None assumido.
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
    __ESBMC_assume(handler.scheduler.state.collector is not None)
    value = handler.scheduler.state.collector.latest()


get(Handler())
