# algo_trading_system/brokers/zerodha/kite_connect.py
import json
import os
from kiteconnect import KiteApp
from kiteconnect.exceptions import KiteException, TokenException, NetworkException, GeneralException, InputException
# Assuming config is accessible
try:
    from config import ZERODHA_API_KEY, ZERODHA_REQUEST_TOKEN, ZERODHA_API_SECRET, ZERODHA_ACCESS_TOKEN_FILE
except ImportError:
    print("Warning: Could not import config values directly in kite_connect.py. Ensure config is accessible.")
    ZERODHA_API_KEY = None 
    ZERODHA_REQUEST_TOKEN = None
    ZERODHA_API_SECRET = None
    ZERODHA_ACCESS_TOKEN_FILE = "logs/zerodha_access_token.json"


class KiteConnectAPI:
    def __init__(self, api_key=None, access_token=None, user_id_for_logging=None, logger=None):
        self.api_key = api_key if api_key else ZERODHA_API_KEY
        self.access_token = access_token
        self.kite = KiteApp(api_key=self.api_key) # Initialize KiteApp
        self.user_id = user_id_for_logging
        self.logger = logger
        self.access_token_file = ZERODHA_ACCESS_TOKEN_FILE

        os.makedirs(os.path.dirname(self.access_token_file), exist_ok=True)
        
        msg = f"KiteConnectAPI initialized for user {self.user_id if self.user_id else 'N/A'}"
        if self.logger: self.logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="INIT_KITE_API", quantity=0, price=0, order_type="-", status="SUCCESS", remarks=msg)
        else: print(msg)

    def _log_api_action(self, action, status, remarks="", symbol="-", exchange="-", data=None):
        if self.logger:
            log_remarks = f"{remarks}"
            if data: # Avoid logging excessively large data structures directly
                log_remarks += f" | Data: {str(data)[:200]}" # Log snippet of data
            self.logger.log_trade(
                strategy_name="SYSTEM_KITE_API", symbol=str(symbol), exchange=str(exchange),
                action=action, quantity=0, price=0, order_type="-",
                status=status, remarks=log_remarks
            )
        else:
            print(f"KITE_API_LOG: Action: {action}, Status: {status}, Symbol: {symbol}, Remarks: {remarks}, Data: {str(data)[:200] if data else 'N/A'}")

    def _save_access_token_data(self, token_data):
        try:
            with open(self.access_token_file, 'w') as f:
                json.dump(token_data, f)
            self._log_api_action("SAVE_TOKEN", "SUCCESS", f"Token saved to {self.access_token_file}")
        except Exception as e:
            self._log_api_action("SAVE_TOKEN", "FAILURE", f"Error saving token: {e}")

    def _load_access_token_data(self):
        if not os.path.exists(self.access_token_file):
            return None
        try:
            with open(self.access_token_file, 'r') as f:
                token_data = json.load(f)
            if 'access_token' in token_data and 'user_id' in token_data:
                self._log_api_action("LOAD_TOKEN", "SUCCESS", f"Token loaded from {self.access_token_file}")
                return token_data
            else:
                self._log_api_action("LOAD_TOKEN", "FAILURE", "Invalid token data structure.")
                return None
        except Exception as e:
            self._log_api_action("LOAD_TOKEN", "FAILURE", f"Error loading token: {e}")
            return None

    def get_login_url(self):
        return self.kite.login_url()

    def generate_session(self, request_token, api_secret):
        action = "GEN_SESSION"
        if not api_secret:
            self._log_api_action(action, "FAILURE", "API secret is required.")
            return None
        try:
            data = self.kite.generate_session(request_token, api_secret=api_secret)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)
            self.user_id = data.get("user_id", self.user_id)
            self._save_access_token_data(data)
            self._log_api_action(action, "SUCCESS", f"Session generated for user {self.user_id}.")
            return self.access_token
        except TokenException as te:
            self._log_api_action(action, "FAILURE", f"TokenException: {te}")
        except KiteException as ke: # Catch specific Kite exceptions
            self._log_api_action(action, "FAILURE", f"KiteException: {ke}")
        except Exception as e:
            self._log_api_action(action, "FAILURE", f"Generic error: {e}")
        return None

    def login(self, request_token_override=None):
        action = "LOGIN"
        loaded_token_data = self._load_access_token_data()
        if loaded_token_data and 'access_token' in loaded_token_data:
            try:
                self.kite.set_access_token(loaded_token_data['access_token'])
                profile = self.get_profile(force_fetch=True) # Test call
                if profile:
                    self.access_token = loaded_token_data['access_token']
                    self.user_id = profile.get("user_id", self.user_id)
                    self._log_api_action(action, "SUCCESS", f"Logged in as {self.user_id} using stored token.")
                    return self.access_token
                else:
                    self._log_api_action(action, "INFO", "Stored token invalid (profile fetch failed). New login needed.")
            except TokenException as te:
                self._log_api_action(action, "INFO", f"Stored token invalid/expired: {te}. New login needed.")
            except KiteException as ke:
                self._log_api_action(action, "INFO", f"KiteException validating stored token: {ke}. New login needed.")
            except Exception as e: # Catch any other error during validation
                self._log_api_action(action, "INFO", f"Error validating stored token: {e}. New login needed.")
        
        current_request_token = request_token_override if request_token_override else ZERODHA_REQUEST_TOKEN
        if not current_request_token:
            login_url = self.get_login_url()
            msg = (f"No valid session. Please login: {login_url}\n"
                   f"Set ZERODHA_REQUEST_TOKEN in config.py with the token from redirect URL, then restart.")
            self._log_api_action(action, "PROMPT", msg)
            return None
            
        api_secret = ZERODHA_API_SECRET
        if not api_secret:
            self._log_api_action(action, "FAILURE", "ZERODHA_API_SECRET not set.")
            return None
        return self.generate_session(current_request_token, api_secret)

    def get_profile(self, force_fetch=False): # force_fetch is for login validation
        action = "GET_PROFILE"
        if not self.access_token and not force_fetch: # Allow if force_fetch for initial login check
             self._log_api_action(action, "FAILURE", "Not logged in.")
             return None
        try:
            profile_data = self.kite.profile()
            self._log_api_action(action, "SUCCESS", f"Fetched profile for {profile_data.get('user_id')}", data=profile_data)
            return profile_data
        except TokenException as te:
            self._log_api_action(action, "TOKEN_ERROR", f"{te}")
            if force_fetch: raise # Re-raise for login validation to catch
        except KiteException as ke:
            self._log_api_action(action, "FAILURE", f"{ke}")
        except Exception as e:
            self._log_api_action(action, "FAILURE", f"Generic error: {e}")
        return None

    def get_margins(self):
        action = "GET_MARGINS"
        if not self.access_token: self._log_api_action(action, "FAILURE", "Not logged in."); return None
        try:
            margins_data = self.kite.margins()
            self._log_api_action(action, "SUCCESS", data=margins_data)
            return margins_data
        except KiteException as ke: self._log_api_action(action, "FAILURE", f"{ke}")
        except Exception as e: self._log_api_action(action, "FAILURE", f"Generic error: {e}")
        return None

    def get_positions(self):
        action = "GET_POSITIONS"
        if not self.access_token: self._log_api_action(action, "FAILURE", "Not logged in."); return None
        try:
            positions_data = self.kite.positions()
            self._log_api_action(action, "SUCCESS", data=positions_data)
            return positions_data
        except KiteException as ke: self._log_api_action(action, "FAILURE", f"{ke}")
        except Exception as e: self._log_api_action(action, "FAILURE", f"Generic error: {e}")
        return None

    def get_holdings(self):
        action = "GET_HOLDINGS"
        if not self.access_token: self._log_api_action(action, "FAILURE", "Not logged in."); return None
        try:
            holdings_data = self.kite.holdings()
            self._log_api_action(action, "SUCCESS", data=holdings_data)
            return holdings_data
        except KiteException as ke: self._log_api_action(action, "FAILURE", f"{ke}")
        except Exception as e: self._log_api_action(action, "FAILURE", f"Generic error: {e}")
        return None

    def place_order(self, variety, exchange, tradingsymbol, transaction_type, quantity,
                    product, order_type, price=None, trigger_price=None,
                    squareoff=None, stoploss=None, trailing_stoploss=None,
                    disclosed_quantity=None, tag=None):
        action = "PLACE_ORDER"
        if not self.access_token: self._log_api_action(action, "FAILURE", "Not logged in.", symbol=tradingsymbol); return None
        try:
            order_id = self.kite.place_order(
                variety=variety, exchange=exchange, tradingsymbol=tradingsymbol,
                transaction_type=transaction_type, quantity=quantity, product=product,
                order_type=order_type, price=price, trigger_price=trigger_price,
                squareoff=squareoff, stoploss=stoploss, trailing_stoploss=trailing_stoploss,
                disclosed_quantity=disclosed_quantity, tag=tag
            )
            self._log_api_action(action, "SUCCESS", f"Order placed: {order_id}", symbol=tradingsymbol, data={'order_id': order_id, 'type': transaction_type, 'qty': quantity})
            return order_id
        except InputException as ie: self._log_api_action(action, "INPUT_ERROR", f"{ie}", symbol=tradingsymbol)
        except TokenException as te: self._log_api_action(action, "TOKEN_ERROR", f"{te}", symbol=tradingsymbol)
        except KiteException as ke: self._log_api_action(action, "FAILURE", f"{ke}", symbol=tradingsymbol)
        except Exception as e: self._log_api_action(action, "FAILURE", f"Generic error: {e}", symbol=tradingsymbol)
        return None

    def modify_order(self, variety, order_id, parent_order_id=None, quantity=None, price=None,
                     order_type=None, trigger_price=None):
        action = "MODIFY_ORDER"
        if not self.access_token: self._log_api_action(action, "FAILURE", "Not logged in.", data={'order_id': order_id}); return None
        try:
            new_order_id = self.kite.modify_order(
                variety=variety, order_id=order_id, parent_order_id=parent_order_id,
                quantity=quantity, price=price, order_type=order_type, trigger_price=trigger_price
            )
            self._log_api_action(action, "SUCCESS", f"Order {order_id} modified to {new_order_id}", data={'order_id': order_id, 'new_id': new_order_id})
            return new_order_id
        except KiteException as ke: self._log_api_action(action, "FAILURE", f"{ke}", data={'order_id': order_id})
        except Exception as e: self._log_api_action(action, "FAILURE", f"Generic error: {e}", data={'order_id': order_id})
        return None

    def cancel_order(self, variety, order_id):
        action = "CANCEL_ORDER"
        if not self.access_token: self._log_api_action(action, "FAILURE", "Not logged in.", data={'order_id': order_id}); return None
        try:
            cancelled_order_id = self.kite.cancel_order(variety=variety, order_id=order_id)
            self._log_api_action(action, "SUCCESS", f"Order {order_id} cancelled.", data={'order_id': cancelled_order_id})
            return cancelled_order_id
        except KiteException as ke: self._log_api_action(action, "FAILURE", f"{ke}", data={'order_id': order_id})
        except Exception as e: self._log_api_action(action, "FAILURE", f"Generic error: {e}", data={'order_id': order_id})
        return None

    def get_order_history(self, order_id):
        action = "GET_ORDER_HISTORY"
        if not self.access_token: self._log_api_action(action, "FAILURE", "Not logged in.", data={'order_id': order_id}); return None
        try:
            order_history = self.kite.order_history(order_id=order_id)
            self._log_api_action(action, "SUCCESS", f"Fetched history for order {order_id}", data=order_history)
            return order_history
        except KiteException as ke: self._log_api_action(action, "FAILURE", f"{ke}", data={'order_id': order_id})
        except Exception as e: self._log_api_action(action, "FAILURE", f"Generic error: {e}", data={'order_id': order_id})
        return None
        
    def get_trades(self, order_id): # Get trades for a specific order
        action = "GET_TRADES_FOR_ORDER"
        if not self.access_token: self._log_api_action(action, "FAILURE", "Not logged in.", data={'order_id': order_id}); return None
        try:
            trades = self.kite.order_trades(order_id=order_id)
            self._log_api_action(action, "SUCCESS", f"Fetched trades for order {order_id}", data=trades)
            return trades
        except KiteException as ke: self._log_api_action(action, "FAILURE", f"{ke}", data={'order_id': order_id})
        except Exception as e: self._log_api_action(action, "FAILURE", f"Generic error: {e}", data={'order_id': order_id})
        return None


