#!/usr/bin/python
# -*- coding: utf-8 -*-
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import MagicMock
from EddyCovTools.file_manager import toa5_to_df, csv_to_df, get_files_pattern, get_files_from_station

# --- FIXTURES ---

@pytest.fixture
def example_toa5_content() -> str:
    """
    Returns a string simulating a standard 4-line header TOA5 Campbell TOA5 file,
    plus 2 lines of actual data.
    """
    return (
        '"TOA5","26458","CR6","26458","CR6.14.5.0","CPU:double_polled_1.05.CR6","19292","Slow"\n'
        '"TIMESTAMP","RECORD","AirTC1","RH1","AirTC2","RH2"\n'
        '"TS","RN","Deg C","%","Deg C","%"\n'
        '"","","Smp","Smp","Smp","Smp"\n'
        '"2026-03-25 23:00:01",1091965,11.86,63.57,11.78,63.61\n'
        '"2026-03-25 23:00:02",1091966,11.89,63.55,11.79,63.66\n'
    )

@pytest.fixture
def temp_toa5_file(tmp_path, example_toa5_content) -> Path:
    """
    Creates a temporary physical file containing the dummy TOA5 data
    and returns its Path object.
    """
    file_path = tmp_path / "TOA5_data.dat"
    file_path.write_text(example_toa5_content, encoding='utf-8')
    return file_path

@pytest.fixture
def empty_toa5_file(tmp_path):
    """Creates a TOA5 file with only the header and no data rows."""
    content = (
        '"TOA5","26458","CR6","26458","CR6.14.5.0","CPU:double_polled_1.05.CR6","19292","Slow"\n'
        '"TIMESTAMP","RECORD","AirTC1","RH1","AirTC2","RH2"\n'
        '"TS","RN","Deg C","%","Deg C","%"\n'
        '"","","Smp","Smp","Smp","Smp"\n'
    )
    file_path = tmp_path / "empty_data.dat"
    file_path.write_text(content, encoding='utf-8')
    return file_path

@pytest.fixture
def mock_InputFileConfig():
    """
    Creates a MagicMock simulating an InputFileConfig object.
    """
    mock_config = MagicMock()
    # columns of the file to import
    mock_config.get_file_cols_name.return_value = ["TIMESTAMP", "RECORD", "AirTC1", "RH1"]
    
    # expected pandas types
    mock_config.get_file_cols_type.return_value = {
        "TIMESTAMP": "datetime64[ms]",
        "RECORD": int,
        "AirTC1": float,
        "RH1": float
    }
    return mock_config


################################################################################
# test toa5_to_df()

def test_toa5todf_header(temp_toa5_file, mock_InputFileConfig, example_toa5_content):
    """
    Correct importing of header from TOA5 file
    
    GIVEN: a valid TOA5 file and a valid InputFileConfig
    WHEN: toa5_to_df is called with date_index=False
    THEN: it returns 4-line header.
    """
    df, header = toa5_to_df(input_file=temp_toa5_file, 
                            config=mock_InputFileConfig, 
                            date_index=False)
    
    # verify 4 line header
    assert len(header) == 4
    # verify the content of header
    expeceted_header = example_toa5_content.splitlines(keepends=True)[:4]
    assert header == expeceted_header

def test_toa5todf_dataframe(temp_toa5_file, mock_InputFileConfig):
    """
    Test if toa5_to_df() return a dataframe with right contents

    GIVEN: a valid TOA5 file and a valid InputFileConfig
    WHEN: toa5_to_df is called with date_index=False
    THEN: it returns a dataframe with right content.
    """
    df, header = toa5_to_df(input_file=temp_toa5_file, 
                            config=mock_InputFileConfig, 
                            date_index=False)

    assert isinstance(df, pd.DataFrame)

    #correct number of data rows
    assert len(df) == 2

    # verify column filtering
    expected_columns = ["TIMESTAMP", "RECORD", "AirTC1", "RH1"]
    assert list(df.columns) == expected_columns

    # verify dtype conversion
    assert df["TIMESTAMP"].dtype == "datetime64[ms]"
    assert df["RECORD"].dtype == int
    assert df["AirTC1"].dtype == float
    assert df["RH1"].dtype == float
    
    # verify index is the default numeric one
    assert df.index.name is None

