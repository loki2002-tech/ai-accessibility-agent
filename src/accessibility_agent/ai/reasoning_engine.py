"""
AI Reasoning Engine.

Takes validated Finding objects (from axe-core / keyboard tests) and enriches
them with:
  1. Root cause analysis
  2. Plain English descriptions
  3. Developer remediation code
  4. Manual review resolution (LIKELY_VIOLATION / LIKELY_FALSE_POSITIVE)

IMPORTANT: This module NEVER creates new findings. It only ENRICHES existing ones.
The AI cannot add or remove findings — only explain and classify them.
All enriched fields are clearly marked as AI-Assisted in the schema.
"""

from __future__ import annotations

import json
import re
from typing import Any

from accessibility_agent.ai.llm_client import BaseLLMClient, create_llm_client
from accessibility_agent.ai.prompts import (
    SYSTEM_PROMPT,
    build_manual_review_prompt,
    build_reasoning_prompt,
)
from accessibility_agent.logging_config import get_logger
from accessibility_agent.wcag.schemas import (
    DetectionMethod,
    Finding,
    FindingStatus,
    RemediationGuidance,
)

log = get_logger(__name__)


def _extract_json(text: str) -> dict[str, Any] | None:
    """
    Safely extract a JSON object from an LLM response.
    LLMs sometimes wrap JSON in markdown code blocks — we handle that.
    """
    # Remove markdown code fences if present
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()

    # Try direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Try to find the first {...} block
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    log.warning("reasoning_engine.json_parse_failed", raw=text[:200])
    return None


class ReasoningEngine:
    """
    Enriches findings with AI reasoning.

    Usage:
        engine = ReasoningEngine()
        enriched = await engine.enrich_findings(findings)
    """

    def __init__(self, llm_client: BaseLLMClient | None = None) -> None:
        self._llm = llm_client or create_llm_client()
        log.info("reasoning_engine.initialized", provider=self._llm.provider_name)

    @property
    def is_enabled(self) -> bool:
        return self._llm.provider_name != "disabled"

    async def enrich_findings(self, findings: list[Finding]) -> list[Finding]:
        """
        Main entry point. Enriches all confirmed and manual-review findings.
        Returns the same list with enriched fields in-place.
        """
        if not self.is_enabled:
            log.info("reasoning_engine.skipped", reason="LLM provider is disabled")
            return findings

        confirmed = [f for f in findings if f.status == FindingStatus.CONFIRMED and not f.duplicate_of]
        manual = [f for f in findings if f.status == FindingStatus.REQUIRES_MANUAL_REVIEW and not f.duplicate_of]

        log.info("reasoning_engine.starting",
                 confirmed_count=len(confirmed),
                 manual_review_count=len(manual))

        # Enrich confirmed violations with root cause + remediation
        for finding in confirmed:
            await self._enrich_confirmed(finding)

        # Attempt to resolve manual review items
        for finding in manual:
            await self._resolve_manual_review(finding)

        log.info("reasoning_engine.complete", total_enriched=len(confirmed) + len(manual))
        return findings

    async def _enrich_confirmed(self, finding: Finding) -> None:
        """Enrich a CONFIRMED finding with root cause and remediation."""
        log.debug("reasoning_engine.enriching", finding_id=finding.finding_id, rule=finding.rule_id)

        prompt = build_reasoning_prompt(finding)
        response = await self._llm.generate(prompt=prompt, system=SYSTEM_PROMPT)

        if not response:
            return

        data = _extract_json(response.text)
        if not data:
            return

        # Update finding fields from AI response
        finding.root_cause = data.get("root_cause", "")
        finding.ai_reasoning = data.get("reasoning_notes", "")
        finding.detection_method = DetectionMethod.AI_ASSISTED

        # Update plain-English description if provided
        plain = data.get("plain_english", "")
        if plain:
            finding.description = plain  # Replace technical description

        # Populate remediation guidance
        finding.remediation = RemediationGuidance(
            summary=data.get("root_cause", ""),
            html_fix=data.get("html_fix", ""),
            aria_fix=data.get("aria_fix", ""),
            testing_guidance=data.get("testing_guidance", ""),
        )

        # Update confidence
        ai_confidence = data.get("confidence", 1.0)
        finding.confidence = min(ai_confidence, finding.confidence)  # Never increase deterministic confidence

        log.info("reasoning_engine.enriched_confirmed",
                 finding_id=finding.finding_id,
                 has_fix=bool(finding.remediation.html_fix))

    async def _resolve_manual_review(self, finding: Finding) -> None:
        """Use AI to determine if a manual-review finding is a real violation."""
        log.debug("reasoning_engine.resolving_manual", finding_id=finding.finding_id, rule=finding.rule_id)

        prompt = build_manual_review_prompt(finding)
        response = await self._llm.generate(prompt=prompt, system=SYSTEM_PROMPT)

        if not response:
            return

        data = _extract_json(response.text)
        if not data:
            return

        verdict = data.get("verdict", "CANNOT_DETERMINE")
        confidence = float(data.get("confidence", 0.5))

        log.info("reasoning_engine.manual_review_resolved",
                 finding_id=finding.finding_id,
                 verdict=verdict,
                 confidence=confidence)

        # Update the finding based on verdict
        if verdict == "LIKELY_VIOLATION":
            finding.status = FindingStatus.LIKELY
            finding.root_cause = data.get("root_cause", "")
            finding.ai_reasoning = data.get("reasoning", "")
            finding.confidence = confidence
            finding.detection_method = DetectionMethod.AI_ASSISTED
            plain = data.get("plain_english", "")
            if plain:
                finding.description = plain
            html_fix = data.get("html_fix", "")
            if html_fix:
                finding.remediation = RemediationGuidance(
                    summary=data.get("root_cause", ""),
                    html_fix=html_fix,
                )

        elif verdict == "LIKELY_FALSE_POSITIVE":
            finding.status = FindingStatus.PASS
            finding.ai_reasoning = (
                f"[AI-Assisted] Classified as likely false positive. "
                f"Reasoning: {data.get('reasoning', 'No reasoning provided.')}"
            )
            finding.confidence = confidence
            finding.detection_method = DetectionMethod.AI_ASSISTED

        else:  # CANNOT_DETERMINE — keep as manual review with AI notes
            finding.ai_reasoning = (
                f"[AI-Assisted] Could not determine conclusively. "
                f"Reasoning: {data.get('reasoning', '')}"
            )
