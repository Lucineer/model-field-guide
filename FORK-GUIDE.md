# 🍴 Fork Guide — How to Be a Good Contributor

## The Workflow

```
Fork → Clone → Run → Explore → Log Lessons → Push → PR upstream
```

1. **Fork** this repo on GitHub
2. **Clone** your fork locally
3. **Configure** API keys in your environment
4. **Run** `python3 field-guide.py`
5. **Explore** models via `/models`, `/v1/chat/completions`, MCP tools
6. **Log** what you learn via `POST /lessons` or edit `data/lessons.json`
7. **Push** your lessons to your fork
8. **PR** back upstream if you found something worth sharing

## Lesson Format

Lessons go in `data/lessons.json`. Each lesson:

```json
{
  "id": "abc12345",
  "model": "microsoft/phi-4",
  "prompt": "Write a PID controller for temperature regulation",
  "what_worked": "Specified units, constraints upfront. temp=0.3 for deterministic output.",
  "what_didnt": "Creative temp killed the math. Vague prompts produced unstable controllers.",
  "tips": "For control systems: specify units, ranges, and stability constraints explicitly.",
  "rating": 4,
  "contributor": "your-handle",
  "tool": "constraint_solve",
  "timestamp": "2026-04-12T21:00:00Z"
}
```

### Required Fields
- `model` — exact model name (must match provider registry)
- `what_worked` — what you did that produced good results
- `rating` — 1-5 scale

### Recommended Fields
- `prompt` — the prompt pattern (anonymize sensitive data)
- `what_didnt` — what failed (equally valuable)
- `tips` — your actionable takeaway
- `tool` — which MCP tool you used (or "general")
- `contributor` — your handle
- `timestamp` — ISO 8601

## Benchmark Format

Benchmarks go in `data/benchmarks.json`:

```json
{
  "model": "Qwen/Qwen3-32B",
  "timestamp": "2026-04-12T21:00:00Z",
  "prompts": ["Explain X in one sentence", "Write a function to Y", "Compare A vs B"],
  "results": [
    {"prompt": "...", "latency_ms": 2100, "status": 200, "has_content": true}
  ],
  "avg_latency_ms": 2100.0,
  "success_rate": "3/3"
}
```

Run benchmarks via `POST /mcp/tool/benchmark` or log manually.

## Newspaper Etiquette

1. **Be specific.** "It was good" helps nobody. "Qwen3-32B at temp=0.7 with system prompt specifying JSON output produced valid JSON 95% of the time" helps everyone.

2. **Be honest.** Include failures. A 2-star lesson about what went wrong is more valuable than a 5-star lesson that omits context.

3. **Include model version and date.** Models change. "Hermes-3-405B in March 2026" is more useful than "Hermes" (which version? which month?).

4. **Anonymize.** Don't include proprietary prompts or sensitive data. Strip PII.

5. **One lesson, one insight.** Don't cram five tips into one lesson. Five focused lessons beat one vague one.

## Data File Specs

### `data/providers.json`
Provider configurations. API keys come from env vars (via `api_key_env`), never stored here.

```json
{
  "provider_name": {
    "base_url": "https://api.provider.com/v1",
    "api_key_env": "ENV_VAR_NAME",
    "models": {
      "model/name": {"type": "creative", "tier": "cheap", "context": 8192}
    }
  }
}
```

### `data/models.json`
Extended model registry (optional — models can live in providers.json).

### `data/lessons.json`
Array of lesson objects (see Lesson Format above).

### `data/benchmarks.json`
Array of benchmark results (see Benchmark Format above).

### `data/interactions.json`
Auto-generated interaction logs (last 100). **Not committed** (in .gitignore).

## Git Workflow

Use commit prefixes so the newspaper is easy to scan:

```bash
# Lesson learned
git commit -m "[LESSON] phi-4 excels at IoT simulation with structured prompts"

# Benchmark results
git commit -m "[BENCH] Qwen3-32B: 2.1s avg, 3/3 success rate"

# New model or provider
git commit -m "[MODEL] Added NousResearch/Hermes-3-Llama-3.1-405B to DeepInfra"

# Bug fix or improvement
git commit -m "[FIX] Handle timeout gracefully in benchmark tool"
```

## Pull Requests

When submitting PRs upstream:

- Include a summary of what you're contributing
- Lessons should have clear model names and actionable tips
- Benchmarks should include the model, prompts used, and results
- Keep PRs focused — one type of contribution per PR is ideal

The upstream maintainer will review for accuracy and merge valuable contributions into the main newspaper.
