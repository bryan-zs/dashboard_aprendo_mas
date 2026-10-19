import streamlit as st
from utils.prompt_utils import build_prompt

st.set_page_config(page_title="Constructor | PromptLab", page_icon="🛠️", layout="wide")
st.title("🛠️ Constructor de prompts")
st.write("Completa los campos para generar un prompt estructurado y reutilizable.")

with st.form("prompt_builder"):
    rol = st.text_input(
        "Rol del modelo",
        value="Experto en la materia",
        help="Ejemplo: analista de datos, docente de matemáticas, desarrollador Python.",
    )
    tarea = st.text_area(
        "¿Qué necesitas que haga?",
        placeholder="Describe la tarea concreta y el resultado que buscas...",
        height=120,
    )
    contexto = st.text_area(
        "Contexto y datos disponibles",
        placeholder="Describe la situación, la audiencia, los datos o las herramientas disponibles...",
        height=120,
    )

    c1, c2 = st.columns(2)
    with c1:
        formato = st.selectbox(
            "Formato de salida",
            [
                "Informe estructurado",
                "Respuesta breve en viñetas",
                "Tabla comparativa",
                "JSON válido",
                "Código comentado",
                "Plan paso a paso",
                "Texto libre especificado por el usuario",
            ],
        )
        detalle = st.radio(
            "Nivel de detalle",
            ["Breve", "Intermedio", "Detallado"],
            index=2,
            horizontal=True,
        )
    with c2:
        tono = st.selectbox(
            "Tono",
            ["Profesional", "Académico", "Didáctico", "Directo y conciso", "Creativo", "Técnico"],
        )
        audiencia = st.text_input("Audiencia (opcional)", placeholder="Ej. equipo directivo, principiantes...")
    restricciones = st.text_area(
        "Restricciones y criterios de calidad",
        value="No inventes datos. Distingue hechos de suposiciones y declara las incertidumbres. "
              "Si falta información crítica, solicita una aclaración.",
        height=100,
    )
    extras = st.text_area(
        "Requisitos adicionales (opcional)",
        placeholder="Ej. incluye ejemplos, cita fuentes verificables, prioriza recomendaciones por impacto...",
        height=80,
    )
    submitted = st.form_submit_button("Generar prompt", type="primary", use_container_width=True)

if submitted:
    if not tarea.strip():
        st.error("Describe la tarea antes de generar el prompt.")
    else:
        result = build_prompt(
            rol=rol, tarea=tarea, contexto=contexto, formato=formato,
            detalle=detalle, tono=tono, audiencia=audiencia,
            restricciones=restricciones, extras=extras
        )
        st.session_state["constructed_prompt"] = result

if st.session_state.get("constructed_prompt"):
    st.divider()
    st.subheader("Tu prompt")
    st.text_area(
        "Prompt generado (puedes editarlo antes de copiarlo)",
        key="constructed_prompt_edit",
        value=st.session_state["constructed_prompt"],
        height=420,
    )
    prompt_final = st.session_state.get("constructed_prompt_edit", st.session_state["constructed_prompt"])
    st.download_button(
        "Descargar prompt como TXT",
        data=prompt_final,
        file_name="prompt_mejorado.txt",
        mime="text/plain",
        use_container_width=True,
    )
    if st.button("Evaluar este prompt", use_container_width=True):
        st.session_state["prompt_to_evaluate"] = prompt_final
        st.switch_page("pages/1_Evaluador.py")

st.divider()
if st.button("← Volver al inicio"):
    st.switch_page("app.py")
