"""Synthetic response fixtures test the evaluator, not any model's accuracy."""
from copy import deepcopy
from pathlib import Path
import json
import os
import socket
import sys
from types import SimpleNamespace

import pytest
from hypothesis import given, settings, strategies as st
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from argbridge import Compiled, canonical
from evals.realworld import harness as h, manual
from evals.realworld.compact import compact_schema, expand_local_refs

pytestmark = pytest.mark.evaluation

def test_prepare_cannot_overwrite_existing_artifacts(tmp_path,monkeypatch):
    monkeypatch.setattr(sys,"argv",["harness","prepare","--output",str(tmp_path)])
    previous=h.ARTIFACTS
    try:
        with pytest.raises(SystemExit) as exc:
            h.main()
        assert exc.value.code==2
        assert list(tmp_path.iterdir())==[]
    finally:
        h.ARTIFACTS=previous

@pytest.fixture(autouse=True)
def forbid_inference_network(monkeypatch):
    def blocked(*a,**kw):
        raise AssertionError("Tests must not open network connections")
    monkeypatch.setattr(socket.socket,"connect",blocked)
    monkeypatch.setattr(socket,"create_connection",blocked)

@pytest.fixture(scope="module")
def data():
    workflows,scenarios,gold,policy=h.dataset()
    config=h.read(h.HERE/"config.json")
    specs=h.make_specs(workflows,config)
    import tiktoken
    encoding=tiktoken.encoding_for_model(config["model"])
    return workflows,scenarios,gold,policy,config,specs,encoding

def response(name,args,status="completed"):
    return {"status":status,"output":[{"type":"function_call","name":name,
            "arguments":args if isinstance(args,str) else json.dumps(args)}],
            "usage":{"input_tokens":500,"output_tokens":30,"input_tokens_details":{"cached_tokens":0}}}

def test_frozen_dataset_is_complete_and_gold_valid(data):
    workflows,scenarios,gold,*_=data
    assert len(scenarios)==56 and len(gold)==56
    assert set(s["id"] for s in scenarios)==set(gold)
    assert all("expected" not in s for s in scenarios)
    assert len(set(s["instruction"] for s in scenarios))==56
    for s in scenarios:
        e=gold[s["id"]]
        assert e["rationale"]
        if e["action"]=="apply_update":
            assert Draft202012Validator(workflows[s["workflow"]]["schema"]).is_valid(e["patch"])

def test_gold_never_leaks_into_request(data):
    workflows,scenarios,gold,policy,config,specs,_=data
    for s in scenarios:
        for method in config["methods"]:
            if "unsupported" in specs[s["workflow"]][method]: continue
            request=h.request_for(config,specs[s["workflow"]][method],workflows[s["workflow"]],s["instruction"],policy)
            assert request["input"]==s["instruction"]
            assert "rationale" not in request["instructions"]
    # All treatment arms see identical instruction, context and model settings.
    s=scenarios[0]
    requests=[h.request_for(config,specs[s["workflow"]][m],workflows[s["workflow"]],s["instruction"],policy) for m in config["methods"]]
    common=[{k:v for k,v in r.items() if k!="tools"} for r in requests]
    assert all(r==common[0] for r in common)

@pytest.mark.parametrize("method",["argbridge","argbridge_factored","manual_strict","original_nonstrict"])
def test_synthetic_reference_responses_score_correctly(data,method):
    workflows,scenarios,gold,_,_,specs,encoding=data
    for s in scenarios:
        e=gold[s["id"]]; w=s["workflow"]
        if e["action"]=="apply_update":
            args=h.reference_arguments(method,w,e["patch"],workflows[w]["schema"])
        else:
            args={"reason":e["rationale"]}
        observed=h.score(response(e["action"],args),{"workflow":w,"method":method},e,workflows[w],specs[w][method],encoding)
        assert observed["structural_valid"], (s["id"],observed)
        assert observed["semantic_correct"], (s["id"],observed)
        assert not observed["unsafe_accepted_mutation"]

def test_valid_shape_is_not_intent_correctness(data):
    workflows,_,gold,_,_,specs,encoding=data
    wrong=Compiled(workflows["flat"]["schema"]).encode({"name":None})
    observed=h.score(response("apply_update",wrong),{"workflow":"flat","method":"argbridge"},
                     gold["omission-01"],workflows["flat"],specs["flat"]["argbridge"],encoding)
    assert observed["structural_valid"] and not observed["semantic_correct"]
    assert observed["unsafe_accepted_mutation"]

