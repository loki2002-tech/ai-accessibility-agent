import uvicorn
import structlog

log = structlog.get_logger()

def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Start the FastAPI server via uvicorn."""
    log.info("server.starting", host=host, port=port)
    uvicorn.run(
        "accessibility_agent.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )

if __name__ == "__main__":
    run_server()
