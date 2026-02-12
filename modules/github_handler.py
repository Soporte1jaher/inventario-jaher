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
            st.error("❌ GITHUB_TOKEN no configurado en los Secrets de Streamlit")
            self.token = None

        self.repo = "Soporte1jaher/inventario-jaher"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Cache-Control": "no-cache",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = f"https://api.github.com/repos/{self.repo}/contents"

    def obtener_archivo(self, path):
        """Descarga el archivo y el SHA para poder actualizarlo"""
        timestamp = int(time.time())
        url = f"{self.base_url}/{path}?t={timestamp}"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                content = base64.b64decode(data["content"]).decode("utf-8")
                return json.loads(content), data.get("sha")
            return None, None
        except Exception as e:
            return None, None

    def enviar_archivo_directo(self, path, datos, mensaje="Update"):
        """Sobrescribe el archivo (Modo necesario para el Robot y GLPI)"""
        _, sha = self.obtener_archivo(path)
        
        # Convertimos a JSON y luego a Base64
        json_string = json.dumps(datos, indent=4)
        encoded_content = base64.b64encode(json_string.encode("utf-8")).decode("utf-8")
        
        payload = {
            "message": mensaje,
            "content": encoded_content,
            "sha": sha if sha else None
        }
        
        url = f"{self.base_url}/{path}"
        r = requests.put(url, headers=self.headers, json=payload)
        return r.status_code in [200, 201]

    def enviar_orden_limpieza(self, orden):
        """Esta es la función que llama tu CleaningTab"""
        # IMPORTANTE: Enviamos la orden directa (sin lista []) para que el Robot no falle
        return self.enviar_archivo_directo("buzon.json", orden, "Orden de Borrado Inteligente")

    def agregar_a_lista(self, path, datos_nuevos, mensaje="Update"):
        """Añade items a una lista (Para el histórico)"""
        contenido, sha = self.obtener_archivo(path)
        if contenido is None or not isinstance(contenido, list): 
            contenido = []
        
        if isinstance(datos_nuevos, list):
            contenido.extend(datos_nuevos)
        else:
            contenido.append(datos_nuevos)
            
        json_string = json.dumps(contenido, indent=4)
        encoded_content = base64.b64encode(json_string.encode("utf-8")).decode("utf-8")

        payload = {
            "message": mensaje,
            "content": encoded_content,
            "sha": sha
        }
        url = f"{self.base_url}/{path}"
        r = requests.put(url, headers=self.headers, json=payload)
        return r.status_code in [200, 201]

    def obtener_historico(self):
        """Devuelve la lista del historial"""
        data, _ = self.obtener_archivo("historico.json")
        return data if isinstance(data, list) else []
