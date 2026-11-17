import pandas as pd
from datetime import datetime

class VesselScheduleParser:
    """
    Handles the loading, merging, and filtering of vessel schedule data
    from 'calls.csv' and 'vessels.csv' files.
    """
    def __init__(self, calls_file_path, vessels_file_path):
        """
        Initializes the parser by loading and merging the vessel data.
        Args:
            calls_file_path (str or Path): The file path for calls.csv.
            vessels_file_path (str or Path): The file path for vessels.csv.
        """
        self.missing_teu_imos = []
        self.merged_df = self._load_and_merge_data(calls_file_path, vessels_file_path) # terminal name

    def _load_and_merge_data(self, calls_file, vessels_file):
        """
        Private method to handle the data loading and merging process.
        """
        try:
            calls_df = pd.read_csv(calls_file)
            vessels_df = pd.read_csv(vessels_file)

            # --- Data Cleaning and Standardization ---
            # Ensure the merge key ('imo') is the same data type in both files.
            # Converting to string is the most robust method.
            calls_df['imo'] = calls_df['imo'].astype(str)
            vessels_df['imo'] = vessels_df['imo'].astype(str)

            # Convert time columns to datetime objects for accurate comparison.
            calls_df['eta'] = pd.to_datetime(calls_df['eta'])
            calls_df['etd'] = pd.to_datetime(calls_df['etd'])

            # Merge the two dataframes into one.
            merged_data = pd.merge(calls_df, vessels_df, on='imo')
            
            # Identify and store only the UNIQUE problematic IMOs before fixing them
            self.missing_teu_imos = merged_data[merged_data['teus'].isnull()]['imo'].unique().tolist()
            
            # Fill missing values to prevent crashes
            merged_data['teus'] = merged_data['teus'].fillna(0)
            
            print("Successfully loaded and merged vessel data.")
            return merged_data

        except FileNotFoundError as e:
            print(f"ERROR: File not found during parsing: {e.filename}")
            return pd.DataFrame() # Return an empty DataFrame on error
        except KeyError as e:
            print(f"ERROR: A required column was not found during parsing: {e}")
            return pd.DataFrame()

    def get_schedule_for_window(self, start_date_str, end_date_str, terminal_name):
        """
        Filters the merged vessel data to a specific time window. [cite: 385]
        Args:
            start_date_str (str): The start date of the simulation ('dd-mm-yyyy HH:MM:SS'). [cite: 385]
            end_date_str (str): The end date of the simulation ('dd-mm-yyyy HH:MM:SS'). [cite: 386]

        Returns:
            pandas.DataFrame: A DataFrame containing only the vessels active
                              during the specified simulation window. [cite: 387]
        """
        if self.merged_df.empty:
            return pd.DataFrame()

        try:
            sim_start_time = datetime.strptime(start_date_str, '%d-%m-%Y %H:%M:%S')
            sim_end_time = datetime.strptime(end_date_str, '%d-%m-%Y %H:%M:%S')
        except ValueError:
            sim_start_time = datetime.strptime(start_date_str, '%d-%m-%Y')
            sim_end_time = datetime.strptime(end_date_str, '%d-%m-%Y') + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)


        print(f"Filtering schedule between {sim_start_time} and {sim_end_time}...")

        # A vessel is active if its stay overlaps with the simulation window.
        # Condition: (vessel_arrival <= sim_end) AND (vessel_departure >= sim_start)
        filtered_df = self.merged_df[
            (self.merged_df['eta'] <= sim_end_time) &
            (self.merged_df['etd'] >= sim_start_time)
        ].copy().reset_index(drop=True)
        filtered_df = filtered_df[
            (filtered_df['terminal'] == terminal_name) & 
            (filtered_df['ship_type'] != 'Chemical Tanker')
        ]
        
        print(f"Found {len(filtered_df)} active vessels for the simulation window.")
        return filtered_df