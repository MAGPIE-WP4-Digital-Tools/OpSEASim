from .vessel_functions import meteo, time_range, get_coordinates
from models.ops.models.ship_object import Vessel
from models.ops.models.ship_power import PowerDemand
from datetime import timedelta
import pandas as pd
import numpy as np


# Create the object vessel
def create_vessels(schedule, parameters, start_date) -> None:
    """A class for defining all the vessels calling at port"""
    coordinates: list = get_coordinates('Porto de Sines')
    
    # Get the simulation start time for timestamp calculations
    try:
        sim_start_dt = pd.to_datetime(start_date, format='%d-%m-%Y %H:%M:%S')
    except (ValueError, TypeError):
        sim_start_dt = pd.to_datetime(start_date, format='%d-%m-%Y')

    # Create vessels and their parameters
    vessels = {}
    schedule = schedule[schedule['call'].isin(parameters.keys())]
    
    for index, visit in schedule.iterrows():
        # Use the unique 'call' ID as the key
        call_id = visit['call']
        parameters[call_id]['connection_time'] = sim_start_dt + timedelta(seconds=int(parameters[call_id]['connection_time']))
        parameters[call_id]['disconnection_time'] = sim_start_dt + timedelta(seconds=int(parameters[call_id]['disconnection_time']))
        
        # Create a Ship object for this specific visit
        ship: Vessel = Vessel(visit, coordinates, parameters[call_id])
        vessels[call_id] = ship

    return vessels


# ENOVA SF reference power values for ship hoteling energy demand estimation
# Mapping based on ship type and gross tonnage (GT) range
ENOVA_POWER = {
    (0, 1000): {
        'Oil Tanker': 37, 'Chemical Tanker': 106, 'Gas Tanker': 111, 'Bulk': 26,
        'General Cargo': 12, 'Container Ship': 31, 'Ro-Ro Cargo': 28, 'Reefer': 44,
        'Passenger': 20, 'Others': 45, 'Fishing': 43
    },
    (1000, 5000): {
        'Oil Tanker': 161, 'Chemical Tanker': 289, 'Gas Tanker': 254, 'Bulk': 80,
        'General Cargo': 66, 'Container Ship': 121, 'Ro-Ro Cargo': 94, 'Reefer': 153,
        'Passenger': 119, 'Others': 144, 'Fishing': 149
    },
    (5000, 10000): {
        'Oil Tanker': 352, 'Chemical Tanker': 531, 'Gas Tanker': 667, 'Bulk': 132,
        'General Cargo': 149, 'Container Ship': 332, 'Ro-Ro Cargo': 213, 'Reefer': 319,
        'Passenger': 272, 'Others': 345, 'Fishing': 284
    },
    (10000, 25000): {
        'Oil Tanker': 476, 'Chemical Tanker': 723, 'Gas Tanker': 836, 'Bulk': 197,
        'General Cargo': 259, 'Container Ship': 473, 'Ro-Ro Cargo': 415, 'Reefer': 542,
        'Passenger': 570, 'Others': 553, 'Fishing': 454
    },
    (25000, 50000): {
        'Oil Tanker': 646, 'Chemical Tanker': 864, 'Gas Tanker': 1078, 'Bulk': 261,
        'General Cargo': 416, 'Container Ship': 864, 'Ro-Ro Cargo': 529, 'Reefer': 672,
        'Passenger': 1194, 'Others': 912, 'Fishing': 454
    },
    (50000, 100000): {
        'Oil Tanker': 838, 'Chemical Tanker': 1434, 'Gas Tanker': 2816, 'Bulk': 350,
        'General Cargo': 579, 'Container Ship': 1535, 'Ro-Ro Cargo': 668, 'Reefer': 800,
        'Passenger': 2100, 'Others': 1144, 'Fishing': 454
    },
    (100000, float('inf')): {
        'Oil Tanker': 1032, 'Chemical Tanker': 1536, 'Gas Tanker': 3556, 'Bulk': 438,
        'General Cargo': 704, 'Container Ship': 2295, 'Ro-Ro Cargo': 735, 'Reefer': 960,
        'Passenger': 2912, 'Others': 1248, 'Fishing': 454
    }
}

