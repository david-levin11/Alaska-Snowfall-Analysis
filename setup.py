import os
import zipfile
import json
import arcpy
import requests
import snowfalloutputconfig as SC
###################### Data & Final Output & Paths #########################################

def ensure_dir(directory):
    """Ensure a directory exists. If not, create it."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Creating {directory} directory")
    else:
        print(f"{directory} already exists...skipping creation step.")

def clear_directory(directory):
    """Remove all files from a directory."""
    for file in os.listdir(directory):
        os.remove(os.path.join(directory, file))
        print(f"Found and removed {file} from {directory}")

def fetch_zones():
    """Fetch zone data from the web service."""
    query_url = f"{SC.base_url}/{SC.layer_id}/query"
    params = {"where": f"state='{SC.state}'", "outFields": "zone", "f": "json"}
    response = requests.get(query_url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        return [feature["attributes"]["zone"] for feature in data.get("features", [])]
    else:
        print(f"Error: Unable to fetch data (HTTP {response.status_code})")
        return []
    
def download_zone_shapefile(zone, shapedir):
    """Download and convert a zone's geometry to a shapefile."""
    query_url = f"{SC.base_url}/{SC.layer_id}/query"
    where_clause = f"zone='{zone}' AND state='AK'"
    json_file = f"Zone_{zone}.json"
    shapefile = os.path.join(shapedir, f"Zone_{zone}.shp")
    
    params = {
        "where": where_clause,
        "returnGeometry": "true",
        "geometryType": "esriGeometryPolygon",
        "f": "json"
    }
    response = requests.get(query_url, params=params)
    
    if response.status_code == 200:
        with open(json_file, "w") as ms_json:
            json.dump(response.json(), ms_json, indent=4)
        arcpy.JSONToFeatures_conversion(json_file, shapefile)
        print(f"Saved {shapefile} to {shapedir}")
        os.remove(json_file)
    else:
        print(f"Failed to fetch geometry for zone: {zone}")

def download_cwa_shapefiles(shapedir):
    """Download and convert CWA shapefiles."""
    query_url = f"{SC.base_url}/{SC.layer_id}/query"
    for cwa in SC.CWAS:
        print(f"Processing CWA: {cwa}")
        params = {"where": f"cwa='{cwa}'", "outFields": "zone", "f": "json"}
        response = requests.get(query_url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            zones = [feature["attributes"]["zone"] for feature in data.get("features", [])]
            zone_query = zone_query = f"ZONE IN ({', '.join([repr(z) for z in zones])}) AND STATE='{SC.state}'"
            json_file = f"{cwa}_CWA.json"
            shapefile = os.path.join(shapedir, f"{cwa}_CWA.shp")
            
            params = {"where": zone_query, "outFields": "*", "returnGeometry": "true", "f": "json"}
            response = requests.get(query_url, params=params)
            
            if response.status_code == 200:
                with open(json_file, "w") as ms_json:
                    json.dump(response.json(), ms_json, indent=4)
                arcpy.JSONToFeatures_conversion(json_file, shapefile)
                print(f"Saved {shapefile} to {shapedir}")
                os.remove(json_file)
            else:
                print(f"Failed to fetch geometry for CWA: {cwa}")
        else:
            print(f"Failed response {response.status_code}")

def update_shapefiles():
    """Main function to update zone and CWA shapefiles."""
    shapedir = "./shapefiles"
    ensure_dir(shapedir)
    clear_directory(shapedir)
    zones = fetch_zones()
    
    if zones:
        print("Found these areas in Alaska which will be downloaded:", zones)
        for zone in zones:
            download_zone_shapefile(zone, shapedir)
    
    download_cwa_shapefiles(shapedir)

    # Function to download and extract the zip files
def download_and_extract_zip(url, working_dir):
    # Download the zip file
    zip_name = url.split('/')[-1]
    print(f"Now grabbing {zip_name} from {url}")
    zip_path = os.path.join(working_dir, zip_name)
    print(f"Zip path is: {zip_path}")
    response = requests.get(url)
    with open(zip_path, 'wb') as zip_file:
        zip_file.write(response.content)
    
    # Extract the contents
    print(f"Extracting contents of {zip_path} to {working_dir}")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(working_dir)
    
    # Delete the zip file after extraction
    os.remove(zip_path)

############################### Downloading relevant data from G-Drive ######################################

# Home directory 
home = SC.home
# where you want your obs data to go
DATAPATH = SC.DATAPATH
# where your obs data goes
datapath = DATAPATH
# where you want your snotel graphics stored (for QC purposes)
GRAPHICSPATH = SC.GRAPHICSPATH
# where you want your log file
LOG_PATH = SC.LOG_PATH
# location of your geodatabase where all your shapefiles will be stored
shpdir = SC.shpdir
# project paths
proj_path = SC.proj_path
# the location of the raster data for Empirical Bayesian Kreiging Analysis (EBK Regression)
# can add this and any config from version 2.0 above to the appropriate section of the config and then delete
# the update (2.0 and 3.0) sections of the config
rasterdir = SC.rasterdir

zip_urls = [SC.ebk_url, SC.proj_url]

def unpack_project_file(infolder, outfolder):
    arcpy.management.ExtractPackage(infolder, outfolder)
    
geopackage = os.path.join(SC.lyr_path, SC.proj_pkg)

if __name__ == "__main__":
    # Ensure directories exist
    for path in [DATAPATH, GRAPHICSPATH, LOG_PATH, shpdir]:
        ensure_dir(path)
    # # downloading data from github
    # Download and extract each zip file
    for url in zip_urls:
        download_and_extract_zip(url, home)
    # unpacking the ArcPro Project
    unpack_project_file(geopackage, home)
    # updating shapefiles
    update_shapefiles()