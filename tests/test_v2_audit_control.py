import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("v2_audit_control",
                                               Path(__file__).resolve().parents[1] / "scripts/v2_audit_control.py")
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def test_a_confirmation_falls_only_when_the_fixed_version_raises_the_same_exception():
    assert audit.control_outcome("CONFIRMED", "not_reproduced", "ZeroDivisionError", "") == audit.HOLDS
    assert audit.control_outcome("CONFIRMED", "reproduced", "IndexError", "IndexError") == audit.BREAKS_FIXED


def test_another_exception_in_the_fixed_version_is_a_changed_behaviour():
    # dz_real_03: the fix raises CroniterBadCronError for the same input (NameError in the harness).
    assert audit.control_outcome("CONFIRMED", "reproduced", "ZeroDivisionError", "NameError") == audit.CHANGED


def test_no_control_and_lost_confirmations():
    assert audit.control_outcome("CONFIRMED", "unavailable", "KeyError", "") == audit.NO_CONTROL
    assert audit.control_outcome("CONFIRMED", None, "KeyError", None) == audit.NO_CONTROL
    assert audit.control_outcome("UNVALIDATED", "not_reproduced", "", "") == audit.LOST
