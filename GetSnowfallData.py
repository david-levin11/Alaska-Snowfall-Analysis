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
    # base_url like "https://example/lsr?"; we’ll handle "?" vs none below
    params = {"sts": start, "ets": end, "wfos": wfo}
    separator = "&" if "?" in base_url else "?"
    url = base_url + separator + urllib.parse.urlencode(params)

    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.load(resp)  # returns a Python dict

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

def downloadSNOTELCWA(url, cwa, start, end, varkey, token, varsoperator="AND"):
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
    url += '&start='+start+'&end='+end+'&vars='+varkey+'&varsoperator='+varsoperator+'&units=english&token='+token
    #print(f"URL is: {url}")
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
    
def check_avg_data_interval(ts, vals):
    '''
    Determines whether to apply filtering based on the average
    interval between VALID observations.

    Returns:
        True  -> apply filter (avg interval < 3 hours)
        False -> do not filter (manual observations)
    '''
    # Build a dataframe
    df = pd.DataFrame({
        "time": pd.to_datetime(ts, format="%Y-%m-%dT%H:%M:%SZ"),
        "val": vals
    })

    # Keep only rows with valid data
    df = df[df["val"].notna()]

    # Need at least two observations to compute an interval
    if len(df)<2:
        return False
    
    #Compute time difference in hours
    diff_hours = df["time"].diff().dt.total_seconds().to_numpy()/3600

    avg_interval = np.nanmean(diff_hours)

    return avg_interval < 3

def eligible_mask(df, qc_cols):
    return df[qc_cols].eq("PASS").all(axis=1)

def drop_high_freq(df, timecol):
    """
    Remove sub-hourly observations from high-frequency stations.

    Many automated sensors report every 5–15 minutes. Since the snow
    depth filtering pipeline assumes hourly data, this function keeps
    only observations occurring near the top of the hour.

    Currently the filter keeps observations where the minute value
    is less than 10.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing timestamp column.

    timecol : str
        Name of the column containing datetime values.

    Returns
    -------
    pandas.DataFrame
        DataFrame indexed by datetime containing only near-hourly
        observations.
    """
    df = df.set_index(timecol)

    # keep only obs within the first 10 minutes of the hour
    resampled = df[df.index.minute < 10]

    return resampled

def create_moving_average(df, obs_col, window="12h", outputcol = "snowfall"):
    df[outputcol] = df[obs_col].rolling(window).mean()
    return df

def gross_check(df, check_col, low=0, high=100):
    """
    Perform a gross error check on snow depth values.

    This test removes obviously unrealistic values using two rules:

    1) Values below a minimum threshold (default = 0 inches)
    2) Values that exceed the median value by a large margin

    The median-based threshold helps detect sensors that suddenly
    report extremely large values due to sensor malfunction.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing the observation column.

    check_col : str
        Name of the column containing the snow depth values.

    low : float, default 0
        Minimum physically possible snow depth.

    high : float, default 100
        Maximum allowable deviation above the median.

    Returns
    -------
    pandas.DataFrame
        DataFrame with a new column "QC_gross" containing PASS/FAIL flags.
    """
    median = df[check_col].median()

    df["QC_gross"] = "PASS"

    df.loc[df[check_col] > median + high, "QC_gross"] = "FAIL"
    df.loc[df[check_col] < low, "QC_gross"] = "FAIL"

    return df

def consistency_check(df, check_col, up=50, down=50, prev_cols=("QC_gross",)):
    """
    Check for unrealistic jumps between consecutive observations.

    This test flags observations where the change from the previous
    valid observation exceeds an allowed threshold.

    Only observations that passed all previous QC checks are evaluated.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing observation values and previous QC columns.

    check_col : str
        Name of the column containing snow depth values.

    up : float
        Maximum allowed increase between consecutive observations.

    down : float
        Maximum allowed decrease between consecutive observations.

    prev_cols : tuple
        QC columns that must have PASS status before applying this test.

    Returns
    -------
    pandas.DataFrame
        DataFrame with column "QC_consistency" added.
    """
    df = df.copy()
    df["QC_consistency"] = "PASS"

    elig = eligible_mask(df, list(prev_cols))

    # Only compute differences for eligible observations
    x = df[check_col].astype(float).where(elig)
    d = x.diff()

    # Optional debug column
    df["Diff"] = d

    df.loc[elig & (d > up), "QC_consistency"] = "FAIL"
    df.loc[elig & (d < -down), "QC_consistency"] = "FAIL"

    return df

