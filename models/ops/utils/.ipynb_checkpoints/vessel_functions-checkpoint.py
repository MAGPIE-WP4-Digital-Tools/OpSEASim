import requests
import math
import re
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
from datetime import datetime, timedelta
from sklearn.ensemble import GradientBoostingRegressor
import matplotlib.pyplot as plt
from ops.utils.equip_power import *


# Pathing
import sys
from pathlib import Path
project_root = Path(__file__).parent
# Go up the directory tree until 'terminaldemandsimulator'
while project_root.name != 'terminaldemandsimulator' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))
from utils.paths import DATA_DIR, OPS_DIR  # noqa: E402

try:
    _path = DATA_DIR / 'vessels.csv'
    VESSELS_DF = pd.read_csv(_path, sep=',')
except FileNotFoundError:
    print(f"Warning: The file at {_path} was not found. Functions in vessel_functions.py may fail.")
    VESSELS_DF = pd.DataFrame()
    
try:
    # Load the load factor sheet once and store it
    _path_lf = OPS_DIR / 'files/container_ship_lf.csv'
    LOAD_FACTOR_TEMPLATE_DF = pd.read_csv(_path_lf, sep=';')
except FileNotFoundError:
    print(f"Warning: The file at {_path_lf} was not found.")
    LOAD_FACTOR_TEMPLATE_DF = pd.DataFrame()


# Function to get port coordinates
def get_coordinates(port, retries=5, delay=1):
    geolocator = Nominatim(user_agent="port_locator")
    
    for attempt in range(retries):
        try:
            location = geolocator.geocode(port)
            if location:
                return location.latitude, location.longitude
            else:
                print(f"Attempt {attempt+1}: No location found.")
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Attempt {attempt+1}: Geocoding error: {e}")
        
        time.sleep(delay)  # espera entre tentativas
    
    print("Failed to retrieve coordinates after multiple attempts.")
    return None, None
            

# Set ships type (Convert to English and group them according to refs)
def ship_type(ship_type):
    if ship_type in ['Graneis Sólidos', 'Graneleiro', 'Graneleiro / Cereais', 'Graneleiro / Granéis Sólidos', 'Graneleiro / Estilha Madeira', 'Graneleiro / Carvão']:
        return 'Bulk'
    elif ship_type in ['Porta-Contentores', 'Carga Geral / Contentores']:
        return 'Container Ship'
    elif ship_type in ['Pesca', 'Embarcação de Pesca', 'Navio Fábrica Tratamento Peixe']:
        return 'Fishing'
    elif ship_type in ['Transporte Gado', 'Carga Geral', 'Transporte Especializado']:
        return 'General Cargo'
    elif ship_type in ['Cruzeiro', 'Carga Geral / Passageiros', 'Passageiros (mais de 12)']:
        return 'Passenger'
    elif ship_type in ['RoRo', 'RoRo / Contentores']:
        return 'Ro-Ro Cargo'
    elif ship_type in ['Frigorífico']:
        return 'Reefer'
    elif ship_type in ['Tanque', 'Tanque / Petroleiro', 'Tanque / Derivados Petróleo']:
        return 'Oil Tanker'
    elif ship_type in ['Tanque / Químico (alto mar)', 'Transporte Produtos Químicos']:
        return 'Chemical Tanker'
    elif ship_type in ['Tanque / Gás Petróleo Liquefeito (LPG)', 'Tanque / Gás Natural Liquefeito (LNG)', 'Tanque / LNG e LPG', 'Tanque / Gás Liquefeito']:
        return 'Gas Tanker'
    else:
        return 'Others'


# Ratio for Aux-Engine calculation
def ae_me_ratio(ship_type):
    if ship_type == 'Bulk':
        return 0.21
    elif ship_type in ['Container Ship', 'Reefer']:
        return 0.22
    elif ship_type == 'Fishing':
        return 0.64
    elif ship_type == 'General Cargo':
        return 0.33
    elif ship_type == 'Others':
        return 0.29
    elif ship_type == 'Passenger':
        return 0.35
    elif ship_type == 'Ro-Ro Cargo':
        return 0.30
    elif ship_type in ['Oil Tanker', 'Chemical Tanker', 'Gas Tanker']:
        return 0.27


