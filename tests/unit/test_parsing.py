"""Testes do extrator robusto de JSON em parsing.py.

extrair_json tem três estratégias em cascata:
1. tira fences ``` ou ```json se cercam o texto inteiro
2. json.loads direto (caminho feliz)
3. fallback: acha primeiro `{`, varre até `}` balanceado respeitando
   strings e escapes
"""

import json

import pytest

from parsing import extrair_json


class TestPureJson:
    def test_parses_simple_object(self):
        assert extrair_json('{"a": 1}') == {"a": 1}

    def test_parses_nested_object(self):
        out = extrair_json('{"a": {"b": 2}, "c": [1, 2, 3]}')
        assert out == {"a": {"b": 2}, "c": [1, 2, 3]}

    def test_handles_unicode(self):
        out = extrair_json('{"msg": "olá Rick 🌀"}')
        assert out == {"msg": "olá Rick 🌀"}

    def test_strips_leading_trailing_whitespace(self):
        assert extrair_json('   \n  {"a": 1}  \t\n') == {"a": 1}


class TestFences:
    def test_strips_json_fence(self):
        text = '```json\n{"a": 1}\n```'
        assert extrair_json(text) == {"a": 1}

    def test_strips_bare_fence(self):
        text = '```\n{"a": 1}\n```'
        assert extrair_json(text) == {"a": 1}

    def test_strips_fence_without_trailing_newline(self):
        text = '```json{"a":1}```'
        assert extrair_json(text) == {"a": 1}


class TestFallbackBalancing:
    def test_extracts_json_with_preamble(self):
        text = 'Aqui vai o briefing:\n{"a": 1}'
        assert extrair_json(text) == {"a": 1}

    def test_extracts_json_with_suffix(self):
        text = '{"a": 1}\n\nEspero que ajude.'
        assert extrair_json(text) == {"a": 1}

    def test_extracts_json_surrounded_by_prose(self):
        text = 'Preâmbulo. {"a": 1} Sufixo.'
        assert extrair_json(text) == {"a": 1}

    def test_respects_braces_inside_strings(self):
        text = 'preamble {"msg": "tem { chave } aqui"} suffix'
        assert extrair_json(text) == {"msg": "tem { chave } aqui"}

    def test_respects_escaped_quotes_in_strings(self):
        text = '{"msg": "ele disse \\"olá\\"" }'
        assert extrair_json(text) == {"msg": 'ele disse "olá"'}

    def test_extracts_first_balanced_object_when_multiple(self):
        # garante que para no primeiro objeto balanceado, não engole o segundo
        text = '{"a": 1} prose {"b": 2}'
        assert extrair_json(text) == {"a": 1}

    def test_handles_deep_nesting(self):
        text = 'prose {"a": {"b": {"c": {"d": 1}}}}'
        assert extrair_json(text) == {"a": {"b": {"c": {"d": 1}}}}

    def test_respects_escaped_quotes_when_in_fallback(self):
        """Quando o fallback de balanceamento roda (json.loads direto
        falhou por causa de prosa em volta), o varredor precisa
        reconhecer escape de aspas pra não fechar string no meio."""
        text = 'prefix {"msg": "diz: \\"oi\\""} suffix'
        assert extrair_json(text) == {"msg": 'diz: "oi"'}


class TestInvalidInput:
    def test_raises_when_no_opening_brace(self):
        with pytest.raises(json.JSONDecodeError):
            extrair_json("texto sem JSON nenhum")

    def test_raises_when_braces_unbalanced(self):
        with pytest.raises(json.JSONDecodeError):
            extrair_json('texto {"a": 1, "b":')

    def test_raises_when_content_inside_braces_not_json(self):
        # encontra { ... } balanceado mas conteúdo não é JSON válido
        with pytest.raises(json.JSONDecodeError):
            extrair_json('{ não é json }')
