import numpy as np
class ITChargingStation:
    """
    An agent representing a single charging station for Internal Trucks.
    This agent will be responsible for the process of charging a truck and
    logging the details of the charging event.
    """
    def __init__(self, env, station_id, charge_rate_kw, efficiency, it_charging_log_ref, 
                 it_charging_queue_ref, ready_it_pool_ref, station_power_profiles_ref, run_time):
        self.env = env
        self.station_id = station_id
        self.charge_rate_kw = charge_rate_kw
        self.efficiency = efficiency
        self.charging_log = it_charging_log_ref
        
        self.charging_queue = it_charging_queue_ref
        self.ready_it_pool = ready_it_pool_ref

        self.power_profile = np.zeros(run_time)
        station_power_profiles_ref[self.station_id] = self.power_profile

        self.process = env.process(self.run_charging_cycle())
        
        
     # --- Lifecycle process ---
    def run_charging_cycle(self):
        """A continuous, efficient process that waits for trucks in the charging queue."""
        while True:
            # The process sleeps here waiting for an item.
            priority_item = yield self.charging_queue.get()
            
            # Unwrap the item to get the actual truck agent
            truck_to_charge = priority_item.item

            # After charging, return the truck to the pool of work-ready ITs
            yield self.env.process(self.charge_truck(truck_to_charge))
            self.ready_it_pool.put(truck_to_charge)
        
        
    # --- Active process to charge a truck ---
    def charge_truck(self, truck_agent):
        """A simpy process for charging a single truck that has arrived at this station."""
        
        # Calculate how much energy is needed to get to 90%
        kwh_needed = truck_agent.target_charge_kWh - truck_agent.current_charge_kWh
        
        if kwh_needed <= 0:
            print(f"{self.env.now:7.1f}: {self.station_id} - {truck_agent.it_id} in queue but needs no charge. Returning to pool.")
            return
        
        actual_nominal_power = min(self.charge_rate_kw, truck_agent.max_charge_rate_kw)
        effective_charge_rate_kw = actual_nominal_power * self.efficiency

        if effective_charge_rate_kw <= 0:
            return # Avoid division by zero
            
        charge_time_hours = kwh_needed / effective_charge_rate_kw
        charge_time_seconds = charge_time_hours * 3600

        print(f"{self.env.now:7.1f}: {self.station_id} starts charging {truck_agent.it_id} for {charge_time_seconds:.0f}s.")
        
        start_charge_time = self.env.now
        
        # Ensure indices are integers and within the array bounds
        start_idx = int(start_charge_time)
        end_idx = int(min(np.ceil(start_charge_time + charge_time_seconds), len(self.power_profile)))
        
        # "Paint" the power draw onto the time-series array (power in Watts)
        self.power_profile[start_idx:end_idx] = self.charge_rate_kw * 1000
        
        yield self.env.timeout(charge_time_seconds)
        
        # Update the truck's battery level
        kwh_added = (effective_charge_rate_kw * charge_time_seconds) / 3600
        truck_agent.current_charge_kWh += kwh_added
        
        # Log the completed charge event: [start_time, end_time, kWh_charged]
        session_log = {
            "truck_id": truck_agent.it_id,
            "charger_id": self.station_id,
            "start_time": start_charge_time,
            "end_time": self.env.now,
            "kwh_added": kwh_added,
            "final_soc_pct": truck_agent.charge_percent,
            "actual_power_kw": actual_nominal_power
        }
        self.charging_log.append(session_log)
            
        print(f"{self.env.now:7.1f}: {self.station_id} finished charging {truck_agent.it_id}. Battery at {truck_agent.charge_percent:.1f}%.")