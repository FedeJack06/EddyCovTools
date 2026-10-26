#!/usr/bin/python
# -*- coding: utf-8 -*-
import warnings
from typing import Tuple
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from .file_manager import toa5_to_df, get_files_pattern
from .config import InputFileConfig
import logging
logger = logging.getLogger(__name__)

'''
Scelte da conoscere
Bordi: uno spike a inizio o fine serie non ha un vicino su un lato, quindi resta NaN. Il paper non dice cosa fare, e la tua versione numpy lasciava il valore originale. Restare NaN mi sembra più coerente con “rimuovere lo spike”.
NaN preesistenti: se uno spike è adiacente a un buco, interpolate lo riempirebbe attraversando il buco. Il controllo only_spikes lo evita, e lo spike resta NaN.
Interpolazione per posizione: method="linear" ignora l’indice temporale, quindi equivale alla tua linear_interp. Se i timestamp avessero buchi, method="time" sarebbe più corretto, ma a 20 Hz continui non cambia nulla.
Conteggio: continua a contare i punti individuati, compresi quelli che restano NaN per i casi sopra.
Efficienza: l’interpolazione è vettoriale e costa poco rispetto alla rolling.
'''


def hor_wind_speed(u: float | pd.Series, 
                   v: float | pd.Series) -> float | pd.Series:
    """
    Calculate the horizontal wind speed

    Parameters
    ----------
    u: float | pd.Series
        first horizonatal wind component.
    v: float | pd.Series
        second horizonatal wind component.

    Returns
    -------
    float | pd.Series
        The horizontal wind speed.
    """
    return np.sqrt(u**2 + v**2)

def module_wind_speed(u: float | pd.Series, 
                      v: float | pd.Series, 
                      w: float | pd.Series) -> float | pd.Series:
    """
    Calculate the 3D wind speed.
    
    Parameters
    ----------
    u: float | pd.Series
        first horizonatal wind component.
    v: float | pd.Series
        second horizonatal wind component.
    w: float | pd.Series
        vertical wind component.
    
    Returns
    -------
    float | pd.Series
        The 3D wind speed.
    """
    return np.sqrt(u**2 + v**2 + w**2)

def true_wind_dir(u, 
                  v):
    """
    For sonic Gill Winmaster with V northward and U westward.
    Gives wind direction in degrees from North, clockwise

    Parameters
    ----------
    u: array_like
        westward components, u
    v: array_like
        northward components, v

    Returns
    -------
    np.array
        Clockwise wind direction respect to North in degrees
    """
    rad = np.arctan2(v, -u)
    return (np.degrees(rad)) % 360

