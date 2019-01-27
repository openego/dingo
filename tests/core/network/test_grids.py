import pytest

from egoio.tools import db
from sqlalchemy.orm import sessionmaker
import oedialect

import networkx as nx
import pandas as pd

from shapely.geometry import Point, LineString, LinearRing, Polygon
from ding0.core import NetworkDing0
from ding0.core.network import (RingDing0, BranchDing0, CircuitBreakerDing0,
                                GeneratorDing0, GeneratorFluctuatingDing0)
from ding0.core.network.stations import MVStationDing0, LVStationDing0
from ding0.core.network.grids import MVGridDing0, LVGridDing0


class TestMVGridDing0(object):

    @pytest.fixture
    def empty_mvgridding0(self):
        """
        Returns an empty MVGridDing0 object
        """
        station = MVStationDing0(id_db=0, geo_data=Point(0.5, 0.5))
        grid = MVGridDing0(id_db=0,
                           station=station)
        return grid

    def test_empty_mvgridding0(self, empty_mvgridding0):
        assert empty_mvgridding0._rings == []
        assert empty_mvgridding0._circuit_breakers == []
        assert empty_mvgridding0.default_branch_kind is None
        assert empty_mvgridding0.default_branch_type is None
        assert empty_mvgridding0.default_branch_kind_settle is None
        assert empty_mvgridding0.default_branch_type_settle is None
        assert empty_mvgridding0.default_branch_kind_aggregated is None
        assert empty_mvgridding0.default_branch_type_aggregated is None
        assert empty_mvgridding0._station.id_db == 0
        assert empty_mvgridding0._station.geo_data == Point(0.5, 0.5)

    def test_add_circuit_breakers(self, empty_mvgridding0):
        circuit_breaker = CircuitBreakerDing0(id_db=0,
                                              geo_data=Point(0, 0),
                                              grid=empty_mvgridding0)
        empty_mvgridding0.add_circuit_breaker(circuit_breaker)
        circuit_breakers_in_grid = list(empty_mvgridding0.circuit_breakers())
        assert len(circuit_breakers_in_grid) == 1
        assert circuit_breakers_in_grid[0] == circuit_breaker

    def test_add_circuit_breakers_negative(self, empty_mvgridding0):
        bad_object = GeneratorDing0(id_db=0)
        empty_mvgridding0.add_circuit_breaker(bad_object)
        circuit_breakers_in_grid = list(empty_mvgridding0.circuit_breakers())
        assert len(circuit_breakers_in_grid) == 0

    @pytest.fixture
    def circuit_breaker_mvgridding0(self):
        """
        Returns an MVGridDing0 object with a branch and a
        circuit breaker
        """
        station = MVStationDing0(id_db=0, geo_data=Point(0.5, 0.5))
        grid = MVGridDing0(id_db=0,
                           station=station)
        branch = BranchDing0(id_db=0, length=2.0, kind='cable')
        circuit_breaker = CircuitBreakerDing0(id_db=0,
                                              geo_data=Point(0, 0),
                                              branch=branch,
                                              grid=grid)
        grid.add_circuit_breaker(circuit_breaker)
        grid._graph.add_edge(circuit_breaker, station,
                             branch=branch)
        return grid

    def test_open_circuit_breakers(self, circuit_breaker_mvgridding0):
        circuit_breakers_in_grid = list(
            circuit_breaker_mvgridding0.circuit_breakers()
        )
        assert circuit_breakers_in_grid[0].status == 'closed'
        circuit_breaker_mvgridding0.open_circuit_breakers()
        assert circuit_breakers_in_grid[0].status == 'open'

    def test_close_circuit_breakers(self, circuit_breaker_mvgridding0):
        circuit_breakers_in_grid = list(
            circuit_breaker_mvgridding0.circuit_breakers()
        )
        assert circuit_breakers_in_grid[0].status == 'closed'
        circuit_breaker_mvgridding0.open_circuit_breakers()
        assert circuit_breakers_in_grid[0].status == 'open'
        circuit_breaker_mvgridding0.close_circuit_breakers()
        assert circuit_breakers_in_grid[0].status == 'closed'

    @pytest.fixture
    def ring_mvgridding0(self):
        """
        Returns an MVGridDing0 object with 2 branches
        a circuitbreaker and a ring
        """
        station = MVStationDing0(id_db=0, geo_data=Point(1, 1))
        grid = MVGridDing0(id_db=0,
                           station=station)
        generator1 = GeneratorDing0(id_db=0,
                                    geo_data=Point(1, 2),
                                    mv_grid=grid)
        grid.add_generator(generator1)
        generator2 = GeneratorDing0(id_db=1,
                                    geo_data=Point(2, 1),
                                    mv_grid=grid)
        grid.add_generator(generator2)
        generator3 = GeneratorDing0(id_db=2,
                                    geo_data=Point(2, 2),
                                    mv_grid=grid)
        grid.add_generator(generator3)
        ring = RingDing0(grid=grid)
        branch1 = BranchDing0(id_db='0', length=2.0, kind='cable', ring=ring)
        branch1a = BranchDing0(id_db='0a', lenght=1.2, kind='cable', ring=ring)
        branch2 = BranchDing0(id_db='1', lenght=3.0, kind='line', ring=ring)
        branch2a = BranchDing0(id_db='1a', lenght=2.0, kind='line', ring=ring)
        branch3 = BranchDing0(id_db='2', length=2.5, kind='line')
        circuit_breaker1 = CircuitBreakerDing0(id_db=0,
                                               geo_data=Point(0, 0),
                                               branch=branch1,
                                               grid=grid)
        grid.add_circuit_breaker(circuit_breaker1)
        grid._graph.add_edge(generator1, station,
                             branch=branch1)
        grid._graph.add_edge(circuit_breaker1, generator1,
                             branch=branch1a)
        grid._graph.add_edge(generator2, station,
                             branch=branch2)
        grid._graph.add_edge(circuit_breaker1, generator2,
                             branch=branch2a)
        grid._graph.add_edge(generator3, generator2, branch=branch3)
        grid.add_ring(ring)
        return (ring, grid)

    def test_add_ring(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        assert len(grid._rings) == 1
        assert grid._rings[0] == ring

    def test_rings_count(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        assert grid.rings_count() == 1
        assert grid._rings[0] == ring

    def test_get_ring_from_node(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        station = grid.station()
        assert grid.get_ring_from_node(station) == ring

    def test_rings_nodes_root_only_include_root(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        station = grid.station()
        generators = list(grid.generators())
        circuit_breakers = list(grid.circuit_breakers())
        rings_nodes_expected = [generators[0],
                                circuit_breakers[0],
                                generators[1],
                                station]
        rings_nodes = list(grid.rings_nodes(include_root_node=True))[0]
        assert rings_nodes == rings_nodes_expected

    def test_rings_nodes_root_only_exclude_root(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        generators = list(grid.generators())
        circuit_breakers = list(grid.circuit_breakers())
        rings_nodes_expected = [generators[0],
                                circuit_breakers[0],
                                generators[1]]
        rings_nodes = list(grid.rings_nodes(include_root_node=False))[0]
        assert rings_nodes == rings_nodes_expected

    def test_rings_nodes_include_satellites_include_root(self,
                                                         ring_mvgridding0):
        ring, grid = ring_mvgridding0
        station = grid.station()
        generators = list(grid.generators())
        circuit_breakers = list(grid.circuit_breakers())
        rings_nodes_expected = [generators[0],
                                circuit_breakers[0],
                                generators[1],
                                station,
                                generators[2]]
        rings_nodes = list(grid.rings_nodes(include_root_node=True,
                                            include_satellites=True))[0]
        assert rings_nodes == rings_nodes_expected

    def test_rings_nodes_include_satellites_exclude_root(self,
                                                         ring_mvgridding0):
        ring, grid = ring_mvgridding0
        generators = list(grid.generators())
        circuit_breakers = list(grid.circuit_breakers())
        rings_nodes_expected = [generators[0],
                                circuit_breakers[0],
                                generators[1],
                                generators[2]]
        rings_nodes = list(grid.rings_nodes(include_root_node=False,
                                            include_satellites=True))[0]
        assert rings_nodes == rings_nodes_expected

    def test_rings_full_data(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        station = grid.station()
        generators = list(grid.generators())
        circuit_breakers = list(grid.circuit_breakers())
        branches = sorted(list(map(lambda x: x['branch'],
                                   grid.graph_edges())),
                          key=lambda x: repr(x))
        ring_expected = ring
        # branches following the ring
        branches_expected = [branches[1],
                             branches[0],
                             branches[3],
                             branches[2]]
        rings_nodes_expected = [generators[0],
                                circuit_breakers[0],
                                generators[1],
                                station]
        (ring_out,
         branches_out,
         rings_nodes_out) = list(grid.rings_full_data())[0]
        assert ring_out == ring_expected
        assert branches_out == branches_expected
        assert rings_nodes_out == rings_nodes_expected

    def test_graph_nodes_from_subtree_station(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        station = grid.station()
        nodes_out = grid.graph_nodes_from_subtree(station)
        nodes_expected = []
        assert nodes_out == nodes_expected

    def test_graph_nodes_from_subtree_circuit_breaker(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        circuit_breakers = list(grid.circuit_breakers())
        nodes_out = grid.graph_nodes_from_subtree(circuit_breakers[0])
        nodes_expected = []
        assert nodes_out == nodes_expected

    def test_graph_nodes_from_subtree_ring_branch_left(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        generators = list(grid.generators())
        nodes_out = grid.graph_nodes_from_subtree(generators[0])
        nodes_expected = []
        assert nodes_out == nodes_expected

    def test_graph_nodes_from_subtree_ring_branch_right(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        generators = list(grid.generators())
        nodes_out = grid.graph_nodes_from_subtree(generators[1])
        nodes_expected = [generators[2]]
        assert nodes_out == nodes_expected

    def test_graph_nodes_from_subtree_off_ring(self, ring_mvgridding0):
        ring, grid = ring_mvgridding0
        generators = list(grid.generators())
        nodes_out = grid.graph_nodes_from_subtree(generators[2])
        nodes_expected = []
        assert nodes_out == nodes_expected

    @pytest.fixture
    def oedb_session(self):
        """
        Returns an ego.io oedb session and closes it on finishing the test
        """
        engine = db.connection(section='oedb')
        session = sessionmaker(bind=engine)()
        yield session
        print("closing session")
        session.close()

    def test_routing(self, oedb_session):
        # instantiate new ding0 network object
        nd = NetworkDing0(name='network')

        nd.import_mv_grid_districts(oedb_session,
                                    mv_grid_districts_no=[460])
        # STEP 2: Import generators
        nd.import_generators(oedb_session)
        # STEP 3: Parametrize MV grid
        nd.mv_parametrize_grid()
        # STEP 4: Validate MV Grid Districts
        nd.validate_grid_districts()
        # STEP 5: Build LV grids
        nd.build_lv_grids()

        graph = nd._mv_grid_districts[0].mv_grid._graph

        assert len(graph.nodes()) == 256
        assert len(graph.edges()) == 0
        assert len(nx.isolates(graph)) == 256
        assert pd.Series(graph.degree()).sum(axis=0) == 0
        assert pd.Series(graph.degree()).mean(axis=0) == 0.0
        assert len(nx.get_edge_attributes(graph, 'branch')) == 0
        assert nx.average_node_connectivity(graph) == 0.0
        assert pd.Series(
            nx.degree_centrality(graph)
            ).mean(axis=0) == 0.0
        assert pd.Series(
            nx.closeness_centrality(graph)
            ).mean(axis=0) == 0.0
        assert pd.Series(
            nx.betweenness_centrality(graph)
            ).mean(axis=0) == 0.0

        nd.mv_routing()

        assert len(graph.nodes()) == 269
        assert len(graph.edges()) == 218
        assert len(nx.isolates(graph)) == 54
        assert pd.Series(graph.degree()).sum(axis=0) == 436
        assert pd.Series(
            graph.degree()
            ).mean(axis=0) == pytest.approx(1.62, 0.001)
        assert len(nx.get_edge_attributes(graph, 'branch')) == 218
        assert nx.average_node_connectivity(graph) == pytest.approx(
            0.688,
            abs=0.0001
            )
        assert pd.Series(
            nx.degree_centrality(graph)
            ).mean(axis=0) == pytest.approx(0.006, abs=0.001)
        assert pd.Series(
            nx.closeness_centrality(graph)
            ).mean(axis=0) == pytest.approx(0.042474, abs=0.00001)
        assert pd.Series(
            nx.betweenness_centrality(graph)
            ).mean(axis=0) == pytest.approx(0.0354629, abs=0.00001)
        assert pd.Series(
            nx.edge_betweenness_centrality(graph)
            ).mean(axis=0) == pytest.approx(0.04636150, abs=0.00001)


class TestLVGridDing0(object):

    @pytest.fixture
    def empty_lvgridding0(self):
        """
        Returns and empty LVGridDing0 object
        """
        lv_station = LVStationDing0(id_db=0, geo_data=Point(1, 1))
        grid = LVGridDing0(id_db=0, station=lv_station)
        return grid


if __name__ == "__main__":
    pass