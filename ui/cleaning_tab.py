import streamlit as st
import pandas as pd
import re

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class CleaningTab:
    """
    Limpieza Inteligente (Modo asistido)
    - Detecta intención (serie / marca / equipo / etc.)
    - Busca coincidencias
    - Si 1: muestra “Encontré este registro… ¿Eliminar?”
    - Si varios: muestra lista para elegir (checkbox por fila)
    - Si 0: “No encontré…”
    - Confirmación obligatoria + bloqueo anti-borrado masivo
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

        # Estados UI
        if "cln_df" not in st.session_state:
            st.session_state.cln_df = pd.DataFrame()
        if "cln_results" not in st.session_state:
            st.session_state.cln_results = pd.DataFrame()
        if "cln_selected_idx" not in st.session_state:
            st.session_state.cln_selected_idx = set()
        if "cln_last_query" not in st.session_state:
            st.session_state.cln_last_query = ""
        if "cln_mode" not in st.session_state:
            st.session_state.cln_mode = "AUTO"

    # ---------------------------
    # Render
    # ---------------------------
    def render(self):
        with st.container(border=True):
            st.markdown("## 🗑️ Limpieza Inteligente del Historial")
            st.caption("Escribe una orden. LAIA detecta coincidencias y tú eliges qué borrar (seguro).")

        # Cargar historial 1 vez por render
        hist = self.github.obtener_historico()
        if hist is None:
            st.error("❌ No pude leer el historial (GitHub). Revisa tu token/secret.")
            return
        if len(hist) == 0:
            st.info("📭 El historial está vacío.")
            return

        df = pd.DataFrame(hist)
        df = self._normalize(df)
        st.session_state.cln_df = df

        with st.container(border=True):
            st.info("💡 Ejemplos: **elimina la serie 12345**, **borra marca LG**, **quita lo de Latacunga**, **elimina destino Puyo**")

            q = st.text_input(
                "¿Qué deseas eliminar?",
                placeholder="Ej: elimina serie 12345 / borra marca LG ...",
                key="txt_limpieza",
            ).strip()

            c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 2.4], vertical_alignment="center")
            with c1:
                if st.button("🔎 Buscar", type="secondary", use_container_width=True):
                    if q:
                        self._run_search(q)
                    else:
                        st.warning("Escribe una instrucción primero.")
            with c2:
                if st.button("🧹 Limpiar", use_container_width=True):
                    self._reset()
                    st.rerun()
            with c3:
                st.session_state.cln_mode = st.selectbox(
                    "Modo",
                    options=["AUTO", "SERIE", "MARCA", "EQUIPO", "DESTINO", "ORIGEN", "TEXTO"],
                    index=0,
                    help="AUTO intenta detectar el campo. Los otros fuerzan dónde buscar.",
                )
            with c4:
                st.caption("✅ Flujo seguro: buscar → seleccionar → confirmar → enviar orden")

        # Render resultados si existen
        if not st.session_state.cln_results.empty:
            self._render_results()

    # ---------------------------
    # Search pipeline
    # ---------------------------
    def _run_search(self, q: str):
        df = st.session_state.cln_df
        mode = st.session_state.cln_mode

        # 1) Intento AI para extraer campo/valor (si existe en tu motor)
        #    Si falla, seguimos con heurística local sin romper nada.
        ai_hint = {}
        try:
            # Si tu AIEngine no tiene esto, no pasa nada
            # (lo atrapamos y seguimos).
            ai_hint = self.ai_engine.generar_orden_borrado(q, df.tail(300).to_dict("records")) or {}
        except Exception:
            ai_hint = {}

        # 2) Detectar criterio (local + hint)
        field, value = self._detect_criterion(q, mode=mode, ai_hint=ai_hint)

        # 3) Buscar
        results = self._search(df, field=field, value=value, raw_query=q)

        st.session_state.cln_last_query = q
        st.session_state.cln_results = results
        st.session_state.cln_selected_idx = set()

        # Mensajes estilo “tono”
        if results.empty:
            st.warning("❌ No he encontrado ningún elemento con esa descripción.")
        elif len(results) == 1:
            r = results.iloc[0]
            st.success(f"✅ He encontrado 1 registro: **{self._pretty_row(r)}**. Selecciónalo abajo para eliminar.")
        else:
            st.success(f"✅ He encontrado **{len(results)}** registros con {field.upper()} = **{value}**. Elige cuáles eliminar abajo.")

    def _detect_criterion(self, q: str, mode: str = "AUTO", ai_hint: dict | None = None):
        """
        Devuelve (field, value)
        field: serie/marca/equipo/destino/origen/text
        """
        ql = q.lower().strip()
        ai_hint = ai_hint or {}

        # Si el usuario fuerza modo
        if mode != "AUTO":
            return mode.lower(), self._extract_value(ql)

        # Heurística directa (serie)
        # Captura: "serie12345", "serie 12345", "serial 12345"
        m = re.search(r"(serie|serial)\s*[:#-]?\s*([a-z0-9\-_/]+)", ql)
        if m:
            return "serie", m.group(2).strip()

        # Marca
        m = re.search(r"(marca)\s*[:#-]?\s*([a-z0-9\-_/]+)", ql)
        if m:
            return "marca", m.group(2).strip()

        # Equipo
        m = re.search(r"(equipo)\s*[:#-]?\s*([a-z0-9\-_/]+)", ql)
        if m:
            return "equipo", m.group(2).strip()

        # Destino / Origen
        m = re.search(r"(destino)\s*[:#-]?\s*([a-z0-9\-_/]+)", ql)
        if m:
            return "destino", m.group(2).strip()

        m = re.search(r"(origen)\s*[:#-]?\s*([a-z0-9\-_/]+)", ql)
        if m:
            return "origen", m.group(2).strip()

        # Si la IA dio pista utilizable
        # (no sé tu formato exacto, por eso lo hago flexible)
        for k in ["serie", "marca", "equipo", "destino", "origen"]:
            v = ai_hint.get(k) or ai_hint.get(k.upper())
            if isinstance(v, str) and v.strip():
                return k, v.strip().lower()

        # Fallback: búsqueda libre en todo
        return "texto", self._extract_value(ql)

    def _extract_value(self, ql: str):
        # Limpieza simple: quitar verbos comunes
        stop = {"elimina", "eliminar", "borra", "borrar", "quita", "quitar", "suprime", "suprimir", "de", "la", "lo", "los", "las"}
        tokens = [t for t in re.split(r"\s+", ql) if t and t not in stop]
        return " ".join(tokens).strip() if tokens else ql

    def _search(self, df: pd.DataFrame, field: str, value: str, raw_query: str):
        """
        Devuelve DF con coincidencias.
        - serie: match más estricto
        - otros: contains
        - texto: busca en todo
        """
        value = (value or "").strip().lower()
        if not value:
            return pd.DataFrame()

        # columnas seguras
        cols = df.columns.tolist()

        if field in cols and field != "texto":
            s = df[field].astype(str).str.lower().str.strip()
            if field == "serie":
                # Serie: preferimos exacto, y si no, contains
                mask = (s == value) | s.str.contains(re.escape(value), na=False)
            else:
                mask = s.str.contains(re.escape(value), na=False)
            out = df[mask].copy()
            return out.sort_values("fecha_registro_dt", ascending=False).head(500)

        # TEXTO: buscar en varias columnas (seguro)
        search_cols = [c for c in ["serie", "marca", "equipo", "modelo", "origen", "destino", "guia", "reporte"] if c in cols]
        if not search_cols:
            search_cols = cols

        mask = pd.Series([False] * len(df), index=df.index)
        for c in search_cols:
            try:
                mask = mask | df[c].astype(str).str.lower().str.contains(re.escape(value), na=False)
            except Exception:
                pass

        out = df[mask].copy()
        return out.sort_values("fecha_registro_dt", ascending=False).head(500)

    # ---------------------------
    # Results UI
    # ---------------------------
    def _render_results(self):
        dfres = st.session_state.cln_results
        q = st.session_state.cln_last_query

        with st.container(border=True):
            st.markdown("### 📌 Resultados encontrados")
            st.caption(f"Consulta: **{q}**")

            # Tabla "bonita"
            cols_pref = [c for c in [
                "fecha_registro", "tipo", "categoria_item", "equipo", "marca", "modelo", "serie",
                "cantidad", "estado", "origen", "destino", "guia", "reporte"
            ] if c in dfres.columns]

            # Selector de filas con checkbox usando Data Editor
            view = dfres[cols_pref].copy()
            view.insert(0, "ELIMINAR", False)

            edited = st.data_editor(
                view,
                use_container_width=True,
                hide_index=False,
                num_rows="fixed",
                height=520,
                key="clean_editor",
            )

            selected_idx = set(edited.index[edited["ELIMINAR"] == True].tolist())
            st.session_state.cln_selected_idx = selected_idx

        # Confirmación + envío
        with st.container(border=True):
            nsel = len(st.session_state.cln_selected_idx)
            total = len(dfres)

            k1, k2, k3 = st.columns([1.2, 1.2, 2.6], vertical_alignment="center")
            with k1:
                st.metric("Encontrados", total)
            with k2:
                st.metric("Seleccionados", nsel)
            with k3:
                st.caption("Selecciona y confirma. No se borra nada hasta que envíes la orden.")

            if total >= 50:
                st.warning("⚠️ Muchos resultados (≥ 50). Selecciona solo lo necesario. Para borrado masivo te conviene filtrar más específico (serie/guía).")

            confirm = st.checkbox("✅ Confirmo que deseo eliminar los registros seleccionados", value=False)

            disabled = (nsel == 0) or (not confirm)

            if st.button("🔥 ENVIAR ORDEN DE BORRADO", type="primary", use_container_width=True, disabled=disabled):
                self._send_delete_order()

    def _send_delete_order(self):
        dfall = st.session_state.cln_df
        dfres = st.session_state.cln_results
        selected_idx = sorted(list(st.session_state.cln_selected_idx))

        if not selected_idx:
            st.warning("Selecciona al menos 1 registro.")
            return

        # Construir "matches" con firma (más seguro)
        firmas = []
        for i in selected_idx:
            try:
                r = dfres.loc[i]
            except Exception:
                continue
            firmas.append({
                "idx": int(i),
                "serie": str(r.get("serie", "")).strip(),
                "guia": str(r.get("guia", "")).strip(),
                "fecha_registro": str(r.get("fecha_registro", "")).strip(),
                "equipo": str(r.get("equipo", "")).strip(),
                "marca": str(r.get("marca", "")).strip(),
                "modelo": str(r.get("modelo", "")).strip(),
                "origen": str(r.get("origen", "")).strip(),
                "destino": str(r.get("destino", "")).strip(),
            })

        orden = {
            "action": "delete",
            "source": "historico.json",
            "instruction": st.session_state.cln_last_query,
            "count": len(firmas),
            "indices": [int(x) for x in selected_idx],
            "matches": firmas,
        }

        ok = self.github.enviar_orden_limpieza(orden)
        if ok:
            st.success("✅ Orden enviada. El robot procesará la limpieza.")
            st.json(orden)
            self._reset()
            st.rerun()
        else:
            st.error("❌ No se pudo enviar la orden. Revisa logs/token/formato esperado por el robot.")
            st.json(orden)

    # ---------------------------
    # Utils
    # ---------------------------
    def _normalize(self, df: pd.DataFrame):
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        # columnas esperadas
        for c in ["fecha_registro", "tipo", "categoria_item", "equipo", "marca", "modelo", "serie",
                  "cantidad", "estado", "origen", "destino", "guia", "reporte"]:
            if c not in df.columns:
                df[c] = ""

        # fecha dt para ordenar
        df["fecha_registro_dt"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
        # versión string bonita
        try:
            df["fecha_registro"] = df["fecha_registro_dt"].dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

        # cantidad numérica
        try:
            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(1).astype(int)
        except Exception:
            pass

        # limpieza texto
        for c in ["tipo", "equipo", "marca", "modelo", "serie", "estado", "origen", "destino", "guia", "reporte", "categoria_item"]:
            df[c] = df[c].astype(str).fillna("").str.strip()

        return df

    def _pretty_row(self, r: pd.Series):
        s = str(r.get("serie", "")).strip()
        e = str(r.get("equipo", "")).strip()
        m = str(r.get("marca", "")).strip()
        f = str(r.get("fecha_registro", "")).strip()
        d = str(r.get("destino", "")).strip()
        return f"serie={s or 'N/A'} | equipo={e or 'N/A'} | marca={m or 'N/A'} | destino={d or 'N/A'} | fecha={f or 'N/A'}"

    def _reset(self):
        st.session_state.cln_results = pd.DataFrame()
        st.session_state.cln_selected_idx = set()
        st.session_state.cln_last_query = ""
