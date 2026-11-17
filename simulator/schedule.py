import pandas as pd

class Schedule:
    def __init__(self, start_date_str, active_vessels_df, vessel_manifest_parser, truck_parser):
        """
        Initializes the simulation schedule.
        """
        self.vessel_manifest_parser = vessel_manifest_parser
        self.ships_schedule = self._create_ships_schedule(start_date_str, active_vessels_df)
        self.ets_schedule = truck_parser.get_truck_schedule()

    def _create_ships_schedule(self, start_str, ships_df):
        ship_scheduling = {}
        start_timestamp = pd.Timestamp(start_str)

        # ! The 'call' column from calls.csv is the unique identifier for a visit
        for _, row in ships_df.iterrows():
            # Use the 'call' ID as the unique key for the schedule dictionary
            call_id = row['call']
            
            eta_seconds = (row['eta'] - start_timestamp).total_seconds()
            etd_seconds = (row['etd'] - start_timestamp).total_seconds()

            ship_scheduling[call_id] = {
                "eta": int(eta_seconds) if eta_seconds >= 0 else 0,
                "real_eta": int(eta_seconds),
                "etd": int(etd_seconds) if etd_seconds >= 0 else 0,
                "real_etd": int(etd_seconds),
                "master_operation_list": None,
                "teus": row['teus'],
                "imo": str(row['imo']) 
            }
        return ship_scheduling