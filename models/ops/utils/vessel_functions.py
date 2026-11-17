import requests
import math
import csv
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
import os
from datetime import datetime
import matplotlib.dates as mdates
from sklearn.ensemble import GradientBoostingRegressor
from.equip_power import equip_power


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
def get_coordinates(location: str, retries: int = 5, delay: int = 1) -> tuple[float | None, float | None]:
    """
    Retrieves the coordinates of a location from a local CSV file,
    or queries Nominatim if not cached. Results are stored in 'data/coordinates.csv'.

    Parameters:
        location (str): Name of the location to geocode.
        retries (int): Number of retries for geocoding.
        delay (int): Delay between retries in seconds.

    Returns:
        tuple: (latitude, longitude) if found, otherwise (None, None)
    """

    os.makedirs("data", exist_ok=True)
    csv_path = "data/coordinates.csv"

    # Ensure the CSV file exists and has correct header
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        with open(csv_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=['location', 'latitude', 'longitude'])
            writer.writeheader()

    # Try to retrieve from CSV
    with open(csv_path, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if 'location' in row and row['location'].lower() == location.lower():
                return float(row['latitude']), float(row['longitude'])

    # Not in CSV, use geocoder
    geolocator = Nominatim(user_agent="port_locator")
    for attempt in range(1, retries + 1):
        try:
            geo = geolocator.geocode(location)
            if geo:
                latitude, longitude = geo.latitude, geo.longitude

                # Append new coordinates to CSV
                with open(csv_path, mode='a', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=['location', 'latitude', 'longitude'])
                    writer.writerow({'location': location, 'latitude': latitude, 'longitude': longitude})

                return latitude, longitude
            else:
                print(f"Attempt {attempt}/{retries}: Location not found.")
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Attempt {attempt}/{retries}: Geocoding error: {e}")
        
        time.sleep(delay)

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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
    aux_engine = me * ae_me_ratio(ship_type)
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


def get_reefers(teus):
    reefers = int(((2e-06) * (teus ** 2)) + (0.0519 * teus))
    return reefers


# Set the time range in seconds
def time_range(start, end):
    # Set start time
    # start_time = datetime.strptime(start, '%d-%m-%Y')
    
    try:
        start_time = datetime.strptime(start, '%d-%m-%Y %H:%M:%S')
    except ValueError:
        start_time = datetime.strptime(start, '%d-%m-%Y')
        
    # start_time = start_time.replace(hour=0, minute=0, second=0)

    # Set end time
    # end_time = datetime.strptime(end, '%d-%m-%Y')
    
    try:
        end_time = datetime.strptime(end, '%d-%m-%Y %H:%M:%S')
    except ValueError:
        end_time = datetime.strptime(end, '%d-%m-%Y')
    # end_time = end_time.replace(hour=23, minute=59, second=59)
    #end_time += timedelta(days=1)

    datetime_list = pd.date_range(start=start_time, end=end_time, freq='s')
    
    # Create a DataFrame with the datetime values
    df = pd.DataFrame(datetime_list, columns=['Datetime'])
    df['Seconds'] = (df['Datetime'] - start_time).dt.total_seconds().astype(int)
    
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
        plug_time = pd.Timedelta(minutes=0)
        unplug_time = pd.Timedelta(minutes=0)
            
        start_timestamp = start + plug_time
        end_timestamp = end - unplug_time
            
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


def fetch_meteo(latitude, longitude, start_date, end_date):
    parameters = "T2M"
    community = "AG"
    data_format = "JSON"
    
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

    def generate_date_ranges(start_date, end_date, step_days=365):
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)# + pd.Timedelta(days=1)
        date_ranges = []
        while start_dt < end_dt:
            next_dt = start_dt + pd.Timedelta(days=step_days)
            if next_dt > end_dt:
                next_dt = end_dt
            date_ranges.append((start_dt.strftime("%Y%m%d"), next_dt.strftime("%Y%m%d")))
            start_dt = next_dt + pd.Timedelta(days=1)
        return date_ranges

    all_data = []
    date_ranges = generate_date_ranges(start_date, end_date)

    for range_start, range_end in date_ranges:
        print(f"Fetching meteo data from {range_start} to {range_end}...")
        result = fetch_data(range_start, range_end)
        if result:
            try:
                t2m_data = result['properties']['parameter']['T2M']
                for datetime_str, temp in t2m_data.items():
                    all_data.append({
                        "Datetime": datetime_str,
                        "Temperature (C)": temp,
                    })
            except KeyError as e:
                print(f"Key error: {e}")
                continue

    if all_data:
        meteo = pd.DataFrame(all_data)
        meteo['Datetime'] = pd.to_datetime(meteo['Datetime'], format='%Y%m%d%H')
        meteo.set_index('Datetime', inplace=True)

        # Create full 15-min index until 23:45 of end_date
        start_time = meteo.index.min()
        end_time = pd.to_datetime(end_date).replace(hour=23, minute=45)
        full_index = pd.date_range(start=start_time, end=end_time, freq='15min')

        meteo = meteo.reindex(full_index)
        meteo = meteo.ffill().reset_index().rename(columns={"index": "Datetime"})
        return meteo
    else:
        print("No data fetched.")
        return pd.DataFrame()

