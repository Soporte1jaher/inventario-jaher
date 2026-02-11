import requests
import json
import base64
import streamlit as st


class GitHubHandler:
    def __init__(self):
        self.token = st.secrets["GITHUB_TOKEN"]
        self.repo = "Soporte1jaher/inventario-jaher"
        self.branch = "main"
        self.base_url = f"https://api.github.com/repos/{self.repo}/contents"

        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    # =====================================================
    # UTILIDAD GENERAL
    # =====================================================

    def _get_file(self, path):
        url = f"{self.base_url}/{path}?ref={self.branch}"
        r = requests.get(url, headers=self.headers)

        if r.status_code == 200:
            data = r.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return json.loads(content), data["sha"]

        return [], None

    def _update_file(self, path, content, sha=None, message="Update file"):
        url = f"{self.base_url}/{path}"

        encoded = base64.b64encode(
            json.dumps(content, indent=2).encode()
        ).decode()

        payload = {
            "message": message,
            "content": encoded,
            "branch": self.branch
        }

        if sha:
            payload["sha"] = sha

        r = requests.put(url, headers=self.headers, json=payload)

        return r.status_code in [200, 201]

    # =====================================================
    # HISTORICO
    # =====================================================

    def guardar_borrador(self, nuevos_items):
        historico, sha = self._get_file("historico.json")

        if not isinstance(historico, list):
            historico = []

        historico.extend(nuevos_items)

        return self._update_file(
            "historico.json",
            historico,
            sha,
            message="Agregar movimiento al historico"
        )

    # =====================================================
    # LECCIONES
    # =====================================================

    def obtener_lecciones(self):
        data, _ = self._get_file("lecciones.json")
        return data if isinstance(data, list) else []

    # =====================================================
    # GLPI INTEGRACION
    # =====================================================

    def solicitar_busqueda_glpi(self, serie):
        payload = {
            "estado": "pendiente",
            "serie": serie
        }

        return self._update_file(
            "buzon.json",
            payload,
            message="Solicitud GLPI"
        )

    def revisar_respuesta_glpi(self):
        data, _ = self._get_file("buzon.json")
        return data
