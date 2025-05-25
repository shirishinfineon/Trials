# algo_trading_system/main.py

import sys # For sys.exit()
from brokers.zerodha.kite_connect import KiteConnectAPI
from data_management.trade_logger import TradeLogger
from config import (
    ZERODHA_API_KEY, 
    ZERODHA_API_SECRET, 
    ZERODHA_REQUEST_TOKEN, # Will be used if user needs to input it
    TRADE_LOG_FILE,
    DAILY_SUMMARY_FILE,
    APPLICATION_LOG_FILE # Though app log isn't fully set up here, good to have
)

def run_manual_tests(broker_api):
    print("\n--- Running Manual Account Info Tests ---")

    profile = broker_api.get_profile()
    if profile:
        print(f"\nUser Profile: {profile.get('user_name')}, Email: {profile.get('email')}, User ID: {profile.get('user_id')}")
    else:
        print("\nFailed to fetch profile.")

    margins = broker_api.get_margins()
    if margins:
        if 'equity' in margins and margins['equity']:
            print(f"\nMargins (Equity Net): {margins['equity'].get('net')}")
            print(f"Margins (Equity Available Cash): {margins['equity'].get('available', {}).get('cash')}")
        if 'commodity' in margins and margins['commodity']:
            print(f"Margins (Commodity Net): {margins['commodity'].get('net')}")
    else:
        print("\nFailed to fetch margins.")

    positions = broker_api.get_positions()
    if positions:
        print(f"\nDay Positions Count: {len(positions.get('day', []))}")
        for pos in positions.get('day', []):
            print(f"  Symbol: {pos['tradingsymbol']}, Qty: {pos['quantity']}, PnL: {pos['pnl']}")
        print(f"Net Positions Count: {len(positions.get('net', []))}")
        for pos in positions.get('net', []):
            print(f"  Symbol: {pos['tradingsymbol']}, Qty: {pos['quantity']}, Avg: {pos['average_price']}, PnL: {pos['pnl']}")
    else:
        print("\nFailed to fetch positions.")

    holdings = broker_api.get_holdings()
    if holdings:
        print(f"\nHoldings Count: {len(holdings)}")
        for holding in holdings:
            print(f"  Symbol: {holding['tradingsymbol']}, Qty: {holding['quantity']}, Avg: {holding['average_price']}")
    else:
        print("\nFailed to fetch holdings.")

    # --- Example: Placing a dummy order (Use with EXTREME CAUTION) ---
    # IMPORTANT: 
    # 1. This is for testing purposes only.
    # 2. Ensure you understand the parameters (exchange, symbol, product type, order type, price).
    # 3. For safety on a live account, use a LIMIT order with a price far from the current market
    #    (e.g., price=1.00 for a stock trading at 1000.00) so it won't execute.
    # 4. Or, test with a paper trading account if your broker provides one via API.
    # 5. Uncomment and modify parameters at your own risk.
    
    # print("\n--- Example Order Placement (Commented Out By Default) ---")
    # example_order_params = {
    #     "variety": "regular",
    #     "exchange": "NSE", # Or "BSE"
    #     "tradingsymbol": "INFY", # Ensure this is a valid symbol for the exchange
    #     "transaction_type": "BUY", # Or "SELL"
    #     "quantity": 1,
    #     "product": "CNC",  # CNC for delivery, MIS for intraday
    #     "order_type": "LIMIT", # Or "MARKET", "SL", "SL-M"
    #     "price": 100.00,  # Set a non-executable price for LIMIT order testing if live
    #     # "trigger_price": None, # For SL or SL-M orders
    #     # "tag": "MyTestOrder" # Optional tag
    # }
    #
    # print(f"Attempting to place test order with params: {example_order_params}")
    # order_id = broker_api.place_order(**example_order_params)
    #
    # if order_id:
    #     print(f"Test order placed successfully. Order ID: {order_id}")
    #     print("Fetching order history for this order...")
    #     order_history = broker_api.get_order_history(order_id=order_id)
    #     if order_history:
    #         for entry in order_history:
    #             print(f"  Status: {entry['status']}, Time: {entry.get('order_timestamp', entry.get('exchange_timestamp'))}, Msg: {entry.get('status_message')}")
    #     else:
    #         print("Could not fetch order history for the test order.")
    #
    #     # Example: Cancel this test order (if it's an open LIMIT order)
    #     # print(f"\nAttempting to cancel order: {order_id}")
    #     # cancelled_id = broker_api.cancel_order(variety="regular", order_id=order_id)
    #     # if cancelled_id: # Note: cancel_order returns the original order_id on success from Kite
    #     #     print(f"Cancel request for order {cancelled_id} successful (or already completed/cancelled). Check status.")
    #     #     order_history_after_cancel = broker_api.get_order_history(order_id=order_id)
    #     #     if order_history_after_cancel:
    #     #          print(f"  Latest Status: {order_history_after_cancel[-1]['status']}")
    #     # else:
    #     #     print(f"Cancel request for order {order_id} failed or order was not cancellable.")
    # else:
    #     print("Test order placement failed or was not attempted.")
    print("\n--- Manual Account Info Tests Finished ---")


