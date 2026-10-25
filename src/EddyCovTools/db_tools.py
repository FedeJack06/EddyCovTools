#!/usr/bin/python
# -*- coding: utf-8 -*-
import duckdb as db
import pandas as pd
from typing import Dict, List
from pathlib import Path
from .config import InputFileConfig, StationConfig
from .file_manager import get_files_from_station, toa5_to_df

import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

'''def df_to_db(con: db.DuckDBPyConnection, 
             df_in: pd.DataFrame, 
             db_table: str, 
             map_df_db_cols: Dict[str, str] = None) -> tuple[int, int]:
    """
    Fill a database table with a Pandas dataframe.
    You can specify a relation between the column names 
    in the dataframe and the column names in the table.
    If you don't pass the relation, the table and df must
    have the same column name.
    If df has index named "datetime", reset index is performed and 
    "datetime" became a column.

    Parameters
    ----------
    con: db.DuckDBPyConnection
        connection to the database
    df_in: pd.DataFrame
        the Pandas dataframe to put into the table
    db_table: str
        the name of the table to fill
    map_df_db_cols: Dict[str, str]
        a map that links the column names in the dataframe (as keys)
        to the column names in the table (as value)

    Returns
    ----------
    int: 
        Number of inserted rows
    int:
        Number of skipped rows: difference between df rows and inserted rows
    """
    if df_in.index.name == "datetime":
        df_in = df_in.reset_index()

    if map_df_db_cols is not None:
        #put the column name in the dataframe and in the table in two list
        #same list index identifies a pair
        table_cols = []
        df_cols = []
        for key, value in map_df_db_cols.items():
            df_cols.append(key)
            table_cols.append(value)

        #query to insert dataframe rows into a table
        query = f"""
            INSERT INTO {db_table} ({", ".join(table_cols)})
            SELECT {", ".join(df_cols)} FROM df_in 
            ON CONFLICT DO NOTHING
        """
    else: #insert all df column into table
        query = f"INSERT INTO {db_table} BY NAME SELECT * FROM df_in ON CONFLICT DO NOTHING"

    try:
        inserted_rows = con.execute(query).fetchone()[0]
    except db.Error as e:
        raise

    skipped = len(df_in) - inserted_rows

    return inserted_rows, skipped'''

def _get_pk(con, db_table: str) -> str:
    """
    Return the name of the primary key column of a table.

    Returns
    -------
    str
        Name of the primary key column.

    Raises
    ------
    ValueError
        If the table has no primary key, or a composite one.
    """
    pk = [r[0] for r in con.execute(
        f"SELECT name FROM pragma_table_info('{db_table}') WHERE pk"
    ).fetchall()]
    if len(pk) != 1:
        raise ValueError(
            f"Table '{db_table}' must have exactly one primary key column, found: {pk}"
        )
    return pk[0]

