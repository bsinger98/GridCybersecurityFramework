import networkx as nx


class GridSimulator:

    def __init__(self, power_flow_case, droop_limit=.05, slack_ramp_limit=.1, agc_limit=.1, total_agc_reserves=0):

        self.power_flow_case = power_flow_case
        self.ranBaseline = False

        # Reserve generation assumptions
        self.droop_limit = droop_limit
        self.total_agc_reserves = total_agc_reserves
        self.agc_limit = agc_limit
        self.slack_ramp_limit = slack_ramp_limit

        return

    # Must run a baseline for each case before running
    def run_baseline(self):
        # TODO Solve power flow equations
        solved_power_flow_case = self.power_flow_case

        if len(solved_power_flow_case.slack_generators) == 0:
            raise Exception('Error: Could not find a slack generator for the test case')

        # TODO if multiple slack generators choose the largest one for baseline measurements
        if len(solved_power_flow_case.slack_generators) > 1:
            raise Exception('Error: Test case has multiple slack generators during baseline')

        slack_generator = solved_power_flow_case.slack_generators[0]

        # Determine baseline slack information
        self.slack_limited_pmax = slack_generator.Pd + slack_generator.Pd * self.slack_ramp_limit
        self.slack_limited_pmin = slack_generator.Pd - slack_generator.Pd * self.slack_ramp_limit
        self.slack_reference_power = (self.slack_limited_pmax + self.slack_limited_pmin) / 2

        # Select AGC generators
        self.agc_gens = []
        sorted_gens = sorted(solved_power_flow_case.active_generators, key=lambda gen: gen.Pg, reverse=True)
        agc_gen_added = 0
        for gen in sorted_gens:
            if agc_gen_added >= self.total_agc_reserves:
                break
            # Skip generator if generator is off or generator is responsive reserve generation
            if not gen.active or gen.ckt == 'RG':
                continue

            self.agc_gens.append(gen.bus_number)
            agc_gen_added += ((gen.Pg * self.agc_limit) - (gen.Pg * self.droop_limit)) * solved_power_flow_case.baseMVA

        # Create graph of grid for contingency analysis
        self.grid_graph = nx.MultiGraph()

        # Gather total power on each bus
        bus_powers = {}
        for gen in solved_power_flow_case.active_generators:
            if gen.bus_number not in bus_powers:
                bus_powers[gen.bus_number] = 0
            bus_powers[gen.bus_number] += gen.Pg
        for load in solved_power_flow_case.loads:
            if load.bus_number not in bus_powers:
                bus_powers[load.bus_number] = 0
            bus_powers[load.bus_number] -= load.Pd
        for slack in solved_power_flow_case.slack_generators:
            if slack.bus_number not in bus_powers:
                bus_powers[slack.bus_number] = 0
            bus_powers[slack.bus_number] += slack.Pd

        # Add nodes with power details
        nodes = []
        for bus in solved_power_flow_case.buses:
            bus_power = 0
            if bus.bus_number in bus_powers:
                bus_power = bus_powers[bus.bus_number]
            self.grid_graph.add_node(bus.bus_number, power=bus_power)

        # Add edges
        for branch in solved_power_flow_case.active_branches:
            self.grid_graph.add_edge(branch.from_bus, branch.to_bus, key=f'line_{branch.branch_id}')

        self.ranBaseline = True
        self.baseline_slack_p = 0
        self.baseline_slack_pmin = 0
        self.baseline_slack_pmax = 0

    def run_simulation(self):
        if not self.ranBaseline:
            raise Exception("Error: you have to run a baseline before simulating grid")

