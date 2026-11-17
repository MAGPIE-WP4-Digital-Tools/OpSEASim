import math
import pandas as pd
import numpy as np


##############################################################
##############################################################
##############################################################
############# Constants for Variables definition #############
##############################################################
##############################################################
##############################################################
# Specific Fuel Oil Consumption (SFOC) of marine engines ranges between 155 and 225 g/kWh we assume 250
sfoc = 250

# Ships usually have between 6 to 12 cylinders, we wil assume 8 cylinders given in mm
n_cylinder = 8

# Fresh water density and bildge pump water density - We assume 1.015 ton/m3
fw_density = 1.015

# Sea water density - 1.025 ton/m3
sw_density = 1.025

# Air density 1.13 kg/m3 (I.e. the density of air, at +35 oC,70 RH and 101.3 kPa)
air_density = 1.13

# Sewage liquid density - Close to 1000 kg/m3 = 1 ton/m3
sewage_density = 1

# Oil demsity
oil_density = 0.85

# Seawage_density
seawage_density = 1 # ton/m3

# Bilge pump diameter not less than 50 mm and more than 100 mm - we will assume 100 mm
bildge_diameter = 100

# Heavy fuel oil Density - 900kg/m3
hfo_density = 900

# Gravity = 9.8 m/s
g = 9.8

# Ballast flow
q_ballast = 450 # m3/h

# Handling velocity
v_handling = 0.15 # m/s

# Number of reefers
n_reefers = 0

# Luminous efficacy acording to lamp type
n_lamp: dict = {'Incandescent Tungsten': 45, 'Fluorescent tube': 60, 'Halogen': 20, 'LED': 120} # (lm/W)

# Provision Plant Volume
prov_p_vol = 50 # m3
##############################################################

##############################################################
# Air compressor tank variables
##############################################################
# Air compressors must guarantie 8 to 12 starts
n_starts = 12

# Every start should occur in 20 s
t_start = 20

# Each start needs 1,5 m3 to 3 m3 of compressed air, we assume 3 m3
air_comp_volume = 3
###############################################################
###############################################################
###############################################################
#################### Variables Calculation ####################
###############################################################
# Ships < 500 GT – 4 stroke engines
# Ships >= 500 GT – 2 stroke engines
def number_stroke(gt, ship_type) -> int:
    if ship_type in ['Container Ship', 'Bulk Carrier', 'General Cargo', 'Tanker']:
        if gt >= 500:
            return 2
        else:
            return 4
    else:
        return 4


# Get bore diameter acording to ship gt and ME stroke
def bore_diam(me_stroke, p_me):
    if me_stroke == 2:
        bore = 8.8608 * (p_me / 1000) + 291.14
    else:
        bore = 257.74 * math.log(p_me / 1000) - 177.14
    return bore


# calculate ME stroke
def stroke_calc(bore, me_stroke):
    if me_stroke == 2:
        stroke = bore * 1.25
    else:
        stroke = bore * 4.4
    return stroke


# Calculate Heavy Fuel Oil Consumption
def hfoc_calc(me, sfoc):
    hfoc = me * sfoc
    return hfoc


# Calculata HCM heat rejection
def hcm_calc(sfc):
    lhv = 42700
    ff = 0.56
    hcm = ((lhv * sfc) - 3600) * (1 - ff)
    return hcm


# Calculate ME displacement volume
def disp_vol(bore, stroke, n_cylinder):
    disp_volume = (np.pi/4) * ((bore / 1000) ** 2) * (stroke / 1000) * n_cylinder
    return disp_volume


# Calculate the swept volume for air compressor
def swept_vol(bore, stroke):
    swept_volume = np.pi * ((bore / (10 * 2)) ** 2) * (stroke / 10)
    return swept_volume


# Ballast pump capacity in m3/h according to ship type
def ballast_pump_capac(ship_type):
    if ship_type == 'Bulk Carrier':
        return 10000
    elif ship_type == 'Container Ship':
        return 2000
    elif ship_type == 'Fishing':
        return 100
    elif ship_type == 'General Cargo':
        return 2000
    elif ship_type == 'Others':
        return 1000
    elif ship_type == 'Passenger':
        return 500
    elif ship_type == 'Ro-Ro Cargo':
        return 2000
    elif ship_type == 'Tanker':
        return 10000


