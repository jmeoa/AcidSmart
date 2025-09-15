import streamlit as st
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Business Case: Dosificación Inteligente de Ácido", layout="wide")

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def fmt_money(x):
    return f"${x:,.0f}"

def compute_case(
    T_Mt, G_pct, R0_pct, A0_kgpt,
    P_Cu, P_Acid, Rmax_pct, Amin_kgpt,
    gammas, alphas, thetas_R, thetas_A, switches
):
    """
    Calcula resultados agregados, secuenciales e incrementales por componente.
    switches: dict {'C1':0/1,'C2':0/1,'C3':0/1,'C4':0/1} en orden secuencial.
    """
    # Conversión tonelaje a t/a
    T = T_Mt * 1_000_000.0
    G = G_pct / 100.0

    # Masa Cu en alimentación
    Cu_in_tpy = T * G

    # Secuencia de recuperación
    R = [R0_pct]
    order = ["C1", "C2", "C3", "C4"]
    for i, c in enumerate(order, start=1):
        s = switches[c]
        theta = thetas_R[c]
        gamma = gammas[c]
        R_next = R[i-1] * (1.0 + s * theta * gamma)
        R.append(R_next)
    R_raw_final = R[-1]
    R_final = min(R_raw_final, Rmax_pct)

    # Secuencia de ácido
    A = [A0_kgpt]
    for i, c in enumerate(order, start=1):
        s = switches[c]
        theta = thetas_A[c]
        alpha = alphas[c]
        A_next = A[i-1] * (1.0 - s * theta * alpha)
        A.append(A_next)
    A_raw_final = A[-1]
    A_final = max(A_raw_final, Amin_kgpt)

    # Incrementos (puntos % de recuperación)
    dR_total_pts = R_final - R0_pct

    # Ahorro de ácido (kg/t)
    dA_total_kgpt = A0_kgpt - A_final

    # Producción adicional de Cu (t/a)
    dCu_tpy = Cu_in_tpy * (dR_total_pts / 100.0)

    # Ahorro ácido anual (t/a)
    acid_saved_tpy = T * (dA_total_kgpt / 1000.0)

    # Beneficios anuales
    B_Cu = dCu_tpy * P_Cu
    B_Acid = acid_saved_tpy * P_Acid
    B_total = B_Cu + B_Acid

    # Aportes marginales por componente (secuencial)
    # Recuperación marginal por paso
    dR_pts_by = []
    for k in range(1, 5):
        dR_k = R[k] - R[k-1]
        dR_pts_by.append(dR_k)
    # Ajustar último tramo si topa Rmax
    # Recalcular R con tope aplicado en el último paso si corresponde:
    if R_raw_final > Rmax_pct:
        # Sobreescritura del último delta para que el total calce con R_final
        overshoot = R_raw_final - Rmax_pct
        dR_pts_by[-1] = max(dR_pts_by[-1] - overshoot, 0.0)

    # Ácido marginal por paso (positivo = ahorro)
    dA_by = []
    for k in range(1, 5):
        dA_k = A[k-1] - A[k]
        dA_by.append(dA_k)
    # Ajustar último tramo si pisó Amin
    if A_raw_final < Amin_kgpt:
        undershoot = Amin_kgpt - A_raw_final
        dA_by[-1] = max(dA_by[-1] - undershoot, 0.0)

    # Beneficio marginal por componente
    B_by = []
    for k, c in enumerate(order):
        if switches[c] == 0:
            B_by.append(0.0)
            continue
        dCu_k = Cu_in_tpy * (dR_pts_by[k] / 100.0)
        acid_saved_k_tpy = T * (dA_by[k] / 1000.0)
        B_k = dCu_k * P_Cu + acid_saved_k_tpy * P_Acid
        B_by.append(B_k)

    results = {
        "R_final_pct": R_final,
        "A_final_kgpt": A_final,
        "dR_total_pts": dR_total_pts,
        "dA_total_kgpt": dA_total_kgpt,
        "dCu_tpy": dCu_tpy,
        "acid_saved_tpy": acid_saved_tpy,
        "B_Cu": B_Cu,
        "B_Acid": B_Acid,
        "B_total": B_total,
        "dR_pts_by": dR_pts_by,
        "dA_by": dA_by,
        "B_by": B_by,
    }
    return results

