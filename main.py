import random
from datetime import datetime
from simulator.simulation_builder import SimulationBuilder
from simulator.report_module import ReportModule
random.seed(1)

# --- Configuration ---

configuration = {}
start_date_str = '26-09-2022 00:00:00' # setting a particular simulated day
end_date_str = '26-09-2022 23:59:59'
configuration["start_date"] = start_date_str
configuration["end_date"] = end_date_str
configuration["terminal_name"] = 'Terminal XXI' # setting a specific container terminal for the simulation

# Calculate runtime from start and end dates
start_dt = datetime.strptime(start_date_str, '%d-%m-%Y %H:%M:%S')
end_dt = datetime.strptime(end_date_str, '%d-%m-%Y %H:%M:%S')
configuration["run_time"] = int((end_dt - start_dt).total_seconds())

configuration["time_step"] = '1h'

print(configuration["terminal_name"])

# --- 1. Build the Simulation ---
builder = SimulationBuilder(configuration)
simulation_manager = builder.build()

report = ReportModule(simulation_manager)
report.initial_yard_state()

# --- 2. Run the Simulation ---
simulation_manager.run_environment()

# --- 3. Generate Final Reports ---
report.output()






