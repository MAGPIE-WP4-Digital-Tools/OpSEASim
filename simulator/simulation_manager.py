import simpy
from simulator.agent_factory import AgentFactory
from simulator.logger import EventLogger
from simulator.simulation_state import SimulationState
class SimulationManager:
    def __init__(self, terminal):
        self.__terminal = terminal
        self.__logger = EventLogger()  
    
    @property
    def terminal(self):
        return self.__terminal
    
    @property
    def logger(self):
        return self.__logger
    
    @property
    def schedule(self):
        return self._schedule

    @schedule.setter
    def schedule(self, value):
        self._schedule = value
        
    @property
    def configuration(self):
        return self._configuration
    
    @configuration.setter
    def configuration(self, value):
        self._configuration = value

    def setup_environment(self):
        self.env = simpy.Environment()
        # Create the single state object, passing its dependencies
        self.state = SimulationState(self.env, self.terminal)
        
        # The manager can still be responsible for complex setup logic
        # that populates the state object.
        self._initialize_yc_id_map()

    def _initialize_yc_id_map(self):
        """Populates the yc_id_map in the state object."""
        sorted_yc_ids = sorted(self.terminal.ycs.keys())
        for i, yc_id_str in enumerate(sorted_yc_ids):
            self.state.yc_id_map[i] = yc_id_str

    def run_environment(self):
        self.run_time = self.configuration["run_time"]
        
        factory = AgentFactory(
            env=self.env,
            terminal=self.terminal,
            schedule=self.schedule,
            logger=self.logger,
            run_time=self.run_time,
            state=self.state  # Pass the state object
        )
        factory.create_all_agents()
        
        self.env.run(until=self.run_time)
        

