import streamlit as st
import pandas as pd
import re
import datetime

from modules.ai_engine import AIEngine
from modules.github_handler import GitHubHandler


class CleaningTab:
    """
    🗑️ Limpieza Inteligente (Modo asistido + SEGURO) — ULTRA PRO

    ✅ Funciones:
    - Detecta intención (serie / marca / equipo / destino / origen / tipo / estado / texto / vacios)
    - Busca coincidencias (exacta + contains, según campo)
    - Tabla editable con checkbox (selección múltiple)
    - Acciones rápidas: Seleccionar todo / Invertir / Limpiar selección
    - Preview de borrado: “Qué se va a borrar” antes de enviar
    - Envía orden al robot con 2 esquemas (nuevo + compat)
    - Evita NaN visual (rellena con N/A)
    - Anti-basuara: detecta registros “vacíos” (>=80% campos N/A)
    - FIX: keys únicos (StreamlitDuplicateElementId)

    🔥 Mejoras “mamadas”:
    - Modo “VACIOS” real (mata filas fantasma)
    - Modo “RANGO_FECHA” por texto: "fecha: 2026-02-12" / "desde 2026-02-10 hasta 2026-02-12"
    - Borrado por “firma” (matches) para robustez si cambian índices
    - Seguridad extra: confirmación + doble confirmación opcional
    """

    def __init__(self):
        self.ai_engine = AIEngine()
        self.github = GitHubHandler()

        # Columnas “canon”
        self.base_cols = [
            "idx",
            "fecha_registro",
            "fecha_registro_dt",
            "tipo",
            "categoria_item",
            "equipo",
            "marca",
            "modelo",
            "serie",
            "cantidad",
            "estado",
            "origen",
            "destino",
            "guia",
            "reporte",
        ]

        # Estado UI
        st.session_state.setdefault("cln_df", pd.DataFrame())
        st.session_state.setdefault("cln_results", pd.DataFrame())
        st.session_state.setdefault("cln_selected_idx", set())
        st.session_state.setdefault("cln_last_query", "")
        st.session_state.setdefault("cln_mode", "AUTO")
        st.session_state.setdefault("cln_last_order", None)
        st.session_state.setdefault("cln_strict_confirm", False)

    # =========================================================
    # UI
    # =========================================================
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
                    if st.button("🔄 Refrescar", key="cln_btn_refresh_after_send", use_container_width=True):
                        st.session_state.cln_last_order = None
                        st.rerun()
                with c2:
                    st.caption("Si el robot aún no corrió, verás el historial igual. Refresca después de que el robot procese.")
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

        # ✅ Sanear “hist” antes de DataFrame (evita columnas 0,1,2… por listas raras)
        df = self._safe_hist_to_df(hist)
        df = self._normalize(df)
        st.session_state.cln_df = df

        with st.container(border=True):
            st.info(
                "💡 Ejemplos:\n"
                "- **elimina la serie 12345**\n"
                "- **borra marca LG**\n"
                "- **quita destino Puyo**\n"
                "- **elimina origen bodega**\n"
                "- **elimina tipo n/a**\n"
                "- **modo VACIOS**: elimina filas fantasma\n"
                "- **fecha: 2026-02-12** o **desde 2026-02-10 hasta 2026-02-12**"
            )

            q = st.text_input(
                "¿Qué deseas eliminar?",
                placeholder="Ej: elimina serie 12345 / borra marca LG / tipo: n/a / fecha: 2026-02-12 ...",
                key="cln_txt_query",
            ).strip()

            c1, c2, c3, c4, c5 = st.columns([1.2, 1.2, 1.8, 1.3, 1.8], vertical_alignment="center")
            with c1:
                if st.button("🔎 Buscar", key="cln_btn_search", type="secondary", use_container_width=True):
                    if q:
                        self._run_search(q)
                    else:
                        st.warning("Escribe una instrucción primero.")
            with c2:
                if st.button("🧹 Limpiar", key="cln_btn_clear", use_container_width=True):
                    self._reset()
                    st.rerun()
            with c3:
                st.session_state.cln_mode = st.selectbox(
                    "Modo",
                    options=["AUTO", "SERIE", "MARCA", "EQUIPO", "DESTINO", "ORIGEN", "TIPO", "ESTADO", "FECHA", "RANGO_FECHA", "TEXTO", "VACIOS"],
                    index=0,
                    key="cln_sel_mode",
                    help="AUTO detecta el campo. Los otros fuerzan dónde buscar.",
                )
            with c4:
                st.session_state.cln_strict_confirm = st.toggle(
                    "Doble confirmación",
                    value=bool(st.session_state.cln_strict_confirm),
                    help="Activa confirmación adicional (más seguro si vas a borrar mucho).",
                    key="cln_tgl_strict_confirm",
                )
            with c5:
                st.caption("🛡️ No se borra nada hasta que confirmes y envíes la orden.")

        if not st.session_state.cln_results.empty:
            self._render_results()

    # =========================================================
    # Search pipeline
    # =========================================================
    def _run_search(self, q: str):
        df = st.session_state.cln_df
        mode = st.session_state.cln_mode

        # Pista IA (opcional)
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

        # ✅ Si el modo está forzado, usa ese
        if mode != "AUTO":
            return mode.lower(), self._extract_value(ql)

        # ✅ fecha / rango fecha por texto
        if re.search(r"\b(desde|hasta|fecha)\b", ql):
            # modo automático de fecha
            if "desde" in ql or "hasta" in ql:
                return "rango_fecha", ql
            return "fecha", ql

        # ✅ serie/serial
        m = re.search(r"(serie|serial)\s*[:#-]?\s*([a-z0-9\-_/]+)", ql)
        if m:
            return "serie", m.group(2).strip()

        # ✅ soporta: marca/equipo/destino/origen/tipo/estado/guia
        for k in ["marca", "equipo", "destino", "origen", "tipo", "estado", "guia"]:
            m = re.search(rf"({k})\s*[:#-]?\s*([a-z0-9\-_/]+)", ql)
            if m:
                return k, m.group(2).strip()

        # ✅ hint IA
        for k in ["serie", "marca", "equipo", "destino", "origen", "tipo", "estado", "guia"]:
            v = ai_hint.get(k) or ai_hint.get(k.upper())
            if isinstance(v, str) and v.strip():
                return k, v.strip().lower()

        return "texto", self._extract_value(ql)

    def _extract_value(self, ql: str):
        stop = {
            "elimina", "eliminar", "borra", "borrar", "quita", "quitar", "suprime", "suprimir",
            "de", "la", "lo", "los", "las", "del", "al", "por", "para", "todo", "toda"
        }
        tokens = [t for t in re.split(r"\s+", ql) if t and t not in stop]
        return " ".join(tokens).strip() if tokens else ql

    def _parse_fecha_simple(self, text: str):
        # Acepta yyyy-mm-dd o yyyy/mm/dd
        m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", text)
        if not m:
            return None
        try:
            return pd.to_datetime(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", errors="coerce")
        except Exception:
            return None

    def _parse_rango_fechas(self, text: str):
        # "desde 2026-02-10 hasta 2026-02-12"
        fechas = re.findall(r"(\d{4}[-/]\d{2}[-/]\d{2})", text)
        if not fechas:
            return (None, None)
        if len(fechas) == 1:
            f = pd.to_datetime(fechas[0].replace("/", "-"), errors="coerce")
            return (f, f)
        f1 = pd.to_datetime(fechas[0].replace("/", "-"), errors="coerce")
        f2 = pd.to_datetime(fechas[1].replace("/", "-"), errors="coerce")
        return (f1, f2)

    def _search(self, df: pd.DataFrame, field: str, value: str):
        field = (field or "").strip().lower()
        value = (value or "").strip().lower()

        if df is None or df.empty:
            return pd.DataFrame()

        # ✅ modo VACIOS: filas fantasma
        if field == "vacios":
            check_cols = [c for c in ["tipo","categoria_item","equipo","marca","modelo","serie","estado","origen","destino","guia","reporte"] if c in df.columns]
            if not check_cols:
                return pd.DataFrame()

            tmp = df[check_cols].astype(str).apply(lambda col: col.str.strip().str.lower())
            na_mask = tmp.isin(["n/a", "na", "", "none", "nan"])

            ratio = na_mask.sum(axis=1) / max(1, len(check_cols))
            out = df[ratio >= 0.8].copy()
            return out.sort_values("fecha_registro_dt", ascending=False).head(1200)

        # ✅ fecha exacta
        if field == "fecha":
            f = self._parse_fecha_simple(value)
            if f is None or pd.isna(f):
                return pd.DataFrame()
            # por día completo
            start = f.normalize()
            end = start + pd.Timedelta(days=1)
            out = df[(df["fecha_registro_dt"] >= start) & (df["fecha_registro_dt"] < end)].copy()
            return out.sort_values("fecha_registro_dt", ascending=False).head(1200)

        # ✅ rango fecha
        if field == "rango_fecha":
            f1, f2 = self._parse_rango_fechas(value)
            if f1 is None or pd.isna(f1):
                return pd.DataFrame()
            if f2 is None or pd.isna(f2):
                f2 = f1
            start = min(f1, f2).normalize()
            end = max(f1, f2).normalize() + pd.Timedelta(days=1)
            out = df[(df["fecha_registro_dt"] >= start) & (df["fecha_registro_dt"] < end)].copy()
            return out.sort_values("fecha_registro_dt", ascending=False).head(1200)

        if not value:
            return pd.DataFrame()

        # ✅ búsqueda por campo directo
        if field in df.columns and field != "texto":
            s = df[field].astype(str).str.lower().str.strip()

            # exactitud por campos críticos
            if field in ["serie", "guia"]:
                mask = (s == value) | s.str.contains(re.escape(value), na=False)
            elif field in ["tipo", "estado"]:
                # tipo/estado: exacto OR contiene (para "n/a", "obsoleto", "bueno")
                mask = (s == value) | s.str.contains(re.escape(value), na=False)
            else:
                mask = s.str.contains(re.escape(value), na=False)

            out = df[mask].copy()
            return out.sort_values("fecha_registro_dt", ascending=False).head(1200)

        # ✅ búsqueda texto (multi-col)
        search_cols = [c for c in ["serie", "marca", "equipo", "modelo", "origen", "destino", "guia", "reporte", "tipo", "estado"] if c in df.columns]
        if not search_cols:
            search_cols = df.columns.tolist()

        mask = pd.Series(False, index=df.index)
        for c in search_cols:
            try:
                mask = mask | df[c].astype(str).str.lower().str.contains(re.escape(value), na=False)
            except Exception:
                pass

        out = df[mask].copy()
        return out.sort_values("fecha_registro_dt", ascending=False).head(1200)

    # =========================================================
    # Results UI
    # =========================================================
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

            view = dfres[cols_pref].copy()
            view.insert(0, "ELIMINAR", False)

            edited = st.data_editor(
                view,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                height=520,
                key="cln_editor_results",
            )

            selected_idx = set(edited.loc[edited["ELIMINAR"] == True, "idx"].astype(int).tolist())
            st.session_state.cln_selected_idx = selected_idx

        # acciones rápidas
        with st.container(border=True):
            total = len(dfres)
            nsel = len(st.session_state.cln_selected_idx)

            k1, k2, k3 = st.columns([1.2, 1.2, 2.6], vertical_alignment="center")
            k1.metric("Encontrados", total)
            k2.metric("Seleccionados", nsel)
            k3.caption("Se enviará una orden al robot con IDX reales del historico.json.")

            b1, b2, b3 = st.columns([1.2, 1.2, 1.6], vertical_alignment="center")
            with b1:
                if st.button("✅ Seleccionar TODO", key="cln_btn_sel_all", use_container_width=True):
                    st.session_state.cln_selected_idx = set(dfres["idx"].astype(int).tolist())
                    st.rerun()
            with b2:
                if st.button("🔁 Invertir selección", key="cln_btn_sel_inv", use_container_width=True):
                    all_idx = set(dfres["idx"].astype(int).tolist())
                    st.session_state.cln_selected_idx = all_idx - set(st.session_state.cln_selected_idx)
                    st.rerun()
            with b3:
                if st.button("🧽 Limpiar selección", key="cln_btn_sel_clear", use_container_width=True):
                    st.session_state.cln_selected_idx = set()
                    st.rerun()

            if total >= 50:
                st.warning("⚠️ Muchos resultados (≥ 50). Mejor filtra más específico (serie/guía/fecha).")

            # preview
            with st.expander("👁️ Preview de lo que se va a borrar", expanded=False):
                sub = st.session_state.cln_df[st.session_state.cln_df["idx"].isin(list(st.session_state.cln_selected_idx))].copy()
                sub_cols = [c for c in ["idx","fecha_registro","tipo","equipo","marca","modelo","serie","estado","origen","destino","guia"] if c in sub.columns]
                st.dataframe(sub[sub_cols].head(200), use_container_width=True, hide_index=True)

            confirm = st.checkbox("✅ Confirmo que deseo eliminar los registros seleccionados", key="cln_chk_confirm", value=False)

            # confirmación estricta
            confirm2 = True
            if st.session_state.cln_strict_confirm:
                confirm2 = st.text_input(
                    "Escribe EXACTAMENTE: BORRAR",
                    key="cln_txt_confirm2",
                    placeholder="BORRAR",
                ).strip().upper() == "BORRAR"

            disabled = (nsel == 0) or (not confirm) or (not confirm2)
            if st.button("🔥 ENVIAR ORDEN DE BORRADO", key="cln_btn_send_delete", type="primary", use_container_width=True, disabled=disabled):
                self._send_delete_order()

    def _send_delete_order(self):
        dfall = st.session_state.cln_df
        selected_idx = sorted(list(st.session_state.cln_selected_idx))

        if not selected_idx:
            st.warning("Selecciona al menos 1 registro.")
            return

        sub = dfall[dfall["idx"].isin(selected_idx)].copy()

        firmas = []
        for _, r in sub.iterrows():
            firmas.append({
                "idx": int(r.get("idx")),
                "serie": str(r.get("serie", "N/A")).strip(),
                "guia": str(r.get("guia", "N/A")).strip(),
                "fecha_registro": str(r.get("fecha_registro", "N/A")).strip(),
                "equipo": str(r.get("equipo", "N/A")).strip(),
                "marca": str(r.get("marca", "N/A")).strip(),
                "modelo": str(r.get("modelo", "N/A")).strip(),
                "origen": str(r.get("origen", "N/A")).strip(),
                "destino": str(r.get("destino", "N/A")).strip(),
                "tipo": str(r.get("tipo", "N/A")).strip(),
                "estado": str(r.get("estado", "N/A")).strip(),
            })

        orden = {
            # Nuevo
            "action": "delete",
            "source": "historico.json",
            "instruction": st.session_state.cln_last_query,
            "count": len(firmas),
            "indices": [int(x) for x in selected_idx],
            "matches": firmas,

            # compat robot viejo
            "accion": "borrar_por_indices",
            "idx_list": [int(x) for x in selected_idx],
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

    # =========================================================
    # Utils / Normalización
    # =========================================================
    def _safe_hist_to_df(self, hist):
        """
        ✅ Convierte 'hist' a DataFrame sin contaminarse con listas raras.
        - Si llega dict -> ok
        - Si llega list/tuple -> ignora (o intenta mapear si quieres)
        """
        filas = []
        for x in hist:
            if isinstance(x, dict):
                filas.append(x)
            elif isinstance(x, (list, tuple)):
                # si te llega basura como lista, la ignoramos para evitar columnas 0,1,2...
                # (si quieres mapearla, aquí sería el lugar)
                continue
            else:
                continue
        return pd.DataFrame(filas)

    def _normalize(self, df: pd.DataFrame):
        df = df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]

        # idx real por posición
        if "idx" not in df.columns:
            df.insert(0, "idx", range(len(df)))

        # asegurar columnas
        for c in [
            "fecha_registro", "tipo", "categoria_item", "equipo", "marca", "modelo", "serie",
            "cantidad", "estado", "origen", "destino", "guia", "reporte"
        ]:
            if c not in df.columns:
                df[c] = ""

        # fecha dt
        df["fecha_registro_dt"] = pd.to_datetime(df["fecha_registro"], errors="coerce")
        df["fecha_registro"] = df["fecha_registro_dt"].dt.strftime("%Y-%m-%d %H:%M")
        df["fecha_registro"] = df["fecha_registro"].fillna("N/A")

        # cantidad
        try:
            df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(1).astype(int)
        except Exception:
            df["cantidad"] = 1

        # limpieza anti nan / none
        text_cols = ["tipo", "categoria_item", "equipo", "marca", "modelo", "serie", "estado", "origen", "destino", "guia", "reporte"]
        for c in text_cols:
            df[c] = df[c].astype(str)
            df[c] = df[c].replace({"nan": "", "None": "", "NONE": "", "NaN": "", "NAN": ""})
            df[c] = df[c].fillna("").str.strip()
            df.loc[df[c] == "", c] = "N/A"

        # recorta a columnas canon + extras permitidos
        keep = [c for c in self.base_cols if c in df.columns]
        df = df[keep].copy()

        return df

    def _pretty_row(self, r: pd.Series):
        return (
            f"serie={str(r.get('serie', 'N/A'))} | "
            f"equipo={str(r.get('equipo', 'N/A'))} | "
            f"marca={str(r.get('marca', 'N/A'))} | "
            f"destino={str(r.get('destino', 'N/A'))} | "
            f"fecha={str(r.get('fecha_registro', 'N/A'))}"
        )

    def _reset(self, keep_order: bool = False):
        st.session_state.cln_results = pd.DataFrame()
        st.session_state.cln_selected_idx = set()
        st.session_state.cln_last_query = ""
        if not keep_order:
            st.session_state.cln_last_order = None
