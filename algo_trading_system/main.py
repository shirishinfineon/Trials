# algo_trading_system/main.py

import sys
import os # For path joining
import time # Added for position tracking loop
# Keep existing imports: KiteConnectAPI, TradeLogger
from brokers.zerodha.kite_connect import KiteConnectAPI 
from brokers.upstox.upstox_api import UpstoxAPI # Added UpstoxAPI
from data_management.trade_logger import TradeLogger
from strategies.sma_crossover_strategy import SmaCrossoverStrategy # Import the new strategy

# Import configurations from config.py
# It's crucial that config.py exists and is populated (as per config.py.example)
try:
    from config import (
        ACTIVE_BROKER, # Added ACTIVE_BROKER
        ZERODHA_API_KEY, ZERODHA_API_SECRET, ZERODHA_REQUEST_TOKEN,
        UPSTOX_API_KEY, UPSTOX_API_SECRET, UPSTOX_REDIRECT_URI, # Added Upstox credentials
        TRADE_LOG_FILE, DAILY_SUMMARY_FILE, APPLICATION_LOG_FILE,
        BACKTEST_DATA_DIR, BACKTEST_START_DATE, BACKTEST_END_DATE,
        BACKTEST_INITIAL_CAPITAL, EXAMPLE_STRATEGY_PARAMS,
        DEFAULT_PRODUCT_TYPE, DEFAULT_ORDER_TYPE,
        ALLOW_PYRAMIDING, MAX_PYRAMID_ENTRIES, # Added pyramiding configs
        # Add other necessary configs if BacktestEngine or strategy needs them directly
    )
except ImportError:
    print("ERROR: config.py not found or missing configurations. Please ensure it exists and is set up.")
    print("You might need to copy config.py.example to config.py and fill it out.")
    sys.exit(1)

# Existing run_manual_tests(broker_api) function can remain unchanged for now
# ... (paste existing run_manual_tests function here if you need to show full context, otherwise assume it's there)
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
    print("\n--- Manual Account Info Tests Finished ---")


