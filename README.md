# 📰 Model Field Guide

> A forkable model exploration tool with crowd-sourced knowledge.
> Every fork contributes, everyone benefits.

## What Is This?

Model Field Guide is a local HTTP server that lets you:

- **Explore models** from DeepInfra, DeepSeek, and any OpenAI-compatible provider
- **Run prompts** against any model via an OpenAI-compatible API (`/v1/chat/completions`)
- **Execute MCP tools** — creative ideation, code generation, analysis, benchmarks, model comparison
- **Log lessons** — what worked, what didn't, tips, ratings
- **Read the newspaper** — a formatted digest of community knowledge at `/newspaper`

Think of it as a **living newspaper** for AI models. You fork this repo, run models, write down what you learn, and push. Others pull your lessons. Knowledge compounds.

## Quick Start

```bash
# Fork & clone
git clone https://github.com/YOUR_USERNAME/model-field-guide.git
cd model-field-guide

# Set API keys (never in code, only in env)
export DEEPINFRA_API_KEY="sk-..."
export DEEPSEEK_API_KEY="sk-..."

# Run
python3 field-guide.py
```

Server starts on `http://localhost:9439`.

```bash
# Read the newspaper
curl http://localhost:9439/newspaper

# List all models
curl http://localhost:9439/models

# Submit a lesson
curl -X POST http://localhost:9439/lessons -H 'Content-Type: application/json' -d '{
  "model": "ByteDance/Seed-2.0-mini",
  "prompt": "Write a creative brief for...",
  "what_worked": "temp=0.9, specify output format in system prompt",
  "what_didnt": "temp < 0.5 killed creativity",
  "tips": "Use system prompts that specify output format",
  "rating": 5,
  "contributor": "your-handle",
  "tool": "creative_ideation"
}'
```

## Endpoints

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
| `/lessons` | GET | All lessons (recent first) |
| `/lessons` | POST | Submit a lesson |
| `/lessons/{model}` | GET | Lessons for a model |
| `/lessons/best` | GET | Top-rated lessons |
| `/newspaper` | GET | 📰 Formatted front page |
| `/digest` | GET | JSON summary |
| `/providers` | GET | Configured providers |
| `/providers` | POST | Add a provider |
| `/providers/test` | POST | Test a provider connection |

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

## Contributing Lessons

The `data/` directory IS the newspaper. Add lessons via the API or by editing `data/lessons.json` directly:

```json
{
  "model": "microsoft/phi-4",
  "prompt": "Simulate a thermostat controller",
  "what_worked": "Structured output format, step-by-step reasoning",
  "what_didnt": "Asked for too many decimal places",
  "tips": "Phi-4 excels at edge/IoT simulation tasks",
  "rating": 4,
  "contributor": "jetsonclaw1",
  "tool": "constraint_solve",
  "timestamp": "2026-04-12T00:00:00Z"
}
```

**Good lessons are:**
- Concrete — specific model, specific prompt pattern
- Actionable — someone else can use your tip immediately
- Honest — include what didn't work too
- Dated — timestamps matter, models change

## Provider Setup

API keys live in environment variables, never in code or committed files:

```bash
export DEEPINFRA_API_KEY="sk-..."
export DEEPSEEK_API_KEY="sk-..."
```

Add custom providers at runtime:

```bash
curl -X POST http://localhost:9439/providers -H 'Content-Type: application/json' -d '{
  "name": "openrouter",
  "base_url": "https://openrouter.ai/api/v1",
  "api_key_env": "OPENROUTER_API_KEY"
}'
```

## Philosophy

**Knowledge compounds.** Every lesson makes every fork better. The more people run models and share what they learn, the smarter the entire network becomes.

This runs on a Jetson Orin Nano. Zero dependencies. Pure Python. Fork it, run it, improve it.

## License

MIT
