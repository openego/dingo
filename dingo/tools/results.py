"""This file is part of DINGO, the DIstribution Network GeneratOr.
DINGO is a tool to generate synthetic medium and low voltage power
distribution grids based on open data.

It is developed in the project open_eGo: https://openegoproject.wordpress.com

DINGO lives at github: https://github.com/openego/dingo/
The documentation is available on RTD: http://dingo.readthedocs.io"""

__copyright__  = "Reiner Lemoine Institut gGmbH"
__license__    = "GNU Affero General Public License Version 3 (AGPL-3.0)"
__url__        = "https://github.com/openego/dingo/blob/master/LICENSE"
__author__     = "nesnoj, gplssm"


import pickle
import os
import pandas as pd

from dingo.tools import config as cfg_dingo
from matplotlib import pyplot as plt
import seaborn as sns

# import DB interface from oemof
import oemof.db as db
from dingo.core import NetworkDingo
from dingo.core import GeneratorDingo
from dingo.core import MVCableDistributorDingo
from dingo.core import LVStationDingo
from dingo.core import CircuitBreakerDingo

from shapely.ops import transform
import pyproj
from functools import partial

import multiprocessing as mp

from math import floor, ceil


def lv_grid_generators_bus_bar(nd):
    """
    Calculate statistics about generators at bus bar in LV grids

    Parameters
    ----------
    nd : dingo.NetworkDingo
        Network container object

    Returns
    -------
    lv_stats : dict
        Dict with keys of LV grid repr() on first level. Each of the grids has
        a set of statistical information about its topology
    """

    lv_stats = {}

    for la in nd._mv_grid_districts[0].lv_load_areas():
        for lvgd in la.lv_grid_districts():

            station_neighbors = list(lvgd.lv_grid._graph[
                                         lvgd.lv_grid._station].keys())

            # check if nodes of a statio are members of list generators
            station_generators = [x for x in station_neighbors
                                  if x in lvgd.lv_grid.generators()]

            lv_stats[repr(lvgd.lv_grid._station)] = station_generators


    return lv_stats

#here original position of function mvgdstats

def save_nd_to_pickle(nd, path='', filename=None):
    """
    Use pickle to save the whole nd-object to disc

    Parameters
    ----------
    nd : NetworkDingo
        Dingo grid container object
    path : str
        Absolute or relative path where pickle should be saved. Default is ''
        which means pickle is save to PWD
    """

    abs_path = os.path.abspath(path)


def save_nd_to_pickle(nd, path='', filename=None):
    """
    Use pickle to save the whole nd-object to disc
    Parameters
    ----------
    nd : NetworkDingo
        Dingo grid container object
    path : str
        Absolute or relative path where pickle should be saved. Default is ''
        which means pickle is save to PWD
    """

    abs_path = os.path.abspath(path)

    if len(nd._mv_grid_districts) > 1:
        name_extension = '_{number}-{number2}'.format(
            number=nd._mv_grid_districts[0].id_db,
            number2=nd._mv_grid_districts[-1].id_db)
    else:
        name_extension = '_{number}'.format(number=nd._mv_grid_districts[0].id_db)

    if filename is None:
        filename = "dingo_grids_{ext}.pkl".format(
            ext=name_extension)

    # delete attributes of `nd` in order to make pickling work
    # del nd._config
    del nd._orm

    pickle.dump(nd, open(os.path.join(abs_path, filename),"wb"))


def load_nd_from_pickle(filename=None, path=''):
    """
    Use pickle to save the whole nd-object to disc

    Parameters
    ----------
    filename : str
        Filename of nd pickle
    path : str
        Absolute or relative path where pickle should be saved. Default is ''
        which means pickle is save to PWD

    Returns
    -------
    nd : NetworkDingo
        Dingo grid container object
    """

    abs_path = os.path.abspath(path)

    if filename is None:
        raise NotImplementedError

    return pickle.load(open(os.path.join(abs_path, filename),"rb"))


def plot_cable_length(stats, plotpath):
    """
    Cable length per MV grid district
    """

    # cable and line kilometer distribution
    f, axarr = plt.subplots(2, sharex=True)
    stats.hist(column=['km_cable'], bins=5, alpha=0.5, ax=axarr[0])
    stats.hist(column=['km_line'], bins=5, alpha=0.5, ax=axarr[1])

    plt.savefig(os.path.join(plotpath,
                             'Histogram_cable_line_length.pdf'))

