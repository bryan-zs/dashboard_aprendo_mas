"""
Cada gráfico se alimenta de una consulta SQL en DuckDB; debajo de cada uno se muestra
exactamente la consulta ejecutada. Las vistas base están en `vistas.sql` (se editan ahí).

Ejecutar:   streamlit run app.py

Dónde busca la base (en este orden):
  1. Variable de entorno APRENDO_DB  -> ruta a un archivo .sqlite o a una carpeta que lo contenga
  2. st.secrets["aprendo_db"]        -> idem (archivo .streamlit/secrets.toml)
  3. ./aprendo_caso.sqlite           -> junto a este archivo (desarrollo)
  4. Subida manual desde la barra lateral -> solo si no se encontró nada Y APRENDO_ALLOW_UPLOAD != "0"

Producción: define APRENDO_DB=/ruta/interna  y  APRENDO_ALLOW_UPLOAD=0. La base se abre en modo solo
lectura y la app recarga los datos sola cuando el archivo cambia (fecha de modificación).
"""
import os
import sqlite3
import tempfile
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Aprendo + · Caso práctico",
    layout="wide",
    initial_sidebar_state="collapsed"
)

APP_DIR = Path(__file__).parent
DB_FILENAME = os.environ.get("APRENDO_DB_FILENAME", "aprendo_caso.sqlite")
ALLOW_UPLOAD = os.environ.get("APRENDO_ALLOW_UPLOAD", "1") != "0"

C_UGEL = {"UGEL A": "#2a7f62", "UGEL B": "#c47f17", "UGEL C": "#3b6fb6", "Total": "#960606"}
C_BEFORE, C_AFTER = "#3b6fb6", "#d1495b"


# ============================================================================= acceso a datos
def _as_db_file(p: str | os.PathLike | None) -> Path | None:
    """Acepta un archivo o una carpeta (busca DB_FILENAME y, si no, el primer .sqlite/.db)."""
    if not p:
        return None
    p = Path(str(p)).expanduser()
    if p.is_file():
        return p
    if p.is_dir():
        if (p / DB_FILENAME).is_file():
            return p / DB_FILENAME
        found = sorted([*p.glob("*.sqlite"), *p.glob("*.db")])
        return found[0] if found else None
    return None


def _secret(name: str):
    try:
        return st.secrets.get(name)
    except Exception:  # no hay secrets.toml
        return None


def resolve_db() -> tuple[Path | None, list[str]]:
    tried = []
    for label, cand in (("APRENDO_DB", os.environ.get("APRENDO_DB")),
                        ("st.secrets['aprendo_db']", _secret("aprendo_db")),
                        ("carpeta de la app", APP_DIR)):
        if cand:
            tried.append(f"{label}: {cand}")
            f = _as_db_file(cand)
            if f:
                return f, tried
            if label != "carpeta de la app":
                break   # ruta configurada explícitamente pero inválida: no caer a una copia local
    return None, tried


@st.cache_resource(show_spinner="Cargando la base en DuckDB…")
def get_connection(path: str, mtime: float) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA db")
    lite = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)   # solo lectura
    try:
        for (name,) in lite.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
            df = pd.read_sql_query(f'SELECT * FROM "{name}"', lite)
            con.register("_tmp", df)
            con.execute(f'CREATE TABLE db."{name}" AS SELECT * FROM _tmp')
            con.unregister("_tmp")
    finally:
        lite.close()
    con.execute((APP_DIR / "vistas.sql").read_text(encoding="utf-8"))
    return con


db_file, tried = resolve_db()
if db_file is None:
    if ALLOW_UPLOAD:
        with st.sidebar:
            st.header("Datos")
            up = st.file_uploader("Sube aprendo_caso.sqlite", type=["sqlite", "db"])
        if up is None:
            st.info("No se encontró la base en las ubicaciones configuradas. Súbela desde la barra lateral.")
            st.stop()
        tmp = Path(tempfile.gettempdir()) / f"aprendo_subido_{abs(hash(up.name))}.sqlite"
        tmp.write_bytes(up.getvalue())
        db_file = tmp
    else:
        st.error("No se encontró la base de datos. Define la variable de entorno APRENDO_DB "
                 "(archivo .sqlite o carpeta que lo contiene).")
        st.code("\n".join(tried) or "(sin ubicaciones configuradas)")
        st.stop()

