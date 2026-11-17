import simpy
from agents.yard_crane import YardCrane
from agents.internal_truck import InternalTruck
from agents.quay_crane import QuayCrane
from agents.external_truck import ExternalTruck
from agents.vessel import Vessel
from agents.onshore_power_supply import OnshorePowerSupply
from agents.it_charging_station import ITChargingStation
from agents.et_charging_station import ETChargingStation

class AgentFactory:
    def __init__(self, env, terminal, schedule, logger, run_time, state):
        self.env = env
        self.terminal = terminal
        self.schedule = schedule
        self.logger = logger
        self.run_time = run_time
        self.state = state

    def create_all_agents(self):
        """A single public method to run the entire creation process."""
        self._preprocess_ET_schedule()
        self._create_yard_crane_agents()
        self._create_internal_truck_agents()
        self._create_quay_crane_agents()
        self._create_external_truck_agents()
        self._create_vessel_agents()
        self._create_onshore_power_supply_agents()
        self._create_it_charging_station_agents()
        self._create_et_charging_station_agents()

    def _preprocess_ET_schedule(self):
        truck_arrivals_by_block = {}
        for et_id, et_details in self.schedule.ets_schedule.items():
            block_id = et_details.get('target_block_id')
            if block_id is not None:
                if block_id not in truck_arrivals_by_block:
                    truck_arrivals_by_block[block_id] = []
                truck_arrivals_by_block[block_id].append(et_details['early_arrival_time'])
        for block_id in truck_arrivals_by_block:
            truck_arrivals_by_block[block_id].sort()
        self.truck_arrivals_by_block = truck_arrivals_by_block

    def _create_yard_crane_agents(self):
        for numeric_id, original_id in self.state.yc_id_map.items():
            yc_info = self.terminal.ycs[original_id]
            self.state.all_yc_agents[numeric_id] = YardCrane(
                env=self.env, yc_id=numeric_id, layer=yc_info['layer'],
                handling_time=yc_info['cycle'],
                et_schedule=self.truck_arrivals_by_block.get(numeric_id, []),
                vessel_agents_ref=self.state.vessel_agents,
                vessel_at_berth_stats_ref=self.state.vessel_at_berth,
                logger=self.logger,
                yc_simpy_resource=simpy.Resource(self.env, capacity=1),
                original_string_id_param=original_id,
                yc_agent_working_stats_ref=self.state.yc_agent_working_stats,
                yard_block_stores_ref=self.state.yard_block_stores,
                container_location_map_ref=self.state.container_location_map
            )

    def _create_internal_truck_agents(self):
        ready_it_pool_ref = self.state.ready_it_pool
        charging_queue_ref = self.state.it_charging_queue
        it_individual_resources_ref = self.state.it_individual_resources
        for it_id, resource in it_individual_resources_ref.items():
            it_agent = InternalTruck(
                env=self.env, it_id=it_id, it_resource=resource,
                all_yc_agents_ref=self.state.all_yc_agents, logger=self.logger,
                it_speeds=self.terminal.its,
                qc_to_yc_distances=self.terminal.qc_to_yc_distances,
                yc_id_map=self.state.yc_id_map
            )
            self.state.all_it_agents.append(it_agent)
            if it_agent.charge_percent < 90:
                priority = 90 - it_agent.charge_percent
                charging_queue_ref.put(simpy.PriorityItem(priority, it_agent))
            else:
                ready_it_pool_ref.put(it_agent)

    def _create_quay_crane_agents(self):
        qc_agent_pool_ref = self.state.qc_agent_pool
        for qc_id in self.terminal.qcs.keys():
            qc_agent = QuayCrane(
                env=self.env, qc_id=qc_id,
                handling_time=self.terminal.qcs[qc_id]['cycle'],
                crew_size=self.terminal.qcs[qc_id]['it_crew'],
                logger=self.logger, qc_working_stats=self.state.qc_working,
                ready_it_pool=self.state.ready_it_pool,
                it_charging_queue=self.state.it_charging_queue,
                container_location_map=self.state.container_location_map,
                all_created_reefers_list_ref=self.state.all_created_reefers
            )
            qc_agent_pool_ref.put(qc_agent)

    def _create_external_truck_agents(self):
        et_agents = {}
        for et_id, et_details in self.schedule.ets_schedule.items():
            et_agent = ExternalTruck(
                env=self.env, et_id=et_id, schedule_details=et_details,
                all_yc_agents_ref=self.state.all_yc_agents,
                yard_block_stores=self.state.yard_block_stores,
                et_charging_queue=self.state.et_charging_queue,
                logger=self.logger
            )
            et_agents[et_id] = et_agent
            self.state.all_et_agents.append(et_agent)

    def _create_vessel_agents(self):
        for visit_id, v_details in self.schedule.ships_schedule.items():
            vessel_imo = v_details["imo"]
            
            self.state.vessel_agents[visit_id] = Vessel(
                env=self.env, 
                vessel_id=visit_id, 
                imo=vessel_imo,
                eta=v_details["eta"],
                real_eta = v_details["real_eta"],
                etd=v_details["etd"],
                real_etd = v_details["real_etd"],
                master_operation_list=v_details["master_operation_list"],
                berth_resource_pool=self.state.berth_resource,
                qc_agent_pool=self.state.qc_agent_pool,
                vessel_agents_ref=self.state.vessel_agents,
                vessel_at_berth_stats_dict=self.state.vessel_at_berth,
                logger=self.logger, 
                ops_agent_pool=self.state.ops_agent_pool,
                ops_vessel_log=self.state.ops_vessel_log,
                run_time=self.run_time,
                teus=v_details["teus"],
                vessel_manifest_parser=self.schedule.vessel_manifest_parser,
                container_location_map=self.state.container_location_map
            )
            
    def _create_onshore_power_supply_agents(self):
        ops_agent_pool_ref = self.state.ops_agent_pool
        for index, row in self.terminal.ops_data.iterrows():
            station = OnshorePowerSupply(env=self.env, ops_data=row)
            ops_agent_pool_ref.put(station)
            print(f"OPS Unit {station.id} created at {station.berth} and is available.")

    def _create_it_charging_station_agents(self):
        if not self.terminal.it_chargers_df.empty:
            for index, row in self.terminal.it_chargers_df.iterrows():
                station_id = row['Charger_ID']
                charge_rate = row['Charger_Output_kW']
                efficiency = row['Efficiency']
                self.state.it_station_configs[station_id] = {
                    'charge_rate_kw': charge_rate, 'efficiency': efficiency
                }
                ITChargingStation(
                    env=self.env, station_id=station_id,
                    charge_rate_kw=charge_rate, efficiency=efficiency,
                    it_charging_log_ref=self.state.it_charging_log,
                    it_charging_queue_ref=self.state.it_charging_queue,
                    ready_it_pool_ref=self.state.ready_it_pool,
                    station_power_profiles_ref=self.state.it_station_power_profiles,
                    run_time=self.run_time
                )
                print(f"IT Charging Station {station_id} created and available.")

    def _create_et_charging_station_agents(self):
        if not self.terminal.et_chargers_df.empty:
            for index, row in self.terminal.et_chargers_df.iterrows():
                station_id = row['Charger_ID']
                charge_rate = row['Charger_Output_kW']
                efficiency = row['Efficiency']
                self.state.et_station_configs[station_id] = {
                    'charge_rate_kw': charge_rate, 'efficiency': efficiency
                }
                ETChargingStation(
                    env=self.env, station_id=station_id,
                    charge_rate_kw=charge_rate, efficiency=efficiency,
                    charging_queue_ref=self.state.et_charging_queue,
                    et_charging_log_ref=self.state.et_charging_log,
                    power_profiles_ref=self.state.et_station_power_profiles,
                    run_time=self.run_time
                )
                print(f"ET Charging Station {station_id} created and active.")