def test_toa5todf_dateindex_true(temp_toa5_file, mock_InputFileConfig):
    """
    GIVEN: a valid TOA5 file and a valid InputFileConfig
    WHEN: toa5_to_df is called with date_index=True
    THEN: the TIMESTAMP column becomes the dataframe index.
    """
    df, _ = toa5_to_df(input_file=temp_toa5_file, 
                        config=mock_InputFileConfig, 
                        date_index=True)

    # Verify TIMESTAMP is the index
    assert df.index.name == "TIMESTAMP"
    assert "TIMESTAMP" not in df.columns

    # other columns are ok
    assert "RECORD" in df.columns
    assert "AirTC1" in df.columns
    assert "RH1" in df.columns

def test_toa5todf_string_path_input(temp_toa5_file, mock_InputFileConfig):
    """
    GIVEN: a valid TOA5 file path passed as string
    WHEN: toa5_to_df is called
    THEN: it handles the string correctly converting it internally to Path.
    """
    # convert Path object to string
    str_path = str(temp_toa5_file)
    
    df, _ = toa5_to_df(input_file=str_path, config=mock_InputFileConfig)
    assert not df.empty

def test_toa5todf_type_conversion_error(temp_toa5_file, mock_InputFileConfig):
    """
    GIVEN: an InputFileConfig that forces an impossible type conversion (e.g. date string to float)
    WHEN: toa5_to_df is called
    THEN: it raises a ValueError directly from Pandas df.astype().
    """
    # try to convert the date string into a float
    mock_InputFileConfig.get_file_cols_type.return_value = {
        "TIMESTAMP": float, 
        "RECORD": int, 
        "AirTC1": float, 
        "RH1": float
    }

    # Verify that attempting to cast a date string to float raises a ValueError
    with pytest.raises(ValueError):
        toa5_to_df(input_file=temp_toa5_file, config=mock_InputFileConfig)

def test_toa5todf_file_not_found(tmp_path, mock_InputFileConfig):
    """
    GIVEN: a file path that does not exist
    WHEN: toa5_to_df is called
    THEN: it raises FileNotFoundError.
    """
    fake_file = tmp_path / "does_not_exist.dat"
    
    with pytest.raises(FileNotFoundError):
        toa5_to_df(input_file=fake_file, config=mock_InputFileConfig)

def test_toa5todf_missing_column(temp_toa5_file, mock_InputFileConfig):
    """
    GIVEN: an InputFileConfig requesting a column not present in the TOA5 file
    WHEN: toa5_to_df is called
    THEN: it raises KeyError during casting.
    """
    # Ask for a column that is not in the example_toa5_content
    mock_InputFileConfig.get_file_cols_name.return_value = ["TIMESTAMP", "missCol"]
    mock_InputFileConfig.get_file_cols_type.return_value = {
        "TIMESTAMP": "datetime64[ms]",
        "missCol": float
    }

    with pytest.raises(KeyError):
        toa5_to_df(input_file=temp_toa5_file, config=mock_InputFileConfig)

def test_toa5todf_no_data_rows(empty_toa5_file, mock_InputFileConfig):
    """
    GIVEN: a valid TOA5 file with headers but no data rows
    WHEN: toa5_to_df is called
    THEN: it returns an empty DataFrame with the correct columns and types.
    """
    df, header = toa5_to_df(input_file=empty_toa5_file, config=mock_InputFileConfig)
    
    assert len(df) == 0
    assert list(df.columns) == ["TIMESTAMP", "RECORD", "AirTC1", "RH1"]
    assert len(header) == 4