# Verify Main Engine data
def gt_verif(gt, breadth, ship_type):
    
    # Function to check if a value can be cast to int
    def is_valid_int(val):
        try:
            int(val)
            return True
        except:
            return False
            
    if math.isnan(gt) or gt == 0:
        df = VESSELS_DF.copy()   
        ships = df[['ship_type', 'gt', 'breadth']]
        ships_gt = ships[ships['ship_type'].isin([ship_type])]
        ships_gt = ships_gt.dropna()
        
        ships_gt_clean = ships_gt[ships_gt['breadth'].apply(is_valid_int) & ships_gt['gt'].apply(is_valid_int)].copy()
        
        x = ships_gt_clean[['breadth']].astype(int)
        y = ships_gt_clean['gt'].astype(int)
        
        # Create and fit the Gradient Boosting model
        model = GradientBoostingRegressor()
        model.fit(x, y)
        breadth_df = pd.DataFrame({'breadth': [breadth]})
        return model.predict(breadth_df)[0]
    else:
        return gt


# Verify Main Engine data
def dwt_verif(dwt, breadth, ship_type):
    dwt = float(dwt)
    
    # Function to check if a value can be cast to int
    def is_valid_int(val):
        try:
            int(val)
            return True
        except:
            return False
            
    if math.isnan(dwt) or dwt == 0:
        df = VESSELS_DF.copy()
        ships = df[['ship_type', 'dwt', 'breadth']]
        ships_dwt = ships[ships['ship_type'].isin([ship_type])]
        ships_dwt = ships_dwt.dropna()
        
        ships_dwt_clean = ships_dwt[ships_dwt['breadth'].apply(is_valid_int) & ships_dwt['dwt'].apply(is_valid_int)].copy()
        
        x = ships_dwt_clean[['breadth']].astype(int)
        y = ships_dwt_clean['dwt'].astype(int)
    
        # Create and fit the Gradient Boosting model
        model = GradientBoostingRegressor()
        model.fit(x, y)
        breadth_df = pd.DataFrame({'breadth': [breadth]})
        return model.predict(breadth_df)[0]
    else:
        return dwt


# Verify Main Engine data
def teus_verif(teus, breadth, ship_type):
    teus = float(teus)
    
    # Function to check if a value can be cast to int
    def is_valid_int(val):
        try:
            int(val)
            return True
        except:
            return False
            
    if math.isnan(teus) or teus == 0:
        df = VESSELS_DF.copy()
        ships = df[['ship_type', 'teus', 'breadth']]
        ships_teus = ships[ships['ship_type'].isin([ship_type])]
        ships_teus = ships_teus.dropna()
        
        ships_teus_clean = ships_teus[ships_teus['breadth'].apply(is_valid_int) & ships_teus['teus'].apply(is_valid_int)].copy()
        
        x = ships_teus_clean[['breadth']].astype(int)
        y = ships_teus_clean['teus'].astype(int)
    
        # Create and fit the Gradient Boosting model
        model = GradientBoostingRegressor()
        model.fit(x, y)
        breadth_df = pd.DataFrame({'breadth': [breadth]})
        return model.predict(breadth_df)[0]
    else:
        return teus


# Verify Main Engine data
def depth_verif(depth, breadth, ship_type):
    depth = float(depth)
    
    # Function to check if a value can be cast to int
    def is_valid_int(val):
        try:
            int(val)
            return True
        except:
            return False
            
    if math.isnan(depth) or depth == 0:
        df = VESSELS_DF.copy()
        ships = df[['ship_type', 'depth', 'breadth']]
        ships_depth = ships[ships['ship_type'].isin([ship_type])]
        ships_depth = ships_depth.dropna()
        
        ships_depth_clean = ships_depth[ships_depth['breadth'].apply(is_valid_int) & ships_depth['depth'].apply(is_valid_int)].copy()
        
        x = ships_depth_clean[['breadth']].astype(int)
        y = ships_depth_clean['depth'].astype(int)
    
        # Create and fit the Gradient Boosting model
        model = GradientBoostingRegressor()
        model.fit(x, y)
        breadth_df = pd.DataFrame({'breadth': [breadth]})
        return model.predict(breadth_df)[0]
    else:
        return depth


