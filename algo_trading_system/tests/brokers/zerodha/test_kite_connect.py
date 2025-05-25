# algo_trading_system/tests/brokers/zerodha/test_kite_connect.py
import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import json
import os

# Ensure the main project directory is in PYTHONPATH if running tests from 'tests' directory
# This might be needed depending on test runner configuration.
# import sys
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Import the class to be tested
from brokers.zerodha.kite_connect import KiteConnectAPI, TokenException, InputException # Import exceptions used

# Mock config values that would normally be imported from config.py
# This avoids direct dependency on the actual config.py file during tests
MOCK_CONFIG_ZERODHA_API_KEY = "test_api_key"
MOCK_CONFIG_ZERODHA_API_SECRET = "test_api_secret"
MOCK_CONFIG_ZERODHA_REQUEST_TOKEN = "test_request_token" # For when no file token exists
MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE = "logs/test_access_token.json"


# Patch the config variables at the module level where KiteConnectAPI is defined
@patch('brokers.zerodha.kite_connect.ZERODHA_API_KEY', MOCK_CONFIG_ZERODHA_API_KEY)
@patch('brokers.zerodha.kite_connect.ZERODHA_API_SECRET', MOCK_CONFIG_ZERODHA_API_SECRET)
@patch('brokers.zerodha.kite_connect.ZERODHA_REQUEST_TOKEN', MOCK_CONFIG_ZERODHA_REQUEST_TOKEN)
@patch('brokers.zerodha.kite_connect.ZERODHA_ACCESS_TOKEN_FILE', MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE)
@patch('brokers.zerodha.kite_connect.os.makedirs') # Mock makedirs
class TestKiteConnectAPIWithActualLogic(unittest.TestCase):

    def setUp(self):
        # Clean up any potential token file from previous test runs
        # Ensure the directory for the mock token file exists for cleanup
        logs_dir = os.path.dirname(MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE)
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir) # Create 'logs' if it doesn't exist for test setup/teardown
            
        if os.path.exists(MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE):
            os.remove(MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE)
        
        # Mock logger can be simple or more complex if log outputs need to be asserted
        self.mock_logger = MagicMock()

    def tearDown(self):
        # Clean up token file created during tests
        if os.path.exists(MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE):
            os.remove(MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE)
        # Clean up the 'logs' directory if it was created by setUp for tests and is empty
        logs_dir = os.path.dirname(MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE)
        if os.path.exists(logs_dir) and not os.listdir(logs_dir):
            os.rmdir(logs_dir)


    @patch('brokers.zerodha.kite_connect.KiteApp')
    def test_01_initialization(self, MockKiteAppClass, mock_makedirs_call):
        mock_kite_instance = MockKiteAppClass.return_value
        api = KiteConnectAPI(api_key="custom_key", logger=self.mock_logger)
        
        MockKiteAppClass.assert_called_once_with(api_key="custom_key")
        self.assertEqual(api.kite, mock_kite_instance)
        self.assertEqual(api.api_key, "custom_key")
        self.assertEqual(api.access_token_file, MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE)
        # makedirs is called by the module-level code in kite_connect.py for ZERODHA_ACCESS_TOKEN_FILE path,
        # and potentially again if a different path was used in constructor (not the case here).
        # The mock_makedirs_call here refers to the one patched for the class context.
        # The actual call to os.makedirs in __init__ uses the self.access_token_file path.
        mock_makedirs_call.assert_any_call(os.path.dirname(MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE), exist_ok=True)
        self.mock_logger.log_trade.assert_called() # Check if logger was called

    @patch('brokers.zerodha.kite_connect.KiteApp')
    def test_02_get_login_url(self, MockKiteAppClass, mock_makedirs_call):
        mock_kite_instance = MockKiteAppClass.return_value
        mock_kite_instance.login_url.return_value = "http://test.login.url"
        
        api = KiteConnectAPI(logger=self.mock_logger)
        login_url = api.get_login_url()
        
        self.assertEqual(login_url, "http://test.login.url")
        mock_kite_instance.login_url.assert_called_once()

    @patch('brokers.zerodha.kite_connect.KiteApp')
    def test_03_generate_session_success(self, MockKiteAppClass, mock_makedirs_call):
        mock_kite_instance = MockKiteAppClass.return_value
        mock_session_data = {
            "access_token": "new_access_token",
            "public_token": "new_public_token",
            "user_id": "testuser123"
        }
        mock_kite_instance.generate_session.return_value = mock_session_data
        
        api = KiteConnectAPI(logger=self.mock_logger)
        
        with patch('builtins.open', mock_open()) as mocked_file_open:
            access_token = api.generate_session("test_req_token", "test_secret")
        
        self.assertEqual(access_token, "new_access_token")
        self.assertEqual(api.access_token, "new_access_token")
        self.assertEqual(api.user_id, "testuser123")
        mock_kite_instance.generate_session.assert_called_once_with("test_req_token", api_secret="test_secret")
        mock_kite_instance.set_access_token.assert_called_once_with("new_access_token")
        
        mocked_file_open.assert_called_once_with(MOCK_CONFIG_ZERODHA_ACCESS_TOKEN_FILE, 'w')
        handle = mocked_file_open()
        handle.write.assert_called_once_with(json.dumps(mock_session_data))
        self.mock_logger.log_trade.assert_any_call(action='GEN_SESSION', status='SUCCESS', remarks='Session generated for user testuser123.', strategy_name='SYSTEM_KITE_API', symbol='-', exchange='-', quantity=0, price=0, order_type='-')


    @patch('brokers.zerodha.kite_connect.KiteApp')
    def test_04_login_no_stored_token_uses_request_token_from_config(self, MockKiteAppClass, mock_makedirs_call):
        mock_kite_instance = MockKiteAppClass.return_value
        with patch('brokers.zerodha.kite_connect.os.path.exists', return_value=False):
            mock_session_data = {"access_token": "generated_token", "user_id": "userXYZ"}
            mock_kite_instance.generate_session.return_value = mock_session_data
            mock_kite_instance.profile.return_value = {"user_id": "userXYZ", "user_name": "Test User"}

            api = KiteConnectAPI(logger=self.mock_logger)
            with patch('builtins.open', mock_open()):
                 access_token = api.login()

        self.assertEqual(access_token, "generated_token")
        mock_kite_instance.generate_session.assert_called_once_with(MOCK_CONFIG_ZERODHA_REQUEST_TOKEN, api_secret=MOCK_CONFIG_ZERODHA_API_SECRET)
        self.mock_logger.log_trade.assert_any_call(action='LOGIN', status='SUCCESS', remarks='Logged in as userXYZ using stored token.', strategy_name='SYSTEM_KITE_API', symbol='-', exchange='-', quantity=0, price=0, order_type='-')


    @patch('brokers.zerodha.kite_connect.KiteApp')
    def test_05_login_with_stored_valid_token(self, MockKiteAppClass, mock_makedirs_call):
        mock_kite_instance = MockKiteAppClass.return_value
        stored_token_data = {
            "access_token": "stored_access_token",
            "public_token": "stored_public_token",
            "user_id": "storedUser"
        }
        with patch('brokers.zerodha.kite_connect.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(stored_token_data))):
            
            mock_kite_instance.profile.return_value = {"user_id": "storedUser", "user_name": "Stored Test User"}
            
            api = KiteConnectAPI(logger=self.mock_logger)
            access_token = api.login()

        self.assertEqual(access_token, "stored_access_token")
        self.assertEqual(api.user_id, "storedUser")
        mock_kite_instance.set_access_token.assert_called_with("stored_access_token")
        mock_kite_instance.profile.assert_called_once() 
        mock_kite_instance.generate_session.assert_not_called() 
        self.mock_logger.log_trade.assert_any_call(action='LOGIN', status='SUCCESS', remarks='Logged in as storedUser using stored token.', strategy_name='SYSTEM_KITE_API', symbol='-', exchange='-', quantity=0, price=0, order_type='-')

    @patch('brokers.zerodha.kite_connect.KiteApp')
    def test_06_login_with_stored_invalid_token_then_new_login(self, MockKiteAppClass, mock_makedirs_call):
        mock_kite_instance = MockKiteAppClass.return_value
        stored_token_data = {"access_token": "expired_token", "user_id": "expiredUser"}

        with patch('brokers.zerodha.kite_connect.os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(stored_token_data))) as mock_file:
            
            mock_kite_instance.profile.side_effect = [
                TokenException("Token expired"), 
                {"user_id": "newUser", "user_name": "New User"}
            ]
            
            new_session_data = {"access_token": "new_valid_token", "user_id": "newUser"}
            mock_kite_instance.generate_session.return_value = new_session_data
            
            api = KiteConnectAPI(logger=self.mock_logger)
            # Use request_token_override for this specific test scenario
            access_token = api.login(request_token_override="new_req_token_for_test") 

        self.assertEqual(access_token, "new_valid_token")
        # generate_session called with the override token
        mock_kite_instance.generate_session.assert_called_once_with("new_req_token_for_test", api_secret=MOCK_CONFIG_ZERODHA_API_SECRET)
        self.assertEqual(mock_kite_instance.set_access_token.call_count, 2) 
        mock_kite_instance.set_access_token.assert_any_call("expired_token")
        mock_kite_instance.set_access_token.assert_any_call("new_valid_token")

    def _setup_api_with_valid_login(self, mock_kite_instance):
        api = KiteConnectAPI(logger=self.mock_logger)
        api.access_token = "fake_access_token" 
        api.kite = mock_kite_instance 
        # Ensure kite instance within api object is correctly set up for profile calls
        # This is crucial if get_profile is called internally by other methods being tested.
        mock_kite_instance.profile.return_value = {"user_id": "fakeUser", "user_name": "Fake User"}
        return api

    @patch('brokers.zerodha.kite_connect.KiteApp')
    def test_07_get_profile_success(self, MockKiteAppClass, mock_makedirs_call):
        mock_kite_instance = MockKiteAppClass.return_value
        api = self._setup_api_with_valid_login(mock_kite_instance) # api.kite is now mock_kite_instance
        
        expected_profile = {"user_name": "Test User", "email": "test@example.com"}
        # Configure the return value of profile on the instance of KiteApp used by api
        api.kite.profile.return_value = expected_profile 
        
        profile = api.get_profile()
        
        self.assertEqual(profile, expected_profile)
        api.kite.profile.assert_called_once()


    @patch('brokers.zerodha.kite_connect.KiteApp')
    def test_08_get_positions_success(self, MockKiteAppClass, mock_makedirs_call):
        mock_kite_instance = MockKiteAppClass.return_value
        api = self._setup_api_with_valid_login(mock_kite_instance)
        
        expected_positions = {"day": [], "net": [{"tradingsymbol": "INFY"}]}
        api.kite.positions.return_value = expected_positions # Configure on the instance
        
        positions = api.get_positions()
        
        self.assertEqual(positions, expected_positions)
        api.kite.positions.assert_called_once()

    @patch('brokers.zerodha.kite_connect.KiteApp')
    def test_09_place_order_success(self, MockKiteAppClass, mock_makedirs_call):
        mock_kite_instance = MockKiteAppClass.return_value
        api = self._setup_api_with_valid_login(mock_kite_instance)
        
        api.kite.place_order.return_value = "test_order_id_123" # Configure on the instance
        
        order_params = {
            "variety": "regular", "exchange": "NSE", "tradingsymbol": "INFY",
            "transaction_type": "BUY", "quantity": 1, "product": "CNC",
            "order_type": "LIMIT", "price": 100.0
        }
        order_id = api.place_order(**order_params, tag="testtag")
        
        self.assertEqual(order_id, "test_order_id_123")
        api.kite.place_order.assert_called_once_with(
            variety='regular', exchange='NSE', tradingsymbol='INFY', 
            transaction_type='BUY', quantity=1, product='CNC', 
            order_type='LIMIT', price=100.0, trigger_price=None, 
            squareoff=None, stoploss=None, trailing_stoploss=None, 
            disclosed_quantity=None, tag='testtag'
        )
        
    @patch('brokers.zerodha.kite_connect.KiteApp')
    def test_10_api_method_exception_handling(self, MockKiteAppClass, mock_makedirs_call):
        mock_kite_instance = MockKiteAppClass.return_value
        api = self._setup_api_with_valid_login(mock_kite_instance)

        api.kite.profile.side_effect = TokenException("API token error")
        profile = api.get_profile()
        self.assertIsNone(profile)
        self.mock_logger.log_trade.assert_any_call(action='GET_PROFILE', status='TOKEN_ERROR', remarks='API token error', strategy_name='SYSTEM_KITE_API', symbol='-', exchange='-', quantity=0, price=0, order_type='-')

        api.kite.place_order.side_effect = InputException("Invalid input")
        order_id = api.place_order(variety="regular", exchange="NSE", tradingsymbol="SBIN", 
                                   transaction_type="BUY", quantity=1, product="MIS", order_type="MARKET")
        self.assertIsNone(order_id)
        self.mock_logger.log_trade.assert_any_call(action='PLACE_ORDER', status='INPUT_ERROR', remarks='Invalid input', strategy_name='SYSTEM_KITE_API', symbol='SBIN', exchange='NSE', quantity=0, price=0, order_type='-')

if __name__ == '__main__':
    unittest.main()
