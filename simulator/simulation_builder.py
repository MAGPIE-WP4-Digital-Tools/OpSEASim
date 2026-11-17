from simulator.terminal_parser import TerminalParser
from simulator.schedule import Schedule
from simulator.simulation_manager import SimulationManager
from parsers.initial_yard_parser import InitialYardParser
from parsers.vessel_manifest_parser import VesselManifestParser
from parsers.external_truck_parser import ExternalTruckParser
from parsers.vessel_schedule_parser import VesselScheduleParser
from utils.paths import DATA_DIR

class SimulationBuilder:
    def __init__(self, configuration):
        self.configuration = configuration
        self.start = configuration["start_date"]
        self.end = configuration["end_date"]
        self.terminal_name = configuration["terminal_name"]

    def build(self):
        """
        Handles the entire simulation setup and returns the ready-to-run simulation manager.
        """
        # --- Core Component Setup ---
        terminal = TerminalParser(self.terminal_name)
        sim_manager = SimulationManager(terminal)
        sim_manager.setup_environment()
        sim_manager.configuration = self.configuration
        state = sim_manager.state
        env = sim_manager.env

        # --- 1. Parse Vessel Schedule ---
        vessel_schedule_parser = VesselScheduleParser(DATA_DIR / 'calls.csv', DATA_DIR / 'vessels.csv')
        active_vessels_df = vessel_schedule_parser.get_schedule_for_window(self.start, self.end, self.terminal_name)
        
        # --- Corrected TEU Check ---
        # Get all IMOs that are active in this specific simulation run
        active_imos = set(active_vessels_df['imo'].unique())
        
        # Get the list of ALL vessels that had missing TEUs from the parser
        all_problematic_imos = set(vessel_schedule_parser.missing_teu_imos)
        
        # Find the intersection: problematic vessels that are ALSO active in our simulation
        active_problematic_imos = active_imos.intersection(all_problematic_imos)

        if active_problematic_imos:
            logger = sim_manager.logger
            env = sim_manager.env
            # Sort the list for consistent, readable output
            for imo in sorted(list(active_problematic_imos)):
                logger.log(env, "Data_Warning", vessel_id=imo, extra_info="Vessel is missing TEU value in input file.")
        
        # *** Store the filtered DataFrame in the state object ***
        state.active_vessels_df = active_vessels_df

        # --- 2. Parse Yard, Manifests, and Trucks ---
        yard_parser = InitialYardParser(env, terminal, state.all_created_reefers)
        if yard_parser.initial_yard_df is None:
            yard_parser.generate_random_inventory(None,0)
        yard_parser.populate_yard_stores(state.yard_block_stores, state.container_location_map)

        dry_blocks, reefer_blocks = yard_parser.get_block_lists_by_type()
        state.dry_l1_blocks, state.reefer_l1_blocks = dry_blocks[1], reefer_blocks[1]
        state.dry_l2_blocks, state.reefer_l2_blocks = dry_blocks[2], reefer_blocks[2]
        
        vessel_manifest_parser = VesselManifestParser(env, state.dry_l1_blocks, state.reefer_l1_blocks,
                                                      yard_parser.initial_containers_by_block, state.all_created_reefers,
                                                      state.container_location_map, active_vessels_df, self.start,
                                                      sim_manager.logger, state.yard_block_stores) 
        truck_parser = ExternalTruckParser(env, state.dry_l2_blocks, state.reefer_l2_blocks,
                                           state.container_location_map, state.all_created_reefers)

        # --- 3. CREATE THE FINAL SCHEDULE ---
        schedule = Schedule(self.start, active_vessels_df, vessel_manifest_parser, truck_parser)
        sim_manager.schedule = schedule

        return sim_manager