def check_df(df: pd.DataFrame,
             sampling_rate_ms: float) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Find the time gaps in the dataframe index. The index must be a timestamp.
    Find the rows with at least one NAN values.
    Find the time duration of interval with consecutive NAN values.

    Parameters
    ----------
    df: pd.DataFrame
        Pandas dataframe to check
    sampling_rate_ms: float
        Expected dt in milliseconds between measure
    
    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
        - First Pandas df with the time gaps in seconds between records,
          greater than sampling rate
        - Second Pandas df with rows containing at least one NAN record.
        - Third Pandas df with info about interval of consecutive NAN values.
          Contains the start and end times of the intervals and the number
          of consecutive NAN measures, df ordered by number of consecutive NAN.
    """
    if not df.empty:
        # expected timedelta between rows
        dt = pd.to_timedelta(sampling_rate_ms, unit='ms')

        # Calc dt in milliseconds between rows in file
        delta_t = df.index.diff().total_seconds() * 1000
        # rows with gaps
        mask = delta_t > sampling_rate_ms

        # Append rows with time gaps to a list
        row_with_gaps = pd.DataFrame({
            "TIMESTAMP": df.index[mask],
            "dtSec": delta_t[mask].to_numpy()/1000
        })
            
        # Find rows with at least one NAN
        nan_df = df[df.isna().any(axis=1)]

        # Find the duration of intervals with consecutive NANs
        if nan_df.empty:
            duration_nan = pd.DataFrame(columns=['start', 'end', 'n_sample'])
        else:
            # difference between consecutvie index
            time_diff = nan_df.index.to_series().diff()
            # count consecutive gaps
            block = (time_diff != dt).cumsum()
            # group together same count (same gaps)
            duration_nan = df.groupby(block).apply(
                lambda x: pd.Series({
                    'start': x.index[0],
                    'end': x.index[-1],
                    'n_sample': len(x),
                })
            ).reset_index(drop=True)
            # for better visualization, at top longer interval
            duration_nan = duration_nan.sort_values('n_sample', ascending=False)
        return row_with_gaps, nan_df, duration_nan
    
    else:
        logger.warning("Empty dataframe passed to check_df.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
def fill_gaps_nan(df: pd.DataFrame,
                  sampling_rate_ms: float) -> pd.DataFrame:
    """
    Fill time gaps with NaN rows

    Parameters
    ----------
    df: pd.DataFrame 
        input dataframe
    sampling_rate_ms: float
        expected delta T in millisecond between two measures

    
    Returns
    -------
    pd.Dataframe
        Dataframe with complete index
    """
    timeDelta = pd.Timedelta(milliseconds=sampling_rate_ms)

    full_index = pd.date_range(
        start=df.index.min(),
        end=df.index.max(),
        freq=pd.tseries.frequencies.to_offset(timeDelta)
    )

    df_reindexed = df.reindex(full_index)
    df_reindexed.index.name = df.index.name
    return df_reindexed

def plausibility_filter(input_series: pd.Series,
                        lower_limit: float,
                        upper_limit: float,
                        ) -> Tuple[pd.Series, int]:
    """
    Replace values out of limits with NaN
    Values into [lower_limit, upper_limit] are retained (limits included).

    Parameters
    ----------
    input_series : pd.Series
        Input time series data, with a DatetimeIndex (optional)
    lower_limit: float
        Lower value to be retained
    upper_limit: float
        Higher value to be retained
    show_plot : bool, optional
        If True, displays a plot showing the original series, the dynamic bounds, 
        and the identified spikes. Default is False.

    Returns
    -------
    pd.Series
        The cleaned series.
    int
        The number of values removed.
    pd.Series
        The mask that identifies the out of range dots, for plotting functions
    """
    # define the mask to be retained
    mask_ok = (input_series >= lower_limit) & (input_series <= upper_limit)
    # replace values out of range with NaN
    out_series = input_series.where(mask_ok)

    # number of values out of range, exclude NaN already present
    n_out_of_range = (~mask_ok & input_series.notna()).sum()

    # out of range mask, for plotting red dot
    out_of_range = input_series[~mask_ok & input_series.notna()]

    return out_series, n_out_of_range, out_of_range

def plot_plausibility(input_series: pd.Series,
                      lower_limit: float,
                      upper_limit: float,
                      mask_oor: pd.Series,
                      save_path: str | Path = None):
    """Visualize plausibility filter apply temporal series""" 
    plt.figure(figsize=(14, 6))
    
    # input series in grey
    plt.plot(input_series.index, input_series, label='Input series', color='black', alpha=0.5, linewidth=1)
    
    # tolerance band
    plt.fill_between(input_series.index, lower_limit, upper_limit, color='blue', alpha=0.1, label='Plausibility range')
    
    plt.ylim([input_series.min()-abs(input_series.min())*0.05, input_series.max()+abs(input_series.max())*0.05])
    
    plt.scatter(mask_oor.index, mask_oor, color='red', label='out of range', zorder=5, s=20)
    
    plt.title(f'{input_series.name} - Out of range detected: {mask_oor.values.sum()}', fontsize=14)
    plt.xlabel('Timestamp', fontsize=12)
    plt.ylabel(f'{input_series.name}', fontsize=12)
    plt.legend(loc='best')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    if save_path != None:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close('all')
    else:
        plt.show()

def plot_despiking(input_series: pd.Series,
                   lower_bound: float,
                   upper_bound: float,
                   despiked_series: pd.Series,
                   spike_mask: pd.Series,
                   save_path: str | Path = None):
    plt.figure(figsize=(14, 6))
    
    # input series in grey
    plt.plot(input_series.index, input_series, label='Input series', color='black', alpha=0.5, linewidth=1)
    
    # tolerance band
    plt.fill_between(input_series.index, lower_bound, upper_bound, color='blue', alpha=0.1, label='Tolerance band')
    
    # despiked series in blue
    plt.plot(despiked_series.index, despiked_series, label='Despiked series', color='blue', linewidth=0.3)
    
    # spikes red dot
    spikes_only = input_series[spike_mask]
    plt.scatter(spikes_only.index, spikes_only, color='red', label='Spike value', zorder=5, s=20)
    
    plt.title(f'{input_series.name} - Robust despike (Spike removed: {spike_mask.values.sum()})', fontsize=14)
    plt.xlabel('Timestamp', fontsize=12)
    plt.ylabel(f'{input_series.name}', fontsize=12)
    plt.legend(loc='best')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    if save_path != None:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close('all')
    else:
        plt.show()

def despiking_series_robust(input_series: pd.Series, 
                            robust_std_dev: float, 
                            n_window_points: int,
                            max_consecutive_spikes: int,
                            show_plot: bool = False) -> Tuple[pd.Series, int]:
    """
    Applies a moving-window robust despiking algorithm directly to a pandas Series.
    If a record exceeds N times the robust standard deviation, it's marked as spike.
    Only consecutive values out of range shorter or equal max_consecutive_spikes
    ere removed and considered spikes.
    
    Detected spikes are replaced with NaN. 

    Parameters
    ----------
    input_series : pd.Series
        Input time series data with a DatetimeIndex.
    robust_std_dev : float
        Threshold multiplier for the robust standard deviation.
    n_window_points : int
        Number of periods for the rolling window.
    max_consecutive_spikes: int
        Are considered spikes only a number of consecutive values less or equal.
        Consecutive values out of bounds longer than this parameters are retained.
    show_plot : bool, optional
        If True, displays a plot showing the original series, the dynamic bounds, 
        and the identified spikes. Default is False.

    Returns
    -------
    pd.Series
        The despiked series.
    int
        The number of spikes removed.
    """
    # check
    if not isinstance(input_series, pd.Series):
        raise TypeError("Input must be a pandas Series.")
    if robust_std_dev <= 0:
        raise ValueError("Number of standard dev must be a positive number.")
    if not isinstance(n_window_points, int) or n_window_points <= 0:
        raise ValueError("n_window_points must be a positive integer.")
    if n_window_points % 2 == 0:
        warnings.warn("It is recommended to use odd number of point in window.")

    timeseries = input_series.copy()

    # rolling window
    roll = timeseries.rolling(window=n_window_points, center=True, min_periods=1)
    
    running_median = roll.median()
    p84 = roll.quantile(0.84)
    p16 = roll.quantile(0.16)
    
    # robust standard deviation
    running_std_robust = 0.5 * (p84 - p16)

    # spike if max between 0.5 (when low variation) and robust std dev
    delta = np.maximum(robust_std_dev * running_std_robust, 0.5)

    upper_bound = running_median + delta
    lower_bound = running_median - delta

    # mask of spikes 
    spike_mask = (timeseries > upper_bound) | (timeseries < lower_bound)
    #count_spike = int(spike_mask.sum())

    # find consecutive spike groups
    spike_groups = (spike_mask != spike_mask.shift()).cumsum()
    spike_group_size = spike_mask.groupby(spike_groups).transform('sum')

    # keep spikes that are part of a consecutive run longer than max allowed
    keep_mask = spike_mask & (spike_group_size > max_consecutive_spikes)

    # spikes to replace with NaN
    final_spike_mask = spike_mask & ~keep_mask

    count_spike = int(final_spike_mask.sum())

    # Visualize spikes and temporal series
    if show_plot:
        plt.figure(figsize=(14, 6))
        
        # input series in grey
        plt.plot(input_series.index, input_series, label='Input series', color='black', alpha=0.5, linewidth=1)
        
        # tolerance band
        plt.fill_between(input_series.index, lower_bound, upper_bound, color='blue', alpha=0.1, label='Tolerance band')
        
        # despiked series in blue
        plt.plot(timeseries.index, timeseries.where(~final_spike_mask, running_median), label='Despiked series', color='blue', linewidth=0.3)
        
        # spikes red dot
        spikes_only = input_series[final_spike_mask]
        plt.scatter(spikes_only.index, spikes_only, color='red', label='Spike value', zorder=5, s=20)
        
        plt.title(f'Robust despike (Spike removed: {count_spike})', fontsize=14)
        plt.xlabel('Timestamp', fontsize=12)
        plt.ylabel('Value', fontsize=12)
        plt.legend(loc='best')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()
        plt.show()

    # Replace bad data with the local median using .loc
    #timeseries.loc[spike_mask] = running_median.loc[spike_mask]

    #timeseries.loc[spike_mask] = np.nan
    timeseries[final_spike_mask] = np.nan

    return timeseries, count_spike

def interpolate_lin(df: pd.DataFrame,
                    limit: int) -> pd.DataFrame:
    """
    Linear interpolation on all df column.
    Only fill NaNs surrounded by valid values (interpolate).
    Limit set the maximum number of values to add during interpolation.
    If there is 20 consecutive NaN and limit = 4, only 8 values are added,
    4 starting from the far right of the range and 4 starting from the far left.

    Parameters
    ----------
    df: dp.Dataframe
        dataframe to interpolate
    limit: int
        Maximum number of consecutive NaNs to fill. Must be greater than 0.
    """
    df = df.interpolate(method='linear', limit=limit, limit_area='inside', limit_direction='both')
    return df

def interpolate_3pol(df: pd.DataFrame,
                     limit: int) -> pd.DataFrame:
    """
    Interpolate all df column with third-degree polynomial.
    Both interpolation and extrapolation are performed.
    Limit set the maximum number of values to add during interpolation.
    If there is 20 consecutive NaN and limit = 4, only 8 values are added,
    4 starting from the far right of the range and 4 starting from the far left.

    Parameters
    ----------
    df: dp.Dataframe
        dataframe to interpolate
    limit: int
        Maximum number of consecutive NaNs to fill. Must be greater than 0.
    """
    df = df.interpolate(method='spline', order=3, limit=limit, limit_direction='both')
    return df

def check_TOA5(input_dir : str | Path,
               pattern: str,
               config: InputFileConfig,
               out_file : bool = False) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Check number of NAN in raw converted TOA5 file and time gaps between rows.
    Usefull to check the status of incoming file from Station direclty on the server.

    Parameters
    ----------
    input_dir: str
        path to directory containing all TOA5 from Stations.
    pattern: str
        Wildcard pattern name of the files (e.g. S*.dat)
    config: InputFileConfig
        Object with all the info about the columns to be imported.
        Contains the correct sampling rate for this type of files.
    out_file: bool
        create CSV file with NAN rows and time gaps info. Defaulf False.

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame]
        - First pandas Dataframe with all the time gaps found into the file.
        - Second pandas Dataframe with all rows containing at least one NAN record.
    """
    # list of dataframe
    df_gaps_list = []
    df_nan_list = []

    # get all file order by AZ
    files = get_files_pattern(input_dir, pattern)

    # get dt for this type of files
    sampling_rate = config.sampling_rate_ms

    # last row from previous file
    last_row_prev_file = None
    last_file = None

    for file in files:
        try:
            df, meta = toa5_to_df(input_file=file, config=config, date_index=True)

            if df.empty:
                logger.warning("Analyzing %s: empty file, skipping...", file.name)
                continue
            
            # Comparison between last timestamp in previous file and first timestamp of current file
            if last_row_prev_file is not None:
                ts_prev = last_row_prev_file.index[0]
                ts_first = df.index[0]

                # calc delta t
                if pd.notna(ts_prev) and pd.notna(ts_first):
                    dt_ms = (ts_first - ts_prev).total_seconds() * 1000 #dt in ms between files
                    if dt_ms > sampling_rate: # gap found
                        logger.info(f"Time gap found between {last_file.name} and {file.name}: dt = {dt_ms/1000:.2f} s")
                        #append gap info to a list
                        row = pd.DataFrame({
                            "file": [f"{last_file.name} → {file.name}"],
                            "dtSec": [dt_ms / 1000]
                        })
                        df_gaps_list.append(row)
                else:
                    logger.error("Analyzing %s: Missing timestamp between consecutive files", file.name)
            
            # Calc dt in milliseconds between rows in file
            delta_t = df.index.diff().total_seconds() * 1000
            
            # Find index with dt > threshold
            time_gaps_index = delta_t[delta_t > sampling_rate]

            # Append rows with time gaps to a list
            if len(time_gaps_index) > 0:
                row_with_gaps = pd.DataFrame({
                            "file": [file.name],
                            "dtSec": delta_t[delta_t > sampling_rate].to_numpy()/1000,
                            "TIMESTAMP": df.index[delta_t > sampling_rate]
                        })
                df_gaps_list.append(row_with_gaps)
                logger.info("Analyzing %s: Found %d rows with delta t > %.1f ms", file.name, len(row_with_gaps), sampling_rate)
            
            # Find rows with at least one NAN
            nan_df = df[df.eq('NAN').any(axis=1)]
            if len(nan_df) > 0:
                df_nan_list.append(nan_df)

            # Update values for next comparison between consecutive files
            last_row_prev_file = df.iloc[[-1]]
            last_file = file

        except Exception as e:
            logger.error("Analyzing %s Error: %s", file.name, e)

    # Output of the results
    info = meta[0].strip().split('","')
    # Build df
    if df_gaps_list:
        df_gaps = pd.concat(df_gaps_list, ignore_index=True)
        logger.info("%s", '='*60)
        logger.info("TOTAL: %d rows with delta t > %.1f ms (include gaps between files)", len(df_gaps), sampling_rate)
        logger.info("%s\n", '='*60)
        logger.info(df_gaps)
        # result in a file named time_gaps
        if out_file:
            out_path = input_dir / Path(f'time_gaps_{info[1]}_{info[7][:-1]}.csv')
            df_gaps.to_csv(out_path, index=False)
    else:
        logger.info('='*60)
        logger.info("No time gaps found.")
        logger.info("%s\n", '='*60)
        df_gaps = pd.DataFrame()

    if df_nan_list:
        df_nan = pd.concat(df_nan_list, ignore_index=True)
        logger.info("="*60)
        logger.info("TOTAL: %d rows with NAN values", {len(df_nan)})
        logger.info("="*60 + "\n")
        logger.info(df_nan)
        # result in a file named nan_
        if out_file:
            out_path = input_dir / Path(f'nan_{info[1]}_{info[7][:-1]}.csv')
            df_nan.to_csv(out_path, index=False)
    else:
        logger.info("="*60)
        logger.info("No NAN values found")
        logger.info("="*60 + "\n")
        df_nan = pd.DataFrame()

    return df_gaps, df_nan

