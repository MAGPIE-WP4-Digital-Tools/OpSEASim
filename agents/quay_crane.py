import random
import simpy
import pandas as pd
from .it_crew import IT_Crew
from .container import Container
from .reefer_container import ReeferContainer
from models.reefers.cargo_definitions import generate_reefer_parameters
class QuayCrane:
    def __init__(self, env, qc_id, handling_time, crew_size, logger, qc_working_stats, 
                 ready_it_pool, it_charging_queue, container_location_map, all_created_reefers_list_ref):

        self.env = env
        self.qc_id = qc_id
        self.handling_time = handling_time
        self.logger = logger
        self.qc_working_stats = qc_working_stats
        self.master_reefer_list = all_created_reefers_list_ref
        
        self.container_location_map = container_location_map
        self.qc_resource = simpy.Resource(env, capacity=1)
        
        self._unsynchronize()
        self.it_crew = IT_Crew(env, ready_it_pool, it_charging_queue, crew_size)
    
        
    def _unsynchronize(self):
        with self.qc_resource.request() as req:
            yield req
            yield self.env.timeout(int(random.uniform(0,100))) # Remove initial syncronization
        
    # --- Reusable logging function for QCs ---
    def _log_work_start(self, container_mass, op_type):
        """
        Logs the start time, container mass, and handling time for a QC operation
        and returns the handling time to be used by the simulation process.
        """
        current_op_time = self.handling_time
        
        # The data structure is a list: [start_time, mass, handling_time, op_type]
        log_entry = [self.env.now, container_mass, current_op_time, op_type]
        
        if self.qc_id in self.qc_working_stats:
            self.qc_working_stats[self.qc_id].append(log_entry)
        else:
            self.qc_working_stats[self.qc_id] = [log_entry]
        
        # Return the handling time so the operation can use it
        return current_op_time

    # --- Process a simple list of operations ---
    def process_operations(self, operations_list, vessel_id, vessel_agent):
        """
        Process a list of operations (imports and exports) sequentially.
        """
        self.current_vessel = vessel_agent
        
        for index, operation in operations_list.iterrows():
            
            # Use concat to append the operation (row) to the DataFrame
            if vessel_agent.current_operations_df.empty:
                vessel_agent.current_operations_df = pd.DataFrame([operation])
            else:
                vessel_agent.current_operations_df = pd.concat([vessel_agent.current_operations_df, pd.DataFrame([operation])], ignore_index=True)
    
            
            if operation['direction'] == 'IMPORT':
                yield self.env.process(self.discharge_single_container(operation))
            elif operation['direction'] == 'EXPORT':
                yield self.env.process(self.load_single_container(operation['container_id'], vessel_id))
            

    def discharge_single_container(self, operation_row):
        """
        Process for a QC to discharge a single container.
        'operation_row' is a pandas Series containing the manifest data for one operation. [cite: 84]
        """
        container_type = operation_row['container_type']
        
        it_agent_instance = yield self.env.process(self.it_crew.get_best_truck())
        self.logger.log(self.env, "QC_Got_IT", qc_id=self.qc_id, it_id=it_agent_instance.it_id)
        # print(f"{self.env.now:5.1f} QC {self.qc_id} got IT {it_agent_instance.it_id} for {container_obj}.")
        
        # --- Request the QC resource before starting the operation ---
        with self.qc_resource.request() as req:
            yield req
            
            # --- Conditionally create the correct container type ---
            if container_type == 'reefer':
                reefer_params = generate_reefer_parameters()
                container_obj = ReeferContainer(
                    env=self.env,
                    container_id=operation_row['container_id'],
                    vessel_id=operation_row['vessel_id'],
                    mass=operation_row['mass'],
                    destination_block=operation_row['destination_block'],
                    **reefer_params
                )
                # Add the new reefer to the master list so it gets simulated and reported
                self.master_reefer_list.append(container_obj)
            else:
                # Fallback to creating a standard dry container
                container_obj = Container(
                    env=self.env,
                    container_id=operation_row['container_id'],
                    vessel_id=operation_row['vessel_id'],
                    mass=operation_row['mass'],
                    container_type='dry',
                    destination_block=operation_row['destination_block']
                )
            
            self.logger.log(self.env, "QC_Start_Unload", qc_id=self.qc_id, container=container_obj.id)    
            
            # 2. Now, use the newly created 'container_obj' for all subsequent logic.
            # The rest of your original logic can now work correctly.
            current_op_time = self._log_work_start(container_obj.mass, "IMPORT")
            yield self.env.timeout(current_op_time)
                
            self.logger.log(self.env, "QC_Finish_Unload", qc_id=self.qc_id, container=container_obj.id)
            # print(f"{self.env.now:5.1f} QC {self.qc_id} requests an IT from its local crew.")
                
            self.env.process(it_agent_instance.transport_container(
                container_obj=container_obj,
                qc=self,
                it_crew=self.it_crew 
            ))
            
    def load_single_container(self, container_id, vessel_id):
        """
        Process for a QC to load a single container ID onto a vessel.
        """
        
        # 1. Request an IT agent from the local crew's pool
        it_agent_instance = yield self.env.process(self.it_crew.get_best_truck())
            
        # 2. Find where the container is located
        if container_id not in self.container_location_map:
            print(f"CRITICAL ERROR: Container {container_id} for loading not found in yard map.")
            self.logger.log(self.env, "ERROR_EVENT", extra_info=f"Container {container_id} not in map")
            
            # Use the proper method to return the truck to the crew's available pool
            self.it_crew.return_truck_to_pool(it_agent_instance)
            return

        target_block = self.container_location_map[container_id]

        # 3. Dispatch the IT with a specific mission to fetch the container
        container_obj = self.env.process(
            it_agent_instance.fetch_export_container(
                qc=self,
                target_container_id=container_id,
                target_block_id=target_block,
                it_crew=self.it_crew, # Pass the crew object
                vessel_id = vessel_id
            )
        )

        if not container_obj:
            # The fetch failed; the IT is already back in the pool, so we can just stop.
            return
        
        self.logger.log(self.env, "QC_Request_Export", 
                        qc_id=self.qc_id, 
                        container=container_id,
                        vessel_id=vessel_id) 

    def finalize_export(self, container_obj, vessel_id):
        # This should be separated and be done by the truck itself, requesting the QC.
        # 4. Perform the final lift onto the vessel
        # --- Request the QC resource before starting the operation ---

        with self.qc_resource.request() as req:
            yield req
            current_op_time = self._log_work_start(container_obj.mass, "EXPORT")
            yield self.env.timeout(current_op_time)
                
            container_obj.add_history(f"Loaded by {self.qc_id} onto Vessel {vessel_id}")
            self.logger.log(self.env, "QC_Container_Loaded", 
                            qc_id=self.qc_id, 
                            container=container_obj.id,
                            vessel_id=vessel_id) 
            
            index_to_remove = self.current_vessel.current_operations_df[
                self.current_vessel.current_operations_df['container_id'] == container_obj.id
            ].index
            self.current_vessel.current_operations_df.drop(index_to_remove, inplace=True)
            
            # print(f"{self.env.now:5.1f} QC {self.qc_id} loaded {container_obj} onto Vessel {vessel_id}.")