def df_to_db(con: db.DuckDBPyConnection, 
               df_in: pd.DataFrame, 
               db_table: str, 
               map_df_db_cols: Dict[str, str] = None, 
               overwrite: bool = False) -> tuple[int, int]:
    """
    Insert a Pandas DataFrame into a DuckDB table.

    The DataFrame may contain only a subset of the table columns. Columns of
    the table that are not in the DataFrame are left to their default value
    on new rows, and untouched on updated rows.

    You can specify a relation between the column names 
    in the dataframe and the column names in the table.
    If you don't pass the relation, the table and df must
    have the same column name.

    If the DataFrame index is named (e.g. "datetime"), it is converted into
    a column. An unnamed index (e.g. the default RangeIndex) is ignored.

    Parameters
    ----------
    con: db.DuckDBPyConnection
        Connection to the database.
    df_in: pd.DataFrame
        The DataFrame to insert. It must contain the primary key column of
        the table (possibly as a named index), with no repeated values.
    db_table: str
        Name of the table to fill. It must have exactly one primary key column.
    map_df_db_cols: Dict[str, str], optional
        Map from DataFrame column names (keys) to table column names (values).
        Only the DataFrame columns listed in the map are inserted, and all of
        them must exist in the DataFrame. If the key is a named index, include
        it in the map as well (e.g. {"datetime": "datetime", ...}).
        If None, DataFrame and table columns are matched by name.
    overwrite: bool, default False
        How to handle rows whose primary key already exists in the table.
        If False, they are skipped. If True, they are updated, only on the
        columns present in the DataFrame.

    Returns
    -------
    int
        Number of rows written by the INSERT statement:
        - overwrite=False: rows actually inserted.
        - overwrite=True: inserted rows plus updated rows.
    int
        Number of skipped rows, i.e. DataFrame rows minus the first value:
        - overwrite=False: rows whose key was already in the table.
        - overwrite=True: always 0.

    Raises
    ------
    ValueError
        - If the table does not have exactly one primary key column.
        - If the primary key column is not among the DataFrame columns
          (e.g. the index holding it is unnamed, or it is missing from the map).
        - If the primary key column has repeated values in the DataFrame.
        - If overwrite=True and the DataFrame contains only the key column.
    KeyError
        If a key of `map_df_db_cols` is not a column of the DataFrame.
    db.BinderException
        If a DataFrame column (after mapping) does not exist in the table.
    db.ConstraintException
        If the insert violates a table constraint other than the primary key
        (e.g. NOT NULL on a column, or a NULL in the key column).

    Notes
    -----
    Nothing is written if any check fails. NaN values in the DataFrame
    overwrite existing values when overwrite=True.
    """
    # duckdb ignore the df index, duck db reads only df columns
    # if df has a custom index with a name, convert it in a df column
    if any(n is not None for n in df_in.index.names):
        df_in = df_in.reset_index()

    # rename the df columns into the corrisponding names in the table
    if map_df_db_cols is not None:
        df_in = df_in[list(map_df_db_cols)].rename(columns=map_df_db_cols)

    # check if the primary key of table is present in the df columns
    key = _get_pk(con, db_table)
    if key not in df_in.columns:
        raise ValueError(
            f"Primary key column '{key}' of table '{db_table}' not found in the dataframe"
            f" (columns: {list(df_in.columns)}). Maybe the index is unnamed."
        )

    # chack if there are two df rows with the same index (e.g same datetime)
    if df_in[key].duplicated().any():
        raise ValueError(f"Duplicated values in key column '{key}' within the dataframe.")

    # build the action ON CONFLICT of the query
    if overwrite:
        sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in df_in.columns if c != key)
        if not sets:
            raise ValueError("overwrite=True but the dataframe contains only the key column: nothing to update")
        action = f"({key}) DO UPDATE SET {sets}"
    else:
        action = "DO NOTHING"

    # generic insert query by name: if a df column not in table -> db Binder Error
    # if a table column not in df -> table column left with his default value
    n = con.execute(
        f"INSERT INTO {db_table} BY NAME SELECT * FROM df_in ON CONFLICT {action}"
    ).fetchone()[0]

    # return the number of inserted rows, and number of skipped rows
    return n, len(df_in) - n

def fill_db_toa5(con: db.DuckDBPyConnection, 
                 db_table: str, 
                 file_list: List[Path],
                 config: InputFileConfig) -> None:
    """
    Fills a database table with a list of TOA5 files.

    Parameters
    ----------
    con: db.DuckDBPyConnection
        connection to the database
    db_table: str
        the name of the table to fill
    file_list: List[Path]
        a list of Path object, containing the files to put 
        into the database table
    config: InputFileConfig
        configuration file input, with all the info about the 
        columns to be inported.
    """
    for file in file_list:
        df, header = toa5_to_df(file, config=config)

        #get the dictiocary that link the column name in the dataframe
        #and the column name in the table
        map = config.get_table_cols_name()

        try:
            #insert entire dataframe into the table
            inserted_rows, skipped_rows = df_to_db(con=con, df_in=df, db_table=db_table, map_df_db_cols=map)
            logger.info(f"{file.name}: Query OK, {inserted_rows} row(s) affected")
            if skipped_rows > 0:
                logger.warning(f"Warning on {file.name}: {skipped_rows} duplicate row(s) skipped, {inserted_rows} inserted.")
        except db.Error as e:
            logger.error(f"Error importing file: {file.name}: {e}")

