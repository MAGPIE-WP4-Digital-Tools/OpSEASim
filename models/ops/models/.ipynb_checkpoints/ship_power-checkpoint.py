import requests
import pandas as pd
import math
from datetime import datetime, timedelta
from ops.utils.vessel_functions import *
from colorama import Fore, Style, init
from ops.Reefers.ThermalModelForOPS import getReeferConsumption


class PowerDemand:
    #def __init__(self: object, port:str, start: datetime, end: datetime, occupancy: int, hvac_p_sys: float, ship_type: str, ship_me) -> None:
    def __init__(self: object, vessel: dict, start: datetime, end : datetime, meteo_data) -> None:

        # Verify if there are no empty atributes
        essential_attributes = {
            'IMO': vessel['imo'],
            'Ship_Type': vessel['Ship Type'],
            'GT': vessel['GT'],
            'DWT': vessel['DWT'],
            'TEUS': vessel['TEUS'],
            'ME': vessel['ME'],
            'Breadth': vessel['Breadth'],
            'Depth': vessel['Depth'],
            'LOA': vessel['LOA'],
            'Velocity': vessel['Velocity'],
            'POB': vessel['POB'],
        }
        
        for key, value in essential_attributes.items():
            if value is None or (isinstance(value, float) and math.isnan(value)):
                if essential_attributes['Ship_Type'] == 'Container Ship':
                    print(Fore.RED + f"Error: '{key}' value cannot be empty or None.")
                self.__is_valid = False
                return

        
        self.__is_valid = True
        self.__vessel: dict = vessel
        self.vessel['eta'] = pd.to_datetime(self.vessel['eta'])
        self.vessel['etd'] = pd.to_datetime(self.vessel['etd'])
        self.__start: datetime = start
        self.__end: datetime = end
        self.__ae: float = ae_me(self.vessel['ME'], self.vessel['Ship Type'])
        self.__latitude: float = get_coordinates('Porto de Sines')[0]
        self.__temp = meteo_data
        self.__rate = ship_active_rate(self.vessel['eta'], self.vessel['etd'])
        self.__load = self.merge()
        self.__hvac_p_sys = 65
        self.__ships_hvac_lf = pd.DataFrame(self.__load.apply(lambda row: load_factor(self.vessel)['hvac_lf'], axis=1))
        self.hvac()
        self.ships_load_factors()
        self.total_ship_lf()
        self.ship_power_demand()
        self.__feus: int = int(((2e-06) * (self.vessel['TEUS'] ** 2)) + (0.0519 * self.vessel['TEUS']))
        if self.vessel['Ship Type'] == 'Container Ship':
            self.__reefers = getReeferConsumption(self.__feus, self.__temp, pd.Timestamp(self.vessel['eta']), pd.Timestamp(self.vessel['etd']))
        self.__power_demand = self.total_power_demand()
        self.__ops_power = self.ops_power_demand()


    def is_valid(self):
        return self.__is_valid

    @property
    def vessel(self: object) -> dict:
        return self.__vessel

    @property
    def start(self: object) -> datetime:
        return self.__start

    @property
    def end(self: object) -> datetime:
        return self.__end

    @property
    def ae(self: object) -> float:
        return self.__ae

    @property
    def latitude(self: object) -> float:
        return self.__latitude
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
        return self.vessel['POB']

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
        self.__load['HVAC Sys LF'] = (self.__load.apply(lambda row: hvac_lf(row['Temperature (C)'], self.__hvac_p_sys, self.vessel['POB'], row['Datetime'], self.__latitude), axis=1))# * self.__ships_hvac_lf['hvac_lf']


    def ships_load_factors(self: object):
        self.__load['Ship LF wo HVAC'] = pd.DataFrame(self.__load.apply(lambda row: load_factor(self.vessel)['ship_lf'], axis=1))
        self.__load['HVAC LF'] = pd.DataFrame(self.__load.apply(lambda row: load_factor(self.vessel)['hvac_lf'], axis=1))


    def total_ship_lf(self: object):
        self.__load['Total Ship LF'] = (self.__load['HVAC Sys LF'] * self.__load['HVAC LF']) + self.__load['Ship LF wo HVAC']

    
    def ship_power_demand(self: object):
        self.__load['Ship Power Demand (MW)'] = self.__load['Ship_Rate'] * self.__load['Total Ship LF'] * self.__ae

    
    # Merge Reefers poweer demand
    def total_power_demand(self: object):
        power_demand = time_range(self.__start, self.__end)
        if self.vessel['Ship Type'] == 'Container Ship':
            power_demand = pd.merge(power_demand, self.__reefers, on='Datetime', how='left')
            power_demand['Reefer Power'] = power_demand['Reefer Power'].ffill()
        
        power_demand = pd.merge_asof(power_demand, self.__load[['Datetime', 'Ship Power Demand (MW)', 'OPS_Rate']], on='Datetime')
        power_demand['Ship Power Demand (MW)'] = power_demand['Ship Power Demand (MW)'].ffill()
        power_demand['OPS_Rate'] = power_demand['OPS_Rate'].ffill()
        power_demand.fillna(0, inplace=True)
        if self.vessel['Ship Type'] == 'Container Ship':
            power_demand['OPS Power Demand (MW)'] = (power_demand['Reefer Power'] + power_demand['Ship Power Demand (MW)']) * power_demand['OPS_Rate']
        else:
            power_demand['OPS Power Demand (MW)'] = power_demand['Ship Power Demand (MW)'] * power_demand['OPS_Rate']

        return power_demand


    def ops_power_demand(self: object):
        # ops_power = self.__power_demand[['Datetime', 'Seconds', 'OPS Power Demand (MW)']]
        ops_power = self.__power_demand[['Datetime', 'OPS Power Demand (MW)']]
        ops_power_demand = ops_power
        return ops_power_demand
    
    
    # def __str__(self: object) -> str:
        # return (f'Start date: {self.vessel['eta']} \nEnd date: {self.vessel['etd']}'
        #        f'\nPort Location - Latitude: {self.__latitude}'
        #        f'\nHourly Ship power Demand (MW) - Mean: {self.__load['Ship Power Demand (MW)'].mean()} - Max: {self.__load['Ship Power Demand (MW)'].max()} - Min: {self.__load[self.__load['Ship Power Demand (MW)'] != 0]['Ship Power Demand (MW)'].min()}'
        #        f'\nHourly OPS power Demand (MW) - Mean: {self.__load['OPS Power Demand (MW)'].mean()} - Max: {self.__load['OPS Power Demand (MW)'].max()} - Min: {self.__load[self.__load['OPS Power Demand (MW)'] != 0]['OPS Power Demand (MW)'].min()}'
        #        f'\nReefers numbers: {self.__feus}')
        # return (f'\nReefers power demand: \n{self.__reefers}')

