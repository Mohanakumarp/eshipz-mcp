#!/usr/bin/env python3
"""
Remote MCP Client for Claude Desktop
Connects to remote SSE MCP server and provides stdio interface for Claude Desktop
"""
import asyncio
import json
import sys
from typing import Any
import httpx
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

REMOTE_SERVER_URL = "https://eshipz-mcp.onrender.com/sse"


async def main():
    """Connect to remote SSE server and provide stdio interface"""
    async with sse_client(REMOTE_SERVER_URL) as (read, write):
        async with stdio_client() as (local_read, local_write):
            # Create tasks for bidirectional communication
            async def forward_to_server():
                """Read from local stdin and forward to remote server"""
                async for message in local_read:
                    await write.send(message)
            
            async def forward_from_server():
                """Read from remote server and forward to local stdout"""
                async for message in read:
                    await local_write.send(message)
            
            # Run both forwarding tasks concurrently
            await asyncio.gather(
                forward_to_server(),
                forward_from_server()
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