# Verify Main Engine data
def loa_verif(loa, breadth, ship_type):
    loa = float(loa)
    
    # Function to check if a value can be cast to int
    def is_valid_int(val):
        try:
            int(val)
            return True
        except:
            return False
            
    if math.isnan(loa) or loa == 0:
        df = VESSELS_DF.copy()
        ships = df[['ship_type', 'loa', 'breadth']]
        ships_loa = ships[ships['ship_type'].isin([ship_type])]
        ships_loa = ships_loa.dropna()
        
        ships_loa_clean = ships_loa[ships_loa['breadth'].apply(is_valid_int) & ships_loa['loa'].apply(is_valid_int)].copy()
        
        x = ships_loa_clean[['breadth']].astype(int)
        y = ships_loa_clean['loa'].astype(int)
    
        # Create and fit the Gradient Boosting model
        model = GradientBoostingRegressor()
        model.fit(x, y)
        breadth_df = pd.DataFrame({'breadth': [breadth]})
        return model.predict(breadth_df)[0]
    else:
        return loa


# Verify Main Engine data
def me_verif(me, gt, ship_type):
    
    # Function to check if a value can be cast to int
    def is_valid_int(val):
        try:
            int(val)
            return True
        except:
            return False

    if math.isnan(me) or me == 0:
        df = VESSELS_DF.copy()
        ships = df[['ship_type', 'gt', 'me']]
        ships_me = ships[ships['ship_type'] == ship_type]
        ships_me = ships_me.dropna()
        ships_me = ships_me.reset_index()
        ships_me = ships_me.drop(columns=["index"])
        
        ships_me_clean = ships_me[ships_me['gt'].apply(is_valid_int) & ships_me['me'].apply(is_valid_int)].copy()
        # Get only the numbers from the data
        
        x = ships_me_clean[['gt']].astype(int)
        y = ships_me_clean['me'].astype(int)
    
        # Create and fit the Gradient Boosting model
        model = GradientBoostingRegressor()
        model.fit(x, y)
        gt_df = pd.DataFrame({'gt': [gt]})
    
        return (model.predict(gt_df)[0]) * 0.7457
    else:
        return me * 0.7457


# Calculate Aux-Engine power
def ae_me(me, ship_type):
    aux_engine = me * ae_me_ratio(ship_type) / 1000
    return aux_engine

    
# Function to get Ships data from APS file
# breadth = Breadth
# depth = Depth
# loa = LOA
# dwt = DWT
# gt = GT
# teus = TEUS
def ships_info(imo) -> dict:
    path = 'data/vessels.csv'
        
    ships = pd.read_csv(path, sep=',')

    info_list = ships.loc[ships['imo'] == str(imo), ['imo', 'name', 'ship_type', 'gt', 'dwt', 'teus', 'depth', 'breadth', 'loa', 'speed', 'pob', 'me']].iloc[0].to_dict()
    
    return info_list


# Function to validate the number of POB if == 0 or NaN, return a value
# Needs to improve to set a number of POB according to ship type
def val_pob(pob, ship_type):
    if ship_type != 'Passenger':
        if math.isnan(pob) or pob == 0:
            return 25
        else:
            return pob
    else:
        if math.isnan(pob) or pob == 0:
            return 500
        else:
            return pob


# Velocity validation
def val_velocity(velocity, ship_type):
    if ship_type != 'Passenger':
        if math.isnan(velocity) or velocity == 0:
            return 20
        else:
            return velocity
    else:
        if math.isnan(velocity) or velocity == 0:
            return 22
        else:
            return velocity


# Set the time range in seconds
def time_range(start, end):
    # Set start time
    start_time = datetime.strptime(start, '%d-%m-%Y')
    start_time = start_time.replace(hour=0, minute=0, second=0)

    # Set end time
    end_time = datetime.strptime(end, '%d-%m-%Y')
    end_time = end_time.replace(hour=23, minute=59, second=59)

    datetime_list = pd.date_range(start=start_time, end=end_time, freq='s')
    
    # Create a DataFrame with the datetime values
    df = pd.DataFrame(datetime_list, columns=['Datetime'])
    df['Seconds'] = (df['Datetime'] - pd.Timestamp('2022-09-26')).dt.total_seconds().astype(int)
    
    return df


