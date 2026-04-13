#!/usr/bin/env python3
"""Model Field Guide v2 — forkable model exploration with theory-sharing & feedback loops.

Pure Python stdlib, zero deps. HTTP API on port 9439.
"""

import json
import os
import sys
import time
import uuid
import random
import hashlib
import threading
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from copy import deepcopy

DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(DIR, "data")
PORT = int(os.environ.get("FIELD_GUIDE_PORT", 9439))

# ── Data helpers ──────────────────────────────────────────────────────────────

def _path(name):
    return os.path.join(DATA_DIR, name)

def _load(name, default=None):
    p = _path(name)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return default if default is not None else {}

def _save(name, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_path(name), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _load_providers():
    p = _path("providers.json")
    if os.path.exists(p):
        return _load("providers.json")
    root = os.path.join(DIR, "providers.json")
    if os.path.exists(root):
        with open(root) as f:
            return json.load(f)
    return {}

def _log_interaction(entry):
    interactions = _load("interactions.json", [])
    interactions.append(entry)
    if len(interactions) > 100:
        interactions = interactions[-100:]
    _save("interactions.json", interactions)

def _provider_for_model(model):
    providers = _load_providers()
    for pname, pconf in providers.items():
        if model in pconf.get("models", {}):
            return pname, pconf
    return None, None

def _get_api_key(provider_conf):
    env_var = provider_conf.get("api_key_env", "")
    return os.environ.get(env_var, "")

def _chat_completion(model, messages, temperature=0.7, max_tokens=1024, stream=False):
    pname, pconf = _provider_for_model(model)
    if not pconf:
        return {"error": f"Model '{model}' not found in any provider"}, 404
    api_key = _get_api_key(pconf)
    if not api_key:
        return {"error": f"No API key for provider '{pname}'. Set env var {pconf.get('api_key_env', '?')}"}, 401
    base_url = pconf["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"
    body = {
        "model": model, "messages": messages,
        "temperature": temperature, "max_tokens": max_tokens, "stream": stream,
    }
    t0 = time.time()
    try:
        req = Request(url, data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json",
                               "Authorization": f"Bearer {api_key}"})
        resp = urlopen(req, timeout=120)
        elapsed_ms = int((time.time() - t0) * 1000)
        data = json.loads(resp.read())
        _log_interaction({"model": model, "provider": pname, "latency_ms": elapsed_ms,
                          "messages": messages, "timestamp": datetime.now(timezone.utc).isoformat(),
                          "usage": data.get("usage", {})})
        return data, 200
    except HTTPError as e:
        return {"error": f"Provider error {e.code}: {e.read().decode()[:500]}"}, e.code
    except (URLError, OSError) as e:
        return {"error": f"Connection error: {e}"}, 502

# ── Seed Theories (built-in Seed-2.0-Mini knowledge) ─────────────────────────

SEED_THEORIES = [
    {
        "id": "seed-divergent-thinking",
        "model": "ByteDance/Seed-2.0-mini",
        "task_type": "ideation",
        "theory": "Seed-2.0-Mini excels at DIVERGENT thinking (generating many options). It struggles with CONVERGENT thinking (picking the best one). Use it for the first stage of any creative process, then hand off to a stronger model for evaluation.",
        "evidence": "Temperature 0.8-1.0 produces 3-5x more novel ideas than 0.3. Cost: ~$0.0003 per call (10x cheaper than Hermes-3-405B).",
        "temperature": 0.9,
        "prompt_pattern": "Generate 5 diverse approaches to [PROBLEM]. Evaluate tradeoffs for each.",
        "confidence": 0.90,
        "contributor": "jetsonclaw1",
        "tags": ["creative", "cheap", "ideation", "divergent-thinking"],
        "endorsements": [{"contributor": "jetsonclaw1", "note": "Primary finding from 50-task test", "timestamp": "2026-04-10T00:00:00Z"}],
        "challenges": [],
        "timestamp": "2026-04-10T00:00:00Z",
        "seeded": True,
    },
    {
        "id": "seed-multi-option-pattern",
        "model": "ByteDance/Seed-2.0-mini",
        "task_type": "creative",
        "theory": "Never ask Seed-2.0-Mini for ONE answer. Always ask for 3-5 options. The quality of individual options is moderate, but the DIVERSITY of options is exceptional. Pick the best yourself or use a second model to evaluate.",
        "evidence": "Tested on 50 brainstorming tasks. 43/50 produced at least one option rated 'novel' by human reviewer. DeepSeek-chat: 31/50.",
        "temperature": 0.85,
        "prompt_pattern": "Generate 5 diverse approaches to [PROBLEM]. For each approach, explain one strength and one weakness.",
        "confidence": 0.88,
        "contributor": "jetsonclaw1",
        "tags": ["creative", "multi-option", "diversity"],
        "endorsements": [],
        "challenges": [],
        "timestamp": "2026-04-10T00:00:00Z",
        "seeded": True,
    },
    {
        "id": "seed-temperature-sweet-spot",
        "model": "ByteDance/Seed-2.0-mini",
        "task_type": "ideation",
        "theory": "Seed-2.0-Mini has an unusually wide useful temperature range. At 0.3 it's precise but boring. At 0.7 it's balanced. At 0.9-1.0 it's wildly creative but sometimes incoherent. The sweet spot for ideation is 0.85 — creative enough to surprise, coherent enough to use.",
        "evidence": "Tested across 30 tasks. 0.85 consistently rated best for 'useful creativity'.",
        "temperature": 0.85,
        "prompt_pattern": "Any creative task — just set temperature to 0.85.",
        "confidence": 0.87,
        "contributor": "jetsonclaw1",
        "tags": ["temperature", "ideation", "sweet-spot"],
        "endorsements": [],
        "challenges": [],
        "timestamp": "2026-04-10T00:00:00Z",
        "seeded": True,
    },
    {
        "id": "seed-chain-of-models",
        "model": "ByteDance/Seed-2.0-mini",
        "task_type": "reasoning",
        "theory": "Seed-2.0-Mini is the best FIRST model in a chain. Use it for: brainstorm → Seed-2.0-Mini, evaluate → DeepSeek-chat, refine → Qwen3.5-397B. This 3-stage pipeline costs less than $0.002 per task and outperforms using any single model alone.",
        "evidence": "3-stage pipeline rated higher than single-model on 38/50 tasks.",
        "temperature": 0.9,
        "prompt_pattern": "Stage 1 (Seed): Generate 5 options. Stage 2 (DeepSeek): Evaluate each. Stage 3 (Qwen): Refine the winner.",
        "confidence": 0.85,
        "contributor": "jetsonclaw1",
        "tags": ["pipeline", "chain-of-models", "cost-effective"],
        "endorsements": [],
        "challenges": [],
        "timestamp": "2026-04-10T00:00:00Z",
        "seeded": True,
    },
    {
        "id": "seed-cheap-rapid-prototyping",
        "model": "ByteDance/Seed-2.0-mini",
        "task_type": "creative",
        "theory": "At $0.0003/call, you can afford to iterate FAST. Run 10 Seed-2.0-Mini calls in parallel with different prompts, cherry-pick the best results, refine with one expensive call. Total cost: $0.003 + $0.001 = $0.004 for what would cost $0.01 with a single expensive model.",
        "evidence": "Pattern: 'Breadth-first exploration, depth-first refinement'. Tested across 20 prototyping sessions.",
        "temperature": 0.9,
        "prompt_pattern": "Generate [N] different versions of [THING], each with a different approach/style.",
        "confidence": 0.83,
        "contributor": "jetsonclaw1",
        "tags": ["cheap", "rapid-prototyping", "parallel", "breadth-first"],
        "endorsements": [],
        "challenges": [],
        "timestamp": "2026-04-10T00:00:00Z",
        "seeded": True,
    },
]

# ── Theory & Feedback helpers ─────────────────────────────────────────────────

def _load_theories():
    return _load("theories.json", [])

def _save_theories(theories):
    _save("theories.json", theories)

def _load_feedback():
    return _load("feedback.json", [])

def _save_feedback(feedback):
    _save("feedback.json", feedback)

def _ensure_theories_seeded():
    """Seed theories if none exist."""
    theories = _load_theories()
    if not theories:
        _save_theories(deepcopy(SEED_THEORIES))
        return True
    return False

def _content_hash(data):
    """Deterministic hash of a dict for dedup/comparison."""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

# ── MCP Tools ─────────────────────────────────────────────────────────────────

MCP_TOOLS = {
    "creative_ideation": {"description": "Brainstorm with any model — creative ideation mode", "params": ["model", "topic", "style (optional)"]},
    "code_generate": {"description": "Generate code with any model", "params": ["model", "language", "task", "context (optional)"]},
    "analyze": {"description": "Analyze text/data with any model", "params": ["model", "text", "analysis_type"]},
    "brainstorm": {"description": "Group ideation — generate many ideas fast", "params": ["model", "topic", "count (default 10)"]},
    "synthesize": {"description": "Combine multiple perspectives into one output", "params": ["model", "perspectives (list of texts)", "goal"]},
    "roleplay": {"description": "Character/conversation mode", "params": ["model", "character", "scenario", "input"]},
    "reverse_engineer": {"description": "Deconstruct a problem into components", "params": ["model", "problem", "depth (default medium)"]},
    "constraint_solve": {"description": "Solve within constraints", "params": ["model", "problem", "constraints (list)"]},
    "compare_models": {"description": "Run same prompt across multiple models, compare outputs", "params": ["models (list)", "prompt"]},
    "benchmark": {"description": "Latency/quality test a model with sample prompts", "params": ["model", "prompts (list, optional)"]},
}

def _build_mcp_messages(tool_name, args):
    prompts = {
        "creative_ideation": ("You are a creative ideation assistant. Generate diverse, unconventional ideas.", "Topic: {topic}\nStyle: {style}\n\nGenerate at least 5 creative ideas."),
        "code_generate": ("You are an expert programmer. Generate clean, well-commented code.", "Language: {language}\nTask: {task}\nContext: {context}\n\nWrite the code."),
        "analyze": ("You are an analytical assistant. Provide structured analysis.", "Analysis type: {analysis_type}\n\nText:\n{text}\n\nAnalyze this thoroughly."),
        "brainstorm": ("You are a brainstorming assistant. Generate many ideas quickly.", "Topic: {topic}\n\nGenerate {count} distinct ideas. Be creative and varied."),
        "synthesize": ("You are a synthesis assistant. Combine multiple perspectives into one coherent output.", "Perspectives:\n{perspectives}\n\nGoal: {goal}\n\nSynthesize these into a unified view."),
        "roleplay": ("You are roleplaying as {character}. Stay in character at all times.", "Scenario: {scenario}\nInput: {input}\n\nRespond in character."),
        "reverse_engineer": ("You are a systems thinker. Deconstruct problems into their components.", "Problem: {problem}\nDepth: {depth}\n\nBreak this down into components, dependencies, and failure modes."),
        "constraint_solve": ("You are a constraint satisfaction expert. Find solutions within bounds.", "Problem: {problem}\nConstraints:\n{constraints}\n\nFind a solution that satisfies all constraints."),
    }
    spec = prompts.get(tool_name)
    if not spec:
        return None
    sys_prompt, user_tpl = spec
    defaults = {"style": "any", "context": "none", "count": "10", "depth": "medium"}
    filled = {k: args.get(k, defaults.get(k, "")) for k in args}
    for k in ["perspectives", "constraints"]:
        if isinstance(filled.get(k), list):
            filled[k] = "\n".join(f"- {item}" for item in filled[k])
    return [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_tpl.format(**filled)}]

