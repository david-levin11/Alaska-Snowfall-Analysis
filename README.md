# Snowfall Analysis Tool

## Prerequisites
- **ArcGIS Pro**: You must have ArcGIS Pro (with Spatial Analyst extension) installed on your local machine (ArcMap is not supported).
- **ArcGIS Online (AGOL) Account**: Licensing is automatic and linked to your AGOL account. You will be prompted to log in upon launching ArcGIS Pro for the first time.

## Installation Instructions

### Step 1: Clone the Repository
1. Clone the repo into a directory on your local machine using: "git clone https://github.com/david-levin11/Alaska-Snowfall-Analysis.git"

### Step 2: Clone Your ArcPro Conda Environment
1. Open ArcGIS Pro and navigate to **Settings**.
2. Click on **Python** (or **Package Manager** in the latest version of ArcGIS Pro) to view your current Conda environment.
3. Click on **Manage Environments** (or the gear icon next to **Active Environment**) to display a list of your environments.
4. If you haven’t already, click **Clone Default Environment** to create a copy of your main Conda environment. This cloned environment will be used for the tool. The cloning process may take a few minutes.
5. Copy the address of your cloned environment for later use.

### Step 3: Associate Python Scripts with the Correct Interpreter
1. Right-click on `setup.py` and select **Open with** → **Choose another app**.
2. Click **More apps**, scroll to the bottom, and select **Look for another app on this PC**.
3. Navigate to the location of your cloned Conda environment (usually in `C:/Users/<YourName>/AppData`, which may be hidden. Enable hidden items in File Explorer if necessary).
4. Inside the Conda environment folder, select the `python` application (not `pythonw`).
5. This should associate all Python scripts in the folder with the correct interpreter, and you should only need to do this once.
6. 'setup.py' should download your ArcPro .aprx file and associated .gdb and layers needed to run the tool as well as appropriate shapefiles.  It will also create the needed directories on your local machine.
7. #### Note that any time the Alaska public zones are updated, you'll need to re-run 'setup.py' to stay current!

## Running the Tool

### Quality Control (QC) and Analysis Workflow
1. **Run `GetSnowfallData.py`**:
   - Launch the script by double-clicking or right-clicking and selecting **Run With ArcGIS Pro**.
   - Enter the start and end dates (UTC) for snowfall data retrieval (pad times to capture all data sources).
   - Optionally, enter site IDs for known zero snowfall locations, separated by commas (e.g., `pajn,paoh,sdia2,kkea2,pags,pagy,pahn`).
   - Click **Get Snowfall Data In Between The Above Times**.
   - A pop-up will indicate the output file to QC. Click **OK** and then **Quit** on the GUI.

2. **QC the Data**:
   - Open the generated spreadsheet and review COOP and SNOTEL data.
   - Ensure COOP data timestamps are correct.
   - Check SNOTEL data for unrealistic values and modify or delete erroneous values.
   - Graphics of SNOTEL smoothing results are available in the `SnotelGraphics` directory.
   - Remove duplicate or outdated LSRs using the `datetime` field.
   - Save the spreadsheet once QC is complete.

3. **Run `RunSnowfallAnalysis.py`**:
   - Launch the script and follow the GUI prompts.
   - Select the **CWA** and appropriate zones for analysis.
   - Enter a **title** for the generated graphic.
   - Adjust **Observation Weight** (default is 1; higher values give more weight to individual observations, making the map less smooth).
   - Use the **population density threshold** (e.g., 500 or 1000) to filter displayed cities.
   - Choose whether to enable **Adjust for Topo**:
     - **Unchecked**: Uses simple inverse distance weighting (similar to SERP in GFE).
     - **Checked**: Uses **Empirical Bayesian Kriging Regression** with PRISM data to fit snowfall data to topography.
   - Click **Create Analysis With Above Selection**.
   - A pop-up will indicate when the analysis is complete.

4. **Review the Output Graphics**:
   - Two graphics will be generated:
     - One with **zone-based statistics** (10-90th percentile, median, mean snowfall per zone).
     - One designed for **public sharing**.

### Congratulations! 🎉
Your snowfall analysis is now complete. If you have suggestions for additional data sources, please contact David Levin.

For any issues, feel free to reach out!



