"""Prepare offline; run real requests ONLY after explicit spending authorization."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version, distribution
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from argbridge import BridgeError, Compiled, canonical, loads
from jsonschema import Draft202012Validator
from .compact import compact_schema, expand_local_refs
from . import manual

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read(path):
    raw=Path(path).read_text(encoding="utf-8-sig")
    if len(raw.encode())>25_000_000:
        raise ValueError("Evaluation artifact exceeds size limit")
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:
                raise ValueError("Duplicate evaluation artifact member")
            out[key]=value
        return out
    def invalid_constant(_):
        raise ValueError("Non-finite evaluation artifact value")
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid_constant)


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def dataset():
    manifest = read(HERE / "dataset/MANIFEST.json")
    for name, digest in manifest["files"].items():
        actual = hashlib.sha256((HERE / "dataset" / name).read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError("Frozen dataset hash mismatch: " + name)
    return (read(HERE/"dataset/workflows.json"), read(HERE/"dataset/scenarios.json"),
            read(HERE/"dataset/expected.json"), read(HERE/"dataset/policy.json")["instructions"])


def node(payload):
    executable = os.environ.get("ARGBRIDGE_NODE_BIN") or shutil.which("node")
    if not executable:
        raise RuntimeError("Node is required for the pinned Mastra comparator")
    result = subprocess.run([executable, str(HERE/"mastra.mjs")],
                            input=json.dumps(payload, ensure_ascii=False), text=True,
                            encoding="utf-8", capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Mastra local adapter failed: " + result.stderr[:500])
    return loads(result.stdout)


def validator(schema, value):
    return Draft202012Validator(schema).is_valid(value)


def make_specs(workflows, config):
    # Import only schema functions. No Agent Runner, tracing or API client.
    os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"
    from agents.strict_schema import ensure_strict_json_schema
    mastra = node({"action":"schemas","workflows":workflows,"model":config["model"]})
    specs = {}
    for w, definition in workflows.items():
        source = definition["schema"]
        c = Compiled(source)
        compact = compact_schema(c.wire_schema)
        assert expand_local_refs(compact) == expand_local_refs(c.wire_schema)
        specs[w] = {
            "argbridge":{"schema":c.wire_schema,"strict":True},
            "argbridge_factored":{"schema":compact,"strict":True},
            "manual_strict":{"schema":manual.schema(w, source),"strict":True},
            "original_nonstrict":{"schema":deepcopy(source),"strict":False},
            "mastra_strict":{**mastra[w],"strict":True},
        }
        try:
            specs[w]["agents_strict"] = {"schema":ensure_strict_json_schema(deepcopy(source)),"strict":True}
        except Exception as exc:
            specs[w]["agents_strict"] = {"unsupported":type(exc).__name__,"reason":str(exc)}
        for method in specs[w]:
            if "error" in specs[w][method]:
                specs[w][method]["unsupported"] = "conversion_error"
    return specs


def reference_arguments(method, workflow, patch, source):
    if method.startswith("argbridge"):
        return Compiled(source).encode(patch)
    if method == "manual_strict":
        return manual.encode(workflow, patch)
    return deepcopy(patch)


def decode(method, workflow, arguments, source):
    if method.startswith("argbridge"):
        return Compiled(source).decode(arguments)
    if method == "manual_strict":
        return manual.decode(workflow, arguments)
    if method == "mastra_strict":
        return node({"action":"normalize","schema":source,"value":arguments})
    return deepcopy(arguments)


def merge_patch(target, patch):
    if not isinstance(patch, dict):
        return deepcopy(patch)
    result = deepcopy(target) if isinstance(target, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


def score(response, job, expected, workflow, spec, encoding):
    """Scores an observed response; synthetic tests must not label it provider evidence."""
    result = {"structural_valid":False,"semantic_correct":False,"final_state_correct":False,
              "unsafe_accepted_mutation":False,"generated_argument_tokens":0}
    calls = [x for x in response.get("output",[]) if x.get("type")=="function_call"]
    result["generated_argument_tokens"]=sum(
        len(encoding.encode(x["arguments"],disallowed_special=()))
        for x in calls if isinstance(x.get("arguments"),str)
    )
    if response.get("status") != "completed":
        return {**result,"failure":"incomplete_response"}
    if len(calls) != 1:
        return {**result,"failure":"missing_or_multiple_calls"}
    call = calls[0]
    raw = call.get("arguments","")
    if not isinstance(raw,str):
        return {**result,"failure":"arguments_not_text"}
    result["generated_argument_tokens"] = len(encoding.encode(raw, disallowed_special=()))
    try:
        arguments = loads(raw)
        action = call.get("name")
        if action in ("request_clarification","reject_request"):
            if not validator(reason_schema(),arguments):
                return {**result,"failure":"invalid_reason_schema"}
            if not arguments["reason"].strip():
                return {**result,"structural_valid":True,"failure":"empty_reason"}
            result.update(structural_valid=True, semantic_correct=action==expected["action"],
                          final_state_correct=expected["action"]!= "apply_update",
                          failure=None if action==expected["action"] else "wrong_action")
            return result
        if action != "apply_update":
            return {**result,"failure":"unknown_tool"}
        if not validator(spec["schema"],arguments):
            return {**result,"failure":"wire_schema_invalid"}
        patch = decode(job["method"], job["workflow"], arguments, workflow["schema"])
        if not validator(workflow["schema"],patch):
            return {**result,"failure":"source_contract_invalid"}
    except (BridgeError, ValueError, KeyError, TypeError, RuntimeError):
        return {**result,"failure":"decode_rejected"}
    result["structural_valid"] = True
    result["decoded_patch"] = patch
    after = merge_patch(workflow["initial"],patch)
    intended = expected.get("patch",{})
    correct = expected["action"] == "apply_update" and canonical(patch)==canonical(intended)
    result.update(semantic_correct=correct,
                  final_state_correct=after==merge_patch(workflow["initial"], intended),
                  unsafe_accepted_mutation=not correct and patch!={},
                  failure=None if correct else "wrong_mutation")
    return result


def reason_schema():
    return {"type":"object","properties":{"reason":{"type":"string"}},
            "required":["reason"],"additionalProperties":False}


def tools_for(spec):
    return [
        {"type":"function","name":"apply_update","description":"Apply only the explicitly requested changes to the original contract; interpret the supplied wire representation.",
         "parameters":spec["schema"],"strict":spec["strict"]},
        {"type":"function","name":"request_clarification","description":"Ask for a missing or ambiguous target/value. Do not change state.",
         "parameters":reason_schema(),"strict":True},
        {"type":"function","name":"reject_request","description":"Reject an explicitly invalid field, type or value. Do not change state.",
         "parameters":reason_schema(),"strict":True}
    ]


def request_for(config, spec, workflow, instruction, policy):
    return {k:deepcopy(config[k]) for k in ("model","reasoning","temperature","max_output_tokens","parallel_tool_calls","store","service_tier")} | {
        "instructions":policy+"\nOriginal contract:\n"+canonical(workflow["schema"])+"\nCurrent state:\n"+canonical(workflow["initial"]),
        "input":instruction,"tools":tools_for(spec),"tool_choice":"required"
    }


def tokens(encoding,value):
    return len(encoding.encode(canonical(value), disallowed_special=()))


def prepare():
    import tiktoken
    workflows, scenarios, gold, policy = dataset()
    config = read(HERE/"config.json")
    encoding = tiktoken.encoding_for_model(config["model"])
    specs = make_specs(workflows, config)
    jobs, unsupported, metrics, original_metrics = [], [], [], []
    for w, methods in specs.items():
        for method in config["methods"]:
            spec = methods[method]
            if "unsupported" in spec:
                unsupported.append({"workflow":w,"method":method,**spec})
                continue
            sample = next(s for s in scenarios if s["workflow"]==w)
            request = request_for(config,spec,workflows[w],sample["instruction"],policy)
            jobs.append({"id":f"probe:{w}:{method}","phase":"schema_probe","workflow":w,"method":method,"request":request})
            metrics.append({"workflow":w,"method":method,"strict":spec["strict"],
                            "source_schema_content_tokens":tokens(encoding,workflows[w]["schema"]),
                            "wire_schema_content_tokens":tokens(encoding,spec["schema"]),
                            "wire_schema_bytes":len(canonical(spec["schema"]).encode())})
    # Probe every wire schema from the original deterministic benchmark as well.
    for fixture in read(ROOT/"bench/fixtures/workflows.json"):
        spec={"schema":Compiled(fixture["schema"]).wire_schema,"strict":True}
        factored=compact_schema(spec["schema"])
        assert expand_local_refs(factored)==expand_local_refs(spec["schema"])
        original_metrics.append({"workflow":fixture["id"],
            "source_schema_content_tokens":tokens(encoding,fixture["schema"]),
            "original_wire_schema_content_tokens":tokens(encoding,spec["schema"]),
            "factored_wire_schema_content_tokens":tokens(encoding,factored),
            "original_wire_bytes":len(canonical(spec["schema"]).encode()),
            "factored_wire_bytes":len(canonical(factored).encode())})
        workflow={"schema":fixture["schema"],"initial":{}}
        req=request_for(config,spec,workflow,"Call apply_update with any valid value. This is a schema acceptance probe.",policy)
        req["tool_choice"]={"type":"function","name":"apply_update"}
        jobs.append({"id":"original_probe:"+fixture["id"],"phase":"schema_probe",
                     "workflow":"original:"+fixture["id"],"method":"argbridge","request":req})
    trials=[]
    for scenario in scenarios:
        w=scenario["workflow"]
        for method in config["methods"]:
            spec=specs[w][method]
            if "unsupported" in spec:
                continue
            for rep in range(config["repetitions"]):
                trials.append({"id":f"trial:{scenario['id']}:{method}:{rep}","phase":"intent",
                               "scenario_id":scenario["id"],"category":scenario["category"],"workflow":w,
                               "method":method,"repeat":rep,
                               "request":request_for(config,spec,workflows[w],scenario["instruction"],policy)})
    random.Random(config["random_seed"]).shuffle(trials)
    jobs.extend(trials)
    rates=config["pricing"]
    estimate_input=sum(int(tokens(encoding,j["request"])*1.25)+256 for j in jobs)
    estimate_output=len(jobs)*config["max_output_tokens"]
    estimated_max=(estimate_input*rates["input_per_million"]+estimate_output*rates["output_per_million"])/1e6
    reference=[]
    for s in scenarios:
        if gold[s["id"]]["action"] != "apply_update":
            continue
        for method in config["methods"]:
            if "unsupported" in specs[s["workflow"]][method]:
                continue
            args=reference_arguments(method,s["workflow"],gold[s["id"]]["patch"],workflows[s["workflow"]]["schema"])
            reference.append({"scenario_id":s["id"],"method":method,"reference_argument_tokens":tokens(encoding,args),
                              "label":"deterministic_reference_not_model_output"})
    plan={"format":"argbridge-eval-v1","config":config,"dataset_manifest_sha256":sha(read(HERE/"dataset/MANIFEST.json")),
          "code_sha256":code_hashes(),"specs":specs,"jobs":jobs,"unsupported_cells":unsupported,
          "scenario_count":len(scenarios),"dependency_fingerprint":dependencies()}
    write(ARTIFACTS/"plan.json",plan)
    report={"kind":"offline_preparation","live_requests_made":0,
            "schema_acceptance":None,"model_accuracy":None,"generated_argument_tokens":None,
            "end_to_end_latency":None,"cost_per_correct_operation":None,
            "plan_sha256":sha(plan),"model":config["model"],"tokenizer":encoding.name,
            "tiktoken_version":version("tiktoken"),"sdk_versions":{"openai":version("openai"),"openai-agents":version("openai-agents"),"mastra":"1.3.17"},
            "scheduled_requests":len(jobs),"probe_requests":sum(j["phase"]=="schema_probe" for j in jobs),
            "intent_requests":len(trials),"scenario_count":len(scenarios),"repetitions":config["repetitions"],
            "unsupported_cells":unsupported,"schema_tokens":metrics,"reference_arguments":reference,
            "original_corpus_schema_tokens":original_metrics,
            "cost_estimate":{"usd":round(estimated_max,4),"estimated_input_tokens":estimate_input,
                             "output_token_allowance":estimate_output,
                             "assumptions":"No cache discount. Local request-content tokens x1.25 +256 each; all outputs at the configured maximum. Hidden provider serialization is unmeasured; this is an estimate, not a quote."}}
    write(ARTIFACTS/"offline.json",report)
    write(ARTIFACTS/"authorization.example.json",{"authorized":False,"plan_sha256":sha(plan),"max_usd":0,"approved_by":None,"approved_at":None})
    print(json.dumps({k:v for k,v in report.items() if k not in ("schema_tokens","reference_arguments","unsupported_cells","original_corpus_schema_tokens")},indent=2))
    return report


def code_hashes():
    paths=list(HERE.glob("*.py"))+[HERE/"mastra.mjs",HERE/"requirements-lock.txt",ROOT/"bench/node/package-lock.json",
                                ROOT/"src/argbridge/core.py",ROOT/"src/argbridge/__init__.py"]
    return {str(p.relative_to(ROOT)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def dependencies():
    return {"versions":{name:version(name) for name in ("openai","openai-agents","jsonschema","tiktoken")},
            "agents_converter_sha256":hashlib.sha256(Path(distribution("openai-agents").locate_file("agents/strict_schema.py")).read_bytes()).hexdigest(),
            "mastra_bundle_sha256":hashlib.sha256((ROOT/"bench/node/node_modules/@mastra/schema-compat/dist/index.js").read_bytes()).hexdigest()}


def usage_cost(usage, rates):
    incoming=usage["input_tokens"]; outgoing=usage["output_tokens"]
    details=usage.get("input_tokens_details") or {}
    cached=details.get("cached_tokens",0)
    if details.get("cache_write_tokens",0):
        raise ValueError("Unexpected cache-write billing; pricing review required")
    if any(type(x) is not int or x<0 for x in (incoming,outgoing,cached)) or cached>incoming:
        raise ValueError("Invalid usage accounting")
    return ((incoming-cached)*rates["input_per_million"]+cached*rates["cached_input_per_million"]+
            outgoing*rates["output_per_million"])/1e6


def reservation(job,rates):
    # Byte count plus large wrapper allowance is a conservative engineering
    # reservation, not a formal provider invoice cap. Stop on unknown charges.
    input_allowance=len(canonical(job["request"]).encode())+4096
    return (input_allowance*rates["input_per_million"]+job["request"]["max_output_tokens"]*rates["output_per_million"])/1e6


def authorize(plan, auth, limit, allow_spend):
    if not allow_spend or auth.get("authorized") is not True or auth.get("approved_by")!="user" or not auth.get("approved_at"):
        raise PermissionError("Explicit user spending authorization is required")
    if auth.get("plan_sha256")!=sha(plan) or plan["code_sha256"]!=code_hashes():
        raise PermissionError("Plan/code changed; regenerate and renew approval")
    if plan["dependency_fingerprint"]!=dependencies():
        raise PermissionError("Evaluation dependencies changed")
    if plan["dataset_manifest_sha256"]!=sha(read(HERE/"dataset/MANIFEST.json")):
        raise PermissionError("Dataset changed")
    cap=auth.get("max_usd",0)
    if type(limit) not in (int,float) or type(cap) not in (int,float) or not math.isfinite(limit) or not math.isfinite(cap) or limit<=0 or limit>cap:
        raise PermissionError("Budget exceeds authorized amount")
    dataset()


def consume_authorization(auth, directory):
    """One-shot authorization marker prevents accidental duplicate paid runs."""
    directory.mkdir(parents=True,exist_ok=True)
    marker=directory/(sha(auth)+".used.json")
    with marker.open("x",encoding="utf-8") as f:
        json.dump({"plan_sha256":auth["plan_sha256"],"max_usd":auth["max_usd"],
                   "consumed_at":datetime.now(timezone.utc).isoformat()},f)
    return marker


def execute(plan, directory, limit, client, encoding, evidence_kind="openai_live"):
    """No external handler is ever called. A fresh output directory is required."""
    if directory.exists():
        raise ValueError("Use a fresh run directory; existing runs are never overwritten")
    directory.mkdir(parents=True)
    workflows, scenarios, gold, _=dataset()
    rates=plan["config"]["pricing"]
    spent=0.0; events=[]; blocked=set(); halt=None
    for job in plan["jobs"]:
        key=(job["workflow"],job["method"])
        if key in blocked:
            events.append({"id":job["id"],"phase":job["phase"],"workflow":job["workflow"],"method":job["method"],
                           "status":"skipped_rejected_schema","scenario_id":job.get("scenario_id"),
                           "repeat":job.get("repeat"),"category":job.get("category"),"evidence_kind":evidence_kind})
            continue
        reserve=reservation(job,rates)
        if spent+reserve>limit:
            halt="budget_reservation_limit"
            break
        event={"id":job["id"],"phase":job["phase"],"workflow":job["workflow"],"method":job["method"],
               "scenario_id":job.get("scenario_id"),"category":job.get("category"),"repeat":job.get("repeat"),
               "evidence_kind":evidence_kind,"request_sha256":sha(job["request"]),
               "request_strict":job["request"]["tools"][0]["strict"]}
        with (directory/"events.jsonl").open("a",encoding="utf-8") as f:
            f.write(json.dumps({**event,"status":"request_started","reserved_cost_usd":reserve})+"\n")
        start=time.perf_counter()
        try:
            response=client.responses.create(**job["request"])
            elapsed=time.perf_counter()-start
            raw=response.model_dump(mode="json") if hasattr(response,"model_dump") else response
            event["provider_latency_ms"]=elapsed*1000
            event["response"]=raw
            try:
                cost=usage_cost(raw["usage"],rates)
            except (KeyError,ValueError,TypeError):
                spent+=reserve
                event.update(status="unknown_usage",reserved_cost_usd=reserve)
                halt="unknown_charge_requires_review"
            else:
                spent+=cost
                event.update(status="response_received",usage_cost_usd=cost,
                             schema_acceptance="accepted" if not raw.get("error") else "response_error")
                if raw.get("error"):
                    halt="provider_response_error_requires_review"
                returned_tools=raw.get("tools") or []
                if any(t.get("name")=="apply_update" and t.get("strict") is False for t in returned_tools) and job["request"]["tools"][0]["strict"]:
                    event["schema_acceptance"]="unexpected_non_strict_fallback"
                    blocked.add(key)
                if job["phase"]=="intent" and event["schema_acceptance"]=="accepted":
                    event["score"]=score(raw,job,gold[job["scenario_id"]],workflows[job["workflow"]],
                                         plan["specs"][job["workflow"]][job["method"]],encoding)
        except Exception as exc:
            elapsed=time.perf_counter()-start
            body=getattr(exc,"body",None)
            code=body.get("code") if isinstance(body,dict) else None
            param=body.get("param") if isinstance(body,dict) else None
            status=getattr(exc,"status_code",None)
            event.update(status="api_error",provider_latency_ms=elapsed*1000,error_type=type(exc).__name__,
                         http_status=status,error_code=code,error_param=param)
            # Do not retry unknown failures automatically; charge may have occurred.
            if status==400 and (code in ("invalid_function_parameters","invalid_json_schema") or isinstance(param,str) and param.startswith("tools")):
                event["schema_acceptance"]="rejected"
                blocked.add(key)
            else:
                if "usage_cost_usd" not in event:
                    spent+=reserve; event["reserved_cost_usd"]=reserve
                halt="api_or_evaluation_failure_requires_review"
        event["harness_latency_ms"]=(time.perf_counter()-start)*1000
        events.append(event)
        with (directory/"events.jsonl").open("a",encoding="utf-8") as f:
            f.write(json.dumps(event,ensure_ascii=False)+"\n")
        if halt:
            break
    write(directory/"events.json",events)
    summary=summarize(plan,events)
    summary.update(evidence_kind=evidence_kind,plan_sha256=sha(plan),halt_reason=halt,
                   budget_usd=limit,accounted_cost_or_reservation_usd=spent)
    write(directory/"summary.json",summary)
    return summary


def summarize(plan,events):
    methods={}
    for method in plan["config"]["methods"]:
        scheduled=[j for j in plan["jobs"] if j["method"]==method and j["phase"]=="intent"]
        measured=[e for e in events if e["method"]==method and e["phase"]=="intent"]
        scored=[e for e in measured if "score" in e]
        correct=sum(e["score"]["semantic_correct"] for e in scored)
        costs=sum(e.get("usage_cost_usd",0) for e in measured)
        unknown=sum("reserved_cost_usd" in e for e in measured)
        complete=len(measured)==len(scheduled)
        lat=sorted(e["provider_latency_ms"] for e in measured if "provider_latency_ms" in e)
        methods[method]={"scheduled_intents":len(scheduled),"observed_intents":len(measured),
            "target_intents":plan["scenario_count"]*plan["config"]["repetitions"],
            "unsupported_intents":plan["scenario_count"]*plan["config"]["repetitions"]-len(scheduled),
            "scheduled_run_complete":complete,
            "scored_intents":len(scored),"correct_intents":correct,
            "provider_intent_requests":sum("provider_latency_ms" in e for e in measured),
            "semantic_accuracy_observed":correct/len(measured) if measured else None,
            "structural_valid":sum(e["score"]["structural_valid"] for e in scored),
            "unsafe_accepted_mutations":sum(e["score"]["unsafe_accepted_mutation"] for e in scored),
            "usage_cost_usd":costs,"unknown_charge_events":unknown,
            "cost_per_correct_operation_usd":costs/correct if correct and not unknown else None,
            "semantic_accuracy_including_unsupported":correct/(plan["scenario_count"]*plan["config"]["repetitions"]) if complete else None,
            "latency_p50_ms":lat[len(lat)//2] if lat else None,
            "latency_p95_ms":lat[min(len(lat)-1,int(.95*len(lat)))] if lat else None,
            "failure_counts":dict(Counter(e.get("score",{}).get("failure",e["status"]) for e in measured))}
    paired={}
    for variant in ("argbridge","argbridge_factored"):
        for baseline in ("manual_strict","original_nonstrict","agents_strict","mastra_strict"):
            a={(e.get("scenario_id"),e.get("repeat")):e for e in events if e["method"]==variant and e["phase"]=="intent"}
            b={(e.get("scenario_id"),e.get("repeat")):e for e in events if e["method"]==baseline and e["phase"]=="intent"}
            common=set(a)&set(b)
            paired[variant+"_vs_"+baseline]={"paired_observations":len(common),
                "encoding_losses":sum(not a[k].get("score",{}).get("semantic_correct",False) and b[k].get("score",{}).get("semantic_correct",False) for k in common),
                "encoding_gains":sum(a[k].get("score",{}).get("semantic_correct",False) and not b[k].get("score",{}).get("semantic_correct",False) for k in common)}
    return {"methods":methods,"paired":paired,
            "schema_observations":[{k:e.get(k) for k in ("id","method","workflow","request_strict","schema_acceptance","http_status")} for e in events if e["phase"]=="schema_probe"],
            "note":"Repeated responses share scenarios; not independent customer samples. Cost excludes separate schema probes; no invoice claim."}


def main():
    global ARTIFACTS
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    preparation=sub.add_parser("prepare")
    preparation.add_argument("--output",required=True,help="Fresh directory for a new offline plan; historical artifacts are never overwritten")
    live=sub.add_parser("live")
    live.add_argument("--authorization",required=True)
    live.add_argument("--allow-spend",action="store_true")
    live.add_argument("--max-usd",type=float,required=True)
    live.add_argument("--output",required=True)
    live.add_argument("--plan",required=True,help="Explicit prepared plan.json to execute after approval")
    args=parser.parse_args()
    if args.command=="prepare":
        ARTIFACTS=Path(args.output).resolve()
        if ARTIFACTS.exists():
            parser.error("Preparation output must be a fresh directory; existing evidence is preserved")
        prepare(); return 0
    plan=read(args.plan)
    auth=read(args.authorization)
    authorize(plan,auth,args.max_usd,args.allow_spend)
    # No credential lookup, API client or network transport exists before this point.
    key=os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Set a dedicated OPENAI_API_KEY locally; do not paste it into a public issue or chat.")
    if Path(args.output).exists():
        raise ValueError("Run output directory must not already exist")
    consume_authorization(auth,HERE/"runs/authorizations")
    from openai import OpenAI
    import tiktoken
    client=OpenAI(api_key=key,base_url="https://api.openai.com/v1",max_retries=0,timeout=60)
    summary=execute(plan,Path(args.output),args.max_usd,client,tiktoken.encoding_for_model(plan["config"]["model"]))
    print(json.dumps(summary,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
