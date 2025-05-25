# algo_trading_system/brokers/upstox/upstox_api.py
import os
import json
import webbrowser
from urllib.parse import urlparse, parse_qs
import upstox_client
from upstox_client.rest import ApiException

# Attempt to import configurations, ensure they are defined in config.py
try:
    from ...config import ( # Relative import from algo_trading_system.config
        UPSTOX_API_KEY, UPSTOX_API_SECRET, UPSTOX_REDIRECT_URI,
        UPSTOX_ACCESS_TOKEN_FILE # e.g., "logs/upstox_access_token.json"
    )
except ImportError:
    print("ERROR: Upstox configurations (UPSTOX_API_KEY, etc.) not found in config.py. Please update config.py.")
    # Define fallbacks if running script directly or for linting, but real execution needs config
    UPSTOX_API_KEY = "YOUR_UPSTOX_API_KEY_HERE"
    UPSTOX_API_SECRET = "YOUR_UPSTOX_API_SECRET_HERE"
    UPSTOX_REDIRECT_URI = "YOUR_UPSTOX_REDIRECT_URI_HERE"
    UPSTOX_ACCESS_TOKEN_FILE = "logs/upstox_access_token.json"


class UpstoxAPI:
    API_VERSION = "2.0" # As seen in documentation

    def __init__(self, api_key=None, api_secret=None, redirect_uri=None, logger=None):
        self.api_key = api_key or UPSTOX_API_KEY
        self.api_secret = api_secret or UPSTOX_API_SECRET
        self.redirect_uri = redirect_uri or UPSTOX_REDIRECT_URI
        self.access_token = None
        self.user_id = None # Or similar identifier from Upstox profile
        self.logger = logger
        self.access_token_file = UPSTOX_ACCESS_TOKEN_FILE

        os.makedirs(os.path.dirname(self.access_token_file), exist_ok=True)
        
        # Configure OAuth2 access token for authorization: default
        # The Upstox SDK might handle this configuration internally when api_client is created.
        # We need to ensure the SDK's api_client is configured with the access token once obtained.
        self.api_client = upstox_client.ApiClient() # Default client

        msg = f"UpstoxAPI initialized. API Key: {'Set' if self.api_key else 'Not Set'}"
        self._log_api_action("INIT_UPSTOX_API", "SUCCESS", msg)

    def _log_api_action(self, action, status, remarks="", symbol="-", exchange="-", data=None):
        log_msg = f"UPSTOX_API_LOG: Action: {action}, Status: {status}, Symbol: {symbol}, Remarks: {remarks}"
        if data: log_msg += f" | Data: {str(data)[:200]}"
        
        if self.logger:
            # Using existing TradeLogger structure - remarks was the variable name in KiteConnectAPI
            # but the method signature for TradeLogger.log_trade expects 'remarks'
            # Ensure consistency or map parameters correctly if TradeLogger changes
            log_remarks_for_tradelogger = remarks # Use the 'remarks' from method args
            if data: log_remarks_for_tradelogger += f" | Data: {str(data)[:200]}"

            self.logger.log_trade( 
                strategy_name="SYSTEM_UPSTOX_API", symbol=str(symbol), exchange=str(exchange),
                action=action, quantity=0, price=0, order_type="-",
                status=status, remarks=log_remarks_for_tradelogger # Pass the constructed remarks here
            )
        else:
            print(log_msg)

    def _save_access_token_data(self, token_data):
        try:
            # token_data from Upstox might directly be the access_token string or a dict
            # For consistency, let's save it as a dict similar to Zerodha if it's just the token string
            if isinstance(token_data, str): # If only token string is passed
                save_data = {'access_token': token_data, 'user_id': self.user_id}
            elif isinstance(token_data, dict) and 'access_token' in token_data:
                save_data = token_data
                if 'user_id' not in save_data and self.user_id:
                    save_data['user_id'] = self.user_id
            else:
                self._log_api_action("SAVE_TOKEN", "FAILURE", "Invalid token data format for saving.")
                return

            with open(self.access_token_file, 'w') as f:
                json.dump(save_data, f)
            self._log_api_action("SAVE_TOKEN", "SUCCESS", f"Token data saved to {self.access_token_file}")
        except Exception as e:
            self._log_api_action("SAVE_TOKEN", "FAILURE", f"Error saving token: {e}")

    def _load_access_token_data(self):
        if not os.path.exists(self.access_token_file):
            return None
        try:
            with open(self.access_token_file, 'r') as f:
                token_data = json.load(f)
            if 'access_token' in token_data: # Basic check
                self._log_api_action("LOAD_TOKEN", "SUCCESS", f"Token data loaded from {self.access_token_file}")
                return token_data
            else:
                self._log_api_action("LOAD_TOKEN", "FAILURE", "Invalid token data structure in file.")
                return None
        except Exception as e:
            self._log_api_action("LOAD_TOKEN", "FAILURE", f"Error loading token: {e}")
            return None

    def _set_sdk_access_token(self, access_token_str):
        """Configures the SDK's ApiClient with the obtained access token."""
        if access_token_str:
            self.access_token = access_token_str
            # This is how the Upstox SDK expects the token to be set on its configuration
            self.api_client.configuration.access_token = access_token_str 
            self._log_api_action("SET_SDK_TOKEN", "SUCCESS", "Access token configured in SDK.")
        else:
            self._log_api_action("SET_SDK_TOKEN", "FAILURE", "Attempted to set empty access token.")


    def get_login_url(self):
        """Generates the authorization URL for the user to grant permissions."""
        # The SDK's LoginApi might have a method or the URL structure is fixed.
        # From docs: https://api.upstox.com/v2/login/authorization/dialog?client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&response_type=code
        # The SDK might not directly provide this URL generation, so we construct it.
        auth_url = (
            f"https://api-v2.upstox.com/login/authorization/dialog?"
            f"client_id={self.api_key}&redirect_uri={self.redirect_uri}&response_type=code"
            # Optional: state parameter for security
        )
        self._log_api_action("GET_LOGIN_URL", "INFO", f"Login URL: {auth_url}")
        return auth_url

    def generate_session(self, auth_code):
        """
        Generates an access token using the authorization code.
        Corresponds to: POST /login/authorization/token
        """
        action = "GEN_SESSION"
        if not self.api_secret:
            self._log_api_action(action, "FAILURE", "API secret is required.")
            return None
        
        login_api = upstox_client.LoginApi(self.api_client)
        try:
            # Parameters for token API:
            # api_version, code, client_id, client_secret, redirect_uri, grant_type
            api_response = login_api.token(
                api_version=self.API_VERSION,
                code=auth_code,
                client_id=self.api_key,
                client_secret=self.api_secret,
                redirect_uri=self.redirect_uri,
                grant_type='authorization_code' 
            )
            
            # api_response is expected to be an object, e.g., TokenResponse
            # The actual access token is usually a field like api_response.access_token
            if hasattr(api_response, 'access_token') and api_response.access_token:
                self.access_token = api_response.access_token
                self._set_sdk_access_token(self.access_token) # Configure SDK with this token
                
                # Try to get user_id or some profile info to store with token
                # profile = self.get_profile() # This might be too early if token not fully set
                # self.user_id = profile.get('user_id') if profile else None
                
                # Save the full response or parts of it
                token_data_to_save = {
                    'access_token': self.access_token,
                    # Include other relevant fields from api_response if needed (e.g. expires_in, refresh_token)
                    'email': getattr(api_response, 'email', None),
                    'user_name': getattr(api_response, 'user_name', None), # Example fields
                    'user_id': getattr(api_response, 'user_id', None)
                }
                self.user_id = token_data_to_save.get('user_id')
                self._save_access_token_data(token_data_to_save)
                self._log_api_action(action, "SUCCESS", f"Session generated. User: {self.user_id or 'N/A'}")
                return self.access_token
            else:
                self._log_api_action(action, "FAILURE", f"Failed to get access_token from response: {api_response}")
                return None

        except ApiException as e:
            self._log_api_action(action, "API_EXCEPTION", f"Upstox API Exception generating session: {e.status} - {e.reason} - {e.body}")
        except Exception as e:
            self._log_api_action(action, "FAILURE", f"Generic error generating session: {e}")
        return None

    def login(self, auth_code_override=None):
        """
        Attempts to log in. Tries to load a stored access token first.
        If no valid stored token, and auth_code_override is provided, uses it.
        Otherwise, user needs to go through the manual auth flow (get_login_url, then provide auth_code).
        """
        action = "LOGIN"
        loaded_token_data = self._load_access_token_data()
        if loaded_token_data and 'access_token' in loaded_token_data:
            self.access_token = loaded_token_data['access_token']
            self.user_id = loaded_token_data.get('user_id')
            self._set_sdk_access_token(self.access_token)
            
            # Test the token with a simple API call, e.g., get_profile()
            try:
                if self.get_profile(force_fetch=True): # force_fetch to bypass initial access_token check in get_profile
                    self._log_api_action(action, "SUCCESS", f"Logged in as {self.user_id or 'N/A'} using stored token.")
                    return self.access_token
            except ApiException as e: # Catch potential 401 from get_profile if token is bad
                 if e.status == 401:
                    self._log_api_action(action, "INFO", f"Stored token seems invalid/expired (401 from get_profile). New login needed. Error: {e.body}")
                 else: # Other API error during validation
                    self._log_api_action(action, "API_EXCEPTION", f"API error validating stored token with get_profile: {e.body}")
                 self.access_token = None # Clear invalid token
                 self.api_client.configuration.access_token = None
            except Exception as e: # Generic error during validation
                 self._log_api_action(action, "FAILURE", f"Generic error validating stored token with get_profile: {e}")
                 self.access_token = None # Clear invalid token
                 self.api_client.configuration.access_token = None


        if auth_code_override:
            self._log_api_action(action, "INFO", f"Attempting login with provided auth_code.")
            return self.generate_session(auth_code_override)
        else:
            # No stored token, no override code - user needs to do the auth flow.
            # main.py will handle getting the auth_code from user after they visit get_login_url()
            self._log_api_action(action, "PROMPT_AUTH", "No valid session. User needs to authorize via URL and provide auth_code.")
            return None # Indicate that auth_code is needed

    def get_profile(self, force_fetch=False):
        action = "GET_PROFILE"
        if not self.access_token and not force_fetch:
            # If called internally for validation (force_fetch=True), this check is skipped.
            self._log_api_action(action, "FAILURE", "Not logged in (no access token).")
            return None
        
        user_api = upstox_client.UserApi(self.api_client)
        try:
            # The SDK method for get_profile might be like user_api.get_profile(api_version)
            profile_data_response = user_api.get_profile(self.API_VERSION) # This is GetProfileResponse
            
            # Access data using .data attribute as per Upstox SDK examples
            # The actual user_id field might differ, adjust based on SDK response object
            if hasattr(profile_data_response, 'data'):
                profile_data = profile_data_response.data
                self.user_id = getattr(profile_data, 'user_id', self.user_id) # Update user_id if available
                self._log_api_action(action, "SUCCESS", f"Fetched profile for {self.user_id}", data=profile_data.to_dict() if hasattr(profile_data, 'to_dict') else str(profile_data))
                return profile_data.to_dict() if hasattr(profile_data, 'to_dict') else profile_data
            else:
                self._log_api_action(action, "FAILURE", "Profile data not found in API response.", data=str(profile_data_response))
                return None
        except ApiException as e:
            self._log_api_action(action, "API_EXCEPTION", f"Upstox API Exception getting profile: {e.status} - {e.reason} - {e.body}")
            if e.status == 401: # Unauthorized, likely bad token
                raise # Re-raise for login validation to catch
        except Exception as e:
            self._log_api_action(action, "FAILURE", f"Generic error getting profile: {e}")
        return None

    # --- Placeholder methods for other functionalities ---
    # These need to be implemented using the Upstox SDK's specific Api classes and methods.

    def get_funds_and_margins(self, segment=None): # segment e.g. 'equity', 'commodity'
        action = "GET_FUNDS_MARGINS"
        if not self.access_token: self._log_api_action(action, "FAILURE", "Not logged in."); return None
        # Example: portfolio_api = upstox_client.PortfolioApi(self.api_client)
        # portfolio_api.get_portfolio_fund_margin(self.API_VERSION, segment=segment)
        self._log_api_action(action, "NOT_IMPLEMENTED", "Get Funds & Margins not implemented yet.")
        return {"error": "Not implemented"}

    def get_positions(self):
        action = "GET_POSITIONS"
        if not self.access_token:
            self._log_api_action(action, "FAILURE", "Not logged in (no access token).")
            return None # Or an empty structure matching expected output: {'net': [], 'day': []}
        
        portfolio_api = upstox_client.PortfolioApi(self.api_client)
        try:
            # The Upstox API distinguishes between short-term/day positions and long-term/delivery.
            # get_positions() in SDK usually refers to day/short-term positions.
            # The API endpoint is /portfolio/short-term-positions
            api_response = portfolio_api.get_positions(api_version=self.API_VERSION)
            
            # Process api_response (should be GetPositionResponse object)
            # The goal is to return a dictionary similar to Zerodha's: {'net': [...], 'day': [...]}
            # Upstox's GetPositionResponse.data is a list of PositionData objects.
            # These are typically day positions. For net positions, it might be the same or require combining with holdings.
            # For simplicity, let's assume these are "day" positions and also "net" for intraday products.
            
            processed_positions_day = []
            if api_response and hasattr(api_response, 'data') and api_response.data:
                for pos in api_response.data:
                    processed_positions_day.append({
                        'tradingsymbol': getattr(pos, 'tradingsymbol', None) or getattr(pos, 'trading_symbol', None), # SDK might use either
                        'exchange': getattr(pos, 'exchange', None),
                        'instrument_token': getattr(pos, 'instrument_token', None),
                        'product': getattr(pos, 'product', None),
                        'quantity': int(getattr(pos, 'quantity', 0)),
                        'average_price': float(getattr(pos, 'average_price', 0.0)),
                        'last_price': float(getattr(pos, 'last_price', 0.0)),
                        'pnl': float(getattr(pos, 'pnl', 0.0)), # Realised P&L might be here for closed day positions
                        'unrealised_pnl': float(getattr(pos, 'unrealised_profit', 0.0)), # Or similar field for open positions
                        'value': float(getattr(pos, 'value', 0.0)), # Market value
                        # Add other relevant fields if available and map to Zerodha-like fields if desired
                        'day_buy_quantity': int(getattr(pos, 'day_buy_quantity', 0)),
                        'day_sell_quantity': int(getattr(pos, 'day_sell_quantity', 0)),
                        'day_buy_price': float(getattr(pos, 'day_buy_price', 0.0)),
                        'day_sell_price': float(getattr(pos, 'day_sell_price', 0.0)),
                    })
            
            # For Upstox, "net" positions often mean a combination of day trades and holdings.
            # The /portfolio/short-term-positions endpoint gives intraday and ST (CNC) trades for the day.
            # True "net" positions (like holdings) are from get_holdings().
            # For consistency with Zerodha's output where 'net' includes all, and 'day' is intraday specific,
            # we will return short-term-positions as 'day'. 'net' will be more complex if we need to combine.
            # For now, let's keep it simple: what get_positions returns will be our 'day' and also 'net' for now.
            # A more accurate 'net' would require combining with holdings if the position is not intraday.
            
            self._log_api_action(action, "SUCCESS", f"Fetched {len(processed_positions_day)} positions.", data=api_response.to_dict() if hasattr(api_response, 'to_dict') else str(api_response))
            return {'net': processed_positions_day, 'day': processed_positions_day} # Simplification for now

        except ApiException as e:
            self._log_api_action(action, "API_EXCEPTION", f"Upstox API Exception getting positions: {e.status} - {e.reason} - {e.body}")
        except Exception as e:
            self._log_api_action(action, "FAILURE", f"Generic error getting positions: {e}")
        return {'net': [], 'day': []} # Return empty structure on failure

    def get_holdings(self):
        action = "GET_HOLDINGS"
        if not self.access_token:
            self._log_api_action(action, "FAILURE", "Not logged in (no access token).")
            return None # Or an empty list: []
        
        portfolio_api = upstox_client.PortfolioApi(self.api_client)
        try:
            # API endpoint is /portfolio/long-term-holdings
            api_response = portfolio_api.get_holdings(api_version=self.API_VERSION)
            
            # Process api_response (should be GetHoldingsResponse object)
            # GetHoldingsResponse.data is a list of HoldingsData objects.
            processed_holdings = []
            if api_response and hasattr(api_response, 'data') and api_response.data:
                for holding in api_response.data:
                    processed_holdings.append({
                        'tradingsymbol': getattr(holding, 'tradingsymbol', None) or getattr(holding, 'trading_symbol', None),
                        'exchange': getattr(holding, 'exchange', None),
                        'instrument_token': getattr(holding, 'instrument_token', None),
                        'product': getattr(holding, 'product', 'CNC'), # Holdings are typically CNC
                        'quantity': int(getattr(holding, 'quantity', 0)),
                        'average_price': float(getattr(holding, 'average_price', 0.0)),
                        'last_price': float(getattr(holding, 'last_price', 0.0)),
                        'close_price': float(getattr(holding, 'close_price', 0.0)), # Previous day's close
                        # Add other relevant fields
                        'isin': getattr(holding, 'isin', None),
                    })
            
            self._log_api_action(action, "SUCCESS", f"Fetched {len(processed_holdings)} holdings.", data=api_response.to_dict() if hasattr(api_response, 'to_dict') else str(api_response))
            return processed_holdings # Returns a list of holdings directly

        except ApiException as e:
            self._log_api_action(action, "API_EXCEPTION", f"Upstox API Exception getting holdings: {e.status} - {e.reason} - {e.body}")
        except Exception as e:
            self._log_api_action(action, "FAILURE", f"Generic error getting holdings: {e}")
        return [] # Return empty list on failure
        
    def place_order(self, 
                       instrument_token: str, # Upstox uses instrument_token directly
                       quantity: int,
                       product: str, # 'D' (Delivery), 'I' (Intraday), 'CO' (Cover), 'BO' (Bracket), 'E' (Margin Plus)
                       order_type: str, # MARKET, LIMIT, SL, SL-M
                       transaction_type: str, # BUY, SELL
                       price: float = 0.0, # Required for LIMIT and SL orders
                       trigger_price: float = 0.0, # Required for SL, SL-M orders
                       disclosed_quantity: int = 0,
                       validity: str = 'DAY', # DAY, IOC
                       tag: str = None, # Optional tag for order
                       is_amo: bool = False 
                      ):
           action = "PLACE_ORDER"
           if not self.access_token:
               self._log_api_action(action, "FAILURE", "Not logged in.", symbol=instrument_token)
               return None
           
           order_api = upstox_client.OrderApi(self.api_client)
           
           # Map our product codes if necessary, or expect direct Upstox codes
           # Zerodha: MIS, CNC. Upstox: I, D, CO, BO, E etc.
           # For now, assume product is passed as Upstox expected code.
           
           # Instrument token format for Upstox: EXCHANGE|TRADINGSYMBOL (e.g., NSE_EQ|INEJ927K01017)
           # The caller needs to provide this. We might need a helper to get this from symbol/exchange later.

           try:
               body = upstox_client.PlaceOrderRequest(
                   quantity=quantity,
                   product=product.upper(), # Ensure it's uppercase as per Upstox examples
                   validity=validity.upper(),
                   price=price,
                   tag=tag if tag else "AlgoTrade", # Default tag
                   instrument_token=instrument_token,
                   order_type=order_type.upper(),
                   transaction_type=transaction_type.upper(),
                   disclosed_quantity=disclosed_quantity,
                   trigger_price=trigger_price,
                   is_amo=is_amo
               )
               
               api_response = order_api.place_order(body, api_version=self.API_VERSION)
               # Response should be PlaceOrderResponse, containing order_id
               order_id = getattr(api_response, 'data', {}).get('order_id') if hasattr(api_response, 'data') else None

               if order_id:
                   self._log_api_action(action, "SUCCESS", f"Order placed: {order_id}", symbol=instrument_token, data={'order_id': order_id, 'type': transaction_type, 'qty': quantity})
                   return order_id
               else:
                   self._log_api_action(action, "FAILURE", "Order placement failed, no order_id in response.", symbol=instrument_token, data=api_response.to_dict() if hasattr(api_response, 'to_dict') else str(api_response))
                   return None
           except ApiException as e:
               self._log_api_action(action, "API_EXCEPTION", f"Upstox API Exception placing order: {e.status} - {e.reason} - {e.body}", symbol=instrument_token)
           except Exception as e:
               self._log_api_action(action, "FAILURE", f"Generic error placing order: {e}", symbol=instrument_token)
           return None

    def modify_order(self, 
                        order_id: str,
                        quantity: int = None, 
                        price: float = None, 
                        order_type: str = None, # Can modify order type (e.g. LIMIT to SL)
                        trigger_price: float = None,
                        validity: str = 'DAY' # Usually DAY for modification
                       ): 
           action = "MODIFY_ORDER"
           if not self.access_token:
               self._log_api_action(action, "FAILURE", "Not logged in.", data={'order_id': order_id})
               return None

           order_api = upstox_client.OrderApi(self.api_client)
           try:
               # SDK expects ModifyOrderRequest object
               body = upstox_client.ModifyOrderRequest(
                   order_id=order_id, # Required
                   quantity=quantity, # New quantity
                   price=price,         # New price
                   order_type=order_type.upper() if order_type else None, # New order type
                   trigger_price=trigger_price, # New trigger price
                   validity=validity.upper()
               )
               
               api_response = order_api.modify_order(body, api_version=self.API_VERSION)
               # Response should be ModifyOrderResponse, containing order_id
               modified_order_id = getattr(api_response, 'data', {}).get('order_id') if hasattr(api_response, 'data') else None
               
               if modified_order_id: # Upstox returns the same order_id on successful modification
                   self._log_api_action(action, "SUCCESS", f"Order {order_id} modification request accepted.", data={'order_id': modified_order_id})
                   return modified_order_id
               else:
                   self._log_api_action(action, "FAILURE", "Order modification failed, no order_id in response.", data=api_response.to_dict() if hasattr(api_response, 'to_dict') else str(api_response))
                   return None
           except ApiException as e:
               self._log_api_action(action, "API_EXCEPTION", f"Upstox API Exception modifying order: {e.status} - {e.reason} - {e.body}", data={'order_id': order_id})
           except Exception as e:
               self._log_api_action(action, "FAILURE", f"Generic error modifying order: {e}", data={'order_id': order_id})
           return None

    def cancel_order(self, order_id: str): 
           action = "CANCEL_ORDER"
           if not self.access_token:
               self._log_api_action(action, "FAILURE", "Not logged in.", data={'order_id': order_id})
               return None
               
           order_api = upstox_client.OrderApi(self.api_client)
           try:
               # SDK expects order_id and api_version
               # The SDK method is cancel_order(order_id, api_version)
               api_response = order_api.cancel_order(order_id=order_id, api_version=self.API_VERSION)
               # Response should be CancelOrderResponse, containing order_id
               cancelled_order_id = getattr(api_response, 'data', {}).get('order_id') if hasattr(api_response, 'data') else None

               if cancelled_order_id:
                   self._log_api_action(action, "SUCCESS", f"Order {order_id} cancellation request accepted.", data={'order_id': cancelled_order_id})
                   return cancelled_order_id
               else:
                   self._log_api_action(action, "FAILURE", "Order cancellation failed, no order_id in response.", data=api_response.to_dict() if hasattr(api_response, 'to_dict') else str(api_response))
                   return None
           except ApiException as e:
               # Handle cases where order might already be cancelled or executed
               body_str = str(e.body).lower()
               if "already cancelled" in body_str or "already completed" in body_str or "oms: order id not found" in body_str :
                   self._log_api_action(action, "INFO", f"Order {order_id} likely already cancelled/completed. Message: {e.reason}", data={'order_id': order_id})
                   return order_id # Return original order_id as success in this case
               self._log_api_action(action, "API_EXCEPTION", f"Upstox API Exception cancelling order: {e.status} - {e.reason} - {e.body}", data={'order_id': order_id})
           except Exception as e:
               self._log_api_action(action, "FAILURE", f"Generic error cancelling order: {e}", data={'order_id': order_id})
           return None
        
    def get_order_history(self, order_id: str):
        """
        Retrieves the history for a specific order_id.
        Upstox SDK uses get_order_details for this.
        """
        action = "GET_ORDER_HISTORY" # Or "GET_ORDER_DETAILS" to match SDK
        if not self.access_token:
            self._log_api_action(action, "FAILURE", "Not logged in.", data={'order_id': order_id})
            return None # Return None or empty list
        if not order_id:
            self._log_api_action(action, "FAILURE", "Order ID not provided.", data={'order_id': order_id})
            return None

        order_api = upstox_client.OrderApi(self.api_client)
        try:
            # The SDK method is get_order_details(api_version, order_id=order_id)
            # It might also accept a 'tag' parameter, but we'll omit it for simplicity.
            api_response = order_api.get_order_details(
                api_version=self.API_VERSION,
                order_id=order_id
            )
            
            # The response (GetOrderResponse) contains a 'data' attribute which is a list of OrderBookData.
            # This list represents the various states/updates of the order.
            order_updates = []
            if api_response and hasattr(api_response, 'data') and isinstance(api_response.data, list):
                for update in api_response.data:
                    order_updates.append({
                        # Common fields, adjust based on actual attributes in OrderBookData
                        'status': getattr(update, 'status', None),
                        'transaction_type': getattr(update, 'transaction_type', None),
                        'quantity': int(getattr(update, 'quantity', 0)),
                        'filled_quantity': int(getattr(update, 'filled_quantity', 0)),
                        'average_price': float(getattr(update, 'average_price', 0.0)),
                        'price': float(getattr(update, 'price', 0.0)), # Limit price
                        'trigger_price': float(getattr(update, 'trigger_price', 0.0)),
                        'order_timestamp': getattr(update, 'order_timestamp', None), # Exchange timestamp might also be available
                        'exchange_timestamp': getattr(update, 'exchange_timestamp', None),
                        'message': getattr(update, 'message', None) or getattr(update, 'status_message', None),
                        # Add other relevant fields from OrderBookData
                        'instrument_token': getattr(update, 'instrument_token', None),
                        'order_type': getattr(update, 'order_type', None),
                        'product': getattr(update, 'product', None),
                    })
            
            self._log_api_action(action, "SUCCESS", f"Fetched history for order {order_id}, {len(order_updates)} updates.", data=api_response.to_dict() if hasattr(api_response, 'to_dict') else str(api_response))
            return order_updates # Returns a list of order updates/states

        except ApiException as e:
            self._log_api_action(action, "API_EXCEPTION", f"Upstox API Exception getting order history for {order_id}: {e.status} - {e.reason} - {e.body}", data={'order_id': order_id})
        except Exception as e:
            self._log_api_action(action, "FAILURE", f"Generic error getting order history for {order_id}: {e}", data={'order_id': order_id})
        return None # Return None or empty list on failure


