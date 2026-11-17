import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
from itertools import chain
from datetime import datetime, timedelta
from utils.paths import OUTPUT_DIR, DATA_DIR
#
#====================================
# A class for calculating the quay and yard cranes energy demand along a specific day
#=====================================
#
class Cranes:
    def __init__(self):
        # Load crane data from Excel
        cranes_df = pd.read_excel(DATA_DIR / 'cranes.xlsx', sheet_name='Cranes')
        
        # --- Create a single template for QCs based on QC01 ---
        qc01_data = cranes_df[cranes_df['QC_ID'] == 'QC01'].iloc[0]
        self.qc_template = {
            "id": "QC_Template",
            "cycle": int(qc01_data['QC_cycle_[s]']),
            "v_hoist_load_qc": float(qc01_data['v_hoist_load_qc']),
            "v_hoist_no_load_qc": float(qc01_data['v_hoist_no_load_qc']),
            "v_trolley_qc": float(qc01_data['v_trolley_qc'])
        }
        
        # --- Create a single template for YCs based on YC01 ---
        yc01_data = cranes_df[cranes_df['YC_ID'] == 'YC01'].iloc[0]
        self.yc_template = {
            "id": "YC_Template",
            "cycle": int(yc01_data['YC_cycle_[s]']),
            "v_hoist_load_yc": float(yc01_data['v_hoist_load_yc']),
            "v_hoist_no_load_yc": float(yc01_data['v_hoist_no_load_yc']),
            "v_trolley_yc": float(yc01_data['v_trolley_yc'])
        }

        self.crane_params = {    
                "eff_inverter": float(cranes_df['eff_inverter'].dropna().values[0]),
                "eff_motor": float(cranes_df['eff_motor'].dropna().values[0]),
                "eff_gearbox": float(cranes_df['eff_gearbox'].dropna().values[0]),
                "eff_regeneration": float(cranes_df['eff_regeneration'].dropna().values[0]),
                "m_spreader": float(cranes_df['m_spreader'].dropna().values[0]),
                "drum_radius": float(cranes_df['drum_radius'].dropna().values[0]),
                "acc_time_hoist_cont": float(cranes_df['acc_time_hoist_cont'].dropna().values[0]),
                "acc_time_hoist_no_cont": float(cranes_df['acc_time_hoist_no_cont'].dropna().values[0]),
                "acc_time_trolley": float(cranes_df['acc_time_trolley'].dropna().values[0]),
                "idle_power": float(cranes_df['idle_power'].dropna().values[0]),
                "gear_ratio_hoist": float(cranes_df['gear_ratio_hoist'].dropna().values[0]),
                "gear_ratio_trolley": float(cranes_df['gear_ratio_trolley'].dropna().values[0])
            }


    def power_crane(
        self, qc_working, yc_working, run_time, yc_id_map, start_date_str,
        regeneration, interval_minutes=60
    ):        
        time_series = np.arange(run_time)

        energy_func = self.energy_calculation_2 if regeneration else self.energy_calculation_1

        power_series_qc_total = np.zeros(run_time)
        power_series_yc_total = np.zeros(run_time)
        power_series_qc_individual = {}
        power_series_yc_individual = {}

        # --- Quay Crane (QC) Logic ---
        for qc_id, logged_operations in qc_working.items():
            power_series_qc_individual[qc_id] = np.zeros(run_time)
            for log_entry in logged_operations:
                start_time_float, container_mass, qc_hndl_time, _ = log_entry
                end_time = int(start_time_float) + int(qc_hndl_time)
                if end_time > run_time: 
                    continue
                
                power_value_cycle = energy_func(
                    int(qc_hndl_time), container_mass, self.qc_template['v_hoist_load_qc'],
                    self.qc_template['v_hoist_no_load_qc'], self.qc_template['v_trolley_qc'])
                
                power_series_qc_individual[qc_id][int(start_time_float):end_time] += power_value_cycle
                power_series_qc_total[int(start_time_float):end_time] += power_value_cycle

        # --- Yard Crane (YC) Logic ---
        for yc_Num, logged_operations in yc_working.items():
            yc_ID = yc_id_map.get(yc_Num)
            if yc_ID is None: 
                continue
            
            power_series_yc_individual[yc_ID] = np.zeros(run_time)
            for log_entry in logged_operations:
                start_time_float, container_mass, yc_hndl_time_float = log_entry
                duration = int(yc_hndl_time_float)
                end_time = int(start_time_float) + duration
                if end_time > run_time: 
                    continue
                
                power_value_cycle = energy_func(
                    duration, container_mass, self.yc_template['v_hoist_load_yc'],
                    self.yc_template['v_hoist_no_load_yc'], self.yc_template['v_trolley_yc'])
                
                power_series_yc_individual[yc_ID][int(start_time_float):end_time] += power_value_cycle
                power_series_yc_total[int(start_time_float):end_time] += power_value_cycle
        
        # --- Generate JSON output with separate bus IDs ---
        try:
            sim_start_dt = datetime.strptime(start_date_str, '%d-%m-%Y %H:%M:%S')
        except ValueError:
            sim_start_dt = datetime.strptime(start_date_str, '%d-%m-%Y')

        e_not_flexible_loads = []
        interval_seconds = interval_minutes * 60
        num_buckets = run_time // interval_seconds

        # Helper function for both QC and YC
        def process_cranes(power_series_dict, bus_id_prefix):
            for crane_id, power_array in power_series_dict.items():
                p_original_profile = []
                for b in range(num_buckets):
                    start_idx, end_idx = b * interval_seconds, (b + 1) * interval_seconds
                    avg_power_megawatts = np.mean(power_array[start_idx:end_idx]) / 1_000_000
                    timestamp_str = (sim_start_dt + timedelta(seconds=b * interval_seconds)).strftime("%Y-%m-%d %H:%M:%S")
                    p_original_profile.append({"snapshots": timestamp_str, "value": avg_power_megawatts})
                
                crane_obj = {
                    "id": f"crane_{crane_id}",
                    "carrier": "AC",
                    "bus_id": bus_id_prefix,
                    "p_original_profile__MW": p_original_profile
                }
                e_not_flexible_loads.append(crane_obj)

        # Process Quay Cranes
        process_cranes(power_series_qc_individual, "bus_q_cranes")
        # Process Yard Cranes
        process_cranes(power_series_yc_individual, "bus_y_cranes")

        final_json_data = {"e_not_flexible_loads": e_not_flexible_loads}
        
        # Save JSON
        with open(OUTPUT_DIR / "e_not_flexible_loads.json", "w") as f:
            json.dump(final_json_data, f, indent=4)
        
        print(f"INFO: 'e_not_flexible_loads.json' has been created with {interval_minutes}-minute snapshots and separate bus IDs.")
                
        total_power_cranes = power_series_qc_total + power_series_yc_total

        # --- Plotting ---
        total_power_cranes_kw = total_power_cranes / 1000
        plt.figure(figsize=(15, 7))
        plt.plot(time_series, power_series_qc_total / 1000, label='Quay Crane Power (kW)', color='blue')
        plt.plot(time_series, power_series_yc_total / 1000, label='Yard Crane Power (kW)', color='green')
        plt.plot(time_series, total_power_cranes_kw, label='Total Power Consumption (kW)', color='red', linestyle='--')
        plt.xlabel('Time (seconds)')
        plt.ylabel('Power Consumption (kW)')
        plt.title(f'Crane Power Consumption from 0 to {run_time} seconds')
        plt.legend()
        plt.grid(True)
        plt.savefig('output\\additional\\cranes_consumption_graph.png')
        plt.show()

        results = {
            "cranes_output": final_json_data,
            "qc_power": power_series_qc_individual,
            "yc_power": power_series_yc_individual,
            "cranes_total_power": total_power_cranes
        }

        clean_consumption_kW = [x for x in total_power_cranes_kw if x == x]
        print(f"The total crane consumption was: {(sum(clean_consumption_kW) / 3600 / 1000):.2f} MWh")

        return results


    # REGENERATION IS OFF 
    def energy_calculation_1(self, cycle, mass_container, v_hoist_load, v_hoist_no_load, v_trolley):

        def perct(number): # Method to calculate the fraction of times of each phase in our reference cycle (the ref cycle lasts 158 seconds)
            percent=(number/158) 
            return percent
        
        cycle_dict = {'lift_cont_acc': [t for t in range(0, int(round(perct(2) * cycle)))],
          'lift_cont_unif': [t for t in range(int(round(perct(2) * cycle)), int(round(perct(36) * cycle)))],
          'lift_cont_deacc': [t for t in range(int(round(perct(36) * cycle)), int(round(perct(38) * cycle)))],
         #
         'horiz_container_acc': [t for t in range(int(round(perct(38) * cycle)), int(round(perct(42) * cycle)))],
         'horiz_container_unif': [t for t in range(int(round(perct(42) * cycle)), int(round(perct(54) * cycle)))],
         'horiz_container_deacc': [t for t in range(int(round(perct(54) * cycle)), int(round(perct(58) * cycle)))],
         #
         'down_container_acc': [t for t in range(int(round(perct(58) * cycle)), int(round(perct(60) * cycle)))],
         'down_container_unif': [t for t in range(int(round(perct(60) * cycle)), int(round(perct(93) * cycle)))],
         'down_container_deacc': [t for t in range(int(round(perct(93) * cycle)), int(round(perct(95) * cycle)))],
         #
         'lift_no_container_acc': [t for t in range(int(round(perct(95) * cycle)), int(round(perct(99) * cycle)))],
         'lift_no_container_unif': [t for t in range(int(round(perct(99) * cycle)), int(round(perct(111) * cycle)))],
         'lift_no_container_deacc': [t for t in range(int(round(perct(111) * cycle)), int(round(perct(115) * cycle)))],
         #
         'horiz_no_container_acc': [t for t in range(int(round(perct(115) * cycle)), int(round(perct(119) * cycle)))],
         'horiz_no_container_unif': [t for t in range(int(round(perct(119) * cycle)), int(round(perct(131) * cycle)))],
         'horiz_no_container_deacc': [t for t in range(int(round(perct(131) * cycle)), int(round(perct(135) * cycle)))],
         #
         'down_no_container_acc': [t for t in range(int(round(perct(135) * cycle)), int(round(perct(139) * cycle)))],
         'down_no_container_unif': [t for t in range(int(round(perct(139) * cycle)), int(round(perct(154) * cycle)))],
         'down_no_container_deacc': [t for t in range(int(round(perct(154) * cycle)), int(round(perct(158) * cycle)))]}
        
        m_load = mass_container + self.crane_params['m_spreader'] #mass with container
        m_unload = self.crane_params['m_spreader'] #mass without container
        
        #Hoist Function - Módulo de Intensidade das Forças envolvidas
        def hoist_up_power_function(m,v,a,w_1,J_1,w_2,J_2,alpha):
            g_value = 9.81 #gravitational acceleration     
            F_friction = 0 #friction force between the drum and the rope (for now lets neglect it - it can be calculated) 
            F=F_friction + m*g_value + m*abs(a) # [N]
            P_hoist = F*v + w_1*J_1*alpha # [W] 
            P_hoist_motor = (P_hoist/self.crane_params['eff_gearbox'] + w_2*J_2*alpha)/(self.crane_params['eff_inverter']*self.crane_params['eff_motor'])
            return P_hoist_motor
        
        def hoist_down_power_function(m,v,a,w_1,J_1,w_2,J_2,alpha):
            g_value = 9.81 #gravitational acceleration     
            F= m*g_value - m*abs(a) # [N] regenerative braking force (deacceleration) = regenerated power
            P_hoist = F*v - w_1*J_1*alpha # [W] 
            P_hoist_motor = (P_hoist * self.crane_params['eff_gearbox'] + w_2*J_2*alpha) * self.crane_params['eff_inverter'] * self.crane_params['eff_motor']
            return P_hoist_motor

        #To have SI Units - Power in Watts - v in m/s, F in N, w in rad/s, J in Kg.m^2 and dw/dt = alpha in rad/s^2

        #Trolley Function - is the drum included?
        def trolley_power_function(m,v,a,w_2,J_2,alpha):
            g_value = 9.81 #gravitational acceleration
            drag_coeff = 1.05 #drag coefficient of a cube for reference
            rolling_resist_coeff = 0.02 # rolling resistance coefficient of iron on iron (Machinery's Handbook)
            rho_air = 1.225 # Kg/m^3 air density
            area = 0.044 # m^2 considering a TEU container 
            F_wind = 0.5*rho_air*(v**2)*area # [N]
            F_air_resist = F_wind * drag_coeff # [N]
            F_rolling = rolling_resist_coeff *(m*g_value) #normal force times coefficient
            F = F_air_resist + F_rolling + m*abs(a) # [N]
            P_trolley = F*v # [W]  in this movement there is no inertia on the drum (no w_1 or J_1)
            P_trolley_motor = (P_trolley/self.crane_params['eff_gearbox'] + w_2*J_2*alpha)/(self.crane_params['eff_inverter']*self.crane_params['eff_motor'])
            return P_trolley_motor
    
        acc_hoist_load = v_hoist_load/self.crane_params['acc_time_hoist_cont']
        deacc_hoist_load = v_hoist_load/self.crane_params['acc_time_hoist_cont']

        acc_hoist_no_load = v_hoist_no_load/self.crane_params['acc_time_hoist_no_cont']
        deacc_hoist_no_load = v_hoist_no_load/self.crane_params['acc_time_hoist_no_cont']

        acc_trolley_load = v_trolley/self.crane_params['acc_time_trolley']
        deacc_trolley_load = v_trolley/self.crane_params['acc_time_trolley']

        acc_trolley_no_load = v_trolley/self.crane_params['acc_time_trolley']
        deacc_trolley_no_load = v_trolley/self.crane_params['acc_time_trolley']

        # assuming that the trolley acc times are the same with or without load 
        # assuming that trolley speed is the same with or without load


        #Velocity Function - hoisting phase
        def v_hoist(v, a, t):
            if t == 0:
                v[t] = 0
                return 0
            else:
                new_v = v[t-1] + a  
                v[t] = new_v
                return new_v
            
        def v_trolley_function(v,a,t):
            if t == int(round(perct(38) * cycle)):
                v[t] = 0 
                return 0
            else:
                new_v = v[t-1] + a
                v[t] = new_v
                return new_v

        #Drum - Angular Velocity Function
        def vangu(v,r):
            w=v/r
            return w # rad/s
        
        #Hoist and Trolley Machines - Angular Velocity Functions
        def vangu_motor(v,r,gr):
            w=v/r #to calculate the angular velocity of the drum
            w_motor = w*gr
            return w_motor 
             
        #outro código/funçao para Hoist e Trolley Machines, atraves do gear ratio (ver influencia nos resultaods)
        J_drum = 1.7 # Kg.m^2 Inertia for a 0.4m drum 
        J_hoist_mach = 5.2 #Kg.m^2 [1] Typical YC Hoist Motor
        J_trolley_mach = 3.0 #Kg.m^2 (No reference found, assumed value) 

        #time = [] #time vector 
        power_model = np.zeros(len( list(chain(*cycle_dict.values())))) ##List with zeros and the same number of elements as the dictionary (n - keys; i - seconds)(i x n)
        v = np.zeros(len(list(chain(*cycle_dict.values()))))
        idle_power = self.crane_params['idle_power'] #corresponding power to the HVAC and Lighting Systems (ADD AS AN ATTRIBUTE) 

        for i,n in enumerate(power_model):
            #time.append(i+1)
            #
            if i in cycle_dict['lift_cont_acc']: 
                power_model[i] = idle_power + hoist_up_power_function(m=m_load,v=v_hoist(v,acc_hoist_load,i),a=acc_hoist_load,\
                                        w_1=vangu(v_hoist(v,acc_hoist_load,i),self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist(v,acc_hoist_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=acc_hoist_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,acc_hoist_load,i)
            #
            elif i in cycle_dict['lift_cont_unif']: 
                power_model[i] = idle_power + hoist_up_power_function(m=m_load,v=v_hoist_load,a=0,\
                                        w_1=vangu(v_hoist_load,self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist_load,self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=0)
                v[i] = v_hoist_load
            #
            elif i in cycle_dict['lift_cont_deacc']: 
                power_model[i] = idle_power + hoist_up_power_function(m=m_load,v=v_hoist(v,-deacc_hoist_load,i),a=deacc_hoist_load,\
                                        w_1=vangu(v_hoist(v,deacc_hoist_load,i),self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist(v,deacc_hoist_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=deacc_hoist_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,-deacc_hoist_load,i)
            #
            elif i in cycle_dict['horiz_container_acc']: 
                power_model[i] = idle_power + trolley_power_function(m=m_load, v=v_trolley_function(v,acc_trolley_load,i),\
                                            a=acc_trolley_load,w_2= vangu_motor(v_trolley_function(v,acc_trolley_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=acc_trolley_load/self.crane_params['drum_radius'])
                v[i] = v_trolley_function(v,acc_trolley_load,i)
            #
            elif i in cycle_dict['horiz_container_unif']:
                power_model[i] = idle_power + trolley_power_function(m=m_load,v=v_trolley,a=0,\
                                            w_2= vangu_motor(v_trolley,self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=0)
                v[i] = v_trolley
            #
            elif i in cycle_dict['horiz_container_deacc']:
                power_model[i] = idle_power + trolley_power_function(m=m_load, v=v_trolley_function(v,-deacc_trolley_load,i),\
                                            a=deacc_trolley_load,w_2= vangu_motor(v_trolley_function(v,-deacc_trolley_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=deacc_trolley_load/self.crane_params['drum_radius'])
                v[i] = v_trolley_function(v,-deacc_trolley_load,i)
            #
            elif i in cycle_dict['down_container_acc']:
                power_model[i] = idle_power 
                v[i] = v_hoist(v,-acc_hoist_load,i)
            #
            elif i in cycle_dict['down_container_unif']:
                power_model[i] = idle_power 
                v[i] = -v_hoist_load
            #
            elif i in cycle_dict['down_container_deacc']:
                power_model[i] = idle_power 
                v[i] = v_hoist(v,deacc_hoist_load,i) 
            #
            elif i in cycle_dict['lift_no_container_acc']:
                power_model[i]= idle_power + hoist_up_power_function(m=m_unload,v=v_hoist(v,acc_hoist_no_load,i),a=acc_hoist_no_load,\
                                        w_1=vangu(v_hoist(v,acc_hoist_no_load,i),self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist(v,acc_hoist_no_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=acc_hoist_no_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,acc_hoist_no_load,i)
            #
            elif i in cycle_dict['lift_no_container_unif']:
                power_model[i]= idle_power + hoist_up_power_function(m=m_unload,v=v_hoist_no_load,a=0,\
                                        w_1=vangu(v_hoist_no_load,self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist_no_load,self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=0)
                v[i] = v_hoist_no_load
            #
            elif i in cycle_dict['lift_no_container_deacc']:
                power_model[i]= idle_power + hoist_up_power_function(m=m_unload,v=v_hoist(v,-deacc_hoist_no_load,i),a=deacc_hoist_no_load,\
                                        w_1=vangu(v_hoist(v,deacc_hoist_no_load,i),self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist(v,-deacc_hoist_no_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=deacc_hoist_no_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,-deacc_hoist_no_load,i)
            #
            elif i in cycle_dict['horiz_no_container_acc']:
                power_model[i] = idle_power + trolley_power_function(m=m_unload, v= v_trolley_function(v,-acc_trolley_no_load,i),\
                                            a= acc_trolley_no_load,w_2= vangu_motor(v_trolley_function(v, -acc_trolley_no_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=acc_trolley_no_load/self.crane_params['drum_radius'])
                v[i] = v_trolley_function(v, -acc_trolley_no_load,i)
            #
            elif i in cycle_dict['horiz_no_container_unif']:
                power_model[i] = idle_power + trolley_power_function(m=m_unload,v= - v_trolley,a=0,\
                                        w_2= vangu_motor(v_trolley ,self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=0)
                v[i] = - v_trolley 
            #
            elif i in cycle_dict['horiz_no_container_deacc']:
                power_model[i] = idle_power + trolley_power_function(m=m_unload, v= v_trolley_function(v, deacc_trolley_no_load,i),\
                                            a= deacc_trolley_no_load,w_2= vangu_motor(v_trolley_function(v, deacc_trolley_no_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=deacc_trolley_no_load/self.crane_params['drum_radius'])
                v[i] = v_trolley_function(v, deacc_trolley_no_load,i) 
            #
            elif i in cycle_dict['down_no_container_acc']:
                power_model[i] = idle_power 
                v[i] = v_hoist(v,-acc_hoist_no_load,i) 
            #
            elif i in cycle_dict['down_no_container_unif']:
                power_model[i] = idle_power 
                v[i] = -v_hoist_no_load 
            #
            elif i in cycle_dict['down_no_container_deacc']:
                power_model[i] = idle_power
                v[i] = v_hoist(v,deacc_hoist_no_load,i)
        
        return power_model
    






    # REGENERATION IS ON
    def energy_calculation_2(self, cycle, mass_container, v_hoist_load, v_hoist_no_load, v_trolley):

        def perct(number): # Method to calculate the fraction of times of each phase in our reference cycle (the ref cycle lasts 158 seconds)
            percent=(number/158) 
            return percent
        
        cycle_dict = {'lift_cont_acc': [t for t in range(0, int(round(perct(2) * cycle)))],
          'lift_cont_unif': [t for t in range(int(round(perct(2) * cycle)), int(round(perct(36) * cycle)))],
          'lift_cont_deacc': [t for t in range(int(round(perct(36) * cycle)), int(round(perct(38) * cycle)))],
         #
         'horiz_container_acc': [t for t in range(int(round(perct(38) * cycle)), int(round(perct(42) * cycle)))],
         'horiz_container_unif': [t for t in range(int(round(perct(42) * cycle)), int(round(perct(54) * cycle)))],
         'horiz_container_deacc': [t for t in range(int(round(perct(54) * cycle)), int(round(perct(58) * cycle)))],
         #
         'down_container_acc': [t for t in range(int(round(perct(58) * cycle)), int(round(perct(60) * cycle)))],
         'down_container_unif': [t for t in range(int(round(perct(60) * cycle)), int(round(perct(93) * cycle)))],
         'down_container_deacc': [t for t in range(int(round(perct(93) * cycle)), int(round(perct(95) * cycle)))],
         #
         'lift_no_container_acc': [t for t in range(int(round(perct(95) * cycle)), int(round(perct(99) * cycle)))],
         'lift_no_container_unif': [t for t in range(int(round(perct(99) * cycle)), int(round(perct(111) * cycle)))],
         'lift_no_container_deacc': [t for t in range(int(round(perct(111) * cycle)), int(round(perct(115) * cycle)))],
         #
         'horiz_no_container_acc': [t for t in range(int(round(perct(115) * cycle)), int(round(perct(119) * cycle)))],
         'horiz_no_container_unif': [t for t in range(int(round(perct(119) * cycle)), int(round(perct(131) * cycle)))],
         'horiz_no_container_deacc': [t for t in range(int(round(perct(131) * cycle)), int(round(perct(135) * cycle)))],
         #
         'down_no_container_acc': [t for t in range(int(round(perct(135) * cycle)), int(round(perct(139) * cycle)))],
         'down_no_container_unif': [t for t in range(int(round(perct(139) * cycle)), int(round(perct(154) * cycle)))],
         'down_no_container_deacc': [t for t in range(int(round(perct(154) * cycle)), int(round(perct(158) * cycle)))]}
        
        m_load = mass_container + self.crane_params['m_spreader'] #mass with container
        m_unload = self.crane_params['m_spreader'] #mass without container
        
        #Hoist Function - Módulo de Intensidade das Forças envolvidas
        def hoist_up_power_function(m,v,a,w_1,J_1,w_2,J_2,alpha):
            g_value = 9.81 #gravitational acceleration     
            F_friction = 0 #friction force between the drum and the rope (for now lets neglect it - it can be calculated) 
            F=F_friction + m*g_value + m*abs(a) # [N]
            P_hoist = F*v + w_1*J_1*alpha # [W] 
            P_hoist_motor = (P_hoist/self.crane_params['eff_gearbox'] + w_2*J_2*alpha)/(self.crane_params['eff_inverter']*self.crane_params['eff_motor'])
            return P_hoist_motor
        
        def hoist_down_power_function(m,v,a,w_1,J_1,w_2,J_2,alpha):
            g_value = 9.81 #gravitational acceleration     
            F= m*g_value - m*abs(a) # [N] regenerative braking force (deacceleration) = regenerated power
            P_hoist = F*v - w_1*J_1*alpha # [W] 
            P_hoist_motor = ((P_hoist * self.crane_params['eff_gearbox'] + w_2*J_2*alpha) * self.crane_params['eff_inverter'] * self.crane_params['eff_motor'])* self.crane_params['eff_regeneration']
            return P_hoist_motor

        #To have SI Units - Power in Watts - v in m/s, F in N, w in rad/s, J in Kg.m^2 and dw/dt = alpha in rad/s^2

        #Trolley Function - is the drum included?
        def trolley_power_function(m,v,a,w_2,J_2,alpha):
            g_value = 9.81 #gravitational acceleration
            drag_coeff = 1.05 #drag coefficient of a cube for reference
            rolling_resist_coeff = 0.02 # rolling resistance coefficient of iron on iron (Machinery's Handbook)
            rho_air = 1.225 # Kg/m^3 air density
            area = 0.044 # m^2 considering a TEU container 
            F_wind = 0.5*rho_air*(v**2)*area # [N]
            F_air_resist = F_wind * drag_coeff # [N]
            F_rolling = rolling_resist_coeff *(m*g_value) #normal force times coefficient
            F = F_air_resist + F_rolling + m*abs(a) # [N]
            P_trolley = F*v # [W]  in this movement there is no inertia on the drum (no w_1 or J_1)
            P_trolley_motor = (P_trolley/self.crane_params['eff_gearbox'] + w_2*J_2*alpha)/(self.crane_params['eff_inverter']*self.crane_params['eff_motor'])
            return P_trolley_motor
    
        acc_hoist_load = v_hoist_load/self.crane_params['acc_time_hoist_cont']
        deacc_hoist_load = v_hoist_load/self.crane_params['acc_time_hoist_cont']

        acc_hoist_no_load = v_hoist_no_load/self.crane_params['acc_time_hoist_no_cont']
        deacc_hoist_no_load = v_hoist_no_load/self.crane_params['acc_time_hoist_no_cont']

        acc_trolley_load = v_trolley/self.crane_params['acc_time_trolley']
        deacc_trolley_load = v_trolley/self.crane_params['acc_time_trolley']

        acc_trolley_no_load = v_trolley/self.crane_params['acc_time_trolley']
        deacc_trolley_no_load = v_trolley/self.crane_params['acc_time_trolley']

        # assuming that the trolley acc times are the same with or without load 
        # assuming that trolley speed is the same with or without load


        #Velocity Function - hoisting phase
        def v_hoist(v, a, t):
            if t == 0:
                v[t] = 0
                return 0
            else:
                new_v = v[t-1] + a  
                v[t] = new_v
                return new_v
            
        def v_trolley_function(v,a,t):
            if t == int(round(perct(38) * cycle)):
                v[t] = 0 
                return 0
            else:
                new_v = v[t-1] + a
                v[t] = new_v
                return new_v

        #Drum - Angular Velocity Function
        def vangu(v,r):
            w=v/r
            return w # rad/s
        
        #Hoist and Trolley Machines - Angular Velocity Functions
        def vangu_motor(v,r,gr):
            w=v/r #to calculate the angular velocity of the drum
            w_motor = w*gr
            return w_motor 
             
        #outro código/funçao para Hoist e Trolley Machines, atraves do gear ratio (ver influencia nos resultaods)
        J_drum = 1.7 # Kg.m^2 Inertia for a 0.4m drum 
        J_hoist_mach = 5.2 #Kg.m^2 [1] Typical YC Hoist Motor
        J_trolley_mach = 3.0 #Kg.m^2 (No reference found, assumed value) 

        #time = [] #time vector 
        power_model = np.zeros(len( list(chain(*cycle_dict.values())))) ##List with zeros and the same number of elements as the dictionary (n - keys; i - seconds)(i x n)
        v = np.zeros(len(list(chain(*cycle_dict.values()))))
        idle_power = self.crane_params['idle_power'] #corresponding power to the HVAC and Lighting Systems (ADD AS AN ATTRIBUTE) 

        for i,n in enumerate(power_model):
            #time.append(i+1)
            #
            if i in cycle_dict['lift_cont_acc']: 
                power_model[i] = idle_power + hoist_up_power_function(m=m_load,v=v_hoist(v,acc_hoist_load,i),a=acc_hoist_load,\
                                        w_1=vangu(v_hoist(v,acc_hoist_load,i),self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist(v,acc_hoist_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=acc_hoist_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,acc_hoist_load,i)
            #
            elif i in cycle_dict['lift_cont_unif']: 
                power_model[i] = idle_power + hoist_up_power_function(m=m_load,v=v_hoist_load,a=0,\
                                        w_1=vangu(v_hoist_load,self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist_load,self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=0)
                v[i] = v_hoist_load
            #
            elif i in cycle_dict['lift_cont_deacc']: 
                power_model[i] = idle_power + hoist_up_power_function(m=m_load,v=v_hoist(v,-deacc_hoist_load,i),a=deacc_hoist_load,\
                                        w_1=vangu(v_hoist(v,deacc_hoist_load,i),self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist(v,deacc_hoist_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=deacc_hoist_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,-deacc_hoist_load,i)
            #
            elif i in cycle_dict['horiz_container_acc']: 
                power_model[i] = idle_power + trolley_power_function(m=m_load, v=v_trolley_function(v,acc_trolley_load,i),\
                                            a=acc_trolley_load,w_2= vangu_motor(v_trolley_function(v,acc_trolley_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=acc_trolley_load/self.crane_params['drum_radius'])
                v[i] = v_trolley_function(v,acc_trolley_load,i)
            #
            elif i in cycle_dict['horiz_container_unif']:
                power_model[i] = idle_power + trolley_power_function(m=m_load,v=v_trolley,a=0,\
                                            w_2= vangu_motor(v_trolley,self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=0)
                v[i] = v_trolley
            #
            elif i in cycle_dict['horiz_container_deacc']:
                power_model[i] = idle_power + trolley_power_function(m=m_load, v=v_trolley_function(v,-deacc_trolley_load,i),\
                                            a=deacc_trolley_load,w_2= vangu_motor(v_trolley_function(v,-deacc_trolley_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=deacc_trolley_load/self.crane_params['drum_radius'])
                v[i] = v_trolley_function(v,-deacc_trolley_load,i)
            #
            elif i in cycle_dict['down_container_acc']:
                power_model[i] = idle_power + hoist_down_power_function(m=m_load,v=v_hoist(v,-acc_hoist_load,i),a=acc_hoist_load,\
                                        w_1=vangu(v_hoist(v,acc_hoist_load,i),self.crane_params['drum_radius']),J_1=J_drum, w_2= vangu_motor(v_hoist(v,-acc_hoist_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=acc_hoist_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,-acc_hoist_load,i)
            #
            elif i in cycle_dict['down_container_unif']:
                power_model[i] = idle_power + hoist_down_power_function(m=m_load,v=-v_hoist_load,a=0,\
                                        w_1=vangu(v_hoist_load,self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist_load,self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=0)
                v[i] = -v_hoist_load
            #
            elif i in cycle_dict['down_container_deacc']:
                power_model[i] = idle_power + hoist_down_power_function(m=m_load,v=v_hoist(v, deacc_hoist_load,i),a=deacc_hoist_load,\
                                        w_1=vangu(v_hoist(v,deacc_hoist_load,i),self.crane_params['drum_radius']),J_1=J_drum, w_2= vangu_motor(v_hoist(v,deacc_hoist_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=deacc_hoist_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,deacc_hoist_load,i) 
            #
            elif i in cycle_dict['lift_no_container_acc']:
                power_model[i]= idle_power + hoist_up_power_function(m=m_unload,v=v_hoist(v,acc_hoist_no_load,i),a=acc_hoist_no_load,\
                                        w_1=vangu(v_hoist(v,acc_hoist_no_load,i),self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist(v,acc_hoist_no_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=acc_hoist_no_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,acc_hoist_no_load,i)
            #
            elif i in cycle_dict['lift_no_container_unif']:
                power_model[i]= idle_power + hoist_up_power_function(m=m_unload,v=v_hoist_no_load,a=0,\
                                        w_1=vangu(v_hoist_no_load,self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist_no_load,self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=0)
                v[i] = v_hoist_no_load
            #
            elif i in cycle_dict['lift_no_container_deacc']:
                power_model[i]= idle_power + hoist_up_power_function(m=m_unload,v=v_hoist(v,-deacc_hoist_no_load,i),a=deacc_hoist_no_load,\
                                        w_1=vangu(v_hoist(v,deacc_hoist_no_load,i),self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist(v,-deacc_hoist_no_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=deacc_hoist_no_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,-deacc_hoist_no_load,i)
            #
            elif i in cycle_dict['horiz_no_container_acc']:
                power_model[i] = idle_power + trolley_power_function(m=m_unload, v= v_trolley_function(v,-acc_trolley_no_load,i),\
                                            a= acc_trolley_no_load,w_2= vangu_motor(v_trolley_function(v, -acc_trolley_no_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=acc_trolley_no_load/self.crane_params['drum_radius'])
                v[i] = v_trolley_function(v, -acc_trolley_no_load,i)
            #
            elif i in cycle_dict['horiz_no_container_unif']:
                power_model[i] = idle_power + trolley_power_function(m=m_unload,v= - v_trolley,a=0,\
                                        w_2= vangu_motor(v_trolley ,self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=0)
                v[i] = - v_trolley 
            #
            elif i in cycle_dict['horiz_no_container_deacc']:
                power_model[i] = idle_power + trolley_power_function(m=m_unload, v= v_trolley_function(v, deacc_trolley_no_load,i),\
                                            a= deacc_trolley_no_load,w_2= vangu_motor(v_trolley_function(v, deacc_trolley_no_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_trolley']),J_2=J_trolley_mach, alpha=deacc_trolley_no_load/self.crane_params['drum_radius'])
                v[i] = v_trolley_function(v, deacc_trolley_no_load,i) 
            #
            elif i in cycle_dict['down_no_container_acc']:
                power_model[i] = idle_power + hoist_down_power_function(m=m_unload,v=v_hoist(v,-acc_hoist_no_load,i),a=acc_hoist_no_load,\
                                        w_1=vangu(v_hoist(v,acc_hoist_no_load,i),self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist(v,-acc_hoist_no_load,i) ,self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=acc_hoist_no_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,-acc_hoist_no_load,i) 
            #
            elif i in cycle_dict['down_no_container_unif']:
                power_model[i] = idle_power + hoist_down_power_function(m=m_unload,v=-v_hoist_no_load,a=0,\
                                        w_1=vangu(v_hoist_load,self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist_no_load ,self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=0)
                v[i] = -v_hoist_no_load 
            #
            elif i in cycle_dict['down_no_container_deacc']:
                power_model[i] = idle_power + hoist_down_power_function(m=m_unload,v=v_hoist(v,deacc_hoist_no_load,i),a=deacc_hoist_no_load,\
                                        w_1=vangu(v_hoist(v,deacc_hoist_no_load,i),self.crane_params['drum_radius']),J_1=J_drum,w_2= vangu_motor(v_hoist(v,deacc_hoist_no_load,i),self.crane_params['drum_radius'],self.crane_params['gear_ratio_hoist']),J_2=J_hoist_mach, alpha=deacc_hoist_no_load/self.crane_params['drum_radius'])
                v[i] = v_hoist(v,deacc_hoist_no_load,i)
        
        return power_model

    
def getCranesResults(cranes:object, qc_working, yc_working, run_time, yc_id_map, start_date_str, time_step, regeneration): # Add start_date_str
    #
    if time_step == "15min":
        interval_minutes = 15 
    elif time_step == "1h":
        interval_minutes = 60
    total_power_cranes = cranes.power_crane(qc_working, yc_working, run_time, yc_id_map, start_date_str, regeneration=regeneration, interval_minutes=interval_minutes) # Pass map and date
    #
    return total_power_cranes