# Set ship active rate by 15-minute interval
def ship_active_rate(start, end):
    start = pd.to_datetime(start, dayfirst=True)
    end = pd.to_datetime(end, dayfirst=True)
        
    start_timestamp = start
    end_timestamp = end
    # Adjust the end timestamp to the next full 15-minute interval
    adjusted_end_timestamp = (end_timestamp + pd.Timedelta(minutes=15)).ceil('15min')
            
    # Create the time series with a 15-minute interval
    time_series = pd.date_range(start=start_timestamp.floor('15min'), end=adjusted_end_timestamp, freq='15min')
            
    # Convert the time series to a DataFrame
    time_series_df = pd.DataFrame(time_series, columns=['Datetime'])
    
    def active_rate(start, end):
        start_timestamp = start
        end_timestamp = end
        # Adjust the end timestamp to the next full 15-minute interval
        adjusted_end_timestamp = (end_timestamp + pd.Timedelta(minutes=15)).ceil('15min')
            
        # Initialize the Active_Percentage column
        active_percentage = []
            
        # Loop through each 15-minute interval in the time series and calculate active percentage
        for i in range(len(time_series_df)):
            current_interval = time_series_df.loc[i, 'Datetime']
            next_interval = current_interval + pd.Timedelta(minutes=15)
            
            if current_interval <= start_timestamp:
                # Partial time in the starting interval
                active_minutes = (next_interval - start_timestamp).seconds / 60
                active_percentage.append(active_minutes / 15)                
            elif current_interval > start_timestamp and next_interval <= end_timestamp:
                # Fully active interval
                active_percentage.append(1)
            elif current_interval <= end_timestamp and next_interval > end_timestamp:
                # Partial time in the ending interval
                active_minutes = (next_interval - end_timestamp).seconds / 60
                active_percentage.append(active_minutes / 15)
            else:
                # Inactive interval (this should not occur with valid input)
                active_percentage.append(0)
    
        return active_percentage
    
    
    def ops_rate(start, end):
        # OPS plug and unplug time
        plug_time = pd.Timedelta(minutes=30)
        unplug_time = pd.Timedelta(minutes=30)
            
        start_timestamp = start + plug_time
        end_timestamp = end - unplug_time
        # Adjust the end timestamp to the next full 15-minute interval
        adjusted_end_timestamp = (end_timestamp + pd.Timedelta(minutes=15)).ceil('15min')
            
        # Initialize the Active_Percentage column
        active_percentage = []
            
        # Loop through each 15-minute interval in the time series and calculate active percentage
        for i in range(len(time_series_df)):
            current_interval = time_series_df.loc[i, 'Datetime']
            next_interval = current_interval + pd.Timedelta(minutes=15)
            
            if start_timestamp > end_timestamp:
                active_percentage.append(0)
            elif current_interval <= start_timestamp and next_interval > start_timestamp:
                # Partial time in the starting interval
                active_minutes = (next_interval - start_timestamp).seconds / 60
                active_percentage.append(active_minutes / 15)                
            elif current_interval > start_timestamp and next_interval <= end_timestamp:
                # Fully active interval
                active_percentage.append(1)
            elif current_interval <= end_timestamp and next_interval > end_timestamp:
                # Partial time in the ending interval
                active_minutes = (next_interval - end_timestamp).seconds / 60
                active_percentage.append(active_minutes / 15)
            else:
                # Inactive interval (this should not occur with valid input)
                active_percentage.append(0)
    
        return active_percentage
    
            
    # Add the Active_Percentage column to the DataFrame
    time_series_df['Ship_Rate'] = active_rate(start, end)
    time_series_df['OPS_Rate'] = ops_rate(start, end)
            
    return time_series_df


