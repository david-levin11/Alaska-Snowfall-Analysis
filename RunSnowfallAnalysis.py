# -*- coding: utf-8 -*-
"""
Created on Tue Feb  8 13:36:47 2022

@author: David Levin
"""
import os
import sys
import time
import logging
import requests
import tkinter
import tkinter.messagebox
import arcpy
import arcpy.cim
from arcpy.sa import *
import snowfalloutputconfig as SC

def Printer(pstring):
    for char in pstring:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(.003)
    sys.stdout.write('\n')
    
def removepng(path, pngfile):
    try:
        os.remove(os.path.join(path, pngfile))
    except FileNotFoundError:
        pass

def cleanup_map(mapx, do_not_remove):
    for lyr in mapx.listLayers():
        if lyr.name not in do_not_remove:
            #print(f'Now removing {lyr} from map')
            mapx.removeLayer(lyr)
    for tbl in mapx.listTables():
        #print(f'Now removing {tbl} from map')
        mapx.removeTable(tbl)
        
def renamelayer(mapx, oldname, newname):
    for lyr in mapx.listLayers():
        if lyr.name == oldname:
            lyr.name = newname

# code for checking for the latest NWS zones			
def get_cwa_dict(query_url, cwas):
    delimiter = "zone"
    cwa_dict = {}
    for cwa in cwas:
        where_query = f"cwa='{cwa}'"
        # Define the query parameters
        params = {
            "where": where_query,
            "outFields": delimiter,
            "f": "json"
        }
        # Send the GET request
        response = requests.get(query_url, params=params)

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            # Extract 'ZONE' values
            zones = [feature["attributes"][delimiter] for feature in data.get("features", [])]
        # updating our dictionary
        cwa_dict.update({cwa:zones})
    return cwa_dict
# code for creating our master list of zones
def get_zone_list(query_url, area, area_delim="state"):
    delimiter = "zone"    
    where_query = f"{area_delim}='{area}'"
    
    # Define the query parameters
    params = {
        "where": where_query,
        "outFields": delimiter,
        "f": "json"
    }
    
    # Send the GET request
    response = requests.get(query_url, params=params)

    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
        # Extract 'ZONE' values, sort numerically, but return as strings
        zones = sorted(
            [feature["attributes"][delimiter] for feature in data.get("features", [])], 
            key=int  # Sort numerically while keeping original strings
        )
    
        return zones  # Return sorted list as strings

    return []  # Return empty list if request fails
        
# code for creating new feature class using a subset of zones from user
def zone_clip(inlayer, geodatabase, expression, outFeatures):
    #running the feature class to feature class tool
    arcpy.FeatureClassToFeatureClass_conversion(inlayer, geodatabase, outFeatures, expression)
    
# building sql queries from lists
def build_sql_expression(zonelist):
    # add a field delimiter
    try:
        delimitedField = arcpy.AddFieldDelimiters(arcpy.env.workspace, 'ZONE')
    except Exception:
        delimitedField = arcpy.AddFieldDelimiters(arcpy.env.workspace, 'zone')
    expression = ''
    # if we are only looking at one zone
    if len(zonelist) <= 1:
        expression += delimitedField +" = \'"+zonelist[0]+"\'"
    # if looking at multiple zones our query gets more complex
    else:
        for count, zone in enumerate(zonelist):
            if count < len(zonelist)-1:
                expression += delimitedField +" = \'"+zone+"\' OR "
            else:
                expression += delimitedField +" = \'"+zone+"\'"
    return expression

def label_points(lyr, labelfield):
    lblClass=lyr.listLabelClasses()
    for lbl in lblClass:
        if lbl.name == 'Class 1':
            lbl.visible=True
        else:
            lbl.visible=False
    

def getlistselection():
    global list1
    zones = []
    for i in list1.curselection():
        zones.append(list1.get(i))
    return zones

def getdropdownselection(var):
    varselect = var.get()
    print(varselect)
    return varselect

def getcheckboxselection():
    global checked
    customselect = checked.get()
    return customselect

def gettoposelection():
    global topocheck
    toposelect = topocheck.get()
    return toposelect

