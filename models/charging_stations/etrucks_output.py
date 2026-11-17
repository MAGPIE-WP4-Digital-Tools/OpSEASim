import json
import numpy as np
from datetime import datetime, timedelta

def generate_etrucks_json(state, run_time, start_date_str, time_step):
    """
    Generates a combined JSON file for all charging infrastructure and electric trucks,
    unifying Internal and External truck types.
    Supports flexible snapshot intervals (default = 60 min).
    """
    output_data = {
        "e_trucks": {
            "e_trucks_chargers": [],
            "e_trucks": []
        }
    }
    
    try:
        sim_start_dt = datetime.strptime(start_date_str, '%d-%m-%Y %H:%M:%S')
    except ValueError:
        sim_start_dt = datetime.strptime(start_date_str, '%d-%m-%Y')

    if time_step == "15min":
        interval_minutes = 15 
    elif time_step == "1h":
        interval_minutes = 60
    interval_seconds = interval_minutes * 60
    num_buckets = run_time // interval_seconds

    # --- Process All Chargers (IT and ET) ---
    for station_id, config in state.it_station_configs.items():
        output_data['e_trucks']['e_trucks_chargers'].append({
            "id": station_id,
            "charger_type": "it_truck",
            "p_max__MW": config['charge_rate_kw'] / 1000,
            "eff_charging__pu": config['efficiency'],
            "bus_id": "bus_it_charger"
        })

    for station_id, config in state.et_station_configs.items():
        output_data['e_trucks']['e_trucks_chargers'].append({
            "id": station_id,
            "charger_type": "e_truck",
            "p_max__MW": config['charge_rate_kw'] / 1000,
            "eff_charging__pu": config['efficiency'],
            "bus_id": "bus_et_truck_charger"
        })
        
    # --- Helper to create baseload profile ---
    def create_baseload(log, truck_id, run_time, sim_start_dt):
        profile = np.zeros(run_time)
        truck_logs = [specific_log for specific_log in log if specific_log['truck_id'] == truck_id]
        first_charger_id = None
        min_start_time, max_end_time = float('inf'), float('-inf')

        if not truck_logs:
            return [], None, None, None

        for session in truck_logs:
            start = int(session['start_time'])
            end = int(session['end_time'])
            
            min_start_time = min(min_start_time, start)
            max_end_time = max(max_end_time, end)

            power_kw = session.get('actual_power_kw', 0)
            profile[start:end] = power_kw

            if not first_charger_id:
                first_charger_id = session['charger_id']

        snapshots = []
        for b in range(num_buckets):
            bucket_start = b * interval_seconds
            bucket_end = (b + 1) * interval_seconds
            avg_power_kw = np.mean(profile[bucket_start:bucket_end])
            if avg_power_kw > 0:
                snap_time = sim_start_dt + timedelta(seconds=bucket_start)
                snapshots.append({
                    "snapshots": snap_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "value": avg_power_kw / 1000  # Convert to MW
                })
        
        initial_snapshot_dt = sim_start_dt + timedelta(seconds=min_start_time)
        final_snapshot_dt = sim_start_dt + timedelta(seconds=max_end_time)

        return snapshots, first_charger_id, initial_snapshot_dt, final_snapshot_dt

    # --- Process All Trucks (IT and ET) ---
    # Internal Trucks
    it_log = state.it_charging_log
    for it_agent in state.all_it_agents:
        baseload, charger_id, initial_snap, final_snap = create_baseload(it_log, it_agent.it_id, run_time, sim_start_dt)
        
        if not baseload:
            continue

        first_session = next((log for log in it_log if log['truck_id'] == it_agent.it_id), None)
        initial_kwh_at_session = 0
        if first_session:
            kwh_added = first_session['kwh_added']
            final_soc_pct = first_session['final_soc_pct']
            final_kwh = it_agent.battery_capacity_kWh * (final_soc_pct / 100.0)
            initial_kwh_at_session = final_kwh - kwh_added

        output_data['e_trucks']['e_trucks'].append({
            "id": it_agent.it_id,
            "charger_id": charger_id,
            "flex_cost_eur_MWh": 5,
            "p_max_charging__MW": it_agent.max_charge_rate_kw / 1000, 
            "capacity__MWh": it_agent.battery_capacity_kWh / 1000, 
            "initial_SOC__MWh": initial_kwh_at_session / 1000,
            "final_SOC__MWh": it_agent.current_charge_kWh / 1000,
            "p_original_profile__MW": baseload,
            "snapshots_available": {
                "initial_snapshot": initial_snap.strftime("%Y-%m-%d %H:%M"),
                "final_snapshot": final_snap.strftime("%Y-%m-%d %H:%M")
            },
        })

    # External Trucks
    et_log = state.et_charging_log
    for et_agent in state.all_et_agents:
        baseload, charger_id, initial_snap, final_snap = create_baseload(et_log, et_agent.et_id, run_time, sim_start_dt)
        
        if not baseload:
            continue

        first_session = next((log for log in et_log if log['truck_id'] == et_agent.et_id), None)
        initial_kwh_at_session = 0
        if first_session:
            kwh_added = first_session['kwh_added']
            final_soc_pct = first_session['final_soc_pct']
            final_kwh = et_agent.battery_capacity_kWh * (final_soc_pct / 100.0)
            initial_kwh_at_session = final_kwh - kwh_added

        output_data['e_trucks']['e_trucks'].append({
            "id": f"ET_{et_agent.et_id}",
            "charger_id": charger_id,
            "flex_cost_eur_MWh": 1, 
            "p_max_charging__MW": et_agent.max_charge_rate_kw / 1000, 
            "capacity__MWh": et_agent.battery_capacity_kWh / 1000, 
            "initial_SOC__MWh": initial_kwh_at_session / 1000,
            "final_SOC__MWh": et_agent.current_charge_kWh / 1000,
            "p_original_profile__MW": baseload,
            "snapshots_available": {
                "initial_snapshot": initial_snap.strftime("%Y-%m-%d %H:%M"),
                "final_snapshot": final_snap.strftime("%Y-%m-%d %H:%M")
            },
        })
        
    # --- Save to file ---
    with open('output/e_trucks.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Combined and unified charging JSON has been saved to 'output/e_trucks.json' "
          f"with {interval_minutes}-minute snapshots.")