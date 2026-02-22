# AppleScript MCP Server (Dual access: python and node.js)

[![npm version](https://img.shields.io/npm/v/@peakmojo/applescript-mcp.svg)](https://www.npmjs.com/package/@peakmojo/applescript-mcp) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

A Model Context Protocol (MCP) server that lets you run AppleScript code to interact with Mac. This MCP is intentionally designed to be simple, straightforward, intuitive, and require minimal setup.

I can't believe how simple and powerful it is. The core code is <100 line of code.

<a href="https://glama.ai/mcp/servers/@peakmojo/applescript-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@peakmojo/applescript-mcp/badge" alt="AppleScript Server MCP server" />
</a>

https://github.com/user-attachments/assets/b85e63ba-fb26-4918-8e6d-2377254ee388

## Features

* Run AppleScript to access Mac applications and data
* Interact with Notes, Calendar, Contacts, Messages, and more
* Search for files using Spotlight or Finder
* Read/write file contents and execute shell commands
* Remote execution support via SSH

## Example Prompts

```
Create a reminder for me to call John tomorrow at 10am
```

```
Add a new meeting to my calendar for Friday from 2-3pm titled "Team Review"
```

```
Create a new note titled "Meeting Minutes" with today's date
```

```
Show me all files in my Downloads folder from the past week
```

```
What's my current battery percentage?
```

```
Show me the most recent unread emails in my inbox
```

```
List all the currently running applications on my Mac
```

```
Play my "Focus" playlist in Apple Music
```

```
Take a screenshot of my entire screen and save it to my Desktop
```

```
Find John Smith in my contacts and show me his phone number
```

```
Create a folder on my Desktop named "Project Files"
```

```
Open Safari and navigate to apple.com
```

```
Tell me how much free space I have on my main drive
```

```
List all my upcoming calendar events for this week
```

## Usage with Claude Desktop

### Node.js
```json
{
  "mcpServers": {
    "applescript_execute": {
      "command": "npx",
      "args": [
        "@peakmojo/applescript-mcp"
      ]
    }
  }
}
```

### Python (uvx)

No clone needed — run directly from the git repo:

```json
{
  "mcpServers": {
    "applescript_execute": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/peakmojo/applescript-mcp",
        "mcp-server-applescript"
      ]
    }
  }
}
```

### Python (local development)

For local development, clone the repo and use `uv` to run from source:

```
brew install uv
git clone https://github.com/peakmojo/applescript-mcp.git
```

```json
{
  "mcpServers": {
    "applescript_execute": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/your/repo",
        "run",
        "mcp-server-applescript"
      ]
    }
  }
}
```

## Development

### Setup

```bash
brew install uv
uv sync --dev
```

### Run all checks (in parallel)

```bash
uv run check
```

This runs linting, formatting, type checking, and tests with 100% coverage — all in parallel.

### Individual commands

```bash
uv run lint        # ruff linter
uv run format      # ruff auto-format
uv run typecheck   # pyrefly type checker
uv run test        # pytest with 100% coverage enforcement
```

## Docker Usage

When running in a Docker container, you can use the special hostname `host.docker.internal` to connect to your Mac host:

### Configuration
```json
{
  "mcpServers": {
    "applescript_execute": {
      "command": "npx",
      "args": [
        "@peakmojo/applescript-mcp",
        "--remoteHost", "host.docker.internal",
        "--remoteUser", "yourusername",
        "--remotePassword", "yourpassword"
      ]
    }
  }
}
```

This allows your Docker container to execute AppleScript on the Mac host system. Make sure:

1. SSH is enabled on your Mac (System Settings → Sharing → Remote Login)
2. Your user has proper permissions
3. The correct credentials are provided in the config
