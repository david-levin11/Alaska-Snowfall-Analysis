# -*- coding: utf-8 -*-
"""
Created on Fri Jan  7 10:55:46 2022

@author: David Levin
"""
import os
###################### Data & Final Output & Paths #########################################
        
# Home directory (change this!!!)
home = os.path.abspath(os.path.dirname(__file__))
# where you want your obs data to go
DATAPATH = os.path.join(home, 'Data')
# where your obs data goes
datapath = DATAPATH
# where you want your snotel graphics stored (for QC purposes)
GRAPHICSPATH = os.path.join(home, 'SnotelGraphics')
# where you want your log file
LOG_PATH = os.path.join(home, 'Logs')
# location of your geodatabase where all your shapefiles will be stored
shpdir = os.path.join(home, 'shapefiles')
# project paths
proj_path = os.path.join(home, 'AnalyzeSnow')
# the location of the raster data for Empirical Bayesian Kreiging Analysis (EBK Regression)
# can add this and any config from version 2.0 above to the appropriate section of the config and then delete
# the update (2.0 and 3.0) sections of the config
rasterdir = os.path.join(home, 'EBK_Rasters')
# your final output file name
OUTFILE = "SnowfallObsTEST.csv"
# columns to keep within your final output...best not to change
KEEP_COLS = [
    "stationname",
    "Lat",
    "Lon",
    "datetime",
    "snowfall",
    "SWE",
    "Precip",
    "ObType",
]
# log file name
LOG_FILE = "get_snow_data_log.log"

################## Paths/Files For GIS Analysis ##########################################

# REST API endpoint for NWS Zones
base_url = "https://mapservices.weather.noaa.gov/static/rest/services/nws_reference_maps/nws_reference_map/MapServer"
# Layer ID for REST API
layer_id = 8
# state we're searching for zones in
state = "AK"
# Construct the query URL
query_url = f"{base_url}/{layer_id}/query"
# explanatory rasters for EBK regression (should be included in the folder above)
toporaster = "AK_PRISM_DEM.tif"
prismraster = "AK_PRISM_Annual_Precip.tif"
# name of your project gdb
proj_gdb = "AnalyzeSnow.gdb"
# name of your project file
proj_name = "AnalyzeSnow.aprx"
# zones feature classes and shapefiles
zones_fc = "Alaska_Zones_Project"
zones_shp = "Alaska_Zones_Project.shp"
# symbology layer file
sym_lyr = "SnowColorRamp.lyrx"
# final observation file
point_data_file = "SnowfallObsTEST.csv"
# graphical output file
graphic_title = "SnowfallGraphic.png"
# external share graphic title
ext_graphic_title = "SnowfallGraphicExternal.png"
# GIS analysis log
GIS_LOG_FILE = "analyze_snow.log"

############################ LSR Config #######################################
# file with latest LSRs from Iowa State
LSR_FILE = "LSR.csv"
# Iowa State LSR api
LSRURL = "http://mesonet.agron.iastate.edu/geojson/lsr.php?"
# Column names for your output spreadsheet
LSR_DICT = {
    "stationname": [],
    "Lat": [],
    "Lon": [],
    "datetime": [],
    "Type": [],
    "snowfall": [],
    "ObType": [],
}

#############################  COOP/CoCoRahs Config  ###################################
## Uses the same start and end time as the LSR config
## Uses the same WFO argument as the LSR config
## Uses the same MW token as the snotel config
## Config for COOP
COOP_FILE = "coop_snowfall.csv"

# Variable names for coop precip and snow from synoptic labs
SNOWVAR = "snow_accum_24_hour_set_1"

PCPVAR = "precip_accum_24_hour_set_1"

# network to pull from Mesowest
COOPNETWORK = "72,73,74,75,76,77,78,79,80"

########################### Snotel Auto Download Config #######################

## Config for downloading snotel from MesoWest
### File names and paths
# what is your output csv called?
SNOTELCSVFILE = "Snotels.csv"
### Mesowest URL config
# url for the mesowest API time series
SNOTEL_URL = "https://api.synopticdata.com/v2/stations/timeseries?"
# API token
TOKEN = "c6c8a66a96094960aabf1fed7d07ccf0"
# variable to look for
VARS = "snow_depth_set_1"
# variables we want from our snotels
SNOTEL_VARS = [
    "snow_depth_set_1",
    "snow_water_equiv_set_1",
    "precip_accum_set_1",
    "air_temp_set_1",
]
# network to pull from Mesowest (25 is for snotels)
NETWORK = "25"
### Miscellaneous config
# number of days back to look for your time series in order to smooth it
DAYSBACK = 15
# Set up the columns for your snotel dataframe
SNOTEL_DICT = {
    "STID": [],
    "Lat": [],
    "Lon": [],
    "Filtered_Depth": [],
    "Smoothed_Depth": [],
    "SWE": [],
    "Precip": [],
    "ObType": [],
}

#############################  Snotel Google Sheet (Manual entry) Config ######
## config for using the snotel google sheet (manual input)

SHEET_URL = "https://docs.google.com/spreadsheets/d/14-hoh_PFkArLml9w86e_GnVz-jZUorSNn98GAavVe0s/edit#gid=0"

########################### Lists for GIS Config ################################

CWAS = ["AFC", "AJK", "AFG"]

DO_NOT_REMOVE = ["World Topographic"]

########################## ArcPro Configurations ###############################

xyname = "PointSnowfall"
yfield = "Lon"
xfield = "Lat"
zfield = "snowfall"
# raster output
idwout = "RawAnalysis"
focalout = "SnowfallAnalysis"
stat_table = "ZoneStats"

################################## Layer Names #####################################
raster_name = "Total Snowfall (inches)"
outline_name = "Analysis Area"

points_visible = True

point_label = "snowfall"

######################### Config Update 2.0 ######################################

CITY_LAYER = "Cities"

ROAD_LAYER = "Alaska Major Roads"

CITY_SHP = "Cities"

ROAD_SHP = "AlaskaMajorRoads"
# symbology layers for roads and cities
sym_city = "Cities.lyrx"

sym_roads = "AlaskaMajorRoads.lyrx"

# default CWA for dropdown list
DEFAULT_CWA = "AFC"

# Population definition query for city density
POP_QUERY = 2000

########################## Config Update 3.0 EBK Regression Topo Analysis ######################################
# EBK Regression settings for topo adjustment
# keeping the layer names the same for continuity
# for more on EBK regression and the various settings read
# https://pro.arcgis.com/en/pro-app/latest/tool-reference/geostatistical-analyst/ebk-regression-prediction.htm
outLayer = idwout
outRaster = focalout
outDiagFeatures = ""
inDepMeField = ""
minCumVariance = 95
outSubsetFeatures = ""
depTransform = "Empirical"
semiVariogram = "K_BESSEL"
maxLocalPoints = 100
overlapFactor = 1.5
simNumber = 100
radius = 5
