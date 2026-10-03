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

Uso:  .venv/bin/python scripts/extraer_datos_oficiales.py
Requiere internet. Fase 1 pide solo conteos agregados a la API, no las bases completas.
Credenciales opcionales en .env: SOCRATA_APP_TOKEN, o SOCRATA_API_KEY_ID + SOCRATA_API_KEY_SECRET.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from _entorno import RAIZ, avisar_si_fuera_de_venv, cargar_env, sin_acentos

DATOS = RAIZ / "03_Fuentes_y_Datos" / "datos"
CRUDOS, PROC = DATOS / "crudos", DATOS / "procesados"
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


def procesar() -> dict:
    """Descarga, limpia y guarda los CSV. Devuelve las tablas de resumen."""
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

    return dict(an_f=an_f, an_p=an_p, an_m=an_m, rk=rk, corr=corr, ag_ant=ag_ant, ag_col=ag_col,
                agresores_ant=agresores_ant, arma=arma, zona=zona, muni=muni, ultimo=ultimo)


def main() -> int:
    avisar_si_fuera_de_venv()
    r = procesar()
    print(f"CSV guardados en {PROC.relative_to(RAIZ)}")
    for _, f in r["corr"].iterrows():
        print(f"  Antioquia {f['anio']}: Policía {f['n_pol']:.0f} | Medicina Legal {f['n_ml']:.0f} | diferencia {f['dif']:.1f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
