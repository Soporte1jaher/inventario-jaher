import streamlit as st
import requests
import base64
import json
import time

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

def obtener_github(archivo):
    timestamp = int(time.time())
    url = f"https://api.github.com/repos/{}/{}/contents/{}?t={}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            d = resp.json()
            contenido = base64.b64decode(d['content']).decode('utf-8')
            return json.loads(contenido), d['sha']
        return [], None
    except Exception:
        return None, None

def enviar_github(archivo, datos_nuevos, mensaje="LAIA Update"):
    contenido_actual, sha = obtener_github(archivo)
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
    url = f"https://api.github.com/repos/{}/{}/contents/{}"
    resp = requests.put(url, headers=HEADERS, json=payload)
    return resp.status_code in [200, 201]

def enviar_github_directo(archivo, datos, mensaje="LAIA Direct"):
    _, sha = obtener_github(archivo)
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(datos, indent=4).encode()).decode(),
        "sha": sha if sha else None
    }
    url = f"https://api.github.com/repos/{}/{}/contents/{}"
    resp = requests.put(url, headers=HEADERS, json=payload)
    return resp.status_code in [200, 201]
