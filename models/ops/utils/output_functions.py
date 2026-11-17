import pandas as pd
import json
import matplotlib.pyplot as plt
from datetime import timedelta
import os
from .vessel_functions import ops_min_energy, ops_nom_power, ops_min_power, ops_base, ops_up, ops_down, insert_ops_boundaries, plot_upward_flexibility, plot_downward_flexibility, apply_time_formatting
from utils.paths import OUTPUT_DIR


def json_output(vessels, ops_data, time_step):
    """Create .json output file"""
    pass
    # 1. Initialize the new output structure
    output = {
        "ops_vessels": {
            "ops": [],
            "vessels": []
        }
    }
    
    # 2. Create and add the OPS charger list
    for _, ops_row in ops_data.iterrows():
        charger_info = {
            "id": f"ops_{ops_row['ops_id']}",
            "charger_type": "ops",
            "p_nom__MW": ops_row['max_power_kW'] / 1000,
            "bus_id": "bus_ops"
        }
        output["ops_vessels"]["ops"].append(charger_info)

    # 3. Fill the "vessels" list with the correct data structure
    for call_id, vessel_obj in vessels.items():
        # This is the section you correctly identified. It will now work because the loop is correct.
        df = vessel_obj.power_demand.copy()
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        conn_time = vessel_obj.ops_connection
        disc_time = vessel_obj.ops_disconnection

        # The rest of the logic inside this loop was already correct and can remain.
        df_in_window = df[(df['Datetime'] >= conn_time) & (df['Datetime'] <= disc_time)]
        df_in_window.set_index('Datetime', inplace=True)
        filtered_df = df_in_window.resample(time_step, label='left', closed='left').max()
        filtered_df = filtered_df[filtered_df["OPS Power Demand (MW)"] != 0]

        e_min, T_berth = ops_min_energy(filtered_df, vessel_obj.flexibility, column="OPS Power Demand (MW)")
        # Pass the vessel object itself to the helper functions
        p_nom = ops_nom_power(vessel_obj)
        p_min = ops_min_power(vessel_obj)
        baseload_profile = ops_base(e_min, T_berth, p_min, filtered_df, column="P_OPS_base (MW)")
        upward_flex = ops_up(baseload_profile, p_nom)
        downward_flex = ops_down(baseload_profile, p_min, e_min, T_berth)

        vessel_info = {
            # Use the call_id or a more descriptive name for the id
            "id": f"{vessel_obj.name}_{call_id}",
            "ops_id": f"ops_{vessel_obj.ops_id}",
            "min_energy__MWh": e_min,
            "p_nom__MW": p_nom,            
            "flex_cost__eur_MWh": 5,
            "snapshots_available": {
                "initial_snapshot": conn_time.strftime('%Y-%m-%d %H:%M'),
                "final_snapshot": disc_time.strftime('%Y-%m-%d %H:%M')
            },
            "p_original_profile__MW": [
                {"snapshots": dt.strftime('%Y-%m-%d %H:%M'), "value": float(power)}
                for dt, power in zip(baseload_profile.index, baseload_profile['P_OPS_base (MW)'])
            ],
            "upward_flexibility__MW": [
                {"snapshots": dt.strftime('%Y-%m-%d %H:%M'), "value": float(power)}
                for dt, power in zip(upward_flex.index, upward_flex['Upward_profile'])
            ],
            "downward_flexibility__MW": [
                {"snapshots": dt.strftime('%Y-%m-%d %H:%M'), "value": float(power)}
                for dt, power in zip(upward_flex.index, downward_flex['Downward_profile'])
            ],
        }

        output["ops_vessels"]["vessels"].append(vessel_info)


    # 4. Save the output file with a static name
    filename = "ops_vessels.json" # Using a static filename
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, "w") as f:
        json.dump(output, f, indent=4)
    print(f"INFO: '{filename}' has been created.")


def flex_output(vessels, ops_data, time_step, save, plot):
    for call_id, vessel_obj in vessels.items():
        # Prepare and filter time series
        df = vessel_obj.power_demand.copy()
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        conn_time = vessel_obj.ops_connection
        disc_time = vessel_obj.ops_disconnection

        # Filter data within OPS connection/disconnection window and resample
        df_in_window = df[(df['Datetime'] >= conn_time) & (df['Datetime'] <= disc_time)]
        df_in_window.set_index('Datetime', inplace=True)
        filtered_df = df_in_window.resample(time_step, label='left', closed='left').max()
        filtered_df = filtered_df[filtered_df["OPS Power Demand (MW)"] != 0]

        # Compute energy and power constraints
        e_min, T_berth = ops_min_energy(filtered_df, vessel_obj.flexibility, column="OPS Power Demand (MW)")
        p_nom = ops_nom_power(vessel_obj)
        p_min = ops_min_power(vessel_obj)
        filtered_df = ops_base(e_min, T_berth, p_min, filtered_df, column="P_OPS_base (MW)")

        # Ensure OPS connection/disconnection times are included in index
        filtered_df = insert_ops_boundaries(filtered_df, conn_time, disc_time)
        filtered_df = filtered_df.sort_index()

        # Skip plotting if not requested
        if not (plot or save):
            continue

        # Prepare data for plotting
        Ps = filtered_df["OPS Power Demand (MW)"].values
        Base = filtered_df["P_OPS_base (MW)"].values
        step_delta = pd.to_timedelta(time_step)
        Emin = e_min / T_berth

        # Create figure and axes
        fig, ax = plt.subplots(figsize=(15, 7))

        # Plot step curves and reference lines
        ax.step(filtered_df.index, Ps, where='post', label=r'$P^s$', linewidth=2, color='orange')
        ax.step(filtered_df.index, Base, where='post', label='Base Load', linestyle='--', linewidth=2, color='gray')
        ax.axhline(p_min, color='black', linestyle='dotted', linewidth=1, label=r'$P_{min}$')
        ax.axhline(p_nom, color='black', linestyle='dotted', linewidth=1, label=r'$P_{OPS}$')
        ax.axvline(conn_time, color='red', linestyle='--', label="OPS Connection")
        ax.axvline(disc_time, color='red', linestyle='--', label="OPS Disconnection")

        # Plot upward and downward flexibility
        plot_upward_flexibility(ax, filtered_df, Ps, Base, conn_time, disc_time)
        plot_downward_flexibility(ax, filtered_df, Ps, Base, p_min, conn_time, disc_time, step_delta)

        # Plot minimum energy area
        ax.fill_between(filtered_df.index, 0, Emin, step='post', hatch='////',
                        edgecolor='gray', facecolor='none', linewidth=0, label=r'$E_{min}$')

        # Time formatting and layout
        apply_time_formatting(ax, conn_time, disc_time)
        ax.set_xlabel("Time")
        ax.set_ylabel("Power (MW)")
        ax.set_title(f"OPS Power Profile - {vessel_obj.name} - Flexibility - {vessel_obj.flexibility}")
        ax.set_ylim(0, max(p_nom, max(Ps)) + 0.5)
        ax.legend(loc='upper right')
        ax.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()

        # Save and/or show plot
        if save:
            filename = OUTPUT_DIR / f"additional/OPS Power Profile - {vessel_obj.name} - {vessel_obj.flexibility}.png"
            plt.savefig(filename, dpi=300)
        if plot:
            plt.show()
        plt.close(fig)

