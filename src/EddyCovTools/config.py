#!/usr/bin/python
# -*- coding: utf-8 -*-

from dataclasses import dataclass, field
from typing import Dict, Tuple, List

@dataclass
class InputFileConfig:
    """
    Configuration parameters for importing data from one type of files. 
    This class contains the structure of the input file and the related database table.
    The input file must contain data arranged in columns.
    Use this class to put in relation a column in the input file 
    with the correspondingcolumn in the database table.
    The file is imported in a Pandas dataframe, then the dataframe is imported 
    in a database table.

    If you want to import a column from a file, you have to insert: 
    * the column info as a new entry in the dictionary named cols
        1) Set the name of the column of the input file, it will be the same in the Pandas
        dataframe related to the file (dictionary key)
        2) Set the Pandas type the column should have in the dataframe (first tuple entry)
        3) Set name the column should have in the database table (second tuple entry)
        4) Set column SQL type the column should have in the database table (third tuple entry)

    .. code-block:: python
        cols = {
            "col_A": (int, "db_col_A", "INTEGER"),
            "col_B": (float, "db_col_B", "DECIMAL(5,2)")
        }

    * the time interval in milliseconds between two measure in the input files.

    Three default profiles of input file are present, you can set these profile with
    the three methods. They refer to TOA5 input files generated from standard
    eddy covariance experiment.
    
    Attributes
    ----------
    sampling_rate_ms : float 
        milliseconds between two measure.
    cols : Dict[str, Tuple[type, str, str]]
        Key is the name of the column in the input files.
        Value is a tuple contains in order, the pandas type of the column,
        the name of the column in the database table (can be different from file),
        the SQL type of the column in the table (used to create the table).

    Examples
    --------
    >>> cols = {
            "col_A": (int, "db_col_A", "INTEGER"),
            "col_B": (float, "db_col_B", "DECIMAL(5,2)")
        }
    >>> configCustom = InputFileConfig(sampling_rate_ms=1000, cols=cols)
    >>> configGill = InputFileConfig.gillwindmaster(level_n=1, sampling_rate_ms=50)
    >>> configRot = InputFileConfig.rotated_wind(rot_type="dr", sampling_rate_ms=50)
    >>> configTherm = InputFileConfig.defaultThermohygrometer(level_n=1, sampling_rate_ms=1000)
    >>> configStatus = InputFileConfig.defaultStatus(sampling_rate_ms=1000)
    """
    sampling_rate_ms: float
    cols: Dict[str, Tuple[type, str, str]]

    @classmethod
    def gillwindmaster(cls,
                       level_n: int = 1,
                       sampling_rate_ms: float = 50):
        """
        Create the configuration to import data from a sonic Gill Windmaster datafile. 
        The sensor is located at n-th vertical level.
        Four variable are expected in the input file: u_i, v_i, w_i, three components of 
        the wind and Ts_i the sonic temperature (i is the number of the level).

        Gill Windmaster generate measures with three decimal digits, if high precision is 
        enabled. The maximum value is 50 m/s so the database type for sonic measure can 
        be DECIMAL(6,3), to save memory. Set the sampling rate for this type of measure.

        Parameters
        ----------
        level_n : int
            number of vertical levels of the instruments.
        sampling_rate_ms : float
            milliseconds between two measure, default 50ms (20Hz).

        Raises
        ------
        TypeError
            If level_n is not an int.
        ValueError
            If level_n is not positive and non-zero.
        """
        if not isinstance(level_n, int):
            raise TypeError("Number of the level/instruments must be an int.")
        if level_n <= 0:
            raise ValueError("Number of the level/instruments must be non zero and positive.")

        i = level_n
        cols_gill_windmaster = {
            "TIMESTAMP": ("datetime64[ms]", "datetime", "DATETIME PRIMARY KEY"),
            f"u_{i}": (float, "u", "DECIMAL(6,3)"),
            f"v_{i}": (float, "v", "DECIMAL(6,3)"),
            f"w_{i}": (float, "w", "DECIMAL(6,3)"),
            f"Ts_{i}": (float, "ts", "DECIMAL(6,3)")
        }

        '''i = level_n
        cols_gill_windmaster["TIMESTAMP"] = ("datetime64[ms]", "datetime", "DATETIME PRIMARY KEY")
        cols_gill_windmaster[f"u_{i}"]  = (float, "u", "DECIMAL(6,3)")
        cols_gill_windmaster[f"v_{i}"]  = (float, "v", "DECIMAL(6,3)")
        cols_gill_windmaster[f"w_{i}"]  = (float, "w", "DECIMAL(6,3)")
        cols_gill_windmaster[f"Ts_{i}"] = (float, "ts", "DECIMAL(6,3)")'''
        
        # Create gill object
        return cls(
            cols = cols_gill_windmaster,
            sampling_rate_ms = sampling_rate_ms
        )
    
    @classmethod
    def defaultThermohygrometer(cls, 
                                level_n: int = 1, 
                                sampling_rate_ms: float = 1000):
        """
        Create the configuration to import data from a thermohygrometer datafile. 
        The sensor is located at n-th vertical level.
        Two variable are expected in the input file: AirTC_i and RH_i, representing 
        the air temperature and relative humidity (i is the number of the level).
        
        Standard slow termoigrometers generate measures with one/two decimal digits.
        The database type for these measure can be DECIMAL(5,2), to save memory. 
        Set the sampling rate for this type of measure.

        Parameters
        ----------
        level_n : int
            number of vertical levels of the instruments.
        sampling_rate_ms : float
            milliseconds between two measure, default 1s (1Hz).

        Raises
        ------
        TypeError
            If level_n is not an int.
        ValueError
            If level_n is not positive and non-zero.
        """
        if not isinstance(level_n, int):
            raise TypeError("Number of the level/instruments must be an int.")
        if level_n <= 0:
            raise ValueError("Number of the level/instruments must be non zero and positive.")

        i = level_n
        cols_trh = {
            "TIMESTAMP": ("datetime64[ms]", "datetime", "DATETIME PRIMARY KEY"),
            f"AirTC{i}": (float, f"t", "DECIMAL(5,2)"),
            f"RH{i}": (float, f"rh", "DECIMAL(5,2)")
        }

        #for i in range(1, level_ns + 1):
        '''i = level_n
        cols_trh["TIMESTAMP"] = ("datetime64[ms]", "datetime", "DATETIME PRIMARY KEY")
        cols_trh[f"AirTC{i}"] = (float, f"t", "DECIMAL(5,2)")
        cols_trh[f"RH{i}"] = (float, f"rh", "DECIMAL(5,2)")'''

        return cls(
            cols = cols_trh,
            sampling_rate_ms = sampling_rate_ms
        )

    @classmethod
    def defaultStatus(cls, 
                      sampling_rate_ms: float = 1000):
        """
        Create the configuration to import data from the status files, containing 
        info about the status of the station, for example a Campbell datalogger. 
        Here an example with battery voltage of the station and info about the SD card
        where files are stored. Set the sampling rate between two records.

        Parameters
        ----------
        sampling_rate_ms : float
            milliseconds between two records. Default 1s (1Hz).
        """

        cols_status = {
            "TIMESTAMP" : ("datetime64[ms]", "datetime", "DATETIME PRIMARY KEY"),
            "BattV_Min": (float, "battVmin", "DECIMAL(5,2)"),
            "CardStatus": (str, "card_status", "VARCHAR(10)")
        }

        return cls( 
            cols = cols_status,
            sampling_rate_ms = sampling_rate_ms
        )

    @classmethod
    def rotated_wind(cls,
                     rot_type: str,
                     sampling_rate_ms: float = 50):
        """
        Set the configuration for standard rotated components database, with n vertical 
        levels. Four variable are expected: u, v, w, three components of the wind and 
        Ts the sonic temperature. Gill Windmaster, with high precision enabled,
        generate measures with three decimal digits. The maximum value is 50 m/s so
        the database type for sonic measure can be DECIMAL(6,3), to save space. 
        Set the sampling rate for this type of measure.

        Parameters
        ----------
        rot_type : str
            planar_fit "pf" or double rotation "dr"
        sampling_rate_ms : float
            milliseconds between two measure. Default 50ms (20Hz).
        
        Raises
        ------
        ValueError
            If rot_type is not 'pf' or 'dr'.
        """
        
        rot_cols = {
            "TIMESTAMP": ("datetime64[ms]", "datetime", "DATETIME PRIMARY KEY"),
            "u": (float, "u", "DECIMAL(6,3)"),
            "v": (float, "v", "DECIMAL(6,3)"),
            "w": (float, "w", "DECIMAL(6,3)"),
            "Ts": (float, "ts", "DECIMAL(6,3)")
        }

        if rot_type == "dr":
            rot_cols["theta"] = (float, "theta", "DECIMAL(5,2)")
            rot_cols["phi"] = (float, "phi", "DECIMAL(5,2)")
        elif rot_type == "pf":
            rot_cols["gamma"] = (float, "gamma", "DECIMAL(5,2)")
        else:
            raise ValueError("rot_type must be 'pf' or 'dr'.")
        
        return cls(
            cols = rot_cols,
            sampling_rate_ms = sampling_rate_ms
        )
    
    def get_file_cols_name(self) -> List[str]:
        """
        Return a list with the column names of the input file.
        """
        return list(self.cols.keys())
    
    def get_file_cols_type(self) -> Dict[str, str]:
        """
        Return a dictionary that maps the input file column name with 
        its type.

        Key: column name in the input file,
        Value: pandas type of the column.
        """
        dict = {}
        for key, value in self.cols.items():
            dict[key] = value[0]
        return dict
    
    def get_table_cols_name(self) -> Dict[str, str]:
        """
        Return a dictionary that maps the input file column name with 
        the column name in the database table.

        Key: column name in the input file,
        Value: column name in the database table.
        """
        dict = {}
        for key, value in self.cols.items():
            dict[key] = value[1]
        return dict
    
    def get_table_cols_type(self) -> Dict[str, str]:
        """
        Return a dictionary that maps the column name in the database table 
        with its SQL type. 

        Key: column name in the database table,
        Value: column SQL type in the database table.
        """
        dict = {}
        for value in self.cols.values():
            dict[value[1]] = value[2]
        return dict