DB_PATH, DB_MTIME = str(db_file), db_file.stat().st_mtime
con = get_connection(DB_PATH, DB_MTIME)
VISTAS_SQL = (APP_DIR / "vistas.sql").read_text(encoding="utf-8")


@st.cache_data(show_spinner=False)
def _run(sql: str, path: str, mtime: float) -> pd.DataFrame:
    return con.cursor().execute(sql).df()


def q(sql: str) -> pd.DataFrame:
    return _run(sql.strip(), DB_PATH, DB_MTIME)


# ============================================================================= consultas
SQL_11 = """
SELECT semana,
    ROUND(100.0 * SUM(evidencias) FILTER (WHERE ugel = 'UGEL A') / SUM(registradas) FILTER (WHERE ugel = 'UGEL A'), 1) AS "UGEL A",
    ROUND(100.0 * SUM(evidencias) FILTER (WHERE ugel = 'UGEL B') / SUM(registradas) FILTER (WHERE ugel = 'UGEL B'), 1) AS "UGEL B",
    ROUND(100.0 * SUM(evidencias) FILTER (WHERE ugel = 'UGEL C') / SUM(registradas) FILTER (WHERE ugel = 'UGEL C'), 1) AS "UGEL C",
    ROUND(100.0 * SUM(evidencias) / SUM(registradas), 1) AS "Total"
FROM v_grupo_semana
GROUP BY semana
ORDER BY semana;
"""

SQL_12 = """
-- 2. Los 5 grupos con mayor caída de participación entre el promedio de las semanas 1 a 4 y el promedio de las semanas 5 y 6.
WITH tasa_grupo AS (
    SELECT
        grupo_id, ugel, institucion_id, zona,
        semana, 100.0 * evidencias / registradas AS tasa
    FROM v_grupo_semana
)

SELECT
    grupo_id, ugel, institucion_id, zona,
    ROUND(AVG(tasa) FILTER (WHERE semana BETWEEN 1 AND 4), 1) AS prom_sem_1_4, -- promedio de tasas semanales (sem 1-4)
    ROUND(AVG(tasa) FILTER (WHERE semana IN (5, 6)), 1) AS prom_sem_5_6, -- promedio de tasas semanales (sem 5-6)
    ROUND(AVG(tasa) FILTER (WHERE semana BETWEEN 1 AND 4) - AVG(tasa) FILTER (WHERE semana IN (5, 6)), 1) AS caida_pp -- caida en puntos porcentuales (pp)
FROM tasa_grupo
GROUP BY grupo_id, ugel, institucion_id, zona
ORDER BY AVG(tasa) FILTER (WHERE semana BETWEEN 1 AND 4) - AVG(tasa) FILTER (WHERE semana IN (5, 6)) DESC, grupo_id
LIMIT 5;
"""

SQL_13_TOTAL = """
-- Total de familias que dejan de participar
SELECT COUNT(*) AS familias_que_dejan_de_participar FROM v_abandonan; -- 144 familias
"""

SQL_13_DETALLE = """
-- Detalle de familias que dejan de participar
SELECT
    a.grupo_id, a.ugel, a.zona,
    COUNT(*) AS familias,
    (SELECT COUNT(*) FROM v_familias f WHERE f.grupo_id = a.grupo_id) AS familias_grupo,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_familias f WHERE f.grupo_id = a.grupo_id), 1) AS pct_del_grupo
FROM v_abandonan a
GROUP BY a.grupo_id, a.ugel, a.zona
ORDER BY familias DESC, a.grupo_id;
"""


def sql_12_semanal(grupos: list[str]) -> str:
    ids = ", ".join(f"'{g}'" for g in grupos)
    return f"""
-- Evolución semanal de los grupos del ranking (usa la misma vista v_grupo_semana)
SELECT grupo_id, semana,
       ROUND(100.0 * evidencias / registradas, 1) AS tasa,
       evidencias, registradas
FROM v_grupo_semana
WHERE grupo_id IN ({ids})
ORDER BY grupo_id, semana;
"""