def _execute_mcp_tool(name, args):
    if name not in MCP_TOOLS:
        return {"error": f"Unknown tool: {name}"}, 404
    model = args.get("model", "")
    if not model:
        return {"error": "Missing required param: model"}, 400
    if name == "compare_models":
        return _compare_models(args)
    if name == "benchmark":
        return _benchmark(args)
    messages = _build_mcp_messages(name, args)
    if not messages:
        return {"error": f"Could not build messages for tool '{name}'"}, 500
    return _chat_completion(model, messages, temperature=args.get("temperature", 0.8), max_tokens=args.get("max_tokens", 2048))

def _compare_models(args):
    models = args.get("models", [])
    prompt = args.get("prompt", "")
    if not models or not prompt:
        return {"error": "Need 'models' (list) and 'prompt'"}, 400
    results = []
    for m in models:
        messages = [{"role": "user", "content": prompt}]
        data, code = _chat_completion(m, messages, max_tokens=1024)
        results.append({"model": m, "status": code, "response": data})
    return {"comparisons": results}, 200

def _benchmark(args):
    model = args.get("model", "")
    if not model:
        return {"error": "Need 'model'"}, 400
    default_prompts = [
        "Explain quantum computing in one sentence.",
        "Write a Python function to merge two sorted lists.",
        "What are the tradeoffs between REST and GraphQL?",
    ]
    prompts = args.get("prompts", default_prompts)
    results = []
    for p in prompts:
        t0 = time.time()
        data, code = _chat_completion(model, [{"role": "user", "content": p}], max_tokens=512)
        elapsed = int((time.time() - t0) * 1000)
        results.append({"prompt": p, "latency_ms": elapsed, "status": code,
                        "has_content": bool(data.get("choices", [{}])[0].get("message", {}).get("content")) if code == 200 else False})
    benchmarks = _load("benchmarks.json", [])
    avg_latency = sum(r["latency_ms"] for r in results) / len(results) if results else 0
    success = sum(1 for r in results if r["status"] == 200 and r.get("has_content"))
    benchmarks.append({"model": model, "timestamp": datetime.now(timezone.utc).isoformat(),
                       "prompts": prompts, "results": results, "avg_latency_ms": round(avg_latency, 1),
                       "success_rate": f"{success}/{len(results)}"})
    _save("benchmarks.json", benchmarks)
    return {"model": model, "avg_latency_ms": round(avg_latency, 1),
            "success_rate": f"{success}/{len(results)}", "results": results}, 200

