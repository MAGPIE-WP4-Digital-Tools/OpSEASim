import simpy

class IT_Crew:
    """
    A helper class to manage a dedicated pool of ITs for a single Quay Crane.
    This class now implements a smart dispatch logic to prioritize trucks with the highest charge.
    """
    def __init__(self, env, ready_it_pool, it_charging_queue, crew_size):
        self.env = env
        self.ready_it_pool = ready_it_pool
        self.it_charging_queue = it_charging_queue
        self.crew_size = crew_size
        self.crew_members = []
        self.available_trucks = []
        self.availability_gate = simpy.Store(env)
        
        # A simple list to hold the truck agents that are currently idle and available.
        self.available_trucks = []
        # A simpy.Store used as a "gate" or "semaphore". It signals when a truck becomes available.
        self.availability_gate = simpy.Store(env)

    def acquire_crew(self):
        """Get the required number of ITs from the main work-ready pool."""
        print(f"{self.env.now:.1f}: Acquiring {self.crew_size} ITs for a crew...")
        for _ in range(self.crew_size):
            # Get a work-ready truck from the correct pool
            it_agent = yield self.ready_it_pool.get()
            self.crew_members.append(it_agent)
            
            # Add the truck to our list of available trucks for this crew
            self.available_trucks.append(it_agent)
            # Put a placeholder in the gate to signal its availability
            self.availability_gate.put(1)
        print(f"{self.env.now:.1f}: Crew of {self.crew_size} ITs acquired.")

    def release_crew(self):
        """Return all ITs from the crew back to the global pool."""
        print(f"{self.env.now:.1f}: Releasing crew of {len(self.crew_members)} ITs.")
        for it_agent in self.crew_members:
            if it_agent.charge_percent < 90:
                priority = 90 - it_agent.charge_percent
                self.it_charging_queue.put(simpy.PriorityItem(priority, it_agent))
            else:
                self.ready_it_pool.put(it_agent)
        self.crew_members = []
        # Reset the custom pool
        self.available_trucks = []
        self.availability_gate = simpy.Store(self.env)

    # --- Method to get the best available truck ---
    def get_best_truck(self):
        """Waits for a truck to be available, then selects and returns the one with the highest charge."""
        # Wait until the gate signals that at least one truck is available.
        yield self.availability_gate.get()
        
        # Sort the list of available trucks in descending order by battery percentage.
        self.available_trucks.sort(key=lambda truck: truck.charge_percent, reverse=True)
        
        # Pop the best truck (the first one after sorting) from the list.
        best_truck = self.available_trucks.pop(0)
        return best_truck

    # --- Truck swapping process ---
    def swap_depleted_truck(self, depleted_truck):
        """
        A process to return a depleted truck to the central charging queue
        and acquire a fresh one from the ready pool. This represents the "pit stop" time.
        """
        print(f"{self.env.now:7.1f}: Crew swapping depleted {depleted_truck.it_id} (charge: {depleted_truck.charge_percent:.1f}%).")

        # 1. Remove the depleted truck from this crew's master list
        self.crew_members.remove(depleted_truck)

        # 2. Calculate priority and send the depleted truck to the central charging queue
        priority = 90 - depleted_truck.charge_percent
        self.it_charging_queue.put(simpy.PriorityItem(priority, depleted_truck))

        # 3. Request a fresh truck from the ready pool. The process will wait here if no trucks are available.
        fresh_truck = yield self.ready_it_pool.get()
        print(f"{self.env.now:7.1f}: Crew acquired fresh {fresh_truck.it_id} to replace depleted truck.")

        # 4. Add the new truck to this crew's master list
        self.crew_members.append(fresh_truck)
        
        # 5. Make the new truck immediately available for work within the crew
        self.available_trucks.append(fresh_truck)
        self.availability_gate.put(1)

    # --- Central handler for returning trucks ---
    def return_truck_to_pool(self, truck_agent, is_depleted=False):
        """
        Handles a truck returning from a task.
        If the truck is depleted, it triggers the swap process.
        Otherwise, it returns the truck to the crew's local available pool.
        """
        if is_depleted:
            # This truck cannot continue working. Start the swap process in the background.
            # The crew's available truck count will be temporarily reduced.
            self.env.process(self.swap_depleted_truck(truck_agent))
        else:
            # The truck is fine. Add it back to the local pool for the next task.
            self.available_trucks.append(truck_agent)
            # Signal that a truck is now available.
            self.availability_gate.put(1)