def spike_check(df, check_col, spikeval=5, prev_cols=("QC_gross","QC_consistency")):
    """
    Detect isolated spikes in the snow depth time series.

    This test compares each observation to the maximum of the next
    five observations. If the current value exceeds the future values
    by more than a specified threshold, it is flagged as a spike.

    This helps identify temporary sensor glitches where a single
    observation briefly jumps to an unrealistic value.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing snow depth values and QC columns.

    check_col : str
        Column containing snow depth observations.

    spikeval : float
        Maximum allowed difference between the current observation
        and the maximum of the next five observations.

    prev_cols : tuple
        QC columns that must have PASS status before applying this test.

    Returns
    -------
    pandas.DataFrame
        DataFrame with column "QC_spike" added.
    """
    df = df.copy()
    df["QC_spike"] = "PASS"

    elig = eligible_mask(df, list(prev_cols))

    # Only evaluate eligible values
    raw = df[check_col].astype(float).where(elig)

    # Look ahead to the next 5 observations
    next5 = np.column_stack([
        raw.shift(-i).to_numpy(dtype=float) for i in range(1, 6)
    ])

    # Count how many future observations exist
    n_future = np.sum(~np.isnan(next5), axis=1)

    # Replace NaN with -inf so they don't affect max calculation
    safe = np.where(np.isnan(next5), -np.inf, next5)

    next5_max = np.max(safe, axis=1)

    # Spike condition
    fail = (
        (elig.to_numpy()) &
        (n_future > 0) &
        (raw.to_numpy(dtype=float) > (next5_max + spikeval))
    )

    df.loc[fail, "QC_spike"] = "FAIL"

    return df

def rate_check_since_last_good(
    df,
    check_col,
    up_rate=2.0,
    down_rate=2.0,
    prev_cols=("QC_gross","QC_consistency","QC_spike"),
    out_col="QC_rate",
):
    '''
    Stateful rate check. Will take a pandas dataframe and
    check for unrealistic snow depth hourly rates which are computed
    only for values that have passed previous QC checks
    '''
    df = df.sort_index().copy()
    # default out column is SKIP...changes to PASS/FAIL later if need be
    df[out_col] = "SKIP"
    # find where we have passed previous QC checks
    elig = df[list(prev_cols)].eq("PASS").all(axis=1).to_numpy()
    # raw values that have passed QC
    vals = df[check_col].astype(float).to_numpy()
    # associated times
    times = df.index.to_numpy()

    last_good_i = None

    for i in range(len(df)):
        if not elig[i] or np.isnan(vals[i]):
            continue

        if last_good_i is None:
            df.iloc[i, df.columns.get_loc(out_col)] = "PASS"
            last_good_i = i
            continue
        # How long since last good value
        dt_hours = (times[i] - times[last_good_i]) / np.timedelta64(1, "h")
        if dt_hours <= 0:
            continue
        # what is the snow depth increase over that time
        rate = (vals[i] - vals[last_good_i]) / dt_hours
        # checking against our rate threshold
        if (rate > up_rate) or (rate < -down_rate):
            df.iloc[i, df.columns.get_loc(out_col)] = "FAIL"
        else:
            df.iloc[i, df.columns.get_loc(out_col)] = "PASS"
            last_good_i = i

    return df


def final_qc(df, qc_cols=("QC_gross","QC_consistency","QC_spike","QC_rate")):
    '''
    Turns on an overall QC flag for any columns that have failed a previous QC
    check.  Can pass any number of columns but the default is used at the end
    of the snow depth qc process
    '''
    df = df.copy()
    df["QC_flag"] = np.where(df[list(qc_cols)].eq("FAIL").any(axis=1), "FAIL", "PASS")
    return df


def interpolate_and_fill(df, ma_col, qc_col, output_col="raw_interp", max_gap=3):
    '''
    Interpolates between good values in the moving average time series
    Copies forward the last good value to the end of the series
    '''
    ma_good = df[ma_col].where(df[qc_col] == "PASS")

    interp = ma_good.interpolate(
        method="time",
        limit=max_gap,
        limit_direction="forward"
    )

    df[output_col] = interp.ffill()

    return df

