import geopandas as gpd

# gdf = gpd.read_file("distritos.shp")

# lima = gdf[(gdf["DEPARTAMEN"] == "LIMA") & (gdf["PROVINCIA"] == "LIMA")]

# lima.to_file("lima_districtsv2.geojson", driver="GeoJSON")

# print(gdf["DEPARTAMEN"].unique())
# print(gdf.head())
gdf2 = gpd.read_file("DISTRITO.gpkg")

# print(gdf2.head())

print(gdf2.columns)