def main():
    print("--- Starting Algo Trading System (Manual Test Mode) ---")

    # Initialize Trade Logger
    # The TradeLogger now creates the 'logs' directory if it doesn't exist.
    logger = TradeLogger(trade_log_file=TRADE_LOG_FILE, 
                         daily_summary_file=DAILY_SUMMARY_FILE)
    print("TradeLogger initialized.")
    logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_START", quantity=0, price=0, order_type="-", status="SUCCESS", remarks="Application started in manual test mode.")

    # Check for API Key and Secret
    if ZERODHA_API_KEY == "YOUR_API_KEY_HERE" or ZERODHA_API_SECRET == "YOUR_API_SECRET_HERE":
        print("\nERROR: Zerodha API Key or Secret not configured in config.py.")
        print("Please update ZERODHA_API_KEY and ZERODHA_API_SECRET in algo_trading_system/config.py")
        logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_EXIT", quantity=0, price=0, order_type="-", status="FAILURE", remarks="API Key/Secret not configured.")
        sys.exit(1)

    # Initialize Broker API
    broker_api = KiteConnectAPI(api_key=ZERODHA_API_KEY, logger=logger)
    
    # Attempt Login
    # The login method will first try to load a stored access token.
    # If that fails, it will check ZERODHA_REQUEST_TOKEN in config.py.
    # If ZERODHA_REQUEST_TOKEN is also empty, it will print the login URL and instructions.
    
    access_token = broker_api.login() # Tries to use stored token or ZERODHA_REQUEST_TOKEN

    if not access_token:
        # If login via stored token and config.ZERODHA_REQUEST_TOKEN failed
        print("\n--- LOGIN REQUIRED ---")
        login_url = broker_api.get_login_url()
        print(f"1. Open this URL in your browser: {login_url}")
        print("2. Login with your Zerodha credentials.")
        print("3. After successful login, you will be redirected to a URL containing a 'request_token'.")
        print("   Example: https://yourredirecturl.com/?status=success&request_token=THIS_IS_YOUR_TOKEN")
        
        try:
            user_provided_request_token = input("\n4. Enter the 'request_token' here: ").strip()
        except KeyboardInterrupt:
            print("\nLogin process aborted by user.")
            logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_EXIT", quantity=0, price=0, order_type="-", status="ABORTED", remarks="Login aborted by user.")
            sys.exit(1)

        if not user_provided_request_token:
            print("No request_token provided. Exiting.")
            logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_EXIT", quantity=0, price=0, order_type="-", status="FAILURE", remarks="No request_token provided by user.")
            sys.exit(1)
        
        # Now try logging in again with the user-provided request_token
        print("Attempting login with provided request_token...")
        access_token = broker_api.login(request_token_override=user_provided_request_token)

    if access_token:
        print("\n--- Login Successful! ---")
        logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="LOGIN", quantity=0, price=0, order_type="-", status="SUCCESS", remarks=f"User {broker_api.user_id} logged in.")
        
        # Run manual tests (fetch profile, positions, etc.)
        run_manual_tests(broker_api)
        
    else:
        print("\n--- Login Failed. Please check credentials and request_token if prompted. ---")
        print("Ensure ZERODHA_API_KEY and ZERODHA_API_SECRET are correct in config.py.")
        print("If you provided a request_token, ensure it was copied correctly and hasn't expired.")
        logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="LOGIN", quantity=0, price=0, order_type="-", status="FAILURE", remarks="Login failed after prompts.")
        sys.exit(1)

    print("\n--- Algo Trading System (Manual Test Mode) Finished ---")
    logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_END", quantity=0, price=0, order_type="-", status="SUCCESS", remarks="Application finished.")

if __name__ == "__main__":
    main()
