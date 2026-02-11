"""
modules/ai_engine.py
Motor de inteligencia artificial y procesamiento
"""
from openai import OpenAI
import json
from config.settings import Config, SYSTEM_PROMPT

class AIEngine:
    """Motor de IA para LAIA"""
    
    def __init__(self):
        self.client = OpenAI(api_key=Config.get_api_key())
        self.model = "gpt-4o-mini"
        self.temperature = 0
    
    def extraer_json(self, texto_completo):
        """
        Separa el texto hablado del bloque JSON
        
        Returns:
            tuple: (texto_hablado, json_puro)
        """
        try:
            inicio = texto_completo.find("{")
            fin = texto_completo.rfind("}") + 1
            
            if inicio != -1:
                texto_hablado = texto_completo[:inicio].strip()
                json_puro = texto_completo[inicio:fin].strip()
                return texto_hablado, json_puro
            
            return texto_completo.strip(), ""
        except:
            return texto_completo.strip(), ""
    
    def procesar_input(self, user_input, lecciones, borrador_actual, historial_mensajes):
        """
        Procesa el input del usuario y retorna la respuesta de LAIA
        
        Args:
            user_input: Mensaje del usuario
            lecciones: Lista de lecciones aprendidas
            borrador_actual: Estado actual del borrador
            historial_mensajes: Últimos mensajes de la conversación
        
        Returns:
            dict: {"mensaje": str, "json_response": dict, "raw_content": str}
        """
        # Construir contexto
        memoria_err = "\n".join([
            f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" 
            for l in lecciones
        ]) if lecciones else ""
        
        contexto_tabla = json.dumps(borrador_actual, ensure_ascii=False) if borrador_actual else "[]"
        
        # Construir mensajes para la API
        mensajes_api = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"LECCIONES TÉCNICAS:\n{memoria_err}"},
            {"role": "system", "content": f"ESTADO ACTUAL: {contexto_tabla}"}
        ]
        
        # Agregar historial reciente (últimos 10 mensajes)
        for m in historial_mensajes[-10:]:
            mensajes_api.append(m)
        
        # Agregar mensaje actual
        mensajes_api.append({"role": "user", "content": user_input})
        
        # Llamar a la API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=mensajes_api,
            temperature=self.temperature
        )
        
        raw_content = response.choices[0].message.content
        texto_fuera, res_txt = self.extraer_json(raw_content)
        
        try:
            res_json = json.loads(res_txt) if res_txt else {}
        except:
            res_json = {}
        
        # Construir mensaje para mostrar
        voz_interna = res_json.get("missing_info", "")
        msg_laia = f"{texto_fuera}\n{voz_interna}".strip()
        
        if not msg_laia:
            msg_laia = "Instrucción técnica procesada."
        
        return {
            "mensaje": msg_laia,
            "json_response": res_json,
            "raw_content": raw_content
        }
    
    def generar_orden_borrado(self, instruccion, historial_reciente):
        """
        Genera una orden de borrado inteligente basada en el historial
        
        Args:
            instruccion: Texto del usuario indicando qué borrar
            historial_reciente: Últimos registros del historial
        
        Returns:
            dict: Orden de borrado en formato JSON
        """
        contexto_breve = json.dumps(historial_reciente, ensure_ascii=False)
        
        prompt_db = f"""
Actúa como DBA Senior. Tu objetivo es generar un comando de borrado en JSON.
Analiza el HISTORIAL ACTUAL para encontrar qué columna y valor coinciden con la instrucción.

COLUMNAS VÁLIDAS: 'equipo', 'marca', 'modelo', 'serie', 'guia', 'destino', 'origen', 'categoria_item'.

HISTORIAL ACTUAL (Muestra): {contexto_breve}

INSTRUCCIÓN DEL USUARIO: "{instruccion}"

REGLAS DE SALIDA:
1. Si pide borrar todo: {{"accion": "borrar_todo"}}
2. Si es específico:
   - Identifica la columna que mejor encaja.
   - Si el usuario menciona un lugar, suele ser 'destino' u 'origen'.
   - Si menciona un código largo, es 'serie' o 'guia'.
   - Genera: {{"accion": "borrar_filtro", "columna": "nombre_de_columna", "valor": "valor_exacto_encontrado_en_historial"}}

RESPONDE ÚNICAMENTE EL JSON.
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt_db}],
            temperature=0
        )
        
        raw_res = response.choices[0].message.content.strip()
        
        # Extraer JSON
        inicio = raw_res.find("{")
        fin = raw_res.rfind("}") + 1
        
        return json.loads(raw_res[inicio:fin])