@pytest.mark.parametrize("raw",['{"arguments":{},"arguments":{}}','{"arguments":NaN}','{"unexpected":1}'])
def test_invalid_raw_arguments_rejected(data,raw):
    workflows,_,gold,_,_,specs,encoding=data
    observed=h.score(response("apply_update",raw),{"workflow":"flat","method":"argbridge"},
                     gold["omission-01"],workflows["flat"],specs["flat"]["argbridge"],encoding)
    assert not observed["structural_valid"]
    assert not observed["semantic_correct"]

def test_empty_clarification_and_multiple_calls_fail(data):
    workflows,_,gold,_,_,specs,encoding=data
    job={"workflow":"flat","method":"argbridge"}
    r=h.score(response("request_clarification",{"reason":""}),job,gold["ambiguous-01"],workflows["flat"],specs["flat"]["argbridge"],encoding)
    assert r["structural_valid"] and not r["semantic_correct"]
    raw=response("request_clarification",{"reason":"Which field?"})
    raw["output"]*=2
    assert h.score(raw,job,gold["ambiguous-01"],workflows["flat"],specs["flat"]["argbridge"],encoding)["failure"]=="missing_or_multiple_calls"

def test_original_corpus_factoring_equivalence():
    for f in h.read(ROOT/"bench/fixtures/workflows.json"):
        c=Compiled(f["schema"]); compact=compact_schema(c.wire_schema)
        assert expand_local_refs(compact)==expand_local_refs(c.wire_schema)
        for value in f["valid"]:
            encoded=c.encode(value)
            assert Draft202012Validator(compact).is_valid(encoded)
            assert canonical(c.decode(encoded))==canonical(value)

@settings(max_examples=500,deadline=None,derandomize=True)
@given(st.fixed_dictionaries({},optional={"name":st.one_of(st.none(),st.text(max_size=15)),
                                          "enabled":st.booleans(),"quota":st.one_of(st.none(),st.integers(0,100))}))
def test_factored_presence_roundtrip(values):
    schema={"type":"object","properties":{"name":{"type":["string","null"]},"enabled":{"type":"boolean"},
            "quota":{"type":["integer","null"],"minimum":0}},"additionalProperties":False}
    c=Compiled(schema)
    wire=c.encode(values)
    assert Draft202012Validator(compact_schema(c.wire_schema)).is_valid(wire)
    assert c.decode(wire)==values

def test_manual_duplicate_and_conflicting_changes_rejected():
    with pytest.raises(ValueError):
        manual.decode("flat",{"changes":[{"field":"name","value":"A"},{"field":"name","value":None}]})
    with pytest.raises(ValueError):
        manual.decode("labels",{"changes":[{"op":"clear_labels"},{"op":"set_label","key":"x","value":"y"}]})

def test_usage_accounting_and_unknown_rates():
    rates={"input_per_million":.75,"cached_input_per_million":.075,"output_per_million":4.5}
    assert h.usage_cost({"input_tokens":1000,"output_tokens":100,"input_tokens_details":{"cached_tokens":400}},rates)==pytest.approx(.00093)
    with pytest.raises(ValueError):
        h.usage_cost({"input_tokens":1000,"output_tokens":100,"input_tokens_details":{"cache_write_tokens":1}},rates)

def small_plan(data):
    workflows,scenarios,gold,policy,config,specs,encoding=data
    s=scenarios[0]
    request=h.request_for(config,specs["flat"]["argbridge"],workflows["flat"],s["instruction"],policy)
    return {"config":config,"code_sha256":h.code_hashes(),"dataset_manifest_sha256":h.sha(h.read(h.HERE/"dataset/MANIFEST.json")),
            "dependency_fingerprint":h.dependencies(),
            "scenario_count":56,"specs":specs,"jobs":[{"id":"synthetic-trial","phase":"intent","scenario_id":s["id"],
            "category":s["category"],"workflow":"flat","method":"argbridge","repeat":0,"request":request}]},encoding

def test_no_authorization_no_live_run(data):
    plan,_=small_plan(data)
    with pytest.raises(PermissionError):
        h.authorize(plan,{"authorized":False},1,False)
    auth={"authorized":True,"approved_by":"user","approved_at":"synthetic-test-only","plan_sha256":h.sha(plan),"max_usd":1}
    h.authorize(plan,auth,1,True)
    with pytest.raises(PermissionError):
        h.authorize(plan,auth,2,True)
    changed=deepcopy(plan); changed["config"]["temperature"]=.1
    with pytest.raises(PermissionError):
        h.authorize(changed,auth,1,True)