# Funtion to get meteo data
def fetch_meteo(latitude, longitude, start_date, end_date):
    # Parameters for the NASA POWER API
    parameters = "T2M"
    community = "AG"  # Agricultural data
    data_format = "JSON"

    # Function to fetch data for a smaller date range
    def fetch_data(dt_start, dt_end):
        url = (
            f"https://power.larc.nasa.gov/api/temporal/hourly/point?"
            f"parameters={parameters}&community={community}&longitude={longitude}"
            f"&latitude={latitude}&start={dt_start}&end={dt_end}&format={data_format}"
        )
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Request failed with status code: {response.status_code}")
                return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    # Split the date range into smaller chunks (e.g., annual)
    def generate_date_ranges(start_date, end_date, step_days=365):
        adjusted_end_date = end_date.ceil('h')
        start_dt = pd.Timestamp(start_date)
        end_dt = pd.Timestamp(adjusted_end_date)
        date_ranges = []
        while start_dt < end_dt:
            next_dt = start_dt + pd.Timedelta(days=step_days)
            if next_dt > end_dt:
                next_dt = end_dt
            date_ranges.append((start_dt.strftime("%Y%m%d"), next_dt.strftime("%Y%m%d")))
            start_dt = next_dt + pd.Timedelta(days=1)
        return date_ranges

    # Main script to fetch and combine data
    all_data = []
    date_ranges = generate_date_ranges(start_date, end_date, step_days=365)

    for start_date, end_date in date_ranges:
        print(f"Fetching meteo data from {start_date} to {end_date}...")
        result = fetch_data(start_date, end_date)
        if result:
            try:
                records = result['properties']['parameter']
                dates = list(records['T2M'].keys())
                for datetime_str in dates:
                    all_data.append({
                        "Datetime": datetime_str,
                        "Temperature (C)": records['T2M'][datetime_str],
                    })
            except KeyError as e:
                print(f"Key error while processing data: {e}")
                continue

    
    if all_data:
        meteo = pd.DataFrame(all_data)
    
        # Convert 'Datetime' column to proper datetime format
        meteo['Datetime'] = pd.to_datetime(meteo['Datetime'], format='%Y%m%d%H')
            
        # Resample the data to 15-minute intervals and forward fill the temperature values
        meteo.set_index('Datetime', inplace=True)
        meteo = meteo.resample('15min').ffill().reset_index()
        return meteo
            
    else:
        print("No data fetched.")
        meteo = pd.DataFrame()
        return meteo


# Funtion to get meteo data
def meteo(latitude, longitude, start_date, end_date):
    while True:
        data = fetch_meteo(latitude, longitude, start_date, end_date)
        if not data.empty:
            return data
        else:
            print("Empty DataFrame received, retrying...")
            time.sleep(1)  # Optional: wait for a second 


# Function to to calculate HVAC load factor
def hvac_lf(temp, hvac_p_sys, ship_occupancy, date_time, latitude):
    
    # Funtion to get season of the year
    def get_season(date_time, latitude):
        # Ensure the input date is a pandas Timestamp
        if not isinstance(date_time, pd.Timestamp):
            date_time = pd.to_datetime(date_time)
    
        day_of_year = date_time.timetuple().tm_yday  # Day of the year (1-365)
    
        # Determine the hemisphere based on latitude
        hemisphere = "north" if latitude > 0 else "south"
    
        # Define summer and winter periods
        if hemisphere == "north":
            # Northern Hemisphere
            summer_start = 171  # June 21
            summer_end = 265    # September 22
            # Summer: June 21 to September 22
            if summer_start <= day_of_year < summer_end:
                return "Summer"
            else:
                return "Winter"
        else:
            # Southern Hemisphere
            summer_start = 355  # December 21
            summer_end = 79     # March 20 (next year)
            # Summer: December 21 to March 20
            if day_of_year >= summer_start or day_of_year < summer_end:
                return "Summer"
            else:
                return "Winter"

    
    period = get_season(date_time, latitude)
    
    var_constant = 0.026
    
    if period == "Summer":
        # Cooling load
        design_temp = 35 # Design temperatures for cooling load
        outdoor_temp = temp
        temp_var = outdoor_temp - design_temp
        lf_var = temp_var * var_constant
        lf_cooling = 1 + lf_var
        return lf_cooling
    else:
        # Heating load
        design_temp = -5 # Design temperatures for cooling load
        outdoor_temp = temp
        temp_var = design_temp - outdoor_temp
        lf_var = temp_var * var_constant
        lf_heating = 1 + lf_var
        return lf_heating


