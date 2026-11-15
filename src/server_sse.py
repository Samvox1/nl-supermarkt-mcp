#!/usr/bin/env python3
"""NL Supermarkt MCP Server - SSE Transport"""

import os
import sys
import asyncio
import logging

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    import uvicorn
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.responses import JSONResponse, Response
    from starlette.requests import Request

    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request):
        logger.info("SSE connection received")
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
        # The SSE transport already sent the response; return an empty one so
        # Starlette doesn't try to call None when the client disconnects.
        return Response()

    async def health(request: Request):
        return JSONResponse({"status": "healthy"})

    app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            # handle_post_message is a raw ASGI app that sends its own 202
            # response, so mount it directly instead of wrapping it in a Route.
            Mount("/messages/", app=sse.handle_post_message),
            Route("/health", endpoint=health),
        ]
    )

    port = int(os.environ.get('PORT', 8000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
