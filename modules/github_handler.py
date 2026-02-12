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
        """Descarga y decodifica archivos JSON desde GitHub (REPLICADO)"""
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
        """Agrega datos a una lista (APPEND) - REPLICADO"""
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
        """Sobrescribe el archivo (REPLICADO)"""
        _, sha = self.obtener_github(archivo)
        payload = {
            "message": mensaje,
            "content": base64.b64encode(json.dumps(datos, indent=4).encode()).decode(),
            "sha": sha if sha else None
        }
        resp = requests.put(f"{self.base_url}/{archivo}", headers=self.headers, json=payload)
        return resp.status_code in [200, 201]

    # --- MÉTODOS DE COMPATIBILIDAD PARA TABS (CHAT Y LIMPIEZA) ---

    def obtener_historico(self):
        data, _ = self.obtener_github("historico.json")
        return data if isinstance(data, list) else []

    def obtener_lecciones(self):
        data, _ = self.obtener_github("lecciones.json")
        return data if isinstance(data, list) else []

    def enviar_orden_limpieza(self, orden):
        """Envía orden de borrado al Robot (Usa Append como el v91.2 original)"""
        return self.enviar_github("buzon.json", orden, "Orden de Borrado Inteligente")

    def guardar_borrador(self, datos):
        """🔥 ESTO ES LO QUE EL CHAT TAB ESTABA BUSCANDO"""
        # Según tu v91.2 original, al guardar se envía al BUZON para que el Robot lo procese
        return self.enviar_github("buzon.json", datos, "Registro LAIA desde Chat")

    def aprender_leccion(self, error, correccion):
        """Guarda errores para la memoria de la IA"""
        lecciones = self.obtener_lecciones()
        nueva = {
            "fecha": time.strftime("%Y-%m-%d %H:%M"),
            "lo_que_hizo_mal": error,
            "como_debe_hacerlo": correccion
        }
        lecciones.append(nueva)
        # Solo guardamos las últimas 15 lecciones
        return self.enviar_github_directo("lecciones.json", lecciones[-15:], "LAIA: Nueva lección aprendida")

    def enviar_a_buzon(self, datos):
        """ Envía registros nuevos al buzon.json para que el Robot los procese """
        # Usamos la función enviar_github que ya definimos (la que hace append)
        return self.enviar_github("buzon.json", datos, "Registro desde Chat Modular")
