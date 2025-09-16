import streamlit as st
import pandas as pd
import csv
import os
from datetime import datetime

# Configuración de página compacta
st.set_page_config(
    page_title="Reporte de Productividad - OEE",
    page_icon="📊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Estilos CSS para diseño compacto
st.markdown("""
<style>
    .stApp {
        padding-top: 0rem !important;
        margin-top: -2rem !important;
    }
    [data-testid="stHeader"] {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        min-height: 0rem !important;
    }
    [data-testid="stToolbar"] {
        display: none !important;
    }
    .reportview-container .main .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 1rem !important;
    }
    h1 {
        margin-top: 0rem !important;
        padding-top: 0rem !important;
    }
    .compact-form {
      font-size: 0.55rem !important;
    }
     .compact-form .stNumberInput, .compact-form .stTextInput, .compact-form .stSelectbox {
      margin-bottom: 0.2rem;
     }
     .compact-table {
      font-size: 0.8rem;
     }
     .section-header {
      font-size: 0.5rem !important;
      margin-bottom: 0.5rem !important;
     }
     .metric-compact {
      font-size: 0.5rem;
      padding: 0.3rem;
     }
     div[data-testid="stHorizontalBlock"] {
      gap: 0.5rem;
     }
</style>
""", unsafe_allow_html=True)

# --- Funciones base ---
def create_initial_csv_files():
    registros_file = 'registros_produccion.csv'
    if not os.path.exists(registros_file):
        with open(registros_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            header = ['fecha', 'turno', 'supervisor', 'linea_produccion', 'tiempo_disponible_min',
                      'tiempo_programado_min', 'producto_terminado', 'produccion_real_unidades', 'produccion_defectuosa_unidades',
                      'tiempo_efectivo_min', 'tiempo_no_conformidad_min', 'tiempo_a_justificar_min']
            for i in range(1, 11):
                header.extend([f'paro_causal_{i}', f'paro_subcausal_{i}', f'tiempo_paro_min_{i}'])
            writer.writerow(header)

def cargar_productos():
    productos = {}
    lineas_disponibles = []
    
    if os.path.exists('productos.csv'):
        try:
            df_productos = pd.read_csv('productos.csv')
            for index, row in df_productos.iterrows():
                productos[row['codigo_producto']] = row.to_dict()
            
            lineas_disponibles = sorted(df_productos['linea_produccion'].dropna().unique().tolist())
            
        except Exception as e:
            st.error(f"Error al cargar productos: {e}")
    else:
        st.warning("El archivo 'productos.csv' no existe. Por favor, cree este archivo para continuar.")
    
    return productos, lineas_disponibles

causales_paros = {
    "Falla de equipo": ["Fallo mecanico", "Fallo electrico", "Falla de sensores", "Fuga de aceite/aire"],
    "Mantenimiento no programado": ["Ajustes de emergencia", "Cambio de repuestos criticos", "Inspecciones correctivas"],
    "Cambio de producto / setup": ["Ajuste de maquina", "Limpieza de linea", "Cambio de herramientas/moldes"],
    "Abastecimiento de materiales": ["Falta de materia prima", "Retraso de logistica interna", "Retraso de proveedor externo", "Material defectuoso recibido"],
    "Calidad del producto": ["Producto fuera de especificacion", "Reproceso en linea", "Bloqueo por inspeccion de calidad"],
    "Problemas de planeacion/programa": ["Orden cancelada", "Espera por programacion", "Secuencia incorrecta"],
    "Servicios auxiliares": ["Falta de energia electrica", "Corte de agua", "Falla de aire comprimido", "Fallo de vapor/gas"],
    "Mano de obra / personal": ["Falta de operador", "Capacitacion en maquina", "Relevo de turno retrasado"],
    "Retrabajo / reproceso": ["Ajuste de lote", "Correccion por error de empaque", "Correccion por error de etiquetado"],
    "Inicio / fin de produccion": ["Arranque de linea (puesta a punto)", "Parada por fin de orden de produccion", "Limpieza final"],
    "Perdida de velocidad": ["Materia Prima", "Equipos/Proceso", "Gestión/Personal"]
}

def initialize_session_state():
    if 'report_products' not in st.session_state:
        st.session_state.report_products = []
    if 'unplanned_stops' not in st.session_state:
        st.session_state.unplanned_stops = []
    if 'productos' not in st.session_state:
        st.session_state.productos, st.session_state.lineas_disponibles = cargar_productos()
    if 'selected_linea' not in st.session_state:
        st.session_state.selected_linea = None
    if 'filtered_products' not in st.session_state:
        st.session_state.filtered_products = {}
    if 'reset_form' not in st.session_state:
        st.session_state.reset_form = False
    if 'validation_error' not in st.session_state:
        st.session_state.validation_error = None
    if 'edited_products' not in st.session_state:
        st.session_state.edited_products = []
    if 'show_paro_error' not in st.session_state:
        st.session_state.show_paro_error = False
    if 'paro_error_message' not in st.session_state:
        st.session_state.paro_error_message = ""

def load_products_for_linea(linea):
    if not linea: return {}
    productos_filtrados = {}
    try:
        for codigo, datos in st.session_state.productos.items():
            if datos['linea_produccion'] == linea:
                productos_filtrados[codigo] = int(datos['estandar_produccion'])
    except Exception as e:
        st.error(f"Error al filtrar productos: {e}")
    return productos_filtrados

def add_product(producto, productos_filtrados):
    if not producto:
        st.warning("Seleccione un producto para agregar.")
        return
    if any(p['codigo'] == producto for p in st.session_state.report_products):
        st.info("Este producto ya ha sido agregado.")
        return
    estandar = productos_filtrados[producto]
    new_product = {'codigo': producto, 'estandar': estandar, 'produccion_real': 0, 'produccion_defectuosa': 0}
    
    st.session_state.report_products.append(new_product)
    st.session_state.edited_products = st.session_state.report_products.copy()

def remove_product(index):
    if 0 <= index < len(st.session_state.report_products):
        st.session_state.report_products.pop(index)
        st.session_state.edited_products.pop(index)

def calculate_times(tiempo_programado, report_products):
    if not tiempo_programado or tiempo_programado <= 0:
        return 0, 0, 0
    tiempo_efectivo = 0
    tiempo_no_conformidad = 0
    for p in report_products:
        estandar = p['estandar']
        if estandar > 0:
            tiempo_efectivo += (p['produccion_real'] / estandar) * 480
            tiempo_no_conformidad += (p['produccion_defectuosa'] / estandar) * 480
    
    tiempo_a_justificar = tiempo_programado - tiempo_efectivo - tiempo_no_conformidad
    
    tiempo_a_justificar = max(0, round(tiempo_a_justificar))
    
    return tiempo_efectivo, tiempo_no_conformidad, tiempo_a_justificar

def add_unplanned_stop(causal, subcausal, tiempo):
    if not all([causal, subcausal, tiempo]):
        st.warning("Debe completar todos los campos del paro.")
        return
    try:
        tiempo = int(tiempo)
        if tiempo <= 0: raise ValueError
    except ValueError:
        st.error("El tiempo debe ser un número positivo.")
        return
    
    total_paros_actual = sum(stop['tiempo'] for stop in st.session_state.unplanned_stops)
    tiempo_justificar_total = st.session_state.tiempo_a_justificar

    if (total_paros_actual + tiempo) > tiempo_justificar_total:
        st.session_state.show_paro_error = True
        st.session_state.paro_error_message = f"El tiempo de paro ({tiempo} min) excede el tiempo restante a justificar ({tiempo_justificar_total - total_paros_actual} min)."
        return

    st.session_state.unplanned_stops.append({
        'causal': causal, 
        'subcausal': subcausal, 
        'tiempo': tiempo
    })
    st.session_state.show_paro_error = False

def remove_unplanned_stop(index):
    if 0 <= index < len(st.session_state.unplanned_stops):
        st.session_state.unplanned_stops.pop(index)

def save_report(fecha, turno, supervisor, linea, tiempo_programado, tiempo_efectivo, tiempo_no_conformidad, tiempo_a_justificar):
    if not st.session_state.report_products:
        st.error("Debe agregar al menos un producto producido.")
        return False
    if not all([fecha, turno, linea]):
        st.error("Debe completar los campos de Fecha, Turno y Línea.")
        return False

    productos_terminados = [p['codigo'] for p in st.session_state.report_products]
    produccion_real_total = sum(p['produccion_real'] for p in st.session_state.report_products)
    produccion_defectuosa_total = sum(p['produccion_defectuosa'] for p in st.session_state.report_products)
    
    new_data = {
        'fecha': fecha,
        'turno': turno,
        'supervisor': supervisor,
        'linea_produccion': linea,
        'tiempo_disponible_min': 480,
        'tiempo_programado_min': tiempo_programado,
        'producto_terminado': ', '.join(productos_terminados),
        'produccion_real_unidades': produccion_real_total,
        'produccion_defectuosa_unidades': produccion_defectuosa_total,
        'tiempo_efectivo_min': int(round(tiempo_efectivo)),
        'tiempo_no_conformidad_min': int(round(tiempo_no_conformidad)),
        'tiempo_a_justificar_min': tiempo_a_justificar,
    }
    
    for i in range(10):
        if i < len(st.session_state.unplanned_stops):
            stop = st.session_state.unplanned_stops[i]
            new_data[f'paro_causal_{i+1}'] = stop['causal']
            new_data[f'paro_subcausal_{i+1}'] = stop['subcausal']
            new_data[f'tiempo_paro_min_{i+1}'] = stop['tiempo']
        else:
            new_data[f'paro_causal_{i+1}'] = ''
            new_data[f'paro_subcausal_{i+1}'] = ''
            new_data[f'tiempo_paro_min_{i+1}'] = ''
            
    try:
        file_path = 'registros_produccion.csv'
        all_reports = []
        header = new_data.keys()
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                if reader.fieldnames:
                    header = reader.fieldnames
                    for row in reader:
                        if not (row['fecha'] == fecha and row['turno'] == turno and row['linea_produccion'] == linea):
                            all_reports.append(row)

        all_reports.append(new_data)
        
        with open(file_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_reports)
            
        st.success("Reporte guardado exitosamente.")
        return True

    except Exception as e:
        st.error(f"Error al guardar el reporte: {e}")
        return False
        
def clear_fields():
    """
    Limpia el estado de la sesión para reiniciar el formulario.
    """
    st.session_state.report_products = []
    st.session_state.unplanned_stops = []
    st.session_state.selected_linea = None
    st.session_state.filtered_products = {}
    
    st.session_state.reset_form = True
    
    keys_to_delete = [
        'fecha_input',
        'turno_select',
        'supervisor_input',
        'linea_select',
        'tiempo_prog',
        'causal_select',
        'subcausal_select',
        'tiempo_paro_input',
        'productos_editor'
    ]

    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]


def show_history():
    st.subheader("Historial de Reportes")
    try:
        if os.path.exists('registros_produccion.csv'):
            df = pd.read_csv('registros_produccion.csv')
            
            cols = st.columns(5)
            lineas = ['Todas'] + sorted(df['linea_produccion'].dropna().unique().tolist())
            turnos = ['Todos'] + sorted(df['turno'].dropna().unique().tolist())
            supervisores = ['Todos'] + sorted(df['supervisor'].dropna().unique().tolist())
            
            df['fecha'] = pd.to_datetime(df['fecha'])
            df['mes'] = df['fecha'].dt.strftime('%Y-%m')
            meses = ['Todos'] + sorted(df['mes'].dropna().unique().tolist())
            
            with cols[0]:
                linea_filter = st.selectbox("Línea:", lineas, key="hist_linea")
            with cols[1]:
                turno_filter = st.selectbox("Turno:", turnos, key="hist_turno")
            with cols[2]:
                mes_filter = st.selectbox("Mes:", meses, key="hist_mes")
            with cols[3]:
                supervisor_filter = st.selectbox("Supervisor:", supervisores, key="hist_supervisor")
            with cols[4]:
                fecha_filter = st.text_input("Fecha:", "", key="hist_fecha")
            
            filtered_df = df.copy()
            if linea_filter != "Todas":
                filtered_df = filtered_df[filtered_df['linea_produccion'] == linea_filter]
            if turno_filter != "Todos":
                filtered_df = filtered_df[filtered_df['turno'] == turno_filter]
            if mes_filter != "Todos":
                filtered_df = filtered_df[filtered_df['mes'] == mes_filter]
            if supervisor_filter != "Todos":
                filtered_df = filtered_df[filtered_df['supervisor'] == supervisor_filter]
            if fecha_filter:
                filtered_df = filtered_df[filtered_df['fecha'].dt.strftime('%Y-%m-%d') == fecha_filter]
            
            st.dataframe(
                filtered_df[['linea_produccion', 'fecha', 'turno', 'supervisor', 'produccion_real_unidades']],
                use_container_width=True,
                height=200
            )
            
            st.subheader("Estadísticas")
            stat_cols = st.columns(3)
            with stat_cols[0]:
                st.metric("Total Reportes", len(filtered_df))
            with stat_cols[1]:
                st.metric("Producción Total", f"{filtered_df['produccion_real_unidades'].sum():,}")
            with stat_cols[2]:
                eficiencia = (filtered_df['produccion_real_unidades'].sum() / 
                               (filtered_df['tiempo_programado_min'].sum() / 60)) if filtered_df['tiempo_programado_min'].sum() > 0 else 0
                st.metric("Eficiencia", f"{eficiencia:.2f}u/h")
        else:
            st.info("No hay registros de producción disponibles.")
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")

# Callback function to handle data editor changes
def handle_editor_change():
    """
    Función que se ejecuta cuando el st.data_editor cambia.
    Realiza la validación y actualiza el estado de la sesión.
    """
    if 'productos_editor' in st.session_state:
        edited_df = st.session_state['productos_editor']['edited_rows']
        
        if edited_df:
            temp_products = st.session_state.report_products.copy()
            try:
                for index, changes in edited_df.items():
                    temp_products[index].update(changes)
                
                tiempo_programado = st.session_state.get('tiempo_prog', 0)
                temp_tiempo_efectivo, temp_tiempo_no_conformidad, temp_tiempo_a_justificar = calculate_times(tiempo_programado, temp_products)
                
                total_paros_actual = sum(stop['tiempo'] for stop in st.session_state.unplanned_stops)

                # Validación estricta: la suma debe ser exactamente igual al tiempo programado
                suma_tiempos = temp_tiempo_efectivo + temp_tiempo_no_conformidad + temp_tiempo_a_justificar
                
                if abs(suma_tiempos - tiempo_programado) > 1:  # Permitir pequeña diferencia por redondeo
                    st.session_state.validation_error = f"❌ La suma del tiempo efectivo ({temp_tiempo_efectivo:.0f} min), tiempo no conforme ({temp_tiempo_no_conformidad:.0f} min) y tiempo a justificar ({temp_tiempo_a_justificar:.0f} min) debe ser exactamente igual al tiempo programado ({tiempo_programado} min). Diferencia: {abs(suma_tiempos - tiempo_programado):.1f} min."
                elif total_paros_actual > temp_tiempo_a_justificar:
                    st.session_state.validation_error = f"❌ ¡Error de coherencia! La suma de paros ({total_paros_actual} min) excede el nuevo tiempo a justificar ({temp_tiempo_a_justificar:.0f} min)."
                else:
                    st.session_state.report_products = temp_products
                    st.session_state.edited_products = temp_products
                    st.session_state.validation_error = None

            except Exception as e:
                st.session_state.validation_error = f"Error al procesar la edición: {e}. Asegúrese de que todos los valores de producción sean números."

# --- Interfaz compacta ---
def main():
    create_initial_csv_files()
    initialize_session_state()
    
    st.title("📊Reporte de Efectividad - OEE")
    
    tab1, tab2 = st.tabs(["Registro", "Historial"])
    
    with tab1:
        st.markdown('<div class="compact-form">', unsafe_allow_html=True)
        
        if st.session_state.reset_form:
            fecha_default = datetime.now()
            turno_default = "1"
            supervisor_default = ""
            linea_default = ""
            tiempo_programado_default = 0
            
            st.session_state.reset_form = False
        else:
            fecha_default = st.session_state.get('fecha_input', datetime.now())
            turno_default = st.session_state.get('turno_select', "1")
            supervisor_default = st.session_state.get('supervisor_input', "")
            linea_default = st.session_state.get('linea_select', "")
            tiempo_programado_default = st.session_state.get('tiempo_prog', 0)
        
        st.markdown('<p class="section-header">Datos del Turno</p>', unsafe_allow_html=True)
        cols = st.columns(6)
        with cols[0]:
            fecha = st.date_input("Fecha:", value=fecha_default, key="fecha_input")
            fecha_str = fecha.strftime("%Y-%m-%d")
        with cols[1]:
            turno = st.selectbox("Turno:", ["1", "2", "3"], index=["1", "2", "3"].index(turno_default) if turno_default in ["1", "2", "3"] else 0, key="turno_select")
        with cols[2]:
            supervisor = st.text_input("Supervisor:", value=supervisor_default, key="supervisor_input")
        with cols[3]:
            linea = st.selectbox("Línea:", [""] + st.session_state.lineas_disponibles, 
                                 index=0 if linea_default == "" else ([""] + st.session_state.lineas_disponibles).index(linea_default) if linea_default in [""] + st.session_state.lineas_disponibles else 0, 
                                 key="linea_select")
            if linea != st.session_state.selected_linea:
                st.session_state.selected_linea = linea
                st.session_state.filtered_products = load_products_for_linea(linea)
        with cols[4]:
            tiempo_disponible = st.number_input("T. Disp (min):", min_value=0, max_value=1440, value=480, disabled=True, key="tiempo_disp")
        with cols[5]:
            tiempo_programado = st.number_input("T. Prog (min):", min_value=0, max_value=480, value=tiempo_programado_default, key="tiempo_prog")
        
        st.markdown('<p class="section-header">Productos Producidos</p>', unsafe_allow_html=True)
        prod_cols = st.columns([3, 1])
        with prod_cols[0]:
            producto_seleccionado = st.selectbox(
                "Seleccionar Producto:", 
                options=[""] + list(st.session_state.filtered_products.keys()),
                disabled=not linea,
                key="product_select"
            )
        with prod_cols[1]:
            st.write("")
            if st.button("+ Agregar Producto", disabled=not producto_seleccionado, key="add_product_btn"):
                add_product(producto_seleccionado, st.session_state.filtered_products)
        
        if st.session_state.report_products:
            current_df = pd.DataFrame(st.session_state.edited_products)
            st.data_editor(
                current_df,
                column_config={
                    "codigo": st.column_config.TextColumn("Producto", disabled=True, width="small"),
                    "estandar": st.column_config.NumberColumn("Estándar", disabled=True, width="small"),
                    "produccion_real": st.column_config.NumberColumn("Prod Real", min_value=0, width="small"),
                    "produccion_defectuosa": st.column_config.NumberColumn("Prod Def", min_value=0, width="small")
                },
                use_container_width=True,
                key="productos_editor",
                num_rows="fixed", 
                on_change=handle_editor_change,
                height=min(35 * (len(st.session_state.report_products) + 1), 200)
            )
            
            if st.button("Eliminar último producto", key="remove_last_product_btn"):
                if st.session_state.report_products:
                    st.session_state.report_products.pop()
                    st.session_state.edited_products.pop()
                    st.rerun()
        
        st.markdown('<p class="section-header">Resumen de Tiempos</p>', unsafe_allow_html=True)
        tiempo_efectivo, tiempo_no_conformidad, tiempo_a_justificar = calculate_times(tiempo_programado, st.session_state.report_products)
        st.session_state.tiempo_a_justificar = tiempo_a_justificar

        time_cols = st.columns(3)
        with time_cols[0]:
            st.metric("T. Efectivo", f"{tiempo_efectivo:.0f} min")
        with time_cols[1]:
            st.metric("T. No Conf", f"{tiempo_no_conformidad:.0f} min")
        with time_cols[2]:
            st.metric("T. Justificar", f"{tiempo_a_justificar} min")
        
        # Validación de coherencia de tiempos
        suma_tiempos = tiempo_efectivo + tiempo_no_conformidad + tiempo_a_justificar
        if abs(suma_tiempos - tiempo_programado) > 1:  # Permitir pequeña diferencia por redondeo
            st.error(f"❌ ¡Error de coherencia! La suma de tiempos ({suma_tiempos:.1f} min) no coincide con el tiempo programado ({tiempo_programado} min). Diferencia: {abs(suma_tiempos - tiempo_programado):.1f} min.")
        
        st.markdown('<p class="section-header">Paradas No Programadas</p>', unsafe_allow_html=True)
        stop_cols = st.columns([2, 2, 1, 1])
        with stop_cols[0]:
            causal = st.selectbox("Causal:", [""] + list(causales_paros.keys()), key="causal_select")
        with stop_cols[1]:
            subcausales = causales_paros.get(causal, []) if causal else []
            subcausal = st.selectbox("Subcausal:", [""] + subcausales, disabled=not causal, key="subcausal_select")
        with stop_cols[2]:
            total_paros_actual = sum(stop['tiempo'] for stop in st.session_state.unplanned_stops)
            max_value = max(0, tiempo_a_justificar - total_paros_actual)
            tiempo_paro = st.number_input(
                "Minutos:", 
                min_value=0, 
                max_value=max_value, 
                value=0, 
                key="tiempo_paro_input"
            )
        with stop_cols[3]:
            st.write("")
            if st.button("+ Agregar Paro", disabled=not (causal and subcausal and tiempo_paro > 0), key="add_paro_btn"):
                add_unplanned_stop(causal, subcausal, tiempo_paro)
                st.rerun()

        # Validación y visualización del error de coherencia
        total_paros_recheck = sum(stop['tiempo'] for stop in st.session_state.unplanned_stops)
        tiempo_a_justificar_recheck = st.session_state.tiempo_a_justificar

        if total_paros_recheck > tiempo_a_justificar_recheck:
            st.error(f"❌ ¡Error de coherencia! La suma de paros ({total_paros_recheck} min) excede el tiempo a justificar ({tiempo_a_justificar_recheck:.0f} min).")
        
        if st.session_state.unplanned_stops:
            paros_df = pd.DataFrame(st.session_state.unplanned_stops)
            
            for i, row in paros_df.iterrows():
                row_cols = st.columns([2, 2, 1, 1])
                row_cols[0].markdown(f"<span style='color: blue'>{row['causal']}</span>", unsafe_allow_html=True)
                row_cols[1].markdown(f"<span style='color: blue'>{row['subcausal']}</span>", unsafe_allow_html=True)
                row_cols[2].markdown(f"<span style='color: blue'>{row['tiempo']} min</span>", unsafe_allow_html=True)
                if row_cols[3].button("🗑️", key=f"delete_paro_{i}"):
                    remove_unplanned_stop(i)
                    st.rerun()
            
        total_paros = sum(stop['tiempo'] for stop in st.session_state.unplanned_stops)
        tiempo_faltante = tiempo_a_justificar - total_paros
        
        paro_cols = st.columns(2)
        with paro_cols[0]:
            st.metric("Total Paros", f"{total_paros:.0f} min")
        with paro_cols[1]:
            color = "off" if abs(tiempo_faltante) < 1 else ("normal" if tiempo_faltante > 0 else "inverse")
            st.metric("T. Faltante", f"{tiempo_faltante:.0f} min", delta_color=color)
        
        st.markdown('<hr style="margin-top:1rem; margin-bottom:1rem;">', unsafe_allow_html=True)
        st.markdown('<p class="section-header">Acciones</p>', unsafe_allow_html=True)

        report_exists_check = False
        if all([fecha_str, turno, linea]):
            try:
                if os.path.exists('registros_produccion.csv'):
                    with open('registros_produccion.csv', 'r', newline='', encoding='utf-8') as file:
                        reader = csv.DictReader(file)
                        for row in reader:
                            if row['fecha'] == fecha_str and row['turno'] == turno and row['linea_produccion'] == linea:
                                report_exists_check = True
                                break
            except Exception:
                pass
        
        if report_exists_check:
            st.warning("Advertencia: Ya existe un reporte para esta fecha, turno y línea. Guardar reemplazará el anterior.")

        action_cols = st.columns(3)
        
        with action_cols[0]:
            total_paros_actual = sum(stop['tiempo'] for stop in st.session_state.unplanned_stops)
            
            # Validación estricta para permitir guardar
            suma_tiempos_actual = tiempo_efectivo + tiempo_no_conformidad + tiempo_a_justificar
            tiempo_coherente = abs(suma_tiempos_actual - tiempo_programado) <= 1
            paros_coherentes = abs(tiempo_a_justificar - total_paros_actual) <= 1
            
            puede_guardar = (
                tiempo_coherente and
                paros_coherentes and
                len(st.session_state.report_products) > 0 and
                all([fecha_str, turno, supervisor, linea])
            )
            
            if st.button("💾 Guardar", disabled=not puede_guardar, type="primary", key="save_btn"):
                if save_report(fecha_str, turno, supervisor, linea, tiempo_programado, 
                               tiempo_efectivo, tiempo_no_conformidad, tiempo_a_justificar):
                    clear_fields()
                    st.rerun()
        
        with action_cols[1]:
            if st.button("🗑️ Limpiar", key="clear_btn"):
                clear_fields()
                st.rerun()
        
        with action_cols[2]:
            st.button("📋 Historial", key="history_btn")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        show_history()

if __name__ == "__main__":
    main()