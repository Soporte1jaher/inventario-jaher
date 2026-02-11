# GUÍA DE MIGRACIÓN

## Del archivo monolítico (app_web_respaldo.py) a la arquitectura modular

### ⚠️ IMPORTANTE: ANTES DE EMPEZAR

1. **Haz un backup completo** de tu código actual
2. **No borres** el archivo `app_web_respaldo.py`
3. **Prueba el nuevo sistema** en un entorno de desarrollo primero

---

## PASO 1: Preparación

### 1.1 Verificar estructura de archivos

```bash
python verify_install.py
```

Esto verificará que todos los archivos estén en su lugar.

### 1.2 Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## PASO 2: Configurar Secrets

### 2.1 Crear directorio de secrets

```bash
mkdir -p .streamlit
```

### 2.2 Crear archivo de secrets

Crear `.streamlit/secrets.toml`:

```toml
GPT_API_KEY = "tu-api-key-aqui"
GITHUB_TOKEN = "tu-github-token-aqui"
```

**CRÍTICO**: Usa las mismas credenciales que tenías en `app_web_respaldo.py`

---

## PASO 3: Migración de Datos

### 3.1 Verificar archivos en GitHub

Los siguientes archivos deben existir en tu repositorio:
- `buzon.json`
- `historico.json`
- `lecciones.json`
- `pedido.json`
- `config_glpi.json`

### 3.2 Formato de archivos

Asegúrate de que tengan el formato correcto:

**buzon.json**:
```json
[]
```

**historico.json**:
```json
[
  {
    "categoria_item": "Computo",
    "equipo": "Laptop",
    ...
  }
]
```

**lecciones.json**:
```json
[]
```

---

## PASO 4: Probar el Sistema Nuevo

### 4.1 Ejecutar en modo prueba

```bash
streamlit run main.py
```

### 4.2 Verificar funcionalidades

✅ **Chat Tab**:
- [ ] Ingresar un equipo nuevo
- [ ] Ver el borrador
- [ ] Guardar en histórico

✅ **Stock Tab**:
- [ ] Ver el inventario
- [ ] Descargar Excel
- [ ] Verificar las 4 hojas

✅ **Cleaning Tab**:
- [ ] Intentar eliminar un registro
- [ ] Verificar orden de borrado

---

## PASO 5: Comparación de Funcionalidades

### Funcionalidades IGUALES (100% compatible):

| Funcionalidad | Archivo Antiguo | Archivo Nuevo |
|---------------|----------------|---------------|
| Chat con IA | ✅ | ✅ |
| Guardar en GitHub | ✅ | ✅ |
| Clasificación CPU | ✅ | ✅ |
| Integración GLPI | ✅ | ✅ |
| Excel 4 hojas | ✅ | ✅ |
| Limpieza de datos | ✅ | ✅ |

### Nuevas VENTAJAS del sistema modular:

✨ **Código más limpio**: Cada módulo tiene una responsabilidad
✨ **Más fácil de debuggear**: Errores aislados por módulo
✨ **Extensible**: Agregar features sin tocar todo el código
✨ **Reutilizable**: Los módulos pueden usarse en otros proyectos
✨ **Testeable**: Se pueden hacer pruebas unitarias

---

## PASO 6: Resolución de Problemas

### Problema: "ModuleNotFoundError: No module named 'config'"

**Solución**: Asegúrate de estar en el directorio correcto:
```bash
cd /ruta/de/tu/proyecto
python verify_install.py
```

### Problema: "KeyError: GPT_API_KEY"

**Solución**: Verifica que `.streamlit/secrets.toml` exista y contenga:
```toml
GPT_API_KEY = "tu-clave"
GITHUB_TOKEN = "tu-token"
```

### Problema: "No se conecta a GitHub"

**Solución**: 
1. Verifica que el token sea válido
2. Verifica que tenga permisos de lectura/escritura
3. Verifica el nombre del repositorio en `config/settings.py`

---

## PASO 7: Deploy en Producción

### 7.1 Streamlit Cloud

Si usas Streamlit Cloud:

1. Sube todos los archivos nuevos a GitHub
2. En Streamlit Cloud, cambia el archivo principal a `main.py`
3. Agrega los secrets en la interfaz web

### 7.2 Servidor propio

Si tienes servidor propio:

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
streamlit run main.py --server.port 8501
```

---

## PASO 8: Mantener Ambas Versiones (Opcional)

Puedes mantener ambas versiones funcionando:

**Versión antigua**:
```bash
streamlit run app_web_respaldo.py --server.port 8501
```

**Versión nueva**:
```bash
streamlit run main.py --server.port 8502
```

Esto te permite comparar ambas en tiempo real.

---

## CHECKLIST FINAL

Antes de considerar la migración completa:

- [ ] Todos los archivos están en su lugar (`verify_install.py` pasa)
- [ ] Las dependencias están instaladas
- [ ] Los secrets están configurados
- [ ] El chat funciona correctamente
- [ ] El stock se calcula bien
- [ ] El Excel se descarga con 4 hojas
- [ ] La integración GLPI responde
- [ ] Se puede eliminar registros

---

## SOPORTE

Si encuentras algún problema:

1. Revisa los logs de error
2. Verifica que `app_web_respaldo.py` funcione (para comparar)
3. Contacta al equipo de desarrollo

---

## ROLLBACK (En caso de emergencia)

Si necesitas volver al sistema antiguo:

```bash
streamlit run app_web_respaldo.py
```

Todos tus datos en GitHub permanecen intactos.

---

**¡Éxito en la migración! 🚀**
