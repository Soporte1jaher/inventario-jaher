import requests
import json
import base64
import streamlit as st
import time

class GitHubHandler:
    def __init__(self):
        try:
            self.token = st.secrets["GITHUB_TOKEN"]
            self.user = "Soporte1jaher"
            self.repo = "inventario-jaher"
        except:
            st.error("❌ GITHUB_TOKEN no configurado en Secrets")
            self.token = None

        self.headers = {
            "Authorization": f"token {self.token}",
            "Cache-Control": "no-cache"
        }

    def obtener_github(self, archivo):
        """Descarga y decodifica archivos JSON desde GitHub"""
        timestamp = int(time.time())
        url = f"https://api.github.com/repos/{self.user}/{self.repo}/contents/{archivo}?t={timestamp}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                contenido = base64.b64decode(d['content']).decode('utf-8')
                return json.loads(contenido), d['sha']
            return None, None
        except:
            return None, None

    def enviar_github_directo(self, archivo, datos, mensaje="LAIA Update"):
        """Sobrescribe el archivo (Indispensable para que el Robot de la PC lo lea)"""
        _, sha = self.obtener_github(archivo)
        payload = {
            "message": mensaje,
            "content": base64.b64encode(json.dumps(datos, indent=4).encode()).decode(),
            "sha": sha if sha else None
        }
        url = f"https://api.github.com/repos/{self.user}/{self.repo}/contents/{archivo}"
        resp = requests.put(url, headers=self.headers, json=payload)
        return resp.status_code in [200, 201]

    def enviar_github(self, archivo, datos_nuevos, mensaje="Actualización LAIA"):
        """Agrega datos a una lista (Para el Histórico)"""
        contenido_actual, sha = self.obtener_github(archivo)
        if not isinstance(contenido_actual, list):
            contenido_actual = []
        
        if isinstance(datos_nuevos, list):
            contenido_actual.extend(datos_nuevos)
        else:
            contenido_actual.append(datos_nuevos)
            
        payload = {
            "message": mensaje,
            "content": base64.b64encode(json.dumps(contenido_actual, indent=4).encode()).decode(),
            "sha": sha
        }
        url = f"https://api.github.com/repos/{self.user}/{self.repo}/contents/{archivo}"
        resp = requests.put(url, headers=self.headers, json=payload)
        return resp.status_code in [200, 201]

    def obtener_historico(self):
        data, _ = self.obtener_github("historico.json")
        return data if isinstance(data, list) else []

    def enviar_orden_limpieza(self, orden):
        """
        ORDEN AL ROBOT: Usamos modo directo para que el archivo sea {...} 
        y la consola lo reconozca inmediatamente.
        """
        return self.enviar_github_directo("buzon.json", orden, "Orden de Borrado")
