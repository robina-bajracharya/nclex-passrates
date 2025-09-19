import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go

# ========== CONFIG ==========
st.set_page_config(layout="wide")
FILE_PATH = "data/pass-rates.xlsx"
YEARS = list(range(2020, 2025))

# ========== SIDEBAR ==========
st.sidebar.title("Filter")
selected_year = st.sidebar.selectbox("Select Year", YEARS)

# ========== LOAD SHAPEFILE ==========
@st.cache_resource
def load_shapefile():
    counties = gpd.read_file("tn_counties/tl_2021_us_county/tl_2021_us_county.shp")
    return counties[counties["STATEFP"] == "47"]  # Tennessee only

tn_counties = load_shapefile()
tn_counties["NAME"] = tn_counties["NAME"].str.strip().str.title()

# ========== LOAD ALL YEARLY DATA ==========
@st.cache_data
def load_excel_data(file_path):
    all_data = []
    for year in YEARS:
        sheet_name = f"Heatmap-{year}"
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        df["Year"] = year
        all_data.append(df)
    return pd.concat(all_data, ignore_index=True)

df_all = load_excel_data(FILE_PATH)

# ========== FILTER BY YEAR ==========
df_year = df_all[df_all["Year"] == selected_year].copy()

df_year["Pass_perct_school"] = round((df_year["Pass"] / df_year["No."]) * 100, 2).fillna(0)

# ========== PROCESS YEAR DATA ==========
grouped = (
    df_year.groupby("County Name")
           .agg({
               "School": lambda x: ", ".join(x.dropna()),
               "Pass": "sum",
               "No.": "sum"
           })
           .reset_index()
)
grouped["Pass_perct_total"] = round((grouped["Pass"] / grouped["No."]) * 100, 2).fillna(0)
grouped["County"] = grouped["County Name"].str.split(',').str[0].str.strip()

school_info = (
    df_year.groupby("County Name")
           .apply(lambda x: [
               f"{row['School']}: {row['Pass_perct_school']}%"
               for _, row in x.iterrows() if pd.notna(row["School"])
           ])
           .to_dict()
)


grouped["Schools_detail"] = grouped["County Name"].map(school_info)

# ========== MERGE WITH SHAPEFILE ==========
merged = tn_counties.merge(grouped, left_on="NAME", right_on="County", how="left")

def build_hover(row):
    schools = "<br>".join(row["Schools_detail"]) if isinstance(row["Schools_detail"], list) else "No data"
    return (
        f"County: {row['NAME']}<br>"
        f"Total Pass %: {row['Pass_perct_total'] if pd.notna(row['Pass_perct_total']) else 'N/A'}<br>"
        f"Schools:<br>{schools}"
    )

# ========== TOOLTIP ==========
merged["hover_text"] = merged.apply(build_hover, axis=1)

# ========== PLOTLY MAP ==========
fig = go.Figure(go.Choropleth(
    geojson=merged.__geo_interface__,
    locations=merged.index,
    z=merged["Pass_perct_total"].fillna(0),
    text=merged["hover_text"],
    hoverinfo="text",
    colorscale="Greens",
    zmin=80,
    zmax=100,
    marker_line_color="black",
    marker_line_width=1.2,
    colorbar_title="Pass %",
))

fig.update_layout(
    margin={"r":0,"t":40,"l":0,"b":0},
    title=f"NCLEX Pass % by County - {selected_year}",
    geo=dict(
        fitbounds="locations",
        visible=True,
        scope="usa",
        projection=dict(type="albers usa")
    )
)

# ========== DISPLAY ==========
st.title("🧪 PN NCLEX Pass Rates in Tennessee (2020–2024)")
st.plotly_chart(fig, use_container_width=True)
