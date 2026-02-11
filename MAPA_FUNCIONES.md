# 🗺️ MAPA DE MIGRACIÓN DE FUNCIONES
## De app_web_respaldo.py a la arquitectura modular

Este documento te ayuda a encontrar dónde quedó cada función del código original.

---

## 📍 FUNCIONES DE GITHUB

### `obtener_github(archivo)` 
**Original**: app_web_respaldo.py (línea ~70)  
**Nuevo**: `modules/github_handler.py` → `GitHubHandler.obtener_archivo()`
```python
# Antes:
contenido, sha = obtener_github("archivo.json")

# Ahora:
from modules.github_handler import GitHubHandler
gh = GitHubHandler()
contenido, sha = gh.obtener_archivo("archivo.json")
```

### `enviar_github(archivo, datos, mensaje)`
**Original**: app_web_respaldo.py (línea ~90)  
**Nuevo**: `modules/github_handler.py` → `GitHubHandler.agregar_a_archivo()`
```python
# Antes:
enviar_github("archivo.json", datos, "Mensaje")

# Ahora:
gh.agregar_a_archivo("archivo.json", datos, "Mensaje")
```

### `enviar_github_directo(archivo, datos, mensaje)`
**Original**: app_web_respaldo.py (línea ~105)  
**Nuevo**: `modules/github_handler.py` → `GitHubHandler.sobrescribir_archivo()`
```python
# Antes:
enviar_github_directo("pedido.json", datos)

# Ahora:
gh.sobrescribir_archivo("pedido.json", datos)
```

### `solicitar_busqueda_glpi(serie)`
**Original**: app_web_respaldo.py (línea ~120)  
**Nuevo**: `modules/github_handler.py` → `GitHubHandler.solicitar_busqueda_glpi()`
```python
# Antes:
solicitar_busqueda_glpi("123456")

# Ahora:
gh.solicitar_busqueda_glpi("123456")
```

### `revisar_respuesta_glpi()`
**Original**: app_web_respaldo.py (línea ~130)  
**Nuevo**: `modules/github_handler.py` → `GitHubHandler.revisar_respuesta_glpi()`
```python
# Antes:
respuesta = revisar_respuesta_glpi()

# Ahora:
respuesta = gh.revisar_respuesta_glpi()
```

---

## 🤖 FUNCIONES DE IA

### `extraer_json(texto_completo)`
**Original**: app_web_respaldo.py (línea ~145)  
**Nuevo**: `modules/ai_engine.py` → `AIEngine.extraer_json()`
```python
# Antes:
texto, json_str = extraer_json(respuesta_ia)

# Ahora:
from modules.ai_engine import AIEngine
ai = AIEngine()
texto, json_str = ai.extraer_json(respuesta_ia)
```

### Procesamiento principal de IA
**Original**: app_web_respaldo.py (línea ~300-400, dentro del chat)  
**Nuevo**: `modules/ai_engine.py` → `AIEngine.procesar_input()`
```python
# Antes:
# Código directo dentro del chat_input

# Ahora:
resultado = ai.procesar_input(
    user_input=prompt,
    lecciones=lecciones,
    borrador_actual=st.session_state.draft,
    historial_mensajes=st.session_state.messages
)
```

### Generación de órdenes de borrado
**Original**: app_web_respaldo.py (línea ~650, en el tab de limpieza)  
**Nuevo**: `modules/ai_engine.py` → `AIEngine.generar_orden_borrado()`
```python
# Antes:
# Llamada directa a OpenAI con prompt de DBA

# Ahora:
orden = ai.generar_orden_borrado(instruccion, historial_reciente)
```

---

## 📊 FUNCIONES DE STOCK

### `extraer_gen(procesador)`
**Original**: app_web_respaldo.py (línea ~160)  
**Nuevo**: `modules/stock_calculator.py` → `StockCalculator.extraer_generacion()`
```python
# Antes:
gen = extraer_gen("Intel Core i5 8th Gen")

# Ahora:
from modules.stock_calculator import StockCalculator
sc = StockCalculator()
gen = sc.extraer_generacion("Intel Core i5 8th Gen")
```

