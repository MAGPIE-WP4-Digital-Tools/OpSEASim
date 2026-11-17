import numpy as np
import pandas as pd
import simpy
import math
from .container import Container

# Pathing
import sys
from pathlib import Path
project_root = Path(__file__).parent
# Go up the directory tree until 'terminaldemandsimulator'
while project_root.name != 'terminaldemandsimulator' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))
from utils.paths import REEFERS_DIR  # noqa: E402

class ReeferContainer(Container):
    """
    A specialized container with thermal properties for refrigerated cargo.
    Inherits basic properties and methods from the base Container class.
    """
    
    df_avgEfficiency = pd.read_pickle(REEFERS_DIR / "Data\\AvgEfficiency.pkl")

    def __init__(self, env, container_id, vessel_id, mass,
                 surfaceArea, heatTransCoef, cargo, temp, 
                 auxiliarPower=0, boolHeating=True, **kwargs):
        
        super().__init__(env, container_id, vessel_id, mass, container_type='reefer', **kwargs)
        
        self._surfaceArea    = surfaceArea
        self._heatTransCoef  = heatTransCoef
        self._cargo          = cargo
        self._initial_temp   = temp
        self._temp           = temp
        self._auxiliarPower  = auxiliarPower
        self._boolHeating    = boolHeating
        self.tempRange       = 2 # +- degrees Celsius from the setpoint
        
        self.power_consumption_log = [] # Logs {'time': env.now, 'power_W': watts}
        self.action = None # To hold the simpy process  
        
    @property
    def surfaceArea(self): return self._surfaceArea
    @property
    def heatTransCoef(self): return self._heatTransCoef
    @property
    def cargo(self): return self._cargo
    @property
    def temp(self): return self._temp
    @property
    def initial_temp(self): return self._initial_temp
    @property
    def auxiliarPower(self): return self._auxiliarPower
    @property
    def boolHeating(self): return self._boolHeating
    @property
    def setpoint(self): return (self.cargo.upperBound + self.cargo.lowerBound) / 2
    @property
    def cUpperBound(self): return min(self.setpoint + self.tempRange, self.cargo.upperBound)
    @property
    def cLowerBound(self): return max(self.setpoint - self.tempRange, self.cargo.lowerBound)
        
    @property
    def cop(self):    
        return np.interp(self.temp, ReeferContainer.df_avgEfficiency['temperature'], ReeferContainer.df_avgEfficiency['avg_COP'])
        
    @property
    def coolingCapacity(self):
        powerConsumed = np.interp(self.temp, ReeferContainer.df_avgEfficiency['temperature'], ReeferContainer.df_avgEfficiency['avg_powerConsumption'])
        return powerConsumed * self.cop
    
    @initial_temp.setter
    def initial_temp(self, value):
        self._initial_temp = value
        self._temp = value
    
    def set_arrival_time(self, time):
        """Starts the reefer's thermal simulation process."""
        super().set_arrival_time(time)
        if self.action is None:
            self.action = self.env.process(self.run_thermal_model())
            print(f"INFO: Reefer {self.id} connected. Thermal model started at {time}.")

    def set_departure_time(self, time):
        """Stops the reefer's thermal simulation process."""
        super().set_departure_time(time)
        if self.action and not self.action.triggered:
            self.action.interrupt()

    # --- Thermal logic from your script is now part of the agent ---
    def _get_ambient_temp(self):
        return 25 

    def _update_temp(self, time):
        # This method correctly uses the full complexity from your model
        temp_amb = self._get_ambient_temp()
        delta_temp_amb = temp_amb - self.temp
        respiration_rate = (10.7 * self.cargo.resp_f / 3600) * ((9 * self.temp / 5 + 32)**self.cargo.resp_g) if self.cargo.resp_f else 0

        if not self._boolHeating: # Cooling
             delta_temp = -self.coolingCapacity * time / (self.mass * self.cargo.specificHeat) + (respiration_rate * time / self.cargo.specificHeat) + delta_temp_amb - delta_temp_amb * math.exp(-self.surfaceArea * self.heatTransCoef * time / (self.mass * self.cargo.specificHeat))
        else: # Passively heating
            delta_temp = delta_temp_amb - delta_temp_amb * math.exp(-self.surfaceArea * self.heatTransCoef * time / (self.mass * self.cargo.specificHeat)) + (respiration_rate*time / self.cargo.specificHeat) 
        self._temp += delta_temp
        
    def copy_for_forecast(self):
        # Create a temporary copy to see what the temperature will be in the future
        temp_container = ReeferContainer(self.env, self.id, self.origin_vessel_id, self.mass, 
                               self.surfaceArea, self.heatTransCoef, self.cargo, self.temp,
                               self.auxiliarPower, self.boolHeating)
        return temp_container

    def run_thermal_model(self, interval=900):
        """A simpy process that simulates consumption, now accounting for partial intervals."""
        last_calc_time = self.env.now
        
        try:
            # 1. Initial wait to align with the first global tick
            initial_wait = interval - (self.env.now % interval) if self.env.now % interval != 0 else 0

            if initial_wait > 0:
                # --- Calculate and log for the initial partial interval ---
                power_watts = self._auxiliarPower
                if not self._boolHeating:
                    power_watts += (self.coolingCapacity / self.cop)
                self.power_consumption_log.append({'time': self.env.now, 'power_W': power_watts})
                self._update_temp(initial_wait) # Update temp over this partial time
                
                yield self.env.timeout(initial_wait)
                last_calc_time = self.env.now

            # 2. Main synchronized loop
            while True:
                # Forecast the temperature at the end of the next interval to decide state
                future_container = self.copy_for_forecast()
                future_container._update_temp(interval)
                
                if self._boolHeating and future_container.temp > self.cUpperBound:
                    self._boolHeating = False # Turn cooling ON
                elif not self._boolHeating and future_container.temp < self.cLowerBound:
                    self._boolHeating = True # Turn cooling OFF
                
                # Calculate and log power for this full interval
                power_watts = self._auxiliarPower
                if not self._boolHeating:
                    power_watts += (self.coolingCapacity / self.cop)
                self.power_consumption_log.append({'time': self.env.now, 'power_W': power_watts})
                
                # Update the actual temperature over this interval
                self._update_temp(interval)
                
                yield self.env.timeout(interval)
                last_calc_time = self.env.now

        except simpy.Interrupt:
            # --- 3. Handle the final partial interval upon interruption ---
            final_interval = self.env.now - last_calc_time
            if final_interval > 0:
                # Log the power consumption for this last, partial period
                power_watts = self._auxiliarPower
                if not self._boolHeating:
                    power_watts += (self.coolingCapacity / self.cop)
                self.power_consumption_log.append({'time': last_calc_time, 'power_W': power_watts})
                # Update final temp state
                self._update_temp(final_interval)
                
            print(f"INFO: Thermal model for {self.id} stopped after final calculation.")

