"""Testes dos dataclasses de mensagem do aquário.

Schema fechado com o time deles — qualquer mudança aqui é breaking
change pro front. Os testes congelam o formato exato.
"""

import json

from aquario.messages import Event, Meeseeks, NAME_MAX_LEN, Snapshot, State


class TestState:
    def test_round_trip_json(self):
        s = State(id="task-42", health=0.74)
        d = s.to_dict()
        assert d == {"type": "state", "id": "task-42", "health": 0.74}
        # JSON-serializable.
        assert json.loads(json.dumps(d)) == d


class TestEventBorn:
    def test_carries_name_and_task(self):
        e = Event(kind="born", id="task-42",
                  name="Meeseeks-7e3a", task="rebalance the database")
        assert e.to_dict() == {
            "type": "event",
            "kind": "born",
            "id": "task-42",
            "name": "Meeseeks-7e3a",
            "task": "rebalance the database",
        }

    def test_truncates_long_name(self):
        e = Event(kind="born", id="x", name="M" * 100, task="t")
        out = e.to_dict()
        assert len(out["name"]) == NAME_MAX_LEN

    def test_omits_missing_optionals(self):
        e = Event(kind="born", id="x")
        out = e.to_dict()
        assert "name" not in out
        assert "task" not in out


class TestEventTerminals:
    def test_died_happy_has_only_id(self):
        e = Event(kind="died_happy", id="task-42")
        assert e.to_dict() == {
            "type": "event", "kind": "died_happy", "id": "task-42",
        }

    def test_died_defeated_has_only_id(self):
        e = Event(kind="died_defeated", id="task-42")
        assert e.to_dict() == {
            "type": "event", "kind": "died_defeated", "id": "task-42",
        }

    def test_freaking_out_has_only_id(self):
        e = Event(kind="freaking_out", id="task-42")
        assert e.to_dict() == {
            "type": "event", "kind": "freaking_out", "id": "task-42",
        }


class TestSnapshot:
    def test_empty_snapshot(self):
        s = Snapshot()
        assert s.to_dict() == {"type": "snapshot", "meeseeks": []}

    def test_snapshot_with_meeseeks(self):
        s = Snapshot(meeseeks=[
            Meeseeks(id="a", health=0.8, isFreakingOut=False,
                     name="Meeseeks-aaaa", task="t1"),
            Meeseeks(id="b", health=0.3, isFreakingOut=True),
        ])
        d = s.to_dict()
        assert d["type"] == "snapshot"
        assert len(d["meeseeks"]) == 2
        assert d["meeseeks"][0] == {
            "id": "a", "health": 0.8, "isFreakingOut": False,
            "name": "Meeseeks-aaaa", "task": "t1",
        }
        # b sem name/task — omitidos.
        assert d["meeseeks"][1] == {
            "id": "b", "health": 0.3, "isFreakingOut": True,
        }


class TestMeeseeksItem:
    def test_defaults_match_aquario_spec(self):
        m = Meeseeks(id="x")
        d = m.to_dict()
        assert d["health"] == 1.0
        assert d["isFreakingOut"] is False

    def test_truncates_long_name(self):
        m = Meeseeks(id="x", name="M" * 50)
        assert len(m.to_dict()["name"]) == NAME_MAX_LEN
