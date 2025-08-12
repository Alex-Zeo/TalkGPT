import subprocess, sys
from pathlib import Path


def run_cli(*args, cwd: Path):
    return subprocess.run([sys.executable, "-m", "src.cli.main", *args], capture_output=True, text=True, cwd=cwd)


def test_cli_help(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    res = run_cli("--help", cwd=root)
    assert res.returncode == 0
    assert "TalkGPT" in res.stdout


def test_status_system_quiet(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    res = run_cli("status", "system", "--quiet", cwd=root)
    assert res.returncode == 0

