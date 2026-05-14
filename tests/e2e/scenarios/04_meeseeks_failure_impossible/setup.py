"""Setup do cenário 04 — força falha do Meeseeks via build quebrado.

A tarefa (`welcome` análoga a `greet`) é razoável e a Garagem aceita
sem pushback. O que provoca o `meeseeks_failure` é o `npm run build`
do fixture, que aqui é deliberadamente trocado por um comando que sai
com exit 1. O Meeseeks no passo 6 do `skills/meeseeks.md` precisa
rodar `npm run build` limpo; ao falhar, ele aborta sem commitar.

Por que build (e não teste pré-quebrado): teste vermelho deixa o
Meeseeks margem pra racionalizar ("já estava quebrado antes das minhas
mudanças, sigo"). Build é um único comando binário no passo 6, sem
contexto que permita racionalização — e package.json não está nos
arquivos_alvo do briefing, então não cabe ao Meeseeks "consertar".

O cleanup do `conftest` (reset --hard pro SHA pristine) desfaz o
commit deste setup ao final do cenário.
"""

import json
import subprocess
from pathlib import Path


def setup(fixture_root: Path) -> None:
    pkg_path = fixture_root / "package.json"
    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    pkg["scripts"]["build"] = 'node -e "process.exit(1)"'
    pkg_path.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")

    subprocess.run(
        ["git", "add", "package.json"],
        cwd=str(fixture_root), check=True,
    )
    subprocess.run(
        ["git", "-c", "user.name=mmb-e2e", "-c", "user.email=e2e@mmb.test",
         "commit", "-m", "test: cenário 04 — build deliberadamente quebrado"],
        cwd=str(fixture_root), check=True,
    )