### `calcular_stock_web(df)`
**Original**: app_web_respaldo.py (línea ~180-280)  
**Nuevo**: `modules/stock_calculator.py` → `StockCalculator.calcular_stock_completo()`
```python
# Antes:
stock, bodega, danados, df_completo = calcular_stock_web(df)

# Ahora:
stock, bodega, danados, df_completo = sc.calcular_stock_completo(df)
```

### Aplicación de reglas de obsolescencia
**Original**: app_web_respaldo.py (línea ~420, en el guardado)  
**Nuevo**: `modules/stock_calculator.py` → `StockCalculator.aplicar_reglas_obsolescencia()`
```python
# Antes:
# Código inline para verificar generación de CPU

# Ahora:
borrador = sc.aplicar_reglas_obsolescencia(borrador)
```

---

## 🔌 FUNCIONES DE GLPI

### `conectar_glpi_jaher()`
**Original**: app_web_respaldo.py (línea ~700)  
**Nuevo**: `modules/glpi_connector.py` → `GLPIConnector.conectar()`
```python
# Antes:
session, base_url = conectar_glpi_jaher()

# Ahora:
from modules.glpi_connector import GLPIConnector
glpi = GLPIConnector()
session, base_url = glpi.conectar()
```

### `consultar_datos_glpi(serie)`
**Original**: app_web_respaldo.py (línea ~750)  
**Nuevo**: `modules/glpi_connector.py` → `GLPIConnector.consultar_equipo()`
```python
# Antes:
resultado = consultar_datos_glpi("123456")

# Ahora:
resultado = glpi.consultar_equipo("123456")
```

---

## 🎨 COMPONENTES DE UI

### Tab de Chat
**Original**: app_web_respaldo.py (línea ~300-550, dentro de `with t1:`)  
**Nuevo**: `ui/chat_tab.py` → `ChatTab.render()`
```python
# Antes:
with t1:
    # Todo el código del chat aquí

# Ahora:
from ui.chat_tab import ChatTab
with tab1:
    chat = ChatTab()
    chat.render()
```

### Tab de Stock
**Original**: app_web_respaldo.py (línea ~580-620, dentro de `with t2:`)  
**Nuevo**: `ui/stock_tab.py` → `StockTab.render()`
```python
# Antes:
with t2:
    # Todo el código de stock aquí

# Ahora:
from ui.stock_tab import StockTab
with tab2:
    stock = StockTab()
    stock.render()
```

### Tab de Limpieza
**Original**: app_web_respaldo.py (línea ~630-690, dentro de `with t3:`)  
**Nuevo**: `ui/cleaning_tab.py` → `CleaningTab.render()`
```python
# Antes:
with t3:
    # Todo el código de limpieza aquí

# Ahora:
from ui.cleaning_tab import CleaningTab
with tab3:
    cleaning = CleaningTab()
    cleaning.render()
```

---

## ⚙️ CONFIGURACIÓN

### Variables globales y credenciales
**Original**: app_web_respaldo.py (línea ~10-50)  
**Nuevo**: `config/settings.py` → Clase `Config`
```python
# Antes:
API_KEY = st.secrets["GPT_API_KEY"]
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_USER = "Soporte1jaher"

# Ahora:
from config.settings import Config
api_key = Config.get_api_key()
token = Config.get_github_token()
usuario = Config.GITHUB_USER
```

### Prompt del sistema
**Original**: app_web_respaldo.py (línea ~200-300, variable SYSTEM_PROMPT)  
**Nuevo**: `config/settings.py` → Variable `SYSTEM_PROMPT`
```python
# Antes:
SYSTEM_PROMPT = """..."""

# Ahora:
from config.settings import SYSTEM_PROMPT
```

### Estilos CSS
**Original**: app_web_respaldo.py (línea ~20-35)  
**Nuevo**: `config/settings.py` → Variable `CUSTOM_CSS`
```python
# Antes:
st.markdown("""<style>...</style>""", unsafe_allow_html=True)

# Ahora:
from config.settings import CUSTOM_CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
```

