class Container:
    """
    A simple, passive agent representing a single shipping container.
    This is the base class for all container types.
    """
    def __init__(self, env, container_id, vessel_id, mass, container_type='dry', destination_block=None):
        self.env = env
        self.id = container_id
        self.origin_vessel_id = vessel_id
        self.mass = mass
        self.type = container_type
        
        self.destination_block = destination_block 
        self.history = [f"{self.env.now:.1f}: Created, origin {vessel_id}"]
        
        self.arrival_time_yard = None
        self.departure_time_yard = None
        self.assigned = False

    def add_history(self, event_description):
        self.history.append(f"{self.env.now:.1f}: {event_description}")

    def set_arrival_time(self, time):
        """Sets the arrival time for the container when it's placed in the yard."""
        self.arrival_time_yard = time
        # The base container does nothing more, but a subclass can override this.
        pass

    def set_departure_time(self, time):
        """Sets the departure time for the container when it's picked up from the yard."""
        self.departure_time_yard = time
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}({self.id}, {self.mass/1000:.1f}t)"