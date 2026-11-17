import simpy

class ExternalTruck:
    def __init__(self, env, et_id, schedule_details,
                 all_yc_agents_ref, yard_block_stores, 
                 et_charging_queue, logger): 
        
        self.env = env
        self.et_id = et_id
        self.schedule_details = schedule_details
        
        # Unpack all schedule details
        self.early_arrival_time = schedule_details.get("early_arrival_time", 0)
        self.operation_time = schedule_details.get("operation_time", 0)
        self.mission = schedule_details.get("mission")
        self.target_container = schedule_details.get("target_container")
        self.target_block_id = schedule_details.get("target_block_id")
        
        # Unpack charging details
        self.needs_charge = self.early_arrival_time < self.operation_time
        self.target_charge_kWh = schedule_details.get("target_charge_kWh")
        self.max_charge_rate_kw = schedule_details.get("charge_rate_kw")
        
        # Battery model setup from schedule data
        self.battery_capacity_kWh = schedule_details.get("battery_capacity_kWh")
        self.current_charge_kWh = self.battery_capacity_kWh * (schedule_details.get("initial_charge_pct", 100.0) / 100.0)

        # Store references
        self.all_yc_agents = all_yc_agents_ref
        self.yard_block_stores = yard_block_stores
        self.et_charging_queue = et_charging_queue # The active queue
        self.logger = logger
        
        # Event to signal when charging is complete
        self.charge_complete_event = self.env.event()
        
        self.process = env.process(self.lifecycle())

    @property
    def charge_percent(self):
        """Returns the current battery charge as a percentage."""
        if self.battery_capacity_kWh == 0: 
            return 100.0
        return (self.current_charge_kWh / self.battery_capacity_kWh) * 100

    def go_charge(self):
        """A simple process to submit a charging request and wait for completion."""
        # print(f"{self.env.now:7.1f}: ET {self.et_id} submitting charge request to active station.")
        # The request is a dictionary containing the truck object and its deadline
        charge_request = {'truck': self, 'deadline': self.operation_time}

        yield self.et_charging_queue.put(charge_request)
        # Now, simply wait for the charging station to signal that it's done
        yield self.charge_complete_event

    def do_mission(self):
        """The process for the ET's primary mission (pickup or dropoff)."""
        # print(f"{self.env.now:7.1f}: ET {self.et_id} starting its yard operation for {self.target_container}.")
        self.logger.log(self.env, "ET_Start_Mission", et_id=self.et_id, container=self.target_container, block=self.target_block_id)
        
        target_yc_agent = self.all_yc_agents.get(self.target_block_id)
        if not target_yc_agent:
            print(f"CRITICAL ERROR: ET {self.et_id} assigned to invalid block ID {self.target_block_id}.")
            return

        if self.mission == 'dropoff':
            yield self.env.process(target_yc_agent.receive_export_container(self.target_container, self.et_id))
        elif self.mission == 'pickup':
            target_container_id = self.target_container
            block_store = self.yard_block_stores[self.target_block_id]
            
            container_to_pickup = yield block_store.get(lambda item: item.id == target_container_id)
            
            if container_to_pickup:
                container_to_pickup.add_history(f"Picked up by ET {self.et_id} from Block {self.target_block_id}")
                yield self.env.process(target_yc_agent.load_container_for_pickup(self.et_id, container_to_pickup))
            else:
                print(f"ERROR: ET {self.et_id} could not find {target_container_id} in Block {self.target_block_id}.")
        
        # print(f"{self.env.now:5.1f} ET {self.et_id} mission complete and departed terminal.")

    def lifecycle(self):
        """The main lifecycle, now robustly handling the charge/work interruption."""
        yield self.env.timeout(self.early_arrival_time)

        if self.needs_charge:
            charge_process = self.env.process(self.go_charge())
            operation_timeout = self.env.timeout(self.operation_time - self.env.now)

            # Wait for EITHER the charge to complete OR the operation time to arrive
            yield charge_process | operation_timeout


        # Wait for any remaining time until the exact operation moment
        time_to_wait = self.operation_time - self.env.now
        if time_to_wait > 0:
            yield self.env.timeout(time_to_wait)

        yield self.env.process(self.do_mission())