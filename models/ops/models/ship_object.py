from datetime import datetime
import pandas as pd
import math
from models.ops.utils.vessel_functions import ships_info, gt_verif, dwt_verif, teus_verif, me_verif, ae_me, depth_verif, loa_verif, val_pob, val_velocity

class Vessel:    
    def __init__(self: object, visit, coordinates: list, parameters) -> None:
        
        self.__imo: int = int(visit['imo'])
        self.__terminal: str = visit['terminal']
        self.__eta: datetime = pd.to_datetime(visit['eta'])
        self.__etd: datetime = pd.to_datetime(visit['etd'])
        self.__latitude: int = coordinates[0]
        self.__longitude: int = coordinates[1]
        self.__ship_type: str = visit['ship_type']
        
        # Ensure self.__data is a dictionary
        if isinstance(visit, list) and len(visit) > 0:
            visit = visit[0]  # Access the first dictionary in the list

        self.__name: str = visit['name']
        self.__breadth: float = visit['breadth']
        self.__gt: float = gt_verif(visit['gt'], self.breadth, self.ship_type)
        self.__dwt: float = dwt_verif(visit['dwt'], self.breadth, self.ship_type)
        self.__teus: int = teus_verif(visit['teus'], self.breadth, self.ship_type)
        self.__me: float = me_verif(float(visit['me']), self.gt, self.ship_type) / 1000
        self.__ae: float = ae_me(self.me, self.ship_type)
        self.__depth: float = depth_verif(visit['depth'], self.breadth, self.ship_type)
        self.__loa: float = loa_verif(visit['loa'], self.breadth, self.ship_type)
        self.__velocity: float = val_velocity(visit['speed'], self.ship_type)
        self.__pob: float = val_pob(visit['pob'], self.ship_type)
        self.__reefers: int = int(parameters['reefers'])
        self.__flexibility: float = parameters['flexibility_factor']
        self.__ops_id: int = int(parameters['ops_agent'].id)
        self.__ops_nom_power: float = parameters['ops_agent'].max_power_kW / 1000
        self.__ops_min_power: float = parameters['p_min']
        self.__ops_connection: datetime = parameters['connection_time']
        self.__ops_disconnection: datetime = parameters['disconnection_time']
        self.__power_demand = None
        self.check_nan()


    @property
    def terminal(self: object) -> str:
        return self.__terminal

    @property
    def imo(self: object) -> int:
        return self.__imo

    @property
    def eta(self: object) -> datetime:
        return self.__eta

    @property
    def etd(self: object) -> datetime:
        return self.__etd

    @property
    def latitude(self: object) -> int:
        return self.__latitude

    @property
    def longitude(self: object) -> int:
        return self.__longitude

    @property
    def ship_type(self: object) -> str:
        return self.__ship_type

    @property
    def name(self: object) -> str:
        return self.__name

    @property
    def gt(self: object) -> int:
        return self.__gt

    @property
    def dwt(self: object) -> int:
        return self.__dwt

    @property
    def teus(self: object) -> int:
        return self.__teus

    @property
    def breadth(self: object) -> float:
        return self.__breadth

    @property
    def depth(self: object) -> float:
        return self.__depth

    @property
    def loa(self: object) -> float:
        return self.__loa

    @property
    def velocity(self: object) -> float:
        return self.__velocity

    @property
    def me(self: object) -> float:
        return self.__me

    @property
    def ae(self: object) -> float:
        return self.__ae

    @property
    def pob(self: object) -> float:
        return self.__pob

    @property
    def reefers(self: object) -> int:
        return self.__reefers

    @property
    def flexibility(self: object) -> float:
        return self.__flexibility

    @property
    def ops_id(self: object) -> int:
        return self.__ops_id

    @property
    def ops_nom_power(self: object) -> int:
        return self.__ops_nom_power

    @property
    def ops_min_power(self: object) -> int:
        return self.__ops_min_power

    @property
    def ops_connection(self: object) -> datetime:
        return self.__ops_connection

    @property
    def ops_disconnection(self: object) -> datetime:
        return self.__ops_disconnection

    @property
    def power_demand(self):
        return self.__power_demand

    @power_demand.setter
    def power_demand(self, consumption):
        """Sets the power demand DataFrame using property syntax."""
        self.__power_demand = consumption

    def add_power_demand(self, consumption):
        """Adds the power demand DataFrame using a dedicated method."""
        self.__power_demand = consumption
  
    def check_nan(self):
        if math.isnan(self.me):
            print("Alert: Main Engine has no value for this ship.\nUnable to calculate Power Demand!")
        if math.isnan(self.teus):
            if self.ship_type != 'Container Ship':
                print("Alert: This is not a Container ship.\nUnable to calculate Power Demand!")
    
    
    def __str__(self: object) -> str:
        return (f'\nTerminal: {self.terminal} \nIMO: {self.imo} \nName: {self.name} \nShip_Type: {self.ship_type}'
                f'\nArrival: {self.eta} \nDeparture: {self.etd} \nLatitude: {self.latitude} \nLongitude: {self.longitude}'
                f'\nGT: {self.gt} \nDWT: {self.dwt} \nTEUS: {self.teus} \nME (MW): {self.me} \nAE (MW): {self.ae}'
                f'\nBreadth: {self.breadth} \nDepth: {self.depth} \nLOA: {self.loa} \nVelocity (knots): {self.velocity} '
                f'\nPOB: {self.pob} \nReefers: {self.reefers} \nFlexibility: {self.flexibility} \nOPS_ID: {self.ops_id} '
                f'\nOPS_Nominal_Power: {self.ops_nom_power} \nOPS_Min_Power: {self.ops_min_power} '
                f'\nOPS_Connection: {self.ops_connection} \nOPS_Disconnection: {self.ops_disconnection} '
                f'\nPower_Demand: {self.power_demand} ')