def checkzones(cwa, zonelist, checkboxoutput, cwadict):
    zonecheck = True
    for zone in zonelist:
        if zone in cwadict[cwa] or checkboxoutput == 0:
            continue
        else:
            zonecheck = False
            break
    return zonecheck

def getgraphictitle():
    global entry1
    snowtitle = entry1.get()
    return snowtitle

def getpopquery():
    global entry2
    dquery = entry2.get()
    return dquery

################################ Paths ############################################
# Home directory
home = SC.home

datapath = SC.datapath
# location of your geodatabase where all your shapefiles will be stored
shpdir = SC.shpdir
#location of your prism rasters
prismdir = SC.rasterdir
# project paths
proj_path = SC.proj_path
################################# Files ###########################################

# name of your project gdb
proj_gdb = SC.proj_gdb
# file geodatabase
gdb_path = SC.gdb_path
# layer files
lyr_path = SC.lyr_path
# name of your project file
proj_name = SC.proj_name

# zones feature classes and shapefiles
zones_fc = SC.zones_fc
zones_shp = SC.zones_shp
# symbology layer file
sym_lyr = SC.sym_lyr
# final observation file
point_data_file = SC.point_data_file

# graphical output file
graphic_title = SC.graphic_title

############################## Config Lists #######################################
# CWA and Zone lists for various extents and masks
#REST API query for NWS Public Zones
QUERY_URL = SC.query_url

CWAS = SC.CWAS

zones = get_zone_list(QUERY_URL, SC.state)

DO_NOT_REMOVE = SC.DO_NOT_REMOVE

CITY_LAYER = SC.CITY_LAYER

ROAD_LAYER = SC.ROAD_LAYER

CITY_SHP = SC.CITY_SHP

ROAD_SHP = SC.ROAD_SHP

SYM_CITY = SC.sym_city

SYM_ROAD = SC.sym_roads

############################ Config for Geoprocessing ############################
class LicenseError(Exception):
    """A custom error for not having correct licensing in ArcPro"""
    pass

# using the default root logger
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
# Configuring our log
logging.basicConfig(filename=os.path.join(SC.LOG_PATH, SC.GIS_LOG_FILE), filemode='w',
                    format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S',
                    level=logging.DEBUG)
# Grabbing our logger
logger = logging.getLogger('')
# checking to make sure we have spatial analyst extensions for IDW
try:
    if not arcpy.CheckOutExtension("Spatial"):
        raise LicenseError('Spatial Analyst extention is unavailable for this account. Please contact your local GIS focal or rep to get this fixed!')
    if not arcpy.CheckOutExtension("GeoStats"):
        raise LicenseError('Geostatistical Analyst extention is not available on this account.  You will likely encounter an error if you checked the topo adjustment. Please contact your local GIS focal or rep to get this fixed!')
except LicenseError as e:
    logger.error(e)
    sys.exit()
# we would like to overwrite output
arcpy.env.overwriteOutput = True
# spatial reference
sr = arcpy.SpatialReference('WGS 1984 Web Mercator (auxiliary sphere)')
# inverse distance weighting vars
#power = 3
cellSize = 0.003
radius = RadiusVariable(12, 1500000)
# smoothing style
neighborhood = NbrRectangle(10,10, "CELL")

xyname = SC.xyname
yfield = SC.yfield
xfield = SC.xfield
zfield = SC.zfield
# raster output
idwout = SC.idwout
focalout = SC.focalout
stat_table = SC.stat_table
points_visible = SC.points_visible
point_label = SC.point_label

