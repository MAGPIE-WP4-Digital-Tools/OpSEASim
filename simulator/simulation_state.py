import simpy

class SimulationState:
    """A data class to create and hold all shared simulation resources and state."""
    def __init__(self, env, terminal):
        # --- Core Resources ---
        self.env = env
        self.terminal = terminal
        
        # --- SimPy Resources & Pools ---
        self.ready_it_pool = simpy.Store(env)
        self.it_charging_queue = simpy.PriorityStore(env)
        self.it_individual_resources = {f"IT_{i+1}": simpy.Resource(env, capacity=1) for i in range(terminal.its['total_its'])}
        self.yard_block_stores = [simpy.FilterStore(env) for _ in range(len(terminal.ycs))]
        self.qc_agent_pool = simpy.Store(env)
        self.berth_resource = simpy.Resource(env, capacity=len(terminal.berths.keys()))
        self.ops_agent_pool = simpy.Store(env)
        self.et_charging_queue = simpy.Store(env)
        
        # --- Agent Lists ---
        self.all_yc_agents = {}
        self.all_it_agents = []
        self.all_et_agents = []
        self.vessel_agents = {}
        
        # --- Data & Logs ---
        self.yc_id_map = {}
        self.container_location_map = {}
        self.truck_arrivals_by_block = {}
        self.it_charging_log = []
        self.et_charging_log = []
        self.it_station_power_profiles = {}
        self.et_station_power_profiles = {}
        self.qc_working = {}
        self.vessel_at_berth = {}
        self.yc_agent_working_stats = {}
        self.all_created_reefers = []
        self.ops_vessel_log = {}
        self.it_station_configs = {}
        self.et_station_configs = {}
        self.dry_l1_blocks = []
        self.reefer_l1_blocks = []
        self.dry_l2_blocks = []
        self.reefer_l2_blocks = []
        self.active_vessels_df = None
        
    