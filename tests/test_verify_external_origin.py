from research_pipeline.verify.external_origin import stubbed_response_origin
from research_pipeline.verify.grounding import ground
from research_pipeline.verify.hypothesis import BugHypothesis

SOURCE = '''
import json

def get_secret_dict(service_client, arn, stage):
    secret = service_client.get_secret_value(SecretId=arn, VersionStage=stage)
    plaintext = secret['SecretString']
    return json.loads(plaintext)

def read_options(options):
    return options['catalog']
'''


def _grounded(function, expression, line):
    h = BugHypothesis(file="m.py", function=function, suspect_expression=expression, line=line)
    grounded = ground(h, SOURCE)
    assert not hasattr(grounded, "reason"), grounded
    return grounded


def test_subscript_of_a_stubbed_library_response_is_reported_with_its_call():
    grounded = _grounded("get_secret_dict", "secret['SecretString']", 6)
    assert stubbed_response_origin(SOURCE, grounded, "KeyError") == "service_client.get_secret_value"


def test_subscript_of_a_parameter_is_the_projects_own_code():
    grounded = _grounded("read_options", "options['catalog']", 10)
    assert stubbed_response_origin(SOURCE, grounded, "KeyError") == ""


def test_other_exceptions_are_not_reclassified():
    grounded = _grounded("get_secret_dict", "secret['SecretString']", 6)
    assert stubbed_response_origin(SOURCE, grounded, "TypeError") == ""


def test_index_errors_stay_confirmed_because_only_dict_keys_are_invented_by_the_stub():
    grounded = _grounded("get_secret_dict", "secret['SecretString']", 6)
    assert stubbed_response_origin(SOURCE, grounded, "IndexError") == ""
