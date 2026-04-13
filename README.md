# 📰 Model Field Guide v2

> A forkable model exploration tool with **theory-sharing**, feedback loops, and crowd-sourced knowledge.
> Every fork contributes, everyone benefits.

## What Is This?

Model Field Guide is a local HTTP server that lets you:

- **Explore models** from DeepInfra, DeepSeek, and any OpenAI-compatible provider
- **Run prompts** against any model via an OpenAI-compatible API (`/v1/chat/completions`)
- **Execute MCP tools** — creative ideation, code generation, analysis, benchmarks, model comparison
- **Log lessons** — what worked, what didn't, tips, ratings
- **Submit & test theories** — working hypotheses about model usage, endorsed or challenged by the community
- **Track feedback** — structured usage data with aggregated stats per model
- **Auto-generate theories** from feedback patterns
- **Sync across forks** — export/import theories, feedback, and lessons
- **Read the newspaper** — a formatted digest of everything at `/newspaper`

Think of it as a **living scientific journal** for AI models. You fork this repo, run models, form theories, test them, share results. Knowledge compounds.

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/model-field-guide.git
cd model-field-guide

export DEEPINFRA_API_KEY="sk-..."
export DEEPSEEK_API_KEY="sk-..."

python3 field-guide.py
```

Server starts on `http://localhost:9439` with **5 pre-loaded theories** about Seed-2.0-Mini.

```bash
# Read the newspaper (includes Theory of the Week, Model Leaderboard, Active Experiments)
curl http://localhost:9439/newspaper

# List all theories
curl http://localhost:9439/theories

# Submit a theory
curl -X POST http://localhost:9439/theories -H 'Content-Type: application/json' -d '{
  "model": "ByteDance/Seed-2.0-mini",
  "task_type": "ideation",
  "theory": "At temperature 0.85, Seed-2.0-Mini produces the best balance of creativity and coherence",
  "evidence": "Tested on 30 tasks, 0.85 rated best for useful creativity",
  "temperature": 0.85,
  "confidence": 0.85,
  "contributor": "your-handle",
  "tags": ["creative", "temperature"]
}'

# Endorse a theory
curl -X POST http://localhost:9439/theories/seed-divergent-thinking/endorse -H 'Content-Type: application/json' -d '{
  "contributor": "your-handle",
  "note": "Confirmed! Used for brainstorming and got 4 novel ideas out of 5 attempts."
}'

# Log feedback after using a model
curl -X POST http://localhost:9439/feedback -H 'Content-Type: application/json' -d '{
  "model": "ByteDance/Seed-2.0-mini",
  "task": "ideation",
  "temperature": 0.85,
  "result_quality": 4,
  "latency_ms": 1200,
  "cost_estimate_usd": 0.0003,
  "would_use_again": true,
  "contributor": "your-handle"
}'

# Get aggregated stats
curl http://localhost:9439/feedback/stats

# Auto-generate a theory from feedback
curl -X POST http://localhost:9439/auto-theory
```

## Why Seed-2.0-Mini?

Our biggest surprise finding: **the cheapest model is often the most useful**.

Seed-2.0-Mini costs ~$0.0003 per call (10x cheaper than Hermes-3-405B), but for ideation tasks it consistently outperforms expensive models — *if you use it correctly*.

The key insights:
1. **Never ask for one answer.** Always ask for 3-5 options. Individual quality is moderate, but diversity is exceptional.
2. **Temperature 0.85 is the sweet spot.** Creative enough to surprise, coherent enough to use.
3. **It's a divergent thinker, not a convergent one.** Use it for brainstorming, then hand off to a stronger model for evaluation.
4. **It's the best first model in a chain.** Brainstorm → Seed-2.0-Mini, Evaluate → DeepSeek-chat, Refine → Qwen3.5-397B.

This 3-stage pipeline costs less than $0.002 per task and outperforms any single model alone.

## The Chain-of-Models Pattern

The most powerful workflow we've found:

```
Stage 1: BREADTH (Seed-2.0-Mini, $0.0003)
  → Generate 5 diverse options
  
Stage 2: EVALUATION (DeepSeek-chat, $0.001)
  → Rate each option, pick the best
  
Stage 3: REFINEMENT (Qwen3.5-397B, $0.001)
  → Polish the winner into final output

Total: ~$0.002 — cheaper and better than one expensive call
```

**When to use it:** Any creative task, research synthesis, problem-solving, or anything where "the first idea isn't the best idea."

## Theory System

Theories are the core knowledge-sharing mechanism. Each theory is a testable claim about how to use a model effectively.

