import streamlit as st
from utils.prompt_utils import evaluate_prompt_with_ai, evaluate_prompt_heuristic

st.set_page_config(page_title="Evaluador | PromptLab", page_icon="🔍", layout="wide")
st.title("🔍 Evaluador de prompts")
st.write(
    "Pega un prompt para evaluar su claridad, contexto, objetivo, restricciones y formato. "
    "**No se ejecutará la tarea descrita en el prompt.**"
)

initial_prompt = st.session_state.get("prompt_to_evaluate", "")
prompt = st.text_area(
    "Prompt que quieres evaluar",
    value=initial_prompt,
    height=260,
    placeholder="Pega aquí el prompt que deseas revisar...",
    key="evaluator_prompt",
)
with st.expander("¿Qué criterios se evalúan?"):
    st.markdown(
        "- **Tarea u objetivo:** ¿define la acción y el resultado esperado?\n"
        "- **Rol y Contexto:** ¿delimita la especialidad y aporta información suficiente?\n"
        "- **Formato de salida:** ¿especifica cómo presentar el resultado?\n"
        "- **Restricciones y Criterios de calidad:** ¿establece límites y cómo evaluar la respuesta?"
    )

if st.button("Evaluar prompt", type="primary", use_container_width=True):
    # Borra los resultados anteriores antes de validar o iniciar la nueva evaluación.
    for old_key in ("evaluation_result", "evaluation_source", "evaluated_prompt"):
        st.session_state.pop(old_key, None)
    if not prompt.strip():
        st.error("Pega un prompt antes de evaluarlo.")
    else:
        with st.spinner("Analizando el texto del prompt…"):
            try:
                result, source = evaluate_prompt_with_ai(prompt)
                # La nota global debe coincidir con la suma de los cuatro criterios.
                dimensions = result.get("dimensions", [])
                if len(dimensions) == 4 and all(isinstance(item.get("score"), (int, float)) for item in dimensions):
                    result["score"] = sum(int(item["score"]) for item in dimensions)
                result["score"] = max(0, min(20, int(result.get("score", 0))))
            except Exception as exc:
                st.warning(
                    "No se pudo completar la evaluación con IA. Se mostrará una evaluación local. "
                    "Comprueba la clave API y la conexión si esperabas usar el modelo."
                )
                result = evaluate_prompt_heuristic(prompt)
                source = "heurística local"
        # Normaliza también el fallback local y limita el total a la escala /20.
        dimensions = result.get("dimensions", [])
        if len(dimensions) == 4 and all(isinstance(item.get("score"), (int, float)) for item in dimensions):
            result["score"] = sum(int(item["score"]) for item in dimensions)
        result["score"] = max(0, min(20, int(result.get("score", 0))))
        st.session_state["evaluation_result"] = result
        st.session_state["evaluation_source"] = source
        st.session_state["evaluated_prompt"] = prompt

if st.session_state.get("evaluation_result"):
    result = st.session_state["evaluation_result"]
    st.divider()
    st.caption(f"Método de evaluación: {st.session_state.get('evaluation_source', 'no especificado')}")

    score = result.get("score")
    if isinstance(score, (int, float)):
        st.metric("Puntuación global", f"{score}/20")
        st.progress(max(0, min(20, int(score))) / 20)
        # st.caption("Escala de 0 a 20: cuatro criterios, cada uno sobre 5 puntos.")

    st.subheader("Resumen")
    st.write(result.get("summary", "No se generó un resumen."))

    dimensions = result.get("dimensions", [])
    if dimensions:
        st.subheader("Evaluación por criterios")
        for item in dimensions:
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{item.get('name', 'Criterio')}**")
                c1.write(item.get("comment", ""))
                if isinstance(item.get("score"), (int, float)):
                    c2.metric("Puntuación", f"{item['score']}/5")

    issues = result.get("issues", [])
    st.subheader("Problemas detectados")
    if issues:
        for issue in issues:
            st.markdown(f"- {issue}")
    else:
        st.write("No se identificaron problemas importantes.")

    suggestions = result.get("suggestions", [])
    st.subheader("Mejoras recomendadas")
    if suggestions:
        for suggestion in suggestions:
            st.markdown(f"- {suggestion}")

    improved = result.get("improved_prompt", "")
    if improved:
        st.subheader("Versión mejorada sugerida")
        st.caption("Esta es una propuesta para que la revises. No se ha ejecutado.")
        improved_key = "improved_prompt_display_" + str(abs(hash(st.session_state.get("evaluated_prompt", ""))))
        st.text_area("Prompt mejorado", value=improved, height=360, key=improved_key)

    def actualizar_texto():
        st.session_state["evaluator_prompt"] = improved

    if st.button("Evaluar prompt mejorado", on_click=actualizar_texto,  use_container_width=True):
        st.session_state["prompt_to_evaluate"] = improved
        st.switch_page("pages/1_Evaluador.py")
    
    if st.button("Construir un prompt nuevo desde cero", use_container_width=True):
        st.switch_page("pages/2_Constructor.py")

st.divider()
if st.button("← Volver al inicio"):
    st.switch_page("app.py")
