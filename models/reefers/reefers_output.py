import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import math
from agents.reefer_container import ReeferContainer
import json
import re

def getReefersResults(reefer_objects, start_date_str, run_time, time_step):
    """
    Takes a list of ReeferContainer objects, processes their power consumption data,
    and generates a graph showing total power in Kilowatts (kW).
    """
    if not reefer_objects:
        print("No reefer containers were found in the simulation to analyze.")
        return

    print(f"Analyzing and plotting {len(reefer_objects)} reefer containers...")
    
    try:
        sim_start_dt = datetime.strptime(start_date_str, '%d-%m-%Y %H:%M:%S')
    except ValueError:
        sim_start_dt = datetime.strptime(start_date_str, '%d-%m-%Y')


    # --- 1. Process Data from Reefer Logs ---
    all_log_times = set()
    for container in reefer_objects:
        for log in container.power_consumption_log:
            all_log_times.add(log['time'])
    
    if not all_log_times:
        print("No reefer consumption data was logged to plot.")
        return

    max_time = max(all_log_times) if all_log_times else 0
    full_time_range_seconds = np.arange(0, max_time + 900, 900)
    full_time_range_dt = [sim_start_dt + timedelta(seconds=int(t)) for t in full_time_range_seconds]
    
    # Create the main DataFrame to hold power in Watts
    consumption_df_W = pd.DataFrame(index=[c.id for c in reefer_objects], columns=full_time_range_seconds, dtype=float).fillna(0.0)
    
    # Populate the DataFrame with logged power data in Watts
    for container in reefer_objects:
        for log_entry in container.power_consumption_log:
            time_sec = log_entry['time']
            if time_sec in consumption_df_W.columns:
                consumption_df_W.at[container.id, time_sec] = log_entry['power_W']
            
    # Calculate active container count (logic is unchanged)
    active_containers_count = []
    for t_sec in full_time_range_seconds:
        active_count = sum(
            (c.arrival_time_yard is not None and c.departure_time_yard is not None and
             c.arrival_time_yard <= t_sec < c.departure_time_yard)
            for c in reefer_objects
        )
        active_containers_count.append(active_count)
        
    # --- 2. Generate and Save the Graph (with kW) ---
    # Convert DataFrame columns from seconds to datetime objects for plotting
    consumption_df_W.columns = full_time_range_dt
    total_consumption_kW = (consumption_df_W.sum() / 1000).tolist()
    
    fig, ax1 = plt.subplots(figsize=(15, 7))

    total_consumption_kW[-1] = np.nan
    color = 'tab:blue'
    ax1.set_xlabel('Time of Day')
    ax1.set_ylabel("Power Consumption (kW)", color=color)
    ax1.plot(full_time_range_dt, total_consumption_kW, marker="o", linestyle="-", color=color, markersize=3, label="Total Power Consumption (kW)")
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_ylim(bottom=0)
    ax1.grid(True)

    active_containers_count[-1] = np.nan
    ax2 = ax1.twinx()  
    color = 'black'
    ax2.set_ylabel("Active Containers Count", color=color)
    ax2.plot(full_time_range_dt, active_containers_count, color=color, linestyle="-", marker="o", label="Active Containers", markersize=2)
    ax2.tick_params(axis='y', labelcolor=color)
    ax2.set_ylim(bottom=0)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2 , loc="upper left")
    
    plt.title('Overall Reefer Consumption and Active Count')
    fig.tight_layout()
    plt.savefig('output\\additional\\reefer_consumption_graph.png')
    plt.show()
    
    clean_consumption_kW = [x for x in total_consumption_kW if x == x]
    print(f"The total reefer consumption was: {(sum(clean_consumption_kW) / 4000):.2f} MWh")

    # --- 3. Save Detailed JSON Output ---
    
    df_reefers_global = []
    time = 15 * 60 # 15 minutes in seconds
    # TODO: Needs to be replaced with dynamic value from the environment.
    temp_amb = 25  # Ambient temperature in Celsius. 
    idx = 1
    
    if time_step == "15min":
        interval_minutes = 15 
    elif time_step == "1h":
        interval_minutes = 60
    
    for container in reefer_objects:
        
        c1 = math.exp(- container.surfaceArea * container.heatTransCoef * time / (container.mass * container.cargo.specificHeat)) 
        c2 = time/((container.mass * container.cargo.specificHeat))
        c3 = temp_amb * (1-c1)
        
        hourly_baseload_profile = aggregate_power_log_to_snapshots(
            power_log=container.power_consumption_log,
            sim_start_dt=sim_start_dt,
            run_time_seconds=run_time,
            interval_minutes=interval_minutes # Input 
        )
        
        if hourly_baseload_profile:
            # Convert arrival and departure times from seconds to datetime objects
            initial_snapshot_dt = sim_start_dt + timedelta(seconds=int(container.arrival_time_yard))
            final_snapshot_dt = sim_start_dt + timedelta(seconds=int(container.departure_time_yard))

            reefer_data = {
                    "id": f"Reefer {idx}",
                    "bus_id": "bus_reefers",
                    "p_original_profile__MW": hourly_baseload_profile,
                    "snapshots_available": {
                        "initial_snapshot": initial_snapshot_dt.strftime("%Y-%m-%d %H:%M"),
                        "final_snapshot": final_snapshot_dt.strftime("%Y-%m-%d %H:%M")
                    },
                    "c1": c1,
                    "c2": c2,
                    "c3": c3,
                    "p_max__MW": np.interp(container.cUpperBound, ReeferContainer.df_avgEfficiency['temperature'], ReeferContainer.df_avgEfficiency['avg_powerConsumption']) * 10**-6,
                    "p_min__MW": 0,
                    "cop": np.interp(container.setpoint, ReeferContainer.df_avgEfficiency['temperature'], ReeferContainer.df_avgEfficiency['avg_COP']),
                    "t_initial__Celcius": container.initial_temp,
                    "t_final__Celcius": container.temp,
                    "t_max_set_point__Celcius": container.cUpperBound,
                    "t_min_set_point__Celcius": container.cLowerBound,
                    "flex_cost__eur_MWh": 89
                }
            df_reefers_global.append(reefer_data)
            idx += 1 
        
    data = {"reefers": df_reefers_global}

    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    
    # Regex to collapse each baseload entry into a single line
    pattern = r'\{\s*"snapshots":\s*(".*?"),\s*"value":\s*([-+]?[\d]*\.?[\d]+)\s*\}'
    replacement = r'{ "snapshots": \1, "value": \2 }'
    modified_json_str = re.sub(pattern, replacement, json_str)
    
    with open("output//reefers.json", "w", encoding="utf-8") as f:
        f.write(modified_json_str)
           
    
    print("Reefer results plotted and saved.")
    
    