def plot_generation_over_load(stats, plotpath):
    """

    :param stats:
    :param plotpath:
    :return:
    """

    # Generation capacity vs. peak load
    sns.set_context("paper", font_scale=1.1)
    sns.set_style("ticks")

    # reformat to MW
    stats[['generation_capacity', 'peak_load']] = stats[['generation_capacity',
                                                         'peak_load']] / 1e3

    sns.lmplot('generation_capacity', 'peak_load',
               data=stats,
               fit_reg=False,
               hue='v_nom',
               # hue='Voltage level',
               scatter_kws={"marker": "D",
                            "s": 100},
               aspect=2)
    plt.title('Peak load vs. generation capcity')
    plt.xlabel('Generation capacity in MW')
    plt.ylabel('Peak load in MW')

    plt.savefig(os.path.join(plotpath,
                             'Scatter_generation_load.pdf'))


def plot_km_cable_vs_line(stats, plotpath):
    """

    :param stats:
    :param plotpath:
    :return:
    """

    # Cable vs. line kilometer scatter
    sns.lmplot('km_cable', 'km_line',
               data=stats,
               fit_reg=False,
               hue='v_nom',
               # hue='Voltage level',
               scatter_kws={"marker": "D",
                            "s": 100},
               aspect=2)
    plt.title('Kilometer of cable/line')
    plt.xlabel('Km of cables')
    plt.ylabel('Km of overhead lines')

    plt.savefig(os.path.join(plotpath,
                             'Scatter_cables_lines.pdf'))


def concat_nd_pickles(self, mv_grid_districts):
    """
    Read multiple pickles, join nd objects and save to file

    Parameters
    ----------
    mv_grid_districts : list
        Ints describing MV grid districts
    """

    pickle_name = cfg_dingo.get('output', 'nd_pickle')
    # self.nd = self.read_pickles_from_files(pickle_name)


    # TODO: instead of passing a list of mvgd's, pass list of filenames plus optionally a basth_path
    for mvgd in mv_grid_districts[1:]:

        filename = os.path.join(
            self.base_path,
            'results', pickle_name.format(mvgd))
        if os.path.isfile(filename):
            mvgd_pickle = pickle.load(open(filename, 'rb'))
            if mvgd_pickle._mv_grid_districts:
                mvgd_1.add_mv_grid_district(mvgd_pickle._mv_grid_districts[0])

    # save to concatenated pickle
    pickle.dump(mvgd_1,
                open(os.path.join(
                    self.base_path,
                    'results',
                    "dingo_grids_{0}-{1}.pkl".format(
                        mv_grid_districts[0],
                        mv_grid_districts[-1])),
                    "wb"))

    # save stats (edges and nodes data) to csv
    nodes, edges = mvgd_1.to_dataframe()
    nodes.to_csv(os.path.join(
        self.base_path,
        'results', 'mvgd_nodes_stats_{0}-{1}.csv'.format(
            mv_grid_districts[0], mv_grid_districts[-1])),
        index=False)
    edges.to_csv(os.path.join(
        self.base_path,
        'results', 'mvgd_edges_stats_{0}-{1}.csv'.format(
            mv_grid_districts[0], mv_grid_districts[-1])),
        index=False)

