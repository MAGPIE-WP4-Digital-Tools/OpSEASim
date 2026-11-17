import numpy as np
import matplotlib.pyplot as plt


def getChargingStationsResults(station_power_profiles, run_time, type, title='Instantaneous Power Consumption of Charging Stations'):
    """
    Takes the time-series power data for charging stations and plots it.
    - station_power_profiles: A dict where keys are station IDs and values are numpy power arrays (in Watts).
    - run_time: The total simulation time in seconds.
    """
    if not station_power_profiles:
        print("No charging station power data was logged to analyze.")
        return

    plt.figure(figsize=(15, 7))
    time_series = np.arange(run_time)
    
    total_power_kw = np.zeros(run_time)

    for station_id, power_profile_w in station_power_profiles.items():
        power_profile_kw = power_profile_w / 1000
        plt.plot(time_series, power_profile_kw, label=f'{station_id} Power (kW)', alpha=0.7)
        total_power_kw += power_profile_kw

    print(f"The total {type} consumption was: {(sum(total_power_kw) / 3600 / 1000):.2f} MWh")

    total_label = 'Total ' + ' '.join(title.split(' ')[3:])
    plt.plot(time_series, total_power_kw, label=total_label, color='black', linestyle='--', linewidth=2)

    plt.xlabel('Time (seconds)')
    plt.ylabel('Power Consumption (kW)')
    plt.title(title)
    plt.legend()
    plt.grid(True)
    plt.ylim(bottom=0)
    plt.savefig(f'output\\additional\\{type}_trucks_consumption_graph.png')
    plt.show()
    
    