def meteo(latitude, longitude, start_date, end_date, max_retries=5):
    # File paths
    data_dir = "data"
    log_dir = "models/ops/logs"
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    csv_file = os.path.join(data_dir, "meteo.csv")
    log_file = os.path.join(log_dir, "meteo_log.txt")

    # Load existing data
    if os.path.exists(csv_file):
        existing = pd.read_csv(csv_file, parse_dates=["Datetime"])
        existing_min = existing["Datetime"].min().date()
        existing_max = existing["Datetime"].max().date()
    else:
        existing = pd.DataFrame()
        existing_min = None
        existing_max = None

    requested_start = pd.to_datetime(start_date).date()
    requested_end = pd.to_datetime(end_date).date()

    # Determine missing intervals
    to_fetch = []
    if existing.empty:
        to_fetch.append((requested_start, requested_end))
    else:
        if requested_start < existing_min:
            to_fetch.append((requested_start, existing_min))
        if requested_end > existing_max:
            to_fetch.append((existing_max, requested_end))

    # Fetch only missing intervals
    new_data = []
    for s, e in to_fetch:
        for attempt in range(max_retries):
            df = fetch_meteo(latitude, longitude, str(s), str(e))
            if not df.empty:
                new_data.append(df)
                break
            else:
                print(f"Attempt {attempt + 1}/{max_retries} failed. Retrying...")
                time.sleep(2)
        else:
            raise RuntimeError(f"Failed to fetch meteo data for range {s} to {e}")

    # Merge and update
    if new_data:
        combined = pd.concat([existing] + new_data, ignore_index=True)
        combined = combined.drop_duplicates(subset="Datetime").sort_values("Datetime")
        combined.to_csv(csv_file, index=False)

        # Update log with new global min/max
        min_date = combined["Datetime"].min().date()
        max_date = combined["Datetime"].max().date()
        with open(log_file, "w") as f:
            f.write(f"{latitude},{longitude},{min_date},{max_date}\n")

        return combined
    else:
        print("All data already up to date. Loading from CSV.")
        return existing


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

# Functon to et the minimun energy only of the ship consumption without reefers consumption
def ops_min_energy(df, percentage, column="OPS Power Demand (MW)"):
    """
    Calculates the minimum required energy (E_min_b) during the berth period.

    Parameters:
        df (pd.DataFrame): DataFrame with power data (MW).
        percentage (float): Minimum required percentage (e.g., 0.5 for 50%).
        column (str): Column name containing ship power demand.

    Returns:
        E_min (float): Minimum required energy (in MWh).
        T_berth (int): Duration of berth (number of time steps).
        P_min (float): Derived minimum power (in MW).
    """

    T_berth = len(df)
    total_energy = df[column].sum()  # Convert to MWh
    E_min = total_energy * (1 - percentage)
    
    return E_min, T_berth

# Function to get the OPS nominal power
def ops_nom_power(vessel):
    nom_power = vessel.ops_nom_power
    return nom_power

# Function to get the OPS minimal power
def ops_min_power(vessel):
    min_power = vessel.ops_min_power
    return min_power
    
# Function to calculate baseload profile
def ops_base(E_min, T_berth, P_min, df, column="P_OPS_base (MW)"):
    """
    Computes the base OPS power for each timestep using the full formula:
    P_OPS_base = min(P_min, E_min / (T_berth * delta_t))

    Parameters:
        E_min (float): Minimum required energy (in MWh).
        T_berth (int): Number of time steps during berth.
        P_min (float): Minimum allowed power (MW).
        df (pd.DataFrame): DataFrame to update.
        column (str): Name of the output column.

    Returns:
        pd.DataFrame: Updated DataFrame with base OPS power column.
    """

    P_from_energy = E_min / T_berth
    P_base = max(P_min, P_from_energy)
    df[column] = P_base
    return df

