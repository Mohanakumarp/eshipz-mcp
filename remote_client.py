#!/usr/bin/env python3
"""
Remote MCP Client for Claude Desktop
Connects to remote SSE MCP server and provides stdio interface for Claude Desktop
"""
import asyncio
import json
import sys
from typing import Any, Optional
import httpx
from httpx_sse import aconnect_sse

REMOTE_SERVER_URL = "https://eshipz-mcp.onrender.com"


class RemoteMCPClient:
    """Client that bridges stdio to remote SSE MCP server"""
    
    def __init__(self, url: str):
        self.url = url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.session_id: Optional[str] = None
    
    async def send_request(self, message: dict) -> None:
        """Send a request to the remote server"""
        try:
            if self.session_id:
                message["sessionId"] = self.session_id
            
            response = await self.client.post(
                f"{self.url}/message",
                json=message,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        except Exception as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr, flush=True)
    
    async def listen_sse(self) -> None:
        """Listen to SSE events from remote server"""
        try:
            async with aconnect_sse(self.client, "GET", self.url) as event_source:
                async for event in event_source.aiter_sse():
                    if event.data:
                        # Forward SSE event to stdout for Claude Desktop
                        print(event.data, flush=True)
                        
                        if event.event == "session":
                            # Store session ID if provided
                            try:
                                data = json.loads(event.data)
                                if "sessionId" in data:
                                    self.session_id = data["sessionId"]
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            print(json.dumps({"error": f"SSE connection error: {str(e)}"}), file=sys.stderr, flush=True)
    
    async def read_stdin(self) -> None:
        """Read JSON-RPC messages from stdin and forward to server"""
        loop = asyncio.get_event_loop()
        
        while True:
            try:
                # Read line from stdin asynchronously
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                
                # Parse and forward to remote server
                message = json.loads(line.strip())
                await self.send_request(message)
            except json.JSONDecodeError as e:
                print(json.dumps({"error": f"Invalid JSON: {str(e)}"}), file=sys.stderr, flush=True)
            except Exception as e:
                print(json.dumps({"error": str(e)}), file=sys.stderr, flush=True)
                break
    
    async def run(self) -> None:
        """Run the client, bridging stdio and SSE"""
        try:
            # Run both stdin reader and SSE listener concurrently
            await asyncio.gather(
                self.listen_sse(),
                self.read_stdin()
            )
        finally:
            await self.client.aclose()


async def main():
    """Main entry point"""
    client = RemoteMCPClient(REMOTE_SERVER_URL)
    await client.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr, flush=True)
        sys.exit(1)
