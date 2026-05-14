"""Setup do cenário 02 — ativa o teste falhando.

Move `tests/pending/farewell.test.js` pra `tests/farewell.test.js` no
master do fixture e commita. Master fica temporariamente "vermelho"
(npm test falha em master enquanto o cenário roda) — o teardown do
conftest reseta pro SHA pristine, então não vaza pra cenários seguintes.
"""

import shutil
import subprocess
from pathlib import Path


def setup(fixture_root: Path) -> None:
    src = fixture_root / "tests" / "pending" / "farewell.test.js"
    dst = fixture_root / "tests" / "farewell.test.js"

    shutil.copy(src, dst)

    subprocess.run(
        ["git", "add", "tests/farewell.test.js"],
        cwd=fixture_root, check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "[fixture-e2e] activate farewell test", "-q"],
        cwd=fixture_root, check=True,
    )