if __name__ == '__main__':
    print("UpstoxAPI class defined. For usage, integrate with main.py.")
    # To test login flow (manual steps required):
    # 1. Ensure UPSTOX_API_KEY, UPSTOX_API_SECRET, UPSTOX_REDIRECT_URI are set in config.py
    # (or directly in this script for isolated testing, not recommended for real use).
    # 2. Create an instance of UpstoxAPI.
    # 3. Call get_login_url() and open the URL in a browser.
    # 4. Authenticate and get the 'auth_code' from the redirect URL.
    # 5. Call login(auth_code_override=YOUR_AUTH_CODE).
    # 6. If successful, try get_profile().

    # Example (requires manual intervention and config.py setup):
    # upstox_broker = UpstoxAPI() # Assuming config.py has values
    # login_url = upstox_broker.get_login_url()
    # print(f"Please login using this URL: {login_url}")
    # auth_code_from_user = input("Enter the authorization code from redirect URL: ").strip()
    # if auth_code_from_user:
    #     access_token = upstox_broker.login(auth_code_override=auth_code_from_user)
    #     if access_token:
    #         print("Upstox login successful!")
    #         profile = upstox_broker.get_profile()
    #         if profile:
    #             print(f"Profile: {profile}")
    #     else:
    #         print("Upstox login failed.")
    # else:
    #     print("No auth code provided.")
