# -*- coding: utf-8 -*-
"""
Created on Fri Jan  7 10:55:46 2022

@author: David Levin
"""

import os
import requests
import subprocess
###################### Data & Final Output & Paths #########################################

def ensure_dir(directory):
    """Ensure a directory exists. If not, create it."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Creating {directory} directory")
    else:
        print(f"{directory} already exists...skipping creation step.")
        
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

# Ensure directories exist
for path in [DATAPATH, GRAPHICSPATH, LOG_PATH, shpdir, proj_path, rasterdir]:
    ensure_dir(path)

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
############################### Downloading relevant data from G-Drive ######################################
# Public Google Drive Folder IDs (Replace with your actual folder IDs)
API_KEY = 'AIzaSyCdQxgDQNL9ZXBIV5sMnqbDvqZtwZYtlrY'

GDRIVE_FOLDERS = {
    "AnalyzeSnow": "1S-PpChJEROZI-1h_r_4MyEClS-qdvZyV",  
    "EBK_Rasters": "1UKDT9cgAP4ScND5kYMQ-S-7X241pahgi"
}

LOCAL_FOLDERS = {
    "AnalyzeSnow": os.path.join(home, "AnalyzeSnow"),
    "EBK_Rasters": os.path.join(home, "EBK_Rasters")
}

def list_files_in_gdrive_folder(folder_id):
    """List all files and subfolders in a Google Drive folder."""
    query = f"'{folder_id}' in parents and trashed=false"
    url = f"https://www.googleapis.com/drive/v3/files?q={query}&fields=files(id,name,mimeType)&key={API_KEY}"
    
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get("files", [])
    else:
        print(f"Error fetching file list: {response.text}")
        return []

def download_file(file_id, file_name, local_path):
    """Download a file from Google Drive with public access"""
    file_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    destination = os.path.join(local_path, file_name)

    try:
        print(f"Downloading {file_name}...")
        subprocess.run(["wget", file_url, "-O", destination], check=True)
    except Exception as e:
        print(f"Failed to download {file_name}: {e}")

def download_folder_recursive(folder_id, local_path):
    """Recursively download all files and subfolders from a Google Drive folder."""
    ensure_dir(local_path)
    items = list_files_in_gdrive_folder(folder_id)
    print(items)
    for item in items:
        item_name = item["name"]
        item_id = item["id"]
        mime_type = item["mimeType"]
        item_path = os.path.join(local_path, item_name)

        if mime_type == "application/vnd.google-apps.folder":
            # If it's a subfolder, create it and recursively download contents
            print(f"Creating local subfolder: {item_path}")
            ensure_dir(item_path)
            download_folder_recursive(item_id, item_path)
        else:
            # If it's a file, download it
            if not os.path.exists(item_path):
                print(f"Downloading {item_name} to {item_path}...")
                download_file(item_id, item_name, local_path)
            else:
                print(f"{item_name} already exists, skipping download.")

def fetch_data():
    """Download all required data from Google Drive."""
    print("Starting downloads...")

    for folder_name, folder_id in GDRIVE_FOLDERS.items():
        local_path = LOCAL_FOLDERS[folder_name]
        print(f"Downloading '{folder_name}' to {local_path}...")

        if folder_name == "AnalyzeSnow":
            download_folder_recursive(folder_id, local_path)
        else:  # EBK_Rasters has only files, no subfolders
            download_folder_recursive(folder_id, local_path)

    print("Download complete!")

    # Call fetch_data() when running the script directly
if __name__ == "__main__":
    fetch_data()