from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, HttpUrl, Field

from accessibility_agent.agent.job_manager import job_manager

router = APIRouter(prefix="/api/v1", tags=["scans"])

class ScanRequest(BaseModel):
    url: HttpUrl = Field(..., description="The full URL of the website you want to scan (e.g., https://example.com)")
    mode: str = Field("automated", description="The type of scan. Supported: 'automated', 'full'")
    agentic: bool = Field(False, description="Set to true to enable the AI to click around and test dynamic elements.")
    browser: str = Field("chromium", description="The browser engine to use. Supported: 'chromium' (Chrome/Edge), 'firefox', or 'webkit' (Safari).")
    headless: bool = Field(True, description="Set to true to run the browser invisibly in the background. Set to false if you want to watch the browser pop up and run.")
    viewport: str = Field("1280x720", description="The screen size to simulate. Format: WIDTHxHEIGHT (e.g., '1920x1080' for desktop, '375x812' for mobile).")

class ScanResponse(BaseModel):
    run_id: str
    message: str

class StatusResponse(BaseModel):
    run_id: str
    status: str
    progress: str
    error: Optional[str] = None
    report_paths: Optional[Dict[str, str]] = None

@router.post("/scan", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_scan(request: ScanRequest) -> ScanResponse:
    """Start a new accessibility scan in the background."""
    run_id = await job_manager.run_job(
        url=str(request.url),
        mode=request.mode,
        agentic=request.agentic,
        browser_name=request.browser,
        headless=request.headless,
        viewport_str=request.viewport,
    )
    
    return ScanResponse(
        run_id=run_id,
        message="Scan started in the background. Check status using /api/v1/scans/{run_id}/status"
    )

@router.get("/scans/{run_id}/status", response_model=StatusResponse)
async def get_scan_status(run_id: str) -> StatusResponse:
    """Get the current status of a scan job."""
    job = job_manager.get_job(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan run_id not found")
        
    return StatusResponse(
        run_id=job.run_id,
        status=job.status,
        progress=job.progress,
        error=job.error,
        report_paths=job.report_paths
    )

@router.get("/scans/{run_id}/report")
async def get_scan_report(run_id: str) -> Any:
    """Get the final JSON report of a completed scan."""
    job = job_manager.get_job(run_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan run_id not found")
        
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Scan is currently {job.status}. Wait for completion.")
        
    if not job.result:
        raise HTTPException(status_code=500, detail="Scan completed but result is missing.")
        
    return job.result.model_dump(mode="json")
