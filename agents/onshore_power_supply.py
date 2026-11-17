import simpy

class OnshorePowerSupply:
    """
    An agent representing a single Onshore Power Supply (OPS) unit.
    """
    def __init__(self, env, ops_data):
        self.env = env
        self.id = ops_data['ops_id']
        self.berth = ops_data['berth']
        self.max_power_kW = ops_data['max_power_kW']
        self.connection_time_min = ops_data['connection_time_min']
        
        self.disconnection_time_min = ops_data['disconnection_time_min']

        self.has_battery = ops_data['battery_installed'] == 'yes'
        self.battery_capacity_kWh = ops_data['battery_capacity_kWh']

        self.resource = simpy.Resource(env, capacity=1)

    def __repr__(self):
        return f"OPS_Unit_{self.id}(Berth: {self.berth})"