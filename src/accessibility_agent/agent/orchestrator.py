"""
Scan Orchestrator — Version 0.1 (Automated Mode).

Coordinates the full scan pipeline for MODE 1: Automated Accessibility Scan.

Pipeline:
    1. Launch browser (BrowserController)
    2. Navigate to URL
    3. Capture initial evidence (screenshot, DOM, AX tree)
    4. Run axe-core deterministic scan (AxeEngine)
    5. Run additional deterministic checks (DOM analyzer)
    6. Deduplicate findings
    7. Finalize ScanResult
    8. Generate reports

This orchestrator is SYNCHRONOUS in its decision logic — it does not use an
AI agent loop yet (that is Version 0.4+).  It is designed to be the stable
core on which the AI layer is added without modifying this module.

Version: 0.1 — Deterministic only (no LLM calls)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from accessibility_agent.accessibility.axe_engine import AxeEngine
from accessibility_agent.accessibility.browser import BrowserController
from accessibility_agent.accessibility.deduplication import DeduplicationEngine
from accessibility_agent.config import settings
from accessibility_agent.evidence.collector import EvidenceCollector
from accessibility_agent.logging_config import get_logger
from accessibility_agent.reporting.generator import ReportGenerator
from accessibility_agent.wcag.schemas import ScanResult

log = get_logger(__name__)


class ScanOrchestrator:
    """
    Orchestrates a complete accessibility scan run.

    Usage:
        orchestrator = ScanOrchestrator(url="https://example.com", mode="automated")
        result = await orchestrator.run()
    """

    def __init__(
        self,
        url: str,
        mode: str = "automated",
        output_dir: Path | None = None,
        browser_type: str | None = None,
        headless: bool | None = None,
        viewport: tuple[int, int] | None = None,
        report_formats: list[str] | None = None,
    ) -> None:
        self.url = url
        self.mode = mode
        self._output_dir = output_dir or settings.report_dir
        self._report_formats = report_formats or settings.report_formats

        # Browser configuration overrides
        from accessibility_agent.config import BrowserType
        self._browser_type = BrowserType(browser_type) if browser_type else None
        self._headless = headless
        self._viewport_width = viewport[0] if viewport else None
        self._viewport_height = viewport[1] if viewport else None

    async def run(self) -> ScanResult:
        """
        Execute the full scan and return a validated ScanResult.

        The scan result is also persisted to disk as configured reports.
        """
        log.info("orchestrator.starting", url=self.url, mode=self.mode)
        settings.ensure_directories()

        result = ScanResult(url=self.url, scan_mode=self.mode)
        step = 0

        async with BrowserController(
            browser_type=self._browser_type,
            headless=self._headless,
            viewport_width=self._viewport_width,
            viewport_height=self._viewport_height,
        ) as browser:

            result.browser = browser.browser_type_name
            result.viewport = browser.viewport_string

            evidence_collector = EvidenceCollector(browser, result.run_id)
            axe_engine = AxeEngine(browser)
            dedup = DeduplicationEngine(settings.dedup_similarity_threshold)

            # ── Step 1: Navigate ───────────────────────────────────────────
            step += 1
            log.info("orchestrator.step", step=step, action="navigate", url=self.url)
            try:
                nav_info = await browser.navigate(self.url)
                page_title = nav_info.get("title", "")
                self._trace(result, step, "navigate", {"url": self.url}, nav_info)
            except Exception as exc:
                error_msg = f"Navigation failed: {exc}"
                log.error("orchestrator.navigate_failed", error=error_msg)
                result.errors.append(error_msg)
                result.finalize()
                return result

            # ── Step 2: Initial Evidence Capture ────────────────────────────
            step += 1
            log.info("orchestrator.step", step=step, action="capture_initial_evidence")

            initial_screenshot = await evidence_collector.capture_screenshot(
                label="initial_state",
                full_page=True,
            )
            dom_snapshot = await evidence_collector.capture_dom_snapshot(label="initial_state")
            ax_tree_snapshot = await evidence_collector.capture_ax_tree(label="initial_state")

            self._trace(result, step, "capture_evidence", {}, {
                "screenshot": initial_screenshot.file_path,
                "dom": dom_snapshot.file_path,
                "ax_tree": ax_tree_snapshot.file_path,
            })

            # ── Step 3: axe-core Scan ──────────────────────────────────────
            step += 1
            log.info("orchestrator.step", step=step, action="run_axe_scan")

            try:
                axe_result = await axe_engine.run(url=self.url, page_title=page_title)

                # Attach element-specific screenshots for each finding
                for finding in axe_result.findings:
                    finding.evidence.append(initial_screenshot)
                    
                    if finding.element.selector:
                        try:
                            el_screenshot = await evidence_collector.capture_screenshot(
                                label=f"element_{finding.finding_id}",
                                full_page=False,
                                element_selector=finding.element.selector,
                            )
                            if el_screenshot.data:
                                finding.evidence.append(el_screenshot)
                        except Exception as e:
                            log.warning("orchestrator.element_screenshot_failed", selector=finding.element.selector, error=str(e))
                            
                    result.add_finding(finding)

                result.metrics.axe_violations = axe_result.violations_count
                result.metrics.axe_passes = axe_result.passes_count
                result.metrics.axe_incomplete = axe_result.incomplete_count
                result.metrics.axe_inapplicable = axe_result.inapplicable_count

                self._trace(result, step, "axe_scan", {}, axe_result.summary())
            except Exception as exc:
                error_msg = f"axe-core scan failed: {exc}"
                log.error("orchestrator.axe_failed", error=error_msg)
                result.errors.append(error_msg)

            # ── Step 4: Keyboard Navigation Test ───────────────────────────
            step += 1
            log.info("orchestrator.step", step=step, action="run_keyboard_test")
            try:
                from accessibility_agent.accessibility.keyboard_tester import KeyboardTester
                kb_tester = KeyboardTester(browser)
                kb_findings = await kb_tester.run(url=self.url, page_title=page_title)
                for finding in kb_findings:
                    finding.evidence.append(initial_screenshot)
                    result.add_finding(finding)
                
                self._trace(result, step, "keyboard_test", {}, {"findings_generated": len(kb_findings)})
            except Exception as exc:
                error_msg = f"Keyboard test failed: {exc}"
                log.error("orchestrator.keyboard_failed", error=error_msg)
                result.errors.append(error_msg)

            # ── Step 5: Deduplication ──────────────────────────────────────
            step += 1
            log.info("orchestrator.step", step=step, action="deduplicate")
            dedup.deduplicate(result.findings)
            self._trace(result, step, "deduplicate", {}, {
                "total": len(result.findings),
                "duplicates": sum(1 for f in result.findings if f.duplicate_of),
            })

            # ── Step 6: AI Reasoning (optional) ───────────────────────────
            step += 1
            log.info("orchestrator.step", step=step, action="ai_reasoning")
            try:
                from accessibility_agent.ai.reasoning_engine import ReasoningEngine
                reasoning = ReasoningEngine()
                if reasoning.is_enabled:
                    await reasoning.enrich_findings(result.findings)
                    self._trace(result, step, "ai_reasoning", {},
                                {"enriched": len([f for f in result.findings if f.ai_reasoning])})
                else:
                    log.info("orchestrator.ai_skipped", reason="LLM provider disabled")
                    self._trace(result, step, "ai_reasoning", {}, {"status": "disabled"})
            except Exception as exc:
                error_msg = f"AI reasoning failed: {exc}"
                log.error("orchestrator.ai_failed", error=error_msg)
                result.errors.append(error_msg)

            # ── Step 7: Final screenshot ────────────────────────────────────
            final_screenshot = await evidence_collector.capture_screenshot(
                label="final_state",
                full_page=True,
            )

            result.agent_steps = step


        # ── Generate Reports ───────────────────────────────────────────────
        report_gen = ReportGenerator(self._output_dir)
        report_paths = report_gen.generate(result)

        log.info(
            "orchestrator.complete",
            run_id=result.run_id,
            findings=result.metrics.total_findings,
            confirmed=result.metrics.confirmed_findings,
            reports={k: str(v) for k, v in report_paths.items()},
        )
        return result

    @staticmethod
    def _trace(
        result: ScanResult,
        step: int,
        action: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
    ) -> None:
        """Append a step to the execution trace for reproducibility."""
        result.execution_trace.append({
            "step": step,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "inputs": inputs,
            "outputs": outputs,
        })