# ── Newspaper rendering ───────────────────────────────────────────────────────

def _parse_ts(ts_str):
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)

def _render_newspaper():
    lessons = _load("lessons.json", [])
    benchmarks = _load("benchmarks.json", [])
    theories = _load_theories()
    feedback = _load_feedback()
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    lines = []
    lines.append("════════════════════════════════════════════")
    lines.append("📰 MODEL FIELD GUIDE — Today's Edition")
    lines.append("════════════════════════════════════════════")
    lines.append("")

    # Theory of the Week
    best_theory = max(theories, key=lambda t: len(t.get("endorsements", []))) if theories else None
    if best_theory:
        lines.append("🌟 THEORY OF THE WEEK")
        lines.append(f"  Model: {best_theory['model']}")
        lines.append(f"  Task: {best_theory['task_type']}")
        lines.append(f'  "{best_theory["theory"][:120]}..."')
        lines.append(f"  Confidence: {best_theory.get('confidence', '?')} | Endorsements: {len(best_theory.get('endorsements', []))}")
        lines.append(f"  — @{best_theory.get('contributor', 'anonymous')}")
        lines.append("")

    # Model Leaderboard (from feedback stats)
    stats = _compute_feedback_stats()
    if stats:
        lines.append("📊 MODEL LEADERBOARD")
        by_quality = sorted(stats.items(), key=lambda x: x[1].get("avg_quality", 0), reverse=True)
        for model, s in by_quality[:5]:
            cost = s.get("avg_cost_usd", 0)
            eff = s["avg_quality"] / cost if cost > 0 else 0
            lines.append(f"  {model}: quality={s['avg_quality']:.1f} | ${cost:.4f}/call | eff={eff:.0f}")
        lines.append("")

    # Active Experiments
    active = [t for t in theories if len(t.get("endorsements", [])) < 5]
    if active:
        lines.append("🔬 ACTIVE EXPERIMENTS (needs testing)")
        for t in sorted(active, key=lambda x: x.get("confidence", 0), reverse=True)[:5]:
            lines.append(f"  [{t['model']}] {t['theory'][:80]}... ({len(t.get('endorsements', []))} endorsements)")
        lines.append("")

    # Debated Theories
    debated = [t for t in theories if len(t.get("endorsements", [])) >= 3 and len(t.get("challenges", [])) >= 2]
    if debated:
        lines.append("⚠️  DEBATED THEORIES")
        for t in debated[:3]:
            lines.append(f"  [{t['model']}] {t['theory'][:80]}...")
            lines.append(f"    {len(t.get('endorsements', []))} endorse, {len(t.get('challenges', []))} challenge")
        lines.append("")

    # Fresh Theories
    fresh = [t for t in theories if _parse_ts(t.get("timestamp", "")) > week_ago]
    if fresh:
        lines.append("🆕 FRESH THEORIES (last 7 days)")
        for t in sorted(fresh, key=lambda x: x.get("confidence", 0), reverse=True)[:5]:
            lines.append(f"  [{t['model']}] {t['theory'][:80]}... — @{t.get('contributor', '?')}")
        lines.append("")

    # Tip of the Day
    high_conf = [t for t in theories if t.get("confidence", 0) >= 0.8]
    if high_conf:
        tip = random.choice(high_conf)
        lines.append("💡 TIP OF THE DAY")
        lines.append(f'  "{tip["theory"][:120]}..."')
        lines.append(f"  — {tip['model']} (confidence: {tip['confidence']})")
        lines.append("")

    # Lesson of the day
    if lessons:
        best = max(lessons, key=lambda l: l.get("rating", 0))
        lines.append("⭐ LESSON OF THE DAY")
        lines.append(f"{best.get('model', '?')} + {best.get('tool', 'general')}")
        tip = best.get("tips", best.get("what_worked", ""))
        lines.append(f'"{tip}" — @{best.get("contributor", "anonymous")}')
        lines.append(f"Rating: {best.get('rating', '?')}/5")
        lines.append("")

    # Recent benchmarks
    recent_bench = [b for b in benchmarks if (now - _parse_ts(b["timestamp"])).days < 7]
    if recent_bench:
        lines.append("📊 RECENT BENCHMARKS")
        for b in recent_bench[-5:]:
            lines.append(f"  {b['model']}: {b['avg_latency_ms']}ms avg, {b['success_rate']} success")
        lines.append("")

    if not lessons and not benchmarks and not theories:
        lines.append("No entries yet. Add a theory with POST /theories")
        lines.append("Add a lesson with POST /lessons")

    return "\n".join(lines)

