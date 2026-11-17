from .models.ship_object import Vessel
from .utils.models_functions import energy_consumption
from .utils.output_functions import json_output, flex_output, generate_excel, plot_terminal_data     
from models.ops.utils.models_functions import create_vessels
    
    
def getOpsResults(ops_data, start_date, end_date, model, time_step, terminal_name, schedule, parameters, save = False, plot = False):
    
    vessels = create_vessels(
            schedule=schedule,
            parameters=parameters, 
            start_date=start_date
        )
    
    
    energy_consumption(vessels, model, start_date, end_date)

    # Save and crete .json output file
    if save:
        json_output(vessels, ops_data, time_step)

    # # Plot and/or save flexibility data for analysis
    # if plot or save:
    #     flex_output(vessels, ops_data, time_step, save, plot)

    # Create and save excel with ships consumption data
    generate_excel(vessels, time_step)
    
    # Plot and/or save teminal power consumption
    plot_terminal_data(vessels, time_step, terminal_name, save, plot)

