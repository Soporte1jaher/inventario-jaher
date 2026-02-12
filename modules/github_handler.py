import requests
import json
import base64
import streamlit as st
import time

class GitHubHandler:
    def __init__(self):
        try:
            self.token = st.secrets["GITHUB_TOKEN"]
        except:
            st.error("❌ GITHUB_TOKEN no configurado")
            self.token = None

        self.repo = "Soporte1jaher/inventario-jaher"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Cache-Control": "no-cache"
        }
        self.base_url = f"https://api.github.com/repos/{self.repo}/contents"

    def obtener_archivo(self, path):
        """Igual al obtener_github original"""
        timestamp = int(time.time())
        url = f"{self.base_url}/{path}?t={timestamp}"
        try:
            r = requests.get(url, headers=self.headers)
            if r.status_code == 200:
                data = r.json()
                content = base64.b64decode(data["content"]).decode("utf-8")
                return json.loads(content), data.get("sha")
            return None, None
        except:
            return None, None

    def enviar_archivo_directo(self, path, datos, mensaje="Update"):
        """ESTA ES LA CLAVE: Igual al enviar_github_directo original"""
        _, sha = self.obtener_archivo(path)
        payload = {
            "message": mensaje,
            "content": base64.b64encode(json.dumps(datos, indent=4).encode()).decode(),
            "sha": sha if sha else None
        }
        url = f"{self.base_url}/{path}"
        r = requests.put(url, headers=self.headers, json=payload)
        return r.status_code in [200, 201]

    def agregar_a_lista(self, path, datos_nuevos, mensaje="Update"):
        """Igual al enviar_github original (para Histórico y Lecciones)"""
        contenido, sha = self.obtener_archivo(path)
        if contenido is None: contenido = []
        
        if isinstance(datos_nuevos, list):
            contenido.extend(datos_nuevos)
        else:
            contenido.append(datos_nuevos)
            
        payload = {
            "message": mensaje,
            "content": base64.b64encode(json.dumps(contenido, indent=4).encode()).decode(),
            "sha": sha
        }
        url = f"{self.base_url}/{path}"
        r = requests.put(url, headers=self.headers, json=payload)
        return r.status_code in [200, 201]

    def obtener_historico(self):
        data, _ = self.obtener_archivo("historico.json")
        return data if data else []