#########################################################################
# test csv_to_df()

# FIXTURES
@pytest.fixture
def example_csv_content() -> str:
    """
    Simulates a standard CSV file with a single header row.
    It also contains an extra column to test column filtering.
    """
    return (
        "TIMESTAMP,RECORD,AirTC1,RH1,ExtraCol\n"
        "2026-03-25 23:00:01,1091965,11.86,63.57,99\n"
        "2026-03-25 23:00:02,1091966,11.89,63.55,100\n"
    )

@pytest.fixture
def temp_csv_file(tmp_path, example_csv_content) -> Path:
    """
    Creates a temporary physical file containing the CSV data
    and returns its Path object.
    """
    file_path = tmp_path / "standard_data.csv"
    file_path.write_text(example_csv_content, encoding='utf-8')
    return file_path

def test_csvtodf_dataframe(temp_csv_file, mock_InputFileConfig):
    """
    GIVEN: a valid CSV file and a valid InputFileConfig
    WHEN: csv_to_df is called
    THEN: it returns a dataframe with the right content and correct data types.
    """

    df = csv_to_df(input_file=temp_csv_file, config=mock_InputFileConfig)

    assert isinstance(df, pd.DataFrame)
    
    # correct number of data rows
    assert len(df) == 2

    # verify column filtering ('ExtraCol' must be dropped)
    assert list(df.columns) == ["TIMESTAMP", "RECORD", "AirTC1", "RH1"]

    # verify dtype conversion
    assert df["TIMESTAMP"].dtype == "datetime64[ms]"
    assert df["RECORD"].dtype == int
    assert df["AirTC1"].dtype == float

    # verify index is the default numeric one
    assert df.index.name is None

def test_csvtodf_with_index(temp_csv_file, mock_InputFileConfig):
    """
    GIVEN: a valid CSV file and a valid InputFileConfig
    WHEN: csv_to_df is called with a specific index string
    THEN: the specified column becomes the dataframe index.
    """

    df = csv_to_df(input_file=temp_csv_file, 
                   config=mock_InputFileConfig, 
                   index="TIMESTAMP")

    # Verify TIMESTAMP is the index
    assert df.index.name == "TIMESTAMP"
    assert "TIMESTAMP" not in df.columns
    
    # other columns are ok
    assert "RECORD" in df.columns
    assert "AirTC1" in df.columns
    assert "RH1" in df.columns

def test_csvtodf_string_path_input(temp_csv_file, mock_InputFileConfig):
    """
    GIVEN: a valid CSV file path passed as a string
    WHEN: csv_to_df is called
    THEN: it handles the string correctly converting it internally to Path.
    """
    str_path = str(temp_csv_file)
    df = csv_to_df(input_file=str_path, config=mock_InputFileConfig)
    
    assert not df.empty

def test_csvtodf_type_conversion_error(temp_csv_file, mock_InputFileConfig):
    """
    GIVEN: an InputFileConfig that forces an impossible type conversion
    WHEN: csv_to_df is called
    THEN: it raises a ValueError directly from Pandas.
    """
    # impossible timestamp conversion
    mock_InputFileConfig.get_file_cols_type.return_value = {
        "TIMESTAMP": float, 
        "RECORD": int, 
        "AirTC1": float, 
        "RH1": float
    }

    with pytest.raises(ValueError):
        csv_to_df(input_file=temp_csv_file, config=mock_InputFileConfig)

def test_csvtodf_file_not_found(tmp_path, mock_InputFileConfig):
    """
    GIVEN: a file path that does not exist
    WHEN: csv_to_df is called
    THEN: it raises FileNotFoundError.
    """
    fake_file = tmp_path / "does_not_exist.csv"
    
    with pytest.raises(FileNotFoundError):
        csv_to_df(input_file=fake_file, config=mock_InputFileConfig)