def fill_db_station_toa5(con: db.DuckDBPyConnection, 
                    station: StationConfig, 
                    input_dir: str,
                    configs: List[str] = None) -> None:
    """
    Fills the database with the files produced by a station.
    StationConfig object is used to put different file types into
    the correct database tables. A table corresponds to a file type,
    and it is filled only with files of the same type.
    Different type of files can be in the same directory. They are sorted
    based on the substring in their name, specified in the station configuration.
    Only file type listed in config parameter will be inseted into db.

    Parameters
    ----------
    con: db.DuckDBPyConnection
        connection to the database
    station: StationConfig
        Station object conaining all the input file configuration
    input_dir: str
        Directory containing all the files produced by the station.
    configs: List[str] = None
        List of id of InputFileConfig in the station, to insert into database.
        If None, all InputFileConfig of station will be inseted.
    """
    #get a dict with the input configuration id as key and
    #the list of related files as value
    all_station_files = get_files_from_station(input_dir, station, configs)

    for config_id, file_list in all_station_files.items():
        #get the InputFileConfig object based on its id
        config = station.get_input_config(config_id)
        #get the database table name associated with this input config
        table_name = station.get_table_name(config_id)
        #fill the table with files of the same type
        fill_db_toa5(con=con, db_table=table_name, file_list=file_list, config=config)

def _db_df(db_path: str | Path, 
           table: str, 
           query: str, 
           params: list = None) -> pd.DataFrame:
    """
    Executes a query and returns a DataFrame
    indexed by the table's PRIMARY KEY column.

    """
    db_path = Path(db_path)
    with db.connect(db_path) as con:
        # get table metadata, one row for each column info
        table_info = con.execute(f"PRAGMA table_info({table})").df()
        # pk column = 1 if is primary key. List of name of pk column
        pk_cols = (table_info[table_info["pk"] > 0].sort_values("pk")["name"].tolist())

        df = con.execute(query, params or []).df()

    # if found pk column
    if pk_cols:
        # index or multindex based on pk column finded
        # drop column index
        df = df.set_index(pk_cols if len(pk_cols) > 1 else pk_cols[0], drop=True)
    else:
        logger.warning(f"No PRIMARY KEY found in {table}, default index in df")

    return df

def table_to_df(db_path: str | Path,
                table: str,
                orderby: str = "1 ASC") -> pd.DataFrame:
    """Get entire db table into a Pandas df"""
    
    query = f"SELECT * FROM {table} ORDER BY {orderby}"
    return _db_df(db_path, table, query)

def table_to_df_date(db_path: str | Path,
                   table: str,
                   start_date: str,
                   end_date: str,
                   orderby: str = "1 ASC") -> pd.DataFrame:
    """
    Get dataframe from a table between two date.

    Parameters
    ----------
    db_path: str | Path
        Path to input database file
    table: str
        Table name to be imported
    start_date: str
        First date to be selected
    end_date: str
        Last date to be selected
    orderby: str
        Column name to order rows ASC or DESC.
        Default is order by the first column (datetime) ascending

    Returns
    -------
    pd.DataFrame
        pd.DataFrame indexed by PRIMARY KEY
    """
    query = f"SELECT * FROM {table} WHERE datetime BETWEEN ? AND ? ORDER BY {orderby}"
    return _db_df(db_path, table, query, [start_date, end_date])

def table_to_df_dates(db_path: str | Path,
                   table: str,
                   dates: List[tuple],
                   orderby: str = "1 ASC") -> pd.DataFrame:
    """
    Get a dataframe from a table from some data intervals.

    Parameters
    ----------
    db_path: str | Path
        Path to input database file
    table: str
        Table name to be imported
    dates: List[tuple]
        List of (start_date, end_date) tuples.
    orderby: str
        Column name to order rows ASC or DESC.
        Default is order by the first column (datetime) ascending

    Returns
    -------
    pd.DataFrame
        pd.DataFrame indexed by PRIMARY KEY
    """
    conditions = " OR ".join(["(datetime BETWEEN ? AND ?)"] * len(dates))
    query = f"SELECT * FROM {table} WHERE {conditions} ORDER BY {orderby}"
    params = [date for interval in dates for date in interval]

    return _db_df(db_path, table, query, params)