# ============================================================================= utilidades de UI
def panel(queries: list[tuple[str, str]], dfs: list[pd.DataFrame], key: str):
    """Debajo de cada gráfico: SQL ejecutado, vistas base y datos."""
    t_sql, t_base, t_data = st.tabs(["SQL de este gráfico", "Vistas base", "Datos del gráfico"])
    with t_sql:
        for title, sql in queries:
            if len(queries) > 1:
                st.caption(title)
            st.code(sql.strip(), language="sql")
    with t_base:
        st.code(VISTAS_SQL, language="sql")
    with t_data:
        for i, df in enumerate(dfs):
            st.dataframe(df, width="stretch", hide_index=True)
            st.download_button("Descargar CSV", df.to_csv(index=False).encode("utf-8"),
                               file_name=f"{key}_{i + 1}.csv", mime="text/csv", key=f"dl_{key}_{i}")


def style(fig: go.Figure, h: int = 380, pct: bool = False, legend: bool = True) -> go.Figure:
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), showlegend=legend,
                      legend=dict(orientation="h", y=1.12, x=0), hovermode="closest")
    if pct:
        fig.update_yaxes(ticksuffix="%", rangemode="tozero")
    return fig


def show(fig: go.Figure, key: str):
    st.plotly_chart(fig, width="stretch", key=key)


# ============================================================================= datos base de las pestañas
df11 = q(SQL_11)
total_leavers = int(q(SQL_13_TOTAL).iloc[0, 0])
detalle = q(SQL_13_DETALLE)
idx = df11.set_index("semana")
wk_max = int(idx["Total"].idxmax())

st.title("Aprendo +")
st.title("Participación semanal de familias")
st.caption("Métrica: familias distintas con ≥1 respuesta con evidencia (foto, imagen, audio o video) ÷ familias registradas al cierre de la semana. "
           "Bajo cada gráfico está la consulta SQL que lo produce.")

tab_res, tab_11, tab_12, tab_13 = st.tabs(
    ["Resumen", "1.1 Tasa semanal", "1.2 Caída por grupo", "1.3 Familias que dejan de participar"])

# ----------------------------------------------------------------------------- Resumen
with tab_res:
    t6, tmax = idx.loc[6, "Total"], idx.loc[wk_max, "Total"]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Participación total, semana 6", f"{t6:.1f}%", f"{t6 - tmax:+.1f} pp vs semana {wk_max} (máximo)")
    for col, u in zip((k2, k3, k4), ("UGEL A", "UGEL B", "UGEL C")):
        col.metric(f"{u}, semana 6", f"{idx.loc[6, u]:.1f}%", f"{idx.loc[6, u] - idx.loc[4, u]:+.1f} pp vs semana 4")
    top = detalle.iloc[0]

    st.divider()

    st.markdown(f"""
**Tres hallazgos**
1. **La participación total cae en las semanas 5–6**, hasta {t6:.1f}% (máximo de {tmax:.1f}% en la semana {wk_max}). Ver *1.1*.
2. **La caída se concentra en UGEL C:** los cinco grupos con mayor caída son de escuelas rurales de esa UGEL. Ver *1.2*.
3. **{total_leavers} familias dejan de participar** (evidencia en al menos 2 de las semanas 1–4 y ninguna en las semanas 5–6); \
{top.grupo_id} es el grupo con más casos ({int(top.familias)} de {int(top.familias_grupo)}). Ver *1.3*.
""")

# ----------------------------------------------------------------------------- 1.1
with tab_11:
    st.subheader("1.1 Tasa de participación semanal por UGEL y total")
    long = df11.melt(id_vars="semana", var_name="serie", value_name="tasa")
    fig = go.Figure()
    for s in ["UGEL A", "UGEL B", "UGEL C", "Total"]:
        d = long[long.serie == s]
        fig.add_trace(go.Scatter(
            x=d.semana, y=d.tasa, mode="lines+markers", name=s,
            line=dict(color=C_UGEL[s], width=4 if s == "Total" else 2.4), marker=dict(size=8 if s == "Total" else 6),
            hovertemplate=f"<b>{s}</b> · semana %{{x}}: %{{y:.1f}}%<extra></extra>"))
    fig.update_xaxes(title="Semana", dtick=1)
    fig.update_yaxes(title="% de familias con evidencia")
    fig.update_layout(yaxis=dict(range=[15, 50]))
    style(fig, 420, pct=True)
    show(fig, "g11")
    panel([("Tasa de participación por UGEL y total", SQL_11)], [df11], "g11")

