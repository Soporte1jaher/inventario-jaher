import requests
import base64
import json
import time
import streamlit as st

def obtener_github(archivo, user, repo, headers):
    """ Descarga y decodifica archivos JSON desde GitHub """
    timestamp = int(time.time())
    url = f"https://api.github.com/repos/{user}/{repo}/contents/{archivo}?t={timestamp}"  
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            d = resp.json()
            contenido = base64.b64decode(d['content']).decode('utf-8')
            try:
                return json.loads(contenido), d['sha']
            except json.JSONDecodeError:
                st.error(f"⛔ Error: El archivo {archivo} está corrupto.")
                return None, None
        elif resp.status_code == 404:
            return [], None
        return None, None
    except Exception as e:
        st.error(f"❌ Error de conexión GitHub: {str(e)}")
        return None, None

def enviar_github(archivo, datos_nuevos, user, repo, headers, mensaje="Actualización LAIA"):
    """ Agrega datos a una lista existente en GitHub (APPEND) """
    contenido_actual, sha = obtener_github(archivo, user, repo, headers)
    if contenido_actual is None: contenido_actual = []
    
    if isinstance(datos_nuevos, list):
        contenido_actual.extend(datos_nuevos)
    else:
        contenido_actual.append(datos_nuevos)
    
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(contenido_actual, indent=4).encode()).decode(),
        "sha": sha if sha else None
    }
    url = f"https://api.github.com/repos/{user}/{repo}/contents/{archivo}"
    resp = requests.put(url, headers=headers, json=payload)
    return resp.status_code in [200, 201]

def enviar_github_directo(archivo, datos, user, repo, headers, mensaje="LAIA Update"):
    """ Sobreescribe el archivo """
    _, sha = obtener_github(archivo, user, repo, headers)
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(datos, indent=4).encode()).decode(),
        "sha": sha if sha else None
    }
    url = f"https://api.github.com/repos/{user}/{repo}/contents/{archivo}"
    resp = requests.put(url, headers=headers, json=payload)
    return resp.status_code in [200, 201]
