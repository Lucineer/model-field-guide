# 🍴 Fork Guide — How to Be a Good Contributor

## The Workflow

```
Fork → Clone → Run → Explore → Log Feedback → Form Theories → Push → PR upstream
```

1. **Fork** this repo on GitHub
2. **Clone** your fork locally
3. **Configure** API keys in your environment
4. **Run** `python3 field-guide.py`
5. **Explore** models via `/models`, `/v1/chat/completions`, MCP tools
6. **Log feedback** via `POST /feedback` after every model interaction
7. **Form theories** when you spot patterns (POST /theories)
8. **Endorse or challenge** others' theories (the scientific method)
9. **Export & push** your knowledge via `POST /sync/export`
10. **PR** back upstream if you found something worth sharing

## Submitting Theories

Theories are the heart of the knowledge-sharing system. A good theory is:

### Specific
❌ "Seed-2.0-Mini is good for creative stuff"
✅ "Seed-2.0-Mini at temperature 0.85 produces more novel ideas than DeepSeek-chat at 0.7 when asked for 5 options instead of 1"

### Testable
❌ "I think this model is underrated"
✅ "On 50 brainstorming tasks, Seed-2.0-Mini at temp 0.9 produced at least one novel option in 43/50 cases vs DeepSeek-chat's 31/50"

### With Evidence
❌ "It just works better"
✅ "Temperature 0.8-1.0 produces 3-5x more novel ideas than 0.3. Cost: $0.0003/call vs $0.003 for Hermes-3-405B"

### Submit via API
```bash
curl -X POST http://localhost:9439/theories -H 'Content-Type: application/json' -d '{
  "model": "ByteDance/Seed-2.0-mini",
  "task_type": "ideation",
  "theory": "Your specific, testable claim here",
  "evidence": "Your data supporting this claim",
  "temperature": 0.85,
  "prompt_pattern": "Generate 5 diverse approaches to [PROBLEM]. For each, explain tradeoffs.",
  "confidence": 0.85,
  "contributor": "your-handle",
  "tags": ["creative", "cheap", "ideation"]
}'
```

## Endorsing & Challenging Theories

This is the **scientific method for model usage**:

### Endorse (confirming a theory)
When you try someone's theory and it works:
```bash
curl -X POST http://localhost:9439/theories/{theory-id}/endorse -H 'Content-Type: application/json' -d '{
  "contributor": "your-handle",
  "note": "Tested on 10 brainstorming tasks. Confirmed: 8/10 produced at least one novel idea at temp 0.85."
}'
```

### Challenge (counter-evidence)
When a theory doesn't hold up for you:
```bash
curl -X POST http://localhost:9439/theories/{theory-id}/challenge -H 'Content-Type: application/json' -d '{
  "contributor": "your-handle",
  "evidence": "Tested on 20 code review tasks. Only 6/20 were useful — the theory seems limited to creative tasks only.",
  "note": "Theory should specify it only applies to ideation, not general use."
}'
```

### Track Evolution
```bash
curl http://localhost:9439/theories/{theory-id}/evolution
```

## The Feedback Loop

Log feedback after every meaningful model interaction:

```bash
curl -X POST http://localhost:9439/feedback -H 'Content-Type: application/json' -d '{
  "model": "ByteDance/Seed-2.0-mini",
  "task": "ideation",
  "prompt_pattern": "Generate 5 approaches to [X]",
  "temperature": 0.85,
  "max_tokens": 2000,
  "result_quality": 4,
  "latency_ms": 1200,
  "cost_estimate_usd": 0.0003,
  "notes": "Great for brainstorming. Weak on technical precision.",
  "would_use_again": true,
  "contributor": "your-handle"
}'
```

After accumulating 3+ feedback entries, you can auto-generate theories:
```bash
curl -X POST http://localhost:9439/auto-theory
```

Check aggregated stats anytime:
```bash
curl http://localhost:9439/feedback/stats
```

## Sync Workflow

### Export your knowledge
```bash
curl -X POST http://localhost:9439/sync/export > export.json
git add export.json
git commit -m "[SYNC] Weekly export — 12 theories, 47 feedback entries"
git push
```

### Import from others
```bash
git pull  # Get their export.json
curl -X POST http://localhost:9439/sync/import -d @export.json
```

### Check what changed
```bash
curl http://localhost:9439/sync/diff
```

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

## Theory Quality Guidelines

### ✅ Good Theories
- **Specific**: exact model, temperature, task type, prompt pattern
- **Testable**: someone else can reproduce your experiment
- **Evidence-backed**: include numbers, sample sizes, comparisons
- **Actionable**: includes a prompt pattern others can copy
- **Scoped**: says what it DOES and DOESN'T apply to

### ❌ Bad Theories
- **Vague**: "this model is pretty good"
- **Untestable**: "I have a feeling about this"
- **Overgeneralized**: applies to "everything" with no specifics
- **Unreplicable**: no prompt pattern, no temperature, no task type

### Confidence Scoring
- **0.9-1.0**: Well-tested, multiple confirmations, clear evidence
- **0.7-0.89**: Tested, some evidence, needs more confirmation
- **0.5-0.69**: Initial hypothesis, limited testing (auto-generated theories start here)
- **0.0-0.49**: Speculative, weak evidence, likely to change

## Newspaper Etiquette

1. **Be specific.** "It was good" helps nobody.
2. **Be honest.** Include failures. A challenged theory is more valuable than an untested one.
3. **Include model version and date.** Models change.
4. **Anonymize.** Don't include proprietary prompts or sensitive data.
5. **One theory, one insight.** Don't cram five claims into one theory.

## Data File Specs

### `data/providers.json`
Provider configurations. API keys come from env vars (via `api_key_env`), never stored here.

### `data/theories.json`
Array of theory objects with endorsements and challenges.

### `data/feedback.json`
Array of feedback entries with quality scores, costs, and latency.

### `data/lessons.json`
Array of lesson objects.

### `data/benchmarks.json`
Array of benchmark results.

### `data/interactions.json`
Auto-generated interaction logs (last 100). **Not committed** (in .gitignore).

### `data/last_import.json`
Snapshot of the last sync import, used for diff calculation.

## Git Workflow

Use commit prefixes:

```bash
git commit -m "[THEORY] Seed-2.0-Mini temp 0.85 is the ideation sweet spot"
git commit -m "[FEEDBACK] 47 entries this week, auto-generated 2 theories"
git commit -m "[LESSON] phi-4 excels at IoT simulation with structured prompts"
git commit -m "[SYNC] Weekly export — merged theories from 3 forks"
git commit -m "[BENCH] Qwen3-32B: 2.1s avg, 3/3 success rate"
git commit -m "[MODEL] Added new model to provider"
git commit -m "[FIX] Handle timeout gracefully in benchmark tool"
```

## Pull Requests

When submitting PRs upstream:
- Theories should have clear evidence and be testable
- Feedback entries should have complete data (quality, cost, latency)
- Keep PRs focused — one type of contribution per PR
- Include a summary of what you're contributing and why it matters
