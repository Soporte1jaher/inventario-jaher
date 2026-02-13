import streamlit as st
import pandas as pd
import re

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class CleaningTab:
    """
    Limpieza Inteligente (Modo asistido + SEGURO)
    - Detecta intención (serie / marca / equipo / destino / origen / texto)
    - Busca coincidencias
    - Si 0: “No encontrado”
    - Si 1 o varios: tabla para elegir (checkbox)
    - Envía orden al robot con:
        - indices (IDX reales del historico.json)
        - matches (firmas) para borrado robusto
    - Evita NaN visual (rellena con N/A)
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

        # Estado UI
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
        if "cln_last_order" not in st.session_state:
            st.session_state.cln_last_order = None

    # ---------------------------
    # Render
    # ---------------------------
    def render(self):
        with st.container(border=True):
            st.markdown("## 🗑️ Limpieza Inteligente del Historial")
            st.caption("Flujo seguro: buscar → seleccionar → confirmar → enviar orden al robot → refrescar.")

        # Aviso de “orden enviada”
        if st.session_state.cln_last_order:
            with st.container(border=True):
                st.success("✅ Orden enviada. Ahora el robot debe procesarla y actualizar historico.json.")
                c1, c2 = st.columns([1.2, 3.8], vertical_alignment="center")
                with c1:
                    if st.button("🔄 Refrescar", use_container_width=True):
                        st.session_state.cln_last_order = None
                        st.rerun()
                with c2:
                    st.caption("Si el robot aún no corrió, verás la serie todavía. Refresca después de que el robot procese.")
                with st.expander("📦 Ver orden enviada", expanded=False):
                    st.json(st.session_state.cln_last_order)

        # Cargar histórico
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
            st.info(
                "💡 Ejemplos: **elimina la serie 12345**, **borra marca LG**, **quita destino Puyo**, "
                "**elimina origen bodega**, **borra lo de Latacunga**"
            )

            q = st.text_input(
                "¿Qué deseas eliminar?",
                placeholder="Ej: elimina serie 12345 / borra marca LG ...",
                key="txt_limpieza",
            ).strip()

            c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.4, 2.2], vertical_alignment="center")
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
                    help="AUTO detecta el campo. Los otros fuerzan dónde buscar.",
                )
            with c4:
                st.caption("🛡️ No se borra nada hasta que confirmes y envíes la orden.")

        # Render resultados si existen
        if not st.session_state.cln_results.empty:
            self._render_results()

    # ---------------------------
    # Search pipeline
    # ---------------------------
    def _run_search(self, q: str):
        df = st.session_state.cln_df
        mode = st.session_state.cln_mode

        # Pista IA (opcional, no rompe si falla)
        ai_hint = {}
        try:
            ai_hint = self.ai_engine.generar_orden_borrado(q, df.tail(300).to_dict("records")) or {}
        except Exception:
            ai_hint = {}

        field, value = self._detect_criterion(q, mode=mode, ai_hint=ai_hint)
        results = self._search(df, field=field, value=value)

        st.session_state.cln_last_query = q
        st.session_state.cln_results = results
        st.session_state.cln_selected_idx = set()

        if results.empty:
            st.warning("❌ No he encontrado ningún elemento con esa descripción.")
        elif len(results) == 1:
            r = results.iloc[0]
            st.success(f"✅ He encontrado 1 registro: **{self._pretty_row(r)}**. Selecciónalo abajo para eliminar.")
        else:
            st.success(f"✅ He encontrado **{len(results)}** registros. Elige cuáles eliminar abajo.")

    def _detect_criterion(self, q: str, mode: str = "AUTO", ai_hint: dict | None = None):
        ql = q.lower().strip()
        ai_hint = ai_hint or {}

        # Forzado
        if mode != "AUTO":
            return mode.lower(), self._extract_value(ql)

        # Serie/Serial
        m = re.search(r"(serie|serial)\s*[:#-]?\s*([a-z0-9\-_/]+)", ql)
        if m:
            return "serie", m.group(2).strip()

        # Marca/Equipo/Destino/Origen
        for k in ["marca", "equipo", "destino", "origen"]:
            m = re.search(rf"({k})\s*[:#-]?\s*([a-z0-9\-_/]+)", ql)
            if m:
                return k, m.group(2).strip()

        # Hint IA (si viene bien)
        for k in ["serie", "marca", "equipo", "destino", "origen"]:
            v = ai_hint.get(k) or ai_hint.get(k.upper())
            if isinstance(v, str) and v.strip():
                return k, v.strip().lower()

        return "texto", self._extract_value(ql)

    def _extract_value(self, ql: str):
        stop = {
            "elimina","eliminar","borra","borrar","quita","quitar","suprime","suprimir",
            "de","la","lo","los","las","del","al","por","para"
        }
        tokens = [t for t in re.split(r"\s+", ql) if t and t not in stop]
        return " ".join(tokens).strip() if tokens else ql

    def _search(self, df: pd.DataFrame, field: str, value: str):
        value = (value or "").strip().lower()
        if not value:
            return pd.DataFrame()

        # Campo directo
        if field in df.columns and field != "texto":
            s = df[field].astype(str).str.lower().str.strip()
            if field == "serie":
                mask = (s == value) | s.str.contains(re.escape(value), na=False)
            else:
                mask = s.str.contains(re.escape(value), na=False)
            out = df[mask].copy()
            return out.sort_values("fecha_registro_dt", ascending=False).head(800)

        # Texto: buscar en columnas típicas
        search_cols = [c for c in ["serie","marca","equipo","modelo","origen","destino","guia","reporte"] if c in df.columns]
        if not search_cols:
            search_cols = df.columns.tolist()

        mask = pd.Series(False, index=df.index)
        for c in search_cols:
            try:
                mask = mask | df[c].astype(str).str.lower().str.contains(re.escape(value), na=False)
            except Exception:
                pass

        out = df[mask].copy()
        return out.sort_values("fecha_registro_dt", ascending=False).head(800)

    # ---------------------------
    # Results UI
    # ---------------------------
    def _render_results(self):
        dfres = st.session_state.cln_results.copy()
        q = st.session_state.cln_last_query

        with st.container(border=True):
            st.markdown("### 📌 Resultados encontrados")
            st.caption(f"Consulta: **{q}**")

            cols_pref = [c for c in [
                "idx", "fecha_registro", "tipo", "categoria_item", "equipo", "marca", "modelo", "serie",
                "cantidad", "estado", "origen", "destino", "guia", "reporte"
            ] if c in dfres.columns]

            # DataEditor con checkbox
            view = dfres[cols_pref].copy()
            view.insert(0, "ELIMINAR", False)

            edited = st.data_editor(
                view,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                height=520,
                key="clean_editor_v2",
            )

            # IMPORTANTÍSIMO: seleccionamos por columna IDX real (no por índice del DF)
            selected_idx = set(edited.loc[edited["ELIMINAR"] == True, "idx"].astype(int).tolist())
            st.session_state.cln_selected_idx = selected_idx

        with st.container(border=True):
            total = len(dfres)
            nsel = len(st.session_state.cln_selected_idx)

            k1, k2, k3 = st.columns([1.2, 1.2, 2.6], vertical_alignment="center")
            k1.metric("Encontrados", total)
            k2.metric("Seleccionados", nsel)
            k3.caption("Se enviará una orden al robot con IDX reales del historico.json.")

            if total >= 50:
                st.warning("⚠️ Muchos resultados (≥ 50). Mejor filtra más específico (serie/guía).")

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

        # Firmas robustas (por si el robot valida)
        firmas = []
        # dfall tiene idx real; filtramos por idx seleccionado
        sub = dfall[dfall["idx"].isin(selected_idx)].copy()

        for _, r in sub.iterrows():
            firmas.append({
                "idx": int(r.get("idx")),
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
            "indices": [int(x) for x in selected_idx],  # IDX reales del historico.json
            "matches": firmas,  # firmas para validar
        }

        ok = self.github.enviar_orden_limpieza(orden)
        if ok:
            st.session_state.cln_last_order = orden
            st.success("✅ Orden enviada. Refresca cuando el robot procese.")
            self._reset(keep_order=True)
            st.rerun()
        else:
            st.error("❌ No se pudo enviar la orden. Revisa formato esperado por el robot.")
            st.json(orden)

    # ---------------------------
    # Utils
    # ---------------------------
    def _normalize(self, df: pd.DataFrame):
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        # idx real del historico.json (posición)
        df.insert(0, "idx", range(len(df)))

        # columnas esperadas
        for c in [
            "fecha_registro", "tipo", "categoria_item", "equipo", "marca", "modelo", "serie",
            "cantidad", "estado", "origen", "destino", "guia", "reporte"
        ]:
            if c not in df.columns:
                df[c] = ""

        # fecha dt para ordenar
        df["fecha_registro_dt"] = pd.to_datetime(df["fecha_registro"], errors="coerce")

        # version bonita string (y evitar NaN)
        df["fecha_registro"] = df["fecha_registro_dt"].dt.strftime("%Y-%m-%d %H:%M")
        df["fecha_registro"] = df["fecha_registro"].fillna("N/A")

        # cantidad numérica
        try:
            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(1).astype(int)
        except Exception:
            df["cantidad"] = 1

        # limpiar NaN en textos
        text_cols = ["tipo","categoria_item","equipo","marca","modelo","serie","estado","origen","destino","guia","reporte"]
        for c in text_cols:
            df[c] = df[c].astype(str).replace({"nan": ""}).fillna("").str.strip()
            df.loc[df[c] == "", c] = "N/A"

        return df

    def _pretty_row(self, r: pd.Series):
        return (
            f"serie={str(r.get('serie','N/A'))} | "
            f"equipo={str(r.get('equipo','N/A'))} | "
            f"marca={str(r.get('marca','N/A'))} | "
            f"destino={str(r.get('destino','N/A'))} | "
            f"fecha={str(r.get('fecha_registro','N/A'))}"
        )

    def _reset(self, keep_order: bool = False):
        st.session_state.cln_results = pd.DataFrame()
        st.session_state.cln_selected_idx = set()
        st.session_state.cln_last_query = ""
        if not keep_order:
            st.session_state.cln_last_order = None
