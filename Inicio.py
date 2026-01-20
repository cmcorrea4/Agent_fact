import streamlit as st
import os
from pathlib import Path
import anthropic
import base64
import pandas as pd
from datetime import datetime

# Configuración
PDF_FOLDER = "facturas"

# Prompt especializado para extracción de IVA
PROMPT_EXTRACCION_IVA = """Analiza esta factura y extrae ÚNICAMENTE las bases imponibles del IVA de manera global.

Debes extraer la información en este formato exacto:

Tarifa                          Base Imponible     Impuesto Calculado      Total con Impuesto 
IVA 19%                     $X,XXX.XX               $X,XXX.XX                      $X,XXX.XX
Excluidos (0%)     $X,XXX.XX             $X,XXX.XX                      $X,XXX.XX
TOTAL                        $X,XXX.XX             $X,XXX.XX                      $X,XXX.XX

IMPORTANTE:
- Busca las bases consolidadas/totales del IVA, no detalles línea por línea
- Si hay IVA 5%, inclúyelo también
- Usa el formato de moneda con separadores de miles y dos decimales
- Si no encuentras alguna tarifa, omítela
- Presenta SOLO la tabla, sin explicaciones adicionales"""

def pdf_to_base64(pdf_path):
    """Convierte PDF a base64"""
    with open(pdf_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def extract_iva_from_pdf(pdf_path, api_key):
    """Extrae bases de IVA de una factura usando Claude"""
    client = anthropic.Anthropic(api_key=api_key)
    
    pdf_data = pdf_to_base64(pdf_path)
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": PROMPT_EXTRACCION_IVA
                    }
                ],
            }
        ],
    )
    
    return message.content[0].text