def run_live_trading_flow(logger):
    print("--- Starting Algo Trading System (Live Trading Mode) ---")
    logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_START_LIVE", quantity=0, price=0, order_type="-", status="SUCCESS", remarks="Application started in live trading mode.")

    broker_api = None # Initialize to None
    access_token = None

    if ACTIVE_BROKER == "zerodha":
        if ZERODHA_API_KEY == "YOUR_API_KEY_HERE" or ZERODHA_API_SECRET == "YOUR_API_SECRET_HERE":
            print("\nERROR: Zerodha API Key or Secret not configured in config.py for active broker 'zerodha'.")
            logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_EXIT_LIVE", quantity=0, price=0, order_type="-", status="FAILURE", remarks="Zerodha API Key/Secret not configured.")
            sys.exit(1)
        
        broker_api = KiteConnectAPI(api_key=ZERODHA_API_KEY, logger=logger)
        access_token = broker_api.login() # Zerodha's specific login flow

        if not access_token: # Zerodha specific re-prompt
            print("\n--- LOGIN REQUIRED for Zerodha (Live Mode) ---")
            login_url = broker_api.get_login_url()
            print(f"1. Open this URL in your browser: {login_url}")
            print("2. Login with your Zerodha credentials.")
            print("3. After successful login, you will be redirected to a URL containing a 'request_token'.")
            print("   Example: https://yourredirecturl.com/?status=success&request_token=THIS_IS_YOUR_TOKEN")
            try:
                user_provided_request_token = input("\n4. Enter the 'request_token' here: ").strip()
            except KeyboardInterrupt:
                print("\nLogin process aborted by user.")
                logger.log_trade(strategy_name="SYSTEM", symbol="ZERODHA", exchange="-", action="APP_EXIT_LIVE", quantity=0, price=0, order_type="-", status="ABORTED", remarks="Login aborted by user.")
                sys.exit(1)

            if not user_provided_request_token:
                print("No request_token provided for Zerodha. Exiting.")
                logger.log_trade(strategy_name="SYSTEM", symbol="ZERODHA", exchange="-", action="APP_EXIT_LIVE", quantity=0, price=0, order_type="-", status="FAILURE", remarks="No request_token provided by user for Zerodha.")
                sys.exit(1)
            access_token = broker_api.login(request_token_override=user_provided_request_token)

    elif ACTIVE_BROKER == "upstox":
        if UPSTOX_API_KEY == "YOUR_UPSTOX_API_KEY_HERE" or UPSTOX_API_SECRET == "YOUR_UPSTOX_API_SECRET_HERE":
            print("\nERROR: Upstox API Key or Secret not configured in config.py for active broker 'upstox'.")
            logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_EXIT_LIVE", quantity=0, price=0, order_type="-", status="FAILURE", remarks="Upstox API Key/Secret not configured.")
            sys.exit(1)

        broker_api = UpstoxAPI(api_key=UPSTOX_API_KEY, api_secret=UPSTOX_API_SECRET, redirect_uri=UPSTOX_REDIRECT_URI, logger=logger)
        access_token = broker_api.login() # Upstox's login flow (tries stored token first)

        if not access_token: # Upstox specific re-prompt for auth_code
            print("\n--- LOGIN REQUIRED for Upstox (Live Mode) ---")
            login_url = broker_api.get_login_url()
            print(f"1. Open this URL in your browser: {login_url}")
            print("2. Login with your Upstox credentials and authorize the app.")
            print("3. After successful authorization, you will be redirected to your redirect_uri with an 'code' (auth_code) in the URL.")
            print("   Example: YOUR_REDIRECT_URI?code=THIS_IS_YOUR_AUTH_CODE")
            try:
                user_provided_auth_code = input("\n4. Enter the 'code' (auth_code) here: ").strip()
            except KeyboardInterrupt:
                print("\nLogin process aborted by user.")
                logger.log_trade(strategy_name="SYSTEM", symbol="UPSTOX", exchange="-", action="APP_EXIT_LIVE", quantity=0, price=0, order_type="-", status="ABORTED", remarks="Login aborted by user.")
                sys.exit(1)

            if not user_provided_auth_code:
                print("No auth_code provided for Upstox. Exiting.")
                logger.log_trade(strategy_name="SYSTEM", symbol="UPSTOX", exchange="-", action="APP_EXIT_LIVE", quantity=0, price=0, order_type="-", status="FAILURE", remarks="No auth_code provided by user for Upstox.")
                sys.exit(1)
            access_token = broker_api.login(auth_code_override=user_provided_auth_code)
    else:
        print(f"ERROR: Invalid ACTIVE_BROKER setting '{ACTIVE_BROKER}' in config.py. Must be 'zerodha' or 'upstox'.")
        logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_EXIT_LIVE", quantity=0, price=0, order_type="-", status="FAILURE", remarks=f"Invalid ACTIVE_BROKER: {ACTIVE_BROKER}")
        sys.exit(1)
        
    if access_token:
        print(f"\n--- Login Successful for {ACTIVE_BROKER.upper()} (Live Mode)! ---")
        logger.log_trade(strategy_name="SYSTEM", symbol=ACTIVE_BROKER.upper(), exchange="-", action="LOGIN_LIVE", quantity=0, price=0, order_type="-", status="SUCCESS", remarks=f"User {broker_api.user_id if hasattr(broker_api, 'user_id') else 'N/A'} logged in via {ACTIVE_BROKER}.")
        
        # Initial account details display
        run_manual_tests(broker_api) 
        
        print("\n--- Starting Live Position Tracking (Ctrl+C to stop) ---")
        try:
            # Configuration for position tracking loop
            position_fetch_interval = 30 # seconds
            max_tracking_iterations = 20 # Stop after N iterations for this example (10 minutes)
            iterations = 0

            while iterations < max_tracking_iterations:
                iterations += 1
                print(f"\n--- Position Update #{iterations} at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
                
                positions_data = broker_api.get_positions()
                net_positions = []
                day_positions = []

                if positions_data:
                    net_positions = positions_data.get('net', [])
                    day_positions = positions_data.get('day', [])
                else:
                    print("Could not fetch position data.")
                    logger.log_trade(strategy_name="SYSTEM_LIVE", symbol="-", exchange="-", action="FETCH_POS_FAIL", quantity=0, price=0, order_type="-", status="WARNING", remarks="Failed to fetch positions")

                if not net_positions and not day_positions:
                    print("No open positions.")
                else:
                    print("Net Positions:")
                    if not net_positions: print("  None")
                    for pos in net_positions:
                        print(f"  Symbol: {pos['tradingsymbol']}, Qty: {pos['quantity']}, Avg: {pos['average_price']:.2f}, "
                              f"LTP: {pos.get('last_price', 0):.2f}, P&L: {pos['pnl']:.2f}, "
                              f"Day P&L: {pos.get('day_pnl', pos.get('pnl'))}") # Use 'pnl' if 'day_pnl' not present

                    print("Day Positions (Intraday):")
                    if not day_positions: print("  None")
                    for pos in day_positions:
                         print(f"  Symbol: {pos['tradingsymbol']}, Qty: {pos['quantity']}, Avg: {pos['average_price']:.2f}, "
                               f"LTP: {pos.get('last_price',0):.2f}, P&L: {pos['pnl']:.2f}")
                
                # Fetch and display available funds/margin (optional enhancement)
                # margins = broker_api.get_margins()
                # if margins and margins.get('equity'):
                #     print(f"Available Equity Cash: {margins['equity'].get('available', {}).get('cash', 'N/A')}")

                # Placeholder for strategy execution loop
                # In a real system, this is where you'd fetch live ticks,
                # feed to strategy.generate_signals(), and then strategy.execute_trade()
                # e.g., my_strategy.run_live_tick(current_tick_data)

                if iterations < max_tracking_iterations: # Don't sleep on the last iteration
                    print(f"Waiting for {position_fetch_interval} seconds before next update...")
                    time.sleep(position_fetch_interval)

        except KeyboardInterrupt:
            print("\n--- Live Position Tracking stopped by user (Ctrl+C). ---")
            logger.log_trade(strategy_name="SYSTEM_LIVE", symbol="-", exchange="-", action="TRACKING_STOP_USER", quantity=0, price=0, order_type="-", status="INFO", remarks="Position tracking stopped by user.")
        except Exception as e:
            print(f"\n--- An error occurred during live position tracking: {e} ---")
            logger.log_trade(strategy_name="SYSTEM_LIVE", symbol="-", exchange="-", action="TRACKING_ERROR", quantity=0, price=0, order_type="-", status="ERROR", remarks=str(e))
        
        print("\n--- Live Position Tracking Finished ---")

        # ADD THIS: Call square off MIS positions before exiting live mode
        if broker_api and broker_api.access_token: # Ensure API is still valid
            square_off_all_mis_positions(broker_api, logger)

    else: # Login failed
        print(f"\n--- Login Failed for {ACTIVE_BROKER.upper()} (Live Mode). ---")
        logger.log_trade(strategy_name="SYSTEM", symbol=ACTIVE_BROKER.upper(), exchange="-", action="LOGIN_LIVE_FAIL", quantity=0, price=0, order_type="-", status="FAILURE", remarks=f"Login failed for {ACTIVE_BROKER}")
        # sys.exit(1) # Not exiting here, just logging

    print("\n--- Algo Trading System (Live Trading Mode) Finished ---")
    logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_END_LIVE", quantity=0, price=0, order_type="-", status="SUCCESS", remarks="Application finished live mode.")


def square_off_all_mis_positions(broker_api, logger):
    """
    Squares off all open MIS (intraday) positions.
    """
    if not broker_api or not broker_api.access_token:
        print("Cannot square off positions: Broker API not connected or not logged in.")
        if logger: logger.log_trade("SYSTEM_SQUARE_OFF", "-", "-", "SQUARE_OFF_FAIL", 0,0,"-", status="FAILURE", remarks="Broker API not connected")
        return

    print("\n--- Attempting to Square Off All MIS Positions ---")
    logger.log_trade("SYSTEM_SQUARE_OFF", "-", "-", "INITIATE_SQUARE_OFF", 0,0,"-", status="INFO", remarks="Starting square off MIS positions.")

    try:
        positions_data = broker_api.get_positions()
        if not positions_data or not positions_data.get('net'):
            print("No net positions found to square off.")
            logger.log_trade("SYSTEM_SQUARE_OFF", "-", "-", "NO_POSITIONS", 0,0,"-", status="INFO", remarks="No net positions.")
            return

        mis_positions_found = 0
        for pos in positions_data['net']:
            if pos.get('product') == 'MIS' and int(pos.get('quantity', 0)) != 0:
                mis_positions_found += 1
                symbol = pos['tradingsymbol']
                quantity = abs(int(pos['quantity'])) # Absolute quantity to square off
                
                # Determine transaction type for squaring off
                # If quantity is positive (long), we sell. If negative (short), we buy.
                transaction_type = "SELL" if int(pos['quantity']) > 0 else "BUY"
                
                print(f"Squaring off {quantity} of {symbol} ({pos['product']}). Action: {transaction_type}")

                try:
                    order_id = broker_api.place_order(
                        variety="regular",
                        exchange=pos['exchange'], # Get exchange from position data
                        tradingsymbol=symbol,
                        transaction_type=transaction_type,
                        quantity=quantity,
                        product="MIS", # Explicitly MIS
                        order_type="MARKET", # Square off with a market order
                        # tag="SquareOffMIS" # Optional tag
                    )
                    if order_id:
                        print(f"Square off order placed for {symbol}. Order ID: {order_id}")
                        logger.log_trade("SYSTEM_SQUARE_OFF", symbol, pos['exchange'], transaction_type, quantity, 0, "MARKET", order_id=order_id, status="PLACED", remarks="MIS position square off order placed.")
                    else:
                        print(f"Failed to place square off order for {symbol}. No Order ID.")
                        logger.log_trade("SYSTEM_SQUARE_OFF", symbol, pos['exchange'], transaction_type, quantity, 0, "MARKET", status="FAILURE", remarks="Square off MIS failed - No Order ID.")
                except Exception as e:
                    print(f"Exception placing square off order for {symbol}: {e}")
                    logger.log_trade("SYSTEM_SQUARE_OFF", symbol, pos['exchange'], transaction_type, quantity, 0, "MARKET", status="EXCEPTION", remarks=f"Square off MIS exception: {e}")
            
        if mis_positions_found == 0:
            print("No open MIS positions found to square off.")
            logger.log_trade("SYSTEM_SQUARE_OFF", "-", "-", "NO_MIS_POSITIONS", 0,0,"-", status="INFO", remarks="No open MIS positions.")

    except Exception as e:
        print(f"Error fetching positions for square off: {e}")
        logger.log_trade("SYSTEM_SQUARE_OFF", "-", "-", "FETCH_POS_FAIL_SQ",0,0,"-", status="ERROR", remarks=f"Error fetching positions: {e}")

    print("--- MIS Positions Square Off Routine Finished ---")


def run_backtest_flow(logger):
    print("--- Starting Algo Trading System (Backtest Mode) ---")
    logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_START_BACKTEST", quantity=0, price=0, order_type="-", status="INFO", remarks="Application started in backtest mode.")

    # 1. Select Strategy and Parameters
    # For now, hardcoding SmaCrossoverStrategy and its params from config
    strategy_name = "SmaCrossover" 
    strategy_params = EXAMPLE_STRATEGY_PARAMS # Loaded from config.py
    
    # Initialize the strategy
    # broker_api is not strictly needed for backtesting, can be None
    # However, strategy __init__ expects it. Pass a None or a mock if it tries to use it.
    # For SmaCrossoverStrategy, broker_api is only used in execute_trade (live).
    strategy_instance = SmaCrossoverStrategy(
        name=strategy_name,
        broker_api=None, # No live broker interaction in backtest
        logger=logger,
        params=strategy_params
    )
    print(f"Strategy '{strategy_instance.name}' initialized for backtesting.")

    # 2. Define Backtest Parameters
    # These should ideally come from config.py or command-line args
    # Using example values for symbol and data file path
    # Ensure BACKTEST_DATA_DIR ends with a '/' in config.py
    backtest_symbol = "DUMMY_TEST_EQ" # Example symbol, user should have DUMMY_TEST_EQ.csv
    historical_data_file = os.path.join(BACKTEST_DATA_DIR, f"{backtest_symbol}.csv") 
    
    # Check if the historical data file exists
    if not os.path.exists(historical_data_file):
        print(f"ERROR: Historical data file not found: {historical_data_file}")
        print("Please ensure the file exists or update BACKTEST_DATA_DIR and symbol.")
        # Create a dummy file if it doesn't exist, for demonstration purposes
        # This part should ideally be handled by user providing data.
        print(f"Attempting to create a dummy CSV for {backtest_symbol} for testing...")
        os.makedirs(BACKTEST_DATA_DIR, exist_ok=True)
        dummy_header = "Date,Open,High,Low,Close,Volume\n" # Note: Date format for pd.to_datetime
        dummy_data_rows = [
            "2023-01-01 09:15:00,100,102,99,100,1000\n",
            "2023-01-02 09:15:00,100,102,99,101.5,1200\n",
            "2023-01-03 09:15:00,101.5,104,101,103,1100\n",
            "2023-01-04 09:15:00,103,103,95,98,1500\n",
            "2023-01-05 09:15:00,98,99,97,98.5,1300\n",
            "2023-01-06 09:15:00,98.5,105,98,104,1400\n",
        ]
        try:
            with open(historical_data_file, 'w') as f:
                f.write(dummy_header)
                for row in dummy_data_rows:
                    f.write(row)
            print(f"Dummy CSV created at: {historical_data_file}. Please replace with actual data.")
        except Exception as e:
            print(f"Could not create dummy CSV: {e}")
            logger.log_trade(strategy_name="SYSTEM", symbol=backtest_symbol, exchange="BACKTEST", action="APP_EXIT_BACKTEST", quantity=0, price=0, order_type="-", status="FAILURE", remarks=f"Historical data file not found and dummy creation failed: {historical_data_file}")
            sys.exit(1)
            
    # 3. Run the backtest using strategy's run_backtest method
    print(f"Starting backtest for {backtest_symbol} using data from {historical_data_file}...")
    strategy_instance.run_backtest(
        historical_data_source=historical_data_file,
        strategy=strategy_instance,
        initial_capital=BACKTEST_INITIAL_CAPITAL,
        start_date=BACKTEST_START_DATE,
        end_date=BACKTEST_END_DATE,
        trade_logger=logger,
        symbol=backtest_symbol,
        stop_loss_percent=strategy_params.get('stop_loss_percent'), # From strategy_params
        target_percent=strategy_params.get('target_percent'),     # From strategy_params
        brokerage_percent=strategy_params.get('brokerage_percent', 0.01),
        slippage_percent=strategy_params.get('slippage_percent', 0.005),
        qty_per_trade=strategy_params.get('qty_per_trade', 10),
        allow_pyramiding=ALLOW_PYRAMIDING, # Directly from config import
        max_pyramid_entries=MAX_PYRAMID_ENTRIES # Directly from config import
    )

    print("\n--- Algo Trading System (Backtest Mode) Finished ---")
    logger.log_trade(strategy_name="SYSTEM", symbol=backtest_symbol, exchange="BACKTEST", action="APP_END_BACKTEST", quantity=0, price=0, order_type="-", status="SUCCESS", remarks="Backtest finished.")


def main():
    # Initialize Trade Logger (common for both modes)
    # Ensure TRADE_LOG_FILE and DAILY_SUMMARY_FILE are defined in config
    logger = TradeLogger(trade_log_file=TRADE_LOG_FILE, 
                         daily_summary_file=DAILY_SUMMARY_FILE)
    print("TradeLogger initialized.")

    # --- Mode Selection ---
    # Simple mode selection: Change this variable to switch mode.
    # Future: Use command-line arguments (e.g., `python main.py --mode backtest`)
    CURRENT_MODE = "backtest" # Options: "live", "backtest" 

    if CURRENT_MODE == "live":
        run_live_trading_flow(logger)
    elif CURRENT_MODE == "backtest":
        run_backtest_flow(logger)
    else:
        print(f"ERROR: Unknown mode '{CURRENT_MODE}'. Valid modes are 'live' or 'backtest'.")
        logger.log_trade(strategy_name="SYSTEM", symbol="-", exchange="-", action="APP_EXIT", quantity=0, price=0, order_type="-", status="FAILURE", remarks=f"Unknown mode: {CURRENT_MODE}")
        sys.exit(1)

if __name__ == "__main__":
    main()