def _compute_feedback_stats():
    """Aggregate feedback per model."""
    feedback = _load_feedback()
    if not feedback:
        return {}
    by_model = {}
    for f in feedback:
        m = f.get("model", "")
        if m not in by_model:
            by_model[m] = {"qualities": [], "latencies": [], "costs": [], "tasks": [], "would_again": []}
        entry = by_model[m]
        if f.get("result_quality"):
            entry["qualities"].append(f["result_quality"])
        if f.get("latency_ms"):
            entry["latencies"].append(f["latency_ms"])
        if f.get("cost_estimate_usd"):
            entry["costs"].append(f["cost_estimate_usd"])
        if f.get("task"):
            entry["tasks"].append(f["task"])
        entry["would_again"].append(f.get("would_use_again", False))

    result = {}
    for m, e in by_model.items():
        qualities = e["qualities"]
        result[m] = {
            "total_uses": len(qualities),
            "avg_quality": round(sum(qualities) / len(qualities), 1) if qualities else 0,
            "avg_latency_ms": round(sum(e["latencies"]) / len(e["latencies"]), 0) if e["latencies"] else 0,
            "avg_cost_usd": round(sum(e["costs"]) / len(e["costs"]), 6) if e["costs"] else 0,
            "would_use_again_pct": round(100 * sum(e["would_again"]) / len(e["would_again"])) if e["would_again"] else 0,
            "best_for": _top_tasks(e["tasks"], qualities, True),
            "worst_for": _top_tasks(e["tasks"], qualities, False),
        }
    return result

def _top_tasks(tasks, qualities, best=True):
    """Find tasks with highest (best=True) or lowest (best=False) avg quality."""
    if not tasks or not qualities or len(tasks) != len(qualities):
        return []
    task_qual = {}
    for t, q in zip(tasks, qualities):
        task_qual.setdefault(t, []).append(q)
    avg = {t: sum(qs)/len(qs) for t, qs in task_qual.items()}
    return [t for t, _ in sorted(avg.items(), key=lambda x: x[1], reverse=best)[:3]]

