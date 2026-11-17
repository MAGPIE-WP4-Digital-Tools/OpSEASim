import pandas as pd

class EventLogger:
    def __init__(self):
        self.events = []

    def log(self, env, event_name, qc_id=None, container=None, it_id=None, 
            et_id=None, block=None, vessel_id=None, yc_id=None, extra_info=None): 
        self.events.append({
            "time": env.now,
            "event": event_name,
            "qc_id": qc_id,
            "container": container,
            "it_id": it_id,
            "et_id": et_id,
            "block": block,
            "vessel_id": vessel_id,
            "yc_id": yc_id,
            "extra_info": extra_info
        })

    def get_dataframe(self):
        return pd.DataFrame(self.events)