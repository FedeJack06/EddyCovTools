import pytest
from EddyCovTools.config import InputFileConfig, StationConfig

@pytest.fixture
def dummy_input_config():
    """
    Fictitious InputFileConfig object to test.
    """
    cols = {
        "col_A": (int, "db_col_A", "INTEGER"),
        "col_B": (float, "db_col_B", "DECIMAL(5,2)")
    }
    return InputFileConfig(sampling_rate_ms=1000, cols=cols)

class TestInputFileConfig:
    
    def test_gillwindmaster_default(self):
        """
        Test Gill Windmaster default config

        WHEN: use the gillwindmaster method with default parameters
        THEN: verify that the returned InputFileConfig object has the correct parameters
        """
        config = InputFileConfig.gillwindmaster()

        # verify correct sampling rate
        assert config.sampling_rate_ms == 50
        
        # expected column names
        expected_file_cols = ["TIMESTAMP", "u_1", "v_1", "w_1", "Ts_1"]
        assert list(config.cols.keys()) == expected_file_cols
        
        # verify correct mapping to database columns
        assert config.cols["TIMESTAMP"] == ('datetime64[ms]', "datetime", "DATETIME PRIMARY KEY")
        assert config.cols["u_1"] == (float, "u", "DECIMAL(6,3)")
        assert config.cols["v_1"] == (float, "v", "DECIMAL(6,3)")
        assert config.cols["w_1"] == (float, "w", "DECIMAL(6,3)")
        assert config.cols["Ts_1"] == (float, "ts", "DECIMAL(6,3)")

    def test_gillwindmaster_level_2(self):
        """
        Test Gill Windmaster config with custom parameters

        WHEN: use the gillwindmaster() method with custom parameters
        THEN: verify that the returned InputFileConfig object has the correct parameters
        """
        config = InputFileConfig.gillwindmaster(n_level=2, sampling_rate_ms=100)

        # verify correct sampling rate
        assert config.sampling_rate_ms == 100
        
        # expected column names
        expected_file_cols = ["TIMESTAMP", "u_2", "v_2", "w_2", "Ts_2"]
        assert list(config.cols.keys()) == expected_file_cols
        
        # verify correct mapping to database columns
        assert config.cols["TIMESTAMP"] == ('datetime64[ms]', "datetime", "DATETIME PRIMARY KEY")
        assert config.cols["u_2"] == (float, "u", "DECIMAL(6,3)")
        assert config.cols["v_2"] == (float, "v", "DECIMAL(6,3)")
        assert config.cols["w_2"] == (float, "w", "DECIMAL(6,3)")
        assert config.cols["Ts_2"] == (float, "ts", "DECIMAL(6,3)")
        
        # ensure level 1 columns are not present
        assert "u_1" not in config.cols

    def test_thermohygrometer_default(self):
        """
        Test Thermohygrometer default config

        WHEN: use the defaultThermohygrometer() method with default parameters
        THEN: verify that the returned InputFileConfig object has the correct parameters
        """
        config = InputFileConfig.defaultThermohygrometer()

        # verify correct sampling rate
        assert config.sampling_rate_ms == 1000

        # expected column names
        expected_file_cols = ["TIMESTAMP", "AirTC1", "RH1"]
        assert list(config.cols.keys()) == expected_file_cols
        
        # verify correct mapping to database columns
        assert config.cols["TIMESTAMP"] == ('datetime64[ms]', "datetime", "DATETIME PRIMARY KEY")
        assert config.cols["AirTC1"] == (float, "t", "DECIMAL(5,2)")
        assert config.cols["RH1"] == (float, "rh", "DECIMAL(5,2)")

    def test_thermohygrometer_level_3(self):
        """
        Test Thermohygrometer config with custom parameters

        WHEN: use the Thermohygrometer method with custom parameters
        THEN: verify that the returned InputFileConfig object has the correct parameters
        """
        config = InputFileConfig.defaultThermohygrometer(n_level=3, sampling_rate_ms=2000)

        # verify correct sampling rate
        assert config.sampling_rate_ms == 2000

        # expected column names
        expected_file_cols = ["TIMESTAMP", "AirTC3", "RH3"]
        assert list(config.cols.keys()) == expected_file_cols
        
        # verify correct mapping to database columns
        assert config.cols["TIMESTAMP"] == ('datetime64[ms]', "datetime", "DATETIME PRIMARY KEY")
        assert config.cols["AirTC3"] == (float, "t", "DECIMAL(5,2)")
        assert config.cols["RH3"] == (float, "rh", "DECIMAL(5,2)")

    def test_rotated_wind_dr(self):
        """
        Test Rotated wind configuration with double rotation and default sampling rate

        WHEN: use the rotated_wind() method with DR type
        THEN: verify that the returned InputFileConfig object has the correct parameters
        """
        config = InputFileConfig.rotated_wind(rot_type="dr")

        # verify correct sampling rate
        assert config.sampling_rate_ms == 50

        # expected column names
        expected_file_cols = ["TIMESTAMP", "u", "v", "w", "Ts", "theta", "phi"]
        assert list(config.cols.keys()) == expected_file_cols

        # verify correct mapping to database columns
        assert config.cols["TIMESTAMP"] == ('datetime64[ms]', "datetime", "DATETIME PRIMARY KEY")
        assert config.cols["u"] == (float, "u", "DECIMAL(6,3)")
        assert config.cols["v"] == (float, "v", "DECIMAL(6,3)")
        assert config.cols["w"] == (float, "w", "DECIMAL(6,3)")
        assert config.cols["Ts"] == (float, "ts", "DECIMAL(6,3)")
        assert config.cols["theta"] == (float, "theta", "DECIMAL(5,2)")
        assert config.cols["phi"] == (float, "phi", "DECIMAL(5,2)")

    def test_rotated_wind_pf(self):
        """
        Test rotated wind configuration with planar fit rotation and custom sampling rate

        WHEN: use the rotated_wind() method with PF type and custom sampling rate
        THEN: verify that the returned InputFileConfig object has the correct parameters
        """
        config = InputFileConfig.rotated_wind(rot_type="pf", sampling_rate_ms=100)
        
        # verify correct sampling rate
        assert config.sampling_rate_ms == 100

        # expected column names
        expected_file_cols = ["TIMESTAMP", "u", "v", "w", "Ts", "gamma"]
        assert list(config.cols.keys()) == expected_file_cols

        # verify correct mapping to database columns
        assert config.cols["TIMESTAMP"] == ('datetime64[ms]', "datetime", "DATETIME PRIMARY KEY")
        assert config.cols["u"] == (float, "u", "DECIMAL(6,3)")
        assert config.cols["v"] == (float, "v", "DECIMAL(6,3)")
        assert config.cols["w"] == (float, "w", "DECIMAL(6,3)")
        assert config.cols["Ts"] == (float, "ts", "DECIMAL(6,3)")
        assert config.cols["gamma"] == (float, "gamma", "DECIMAL(5,2)")

    def test_defaultStatus(self):
        """
        Test default status configuration

        WHEN: use the defaultStatus() method with default parameters
        THEN: verify that the returned InputFileConfig object has the correct parameters
        """
        config = InputFileConfig.defaultStatus()

        # verify correct sampling rate
        assert config.sampling_rate_ms == 1000

        # expected column names
        expected_file_cols = ["TIMESTAMP", "BattV_Min", "CardStatus"]
        assert list(config.cols.keys()) == expected_file_cols
        
        # verify correct mapping to database columns
        assert config.cols["TIMESTAMP"] == ('datetime64[ms]', "datetime", "DATETIME PRIMARY KEY")
        assert config.cols["BattV_Min"] == (float, "battVmin", "DECIMAL(5,2)")
        assert config.cols["CardStatus"] == (str, "card_status", "VARCHAR(10)")

    def test_Status_config(self):
        """
        Test status config and custom sampling rate

        WHEN: use the defaultStatus() method with custom parameters
        THEN: verify that the returned InputFileConfig object has the correct parameters
        """
        config = InputFileConfig.defaultStatus(sampling_rate_ms=500)

        # verify correct sampling rate
        assert config.sampling_rate_ms == 500

        # expected column names
        expected_file_cols = ["TIMESTAMP", "BattV_Min", "CardStatus"]
        assert list(config.cols.keys()) == expected_file_cols
        
        # verify correct mapping to database columns
        assert config.cols["TIMESTAMP"] == ('datetime64[ms]', "datetime", "DATETIME PRIMARY KEY")
        assert config.cols["BattV_Min"] == (float, "battVmin", "DECIMAL(5,2)")
        assert config.cols["CardStatus"] == (str, "card_status", "VARCHAR(10)")

    def test_getters(self, dummy_input_config):
        """
        Test getter methods of InputFileConfig class.

        GIVEN: a fictitious InputFileConfig object
        WHEN: use getter methods to retrieve object attributes
        THEN: verify that the getters return the correct values for the inserted configuration
        """
        
        # test get_file_cols_name, give input file column names
        assert dummy_input_config.get_file_cols_name() == ["col_A", "col_B"]
        
        # test get_file_cols_type, first index of the tuple
        file_types = dummy_input_config.get_file_cols_type()
        assert file_types["col_A"] == int
        assert file_types["col_B"] == float
        
        # test get_table_cols_name, second index of the tuple
        table_cols = dummy_input_config.get_table_cols_name()
        assert table_cols["col_A"] == "db_col_A"
        assert table_cols["col_B"] == "db_col_B"
        
        # test get_table_cols_type, third index of the tuple
        table_types = dummy_input_config.get_table_cols_type()
        assert table_types["db_col_A"] == "INTEGER"
        assert table_types["db_col_B"] == "DECIMAL(5,2)"

    def test_gillwindmaster_invalid_parameters(self):
        """
        Test gillwindmaster() method with invalid parameters

        WHEN: use the gillwindmaster() method with wrong parameters
        THEN: verify that the method raises the correct exceptions
        """
        # n_level is zero
        with pytest.raises(ValueError, match="non zero and positive"):
            InputFileConfig.gillwindmaster(n_level=0)

        # n_level is negative
        with pytest.raises(ValueError, match="non zero and positive"):
            InputFileConfig.gillwindmaster(n_level=-1)

        # n_level is a string
        with pytest.raises(TypeError, match="must be an int"):
            InputFileConfig.gillwindmaster(n_level="1")

        # n_level is a float
        with pytest.raises(TypeError, match="must be an int"):
            InputFileConfig.gillwindmaster(n_level=1.5)

    def test_rotated_wind_invalid_type(self):
        """
        Test rotated_wind method with invalid rotation type

        WHEN: use the rotated_wind() method with an invalid rotation type
        THEN: verify that the method raises a ValueError with the correct message
        """
        with pytest.raises(ValueError, match="must be 'pf' or 'dr'"):
            InputFileConfig.rotated_wind(rot_type="invalid_rotation")