################################## Layer Names #####################################
raster_name = SC.raster_name
outline_name = SC.outline_name
ebk_topo = SC.toporaster
ebk_precip = SC.prismraster
###################################################################################
def input():
    global window, CWAS, home, graphic_title, clicked, idwpower, logger
    # getting our user config and running error checks
    cwa = getdropdownselection(clicked)
    # creating our dictionary of zones within our cwa
    cwa_dict = get_cwa_dict(QUERY_URL, CWAS)
    logger.info('Entry function: CWA/Zone selection is: %s', cwa)
    custom = getcheckboxselection()
    inv_power = int(getdropdownselection(idwpower))
    if custom == 0:
        extent_choice = cwa
    else:
        extent_choice = 'Custom'
    custom_list = getlistselection()
    logger.info('Entry function: Extent choice is: %s', extent_choice)
    logger.info('Entry function: Custom list is: %s', custom_list)
    areacheck = checkzones(cwa, custom_list, custom, cwa_dict)
    if not areacheck:
        tkinter.messagebox.showwarning(title=None, message='Selected zone(s) are not in the selected CWA! \nPlease try again.')
        sys.exit()

    if extent_choice in CWAS:
        mask_area = extent_choice+'_CWA.shp'
        custom_area = False
        exp = ''
    elif extent_choice in zones:
        mask_area = 'Zone_'+extent_choice+'.shp'
        custom_area = False
        exp = ''
    else:
        exp = build_sql_expression(custom_list)
        mask_area = cwa+'_CWA.shp'
        custom_area = True
    #accessing our graphic title
    graphictitle = getgraphictitle()
    # accessing our population density query
    query = getpopquery()
    # accessing our topo check box
    topo_select = gettoposelection()
    try:
        execute(mask_area, cwa, exp, custom_area, extent_choice, inv_power, graphictitle, query, topo_select)
        tkinter.messagebox.showwarning(title=None, message=f'All done with snowfall analysis!  \n\nPlease check {os.path.join(home, graphic_title)} to view graphic.')
        window.destroy()
    except IndexError:
        tkinter.messagebox.showwarning(title=None, message=f'Custom analysis area is checked but no zones were selected!  \n\nPlease either uncheck the custom analysis area or select 1 or more zones from the list!')
        window.destroy()