####################################################
def calculate_mvgd_stats(nw):
    """
    Statistics for an arbitrary network

    Parameters
    ----------
    nw: NetworkDingo
        The MV grid to be studied

    Returns
    -------
    mvgd_stats : pandas.DataFrame
        Dataframe containing several statistical numbers about the MVGD
    """

    ##############################
    # Collect info from nw into dataframes
    # define dictionaries for collection
    trafos_dict = {}
    generators_dict = {}
    branches_dict = {}
    ring_dict = {}
    LA_dict = {}
    other_nodes_dict = {}
    lv_branches_dict = {}
    # initiate indexes
    trafos_idx = 0
    gen_idx = 0
    branch_idx = 0
    ring_idx = 0
    LA_idx = 0
    lv_branches_idx = 0
    for district in nw.mv_grid_districts():
        root = district.mv_grid.station()
        max_mv_path = 0
        max_mvlv_path = 0

        # transformers in main station
        for trafo in district.mv_grid.station().transformers():
            trafos_idx+=1
            trafos_dict[trafos_idx] = {
                'grid_id':district.mv_grid.id_db,
                's_max_a':trafo.s_max_a}

        # Generators and other MV special nodes
        cd_count = 0
        LVs_count = 0
        cb_count =  0
        lv_trafo_count = 0
        for node in district.mv_grid._graph.nodes():
            mv_path_length = 0
            mvlv_path_length = 0
            if isinstance(node, GeneratorDingo):
                gen_idx+=1
                subtype = node.subtype
                if subtype==None:
                    subtype = 'other'
                generators_dict[gen_idx] = {
                    'grid_id':district.mv_grid.id_db,
                    'type':node.type,
                    'sub_type':node.type+'/'+subtype,
                    'gen_cap':node.capacity,
                    'v_level':node.v_level,
                    }
                mv_path_length = district.mv_grid.graph_path_length(
                                   node_source=root,
                                   node_target=node)
            elif isinstance(node, MVCableDistributorDingo):
                cd_count+=1
            elif isinstance(node, LVStationDingo):
                LVs_count+=1
                lv_trafo_count += len([trafo for trafo in node.transformers()])
                if not node.lv_load_area.is_aggregated:
                    mv_path_length = district.mv_grid.graph_path_length(
                        node_source=root,
                        node_target=node)
                    max_lv_path = 0
                    for lv_LA in district.lv_load_areas():
                        for lv_dist in lv_LA.lv_grid_districts():
                            if lv_dist.lv_grid._station == node:
                                for lv_node in lv_dist.lv_grid._graph.nodes():
                                    lv_path_length = lv_dist.lv_grid.graph_path_length(
                                        node_source=node,
                                        node_target=lv_node)
                                    max_lv_path = max(max_lv_path,lv_path_length)
                    mvlv_path_length = mv_path_length + max_lv_path
            elif isinstance(node, CircuitBreakerDingo):
                cb_count+=1

            max_mv_path = max(max_mv_path,mv_path_length/1000)
            max_mvlv_path = max(max_mvlv_path,mvlv_path_length/1000)

        other_nodes_dict[district.mv_grid.id_db] = {
                         'CD_count':cd_count,
                         'LV_count':LVs_count,
                         'CB_count':cb_count,
                         'MVLV_trafo_count':lv_trafo_count,
                         'max_mv_path':max_mv_path,
                         'max_mvlv_path':max_mvlv_path,
                         }

        # branches
        gen_isolated = []
        for branch in district.mv_grid.graph_edges():
            branch_idx+=1
            br_in_ring = not(branch['branch'].ring == None)
            branches_dict[branch_idx] = {
                'grid_id':district.mv_grid.id_db,
                'length': branch['branch'].length / 1e3,
                'type_name': branch['branch'].type['name'],
                'type_kind': branch['branch'].kind,
                'in_ring': br_in_ring,
            }
            #search for isolated generators (not connected to MV ring)
            if not br_in_ring:
                node1 = branch['adj_nodes'][0]
                node2 = branch['adj_nodes'][1]
                if isinstance(node1,GeneratorDingo):
                    if node1 not in gen_isolated:
                        gen_isolated.append(node1)
                if isinstance(node2,GeneratorDingo):
                    if node2 not in gen_isolated:
                        gen_isolated.append(node2)
        other_nodes_dict[district.mv_grid.id_db].update({'Iso_Gen_count':len(gen_isolated)})
        # rings
        for ring in district.mv_grid._rings:
            ring_idx+=1
            ring_gen = 0
            for node in ring._grid._graph.nodes():
                if isinstance(node,GeneratorDingo):
                    ring_gen+=node.capacity

            ring_dict[ring_idx] = {
                'grid_id': district.mv_grid.id_db,
                'ring_length': sum([br['branch'].length / 1e3 for br in ring.branches()]),
                'ring_capacity': ring_gen,
                }
            #print(str(ring_idx)+str([br for br in ring.branches()]))

        # Load Areas
        for LA in district.lv_load_areas():
            LA_idx += 1
            LA_dict[LA_idx] = {
                'grid_id':district.mv_grid.id_db,
                'is_agg': LA.is_aggregated,
                'is_sat': LA.is_satellite,
                #'peak_gen':LA.peak_generation,
            }
            LA_pop = 0
            residential_peak_load = 0
            retail_peak_load = 0
            industrial_peak_load = 0
            agricultural_peak_load = 0
            lv_gen_level_6 = 0
            lv_gen_level_7 = 0
            for lv_district in LA.lv_grid_districts():
                LA_pop =+ lv_district.population
                residential_peak_load += lv_district.peak_load_residential
                retail_peak_load += lv_district.peak_load_retail
                industrial_peak_load += lv_district.peak_load_industrial
                agricultural_peak_load += lv_district.peak_load_agricultural

                #generation capacity
                for g in lv_district.lv_grid.generators():
                    if g.v_level == 6:
                        lv_gen_level_6 += g.capacity
                    elif g.v_level == 7:
                        lv_gen_level_7 += g.capacity

                #branches lengths
                for br in lv_district.lv_grid.graph_edges():
                    lv_branches_idx+=1
                    lv_branches_dict[lv_branches_idx] = {
                        'grid_id':district.mv_grid.id_db,
                        'length': br['branch'].length / 1e3,
                        'type_name': br['branch'].type.to_frame().columns[0], #why is it different as for MV grids?
                        'type_kind': br['branch'].kind,
                    }

            LA_dict[LA_idx].update({
                'population': LA_pop,
                'residential_peak_load': residential_peak_load,
                'retail_peak_load': retail_peak_load,
                'industrial_peak_load': industrial_peak_load,
                'agricultural_peak_load': agricultural_peak_load,
                'lv_generation': lv_gen_level_6 + lv_gen_level_7,
                'lv_gens_lvl_6': lv_gen_level_6,
                'lv_gens_lvl_7': lv_gen_level_7,
            })

        # geographic
        #  ETRS (equidistant) to WGS84 (conformal) projection
        proj = partial(
            pyproj.transform,
            #pyproj.Proj(init='epsg:3035'),  # source coordinate system
            #pyproj.Proj(init='epsg:4326'))  # destination coordinate system
            pyproj.Proj(init='epsg:4326'),  # source coordinate system
            pyproj.Proj(init='epsg:3035'))  # destination coordinate system
        district_geo = transform(proj, district.geo_data)
        other_nodes_dict[district.mv_grid.id_db].update({'Dist_area': district_geo.area})

    mvgd_stats = pd.DataFrame.from_dict({}, orient='index')
    ###################################
    #built dataframes from dictionaries
    trafos_df = pd.DataFrame.from_dict(trafos_dict, orient='index')
    generators_df = pd.DataFrame.from_dict(generators_dict, orient='index')
    other_nodes_df = pd.DataFrame.from_dict(other_nodes_dict, orient='index')
    branches_df = pd.DataFrame.from_dict(branches_dict, orient='index')
    lv_branches_df = pd.DataFrame.from_dict(lv_branches_dict, orient='index')
    ring_df = pd.DataFrame.from_dict(ring_dict, orient='index')
    LA_df = pd.DataFrame.from_dict(LA_dict, orient='index')

    ###################################
    #Aggregated data HV/MV Trafos
    if not trafos_df.empty:
        mvgd_stats = pd.concat([mvgd_stats, trafos_df.groupby('grid_id').count()['s_max_a']], axis=1)
        mvgd_stats = pd.concat([mvgd_stats, trafos_df.groupby('grid_id').sum()[['s_max_a']]], axis=1)
        mvgd_stats.columns = ['N° of HV/MV Trafos','Trafos HV/MV Acc s_max_a']

    ###################################
    #Aggregated data Generators
    if not generators_df.empty:
        #MV generation per sub_type
        mv_generation = generators_df.groupby(['grid_id', 'sub_type'])['gen_cap'].sum().to_frame().unstack(level=-1)
        mv_generation.columns = ['Gen. Cap. of MV '+_[1] if isinstance(_, tuple) else _
                             for _ in mv_generation.columns]
        mvgd_stats = pd.concat([mvgd_stats, mv_generation], axis=1)

        #MV generation at V levels
        mv_generation = generators_df.groupby(
            ['grid_id', 'v_level'])['gen_cap'].sum().to_frame().unstack(level=-1)
        mv_generation.columns = ['Gen. Cap. of MV at v_level '+str(_[1])
                             if isinstance(_, tuple) else _
                             for _ in mv_generation.columns]
        mvgd_stats = pd.concat([mvgd_stats, mv_generation], axis=1)

    ###################################
    #Aggregated data of other nodes
    if not other_nodes_df.empty:
        #print(other_nodes_df['CD_count'].to_frame())
        mvgd_stats['N° of Cable Distr'] = other_nodes_df['CD_count'].to_frame().astype(int)
        mvgd_stats['N° of LV Stations'] = other_nodes_df['LV_count'].to_frame().astype(int)
        mvgd_stats['N° of Circuit Breakers'] = other_nodes_df['CB_count'].to_frame().astype(int)
        mvgd_stats['N° of isolated MV Generators'] = other_nodes_df['Iso_Gen_count'].to_frame().astype(int)
        mvgd_stats['District Area'] = other_nodes_df['Dist_area'].to_frame()
        mvgd_stats['N° of MV/LV Trafos'] = other_nodes_df['MVLV_trafo_count'].to_frame().astype(int)
        mvgd_stats['Length of MV max path'] = other_nodes_df['max_mv_path'].to_frame()
        mvgd_stats['Length of MVLV max path'] = other_nodes_df['max_mvlv_path'].to_frame()

    ###################################
    #Aggregated data of MV Branches
    if not branches_df.empty:
        #km of underground cable
        branches_data = branches_df[branches_df['type_kind']=='cable'].groupby(
            ['grid_id'])['length'].sum().to_frame()
        branches_data.columns = ['Length of MV underground cable']
        mvgd_stats = pd.concat([mvgd_stats, branches_data], axis=1)

        #km of overhead lines
        branches_data = branches_df[branches_df['type_kind']=='line'].groupby(
            ['grid_id'])['length'].sum().to_frame()
        branches_data.columns = ['Length of MV overhead lines']
        mvgd_stats = pd.concat([mvgd_stats, branches_data], axis=1)

        #km of different wire types
        branches_data = branches_df.groupby(
            ['grid_id', 'type_name'])['length'].sum().to_frame().unstack(level=-1)
        branches_data.columns = ['Length of MV type '+_[1] if isinstance(_, tuple) else _
                             for _ in branches_data.columns]
        mvgd_stats = pd.concat([mvgd_stats, branches_data], axis=1)

        #branches not in ring
        total_br = branches_df.groupby(['grid_id'])['length'].count().to_frame()
        ring_br = branches_df[branches_df['in_ring']].groupby(
            ['grid_id'])['length'].count().to_frame()
        branches_data = total_br - ring_br
        total_br.columns = ['N° of MV branches']
        mvgd_stats = pd.concat([mvgd_stats, total_br], axis=1)
        branches_data.columns = ['N° of MV branches not in a ring']
        mvgd_stats = pd.concat([mvgd_stats, branches_data], axis=1)

    ###################################
    #Aggregated data of LV Branches
    if not lv_branches_df.empty:
        #km of underground cable
        lv_branches_data = lv_branches_df[lv_branches_df['type_kind']=='cable'].groupby(
            ['grid_id'])['length'].sum().to_frame()
        lv_branches_data.columns = ['Length of LV underground cable']
        mvgd_stats = pd.concat([mvgd_stats, lv_branches_data], axis=1)

        #km of overhead lines
        lv_branches_data = lv_branches_df[lv_branches_df['type_kind']=='line'].groupby(
            ['grid_id'])['length'].sum().to_frame()
        lv_branches_data.columns = ['Length of LV overhead lines']
        mvgd_stats = pd.concat([mvgd_stats, lv_branches_data], axis=1)

        #km of different wire types
        lv_branches_data = lv_branches_df.groupby(
            ['grid_id', 'type_name'])['length'].sum().to_frame().unstack(level=-1)
        lv_branches_data.columns = ['Length of LV type '+_[1] if isinstance(_, tuple) else _
                             for _ in lv_branches_data.columns]
        mvgd_stats = pd.concat([mvgd_stats, lv_branches_data], axis=1)

        #n° of branches
        total_lv_br = lv_branches_df.groupby(['grid_id'])['length'].count().to_frame()
        total_lv_br.columns = ['N° of LV branches']
        mvgd_stats = pd.concat([mvgd_stats, total_lv_br], axis=1)


    ###################################
    #Aggregated data of Rings
    if not ring_df.empty:
        #N° of rings
        ring_data = ring_df.groupby(['grid_id'])['grid_id'].count().to_frame()
        ring_data.columns = ['N° of MV Rings']
        mvgd_stats = pd.concat([mvgd_stats, ring_data], axis=1)

        #min,max,mean km of all rings
        ring_data = ring_df.groupby(['grid_id'])['ring_length'].min().to_frame()
        ring_data.columns = ['Length of MV Ring min']
        mvgd_stats = pd.concat([mvgd_stats, ring_data], axis=1)
        ring_data = ring_df.groupby(['grid_id'])['ring_length'].max().to_frame()
        ring_data.columns = ['Length of MV Ring max']
        mvgd_stats = pd.concat([mvgd_stats, ring_data], axis=1)
        ring_data = ring_df.groupby(['grid_id'])['ring_length'].mean().to_frame()
        ring_data.columns = ['Length of MV Ring mean']
        mvgd_stats = pd.concat([mvgd_stats, ring_data], axis=1)

        #km of all rings
        ring_data = ring_df.groupby(['grid_id'])['ring_length'].sum().to_frame()
        ring_data.columns = ['Length of MV Rings total']
        mvgd_stats = pd.concat([mvgd_stats, ring_data], axis=1)

        #km of non-ring
        non_ring_data = branches_df.groupby(['grid_id'])['length'].sum().to_frame()
        non_ring_data.columns = ['Length of MV Rings total']
        ring_data  = non_ring_data - ring_data
        ring_data.columns = ['Length of MV Non-Rings total']
        mvgd_stats = pd.concat([mvgd_stats, ring_data.round(1).abs()], axis=1)

        #rings generation capacity
        ring_data = ring_df.groupby(['grid_id'])['ring_capacity'].sum().to_frame()
        ring_data.columns = ['Gen. Cap. Connected to MV Rings']
        mvgd_stats = pd.concat([mvgd_stats, ring_data], axis=1)
    ###################################
    #Aggregated data of Load Areas
    if not LA_df.empty:
        LA_data = LA_df.groupby(['grid_id'])['population'].count().to_frame()
        LA_data.columns = ['N° of Load Areas']

        mvgd_stats = pd.concat([mvgd_stats, LA_data], axis=1)

        LA_data = LA_df.groupby(['grid_id'])['population',
                                             'residential_peak_load',
                                             'retail_peak_load',
                                             'industrial_peak_load',
                                             'agricultural_peak_load',
                                             'lv_generation',
                                             'lv_gens_lvl_6',
                                             'lv_gens_lvl_7'
                                            ].sum()
        LA_data.columns = ['LA Total Population',
                           'LA Total LV Peak Load Residential',
                           'LA Total LV Peak Load Retail',
                           'LA Total LV Peak Load Industrial',
                           'LA Total LV Peak Load Agricultural',
                           'LA Total LV Gen. Cap.',
                           'Gen. Cap. of LV at v_level 6',
                           'Gen. Cap. of LV at v_level 7',
                           ]
        mvgd_stats = pd.concat([mvgd_stats, LA_data], axis=1)

    ###################################
    #Aggregated data of Aggregated Load Areas
    if not LA_df.empty:
        agg_LA_data = LA_df[LA_df['is_agg']].groupby(
            ['grid_id'])['population'].count().to_frame()
        agg_LA_data.columns = ['N° of Load Areas - Aggregated']
        mvgd_stats = pd.concat([mvgd_stats, agg_LA_data], axis=1)

        sat_LA_data = LA_df[LA_df['is_sat']].groupby(
            ['grid_id'])['population'].count().to_frame()
        sat_LA_data.columns = ['N° of Load Areas - Satellite']
        mvgd_stats = pd.concat([mvgd_stats, sat_LA_data], axis=1)

        agg_LA_data = LA_df[LA_df['is_agg']].groupby(['grid_id'])['population',
                                                              'lv_generation'
                                                             ].sum()
        agg_LA_data.columns = ['LA Aggregated Population',
                           'LA Aggregated LV Gen. Cap.']
        mvgd_stats = pd.concat([mvgd_stats, agg_LA_data], axis=1)

    ###################################
    mvgd_stats=mvgd_stats.fillna(0)
    mvgd_stats = mvgd_stats[sorted(mvgd_stats.columns.tolist())]
    return mvgd_stats
