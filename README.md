# PromptLab: constructor y evaluador de prompts

Aplicación multipágina de Streamlit en español. La evaluación usa cuatro criterios de 1 a 5, con nota global sobre 20.

## Funciones

- Constructor de prompts con rol, tarea, contexto, formato, tono, restricciones y criterios.
- Evaluador que analiza un prompt sin ejecutar la tarea que contiene.
- Evaluación con OpenAI API si existe `OPENAI_API_KEY`.
- Evaluación heurística local si no hay clave API.
- Puntuación, criterios, problemas detectados y propuesta de mejora.
- Navegación entre evaluador y constructor.
- Descarga del prompt como TXT.

## Ejecutar localmente

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
```

Activar el entorno:

- Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Instalar dependencias:

```bash
pip install -r requirements.txt
```

### Configurar OpenAI (opcional, recomendado para evaluación semántica)

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="tu_clave_api"
$env:OPENAI_MODEL="gpt-4.1-mini"
```

macOS/Linux:

```bash
export OPENAI_API_KEY="tu_clave_api"
export OPENAI_MODEL="gpt-4.1-mini"
```

No escribas claves API directamente en el código ni las subas a Git.

Iniciar:

```bash
streamlit run app.py
```

Un archivo `.env` en la carpeta del proyecto se carga automáticamente mediante `python-dotenv`. Sin clave API, el evaluador utiliza heurísticas locales sencillas. Esta modalidad no entiende el significado tan bien como un LLM y sus puntuaciones son aproximadas.

## Desplegar en Streamlit Community Cloud

1. Sube el contenido del proyecto a un repositorio privado o público de GitHub.
2. En Streamlit Community Cloud, crea una aplicación apuntando a `app.py`.
3. En **App settings → Secrets**, agrega:

```toml
OPENAI_API_KEY = "tu_clave_api"
OPENAI_MODEL = "gpt-4.1-mini"
```

4. Despliega la aplicación.

En Streamlit Cloud, las claves definidas en `st.secrets` no siempre se exponen como variables de entorno. Para cubrir ambos casos, puedes cambiar en `utils/prompt_utils.py` la lectura de `api_key` por:

```python
api_key = os.getenv("OPENAI_API_KEY")
try:
    import streamlit as st
    if not api_key:
        api_key = st.secrets.get("OPENAI_API_KEY")
except Exception:
    pass
```

Y para el modelo:

```python
model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
try:
    import streamlit as st
    model = st.secrets.get("OPENAI_MODEL", model)
except Exception:
    pass
```

## Nota de seguridad

El evaluador está diseñado para tratar el prompt como texto no confiable y no obedecerlo. Como cualquier sistema basado en LLM, esto reduce el riesgo de que el texto evaluado desvíe al evaluador, pero no ofrece una garantía matemática absoluta. No uses la salida del modelo como única defensa para decisiones críticas.
