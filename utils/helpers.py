import json
from datetime import datetime, timedelta
from utils.paths import OUTPUT_DIR
import pandas as pd

def to_seconds(time_value):
    """
    Converts a time value (like a pandas Timestamp or datetime.time) 
    into an integer representing the total number of seconds.
    """
    # Return 0 if the value from the spreadsheet is empty
    if pd.isna(time_value):
        return 0
    
    # If string, try to parse
    if isinstance(time_value, str):
        try:
            time_value = pd.to_datetime(time_value)
        except Exception:
            raise TypeError(f"Unsupported string format: {time_value}")

    # If the object has hour, minute, and second attributes, calculate total seconds
    if hasattr(time_value, 'hour'):
        return time_value.hour * 3600 + time_value.minute * 60 + time_value.second

    # If it's already a number, just ensure it's an integer
    if isinstance(time_value, (int, float)):
        return int(time_value)

    # If it's none of the above, raise an error
    raise TypeError(f"Unsupported type for time conversion: {type(time_value)}")

def generate_general_config(start_date_str, run_time_seconds, time_step_str):
    """
    Generates the general_config.json file with simulation metadata.
    """
    try:
        start_dt = datetime.strptime(start_date_str, '%d-%m-%Y %H:%M:%S')
    except ValueError:
        start_dt = datetime.strptime(start_date_str, '%d-%m-%Y')
        
    end_dt = start_dt + timedelta(seconds=run_time_seconds)

    config = {
        "general_config": {
            "snapshots": {
                "initial_snapshot": start_dt.strftime("%Y-%m-%d %H:%M"),
                "final_snapshot": end_dt.strftime("%Y-%m-%d %H:%M")
            },
            "time_granularity": time_step_str
        }
    }
    
    filepath = OUTPUT_DIR / "general_config.json"
    with open(filepath, "w") as f:
        json.dump(config, f, indent=4)
    
    print(f"INFO: '{filepath.name}' has been created.")