# Convert bar to mwc
def mwc(pressure) -> float:
    return pressure * 10


# Daily fuel oil consumption in m3/day
def dfoc_calc(hfoc):
    return (hfoc * 24) / (1000 * 0.96)


# Pump flow conversion m3/h to m3/s
def pump_flow_conv(flow) -> float:
    return (flow / 3600)


# Calculate the deck area for external illumination
def deck_a(ship_type, loa, breadth) -> float:
    if ship_type in ['Bulk Carrier', 'Tanker']:
        n = 0.91
    elif ship_type in ['Container Ship', 'General Cargo', 'Ro-Ro Cargo']:
        n = 0.88
    else:
        n = 0.84

    area = loa * breadth * n
    return area


# Calculate the provision plant volume
def prov_plant_vol(pob) -> int:
    return pob * 4

##############################################################
##############################################################
##############################################################
############ Electric equipment power calculation ############
##############################################################
##############################################################
##############################################################
#####################  Engine Room  ##########################
##############################################################
# Fuel Oil and Diesel Oil Purifier Feed Pump
def fo_p_f_p(hfoc, hcm, me_stroke) -> float:
    if me_stroke == 2:
        return 4e-07 * hfoc + 0.0417
    else:
        return 3e-07 * hcm + 0.0518


# Fuel Oil Circulating Pump
def fo_c_p(hfoc, me_stroke) -> float:
    if me_stroke == 2:
        return 1e-06 * hfoc + 0.4278
    else:
        return 3e-06 * hfoc - 0.1848


# Fuel Oil Supply Pump
def fo_s_p(hfoc, me_stroke) -> float:
    if me_stroke == 2:
        return 6e-07 * hfoc + 0.0866
    else:
        return 3e-06 * hfoc - 0.061


# Fuel oil and Diesel Oil Purifier
def fo_purif(hfoc, me_stroke) -> float:
    if me_stroke == 2:
        return 2e-06 * hfoc + 2.9358
    else:
        return 1e-06 * hfoc + 3.1114


# System Lube Oil Pump
def sys_lo_p(disp_volume, me_stroke) -> float:
    if me_stroke == 2:
        return 9.2414 * disp_volume + 20.656
    else:
        return 59.318 * disp_volume + 45.823


# Lube Oil Purifier Feed Pump
def lo_p_f_p(disp_volume, me_stroke) -> float:
    if me_stroke == 2:
        return 0.1265 * disp_volume + 0.1868
    else:
        return 0.6843 * disp_volume + 0.1458


# Lube Oil Purifier
def lo_p(disp_volume, me_stroke) -> float:
    if me_stroke == 2:
        return 0.4315 * disp_volume + 3.4796
    else:
        return 2.2101 * disp_volume + 3.4383


# SW Circulating Pump
def sw_c_p(sw_density, g) -> float:
    q_pump = 450 # m3/h
    pressure = 1.6 # bar
    Q_pump = pump_flow_conv(q_pump)
    H = mwc(pressure)
    n = 0.85 # efficiency

    return (Q_pump * H * g * sw_density) / n


# FW Circulating Central Pump
def fw_c_c_p(fw_density, g) -> float:
    q_pump = 210 # m3/h
    pressure = 2 # bar
    Q_pump = pump_flow_conv(q_pump)
    H = mwc(pressure)
    n = 0.85 # efficiency

    return (Q_pump * H * g * fw_density) / n


# FW Circulating Jacket Pump
def fw_c_j_p(fw_density, g) -> float:
    q_pump = 150 # m3/h
    pressure = 3.3 # bar
    Q_pump = pump_flow_conv(q_pump)
    H = mwc(pressure)
    n = 0.85 # efficiency

    return (Q_pump * H * g * fw_density) / n


