import streamlit as st
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="SmartAcid Curado – Business Case", layout="wide")

# ---------------------------------------------------------
# Utils
# ---------------------------------------------------------
ORDER = ["C1", "C2", "C3", "C4"]
NAMES = {
    "C1": "C1 – Soft Sensor P80",
    "C2": "C2 – Clusterización UGMs",
    "C3": "C3 – Mineral Tracker",
    "C4": "C4 – Polinomio + Control",
}
PALETTE = ["#328BA1", "#DEA942", "#DC5214", "#328BA1"]  # para barras si quieres extender

def fmt_money(x):
    return f"${x:,.0f}"

def waterfall_benefit(benefits, labels, title):
    measure = ["relative"] * len(benefits) + ["total"]
    x = labels + ["Total"]
    y = benefits + [sum(benefits)]
    fig = go.Figure(go.Waterfall(
        name="Beneficio",
        orientation="v",
        measure=measure,
        x=x,
        y=y,
        connector={"line": {"width": 1}},
        decreasing={"marker": {"color": "#DC5214"}},  # naranja para negativos (no esperamos)
        increasing={"marker": {"color": "#328BA1"}},  # azul para positivos
        totals={"marker": {"color": "#DEA942"}}       # dorado para total
    ))
    fig.update_layout(
        title=title,
        showlegend=False,
        yaxis_title="USD/año",
        margin=dict(l=10, r=10, t=60, b=10)
    )
    return fig

# ---------------------------------------------------------
# Reglas de recorte (cuando se superan límites técnicos)
# ---------------------------------------------------------
def allocate_sequential(deltas, limit_excess):
    """
    deltas: lista de aportes absolutos por componente (>=0) en orden C1..C4
    limit_excess: exceso a recortar (>=0)
    Retorna lista con aportes acreditados luego del recorte secuencial.
    """
    credited = []
    remaining_excess = max(limit_excess, 0.0)
    for d in deltas:
        if remaining_excess <= 0:
            credited.append(d)
        else:
            take = max(d - remaining_excess, 0.0)
            credited.append(take)
            remaining_excess = max(remaining_excess - d, 0.0)
    return credited

def allocate_proportional(deltas, limit_excess):
    """
    Reparte el recorte proporcionalmente a los propios deltas.
    """
    S = sum(deltas)
    if S <= 0 or limit_excess <= 0:
        return deltas[:]
    factor = max(1.0 - limit_excess / S, 0.0)
    return [max(d * factor, 0.0) for d in deltas]

def allocate_weighted(deltas, weights, limit_excess):
    """
    Reparte el recorte proporcional a weights*deltas.
    weights: lista de pesos >=0 (no es necesario que sumen 1, se normalizan por construcción).
    credited_i = d_i - excess * (w_i * d_i) / sum_j(w_j * d_j)
    """
    wd = [w * d for w, d in zip(weights, deltas)]
    S = sum(wd)
    if S <= 0 or limit_excess <= 0:
        return deltas[:]
    credited = []
    for d, wd_i in zip(deltas, wd):
        cut_i = limit_excess * (wd_i / S)
        credited.append(max(d - cut_i, 0.0))
    return credited

# ---------------------------------------------------------
# Sidebar: Inputs (todos parten en 0 según tu requerimiento)
# ---------------------------------------------------------
st.sidebar.header("Parámetros de operación")
T_Mt  = st.sidebar.slider("Toneladas tratadas (Mt/a)", 0.0, 20.0, 10.0, 0.1)
G_pct = st.sidebar.slider("Ley de Cu total (%)", 0.00, 1.00, 0.50, 0.01)
R0_pct = st.sidebar.slider("Recuperación base R0 (%)", 0.0, 100.0, 60.0, 0.5)
A0_kgpt = st.sidebar.slider("Consumo ácido base A0 (kg/t)", 0.0, 100.0, 35.0, 0.5)

st.sidebar.header("Precios")
P_Cu   = st.sidebar.slider("Precio Cu (US$/t)", 0, 11000, 9000, 50)
P_Acid = st.sidebar.slider("Precio ácido (US$/t H2SO4)", 0, 150, 120, 5)

st.sidebar.header("Límites técnicos")
Rmax_pct  = st.sidebar.slider("Recuperación máx. Rmax (%)", 0.0, 100.0, 75.0, 0.5)
Amin_kgpt = st.sidebar.slider("Ácido mín. Amin (kg/t)", 0.0, 100.0, 20.0, 0.5)