---

## 📝 ESTADO DE SESIÓN

### Inicialización del estado
**Original**: app_web_respaldo.py (línea ~350-360)  
**Nuevo**: `ui/chat_tab.py` → `ChatTab.__init__()`

Todo el manejo de `st.session_state` ahora está encapsulado en las clases de UI.

---

## 🔍 TABLA COMPARATIVA RÁPIDA

| Función Original | Nuevo Ubicación | Clase.Método |
|-----------------|-----------------|--------------|
| `obtener_github()` | modules/github_handler.py | `GitHubHandler.obtener_archivo()` |
| `enviar_github()` | modules/github_handler.py | `GitHubHandler.agregar_a_archivo()` |
| `enviar_github_directo()` | modules/github_handler.py | `GitHubHandler.sobrescribir_archivo()` |
| `solicitar_busqueda_glpi()` | modules/github_handler.py | `GitHubHandler.solicitar_busqueda_glpi()` |
| `revisar_respuesta_glpi()` | modules/github_handler.py | `GitHubHandler.revisar_respuesta_glpi()` |
| `extraer_json()` | modules/ai_engine.py | `AIEngine.extraer_json()` |
| Procesamiento IA | modules/ai_engine.py | `AIEngine.procesar_input()` |
| Orden de borrado | modules/ai_engine.py | `AIEngine.generar_orden_borrado()` |
| `extraer_gen()` | modules/stock_calculator.py | `StockCalculator.extraer_generacion()` |
| `calcular_stock_web()` | modules/stock_calculator.py | `StockCalculator.calcular_stock_completo()` |
| Reglas obsolescencia | modules/stock_calculator.py | `StockCalculator.aplicar_reglas_obsolescencia()` |
| `conectar_glpi_jaher()` | modules/glpi_connector.py | `GLPIConnector.conectar()` |
| `consultar_datos_glpi()` | modules/glpi_connector.py | `GLPIConnector.consultar_equipo()` |
| Tab de Chat | ui/chat_tab.py | `ChatTab.render()` |
| Tab de Stock | ui/stock_tab.py | `StockTab.render()` |
| Tab de Limpieza | ui/cleaning_tab.py | `CleaningTab.render()` |
| Variables globales | config/settings.py | `Config` |
| SYSTEM_PROMPT | config/settings.py | `SYSTEM_PROMPT` |
| CSS | config/settings.py | `CUSTOM_CSS` |

---

## 💡 PATRÓN DE USO

### Antes (código monolítico):
```python
# Todo en un archivo
import streamlit as st
from openai import OpenAI

API_KEY = st.secrets["GPT_API_KEY"]
client = OpenAI(api_key=API_KEY)

def obtener_github(archivo):
    # código...
    
if prompt := st.chat_input("..."):
    # procesamiento directo
```

### Ahora (modular):
```python
# main.py
import streamlit as st
from ui.chat_tab import ChatTab
from ui.stock_tab import StockTab
from ui.cleaning_tab import CleaningTab

def main():
    tab1, tab2, tab3 = st.tabs([...])
    
    with tab1:
        chat = ChatTab()
        chat.render()
    
    # ...
```

---

## ✅ BENEFICIOS DE LA NUEVA ESTRUCTURA

1. **Separación de responsabilidades**: Cada módulo hace una sola cosa
2. **Reutilización**: Puedes usar `GitHubHandler` en otros proyectos
3. **Testing**: Puedes probar cada módulo por separado
4. **Mantenimiento**: Más fácil encontrar y arreglar bugs
5. **Extensibilidad**: Agregar features sin tocar todo el código
6. **Legibilidad**: Archivos más cortos y enfocados

---

## 🎯 SIGUIENTE PASO

Usa este mapa cuando necesites:
- Encontrar dónde está una función
- Migrar código personalizado
- Entender el flujo de datos
- Debugging de problemas específicos

---

**¡Feliz codificación! 🚀**