def should_run_repeated_check(df, check_col="Raw", range_thresh=100):
    """
    Decide whether a site is suspicious enough to justify a repeated-run check.

    range_thresh: apply repeated-run filter only if 30-day range exceeds this value
    """
    x = pd.to_numeric(df[check_col], errors="coerce")
    if x.notna().sum() < 2:
        return False

    site_range = x.max() - x.min()
    return site_range >= range_thresh


def repeated_run_check(df, check_col, window=12, max_unique=2, out_col="QC_repeat_run"):
    """
    Flag long runs where the sensor only cycles through a very small number
    of rounded values.

    window: number of consecutive hours to inspect
    max_unique: maximum number of unique rounded values allowed in the window
    """
    df = df.copy()
    df[out_col] = "PASS"

    x = df[check_col].astype(float).round(2).to_numpy()
    n = len(x)

    for i in range(n - window + 1):
        seg = x[i:i+window]

        if np.isnan(seg).any():
            continue

        n_unique = len(np.unique(seg))

        if n_unique <= max_unique:
            df.iloc[i:i+window, df.columns.get_loc(out_col)] = "FAIL"

    return df

def manual_depth_change(df, start_dt, end_dt, value_col="Raw", time_col="DateTime"):
    """
    Compute snow depth change for a manual site using the most recent
    available observation at or before each requested datetime.
    """

    df = df.copy()

    # If DateTime is still a column, make it the index
    if time_col in df.columns:
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.set_index(time_col)

    # Make sure the index is datetime and sorted
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    x = pd.to_numeric(df[value_col], errors="coerce").dropna()

    start_dt = pd.to_datetime(start_dt)
    end_dt = pd.to_datetime(end_dt)

    before_start = x.loc[:start_dt]
    before_end = x.loc[:end_dt]
    inside_window = x.loc[start_dt:end_dt]

    # case 1: both sides exist
    if not before_start.empty and not before_end.empty:
        start_val = before_start.iloc[-1]
        end_val = before_end.iloc[-1]
        start_time = before_start.index[-1]
        end_time = before_end.index[-1]

    # case 2: only obs inside window
    elif not inside_window.empty:
        val = inside_window.iloc[0]
        start_val = val
        end_val = val
        start_time = inside_window.index[0]
        end_time = inside_window.index[0]

    # case 3: only obs before start
    elif not before_start.empty:
        val = before_start.iloc[-1]
        start_val = val
        end_val = val
        start_time = before_start.index[-1]
        end_time = before_start.index[-1]

    else:
        return None

    return {
        "start_obs_time": start_time,
        "start_val": start_val,
        "end_obs_time": end_time,
        "end_val": end_val,
        "depth_change": end_val - start_val
    }