# FW Generator
def fw_g(ship_type, pob) -> float:
    Vr = 3.72 # l/s
    if ship_type == 'Passenger Ship':
        Vs = (4e-08 * (Vr ** 3) - 1e-05 * (Vr ** 2) + 0.0973 * Vr + 0.77962) * 1.1 * pob
    else:
        Vs = (-3e-11 * (Vr ** 4) + 7e-08 * (Vr ** 3) - 5e-05 * (Vr ** 2) + 0.0343 * Vr + 0.593) * 1.1 * pob
    return 0.5373 * Vs + 1.1283


# Scruber for this we will assume that the pump is in open loop
def scruber_power(me_power) -> int:
    if (me_power / 1000) <= 5:
        return 65
    elif (me_power / 1000) <= 20:
        return 205
    else:
        return 395


# Sewage Treatment Plant
def sewage_t_p(ship_type, pob) -> float:
    if ship_type == 'Passenger Ship':
        n_sewage = 185
    else:
        n_sewage = 135
    v_sewage = n_sewage * pob
    Q_average_waste_water = v_sewage
    return 0.0003 * Q_average_waste_water + 1.9975


# ER Ventilation System
def er_v_sys(me_power, me_stroke, air_density) -> float:
    mcr = me_power
    if me_power >= 10000:
        p_ae = (0.025 * mcr) +250
    else:
        p_ae = (0.05 * mcr)
    
    if me_stroke == 2:
        m_ad = 0.0025 # kg/(kW*s) for 2-stroke engines
    else:
        m_ad = 0.002 # kg/(kW*s) for 2-stroke engines
    
    p_ref = 0.69 # kPa
    Q_er_vent = (me_power * m_ad + p_ae * m_ad) / air_density
    n = 0.85 # efficiency
    return (Q_er_vent * p_ref) / n


# Fuel Oil Transfer Pump
def fo_t_p(hfoc, me_stroke) -> float:
    if me_stroke == 2:
        return 1e-06 * hfoc + 0.8778
    else:
        return 2e-06 * hfoc + 0.0574


# Main Air Compressor
def m_air_c() -> float:
    ps = 3000 # corresponds to the exist pressure of the fluid in kPa (3000 kPa),
    pe = 101.325 # the entrance pressure in kPa (101.325 kPa),
    Q = 145 # the air flow in m3/h (145 m3/h),
    R = 287.05 # the gas constant in J/kgK (287.05 J/kgK),
    Cp = 1005 # is the specific heat in J/kgK (1005 J/kgK),
    v = 1.4 # is the isentropic coefficient (1.4),
    nc = 0.9 # compressor efficiency (0.9).
    p_c = ((pe * Q) / (3600 * R)) * Cp * ((((ps / pe) ** ((v - 1) / v)) - 1) / nc)
    return p_c


# Working Air Compressor
def w_air_c() -> float:
    ps = 1000 # corresponds to the exist pressure of the fluid in kPa (1000 kPa),
    pe = 101.325 # the entrance pressure in kPa (101.325 kPa),
    Q = 150 # the air flow in m3/h (150 m3/h),
    R = 287.05 # the gas constant in J/kgK (287.05 J/kgK),
    Cp = 1005 # is the specific heat in J/kgK (1005 J/kgK),
    v = 1.4 # is the isentropic coefficient (1.4),
    nc = 0.9 # compressor efficiency (0.9).
    p_c = ((pe * Q) / (3600 * R)) * Cp * ((((ps / pe) ** ((v - 1) / v)) - 1) / nc)
    return p_c


# Bilge Pump
def q_bilge_p(loa, breadth, depth) -> float:
    v_bilge = (1.68 * math.sqrt(loa * (breadth + depth))) + 25    
    return (5.75 * (v_bilge ** 2)) / (1000 * 3600)


# Bilge Pump
def bilge_p(fw_density, loa, breadth, depth, g) -> float:
    
    Q_bilge_p = q_bilge_p(loa, breadth, depth)
    
    pressure = 2 # bar
    H = mwc(pressure)
    n = 0.85 # efficiency
    
    return (Q_bilge_p * H * g * fw_density) / n