def create_station_db(db_path: str | Path,
              stations: List[StationConfig],
              configs_id: List[str] = None) -> None:
    """
    Create a database structure with tables for each station
    as described in the configuration objects.
    """
    db_path = Path(db_path)

    if configs_id == None: # all configuration
        with db.connect(db_path) as con:
            for station in stations:
                for config_id, config in station.get_configs().items():
                    table_name = station.get_table_name(config_id)
                    cols_type = config.get_table_cols_type()
                    cols_query = ", ".join(f"{k} {v}" for k, v in cols_type.items())
                    query = f"""
                        CREATE TABLE IF NOT EXISTS {table_name} (
                            {cols_query}
                        )
                    """
                    try:
                        con.execute(query)
                        logger.info(f"Table created (or already exists): {table_name}")
                    except db.Error as e:
                        logger.error(f"Error creating {table_name}: {e}")
    else:
        with db.connect(db_path) as con:
            for station in stations:
                for config_id in configs_id:
                    config = station.get_input_config(config_id)
                    table_name = station.get_table_name(config_id)
                    cols_type = config.get_table_cols_type()
                    cols_query = ", ".join(f"{k} {v}" for k, v in cols_type.items())
                    query = f"""
                        CREATE TABLE IF NOT EXISTS {table_name} (
                            {cols_query}
                        )
                    """
                    try:
                        con.execute(query)
                        logger.info(f"Table created (or already exists): {table_name}")
                    except db.Error as e:
                        logger.error(f"Error creating {table_name}: {e}")

def create_flux_table(conn, table_name):
    """
    Create flux table in DuckDB with columns for each sonic level.
    
    Parameters
    ----------
    conn : duckdb.DuckDBPyConnection
    table_name : str
    n_levels : int
        Number of sonic levels.
    """
    cols = ["datetime TIMESTAMP PRIMARY KEY"]
    cols += [
        # avg wind components
        "u DOUBLE",
        "v DOUBLE",
        "w DOUBLE",
        "ts DOUBLE",
        "u_real DOUBLE",
        "v_real DOUBLE",
        "w_real DOUBLE",
        # second order moments
        "uw DOUBLE",
        "vw DOUBLE",
        "uv DOUBLE",
        "wT DOUBLE",
        "uT DOUBLE",
        "vT DOUBLE",
        "uu DOUBLE",
        "vv DOUBLE",
        "ww DOUBLE",
        "TT DOUBLE",
        "sigu DOUBLE",
        "sigv DOUBLE",
        "sigw DOUBLE",
        "sigT DOUBLE",
        "ustar DOUBLE",
        "TKE DOUBLE",
        "L DOUBLE"
    ]
    
    cols_def = ", ".join(cols)
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_def})")

def multi_db_table_to_df_dates(db_paths: List[str | Path],
                               table: str,
                               dates: List[tuple],
                               orderby: str = "1 ASC") -> pd.DataFrame:
    """
    Get a dataframe from a table spanning multiple database files, 
    filtered by date intervals.
    """
    con = db.connect(":memory:")
    
    # 1. Attacca tutti i database validi
    selects = []
    for idx, db_path in enumerate(db_paths):
        path_obj = Path(db_path)
        if not path_obj.exists():
            logger.warning(f"Database ignorato (non trovato): {path_obj}")
            continue
            
        alias = f"db_{idx}"
        con.execute(f"ATTACH '{path_obj}' AS {alias} (READ_ONLY)")
        selects.append(f"SELECT * FROM {alias}.{table}")
        
    if not selects:
        raise FileNotFoundError("Nessun database valido trovato tra i percorsi forniti.")
        
    # 2. Crea la vista unificata
    con.execute(f"CREATE TEMP VIEW all_data AS {' UNION ALL '.join(selects)}")
    
    # 3. Costruisci i filtri temporali
    conditions = " OR ".join(["(datetime BETWEEN ? AND ?)"] * len(dates))
    query = f"SELECT * FROM all_data WHERE {conditions} ORDER BY {orderby}"
    
    # Appiattisce la lista di tuple [(start1, end1), (start2, end2)]
    params = [date for interval in dates for date in interval]
    
    # 4. Esegue la query e indicizza
    df = con.execute(query, params).df()
    
    if 'datetime' in df.columns:
        df = df.set_index('datetime', drop=True)
    else:
        logger.warning(f"Colonna 'datetime' non trovata in {table}, indice default.")

    """db_path = Path(db_path)
        with db.connect(db_path) as con:
            # get table metadata, one row for each column info
            table_info = con.execute(f"PRAGMA table_info({table})").df()
            # pk column = 1 if is primary key. List of name of pk column
            pk_cols = (table_info[table_info["pk"] > 0].sort_values("pk")["name"].tolist())
    
            df = con.execute(query, params or []).df()
    
        # if found pk column
        if pk_cols:
            # index or multindex based on pk column finded
            # drop column index
            df = df.set_index(pk_cols if len(pk_cols) > 1 else pk_cols[0], drop=True)
        else:
            logger.warning(f"No PRIMARY KEY found in {table}, default index in df")
    """
        
    return df
        