########################################################
def init_mv_grid(mv_grid_districts=[3545], filename='dingo_tests_grids_1.pkl'):
    '''Runs dingo over the districtis selected in mv_grid_districts 
    
    It also writes the result in filename. If filename = False, 
    then the network is not saved.

    Parameters
    ----------
    mv_grid_districts: :any:`list` of :obj:`int`
        Districts IDs: Defaults to [3545]
    filename: str
        Defaults to 'dingo_tests_grids_1.pkl'
        If filename=False, then the network is not saved
        
    Returns
    -------
    NetworkDingo
        The created MV network.

    '''
    print('\n########################################')
    print('  Running dingo for district', mv_grid_districts)
    # database connection
    conn = db.connection(section='oedb')

    # instantiate new dingo network object
    nd = NetworkDingo(name='network')

    # run DINGO on selected MV Grid District
    nd.run_dingo(conn=conn, mv_grid_districts_no=mv_grid_districts)

    # export grid to file (pickle)
    if filename:
        print('\n########################################')
        print('  Saving result in ', filename)
        save_nd_to_pickle(nd, filename=filename)

    conn.close()
    print('\n########################################')
    return nd
########################################################
def process_stats(mv_grid_districts,n_of_districts,output_stats):
    '''Runs dingo over mv_grid_districts and generates stats dataframe

    Parameters
    ----------
    mv_grid_districts: :any:`list` of :obj:`int`
        Districts IDs
    n_of_districts: int
        Number of districts to run simultaneously
    output_stats: 
        A multiprocess queue for saving the output data when parallelizing
    
    Notes
    -----
    The stats for the districts in a cluster are saved in a csv file of name::
    
        "stats_MV_distrs_<min dist>_to_<max dist>.csv"    
    '''

    # database connection
    conn = db.connection(section='oedb')

    i = 0
    j = min(n_of_districts,len(mv_grid_districts)-1)
    mvgd_stats = pd.DataFrame.from_dict({}, orient='index')
    while True:
        print('\n########################################')
        print('  Running dingo for district', mv_grid_districts[i:j])
        print('########################################')
        nw = NetworkDingo(name='network_'+str(mv_grid_districts[i])+'_to_'+str(mv_grid_districts[j-1]))
        nw.run_dingo(conn=conn, mv_grid_districts_no=mv_grid_districts[i:j])
        stats = calculate_mvgd_stats(nw)
        name = 'stats_MV_distrs_' + \
               str(mv_grid_districts[i]) + '_to_' + \
               str(mv_grid_districts[j-1]) + '.csv'
        stats.to_csv(name)
        mvgd_stats = pd.concat([mvgd_stats, stats], axis=0)
        i = min(i+n_of_districts, len(mv_grid_districts))
        j = min(j+n_of_districts, len(mv_grid_districts))
        if i>=len(mv_grid_districts):
            break

    conn.close()
    output_stats.put(mvgd_stats)