@dataclass
class StationConfig:
    """
    Configuration parameters for a single station, identified by station_name,
    for example the serial number of a Campbell datalogger.
    The aim is use this class to contains all the info about the station data
    and related files.

    You can add to a single station multiple InputFileConfig (one for each type
    of input file), using add_input_file_config() method. You have to specify:
    1) An ID that identify the type of input file (e.g. sonic, slow, stat)
    2) A dictionary that associates the config_id and the name of the database table,
       which will contain data from all files of the same type
    3) A dictionary that associates the config_id and the pattern filename in
       all file names of the same type (e.g. S*.dat or *2026-05-10*)

    Attributes:
        station_name: name of the station, longer description
        station_id: id of the station, with no space
        db_table_names: dict with config_id as key and database table name as value
        input_files_name: dict with config_id as key and substring as value. The substring
          must be contained in all file names related to the same InputFileConfig object,
          it is used to select the files to import
        input_files_config: dict with config_id as key and InputFileConfig as value
    """
    station_name: str
    station_id: str
    db_table_names: Dict[str, str] = field(default_factory=dict)
    input_files_name: Dict[str, str] = field(default_factory=dict)
    input_files_config: Dict[str, 'InputFileConfig'] = field(default_factory=dict)

    def add_input_file_config(self, config_id: str, config: 'InputFileConfig', db_table_name: str, input_files_name: str):
        """
        Add new InputFileConfig object to the station.
        One config for each type of files generated from the station.

        Attributes:
            config_id: id of the input configuration files
            config: InputFileConfig object contains column info
            db_table_name: name of the database table, which will contain 
                           data from all files of the same type
            input_files_name: a wildcard pattern contained in all file names that 
                              match the stucture described in the config object
                              (e.g. S*.dat or *2026-05-10*)
        """
        self.input_files_config[config_id] = config
        self.db_table_names[config_id] = db_table_name
        self.input_files_name[config_id] = input_files_name

    def get_configs(self) -> Dict[str, 'InputFileConfig']:
        """
        Get dictionary contains all InputFileConfig object
        """
        return self.input_files_config

    def get_input_config(self, config_id) -> InputFileConfig:
        """
        Get one InputFileConfig object given its config id.

        Parameters
        ----------
        config_id : str
            The id of the configuration to return.

        Returns
        -------
        InputFileConfig
            The configuration associated with config_id.

        Raises
        ------
        KeyError
            If config_id is not present in the station configurations.
        """
        return self.input_files_config[config_id]
    
    def get_table_name(self, config_id):
        """
        Get the name of the table in the database, 
        given the the indetifier of the input config.

        Attributes:
            config_id: the id of the configuration
        """
        return self.db_table_names[config_id]
    
    def get_input_file_name(self, config_id) -> str:
        """
        Get the substring the file names must contains, to be imported, 
        given the the indetifier of the input config.

        Attributes:
            config_id: the id of the configuration

        
        """
        return self.input_files_name[config_id]