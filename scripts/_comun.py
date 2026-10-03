"""Utilidades compartidas por los scripts de la bóveda (solo biblioteca estándar)."""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETAS_IGNORADAS = {".obsidian", ".claude", ".git", ".venv", "scripts", "node_modules", "datos"}
ARCHIVOS_SISTEMA = {"CLAUDE.md", "README.md"}  # no son notas de la bóveda

RE_WIKILINK = re.compile(r"(?<!!)\[\[([^\]\|#\^]+)(?:[#\^][^\]\|]*)?(?:\|[^\]]*)?\]\]")
RE_CODIGO = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)


def en_venv() -> bool:
    """True si el intérprete actual es el de un entorno virtual."""
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def avisar_si_fuera_de_venv() -> None:
    if not en_venv():
        print("AVISO: ejecutando fuera de .venv. Usa .venv/bin/python (regla R11).", file=sys.stderr)


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def notas() -> list[Path]:
    """Todas las notas .md de la bóveda (sin carpetas técnicas ni archivos de sistema)."""
    resultado = []
    for ruta in sorted(RAIZ.rglob("*.md")):
        partes = set(ruta.relative_to(RAIZ).parts[:-1])
        if partes & CARPETAS_IGNORADAS or ruta.name in ARCHIVOS_SISTEMA:
            continue
        resultado.append(ruta)
    return resultado


def leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def separar_frontmatter(texto: str) -> tuple[dict[str, list[str]] | None, str]:
    """Devuelve (propiedades, cuerpo). Propiedades es None si no hay frontmatter."""
    if not texto.startswith("---\n"):
        return None, texto
    fin = texto.find("\n---", 4)
    if fin == -1:
        return None, texto
    bloque, cuerpo = texto[4:fin], texto[fin + 4:]
    props: dict[str, list[str]] = {}
    clave = None
    for linea in bloque.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", linea)
        if m:
            clave, valor = m.group(1), m.group(2).strip()
            props[clave] = []
            if valor.startswith("[") and valor.endswith("]"):
                props[clave] = [v.strip().strip("'\"") for v in valor[1:-1].split(",") if v.strip()]
            elif valor:
                props[clave] = [valor.strip("'\"")]
        elif clave and re.match(r"^\s+-\s+", linea):
            props[clave].append(re.sub(r"^\s+-\s+", "", linea).strip().strip("'\""))
    return props, cuerpo


def wikilinks(texto: str) -> list[str]:
    return [m.strip() for m in RE_WIKILINK.findall(RE_CODIGO.sub("", texto))]


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


def claves_env(ruta: Path) -> list[str]:
    return list(cargar_env(ruta).keys()) if ruta.exists() else []


def num(texto: str) -> float:
    """'1.831' -> 1831 ; '10,3' -> 10.3 (formato es-CO)."""
    t = texto.strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        return float(t.replace(".", ""))
    return float(t.replace(",", "."))