# Function to calculate upward flexibility
def ops_up(baseload, p_nom):
    # Reset index to expose 'Datetime' as a column
    base = baseload.reset_index()

    # Compute the two deltas
    delta_p_nom = p_nom - base['P_OPS_base (MW)']
    delta_ops_demand = base['OPS Power Demand (MW)'] - base['P_OPS_base (MW)']

    # Take the minimum of both, and ensure no negative values
    base['Upward_profile'] = pd.concat([delta_p_nom, delta_ops_demand], axis=1).min(axis=1).clip(lower=0)

    # Return only Datetime and Upward_profile with Datetime as index
    result = base[['Datetime', 'Upward_profile']].set_index('Datetime')

    return result

# Function to calculate upward flexibility
def ops_down(baseload, p_min, E_min, T_berth):
    # Copy input to avoid modifying original DataFrame
    base = baseload.copy().reset_index()

    P_min = max(p_min, E_min/T_berth)

    # Compute downward flexibility = Baseload - p_min, clipped to non-negative
    base['Downward_profile'] =  base['P_OPS_base (MW)'] - P_min

    # Keep only Datetime and Downward_profile, set Datetime as index
    result = base[['Datetime', 'Downward_profile']].set_index('Datetime')

    return result


def insert_ops_boundaries(df, conn_time, disc_time):
    """
    Ensure OPS connection and disconnection timestamps are included in the time index.
    """
    if df.index.min() < conn_time and conn_time not in df.index:
        row = df.iloc[0].copy()
        row.name = conn_time
        df = pd.concat([df, row.to_frame().T])
    if df.index.max() < disc_time and disc_time not in df.index:
        row = df.iloc[-1].copy()
        row.name = disc_time
        df = pd.concat([df, row.to_frame().T])
    return df[(df.index >= conn_time) & (df.index <= disc_time)]

def plot_upward_flexibility(ax, df, Ps, Base, conn_time, disc_time):
    """
    Plot the area of upward flexibility (Ps > Base).
    """
    mask = (df.index >= conn_time) & (df.index <= disc_time) & (Ps > Base)
    ax.fill_between(df.index, Base[-1], Ps, where=mask, step='post',
                    alpha=0.3, color='green', label='Upward Flexibility')

def plot_downward_flexibility(ax, df, Ps, Base, p_min, conn_time, disc_time, step_delta):
    """
    Plot the area of downward flexibility (Base > min(Ps, P_min)).
    """
    t_steps, p_low, p_high = [], [], []
    for i in range(len(df)):
        t = df.index[i]
        if t < conn_time or t > disc_time:
            continue
        base = Base[i]
        ps = Ps[i]
        if pd.isna(base) or pd.isna(ps):
            continue
        min_ps_pmin = min(ps, p_min)
        if base > min_ps_pmin:
            t_steps.append(t)
            p_low.append(min_ps_pmin)
            p_high.append(base)

    if t_steps:
        last_step = t_steps[-1]
        next_step = last_step + step_delta
        if next_step <= disc_time:
            t_steps.append(next_step)
            p_low.append(p_low[-1])
            p_high.append(p_high[-1])
        else:
            t_steps.append(disc_time)
            p_low.append(p_low[-1])
            p_high.append(p_high[-1])
        ax.fill_between(t_steps, p_low, p_high, step='post',
                        color='blue', alpha=0.3, label='Downward Flexibility')

def apply_time_formatting(ax, conn_time, disc_time):
    """
    Adjust x-axis time formatting and set x-limits with buffer.
    """
    prev_hour = (conn_time - pd.Timedelta(hours=1)).replace(minute=0, second=0)
    left_margin = max(prev_hour, conn_time.replace(hour=0, minute=0, second=0))
    next_hour_end = (disc_time + pd.Timedelta(hours=1)).replace(minute=59, second=59)
    day_end = disc_time.replace(hour=23, minute=59, second=59)
    right_margin = min(next_hour_end, day_end)
    ax.set_xlim(left_margin, right_margin)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m %H:%M'))




    