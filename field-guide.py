#!/usr/bin/env python3
"""Model Field Guide — a forkable model exploration & crowd-sourced improvement tool.

Pure Python stdlib, zero deps. HTTP API on port 9439.
"""

import json
import os
import sys
import time
import uuid
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

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
    """Load from data/providers.json first, else fall back to root providers.json."""
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
    """Find which provider hosts a given model."""
    providers = _load_providers()
    for pname, pconf in providers.items():
        if model in pconf.get("models", {}):
            return pname, pconf
    return None, None

def _get_api_key(provider_conf):
    env_var = provider_conf.get("api_key_env", "")
    return os.environ.get(env_var, "")

def _chat_completion(model, messages, temperature=0.7, max_tokens=1024, stream=False):
    """Route a chat completion to the correct provider."""
    pname, pconf = _provider_for_model(model)
    if not pconf:
        return {"error": f"Model '{model}' not found in any provider"}, 404

    api_key = _get_api_key(pconf)
    if not api_key:
        return {"error": f"No API key for provider '{pname}'. Set env var {pconf.get('api_key_env', '?')}"}, 401

    base_url = pconf["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"

    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
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

# ── MCP Tools ─────────────────────────────────────────────────────────────────

MCP_TOOLS = {
    "creative_ideation": {
        "description": "Brainstorm with any model — creative ideation mode",
        "params": ["model", "topic", "style (optional)"],
    },
    "code_generate": {
        "description": "Generate code with any model",
        "params": ["model", "language", "task", "context (optional)"],
    },
    "analyze": {
        "description": "Analyze text/data with any model",
        "params": ["model", "text", "analysis_type"],
    },
    "brainstorm": {
        "description": "Group ideation — generate many ideas fast",
        "params": ["model", "topic", "count (default 10)"],
    },
    "synthesize": {
        "description": "Combine multiple perspectives into one output",
        "params": ["model", "perspectives (list of texts)", "goal"],
    },
    "roleplay": {
        "description": "Character/conversation mode",
        "params": ["model", "character", "scenario", "input"],
    },
    "reverse_engineer": {
        "description": "Deconstruct a problem into components",
        "params": ["model", "problem", "depth (default medium)"],
    },
    "constraint_solve": {
        "description": "Solve within constraints",
        "params": ["model", "problem", "constraints (list)"],
    },
    "compare_models": {
        "description": "Run same prompt across multiple models, compare outputs",
        "params": ["models (list)", "prompt"],
    },
    "benchmark": {
        "description": "Latency/quality test a model with sample prompts",
        "params": ["model", "prompts (list, optional)"],
    },
}

def _build_mcp_messages(tool_name, args):
    """Build system+user messages for an MCP tool invocation."""
    prompts = {
        "creative_ideation": (
            "You are a creative ideation assistant. Generate diverse, unconventional ideas.",
            "Topic: {topic}\nStyle: {style}\n\nGenerate at least 5 creative ideas."
        ),
        "code_generate": (
            "You are an expert programmer. Generate clean, well-commented code.",
            "Language: {language}\nTask: {task}\nContext: {context}\n\nWrite the code."
        ),
        "analyze": (
            "You are an analytical assistant. Provide structured analysis.",
            "Analysis type: {analysis_type}\n\nText:\n{text}\n\nAnalyze this thoroughly."
        ),
        "brainstorm": (
            "You are a brainstorming assistant. Generate many ideas quickly.",
            "Topic: {topic}\n\nGenerate {count} distinct ideas. Be creative and varied."
        ),
        "synthesize": (
            "You are a synthesis assistant. Combine multiple perspectives into one coherent output.",
            "Perspectives:\n{perspectives}\n\nGoal: {goal}\n\nSynthesize these into a unified view."
        ),
        "roleplay": (
            "You are roleplaying as {character}. Stay in character at all times.",
            "Scenario: {scenario}\nInput: {input}\n\nRespond in character."
        ),
        "reverse_engineer": (
            "You are a systems thinker. Deconstruct problems into their components.",
            "Problem: {problem}\nDepth: {depth}\n\nBreak this down into components, dependencies, and failure modes."
        ),
        "constraint_solve": (
            "You are a constraint satisfaction expert. Find solutions within bounds.",
            "Problem: {problem}\nConstraints:\n{constraints}\n\nFind a solution that satisfies all constraints."
        ),
    }
    spec = prompts.get(tool_name)
    if not spec:
        return None
    sys_prompt, user_tpl = spec
    # Fill in defaults
    defaults = {"style": "any", "context": "none", "count": "10", "depth": "medium"}
    filled = {k: args.get(k, defaults.get(k, "")) for k in args}
    # Handle list fields
    for k in ["perspectives", "constraints"]:
        if isinstance(filled.get(k), list):
            filled[k] = "\n".join(f"- {item}" for item in filled[k])
    user_msg = user_tpl.format(**filled)
    return [{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_msg}]

def _execute_mcp_tool(name, args):
    """Execute an MCP tool. Returns (result, status_code)."""
    if name not in MCP_TOOLS:
        return {"error": f"Unknown tool: {name}"}, 404

    model = args.get("model", "")
    if not model:
        return {"error": "Missing required param: model"}, 400

    # Special handling for compare_models and benchmark
    if name == "compare_models":
        return _compare_models(args)
    if name == "benchmark":
        return _benchmark(args)

    messages = _build_mcp_messages(name, args)
    if not messages:
        return {"error": f"Could not build messages for tool '{name}'"}, 500

    return _chat_completion(model, messages,
                            temperature=args.get("temperature", 0.8),
                            max_tokens=args.get("max_tokens", 2048))

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
    # Save benchmark
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

def _render_newspaper():
    lessons = _load("lessons.json", [])
    benchmarks = _load("benchmarks.json", [])

    lines = []
    lines.append("══════════════════════════════════════")
    lines.append("📰 MODEL FIELD GUIDE — Today's Edition")
    lines.append("══════════════════════════════════════")
    lines.append("")

    # Lesson of the day (best recent)
    if lessons:
        best = max(lessons, key=lambda l: l.get("rating", 0))
        lines.append("⭐ LESSON OF THE DAY")
        lines.append(f"{best.get('model', '?')} + {best.get('tool', 'general')}")
        tip = best.get("tips", best.get("what_worked", ""))
        lines.append(f'"{tip}" — @{best.get("contributor", "anonymous")}')
        lines.append(f"Rating: {best.get('rating', '?')}/5")
        lines.append("")

    # Recent benchmarks
    recent_bench = [b for b in benchmarks if (datetime.now(timezone.utc) - datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))).days < 7]
    if recent_bench:
        lines.append("📊 RECENT BENCHMARKS")
        for b in recent_bench[-5:]:
            lines.append(f"  {b['model']}: {b['avg_latency_ms']}ms avg, {b['success_rate']} success")
        lines.append("")

    # Hot tips
    recent_lessons = [l for l in lessons if (datetime.now(timezone.utc) - datetime.fromisoformat(l["timestamp"].replace("Z", "+00:00"))).days < 7]
    if recent_lessons:
        lines.append("🔥 HOT TIPS (this week)")
        for l in recent_lessons[-8:]:
            tip = l.get("tips", l.get("what_worked", ""))[:80]
            lines.append(f'  - "{tip}" — @{l.get("contributor", "anonymous")}')
        lines.append("")

    if not lessons and not benchmarks:
        lines.append("No entries yet. Add a lesson with POST /lessons")
        lines.append("Run a benchmark with POST /mcp/tool/benchmark")

    return "\n".join(lines)

