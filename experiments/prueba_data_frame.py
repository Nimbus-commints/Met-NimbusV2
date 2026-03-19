import pandas as pd
import numpy as np

num_data_points_per_country = 20

# Generate random temperature data for each country
# Temperature range for France (10-20 degrees)
france_temperatures = np.random.uniform(10, 20, num_data_points_per_country)
# Temperature range for Germany (0-10 degrees)
germany_temperatures = np.random.uniform(0, 10, num_data_points_per_country)
# Temperature range for Italy (25-30 degrees)
italy_temperatures = np.random.uniform(25, 30, num_data_points_per_country)

# Create an array of country labels corresponding to the data points
countries = ["France", "Germany", "Italy"]
country_labels = np.repeat(countries, num_data_points_per_country)

# Generate time values
time_values = np.tile(np.arange(num_data_points_per_country), len(countries))

# Create a Pandas DataFrame
data = {
    "Country": country_labels,
    "Temperature": np.concatenate(
        [france_temperatures, germany_temperatures, italy_temperatures]
    ),
    "Time": time_values,
}

df = pd.DataFrame(data)

print(df)