# ER Bilge Pump
def er_bilge_p(fw_density, g) -> float:
    q_pump = 5 # m3/h
    pressure = 3 # bar
    Q_pump = pump_flow_conv(q_pump)
    H = mwc(pressure)
    n = 0.85 # efficiency

    return (Q_pump * H * g * fw_density) / n


# Ballast Pump
def ballast_p(fw_density, q_ballast, g) -> float:
    pressure = 1.6 # bar
    Q_pump = pump_flow_conv(q_ballast)
    H = mwc(pressure)
    n = 0.85 # efficiency

    return (Q_pump * H * g * fw_density) / n


# Ballast Water Treatment System
def ballast_w_t_sys(q_ballast) -> float:
    return 0.0717 * (q_ballast ** 0.8789)


# ER Stripping Pump
def er_strip_p(me_power, oil_density, g) -> float:
    if me_power <= 1000:
        v_oily_tank = 4
    elif 1000 < me_power <= 20000:
        v_oily_tank = me_power / 250
    else:
        v_oily_tank = (me_power / 500) + 40

    Q_pump = v_oily_tank / (3600 * 1.5)
    pressure = 1 # bar
    H = mwc(pressure)
    n = 0.85 # efficiency

    return (Q_pump * H * g * oil_density) / n


# Oily Water Separator      
def oily_w_sep(gt) -> float:
    if gt <= 400:
        ows_cap = 0.25
    elif 400 < gt <= 1600:
        ows_cap = 0.5
    elif 1600 < gt <= 4000:
        ows_cap = 1
    elif 4000 < gt <= 15000:
        ows_cap = 2.5
    else:
        ows_cap = 5

    if ows_cap <= 2.5:
        return 3
    else:
        return 6


# Sludge Pump
def sludge_p(hfoc) -> float:
    k_ifo = 0.015
    t_voyage = 1 # We will assume 1 day as time of voyage
    dfoc = dfoc_calc(hfoc)
    v_sludge_t = k_ifo * dfoc * t_voyage

    t = 4 # Assuming 4 hours to drain the tank
    Q_sludge_p = v_sludge_t / (t * 3600)
    return 0.0003 * Q_sludge_p + 1.9975


# Main Fire Pump
def m_fire_p(fw_density, loa, breadth, depth, g):
    Q_bilge_p = q_bilge_p(loa, breadth, depth)
    Q_fire_pump = (4 / 3) * Q_bilge_p
    pressure = 2.7 # bar
    H = mwc(pressure)
    n = 0.85 # efficiency
    
    return (Q_fire_pump * H * g * fw_density) / n


# Emergence Fire Pump
def e_fire_p(fw_density, loa, breadth, depth, g):
    Q_bilge_p = q_bilge_p(loa, breadth, depth)
    Q_fire_pump = (4 / 3) * Q_bilge_p
    pressure = 2.7 # bar
    H = mwc(pressure)
    n = 0.85 # efficiency
    return ((Q_fire_pump * H * g * fw_density) / n) * 0.75


# FW Hydrophore Water Pumps
def fw_hydro_w_p(pob, fw_density, g) -> float:
    Q_pump = (pob * 1.1) / 1000
    pressure = 5 # bar
    H = mwc(pressure)
    n = 0.85 # efficiency
    
    return  (Q_pump * H * g * fw_density) / n


# Hydrophore Heater
def hydro_h(pob) -> float:
    if pob <= 10:
        return 15
    elif 10 < pob <= 20:
        return 30
    elif 20 < pob <= 50:
        return 40
    elif 50 < pob <= 100:
        return 80
    elif 100 < pob <= 150:
        return 100
    elif 150 < pob <= 200:
        return 160
    elif 200 < pob <= 300:
        return 200
    elif 300 < pob <= 500:
        return 300
    elif 500 < pob <= 700:
        return 400
    else:
        return 550


# Sewage Pump
def sewage_p(vel, depth, breadth, seawage_density, g) -> float:
    Q_pump = (0.00926 * vel * depth * breadth) / 3600
    pressure = 5 # bar
    H = mwc(pressure)
    n = 0.85 # efficiency
    
    return  (Q_pump * H * g * seawage_density) / n


