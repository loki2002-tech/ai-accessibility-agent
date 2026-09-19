# AI Accessibility Testing Agent

A production-grade, deterministic-first, AI-assisted accessibility testing platform that combines browser automation (Playwright), deterministic rule evaluation (axe-core), and an AI reasoning layer for root-cause analysis, remediation, and evidence-driven WCAG 2.2 reporting.

## Core Principle

```
DETERMINISTIC TESTING FIRST
        +
    EVIDENCE
        +
AI REASONING SECOND
        +
HUMAN VALIDATION WHERE REQUIRED
```

The AI layer **never replaces** deterministic accessibility rules. It reasons over evidence produced by those rules.

## Architecture

```
User / CI
    ↓
Agent Orchestrator
    ↓
Test Planner
    ↓
Accessibility Test Engine
    ├── axe-core (deterministic)
    ├── DOM Analyzer
    ├── Accessibility Tree Analyzer
    ├── Keyboard / Focus Analyzer
    ├── Contrast Analyzer
    └── Evidence Collector
    ↓
Evidence Normalizer
    ↓
WCAG Mapping Engine
    ↓
AI Reasoning Layer
    ↓
Finding Validator (Pydantic schema enforcement)
    ↓
Deduplication & Correlation
    ↓
Report Generator (JSON / HTML / CSV)
    ↓
Human Review Workflow
```

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"
playwright install chromium

# Run a basic automated scan
a11y-agent scan --url "https://example.com" --mode automated

# Full audit
a11y-agent scan --url "https://example.com" --mode full --output ./reports/
```

## Testing Modes

| Mode | Description |
|------|-------------|
| `automated` | Deterministic axe-core scan |
| `keyboard` | Keyboard and focus-order testing |
| `semantic` | DOM and accessibility tree inspection |
| `visual` | Screenshot-based evidence collection |
| `interaction` | Dynamic content and state-change testing |
| `dynamic` | SPA route change and live region monitoring |
| `manual-assist` | Generate manual test procedures |
| `ai-analysis` | AI reasoning over collected evidence |
| `full` | Full audit orchestrating all modes |

## WCAG Coverage

- **WCAG 2.2** — Level A and AA (primary)
- Detections mapped to W3C ACT Rules where applicable
- Clear distinction between CONFIRMED, LIKELY, POSSIBLE, and REQUIRES_MANUAL_REVIEW

## Repository Structure

```
src/accessibility_agent/
├── agent/              # Orchestrator, planner, tools, memory
├── accessibility/      # Test engines (axe, dom, keyboard, focus, contrast)
├── wcag/               # SC mappings, Pydantic schemas, validators
├── evidence/           # Screenshot, DOM, AX tree capture
├── reporting/          # JSON, HTML, CSV generators
└── cli.py              # Typer CLI entry point

tests/
├── unit/
├── integration/
├── corpus/             # Known-pass / known-fail HTML fixtures
└── evaluation/         # Precision/recall measurement

config/
├── settings.yaml
└── prompts/

docs/
```

## Development

```bash
# Run tests
pytest

# Type check
mypy src/

# Lint
ruff check src/ tests/
```

## Security

- No credentials in logs, reports, or screenshots
- Configurable PII/secret redaction before LLM calls
- Browser contexts are isolated per scan run
- Session state stored encrypted (configurable)

## Disclaimer

This tool assists accessibility testing. A clean scan result **does not constitute WCAG conformance**. Human expert review is always required for full conformance determination.
