import random

class YardCrane:
    def __init__(self, env, yc_id, layer, handling_time, et_schedule, 
                 vessel_agents_ref, vessel_at_berth_stats_ref, logger, yc_simpy_resource, 
                 original_string_id_param, yc_agent_working_stats_ref, yard_block_stores_ref,
                 container_location_map_ref):
        
        self.env = env
        self.yc_id = yc_id
        self.layer = layer 
        self.handling_time = handling_time
        self.et_schedule = et_schedule
        self.logger = logger
        self.yc_simpy_resource = yc_simpy_resource
        self.original_string_id = original_string_id_param
        self.yc_agent_working_stats = yc_agent_working_stats_ref
        self.yard_block_stores = yard_block_stores_ref
        self.container_location_map = container_location_map_ref

        self.vessel_agents = vessel_agents_ref
        self.vessel_at_berth_stats = vessel_at_berth_stats_ref
        
        self.housekeeping_upper_bound = self.handling_time * 0.8
        self.housekeeping_lower_bound = self.handling_time * 0.6
        
        self.rehandle_count = 0
        self.store_count = 0
        self.retrieve_count = 0
    
        self.env.process(self.run_unified_lifecycle())
        
    # --- Logging function ---
    def _log_work_start(self, container_mass):
        """
        Calculates a variable handling time for an operation, logs the data,
        and returns the calculated time to be used by the simulation process.
        """
        # Calculate a variable time using a uniform distribution
        variable_handling_time = int(random.uniform(self.handling_time * 0.8, self.handling_time * 1.2))

        # The data structure now logs this specific, variable time
        log_entry = [self.env.now, container_mass, variable_handling_time]
        
        if self.yc_id in self.yc_agent_working_stats:
            self.yc_agent_working_stats[self.yc_id].append(log_entry) 
        else:
            self.yc_agent_working_stats[self.yc_id] = [log_entry]
            
        # Return the calculated time so the operation can use it
        return variable_handling_time

    # --- Separate logging function for housekeeping ---
    def _log_housekeeping_start(self, container_mass):
        """
        Calculates a variable time for a HOUSEKEEPING operation, logs the data,
        and returns the calculated time to be used by the simulation process.
        """
        variable_move_time = int(random.uniform(self.housekeeping_lower_bound, self.housekeeping_upper_bound))

        # Log the operation details just like a productive move
        log_entry = [self.env.now, container_mass, variable_move_time]
        if self.yc_id in self.yc_agent_working_stats:
            self.yc_agent_working_stats[self.yc_id].append(log_entry) 
        else:
            self.yc_agent_working_stats[self.yc_id] = [log_entry]
        
        # Return the calculated time for the operation to use
        return variable_move_time
    
    def _do_housekeeping_move(self):
        """
        A process for a single housekeeping move. It now calls a dedicated
        logging function to get its duration and log its details.
        """
        with self.yc_simpy_resource.request() as req:
            yield req
            
            block_store = self.yard_block_stores[self.yc_id]
            
            if not block_store.items:
                return

            container_to_move = random.choice(block_store.items)
            retrieved_container = yield block_store.get(lambda item: item.id == container_to_move.id)
            
            # Call the housekeeping logging function to get the duration and log the data
            variable_move_time = self._log_housekeeping_start(retrieved_container.mass)

            self.logger.log(self.env, "YC_Start_Housekeeping", yc_id=self.original_string_id, 
                            container=retrieved_container.id,
                            extra_info=f"YC {self.original_string_id} starts housekeeping on {retrieved_container.id}.")
            
            # Use the variable time for the simulation timeout
            yield self.env.timeout(variable_move_time)
            
            yield block_store.put(retrieved_container)
            
            # --- ADD: Count this move as a rehandle ---
            self.rehandle_count += 1
            
            self.logger.log(self.env, "YC_Finished_Housekeeping", yc_id=self.original_string_id, 
                            container=retrieved_container.id,
                            extra_info=f"YC {self.original_string_id} finished housekeeping on {retrieved_container.id}.")
            
    def run_unified_lifecycle(self):
        """
        A continuous process that governs the crane's idle-time behavior.
        - Layer 1 (Seaside) cranes predictively check vessel work queues.
        - Layer 2 (Landside) cranes predictively check truck schedules.
        """
        check_interval = 40 # seconds
        
        yield self.env.timeout(int(random.uniform(0,100))) # Remove initial syncronization
        while True:
            if self.layer == 1:
                # --- Predictive Seaside Logic ---
                is_needed_soon = False
                # Check all known vessel agents
                for vessel in self.vessel_agents.values():
                    # Is the vessel at the berth? (Arrived but not yet departed)
                    arrival_event = self.vessel_at_berth_stats.get(vessel.vessel_id)
                    is_berthed = arrival_event is not None and len(arrival_event) == 1
                    
                    if is_berthed:
                        # Check if this YC is needed in the next operations
                        upcoming_yc_ids = vessel.get_upcoming_yc_operations(lookahead_count=5)
                        if self.yc_id in upcoming_yc_ids:
                            is_needed_soon = True
                            break # Found a reason to wait, no need to check other vessels
                
                if is_needed_soon:
                    # This YC is needed soon, wait before checking again
                    yield self.env.timeout(check_interval)
                else:
                    # This YC is idle, perform a housekeeping move
                    yield self.env.process(self._do_housekeeping_move())

            elif self.layer == 2:
                # --- Predictive Landside Logic ---
                safety_buffer = 10 # seconds
                next_arrival = None
                for arrival_time in self.et_schedule:
                     if arrival_time > self.env.now:
                        next_arrival = arrival_time
                        break
                
                if next_arrival is None:
                    # No more trucks are scheduled; just do housekeeping indefinitely.
                    yield self.env.process(self._do_housekeeping_move())
                else:
                    # Trucks are still scheduled; decide whether to work or wait.
                    time_until_next_truck = next_arrival - self.env.now
                    if time_until_next_truck > self.housekeeping_upper_bound + safety_buffer:
                        yield self.env.process(self._do_housekeeping_move())
                    else:
                        time_to_sleep = time_until_next_truck + self.handling_time + safety_buffer
                        if time_to_sleep > 0:
                            yield self.env.timeout(time_to_sleep)
                        else:
                            yield self.env.timeout(1)
    
        
    def store_container(self, container_obj, it_id, qc_id_origin):
        """Process for a YC to store an import container delivered by an IT."""
        with self.yc_simpy_resource.request() as req:
            yield req
            
            # --- Log the operation and get the specific duration for this move ---
            current_op_time = self._log_work_start(container_obj.mass)

            container_obj.add_history(f"Handled by YC {self.original_string_id}")
            self.logger.log(self.env, "YC_Start_Handling", yc_id=self.original_string_id, 
                             container=container_obj.id, 
                            it_id=it_id, qc_id=qc_id_origin,
                            extra_info=f"YC {self.original_string_id} starts handling {container_obj}")
            print(f"{self.env.now:5.1f} YC {self.original_string_id} starts handling {container_obj}")

            # --- Use the variable duration for the timeout ---
            yield self.env.timeout(current_op_time)

            block_store = self.yard_block_stores[self.yc_id]
            block_store.put(container_obj)
            container_obj.add_history(f"Stored in Block {self.yc_id+1}")
            
            self.container_location_map[container_obj.id] = self.yc_id
            
            if container_obj.type == 'reefer':
                container_obj.set_arrival_time(self.env.now)
                
            # --- Count this move as a store ---
            self.store_count += 1

            self.logger.log(self.env, "YC_Stored_Container", yc_id=self.original_string_id, 
                            container=container_obj.id, 
                            it_id=it_id, qc_id=qc_id_origin,
                             extra_info=f"{container_obj} stored in Block {self.yc_id+1} by YC {self.original_string_id}.")
            print(f"{self.env.now:5.1f} {container_obj} stored in Block {self.yc_id+1} by YC {self.original_string_id}.")
            
    def load_container_for_export(self, it_id, target_container_id):
        """
        Process for a YC to retrieve a specific export container from its block
        and load it onto an Internal Truck.
        """
        with self.yc_simpy_resource.request() as req:
            yield req
            
            self.logger.log(self.env, "YC_Start_Loading_IT", yc_id=self.original_string_id, 
                            it_id=it_id, container=target_container_id,
                            extra_info=f"YC {self.original_string_id} starts finding {target_container_id} for IT {it_id}.")
            print(f"{self.env.now:5.1f} YC {self.original_string_id} starts finding {target_container_id} for IT {it_id}.")

            block_store = self.yard_block_stores[self.yc_id]
            container_to_load = yield block_store.get(lambda item: item.id == target_container_id)
            
            # --- Log the operation and get the specific duration for this move ---
            current_op_time = self._log_work_start(container_to_load.mass)
            
            if container_to_load.type == 'reefer':
                container_to_load.set_departure_time(self.env.now)
            
            # --- Use the variable duration for the timeout ---
            yield self.env.timeout(current_op_time)
            
            # --- Count this move as a retrieve ---
            self.retrieve_count += 1

            self.logger.log(self.env, "YC_Finished_Loading_IT", yc_id=self.original_string_id, 
                         it_id=it_id, container=container_to_load.id,
                            extra_info=f"YC {self.original_string_id} finished loading {container_to_load} onto IT {it_id}.")
            print(f"{self.env.now:5.1f} YC {self.original_string_id} finished loading {container_to_load} onto IT {it_id}.")
            
            return container_to_load
        
    def load_container_for_pickup(self, et_id, container_to_pickup):
        """Process for a YC to load a container onto an external truck for pickup."""
        with self.yc_simpy_resource.request() as req:
            yield req
            
            # --- Log the operation and get the specific duration for this move ---
            current_op_time = self._log_work_start(container_to_pickup.mass)
            
            if container_to_pickup.type == 'reefer':
                 container_to_pickup.set_departure_time(self.env.now)

            self.logger.log(self.env, "YC_Start_Loading_ET", yc_id=self.original_string_id, 
                            et_id=et_id, container=container_to_pickup.id,
                            extra_info=f"YC {self.original_string_id} starts loading {container_to_pickup} for ET {et_id}")
            print(f"{self.env.now:5.1f} YC {self.original_string_id} starts loading {container_to_pickup} for ET {et_id}")

            # --- Use the variable duration for the timeout ---
            yield self.env.timeout(current_op_time)
            
            # --- Count this move as a retrieve ---
            self.retrieve_count += 1

            self.logger.log(self.env, "YC_Finished_Loading_ET", yc_id=self.original_string_id, 
                            et_id=et_id, container=container_to_pickup.id,
                             extra_info=f"YC {self.original_string_id} finished loading {container_to_pickup} for ET {et_id}.")
            print(f"{self.env.now:5.1f} YC {self.original_string_id} finished loading for ET {et_id}.")
                
    def receive_export_container(self, container_obj, et_id):
        """Process for a YC to take an export container from an ET and place it in its block store."""
        with self.yc_simpy_resource.request() as req:
            yield req
            
            # --- Log the operation and get the specific duration for this move ---
            current_op_time = self._log_work_start(container_obj.mass)

            self.logger.log(self.env, "YC_Start_Receiving_ET", yc_id=self.original_string_id, 
                            et_id=et_id, container=container_obj.id,
                            extra_info=f"YC {self.original_string_id} starts receiving {container_obj} from ET {et_id}")
            print(f"{self.env.now:5.1f} YC {self.original_string_id} starts receiving {container_obj} from ET {et_id}")

            # --- Use the variable duration for the timeout ---
            yield self.env.timeout(current_op_time)
            
            block_store = self.yard_block_stores[self.yc_id]
            block_store.put(container_obj)
            container_obj.add_history(f"Stored in export yard at Block {self.yc_id+1}")
             
            if container_obj.type == 'reefer':
                container_obj.set_arrival_time(self.env.now)
                
            # --- Count this move as a store ---
            self.store_count += 1
            
            self.logger.log(self.env, "YC_Finished_Receiving_ET", yc_id=self.original_string_id, 
                            et_id=et_id, container=container_obj.id,
                           extra_info=f"YC {self.original_string_id} placed {container_obj} into Block {self.yc_id+1} store.")
            print(f"{self.env.now:5.1f} YC {self.original_string_id} placed {container_obj} into Block {self.yc_id+1} store.")
        