def process_all_invoices(folder_path, api_key):
    """Procesa todas las facturas en la carpeta"""
    results = {}
    pdf_files = list(Path(folder_path).glob("*.pdf"))
    
    if not pdf_files:
        return None
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, pdf_path in enumerate(pdf_files):
        status_text.text(f"Procesando: {pdf_path.name} ({idx + 1}/{len(pdf_files)})")
        
        try:
            result = extract_iva_from_pdf(str(pdf_path), api_key)
            results[pdf_path.name] = {
                'status': 'success',
                'data': result,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            results[pdf_path.name] = {
                'status': 'error',
                'data': f"Error: {str(e)}",
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        progress_bar.progress((idx + 1) / len(pdf_files))
    
    status_text.empty()
    progress_bar.empty()
    
    return results

def create_summary_table(results):
    """Crea tabla resumen para exportar"""
    summary = []
    for filename, result in results.items():
        summary.append({
            'Factura': filename,
            'Estado': result['status'],
            'Fecha Procesamiento': result['timestamp'],
            'Resultado': result['data']
        })
    return pd.DataFrame(summary)

# Interfaz Streamlit
st.set_page_config(page_title="Extractor de IVA", page_icon="📊", layout="wide")

st.title("📊 Extractor de Bases de IVA de Facturas")
st.markdown("**Procesamiento automático con Claude API**")

# Sidebar con configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Campo para ingresar API Key
    st.subheader("🔑 Anthropic API Key")
    
    # Intentar cargar desde variable de entorno primero
    default_key = os.getenv("ANTHROPIC_API_KEY", "")
    
    api_key_input = st.text_input(
        "Ingresa tu API Key:",
        value=default_key,
        type="password",
        help="Obtén tu API Key en: https://console.anthropic.com/settings/keys"
    )
    
    # Guardar en session state
    if api_key_input:
        st.session_state['api_key'] = api_key_input
        st.success("✅ API Key configurada")
    else:
        st.warning("⚠️ Ingresa tu API Key para continuar")
        st.session_state['api_key'] = None
    
    # Link para obtener API Key
    st.markdown("[📖 Cómo obtener tu API Key](https://console.anthropic.com/settings/keys)")
    
    st.divider()
    
    # Carpeta de facturas
    st.write(f"📁 Carpeta: `{PDF_FOLDER}`")
    os.makedirs(PDF_FOLDER, exist_ok=True)
    
    pdf_files = list(Path(PDF_FOLDER).glob("*.pdf"))
    st.metric("Facturas encontradas", len(pdf_files))
    
    if pdf_files:
        with st.expander("Ver archivos"):
            for pdf in pdf_files:
                st.write(f"• {pdf.name}")
    
    st.divider()
    
    # Información adicional
    with st.expander("ℹ️ Información"):
        st.markdown("""
        **Modelo usado:** Claude Sonnet 4
        
        **Formato esperado:**
        - PDFs de facturas colombianas
        - Con IVA 19%, 5% o Excluidos
        
        **Costos aproximados:**
        - ~$0.003 por factura
        - Procesamiento rápido
        """)

# Verificar si hay API Key
has_api_key = st.session_state.get('api_key') is not None and st.session_state.get('api_key') != ""

# Área principal
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🚀 Procesamiento Masivo")
    
    if not has_api_key:
        st.info("👈 Ingresa tu API Key en el panel lateral para continuar")
    
    if st.button("Procesar todas las facturas", type="primary", disabled=not has_api_key):
        if not pdf_files:
            st.error("❌ No hay facturas en la carpeta")
        else:
            with st.spinner("Procesando facturas..."):
                try:
                    results = process_all_invoices(PDF_FOLDER, st.session_state['api_key'])
                    
                    st.success(f"✅ Procesamiento completado: {len(results)} facturas")
                    
                    # Guardar en session state
                    st.session_state['results'] = results
                    st.session_state['processed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    st.error(f"❌ Error en el procesamiento: {str(e)}")
                    if "invalid x-api-key" in str(e).lower() or "authentication" in str(e).lower():
                        st.error("🔑 API Key inválida. Verifica tu clave en el panel lateral.")

with col2:
    st.subheader("📤 Exportar")
    
    if 'results' in st.session_state:
        results = st.session_state['results']
        
        # Crear archivo de texto combinado
        combined_text = f"EXTRACCIÓN DE BASES DE IVA\nFecha: {st.session_state['processed_at']}\n\n"
        combined_text += "="*80 + "\n\n"
        
        for filename, result in results.items():
            combined_text += f"FACTURA: {filename}\n"
            combined_text += f"Estado: {result['status']}\n"
            combined_text += "-"*80 + "\n"
            combined_text += result['data'] + "\n"
            combined_text += "="*80 + "\n\n"
        
        st.download_button(
            "📄 Descargar TXT",
            combined_text,
            file_name=f"bases_iva_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )
        
        # Crear Excel
        df_summary = create_summary_table(results)
        
        # Convertir a Excel
        from io import BytesIO
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_summary.to_excel(writer, index=False, sheet_name='Resumen')
        
        st.download_button(
            "📊 Descargar Excel",
            buffer.getvalue(),
            file_name=f"bases_iva_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# Mostrar resultados
if 'results' in st.session_state:
    st.divider()
    st.subheader("📋 Resultados")
    
    results = st.session_state['results']
    
    # Estadísticas rápidas
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    
    success_count = sum(1 for r in results.values() if r['status'] == 'success')
    error_count = len(results) - success_count
    
    with col_stat1:
        st.metric("Total procesadas", len(results))
    with col_stat2:
        st.metric("Exitosas", success_count, delta=None, delta_color="off")
    with col_stat3:
        st.metric("Errores", error_count, delta=None, delta_color="off")
    
    st.divider()
    
    # Pestañas para cada factura
    tabs = st.tabs([f"📄 {name[:30]}..." if len(name) > 30 else f"📄 {name}" 
                    for name in results.keys()])
    
    for tab, (filename, result) in zip(tabs, results.items()):
        with tab:
            col_a, col_b = st.columns([3, 1])
            
            with col_a:
                st.text(filename)
            
            with col_b:
                if result['status'] == 'success':
                    st.success("✅ Éxito")
                else:
                    st.error("❌ Error")
            
            st.code(result['data'], language=None)
            st.caption(f"Procesado: {result['timestamp']}")

# Procesamiento individual
st.divider()
st.subheader("📎 Procesamiento Individual")

if not has_api_key:
    st.info("👈 Ingresa tu API Key en el panel lateral para usar esta función")

uploaded_file = st.file_uploader("Cargar una factura específica", type="pdf", disabled=not has_api_key)

if uploaded_file and has_api_key:
    if st.button("Procesar factura cargada"):
        # Guardar temporalmente
        temp_path = Path(PDF_FOLDER) / uploaded_file.name
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        with st.spinner("Extrayendo bases de IVA..."):
            try:
                result = extract_iva_from_pdf(str(temp_path), st.session_state['api_key'])
                st.success("✅ Extracción completada")
                st.code(result, language=None)
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                if "invalid x-api-key" in str(e).lower() or "authentication" in str(e).lower():
                    st.error("🔑 API Key inválida. Verifica tu clave en el panel lateral.")

# Footer
st.divider()
st.caption("💡 Asegúrate de tener las facturas en formato PDF en la carpeta 'facturas'")
st.caption("🔒 Tu API Key se almacena solo en la sesión actual y no se guarda en el servidor")
