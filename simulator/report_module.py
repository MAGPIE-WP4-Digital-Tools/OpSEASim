from agents.reefer_container import ReeferContainer
from models.charging_stations.etrucks_output import generate_etrucks_json
from utils.helpers import generate_general_config
from utils.simulation_stats import generate_yard_report, generate_yard_operations_report, generate_quay_operations_report
from models.reefers.reefers_output import getReefersResults
from models.cranes.cranes import Cranes, getCranesResults
from models.charging_stations.charging_stations import getChargingStationsResults
from models.ops.vessels import getOpsResults
from models.ops.utils.models_functions import create_vessels


class ReportModule:
    def __init__(self, simulation_manager):
        self.configuration = simulation_manager.configuration
        self.simulation_manager = simulation_manager

    def initial_yard_state(self):
        # print("\n--- Initial Yard State ---")
        initial_report = generate_yard_report(self.simulation_manager.state.yard_block_stores, self.simulation_manager.state.yc_id_map)
        # print(initial_report)
        with open("output/additional/initial_yard_state.txt", "w") as f:
            f.write(initial_report)

    def output(self):
        state = self.simulation_manager.state
        terminal = self.simulation_manager.terminal
        start_date = self.configuration["start_date"]
        end_date = self.configuration["end_date"]
        run_time = self.configuration["run_time"]
        time_step = self.configuration["time_step"]
        
        # print("\n--- Final Yard State ---")
        final_report = generate_yard_report(state.yard_block_stores, state.yc_id_map)
        # print(final_report)
        with open("output/additional/final_yard_state.txt", "w") as f:
            f.write(final_report)
            
        ycs_report = generate_yard_operations_report(state.all_yc_agents, state.yc_agent_working_stats, run_time)
        qcs_report = generate_quay_operations_report(state.qc_working, run_time)
        print(ycs_report)
        print(qcs_report)
        with open("output/additional/YCs_summary.txt", "w") as f:
            f.write(ycs_report)

        generate_general_config(start_date, run_time, time_step)

        df_logs = self.simulation_manager.logger.get_dataframe()
        df_logs.to_excel("output/additional/logs.xlsx")

        # --- Post-Processing & Plotting ---
        all_simulated_reefers = state.all_created_reefers
        for container in all_simulated_reefers:
            if isinstance(container, ReeferContainer) and container.departure_time_yard is None:
                container.set_departure_time(run_time)
                
        getReefersResults(all_simulated_reefers, start_date, run_time, time_step)
        getCranesResults(Cranes(), state.qc_working, state.yc_agent_working_stats, run_time, state.yc_id_map, start_date, time_step, regeneration=state.terminal.regeneration)

        if state.it_station_power_profiles:
            getChargingStationsResults(state.it_station_power_profiles, run_time, type= 'IT', title='Power Consumption of Internal Truck (IT) Stations')
        if state.et_station_power_profiles:
            getChargingStationsResults(state.et_station_power_profiles, run_time, type= 'ET', title='Power Consumption of External Truck (ET) Stations')
        generate_etrucks_json(state, run_time, start_date, time_step)

        # --- OPS Analysis ---

        print("\n--- Generating Onshore Power Supply (OPS) Results ---")
        getOpsResults(
            terminal.ops_data, 
            start_date, 
            end_date, 
            'ship_model', 
            time_step, 
            terminal.name,  
            schedule=state.active_vessels_df,
            parameters=state.ops_vessel_log,
            save=True, 
            plot=True
        )
        
        