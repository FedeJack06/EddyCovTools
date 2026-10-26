#!/usr/bin/python
# -*- coding: utf-8 -*-
from pathlib import Path
import pandas as pd
from typing import List, Dict, Tuple
from natsort import natsorted
from .config import InputFileConfig, StationConfig
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def toa5_to_df(input_file : str | Path,
               config: InputFileConfig,
               date_index: bool = False) -> Tuple[pd.DataFrame, List[str]]:
    """
    Import a TOA5 Campbell file into a Pandas Dataframe.
    TOA5 should have the datetime column named "TIMESTAMP", important only
    if you chose to set the datetime column as index.
    The output dataframe has all the columns and types specified in the
    InputFileConfig passed. Be sure you have set the config right.
    The name of the columns in the dataframe are the same of the files.

    Parameters
    ----------
    input_file: str | Path
        path of TOA5 file
    config: InputFileConfig
        configuration file input, with all the info about the 
        columns to be imported.
    date_index: bool
        If true sets the datetime column ("TIMESTAMP") as index and
        removes it from df columns. Default False, so keeps the 
        default numeric df index.

    Returns
    -------
    Tuple[pd.DataFrame, List[str]]
        - The file as a dataframe.
        - List of strings containing the original 4 header lines.
    """
    #if string, convert to Path object
    input_file = Path(input_file)

    #extract 4 line header from file
    raw_header = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for _ in range(4):
            raw_header.append(f.readline())

    #get pandas dtype for each column from the config object
    types = config.get_file_cols_type()
    #toa5 file to pandas 
    df = pd.read_csv(input_file, sep=",", header=1, skiprows=[2, 3], dtype="string")
    #remove column not specified in the input files configuration
    df = df.filter(items=config.get_file_cols_name())
    #convert the column dtypes to dtypes specified in the config
    df = df.astype(dtype=types, errors='raise')

    #set datetime column as index
    if date_index:
        #column_name_date = df.dtypes[df.dtypes == 'datetime64[ms]'].index[0]
        df.set_index("TIMESTAMP", inplace=True)
        df.drop(columns=["TIMESTAMP"], inplace=True, errors='ignore')

    return df, raw_header

def csv_to_df(input_file : str | Path,
               config: InputFileConfig,
               index: str = None) -> pd.DataFrame:
    """
    Import a generic csv file into a Pandas Dataframe.
    The input file must have the first row containing the name of
    th columns.
    The output dataframe has all the columns and types specified in the
    InputFileConfig passed. Be sure you have set the config right.
    The name of the columns in the dataframe are the same of the files.
    You can specify the column to set as dataframe index.

    Parameters
    ----------
    input_file: str | Path
        path of csv file
    config: InputFileConfig
        configuration file input, with all the info about the 
        columns to be inported.
    index: str
        The name of the column to set as dataframe index.
        This column will be removed from the columns of the dataframe.
        Default None, so keeps the default numeric index.

    Returns
    -------
    pd.DataFrame
        Dataframe containing the columns choosen in InputConfigFile.
    """
    #if string, convert to Path object
    input_file = Path(input_file)

    #get pandas dtype for each column from the config object
    types = config.get_file_cols_type()

    df = pd.read_csv(input_file, sep=",", header=0, dtype="string")
    #remove column not specified in the input files configuration
    df = df.filter(items=config.get_file_cols_name())
    #convert the column dtypes to dtypes specified in the config
    df = df.astype(dtype=types, errors='raise')

    #set datetime column as index
    if index:
        #column_name_date = df.dtypes[df.dtypes == 'datetime64[ms]'].index[0]
        df.set_index(index, inplace=True)
        df.drop(columns=[index], inplace=True, errors='ignore')

    return df

def get_files_pattern(folder_path: str | Path,
                      pattern: str,
                      sorted: bool = False) -> List[Path]:
    """
    Get a list of files from a folder matching a wildcard pattern.
    You can use "*" to substitute any char.
    The search is CASE-SENSITIVE.

    Parameters
    ----------
    folder_path: str or Path
        Search is performed in this path.
    pattern: str
        Wildcard pattern to match (e.g., 'TOA5py_Sonic*.dat').
    sorted: bool = False
        If true return a sorted list of files using natsort library

    Returns
    -------
    List[Path]
        A list of the selected files as pathlib.Path objects.
    """
    #if string, convert to Path object
    folder = Path(folder_path)
    
    if not folder.exists() or not folder.is_dir():
        raise NotADirectoryError(f"Folder {folder} not found or is not a directory.")

    # Find only files, based on a wildcard pattern
    # sorted based on filename
    if sorted:
        files = natsorted([f for f in folder.glob(pattern) if f.is_file()], 
                        key=lambda f: f.name)
    else:
        files = [f for f in folder.glob(pattern) if f.is_file()]
    
    logger.info(f"Found {len(files)} files matching '{pattern}' in {folder}.")
    return files

def get_files_from_station(folder_path: str | Path, 
                           station: StationConfig,
                           configs: List[str] = None) -> Dict[str, List[Path]]:
    """
    Gets all the input files related to one station. One search is performed
    for every InputFileConfig object in the configs list.
    Returns a dictionary, with a list of files for each 
    InputFileConfig of the station selected.
    The files are returned as a Path object.

    Parameters
    ----------
    folder_path: str
        Serach is perfomed in this path.
    station: StationConfig
        Station object conaining all the input file configuration.
        Only files related to config_id selected are searched.
        Only files containing the "input_files_name" in the filename are selected.
        Serch string case-insensitive and result not sorted
    configs: List[str] = None
        The id of the configuretion to be imported.
        Default is None: get files from all config in the station

    Returns
    ----------
    Dict[str, List[Path]]
        Return a dictionary of list of files. 
        Key is the config ID, value is a list of files Path object.

    """
    if not isinstance(station, StationConfig):
        raise TypeError("station must be an instance of StationConfig dataclass")
    
    #dictionary: key is the config_id, value is the related list of files
    dict_files = {}

    # if no config id passed, seach files for all configs object in the station
    keys = configs if configs is not None else station.input_files_name.keys()

    for config_id in keys:
        substring = station.get_input_file_name(config_id)
        #get the list of files of the same type (the same input config)
        list_of_file = get_files_pattern(folder_path=folder_path, pattern=substring)
        #output
        dict_files[config_id] = list_of_file

    return dict_files

