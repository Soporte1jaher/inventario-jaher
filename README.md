# LAIA v91.2 - Sistema de Auditoría de Inventario TI

Sistema modular de gestión de inventario con inteligencia artificial para control de hardware y equipos de TI.

## 📁 Estructura del Proyecto

```
proyecto/
├── main.py                      # Archivo principal (ejecutar este)
├── app_web_respaldo.py          # Versión monolítica original (respaldo)
├── requirements.txt             # Dependencias del proyecto
├── README.md                    # Este archivo
│
├── config/
│   ├── __init__.py
│   └── settings.py              # Configuración, credenciales y prompts
│
├── modules/
│   ├── __init__.py
│   ├── github_handler.py        # Operaciones con GitHub
│   ├── ai_engine.py             # Motor de IA (OpenAI)
│   ├── stock_calculator.py      # Cálculos de stock y clasificación
│   └── glpi_connector.py        # Conexión con GLPI
│
└── ui/
    ├── __init__.py
    ├── chat_tab.py              # Interfaz del chat auditor
    ├── stock_tab.py             # Interfaz de control de stock
    └── cleaning_tab.py          # Interfaz de limpieza de datos
```

## 🚀 Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/Soporte1jaher/inventario-jaher.git
cd inventario-jaher
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar Secrets en Streamlit

Crear archivo `.streamlit/secrets.toml`:

```toml
GPT_API_KEY = "tu-api-key-de-openai"
GITHUB_TOKEN = "tu-github-token"
```

### 4. Ejecutar la aplicación
```bash
streamlit run main.py
```

## 📦 Módulos del Sistema

### Config (config/settings.py)
- Configuración centralizada
- Gestión de credenciales
- Prompts del sistema
- Estilos CSS

### GitHub Handler (modules/github_handler.py)
Funciones:
- `obtener_archivo(nombre)`: Descarga archivos JSON
- `agregar_a_archivo(nombre, datos, mensaje)`: Agrega datos (append)
- `sobrescribir_archivo(nombre, datos, mensaje)`: Sobreescribe archivo
- `solicitar_busqueda_glpi(serie)`: Crea solicitud GLPI
- `revisar_respuesta_glpi()`: Verifica respuesta GLPI
- `obtener_lecciones()`: Obtiene lecciones aprendidas
- `obtener_historico()`: Obtiene historial completo

### AI Engine (modules/ai_engine.py)
Funciones:
- `procesar_input(...)`: Procesa entrada del usuario con IA
- `extraer_json(texto)`: Separa texto de JSON
- `generar_orden_borrado(...)`: Genera órdenes de eliminación

### Stock Calculator (modules/stock_calculator.py)
Funciones:
- `extraer_generacion(procesador)`: Clasifica CPU como obsoleta/moderna
- `calcular_stock_completo(df)`: Calcula inventario completo
- `aplicar_reglas_obsolescencia(borrador)`: Aplica reglas automáticas

### GLPI Connector (modules/glpi_connector.py)
Funciones:
- `conectar()`: Establece sesión con GLPI
- `consultar_equipo(serie)`: Busca equipo por serie

## 🎨 Interfaz de Usuario

### Chat Tab (ui/chat_tab.py)
- Chat conversacional con IA
- Editor de borrador
- Integración GLPI
- Guardado en histórico

### Stock Tab (ui/stock_tab.py)
- Visualización de inventario
- Métricas de stock
- Exportación a Excel (4 hojas)
- Sincronización con GitHub

### Cleaning Tab (ui/cleaning_tab.py)
- Limpieza inteligente de registros
- Procesamiento con lenguaje natural
- Generación de órdenes de borrado

## 🔧 Mantenimiento y Extensión

### Agregar una nueva funcionalidad

1. **Si es lógica de negocio**: Agregar a `modules/`
2. **Si es interfaz**: Agregar a `ui/`
3. **Si es configuración**: Modificar `config/settings.py`

### Ejemplo: Agregar nuevo módulo

```python
# modules/nuevo_modulo.py
class NuevoModulo:
    def __init__(self):
        pass
    
    def nueva_funcion(self):
        # Tu código aquí
        pass
```

Luego importar en el archivo correspondiente:
```python
from modules.nuevo_modulo import NuevoModulo
```

## 📊 Flujo de Datos

```
Usuario → Chat UI → AI Engine → GitHub Handler → GitHub Repo
                         ↓
                  Stock Calculator
                         ↓
                  Stock UI (Visualización)
```

## 🔐 Seguridad

- Las credenciales NUNCA deben estar en el código
- Usar siempre `st.secrets` para datos sensibles
- El token de GitHub debe tener permisos mínimos necesarios

## 🐛 Debugging

### Problema: Error al conectar con GitHub
- Verificar que `GITHUB_TOKEN` esté en secrets
- Verificar permisos del token en GitHub

### Problema: IA no responde correctamente
- Verificar que `GPT_API_KEY` sea válida
- Revisar el prompt en `config/settings.py`

### Problema: No se actualiza el stock
- Verificar que el archivo en GitHub tenga formato JSON válido
- Revisar logs de `stock_calculator.py`

## 📝 Notas de Migración desde app_web_respaldo.py

El código fue refactorizado para:
- ✅ Separación de responsabilidades
- ✅ Reutilización de código
- ✅ Facilidad de mantenimiento
- ✅ Testing independiente por módulo
- ✅ Escalabilidad

**El archivo original (`app_web_respaldo.py`) se mantiene como respaldo.**

## 🤝 Contribuir

1. Fork el proyecto
2. Crear rama de feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -m 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abrir Pull Request

## 📄 Licencia

Uso interno - JAHER

## 👤 Autor

Equipo de Desarrollo JAHER

## 📞 Soporte

Para soporte técnico, contactar a: soporte1@jaher.com
