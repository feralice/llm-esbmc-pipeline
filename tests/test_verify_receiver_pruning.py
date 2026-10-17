from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import BugHypothesis

CONTEXT_MANAGER = '''class Downloader:
    def __init__(self, params):
        self.params = params

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cookiejar.save()

    def pick(self, formats):
        return formats[self.params]
'''


def _module(source, function, expression):
    grounded = ground(BugHypothesis("d.py", function, expression), source)
    assert isinstance(grounded, Grounded), grounded
    return grounded


def test_an_unreached_context_manager_leaves_when_nothing_uses_with():
    # bip_youtube_dl_30: __exit__ pulled in an untyped cookiejar.
    grounded = _module(CONTEXT_MANAGER, "Downloader.pick", "formats[self.params]")
    assert "__exit__" not in grounded.module and "cookiejar" not in grounded.module
    assert any(t.startswith("special_methods_removed:__enter__,__exit__") for t in grounded.transforms)


def test_a_with_statement_keeps_the_context_manager():
    source = CONTEXT_MANAGER.replace("        return formats[self.params]",
                                     "        with self:\n            return formats[self.params]")
    grounded = _module(source, "Downloader.pick", "formats[self.params]")
    assert "__exit__" in grounded.module


def test_an_unreached_numpy_protocol_leaves_without_numpy():
    # bip_pandas_33: __array_ufunc__ used **kwargs, which ESBMC refuses.
    source = '''class IntegerArray:
    def __init__(self, data):
        self._data = data

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        return ufunc(*inputs, **kwargs)

    def first(self):
        return self._data[0]
'''
    grounded = _module(source, "IntegerArray.first", "self._data[0]")
    assert "__array_ufunc__" not in grounded.module


def test_other_special_methods_stay():
    source = '''class Box:
    def __init__(self, items):
        self.items = items

    def __len__(self):
        return len(self.items)

    def first(self):
        return self.items[0]
'''
    assert "__len__" in _module(source, "Box.first", "self.items[0]").module


def test_a_method_a_kept_special_method_calls_stays():
    # ip_real_14: __getitem__ was kept but _empty_batch, which it unpacks, was removed.
    source = '''class Batches:
    def __init__(self, n, stride):
        self.n = n
        self.stride = stride

    def __getitem__(self, i):
        samples, targets = self._empty_batch(i)
        return samples

    def _empty_batch(self, i):
        return [i], [i]

    def __len__(self):
        return self.n // self.stride
'''
    grounded = _module(source, "Batches.__len__", "self.n // self.stride")
    assert "__getitem__" in grounded.module
    assert "def _empty_batch" in grounded.module


FRAME = '''class Frame:
    _internal_names_set = set(["index", "columns", "a_very_long_name_19"])
    _AXIS_ALIASES = {"rows": 0}
    _lookup = "index"
    hist = None

    def __init__(self, axis):
        self.axis = axis

    def axis_number(self):
        return self._AXIS_ALIASES.get(self.axis, getattr(self, "_lookup"))
'''


def test_class_attributes_nothing_reads_leave_the_receiver():
    # bip_pandas_133: an unused set of long strings killed every path at --unwind 5.
    grounded = _module(FRAME, "Frame.axis_number", 'self._AXIS_ALIASES.get(self.axis, getattr(self, "_lookup"))')
    assert "_internal_names_set" not in grounded.module and "hist" not in grounded.module
    assert "_AXIS_ALIASES" in grounded.module
    assert '_lookup = "index"' in grounded.module  # read by name through getattr
    assert any(t == "unused_class_attributes_removed:_internal_names_set,hist" for t in grounded.transforms)


def test_a_class_attribute_built_by_a_call_stays():
    source = FRAME.replace('    hist = None\n', '    hist = register(None)\n')
    grounded = _module(source, "Frame.axis_number", 'self._AXIS_ALIASES.get(self.axis, getattr(self, "_lookup"))')
    assert "hist = register(None)" in grounded.module


def test_a_special_method_a_kept_one_calls_stays():
    # Review C3: __eq__ calls __getstate__, which reaches the ZeroDivisionError.
    source = '''class Key:
    def __init__(self, k):
        self.k = k

    def __getstate__(self):
        return self._key()

    def _key(self):
        return 10 // self.k

    def __eq__(self, other):
        return self.__getstate__() == other

    def same(self, other):
        return self == other
'''
    grounded = _module(source, "Key.same", "self == other")
    assert "def __getstate__" in grounded.module and "def _key" in grounded.module


def test_dataclass_fields_and_enum_members_stay():
    # Review I4: removing fields changes the constructor; removing members breaks Color(2).
    dataclass = '''from dataclasses import dataclass


@dataclass
class P:
    x: int = 0
    y: int = 1

    @classmethod
    def make(cls, a):
        return cls(a, 10 // a)
'''
    assert "y: int = 1" in _module(dataclass, "P.make", "10 // a").module
    enum = '''from enum import Enum


class Color(Enum):
    RED = 1
    BLUE = 2

    def other(self, n):
        return Color(n)
'''
    assert "BLUE = 2" in _module(enum, "Color.other", "Color(n)").module


def test_a_keyword_argument_name_counts_as_a_read():
    source = FRAME.replace('    hist = None\n', '    hist = None\n\n    def plot(self):\n        return draw(hist=self.axis)\n')
    grounded = _module(source, "Frame.axis_number", 'self._AXIS_ALIASES.get(self.axis, getattr(self, "_lookup"))')
    assert "hist = None" in grounded.module


def test_init_callees_stay_when_the_real_init_runs():
    # Review I8: a classmethod entry keeps __init__, so what it calls must stay.
    source = '''class Conf:
    def __init__(self):
        self._setup()

    def _setup(self):
        self.v = 1

    @classmethod
    def build(cls, n):
        return cls().v // n
'''
    assert "def _setup" in _module(source, "Conf.build", "cls().v // n").module
