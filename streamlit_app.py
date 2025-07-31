import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO

st.set_page_config(page_title="App Meteorológico INMET", layout="wide")

st.title("\U0001F324️ Organização de Dados Meteorológicos - INMET")
st.markdown("""
**Algoritmo desenvolvido em caráter experimental para organização dos dados meteorológicos das estações meteorológicas do INMET.**  
Desenvolvido por **Cláudio Ricardo da Silva - UFU**
""")

# Upload do arquivo
arquivo = st.file_uploader("\U0001F4C2 Faça o upload do arquivo CSV da estação INMET", type="csv")

if arquivo:
    df = pd.read_csv(arquivo, sep=';', encoding='utf-8')

    # Converter Hora UTC para string no formato HH:MM
    df["Hora_Local"] = df["Hora (UTC)"].apply(lambda x: f"{int(x):04d}")
    df["Hora_Local"] = df["Hora_Local"].str.slice(0, 2) + ":" + df["Hora_Local"].str.slice(2, 4)

    df["Data_Hora_UTC"] = pd.to_datetime(df["Data"] + " " + df["Hora_Local"], dayfirst=True)
    df["Data_Hora_Local"] = df["Data_Hora_UTC"] - pd.Timedelta(hours=3)
    df["Data_Hora_Local_Str"] = df["Data_Hora_Local"].dt.strftime("%Y-%m-%d %H:%M")
    df["Hora_Local"] = df["Data_Hora_Local"].dt.strftime("%H:%M")
    df["Data_Local"] = (df["Data_Hora_Local"] - pd.Timedelta(hours=1)).dt.date

    # Corrigir colunas e converter valores
    df.rename(columns={"Dir. Vento (m/s)": "Dir. Vento (°)"}, inplace=True)
    df["Radiacao (KJ/m²)"] = pd.to_numeric(df["Radiacao (KJ/m²)"].astype(str).str.replace(",", "."), errors="coerce")
    df["Radiacao (MJ/m².d)"] = df["Radiacao (KJ/m²)"] / 1000
    df.drop(columns=["Radiacao (KJ/m²)"] , inplace=True)

    colunas_para_corrigir = ['Temp. Max. (C)', 'Temp. Min. (C)', 'Umi. Max. (%)', 'Umi. Min. (%)',
                             'Vel. Vento (m/s)', 'Raj. Vento (m/s)', 'Dir. Vento (°)', 'Chuva (mm)']

    for col in colunas_para_corrigir:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "."), errors="coerce")

    # Selecionar colunas úteis
    colunas_uteis = [
        "Data_Local", "Hora_Local", "Data_Hora_Local_Str", "Temp. Max. (C)", "Temp. Min. (C)", "Umi. Max. (%)", "Umi. Min. (%)",
        "Vel. Vento (m/s)", "Dir. Vento (°)", "Raj. Vento (m/s)", "Radiacao (MJ/m².d)", "Chuva (mm)"
    ]
    df = df[colunas_uteis]

    # Cálculo dos dados diários e ETo
    variaveis_media = ['Umi. Max. (%)', 'Umi. Min. (%)', 'Vel. Vento (m/s)', 'Dir. Vento (°)', 'Raj. Vento (m/s)']
    variaveis_soma = ['Radiacao (MJ/m².d)', 'Chuva (mm)']
    medias_diarias = df.groupby("Data_Local")[variaveis_media].mean().round(2)
    somas_diarias = df.groupby("Data_Local")[variaveis_soma].sum().round(2)
    temp_max_abs = df.groupby("Data_Local")["Temp. Max. (C)"].max()
    temp_min_abs = df.groupby("Data_Local")["Temp. Min. (C)"].min()
    dados_diarios = pd.concat([temp_max_abs, temp_min_abs, medias_diarias, somas_diarias], axis=1).reset_index()

    # Cálculo ETo (Penman-Monteith simplificado)
    G = 0
    gamma = 0.063
    dados_diarios["Tmedia (°C)"] = ((dados_diarios["Temp. Max. (C)"] + dados_diarios["Temp. Min. (C)"]) / 2).round(2)
    dados_diarios["URmedia (%)"] = ((dados_diarios["Umi. Max. (%)"] + dados_diarios["Umi. Min. (%)"]) / 2).round(2)

    def calcular_es(T):
        return 0.6108 * np.exp((17.27 * T) / (T + 237.3))

    dados_diarios["es (kPa)"] = calcular_es(dados_diarios["Tmedia (°C)"]).round(2)
    dados_diarios["ea (kPa)"] = (dados_diarios["es (kPa)"] * dados_diarios["URmedia (%)"] / 100).round(2)
    dados_diarios["Rn (MJ/m².d)"] = (0.5 * dados_diarios["Radiacao (MJ/m².d)"]).round(2)
    dados_diarios["Delta (kPa/°C)"] = (
        (4098 * dados_diarios["es (kPa)"]) / ((dados_diarios["Tmedia (°C)"] + 237.3) ** 2)
    ).round(2)
    dados_diarios["ETo (mm/dia)"] = (
        (0.408 * dados_diarios["Delta (kPa/°C)"] * (dados_diarios["Rn (MJ/m².d)"] - G)) +
        (gamma * (900 / (dados_diarios["Tmedia (°C)"] + 273)) *
         dados_diarios["Vel. Vento (m/s)"] *
         (dados_diarios["es (kPa)"] - dados_diarios["ea (kPa)"]))
    ) / (
        dados_diarios["Delta (kPa/°C)"] + gamma * (1 + 0.34 * dados_diarios["Vel. Vento (m/s)"])
    )
    dados_diarios["ETo (mm/dia)"] = dados_diarios["ETo (mm/dia)"].round(2)

    st.markdown("### \U0001F4E5 Exportar Dados")
    def to_excel_download(df):
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        return buffer

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("⬇️ Baixar Dados Horários (tratados)", to_excel_download(df), file_name="dados_horarios.xlsx")
    with col2:
        st.download_button("⬇️ Baixar Dados Diários (com ETo)", to_excel_download(dados_diarios), file_name="dados_diarios.xlsx")

    # Estatísticas
    st.subheader("\U0001F4CA Estatísticas Meteorológicas do Período")
    ultima_data = dados_diarios["Data_Local"].max()
    temp_media = dados_diarios["Tmedia (°C)"].mean().round(1)
    chuva_total = dados_diarios["Chuva (mm)"].sum().round(1)
    linha_maior_chuva = dados_diarios.loc[dados_diarios["Chuva (mm)"].idxmax()]
    linha_temp_max = df.loc[df["Temp. Max. (C)"].idxmax()]
    linha_temp_min = df.loc[df["Temp. Min. (C)"].idxmin()]
    linha_vento_max = df.loc[df["Vel. Vento (m/s)"].idxmax()]
    linha_ur_min = df.loc[df["Umi. Min. (%)"].idxmin()]

    st.markdown(f"📅 Última data registrada: `{ultima_data}`")
    st.markdown(f"🌡️ Temperatura média: `{temp_media} °C`")
    st.markdown(f"🌧️ Chuva total: `{chuva_total} mm`")
    st.markdown(f"🌧️ Maior chuva: `{linha_maior_chuva['Chuva (mm)']} mm` em `{linha_maior_chuva['Data_Local']}`")
    st.markdown(f"🔥 Temperatura máxima: `{linha_temp_max['Temp. Max. (C)']} °C` em `{linha_temp_max['Data_Local']}`")
    st.markdown(f"❄️ Temperatura mínima: `{linha_temp_min['Temp. Min. (C)']} °C` em `{linha_temp_min['Data_Local']}`")
    st.markdown(f"💨 Maior velocidade do vento: `{linha_vento_max['Vel. Vento (m/s)']} m/s` em `{linha_vento_max['Data_Local']}`")
    st.markdown(f"💧 Umidade relativa mínima: `{linha_ur_min['Umi. Min. (%)']}%` em `{linha_ur_min['Data_Local']}`")

    # Checagem de dados completos
    faltantes = df["Temp. Max. (C)"].isna().sum()
    if faltantes == 0:
        st.success("✅ Dados completos: Sim")
    else:
        st.warning(f"⚠️ Dados incompletos: {faltantes} registros ausentes em 'Temp. Max. (C)'")

    # Última chuva e dias sem chuva
    dias_sem_chuva = df[df["Chuva (mm)"] > 0]["Data_Local"].max()
    if pd.notna(dias_sem_chuva):
        dias_desde = (pd.to_datetime(ultima_data) - pd.to_datetime(dias_sem_chuva)).days
        st.markdown(f"🗓️ Última chuva em: `{dias_sem_chuva}` — {dias_desde} dias sem chuva")

    # Visualizar amostra dos dados diários
    st.markdown("### 🔎 Visualização de amostra dos dados diários")
    st.dataframe(dados_diarios.head())

    # Gráficos mensais
    st.subheader("\U0001F4C8 Gráficos Mensais")
    dados_diarios["Data_Local"] = pd.to_datetime(dados_diarios["Data_Local"])
    dados_diarios["Mes"] = dados_diarios["Data_Local"].dt.month
    meses_dict = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}
    dados_diarios["Mes_nome"] = dados_diarios["Mes"].map(meses_dict)
    resumo_mensal = dados_diarios.groupby("Mes_nome").agg({
        "Chuva (mm)": "sum",
        "ETo (mm/dia)": "sum",
        "Tmedia (°C)": "mean",
        "Temp. Max. (C)": "mean",
        "Temp. Min. (C)": "mean",
        "Vel. Vento (m/s)": "mean",
        "Radiacao (MJ/m².d)": "mean",
        "URmedia (%)": "mean"
    }).round(2).reindex(meses_dict.values())

    col1, col2 = st.columns(2)
    with col1:
        fig, ax = plt.subplots()
        x = np.arange(len(resumo_mensal))
        ax.bar(x - 0.2, resumo_mensal["Chuva (mm)"], width=0.4, label="Chuva (mm)", color='blue')
        ax.bar(x + 0.2, resumo_mensal["ETo (mm/dia)"], width=0.4, label="ETo (mm)", color='red')
        ax.set_xticks(x)
        ax.set_xticklabels(resumo_mensal.index, rotation=45)
        ax.set_title("Chuva e ETo")
        ax.legend()
        st.pyplot(fig)

    with col2:
        fig, ax = plt.subplots()
        ax.plot(resumo_mensal.index, resumo_mensal["Tmedia (°C)"], label="T Média")
        ax.plot(resumo_mensal.index, resumo_mensal["Temp. Max. (C)"], label="T Max")
        ax.plot(resumo_mensal.index, resumo_mensal["Temp. Min. (C)"], label="T Min")
        ax.set_title("Temperaturas")
        ax.legend()
        st.pyplot(fig)

    col3, col4 = st.columns(2)
    with col3:
        fig, ax = plt.subplots()
        ax.plot(resumo_mensal.index, resumo_mensal["Vel. Vento (m/s)"], label="Vento")
        ax.set_title("Velocidade do Vento")
        ax.legend()
        st.pyplot(fig)

    with col4:
        fig, ax = plt.subplots()
        ax.plot(resumo_mensal.index, resumo_mensal["Radiacao (MJ/m².d)"], label="Radiação")
        ax.set_title("Radiação Solar")
        ax.legend()
        st.pyplot(fig)

    fig, ax = plt.subplots()
    ax.plot(resumo_mensal.index, resumo_mensal["URmedia (%)"], label="UR Média")
    ax.set_title("Umidade Relativa")
    ax.legend()
    st.pyplot(fig)
