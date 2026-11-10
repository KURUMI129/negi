"""Traduce los errores de yt-dlp a algo que cualquiera entienda."""

from __future__ import annotations

import re

ANSI = re.compile(r"\x1b\[[0-9;]*m")

NO_DISPONIBLE = "El video no está disponible (borrado, privado o bloqueado en tu país)."

PISTAS = [
    ("unsupported url", "Ese enlace no es de un video que se pueda descargar."),
    ("is not a valid url", "Ese texto no es un enlace válido."),
    ("video unavailable", NO_DISPONIBLE),
    ("this video is unavailable", NO_DISPONIBLE),
    ("private video", "El video es privado."),
    ("sign in to confirm your age", "El video tiene restricción de edad y YouTube pide iniciar sesión."),
    ("sign in to confirm you", "YouTube pide iniciar sesión para este video. Prueba más tarde."),
    ("login required", "Esta página pide iniciar sesión para ver el video (pasa seguido en Instagram)."),
    ("requested content is not available", "La página no deja descargar este video sin iniciar sesión."),
    ("members-only", "El video es solo para miembros del canal."),
    ("live event will begin", "El directo todavía no ha empezado."),
    ("getaddrinfo failed", "No hay conexión a internet."),
    ("failed to resolve", "No hay conexión a internet."),
    ("timed out", "La conexión tardó demasiado. Inténtalo de nuevo."),
    ("no space left", "No queda espacio en el disco."),
    ("permission denied", "No se puede guardar en esa carpeta. Elige otra."),
    ("http error 403", "YouTube rechazó la descarga. Busca actualizaciones en Ajustes."),
]


def limpiar(texto: str) -> str:
    return ANSI.sub("", texto).replace("ERROR:", "").strip()


def mensaje_amigable(texto: str) -> str:
    detalle = limpiar(texto)
    bajo = detalle.lower()
    for clave, explicacion in PISTAS:
        if clave in bajo:
            return explicacion
    return ("No se pudo descargar. Si pasa con todos los videos, actualiza el programa "
            "en Ajustes → Buscar actualizaciones.\nDetalle: " + detalle[:240])
