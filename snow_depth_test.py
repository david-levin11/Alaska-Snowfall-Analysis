import os
import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import urllib
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, DayLocator
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import snowfalloutputconfig as SC

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

VARKEY = SC.VARKEY
 
SNOTEL_SHEET = False

SNOTEL_DICT = SC.SNOTEL_DICT

SNOTELCSVFILE = SC.SNOTELCSVFILE

GRAPHICSPATH = SC.GRAPHICSPATH

COOPFILE = SC.COOP_FILE

LOG_PATH = SC.LOG_PATH

LOG_FILE = SC.LOG_FILE

def downloadSNOTELCWA_dev(url, cwa, start, end, varkey, token, varsoperator="AND"):
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

def calcsnoteldaytimerange(start, end, daysback):
    tr_start = (datetime.strptime(end, '%Y%m%d%H%M')-timedelta(days=daysback)).strftime('%Y%m%d%H%M')
    tr_end = end
    return tr_start, tr_end

def parse_json(data):
    # Converting from json to python dictionary
    json_dict = json.loads(data)
    return json_dict

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
    df = df.set_index(timecol)
    # keep only obs near the top of the hour
    resampled = df[df.index.minute < 10]
    return resampled

def create_moving_average(df, obs_col, window="12h", outputcol = "snowfall"):
    df[outputcol] = df[obs_col].rolling(window).mean()
    return df

def gross_check(df, check_col, low=0, high=100):
    median = df[check_col].median()

    df["QC_gross"] = "PASS"

    df.loc[df[check_col] > median + high, "QC_gross"] = "FAIL"
    df.loc[df[check_col] < low, "QC_gross"] = "FAIL"

    return df

def consistency_check(df, check_col, up=50, down=50, prev_cols=("QC_gross",)):
    df = df.copy()
    df["QC_consistency"] = "PASS"

    elig = eligible_mask(df, list(prev_cols))
    x = df[check_col].astype(float).where(elig)  # non-eligible become NaN
    d = x.diff()

    df["Diff"] = d  # optional debug
    df.loc[elig & (d > up), "QC_consistency"] = "FAIL"
    df.loc[elig & (d < -down), "QC_consistency"] = "FAIL"
    return df

def spike_check(df, check_col, spikeval=5, prev_cols=("QC_gross","QC_consistency")):
    df = df.copy()
    df["QC_spike"] = "PASS"

    elig = eligible_mask(df, list(prev_cols))
    raw = df[check_col].astype(float).where(elig)  # only eligible values participate

    next5 = np.column_stack([raw.shift(-i).to_numpy(dtype=float) for i in range(1, 6)])
    n_future = np.sum(~np.isnan(next5), axis=1)

    safe = np.where(np.isnan(next5), -np.inf, next5)
    next5_max = np.max(safe, axis=1)

    fail = (elig.to_numpy()) & (n_future > 0) & (raw.to_numpy(dtype=float) > (next5_max + spikeval))
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
    df = df.sort_index().copy()
    df[out_col] = "SKIP"

    elig = df[list(prev_cols)].eq("PASS").all(axis=1).to_numpy()
    vals = df[check_col].astype(float).to_numpy()
    times = df.index.to_numpy()

    last_good_i = None

    for i in range(len(df)):
        if not elig[i] or np.isnan(vals[i]):
            continue

        if last_good_i is None:
            df.iloc[i, df.columns.get_loc(out_col)] = "PASS"
            last_good_i = i
            continue

        dt_hours = (times[i] - times[last_good_i]) / np.timedelta64(1, "h")
        if dt_hours <= 0:
            continue

        rate = (vals[i] - vals[last_good_i]) / dt_hours

        if (rate > up_rate) or (rate < -down_rate):
            df.iloc[i, df.columns.get_loc(out_col)] = "FAIL"
        else:
            df.iloc[i, df.columns.get_loc(out_col)] = "PASS"
            last_good_i = i

    return df


def final_qc(df, qc_cols=("QC_gross","QC_consistency","QC_spike","QC_rate")):
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