###################################################### VM 97

def running_bounds(input_series: pd.Series,
                   n_std: float,
                   n_window_points: int) -> Tuple[pd.Series, pd.Series]:
    """Lower/upper bounds: centered running mean -/+ n_std * running std (ddof=0, NaN ignored)."""
    # rolling window
    roll = input_series.rolling(window=n_window_points, 
                                center=True, 
                                min_periods=1)
    mean = roll.mean() # mean in each window
    delta = n_std * roll.std(ddof=0) # n * std dev in each window
    return mean - delta, mean + delta


def keep_only_spikes(mask: pd.Series, 
                     max_length: int) -> pd.Series:
    """
    Keep True only for runs of consecutive True with length <= max_length.
    
    Parameters
    ----------
    mask: pd.Series
        mask of out of bound values of the series
    max_length: int
        max number of consecutive values out of bounds to be considered 
        spikes, so interpolated or replaced with NaN.
    """
    # shifted series with False at top
    shifted = mask.shift(periods=1, fill_value=False)
    # find consecutive spike groups, True where there is a True/False change
    # count the number of True at each position, block of T or F have same value
    run_id = mask.ne(shifted).cumsum() 
    # size of the block of consecutive True of False
    run_length = mask.groupby(run_id).transform("size")
    # a new mask: true for blocks of True with len <= max length
    true_spikes = mask & (run_length <= max_length)
    return true_spikes

