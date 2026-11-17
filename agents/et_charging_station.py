import numpy as np

class ETChargingStation:
    """
    An ACTIVE agent representing a single charging station for External Trucks.
    It pulls charging requests from a queue and manages the entire charging process,
    including interruptions based on the truck's operational schedule.
    """
    def __init__(self, env, station_id, charge_rate_kw, efficiency, 
                 charging_queue_ref, et_charging_log_ref, power_profiles_ref, run_time):
        self.env = env
        self.id = station_id
        self.charge_rate_kw = charge_rate_kw
        self.efficiency = efficiency
        
        self.charging_queue = charging_queue_ref
        self.log = et_charging_log_ref

        # Setup the time-series power profile for this specific station
        self.power_profile = np.zeros(run_time)
        power_profiles_ref[self.id] = self.power_profile
        
        # Start the active lifecycle
        self.process = env.process(self.run_charging_cycle())

    def run_charging_cycle(self):
        """A continuous process that waits for trucks in the charging queue."""
        while True:
            # Wait for a truck to submit a charging request
            request = yield self.charging_queue.get()
            
            truck_agent = request['truck']
            deadline = request['deadline']
            
            # Handle this truck in a separate, non-blocking process
            self.env.process(self.charge_et(truck_agent, deadline))

    def charge_et(self, truck, deadline):
        """Contains the full logic for charging a single ET, including interruptions."""
        
        
        kwh_needed = truck.target_charge_kWh - truck.current_charge_kWh
        
        if kwh_needed > 0:
            # The actual power is the minimum of what the station can provide and what the truck can accept
            actual_nominal_power = min(self.charge_rate_kw, truck.max_charge_rate_kw)
            effective_charge_rate_kw = actual_nominal_power * self.efficiency
            
            if effective_charge_rate_kw > 0:
                time_needed = (kwh_needed / effective_charge_rate_kw) * 3600
                time_available = deadline - self.env.now
                charge_duration = min(time_needed, time_available)

                if charge_duration > 0:
                    start_time = self.env.now
                    # "Paint" the power draw onto the time-series array
                    start_idx = int(start_time)
                    end_idx = int(min(np.ceil(start_time + charge_duration), len(self.power_profile)))
                    self.power_profile[start_idx:end_idx] = self.charge_rate_kw * 1000 # Log in Watts
                    
                    yield self.env.timeout(charge_duration)
                    
                    kwh_added = (effective_charge_rate_kw * charge_duration) / 3600
                    truck.current_charge_kWh += kwh_added
                    
                    # Create a detailed log for this specific charging session
                    session_log = {
                        "truck_id": truck.et_id,
                        "charger_id": self.id,
                        "start_time": start_time,
                        "end_time": self.env.now,
                        "kwh_added": kwh_added,
                        "final_soc_pct": truck.charge_percent,
                        "actual_power_kw": actual_nominal_power
                    }
                    self.log.append(session_log)
                    # print(f"{self.env.now:7.1f}: ET Station {self.id} finished charging ET {truck.et_id}.")

        # Crucially, signal to the truck that its charging session is over (or was never needed).
        if truck.charge_complete_event and not truck.charge_complete_event.triggered:
            truck.charge_complete_event.succeed()