def plottimeseriessmoothed(path, dates, site, raw, adjusted, smoothed):
    plt.rc('font', size=12)
    # # creating our plot using FigureCanvas to avoid consuming too much memory
    fig = Figure(figsize=(10,6))
    canvas = FigureCanvas(fig)
    ax = fig.add_subplot(1,1,1)
    ax.plot(dates, raw, color='blue', label='Raw')
    ax.plot(dates, adjusted, color = 'red', label='Raw_Interpolated')
    ax.plot(dates, smoothed, color='green', label='Applied 12hr Moving Mean')
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


START = "202603030600"
END = "202603042100"
WFO = "AJK"

# Set up the columns for your snotel dataframe
outputdict = {
    "STID": [],
    "Lat": [],
    "Lon": [],
    "Raw": [],
    "Filtered_Depth": [],
    "Smoothed_Depth": [],
    "SWE": [],
    "Precip": [],
    "ObType": [],
}
# new start and end times for smoothing the data
starttime, endtime = calcsnoteldaytimerange(START, END, DAYSBACK)
print('Now getting snotel data from %s to %s from mesowest' % (starttime, endtime))
# testing to see if our original start time is > 15 days back from the end time
calc_start = datetime.strptime(starttime, '%Y%m%d%H%M')
orig_start = datetime.strptime(START, '%Y%m%d%H%M')
if orig_start < calc_start:
    # downloading the data
    #rawdata = downloadSNOTELCWA(SNOTEL_URL, WFO, START, endtime, NETWORK, TOKEN)
    rawdata = downloadSNOTELCWA_dev(SNOTEL_URL, WFO, START, endtime, VARKEY, TOKEN)
else:
    # downloading the data
    #rawdata = downloadSNOTELCWA(SNOTEL_URL, WFO, starttime, endtime, NETWORK, TOKEN)
    rawdata = downloadSNOTELCWA_dev(SNOTEL_URL, WFO, starttime, endtime, VARKEY, TOKEN)
jsondata = parse_json(rawdata)

for site in jsondata["STATION"]:
    print(f"Site is: {site['STID']}")
    print(f"Network is: {site['MNET_ID']}")
    # checking for whether we have an automated snow depth or a manual one
    filter_check = check_avg_data_interval(site['OBSERVATIONS']['date_time'], site['OBSERVATIONS'][SC.VARS])
    #print(f"Ob times are: {site['OBSERVATIONS']['date_time']}")
    #print(f"Ob vals are: {site['OBSERVATIONS']['snow_depth_set_1']}")
    print(f"Should I filter? {filter_check}")
    # appending metadata
    outputdict['STID'].append(site['STID'])
    outputdict['Lat'].append(site['LATITUDE'])
    outputdict['Lon'].append(site['LONGITUDE'])
    outputdict['ObType'].append('SNOWDEPTH_SITE')
    datetimes = site['OBSERVATIONS']['date_time']
    dt_converted = [datetime.strptime(x, '%Y-%m-%dT%H:%M:%SZ') for x in datetimes]
    dates = pd.DataFrame(dt_converted, columns = ['DateTime'])
    #getting the snow depth and smoothing
    try:
        depth = site['OBSERVATIONS']['snow_depth_set_1']
        depthdf = pd.DataFrame(depth, columns = ['Raw'])
    except KeyError:
           depthdf = pd.DataFrame([], columns = ['Raw'])
    # concatenating the dataframes
    sitedf = pd.concat([dates, depthdf], axis=1)
    #applying filters if the filter check is True
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
        if site["STID"] == "JTMA2" or site["STID"] == "HMWA2":
            df_snow_depth.to_csv(f"{site['STID']}.csv")
        #plotting
        plottimeseriessmoothed(SC.GRAPHICSPATH, df_snow_depth.index, site["STID"], df_snow_depth["Raw"], df_snow_depth["raw_interp"], df_snow_depth["snowfall"])
        print(f"Done plotting snow depth data for {site['STID']}")
        






#These checks do a ‘decent’ job of smoothing the noisy snow depth time series.  The full QC lags the obs by ~6 hours.  