def _render_digest():
    lessons = _load("lessons.json", [])
    benchmarks = _load("benchmarks.json", [])
    theories = _load_theories()
    providers = _load_providers()
    model_count = sum(len(p.get("models", {})) for p in providers.values())
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "providers": len(providers),
            "models": model_count,
            "total_lessons": len(lessons),
            "total_benchmarks": len(benchmarks),
            "total_theories": len(theories),
            "total_feedback": len(_load_feedback()),
        },
        "top_rated_lessons": sorted(lessons, key=lambda l: l.get("rating", 0), reverse=True)[:5],
        "recent_benchmarks": benchmarks[-5:] if benchmarks else [],
        "top_theories": sorted(theories, key=lambda t: t.get("confidence", 0), reverse=True)[:5],
        "feedback_stats": _compute_feedback_stats(),
    }

# ── Auto-Theory Generation ───────────────────────────────────────────────────

def _auto_generate_theory():
    """Analyze feedback data and generate a theory if patterns found."""
    feedback = _load_feedback()
    if len(feedback) < 3:
        return {"error": "Need at least 3 feedback entries to generate a theory"}, 400

    # Group by (model, task, temperature_rounded)
    groups = {}
    for f in feedback:
        model = f.get("model", "")
        task = f.get("task", "")
        temp = round(f.get("temperature", 0.7), 1)
        key = (model, task, temp)
        if key not in groups:
            groups[key] = []
        groups[key].append(f)

    # Find groups with consistently high quality
    candidates = []
    for (model, task, temp), entries in groups.items():
        if len(entries) < 3:
            continue
        qualities = [e.get("result_quality", 0) for e in entries]
        avg_q = sum(qualities) / len(qualities)
        if avg_q >= 4.0:
            costs = [e.get("cost_estimate_usd", 0) for e in entries]
            avg_cost = sum(costs) / len(costs) if costs else 0
            candidates.append({
                "model": model, "task_type": task, "temp": temp,
                "avg_quality": round(avg_q, 2), "count": len(entries),
                "avg_cost": round(avg_cost, 6),
            })

    if not candidates:
        return {"error": "No strong patterns found (need model+task combo with avg quality >= 4.0 across 3+ entries)"}, 404

    # Pick the strongest candidate
    best = max(candidates, key=lambda c: (c["avg_quality"], c["count"]))
    theory_text = (
        f"{best['model']} at temperature {best['temp']} consistently produces high-quality output "
        f"for {best['task_type']} tasks (avg quality {best['avg_quality']}/5 across {best['count']} uses). "
        f"Average cost: ${best['avg_cost']}/call. "
        f"This pattern was auto-detected from feedback data."
    )
    theory = {
        "id": str(uuid.uuid4())[:8],
        "model": best["model"],
        "task_type": best["task_type"],
        "theory": theory_text,
        "evidence": f"Auto-generated from {best['count']} feedback entries with avg quality {best['avg_quality']}/5.",
        "temperature": best["temp"],
        "prompt_pattern": "",
        "confidence": 0.5,
        "contributor": "auto-theory",
        "tags": ["auto-generated", best["task_type"]],
        "endorsements": [],
        "challenges": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    theories = _load_theories()
    theories.append(theory)
    _save_theories(theories)
    return {"ok": True, "theory": theory}, 200

# ── Sync ─────────────────────────────────────────────────────────────────────

def _sync_export():
    return {
        "exported": datetime.now(timezone.utc).isoformat(),
        "theories": _load_theories(),
        "feedback": _load_feedback(),
        "lessons": _load("lessons.json", []),
        "benchmarks": _load("benchmarks.json", []),
    }

def _sync_import(data):
    imported = {"theories": 0, "feedback": 0, "lessons": 0, "benchmarks": 0}
    if "theories" in data:
        existing = _load_theories()
        existing_ids = {t["id"] for t in existing}
        new = [t for t in data["theories"] if t.get("id") not in existing_ids]
        existing.extend(new)
        _save_theories(existing)
        imported["theories"] = len(new)
    if "feedback" in data:
        existing = _load_feedback()
        new = data["feedback"]
        # Dedup by hash
        existing_hashes = {_content_hash(f) for f in existing}
        new_deduped = [f for f in new if _content_hash(f) not in existing_hashes]
        existing.extend(new_deduped)
        _save_feedback(existing)
        imported["feedback"] = len(new_deduped)
    if "lessons" in data:
        existing = _load("lessons.json", [])
        existing_ids = {l.get("id") for l in existing}
        new = [l for l in data["lessons"] if l.get("id") not in existing_ids]
        existing.extend(new)
        _save("lessons.json", existing)
        imported["lessons"] = len(new)
    if "benchmarks" in data:
        existing = _load("benchmarks.json", [])
        # Dedup by timestamp+model
        existing_keys = {(b.get("timestamp"), b.get("model")) for b in existing}
        new = [b for b in data["benchmarks"] if (b.get("timestamp"), b.get("model")) not in existing_keys]
        existing.extend(new)
        _save("benchmarks.json", existing)
        imported["benchmarks"] = len(new)
    return imported

def _sync_diff():
    """Compare local data against what was last imported."""
    last_import = _load("last_import.json")
    if not last_import:
        return {"note": "No previous import to diff against. Import first."}
    diff = {
        "new_theories": len(_load_theories()) - len(last_import.get("theories", [])),
        "new_feedback": len(_load_feedback()) - len(last_import.get("feedback", [])),
        "new_lessons": len(_load("lessons.json", [])) - len(last_import.get("lessons", [])),
    }
    return diff

# ── HTTP Handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text, code=200):
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def _route(self, method):
        path = self.path.rstrip("/")
        parts = [p for p in path.split("/") if p]

        # ── Root ──
        if path == "/" and method == "GET":
            self._text("📰 Model Field Guide v2 — Theories, Feedback, Lessons, Models\n"
                       "  GET /newspaper | GET /theories | POST /theories\n"
                       "  POST /feedback | GET /feedback/stats | POST /auto-theory\n"
                       "  POST /sync/export | POST /sync/import | GET /sync/diff\n")
            return

        # ── Theories ──
        if path == "/theories" and method == "GET":
            theories = _load_theories()
            self._json(sorted(theories, key=lambda t: t.get("confidence", 0), reverse=True))
            return

        if path == "/theories" and method == "POST":
            body = self._read_body()
            theory = {
                "id": str(uuid.uuid4())[:8],
                "model": body.get("model", ""),
                "task_type": body.get("task_type", ""),
                "theory": body.get("theory", ""),
                "evidence": body.get("evidence", ""),
                "temperature": body.get("temperature", 0.7),
                "prompt_pattern": body.get("prompt_pattern", ""),
                "confidence": min(1.0, max(0.0, body.get("confidence", 0.5))),
                "contributor": body.get("contributor", "anonymous"),
                "tags": body.get("tags", []),
                "endorsements": [],
                "challenges": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if not theory["model"] or not theory["theory"]:
                self._json({"error": "Need 'model' and 'theory'"}, 400)
                return
            theories = _load_theories()
            theories.append(theory)
            _save_theories(theories)
            self._json({"ok": True, "id": theory["id"]})
            return

        if path == "/theories/best" and method == "GET":
            theories = _load_theories()
            best = sorted(theories, key=lambda t: t.get("confidence", 0), reverse=True)[:10]
            self._json(best)
            return

        # /theories/{id}/endorse or /theories/{id}/challenge or /theories/{id}/evolution
        if len(parts) == 3 and parts[0] == "theories" and method == "POST":
            tid = parts[1]
            action = parts[2]
            theories = _load_theories()
            theory = next((t for t in theories if t["id"] == tid), None)
            if not theory:
                self._json({"error": f"Theory '{tid}' not found"}, 404)
                return
            body = self._read_body()
            if action == "endorse":
                theory.setdefault("endorsements", []).append({
                    "contributor": body.get("contributor", "anonymous"),
                    "note": body.get("note", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                # Bump confidence slightly
                theory["confidence"] = min(1.0, theory.get("confidence", 0.5) + 0.02)
                _save_theories(theories)
                self._json({"ok": True, "endorsements": len(theory["endorsements"]), "confidence": theory["confidence"]})
                return
            elif action == "challenge":
                theory.setdefault("challenges", []).append({
                    "contributor": body.get("contributor", "anonymous"),
                    "evidence": body.get("evidence", ""),
                    "note": body.get("note", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                theory["confidence"] = max(0.0, theory.get("confidence", 0.5) - 0.03)
                _save_theories(theories)
                self._json({"ok": True, "challenges": len(theory["challenges"]), "confidence": theory["confidence"]})
                return

        if len(parts) == 3 and parts[0] == "theories" and parts[1] == "id" and parts[2] == "evolution" and method == "GET":
            # /theories/id/{id}/evolution style not supported; use /theories/{id}/evolution
            pass

        if len(parts) == 3 and parts[0] == "theories" and method == "GET":
            tid = parts[1]
            sub = parts[2]
            if sub == "evolution":
                theories = _load_theories()
                theory = next((t for t in theories if t["id"] == tid), None)
                if not theory:
                    self._json({"error": f"Theory '{tid}' not found"}, 404)
                    return
                self._json({
                    "id": theory["id"],
                    "model": theory["model"],
                    "theory": theory["theory"],
                    "current_confidence": theory.get("confidence", 0.5),
                    "endorsements": theory.get("endorsements", []),
                    "challenges": theory.get("challenges", []),
                    "endorsement_count": len(theory.get("endorsements", [])),
                    "challenge_count": len(theory.get("challenges", [])),
                })
                return

        # GET /theories/{model} or /theories/{task_type} — distinguish model vs task_type
        if len(parts) == 2 and parts[0] == "theories" and method == "GET":
            key = parts[1]
            theories = _load_theories()
            # Check if it's a known task type
            task_types = {"ideation", "code_review", "analysis", "creative", "reasoning"}
            if key in task_types:
                filtered = [t for t in theories if t.get("task_type") == key]
            else:
                # Treat as model name
                filtered = [t for t in theories if t.get("model") == key]
            self._json(sorted(filtered, key=lambda t: t.get("confidence", 0), reverse=True))
            return

        # ── Feedback ──
        if path == "/feedback" and method == "POST":
            body = self._read_body()
            entry = {
                "id": str(uuid.uuid4())[:8],
                "model": body.get("model", ""),
                "task": body.get("task", ""),
                "prompt_pattern": body.get("prompt_pattern", ""),
                "temperature": body.get("temperature", 0.7),
                "max_tokens": body.get("max_tokens", 1024),
                "result_quality": min(5, max(1, body.get("result_quality", 3))),
                "latency_ms": body.get("latency_ms", 0),
                "cost_estimate_usd": body.get("cost_estimate_usd", 0),
                "notes": body.get("notes", ""),
                "would_use_again": body.get("would_use_again", False),
                "contributor": body.get("contributor", "anonymous"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if not entry["model"]:
                self._json({"error": "Need 'model'"}, 400)
                return
            feedback = _load_feedback()
            feedback.append(entry)
            _save_feedback(feedback)
            self._json({"ok": True, "id": entry["id"]})
            return

        if path == "/feedback/stats" and method == "GET":
            self._json(_compute_feedback_stats())
            return

        if len(parts) == 2 and parts[0] == "feedback" and method == "GET":
            model = parts[1]
            feedback = _load_feedback()
            filtered = [f for f in feedback if f.get("model") == model]
            self._json(sorted(filtered, key=lambda f: f.get("timestamp", ""), reverse=True))
            return

        # ── Auto-Theory ──
        if path == "/auto-theory" and method == "POST":
            result = _auto_generate_theory()
            if isinstance(result, tuple):
                self._json(result[0], result[1])
            else:
                self._json(result)
            return

        # ── Sync ──
        if path == "/sync/export" and method == "POST":
            self._json(_sync_export())
            return

        if path == "/sync/import" and method == "POST":
            body = self._read_body()
            result = _sync_import(body)
            # Save snapshot for future diffs
            _save("last_import.json", body)
            self._json({"ok": True, **result})
            return

        if path == "/sync/diff" and method == "GET":
            self._json(_sync_diff())
            return

        # ── Models ──
        if path == "/models" and method == "GET":
            providers = _load_providers()
            all_models = []
            for pname, pconf in providers.items():
                for mname, minfo in pconf.get("models", {}).items():
                    entry = {"model": mname, "provider": pname}
                    # Skip internal _ fields
                    for k, v in minfo.items():
                        if not k.startswith("_"):
                            entry[k] = v
                    lessons = _load("lessons.json", [])
                    model_lessons = [l for l in lessons if l.get("model") == mname]
                    if model_lessons:
                        ratings = [l.get("rating", 0) for l in model_lessons]
                        entry["community_rating"] = round(sum(ratings) / len(ratings), 1)
                        entry["lesson_count"] = len(model_lessons)
                    all_models.append(entry)
            self._json(all_models)
            return

        if len(parts) == 2 and parts[0] == "models" and method == "GET":
            providers = _load_providers()
            pname = parts[1]
            if pname not in providers:
                self._json({"error": f"Provider '{pname}' not found"}, 404)
                return
            pconf = providers[pname]
            models = [{"model": m, **{k: v for k, v in info.items() if not k.startswith("_")}} for m, info in pconf.get("models", {}).items()]
            self._json({"provider": pname, "models": models})
            return

        if len(parts) >= 3 and parts[0] == "models" and method == "GET":
            providers = _load_providers()
            pname, mname = parts[1], "/".join(parts[2:])
            pconf = providers.get(pname)
            if not pconf:
                self._json({"error": f"Provider '{pname}' not found"}, 404)
                return
            minfo = pconf.get("models", {}).get(mname)
            if not minfo:
                self._json({"error": f"Model '{mname}' not found in provider '{pname}'"}, 404)
                return
            lessons = _load("lessons.json", [])
            model_lessons = [l for l in lessons if l.get("model") == mname]
            clean_info = {k: v for k, v in minfo.items() if not k.startswith("_")}
            result = {"model": mname, "provider": pname, **clean_info, "lessons": model_lessons}
            if model_lessons:
                ratings = [l.get("rating", 0) for l in model_lessons]
                result["community_rating"] = round(sum(ratings) / len(ratings), 1)
            self._json(result)
            return

        if path == "/models" and method == "POST":
            body = self._read_body()
            providers = _load_providers()
            pname = body.get("provider", "")
            mname = body.get("model", "")
            if not pname or not mname:
                self._json({"error": "Need 'provider' and 'model'"}, 400)
                return
            if pname not in providers:
                providers[pname] = {"base_url": body.get("base_url", ""),
                                     "api_key_env": body.get("api_key_env", ""), "models": {}}
            providers[pname]["models"][mname] = {
                "type": body.get("type", "general"),
                "tier": body.get("tier", "medium"),
                "context": body.get("context", 4096),
            }
            _save("providers.json", providers)
            self._json({"ok": True, "model": mname, "provider": pname})
            return

        # ── Chat completions ──
        if path == "/v1/chat/completions" and method == "POST":
            body = self._read_body()
            data, code = _chat_completion(
                body.get("model", ""), body.get("messages", []),
                temperature=body.get("temperature", 0.7),
                max_tokens=body.get("max_tokens", 1024),
                stream=body.get("stream", False),
            )
            self._json(data, code)
            return

        # ── MCP tools ──
        if path == "/mcp/tools" and method == "GET":
            tools = [{"name": name, **spec} for name, spec in MCP_TOOLS.items()]
            self._json({"tools": tools})
            return

        if len(parts) >= 3 and parts[0] == "mcp" and parts[1] == "tool" and method == "POST":
            tool_name = parts[2]
            args = self._read_body()
            result, code = _execute_mcp_tool(tool_name, args)
            self._json(result, code)
            return

        # ── Lessons ──
        if path == "/lessons" and method == "POST":
            body = self._read_body()
            lesson = {
                "id": str(uuid.uuid4())[:8],
                "model": body.get("model", ""),
                "prompt": body.get("prompt", ""),
                "what_worked": body.get("what_worked", ""),
                "what_didnt": body.get("what_didnt", ""),
                "tips": body.get("tips", ""),
                "rating": min(5, max(1, body.get("rating", 3))),
                "contributor": body.get("contributor", "anonymous"),
                "tool": body.get("tool", "general"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            lessons = _load("lessons.json", [])
            lessons.append(lesson)
            _save("lessons.json", lessons)
            self._json({"ok": True, "id": lesson["id"]})
            return

        if path == "/lessons" and method == "GET":
            lessons = _load("lessons.json", [])
            self._json(sorted(lessons, key=lambda l: l.get("timestamp", ""), reverse=True))
            return

        if len(parts) >= 2 and parts[0] == "lessons" and method == "GET":
            model = "/".join(parts[1:])
            if model == "best":
                lessons = _load("lessons.json", [])
                best = sorted(lessons, key=lambda l: l.get("rating", 0), reverse=True)[:20]
                self._json(best)
                return
            lessons = _load("lessons.json", [])
            filtered = [l for l in lessons if l.get("model") == model]
            self._json(filtered)
            return

        # ── Newspaper / Digest ──
        if path == "/newspaper" and method == "GET":
            self._text(_render_newspaper())
            return

        if path == "/digest" and method == "GET":
            self._json(_render_digest())
            return

        # ── Providers ──
        if path == "/providers" and method == "GET":
            providers = _load_providers()
            safe = {}
            for name, conf in providers.items():
                safe[name] = {"base_url": conf.get("base_url", ""),
                              "api_key_env": conf.get("api_key_env", ""),
                              "model_count": len(conf.get("models", {}))}
            self._json(safe)
            return

        if path == "/providers" and method == "POST":
            body = self._read_body()
            providers = _load_providers()
            name = body.get("name", "")
            if not name:
                self._json({"error": "Need 'name'"}, 400)
                return
            providers[name] = {
                "base_url": body.get("base_url", ""),
                "api_key_env": body.get("api_key_env", ""),
                "models": body.get("models", {}),
            }
            _save("providers.json", providers)
            self._json({"ok": True})
            return

        if path == "/providers/test" and method == "POST":
            body = self._read_body()
            providers = _load_providers()
            name = body.get("provider", "")
            pconf = providers.get(name)
            if not pconf:
                self._json({"error": f"Provider '{name}' not found"}, 404)
                return
            api_key = _get_api_key(pconf)
            if not api_key:
                self._json({"error": f"No API key set. Set {pconf.get('api_key_env', '?')}"}, 401)
                return
            base_url = pconf["base_url"].rstrip("/")
            try:
                req = Request(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"})
                resp = urlopen(req, timeout=10)
                models_data = json.loads(resp.read())
                self._json({"ok": True, "provider": name, "available_models": len(models_data.get("data", []))})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 502)
            return

        self._json({"error": "Not found", "path": path}, 404)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")


def main():
    # Ensure data dir
    os.makedirs(DATA_DIR, exist_ok=True)

    # Seed data files
    for name in ["lessons.json", "benchmarks.json", "interactions.json", "theories.json", "feedback.json"]:
        if not os.path.exists(_path(name)):
            _save(name, [])

    # Copy root providers.json to data/ if not already there
    data_providers = _path("providers.json")
    root_providers = os.path.join(DIR, "providers.json")
    if not os.path.exists(data_providers) and os.path.exists(root_providers):
        import shutil
        shutil.copy2(root_providers, data_providers)

    # Seed theories
    seeded = _ensure_theories_seeded()
    if seeded:
        print("🌱 Seeded 5 built-in Seed-2.0-Mini theories")

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"📰 Model Field Guide v2 running on http://0.0.0.0:{PORT}")
    print(f"   Theories: GET/POST /theories, GET /theories/best, POST /theories/{{id}}/endorse|challenge")
    print(f"   Feedback: POST /feedback, GET /feedback/stats")
    print(f"   Auto-Theory: POST /auto-theory")
    print(f"   Sync: POST /sync/export, POST /sync/import, GET /sync/diff")
    print(f"   Newspaper: GET /newspaper | Digest: GET /digest")
    print(f"   Models: GET /models | Chat: POST /v1/chat/completions")
    print(f"   MCP Tools: GET /mcp/tools, POST /mcp/tool/{{name}}")
    print(f"   Lessons: POST /lessons, GET /lessons")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down.")
        server.shutdown()

if __name__ == "__main__":
    main()
