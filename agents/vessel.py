import simpy
import pandas as pd
from models.ops.utils.vessel_functions import get_reefers

class Vessel:
    def __init__(self, env, vessel_id, imo, eta, real_eta, etd, real_etd, master_operation_list,
                 berth_resource_pool, qc_agent_pool, vessel_agents_ref,
                 vessel_at_berth_stats_dict, logger, ops_agent_pool, 
                 ops_vessel_log, run_time, teus, vessel_manifest_parser, container_location_map):
        
        self.env = env
        self.vessel_id = vessel_id 
        self.imo = imo
        self.eta = eta
        self.real_eta = real_eta
        self.etd = etd
        self.real_etd = real_etd
        
        self.master_operation_list = master_operation_list
        self.operation_index = 0
        
        self.berth_resource_pool = berth_resource_pool
        self.qc_agent_pool = qc_agent_pool
        self.ops_agent_pool = ops_agent_pool
        
        self.logger = logger
        self.vessel_at_berth_stats = vessel_at_berth_stats_dict
        self.ops_vessel_log = ops_vessel_log
        
        self.run_time = run_time
        self.teus = teus
        self.vessel_manifest_parser = vessel_manifest_parser
        self.container_location_map = container_location_map
        
        # Event to signal when to start disconnection
        self.start_disconnection_event = self.env.event()
        
        vessel_agents_ref[self.vessel_id] = self
        self.process = env.process(self.lifecycle())
        
        self.current_operations_df = pd.DataFrame(columns=['direction', 'container_id', 'vessel_id', 'container_type', 'mass', 'destination_block'])

    def get_upcoming_yc_operations(self, lookahead_count):
        """
        Predicts the next N yard crane (YC) operations.
        - For IMPORTs, the YC is determined by the destination block.
        - For EXPORTs, the YC is determined by the container's current location in the yard.
        """
        
        upcoming_yc_ids = set()

        for index, op in self.current_operations_df.iterrows():
            direction = op.get('direction')
            
            if direction == 'IMPORT':
                # For imports, the crane is tied to the destination block
                block_number = op.get('destination_block')
                upcoming_yc_ids.add(block_number)

            elif direction == 'EXPORT':
                # For exports, the crane is tied to the container's current location
                container_id = op.get('container_id')
                if container_id:
                    target_block = self.container_location_map[container_id]
                    upcoming_yc_ids.add(target_block)

        return upcoming_yc_ids
    
    
    def manage_cargo_operations(self):
        """A process to manage acquiring QCs and performing all container moves."""
        num_qcs_to_request = 3
        assigned_qcs = []
        for _ in range(num_qcs_to_request):
            qc_agent = yield self.qc_agent_pool.get()
            assigned_qcs.append(qc_agent)
        
        crew_acquisition_processes = [self.env.process(qc.it_crew.acquire_crew()) for qc in assigned_qcs]
        yield self.env.all_of(crew_acquisition_processes)
        
        if not self.master_operation_list.empty and assigned_qcs:
            all_qc_processes = []
            num_ops = len(self.master_operation_list)
            ops_per_qc = num_ops // len(assigned_qcs)
            ops_assigned = 0
            for i, qc_agent in enumerate(assigned_qcs):
                start_index = ops_assigned
                num_for_this_qc = ops_per_qc + (num_ops % len(assigned_qcs)) if i == len(assigned_qcs) - 1 else ops_per_qc
                end_index = start_index + num_for_this_qc
                ops_for_this_qc = self.master_operation_list[start_index:end_index]
                ops_assigned = end_index
                proc = self.env.process(qc_agent.process_operations(
                    operations_list=ops_for_this_qc, vessel_id=self.vessel_id, vessel_agent=self
                ))
                all_qc_processes.append(proc)
            yield self.env.all_of(all_qc_processes)
        
        for qc_agent in assigned_qcs:
            qc_agent.it_crew.release_crew()
            self.qc_agent_pool.put(qc_agent)
            
        return self.env.now

    def manage_ops_connection(self):
        """Manages the lifecycle of an OPS connection, now waiting for a signal to disconnect."""
        ops_agent = None
        try:
            ops_agent = yield self.ops_agent_pool.get()

            MIN_OPS_THRESHOLD = 20
            MIN_STAY_DURATION_S = 3600  # Minimum time (in seconds) at berth to justify connection
            UPPER_BOUND_CONN_S = 30 * 60
            UPPER_BOUND_DISCONN_S = 30 * 60
            
            # --- Check viability conditions ---
            # 1. Is there physically enough time in the schedule to connect and disconnect?
            projected_finish_time = self.env.now + UPPER_BOUND_CONN_S + UPPER_BOUND_DISCONN_S
            can_fit_in_schedule = projected_finish_time <= self.etd

            # 2. Is there enough work to do?
            remaining_operations = len(self.master_operation_list) - self.operation_index
            has_enough_work = remaining_operations >= MIN_OPS_THRESHOLD

            # 3. Is the vessel staying long enough? (Your new condition)
            has_enough_time = (self.etd - self.env.now) >= MIN_STAY_DURATION_S

            # --- Final Decision Logic ---
            # The vessel must be able to fit the process in its schedule, AND
            # it must either have enough work OR be staying for at least an hour.
            if can_fit_in_schedule and (has_enough_work or has_enough_time):
                # Condition met, proceed with connection
                pass
            else:
                # Condition not met, release the OPS agent and exit
                yield self.ops_agent_pool.put(ops_agent)
                return None 

            # --- Connection Process (if conditions were met) ---
            with ops_agent.resource.request() as req:
                yield req
                
                if self.env.now > 0:
                    conn_time_s = ops_agent.connection_time_min * 60
                    yield self.env.timeout(conn_time_s)

                connection_time = self.env.now
                reefers = get_reefers(self.teus)
                self.ops_vessel_log[self.vessel_id] = {
                    "connection_time": connection_time,
                    "disconnection_time": self.run_time,
                    "ops_agent": ops_agent,
                    "reefers": reefers,
                    "flexibility_factor": 0.5,
                    "p_min": 0
                }
                
                yield self.start_disconnection_event
                
                self.ops_vessel_log[self.vessel_id]["disconnection_time"] = self.env.now
                
                disconn_time_s = ops_agent.disconnection_time_min * 60
                yield self.env.timeout(disconn_time_s)

            yield self.ops_agent_pool.put(ops_agent)
            return self.env.now

        except simpy.Interrupt:
            if ops_agent:
                yield self.ops_agent_pool.put(ops_agent)
            return None

    def lifecycle(self):
        """The main process for a vessel, resolving the deadlock and coordinating disconnection."""
        yield self.env.timeout(self.eta)
        
        berth_req = self.berth_resource_pool.request()
        yield berth_req
        self.vessel_at_berth_stats[self.vessel_id] = [self.env.now]
        
        self.logger.log(self.env, "Vessel_Berthed", vessel_id=self.vessel_id, extra_info=f"Berthed at {self.env.now}")
        
        # --- Generate manifest JUST-IN-TIME after berthing ---
        manifest_data = self.vessel_manifest_parser.generate_manifest_for_vessel(self.vessel_id, self)
        self.master_operation_list = pd.DataFrame(manifest_data)
        
        # Start both processes concurrently
        cargo_process = self.env.process(self.manage_cargo_operations())
        ops_process = self.env.process(self.manage_ops_connection())

        # Wait for cargo operations to complete
        cargo_finish_time = yield cargo_process
        
        # Now, calculate when the disconnection signal should be sent
        disconn_duration = 30 * 60 
        disconnection_start_time_by_etd = self.etd - disconn_duration
        
        # The signal should be sent at the LATER of the two times: when cargo is done, or when it's time to leave.
        actual_disconnection_start_time = max(cargo_finish_time, disconnection_start_time_by_etd)
        
        # If we need to wait until that time, do so.
        if self.env.now < actual_disconnection_start_time:
            wait_duration = actual_disconnection_start_time - self.env.now
            yield self.env.timeout(wait_duration)
        
        # Now, trigger the event. This will release the manage_ops_connection process.
        if not self.start_disconnection_event.triggered:
            self.start_disconnection_event.succeed()

        # Wait for the OPS process to finish its disconnection routine
        ops_finish_time = yield ops_process
        
        # Determine the final departure time, which is the later of when OPS finished or the scheduled ETD
        if ops_finish_time is not None:
            final_departure_time = max(ops_finish_time, self.etd)
        else:
            final_departure_time = max(cargo_finish_time, self.etd)
        
        # Wait until the final departure time
        time_to_wait = final_departure_time - self.env.now
        if time_to_wait > 0:
            yield self.env.timeout(time_to_wait)

        self.vessel_at_berth_stats[self.vessel_id].append(self.env.now)
        self.berth_resource_pool.release(berth_req)
        self.logger.log(self.env, "Vessel_Departed", vessel_id=self.vessel_id, extra_info=f"Departed at {self.env.now}")