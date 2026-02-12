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

    # =====================================================
    # UTILIDAD GENERAL
    # =====================================================

    def _get_file(self, path):
        try:
            url = f"{self.base_url}/{path}?ref={self.branch}"
            r = requests.get(url, headers=self.headers)

            if r.status_code == 200:
                data = r.json()
                content = base64.b64decode(data["content"]).decode("utf-8")
                return json.loads(content), data.get("sha")

            elif r.status_code == 404:
                # Archivo no existe todavía
                return [], None

            else:
                st.error(f"Error GitHub GET {path}: {r.status_code}")
                return [], None

        except Exception as e:
            st.error(f"Error leyendo {path}: {str(e)}")
            return [], None

    def _update_file(self, path, content, sha=None, message="Update file"):
        try:
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

            if r.status_code in [200, 201]:
                return True
            else:
                st.error(f"Error GitHub PUT {path}: {r.status_code} - {r.text}")
                return False

        except Exception as e:
            st.error(f"Error actualizando {path}: {str(e)}")
            return False

    # =====================================================
    # METODO GENERICO PARA AGREGAR A ARCHIVO JSON (LISTA)
    # =====================================================

    def agregar_a_archivo(self, nombre_archivo, nuevos_datos, mensaje="Actualización"):
        data, sha = self._get_file(nombre_archivo)

        if not isinstance(data, list):
            data = []

        if isinstance(nuevos_datos, list):
            data.extend(nuevos_datos)
        else:
            data.append(nuevos_datos)

        return self._update_file(
            nombre_archivo,
            data,
            sha,
            message=mensaje
        )

    # =====================================================
    # HISTORICO
    # =====================================================

    def obtener_historico(self):
        data, _ = self._get_file("historico.json")
        return data if isinstance(data, list) else []

    def guardar_borrador(self, nuevos_items):
        return self.agregar_a_archivo(
            "historico.json",
            nuevos_items,
            mensaje="Agregar movimiento al historico"
        )

    # =====================================================
    # LECCIONES
    # =====================================================

    def obtener_lecciones(self):
        data, _ = self._get_file("lecciones.json")
        return data if isinstance(data, list) else []

    # =====================================================
    # PEDIDOS
    # =====================================================

    def obtener_pedidos(self):
        data, _ = self._get_file("pedido.json")
        return data if isinstance(data, list) else []

    # =====================================================
    # GLPI INTEGRACION
    # =====================================================

    def solicitar_busqueda_glpi(self, serie):
        payload = {
            "estado": "pendiente",
            "serie": serie
        }

        # buzon.json es dict, no lista
        _, sha = self._get_file("buzon.json")

        return self._update_file(
            "buzon.json",
            payload,
            sha,
            message="Solicitud GLPI"
        )

    def revisar_respuesta_glpi(self):
        data, _ = self._get_file("buzon.json")
        return data if isinstance(data, dict) else {}
