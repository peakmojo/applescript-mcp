import argparse
import asyncio
import logging
import os
import tempfile
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

logger = logging.getLogger("applescript_mcp")


def parse_arguments() -> argparse.Namespace:
    """Use argparse to allow values to be set as CLI switches
    or environment variables

    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"))
    return parser.parse_args()


def configure_logging() -> None:
    """Configure logging based on the log level argument"""
    args = parse_arguments()
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.setLevel(log_level)
    logger.info(f"Logging configured with level: {args.log_level.upper()}")


async def main() -> None:
    """Run the AppleScript MCP server."""
    configure_logging()
    logger.info("Server starting")
    server = Server("applescript-mcp")

    @server.list_resources()
    async def handle_list_resources() -> list[types.Resource]:
        return []

    @server.read_resource()
    async def handle_read_resource(uri: AnyUrl) -> str:
        return ""

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        """List available tools"""
        return [
            types.Tool(
                name="applescript_execute",
                description=(
                    "Run AppleScript code to interact with Mac applications and system features."
                    " This tool can access and manipulate data in Notes, Calendar, Contacts,"
                    " Messages, Mail, Finder, Safari, and other Apple applications."
                    " Common use cases include but not limited to:\n"
                    "- Retrieve or create notes in Apple Notes\n"
                    "- Access or add calendar events and appointments\n"
                    "- List contacts or modify contact details\n"
                    "- Search for and organize files using Spotlight or Finder\n"
                    "- Get system information like battery status, disk space, or network details\n"
                    "- Read or organize browser bookmarks or history\n"
                    "- Access or send emails, messages, or other communications\n"
                    "- Read, write, or manage file contents\n"
                    "- Execute shell commands and capture the output\n"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code_snippet": {
                            "type": "string",
                            "description": """Multi-line appleScript code to execute. """,
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Command execution timeout in seconds (default: 60)",
                        },
                    },
                    "required": ["code_snippet"],
                },
            )
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Handle execution of AppleScript to interact with Mac applications and data"""
        try:
            if name == "applescript_execute":
                if not arguments or "code_snippet" not in arguments:
                    raise ValueError("Missing code_snippet argument")

                # Get timeout parameter or use default
                timeout = arguments.get("timeout", 60)

                # Create temp file for the AppleScript and close it before execution
                temp = tempfile.NamedTemporaryFile(suffix=".scpt", delete=False)
                temp_path = temp.name
                try:
                    temp.write(arguments["code_snippet"].encode("utf-8"))
                    temp.close()

                    # Execute the AppleScript asynchronously
                    proc = await asyncio.create_subprocess_exec(
                        "/usr/bin/osascript",
                        temp_path,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    try:
                        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                    except asyncio.TimeoutError:
                        proc.kill()
                        return [
                            types.TextContent(
                                type="text",
                                text=f"AppleScript execution timed out after {timeout} seconds",
                            )
                        ]

                    if proc.returncode != 0:
                        error_message = f"AppleScript execution failed: {stderr.decode()}"
                        return [types.TextContent(type="text", text=error_message)]

                    return [types.TextContent(type="text", text=stdout.decode())]
                except Exception as e:
                    return [types.TextContent(type="text", text=f"Error executing AppleScript: {str(e)}")]
                finally:
                    # Clean up the temporary file
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
            else:
                raise ValueError(f"Unknown tool: {name}")

        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("Server running with stdio transport")
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="applescript-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
