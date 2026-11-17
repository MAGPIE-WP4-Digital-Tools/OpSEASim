import pandas as pd
import random
import string
from utils.paths import DATA_DIR

class VesselManifestParser:
    def __init__(self, env, all_l1_dry_blocks, all_l1_reefer_blocks, 
                 initial_containers_by_block, all_created_reefers_list, container_location_map,
                 ships_call_df, start_date, logger, yard_block_stores_ref):
        self.env = env
        self.all_l1_dry_blocks = all_l1_dry_blocks
        self.all_l1_reefer_blocks = all_l1_reefer_blocks
        self.initial_containers_by_block = initial_containers_by_block
        self.master_reefer_list = all_created_reefers_list
        self.container_location_map = container_location_map
        self.logger = logger
        self.yard_block_stores = yard_block_stores_ref
        
        # Store schedule info for ETA checks
        self.ships_call_df = ships_call_df
        self.start_date_ts = pd.Timestamp(start_date)

        # Track used containers to ensure they are not assigned to more than one vessel
        self.used_export_container_ids = set()

        try:
            self.vessel_manifests_df = pd.read_excel(DATA_DIR / 'inputs.xlsx', sheet_name='Vessel_Manifests')
            print("Successfully loaded 'Vessel_Manifests' from inputs.xlsx.")
        except (FileNotFoundError, ValueError):
            print("Warning: 'Vessel_Manifests' sheet not found. A random manifest will be generated.")
            self.vessel_manifests_df = None

    def _generate_plate_id(self, owner_code="IMPV"):
        random_part = ''.join(random.choices(string.digits, k=7))
        return f"{owner_code}{random_part}"

    def generate_manifest_for_vessel(self, call_id, vessel_obj):
        """
        Generates a complete, random manifest for a single vessel.
        """
        
        # --- Check if the vessel is a container ship ---
        vessel_visit_info = self.ships_call_df[self.ships_call_df['call'] == call_id]
        if vessel_visit_info.empty or vessel_visit_info.iloc[0]['ship_type'] != 'Container Ship':
            return [] # Return an empty manifest for non-container ships
        
        visit_details = vessel_visit_info.iloc[0]
        imo = visit_details['imo']
        
        # --- 1. Define total containers and ratios ---
        # total_containers = random.randint(700, 1000)
        total_containers = 1400

        # Check if the vessel's ETA is at the start of the simulation
        eta_timestamp = visit_details['eta'] 
        eta_seconds = (eta_timestamp - self.start_date_ts).total_seconds()
        sim_eta = int(eta_seconds) if eta_seconds >= 0 else 0
        
        if sim_eta == 0:
            real_eta = vessel_obj.real_eta
            real_etd = vessel_obj.real_etd
            visit_ratio = real_etd / (abs(real_eta) + real_etd)
            total_containers = int(total_containers * visit_ratio) 

        import_ratio = 60/100  # 60% of containers will be imports
        reefer_ratio = 0.05

        num_imports = int(total_containers * import_ratio)
        num_exports = total_containers - num_imports

        num_reefer_imports = int(num_imports * reefer_ratio)
        num_dry_imports = num_imports - num_reefer_imports

        num_reefer_exports = int(num_exports * reefer_ratio)
        num_dry_exports = num_exports - num_reefer_exports

        # --- 2. Select Dedicated Blocks for This Vessel ---

        # For Imports (where discharging containers will be placed) 
        num_dry_import_blocks = 999
        num_reefer_import_blocks = 999
        k_dry_import = min(num_dry_import_blocks, len(self.all_l1_dry_blocks))
        k_reefer_import = min(num_reefer_import_blocks, len(self.all_l1_reefer_blocks))

        dedicated_import_dry_blocks = random.sample(self.all_l1_dry_blocks, k=k_dry_import) if k_dry_import > 0 else []
        dedicated_import_reefer_blocks = random.sample(self.all_l1_reefer_blocks, k=k_reefer_import) if k_reefer_import > 0 else []

        # For Exports (where loading containers will be sourced from) 
        num_dry_export_blocks = 999
        num_reefer_export_blocks = 999
        k_dry_export = min(num_dry_export_blocks, len(self.all_l1_dry_blocks))
        k_reefer_export = min(num_reefer_export_blocks, len(self.all_l1_reefer_blocks))

        dedicated_export_dry_blocks = random.sample(self.all_l1_dry_blocks, k=k_dry_export) if k_dry_export > 0 else [] 
        dedicated_export_reefer_blocks = random.sample(self.all_l1_reefer_blocks, k=k_reefer_export) if k_reefer_export > 0 else [] 

        # --- 3. Create Export Pools from Dedicated Blocks ---
        # Create a pool of available containers ONLY from these dedicated blocks 
        available_dry_exports = []
        for block_id in dedicated_export_dry_blocks:
            # Use the live yard stores
            for container in self.yard_block_stores[block_id].items:
                if not container.assigned: 
                    available_dry_exports.append(container) 
        random.shuffle(available_dry_exports) 

        available_reefer_exports = []
        for block_id in dedicated_export_reefer_blocks:
            # Use the live yard stores
            for container in self.yard_block_stores[block_id].items:
                if not container.assigned: 
                    available_reefer_exports.append(container) 
        random.shuffle(available_reefer_exports)

        # --- 4. Generate IMPORT containers (discharges) ---
        all_manifest_data = []
        for _ in range(num_dry_imports):
            destination_block = random.choice(dedicated_import_dry_blocks) if dedicated_import_dry_blocks else None 
            all_manifest_data.append({
                'vessel_id': call_id, 'container_id': self._generate_plate_id(),
                'mass': random.uniform(5000, 25000), 'container_type': 'dry',
                'direction': 'IMPORT', 'destination_block': destination_block
            })

        for _ in range(num_reefer_imports):
            destination_block = random.choice(dedicated_import_reefer_blocks) if dedicated_import_reefer_blocks else None 
            all_manifest_data.append({
                'vessel_id': call_id, 'container_id': self._generate_plate_id(),
                'mass': random.uniform(5000, 25000), 'container_type': 'reefer',
                'direction': 'IMPORT', 'destination_block': destination_block
            })

        # --- 5. Generate EXPORT manifest (loads) ---
        for _ in range(num_dry_exports):
            if not available_dry_exports:
                self.logger.log(self.env, "Manifest_Warning", vessel_id=imo, 
                                extra_info=f"Ran out of available dry export containers from dedicated blocks for vessel {imo} with call {call_id}.")
                break
            container_to_load = available_dry_exports.pop()
            container_to_load.assigned = True
            all_manifest_data.append({
                'vessel_id': call_id, 'container_id': container_to_load.id, 'mass': container_to_load.mass,
                'container_type': 'dry', 'direction': 'EXPORT', 'destination_block': -1
            })

        for _ in range(num_reefer_exports):
            if not available_reefer_exports:
                self.logger.log(self.env, "Manifest_Warning", vessel_id=imo, 
                                extra_info=f"Ran out of available reefer export containers from dedicated blocks for vessel {imo} with call {call_id}.")
                break
            container_to_load = available_reefer_exports.pop()
            container_to_load.assigned = True
            all_manifest_data.append({
                'vessel_id': call_id, 'container_id': container_to_load.id, 'mass': container_to_load.mass,
                'container_type': 'reefer', 'direction': 'EXPORT', 'destination_block': -1
            })
        
        random.shuffle(all_manifest_data) 
        return all_manifest_data