"""Cliente WebSocket pro aquário com reconnect + ring buffer.

One-way push do MMB pro aquário. Sem ack, sem polling. Falha de rede
ou servidor caído nunca derruba o bot — mensagens enfileiram num ring
buffer (descarta mais antiga quando cheio), e o reconnect transparente
retoma o envio assim que o servidor volta.

Modelo de uso:
    client = AquarioClient("ws://localhost:8080/ws")
    await client.start()
    client.emit(Event(kind="born", id="task-42", name="...", task="..."))
    ...
    await client.stop()
"""

import asyncio
import json
import random
from collections import deque
from typing import Any, Awaitable, Callable, Optional, Protocol


# Backoff exponencial 1→2→5→10→30 com cap em 30. Decisão fechada do brief.
DEFAULT_BACKOFF_S: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 30.0)
DEFAULT_BUFFER_SIZE = 1000
DEFAULT_PING_INTERVAL = 20
DEFAULT_PING_TIMEOUT = 10
JITTER_RATIO = 0.2


class _HasToDict(Protocol):
    def to_dict(self) -> dict: ...


def _next_delay(
    attempt: int,
    *,
    backoff: tuple[float, ...] = DEFAULT_BACKOFF_S,
    rand: Callable[[], float] = random.random,
) -> float:
    """Delay pro próximo reconnect com jitter ±JITTER_RATIO.

    `attempt` é zero-based; valores acima do tamanho da tabela ficam
    no último step (cap). `rand` recebível pra facilitar teste
    determinístico."""
    base = backoff[min(max(attempt, 0), len(backoff) - 1)]
    # rand() ∈ [0,1) → mapeia pra [-JITTER_RATIO, +JITTER_RATIO).
    jitter = (rand() * 2 - 1) * JITTER_RATIO
    return max(0.05, base * (1 + jitter))


class AquarioClient:
    """Pipe assíncrono pro WebSocket do aquário.

    `emit` é sync — só enfileira. Uma task de fundo drena a fila no
    socket, reconectando transparentemente sob falha. Quando o buffer
    está cheio, descarta a mensagem mais antiga (FIFO drop).
    """

    def __init__(
        self,
        ws_url: str,
        *,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        ping_interval: int = DEFAULT_PING_INTERVAL,
        ping_timeout: int = DEFAULT_PING_TIMEOUT,
        backoff: tuple[float, ...] = DEFAULT_BACKOFF_S,
        connect_fn: Optional[Callable[..., Awaitable[Any]]] = None,
        snapshot_provider: Optional[Callable[[], _HasToDict]] = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rand: Callable[[], float] = random.random,
    ) -> None:
        self._url = ws_url
        self._buffer: deque[dict] = deque(maxlen=buffer_size)
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout
        self._backoff = backoff
        self._connect_fn = connect_fn
        self._snapshot_provider = snapshot_provider
        self._sleep = sleep
        self._rand = rand
        self._has_item = asyncio.Event()
        self._stop_requested = False
        self._task: Optional[asyncio.Task] = None
        self._connected = asyncio.Event()

    # ── API pública ──────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_requested = False
        self._task = asyncio.create_task(self._run(), name="aquario-client")

    async def stop(self, *, drain_timeout_s: float = 2.0) -> None:
        """Pede pra parar; espera drain ou timeout, e cancela o task."""
        self._stop_requested = True
        # Tenta deixar o loop drenar naturalmente antes de cancelar.
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=drain_timeout_s)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
                try:
                    await self._task
                except (asyncio.CancelledError, Exception):
                    pass
            self._task = None

    def emit(self, message: _HasToDict) -> None:
        """Enfileira uma mensagem. Sync, nunca bloqueia, nunca raises.

        Se o buffer estiver cheio, a mensagem mais antiga é descartada
        — ring-buffer FIFO. Aquário tolera gaps; o que ele NÃO tolera
        é perder o `born`. Cliente do bot.py é responsável por garantir
        ordem (born vem antes de state/event do mesmo id) — esta
        camada não reordena."""
        try:
            payload = message.to_dict()
        except Exception as e:
            print(f"[warn] aquario: payload inválido: {e}")
            return
        if (
            len(self._buffer) == self._buffer.maxlen
            and self._buffer.maxlen is not None
        ):
            # Ring buffer cheio — vamos sobrescrever a mais antiga.
            # Loga uma vez quando começa a descartar pra não inundar.
            pass
        self._buffer.append(payload)
        self._has_item.set()

    @property
    def buffered(self) -> int:
        """Quantas mensagens estão na fila esperando envio."""
        return len(self._buffer)

    # ── loop interno ─────────────────────────────────────────────────────

    async def _run(self) -> None:
        attempt = 0
        while not self._stop_requested:
            try:
                async with await self._open() as ws:
                    attempt = 0  # conexão ok → reseta backoff
                    self._connected.set()
                    await self._announce_snapshot(ws)
                    await self._drain_loop(ws)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[warn] aquario: conexão caiu ({e!r})")
            finally:
                self._connected.clear()
            if self._stop_requested:
                break
            delay = _next_delay(
                attempt, backoff=self._backoff, rand=self._rand
            )
            attempt += 1
            try:
                await self._sleep(delay)
            except asyncio.CancelledError:
                raise

    async def _open(self):
        if self._connect_fn is not None:
            return await self._connect_fn(self._url)
        # Import tardio: falha mais clara se a lib não estiver instalada
        # e mantém este módulo importável em testes sem websockets.
        import websockets
        return await websockets.connect(
            self._url,
            ping_interval=self._ping_interval,
            ping_timeout=self._ping_timeout,
        )

    async def _announce_snapshot(self, ws) -> None:
        if self._snapshot_provider is None:
            return
        try:
            snap = self._snapshot_provider()
            await ws.send(json.dumps(snap.to_dict()))
        except Exception as e:
            print(f"[warn] aquario: falha anunciando snapshot: {e!r}")

    async def _drain_loop(self, ws) -> None:
        while True:
            while not self._buffer:
                if self._stop_requested:
                    return
                self._has_item.clear()
                await self._has_item.wait()
            # Peek antes de send: se o socket cair, a mensagem
            # permanece no buffer e é reenviada após reconnect.
            payload = self._buffer[0]
            await ws.send(json.dumps(payload))
            self._buffer.popleft()
