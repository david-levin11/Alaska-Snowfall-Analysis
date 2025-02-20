# -*- coding: utf-8 -*-
"""
Created on Tue Dec 21 10:16:04 2021

@author: David Levin
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import urllib
import requests
import tkinter
import tkinter.messagebox
import logging
import json
import matplotlib.pyplot as plt
from io import StringIO
from matplotlib.dates import DateFormatter, DayLocator
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import snowfalloutputconfig as SC

def removegraphics(gpath):
    for f in os.listdir(gpath):
        os.remove(os.path.join(gpath, f))

def downloadLSR(base_url, start, end, wfo):
    base_url+='sts='+start+'&ets='+end+'&wfos='+wfo+'&callback=gotData'
    page = urllib.request.urlopen(base_url)
    data = page.read()
    return data

def parse_json(data):
    # Converting from json to python dictionary
    json_dict = json.loads(data)
    return json_dict

def formatLSRcsv(json_dict, outputdict):
    # looping through the json features
    for feature in json_dict['features']:
        outputdict['stationname'].append(feature['properties']['city'])
        outputdict['Lat'].append(feature['properties']['lat'])
        outputdict['Lon'].append(feature['properties']['lon'])
        outputdict['datetime'].append(datetime.strptime(feature['properties']['valid'],'%Y-%m-%dT%H:%M:%SZ'))
        outputdict['Type'].append(feature['properties']['typetext'])
        outputdict['snowfall'].append(feature['properties']['magnitude'])
        outputdict['ObType'].append('LSR')
    return outputdict


def downloadSNOTELCWA(url, cwa, start, end, networkkey, token):
    '''
    Parameters
    ----------
    url : Mesowest API Time Series URL
    cwa : 3 Letter CWA indentifier
    start : Start time of the time range you want snotel data for (YYYYmmddHHMM)
    end : End time of the time range you want snotel data for (YYYYmmddHHMM)
    networkkey : Network ID from Mesowest API documentation (25 is Snotels)
    token : Your unique MesoWest API token
    Returns
    -------
    data : Json dictionary of Snotel output

    '''
     # Initializing our url
    url += 'cwa='+cwa
    url += '&start='+start+'&end='+end+'&network='+networkkey+'&units=english&token='+token
    page = urllib.request.urlopen(url)
    data = page.read()
    return data

def parse_json(data):
    # Converting from json to python dictionary
    json_dict = json.loads(data)
    return json_dict

def grabvars(jsondict, variable):
    for site in jsondict['STATION']:
        wxvar = site['OBSERVATIONS'][variable]
        datetimes = site['OBSERVATIONS']['date_time']
        dt_converted = [datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ') for x in datetimes]
    return dt_converted, wxvar

def calcsnoteldaytimerange(start, end, daysback):
    tr_start = (datetime.strptime(end, '%Y%m%d%H%M')-timedelta(days=daysback)).strftime('%Y%m%d%H%M')
    tr_end = end
    return tr_start, tr_end

    
def plottimeseriessmoothed(path, dates, site, raw, adjusted, smoothed):
    plt.rc('font', size=12)
    # # creating our plot using FigureCanvas to avoid consuming too much memory
    fig = Figure(figsize=(10,6))
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(1,1,1)
    ax.plot(dates, raw, color='blue', label='Raw')
    ax.plot(dates, adjusted, color = 'red', label='Adjusted')
    ax.plot(dates, smoothed, color='green', label='Smoothed')
    ax.set_xlabel('Time')
    ax.set_ylabel('Snow Depth (in)')
    ax.set_title(site.upper()+' Snow Depth')
    ax.grid(True)
    ax.legend(loc='upper left')
    ax.xaxis.set_major_locator(DayLocator(interval=3))
    ax.xaxis.set_major_formatter(DateFormatter('%m/%d'))
    flname = site+'_SnotelData.png'
    fig.tight_layout()
    fig.savefig(os.path.join(path, flname), bbox_inches='tight')
    plt.close(fig)
    #plt.show()
    
def second_filter(df, col, newcol, thresh):
    #filtering out values that are above the threshold
    df[newcol] = np.where(df[col] >= thresh, np.nan, df[col])
    return df


def ratefilter(df, col, newcol, thresh, absolute=False):
    # calculating the hourly snowfall rates
    df['Rate'] = df[col].diff()
    # getting rid of obs where the snowfall rates are unrealistic
    if absolute:
        df[newcol]=np.where(df['Rate'].abs() >= thresh, np.nan, df[col])
    else:
        df[newcol]=np.where((df['Rate'] >= thresh) | (df['Rate'].shift(-1) <= -thresh), np.nan, df[col])
    return df


def pctchangefilter(df, col, newcol, thresh, window, absolute=False):
    # calculating the percent change over whatever rolling window you wish
    df['Pct_Change'] = df[col].pct_change(periods=window)
    # getting rid of areas where the percent change over the rolling window is too large
    if absolute:
        df[newcol] = np.where(df['Pct_Change'].abs() >= thresh, np.nan, df[col])
    else:
        df[newcol] = np.where(df['Pct_Change'].abs() >= thresh, np.nan, df[col])
    return df

def calcsnotelstats(wxlist):
    #converting to numpy array
    oblist = np.array(wxlist)
    maxval = round(oblist.max(),1)
    minval = round(oblist.min(),1)
    meanval = round(oblist.mean(),1)
    depthdiff = maxval-minval
    return depthdiff, maxval, minval, meanval

def formatSNOTELcsv(graphicspath, jsondict, outputdict, variables, start, end, plot=True):
    # converting start and end to datetime objects
    trstart = datetime.strptime(start, '%Y%m%d%H%M')
    trend = datetime.strptime(end, '%Y%m%d%H%M')
    # looping through the sites and grabbing our data
    # removing old graphics first
    if plot:
        removegraphics(graphicspath)
    for site in jsondict['STATION']:
        # appending metadata
        outputdict['STID'].append(site['STID'])
        outputdict['Lat'].append(site['LATITUDE'])
        outputdict['Lon'].append(site['LONGITUDE'])
        outputdict['ObType'].append('SNOTEL')
        datetimes = site['OBSERVATIONS']['date_time']
        dt_converted = [datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ') for x in datetimes]
        dates = pd.DataFrame(dt_converted, columns = ['DateTime'])
        #getting the snow depth and smoothing
        try:
            depth = site['OBSERVATIONS']['snow_depth_set_1']
            depthdf = pd.DataFrame(depth, columns = ['Raw'])
            # calculating stats from the raw data
            median = depthdf['Raw'].median()
            std = depthdf['Raw'].std()
            maximum = depthdf['Raw'].max()
            minimum = depthdf['Raw'].min()
            spread = maximum - minimum
            # thesholds for filtering vary depending on how much spread there is
            if spread >= 50:
                threshold = median+std
            else:
                threshold = median+std*4
            # filtering out high outliers from the raw data
            df_filtered = second_filter(depthdf, 'Raw', 'Adj_Depth', threshold)
            # filtering out rates > 5 inch per hour
            df_filtered = ratefilter(df_filtered, 'Adj_Depth', 'Adj_Depth', 5)             
            # recalculating the stats from the filtered data
            newmaximum = df_filtered['Adj_Depth'].max()
            newminimum = df_filtered['Adj_Depth'].min()
            newmedian = df_filtered['Adj_Depth'].median()
            newspread = newmaximum - newminimum
            if newmedian <= 30:
                pct_thresh = 0.75
            elif newmedian > 30 and newmedian <= 50:
                pct_thresh = 0.4
            else:
                pct_thresh = 0.2
            # filtering on percent change in 12 hrs from thesholds calculated above
            pctchangefilter(df_filtered, 'Adj_Depth','Adj_Depth', pct_thresh, 12)
            # interpolating again
            df_filtered['Adj_Depth'] = df_filtered['Adj_Depth'].interpolate()
            # applying a 12 hr moving mean
            df_filtered['MovingMean']=df_filtered['Adj_Depth'].rolling(window=12).mean()
        except KeyError:
            df_filtered = pd.DataFrame([], columns = ['Raw','Rate','Adj_Depth','MovingMean'])
        # grabbing the SWE
        try:
            SWEdf = pd.DataFrame(site['OBSERVATIONS']['snow_water_equiv_set_1'], columns = ['SWE'])
        except KeyError:
            SWEdf = pd.DataFrame([],columns=['SWE'])
        # grabbing the precip
        try:
            PCPdf = pd.DataFrame(site['OBSERVATIONS']['precip_accum_set_1'], columns = ['Precip'])
        except KeyError:
            PCPdf = pd.DataFrame([], columns = ['Precip'])
        # grabbing the temps
        try:
            TMPdf = pd.DataFrame(site['OBSERVATIONS']['air_temp_set_1'], columns = ['Temp'])
        except KeyError:
            TMPdf = pd.DataFrame([], columns = ['Temp'])
        # combining dataframes
        sitedf = pd.concat([dates, df_filtered, SWEdf, PCPdf, TMPdf], axis=1)
        # now we need to trim the data to our time range in question
        tr_df = sitedf.loc[(sitedf['DateTime'] >= trstart) & (sitedf['DateTime'] <= trend)]
        # now we can pick out the data we need
        for element in outputdict:
            if element == 'Smoothed_Depth':
                diff, maxvar, minvar, meanvar = calcsnotelstats(tr_df['MovingMean'].values.tolist())
                outputdict['Smoothed_Depth'].append(diff)
            if element == 'Filtered_Depth':
                diff, maxvar, minvar, meanvar = calcsnotelstats(tr_df['Adj_Depth'].values.tolist())
                outputdict['Filtered_Depth'].append(diff)
            if element == 'SWE':
                diff, maxvar, minvar, meanvar = calcsnotelstats(tr_df['SWE'].values.tolist())
                outputdict['SWE'].append(diff)
            if element == 'Precip':
                diff, maxvar, minvar, meanvar = calcsnotelstats(tr_df['Precip'].values.tolist())
                outputdict['Precip'].append(diff)
        # if the plot flag is passed, produce graphs of the 15 day data and store them locally 
        # so forecasters can see how the snotel amounts were generated for QC purposes
        if plot:
            plottimeseriessmoothed(graphicspath, sitedf['DateTime'], site['STID'], sitedf['Raw'], sitedf['Adj_Depth'], sitedf['MovingMean'])
        else:
            pass
    return outputdict

def calcPrecipDuration(start, end):
    trstart = datetime.strptime(start, '%Y%m%d%H%M')
    trend = datetime.strptime(end, '%Y%m%d%H%M')
    duration = trend-trstart
    duration_days = duration.days
    duration_hours = duration.seconds/3600
    #durations less than a day get 24hr snow amounts
    if duration_days < 1 and duration_hours > 0:
        time = 1
    # if its 1 day exactly, grab 1 day totals
    if duration_days >= 1 and duration_days < 2 and duration_hours < 1:
        time = 1
    # if its more than 24hrs but less than 48 grab 2 day totals
    if duration_days >= 1 and duration_days < 2 and duration_hours >= 1:
        time = 2
    # if its 2 days exactly, grab 2 day totals
    if duration_days >= 2 and duration_days < 3 and duration_hours < 1:
        time = 2
    # if its more than 48hrs but less than 72 grab 3 day totals
    if duration_days >= 2 and duration_days < 3 and duration_hours >= 1:
        time = 3
     # if its 3 days exactly, grab 3 day totals
    if duration_days >= 3 and duration_days < 4 and duration_hours < 1:
        time = 3
    # if its more than 72hrs but less than 96 grab 4 day totals
    if duration_days >= 3 and duration_days < 4 and duration_hours >= 1:
        time = 4
     # if its 4 days exactly, grab 4 day totals
    if duration_days >= 4 and duration_days < 5 and duration_hours < 1:
        time = 4
    # if its more than 96hrs but less than 120 grab 5 day totals
    if duration_days >= 4 and duration_days < 5 and duration_hours >= 1:
        time = 5
    if duration_days >=5 and duration_days < 6 and duration_hours < 1:
        time = 5
    # time ranges > 5 days don't exist on IRIS
    if duration_days >=6:
        raise RuntimeError
        time = 0
    return time 

def getCoCoRahs(start, end, duration): 
    # base url for grabbing CoCoRahs
    base_url = 'https://data.cocorahs.org/export/exportreports.aspx?ReportType=Daily&Format=CSV&State=AK'
    # converting start and end to datetime objects
    trstart = datetime.strptime(start, '%Y%m%d%H%M')
    trend = datetime.strptime(end, '%Y%m%d%H%M')
    # if the ending hour is > 18 then we need to try to grab the next days total
    end_hour = trend.hour
    next_day = trend+timedelta(days = 1)
    if end_hour > 18:
        end_range = duration+1
    else:
        end_range = duration
    # building our list of days for which to grab daily CoCoRahs data
    # building our CoCoRahs date range
    start_format = trstart.strftime('%m/%d/%Y')
    end_format = (trstart + timedelta(days=end_range)).strftime('%m/%d/%Y')
    date_for_file = trstart.strftime('%Y%m%d')+'_'+(trstart + timedelta(days=end_range)).strftime('%Y%m%d')
    url = base_url+'&startdate='+start_format+'&enddate='+end_format
    response = requests.get(url, timeout=30)
    csv_data = StringIO(response.text)
    df = pd.read_csv(csv_data, index_col=0)
    #df['EntryDateTime'] = pd.to_datetime(df['EntryDateTime'], format=' %Y-%m-%d %I:%M %p')
    cols_to_clean = ['TotalPrecipAmt', 'NewSnowDepth', 'NewSnowSWE', 'TotalSnowDepth', 'TotalSnowSWE']
    df[cols_to_clean] = df[cols_to_clean].replace({' NA': '0', ' T': '0'})
    # now summing
    cols_to_sum = ['TotalPrecipAmt', 'NewSnowDepth', 'NewSnowSWE']
    groupby_cols = ['StationNumber', 'StationName', 'Latitude', 'Longitude']
    # changing columns to numeric
    df[cols_to_sum] = df[cols_to_sum].apply(pd.to_numeric)
    #summing multiple day precip amounts if necessary
    df2 = df.groupby(groupby_cols)[cols_to_sum].sum()
    df2.reset_index(inplace=True)
    # inserting the type of ob
    df2.insert(len(df2.columns), column='ObType', value='CoCoRahs')
    # renaming the columns to match our master sheet
    df3 = df2.rename(columns={'StationName': 'stationname', 'Latitude':'Lat', 'Longitude':'Lon', 'TotalPrecipAmt':'Precip', 'NewSnowDepth':'snowfall', 'NewSnowSWE':'SWE'})
    myfile = 'AK_CoCoRahs_'+date_for_file+'.csv'
    return df3, myfile

def downloadCOOP(url, cwa, networkkey, start, end, token):
    '''
    Parameters
    ----------
    url : Mesowest API Time Series URL
    cwa : 3 Letter CWA indentifier
    start : Start time of the time range you want snotel data for (YYYYmmddHHMM)
    end : End time of the time range you want snotel data for (YYYYmmddHHMM)
    networkkey : Network ID from Mesowest API documentation (25 is Snotels)
    token : Your unique MesoWest API token
    Returns
    -------
    data : Json dictionary of Snotel output

    '''
     # Initializing our url
    url += f'cwa={cwa}&network={networkkey}'
    url += '&start='+start+'&end='+end+'&units=english&token='+token
    page = urllib.request.urlopen(url)
    data = page.read()
    return data

def grabcoopvars(jsondict, snowvar, pcpvar):
    coopdata = {'stationname': [], 'stid': [], 'Lat': [], 'Lon': [], 'datetime': [], 'snowfall': [], 'Precip': [], 'ObType': []}
    for site in jsondict['STATION']:
        name = site['NAME']
        stid = site['STID']
        lat = site['LATITUDE']
        lon = site['LONGITUDE']
        obtype = 'COOP'
        print(f'Name is: {name}')
        print(site['OBSERVATIONS'])
        try:
            snw = round(sum(site['OBSERVATIONS'][snowvar]),1)
            print(snw)
            #snwidx = site['OBSERVATIONS'][snowvar].index(-1)
            snwidx = -1
        except KeyError:
            continue
        except TypeError:
            continue
        try:
            pcp = site['OBSERVATIONS'][pcpvar][snwidx]
        except KeyError:
            continue
        datetimes = site['OBSERVATIONS']['date_time']
        dt_converted = [datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ') for x in datetimes]
        timedata = dt_converted[snwidx]
        coopdata['stationname'].append(name)
        coopdata['stid'].append(stid)
        coopdata['Lat'].append(lat)
        coopdata['Lon'].append(lon)
        coopdata['datetime'].append(timedata)
        coopdata['snowfall'].append(snw)
        coopdata['Precip'].append(pcp)
        coopdata['ObType'].append(obtype)
    return coopdata     

def getzeroes(sitelist):
    global TOKEN
    url = 'https://api.synopticlabs.org/v2/stations/metadata?'
    url+=f'&stid={sitelist}'
    url+=f'&token={TOKEN}'
    page = urllib.request.urlopen(url)
    data = page.read()
    return data


def parsezerodata(json_response):
    sitedict = {'stationname': [], 'Lat': [], 'Lon': [], 'snowfall': []}
    for response in json_response['STATION']:
        sitedict['stationname'].append(response['STID'])
        sitedict['Lat'].append(float(response['LATITUDE']))
        sitedict['Lon'].append(float(response['LONGITUDE']))
        sitedict['snowfall'].append(0)
    df = pd.DataFrame(sitedict)
    return df

    

################## Set up from config file ##################################

DATAPATH = SC.DATAPATH

COOP_FILE = SC.COOP_FILE

COOPNETWORK = SC.COOPNETWORK

SNOWVAR = SC.SNOWVAR

PCPVAR = SC.PCPVAR

LSR_FILE = SC.LSR_FILE

LSR_DICT = SC.LSR_DICT

OUTFILE = SC.OUTFILE

KEEP_COLS = SC.KEEP_COLS

SHEET_URL = SC.SHEET_URL

SNOTEL_URL = SHEET_URL.replace('/edit#gid=', '/export?format=csv&gid=')

LSRURL = SC.LSRURL

DAYSBACK = SC.DAYSBACK

SNOTEL_URL = SC.SNOTEL_URL

TOKEN = SC.TOKEN

VARS = SC.VARS

SNOTEL_VARS = SC.SNOTEL_VARS

NETWORK = SC.NETWORK
 
SNOTEL_SHEET = False

SNOTEL_DICT = SC.SNOTEL_DICT

SNOTELCSVFILE = SC.SNOTELCSVFILE

GRAPHICSPATH = SC.GRAPHICSPATH

COOPFILE = SC.COOP_FILE

LOG_PATH = SC.LOG_PATH

LOG_FILE = SC.LOG_FILE

###########################  Main Script #####################################

def execute(START, END, WFO, ZEROS):
    global LOG_PATH, LOG_FILE, LSR_FILE, LSR_DICT, LSRURL, SNOTEL_URL, COOPNETWORK, TOKEN
    global SNOWVAR, PCPVAR, COOP_FILE, SNOTEL_DICT, SNOTEL_SHEET, SNOTEL_VARS, NETWORK
    global SNOTELCSVFILE, GRAPHICSPATH, OUTFILE
    # Setting up our logging
    # using the default root logger
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    # Configuring our log
    logging.basicConfig(filename=os.path.join(LOG_PATH, LOG_FILE), filemode='w',
                        format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S',
                        level=logging.DEBUG)
    # Grabbing our logger
    logger = logging.getLogger('')
    # Gathering LSR data
    logger.info('Now collecting LSR data for the time frame %s to %s', START, END )
    # testing our datetime format to make sure its correct
    trstart = datetime.strptime(START, '%Y%m%d%H%M')
    trend = datetime.strptime(END, '%Y%m%d%H%M')
    if len(START) != 12 or len(END) != 12:
        raise ValueError
    else:
        pass
    # Don't want to do more than 6 days accumulation
    if trend-trstart >= timedelta(days=6):
        raise RuntimeError
    else:
        pass
    # Don't want the start time to be => end time
    if trstart >= trend:
        raise UnboundLocalError
    else:
        pass
        
    lsrdata = downloadLSR(LSRURL, START, END, WFO)
    lsr_json = parse_json(lsrdata)
    lsr_df = pd.DataFrame(formatLSRcsv(lsr_json, LSR_DICT))
    logger.info('Got LSRs!')
    #print(lsr_json)
    # error handling for empty dataframes
    try:
        # now we sort by datetime
        logger.info('Sorting LSRs and keeping only the latest one')
        sorted_df = lsr_df.sort_values(by = 'datetime', ascending=False)
        # now we remove duplicates  in lat and lon taking the latest lsr
        trimmed_df = sorted_df.drop_duplicates(subset=['Lat', 'Lon'], keep='first')
        # making sure we just have snow LSRs
        logger.info('Dropping non snow LSRs')
        snowdf = trimmed_df[trimmed_df['Type'].str.contains('SNOW')]
        snowdf.to_csv(os.path.join(DATAPATH, LSR_FILE))
        logger.info('LSRs all saved to %s', os.path.join(DATAPATH, LSR_FILE))
    except AttributeError:
        logger.info('No LSRs found for the time period %s to %s' % (START, END))
        lsr_df.to_csv(os.path.join(DATAPATH, LSR_FILE))
    ## Gathering CoCoRahs Data
    logger.info('Now grabbing CoCoRahs data')
    duration = calcPrecipDuration(START, END)
    logger.info('Precip duration is %s', duration)
    if duration != 0:
        coco_df, cocoflname = getCoCoRahs(START, END, duration)
        coco_df.to_csv(os.path.join(DATAPATH, cocoflname))
        logger.info('CoCoRahs data now saved to %s', os.path.join(DATAPATH, cocoflname))
    else:
        logger.info('Precipitation duration is 0 hrs.  Please choose a different start and end time!')
        sys.exit()
    ## Gathering COOP data...there will likely be duplicates between LSRs/COOPs/CoCoRahs so
    ## need thorough QC for the best analysis
    logger.info('Now grabbing COOP data')
    jsondata = parse_json(downloadCOOP(SNOTEL_URL, WFO, COOPNETWORK, START, END, TOKEN))
    #print(jsondata)
    coopvals = grabcoopvars(jsondata, SNOWVAR, PCPVAR)
    coopdf = pd.DataFrame(coopvals)
    coopdf.to_csv(os.path.join(DATAPATH, COOP_FILE))
    logger.info('All done grabbing COOP data. CSV is saved to %s', os.path.join(DATAPATH, COOP_FILE))
    ## Gathering Snotel Data...use the manual google sheet unless passed False on
    ## the snotel sheet flag...at which point we use the automated download and 
    ## smoothing process (which will still need to be looked at for bad data!)
    logger.info('Now grabbing snotel data...')
    if SNOTEL_SHEET:
        pass
    else:
        # new start and end times for smoothing the data
        starttime, endtime = calcsnoteldaytimerange(START, END, DAYSBACK)
        logger.info('Now getting snotel data from %s to %s from mesowest' % (starttime, endtime))
        # testing to see if our original start time is > 15 days back from the end time
        calc_start = datetime.strptime(starttime, '%Y%m%d%H%M')
        orig_start = datetime.strptime(START, '%Y%m%d%H%M')
        if orig_start < calc_start:
            # downloading the data
            rawdata = downloadSNOTELCWA(SNOTEL_URL, WFO, START, endtime, NETWORK, TOKEN)
        else:
            # downloading the data
            rawdata = downloadSNOTELCWA(SNOTEL_URL, WFO, starttime, endtime, NETWORK, TOKEN)
        jsondata = parse_json(rawdata)
        logger.info('Got the data!')
        #print(jsondata)
        # now formatting the dataframes with 15 days of data
        logger.info('Now formatting and smoothing snotel data')
        snoteloutput = formatSNOTELcsv(GRAPHICSPATH, jsondata, SNOTEL_DICT, SNOTEL_VARS, START, END)
        # creating output csv
        snotelcsv = pd.DataFrame(snoteloutput)
        newsnotelcsv = snotelcsv.rename(columns={'STID': 'stationname', 'Filtered_Depth':'snowfall'})
        newsnotelcsv.to_csv(os.path.join(DATAPATH, SNOTELCSVFILE))
        logger.info('Done downloading and saving %s to %s.  This data will still need to be QCed! Check %s for the output graphics' % (SNOTELCSVFILE, DATAPATH, GRAPHICSPATH))

    if len(ZEROS) > 0:
        # Adding in any sites with zero data
        formatted_zeros = ZEROS.replace(' ','').lower()
        logger.info(f'Sites with zero snowfall data are: {formatted_zeros}')
        zerodata = parse_json(getzeroes(formatted_zeros))
        if zerodata['SUMMARY']['RESPONSE_MESSAGE'] == 'OK':
            logger.info('Found valid json response for zero data')
            zerosdf = parsezerodata(zerodata)
        else:
            logger.error(f'Formatting error on sites with zero snowfall!  See message from Synoptic: {zerodata["SUMMARY"]["RESPONSE_MESSAGE"]}')
            newsitelist = formatted_zeros.rstrip(',')
            newzerodata = parse_json(getzeroes(newsitelist))
            logger.info(f'New json response is: {newzerodata}')
            zerosdf = parsezerodata(newzerodata)
    
    ## Merging all the data in to one csv
    logger.info('Now merging all the data together...')
    cocorahdf = pd.read_csv(os.path.join(DATAPATH, cocoflname))
    coopdf = pd.read_csv(os.path.join(DATAPATH, COOP_FILE))
    lsrdf = pd.read_csv(os.path.join(DATAPATH, LSR_FILE))
    snoteldf = pd.read_csv(os.path.join(DATAPATH, SNOTELCSVFILE))
    if len(ZEROS) > 0:
        finaldf = pd.concat([lsrdf, coopdf, cocorahdf, snoteldf, zerosdf])
    else:
        finaldf = pd.concat([lsrdf, coopdf, cocorahdf, snoteldf])
    finaldf.to_csv(os.path.join(DATAPATH, OUTFILE), columns=KEEP_COLS, index=False)
    logger.info('All done with merging of snow data.  Please check %s and QC final output before plotting!', os.path.join(DATAPATH, OUTFILE))


def input():
    global window
    # grabbing our start and end times from the GUI
    START = startvar.get()
    END = endvar.get()
    CWA = clicked.get()
    ZEROS = zero_obs_var.get()
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    # Configuring our log
    logging.basicConfig(filename=os.path.join(LOG_PATH, LOG_FILE), filemode='w',
                        format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S',
                        level=logging.DEBUG)
    # Grabbing our logger
    logger = logging.getLogger('')
    #execute(START, END, CWA, ZEROS)
    try:
        execute(START, END, CWA, ZEROS)
        tkinter.messagebox.showwarning(title=None, message=f'All done with merging of snow data.  \n\nPlease check {os.path.join(DATAPATH, OUTFILE)} and QC final output before plotting! \n\nHit "Quit" to close main window or enter new dates to try again.')
    except ValueError:
        logger.info('Wrong datetime format! Must be YYYYmmddHHMM. Ex: 202012021800')
        tkinter.messagebox.showwarning(title=None, message='Wrong datetime format! Must be YYYYmmddHHMM. Ex: 202012021800')
        #tkinter.messagebox.showerror(title=None, message=None)
        window.destroy()
        sys.exit()
    except UnboundLocalError:
        logger.info('End date is before your start date.  Please try again!')
        tkinter.messagebox.showwarning(title=None, message='End date is before your start date.  Please try again!')
        window.destroy()
        sys.exit()
    except RuntimeError:
        logger.info('Requested time range is > 5 days.  Try again with a shorter time range')
        tkinter.messagebox.showwarning(title=None, message='Requested time range is > 5 days.  Try again with a shorter time range')
        window.destroy()
        sys.exit()

window = tkinter.Tk()

window.title('Get Snowfall Data')

window.geometry("%dx%d+%d+%d" % (600, 600, 800, 800))

window.eval('tk::PlaceWindow %s center' % window.winfo_toplevel())

window.config(bg="blue")

# label for dropdown menu
label1 = tkinter.Label(window, text = "Select Your CWA", font=('Arial', 12, 'bold'), padx = 10, pady = 10)
label1.config(bg='blue', fg='white')
label1.pack()
#datatype of dropdown menu
clicked = tkinter.StringVar()
#initial set for dropdown
clicked.set(SC.DEFAULT_CWA)
#creating dropdown menu
dropdown = tkinter.OptionMenu(window, clicked, *SC.CWAS)
dropdown.pack(side='top',padx=10, pady=10, expand='no', fill='y')

label = tkinter.Label(window,text='Enter Start Time (UTC): YYYYmmddHHMM', font=('Arial', 12, 'bold'))
label.config(bg='blue', fg='white')
label.pack(side='top', pady='20', padx='20')
startvar = tkinter.Entry(window)

startvar.pack(side = 'top', pady = '10', padx = '10')

label2 = tkinter.Label(window,text='Enter End Time (UTC): YYYYmmddHHMM',font=('Arial', 12, 'bold'))
label2.config(bg='blue', fg='white')
label2.pack(side='top', pady='20', padx='20')
endvar = tkinter.Entry(window)

endvar.pack(side = 'top', pady = '10', padx = '10')

zero_obs_label = tkinter.Label(window,text='If you wish to add sites with 0 snowfall,\n type the site IDs in comma separated format\n (Ex: panc,pajn,pawd) below.\n Leave blank if you do not wish to add sites with 0 snowfall.',font=('Arial', 12, 'bold'))
zero_obs_label.config(bg='blue', fg='white')
zero_obs_label.pack(side='top', pady='20', padx='20')
zero_obs_var = tkinter.Entry(window, width=80)
zero_obs_var.pack(side = 'top', pady = '10', padx = '10')

button = tkinter.Button(window, text="Get Snowfall Data In Between The Above Times", command=input)
button.config(bg="forest green",fg="white", activebackground="gray", activeforeground="black", width=60)
button.pack(side='top', padx=20, pady=10)

quitbutton = tkinter.Button(window, text="Quit", command=window.destroy)
quitbutton.config(bg="forest green",fg="white", activebackground="gray", activeforeground="black", width=10)
quitbutton.pack(side='top', padx=20, pady=10)

window.mainloop()

'''
Sites to add for snotel: LSL, HUR, GIR, AYM, MRW, GCV, RRP, HRP, LES, NVS, GCD, HMW, TUN, MPS, SNE, RRW (same as snotels...need to be smoothed)
'''