def formatSNOTELcsv(graphicspath, jsondata, outputdict, start, end, plot=True):
    # converting start and end to datetime objects
    trstart = datetime.strptime(start, '%Y%m%d%H%M')
    trend = datetime.strptime(end, '%Y%m%d%H%M')
    # removing old graphics first
    if plot:
        removegraphics(graphicspath)
    for site in jsondata["STATION"]:
        if site['MNET_ID'] in SC.COOPIDS:
            print(f"{site['STID']} is a COOP site and will be handled differently")
            continue

        raw_out = np.nan
        filtered_out = np.nan
        smoothed_out = np.nan

        filter_check = check_avg_data_interval(
            site['OBSERVATIONS']['date_time'],
            site['OBSERVATIONS'][SC.VARS]
        )

        datetimes = site['OBSERVATIONS']['date_time']
        dt_converted = [datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ') for x in datetimes]
        dates = pd.DataFrame(dt_converted, columns=['DateTime'])

        try:
            depth = site['OBSERVATIONS']['snow_depth_set_1']
            depthdf = pd.DataFrame(depth, columns=['Raw'])
        except KeyError:
            depthdf = pd.DataFrame([], columns=['Raw'])

        sitedf = pd.concat([dates, depthdf], axis=1)

        if filter_check:
            df_hourly = drop_high_freq(sitedf, "DateTime")
            df1 = gross_check(df_hourly, "Raw")

            if should_run_repeated_check(df1, "Raw", range_thresh=100):
                df2 = repeated_run_check(df1, "Raw", window=12, max_unique=2)
            else:
                df2 = df1.copy()
                df2["QC_repeat_run"] = "PASS"

            df3 = consistency_check(df2, "Raw", up=5, down=5, prev_cols=("QC_gross", "QC_repeat_run"))
            df4 = spike_check(df3, "Raw", spikeval=5, prev_cols=("QC_gross", "QC_repeat_run", "QC_consistency"))
            df5 = rate_check_since_last_good(
                df4,
                "Raw",
                up_rate=1.5,
                down_rate=1.5,
                prev_cols=("QC_gross", "QC_repeat_run", "QC_consistency", "QC_spike"),
                out_col="QC_rate"
            )
            df6 = final_qc(df5, qc_cols=("QC_gross", "QC_repeat_run", "QC_consistency", "QC_spike", "QC_rate"))
            df_interp = interpolate_and_fill(df6, "Raw", "QC_flag", output_col="raw_interp")
            df_snow_depth = create_moving_average(df_interp, "raw_interp")
            # if the plot flag is passed, produce graphs of the 30 day data and store them locally 
            # so forecasters can see how the snotel amounts were generated for QC purposes
            #print(df_snow_depth.columns)
            if plot:
                plottimeseriessmoothed(graphicspath, df_snow_depth.index,
                                        site["STID"], df_snow_depth["Raw"],
                                        df_snow_depth["raw_interp"],
                                            df_snow_depth["snowfall"])

            depth_change = df_snow_depth.loc[pd.to_datetime(trstart):pd.to_datetime(trend)]

            if not depth_change.empty:
                raw_out = depth_change["Raw"].iloc[-1] - depth_change["Raw"].iloc[0]
                filtered_out = depth_change["raw_interp"].iloc[-1] - depth_change["raw_interp"].iloc[0]
                smoothed_out = depth_change["snowfall"].iloc[-1] - depth_change["snowfall"].iloc[0]
                # Don't include negative snow depths for mapping purposes
                if filtered_out < 0:
                    filtered_out = 0.0
                if smoothed_out < 0:
                    smoothed_out = 0.0

        else:
            depth_dict = manual_depth_change(sitedf, trstart, trend, value_col="Raw", time_col="DateTime")
            if depth_dict is not None:
                raw_out = depth_dict["depth_change"]
                filtered_out = depth_dict["depth_change"]
                smoothed_out = depth_dict["depth_change"]
                # Don't include negative snow depths for mapping purposes
                if filtered_out < 0:
                    filtered_out = 0.0
                if smoothed_out < 0:
                    smoothed_out = 0.0
        #print(f"Columns are: {df_snow_depth.columns}")
        outputdict['STID'].append(site['STID'])
        outputdict['Lat'].append(site['LATITUDE'])
        outputdict['Lon'].append(site['LONGITUDE'])
        outputdict['ObType'].append('SNOWDEPTH_SITE')
        outputdict['Raw'].append(raw_out)
        outputdict["Filtered_Depth"].append(round(filtered_out,1))
        outputdict["Smoothed_Depth"].append(round(smoothed_out,1))

        print(f"Done calculating obs from {site['STID']}")
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
        #print(f'Name is: {name}')
        #print(site['OBSERVATIONS'])
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

NETWORK = SC.NETWORK

VARKEY = SC.VARKEY
 
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
    global SNOWVAR, PCPVAR, COOP_FILE, SNOTEL_DICT, SNOTEL_SHEET, NETWORK
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
        
    lsr_json = downloadLSR(LSRURL, START, END, WFO)
    #print(f"LSR data is: {lsr_json}")
    #lsr_json = parse_json(lsrdata)
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
            rawdata = downloadSNOTELCWA(SNOTEL_URL, WFO, START, endtime, VARKEY, TOKEN)
        else:
            # downloading the data
            rawdata = downloadSNOTELCWA(SNOTEL_URL, WFO, starttime, endtime, VARKEY, TOKEN)
        jsondata = parse_json(rawdata)
        logger.info('Got the data!')
        #print(jsondata)
        # now formatting the dataframes with 15 days of data
        logger.info('Now formatting and smoothing snotel data')
        snoteloutput = formatSNOTELcsv(GRAPHICSPATH, jsondata, SNOTEL_DICT, START, END)
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

# if __name__ == "__main__":
#     execute("202603030600","202603042100","AJK","")