# Function to calculate the load factor
def load_factor(vessels: dict):
    lf_df = LOAD_FACTOR_TEMPLATE_DF.copy()
    for i in lf_df['Electrical Equipment']:
        lf_df.loc[lf_df['Electrical Equipment'] == i, 'Nominal Power (kW)'] = equip_power(i, vessels)
    
    # Perform all the calculations as before
    lf_df['Total Nominal Power (kW)'] = lf_df['Nominal Power (kW)'] * lf_df['Nº of Units']
    
    # Avoid division by zero if the sum is zero
    total_power_sum = lf_df['Total Nominal Power (kW)'].sum()
    if total_power_sum > 0:
        lf_df['Nominal Power Weights'] = lf_df['Total Nominal Power (kW)'] / total_power_sum
    else:
        lf_df['Nominal Power Weights'] = 0
        
    lf_df['Required Power (kW)'] = lf_df['Total Nominal Power (kW)'] * lf_df['Load Factor (Un)Loading']
    lf_df['Weighted Load Factor'] = lf_df['Nominal Power Weights'] * lf_df['Load Factor (Un)Loading']
    lf_df['W_LF SimultaneityFactor Included'] = lf_df['Weighted Load Factor'] * lf_df['Simultaneity Factor']
    
    ship_lf = lf_df.loc[lf_df['Group'] != 'AC /HVAC', 'W_LF SimultaneityFactor Included'].sum()
    hvac_lf = lf_df.loc[lf_df['Group'] == 'AC /HVAC', 'W_LF SimultaneityFactor Included'].sum()
    
    return {'ship_lf': ship_lf, 'hvac_lf': hvac_lf}


# Function to plot data
def plot_power_demand(load):
    # Plot
    fig, axs = plt.subplots(4, figsize=(15, 7))
    
    # Plot Temperature
    axs[0].plot(load['Datetime'], load['Temperature (C)'], label='Temperature (C)', color='orange')
    # Set title and labels
    axs[0].set_title('Temperature over Time')
    axs[0].set_xlabel('Datetime')
    axs[0].set_ylabel('Temperature (C)')
    # Add legend
    axs[0].legend()
    
    # Plot HVAC Sys LF
    axs[1].plot(load['Datetime'], load['HVAC Sys LF'], label='HVAC Sys LF', color='green')
    # Set title and labels
    axs[1].set_title('HVAC Sys LF over Time')
    axs[1].set_xlabel('Datetime')
    axs[1].set_ylabel('HVAC Sys LF')
    # Add legend
    axs[1].legend()
    
    # Plot Total Ship LF
    axs[2].plot(load['Datetime'], load['Total Ship LF'], label='Total Ship LF', color='blue')
    # Set title and labels
    axs[2].set_title('Total Ship LF over Time')
    axs[2].set_xlabel('Datetime')
    axs[2].set_ylabel('Total Ship LF')
    # Add legend
    axs[2].legend()
    
    # Plot Power Demand
    axs[3].plot(load['Datetime'], load['Ship Power Demand (kW)'], label='Ship Power Demand (kW)', color='red')
    # Plot OPS Power Demand
    axs[3].plot(load['Datetime'], load['OPS Power Demand (kW)'], label='OPS Power Demand (kW)', color='blue')
    # Set title and labels
    axs[3].set_title('Power Demand over Time')
    axs[3].set_xlabel('Datetime')
    axs[3].set_ylabel('Ship Power Demand (kW)')
    # Add legend
    axs[3].legend()
    
    plt.tight_layout()
    plt.show()


