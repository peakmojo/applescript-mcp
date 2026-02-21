import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import applescript_mcp
from applescript_mcp.server import configure_logging, main, parse_arguments

# ============== __init__.py ==============


class TestInitMain:
    def test_calls_server_main(self):
        with patch.object(applescript_mcp.server, "main", new_callable=AsyncMock) as mock_main:
            applescript_mcp.main()
            mock_main.assert_awaited_once()


# ============== parse_arguments ==============


class TestParseArguments:
    def test_defaults_to_info(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.setattr("sys.argv", ["prog"])
        args = parse_arguments()
        assert args.log_level == "INFO"

    def test_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setattr("sys.argv", ["prog"])
        args = parse_arguments()
        assert args.log_level == "DEBUG"

    def test_cli_overrides_env(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setattr("sys.argv", ["prog", "--log-level", "WARNING"])
        args = parse_arguments()
        assert args.log_level == "WARNING"


# ============== configure_logging ==============


class TestConfigureLogging:
    def test_sets_debug_level(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--log-level", "DEBUG"])
        configure_logging()
        assert logging.getLogger("applescript_mcp").level == logging.DEBUG

    def test_invalid_level_defaults_to_info(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--log-level", "BOGUS"])
        configure_logging()
        assert logging.getLogger("applescript_mcp").level == logging.INFO


# ============== Handler fixture ==============


def _make_decorator_factory(captured: dict[str, object], name: str):
    """Create a fake decorator factory that captures the handler function."""

    def factory():
        def decorator(fn):
            captured[name] = fn
            return fn

        return decorator

    return factory


def _mock_proc(*, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> AsyncMock:
    """Create a mock async subprocess process."""
    proc = AsyncMock()
    proc.communicate.return_value = (stdout, stderr)
    proc.returncode = returncode
    proc.kill = MagicMock()
    return proc


@pytest.fixture
async def handlers():
    """Run main() with a mocked Server to capture the registered handlers."""
    captured: dict[str, object] = {}

    mock_server = MagicMock()
    mock_server.list_resources = _make_decorator_factory(captured, "list_resources")
    mock_server.read_resource = _make_decorator_factory(captured, "read_resource")
    mock_server.list_tools = _make_decorator_factory(captured, "list_tools")
    mock_server.call_tool = _make_decorator_factory(captured, "call_tool")
    mock_server.get_capabilities.return_value = {}
    mock_server.run = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = (MagicMock(), MagicMock())
    mock_ctx.__aexit__.return_value = False

    with (
        patch("applescript_mcp.server.Server", return_value=mock_server),
        patch("applescript_mcp.server.configure_logging"),
        patch("applescript_mcp.server.InitializationOptions"),
        patch("applescript_mcp.server.NotificationOptions"),
        patch("mcp.server.stdio.stdio_server", return_value=mock_ctx),
    ):
        await main()

    return captured


# ============== handle_list_resources ==============


class TestHandleListResources:
    async def test_returns_empty_list(self, handlers):
        result = await handlers["list_resources"]()
        assert result == []


# ============== handle_read_resource ==============


class TestHandleReadResource:
    async def test_returns_empty_string(self, handlers):
        result = await handlers["read_resource"]("https://example.com")
        assert result == ""


# ============== handle_list_tools ==============


class TestHandleListTools:
    async def test_returns_applescript_tool(self, handlers):
        tools = await handlers["list_tools"]()
        assert len(tools) == 1
        assert tools[0].name == "applescript_execute"
        assert "code_snippet" in tools[0].inputSchema["properties"]
        assert "timeout" in tools[0].inputSchema["properties"]


# ============== handle_call_tool ==============


class TestHandleCallTool:
    async def test_success(self, handlers):
        proc = _mock_proc(returncode=0, stdout=b"Hello World\n")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
            result = await handlers["call_tool"]("applescript_execute", {"code_snippet": 'display dialog "hi"'})

        assert len(result) == 1
        assert result[0].text == "Hello World\n"

    async def test_error_returncode(self, handlers):
        proc = _mock_proc(returncode=1, stderr=b"syntax error")

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
            result = await handlers["call_tool"]("applescript_execute", {"code_snippet": "bad script"})

        assert "AppleScript execution failed" in result[0].text
        assert "syntax error" in result[0].text

    async def test_timeout(self, handlers):
        proc = _mock_proc()

        with (
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc),
            patch("asyncio.wait_for", new_callable=AsyncMock, side_effect=asyncio.TimeoutError),
        ):
            result = await handlers["call_tool"]("applescript_execute", {"code_snippet": "slow script", "timeout": 30})

        assert "timed out after 30 seconds" in result[0].text
        proc.kill.assert_called_once()

    async def test_generic_exception(self, handlers):
        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
            result = await handlers["call_tool"]("applescript_execute", {"code_snippet": "bad"})

        assert "Error executing AppleScript: boom" in result[0].text

    async def test_missing_code_snippet(self, handlers):
        result = await handlers["call_tool"]("applescript_execute", {})
        assert "Error: Missing code_snippet argument" in result[0].text

    async def test_none_arguments(self, handlers):
        result = await handlers["call_tool"]("applescript_execute", None)
        assert "Error: Missing code_snippet argument" in result[0].text

    async def test_unknown_tool(self, handlers):
        result = await handlers["call_tool"]("nonexistent", {})
        assert "Error: Unknown tool: nonexistent" in result[0].text

    async def test_temp_file_closed_before_execution(self, handlers):
        """Regression: temp file must be closed before osascript reads it (269b8d7)."""
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test.scpt"

        file_was_closed = False

        def mark_closed():
            nonlocal file_was_closed
            file_was_closed = True

        mock_temp.close = mark_closed

        proc = _mock_proc(returncode=0, stdout=b"ok")

        async def assert_closed_at_exec_time(*args, **kwargs):
            assert file_was_closed, "Temp file should be closed before subprocess starts"
            return proc

        with (
            patch("tempfile.NamedTemporaryFile", return_value=mock_temp),
            patch("asyncio.create_subprocess_exec", side_effect=assert_closed_at_exec_time),
        ):
            await handlers["call_tool"]("applescript_execute", {"code_snippet": "test"})

    async def test_subprocess_does_not_block_event_loop(self, handlers):
        """Regression: subprocess must be async so the event loop stays responsive (ba1e331)."""
        concurrent_task_ran = False

        async def slow_communicate():
            await asyncio.sleep(0)
            return (b"ok", b"")

        proc = _mock_proc(returncode=0)
        proc.communicate = slow_communicate

        async def check_concurrent():
            nonlocal concurrent_task_ran
            concurrent_task_ran = True

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc):
            await asyncio.gather(
                handlers["call_tool"]("applescript_execute", {"code_snippet": "test"}),
                check_concurrent(),
            )

        assert concurrent_task_ran, "Event loop should remain responsive during subprocess execution"

    async def test_temp_file_cleanup_on_success(self, handlers):
        proc = _mock_proc(returncode=0, stdout=b"ok")

        with (
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc),
            patch("os.unlink") as mock_unlink,
        ):
            await handlers["call_tool"]("applescript_execute", {"code_snippet": "test"})
            mock_unlink.assert_called_once()

    async def test_temp_file_cleanup_on_error(self, handlers):
        with (
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, side_effect=RuntimeError("fail")),
            patch("os.unlink") as mock_unlink,
        ):
            await handlers["call_tool"]("applescript_execute", {"code_snippet": "test"})
            mock_unlink.assert_called_once()

    async def test_unlink_failure_suppressed(self, handlers):
        proc = _mock_proc(returncode=0, stdout=b"ok")

        with (
            patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=proc),
            patch("os.unlink", side_effect=OSError("rm failed")),
        ):
            result = await handlers["call_tool"]("applescript_execute", {"code_snippet": "test"})

        # Should still return successfully despite unlink failure
        assert result[0].text == "ok"


# ============== main() server startup ==============


class TestMain:
    async def test_starts_server(self):
        mock_server = MagicMock()
        mock_server.list_resources = _make_decorator_factory({}, "lr")
        mock_server.read_resource = _make_decorator_factory({}, "rr")
        mock_server.list_tools = _make_decorator_factory({}, "lt")
        mock_server.call_tool = _make_decorator_factory({}, "ct")
        mock_server.get_capabilities.return_value = {}
        mock_server.run = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = (MagicMock(), MagicMock())
        mock_ctx.__aexit__.return_value = False

        with (
            patch("applescript_mcp.server.Server", return_value=mock_server) as mock_cls,
            patch("applescript_mcp.server.configure_logging"),
            patch("applescript_mcp.server.InitializationOptions"),
            patch("applescript_mcp.server.NotificationOptions"),
            patch("mcp.server.stdio.stdio_server", return_value=mock_ctx),
        ):
            await main()

        mock_cls.assert_called_once_with("applescript-mcp")
        mock_server.run.assert_awaited_once()
