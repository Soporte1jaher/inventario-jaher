import requests
import json
import base64
import streamlit as st

class GitHubHandler:
    def __init__(self):
        try:
            self.token = st.secrets["GITHUB_TOKEN"]
        except Exception:
            st.error("⚠️ GITHUB_TOKEN no configurado en Secrets")
            self.token = None

        self.repo = "Soporte1jaher/inventario-jaher"
        self.branch = "main"
        self.base_url = f"https://api.github.com/repos/{self.repo}/contents"

        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def obtener_archivo(self, path):
        """Método público para obtener cualquier JSON y su SHA"""
        try:
            url = f"{self.base_url}/{path}?ref={self.branch}"
            r = requests.get(url, headers=self.headers)
            if r.status_code == 200:
                data = r.json()
                content = base64.b64decode(data["content"]).decode("utf-8")
                return json.loads(content), data.get("sha")
            return [], None
        except Exception as e:
            st.error(f"Error leyendo {path}: {str(e)}")
            return [], None

    def _update_file(self, path, content, sha=None, message="Update file"):
        try:
            url = f"{self.base_url}/{path}"
            encoded = base64.b64encode(json.dumps(content, indent=2).encode()).decode()
            payload = {
                "message": message,
                "content": encoded,
                "branch": self.branch
            }
            if sha:
                payload["sha"] = sha
            r = requests.put(url, headers=self.headers, json=payload)
            return r.status_code in [200, 201]
        except Exception as e:
            st.error(f"Error actualizando {path}: {str(e)}")
            return False

    def agregar_a_archivo(self, nombre_archivo, nuevos_datos, mensaje="Actualización"):
        """Agrega datos a una lista (Append)"""
        data, sha = self.obtener_archivo(nombre_archivo)
        if not isinstance(data, list):
            data = []
        if isinstance(nuevos_datos, list):
            data.extend(nuevos_datos)
        else:
            data.append(nuevos_datos)
        return self._update_file(nombre_archivo, data, sha, message=mensaje)

    def obtener_historico(self):
        data, _ = self.obtener_archivo("historico.json")
        return data if isinstance(data, list) else []

    # --- GLPI Y LIMPIEZA ---
    
    def enviar_orden_limpieza(self, orden):
        """Las órdenes de limpieza van al buzón como una lista para el Robot"""
        return self.agregar_a_archivo("buzon.json", orden, "Orden de Borrado Inteligente")

    def solicitar_busqueda_glpi(self, serie):
        """Los pedidos de GLPI suelen ser un archivo único (pedido.json)"""
        payload = {"estado": "pendiente", "serie_a_buscar": serie, "info": ""}
        _, sha = self.obtener_archivo("pedido.json")
        return self._update_file("pedido.json", payload, sha, message=f"Solicitud serie {serie}")

    def revisar_respuesta_glpi(self):
        data, _ = self.obtener_archivo("pedido.json")
        return data if isinstance(data, dict) else {}