###############################################################
####################  Deck Machinery  #########################
###############################################################
# Anchor Windlass
def anch_wind(dwt, g):
    diam_anch_chain = 1.714 * (dwt ** 0.3095)
    anchor_w = 0.1 * dwt
    anchor_chain = (0.0228 * (diam_anch_chain ** 2)) + (0.0567 * diam_anch_chain) - 1.4508
    w_total = anchor_w + (0.85 * anchor_chain)    
    v = 0.45 # Velocity of handling m/s
    n = 0.85

    return (w_total * g * v) / (1000 * n)


# Warping Winch
def warping_w():
    T = 260 # Hauling tension kN
    v = 15 # Velocity required m/min
    n = 0.85

    return (T * v) / (60 * n)


# Provision Crane
def prov_crane(g):
    prov_weight = 10000 # kg Assumed
    prov_c_velocity = (13 / 60) # m/s
    n = 0.85

    return (prov_weight * prov_c_velocity * g) / (1000 * n)


# Reefers Conatiners
def reefers_power(n_reefers, teus):
    if n_reefers == 0:
        reefers = int(((2e-06) * (teus ** 2)) + (0.0519 * teus))
    else:
        reefers = n_reefers

    return 11 * reefers


# Cargo Ventilation
def cargo_vent(n_reefers, teus, ship_type, gt):
    if ship_type == 'Container Ship':
        if n_reefers == 0:
            reefers = int(((2e-06) * (teus ** 2)) + (0.0519 * teus))
        else:
            reefers = n_reefers
        return 1.3 * (0.2 * reefers)
    else:
        cargo_vol = 2.83 * gt
        Q_fan = (20 * cargo_vol) / 3600
        n = 0.85
        return (Q_fan * 0.069) / n


##############################################################
#########################  Lighting  #########################
##############################################################
# Superstructure Illumination
def super_illum(ship_type, pob, n_lamp):
    cargo_ship: dict = {'Cargo_Ship': [0.00277, 0.00376, 0.00594, 0, 0.00095, 0.00036, 0.00174, 0.01208, 0.00342, 0.09497, 0.01632, 0.03254, 0.05887, 0.02208, 0.05768, 0.06829, 0, 0, 0, 0, 0]}
    passenger_ship: dict = {'Passenger_Ship': [0.0004425, 0.0001619, 0.000364, 0.0007953, 0.1029, 0.00034, 1.11e-05, 0.0027936, 0.0002384, 0.0431108, 0.0040339, 0, 0.0044776, 0, 0.0220603, 0.022808, 0.00192738, 1.2455, 0.02036, 0.07925, 2.50e-05]}
    illuminance: dict = {'Illuminance': [150, 150, 150, 150, 500, 300, 200, 300, 300, 100, 150, 200, 300, 300, 200, 300, 150, 300, 300, 300, 200]}
    fd = 2 # Depreciation factor Fd
    fs = 0.55 # Utilization factor Fs
    
    if ship_type == 'Passenger Ship':
        df = pd.DataFrame({
            'Passenger_Ship': passenger_ship['Passenger_Ship'],
            'Illuminance': illuminance['Illuminance']
        })
        luminous_flux = df['Illuminance'] * (df['Passenger_Ship'] * pob) * (fd / fs)
    else:
        df = pd.DataFrame({
            'Cargo_Ship': cargo_ship['Cargo_Ship'],
            'Illuminance': illuminance['Illuminance']
        })
        luminous_flux = df['Illuminance'] * (df['Cargo_Ship'] * pob) * (fd / fs)

    p_illum = luminous_flux.sum() / (1000 * n_lamp)
    return p_illum


# Engine Room Illumination
def er_illum(me, n_lamp):
    k = 1.8
    me_area = k * (me ** 0.5)
    me_illuminance = 300 * me_area * (1.75 / 0.55)
    return me_illuminance / (1000 * n_lamp)


