"""Static fixtures inspired by aws-samples/sam-python-crud-sample, f91982d24775dce644283b9ae33deb78e49c49fc."""
import json
from pathlib import Path

import pytest

from research_pipeline.scan.callgraph import build_callgraph


TEMPLATE = """Transform: AWS::Serverless-2016-10-31
Resources:
  UpdateActivity:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/update_activity/
      Handler: app.lambda_handler
      Events:
        Update:
          Type: Api
          Properties:
            Path: /activities/{id}
            Method: put
  DeleteActivity:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/delete_activity/
      Handler: app.lambda_handler
      Events:
        Delete:
          Type: Api
          Properties:
            Path: /activities/{id}/{date}
            Method: delete
"""


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repo"
    for kind in ("update", "delete"):
        folder = root / "src" / f"{kind}_activity"
        folder.mkdir(parents=True)
        (folder / "app.py").write_text("def lambda_handler(message, context):\n    return message['httpMethod']\n")
    (root / "template.yaml").write_text(TEMPLATE)
    (root / "README.md").write_text("Update instructions: src/update_activity/\nDelete instructions: src/delete_activity/\n")
    (root / "events").mkdir()
    (root / "events/update_activity_event.json").write_text('{"httpMethod": "PUT", "body": "{}"}')
    (root / "events/delete_activity_event.json").write_text('{"httpMethod": "DELETE", "pathParameters": {"id": "x"}}')
    return root


def collect(root):
    from research_pipeline.scan.repository_context import collect_repository_context
    return collect_repository_context(root, build_callgraph(root))


def test_sam_association_distinguishes_identically_named_handlers(repository):
    from research_pipeline.scan.repository_context import render_repository_context
    snapshot = collect(repository)
    update = snapshot.by_function["src.update_activity.app:lambda_handler"]
    delete = snapshot.by_function["src.delete_activity.app:lambda_handler"]
    assert update.status == delete.status == "matched"
    first, second = render_repository_context(update), render_repository_context(delete)
    assert "Method: put" in first and "Method: delete" not in first
    assert "Method: delete" in second and "Method: put" not in second
    assert "README.md:1" in first and "Update instructions" in first
    assert "Delete instructions" not in first
    assert "events/update_activity_event.json" in first
    assert "events/delete_activity_event.json" not in first
    assert "httpMethod" in first and "not universal" in first
    assert "UNTRUSTED_REPOSITORY_CONTEXT" in first
    config = next(e for e in update.evidence if e.kind == "integration_config")
    assert config.path == "template.yaml" and config.start_line == 4
    assert snapshot.to_dict()["digest"] == snapshot.digest


@pytest.mark.parametrize("replacement", ["!Ref ExternalCode", "../outside/", "s3://bucket/code", "src/missing/"])
def test_unresolved_or_external_codeuri_does_not_claim_framework_contract(repository, replacement):
    p = repository / "template.yaml"
    p.write_text(TEMPLATE.replace("src/update_activity/", replacement))
    context = collect(repository).by_function["src.update_activity.app:lambda_handler"]
    assert context.status == "unresolved"
    assert not any(e.path.startswith("https://docs.aws.amazon.com") for e in context.evidence)
    assert context.diagnostics


def test_custom_api_and_multiple_sources_remain_unresolved(repository):
    p = repository / "template.yaml"
    p.write_text(TEMPLATE.replace("Method: put", "Method: put\n            RestApiId: !Ref CustomApi"))
    context = collect(repository).by_function["src.update_activity.app:lambda_handler"]
    assert context.status == "unresolved"
    assert not any(e.path.startswith("https://docs.aws.amazon.com") for e in context.evidence)
    p.write_text(TEMPLATE.replace("        Update:\n", "        Other:\n          Type: S3\n          Properties: {}\n        Update:\n"))
    context = collect(repository).by_function["src.update_activity.app:lambda_handler"]
    assert context.status == "unresolved"


def test_example_presence_is_not_a_contract_without_sam_binding(repository):
    (repository / "template.yaml").unlink()
    context = collect(repository).by_function["src.update_activity.app:lambda_handler"]
    assert context.status == "not_found"
    assert not any(e.path.startswith("https://docs.aws.amazon.com") for e in context.evidence)


