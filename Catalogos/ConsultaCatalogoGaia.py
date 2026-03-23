from units import *
import astropy.units as u
from astropy.coordinates import SkyCoord
from astroquery.gaia import Gaia

# Gaia.MAIN_GAIA_TABLE = "gaiadr2.gaia_source"  # Select Data Release 2
Gaia.MAIN_GAIA_TABLE = "gaiadr3.gaia_source"  # Reselect Data Release 3, default


import astropy.units as u
from astropy.coordinates import SkyCoord
from astroquery.gaia import Gaia

coord = SkyCoord(ra=0.0014503, dec=31.0570374, unit=(u.degree, u.degree), frame='icrs')
width = u.Quantity(0.03, u.deg)
height = u.Quantity(0.03, u.deg)
r = Gaia.query_object_async(coordinate=coord, width=width, height=height)
r.pprint(max_lines=12, max_width=13000)