def detect_spikes(input_series: pd.Series,
                  n_std: float,
                  n_window_points: int,
                  max_consecutive_spikes: int) -> pd.Series:
    """One Vickers & Mahrt pass: boolean mask of spikes.
    
    Returns
    -------
    pd.Series
        A mask that identifies the spikes of the input_series.
    """
    # limit for each value in input_series
    lower, upper = running_bounds(input_series, n_std, n_window_points)
    # mask: True where value is out of bounds
    out_of_bounds = (input_series > upper) | (input_series < lower)
    # filter only true spikes (consecutive values out of bound)
    spike_mask = keep_only_spikes(out_of_bounds, max_consecutive_spikes)
    return spike_mask, lower, upper

def interpolate_spikes(input_series: pd.Series, 
                       spikes_mask: pd.Series) -> pd.Series:
    """
    Replace spike points with linear interpolation between the nearest valid
    neighbours. A spike is left as NaN when it cannot be interpolated:
    at the series borders, or when it touches a pre-existing NaN.

    Parameters
    ----------
    input_series: pd.Series
        The input Pandas Series to despike
    spikes_mask: pd.Series
        The mask that identifies the spikes
    """
    # Replace spikes in input_series with NaN 
    masked = input_series.mask(spikes_mask)
    # lin interp only between two values
    interp = masked.interpolate(method="linear", limit_area="inside")

    # a gap is fillable only if made entirely of spikes
    # mask: all NaNs of the input (spike + pre-existing nan)
    gap = masked.isna()
    # one id for each consec NaN block
    gap_id = gap.ne(gap.shift(fill_value=False)).cumsum()
    # only gap made with only spikes
    only_spikes = spikes_mask.groupby(gap_id).transform("all")
    # interpolate only spikes without adjacent NaN
    mask_fill = spikes_mask & only_spikes

    # if spikes with adiacent NaN -> not interpolate
    interp_series = masked.where(~mask_fill, interp)
    return interp_series

