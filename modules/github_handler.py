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
        """ REPLICADO EXACTO DEL ORIGINAL v91.2 """
        timestamp = int(time.time())
        url = f"{self.base_url}/{archivo}?t={timestamp}"  
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                d = resp.json()
                contenido = base64.b64decode(d['content']).decode('utf-8')
                return json.loads(contenido), d['sha']
            elif resp.status_code == 404:
                return [], None
            return None, None
        except:
            return None, None

    def enviar_github(self, archivo, datos_nuevos, mensaje="Actualización LAIA"):
        """ REPLICADO EXACTO (APPEND) - Usado para Limpieza e Historial """
        contenido_actual, sha = self.obtener_github(archivo)
        if not isinstance(contenido_actual, list): contenido_actual = []
         
        if isinstance(datos_nuevos, list):
            contenido_actual.extend(datos_nuevos)
        else:
            contenido_actual.append(datos_nuevos)
         
        payload = {
            "message": mensaje,
            "content": base64.b64encode(json.dumps(contenido_actual, indent=4).encode()).decode(),
            "sha": sha if sha else None
        }
        resp = requests.put(f"{self.base_url}/{archivo}", headers=self.headers, json=payload)
        return resp.status_code in [200, 201]

    def enviar_github_directo(self, archivo, datos, mensaje="LAIA Update"):
        """ REPLICADO EXACTO (SOBRESCRIBIR) - Usado para Pedidos y Config """
        _, sha = self.obtener_github(archivo)
        payload = {
            "message": mensaje,
            "content": base64.b64encode(json.dumps(datos, indent=4).encode()).decode(),
            "sha": sha if sha else None
        }
        resp = requests.put(f"{self.base_url}/{archivo}", headers=self.headers, json=payload)
        return resp.status_code in [200, 201]

    def obtener_historico(self):
        data, _ = self.obtener_github("historico.json")
        return data if data else []
    def enviar_orden_limpieza(self, orden):
        """
        ORDEN AL ROBOT: Usamos modo directo para que el archivo sea {...} 
        y la consola lo reconozca inmediatamente.
        """
        return self.enviar_github_directo("buzon.json", orden, "Orden de Borrado")