def aggregate_power_log_to_snapshots(power_log, sim_start_dt, run_time_seconds, interval_minutes=60):
    """
    Takes a detailed power log and aggregates it into average power snapshots
    over a given interval (default = 60 min), only for the periods the reefer was present.
    
    Args:
        power_log: list of dicts with {'time': seconds_from_start, 'power_W': value}
        sim_start_dt: datetime of simulation start
        run_time_seconds: total simulation time in seconds
        interval_minutes: bucket size in minutes (e.g., 60 for 1h, 15 for 15min)
    """
    if not power_log:
        return []

    interval_seconds = interval_minutes * 60

    # --- Determine the actual time window of the reefer's presence ---
    first_log_time_s = power_log[0]['time']
    last_log_time_s = power_log[-1]['time']

    # Find the interval number for start and end
    start_bucket = int(first_log_time_s // interval_seconds)
    end_bucket = int(last_log_time_s // interval_seconds)

    # Initialize energy buckets
    energy_joules = {b: 0.0 for b in range(start_bucket, end_bucket + 1)}

    # --- 1. Calculate Total Energy Consumed in Each Relevant Interval ---
    for i in range(len(power_log)):
        step_start_s = power_log[i]['time']
        power_w = power_log[i]['power_W']
        step_end_s = power_log[i+1]['time'] if i + 1 < len(power_log) else run_time_seconds

        for b in range(start_bucket, end_bucket + 1):
            bucket_start_s = b * interval_seconds
            bucket_end_s = (b + 1) * interval_seconds

            overlap_start = max(step_start_s, bucket_start_s)
            overlap_end = min(step_end_s, bucket_end_s)
            overlap_duration = max(0, overlap_end - overlap_start)

            if overlap_duration > 0:
                energy_joules[b] += power_w * overlap_duration

    # --- 2. Convert Energy to Average Power and Format for JSON ---
    json_profile = []
    for b in range(start_bucket, end_bucket + 1):
        total_energy = energy_joules.get(b, 0.0)

        avg_power_watts = total_energy / interval_seconds
        avg_power_mw = avg_power_watts / 1_000_000

        snapshot_time = sim_start_dt + timedelta(seconds=b * interval_seconds)
        snapshot_str = snapshot_time.strftime("%Y-%m-%d %H:%M")

        json_profile.append({
            "snapshots": snapshot_str,
            "value": avg_power_mw
        })

    return json_profile