class TestStationConfig:

    def test_getters(self, dummy_input_config):
        """
        Test getter methods of StationConfig.

        GIVEN: a StationConfig initialized with the constructor
        WHEN: use a getter method to retrieve the InputFileConfig object, database table name, and input file name
        THEN: verify that getters return the correct values for the inserted configuration
        """
        # dict containing the input file configuration for the station
        dict_config = {
            "config_1": dummy_input_config
        }
        # create a StationConfig object using the constructor 
        station = StationConfig(
            station_name="Test Station",
            station_id="123",
            db_table_names={"config_1": "table_test"},
            input_files_name={"config_1": "*test*"},
            input_files_config=dict_config
        )

        # verify that the getters return the correct values
        assert station.get_input_config("config_1") is dummy_input_config
        assert station.get_table_name("config_1") == "table_test"
        assert station.get_input_file_name("config_1") == "*test*"

        # test get_configs method
        all_configs = station.get_configs()
        assert all_configs == dict_config
        assert all_configs["config_1"] is dummy_input_config

    def test_add_input_file_config(self, dummy_input_config):
        """
        Test add_input_file_config method of StationConfig class.

        GIVEN: a StationConfig initialized with the constructor
        WHEN: use add_input_file_config to insert a new InputFileConfig object
        THEN: verify that the new configuration is correctly inserted
        """
        station = StationConfig(station_name="Test Station", station_id="123")
        
        # insert input file config to station config
        station.add_input_file_config(
            config_id = "config_1",
            config = dummy_input_config,
            db_table_name = "table_test",
            input_files_name = "*test*"
        )

        # verify correct insertion of the configuration
        assert station.get_input_config("config_1") is dummy_input_config
        assert station.get_table_name("config_1") == "table_test"
        assert station.get_input_file_name("config_1") == "*test*"

    def test_getters_keyerror(self):
        """
        Test getter methods of StationConfig.

        GIVEN: a StationConfig initialized with the constructor with no configurations
        WHEN: use a getter method with a config_id that does not exist in the configuration
        THEN: verify that getters return KeyError
        """
        station = StationConfig(station_name="Test Station", station_id="123")

        with pytest.raises(KeyError):
            station.get_input_config("wrong_key")

        with pytest.raises(KeyError):
            station.get_table_name("wrong_key")

        with pytest.raises(KeyError):
            station.get_input_file_name("wrong_key")

    def test_get_config_empty(self):
        """
        Test get_configs() of StationConfig.

        GIVEN: a StationConfig initialized with the constructor with no configurations
        WHEN: use get_configs() method
        THEN: verify that return an empty dictionary
        """
        station = StationConfig(station_name="Test Station", station_id="123")

        assert station.get_configs() == {}

    def test_add_multiple_configs(self, dummy_input_config):
        """
        Test add_input_file_config method of StationConfig class for multiple configurations.

        GIVEN: a StationConfig initialized with the constructor
        WHEN: use add_input_file_config to insert multiple InputFileConfig objects with different config_id
        THEN: verify that all configurations are correctly inserted
        """
        station = StationConfig(station_name="Test Station", station_id="123")

        # insert multiple InputFileConfig objects with different config_id
        station.add_input_file_config("sonic", dummy_input_config, "table_sonic", "*sonic*")
        station.add_input_file_config("slow", dummy_input_config, "table_slow", "*slow*")

        # verify correct insertion of the configurations
        assert station.get_table_name("sonic") == "table_sonic"
        assert station.get_table_name("slow") == "table_slow"
        assert len(station.get_configs()) == 2

    def test_config_overwrite(self, dummy_input_config):
        """
        Test add_input_file_config method overwriting an existing configuration in StationConfig.

        GIVEN: a StationConfig with an existing configuration
        WHEN: use add_input_file_config with the same config_id but different db_table_name and input_files_name
        THEN: verify that the existing configuration is overwritten
        """
        station = StationConfig(station_name="Test Station", station_id="123")
        
        # pre-existing configuration
        station.add_input_file_config("sonic", dummy_input_config, "old_table", "*old*")
        
        # overwrite the existing configuration
        station.add_input_file_config("sonic", dummy_input_config, "new_table", "*new*")

        # check new values
        assert station.get_table_name("sonic") == "new_table"
        assert station.get_input_file_name("sonic") == "*new*"
        # check no duplicate exists
        assert len(station.get_configs()) == 1