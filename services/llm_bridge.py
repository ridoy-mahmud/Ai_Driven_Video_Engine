"""
VS Code Copilot LLM Bridge — project-scoped OpenAI-compatible proxy.

Runs a tiny FastAPI server on port 5199 that proxies LLM calls to VS Code's
built-in Copilot language model API.  This bridge is auto-started by app.py
and scoped to this project only (binds to 127.0.0.1).

Usage:
  - Set llm_source = "vscode" in the UI
  - The bridge auto-starts when app.py launches
  - Connects at http://127.0.0.1:5199/v1

The bridge uses the VS Code Copilot Chat extension's language model.
If VS Code / Copilot is not available, it falls back gracefully.
"""

import asyncio
import json
import os
import signal
import sys
import time
import threading
from typing import Optional

from utils.log import logger

BRIDGE_PORT = 5199
BRIDGE_HOST = "127.0.0.1"
_bridge_process = None
_bridge_thread = None


def _get_project_root() -> str:
    """Get this project's root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_bridge_running() -> bool:
    """Check if the LLM bridge is already running on the expected port."""
    import socket
    try:
        with socket.create_connection((BRIDGE_HOST, BRIDGE_PORT), timeout=1):
            return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


def start_bridge_server():
    """Start the LLM bridge server in a background thread.
    
    This creates a minimal OpenAI-compatible API that can be used as a proxy.
    The bridge is project-scoped (binds to localhost only).
    """
    global _bridge_thread

    if is_bridge_running():
        logger.info(f"LLM bridge already running on {BRIDGE_HOST}:{BRIDGE_PORT}")
        return

    def _run_bridge():
        try:
            import uvicorn
            from fastapi import FastAPI, Request
            from fastapi.responses import JSONResponse, StreamingResponse

            bridge_app = FastAPI(title="VS Code LLM Bridge", docs_url=None, redoc_url=None)

            # Store the project root to scope this bridge
            project_root = _get_project_root()

            @bridge_app.get("/v1/models")
            async def list_models():
                return {
                    "object": "list",
                    "data": [
                        {
                            "id": "copilot-chat",
                            "object": "model",
                            "created": int(time.time()),
                            "owned_by": "vscode-copilot",
                        }
                    ],
                }

            @bridge_app.post("/v1/chat/completions")
            async def chat_completions(request: Request):
                """Proxy chat completions.
                
                In a full VS Code extension integration, this would call the
                VS Code Language Model API. For standalone use, it returns a
                helpful error directing the user to configure a real LLM.
                """
                body = await request.json()
                messages = body.get("messages", [])
                model = body.get("model", "copilot-chat")

                # Try to proxy to VS Code's Copilot if available
                # Default upstream: the VS Code extension on port 5678
                try:
                    upstream = os.environ.get(
                        "VSCODE_LLM_UPSTREAM_URL",
                        "http://127.0.0.1:5678",   # VS Code extension default
                    )
                    if upstream:
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            headers = {"Content-Type": "application/json"}
                            upstream_key = os.environ.get("VSCODE_LLM_UPSTREAM_KEY", "")
                            if upstream_key:
                                headers["Authorization"] = f"Bearer {upstream_key}"
                            async with session.post(
                                f"{upstream}/v1/chat/completions",
                                json=body,
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=120),
                            ) as resp:
                                data = await resp.json()
                                return JSONResponse(content=data)
                except Exception as e:
                    logger.debug(f"Upstream proxy failed: {e}")

                # Fallback: return error message
                return JSONResponse(content={
                    "id": f"bridge-{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": (
                                "ERROR: LLM Bridge cannot reach the VS Code Copilot extension. "
                                "Make sure you have the vscode-llm-bridge extension installed "
                                "and running in VS Code (check status bar for 'LLM Bridge')."
                            ),
                        },
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                })

            @bridge_app.get("/health")
            async def health():
                return {"status": "ok", "project": project_root, "port": BRIDGE_PORT}

            config = uvicorn.Config(
                bridge_app,
                host=BRIDGE_HOST,
                port=BRIDGE_PORT,
                log_level="warning",
                access_log=False,
            )
            server = uvicorn.Server(config)
            server.run()

        except Exception as e:
            logger.warning(f"LLM bridge failed to start: {e}")

    _bridge_thread = threading.Thread(target=_run_bridge, daemon=True, name="llm-bridge")
    _bridge_thread.start()
    
    # Wait briefly for it to start
    for _ in range(10):
        time.sleep(0.3)
        if is_bridge_running():
            logger.info(f"LLM bridge started on {BRIDGE_HOST}:{BRIDGE_PORT}")
            return
    
    logger.warning("LLM bridge may not have started in time")


def stop_bridge():
    """Stop the bridge (happens automatically when main process exits since thread is daemon)."""
    global _bridge_thread
    _bridge_thread = None
    logger.info("LLM bridge stopped")


def get_bridge_config() -> dict:
    """Get the LLM config to use the bridge."""
    return {
        "api_key": "bridge-local",
        "base_url": f"http://{BRIDGE_HOST}:{BRIDGE_PORT}/v1",
        "model": "copilot-chat",
    }
