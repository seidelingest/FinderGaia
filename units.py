from matplotlib import *
from scipy import *
import sys
from astropy.io import fits
from pymongo import MongoClient
import numpy as np
import pandas as pd
import io
import timeit
from matplotlib import pyplot as plt
import base64
from astroquery.gaia import Gaia
import os
import gzip
import shutil
import math
import seaborn as sns
from scipy.stats import norm

serieNanometros = pd.Series(range(336, 1021, 2))

sys.path.append('../AccesoBD/')
sys.path.append('../Catalogos/')

from AccesoBD import *
from functions import *