def execute(mask_area, cwa, exp, custom_area, extent_choice, power, title, pquery, tquery):
    global home, datapath, proj_gdb, proj_path, proj_name, shpdir, sym_lyr, point_data_file, graphic_title
    global DO_NOT_REMOVE, sr, cellSize, radius, neighborhood, xyname, xfield, yfield, zfield
    global idwout, focalout, stat_table, points_visible, point_label, raster_name, outline_name, CITY_LAYER, ROAD_LAYER
    global CITY_SHP, ROAD_SHP, SYM_CITY, SYM_ROAD
    # using the default root logger
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    # Configuring our log
    logging.basicConfig(filename=os.path.join(SC.LOG_PATH, SC.GIS_LOG_FILE), filemode='w',
                        format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S',
                        level=logging.DEBUG)
    # Grabbing our logger
    logger = logging.getLogger('')
    logger.info('CWA is %s, our extent is %s, mask area is %s, and title is %s', cwa, extent_choice, mask_area, title)
    # opening our project and cleaning up
    geodatabase = os.path.join(gdb_path, proj_gdb)
    arcpy.env.workspace = geodatabase
    logger.info('Project workspace found!')
    p = arcpy.mp.ArcGISProject(os.path.join(proj_path, proj_name))
    m = p.listMaps('Map')[0]
    # remove all previous layers
    logger.info('Now removing old layers from the map frame')
    cleanup_map(m, DO_NOT_REMOVE)
    # removing any old graphics
    logger.info('Now removing old graphics')
    removepng(home, graphic_title)
    # now adding your mask layer if it's not a custom mask
    logger.info('Now adding %s to map', os.path.join(shpdir, mask_area))
    m.addDataFromPath(os.path.join(shpdir, mask_area))
    logger.info('Custom area is %s', custom_area)
    # if it is a custom mask, add from user input
    if custom_area:
        l = m.listLayers(cwa+'_CWA')[0]
        zone_clip(l, lyr_path, exp, extent_choice)
        boundary = f"{extent_choice}.shp"
        logger.info(f"My shapefile is: {os.path.join(lyr_path, boundary)}")
        m.addDataFromPath(os.path.join(lyr_path,boundary))
        for lyr in m.listLayers():
            if cwa+'_CWA' in lyr.name:
                m.removeLayer(lyr)
        # resetting mask area
        mask_area = extent_choice
    logger.info('Mask area is: %s', mask_area)
    # now setting the mask and extent of the geoprocessing
    if custom_area:
        arcpy.env.extent = os.path.join(lyr_path, boundary)
        arcpy.env.mask = os.path.join(lyr_path, boundary)
    else:
        arcpy.env.extent = os.path.join(shpdir, mask_area)
        arcpy.env.mask = os.path.join(shpdir, mask_area)
        
    # now we change the symbology of the mask outline
    logger.info('Current layers in map are: ')
    for layer in m.listLayers():
        logger.info(layer.name)
    logger.info('Now applying symbology to the outline layer')
    outlines = m.listLayers(mask_area.split('.')[0])[0]
    symbology = outlines.symbology
    # applying different symbology
    symbology.renderer.symbol.applySymbolFromGallery('Extent Yellow Hollow')
    outlines.symbology = symbology
    logger.info('Done applying symbology to %s', outlines)
    # now adding our table of data
    logger.info('Now adding %s to map', os.path.join(datapath, point_data_file))
    addTab = os.path.join(datapath, point_data_file)
    m.addDataFromPath(addTab)
    # now adding cities and roads
    clippath = geodatabase
    workingdir = geodatabase
    citylayer = os.path.join(workingdir, CITY_SHP)
    m.addDataFromPath(citylayer)
    #creating a cities layer which is clipped to analysis area
    #arcpy.analysis.Clip(citylayer, outlines, CITY_LAYER+'.shp')
    roadlayer = os.path.join(workingdir, ROAD_SHP)
    m.addDataFromPath(roadlayer)
    # adding symbology from layer file
    citysym = os.path.join(lyr_path, SYM_CITY)
    roadsym = os.path.join(lyr_path, SYM_ROAD)
    cities = m.listLayers(CITY_SHP)[0]
    # adding our definition query
    if pquery != '':
        for l in m.listLayers(CITY_SHP+"*"):
            l.definitionQuery = '"POP_2010" >= '+ pquery
    roads = m.listLayers(ROAD_SHP)[0]
    arcpy.ApplySymbologyFromLayer_management(cities, citysym)
    arcpy.ApplySymbologyFromLayer_management(roads, roadsym)
    # now clipping to extent of analysis layer
    # displaying the x/y data
    logger.info('Now adding point snowfall data to map')
    arcpy.management.XYTableToPoint(addTab, xyname, yfield, xfield, zfield)
    m.addDataFromPath(os.path.join(geodatabase,xyname))
    # clipping point data to mask
    logger.info('Done adding %s ', os.path.join(geodatabase, xyname))
    # Accessing the symbology properties of point snowfall
    snowlayer = m.listLayers(xyname)[0]
    logger.info('Point snowfall layer is %s', snowlayer)
    # now accessing the point symbol
    symbol = snowlayer.symbology
    # applying different symbology
    squarelist = symbol.renderer.symbol.listSymbolsFromGallery('Square')
    for square in squarelist:
        if square.name == 'Square 1':
            symbol.renderer.symbol = square
            symbol.renderer.symbol.size = 4
            snowlayer.symbology = symbol
    logger.info('Done applying symbology to point snowfall layer')
    logger.info('Now applying symbology changes to point layer')
    # now working on the labels
    # setting the halo properties
    # first create a color
    fillRGBColor = arcpy.cim.CreateCIMObjectFromClassName('CIMRGBColor', 'V2')
    fillRGBColor.values = [0,0,0,100]
    #create a fill
    solFill = arcpy.cim.CreateCIMObjectFromClassName('CIMSolidFill', 'V2')
    solFill.color = fillRGBColor
    solFill.enable = True
    solFill.colorlocked = False
    solFill.overprint = False

    #create a polygon symbol and set its symbol layers
    sym = arcpy.cim.CreateCIMObjectFromClassName('CIMPolygonSymbol', 'V2')
    sym.symbolLayers = [solFill]

    # setting the label properties
    cim_snow = snowlayer.getDefinition('V2')
    # setting the display field and font size
    cim_snow.labelClasses[0].expression = "\"<FNT size = '14'>\" + $feature.snowfall + \"</FNT>\""
    label = cim_snow.labelClasses[0].textSymbol.symbol
    label.haloSize = 1
    # now inserting our halo we created from before into the layer definition
    label.haloSymbol = sym

    # setting the font color
    label.symbol.symbolLayers[0].color.values = [255,255,255,100]
    # turning on labels
    cim_snow.labelVisibility=True
    # pushing the changes back to the layer object
    snowlayer.setDefinition(cim_snow)
    logger.info('Done pushing the changes to labelling and point snowfall back to the CIM')
    if tquery == 0:
        # now interpolating the points using the IDW tool
        logger.info('Now running IDW on %s with field of %s', xyname,zfield)
        outIDW = Idw(xyname, zfield, cellSize, power, radius)
        outIDW.save(os.path.join(geodatabase,idwout))
        logger.info('Now smoothing %s ', os.path.join(geodatabase,idwout))
        # Do a 5x5 smoothing 
        outFocal = FocalStatistics(os.path.join(geodatabase,idwout),neighborhood, "MEAN")  
        outFocal.save(os.path.join(geodatabase,focalout))
        m.addDataFromPath(os.path.join(geodatabase,focalout))
        logger.info('Done adding %s to map', os.path.join(geodatabase,focalout))
        focallyr = m.listLayers(focalout)[0]
        sympath = os.path.join(lyr_path, sym_lyr)
        # adding symbology from layer file
        arcpy.ApplySymbologyFromLayer_management(focallyr, sympath)
    else:
        # executing EBK regression if topo adjustment is selected
        exp1 = os.path.join(prismdir, ebk_topo)
        exp2 = os.path.join(prismdir, ebk_precip)
        explanatory_rasters = [exp1, exp2]
        searchRadius = arcpy.SearchNeighborhoodStandardCircular(SC.radius)
        logger.info('Now running EBK regression on %s with field of %s', xyname,zfield)
        outEBK = arcpy.EBKRegressionPrediction_ga(xyname, zfield, explanatory_rasters, SC.outLayer, SC.outRaster, SC.outDiagFeatures,
                        SC.inDepMeField, SC.minCumVariance, SC.outSubsetFeatures, SC.depTransform, SC.semiVariogram, SC.maxLocalPoints,
                        SC.overlapFactor, SC.simNumber, searchRadius)
        #outEBK.save(os.path.join(os.path.join(proj_path, proj_gdb),focalout))
        m.addDataFromPath(os.path.join(geodatabase,SC.outRaster))
        logger.info('Done adding %s to map', os.path.join(geodatabase,SC.outRaster))
        focallyr = m.listLayers(focalout)[0]
        sympath = os.path.join(lyr_path, sym_lyr)
        # adding symbology from layer file
        arcpy.ApplySymbologyFromLayer_management(focallyr, sympath)
    # turning off all layers except for the raster 
    # also checking to see if we need to label our points and turn that layer on
    for lyr in m.listLayers():
        if lyr.name == focalout or lyr.name == mask_area or lyr.name == CITY_SHP or lyr.name == ROAD_SHP:
            lyr.visible = True
        elif lyr.name == xyname and points_visible:
            lyr.visible = True
            #label_points(lyr, point_label)
        else:
            lyr.visible = False

    # running zonal statistics on analysis
    zonestats = ZonalStatisticsAsTable(outlines, 'ZONE', focallyr, stat_table,
                                    statistics_type='ALL', percentile_values=[10,25,50,75,90])

    # adding the table to our map
    m.addDataFromPath(zonestats)       
    # renaming layers so the legend prints better
    renamelayer(m, focalout, raster_name)
    logger.info('Changing %s to %s', mask_area, outline_name)
    renamelayer(m, mask_area.split('.')[0], outline_name)
    renamelayer(m, ROAD_SHP, ROAD_LAYER)
    logger.info('Changing %s to %s', ROAD_SHP, ROAD_LAYER)
    # accessing the layout and mapframes
    logger.info('Now listing layers on the current map and moving point data on top')
    for layer in m.listLayers():
        logger.info(layer.name)
        if layer.name == raster_name:
            refLayer = layer
        if layer.name == xyname:
            moveLayer = layer
        if layer.name == CITY_LAYER:
            citylayer = layer
        if layer.name == ROAD_LAYER:
            roadlayer = layer
    m.moveLayer(refLayer, moveLayer, 'BEFORE')
    m.moveLayer(refLayer, citylayer, 'BEFORE')
    m.moveLayer(refLayer, roadlayer, 'BEFORE')
    ext_lyr = m.listLayers(outline_name)[0]
    #lyt = p.listLayouts()[0]
    public_layout = p.listLayouts()[1]
    logger.info('List of avaialble layouts is %s', p.listLayouts())
    # code for removing duplicate legend items
    legends = [element for element in public_layout.listElements("LEGEND_ELEMENT")]
    legend = legends[0]
    # track items we have already encountered
    seen_items = set()
    # loop through the legend elements
    for item in legend.items:
        if item.name in seen_items or item.name == 'Analysis Area':
            # if the item is already in the set, mark it for removal
            legend.removeItem(item)
            logger.info(f"Found duplicate: {item.name}")
        else:
            seen_items.add(item.name)
            logger.info(f"Adding {item.name} to keep in legend")
    
    #mf = lyt.listElements('MAPFRAME_ELEMENT')[0]
    mf_public = public_layout.listElements('MAPFRAME_ELEMENT')[0]
    
    logger.info('Now setting the extent of map frame to the extent of the mask layer')
    # setting the extent of the mapframe to be the extent of the mask layer
    #mf.camera.setExtent(mf.getLayerExtent(ext_lyr))
    mf_public.camera.setExtent(mf_public.getLayerExtent(ext_lyr))
    # setting the title
    logger.info('Setting text and title')
    #txt = lyt.listElements('TEXT_ELEMENT')[0]
    txt_public = public_layout.listElements('TEXT_ELEMENT')[0]
    #txt.text = title
    txt_public.text = title
    logger.info('Exporting to png %s', os.path.join(home, graphic_title))
    #lyt.exportToPNG(os.path.join(home, graphic_title))
    public_layout.exportToPNG(os.path.join(home, 'PublicSnowfallGraphic.png'))
    p.saveACopy(os.path.join(proj_path, proj_name))
    #p.save(os.path.join(proj_path, proj_name))
    del p

