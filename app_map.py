import streamlit as st 
import geemap 
import folium 
import geemap.foliumap as geemap
import ee
import json
import pandas as pd
import plotly.express as px 

st.set_page_config(layout='wide')

##Inicialização do GEE
# ee.Initialize(project='ee-meusuario')
m = geemap.Map()

##Titulo do app 
st.title('APP - MapBiomas')
st.write("""
    Este aplicativo permite a visualização interativa da classificação de uso do solo no Brasil, utilizando dados da 
    Coleção 9 do projeto MapBiomas. Com uma série histórica de 1985 a 2023, o aplicativo oferece a possibilidade de 
    selecionar o ano desejado e visualizar o uso do solo remapeado em seis classes principais. 
    **Fonte dos dados**: [MapBiomas](https://mapbiomas.org)
""")

##Processamento das imagens 
mapbiomas_image= ee.Image('projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1')

# Códigos originais e classes remapeadas conforme a legenda fornecida
codes = [
    1, 3, 4, 5, 6, 49,          # Floresta e subcategorias
    10, 11, 12, 32, 29, 50,     # Vegetação Herbácea e Arbustiva e subcategorias
    14, 15, 18, 19, 39, 20, 40, 62, 41, 36, 46, 47, 35, 48, 9, 21,  # Agropecuária e subcategorias
    22, 23, 24, 30, 25,         # Área não Vegetada e subcategorias
    26, 33, 31,                 # Corpo D'água e subcategorias
    27                          # Não Observado
]

new_classes = [
    1, 1, 1, 1, 1, 1,           # Floresta e subcategorias
    2, 2, 2, 2, 2, 2,           # Vegetação Herbácea e Arbustiva e subcategorias
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, # Agropecuária e subcategorias
    4, 4, 4, 4, 4,              # Área não Vegetada e subcategorias
    5, 5, 5,                    # Corpo D'água e subcategorias
    6                           # Não Observado
]

# Dicionário para mapeamento de nomes das classes
class_names = {
    1: "Floresta",
    2: "Vegetação Herbácea e Arbustiva",
    3: "Agropecuária",
    4: "Área não Vegetada",
    5: "Corpo D'água",
    6: "Não Observado"
}

# Palette de cores para as classes remapeadas
palette = [
    "#1f8d49",  # 1. Floresta
    "#ad975a",  # 2. Vegetação Herbácea e Arbustiva
    "#FFFFB2",  # 3. Agropecuária
    "#d4271e",  # 4. Área não Vegetada
    "#0000FF",  # 5. Corpo D'água
    "#ffffff"   # 6. Não Observado
]

remapped_bands = []
for year in range(1985, 2024):
    original_band= f'classification_{year}'
    remapped_band = mapbiomas_image.select(original_band).remap(codes, new_classes).rename(original_band)
    remapped_bands.append(remapped_band)

remapped_image = ee.Image.cat(remapped_bands)

years = list(range(1985,2024))
selected_years = st.multiselect('Selecione o(s) anos(s)', years, default=[2023])

with st.expander('Defina a área de estudo (opcional)'):
    geometry_input = st.text_area(
        """Insira as coordenadas de área de estudo em formato GeoJSON."""
        """Selecione sua área de estudo usando as geometrias disponíveis no mapa abaixo, depois clique sobre a geometria desenhada e copie o resultado."""
    )	

###verificação da geometria ou não para prosseguir com o código 
geometry= None
if geometry_input:
    try:
        geometry = ee.Geometry(json.loads(geometry_input)['geometry'])
    except:
        st.error('Erro no Formato de Coordenadas. Verifique o GeoJson inserido')


# Se houver uma geometria, aplicar o recorte e centralizar o mapa na área de estudo
if geometry:
    # Exibir a área de estudo no mapa
    study_area = ee.FeatureCollection([ee.Feature(geometry)])
    m.centerObject(study_area, zoom=8)
    m.addLayer(study_area, {"color": "red"}, "Área de Estudo")

    # Recortar a imagem remapeada pela geometria da área de estudo
    remapped_image = remapped_image.clip(geometry)
    
# Adicionar as bandas remapeadas selecionadas ao mapa
for year in selected_years:
    selected_band = f"classification_{year}"
    m.addLayer(remapped_image.select(selected_band), {'palette': palette, 'min': 1, 'max': 6}, 
                                                            f"Classificação Remapeada {year}")

# Exibir o mapa no Streamlit
m.to_streamlit(height=600)

# Função para calcular a área por classe
if geometry:
    st.subheader("Estatísticas de Área por Classe")
    areas = []
    
    for year in selected_years:
        band = remapped_image.select(f"classification_{year}")
        for class_value in range(1, 7):  # Classes de 1 a 6
            class_area = band.eq(class_value).multiply(ee.Image.pixelArea()).reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=geometry,
                scale=30,
                maxPixels=1e9
            ).getInfo()
            area_km2 = class_area.get(f"classification_{year}", 0) / 1e6  # Convertendo para km²
            areas.append({"Ano": year, "Classe": class_value, "Nome da Classe": class_names[class_value], "Área (km²)": area_km2})
    
    # Convertendo os dados de área para um único DataFrame
    df = pd.DataFrame(areas) 
    
    # Layout de colunas
    col1, col2 = st.columns(2)    
    
    # Exibir DataFrame e gráfico lado a lado
    with col1:
        st.dataframe(df)    
        
     # Exibir gráfico apenas se houver mais de um ano selecionado
    if len(selected_years) > 1:
        with col2:
            # Criando o gráfico de área com Plotly
            fig = px.area(
                df,
                x="Ano",
                y="Área (km²)",
                color="Nome da Classe",
                title="Evolução da Área por Classe ao Longo do Tempo",
                color_discrete_sequence=palette
            )
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Nenhuma área de estudo definida. As estatísticas de área por classe não serão exibidas.")


    