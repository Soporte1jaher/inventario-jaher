import requests
import json
import base64
import streamlit as st
import time

class GitHubHandler:
    def __init__(self):
        self.token = st.secrets["GITHUB_TOKEN"]
        self.user = "Soporte1jaher"
        self.repo = "inventario-jaher"
        self.headers = {"Authorization": f"token {self.token}", "Cache-Control": "no-cache"}
        self.base_url = f"https://api.github.com/repos/{self.user}/{self.repo}/contents"

    def obtener_github(self, archivo):
        """ REPLICADO del original """
        timestamp = int(time.time())
        url = f"{self.base_url}/{archivo}?t={timestamp}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                contenido = base64.b64decode(d['content']).decode('utf-8')
                return json.loads(contenido), d['sha']
            return [], None
        except:
            return [], None

    def enviar_github(self, archivo, datos_nuevos, mensaje="Actualización LAIA"):
        """ REPLICADO (Modo APPEND para Limpieza) """
        contenido_actual, sha = self.obtener_github(archivo)
        if contenido_actual is None: contenido_actual = []
        
        if isinstance(datos_nuevos, list):
            contenido_actual.extend(datos_nuevos)
        else:
            contenido_actual.append(datos_nuevos)
            
        payload = {
            "message": mensaje,
            "content": base64.b64encode(json.dumps(contenido_actual, indent=4).encode()).decode(),
            "sha": sha
        }
        resp = requests.put(f"{self.base_url}/{archivo}", headers=self.headers, json=payload)
        return resp.status_code in [200, 201]

    def enviar_github_directo(self, archivo, datos, mensaje="LAIA Update"):
        """ REPLICADO (Modo Sobrescribir para Pedidos) """
        _, sha = self.obtener_github(archivo)
        payload = {
            "message": mensaje,
            "content": base64.b64encode(json.dumps(datos, indent=4).encode()).decode(),
            "sha": sha
        }
        resp = requests.put(f"{self.base_url}/{archivo}", headers=self.headers, json=payload)
        return resp.status_code in [200, 201]

    def obtener_historico(self):
        data, _ = self.obtener_github("historico.json")
        return data if data else []

    def enviar_orden_limpieza(self, orden):
        # El código original usaba enviar_github (append) para buzon.json
        return self.enviar_github("buzon.json", orden, "Orden de Borrado Inteligente")
