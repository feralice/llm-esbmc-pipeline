from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.spec import InputSpec, spec_problems


def _spec(source, expression):
    grounded = ground(BugHypothesis('x.py', 'read', expression), source)
    assert isinstance(grounded, Grounded)
    return spec_problems(InputSpec({}, {}, (), {'ctypes.create_string_buffer': 'bytes'}), grounded)


def test_buffer_stub_bytes_cannot_supply_raw():
    source = 'import ctypes\ndef read():\n    buf = ctypes.create_string_buffer(2)\n    return buf.raw\n'
    assert any('create_string_buffer' in p and 'raw' in p for p in _spec(source, 'buf.raw'))


def test_unrelated_raw_attribute_is_not_rejected():
    source = ('import ctypes\ndef read():\n    buf = ctypes.create_string_buffer(2)\n'
              '    other = object()\n    return other.raw\n')
    assert not any('create_string_buffer' in p and 'raw' in p for p in _spec(source, 'other.raw'))