def waterfall_benefit(benefits, labels, title, palette):
    """Construye un Waterfall Plotly de aportes incrementales."""
    measure = ["relative"] * len(benefits) + ["total"]
    x = labels + ["Total"]
    y = benefits + [sum(benefits)]
    # Colores por componente y total
    base_colors = [palette[i % len(palette)] for i in range(len(benefits))]
    total_color = "#0B5563"  # un azul profundo para el total
    colors = base_colors + [total_color]

    fig = go.Figure(go.Waterfall(
        name="Beneficio",
        orientation="v",
        measure=measure,
        x=x,
        y=y,
        connector={"line": {"width": 1}},
        decreasing={"marker": {"color": "#DC5214"}},   # naranja para negativos (no debería haber)
        increasing={"marker": {"color": "#328BA1"}},   # azul para positivos
        totals={"marker": {"color": "#DEA942"}}        # dorado para total
    ))
    fig.update_layout(
        title=title,
        showlegend=False,
        yaxis_title="USD/año",
        margin=dict(l=10, r=10, t=60, b=10)
    )
    return fig

# ---------------------------------------------------------
# Sidebar: Inputs
# ---------------------------------------------------------
st.sidebar.header("Parámetros de operación")
T_Mt = st.sidebar.slider("Toneladas tratadas (Mt/a)", 5.0, 20.0, 10.0, 0.5)
G_pct = st.sidebar.slider("Ley de Cu total (%)", 0.30, 1.00, 0.50, 0.01)
R0_pct = st.sidebar.slider("Recuperación base R0 (%)", 50.0, 70.0, 60.0, 0.5)
A0_kgpt = st.sidebar.slider("Consumo ácido base A0 (kg/t)", 25.0, 50.0, 35.0, 0.5)

st.sidebar.header("Precios")
P_Cu = st.sidebar.slider("Precio Cu (US$/t)", 7000, 11000, 9000, 50)
P_Acid = st.sidebar.slider("Precio ácido (US$/t H2SO4)", 80, 150, 120, 5)

st.sidebar.header("Límites técnicos")
Rmax_pct = st.sidebar.slider("Recuperación máx. Rmax (%)", 65.0, 80.0, 75.0, 0.5)
Amin_kgpt = st.sidebar.slider("Ácido mín. Amin (kg/t)", 15.0, 25.0, 20.0, 0.5)

st.sidebar.header("Activación de componentes")
C1 = st.sidebar.checkbox("C1 – Soft Sensor P80", True)
C2 = st.sidebar.checkbox("C2 – Clusterización UGMs", True)
C3 = st.sidebar.checkbox("C3 – Mineral Tracker", True)
C4 = st.sidebar.checkbox("C4 – Polinomio + Control", True)

st.sidebar.header("Efectos (benchmark, relativos)")
st.sidebar.caption("γ = mejora relativa de recuperación | α = reducción relativa de ácido")
gamma1 = st.sidebar.number_input("γ1 C1", 0.0, 0.05, 0.005, 0.001, format="%.3f")
gamma2 = st.sidebar.number_input("γ2 C2", 0.0, 0.05, 0.015, 0.001, format="%.3f")
gamma3 = st.sidebar.number_input("γ3 C3", 0.0, 0.05, 0.010, 0.001, format="%.3f")
gamma4 = st.sidebar.number_input("γ4 C4", 0.0, 0.05, 0.020, 0.001, format="%.3f")

alpha1 = st.sidebar.number_input("α1 C1", 0.0, 0.30, 0.020, 0.005, format="%.3f")
alpha2 = st.sidebar.number_input("α2 C2", 0.0, 0.30, 0.040, 0.005, format="%.3f")
alpha3 = st.sidebar.number_input("α3 C3", 0.0, 0.30, 0.030, 0.005, format="%.3f")
alpha4 = st.sidebar.number_input("α4 C4", 0.0, 0.30, 0.100, 0.005, format="%.3f")

