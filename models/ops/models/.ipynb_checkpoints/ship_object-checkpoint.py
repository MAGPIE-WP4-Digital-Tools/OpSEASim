from datetime import datetime
import pandas as pd
import math
from colorama import Fore, Style, init
from ops.utils.vessel_functions import *
from ops.utils.equip_power import *

class Ship:    
    def __init__(self: object, imo: int) -> None:
        self.__imo: int = imo
        self.__ship_data: dict = ships_info(self.__imo)
        self.__ship_type: str = ship_type(self.__ship_data['ship_type'])  # Call the method here
        
        # Ensure self.__data is a dictionary
        if isinstance(self.__ship_data, list) and len(self.__ship_data) > 0:
            self.__ship_data = self.__ship_data[0]  # Access the first dictionary in the list

        self.__name: str = self.__ship_data['name']
        self.__breadth: float = self.__ship_data['breadth']
        self.__gt: float = gt_verif(self.ship_data['gt'], self.breadth, self.ship_data['ship_type'])
        self.__dwt: float = dwt_verif(self.ship_data['dwt'], self.breadth, self.ship_data['ship_type'])
        self.__teus: int = teus_verif(self.__ship_data['teus'], self.breadth, self.ship_data['ship_type'])
        self.__me: float = me_verif(float(self.ship_data['me']), self.gt, self.ship_data['ship_type'])
        self.__depth: float = depth_verif(self.__ship_data['depth'], self.breadth, self.ship_data['ship_type'])
        self.__loa: float = loa_verif(self.__ship_data['loa'], self.breadth, self.ship_data['ship_type'])
        self.__velocity: float = val_velocity(self.__ship_data['speed'], self.ship_type)
        self.__pob: float = val_pob(self.ship_data['pob'], self.ship_type)
        self.check_nan()


    @property
    def imo(self: object) -> int:
        return self.__imo

    @property
    def ship_data(self: object) -> dict:
        return self.__ship_data

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
    def pob(self: object) -> float:
        return self.__pob
  
    def check_nan(self):
        if math.isnan(self.me):
            print(Fore.RED + "Alert: Main Engine has no value for this ship.\nUnable to calculate Power Demand!")
        if math.isnan(self.teus):
            if self.ship_type != 'Container Ship':
                print(Fore.RED + "Alert: This is not a Container ship.\nUnable to calculate Power Demand!")
    
    
    def __str__(self: object) -> str:
        return (f'\nIMO: {self.imo} \nName: {self.name} \nShip_Type: {self.ship_type}'
                f'\nGT: {self.gt} \nDWT: {self.dwt} \nTEUS: {self.teus} \nME (kW): {self.me}'
                f'\nBreadth: {self.breadth} \nDepth: {self.depth} \nLOA: {self.loa} \nVelocity (knots): {self.velocity} '
                f'\nPOB: {self.pob} ')