### Submitting a Theory
```bash
POST /theories
{
  "model": "model-name",
  "task_type": "ideation|code_review|analysis|creative|reasoning",
  "theory": "Your testable claim",
  "evidence": "What data supports this",
  "temperature": 0.85,
  "prompt_pattern": "The prompt template that works",
  "confidence": 0.0-1.0,
  "tags": ["relevant", "tags"]
}
```

### The Scientific Method for Model Usage
1. **Observe** — use models, notice patterns
2. **Hypothesize** — submit a theory (POST /theories)
3. **Test** — others try it and endorse or challenge
4. **Evolve** — theories gain/lose confidence based on evidence
5. **Share** — export via sync, commit to fork

### Endorsing & Challenging
- **Endorse** (POST /theories/{id}/endorse) — "I tried this and it works"
- **Challenge** (POST /theories/{id}/challenge) — "Here's counter-evidence"
- Endorsements bump confidence +0.02, challenges drop it -0.03
- View full evolution at GET /theories/{id}/evolution

## Cost-Effectiveness Leaderboard

Based on feedback data, the leaderboard ranks models by **quality per dollar**:

| Rank | Model | Avg Quality | Cost/Call | Efficiency |
|------|-------|-------------|-----------|------------|
| 🥇 | Seed-2.0-Mini | 4.2 | $0.0003 | 14,000 |
| 🥈 | phi-4 | 3.8 | $0.0005 | 7,600 |
| 🥉 | DeepSeek-chat | 4.0 | $0.001 | 4,000 |
| 4 | Qwen3-32B | 4.1 | $0.002 | 2,050 |
| 5 | Hermes-3-70B | 4.3 | $0.005 | 860 |

*Efficiency = quality / cost. Higher is better. Data from community feedback.*

## Endpoints

### Theories
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/theories` | GET | All theories, sorted by confidence |
| `/theories` | POST | Submit a new theory |
| `/theories/best` | GET | Top 10 highest-confidence theories |
| `/theories/{model}` | GET | Theories for a specific model |
| `/theories/{task_type}` | GET | Theories for a task type |
| `/theories/{id}/endorse` | POST | Endorse a theory |
| `/theories/{id}/challenge` | POST | Challenge a theory |
| `/theories/{id}/evolution` | GET | Theory's endorsement/challenge history |

### Feedback
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/feedback` | POST | Log model usage feedback |
| `/feedback/{model}` | GET | All feedback for a model |
| `/feedback/stats` | GET | Aggregated stats per model |

### Auto-Theory & Sync
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auto-theory` | POST | Auto-generate theory from feedback patterns |
| `/sync/export` | POST | Export all data as JSON |
| `/sync/import` | POST | Import theories from another fork |
| `/sync/diff` | GET | Diff against last import |

### Everything Else
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Status & links |
| `/models` | GET | All known models |
| `/models/{provider}` | GET | Models for a provider |
| `/models/{provider}/{model}` | GET | Model details + ratings |
| `/models` | POST | Add a model |
| `/v1/chat/completions` | POST | OpenAI-compatible chat |
| `/mcp/tools` | GET | List MCP tools |
| `/mcp/tool/{name}` | POST | Execute an MCP tool |
| `/lessons` | GET/POST | List/submit lessons |
| `/lessons/{model}` | GET | Lessons for a model |
| `/lessons/best` | GET | Top-rated lessons |
| `/newspaper` | GET | 📰 Formatted front page |
| `/digest` | GET | JSON summary |
| `/providers` | GET/POST | List/add providers |
| `/providers/test` | POST | Test a provider connection |

## Sync Workflow (Sharing Across Forks)

After using models for a week:

```bash
# Export everything
curl -X POST http://localhost:9439/sync/export > export.json

# Commit and push
git add export.json
git commit -m "[SYNC] Weekly theory & feedback export"
git push

# Other users pull and import
git pull
curl -X POST http://localhost:9439/sync/import -d @export.json
```

Check what's new: `GET /sync/diff`

## MCP Tools

- **creative_ideation** — Brainstorm with any model
- **code_generate** — Code with any model
- **analyze** — Analyze text/data
- **brainstorm** — Group ideation
- **synthesize** — Combine perspectives
- **roleplay** — Character mode
- **reverse_engineer** — Deconstruct problems
- **constraint_solve** — Solve within constraints
- **compare_models** — Run same prompt across multiple models
- **benchmark** — Latency/quality test

## Philosophy

**Knowledge compounds.** Every theory, every feedback entry, every lesson makes every fork better.

**Theories are scientific claims, not opinions.** They have evidence, confidence scores, and they evolve through endorsement and challenge.

**Cheap models are underrated.** The most expensive model isn't always the best. Sometimes 10 cheap calls beat 1 expensive one.

This runs on a Jetson Orin Nano. Zero dependencies. Pure Python. Fork it, run it, improve it.

## License

MIT
