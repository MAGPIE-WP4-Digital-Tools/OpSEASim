import pandas as pd
import random
from utils.paths import DATA_DIR
from utils.helpers import to_seconds
from agents.container import Container
from agents.reefer_container import ReeferContainer
from models.reefers.cargo_definitions import generate_reefer_parameters

class ExternalTruckParser:
    """
    Parses the external truck manifest, creating dropoff missions and
    assigning pickup missions from a specific pool (Layer 3).
    """
    def __init__(self, env, dry_l2_blocks, reefer_l2_blocks, container_location_map, all_created_reefers_list):
        self.env = env
        self.dry_l2_blocks = dry_l2_blocks
        self.reefer_l2_blocks = reefer_l2_blocks
        self.container_location_map = container_location_map 
        self.master_reefer_list = all_created_reefers_list
        
        try:
            self.truck_schedule_df = pd.read_excel(DATA_DIR / 'inputs.xlsx', sheet_name='ET_Schedule')
            print("Successfully loaded 'External_Trucks' schedule from inputs.xlsx.")
        except (FileNotFoundError, ValueError):
            print("Warning: 'External_Trucks' sheet not found.")
            self.truck_schedule_df = None

    def _generate_mission_for_truck(self, reefer_ratio):
        """Generates a random mission, now with a reefer ratio for dropoffs."""
        mission_type = random.choices(population=['pickup', 'dropoff'], weights=[0.5, 0.5], k=1)[0]
        
        if mission_type == 'pickup':
            # Decide if this pickup should be a reefer or dry based on reefer_ratio
            is_reefer_pickup = random.random() < reefer_ratio

            if is_reefer_pickup and self.reefer_l2_blocks:
                # Only consider containers in reefer L2 blocks
                pickup_candidates = [cid for cid, blk_id in self.container_location_map.items()
                            if blk_id in self.reefer_l2_blocks]
            else:
                # Only consider containers in dry L2 blocks
                pickup_candidates = [cid for cid, blk_id in self.container_location_map.items()
                            if blk_id in self.dry_l2_blocks]

            if not pickup_candidates:
                return None  # Cannot create a pickup mission if no containers are available

            container_id = random.choice(pickup_candidates)
            target_block_id = self.container_location_map[container_id]
            return {"mission": "pickup", "container": container_id, "block_id": target_block_id}

        else: # Dropoff Mission
            is_reefer = random.random() < reefer_ratio
            
            # --- Logic for Reefer Dropoff ---
            if is_reefer and self.reefer_l2_blocks:
                reefer_params = generate_reefer_parameters()
                new_container = ReeferContainer(
                    env=self.env, 
                    container_id=f"ET_RE_{random.randint(1000,9999)}",
                    vessel_id="ET_DROPOFF", 
                    mass=random.uniform(17000, 23000),
                    **reefer_params
                )
                # Add the new reefer to the master list for thermal simulation
                new_container.initial_temp = new_container.cUpperBound - 0.1 # TODO Make the imported reefer parameters start at T_max-0.1 instead of modifying afterwards.
                self.master_reefer_list.append(new_container)
                target_block_id = random.choice(self.reefer_l2_blocks)
                
                return {"mission": "dropoff", "container": new_container, "block_id": target_block_id}
            
            # --- Logic for Dry Dropoff (fallback) ---
            elif self.dry_l2_blocks:
                new_container = Container(
                    env=self.env, 
                    container_id=f"ET_DRY_{random.randint(1000,9999)}",
                    vessel_id="ET_DROPOFF", 
                    mass=random.uniform(17000, 23000)
                )
                target_block_id = random.choice(self.dry_l2_blocks)
                
                return {"mission": "dropoff", "container": new_container, "block_id": target_block_id}

            else:
                # If there are no suitable L2 blocks for dropoff, no mission can be created
                return None

    def get_truck_schedule(self):
        if self.truck_schedule_df is None: 
            return {}
            
        et_scheduling = {}
        for i, row in self.truck_schedule_df.iterrows():
            # Generate the operational mission for this truck
            mission_details = self._generate_mission_for_truck(reefer_ratio=0.4)
            if mission_details is None: 
                continue # Skip if a mission couldn't be generated

            et_scheduling[i] = {
                # Data from the file
                "early_arrival_time": to_seconds(row['early_arrival_time']),
                "operation_time": to_seconds(row['operation_time']),
                "initial_charge_pct": float(row['initial_SOC']),
                "target_charge_kWh": float(row['capacity__kWh']) * (float(row['final_SOC']) / 100.0),
                "battery_capacity_kWh": float(row['capacity__kWh']),
                "charge_rate_kw": float(row['p_nom_charging__kW']),
                # "charging_efficiency": float(row['charging_efficiency__pu']),
                
                # Generated mission data
                "mission": mission_details['mission'],
                "target_container": mission_details['container'],
                "target_block_id": mission_details['block_id']
            }
        return et_scheduling