def test_budget_prevents_request(data,tmp_path):
    plan,encoding=small_plan(data)
    calls=[]
    client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kw:calls.append(kw)))
    summary=h.execute(plan,tmp_path/"budget",.0000001,client,encoding,evidence_kind="synthetic_fixture")
    assert not calls and summary["halt_reason"]=="budget_reservation_limit"

def test_recorded_synthetic_transport_and_timeout(data,tmp_path):
    plan,encoding=small_plan(data)
    args=Compiled(data[0]["flat"]["schema"]).encode({"enabled":False})
    client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kw:response("apply_update",args)))
    summary=h.execute(plan,tmp_path/"synthetic",1,client,encoding,evidence_kind="synthetic_fixture")
    assert summary["evidence_kind"]=="synthetic_fixture"
    assert summary["methods"]["argbridge"]["correct_intents"]==1
    def timeout(**kw): raise TimeoutError("simulated; no network")
    client.responses.create=timeout
    summary=h.execute(plan,tmp_path/"timeout",1,client,encoding,evidence_kind="synthetic_fixture")
    assert summary["halt_reason"]=="api_or_evaluation_failure_requires_review"
    assert summary["accounted_cost_or_reservation_usd"]>0
    assert summary["methods"]["argbridge"]["cost_per_correct_operation_usd"] is None
    with pytest.raises(ValueError):
        h.execute(plan,tmp_path/"timeout",1,client,encoding,evidence_kind="synthetic_fixture")

def test_real_provider_is_never_involved_in_unit_tests():
    with pytest.raises(AssertionError):
        socket.create_connection(("api.openai.com",443))


def test_current_sdk_behavior_is_observed_not_assumed(data):
    workflows,_,_,_,_,specs,_=data
    assert "unsupported" in specs["labels"]["agents_strict"]
    assert set(specs["flat"]["agents_strict"]["schema"]["required"])=={"name","quota","enabled"}
    restored=h.decode("mastra_strict","flat",{"name":None,"enabled":False,"quota":None},workflows["flat"]["schema"])
    assert restored=={"enabled":False}
    neutral={"ticket_id":"T-7","priority":"high"}
    assert h.decode("mastra_strict","ticket",neutral,workflows["ticket"]["schema"])==neutral

def test_real_sdk_serialization_with_mock_http_only(data,tmp_path):
    import httpx2
    from openai import OpenAI
    plan,encoding=small_plan(data)
    seen=[]
    args=Compiled(data[0]["flat"]["schema"]).encode({"enabled":False})
    def handler(request):
        assert str(request.url)=="https://api.openai.com/v1/responses"
        payload=json.loads(request.content)
        seen.append(payload)
        assert payload["model"]=="gpt-5.4-mini-2026-03-17"
        assert payload["tools"][0]["strict"] is True
        assert payload["store"] is False and payload["parallel_tool_calls"] is False
        body=response("apply_update",args)
        body.update(id="resp_synthetic",created_at=0,object="response",model=payload["model"])
        return httpx2.Response(200,json=body)
    http=httpx2.Client(transport=httpx2.MockTransport(handler))
    client=OpenAI(api_key="synthetic-unit-test-only",http_client=http,max_retries=0,base_url="https://api.openai.com/v1")
    summary=h.execute(plan,tmp_path/"sdk-mock",1,client,encoding,evidence_kind="synthetic_fixture")
    assert len(seen)==1
    assert summary["methods"]["argbridge"]["correct_intents"]==1
    assert summary["evidence_kind"]=="synthetic_fixture"
    client.close()


@pytest.mark.parametrize("limit",[float("nan"),float("inf"),-1,0,True])
def test_invalid_budget_rejected(data,limit):
    plan,_=small_plan(data)
    auth={"authorized":True,"approved_by":"user","approved_at":"synthetic-test-only","plan_sha256":h.sha(plan),"max_usd":5}
    with pytest.raises(PermissionError):
        h.authorize(plan,auth,limit,True)

def test_authorization_is_single_use(tmp_path):
    auth={"authorized":True,"plan_sha256":"synthetic","max_usd":1,"approved_at":"synthetic-test-only"}
    h.consume_authorization(auth,tmp_path)
    with pytest.raises(FileExistsError):
        h.consume_authorization(auth,tmp_path)
