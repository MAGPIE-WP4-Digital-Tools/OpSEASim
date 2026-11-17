import os
import pandas as pd
import numpy as np

class Container:
    # Construct the path relative to this file's directory
    _here = os.path.dirname(os.path.abspath(__file__))
    _data_path = os.path.join(_here, "Data", "AvgEfficiency.pkl")
    df_avgEfficiency = pd.read_pickle(_data_path)

    def __init__(self, surfaceArea, heatTransCoef, cargo, mass, temp, arrival, departure, auxiliarPower = 0, boolHeating = True):
        self._surfaceArea    = surfaceArea   # Float, in m^2
        self._heatTransCoef  = heatTransCoef # Float, in W/(K*m^2)
        self._cargo          = cargo         # Cargo object
        self._mass           = mass          # Float, in kg
        self._temp           = temp          # Float, in °C
        self._auxiliarPower  = auxiliarPower # Float, in W. If not given, assumes 0W.
        self._boolHeating    = boolHeating   # Boolean: True if heating, False if cooling. If not given, assumes that everything starts in heating phase.
        self._arrival        = arrival       # Datetime
        self._departure      = departure     # Datetime
        # self.coolingCapacity                 Float, in W
        # sel.cop                              Float, dimensionless
        
        
    @property
    def surfaceArea(self):
        return self._surfaceArea
    
    @property
    def heatTransCoef(self):
        return self._heatTransCoef
    
    @property
    def cargo(self):
        return self._cargo
    
    @property
    def mass(self):
        return self._mass
    
    @property
    def temp(self):
        return self._temp
    
    @property
    def auxiliarPower(self):
        return self._auxiliarPower
    
    @temp.setter
    def temp(self, value):
        if isinstance(value, (int, float)):
            self._temp = value
        else:
            raise TypeError("Temperature must be float or integer.")
        
    @property
    def arrival(self):
        return self._arrival
    
    @property
    def departure(self):
        return self._departure
        
    @property
    def boolHeating(self):
        return self._boolHeating
    
    @boolHeating.setter
    def boolHeating(self, value):
        if isinstance(value, (bool)):
            self._boolHeating = value
        else:
            raise TypeError("boolHeating must be boolean.")
        
    @property
    def cop(self):    
        return np.interp(self.temp, Container.df_avgEfficiency['temperature'], self.__class__.df_avgEfficiency['avg_COP']) # Interpolate from avgEfficiency table, dimensionless  
        
    @property
    def coolingCapacity(self):
        powerConsumed = np.interp(self.temp, Container.df_avgEfficiency['temperature'], self.__class__.df_avgEfficiency['avg_powerConsumption']) # Interpolate from avgEfficiency table, in W
        return powerConsumed * self.cop
        