########################################################
def parallel_running_stats(max_dist,n_of_processes, n_of_districts):
    '''Organize parallel runs of dingo and collect the stats for the networks.
    
    The function take districts from 1 to max_dist and divide them into 
    n_of_processes groups. For each group, a parallel dingo process is run 
    through the function process_stats and the information is collected together

    Parameters
    ----------
    max_dist: int
        Number of districts to run.
    n_of_processes: int
        Number of processes to run in parallel
    n_of_districts: int
        Number of districts to be run in each cluster
    
    '''
    #######################################################################
    # Define an output queue
    output_stats = mp.Queue()
    #######################################################################
    # Setup a list of processes that we want to run
    cluster_long = floor(max_dist/n_of_processes)
    last = n_of_processes*cluster_long
    processes = []
    for p in range(0, n_of_processes):
        dist     = 1 + p*cluster_long
        if p<n_of_processes-1:
            dist_end = dist + cluster_long
        else:
            dist_end = max_dist + 1
        mv_districts = list(range(dist, dist_end))
        processes.append(mp.Process(target=process_stats,
                                    args=(mv_districts,n_of_districts,output_stats)))
    #######################################################################
    # Run processes
    for p in processes:
        p.start()
    # Exit the completed processes
    for p in processes:
        p.join()

    #######################################################################
    # Get process results from the output queue
    mvgd_stats_list = [output_stats.get() for p in processes]
    mvgd_stats      = pd.DataFrame.from_dict({}, orient='index')

    print('\n########################################')
    for p in range(0,len(processes)):
        mvgd_stats = pd.concat([mvgd_stats, mvgd_stats_list[p]], axis=0)
    mvgd_stats = mvgd_stats.fillna(0)
    mvgd_stats = mvgd_stats[sorted(mvgd_stats.columns.tolist())]
    mvgd_stats.sort_index(inplace=True)

    mv_grid_districts = mvgd_stats.index.tolist()
    print(mv_grid_districts)
    name = 'stats_MV_distrs_' + \
           str(min(mv_grid_districts)) + '_to_' + \
           str(max(mv_grid_districts)) + '.csv'
    mvgd_stats.to_csv(name)
    print(mvgd_stats.T)

