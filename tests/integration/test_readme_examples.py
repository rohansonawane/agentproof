from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def test_readme_quickstart_python_block_executes(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")
    block = re.search(r"```python\n(.*?)\n```", readme, re.DOTALL)
    assert block is not None
    script = tmp_path / "readme_quickstart.py"
    script.write_text(block.group(1), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        cwd=root,
        env={"PYTHONPATH": "src", **os.environ},
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "INVARIANT_FAILURE" in completed.stdout
    assert "no_double_refunds" in completed.stdout
    assert "98.0" in completed.stdout