def despiking_VM97(input_series: pd.Series,
                   n_window_points: int,
                   n_std: float = 3.5,
                   max_consecutive_spikes: int = 3,
                   max_iterations: int = 10,
                   n_std_increment: float = 0.1,
                   interpolate: bool = False,
                   save_path: str | Path = None) -> Tuple[pd.Series, int, int]:
    """
    Despiking after Vickers & Mahrt (1997). Spikes are replaced with NaN.
    Returns the despiked series and the total number of spike points.

    Applies the despiking algorithm based on Vickers and Mahrt (1997) to remove spikes from a time series.
    
    This method identifies and replaces spikes in the input Series by comparing values against a running
    mean and standard deviation computed over a moving window. Points lying beyond a threshold defined
    by `n_std` times the local standard deviation from the local mean are considered spikes. Spikes are 
    replaced using interpolation if their number is below `max_consecutive_spikes`.
    
    The `n_std` factor is incrementally increased after each iteration.
    The process stops when no more spikes are detected or when `max_iterations` is reached.
    
    Parameters
    ----------
    input_series : np.ndarray
        The input Pandas Series containing the signal to be despiked.
    n_window_points : int
        Length of the moving window used to compute running statistics.
    n_std : float
        Initial threshold multiplier for the standard deviation used to detect spikes.
    max_consecutive_spikes : int
        Maximum number of consecutive values out of bounds considered spikes,
        so they are interpolated or replaced with NaN.
    max_iterations : int
        Maximum number of iterations to perform if spikes continue to be found.
    n_std_increment: float
        At the end of each interation, the `n_std` factor has increased by `n_std_increment`.
    interpolate: bool = False
        If False (default), the spikes points are replaced with NaNs,
        if True they are interpolated only if there are adjacent values.

    Returns
    -------

    """
    if not isinstance(input_series, pd.Series):
        raise TypeError("Input must be a pandas Series.")
    if not isinstance(n_window_points, int) or n_window_points <= 0:
        raise ValueError("n_window_points must be a positive integer.")
    if n_std <= 0:
        raise ValueError("n_std must be positive.")
    if not isinstance(max_consecutive_spikes, int) or max_consecutive_spikes <= 0:
        raise ValueError("max_consecutive_spikes must be a positive integer.")
    if not isinstance(max_iterations, int) or max_iterations <= 0:
        raise ValueError("max_iterations must be a positive integer.")
    if n_window_points % 2 == 0:
        warnings.warn("n_window_points is even: the window is asymmetric.", UserWarning)

    timeseries = input_series.copy()
    total_spikes = 0
    iter_perf = 0

    for i in range(max_iterations):
        iter_perf = i + 1
        current_std = n_std + i * n_std_increment
        # find the spikes in the timeseries
        spikes_mask, lower, upper = detect_spikes(timeseries, 
                               current_std,
                               n_window_points, 
                               max_consecutive_spikes)
        # number of point considered spikes
        n_new = int(spikes_mask.sum())
        logger.info("iteration %d: %d spikes identified.", i, n_new)
        # if no more spikes found, end the despiking
        if n_new == 0:
            break
        # replace spikes with nan or interpolate the gap
        timeseries = interpolate_spikes(timeseries, spikes_mask) if interpolate else timeseries.mask(spikes_mask)
        total_spikes += n_new
        if save_path != None:
            plot_despiking(input_series, lower, upper, timeseries, spikes_mask, save_path / f"desp_{input_series.name}_iter_{i}")

    return timeseries, total_spikes, iter_perf

