from __future__ import annotations

import json
from copy import deepcopy

import pytest

from geo_seo_hub.control.planning import compile_task_plan, write_task_plan
from geo_seo_hub.control.execution import load_task_plan
from geo_seo_hub.router import route
from geo_seo_hub.validation import validate_artifact


def test_single_skill_plan_is_deterministic_and_valid():
    request = "帮我挖掘 AI 搜索问题"
    first = compile_task_plan(request, route(request))
    second = compile_task_plan(request, route(request))
    assert first == second
    assert first["status"] == "ready"
    assert [node["skill_id"] for node in first["nodes"]] == ["geo-discover"]
    assert first["required_inputs"] == ["geo-brief"]
    validate_artifact("task-plan", first)


def test_exact_workflow_compiles_dependencies_and_inputs():
    request = "先拓词，再诊断网站"
    plan = compile_task_plan(request, route(request))
    assert plan["workflow_id"] == "brand-baseline-lite"
    assert plan["status"] == "ready"
    assert [node["id"] for node in plan["nodes"]] == ["discover", "diagnose"]
    assert plan["nodes"][1]["depends_on"] == ["discover"]
    assert plan["required_inputs"] == ["diagnosis-brief", "geo-brief"]


def test_workflow_bindings_only_use_dependency_ancestors():
    request = "Discover questions, audit our site, then write an explainer"
    plan = compile_task_plan(request, route(request))
    content = next(node for node in plan["nodes"] if node["id"] == "content")
    assert content["depends_on"] == ["discover"]
    assert content["input_bindings"] == [
        {"artifact": "content-brief", "schema": None, "source": "request:content-brief"}
    ]


def test_strategy_loop_compiles_approval_and_external_evidence_gates():
    request = "Build a GEO strategy, then monitor AI visibility"
    plan = compile_task_plan(request, route(request))
    assert plan["status"] == "ready"
    assert [node["kind"] for node in plan["nodes"]] == [
        "skill",
        "approval",
        "external-publication",
        "external-observation",
        "skill",
    ]
    assert plan["nodes"][-1]["input_bindings"] == [
        {
            "artifact": "engine-observation-bundle",
            "schema": "engine-observation-bundle",
            "source": "node:observation:engine-observation-bundle",
        }
    ]
    assert plan["required_inputs"] == ["strategy-request"]


@pytest.mark.parametrize(
    ("request_text", "status"),
    [
        ("What is the weather?", "needs-clarification"),
        ("GEO 能帮我做什么", "needs-clarification"),
        ("brand audit and roadmap", "needs-clarification"),
        ("把内容发布到官网", "unavailable"),
    ],
)
def test_non_executable_decisions_do_not_create_nodes(request_text, status):
    plan = compile_task_plan(request_text, route(request_text))
    assert plan["status"] == status
    assert plan["nodes"] == []


def test_planner_fails_closed_for_non_active_skill_and_workflow():
    publish_route = route("把内容发布到官网")
    publish_route["decision"]["type"] = "single_skill"
    publish_route["skill_id"] = "geo-publish"
    publish_plan = compile_task_plan("把内容发布到官网", publish_route)
    assert publish_plan["status"] == "unavailable"
    assert publish_plan["nodes"] == []

    workflow_route = route("先拓词，再诊断网站")
    from geo_seo_hub.registry import load_registry

    registry = deepcopy(load_registry())
    workflow = next(item for item in registry["workflows"] if item["id"] == "brand-baseline-lite")
    workflow["status"] = "planned"
    workflow_plan = compile_task_plan("先拓词，再诊断网站", workflow_route, registry)
    assert workflow_plan["status"] == "unavailable"
    assert workflow_plan["nodes"] == []


def test_runtime_rejects_non_ancestor_plan_binding(tmp_path):
    request = "Discover questions, audit our site, then write an explainer"
    plan = compile_task_plan(request, route(request))
    content = next(node for node in plan["nodes"] if node["id"] == "content")
    content["input_bindings"][0] = {
        "artifact": "content-brief",
        "schema": None,
        "source": "node:diagnose:diagnosis",
    }
    plan["required_inputs"].remove("content-brief")
    from geo_seo_hub.control.planning import _digest

    plan["plan_digest"] = _digest({key: value for key, value in plan.items() if key != "plan_digest"})
    target = tmp_path / "task-plan.json"
    write_task_plan(target, plan)
    with pytest.raises(ValueError, match="dependency ancestor"):
        load_task_plan(target)


def test_task_plan_writer_is_atomic_and_refuses_overwrite(tmp_path):
    request = "query research"
    plan = compile_task_plan(request, route(request))
    target = tmp_path / "task-plan.json"
    assert write_task_plan(target, plan) == target
    assert json.loads(target.read_text(encoding="utf-8")) == plan
    with pytest.raises(ValueError, match="already exists"):
        write_task_plan(target, plan)
