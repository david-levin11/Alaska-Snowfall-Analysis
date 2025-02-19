import os
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

############################### Downloading relevant data from G-Drive ######################################

# Home directory (change this!!!)
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

API_KEY = "AIzaSyCdQxgDQNL9ZXBIV5sMnqbDvqZtwZYtlrY"

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
    """Download a file from Google Drive using Python (no wget needed)."""
    file_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    destination = os.path.join(local_path, file_name)

    try:
        print(f"Downloading {file_name} to {destination}...")
        response = requests.get(file_url, stream=True)
        response.raise_for_status()  # Raise error if request fails
        
        with open(destination, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        print(f"Download complete: {file_name}")
    except Exception as e:
        print(f"Failed to download {file_name}: {e}")
        
def download_folder_recursive(folder_id, local_path):
    """Recursively download all files and subfolders from a Google Drive folder."""
    ensure_dir(local_path)
    items = list_files_in_gdrive_folder(folder_id)
    #print(items)
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

if __name__ == "__main__":
    # Ensure directories exist
    for path in [DATAPATH, GRAPHICSPATH, LOG_PATH, shpdir, proj_path, rasterdir]:
        ensure_dir(path)
    # downloading data from public g-drive
    fetch_data()
    # updating shapefiles
    update_shapefiles()