if __name__ == '__main__':
    print("Testing KiteConnectAPI Core Functionalities (manual steps required for login)...")
    
    class MockLogger: # Replace with actual logger if available
        def log_trade(self, **kwargs):
            print(f"LOG: {kwargs['action']} - {kwargs['status']} - {kwargs.get('remarks', '')} - Data: {str(kwargs.get('data'))[:100]}")

    mock_logger_instance = MockLogger()
    
    broker = KiteConnectAPI(api_key=ZERODHA_API_KEY, logger=mock_logger_instance)
    
    # --- Login ---
    # For first time run:
    # 1. Set ZERODHA_API_KEY, ZERODHA_API_SECRET in config.py
    # 2. Run this script. It will print a login URL.
    # 3. Open the URL, login, get the request_token from the redirect URL.
    # 4. Set ZERODHA_REQUEST_TOKEN in config.py with this token.
    # 5. Re-run the script.
    # For subsequent runs, it should use the stored access token.
    if not broker.access_token: # If login didn't happen during init (e.g. no stored token)
        print(f"Login URL (if needed): {broker.get_login_url()}")
        print("Ensure ZERODHA_REQUEST_TOKEN is set in config.py if this is the first login or token expired.")
        broker.login() # Will use ZERODHA_REQUEST_TOKEN from config if needed

    if broker.access_token:
        print("\n--- Login Successful ---")
        
        profile = broker.get_profile()
        # if profile: print(f"Profile: {profile.get('user_name')}")

        margins = broker.get_margins()
        # if margins: print(f"Margins (Equity Net): {margins.get('equity', {}).get('net')}")

        positions = broker.get_positions()
        # if positions: print(f"Positions (Day count): {len(positions.get('day', []))}, Net count: {len(positions.get('net', []))}")

        holdings = broker.get_holdings()
        # if holdings: print(f"Holdings count: {len(holdings)}")

        # --- Example: Placing a dummy order (Use with extreme caution, on a test account or paper trading if possible) ---
        # Ensure you understand the parameters and risks before uncommenting.
        # This is a LIMIT order for INFY which might not execute if price is far off.
        # variety='regular', exchange='NSE', tradingsymbol='INFY', transaction_type='BUY', 
        # quantity=1, product='CNC', order_type='LIMIT', price=100.00 # Deliberately low price for testing
        
        # print("\n--- Example Order Placement (Commented out by default) ---")
        # order_id = broker.place_order(
        #     variety='regular', exchange='NSE', tradingsymbol='INFY', 
        #     transaction_type='BUY', quantity=1, product='CNC', 
        #     order_type='LIMIT', price=100.00 # Use a price that won't execute for safety
        # )
        # if order_id:
        #     print(f"Test order placed with ID: {order_id}")
        #     order_details = broker.get_order_history(order_id)
            # if order_details: print(f"Order details for {order_id}: {order_details[-1].get('status') if order_details else 'N/A'}") # Get last status
            
            # Example: Cancel this test order
            # print(f"Attempting to cancel order: {order_id}")
            # cancelled_id = broker.cancel_order(variety='regular', order_id=order_id)
            # if cancelled_id:
            #     print(f"Cancel request successful for order: {cancelled_id}. Check status.")
            #     order_details_after_cancel = broker.get_order_history(order_id)
                # if order_details_after_cancel: print(f"Order status after cancel: {order_details_after_cancel[-1].get('status') if order_details_after_cancel else 'N/A'}")
        # else:
        #     print("Test order placement failed or was not attempted.")

    else:
        print("\n--- Login Failed ---")
        print("Please check API Key/Secret in config.py and ensure ZERODHA_REQUEST_TOKEN is correctly set for initial login.")