st.sidebar.header("Rendimientos decrecientes (θ)")
thetaR1 = st.sidebar.number_input("θR1 C1", 0.0, 1.0, 1.00, 0.05)
thetaR2 = st.sidebar.number_input("θR2 C2", 0.0, 1.0, 0.80, 0.05)
thetaR3 = st.sidebar.number_input("θR3 C3", 0.0, 1.0, 0.70, 0.05)
thetaR4 = st.sidebar.number_input("θR4 C4", 0.0, 1.0, 0.60, 0.05)

thetaA1 = st.sidebar.number_input("θA1 C1", 0.0, 1.0, 1.00, 0.05)
thetaA2 = st.sidebar.number_input("θA2 C2", 0.0, 1.0, 0.85, 0.05)
thetaA3 = st.sidebar.number_input("θA3 C3", 0.0, 1.0, 0.80, 0.05)
thetaA4 = st.sidebar.number_input("θA4 C4", 0.0, 1.0, 0.70, 0.05)

# Paleta corporativa
PALETTE = ["#328BA1", "#DEA942", "#DC5214"]

# ---------------------------------------------------------
# Cálculos
# ---------------------------------------------------------
gammas = {"C1": gamma1, "C2": gamma2, "C3": gamma3, "C4": gamma4}
alphas = {"C1": alpha1, "C2": alpha2, "C3": alpha3, "C4": alpha4}
thetas_R = {"C1": thetaR1, "C2": thetaR2, "C3": thetaR3, "C4": thetaR4}
thetas_A = {"C1": thetaA1, "C2": thetaA2, "C3": thetaA3, "C4": thetaA4}
switches = {"C1": int(C1), "C2": int(C2), "C3": int(C3), "C4": int(C4)}

res = compute_case(
    T_Mt, G_pct, R0_pct, A0_kgpt,
    P_Cu, P_Acid, Rmax_pct, Amin_kgpt,
    gammas, alphas, thetas_R, thetas_A, switches
)

# ---------------------------------------------------------
# Layout principal
# ---------------------------------------------------------
st.title("Business Case – Dosificación Inteligente de Ácido en Curado")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Recuperación final (%)", f"{res['R_final_pct']:.2f}")
col2.metric("Δ Recup (pts %)", f"{res['dR_total_pts']:.2f}")
col3.metric("Ácido final (kg/t)", f"{res['A_final_kgpt']:.2f}")
col4.metric("Ahorro ácido (kg/t)", f"{res['dA_total_kgpt']:.2f}")

col5, col6, col7 = st.columns(3)
col5.metric("Δ Cu (t/a)", f"{res['dCu_tpy']:,.0f}")
col6.metric("Ahorro ácido (t/a)", f"{res['acid_saved_tpy']:,.0f}")
col7.metric("Beneficio anual", fmt_money(res["B_total"]))

st.divider()

# ---------------------------------------------------------
# Waterfall: Aporte incremental por componente
# ---------------------------------------------------------
labels = ["C1 SoftSensor", "C2 UGMs", "C3 Tracker", "C4 Polinomio"]
benefits = res["B_by"]  # USD/año por componente (marginal)
fig = waterfall_benefit(benefits, labels, "Waterfall – Aporte incremental por componente (USD/año)", PALETTE)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# Tabla de aportes marginales
# ---------------------------------------------------------
st.subheader("Aportes marginales por componente")
rows = []
order = ["C1", "C2", "C3", "C4"]
names = {"C1":"C1 – Soft Sensor P80", "C2":"C2 – Clusterización UGMs", "C3":"C3 – Mineral Tracker", "C4":"C4 – Polinomio + Control"}
for i, c in enumerate(order):
    rows.append({
        "Componente": names[c],
        "Δ Recuperación (pts %)": round(res["dR_pts_by"][i], 3),
        "Ahorro ácido (kg/t)": round(res["dA_by"][i], 3),
        "Beneficio (USD/año)": fmt_money(res["B_by"][i]),
    })
st.dataframe(rows, use_container_width=True)
