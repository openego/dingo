import os
import sys

# workaround: add dingo to sys.path to allow imports
PACKAGE_PARENT = '../../..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

import time
import matplotlib.pyplot as plt

from dingo.grid.mv_routing.models.models import Graph
from dingo.grid.mv_routing.util import util, data_input
from dingo.grid.mv_routing.solvers import savings, local_search
from dingo.grid.mv_routing.util.distance import calc_geo_distance_vincenty
from dingo.core.network.stations import *


def dingo_graph_to_routing_specs(graph):
    """ Build data dictionary from graph nodes for routing (translation)

    Args:
        graph: NetworkX graph object with nodes

    Returns:
        specs: Data dictionary for routing, See class `Graph()` in routing's model definition for keys
    """

    specs = {}
    nodes_demands = {}
    nodes_pos = {}
    for node in graph.nodes():
        if isinstance(node, StationDingo):
            nodes_pos[str(node)] = (node.geo_data.x, node.geo_data.y)

            if isinstance(node, LVStationDingo):
                nodes_demands[str(node)] = node.grid.region.peak_load_sum
            elif isinstance(node, MVStationDingo):
                nodes_demands[str(node)] = 0
                specs['DEPOT'] = str(node)

    specs['NODE_COORD_SECTION'] = nodes_pos
    specs['DEMAND'] = nodes_demands
    specs['MATRIX'] = calc_geo_distance_vincenty(nodes_pos)

    # TODO: capacity per MV ring (TEMP) -> Later tech. constraints are used for limitation of ring length
    specs['CAPACITY'] = 500000

    return specs


def routing_solution_to_dingo_graph(graph, solution):
    """ Insert `solution` from routing into `graph`

    Args:
        graph: NetworkX graph object with nodes
        solution: Instance of `BaseSolution` or child class (e.g. `LocalSearchSolution`) (=solution from routing)

    Returns:
        graph: NetworkX graph object with nodes and edges
    """

    # TODO: 1) check nodes from solution with nodes from graph, 2) map it!, 3) add edges to graph

    depot = solution._nodes[solution._problem._depot._name]
    for r in solution.routes():
        n1 = r._nodes[0:len(r._nodes)-1]
        n2 = r._nodes[1:len(r._nodes)]
        e = list(zip(n1, n2))
        e.append((depot, r._nodes[0]))
        e.append((r._nodes[-1], depot))
        g.add_edges_from(e)

    return graph

def solve(graph, debug=False):
    """ Do MV routing for given nodes in `graph`. Translate data from node objects to appropriate format before.

    Args:
        graph: NetworkX graph object with nodes
        debug: If True, information is printed while routing

    Returns:
        graph: NetworkX graph object with nodes and edges
    """

    # TODO: Implement debug mode (pass to solver) to get more information while routing (print routes, draw network, ..)

    # translate DINGO graph to routing specs
    specs = dingo_graph_to_routing_specs(graph)

    # create routing graph using specs
    RoutingGraph = Graph(specs)

    timeout = 30000

    # create solver objects
    savings_solver = savings.ClarkeWrightSolver()
    local_search_solver = local_search.LocalSearchSolver()

    start = time.time()

    # create initial solution using Clarke and Wright Savings methods
    savings_solution = savings_solver.solve(RoutingGraph, timeout)

    # OLD, MAY BE USED LATER - Guido, please don't declare a variable later=now() :) :
    #if not savings_solution.is_complete():
    #    print('=== Solution is not a complete solution! ===')

    if debug:
        print('ClarkeWrightSolver solution:')
        util.print_solution(savings_solution)
        print('Elapsed time (seconds): {}'.format(time.time() - start))
        #savings_solution.draw_network()

    # improve initial solution using local search
    local_search_solution = local_search_solver.solve(RoutingGraph, savings_solution, timeout)

    if debug:
        print('Local Search solution:')
        util.print_solution(local_search_solution)
        print('Elapsed time (seconds): {}'.format(time.time() - start))
        local_search_solution.draw_network()

    return routing_solution_to_dingo_graph(graph, local_search_solution)