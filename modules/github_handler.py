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
        self.base_url = f"https://api.github.com/repos/{self.user}/{self.repo}/contents"

    def obtener_github(self, archivo):
        """Método base para descargar archivos"""
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
        """Método para acumular datos en una lista (APPEND)"""
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
            "sha": sha if sha else None
        }
        resp = requests.put(f"{self.base_url}/{archivo}", headers=self.headers, json=payload)
        return resp.status_code in [200, 201]

    def enviar_github_directo(self, archivo, datos, mensaje="LAIA Update"):
        """Método para sobrescribir archivos (Para pedidos y configuración)"""
        _, sha = self.obtener_github(archivo)
        payload = {
            "message": mensaje,
            "content": base64.b64encode(json.dumps(datos, indent=4).encode()).decode(),
            "sha": sha if sha else None
        }
        resp = requests.put(f"{self.base_url}/{archivo}", headers=self.headers, json=payload)
        return resp.status_code in [200, 201]

    # --- MÉTODOS DE CONVENIENCIA PARA LA APP ---

    def obtener_historico(self):
        """Usado por Limpieza y Stock"""
        data, _ = self.obtener_github("historico.json")
        return data if isinstance(data, list) else []

    def obtener_lecciones(self):
        """🔥 ESTO ES LO QUE FALTABA: Memoria del Chat"""
        data, _ = self.obtener_github("lecciones.json")
        return data if isinstance(data, list) else []

    def enviar_orden_limpieza(self, orden):
        """Envía la orden al Robot de la PC"""
        # Usamos enviar_github para acumular órdenes o directo para una sola
        return self.enviar_github("buzon.json", orden, "Orden de Borrado Inteligente")
