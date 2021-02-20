import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope='session')
def path0(tmp_path_factory):
    cd = Path(os.getcwd())
    if (cd / 'work' / 'reference').exists():
        return cd / 'work' / 'reference'
    path0 = tmp_path_factory.mktemp("path0_")
    run_on_path(path0)
    return path0


def run_on_path(path):
    """Run at path"""
    cd = Path(os.getcwd())
    cmd = (
        f"python {cd}/itassets/itassets.py --updated Today "
        f"--theme dark --assets {cd}/work/source/assets/*.yaml "
        f"--output {path}",
    )
    run = subprocess.run(cmd, shell=True)
    run.check_returncode()


def test_date_lock(tmp_path_factory, path0):
    """Test that `--updated` generates identical output.

    --updated foo can be used to avoid changes due solely to time of
    generation, useful for testing.
    """
    path1 = tmp_path_factory.mktemp('path1_')
    run_on_path(path1)
    run = subprocess.run(
        f"diff -r {path0} {path1}",
        capture_output=True,
        shell=True,
    )
    assert run.returncode < 2  # 1 indicates a diff
    assert run.stdout == b""
