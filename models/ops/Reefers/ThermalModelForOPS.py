import pandas as pd
import numpy as np
import random
from .cargo import Cargo


def getReeferConsumption(numReefers, meteo, arrival, departure):
    """
    Calculates the total power consumption for a fleet of reefer containers
    using an efficient, vectorized approach.
    """
    # --- Power Efficiency Setup ---
    # Restore the full data dictionary with both models
    data = {
        'temperature': [-29, -18, 2, 21],
        'powerConsumption R404A': [5300, 6100, 9100, 10700],
        'coolingCapacity R404A': [3809, 5860, 9962, 13771],
        'powerConsumption R134a': [4500, 6000, 10500, 12000],
        'coolingCapacity R134a': [3023, 5604, 11456, 13507]
    }
    df_powerEfficiency = pd.DataFrame(data)

    # --- Restore the original, generic averaging logic ---
    cooling_capacity_columns = df_powerEfficiency.filter(like='coolingCapacity').columns
    power_consumption_columns = df_powerEfficiency.filter(like='powerConsumption').columns

    # Calculate COP for each model found in the data
    for cooling_col, power_col in zip(cooling_capacity_columns, power_consumption_columns):
        cop_column_name = f"COP {cooling_col.split()[1]}"
        df_powerEfficiency[cop_column_name] = df_powerEfficiency[cooling_col] / df_powerEfficiency[power_col]

    # Average the performance across all models
    cop_columns = df_powerEfficiency.filter(like='COP').columns
    df_avgEfficiency = pd.DataFrame({
        'avg_powerConsumption': df_powerEfficiency.groupby('temperature')[power_consumption_columns].mean().mean(axis=1),
        'avg_COP': df_powerEfficiency.groupby('temperature')[cop_columns].mean().mean(axis=1)
    }).reset_index()


    # --- Avoid modifying the original 'meteo' DataFrame ---
    # Create a new DataFrame with 'Datetime' as the index instead of changing it in-place.
    meteo_indexed = meteo.set_index('Datetime')


    # --- Cargo and Container Definitions ---
    cargoTomatoesMatureGreen = Cargo(3, "Tomatoes", 4020, 10, 18.3, 2.0074 * 10**-4, 2.8350)
    cargoOnions = Cargo(4, "Onions", 3950, -0.6, 5, 3.668 * 10**-4, 2.538)
    cargoFreshPeaches = Cargo(5, "Fresh Peaches", 3910, -1.1, 2.2, 1.2996 * 10**-5, 3.6417)
    cargo_list = [cargoTomatoesMatureGreen, cargoOnions, cargoFreshPeaches]

    # --- Generate DataFrame of Container Properties ---
    def generate_containers_df(numContainers, cargo_list):
        container_data = []
        for i in range(numContainers):
            cargo = random.choice(cargo_list)
            setpoint_temp = (cargo.upperBound + cargo.lowerBound) / 2
            cop = np.interp(setpoint_temp, df_avgEfficiency['temperature'], df_avgEfficiency['avg_COP'])
            cooling_capacity = np.interp(setpoint_temp, df_avgEfficiency['temperature'], df_avgEfficiency['avg_powerConsumption']) * cop
            container_data.append({
                'id': i, 
                'surfaceArea': 74.97, 
                'heatTransCoef': 0.5,
                'cargo_specificHeat': cargo.specificHeat, 
                'cargo_resp_f': cargo.resp_f, 
                'cargo_resp_g': cargo.resp_g,
                'cargo_lowerBound': cargo.lowerBound, 
                'cargo_upperBound': cargo.upperBound,
                'mass': round(random.uniform(17000, 23000), 2), 
                'temp': setpoint_temp,
                'auxiliarPower': 0, 
                'boolHeating': random.choices([True, False], weights=[0.8, 0.2])[0],
                'cop': cop, 
                'coolingCapacity': cooling_capacity
            })
        return pd.DataFrame(container_data)

    # --- Main Execution ---
    random.seed(1)
    containers_df = generate_containers_df(numReefers, cargo_list)

    # --- Create Unified Timeline ---
    timeline_index = pd.date_range(start=arrival.floor('15min'), end=departure, freq='15min')
    timeline_df = pd.DataFrame(index=timeline_index)
    
    # --- Use the new 'meteo_indexed' DataFrame ---
    timeline_df = timeline_df.join(meteo_indexed['Temperature (C)'])
    
    timeline_df['Temperature (C)'] = timeline_df['Temperature (C)'].interpolate(method='time')
    timeline_df.rename(columns={'Temperature (C)': 'ambient_temp'}, inplace=True)
    timeline_df['power_W'] = 0.0
    interval_s = 15 * 60
    # --- Vectorized Simulation Loop ---
    for timestamp, row in timeline_df.iterrows():
        ambient_temp = row['ambient_temp']
        
        # Vectorized physics calculations
        delta_temp_if_heating = (ambient_temp - containers_df['temp']) * (1 - np.exp(-containers_df['surfaceArea'] * containers_df['heatTransCoef'] * interval_s / (containers_df['mass'] * containers_df['cargo_specificHeat'])))
        respiration_rate = (10.7 * containers_df['cargo_resp_f'] / 3600) * ((9 * containers_df['temp'] / 5 + 32)**containers_df['cargo_resp_g'])
        respiration_component = (respiration_rate * interval_s / containers_df['cargo_specificHeat'])
        delta_temp_if_cooling = -containers_df['coolingCapacity'] * interval_s / (containers_df['mass'] * containers_df['cargo_specificHeat']) + delta_temp_if_heating + respiration_component
        
        # Predict future state and decide on action
        future_temp_if_heating = containers_df['temp'] + delta_temp_if_heating
        future_temp_if_cooling = containers_df['temp'] + delta_temp_if_cooling
        switch_to_cooling = containers_df['boolHeating'] & (future_temp_if_heating > containers_df['cargo_upperBound'])
        switch_to_heating = ~containers_df['boolHeating'] & (future_temp_if_cooling < containers_df['cargo_lowerBound'])
        containers_df.loc[switch_to_cooling, 'boolHeating'] = False
        containers_df.loc[switch_to_heating, 'boolHeating'] = True
        
        # Calculate power for all containers and sum for this timestamp
        power_consumption = np.where(containers_df['boolHeating'], containers_df['auxiliarPower'], (containers_df['coolingCapacity'] / containers_df['cop']) + containers_df['auxiliarPower'])
        timeline_df.loc[timestamp, 'power_W'] = power_consumption.sum()
        
        # Update temperature for all containers
        delta_temp = np.where(containers_df['boolHeating'], delta_temp_if_heating, delta_temp_if_cooling)
        containers_df['temp'] += delta_temp

    # --- Final Output Formatting ---
    # Resample the 15-minute results to a per-second format to match the original output
    final_df = timeline_df.rename(columns={'power_W': 'Reefer Power'})
    final_df.index.name = 'Datetime'
    
    # Create a full per-second index
    per_second_index = pd.date_range(start=arrival, end=departure, freq='s')
    # Reindex and forward-fill to "stretch" the 15-min values to per-second
    final_df = final_df.reindex(per_second_index, method='ffill')
    
    # Convert power from Watts to MW to match original output units
    final_df['Reefer Power'] = final_df['Reefer Power'] / 1_000_000
    
    # 1. Convert the Datetime index into a column.
    final_df.reset_index(inplace=True)
    # 2. Rename the new 'index' column to 'Datetime'.
    final_df.rename(columns={'index': 'Datetime'}, inplace=True)
    

    return final_df