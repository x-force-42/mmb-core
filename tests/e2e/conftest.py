"""Fixtures pytest pro E2E.

- `fixture_root` (session scope): captura SHA pristine do master e
  garante reset + cleanup ao final da sessão.
- `clean_fixture` (function scope): reseta para o pristine antes de
  cada cenário rodar (caso anterior tenha sujado).
"""

import pytest

from .harness import (
    cleanup_meeseeks_artifacts,
    fixture_path,
    kill_port,
    pristine_sha,
    reset_to,
)


@pytest.fixture(scope="session")
def fixture_root():
    root = fixture_path()
    sha = pristine_sha(root)
    # garante que entramos numa árvore limpa
    cleanup_meeseeks_artifacts(root)
    reset_to(root, sha)
    yield root
    # teardown de sessão — não deixa rastro
    kill_port(5173)
    cleanup_meeseeks_artifacts(root)
    reset_to(root, sha)


@pytest.fixture
def clean_fixture(fixture_root):
    """Reseta antes E depois de cada cenário — não confia que o cenário
    anterior limpou tudo."""
    sha = pristine_sha(fixture_root)
    cleanup_meeseeks_artifacts(fixture_root)
    reset_to(fixture_root, sha)
    yield fixture_root
    kill_port(5173)
    cleanup_meeseeks_artifacts(fixture_root)
    reset_to(fixture_root, sha)