def _render_digest():
    lessons = _load("lessons.json", [])
    benchmarks = _load("benchmarks.json", [])
    providers = _load_providers()
    model_count = sum(len(p.get("models", {})) for p in providers.values())
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "providers": len(providers),
            "models": model_count,
            "total_lessons": len(lessons),
            "total_benchmarks": len(benchmarks),
        },
        "top_rated_lessons": sorted(lessons, key=lambda l: l.get("rating", 0), reverse=True)[:5],
        "recent_benchmarks": benchmarks[-5:] if benchmarks else [],
    }

# ── HTTP Handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Suppress default logging

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

        # ── Models ──
        if path == "/models" and method == "GET":
            providers = _load_providers()
            all_models = []
            for pname, pconf in providers.items():
                for mname, minfo in pconf.get("models", {}).items():
                    entry = {"model": mname, "provider": pname, **minfo}
                    # Add community rating if lessons exist
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
            # GET /models/{provider}
            providers = _load_providers()
            pname = parts[1]
            if pname not in providers:
                self._json({"error": f"Provider '{pname}' not found"}, 404)
                return
            pconf = providers[pname]
            models = [{"model": m, **info} for m, info in pconf.get("models", {}).items()]
            self._json({"provider": pname, "models": models})
            return

        if len(parts) >= 3 and parts[0] == "models" and method == "GET":
            # GET /models/{provider}/{model}
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
            # Add community data
            lessons = _load("lessons.json", [])
            model_lessons = [l for l in lessons if l.get("model") == mname]
            result = {"model": mname, "provider": pname, **minfo, "lessons": model_lessons}
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
                body.get("model", ""),
                body.get("messages", []),
                temperature=body.get("temperature", 0.7),
                max_tokens=body.get("max_tokens", 1024),
                stream=body.get("stream", False),
            )
            self._json(data, code)
            return

        # ── MCP tools ──
        if path == "/mcp/tools" and method == "GET":
            tools = []
            for name, spec in MCP_TOOLS.items():
                tools.append({"name": name, **spec})
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

        # ── Newspaper ──
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
                req = Request(f"{base_url}/models",
                              headers={"Authorization": f"Bearer {api_key}"})
                resp = urlopen(req, timeout=10)
                models_data = json.loads(resp.read())
                self._json({"ok": True, "provider": name,
                            "available_models": len(models_data.get("data", []))})
            except Exception as e:
                self._json({"ok": False, "error": str(e)}, 502)
            return

        # ── Root ──
        if path == "/" and method == "GET":
            self._text("📰 Model Field Guide — POST /lessons, GET /newspaper, GET /models\n")
            return

        self._json({"error": "Not found", "path": path}, 404)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")


def main():
    # Seed data files if they don't exist
    for name in ["lessons.json", "benchmarks.json", "interactions.json"]:
        p = _path(name)
        if not os.path.exists(p):
            _save(name, [] if name != "providers.json" else {})

    # Copy root providers.json to data/ if not already there
    data_providers = _path("providers.json")
    root_providers = os.path.join(DIR, "providers.json")
    if not os.path.exists(data_providers) and os.path.exists(root_providers):
        import shutil
        shutil.copy2(root_providers, data_providers)

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"📰 Model Field Guide running on http://0.0.0.0:{PORT}")
    print(f"   Models: GET /models")
    print(f"   Lessons: POST /lessons, GET /lessons")
    print(f"   Newspaper: GET /newspaper")
    print(f"   Chat: POST /v1/chat/completions")
    print(f"   MCP Tools: GET /mcp/tools, POST /mcp/tool/{{name}}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down.")
        server.shutdown()

if __name__ == "__main__":
    main()
