"""Specification preparation, separated from attempt scheduling and verdict policy."""

from .caller_facts import CallerFacts, guard_assumptions, usage_problems
from .grounding import Grounded
from .spec import InputSpec, parse_spec, shape_unpacked, spec_problems


def prepare_spec(text: str, grounded: Grounded, facts: CallerFacts | None, *, require_property: bool
                 ) -> tuple[InputSpec | None, list[str], tuple[str, ...]]:
    assumed: tuple[str, ...] = ()
    try:
        spec = shape_unpacked(parse_spec(text), grounded)
        problems = spec_problems(spec, grounded, require_property=require_property)
        if not problems and facts is not None:
            assumed, contradicted = guard_assumptions(facts, spec, grounded)
            problems = usage_problems(spec, grounded, facts) + contradicted
    except ValueError as exc:
        return None, [str(exc)], ()
    return spec, problems, assumed
