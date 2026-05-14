"""Testes do AquarioClient sem WS real.

Injeta `connect_fn`, `sleep` e `rand` pra eliminar IO e flakiness.
Foca em comportamento observável: enqueue, drop, backoff, drain,
stop gracioso.
"""

import asyncio
import json

import pytest

from aquario.client import (
    DEFAULT_BACKOFF_S,
    JITTER_RATIO,
    AquarioClient,
    _next_delay,
)
from aquario.messages import Event, Snapshot, State


# ─── Fake WebSocket ──────────────────────────────────────────────────────

class FakeWS:
    """Substituto do WebSocketClientProtocol pros testes.

    Implementa só o que o cliente toca: `send`, `__aenter__/__aexit__`.
    Pode ser configurado pra simular disconnect após N envios.
    """

    def __init__(self, *, fail_after: int | None = None):
        self.sent: list[str] = []
        self.closed = False
        self._fail_after = fail_after

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        self.closed = True
        return False

    async def send(self, msg: str) -> None:
        if (
            self._fail_after is not None
            and len(self.sent) >= self._fail_after
        ):
            raise ConnectionError("simulated disconnect")
        self.sent.append(msg)


def make_connect(*sockets: FakeWS):
    """Devolve um connect_fn que entrega `sockets` em sequência.

    Quando esgota a lista, levanta ConnectionRefusedError (servidor
    fora do ar) — útil pra testar backoff sem loop infinito."""
    pool = list(sockets)

    async def connect(url):
        if not pool:
            raise ConnectionRefusedError("no more fake sockets")
        return pool.pop(0)

    return connect


# ─── _next_delay ─────────────────────────────────────────────────────────

class TestNextDelay:
    def test_first_attempt_uses_first_step(self):
        d = _next_delay(0, backoff=(1.0, 2.0, 5.0), rand=lambda: 0.5)
        assert d == pytest.approx(1.0)  # jitter neutro com rand=0.5

    def test_steps_through_table(self):
        zero_jitter = lambda: 0.5  # noqa: E731
        assert _next_delay(0, backoff=(1, 2, 5), rand=zero_jitter) == 1
        assert _next_delay(1, backoff=(1, 2, 5), rand=zero_jitter) == 2
        assert _next_delay(2, backoff=(1, 2, 5), rand=zero_jitter) == 5

    def test_caps_at_last_step(self):
        d = _next_delay(99, backoff=(1, 2, 5, 30), rand=lambda: 0.5)
        assert d == pytest.approx(30.0)

    def test_jitter_within_bounds(self):
        # rand=0 → jitter = -JITTER_RATIO; rand→1 → jitter ≈ +JITTER_RATIO.
        low = _next_delay(0, backoff=(10.0,), rand=lambda: 0.0)
        high = _next_delay(0, backoff=(10.0,), rand=lambda: 0.9999)
        assert low == pytest.approx(10.0 * (1 - JITTER_RATIO))
        assert high == pytest.approx(10.0 * (1 + JITTER_RATIO), rel=1e-3)

    def test_default_backoff_matches_brief(self):
        # 1 → 2 → 5 → 10 → 30s, cap em 30. Decisão fechada do brief.
        assert DEFAULT_BACKOFF_S == (1.0, 2.0, 5.0, 10.0, 30.0)


# ─── emit / ring buffer ──────────────────────────────────────────────────

class TestEmitAndBuffer:
    def test_emit_increases_buffered(self):
        c = AquarioClient("ws://x", buffer_size=10)
        assert c.buffered == 0
        c.emit(State(id="a", health=1.0))
        c.emit(State(id="a", health=0.9))
        assert c.buffered == 2

    def test_emit_never_raises_on_bad_payload(self):
        c = AquarioClient("ws://x")

        class Broken:
            def to_dict(self):
                raise RuntimeError("kaboom")

        c.emit(Broken())  # type: ignore[arg-type]
        assert c.buffered == 0  # nada enfileirado, sem crash

    def test_ring_buffer_drops_oldest_when_full(self):
        c = AquarioClient("ws://x", buffer_size=3)
        for i in range(5):
            c.emit(State(id=f"task-{i}", health=1.0))
        assert c.buffered == 3
        # As 3 mais recentes devem ter sobrevivido.
        ids = [p["id"] for p in list(c._buffer)]
        assert ids == ["task-2", "task-3", "task-4"]


# ─── drain ───────────────────────────────────────────────────────────────

