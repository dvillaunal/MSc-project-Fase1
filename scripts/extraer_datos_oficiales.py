#!/usr/bin/env python3
"""Descarga y cruza datos oficiales abiertos sobre feminicidio y homicidio de mujeres.

Fuentes (todas en datos.gov.co, API Socrata, sin clave obligatoria):
  * Fiscalía General de la Nación - Víctimas V3 (hr73-zqjf): delito de feminicidio (Art. 104A C.P.).
  * Policía Nacional / MinDefensa - HOMICIDIO (m8fd-ahd9): homicidios intencionales por sexo, arma, zona.
  * Medicina Legal - Presuntos homicidios 2015-2024 definitivos (vtub-3de2) y preliminar 2025-2026 (2kpj-cktv).
  * DANE - Proyecciones de población departamental por sexo 2018-2050 (archivo xlsx, se descarga una vez).

Escribe:
  03_Fuentes_y_Datos/datos/crudos/<fuente>/*.json      respuestas originales de la API (con URL y fecha)
  03_Fuentes_y_Datos/datos/procesados/*.csv             tablas ordenadas
  03_Fuentes_y_Datos/Datos_Oficiales_Feminicidio.md     nota con resultados y clasificación (A1-F6)

Uso:  .venv/bin/python scripts/extraer_datos_oficiales.py
Requiere internet. Credenciales opcionales en .env: SOCRATA_APP_TOKEN, o SOCRATA_API_KEY_ID + SOCRATA_API_KEY_SECRET.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from _comun import RAIZ, avisar_si_fuera_de_venv, cargar_env, sin_acentos

DATOS = RAIZ / "03_Fuentes_y_Datos" / "datos"
CRUDOS, PROC = DATOS / "crudos", DATOS / "procesados"
NOTA = RAIZ / "03_Fuentes_y_Datos" / "Datos_Oficiales_Feminicidio.md"
API = "https://www.datos.gov.co/resource/{}.json"
PAGINA = "https://www.datos.gov.co/d/{}"
DANE_URL = ("https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Departamental/"
            "PPED-AreaSexoEdadDep-2018-2050_VP.xlsx")
DANE_XLSX = CRUDOS / "dane" / "PPED-AreaSexoEdadDep-2018-2050_VP.xlsx"
HOY = date.today().isoformat()

FUENTES = {
    "fiscalia": {"id": "hr73-zqjf", "nombre": "Fiscalía General de la Nación – Víctimas V3", "clasif_letra": "B"},
    "policia": {"id": "m8fd-ahd9", "nombre": "Policía Nacional / MinDefensa – Homicidio", "clasif_letra": "B"},
    "ml_def": {"id": "vtub-3de2", "nombre": "Medicina Legal – Presuntos homicidios 2015-2024 (definitivo)", "clasif_letra": "B"},
    "ml_pre": {"id": "2kpj-cktv", "nombre": "Medicina Legal – Lesiones fatales 2025-2026 (preliminar)", "clasif_letra": "B"},
}
AGRESOR_PAREJA = ("pareja", "compañero", "esposo", "novio", "amante")
NO_PAREJA = ("trabajo", "estudio", "celda", "familiar")


# ---------------------------------------------------------------- descarga
def consultar(clave: str, nombre: str, **soql) -> pd.DataFrame:
    """Consulta agregada SoQL. Guarda la respuesta cruda con su URL y fecha."""
    ds = FUENTES[clave]["id"]
    params = {f"${k}": v for k, v in soql.items()}
    params.setdefault("$limit", 50000)
    cab, auth = {}, None
    env = cargar_env()
    if env.get("SOCRATA_APP_TOKEN"):
        cab["X-App-Token"] = env["SOCRATA_APP_TOKEN"]
    if env.get("SOCRATA_API_KEY_ID") and env.get("SOCRATA_API_KEY_SECRET"):
        auth = (env["SOCRATA_API_KEY_ID"], env["SOCRATA_API_KEY_SECRET"])  # «API Key»: ID + clave secreta
    for intento in range(3):
        try:
            r = requests.get(API.format(ds), params=params, headers=cab, auth=auth, timeout=600)
            r.raise_for_status()
            break
        except requests.RequestException as e:
            if intento == 2:
                raise
            print(f"  reintento {intento + 1} ({clave}/{nombre}): {e}")
            time.sleep(10)
    filas = r.json()
    destino = CRUDOS / clave
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"{nombre}.json").write_text(json.dumps(
        {"fuente": FUENTES[clave]["nombre"], "dataset": ds, "url": r.url, "consultado": HOY, "filas": filas},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {clave}/{nombre}: {len(filas)} filas")
    return pd.DataFrame(filas)


def norm_depto(nombre: str) -> str:
    n = sin_acentos(str(nombre)).upper().strip()
    n = n.replace(", D.C.", "").replace(" D.C.", "").replace("D.C", "").strip()
    reemplazos = {"BOGOTA": "BOGOTA", "SAN ANDRES": "SAN ANDRES", "ARCHIPIELAGO DE SAN ANDRES": "SAN ANDRES",
                  "VALLE": "VALLE DEL CAUCA", "NORTE SANTANDER": "NORTE DE SANTANDER", "GUAJIRA": "LA GUAJIRA"}
    for k, v in reemplazos.items():
        if n.startswith(k):
            return v
    return n


def poblacion_mujeres() -> pd.DataFrame:
    if not DANE_XLSX.exists():
        DANE_XLSX.parent.mkdir(parents=True, exist_ok=True)
        DANE_XLSX.write_bytes(requests.get(DANE_URL, timeout=300, headers={"User-Agent": "Mozilla/5.0"}).content)
    df = pd.read_excel(DANE_XLSX, sheet_name="PobDepartamentalxÁreaSexoEdad", header=None, skiprows=9, usecols=[0, 1, 2, 3, 6])
    df.columns = ["cod", "departamento", "anio", "area", "mujeres"]
    df = df[df["area"] == "Total"].dropna(subset=["anio"])
    df["anio"] = df["anio"].astype(int)
    df["departamento"] = df["departamento"].map(norm_depto)
    return df[["departamento", "anio", "mujeres"]]


# ---------------------------------------------------------------- extracción
def extraer() -> dict[str, pd.DataFrame]:
    t: dict[str, pd.DataFrame] = {}
    print("Fiscalía (consulta lenta)...")
    f = consultar("fiscalia", "feminicidio_depto_anio",
                  select="departamento_hecho_origen as departamento, a_o_hecho_origen as anio, count(*) as n",
                  where="delito like 'Feminicidio%'", group="departamento, anio")
    f["medida"] = "Fiscalía: víctimas registradas por feminicidio"
    t["fiscalia"] = f

    print("Policía...")
    p = consultar("policia", "homicidio_mujeres_depto_anio",
                  select="departamento, date_extract_y(fecha_hecho) as anio, sum(cantidad) as n",
                  where="sexo='FEMENINO'", group="departamento, anio")
    p["medida"] = "Policía: homicidios de mujeres"
    t["policia"] = p
    t["policia_arma"] = consultar("policia", "antioquia_arma_anio",
                                  select="arma_medio, date_extract_y(fecha_hecho) as anio, sum(cantidad) as n",
                                  where="sexo='FEMENINO' AND cod_depto='05'", group="arma_medio, anio")
    t["policia_zona"] = consultar("policia", "antioquia_zona_anio",
                                  select="zona, date_extract_y(fecha_hecho) as anio, sum(cantidad) as n",
                                  where="sexo='FEMENINO' AND cod_depto='05'", group="zona, anio")
    t["policia_muni"] = consultar("policia", "antioquia_municipio",
                                  select="municipio, sum(cantidad) as n",
                                  where="sexo='FEMENINO' AND cod_depto='05' AND fecha_hecho >= '2018-01-01'",
                                  group="municipio", order="n DESC")

    print("Medicina Legal...")
    m = consultar("ml_def", "homicidio_mujeres_depto_anio",
                  select="departamento_del_hecho_dane as departamento, a_o_del_hecho as anio, count(*) as n",
                  where="sexo_de_la_victima='Mujer'", group="departamento, anio")
    m["medida"] = "Medicina Legal: homicidios de mujeres"
    m2 = consultar("ml_pre", "homicidio_mujeres_depto_anio",
                   select="departamento_del_hecho_dane as departamento, a_o_del_hecho as anio, count(*) as n",
                   where="sexo_de_la_victima='Mujer' AND manera_de_muerte='1 Presuntos Homicidios'",
                   group="departamento, anio")
    m2["medida"] = "Medicina Legal: homicidios de mujeres"
    m2["preliminar"] = True
    t["ml"] = pd.concat([m, m2], ignore_index=True)
    a1 = consultar("ml_def", "agresor_depto_anio",
                   select="departamento_del_hecho_dane as departamento, a_o_del_hecho as anio, presunto_agresor_detallado as agresor, count(*) as n",
                   where="sexo_de_la_victima='Mujer'", group="departamento, anio, agresor")
    t["ml_agresor"] = a1
    return t


# ---------------------------------------------------------------- análisis
def limpiar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["departamento"] = df["departamento"].map(norm_depto)
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce")
    df["n"] = pd.to_numeric(df["n"], errors="coerce").fillna(0)
    df = df.dropna(subset=["anio"])
    df["anio"] = df["anio"].astype(int)
    return df


def tabla_anual(df: pd.DataFrame, pob: pd.DataFrame) -> pd.DataFrame:
    """Antioquia vs Colombia por año: casos, % nacional, tasa por 100.000 mujeres y puesto."""
    df = df.groupby(["departamento", "anio"], as_index=False)["n"].sum()
    nac = df.groupby("anio", as_index=False)["n"].sum().rename(columns={"n": "colombia"})
    pob_nac = pob.groupby("anio", as_index=False)["mujeres"].sum().rename(columns={"mujeres": "mujeres_col"})
    dd = df.merge(pob, on=["departamento", "anio"], how="left")
    dd["tasa"] = dd["n"] / dd["mujeres"] * 1e5
    dd["puesto"] = dd.groupby("anio")["tasa"].rank(ascending=False, method="min")
    ant = dd[dd["departamento"] == "ANTIOQUIA"][["anio", "n", "tasa", "puesto"]]
    out = nac.merge(ant, on="anio", how="left").merge(pob_nac, on="anio", how="left")
    out["pct_nacional"] = out["n"] / out["colombia"] * 100
    out["tasa_colombia"] = out["colombia"] / out["mujeres_col"] * 1e5
    out["anio"] = out["anio"].astype(int)
    return out.sort_values("anio")


def ranking(df: pd.DataFrame, pob: pd.DataFrame, anio: int) -> pd.DataFrame:
    d = df[df["anio"] == anio].groupby("departamento", as_index=False)["n"].sum().merge(
        pob[pob["anio"] == anio], on="departamento", how="left")
    d["tasa"] = d["n"] / d["mujeres"] * 1e5
    return d.sort_values("tasa", ascending=False).reset_index(drop=True)


def codigo_corroboracion(a: float, b: float) -> tuple[str, float]:
    """Número de credibilidad según acuerdo entre dos fuentes independientes."""
    if not a or not b or pd.isna(a) or pd.isna(b):
        return "6", float("nan")
    dif = abs(a - b) / max(a, b) * 100
    return ("2" if dif <= 10 else "3" if dif <= 25 else "4"), dif


def fmt(x, dec=0) -> str:
    if pd.isna(x):
        return "—"
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> int:
    avisar_si_fuera_de_venv()
    PROC.mkdir(parents=True, exist_ok=True)
    pob = poblacion_mujeres()
    pob.to_csv(PROC / "dane_mujeres_depto_anio.csv", index=False)
    t = extraer()
    fis, pol, ml = limpiar(t["fiscalia"]), limpiar(t["policia"]), limpiar(t["ml"])
    for k, df in (("fiscalia_feminicidio_depto_anio", fis), ("policia_homicidio_mujeres_depto_anio", pol),
                  ("ml_homicidio_mujeres_depto_anio", ml)):
        df.to_csv(PROC / f"{k}.csv", index=False)

    an_f, an_p, an_m = tabla_anual(fis, pob), tabla_anual(pol, pob), tabla_anual(ml, pob)
    ultimo = 2024  # último año con cifras definitivas de Medicina Legal
    rk = {"Fiscalía (feminicidio)": ranking(fis, pob, ultimo), "Policía (homicidio de mujeres)": ranking(pol, pob, ultimo),
          "Medicina Legal (homicidio de mujeres)": ranking(ml[ml["anio"] <= 2024], pob, ultimo)}

    # corroboración Policía vs Medicina Legal (Antioquia)
    corr = an_p[["anio", "n"]].merge(an_m[["anio", "n"]], on="anio", suffixes=("_pol", "_ml"))
    corr[["codigo", "dif"]] = corr.apply(lambda r: pd.Series(codigo_corroboracion(r["n_pol"], r["n_ml"])), axis=1)

    # agresor pareja/expareja (Medicina Legal)
    ag = limpiar(t["ml_agresor"])
    baja = ag["agresor"].str.lower()
    ag["pareja"] = baja.str.contains("|".join(AGRESOR_PAREJA), na=False) & ~baja.str.contains("|".join(NO_PAREJA), na=False)
    ag_ant = ag[ag["departamento"] == "ANTIOQUIA"].groupby("anio").apply(
        lambda g: pd.Series({"total": g["n"].sum(), "pareja": g.loc[g["pareja"], "n"].sum(),
                             "sin_info": g.loc[g["agresor"].str.contains("Sin información|Sin Información|desconocido", case=False, na=False), "n"].sum()}),
        include_groups=False).reset_index()
    ag_col = ag.groupby("anio").apply(lambda g: pd.Series({"total": g["n"].sum(), "pareja": g.loc[g["pareja"], "n"].sum()}),
                                      include_groups=False).reset_index()
    agresores_ant = (ag[(ag["departamento"] == "ANTIOQUIA") & (ag["anio"] >= 2020)]
                     .groupby("agresor", as_index=False)["n"].sum().sort_values("n", ascending=False).head(10))

    arma = limpiar(t["policia_arma"].assign(departamento="ANTIOQUIA"))
    zona = limpiar(t["policia_zona"].assign(departamento="ANTIOQUIA"))
    muni = t["policia_muni"].copy()
    muni["n"] = pd.to_numeric(muni["n"])
    for k, df in (("antioquia_arma_anio", arma), ("antioquia_zona_anio", zona), ("antioquia_municipio_2018_hoy", muni),
                  ("antioquia_agresor_anio", ag[ag["departamento"] == "ANTIOQUIA"])):
        df.to_csv(PROC / f"{k}.csv", index=False)

    escribir_nota(an_f, an_p, an_m, rk, corr, ag_ant, ag_col, agresores_ant, arma, zona, muni, ultimo)
    print(f"Nota escrita: {NOTA.relative_to(RAIZ)}")
    return 0


# ---------------------------------------------------------------- nota markdown
def escribir_nota(an_f, an_p, an_m, rk, corr, ag_ant, ag_col, agresores_ant, arma, zona, muni, ultimo) -> None:
    L = ["---", "tags:", "  - datos-oficiales", "  - feminicidio", "  - tesis-antioquia", "  - fuente",
         "aliases:", "  - Datos oficiales de feminicidio", "tipo: fuente", "clasificacion: B3", f"actualizado: {HOY}", "---", "",
         "# Datos oficiales: feminicidio y homicidio de mujeres en Antioquia y Colombia", "",
         f"Generado por `scripts/extraer_datos_oficiales.py` el {HOY} con datos abiertos de datos.gov.co y el DANE. "
         "No se editó a mano: para actualizar, vuelve a ejecutar el script. Clasificación según [[Sistema_de_Clasificacion_de_Fuentes]].", "",
         "> [!warning] Tres medidas distintas, no se suman ni se comparan como si fueran la misma",
         "> - **Fiscalía:** víctimas registradas en procesos por el delito de feminicidio (Art. 104A). Una persona puede aparecer más de una vez. Los años recientes están incompletos porque la tipificación tarda.",
         "> - **Policía:** homicidios intencionales de mujeres (todas las causas, no solo feminicidio).",
         "> - **Medicina Legal:** presuntos homicidios de mujeres según necropsia; 2015-2024 definitivo, 2025-2026 preliminar.",
         "> La tasa es por 100.000 mujeres con la población proyectada por el DANE (solo desde 2018).", "",
         "## 1. Fuentes y clasificación", "",
         "| Fuente | Conjunto | Enlace | Clasif. | Motivo |", "| :-- | :-- | :-- | :-: | :-- |"]
    motivos = {
        "fiscalia": ("B3", "Entidad oficial que define la categoría legal; sin otra fuente independiente con la misma definición; rezago y registros repetidos."),
        "policia": ("B" + corr["codigo"].mode().iat[0] if len(corr) else "B6", "Registro oficial; corroborado con Medicina Legal año a año (ver sección 5)."),
        "ml_def": ("B" + corr["codigo"].mode().iat[0] if len(corr) else "B6", "Registro forense oficial definitivo; corroborado con Policía (sección 5)."),
        "ml_pre": ("B4", "Oficial pero preliminar: puede cambiar."),
    }
    for k, v in FUENTES.items():
        c, mot = motivos[k]
        L.append(f"| {v['nombre']} | `{v['id']}` | [datos.gov.co]({PAGINA.format(v['id'])}) | {c} | {mot} |")
    L += [f"| DANE – Proyecciones de población 2018-2050 | xlsx | [dane.gov.co]({DANE_URL}) | A2 | Denominador oficial usado por las entidades; es proyección, no conteo. |", ""]

    def tabla(an: pd.DataFrame, titulo: str) -> list[str]:
        out = [f"### {titulo}", "", "| Año | Antioquia | % de Colombia | Tasa Antioquia | Tasa Colombia | Puesto de Antioquia (tasa) | Colombia |",
               "| :-: | :-: | :-: | :-: | :-: | :-: | :-: |"]
        for _, r in an.iterrows():
            out.append(f"| {int(r['anio'])}{' (parcial)' if int(r['anio']) == 2026 else ''} | {fmt(r['n'])} | {fmt(r['pct_nacional'], 1)}% | {fmt(r['tasa'], 2)} | {fmt(r['tasa_colombia'], 2)} | "
                       f"{fmt(r['puesto'])} | {fmt(r['colombia'])} |")
        return out + [""]

    L += ["## 2. Antioquia frente a Colombia, año por año", "",
          "2026 es parcial: Policía hasta la fecha de corte del conjunto y Medicina Legal hasta julio.", ""]
    L += tabla(an_f[an_f["anio"] >= 2015], "Fiscalía: víctimas registradas por feminicidio")
    L += tabla(an_p[an_p["anio"] >= 2015], "Policía: homicidios de mujeres")
    L += tabla(an_m, "Medicina Legal: homicidios de mujeres (2025-2026 preliminar)")

    L += [f"## 3. Antioquia frente a otros departamentos ({ultimo})", "",
          "Diez departamentos con mayor tasa por 100.000 mujeres. Departamentos con poca población pueden tener tasas altas con pocos casos.", ""]
    for nombre, d in rk.items():
        L += [f"### {nombre}", "", "| Puesto | Departamento | Casos | Tasa |", "| :-: | :-- | :-: | :-: |"]
        for i, r in d.head(10).iterrows():
            L.append(f"| {i + 1} | {'**' + r['departamento'] + '**' if r['departamento'] == 'ANTIOQUIA' else r['departamento']} | {fmt(r['n'])} | {fmt(r['tasa'], 2)} |")
        pos = d.index[d["departamento"] == "ANTIOQUIA"]
        if len(pos):
            r = d.loc[pos[0]]
            L.append(f"\nAntioquia: puesto **{pos[0] + 1}** de {len(d)} departamentos con casos registrados, con {fmt(r['n'])} casos y tasa {fmt(r['tasa'], 2)}.")
        L.append("")

    L += ["## 4. Antioquia por dentro", "", "### Presunto agresor (Medicina Legal, homicidios de mujeres)", "",
          "| Año | Total | Pareja o expareja | % pareja | Agresor sin información o desconocido | % pareja entre casos con agresor conocido | % pareja en Colombia |", "| :-: | :-: | :-: | :-: | :-: | :-: | :-: |"]
    agm = ag_ant.merge(ag_col, on="anio", suffixes=("", "_col"))
    for _, r in agm.iterrows():
        L.append(f"| {r['anio']} | {fmt(r['total'])} | {fmt(r['pareja'])} | {fmt(r['pareja'] / r['total'] * 100, 1)}% | {fmt(r['sin_info'])} | "
                 f"{fmt(r['pareja'] / (r['total'] - r['sin_info']) * 100, 1)}% | {fmt(r['pareja_col'] / r['total_col'] * 100, 1)}% |")
    L += ["", "Pareja o expareja = categorías de presunto agresor que contienen: " + ", ".join(AGRESOR_PAREJA) + ". "
          "Un porcentaje alto de «sin información» limita la lectura.", "",
          "Agresores más frecuentes en Antioquia desde 2020:", "", "| Presunto agresor | Casos |", "| :-- | :-: |"]
    L += [f"| {r['agresor']} | {fmt(r['n'])} |" for _, r in agresores_ant.iterrows()]

    L += ["", "### Arma o medio (Policía, homicidios de mujeres en Antioquia)", ""]
    tab = arma.pivot_table(index="arma_medio", columns="anio", values="n", aggfunc="sum").fillna(0)
    anios = [a for a in sorted(tab.columns) if a >= 2019]
    tab = tab[anios]
    tab["total"] = tab.sum(axis=1)
    tab = tab.sort_values("total", ascending=False)
    principales = tab.head(3)
    otros = tab.iloc[3:].sum().to_frame("Otros medios").T
    tab = pd.concat([principales, otros])
    L += ["| Arma o medio | " + " | ".join(str(a) for a in anios) + " | % del periodo |", "| :-- |" + " :-: |" * (len(anios) + 1)]
    tot = tab["total"].sum()
    for idx, r in tab.iterrows():
        L.append(f"| {idx} | " + " | ".join(fmt(r[a]) for a in anios) + f" | {fmt(r['total'] / tot * 100, 1)}% |")

    L += ["", "### Zona (Policía)", ""]
    tz = zona.pivot_table(index="anio", columns="zona", values="n", aggfunc="sum").fillna(0)
    tz = tz[tz.index >= 2019]
    L += ["| Año | " + " | ".join(tz.columns) + " |", "| :-: |" + " :-: |" * len(tz.columns)]
    L += [f"| {a}{' (parcial)' if a == 2026 else ''} | " + " | ".join(fmt(v) for v in r) + " |" for a, r in tz.iterrows()]

    tot_m = muni["n"].sum()
    L += ["", "### Municipios con más homicidios de mujeres (Policía, 2018 a hoy)", "", "| Municipio | Casos | % de Antioquia |", "| :-- | :-: | :-: |"]
    L += [f"| {r['municipio']} | {fmt(r['n'])} | {fmt(r['n'] / tot_m * 100, 1)}% |" for _, r in muni.head(15).iterrows()]

    L += ["", "## 5. Corroboración entre fuentes (Antioquia)", "",
          "Policía y Medicina Legal registran el mismo hecho por caminos independientes (denuncia y necropsia). "
          "Regla: diferencia ≤ 10 % → 2 (probable); ≤ 25 % → 3 (posible); mayor → 4 (dudoso).", "",
          "| Año | Policía | Medicina Legal | Diferencia | Número asignado |", "| :-: | :-: | :-: | :-: | :-: |"]
    L += [f"| {r['anio']} | {fmt(r['n_pol'])} | {fmt(r['n_ml'])} | {fmt(r['dif'], 1)}% | {r['codigo']} |" for _, r in corr.iterrows()]

    L += ["", "## 6. Fase 1: qué se bajó y cómo escalar", "",
          "Regla R20 de [[Reglas_de_Oro]]: en Fase 1 se piden **agregados** a la API, no las bases completas.", "",
          "| Fuente | Tamaño completo | Qué se bajó en Fase 1 | Cómo escalar en Fase 2 |", "| :-- | :-- | :-- | :-- |",
          "| Fiscalía (`hr73-zqjf`) | ~17,6 millones de registros (todas las víctimas de todos los delitos) | Conteo por departamento y año del delito de feminicidio | Bajar solo filas de feminicidio y homicidio de mujeres de Antioquia, por lotes de 50.000 (`$limit`/`$offset`), y guardarlas en formato columnar (Parquet). |",
          "| Policía (`m8fd-ahd9`) | ~345.000 filas desde 2003 | Agregados por departamento, año, arma, zona y municipio | Bajar las filas de Antioquia para el modelo municipal. |",
          "| Medicina Legal (`vtub-3de2`, `2kpj-cktv`) | ~125.000 filas | Agregados por departamento, año y agresor | Bajar las filas de mujeres en Antioquia (≈1.500) con todas las variables. |", "",
          "## 7. Cómo leer y usar estas cifras", "",
          "- Para el póster usa una sola medida por gráfico y di cuál es. Ver [[Datos_Clave_para_el_Poster]].",
          "- Las cifras de la Fiscalía de 2025-2026 subirán cuando avancen los procesos: no son una caída real.",
          "- Las tasas departamentales usan la población proyectada de mujeres; no hay tasas antes de 2018 con este archivo.",
          "", "## Notas relacionadas", "",
          "- [[Registro_de_Fuentes]] (fuentes 88 en adelante)", "- [[01_Adquisicion_Datos_Scraping_y_Fronteras_Antioquia]]",
          "- [[Revision_de_Cifras_y_Citas]]", "- Volver al [[Indice_Maestro]]", ""]
    NOTA.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