st.sidebar.caption(
    "Rmax: techo técnico de recuperación. Amin: piso técnico de ácido.\n"
    "Si Rmax < R0 no habrá mejora posible; si Amin > A0 no habrá ahorro posible."
)

st.sidebar.header("Activación de componentes")
C1 = st.sidebar.checkbox(NAMES["C1"], True)
C2 = st.sidebar.checkbox(NAMES["C2"], True)
C3 = st.sidebar.checkbox(NAMES["C3"], True)
C4 = st.sidebar.checkbox(NAMES["C4"], True)
switches = {"C1": int(C1), "C2": int(C2), "C3": int(C3), "C4": int(C4)}

st.sidebar.header("Aportes absolutos por componente")
st.sidebar.caption("ΔR en puntos porcentuales (+pts %). ΔA en kg/t ahorrados.")
colR1, colR2 = st.sidebar.columns(2)
# Defaults mapeados desde el benchmark anterior
dR_C1 = colR1.number_input("ΔR C1 (pts %)", 0.0, 20.0, 0.5, 0.1)
dR_C2 = colR1.number_input("ΔR C2 (pts %)", 0.0, 20.0, 1.2, 0.1)
dR_C3 = colR1.number_input("ΔR C3 (pts %)", 0.0, 20.0, 0.7, 0.1)
dR_C4 = colR1.number_input("ΔR C4 (pts %)", 0.0, 20.0, 3.0, 0.1)

dA_C1 = colR2.number_input("ΔA C1 (kg/t)", 0.0, 50.0, 0.7, 0.1)
dA_C2 = colR2.number_input("ΔA C2 (kg/t)", 0.0, 50.0, 1.4, 0.1)
dA_C3 = colR2.number_input("ΔA C3 (kg/t)", 0.0, 50.0, 1.1, 0.1)
dA_C4 = colR2.number_input("ΔA C4 (kg/t)", 0.0, 50.0, 3.3, 0.1)

st.sidebar.header("Regla de recorte ante límites técnicos")
rule = st.sidebar.selectbox("Selecciona regla", ["Secuencial", "Proporcional", "Ponderada"])

weights = [1.0, 1.0, 1.0, 1.0]
if rule == "Ponderada":
    st.sidebar.caption("Pesos relativos por componente (arbitrarios, se normalizan por construcción).")
    w1 = st.sidebar.slider("Peso C1", 0.0, 5.0, 1.0, 0.1)
    w2 = st.sidebar.slider("Peso C2", 0.0, 5.0, 1.0, 0.1)
    w3 = st.sidebar.slider("Peso C3", 0.0, 5.0, 1.0, 0.1)
    w4 = st.sidebar.slider("Peso C4", 0.0, 5.0, 1.0, 0.1)
    weights = [w1, w2, w3, w4]

# ---------------------------------------------------------
# Validaciones UI
# ---------------------------------------------------------
if Rmax_pct < R0_pct:
    st.warning("⚠️ Rmax es menor que R0. No hay espacio para mejorar recuperación.")
if Amin_kgpt > A0_kgpt:
    st.warning("⚠️ Amin es mayor que A0. No hay espacio para ahorrar ácido.")
if T_Mt == 0 or G_pct == 0:
    st.info("ℹ️ Con T=0 o Ley=0, el beneficio por cobre será 0 (no hay producción).")
if P_Cu == 0 and P_Acid == 0:
    st.info("ℹ️ Con precios en 0, el beneficio económico será 0 aunque existan mejoras.")

# ---------------------------------------------------------
# Cálculos principales (modelo aditivo con topes)
# ---------------------------------------------------------
# Toneladas y cobre en alimentación
T = T_Mt * 1_000_000.0
Cu_in_tpy = T * (G_pct / 100.0)

# Deltas por componente (aportes absolutos) y switches
dR_list = [dR_C1, dR_C2, dR_C3, dR_C4]
dA_list = [dA_C1, dA_C2, dA_C3, dA_C4]
active_mask = [switches[c] == 1 for c in ORDER]

# Aplica switches (componentes apagados = 0 aporte)
dR_active = [d if m else 0.0 for d, m in zip(dR_list, active_mask)]
dA_active = [d if m else 0.0 for d, m in zip(dA_list, active_mask)]

