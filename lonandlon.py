import geopandas as gpd
import pandas as pd

# --- 1. Load GeoJSON ---
file_path = "lima_districtsv2.geojson"
gdf = gpd.read_file(file_path)

print("CRS before:", gdf.crs)

# --- 2. Ensure CRS is WGS84 (required for web maps & APIs) ---
if gdf.crs is None:
    print("No CRS found. Assuming EPSG:4326")
    gdf.set_crs(epsg=4326, inplace=True)

# Convert to WGS84 if needed
if gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)

print("CRS after:", gdf.crs)

# --- 3. Generate safe representative point ---
gdf["rep_point"] = gdf.geometry.representative_point()

# Extract lon / lat
gdf["lon"] = gdf["rep_point"].x
gdf["lat"] = gdf["rep_point"].y

# --- 4. Select district name column ---
print("Available columns:", gdf.columns)

# Adjust this if needed:
district_column = "DISTRITO" if "DISTRITO" in gdf.columns else gdf.columns[0]

result = gdf[[district_column, "lat", "lon"]].copy()
result.columns = ["district", "lat", "lon"]

# --- 5. Save to CSV ---
result.to_csv("lima_district_coordinates.csv", index=False)

print("Done. Sample:")
print(result.head())
