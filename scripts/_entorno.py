"""Utilidades básicas de los scripts: raíz del proyecto, lectura de .env y entorno virtual (solo biblioteca estándar)."""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def en_venv() -> bool:
    """True si el intérprete actual es el de un entorno virtual."""
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def avisar_si_fuera_de_venv() -> None:
    if not en_venv():
        print("AVISO: ejecutando fuera de .venv. Usa .venv/bin/python.", file=sys.stderr)


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def cargar_env(ruta: Path | None = None) -> dict[str, str]:
    """Lector mínimo de .env (KEY=valor). No exporta nada al entorno."""
    ruta = ruta or RAIZ / ".env"
    datos: dict[str, str] = {}
    if not ruta.exists():
        return datos
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        datos[k.strip()] = v.strip().strip("'\"")
    return datos