# Recuperación: suma y tope
R_raw = R0_pct + sum(dR_active)
excess_R = max(R_raw - Rmax_pct, 0.0)
if rule == "Secuencial":
    dR_accredited = allocate_sequential(dR_active, excess_R)
elif rule == "Proporcional":
    dR_accredited = allocate_proportional(dR_active, excess_R)
else:
    dR_accredited = allocate_weighted(dR_active, weights, excess_R)
R_final = R0_pct + sum(dR_accredited)

# Ácido: ahorro y piso
A_raw = A0_kgpt - sum(dA_active)
excess_A = max((Amin_kgpt - A_raw), 0.0)  # cuánto ahorro hay que recortar para no bajar de Amin
if rule == "Secuencial":
    dA_accredited = allocate_sequential(dA_active, excess_A)
elif rule == "Proporcional":
    dA_accredited = allocate_proportional(dA_active, excess_A)
else:
    dA_accredited = allocate_weighted(dA_active, weights, excess_A)
A_final = A0_kgpt - sum(dA_accredited)

# KPIs operacionales
dR_total_pts = R_final - R0_pct                # puntos %
dA_total_kgpt = A0_kgpt - A_final              # kg/t
dCu_tpy = Cu_in_tpy * (dR_total_pts / 100.0)   # t/a
acid_saved_tpy = T * (dA_total_kgpt / 1000.0)  # t/a

# Beneficios
B_Cu = dCu_tpy * P_Cu
B_Acid = acid_saved_tpy * P_Acid
B_total = B_Cu + B_Acid

# Beneficio por componente (acreditado)
B_by = []
for i, c in enumerate(ORDER):
    dR_i = dR_accredited[i]
    dA_i = dA_accredited[i]
    dCu_i = Cu_in_tpy * (dR_i / 100.0)
    acid_saved_i_tpy = T * (dA_i / 1000.0)
    B_i = dCu_i * P_Cu + acid_saved_i_tpy * P_Acid
    B_by.append(B_i)

# ---------------------------------------------------------
# UI principal
# ---------------------------------------------------------
st.title("SmartAcid – Caso de Negocio")

with st.expander("ℹ️ Cómo funciona este modelo"):
    st.markdown(
        """
**Aportes absolutos por componente**  
- Ingresas **ΔR** en puntos porcentuales y **ΔA** en kg/t que cada componente podría aportar *si operara solo*.  
- Los componentes se suman de forma **aditiva**.  
- Si la suma supera los **límites técnicos** (Rmax o Amin), se aplica un **recorte** según la regla elegida:  
  - **Secuencial**: se acredita primero C1, luego C2, etc., hasta llenar el límite.  
  - **Proporcional**: se reduce a todos por igual en proporción a su aporte.  
  - **Ponderada**: se reduce en proporción a `peso × aporte` (permitiendo priorizar componentes).  
- El **Waterfall** muestra el beneficio **acreditado** por cada componente (después de recortes).
        """
    )

k1, k2, k3, k4 = st.columns(4)
k1.metric("Recuperación final (%)", f"{R_final:.2f}")
k2.metric("Δ Recup (pts %)", f"{dR_total_pts:.2f}")
k3.metric("Ácido final (kg/t)", f"{A_final:.2f}")
k4.metric("Ahorro ácido (kg/t)", f"{dA_total_kgpt:.2f}")

k5, k6, k7 = st.columns(3)
k5.metric("Δ Cu (t/a)", f"{dCu_tpy:,.0f}")
k6.metric("Ácido ahorrado (t/a)", f"{acid_saved_tpy:,.0f}")
k7.metric("Beneficio anual", fmt_money(B_total))

st.divider()

labels = [NAMES[c] for c in ORDER]
fig = waterfall_benefit(B_by, labels, "Waterfall – Aporte incremental acreditado (USD/año)")
st.plotly_chart(fig, use_container_width=True)

# Tabla de aportes acreditados
st.subheader("Aportes acreditados por componente (post-límites)")
rows = []
for i, c in enumerate(ORDER):
    rows.append({
        "Componente": NAMES[c],
        "Δ Recuperación acreditada (pts %)": round(dR_accredited[i], 3),
        "Ahorro ácido acreditado (kg/t)": round(dA_accredited[i], 3),
        "Beneficio (USD/año)": fmt_money(B_by[i]),
    })
st.dataframe(rows, use_container_width=True)
