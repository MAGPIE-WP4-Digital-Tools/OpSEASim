import random
from .cargo import Cargo 

# --- Define all available cargo types using the Cargo class ---
CARGO_LIST = [
    Cargo(3, "Tomatoes", 4020, 10, 18.3, 2.0074 * 10**-4, 2.8350),
    Cargo(4, "Onions", 3950, -0.6, 5, 3.668 * 10**-4, 2.538),
    Cargo(5, "Fresh Peaches", 3910, -1.1, 2.2, 1.2996 * 10**-5, 3.6417),
    Cargo(6, "Carrots", 3920, -1.1, 6.7, 0.050018, 1.7926),
    Cargo(7, "Grapefruits", 3960, 8.9, 15.6, 0.0035828, 1.9982)
]


def generate_reefer_parameters():
    # 1. Randomly select a cargo type from our master list
    cargo_object = random.choice(CARGO_LIST)
    
    tempRange = 2
    setpoint = (cargo_object.upperBound + cargo_object.lowerBound) / 2
    cUpperBound = min(setpoint + tempRange, cargo_object.upperBound)
    cLowerBound = max(setpoint - tempRange, cargo_object.lowerBound)
    
    # 2. Generate the parameters based on your snippet
    params = {
        "surfaceArea": 74.97,
        "heatTransCoef": 0.5,
        "cargo": cargo_object, 
        "temp": random.uniform(cLowerBound, cUpperBound),  # Start at a random temperature within bounds
        "auxiliarPower": 0,
        "boolHeating": random.choices(population=[True, False], weights=[0.85, 0.15])[0]
    }
    return params