class TestDrain:
    async def test_drains_queued_messages_on_connect(self):
        ws = FakeWS()
        c = AquarioClient(
            "ws://x",
            connect_fn=make_connect(ws),
            sleep=lambda d: asyncio.sleep(0),
        )
        c.emit(Event(kind="born", id="task-1", name="Meeseeks-x", task="t"))
        c.emit(State(id="task-1", health=0.8))

        await c.start()
        await _wait_until(lambda: len(ws.sent) >= 2)
        await c.stop()

        sent = [json.loads(m) for m in ws.sent]
        assert sent[0]["kind"] == "born"
        assert sent[1]["type"] == "state"

    async def test_emit_after_start_also_drains(self):
        ws = FakeWS()
        c = AquarioClient(
            "ws://x",
            connect_fn=make_connect(ws),
            sleep=lambda d: asyncio.sleep(0),
        )
        await c.start()
        c.emit(Event(kind="died_happy", id="task-9"))
        await _wait_until(lambda: len(ws.sent) >= 1)
        await c.stop()
        assert json.loads(ws.sent[0])["kind"] == "died_happy"


# ─── reconnect ───────────────────────────────────────────────────────────

class TestReconnect:
    async def test_reconnects_after_disconnect(self):
        # Primeira conexão falha após 1 send; segunda funciona.
        ws1 = FakeWS(fail_after=1)
        ws2 = FakeWS()
        delays: list[float] = []

        async def record_sleep(d):
            delays.append(d)

        c = AquarioClient(
            "ws://x",
            connect_fn=make_connect(ws1, ws2),
            sleep=record_sleep,
            rand=lambda: 0.5,  # jitter neutro
            backoff=(1.0, 2.0),
        )
        c.emit(State(id="a", health=1.0))  # ws1 envia este e cai
        c.emit(State(id="a", health=0.5))  # ws2 deve enviar este

        await c.start()
        await _wait_until(lambda: len(ws2.sent) >= 1, timeout=2)
        await c.stop()

        assert len(ws1.sent) == 1
        assert len(ws2.sent) >= 1
        # Backoff: 1 sleep entre as conexões.
        assert delays and delays[0] == pytest.approx(1.0)

    async def test_backoff_progresses_through_failures(self):
        delays: list[float] = []

        async def record_sleep(d):
            delays.append(d)
            # Trava na primeira espera longa pra controlarmos o loop.
            if len(delays) >= 3:
                await asyncio.sleep(0.05)

        async def always_fail(url):
            raise ConnectionRefusedError("nope")

        c = AquarioClient(
            "ws://x",
            connect_fn=always_fail,
            sleep=record_sleep,
            rand=lambda: 0.5,
            backoff=(1.0, 2.0, 5.0),
        )
        await c.start()
        await _wait_until(lambda: len(delays) >= 3, timeout=2)
        await c.stop()
        # Cada falha consecutiva avança no backoff.
        assert delays[0] == pytest.approx(1.0)
        assert delays[1] == pytest.approx(2.0)
        assert delays[2] == pytest.approx(5.0)


# ─── snapshot no (re)connect ─────────────────────────────────────────────

class TestSnapshot:
    async def test_snapshot_provider_called_on_connect(self):
        ws = FakeWS()
        calls = 0

        def provider():
            nonlocal calls
            calls += 1
            return Snapshot()

        c = AquarioClient(
            "ws://x",
            connect_fn=make_connect(ws),
            snapshot_provider=provider,
            sleep=lambda d: asyncio.sleep(0),
        )
        await c.start()
        await _wait_until(lambda: len(ws.sent) >= 1)
        await c.stop()
        assert calls == 1
        assert json.loads(ws.sent[0])["type"] == "snapshot"


# ─── stop gracioso ───────────────────────────────────────────────────────

class TestStop:
    async def test_stop_is_idempotent(self):
        c = AquarioClient(
            "ws://x",
            connect_fn=make_connect(FakeWS()),
            sleep=lambda d: asyncio.sleep(0),
        )
        await c.start()
        await c.stop()
        await c.stop()  # segunda chamada não deve raise

    async def test_stop_without_start_is_safe(self):
        c = AquarioClient("ws://x")
        await c.stop()


# ─── helper ──────────────────────────────────────────────────────────────

async def _wait_until(predicate, *, timeout: float = 1.0) -> None:
    """Polling cooperativo até `predicate()` ser truthy ou estourar."""
    deadline = asyncio.get_event_loop().time() + timeout
    while not predicate():
        if asyncio.get_event_loop().time() > deadline:
            raise AssertionError("timeout esperando condição")
        await asyncio.sleep(0.01)