####################### original function

def running_stats(array: np.ndarray, 
                  window_length: int
                  ) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute the running (moving) mean and standard deviation of a 1D array using a sliding window.

    This function uses a centered sliding window of fixed length to calculate
    the mean and standard deviation at each point in the input array. The array
    is padded at the edges to allow computation at the boundaries.

    Parameters
    ----------
    array : np.ndarray
        Input 1D array of numerical values.
    window_length : int
        Number of points within the sliding window. Must be a positive odd integer less than or equal to the array length.

    Returns
    -------
    running_mean : np.ndarray
        Array of the same length as the input, containing the running mean.
    running_std : np.ndarray
        Array of the same length as the input, containing the running standard deviation.

    Raises
    ------
    ValueError
        If `window_length` is not a positive integer.
        If `window_length` is greater than the length of the input array.

    Warns
    -----
    UserWarning
        If `window_length` is even, a warning is issued that using an even-length window may result in asymmetric behavior.

    Notes
    -----
    - The function pads the input array using constant values equals to the edge values of the array.
    - If the input contains NaNs, they are ignored in the mean and std computation using `np.nanmean` and `np.nanstd`.
    """
    # --- Input validation ---
    if not isinstance(window_length, int) or window_length <= 0:
        raise ValueError("window_length must be a positive integer.")
    if window_length > len(array):
        raise ValueError("window_length must not be greater than the length of the array.")
    if window_length % 2 == 0:
        warnings.warn(
            "window_length is even; using an even-length window may result in asymmetric behavior.",
            UserWarning)

    # --- Initialization ---
    if not isinstance(window_length, int) or window_length <= 0:
        raise ValueError("window_length must be a positive integer.")
    if window_length > len(array):
        raise ValueError("window_length must not be greater than the length of the array.")
    if window_length % 2 == 0:
        warnings.warn(
            "window_length is even; using an even-length window may result in asymmetric behavior.",
            UserWarning)

    # --- Initialization ---
    N = len(array)
    half_window = window_length // 2

    # Pad the array to handle edge
    # The padding replicates the boundary values of the array
    padded_array = np.pad(array, (half_window, half_window), mode='edge')

    running_mean = np.full(N, np.nan)
    running_std = np.full(N, np.nan)

    # --- Running statistics calculation ---
    for i in range(N):
        # Define the window centered around index 'i'
        window = padded_array[i:i + window_length]
        
        # Calculate the running mean and standard deviation for the current window, ignoring NaN values
        running_mean[i] = np.nanmean(window)
        running_std[i] = np.nanstd(window)

    return running_mean, running_std

def linear_interp(left_value : float,
                  right_value : float,
                  length : int
                  ) -> np.ndarray:
    """
    Performs linear interpolation between `left_value` and `right_value`, 
    returning a NumPy array of length `length` whose elements represent 
    evenly spaced values between the two endpoints.
    
    Parameters
    ----------
    left_value : float
        The reference value on the left border.
    right_value : float
        The reference value on the right border.
    length : int
        The length of the array to perform the interpolation over.
    
    Returns
    -------
    interpolated_values : np.ndarray
        An array containing the interpolated values.
    
    Raises
    ------
    ValueError
        If `length` is not a positive integer.

    """
    # --- Input validation ---
    if not isinstance(length, int) or length <= 0:
        raise ValueError("`length` must be a positive integer.")

    # Create an array of relative indices
    x = np.arange(1, length + 1)
    
    # Compute the interpolation
    interpolated_values = left_value + (x / (length + 1)) * (right_value - left_value)
    
    return interpolated_values

def identify_interp_spikes(array : np.ndarray,
                           mask : np.ndarray,
                           max_length_spike : int
                           ) -> tuple[np.ndarray, int]:
    """
    Identifies and interpolates spikes in the provided `array` based on the given mask.
    
    A spike is defined as a sequence of consecutive True values in the mask that is shorter than or equal to
    the specified maximum length (`max_length_spike`). The function applies linear interpolation to replace 
    the spike values with interpolated ones by calling `core.linear_interp()`. If the spike is at the boundary 
    of the array (either at the start or at the end), interpolation is not performed.

    Parameters
    ----------
    array : np.ndarray
        The 1D array containing the data to be processed.
    mask : np.ndarray
        A boolean mask where True values indicate potential spikes.
    max_length_spike : int
        The maximum length of consecutive True values in the mask to be considered a spike.

    Returns
    -------
    array : np.ndarray
        The modified array with interpolated spike values
    count_spike : int
        The total count of detected spikes.
    
    Raises
    ------
    ValueError
        If `array` and `mask` do not have the same length.
    ValueError
        If `mask` is not a boolean array.
    ValueError
        If `max_length_spike` is not a positive integer.

    Notes
    -----
    - If either the left or right neighbor is missing (i.e., the spike is at
      the boundary), the spike is not interpolated.
    - Only sequences of True values that are smaller than or equal to `max_length_spike` are considered spikes.
    """

     # --- Input validation ---
    if len(array) != len(mask):
        raise ValueError("`array` and `mask` must have the same length.")
    if mask.dtype != bool:
        raise ValueError("`mask` must be a boolean array.")
    if not isinstance(max_length_spike, int) or max_length_spike <= 0:
        raise ValueError("`max_length_spike` must be a positive integer.")

    # --- Spike detection and interpolation ---
    flag = False  # Flag to track the beginning of a spike sequence
    count_spike = 0  # Counter to keep track of the total number of spikes detected
    count_points = 0  # Counter for the total number of individual spike points

    # Loop through the array to check each element
    for i in range(len(array)):
        # Check if the mask indicates a True value at index i
        if mask[i]:
            # If flag is False, it's the first time encountering a True value in the mask
            if flag == False:
                spike_indices = [i]  # Save the index of the first True value
                flag = True  # Set the flag to True indicating a spike sequence has started
            else:
                # If the flag is True, append the index of consecutive True values
                spike_indices.append(i)
        else:
            # If the current mask value is False and a spike sequence was detected (flag is True)
            if flag == True:
                # Count the length of the detected spike sequence
                length_spike = len(spike_indices)
                # If the sequence is shorter than or equal to the max allowed spike length, treat it as a spike
                if length_spike <= max_length_spike:
                    # Check if interpolation is possible (the spike is not at the border of the array)
                    if spike_indices[0] > 0 and spike_indices[-1] < len(array) - 1:
                        # Retrieve the neighboring values for interpolation
                        left_value = array[spike_indices[0] - 1]
                        right_value = array[spike_indices[-1] + 1]
                        # Perform linear interpolation to smooth the spike
                        array[spike_indices] = linear_interp(left_value, right_value, length_spike)
                        # Increment the spike count
                        count_spike += 1
                        count_points += length_spike  # <-- Aggiunge il numero di punti di questa spike
                # Reset the flag and clean up the temporary variables
                flag = False
                del spike_indices  # Delete the spike indices list to free memory

    return array, count_spike, count_points

def o_despiking_VM97(array_to_despike : np.ndarray,
                   c : float,
                   window_length : int,
                   max_consecutive_spikes : int,
                   max_iterations : int
                   ) -> np.ndarray:
    """
    Applies the despiking algorithm based on Vickers and Mahrt (1997) to remove spikes from a time series.

    This method identifies and replaces spikes in the input array by comparing values against a running
    mean and standard deviation computed over a moving window. Points lying beyond a threshold defined
    by `c` times the local standard deviation from the local mean are considered spikes. Spikes are 
    replaced using interpolation if their number is below `max_consecutive_spikes`.

    The `c` factor is incrementally increased after each iteration.
    The process stops when no more spikes are detected or when `max_iterations` is reached.

    The function calls `pre_processing.identify_inter_spikes()` and `core.running_stats()` functions.

    Parameters
    ----------
    array_to_despike : np.ndarray
        The input 1D array containing the signal to be despiked.
    c : float
        Initial threshold multiplier for the standard deviation used to detect spikes.
    window_length : int
        Length of the moving window used to compute running statistics.
    max_consecutive_spikes : int
        Maximum number of consecutive spike points allowed for interpolation.
    max_iterations : int
        Maximum number of iterations to perform if spikes continue to be found.
    logger : Optional[logging.Logger], default=None
        A logger instance following the `logging.Logger` interface. If provided, the function will use it to
        log dialogues during the despiking procedure. If set to `None`, the function will operate
        silently without producing any log output.
    
    Returns
    -------
    array_despiked : np.ndarray
        The despiked version of the input array.
    
    Raises
    ------
    ValueError
        If `c` is not a positive number.
    ValueError
        If `window_length` is not a positive integer.
    ValueError
        If `max_consecutive_spikes` is not a positive integer.
    ValueError
        If `max_iterations` is not a positive integer.
    ValueError
        If `logger` is not a logging.Logger instance or None.
    
    References
    ----------
    Vickers, D., & Mahrt, L. (1997). Quality control and flux sampling problems for tower and aircraft data.
    Journal of Atmospheric and Oceanic Technology, 14(3), 512–526. https://doi.org/10.1175/1520-0426(1997)014<0512:QCAFSP>2.0.CO;2
    """
    
    # --- Input validation ---
    if not (isinstance(c, (int, float)) and c > 0):
        raise ValueError("`c` must be a positive number.")
    if not isinstance(window_length, int) or window_length <= 0:
        raise ValueError("`window_length` must be a positive integer.")
    if not isinstance(max_consecutive_spikes, int) or max_consecutive_spikes <= 0:
        raise ValueError("`max_consecutive_spikes` must be a positive integer.")
    if not isinstance(max_iterations, int) or max_iterations <= 0:
        raise ValueError("`max_iterations` must be a positive integer.")
    
    # --- Despiking process ---
    iteration = 0  # Counter for the number of iterations in the despiking process
    c_increment = 0.1  # Increment value for adjusting the bounds in each iteration
    current_c = c  # Initial multiplier for the standard deviation (controls the bounds)
    array_despiked = array_to_despike.copy()  # Copy of the original array to be despiked
    count_spike = 1  # Initial value greater than 0 to start the despiking cycle
    total_points = 0

    # The loop continues until no more spikes are detected or the maximum number of iterations is reached
    max_iterations = max_iterations - 1  # Adjust for zero-based counting
    while count_spike != 0 and iteration <= max_iterations:
        # Calculate the running mean and standard deviation for the current array
        running_mean, running_std = running_stats(array_despiked, window_length)

        # Define the upper and lower bounds based on the running statistics and current multiplier (current_c)
        upper_bound = running_mean + current_c * running_std
        lower_bound = running_mean - current_c * running_std

        # Create a mask to detect values beyond the defined bounds
        beyond_bounds_mask = (array_despiked > upper_bound) | (array_despiked < lower_bound)

        # Identify and interpolate values that are beyond the bounds and respect max_length criterion (spikes)
        array_despiked, count_spike, count_points = identify_interp_spikes(array_despiked, beyond_bounds_mask, max_consecutive_spikes)
        total_points += count_points
        
        # Log the progress if the logger is enabled
        logger.info(
            f"Iteration: {iteration}, identified and removed spikes (groups): {count_spike}, "
            f"individual points: {count_points} (total points so far: {total_points})"
        )
        

        # Increase the multiplier for the next iteration to make the bounds wider
        current_c += c_increment
        iteration += 1  # Increment the iteration counter

    return array_despiked, total_points
