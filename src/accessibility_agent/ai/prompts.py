"""
Prompt Templates for AI Accessibility Reasoning.

Rules for all prompts:
1. Always ground the AI in WCAG 2.2 — never let it invent rules.
2. Always instruct the AI to cite specific evidence it used.
3. Always ask for structured JSON output for reliable parsing.
4. Always include an explicit "do not hallucinate" instruction.
5. Keep prompts under 4000 tokens to avoid excessive cost.
"""

from __future__ import annotations

from accessibility_agent.wcag.schemas import Finding


SYSTEM_PROMPT = """You are a senior WCAG 2.2 accessibility engineer with 15 years of experience.
Your job is to analyse accessibility findings detected by automated tools and provide:
- Accurate root cause analysis based on EVIDENCE ONLY
- Developer-ready remediation code
- Plain English explanations for non-technical stakeholders

CRITICAL RULES you must NEVER violate:
1. Only reference WCAG 2.2 success criteria that actually exist (1.1.1 through 4.1.3).
2. Base ALL conclusions on the provided DOM evidence and tool output — never guess.
3. If you are uncertain, say so explicitly. Never fabricate.
4. Always label your reasoning as "AI-Assisted" — it is supplementary, not definitive.
5. Return ONLY valid JSON in the format specified — no markdown, no explanation outside JSON.
"""


def build_reasoning_prompt(finding: Finding) -> str:
    """
    Build the full reasoning prompt for a single finding.
    Includes: rule ID, WCAG reference, DOM HTML, failure summary, selector.
    """
    # Extract the most useful evidence (tool_output from axe)
    tool_evidence = ""
    for ev in finding.evidence:
        if ev.evidence_type == "tool_output":
            tool_evidence = ev.data[:1500]  # Truncate to save tokens
            break

    prompt = f"""Analyse the following accessibility finding detected by axe-core on the page: {finding.url}

## Finding Details
- Rule ID: {finding.rule_id}
- WCAG Success Criterion: {finding.wcag.success_criterion} — {finding.wcag.title} (Level {finding.wcag.level.value})
- Current Status: {finding.status.value}
- Automated Description: {finding.description}
- Actual Problem Observed: {finding.actual_result}
- What WCAG Expects: {finding.expected_result}
- Affected Element (CSS Selector): {finding.element.selector}
- Element HTML: {finding.element.html[:500] if finding.element.html else 'Not available'}

## Raw Tool Evidence (axe-core output)
{tool_evidence if tool_evidence else 'No raw tool evidence available.'}

## Your Task
Return a JSON object with EXACTLY these fields and no others:

{{
  "root_cause": "A single clear sentence explaining WHY this bug exists in the code.",
  "plain_english": "A 1-2 sentence explanation a non-technical manager could understand.",
  "html_fix": "The corrected HTML snippet the developer should use. Be specific and complete.",
  "aria_fix": "Any ARIA attributes to add/remove (empty string if none needed).",
  "testing_guidance": "How a developer can verify their fix is correct (1-2 sentences).",
  "confidence": 0.0,
  "reasoning_notes": "Brief notes on evidence used and any uncertainty."
}}

The "confidence" field must be a number between 0.0 (very uncertain) and 1.0 (highly certain).
Base confidence on how much evidence is available and how clear the violation is.
"""
    return prompt


def build_manual_review_prompt(finding: Finding) -> str:
    """
    Build a prompt for the AI to decide if a manual-review finding is a real bug.
    """
    tool_evidence = ""
    for ev in finding.evidence:
        if ev.evidence_type in ("tool_output", "computed_style"):
            tool_evidence = ev.data[:1200]
            break

    prompt = f"""An automated accessibility scanner flagged the following element for MANUAL REVIEW.
It was UNABLE to automatically determine if this is a real accessibility violation or a false positive.

## Page: {finding.url}
## WCAG Criterion: {finding.wcag.success_criterion} — {finding.wcag.title} (Level {finding.wcag.level.value})
## Rule: {finding.rule_id}
## Automated Message: {finding.description}
## Affected Element: {finding.element.selector}
## Element HTML: {finding.element.html[:400] if finding.element.html else 'Not available'}

## Raw Evidence
{tool_evidence if tool_evidence else 'No raw tool evidence available.'}

## Your Task
Determine if this is likely a real accessibility violation or a false positive.

Return a JSON object with EXACTLY these fields:

{{
  "verdict": "LIKELY_VIOLATION" or "LIKELY_FALSE_POSITIVE" or "CANNOT_DETERMINE",
  "confidence": 0.0,
  "reasoning": "Explain what evidence led to your verdict.",
  "root_cause": "If LIKELY_VIOLATION: why does this fail? If false positive: why is it actually OK?",
  "html_fix": "If LIKELY_VIOLATION: the corrected HTML. Otherwise empty string.",
  "plain_english": "1-2 sentence plain English explanation for a manager."
}}

"confidence" must be between 0.0 and 1.0. Use lower values when evidence is ambiguous.
"""
    return prompt