def generate_excel(vessels, time_step):
    # To print excell files of consumption
    
    # --- FAILSAFE ---
    # If the vessels dictionary is empty, stop processing.
    if not vessels:
        print("Warning: No vessels in OPS found. Skipping Excel generation.")
        return  # Exit the function early
    
    
    # Initialize a list to collect dataframes for each vessel
    dfs = []
    
    for imo, vessel_obj in vessels.items():
        df = vessel_obj.power_demand.copy()
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        df.set_index('Datetime', inplace=True)
    
        # Resample and clean
        ship_df = df.resample(time_step, label='left', closed='left').max().reset_index()
        ship_df = ship_df.drop(columns=['Ship Power Demand (MW)'], errors='ignore')
    
        # Add IMO and reorder
        ship_df['IMO'] = imo
        ship_df = ship_df[['Datetime', 'IMO', 'OPS Power Demand (MW)']]
    
        dfs.append(ship_df)
            
    # Final concatenation, with duplicates removed
    excel_df = pd.concat(dfs, axis=0).drop_duplicates(subset=['Datetime', 'IMO'])
    
    # Optional: sort by time and IMO
    excel_df = excel_df.sort_values(['Datetime', 'IMO']).reset_index(drop=True)
    
    # Define output path for Excel file
    output_path = OUTPUT_DIR / "additional/ops_power_profile.xlsx"
    
    # Save the final dataframe to Excel
    excel_df.to_excel(output_path, index=False)
    
    data={
        imo: {
            'IMO': vessel.imo, 
            'Name': vessel.name,
            'Ship_Type': vessel.ship_type,
            'Arrival': vessel.eta,
            'Departure': vessel.etd,
            'GT': vessel.gt,
            'DWT': vessel.dwt,
            'TEUS': vessel.teus,
            'ME (kW)': vessel.me,
            'Breadth': vessel.breadth,
            'Depth': vessel.depth,
            'LOA': vessel.loa,
            'Velocity (knots)': vessel.velocity,
            'POB': vessel.pob,
            'Reefers': vessel.reefers,
            'Flexibility': vessel.flexibility,
            'OPS_ID': vessel.ops_id,
            'OPS_Nominal_Power': vessel.ops_nom_power,
            'OPS_Min_Power': vessel.ops_min_power,
            'OPS_Connection': vessel.ops_connection,
            'OPS_Disconnection': vessel.ops_disconnection
        }
        for imo, vessel in vessels.items()
    }

    ship_data = pd.DataFrame(data).T
    ship_data = ship_data.reset_index(drop=True)
    filename = OUTPUT_DIR / "additional/ship_data.xlsx"
    ship_data.to_excel(filename, index=False)


def plot_terminal_data(vessels, time_step, terminal_name, save, plot):
    plt.figure(figsize=(15, 7))

    total_energy = 0 # MWh
    
    for imo in vessels.keys():
        df = vessels[imo].power_demand.copy()
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        df.set_index('Datetime', inplace=True)

        # Resample to averages (change to '1min' to '2min' to '5min' to '10min' or '15min', if we need precision just use 's')
        df_resampled = df.resample('15min').mean().reset_index() # ! TODO Should be dynamic.

        plt.plot(df_resampled['Datetime'], df_resampled['OPS Power Demand (MW)'],
                label=vessels[imo].name)
        
        vessel_energy = (df_resampled['OPS Power Demand (MW)'] * 0.25).sum() # 15 minutes is 0.25 of an hour
        total_energy += vessel_energy
        
    print(f"OPS Energy Consumption: {total_energy:.2f} MWh") 

    plt.xlabel("Hours", fontsize=14)
    plt.ylabel("Power [MW]", fontsize=14)
    plt.title(f"OPS Power Demand - {terminal_name}", fontsize=16)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    # Save and/or show plot
    if save:
        filename = OUTPUT_DIR / f"additional/{terminal_name}.png"
        plt.savefig(filename, dpi=300)
    if plot:
        plt.show()
    plt.close()