# GUI Set Up 

window = tkinter.Tk()

window.title('Run Snowfall Analysis')

#window.geometry("%dx%d+%d+%d" % (650, 650, 600, 600))

window.eval('tk::PlaceWindow %s center' % window.winfo_toplevel())

window.config(bg="blue")

window.grid_rowconfigure(0, weight=1)
window.grid_columnconfigure(0, weight=1)

##################################### Left Column ##################################

# label for dropdown menu
label1 = tkinter.Label(window, text = "Select Your CWA", font=('Arial', 12, 'bold'))
label1.config(bg='blue', fg='white')
label1.grid(row=0, column=0, padx=10, pady=10)
#datatype of dropdown menu
clicked = tkinter.StringVar()
#initial set for dropdown
clicked.set(SC.DEFAULT_CWA)#
#creating dropdown menu
dropdown = tkinter.OptionMenu(window, clicked, *CWAS)
#dropdown.pack(side='top',padx=10, pady=10, expand='no', fill='y')
dropdown.grid(row=1, column=0, padx=10, pady=10)

# label for custom area selection
label3 = tkinter.Label(window, text='Enter A Title For Your Graphic Below (Shorter Is Better!)', font = ('Arial', 12, 'bold'), padx = 10, pady = 10 )
label3.config(bg='blue', fg='white')
#label3.pack(side='top',padx = 10, pady = 10)
label3.grid(row=2, column=0, padx = 10, pady = 10)
#creating our entry widget
entry1 = tkinter.Entry(window, width=80)
#entry1.pack(side='top', padx = 10, pady = 10)
entry1.grid(row=3, column=0,padx = 1, pady = 1)