@pytest.mark.parametrize("content", ["Resources: [", "x: &x {again: *x}", "x: " + "[" * 45 + "0" + "]" * 45])
def test_invalid_cyclic_or_deep_yaml_is_diagnostic_not_a_silent_contract(repository, content):
    (repository / "template.yaml").write_text(content)
    snapshot = collect(repository)
    assert snapshot.diagnostics
    assert snapshot.by_function["src.update_activity.app:lambda_handler"].status == "unresolved"


def test_does_not_follow_source_or_documentation_symlinks(repository, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("EXTERNAL SECRET DO NOT READ")
    (repository / "README.md").unlink()
    (repository / "README.md").symlink_to(outside)
    original = collect(repository)
    assert "EXTERNAL SECRET" not in json.dumps(original.to_dict())
    assert any("symlink" in d for d in original.diagnostics)
    source = repository / "src/update_activity/app.py"
    source.unlink()
    source.symlink_to(repository / "src/delete_activity/app.py")
    context = collect(repository).by_function["src.update_activity.app:lambda_handler"]
    assert context.status == "unresolved"


def test_inventory_and_digest_change_with_sources_and_new_documents(repository):
    first = collect(repository)
    assert collect(repository).digest == first.digest
    (repository / "events/update_activity_event.json").write_text('{"httpMethod": "PUT", "body": "changed"}')
    second = collect(repository)
    assert first.digest != second.digest
    (repository / "docs").mkdir()
    (repository / "docs/new.md").write_text("Not a function match, but a changed consulted source.")
    assert collect(repository).digest != second.digest


def test_large_files_and_excerpts_are_bounded_and_reported(repository):
    (repository / "README.md").write_text("src/update_activity/ " * 9000)
    snapshot = collect(repository)
    assert any("size" in d for d in snapshot.diagnostics)
    assert all(sum(len(e.text) for e in c.evidence) <= 4800 for c in snapshot.by_function.values())


def test_missing_yaml_parser_fails_before_calling_a_model(repository, monkeypatch):
    import builtins
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("absent for test")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(ValueError, match="scan-context"):
        collect(repository)


class RecordingAnalyzer:
    model = "fixed"
    telemetry_events = []

    def __init__(self):
        self.units = []

    def analyze(self, unit):
        from research_pipeline.models import Finding
        self.units.append(unit)
        return [Finding("candidate", "llm", "suspected_bug", "", "", "missing method", [], True, "low",
                        {"expression": "message['httpMethod']", "violated_property": "KeyError"})]


def recording_verify(received):
    def verify(hypotheses, *, on_result, completed, **kwargs):
        received.append(kwargs)
        results = []
        for index, h in enumerate(hypotheses):
            context = kwargs.get("repository_context")
            data = completed.get(index) or {"hypothesis": h.to_dict(), "verdict": "LLM_ONLY", "reason": "fixture",
                                            "attempts": [{"spec": "fixture"}], "llm_calls": 1,
                                            "spec_context": {"repository_evidence_chars": len(context(h))} if context else {}}
            on_result(index, data)
            results.append(data)
        return results
    return verify


def test_opt_in_context_reaches_detection_and_verification_and_is_saved(repository, tmp_path):
    from research_pipeline.scan.pipeline import execute_scan, plan_scan
    out = tmp_path / "evidence"
    plan = plan_scan(repository, out, repository_context="evidence")
    assert (out / "scan_repository_context.json").exists()
    analyzer, received = RecordingAnalyzer(), []
    report = execute_scan(plan, analyzer=analyzer, spec_llm=None, verify=recording_verify(received))
    by_file = {Path(u.path).parent.name: u for u in analyzer.units}
    assert "Method: put" in by_file["update_activity"].caller_context
    assert "Method: delete" not in by_file["update_activity"].caller_context
    provider = received[0]["repository_context"]
    from research_pipeline.verify.hypothesis import BugHypothesis
    h = BugHypothesis(str(repository / "src/update_activity/app.py"), "lambda_handler", "message['httpMethod']")
    assert "Method: put" in provider(h)
    assert report["repository_context"]["digest"] == plan.repository_context.digest
    assert report["verification"]["by_verdict"]["LLM_ONLY"] == 2
    audit = json.loads((out / "scan_repository_context.json").read_text())
    assert len(audit["sent_to_detection"]) == 2
    assert len(audit["sent_to_specification"]) == 2


def test_disabled_context_preserves_prompt_and_fingerprints(repository, tmp_path):
    from research_pipeline.scan.pipeline import _detection_fingerprint, execute_scan, plan_scan
    from research_pipeline.llm.prompts import build_user_prompt
    first = plan_scan(repository, tmp_path / "default")
    second = plan_scan(repository, tmp_path / "off", repository_context="off")
    assert _detection_fingerprint(first, "fixed") == _detection_fingerprint(second, "fixed")
    assert [build_user_prompt(t.unit) for t in first.targets] == [build_user_prompt(t.unit) for t in second.targets]
    analyzer, received = RecordingAnalyzer(), []
    report = execute_scan(second, analyzer=analyzer, spec_llm=None, verify=recording_verify(received), bound=20)
    assert "repository_context" not in report
    assert "repository_context" not in received[0]
    assert not (tmp_path / "off/scan_repository_context.json").exists()


def test_enabled_resume_rejects_changed_source_context(repository, tmp_path):
    from research_pipeline.scan.pipeline import _detection_fingerprint, _verify_fingerprint, execute_scan, plan_scan
    out = tmp_path / "enabled"
    plan = plan_scan(repository, out, repository_context="evidence")
    execute_scan(plan, analyzer=RecordingAnalyzer(), spec_llm=None, verify=recording_verify([]))
    before = _verify_fingerprint(verify_config={"repository_context": plan.repository_context})
    (repository / "template.yaml").write_text(TEMPLATE.replace("Method: put", "Method: patch"))
    changed = plan_scan(repository, out, repository_context="evidence")
    assert _detection_fingerprint(plan, "fixed") != _detection_fingerprint(changed, "fixed")
    assert before != _verify_fingerprint(verify_config={"repository_context": changed.repository_context})
    with pytest.raises(ValueError, match="cannot resume"):
        execute_scan(changed, analyzer=RecordingAnalyzer(), spec_llm=None, verify=recording_verify([]), resume=True)


@pytest.mark.parametrize("mode", ["hybrid", "benchmark"])
def test_context_option_rejected_outside_scan_before_creating_output(repository, tmp_path, monkeypatch, mode):
    import main
    import sys
    out = tmp_path / "forbidden"
    monkeypatch.setattr(sys, "argv", ["main.py", "--mode", mode, "--input", str(repository),
                                     "--output-dir", str(out), "--scan-repository-context", "evidence"])
    assert main.main() == 1
    assert not out.exists()


def test_engine_receives_attributed_evidence_without_inventing_assumptions(repository, tmp_path):
    from research_pipeline.verify.hypothesis import BugHypothesis
    from research_pipeline.verify.llm_client import SynthResult
    from research_pipeline.verify.loop import verify_hypothesis
    class InvalidSpec:
        model = "fixed"
        def __init__(self):
            self.prompts = []
        def complete(self, system, user, **kwargs):
            self.prompts.append(user)
            return SynthResult(harness="invalid JSON", raw_response="", model=self.model, telemetry={})
    llm = InvalidSpec()
    file = repository / "src/update_activity/app.py"
    h = BugHypothesis(str(file), "lambda_handler", "message['httpMethod']")
    context = collect(repository)(h)
    result = verify_hypothesis(h, llm=llm, source=file.read_text(), esbmc_command=None, bound=5,
                              timeout_seconds=1, work_dir=tmp_path / "programs", max_repairs=0,
                              repository_context=context)
    assert result.verdict == "SPEC_FAILED"
    assert context in llm.prompts[0]
    assert "__ESBMC_assume" not in context
    assert result.spec_context["repository_evidence_chars"] == len(context)


def test_agent_receives_same_evidence_with_no_duplicate_docs(repository, tmp_path):
    from research_pipeline.verify.agent_scan import agent_verifier
    from research_pipeline.verify.hypothesis import BugHypothesis
    prompts = []
    def run_agent(prompt, work_dir, **kwargs):
        prompts.append(prompt)
        return {"error": "fixture refuses execution"}
    provider = collect(repository)
    verify = agent_verifier(run_agent, esbmc_command=None, bound=5, timeout_seconds=1, agent_timeout=1,
                            documentation_root=repository, repository_context=provider)
    h = BugHypothesis(str(repository / "src/update_activity/app.py"), "lambda_handler", "message['httpMethod']")
    from unittest.mock import patch
    def capture(hypothesis, **kwargs):
        prompts.append(kwargs["documentation"])
        return {"hypothesis": hypothesis.to_dict(), "verdict": "AGENT_FAILED", "reason": "fixture"}
    with patch("research_pipeline.verify.agent_scan.run_agent_arm", capture):
        verify([h], llm=None, output_dir=tmp_path, completed={}, on_result=lambda *args: None)
    assert prompts == [provider(h)]
    assert provider.config_label in verify.label


def test_globals_codeuri_binds_the_inherited_source_not_a_root_namesake(repository):
    (repository / "app.py").write_text("def lambda_handler(message, context):\n    return message['httpMethod']\n")
    template = TEMPLATE.replace("Resources:\n", "Globals:\n  Function:\n    CodeUri: src/update_activity/\nResources:\n")
    (repository / "template.yaml").write_text(template.replace("      CodeUri: src/update_activity/\n", "", 1))
    snapshot = collect(repository)
    inherited = snapshot.by_function["src.update_activity.app:lambda_handler"]
    assert inherited.status == "matched"
    assert snapshot.by_function["app:lambda_handler"].status != "matched"
    from research_pipeline.scan.repository_context import render_repository_context
    assert "CodeUri: src/update_activity/" in render_repository_context(inherited)


@pytest.mark.parametrize("inherited", [False, True])
def test_function_url_additional_entrypoint_never_claims_a_unique_proxy_contract(repository, inherited):
    text = TEMPLATE
    if inherited:
        text = text.replace("Resources:\n", "Globals:\n  Function:\n    FunctionUrlConfig:\n      AuthType: NONE\nResources:\n")
    else:
        text = text.replace("      CodeUri: src/update_activity/", "      FunctionUrlConfig:\n        AuthType: NONE\n      CodeUri: src/update_activity/")
    (repository / "template.yaml").write_text(text)
    context = collect(repository).by_function["src.update_activity.app:lambda_handler"]
    assert context.status == "unresolved"
    assert context.diagnostics
    assert not any(e.path.startswith("https://docs.aws.amazon.com") for e in context.evidence)


def test_globals_custom_api_definition_does_not_claim_default_proxy_contract(repository):
    (repository / "template.yaml").write_text(TEMPLATE.replace("Resources:\n", "Globals:\n  Api:\n    DefinitionUri: s3://bucket/custom.yaml\nResources:\n"))
    context = collect(repository).by_function["src.update_activity.app:lambda_handler"]
    assert context.status == "unresolved"
    assert not any(e.path.startswith("https://docs.aws.amazon.com") for e in context.evidence)


@pytest.mark.parametrize("package_root", [True, False])
def test_provider_uses_graph_identity_for_package_roots_and_init_modules(repository, package_root):
    from research_pipeline.verify.hypothesis import BugHypothesis
    if package_root:
        (repository / "__init__.py").write_text("")
        file = repository / "src/update_activity/app.py"
    else:
        package = repository / "mypackage"
        package.mkdir()
        file = package / "__init__.py"
        file.write_text("def lambda_handler(message, context):\n    return message['httpMethod']\n")
        (repository / "template.yaml").write_text(TEMPLATE.replace("CodeUri: src/update_activity/", "CodeUri: .").replace("Handler: app.lambda_handler", "Handler: mypackage.lambda_handler", 1))
    snapshot = collect(repository)
    assert "Method: put" in snapshot(BugHypothesis(str(file), "lambda_handler", "message['httpMethod']"))


def test_serialized_excerpt_budget_is_auditable_and_keeps_valid_metadata(repository):
    from research_pipeline.scan.repository_context import render_repository_context
    (repository / "README.md").write_text("src/update_activity/ " + "\\" * 2000)
    snapshot = collect(repository)
    context = snapshot.by_function["src.update_activity.app:lambda_handler"]
    block = render_repository_context(context)
    assert len(block) <= 4800
    assert context.truncated
    assert snapshot.to_dict()["functions"][context.key]["truncated"]
    payload = json.loads(block.split("\n", 2)[2].rsplit("\n", 1)[0])
    assert payload["truncated"]
    assert payload["diagnostics"]