# ----------------------------------------------------------------------------- 1.2
with tab_12:
    st.subheader("1.2 Los cinco grupos con mayor caída")
    st.caption("Caída = promedio de las tasas semanales de las semanas 1–4 menos el promedio de las semanas 5–6 (puntos porcentuales).")
    drop = q(SQL_12)
    fig = go.Figure()
    fig.add_bar(x=drop.grupo_id, y=drop.prom_sem_1_4, name="Promedio semanas 1–4", marker_color=C_BEFORE,
                text=drop.prom_sem_1_4.map("{:.1f}%".format), textposition="outside",
                hovertemplate="<b>%{x}</b><br>Sem. 1–4: %{y:.1f}%<extra></extra>")
    fig.add_bar(x=drop.grupo_id, y=drop.prom_sem_5_6, name="Promedio semanas 5–6", marker_color=C_AFTER,
                text=drop.prom_sem_5_6.map("{:.1f}%".format), textposition="outside",
                customdata=drop.caida_pp,
                hovertemplate="<b>%{x}</b><br>Sem. 5–6: %{y:.1f}%<br>Caída: %{customdata:.1f} pp<extra></extra>")
    fig.update_layout(barmode="group")
    fig.update_xaxes(type="category")
    fig.update_yaxes(title="% de familias con evidencia", ticksuffix="%", range=[0, drop.prom_sem_1_4.max() * 1.18])
    style(fig, 400)
    show(fig, "g12a")
    panel([("Ranking de caída por grupo", SQL_12)], [drop], "g12a")

    st.markdown("**Evolución semanal de esos grupos**")
    sql_wk = sql_12_semanal(drop.grupo_id.tolist())
    wk = q(sql_wk)
    fig = go.Figure()
    for g, d in wk.groupby("grupo_id"):
        fig.add_trace(go.Scatter(
            x=d.semana, y=d.tasa, mode="lines+markers", name=g, customdata=list(zip(d.evidencias, d.registradas)),
            hovertemplate="<b>" + g + "</b> · sem. %{x}<br>%{y:.1f}% (%{customdata[0]} de %{customdata[1]})<extra></extra>"))
    fig.add_vrect(x0=4.5, x1=6.5, fillcolor=C_AFTER, opacity=0.07, line_width=0)
    fig.update_xaxes(title="Semana", dtick=1)
    style(fig, 380, pct=True)
    show(fig, "g12b")
    panel([("Tasa semanal de los grupos del ranking", sql_wk)], [wk], "g12b")

# ----------------------------------------------------------------------------- 1.3
with tab_13:
    st.subheader("1.3 Familias que dejan de participar")
    st.caption("Familias con evidencia en al menos 2 de las 4 primeras semanas y ninguna evidencia en las semanas 5 y 6. Se cuentan familias, no grupos.")
    m1, m2, m3 = st.columns(3)
    m1.metric("Familias que dejan de participar", total_leavers)
    m2.metric("Grupos con al menos 1", len(detalle))
    m3.metric("Grupo con más casos", f"{detalle.grupo_id.iloc[0]} ({int(detalle.familias.iloc[0])})")

    g = detalle.head(15).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=g.familias, y=g.grupo_id, orientation="h", marker_color=[C_UGEL[u] for u in g.ugel], showlegend=False,
        text=[f"{f} de {t} ({p:.0f}%)" for f, t, p in zip(g.familias, g.familias_grupo, g.pct_del_grupo)],
        textposition="outside", customdata=g.ugel,
        hovertemplate="<b>%{y}</b> (%{customdata})<br>%{x} familias<extra></extra>"))
    for u in ("UGEL A", "UGEL B", "UGEL C"):
        fig.add_trace(go.Bar(x=[None], y=[None], name=u, marker_color=C_UGEL[u]))
    fig.update_xaxes(title="Familias que dejan de participar", range=[0, g.familias.max() * 1.35])
    fig.update_yaxes(type="category")
    fig.update_layout(barmode="overlay")
    style(fig, max(320, 30 * len(g) + 120))
    show(fig, "g13")
    st.caption("Se muestran los 15 grupos con más casos; el detalle completo está en «Datos del gráfico».")
    panel([("Total", SQL_13_TOTAL), ("Detalle por grupo", SQL_13_DETALLE)],
          [q(SQL_13_TOTAL), detalle], "g13")