# entry widget for city density
label5 = tkinter.Label(window, text='Enter Population Density Threshold To Thin Out Cities (i.e. "2000")', font = ('Arial', 12, 'bold'), padx = 10, pady = 10 )
label5.config(bg='blue', fg='white')
#label5.pack(side='top', padx=10, pady=10)
label5.grid(row=4, column=0,padx=10, pady=10)
entry2 = tkinter.Entry(window)
#entry2.pack(side='top', padx = 10, pady = 10)
entry2.grid(row=5, column=0)


#datatype of dropdown menu
# label for dropdown menu
label4 = tkinter.Label(window, text = "Observation Weight (Higher=More Weight For Each Ob, Lower=Smoother Plot)", font=('Arial', 12, 'bold'), padx = 10, pady = 10)
label4.config(bg='blue', fg='white')
#label4.pack()
label4.grid(row=6, column=0)
idwpower = tkinter.StringVar()
#initial set for dropdown
idwpower.set('1')
#creating dropdown menu
dropdown = tkinter.OptionMenu(window, idwpower, *['1','2','3'])
#dropdown.pack(side='top',padx=10, pady=10, expand='no', fill='y')
dropdown.grid(row=7, column=0,padx=10, pady=10)


######################## Right Column ####################################

# label for custom area selection
label2 = tkinter.Label(window, text='For A Custom Analysis Area Within Your CWA Check The Box Below\n Then Use The Menu To Select Custom Zone(s)\n\n For Your Entire CWA, Leave The Custom Box Unchecked', font = ('Arial', 12, 'bold'), padx = 10, pady = 10 )
label2.config(bg='blue', fg='white')
#label2.pack(side='top',padx = 10, pady = 10)
label2.grid(row=0, column=1, rowspan=2)
# initiating check box for custom area
checked = tkinter.IntVar()
checkbox = tkinter.Checkbutton(window, text='Custom Analysis Area', variable=checked)
#checkbox.pack(side='top',padx = 10, pady = 10)
checkbox.grid(row=2, column=1)
#setting up our list of zones
list1 = tkinter.Listbox(window, selectmode = 'multiple', yscrollcommand = lambda y1, y2: yscrollbar.set(y1, y2), font=('Arial', 10))
#list1.pack(side = 'top', padx = 10, pady = 10, expand = 'no', fill = 'y')
list1.grid(row=3, column=1, rowspan=3)
for item in range(len(zones)):
    list1.insert('end', zones[item])
    list1.itemconfig(item, bg = 'lime')
    #inserting scroll bar
