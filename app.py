import streamlit as st

st.set_page_config(
    page_title="PromptLab | Constructor y evaluador",
    page_icon="🧩",
    layout="wide",
)

st.title("🧩 PromptLab")
st.subheader("Construye, evalúa y mejora prompts para modelos de lenguaje")
st.write(
    "Usa el constructor para crear prompts desde cero o el evaluador para revisar "
    "un prompt existente sin ejecutar la tarea que contiene."
)

col1, col2 = st.columns(2)
with col1:
    st.markdown("### 🔍 Evaluador")
    st.write("Obtén una evaluación, puntuación, problemas detectados y sugerencias.")
    if st.button("Abrir evaluador", use_container_width=True):
        st.switch_page("pages/1_Evaluador.py")
with col2:
    st.markdown("### 🛠️ Constructor")
    st.write("Define el rol, objetivo, contexto, restricciones y formato de salida.")
    if st.button("Abrir constructor", use_container_width=True):
        st.switch_page("pages/2_Constructor.py")

st.divider()
st.info("La evaluación analiza el prompt como texto. No ejecuta la solicitud que aparece dentro de él.")
