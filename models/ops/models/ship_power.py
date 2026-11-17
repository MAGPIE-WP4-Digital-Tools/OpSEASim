# import requests
import pandas as pd
import math
from models.ops.utils.vessel_functions import ship_active_rate, load_factor, time_range, hvac_lf
from models.ops.models.ship_object import Vessel
from colorama import Fore
from models.ops.Reefers.ThermalModelForOPS import getReeferConsumption


class PowerDemand:
    def __init__(self: object, vessel: Vessel, start, end, meteo_data) -> None:

        # Verify if there are no empty atributes
        essential_attributes = {
            'IMO': vessel.imo,
            'Ship_Type': vessel.ship_type,
            'GT': vessel.gt,
            'DWT': vessel.dwt,
            'TEUS': vessel.teus,
            'ME': vessel.me,
            'Breadth': vessel.breadth,
            'Depth': vessel.depth,
            'LOA': vessel.loa,
            'Velocity': vessel.velocity,
            'POB': vessel.pob,
        }
        
        for key, value in essential_attributes.items():
            if value is None or (isinstance(value, float) and math.isnan(value)):
                if essential_attributes['Ship_Type'] == 'Container Ship':
                    print(Fore.RED + f"Error: '{key}' value cannot be empty or None.")
                self.__is_valid = False
                return

        
        self.__is_valid = True
        self.__vessel: Vessel = vessel
        self.__start = start
        self.__end = end
        self.__connection = self.vessel.ops_connection.floor('15min')
        self.__disconnection = self.vessel.ops_disconnection.ceil('15min')
        self.__temp = meteo_data
        self.__rate = ship_active_rate(self.connection, self.disconnection)
        self.__load = self.merge()
        self.__hvac_p_sys = 65
        self.__ships_hvac_lf = pd.DataFrame(self.__load.apply(lambda row: load_factor(self.vessel)['hvac_lf'], axis=1))
        self.hvac()
        self.ships_load_factors()
        self.total_ship_lf()
        self.ship_power_demand()
        self.__feus: int = int(((2e-06) * (self.vessel.teus ** 2)) + (0.0519 * self.vessel.teus))
        if self.vessel.ship_type == 'Container Ship':
            self.__reefers = getReeferConsumption(self.__feus, self.__temp, pd.Timestamp(self.connection), pd.Timestamp(self.disconnection))
        self.__power_demand = self.total_power_demand()
        self.__ops_power = self.ops_power_demand()


    def is_valid(self):
        return self.__is_valid

    @property
    def vessel(self: object) -> dict:
        return self.__vessel

    @property
    def start(self: object):
        return self.__start

    @property
    def end(self: object):
        return self.__end

    @property
    def connection(self: object):
        return self.__connection

    @property
    def disconnection(self: object):
        return self.__disconnection

    @property
    def latitude(self: object) -> float:
        return self.vessel.latitude
    @property
    def temp(self: object):
        return self.__temp

    @property
    def rate(self: object):
        return self.__rate

    @property
    def load(self: object):
        return self.__load

    @property
    def ship_occupancy(self: object) -> int:
        return self.vessel.pob

    @property
    def hvac_p_sys(self: object) -> float:
        return self.__hvac_p_sys
    

    @property
    def reefers(self: object):
        return self.__reefers

    @property
    def power_demand(self: object):
        return self.__power_demand

    @property
    def ops_power(self: object):
        return self.__ops_power


    # Merge data
    def merge(self: object):
        load = pd.merge(self.__rate, self.__temp, on='Datetime', how='left')
        return load

    
    def hvac(self: object):
        self.__load['HVAC Sys LF'] = (self.__load.apply(lambda row: hvac_lf(row['Temperature (C)'], self.__hvac_p_sys, self.vessel.pob, row['Datetime'], self.vessel.latitude), axis=1))# * self.__ships_hvac_lf['hvac_lf']


    def ships_load_factors(self: object):
        self.__load['Ship LF wo HVAC'] = pd.DataFrame(self.__load.apply(lambda row: load_factor(self.vessel)['ship_lf'], axis=1))
        self.__load['HVAC LF'] = pd.DataFrame(self.__load.apply(lambda row: load_factor(self.vessel)['hvac_lf'], axis=1))


    # Calculate ship load factor
    def total_ship_lf(self: object):
        self.__load['Total Ship LF'] = (self.__load['HVAC Sys LF'] * self.__load['HVAC LF']) + self.__load['Ship LF wo HVAC']


    # Create the column 'Ship Power Demand (MW)' with ship power demand consumption
    def ship_power_demand(self: object):
        self.__load['Ship Power Demand (MW)'] = self.__load['Ship_Rate'] * self.__load['Total Ship LF'] * self.vessel.ae

    
    # Merge Reefers poweer demand
    def total_power_demand(self: object):
        power_demand = time_range(self.__start, self.__end)
        if self.vessel.ship_type == 'Container Ship':
            power_demand = pd.merge(power_demand, self.__reefers, on='Datetime', how='left')
            power_demand['Reefer Power'] = power_demand['Reefer Power'].ffill()
        
        power_demand = pd.merge_asof(power_demand, self.__load[['Datetime', 'Ship Power Demand (MW)', 'OPS_Rate']], on='Datetime')
        power_demand['Ship Power Demand (MW)'] = power_demand['Ship Power Demand (MW)'].ffill()
        power_demand['OPS_Rate'] = power_demand['OPS_Rate'].ffill()
        power_demand.fillna(0, inplace=True)
        if self.vessel.ship_type == 'Container Ship':
            power_demand['Ship Power Demand (MW)'] = power_demand['Ship Power Demand (MW)'] * power_demand['OPS_Rate']
            power_demand['OPS Power Demand (MW)'] = (power_demand['Reefer Power'] * power_demand['OPS_Rate']) + power_demand['Ship Power Demand (MW)']
        else:
            power_demand['Ship Power Demand (MW)'] = power_demand['Ship Power Demand (MW)'] * power_demand['OPS_Rate']
            power_demand['OPS Power Demand (MW)'] = power_demand['Ship Power Demand (MW)']

        return power_demand

    # Create a df with datetime and total ops power consumption
    def ops_power_demand(self: object):
        ops_power = self.__power_demand[['Datetime', 'Seconds', 'Ship Power Demand (MW)', 'OPS Power Demand (MW)']]

        return ops_power
