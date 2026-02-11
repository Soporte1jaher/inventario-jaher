# 🚀 GUÍA RÁPIDA DE IMPLEMENTACIÓN
## LAIA v91.2 - Versión Modular

---

## 📦 CONTENIDO DEL PAQUETE

Has recibido el archivo **`laia_modular.tar.gz`** que contiene:

```
laia_modular/
├── main.py                   # ⭐ Archivo principal (ejecutar este)
├── verify_install.py         # Script de verificación
├── requirements.txt          # Dependencias
├── README.md                 # Documentación completa
├── ARQUITECTURA.md           # Diagramas del sistema
├── MIGRACION.md              # Guía de migración detallada
├── config/
│   ├── __init__.py
│   └── settings.py           # Configuración y prompts
├── modules/
│   ├── __init__.py
│   ├── github_handler.py     # Manejo de GitHub
│   ├── ai_engine.py          # Motor de IA
│   ├── stock_calculator.py   # Cálculos de inventario
│   └── glpi_connector.py     # Integración GLPI
└── ui/
    ├── __init__.py
    ├── chat_tab.py           # Interfaz de chat
    ├── stock_tab.py          # Interfaz de stock
    └── cleaning_tab.py       # Interfaz de limpieza
```

---

## ⚡ INSTALACIÓN RÁPIDA (5 minutos)

### Paso 1: Descomprimir
```bash
tar -xzf laia_modular.tar.gz
cd laia_modular
```

### Paso 2: Instalar dependencias
```bash
pip install -r requirements.txt
```

### Paso 3: Configurar secrets

Crear directorio y archivo:
```bash
mkdir -p .streamlit
nano .streamlit/secrets.toml
```

Contenido del archivo:
```toml
GPT_API_KEY = "tu-api-key-de-openai"
GITHUB_TOKEN = "tu-github-token"
```

### Paso 4: Verificar instalación
```bash
python verify_install.py
```

Si todo está ✅, continúa al paso 5.

### Paso 5: Ejecutar
```bash
streamlit run main.py
```

---

## 🎯 VERIFICACIÓN RÁPIDA

Después de ejecutar, verifica que:

1. **Chat Tab** ✅
   - Puedes escribir en el chat
   - La IA responde
   - Se crea el borrador

2. **Stock Tab** ✅
   - Ves el historial
   - Puedes descargar Excel
   - Tiene 4 hojas (Histórico, Stock, Bodega, Dañados)

3. **Cleaning Tab** ✅
   - Puedes escribir una orden de borrado
   - Se genera la orden JSON

---

## 🔄 MIGRACIÓN DESDE TU CÓDIGO ACTUAL

### ¿Tienes el archivo `app_web_respaldo.py`?

**NO LO BORRES**. El nuevo sistema es 100% compatible.

### Proceso de migración:

1. **Prueba el nuevo sistema** en paralelo
2. **Compara** los resultados
3. **Cuando estés seguro**, cambia la ejecución a `main.py`

**Rollback inmediato**: Si algo falla, vuelve a ejecutar:
```bash
streamlit run app_web_respaldo.py
```

---

## 📊 COMPARATIVA

| Aspecto | Archivo Monolítico | Versión Modular |
|---------|-------------------|-----------------|
| Líneas de código por archivo | ~800 | ~100-200 |
| Facilidad de debugging | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Extensibilidad | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Mantenimiento | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Funcionalidad | ✅ Igual | ✅ Igual |
| Velocidad | ✅ Igual | ✅ Igual |

---

## 🆘 SOLUCIÓN DE PROBLEMAS COMUNES

### Error: "ModuleNotFoundError"
```bash
# Verifica que estés en el directorio correcto
pwd
# Debe mostrar algo como: /home/usuario/laia_modular

# Si no, navega al directorio
cd /ruta/a/laia_modular
```

### Error: "KeyError: 'GPT_API_KEY'"
```bash
# Verifica que el archivo de secrets exista
cat .streamlit/secrets.toml

# Debe mostrar tus credenciales
# Si no existe, créalo siguiendo el Paso 3
```

### Error: "Cannot connect to GitHub"
```bash
# Verifica tu token
# 1. Ve a GitHub → Settings → Developer settings → Personal access tokens
# 2. Genera uno nuevo si es necesario
# 3. Debe tener permisos: repo, write:packages
```

### La IA no responde bien
```bash
# Verifica tu API key de OpenAI
# 1. Ve a https://platform.openai.com/api-keys
# 2. Verifica que tenga saldo
# 3. Copia la key correctamente en secrets.toml
```

---

## 📚 DOCUMENTACIÓN ADICIONAL

- **README.md**: Documentación completa del proyecto
- **ARQUITECTURA.md**: Diagramas y flujos del sistema
- **MIGRACION.md**: Guía detallada de migración paso a paso

---

## 🎓 PRÓXIMOS PASOS

### Para desarrolladores:

1. Lee `ARQUITECTURA.md` para entender el diseño
2. Lee el código de cada módulo
3. Experimenta agregando funcionalidades en los módulos

### Para usuarios:

1. Ejecuta `main.py`
2. Usa el sistema normalmente
3. Reporta cualquier anomalía

---

## ✅ CHECKLIST DE IMPLEMENTACIÓN

Marca cada item cuando lo completes:

- [ ] Descargué y descomprimí el archivo
- [ ] Instalé las dependencias (`pip install -r requirements.txt`)
- [ ] Configuré los secrets (`.streamlit/secrets.toml`)
- [ ] Ejecuté `verify_install.py` y todo pasó ✅
- [ ] Ejecuté `streamlit run main.py`
- [ ] Probé el Chat Tab
- [ ] Probé el Stock Tab
- [ ] Probé el Cleaning Tab
- [ ] Descargué un Excel y verificé las 4 hojas
- [ ] Guardé un registro exitosamente
- [ ] Leí la documentación completa

---

## 🎉 ¡LISTO!

Si completaste todos los items del checklist, **¡ya tienes LAIA modular funcionando!**

### Recursos de ayuda:

- 📖 Documentación: Lee README.md
- 🏗️ Arquitectura: Lee ARQUITECTURA.md  
- 🔄 Migración: Lee MIGRACION.md
- 🐛 Debug: Ejecuta `verify_install.py`

### Soporte:

Para cualquier duda o problema, contacta al equipo de desarrollo.

---

**¡Feliz auditoría! 🚀**