# Enova SF power references for ship power demand calculation
def enova(gt, ship_type):   
    if gt < 1000:
        if ship_type == 'Oil Tanker':
            return 37
        elif ship_type == 'Chemical Tanker':
            return 106
        elif ship_type == 'Gas Tanker':
            return 111
        elif ship_type == 'Bulk':
            return 26
        elif ship_type == 'General Cargo':
            return 12
        elif ship_type == 'Container Ship':
            return 31
        elif ship_type == 'Ro-Ro Cargo':
            return 28
        elif ship_type == 'Reefer':
            return 44
        elif ship_type == 'Passenger':
            return 20
        elif ship_type == 'Others':
            return 45
        elif ship_type == 'Fishing':
            return 43
    elif 1000 <= gt < 5000:
        if ship_type == 'Oil Tanker':
            return 161
        elif ship_type == 'Chemical Tanker':
            return 289
        elif ship_type == 'Gas Tanker':
            return 254
        elif ship_type == 'Bulk':
            return 80
        elif ship_type == 'General Cargo':
            return 66
        elif ship_type == 'Container Ship':
            return 121
        elif ship_type == 'Ro-Ro Cargo':
            return 94
        elif ship_type == 'Reefer':
            return 153
        elif ship_type == 'Passenger':
            return 119
        elif ship_type == 'Others':
            return 144
        elif ship_type == 'Fishing':
            return 149
    elif 5000 <= gt < 10000:
        if ship_type == 'Oil Tanker':
            return 352
        elif ship_type == 'Chemical Tanker':
            return 531
        elif ship_type == 'Gas Tanker':
            return 667
        elif ship_type == 'Bulk':
            return 132
        elif ship_type == 'General Cargo':
            return 149
        elif ship_type == 'Container Ship':
            return 332
        elif ship_type == 'Ro-Ro Cargo':
            return 213
        elif ship_type == 'Reefer':
            return 319
        elif ship_type == 'Passenger':
            return 272
        elif ship_type == 'Others':
            return 345
        elif ship_type == 'Fishing':
            return 284
    elif 10000 <= gt < 25000:
        if ship_type == 'Oil Tanker':
            return 476
        elif ship_type == 'Chemical Tanker':
            return 723
        elif ship_type == 'Gas Tanker':
            return 836
        elif ship_type == 'Bulk':
            return 197
        elif ship_type == 'General Cargo':
            return 259
        elif ship_type == 'Container Ship':
            return 473
        elif ship_type == 'Ro-Ro Cargo':
            return 415
        elif ship_type == 'Reefer':
            return 542
        elif ship_type == 'Passenger':
            return 570
        elif ship_type == 'Others':
            return 553
        elif ship_type == 'Fishing':
            return 454
    elif 25000 <= gt < 50000:
        if ship_type == 'Oil Tanker':
            return 646
        elif ship_type == 'Chemical Tanker':
            return 864
        elif ship_type == 'Gas Tanker':
            return 1078
        elif ship_type == 'Bulk':
            return 261
        elif ship_type == 'General Cargo':
            return 416
        elif ship_type == 'Container Ship':
            return 864
        elif ship_type == 'Ro-Ro Cargo':
            return 529
        elif ship_type == 'Reefer':
            return 672
        elif ship_type == 'Passenger':
            return 1194
        elif ship_type == 'Others':
            return 912
        elif ship_type == 'Fishing':
            return 454
    elif 50000 <= gt < 100000:
        if ship_type == 'Oil Tanker':
            return 838
        elif ship_type == 'Chemical Tanker':
            return 1434
        elif ship_type == 'Gas Tanker':
            return 2816
        elif ship_type == 'Bulk':
            return 350
        elif ship_type == 'General Cargo':
            return 579
        elif ship_type == 'Container Ship':
            return 1535
        elif ship_type == 'Ro-Ro Cargo':
            return 668
        elif ship_type == 'Reefer':
            return 800
        elif ship_type == 'Passenger':
            return 2100
        elif ship_type == 'Others':
            return 1144
        elif ship_type == 'Fishing':
            return 454
    else:
        if ship_type == 'Oil Tanker':
            return 1032
        elif ship_type == 'Chemical Tanker':
            return 1536
        elif ship_type == 'Gas Tanker':
            return 3556
        elif ship_type == 'Bulk':
            return 438
        elif ship_type == 'General Cargo':
            return 704
        elif ship_type == 'Container Ship':
            return 2295
        elif ship_type == 'Ro-Ro Cargo':
            return 735
        elif ship_type == 'Reefer':
            return 960
        elif ship_type == 'Passenger':
            return 2912
        elif ship_type == 'Others':
            return 1248
        elif ship_type == 'Fishing':
            return 454


