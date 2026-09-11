"""
Message Queue — Fila de mensagens por sessao.
Permite enviar multiplas mensagens enquanto o processador esta ocupado.
"""
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Callable, Any


@dataclass
class QueuedMessage:
    user: str
    provider: str = "ollama"
    model: str = ""
    mood: str = ""
    root: str = ""
    images: list = field(default_factory=list)
    temperature: float = 0.7
    api_key: str = ""
    task_id: str = ""
    timestamp: float = 0.0
    interrupted: bool = False  # True se foi interrompida por mensagem urgente


class MessageQueue:
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._processing: dict[str, bool] = {}
        self._current_task: dict[str, Optional[QueuedMessage]] = {}

    def _get_queue(self, session_id: str) -> asyncio.Queue:
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue()
            self._processing[session_id] = False
            self._current_task[session_id] = None
        return self._queues[session_id]

    async def enqueue(self, session_id: str, msg: QueuedMessage) -> dict:
        """Adiciona mensagem na fila. Retorna status."""
        q = self._get_queue(session_id)
        await q.put(msg)
        position = q.qsize()
        is_processing = self._processing.get(session_id, False)

        return {
            "queued": True,
            "position": position,
            "is_processing": is_processing,
            "message": f"Mensagem enfileirada (posicao {position}). {'Processando tarefa anterior...' if is_processing else 'Iniciando processamento...'}"
        }

    async def dequeue(self, session_id: str) -> Optional[QueuedMessage]:
        """Remove e retorna a proxima mensagem da fila."""
        q = self._get_queue(session_id)
        if q.empty():
            return None
        return await q.get()

    def is_processing(self, session_id: str) -> bool:
        return self._processing.get(session_id, False)

    def set_processing(self, session_id: str, value: bool):
        self._processing[session_id] = value

    def set_current_task(self, session_id: str, task: Optional[QueuedMessage]):
        self._current_task[session_id] = task

    def get_current_task(self, session_id: str) -> Optional[QueuedMessage]:
        return self._current_task.get(session_id)

    def queue_size(self, session_id: str) -> int:
        q = self._queues.get(session_id)
        return q.qsize() if q else 0

    def get_status(self, session_id: str) -> dict:
        """Retorna status completo da fila."""
        q = self._get_queue(session_id)
        return {
            "is_processing": self._processing.get(session_id, False),
            "queue_size": q.qsize(),
            "current_task": self._current_task.get(session_id),
        }


# Singleton global
message_queue = MessageQueue()
