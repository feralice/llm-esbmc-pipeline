from research_pipeline.verify.compat import rewrite_compat
from research_pipeline.verify.rules import ALL_RULES, IO_ERROR_ALIAS


def test_io_error_becomes_os_error_and_is_reported():
    source = "def f(x):\n    try:\n        raise IOError(x)\n    except EnvironmentError:\n        return 0\n"
    rewritten, transforms = rewrite_compat(source)
    assert "IOError" not in rewritten and "EnvironmentError" not in rewritten
    assert rewritten.count("OSError") == 2
    assert any(t.startswith(IO_ERROR_ALIAS) for t in transforms)


def test_a_program_that_binds_the_name_itself_is_left_alone():
    source = "IOError = 3\n\ndef f():\n    return IOError\n"
    rewritten, _ = rewrite_compat(source)
    assert rewritten == source


def test_the_rule_can_be_switched_off():
    source = "def f():\n    raise IOError('x')\n"
    rewritten, _ = rewrite_compat(source, rules=ALL_RULES - {IO_ERROR_ALIAS})
    assert rewritten == source
