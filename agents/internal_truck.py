CRITICAL_CHARGE_THRESHOLD = 10 # Trucks below 10% must be swapped and go to queue for charging
class InternalTruck:
    def __init__(self, env, it_id, it_resource, all_yc_agents_ref, 
                 logger, it_speeds, qc_to_yc_distances, yc_id_map):
        self.env = env
        self.it_id = it_id
        self.it_resource = it_resource
        
        # Store speeds in m/s for easy calculation
        self.speed_loaded_mps = it_speeds['it_full_speed_[km/h]'] * 1000 / 3600
        self.speed_empty_mps = it_speeds['it_empty_speed_[km/h]'] * 1000 / 3600
        self.qc_to_yc_distances = qc_to_yc_distances
        self.yc_id_map = yc_id_map # Store the mapfetch_export_container

        self.all_yc_agents = all_yc_agents_ref
        self.logger = logger
        
        self.battery_capacity_kWh = 150 #can be converted to a input instead!!
        
        initial_charge_percent = 90
        self.current_charge_kWh = self.battery_capacity_kWh * (initial_charge_percent / 100.0)
        
        self.target_charge_kWh = self.battery_capacity_kWh * 0.9
        self.power_draw_loaded_kW = 50
        self.power_draw_empty_kW = 25
        self.max_charge_rate_kw = 50

    @property
    def charge_percent(self):
        """Returns the current battery charge as a percentage."""
        return (self.current_charge_kWh / self.battery_capacity_kWh) * 100
    
    
    # --- Internal method to calculate travel time between QC and YC ---
    def _get_travel_time(self, from_qc, to_yc_numeric, is_loaded):
        to_yc_str = self.yc_id_map.get(to_yc_numeric)
        
        if to_yc_str is None:
            print(f"CRITICAL ERROR: Could not find string ID for YC numeric ID {to_yc_numeric}")
            return float('inf')

        distance_m = self.qc_to_yc_distances[from_qc][to_yc_str]
        speed_mps = self.speed_loaded_mps if is_loaded else self.speed_empty_mps

        if speed_mps == 0:
            return float('inf')

        return int(distance_m / speed_mps)

    # --- Internal method to calculate energy consumption ---
    def _consume_energy(self, duration_s, is_loaded):
        """Calculates energy consumed during a trip and subtracts it from the battery."""
        if duration_s <= 0:
            return
            
        power_draw = self.power_draw_loaded_kW if is_loaded else self.power_draw_empty_kW
        # Convert power (kW) and time (s) to energy (kWh)
        energy_consumed_kWh = (power_draw * duration_s) / 3600
        
        self.current_charge_kWh -= energy_consumed_kWh
 
    def transport_container(self, container_obj, qc, it_crew):
        """Process for an IT to transport an IMPORT container from QC to YC."""
        with self.it_resource.request() as req:
            yield req

            block_to_travel = container_obj.destination_block
            if block_to_travel is None:
                print(f"CRITICAL ERROR: IT {self.it_id} received container {container_obj.id} with no destination assigned.")
                return 
            # print(f"{self.env.now:7.1f} {container_obj} loaded to IT {self.it_id}...")
            
            time_to_yard = self._get_travel_time(qc.qc_id, block_to_travel, is_loaded=True)
            yield self.env.timeout(time_to_yard)
            self._consume_energy(time_to_yard, is_loaded=True)
            # print(f"{self.env.now:7.1f} IT {self.it_id} with {container_obj} arrived at Yard Block {block_to_travel}.")
            
            target_yc_agent = self.all_yc_agents[block_to_travel]
            yield self.env.process(target_yc_agent.store_container(container_obj, self.it_id, qc.qc_id))
            # print(f"{self.env.now:7.1f} IT {self.it_id} returning to quay.")
            
            time_from_yard = self._get_travel_time(qc.qc_id, block_to_travel, is_loaded=False)
            yield self.env.timeout(time_from_yard) 
            self._consume_energy(time_from_yard, is_loaded=False)
            # print(f"{self.env.now:7.1f} IT {self.it_id} finished task, returned to quay.")
            
            index_to_remove = qc.current_vessel.current_operations_df[
                qc.current_vessel.current_operations_df['container_id'] == container_obj.id
            ].index
            qc.current_vessel.current_operations_df.drop(index_to_remove, inplace=True)

        # Put the IT back in the crew pool for the QC to use
        is_depleted = self.charge_percent < CRITICAL_CHARGE_THRESHOLD
        it_crew.return_truck_to_pool(self, is_depleted)
        # print(f"{self.env.now:7.1f}: IT {self.it_id} is now available in crew pool.")
        

    
    def fetch_export_container(self, qc, target_container_id, target_block_id, it_crew, vessel_id):
        """
        Process for an IT to fetch a export container. It now requests the YC at the target block to perform the lift.  """
        container_to_load = None
        with self.it_resource.request() as req:
            yield req
            print(f"{self.env.now:7.1f} IT {self.it_id} assigned to fetch {target_container_id}...")
            
            time_to_yard = self._get_travel_time(qc.qc_id, target_block_id, is_loaded=False)
            yield self.env.timeout(time_to_yard)
            self._consume_energy(time_to_yard, is_loaded=False)
            
            target_yc_agent = self.all_yc_agents[target_block_id]
            container_to_load = yield self.env.process(
                target_yc_agent.load_container_for_export(self.it_id, target_container_id)
            )

            if container_to_load is None:
                print(f"ERROR: IT {self.it_id} failed to get {target_container_id}.")
                return None
            # print(f"{self.env.now:7.1f} IT {self.it_id} has received {container_to_load} from YC.")
            
            time_from_yard = self._get_travel_time(qc.qc_id, target_block_id, is_loaded=True)
            yield self.env.timeout(time_from_yard)
            self._consume_energy(time_from_yard, is_loaded=True)

            # print(f"{self.env.now:7.1f} IT {self.it_id} arrived at QC {qc.qc_id} with {container_to_load}.")
        
        self.logger.log(self.env, "IT_Arrived_To_Load_QC",
                         it_id=self.it_id, container=container_to_load.id)
        
        # Request QC to load the container    
        yield self.env.process(qc.finalize_export(container_to_load, vessel_id))
        
        # Put the IT back in the crew pool for the QC to use
        is_depleted = self.charge_percent < CRITICAL_CHARGE_THRESHOLD
        it_crew.return_truck_to_pool(self, is_depleted)
        # print(f"{self.env.now:7.1f}: IT {self.it_id} is now available in crew pool.")
    
        return container_to_load   