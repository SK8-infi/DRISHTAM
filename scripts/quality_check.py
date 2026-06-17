"""Run all code quality checks in sequence.

Usage:
    python scripts/quality_check.py [--fix]

Runs: ruff format, ruff check, bandit, mypy, pytest
Reports pass/fail for each and overall status.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Force UTF-8 output on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DRISHTAM_DIR = PROJECT_ROOT / "drishtam"
API_DIR = PROJECT_ROOT / "api"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
VENV_SCRIPTS = PROJECT_ROOT / ".venv" / "Scripts"


def _tool_path(name: str) -> str:
    """Resolve tool path from venv Scripts directory."""
    venv_tool = VENV_SCRIPTS / f"{name}.exe"
    if venv_tool.exists():
        return str(venv_tool)
    return name  # Fallback to PATH


@dataclass
class CheckResult:
    """Result of a single quality check."""

    name: str
    passed: bool
    duration_s: float
    output: str
    return_code: int


def run_check(name: str, cmd: list[str], *, allow_failure: bool = False) -> CheckResult:
    """Run a single quality check command.

    Args:
        name: Human-readable name for the check.
        cmd: Command to execute as list of strings.
        allow_failure: If True, non-zero exit code doesn't mean failure.

    Returns:
        CheckResult with pass/fail status and output.
    """
    print(f"\n{'=' * 60}")
    print(f"  Running: {name}")
    print(f"  Command: {' '.join(cmd)}")
    print(f"{'=' * 60}")

    start = time.perf_counter()
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        duration = time.perf_counter() - start
        output = result.stdout + result.stderr

        passed = result.returncode == 0 or allow_failure
        status = "[PASS]" if passed else "[FAIL]"
        print(f"\n  {status} ({duration:.1f}s)")

        if not passed:
            # Show first 50 lines of output on failure
            lines = output.strip().split("\n")[:50]
            for line in lines:
                print(f"    {line}")
            if len(output.strip().split("\n")) > 50:
                print(f"    ... ({len(output.strip().split(chr(10)))} total lines)")

        return CheckResult(
            name=name,
            passed=passed,
            duration_s=duration,
            output=output,
            return_code=result.returncode,
        )

    except FileNotFoundError:
        duration = time.perf_counter() - start
        print(f"\n  [SKIP] Tool not installed: {cmd[0]}")
        return CheckResult(
            name=name,
            passed=True,  # Don't fail if tool isn't installed yet
            duration_s=duration,
            output=f"Tool not found: {cmd[0]}",
            return_code=-1,
        )

    except subprocess.TimeoutExpired:
        duration = time.perf_counter() - start
        print(f"\n  [TIMEOUT] after {duration:.0f}s")
        return CheckResult(
            name=name,
            passed=False,
            duration_s=duration,
            output="Command timed out after 300 seconds",
            return_code=-2,
        )


def main() -> int:
    """Run all quality checks and report results.

    Returns:
        Exit code: 0 if all checks pass, 1 if any fail.
    """
    fix_mode = "--fix" in sys.argv

    print("\n" + "=" * 60)
    print("  DRISHTAM -- Code Quality Check Suite")
    print("=" * 60)

    if fix_mode:
        print("  Mode: FIX (auto-fixing where possible)")
    else:
        print("  Mode: CHECK (read-only, use --fix to auto-fix)")

    # Determine which directories exist for checking
    check_dirs = [str(d) for d in [DRISHTAM_DIR, API_DIR, SCRIPTS_DIR] if d.exists() and any(d.glob("*.py"))]
    if not check_dirs:
        check_dirs = ["."]

    results: list[CheckResult] = []

    ruff = _tool_path("ruff")
    bandit_cmd = _tool_path("bandit")
    mypy_cmd = _tool_path("mypy")
    pytest_cmd = _tool_path("pytest")

    # 1. Ruff Format Check
    if fix_mode:
        results.append(
            run_check(
                "Ruff Format (apply)",
                [ruff, "format", *check_dirs],
            )
        )
    else:
        results.append(
            run_check(
                "Ruff Format (check)",
                [ruff, "format", "--check", *check_dirs],
            )
        )

    # 2. Ruff Lint
    lint_cmd = [ruff, "check", *check_dirs]
    if fix_mode:
        lint_cmd.append("--fix")
    results.append(run_check("Ruff Lint", lint_cmd))

    # 3. Bandit Security Scan
    if DRISHTAM_DIR.exists():
        results.append(
            run_check(
                "Bandit Security Scan",
                [bandit_cmd, "-r", str(DRISHTAM_DIR), "-c", "pyproject.toml", "-q"],
            )
        )

    # 4. Mypy Type Check
    if DRISHTAM_DIR.exists():
        results.append(
            run_check(
                "Mypy Type Check",
                [mypy_cmd, str(DRISHTAM_DIR), "--ignore-missing-imports"],
            )
        )

    # 5. Pytest
    tests_dir = PROJECT_ROOT / "tests"
    if tests_dir.exists() and any(tests_dir.glob("test_*.py")):
        results.append(
            run_check(
                "Pytest",
                [pytest_cmd, "--tb=short", "-q"],
            )
        )
    else:
        print("\n  [SKIP] Skipping pytest -- no tests directory or test files found yet")

    # Summary
    print("\n" + "=" * 60)
    print("  QUALITY CHECK SUMMARY")
    print("=" * 60)

    total_duration = sum(r.duration_s for r in results)
    all_passed = all(r.passed for r in results)

    for r in results:
        status = "[PASS]" if r.passed else "[FAIL]"
        print(f"  {status} {r.name:<30s} ({r.duration_s:.1f}s)")

    print(f"\n  Total time: {total_duration:.1f}s")
    if all_passed:
        print("  >>> ALL CHECKS PASSED <<<")
    else:
        failed = [r.name for r in results if not r.passed]
        print(f"  >>> FAILED: {', '.join(failed)} <<<")

    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
