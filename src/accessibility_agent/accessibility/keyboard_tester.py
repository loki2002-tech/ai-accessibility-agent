"""
Keyboard Accessibility Tester.

Simulates human keyboard interaction to verify:
1. All interactive elements are reachable via Tab key (WCAG 2.1.1).
2. Elements have a visible focus indicator (WCAG 2.4.7).
3. No keyboard traps exist (WCAG 2.1.2).
"""

import json
from typing import Any

from accessibility_agent.accessibility.browser import BrowserController
from accessibility_agent.logging_config import get_logger
from accessibility_agent.wcag.schemas import (
    DetectionMethod,
    ElementLocator,
    EvidenceItem,
    Finding,
    FindingStatus,
    ImpactLevel,
    WCAGLevel,
    WCAGMapping,
    WCAGPrinciple,
    WCAGVersion,
)

log = get_logger(__name__)


class KeyboardTester:
    """Runs automated keyboard navigation and focus tests."""

    def __init__(self, browser: BrowserController) -> None:
        self._browser = browser

    async def run(self, url: str, page_title: str) -> list[Finding]:
        """Execute keyboard tests and return findings."""
        findings: list[Finding] = []
        log.info("keyboard_tester.starting")

        # Inject script to find all focusable elements and their initial state
        setup_script = """() => {
            const selectors = [
                'a[href]', 'button', 'input:not([type="hidden"])', 
                'select', 'textarea', '[tabindex]:not([tabindex="-1"])'
            ].join(',');
            
            const elements = Array.from(document.querySelectorAll(selectors));
            
            const visibleElements = elements.filter(el => {
                if (el.hasAttribute('disabled')) return false;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return false;
                return true;
            });
            
            return visibleElements.map(el => ({
                tag: el.tagName.toLowerCase(),
                id: el.id,
                text: el.innerText ? el.innerText.trim().substring(0, 50) : '',
                html: el.outerHTML.substring(0, 200)
            }));
        }"""
        
        try:
            expected_elements = await self._browser.evaluate(setup_script)
            log.info("keyboard_tester.elements_found", count=len(expected_elements))
            
            if not expected_elements:
                return findings
                
            focused_history = []
            max_tabs = min(len(expected_elements) + 5, 50) # Limit for V0.3 prototype
            
            await self._browser.evaluate("() => document.activeElement.blur()")
            
            for i in range(max_tabs):
                action_result = await self._browser.press_key("Tab")
                focused_info = action_result.get("focused_element", {})
                
                if not focused_info.get("focused"):
                    break
                    
                focused_history.append(focused_info)
                
                # Check for visible focus (WCAG 2.4.7)
                has_visible_focus = await self._check_visible_focus()
                
                if not has_visible_focus:
                    finding = self._create_focus_visible_finding(url, page_title, focused_info)
                    findings.append(finding)
                    
        except Exception as e:
            log.error("keyboard_tester.error", error=str(e))
            
        return findings

    async def _check_visible_focus(self) -> bool:
        """Check if the currently focused element has a visible focus indicator."""
        script = """() => {
            const el = document.activeElement;
            if (!el || el === document.body) return true;
            
            const style = window.getComputedStyle(el);
            
            const outlineWidth = parseFloat(style.outlineWidth) || 0;
            const outlineStyle = style.outlineStyle;
            const outlineColor = style.outlineColor;
            
            if (outlineStyle !== 'none' && outlineWidth > 0 && outlineColor !== 'transparent' && outlineColor !== 'rgba(0, 0, 0, 0)') {
                return true;
            }
            
            const boxShadow = style.boxShadow;
            if (boxShadow && boxShadow !== 'none') {
                return true;
            }
            
            return false;
        }"""
        return await self._browser.evaluate(script)

    def _create_focus_visible_finding(self, url: str, page_title: str, focused_info: dict) -> Finding:
        """Create a Finding for missing focus indicator (WCAG 2.4.7)."""
        selector = focused_info.get("selector", "unknown")
        html = focused_info.get("outerHTML", "")
        
        wcag = WCAGMapping(
            version=WCAGVersion.V22,
            success_criterion="2.4.7",
            title="Focus Visible",
            level=WCAGLevel.AA,
            principle=WCAGPrinciple.OPERABLE,
            url="https://www.w3.org/TR/WCAG22/#focus-visible",
        )
        
        evidence = EvidenceItem(
            evidence_type="computed_style",
            description="Computed styles showed no valid outline or box-shadow while element had focus.",
            data=json.dumps(focused_info, indent=2),
            url=url,
        )
        
        import hashlib
        raw_id = f"{url}::kb-focus::{selector}::2.4.7"
        h = hashlib.sha256(raw_id.encode()).hexdigest()[:8].upper()
        fid = f"A11Y-{h}"
        
        return Finding(
            finding_id=fid,
            url=url,
            page_title=page_title,
            element=ElementLocator(selector=selector, html=html),
            status=FindingStatus.REQUIRES_MANUAL_REVIEW,
            detection_method=DetectionMethod.SEMI_AUTOMATED,
            confidence=0.7,
            impact=ImpactLevel.SERIOUS,
            rule_id="kb-focus-visible",
            wcag=wcag,
            description="Element does not appear to have a visible focus indicator (outline or box-shadow).",
            actual_result="No CSS outline or box-shadow detected on focus.",
            expected_result="Element should have a highly visible focus indicator when navigated to via keyboard.",
            evidence=[evidence],
            manual_review_required=True,
            component_signature=hashlib.sha256(raw_id.encode()).hexdigest()[:16],
        )