yscrollbar = tkinter.Scrollbar(window, command=list1.yview)
#yscrollbar.pack(side= "right", fill = "y")
yscrollbar.grid(row=0, column=2, rowspan=10, sticky='ns')
yscrollbar.config(command=list1.yview)


# initiating check box for Topography adjustment
topocheck = tkinter.IntVar()
topocheckbox = tkinter.Checkbutton(window, text='Check To Adjust For Topo', variable=topocheck)
#topocheckbox.pack(side='top',padx = 10, pady = 10)
topocheckbox.grid(row=7, column=1,padx = 10, pady = 10)

############################# Bottom Column ############################
# creating a button to run analysis for selected zones
listbutton = tkinter.Button(window, text = 'Create Analysis With Above Selection', command = input)
listbutton.config(bg="forest green",fg="white", activebackground="gray", activeforeground="black")
#listbutton.pack(side='top',padx = 10, pady = 10)
listbutton.grid(row=8, column=0, columnspan=2, padx = 10, pady = 20)

quitbutton = tkinter.Button(window, text="Quit", command=window.destroy)
quitbutton.config(bg="forest green",fg="white", activebackground="gray", activeforeground="black", width=10)
#quitbutton.pack(side='top', padx=20, pady=10)
quitbutton.grid(row=9, column=0, columnspan=2, padx=10, pady=10)
window.mainloop()


'''
To do-- 
3. User input to add roads & cities?
4. Can we clip layers at the end to the analysis area?

'''