########################################################
if __name__ == "__main__":
    #nw = init_mv_grid(mv_grid_districts=[3544, 3545])
    #init_mv_grid(mv_grid_districts=list(range(1, 4500, 200)),filename='dingo_tests_grids_1_4500_200.pkl')
    #nw = load_nd_from_pickle(filename='dingo_tests_grids_1.pkl')
    #nw = load_nd_from_pickle(filename='dingo_tests_grids_SevenDistricts.pkl')
    #nw = load_nd_from_pickle(filename='dingo_tests_grids_1_4500_200.pkl')
    #nw = init_mv_grid(mv_grid_districts=[2370],filename=False)
    #stats = calculate_mvgd_stats(nw)
    #print(stats)
    #print(stats.T)
    #stats.to_csv('stats_1_4500_200.csv')

    # generate stats in parallel
    max_districts = 10#3607 # districts from 1 to max_districts
    n_of_processes = mp.cpu_count() #number of parallel threaths
    n_of_districts = 4 #n° of districts in each cluster
    parallel_running_stats(max_districts,n_of_processes,n_of_districts)
    #nw = init_mv_grid(mv_grid_districts=[n_of_districts],filename=False)
    #stats = calculate_mvgd_stats(nw)
    #print(stats.T)

# TODO: old code, that may is used for re-implementation, @gplssm
# that old code was part of the ResultsDingo class that was removed later
#
# def concat_nd_pickles(self, mv_grid_districts):
#     """
#     Read multiple pickles, join nd objects and save to file
#
#     Parameters
#     ----------
#     mv_grid_districts : list
#         Ints describing MV grid districts
#     """
#
#     pickle_name = cfg_dingo.get('output', 'nd_pickle')
#     # self.nd = self.read_pickles_from_files(pickle_name)
#
#     mvgd_1 = pickle.load(
#         open(os.path.join(
#             self.base_path,
#             'results',
#             pickle_name.format(mv_grid_districts[0])),
#             'rb'))
#     # TODO: instead of passing a list of mvgd's, pass list of filenames plus optionally a basth_path
#     for mvgd in mv_grid_districts[1:]:
#
#         filename = os.path.join(
#             self.base_path,
#             'results', pickle_name.format(mvgd))
#         if os.path.isfile(filename):
#             mvgd_pickle = pickle.load(open(filename, 'rb'))
#             if mvgd_pickle._mv_grid_districts:
#                 mvgd_1.add_mv_grid_district(mvgd_pickle._mv_grid_districts[0])
#
#     # save to concatenated pickle
#     pickle.dump(mvgd_1,
#                 open(os.path.join(
#                     self.base_path,
#                     'results',
#                     "dingo_grids_{0}-{1}.pkl".format(
#                         mv_grid_districts[0],
#                         mv_grid_districts[-1])),
#                     "wb"))
#
#     # save stats (edges and nodes data) to csv
#     nodes, edges = mvgd_1.to_dataframe()
#     nodes.to_csv(os.path.join(
#         self.base_path,
#         'results', 'mvgd_nodes_stats_{0}-{1}.csv'.format(
#             mv_grid_districts[0], mv_grid_districts[-1])),
#         index=False)
#     edges.to_csv(os.path.join(
#         self.base_path,
#         'results', 'mvgd_edges_stats_{0}-{1}.csv'.format(
#             mv_grid_districts[0], mv_grid_districts[-1])),
#         index=False)
#
#
# def concat_csv_stats_files(self, ranges):
#     """
#     Concatenate multiple csv files containing statistics on nodes and edges.
#
#
#     Parameters
#     ----------
#     ranges : list
#         The list contains tuples of 2 elements describing start and end of
#         each range.
#     """
#
#     for f in ['nodes', 'edges']:
#         file_base_name = 'mvgd_' + f + '_stats_{0}-{1}.csv'
#
#         filenames = []
#         [filenames.append(file_base_name.format(mvgd_ids[0], mvgd_ids[1]))
#          for mvgd_ids in ranges]
#
#         results_file = 'mvgd_{0}_stats_{1}-{2}.csv'.format(
#             f, ranges[0][0], ranges[-1][-1])
#
#         self.concat_and_save_csv(filenames, results_file)
#
#
# def concat_and_save_csv(self, filenames, result_filename):
#     """
#     Concatenate and save multiple csv files in `base_path` specified by
#     filnames
#
#     The path specification of files in done via `self.base_path` in the
#     `__init__` method of this class.
#
#
#     Parameters
#     filenames : list
#         Files to be concatenates
#     result_filename : str
#         File name of resulting file
#
#     """
#
#     list_ = []
#
#     for filename in filenames:
#         df = pd.read_csv(os.path.join(self.base_path, 'results', filename),
#                          index_col=None, header=0)
#         list_.append(df)
#
#     frame = pd.concat(list_)
#     frame.to_csv(os.path.join(
#         self.base_path,
#         'results', result_filename), index=False)
#
#
# def read_csv_results(self, concat_csv_file_range):
#     """
#     Read csv files (nodes and edges) containing results figures
#     Parameters
#     ----------
#     concat_csv_file_range : list
#         Ints describe first and last mv grid id
#     """
#
#     self.nodes = pd.read_csv(
#         os.path.join(self.base_path,
#                      'results',
#                      'mvgd_nodes_stats_{0}-{1}.csv'.format(
#                          concat_csv_file_range[0], concat_csv_file_range[-1]
#                      ))
#     )
#
#     self.edges = pd.read_csv(
#         os.path.join(self.base_path,
#                      'results',
#                      'mvgd_edges_stats_{0}-{1}.csv'.format(
#                          concat_csv_file_range[0], concat_csv_file_range[-1]
#                      ))
#     )