# Exterior illumination (Deck)
def deck_illum(breadth, loa, n_lamp):
    deck_area = breadth * loa * 0.88
    deck_illum = 300 * deck_area * (1.5 / 0.8)
    
    return deck_illum / (1000 * n_lamp)


###############################################################
##################  Refrigeration Equipment  ##################
###############################################################
# Provision Plant System
def prov_plant(prov_p_vol):
    return 0.0705 * prov_p_vol + 2.8165


##############################################################
#####################  Galley Equipment  #####################
##############################################################
# Dish Wash Machine
def dish_m(pob):
    return 0.275 * pob


# Refrigerator
def refrig(pob):
    return 0.0175 * pob


# Microwaves
def microw(pob):
    return 0.09875 * pob


###############################################################
#####################  Laundry Equipment  #####################
###############################################################
# Dryer Machine
def dryer_m(pob):
    return 0.3816 * pob


# Washing Machine
def washing_m(pob):
    return 0.3032 * pob


# Funtion to get equipment power
def equip_power(equip, vessels: dict):
    ###############################################################
    ############  Variables for Equipment Calculation  ############
    ###############################################################
    me_stroke: int = number_stroke(vessels['GT'], vessels['Ship Type'])
    bore: float = bore_diam(me_stroke, vessels['ME'])
    stroke: float = stroke_calc(bore, me_stroke)
    hfoc: float = hfoc_calc(vessels['ME'], sfoc)
    hcm: float = hcm_calc(sfoc)
    disp_volume: float = disp_vol(bore, stroke, n_cylinder)
    swept_volume: float = swept_vol(bore, stroke)
    ballast_pump_capacity: int = ballast_pump_capac(vessels['Ship Type'])
    deck_area = deck_a(vessels['Ship Type'], vessels['LOA'], vessels['Breadth'])
    provision_plant_volume = prov_plant_vol(vessels['POB'])
    #####################  Engine Room  ##########################
    if equip == 'Fuel Oil Purifier Feed Pump':
        fo_purifier_feed_pump = fo_p_f_p(hfoc, hcm, me_stroke)
        return fo_purifier_feed_pump
    elif equip == 'Fuel Oil Circulating Pump':
        fo_circulating_pump = fo_c_p(hfoc, me_stroke)
        return fo_circulating_pump
    elif equip == 'Fuel Oil Supply Pump':
        fo_supply_pump = fo_s_p(hfoc, me_stroke)
        return fo_supply_pump
    elif equip == 'Fuel Oil Purifier':
        fo_purifier = fo_purif(hfoc, me_stroke)
        return fo_purifier
    elif equip == 'Diesel Oil Purifier Feed Pump':
        do_purifier_feed_pump = fo_p_f_p(hfoc, hcm, me_stroke)
        return do_purifier_feed_pump
    elif equip == 'Diesel Oil Purifier':
        do_purifier = fo_purif(hfoc, me_stroke)
        return do_purifier
    elif equip == 'System Lube Oil Pump':
        sys_lo_pump = sys_lo_p(disp_volume, me_stroke)
        return sys_lo_pump
    elif equip == 'Lube Oil Purifier Feed Pump':
        lo_purifier_feed_pump = lo_p_f_p(disp_volume, me_stroke)
        return lo_purifier_feed_pump
    elif equip == 'Lube Oil Purifier':
        lo_purifier = lo_p(disp_volume, me_stroke)
        return lo_purifier
    elif equip == 'SW Circulating Pump':
        sw_circulating_pump = sw_c_p(sw_density, g)
        return sw_circulating_pump
    elif equip == 'FW Circulating Central Pump':
        fw_circulating_central_pump = fw_c_c_p(fw_density, g)
        return fw_circulating_central_pump
    elif equip == 'FW Circulating Jacket Pump':
        fw_circulating_jacket_pump = fw_c_j_p(fw_density, g)
        return fw_circulating_jacket_pump
    elif equip == 'FW Generator':
        fw_generator = fw_g(vessels['Ship Type'], vessels['POB'])
        return fw_generator
    elif equip == 'Scrubber':
        scrubber = scruber_power(vessels['ME'])
        return scrubber
    elif equip == 'Sewage Treatment Plant':
        sewage_treatment_plant = sewage_t_p(vessels['Ship Type'], vessels['POB'])
        return sewage_treatment_plant
    elif equip == 'ER Ventilation System':
        er_ventilation_system = er_v_sys(vessels['ME'], me_stroke, air_density)
        return er_ventilation_system
    elif equip == 'Fuel Oil Transfer Pump':
        fo_transfer_pump = fo_t_p(hfoc, me_stroke)
        return fo_transfer_pump
    elif equip == 'Diesel Oil Transfer Pump':
        do_transfer_pump = fo_t_p(hfoc, me_stroke)
        return do_transfer_pump
    elif equip == 'Main Air Compressor':
        main_air_compressor = m_air_c()
        return main_air_compressor
    elif equip == 'Working Air Compressor':
        working_air_compressor = w_air_c()
        return working_air_compressor
    elif equip == 'Bilge Pump':
        bilge_pump = bilge_p(fw_density, vessels['LOA'], vessels['Breadth'], vessels['Depth'], g)
        return bilge_pump
    elif equip == 'ER Bilge Pump':
        er_bilge_pump = er_bilge_p(fw_density, g)
        return er_bilge_pump
    elif equip == 'Ballast Pump':
        ballast_pump = ballast_p(fw_density, q_ballast, g)
        return ballast_pump
    elif equip == 'Ballast Water Treatment System':
        ballast_water_treatment_system = ballast_w_t_sys(q_ballast)
        return ballast_water_treatment_system
    elif equip == 'ER Stripping Pump':
        er_stripping_pump = er_strip_p(vessels['ME'], oil_density, g)
        return er_stripping_pump
    elif equip == 'Oily Water Separator':
        oily_water_separator = oily_w_sep(vessels['GT'])
        return oily_water_separator
    elif equip == 'Sludge Pump':
        sludge_pump = sludge_p(hfoc)
        return sludge_pump
    elif equip == 'Main Fire Pump':
        main_fire_pump = m_fire_p(fw_density, vessels['LOA'], vessels['Breadth'], vessels['Depth'], g)
        return main_fire_pump
    elif equip == 'Emergence Fire Pump':
        emergency_fire_pump = e_fire_p(fw_density, vessels['LOA'], vessels['Breadth'], vessels['Depth'], g)
        return emergency_fire_pump
    elif equip == 'FW Hydrophore Water Pumps':
        fw_hydrophore_water_pump = fw_hydro_w_p(vessels['POB'], fw_density, g)
        return fw_hydrophore_water_pump
    elif equip == 'Hydrophore Heater':
        hydrophore_heater = hydro_h(vessels['POB'])
        return hydrophore_heater
    elif equip == 'Sewage Pump':
        sewage_pump = sewage_p(vessels['Velocity'], vessels['Depth'], vessels['Breadth'], seawage_density, g)
        return sewage_pump
    ####################  Deck Machinery  #########################
    elif equip == 'Anchor Windlass':
        anchor_windlass = anch_wind(vessels['DWT'], g)
        return anchor_windlass
    elif equip == 'Warping Winch':
        warping_winch = warping_w()
        return warping_winch
    elif equip == 'Provision Crane':
        provision_crane = prov_crane(g)
        return provision_crane
    elif equip == 'Reefer Containers':
        reefer_containers = reefers_power(n_reefers, vessels['TEUS'])
        return reefer_containers
    elif equip == 'Cargo Ventilation':
        cargo_ventilation = cargo_vent(n_reefers, vessels['TEUS'], vessels['Ship Type'], vessels['GT'])
        return cargo_ventilation
    ##########  Communication and Navigation Equipment  ##########
    elif equip == 'Girocompass':
        girocompass = 0.3
        return girocompass
    elif equip == 'ECDIS':
        ecdis = 0.16
        return ecdis
    elif equip == 'Speed Equipment':
        speed_equipment = 0.46
        return speed_equipment
    elif equip == 'Echo Sounder':
        echo_sounder = 0.24
        return echo_sounder
    elif equip == 'Radar':
        radar = 2.37
        return radar
    elif equip == 'Recorder':
        recorder = 0.11
        return recorder
    elif equip == 'BNAWS':
        bnaws = 0.08
        return bnaws
    elif equip == 'Satelite Nav Equipm':
        satelite_nav_equipm = 0.34
        return satelite_nav_equipm
    elif equip == 'Navtex Receiver':
        navtex_receiver = 0.14
        return navtex_receiver
    elif equip == 'INMARSAT Communication':
        inmarsat_communication = 0.97
        return inmarsat_communication
    elif equip == 'VHF':
        vhf = 0.28
        return vhf
    elif equip == 'Internal Telephone':
        internal_telephone = 0.35
        return internal_telephone
    elif equip == 'Batteries Chargers':
        batteries_chargers = 1
        return batteries_chargers
    elif equip == 'Clear Viewr Sreen':
        clear_viewr_sreen = 0.62
        return clear_viewr_sreen
    elif equip == 'Horn/Whistle':
        horn_whistle = 5.53
        return horn_whistle
    #########################  Lighting  #########################
    elif equip == 'Superstructure Illumination':
        superstructure_illumination = super_illum(vessels['Ship Type'], vessels['POB'], n_lamp['Fluorescent tube'])
        return superstructure_illumination
    elif equip == 'Engine Room Illumination':
        engine_room_illumination = er_illum(vessels['ME'], n_lamp['Fluorescent tube'])
        return engine_room_illumination
    elif equip == 'Exterior illumination (Deck)':
        deck_illumination = deck_illum(vessels['Breadth'], vessels['LOA'], n_lamp['LED'])
        return deck_illumination
    ##################  Refrigeration Equipment  ##################
    elif equip == 'Provision Plant System':
        provision_plant = prov_plant(prov_p_vol)
        return provision_plant
    ##########################  AC/HVAC  ##########################
    # HVAC systems will be assumer acording with others comercial ships data
    elif equip == 'AC Superstructure':
        ac_superstructure = 65
        return ac_superstructure
    elif equip == 'Superstructure Exhaust':
        superstructure_exhaust = 12
        return superstructure_exhaust
    elif equip == 'Galley Ventilation Fan':
        galley_ventilation_fan = 1.32
        return galley_ventilation_fan
    elif equip == 'WC Extra':
        wc_extra = 1.32
        return wc_extra
    elif equip == 'HVAC Echaust':
        hvac_echaust = 0.86
        return hvac_echaust
    elif equip == 'Deck Stores and Workshop Exhaust':
        deck_stores_and_workshop_exhaust = 0.81
        return deck_stores_and_workshop_exhaust
    #####################  Galley Equipment  #####################
    elif equip == 'Dish Wash Machine':
        dish_wash_machine = dish_m(vessels['POB'])
        return dish_wash_machine
    elif equip == 'Electric Range':
        electric_range = 9.7
        return electric_range
    elif equip == 'Hot Plate':
        hot_plate = 1.4
        return hot_plate
    elif equip == 'Refrigerator':
        refrigerator = refrig(vessels['POB'])
        return refrigerator
    elif equip == 'Microwaves':
        microwaves = microw(vessels['POB'])
        return microwaves
    elif equip == 'Electric Frying':
        electric_frying = 4.87
        return electric_frying
    ####################  Workshop Equipment  ####################
    elif equip == 'Drilling Machine':
        drilling_machine = 1.5
        return drilling_machine
    elif equip == 'Lathe':
        lathe = 6
        return lathe
    elif equip == 'Welding Transformer':
        welding_transformer = 13.5
        return welding_transformer
    elif equip == 'Double Grinder':
        double_grinder = 0.75
        return double_grinder
    #####################  Laundry Equipment  #####################
    elif equip == 'Dryer Machine':
        dryer_machine = dryer_m(vessels['POB'])
        return dryer_machine
    elif equip == 'Washing Machine':
        washing_machine = washing_m(vessels['POB'])
        return washing_machine
    else:
        return 0