#################################################################################
# test get_files_pattern()

#FIXTURE
@pytest.fixture
def mock_station_directory(tmp_path) -> Path:
    """
    Creates a temporary directory populated with various files and subdirectories
    to test the glob pattern matching.
    """
    # Create valid TOA5 sonic files (out of order to test sorting)
    (tmp_path / "TOA5_Sonic_2026_03_02.dat").touch()
    (tmp_path / "TOA5_Sonic_2026_03_01.dat").touch()
    (tmp_path / "TOA5_Sonic_2026_03_10.dat").touch()
    
    # Create valid TOA5 slow files
    (tmp_path / "TOA5_Slow_2026_03_01.dat").touch()
    
    # Create a file that matches the pattern but is a directory (edge case)
    sub_dir = tmp_path / "TOA5_Sonic_Dir.dat"
    sub_dir.mkdir()
    
    # Create a random text file
    (tmp_path / "readme.txt").touch()

    return tmp_path

def test_get_files_pattern_basic_match(mock_station_directory):
    """
    GIVEN: a directory with mixed files
    WHEN: get_files_pattern is called with a specific pattern
    THEN: it returns only the files matching the pattern, ignoring directories.
    """
    pattern = "TOA5_Sonic_*.dat"
    
    files = get_files_pattern(folder_path=mock_station_directory, 
                              pattern=pattern, 
                              sorted=False)
    
    # It should find 3 valid files (it must ignore the directory 'TOA5_Sonic_Dir.dat')
    assert len(files) == 3
    assert all(isinstance(f, Path) for f in files)
    assert all("Sonic" in f.name for f in files)

def test_get_files_pattern_sorted(mock_station_directory):
    """
    GIVEN: a directory with files created out of alphabetical order
    WHEN: get_files_pattern is called with sorted=True
    THEN: it returns a list naturally sorted by filename.
    """
    pattern = "TOA5_Sonic_*.dat"
    
    files = get_files_pattern(folder_path=mock_station_directory, 
                              pattern=pattern, 
                              sorted=True)
    
    assert len(files) == 3
    # Check natural sorting order
    assert files[0].name == "TOA5_Sonic_2026_03_01.dat"
    assert files[1].name == "TOA5_Sonic_2026_03_02.dat"
    assert files[2].name == "TOA5_Sonic_2026_03_10.dat"

def test_get_files_pattern_no_match(mock_station_directory):
    """
    GIVEN: a valid directory but a pattern that matches nothing
    WHEN: get_files_pattern is called
    THEN: it returns an empty list.
    """
    files = get_files_pattern(folder_path=mock_station_directory, 
                              pattern="*Ghost*.dat")
    
    assert isinstance(files, list)
    assert len(files) == 0

def test_get_files_pattern_string_input(mock_station_directory):
    """
    GIVEN: a directory path passed as a string
    WHEN: get_files_pattern is called
    THEN: it handles the string conversion correctly.
    """
    str_path = str(mock_station_directory)
    
    files = get_files_pattern(folder_path=str_path, pattern="*Slow*")
    
    assert len(files) == 1
    assert files[0].name == "TOA5_Slow_2026_03_01.dat"

def test_get_files_pattern_invalid_directory(tmp_path):
    """
    GIVEN: a path that does not exist or is a file instead of a directory
    WHEN: get_files_pattern is called
    THEN: it raises NotADirectoryError.
    """
    # 1. Test completely non-existent path
    fake_path = tmp_path / "does_not_exist_folder"
    
    with pytest.raises(NotADirectoryError):
        get_files_pattern(folder_path=fake_path, pattern="*.*")

    # 2. Test passing a file path instead of a directory
    file_path = tmp_path / "just_a_file.txt"
    file_path.touch()
    
    with pytest.raises(NotADirectoryError):
        get_files_pattern(folder_path=file_path, pattern="*.*")