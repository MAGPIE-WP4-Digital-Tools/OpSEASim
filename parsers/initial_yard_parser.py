import pandas as pd
import random
import string
from utils.paths import DATA_DIR
from agents.container import Container
from agents.reefer_container import ReeferContainer
from models.reefers.cargo_definitions import generate_reefer_parameters

class InitialYardParser:
    def __init__(self, env, terminal_layout, all_created_reefers_list):
        self.env = env
        self.terminal_layout = terminal_layout
        self.master_reefer_list = all_created_reefers_list
        self.initial_containers_by_block = {}
        self.container_location_map = {}
        self.export_pool_l1_dry = []
        self.export_pool_l1_reefer = []
        self.import_pool_layer2 = []

        try:
            self.initial_yard_df = pd.read_excel(DATA_DIR / 'inputs.xlsx', sheet_name='Initial_Yard_Inventory')
            print("Successfully loaded 'Initial_Yard_Inventory' from inputs.xlsx.")
        except (FileNotFoundError, ValueError):
            print("Warning: 'Initial_Yard_Inventory' sheet not found. A random yard inventory will be generated.")
            self.initial_yard_df = None

    def _generate_plate_id(self, owner_code="YARD"):
        random_part = ''.join(random.choices(string.digits, k=7))
        return f"{owner_code}{random_part}"

    def generate_random_inventory(self, containers_per_block, reefer_ratio):
        print(f"Generating random initial inventory for {len(self.terminal_layout.ycs)} yard blocks...")
        yard_data = []
        occupancy_factor = 0.6
        containers_per_block = int(25 * 6 * 5 * occupancy_factor) #based on this terminal aerial view....should be an input
        reefer_ratio = 0.10
        dry_blocks = {1: [], 2: []}
        reefer_blocks = {1: [], 2: []}

        for i, yc_id in enumerate(self.terminal_layout.ycs.keys()):
            yc_info = self.terminal_layout.ycs[yc_id]
            layer = yc_info.get('layer', 1)
            block_type = yc_info.get('block_type', 'Dry')
            if layer in [1, 2]:
                if block_type == 'Reefer':
                    reefer_blocks[layer].append(i)
                else:
                    dry_blocks[layer].append(i)

        for layer in [1, 2]:
            all_blocks_in_layer = dry_blocks[layer] + reefer_blocks[layer]
            for block_id in all_blocks_in_layer:
                for _ in range(containers_per_block):
                    is_reefer = random.random() < reefer_ratio
                    if is_reefer and reefer_blocks[layer]:
                        target_block = block_id if block_id in reefer_blocks[layer] else random.choice(reefer_blocks[layer])
                        container_type = 'reefer'
                    elif dry_blocks[layer]:
                        target_block = block_id if block_id in dry_blocks[layer] else random.choice(dry_blocks[layer])
                        container_type = 'dry'
                    else:
                        continue
                    yard_data.append({
                        'Container_ID': self._generate_plate_id(owner_code=f"L{layer}INI"),
                        'Mass_kg': random.uniform(17000, 23000),
                        'Type': container_type,
                        'Block_ID': target_block,
                        'Layer': layer
                    })
        self.initial_yard_df = pd.DataFrame(yard_data)

    def get_initial_containers_by_block(self):
        if self.initial_containers_by_block:
            return self.initial_containers_by_block, self.container_location_map
        if self.initial_yard_df is None:
            return {}, {}

        for _, row in self.initial_yard_df.iterrows():
            block_id = int(row['Block_ID'])
            container_id = row['Container_ID']
            layer = int(row['Layer'])
            container_type = row['Type']
            if block_id not in self.initial_containers_by_block:
                self.initial_containers_by_block[block_id] = []
            self.container_location_map[container_id] = block_id

            if container_type == 'reefer':
                reefer_params = generate_reefer_parameters()
                container = ReeferContainer(
                    env=self.env, container_id=container_id, vessel_id=f"YARD_START_L{layer}",
                    mass=row['Mass_kg'], **reefer_params
                )
                container.set_arrival_time(0)
                self.master_reefer_list.append(container)
            else:
                container = Container(
                    env=self.env, container_id=container_id, vessel_id=f"YARD_START_L{layer}",
                    mass=row['Mass_kg'], container_type='dry'
                )

            if layer == 1 and container_type == 'dry':
                self.export_pool_l1_dry.append(container)
            elif layer == 1 and container_type == 'reefer':
                self.export_pool_l1_reefer.append(container)
            elif layer == 2:
                self.import_pool_layer2.append(container_id)

            container.add_history(f"Present in yard at simulation start in Layer {layer}")
            self.initial_containers_by_block[block_id].append(container)
            self.container_location_map[container_id] = block_id
        return self.initial_containers_by_block, self.container_location_map

    def populate_yard_stores(self, yard_block_stores, container_location_map):
        """
        Takes the initial container data and populates the simulation's
        SimPy stores and the state's container location map.
        """
        initial_yard_containers, parsed_location_map = self.get_initial_containers_by_block()
        container_location_map.update(parsed_location_map)

        for block_id, container_list in initial_yard_containers.items():
            if block_id < len(yard_block_stores):
                # print(f"Initializing Yard Block {block_id+1} with {len(container_list)} containers.")
                for container in container_list:
                    yard_block_stores[block_id].put(container)

    def get_block_lists_by_type(self):
        dry_blocks = {1: [], 2: []}
        reefer_blocks = {1: [], 2: []}
        for i, yc_id in enumerate(self.terminal_layout.ycs.keys()):
            yc_info = self.terminal_layout.ycs[yc_id]
            layer = yc_info.get('layer', 1)
            block_type = yc_info.get('block_type', 'Dry')
            if layer in [1, 2]:
                if block_type == 'Reefer':
                    reefer_blocks[layer].append(i)
                else:
                    dry_blocks[layer].append(i)
        return dry_blocks, reefer_blocks