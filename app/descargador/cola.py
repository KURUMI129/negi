"""Cola de descargas: se bajan de una en una, en orden. Si una falla, sigue la siguiente."""

from __future__ import annotations

import threading
import uuid
from typing import Callable

from . import historial, motor

FINALES = ("listo", "error", "cancelado")


class Cola:
    def __init__(self, al_evento: Callable[[dict], None], fabrica=motor.Descarga) -> None:
        self._emitir = al_evento
        self._fabrica = fabrica
        self._candado = threading.RLock()
        self._espera: list[dict] = []
        self._actual: dict | None = None
        self._descarga = None

    # --- consulta --------------------------------------------------------
    def elementos(self) -> list[dict]:
        with self._candado:
            return [dict(e) for e in ([self._actual] if self._actual else []) + self._espera]

    def ocupada(self) -> bool:
        with self._candado:
            return self._actual is not None or bool(self._espera)

    def descargando(self) -> bool:
        with self._candado:
            return self._actual is not None

    # --- cambios ---------------------------------------------------------
    def agregar(self, url: str, modo: str, calidad: int | None, carpeta: str, titulo: str = "",
                miniatura: str = "", lista: bool = False, al_frente: bool = False) -> str:
        e = {"id": uuid.uuid4().hex[:10], "url": url, "modo": modo, "calidad": calidad, "carpeta": carpeta,
             "titulo": titulo or url, "miniatura": miniatura, "lista": lista, "estado": "espera", "pct": None}
        with self._candado:
            if al_frente:
                self._espera.insert(0, e)
            else:
                self._espera.append(e)
        self._avisar_lista()
        self._siguiente()
        return e["id"]

    def quitar(self, ident: str) -> None:
        with self._candado:
            if self._actual and self._actual["id"] == ident:
                self._actual["estado"] = "cancelando"
                descarga = self._descarga
            else:
                self._espera = [e for e in self._espera if e["id"] != ident]
                descarga = None
        if descarga:
            descarga.cancelar()
        self._avisar_lista()

    def cancelar_todo_y_esperar(self, timeout: float = 10) -> None:
        """Al cerrar la app: vacía la cola, cancela la descarga actual y deja que limpie."""
        with self._candado:
            self._espera.clear()
            descarga = self._descarga
        if descarga:
            descarga.cancelar()
            descarga.esperar(timeout)

    # --- interno ---------------------------------------------------------
    def _avisar_lista(self) -> None:
        self._emitir({"tipo": "cola", "elementos": self.elementos()})

    def _siguiente(self) -> None:
        with self._candado:
            if self._actual is not None or not self._espera:
                return
            e = self._espera.pop(0)
            e["estado"] = "descargando"
            self._actual = e
            self._descarga = self._fabrica(e["url"], e["modo"], e["carpeta"],
                                           lambda ev, ident=e["id"]: self._al_evento(ident, ev),
                                           lista=e["lista"], calidad=e["calidad"])
            descarga = self._descarga
        self._avisar_lista()
        descarga.iniciar()

    def _al_evento(self, ident: str, evento: dict) -> None:
        with self._candado:
            e = self._actual if self._actual and self._actual["id"] == ident else None
        if e is None:
            return
        evento = {**evento, "id": ident, "titulo": e["titulo"]}
        if evento["tipo"] == "progreso":
            e["pct"] = evento.get("pct")
        if evento["tipo"] not in FINALES:
            self._emitir(evento)
            return
        if evento["tipo"] == "listo":
            try:
                evento["historial"] = historial.agregar({
                    "titulo": e["titulo"], "archivo": evento["archivo"], "miniatura": e["miniatura"],
                    "modo": e["modo"], "calidad": e["calidad"], "cantidad": evento.get("cantidad", 1)})
            except OSError:
                pass  # el historial es un extra: la descarga sí se completó
        with self._candado:
            self._actual = None
            self._descarga = None
            quedan = len(self._espera)
        evento["quedan"] = quedan
        self._emitir(evento)
        self._avisar_lista()
        self._siguiente()
