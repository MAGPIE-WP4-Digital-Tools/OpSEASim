import pandas as pd
import ast
from parsers.ops_parser import OPSParser


# Pathing
import sys
from pathlib import Path
project_root = Path(__file__).parent
# Go up the directory tree until 'terminaldemandsimulator'
while project_root.name != 'terminaldemandsimulator' and project_root.parent != project_root:
    project_root = project_root.parent
sys.path.insert(0, str(project_root))
from utils.paths import  DATA_DIR  # noqa: E402

#
#
#====================================
# A class for defining the layout of the terminal on a specific day
#=====================================

# ! This is parsing and also the object Terminal itself - wouldnt be bad to separate those.

class TerminalParser():
    #
    """ A class for defining the layout of any container terminal"""
    #
    def __init__(self: object, name: str) -> None:
        #
        self.__name: str = name
        terminal_df = pd.read_excel(DATA_DIR / 'terminal.xlsx', sheet_name = 'Layout')
        
        # Gets QCs and corresponding cycle time (s)
        qcs = {}
        for qc in terminal_df['QC_ID'].dropna():
            qcs['%s' %qc] = {"id":qc,
                             "cycle":terminal_df[terminal_df['QC_ID']==qc]['QC_cycle_[s]'].values[0],
                              "it_crew": int(terminal_df['IT_by_QC'].dropna().values[0])} 
            
        # Gets YCs and corresponding cycle time (s)
        # as well as distance from QC to YC
        ycs = {}
        for _, row in terminal_df.dropna(subset=['YC_ID']).iterrows():
            yc_id = row['YC_ID']
            ycs[yc_id] = {
                "id": yc_id,
                "cycle": row['YC_cycle_[s]'],
                "layer": int(row['Layer']), 
                "block_type": row['Block_Type'],
                "distance": {qc:d for qc,d in zip(terminal_df['QC_ID'].dropna(),
                                            ast.literal_eval(row['Mean_Distance_QCtoYC_[m]'])) }
            }
            
        # Create a new dictionary to store distances from the QC's perspective
        qc_to_yc_distances = {}
        qc_ids = [qc for qc in terminal_df['QC_ID'].dropna()]

        for i, qc_id in enumerate(qc_ids):
            # For each QC, create a mapping from YC ID to distance
            qc_to_yc_distances[qc_id] = {}
            for yc_id, yc_data in ycs.items():
                # The 'i' index corresponds to the column for the current QC
                distance = yc_data['distance'][qc_id]
                # Map the YC's original string ID to the distance
                qc_to_yc_distances[qc_id][yc_id] = distance

        # Store this new structure on the Terminal object
        self.qc_to_yc_distances = qc_to_yc_distances
            
        its = {
            'total_its': 400, # TODO Make it come from terminal input
            'it_full_speed_[km/h]': terminal_df['IT_full_speed_[km/h]'].values[0],
            'it_empty_speed_[km/h]': terminal_df['IT_empty_speed_[km/h]'].values[0]
        }
        
        berths = {"B01": 1, "B02": 2, "B03": 3, "B04": 4, "B05": 5, "B06": 6, "B07": 7, "B08": 8, "B09": 9, "B10": 10, "B11": 11, "B12": 12, "B13": 13, "B14": 14, "B15": 15}
        # berths = {"B01": 1, "B02": 2} # TODO Make it come from terminal input
        
        # Load IT and ET chargers data from the terminal configuration file
        try:
            self.it_chargers_df = pd.read_excel(DATA_DIR / 'terminal.xlsx', sheet_name='IT_Chargers')
        except ValueError:
            self.it_chargers_df = pd.DataFrame() 

        try:
            self.et_chargers_df = pd.read_excel(DATA_DIR / 'terminal.xlsx', sheet_name='ET_Chargers')
        except ValueError:
            self.et_chargers_df = pd.DataFrame() 
            
        #-----
        self.qcs = qcs
        self.ycs = ycs
        self.its = its
        self.berths = berths
        
        self.regeneration = terminal_df['Regeneration'].values[0]
        
        ops_parser = OPSParser()
        self.ops_data = ops_parser.get_ops_data()

    @property
    def name(self: object) -> str:
        return self.__name
#------------------------------
#

        

        
        

 