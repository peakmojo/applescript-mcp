"""Dev script entry points for `uv run check`, `uv run lint`, etc."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

CHECKS = {
    "lint": ["ruff", "check", "src/", "tests/"],
    "format": ["ruff", "format", "--check", "src/", "tests/"],
    "typecheck": ["pyrefly", "check"],
    "test": ["pytest", "--cov=applescript_mcp", "--cov-report=term-missing", "--cov-fail-under=100"],
}


def _run(cmd: list[str]) -> None:
    sys.exit(subprocess.call(cmd))


def _run_check(name: str, cmd: list[str]) -> tuple[str, int, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return name, result.returncode, result.stdout + result.stderr


def lint() -> None:
    _run(CHECKS["lint"])


def format_code() -> None:
    _run(["ruff", "format", "src/", "tests/"])


def typecheck() -> None:
    _run(CHECKS["typecheck"])


def test() -> None:
    _run(CHECKS["test"])


def check() -> None:
    """Run all checks in parallel."""
    failed = False
    with ThreadPoolExecutor(max_workers=len(CHECKS)) as pool:
        futures = {pool.submit(_run_check, name, cmd): name for name, cmd in CHECKS.items()}
        for future in as_completed(futures):
            name, returncode, output = future.result()
            status = "PASS" if returncode == 0 else "FAIL"
            print(f"\n{'=' * 60}")
            print(f"  {name}: {status}")
            print(f"{'=' * 60}")
            if output.strip():
                print(output.strip())
            if returncode != 0:
                failed = True

    print()
    if failed:
        print("Some checks failed.")
        sys.exit(1)
    else:
        print("All checks passed.")
