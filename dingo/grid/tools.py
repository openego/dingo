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


def cable_type(nom_power, nom_voltage, avail_cables):
    """
    Determine suitable type of cable for given nominal power

    Based on maximum occurring current which is derived from nominal power
    (either peak load or max. generation capacity) a suitable cable type is
    chosen. Thus, no line overloading issues should occur.

    Parameters
    ----------
    nom_power : numeric
        Nominal power of generators or loads connected via a cable
    nom_voltage : numeric
        Nominal voltage in kV
    avail_cables : pandas.DataFrame
        Available cable types including it's electrical parameters
    Returns
    -------
    cable_type : pandas.DataFrame
        Parameters of cable type
    """

    I_max_load = nom_power / (3 ** 0.5 * nom_voltage)

    # determine suitable cable for this current
    suitable_cables = avail_cables[avail_cables['I_max_th'] > I_max_load]
    cable_type = suitable_cables.ix[suitable_cables['I_max_th'].idxmin()]

    return cable_type