def enova(gt, ship_type):
    """
    Returns the reference hoteling power demand (kW) for a ship based on its gross tonnage (GT)
    and type, using ENOVA SF empirical data.
    
    Parameters:
        gt (float): Gross tonnage of the ship.
        ship_type (str): Type of the ship (e.g., 'Oil Tanker', 'Container Ship').
    
    Returns:
        int or None: Estimated power demand in kW or None if no match is found.
    """
    for (lower, upper), values in ENOVA_POWER.items():
        if lower <= gt < upper:
            return values.get(ship_type, None)  # Returns None if ship type not found
    return None  # Returns None if GT is outside all defined ranges


# Power demand calculation regardint the model selected
# Calculate energy demand
def energy_consumption(vessels, model, start_date, end_date):
# Calculate ship power demand according to their electrical equipment and reefers, dynamic model
    if model == 'ship_model':
        
        # --- FAILSAFE ---
        # If the vessels dictionary is empty, stop processing.
        if not vessels:
            print("Warning: No vessels in OPS found. Skipping energy consumption calculation.")
            return 

        
        min_eta = [v.eta for v in vessels.values()]
        max_etd = [v.etd for v in vessels.values()]
        min_start = pd.to_datetime(min(min_eta))
        max_end = pd.to_datetime(max(max_etd))
        latitude = [v.latitude for v in vessels.values()][0]
        longitude = [v.longitude for v in vessels.values()][0]
        meteo_data = meteo(latitude, longitude, min_start, max_end)

        for s in vessels.keys():
            print(f"{vessels[s].name} - {vessels[s].imo}")

            power_demand_profile = PowerDemand(vessels[s], start_date, end_date, meteo_data).ops_power

            df = power_demand_profile
            df.loc[(df['Datetime'] <= vessels[s].ops_connection) | (df['Datetime'] >= vessels[s].ops_disconnection), 'OPS Power Demand (MW)'] = 0
            
            df.drop(columns='Seconds', inplace=True)
            vessels[s].add_power_demand(df)
            

    elif model == 'enova':
        for i in vessels.keys():

            # Get power demand from Enova reference and convert to MW
            power = enova(vessels[i].gt, vessels[i].ship_type) / 1000

            # Create a time series to fill with the power demand 
            df = time_range(start_date, end_date)
            print(type(df['Seconds']))
            print(type(vessels[i].ops_connection))
            df['OPS Power Demand (MW)'] = np.where((df['Datetime'] >= vessels[i].ops_connection) & (df['Datetime'] <= vessels[i].ops_disconnection), power, 0)
            df['Ship Power Demand (MW)'] = df['OPS Power Demand (MW)']
            
            # Remove a coluna 'Seconds' and save the data
            df.drop(columns='Seconds', inplace=True)
            vessels[i].add_power_demand(df)
            
    elif model == 'formula':
        for i in vessels.keys():
            power = min(7.500, 0.001 * int(2.9165 * 0.25 * vessels[i].flexibility * (vessels[i].gt ** 0.8719)))

            # Create a time series to fill with the power demand 
            df = time_range(start_date, end_date)
            df['OPS Power Demand (MW)'] = np.where((df['Datetime'] >= vessels[i].ops_connection) & (df['Datetime'] <= vessels[i].ops_disconnection), power, 0)
            df['Ship Power Demand (MW)'] = df['OPS Power Demand (MW)']
            
            # Remove a coluna 'Seconds' and save the data
            df.drop(columns='Seconds', inplace=True)
            vessels[i].add_power_demand(df)

    elif model == 'emsa':
        for i in vessels.keys():
            if vessels[i].gt < 10000:
                power = 1.500
                # peak = 2000
            elif 10000 <= vessels[i].gt < 50000:
                power = 2.000
                # peak = 5000
            else:
                power = 4.000
                # peak = 6000

            # Create a time series to fill with the power demand 
            df = time_range(start_date, end_date)
            df['OPS Power Demand (MW)'] = np.where((df['Datetime'] >= vessels[i].ops_connection) & (df['Datetime'] <= vessels[i].ops_disconnection), power, 0)
            df['Ship Power Demand (MW)'] = df['OPS Power Demand (MW)']
            
            # Remove column 'Seconds' and save the data
            df.drop(columns='Seconds', inplace=True)
            vessels[i].add_power_demand(df)  