"""Harness rewrites that exist only because ESBMC-Python refuses or mis-models a construct.

Each id is the transform the pipeline reports (``none_guards`` is split by construct);
capabilities.py probes the installed ESBMC and switches a rule off once ESBMC handles it."""

from __future__ import annotations

PERCENT_FORMAT = "compat_percent_format"
METHOD_ALIAS = "compat_method_alias"
BUILTIN_NAMED_METHODS = "builtin_named_methods_renamed"
PROPERTIES_AS_ATTRIBUTES = "properties_as_attributes"
PROJECT_DECORATORS = "project_decorators_removed"
CONDITIONAL_ASSIGNMENTS = "conditional_assignments_split"
NONE_ATTRIBUTE = "none_guards_attribute"
NONE_SUBSCRIPT = "none_guards_subscript"
NONE_CALL = "none_guards_call"
NONE_MEMBERSHIP = "none_guards_membership"
NONE_ORDERING = "none_guards_ordering"
NONE_ARITHMETIC = "none_guards_arithmetic"

NONE_GUARD_KINDS = frozenset({NONE_ATTRIBUTE, NONE_SUBSCRIPT, NONE_CALL, NONE_MEMBERSHIP, NONE_ORDERING,
                              NONE_ARITHMETIC})
ALL_RULES = frozenset({PERCENT_FORMAT, METHOD_ALIAS, BUILTIN_NAMED_METHODS, PROPERTIES_AS_ATTRIBUTES,
                       PROJECT_DECORATORS, CONDITIONAL_ASSIGNMENTS, *NONE_GUARD_KINDS})
