# algo_trading_system/core/backtest_engine.py
import pandas as pd
from datetime import datetime
import os # Added for dummy data creation and path joining in main example

# Attempt relative imports, adjust if necessary based on execution context
try:
    from ..data_management.trade_logger import TradeLogger
    from ..strategies.base_strategy import BaseStrategy
except ImportError:
    # Fallback for direct execution or if modules are not found with relative paths
    # This might happen if 'core' is not recognized as part of a package immediately
    # or if this script is run standalone for testing.
    # Ensure your PYTHONPATH is set up correctly if running from project root for imports to work.
    print("Could not perform relative imports for TradeLogger/BaseStrategy in backtest_engine.py. Using placeholder mocks if in __main__.")
    # Define placeholder mocks if needed for direct script execution, actual instances will be passed from main.py
    if __name__ == '__main__':
        TradeLogger = None
        BaseStrategy = None


class BacktestEngine:
    def __init__(self, historical_data_source, strategy, initial_capital, 
                 start_date, end_date, trade_logger, symbol,
                 stop_loss_percent=None, target_percent=None,
                 brokerage_percent=0.0, slippage_percent=0.0,
                 qty_per_trade=10, 
                 allow_pyramiding=False, # New
                 max_pyramid_entries=1):   # New
        """
        Initializes the BacktestEngine.

        Args:
            historical_data_source (str or pd.DataFrame): Path to CSV data file or DataFrame.
            strategy (BaseStrategy): The trading strategy instance.
            initial_capital (float): The starting capital for the backtest.
            start_date (str or datetime): The start date for the backtest.
            end_date (str or datetime): The end date for the backtest.
            trade_logger (TradeLogger): Instance of TradeLogger for logging trades and summary.
            symbol (str): The trading symbol (e.g., 'INFY_EQ').
            stop_loss_percent (float, optional): Default stop-loss percentage if not set by strategy.
            target_percent (float, optional): Default target profit percentage if not set by strategy.
            brokerage_percent (float, optional): Percentage brokerage per trade.
            slippage_percent (float, optional): Percentage slippage per trade.
            qty_per_trade (int, optional): Fixed quantity for each trade.
            allow_pyramiding (bool, optional): Whether to allow pyramiding entries.
            max_pyramid_entries (int, optional): Max number of entries if pyramiding.
        """
        self.historical_data_source = historical_data_source
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.trade_logger = trade_logger # This should be an actual instance of TradeLogger
        self.symbol = symbol
        self.stop_loss_percent = stop_loss_percent
        self.target_percent = target_percent
        self.brokerage_percent = brokerage_percent
        self.slippage_percent = slippage_percent
        self.qty_per_trade = qty_per_trade 
        self.allow_pyramiding = allow_pyramiding # New
        self.max_pyramid_entries = max_pyramid_entries if self.allow_pyramiding else 1 # New

        self.data = self._load_data()
        
        self.trades = [] 
        # self.positions structure will be: 
        # {'SYMBOL': {'qty': X, 'avg_price': Y, ..., 'num_entries': N}}
        self.positions = {} 
        
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        
        self._log_initial_setup()

    def _log_initial_setup(self):
        if self.trade_logger: # Check if a logger instance is provided
            self.trade_logger.log_trade(
                strategy_name="BACKTEST_ENGINE_SETUP",
                symbol=self.symbol,
                exchange="BACKTEST",
                action="INIT",
                quantity=0,
                price=self.initial_capital,
                order_type="-",
                status="INFO",
                remarks=f"Backtest initialized. Capital: {self.initial_capital}, Period: {self.start_date.date()} to {self.end_date.date()}"
            )
        print(f"BacktestEngine initialized for {self.symbol} from {self.start_date.date()} to {self.end_date.date()} with capital {self.initial_capital}.")

    def _load_data(self):
        print(f"Loading data for {self.symbol}...")
        if isinstance(self.historical_data_source, str):
            try:
                df = pd.read_csv(self.historical_data_source)
            except FileNotFoundError:
                print(f"ERROR: Data file not found: {self.historical_data_source}")
                if self.trade_logger:
                    self.trade_logger.log_trade(strategy_name="BACKTEST_ENGINE_ERROR", symbol=self.symbol, exchange="BACKTEST", action="LOAD_DATA_FAIL", quantity=0, price=0, order_type="-", status="FAILURE", remarks=f"Data file not found: {self.historical_data_source}")
                return pd.DataFrame()
        elif isinstance(self.historical_data_source, pd.DataFrame):
            df = self.historical_data_source.copy()
        else:
            print("ERROR: Invalid historical_data_source type.")
            if self.trade_logger:
                 self.trade_logger.log_trade(strategy_name="BACKTEST_ENGINE_ERROR", symbol=self.symbol, exchange="BACKTEST", action="LOAD_DATA_FAIL", quantity=0, price=0, order_type="-", status="FAILURE", remarks="Invalid data source type")
            return pd.DataFrame()

        if df.empty:
            print("ERROR: Loaded data is empty.")
            return pd.DataFrame()

        df.rename(columns={
            'Date': 'timestamp', 'date': 'timestamp', 'time': 'timestamp',
            'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
        }, inplace=True, errors='ignore') # errors='ignore' to not fail if some columns don't exist

        if 'timestamp' not in df.columns:
            print("ERROR: 'timestamp' column not found in data after renaming.")
            return pd.DataFrame()
            
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        except Exception as e:
            print(f"ERROR: Could not parse 'timestamp' column: {e}")
            return pd.DataFrame()

        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        
        df = df[(df.index >= self.start_date) & (df.index <= self.end_date)]
        
        if df.empty:
            print(f"ERROR: No data available for the specified date range: {self.start_date.date()} to {self.end_date.date()}.")
            return pd.DataFrame()
            
        required_cols = ['open', 'high', 'low', 'close'] # volume is optional
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"ERROR: Data is missing required OHLC columns: {', '.join(missing_cols)}")
            return pd.DataFrame()

        print(f"Data loaded successfully: {len(df)} rows from {df.index.min().date()} to {df.index.max().date()}")
        return df

    def _calculate_brokerage(self, trade_value):
        return trade_value * (self.brokerage_percent / 100.0)

    def _apply_slippage(self, price, action):
        slippage_amount = price * (self.slippage_percent / 100.0)
        if action == 'BUY':
            return price + slippage_amount
        elif action == 'SELL':
            return price - slippage_amount
        return price

    def _execute_signal(self, signal_details, current_bar_data):
    def _execute_signal(self, signal_details, current_bar_data): # quantity_to_trade removed from args, use self.qty_per_trade
        action = signal_details.get('action')
        signal_price = signal_details.get('price', current_bar_data['close']) 
        quantity_to_trade = self.qty_per_trade # Use instance variable

        pos_details = self.positions.get(self.symbol)

        if action == 'BUY':
            if pos_details and pos_details.get('entry_type') == 'LONG': # Already long
                if not self.allow_pyramiding or pos_details.get('num_entries', 0) >= self.max_pyramid_entries:
                    # print(f"{current_bar_data.name} - INFO: Pyramiding not allowed or max entries reached for {self.symbol}. Holding.")
                    return # No new BUY
                # Pyramiding allowed and entries < max: proceed to buy more
                print(f"{current_bar_data.name} - INFO: Pyramiding BUY for {self.symbol}. Current entries: {pos_details.get('num_entries',0)}")
            # If no existing long position, or if pyramiding is allowed and conditions met, proceed to BUY logic.
        
        elif action == 'SELL': # This is for closing a long or entering a short
            if pos_details and pos_details.get('entry_type') == 'LONG': # Existing long position, this SELL is to close it
                # This part of logic is for closing the existing long position
                entry_price = pos_details['avg_price']
                closed_qty = pos_details['qty'] # Close the entire position for now
                exec_price_sell = self._apply_slippage(signal_price, 'SELL') # Slippage on sell
                brokerage_sell = self._calculate_brokerage(exec_price_sell * closed_qty)
                pnl = (exec_price_sell - entry_price) * closed_qty - brokerage_sell
                self.current_capital += (closed_qty * exec_price_sell) - brokerage_sell
                # ... (logging and trade recording for closing trade - this part is mostly fine) ...
                log_msg = f"EXECUTED: SELL_CLOSE {closed_qty} {self.symbol} at {exec_price_sell:.2f} (from entry {entry_price:.2f}). PnL: {pnl:.2f}"
                print(f"{current_bar_data.name} - {log_msg}")
                if pnl > 0: self.winning_trades +=1
                else: self.losing_trades +=1
                self.total_trades +=1
                self.trades.append({
                    'symbol': self.symbol, 'entry_time': pos_details['entry_time'], 'exit_time': current_bar_data.name,
                    'entry_price': entry_price, 'exit_price': exec_price_sell, 'qty': closed_qty,
                    'pnl': pnl, 'type': pos_details['entry_type'], 'exit_reason': signal_details.get('reason', 'STRATEGY_SELL_CLOSE')
                })
                if self.trade_logger: self.trade_logger.log_trade(self.strategy.name, self.symbol, "BACKTEST", "SELL", closed_qty, exec_price_sell, "MARKET", status="EXECUTED_CLOSE", remarks=f"Capital: {self.current_capital:.2f}, Trade PnL: {pnl:.2f}, Reason: {signal_details.get('reason', 'STRATEGY_SELL_CLOSE')}")
                del self.positions[self.symbol]
                return # Explicitly return after closing a position based on SELL signal
            
            # If action is SELL and no existing LONG position, this could be an entry for a SHORT position.
            # Add short selling logic here if desired, respecting pyramiding for shorts.
            # For now, we are not implementing short selling entry.
            # if not pos_details: # Or if pos_details.get('entry_type') == 'SHORT' and allow_pyramiding_short...
            # print(f"{current_bar_data.name} - INFO: SELL signal received, no current LONG position to close. Short selling not implemented in this engine version.")
            return # No action if SELL signal and no long position to close.

        # Common execution logic for BUY (new entry or pyramiding)
        if action == 'BUY': # This block will only be reached for initial BUY or allowed pyramid BUY
            exec_price_buy = self._apply_slippage(signal_price, 'BUY')
            trade_value_buy = exec_price_buy * quantity_to_trade
            brokerage_buy = self._calculate_brokerage(trade_value_buy)

            if self.current_capital < trade_value_buy + brokerage_buy:
                # ... (insufficient funds logging) ...
                print(f"{current_bar_data.name} - INSUFFICIENT_FUNDS: Cannot {action} {quantity_to_trade} {self.symbol} at {exec_price_buy:.2f}.")
                if self.trade_logger: self.trade_logger.log_trade(self.strategy.name, self.symbol, "BACKTEST", action, quantity_to_trade, exec_price_buy, "MARKET", status="REJECTED", remarks="Insufficient funds")
                return

            self.current_capital -= (trade_value_buy + brokerage_buy)
            entry_sl = signal_details.get('sl_price') # Use sl_price from signal if available
            entry_tp = signal_details.get('tp_price') # Use tp_price from signal if available

            if not pos_details or pos_details.get('entry_type') != 'LONG': # New LONG position
                self.positions[self.symbol] = {
                    'qty': quantity_to_trade, 
                    'avg_price': exec_price_buy, 
                    'entry_time': current_bar_data.name, 
                    'stop_loss': entry_sl, 
                    'target': entry_tp, 
                    'entry_type': 'LONG',
                    'num_entries': 1
                }
                log_msg_details = f"New Entry. SL: {entry_sl:.2f if entry_sl else 'N/A'}, TP: {entry_tp:.2f if entry_tp else 'N/A'}"
            else: # Pyramiding into existing LONG position
                new_total_qty = pos_details['qty'] + quantity_to_trade
                new_avg_price = ((pos_details['avg_price'] * pos_details['qty']) + (exec_price_buy * quantity_to_trade)) / new_total_qty
                pos_details['qty'] = new_total_qty
                pos_details['avg_price'] = new_avg_price
                pos_details['num_entries'] = pos_details.get('num_entries', 0) + 1
                # SL/TP for pyramided position might need recalculation or use the latest signal's SL/TP.
                # For simplicity, let's assume the latest signal's SL/TP applies to the whole position, or they are None.
                if entry_sl: pos_details['stop_loss'] = entry_sl 
                if entry_tp: pos_details['target'] = entry_tp
                log_msg_details = f"Pyramid Entry #{pos_details['num_entries']}. New AvgPx: {new_avg_price:.2f}. SL: {entry_sl:.2f if entry_sl else 'N/A'}, TP: {entry_tp:.2f if entry_tp else 'N/A'}"

            log_action_msg = f"EXECUTED: BUY {quantity_to_trade} {self.symbol} at {exec_price_buy:.2f}. {log_msg_details}"
            print(f"{current_bar_data.name} - {log_action_msg}")
            if self.trade_logger: 
                self.trade_logger.log_trade(
                    self.strategy.name, self.symbol, "BACKTEST", action, quantity_to_trade, exec_price_buy, "MARKET", 
                    status="EXECUTED_BUY", 
                    stop_loss=self.positions[self.symbol]['stop_loss'], 
                    target=self.positions[self.symbol]['target'], 
                    remarks=f"Capital: {self.current_capital:.2f}. {log_msg_details}"
                )
        # (No explicit SELL entry logic for short positions here, this was handled above)

    def _check_sl_tp(self, current_bar_data):
        if not self.positions.get(self.symbol):
            return

        pos_details = self.positions[self.symbol]
        qty = pos_details['qty']
        entry_price = pos_details['avg_price']
        sl_price = pos_details.get('stop_loss')
        tp_price = pos_details.get('target')
        entry_type = pos_details.get('entry_type', 'LONG')

        exit_reason = None
        exit_price = None

        if entry_type == 'LONG':
            if sl_price and current_bar_data['low'] <= sl_price:
                exit_price = self._apply_slippage(sl_price, 'SELL')
                exit_reason = "STOP_LOSS_HIT"
            elif tp_price and current_bar_data['high'] >= tp_price:
                exit_price = self._apply_slippage(tp_price, 'SELL')
                exit_reason = "TARGET_HIT"
        # Add logic for SHORT positions if implemented (e.g. if current_bar_data['high'] >= sl_price for short)

        if exit_reason:
            brokerage = self._calculate_brokerage(exit_price * qty)
            pnl = (exit_price - entry_price) * qty - brokerage # For LONG

            self.current_capital += (qty * exit_price) - brokerage
            log_msg = f"{exit_reason}: SELL {qty} {self.symbol} at {exit_price:.2f} (from entry {entry_price:.2f}). PnL: {pnl:.2f}"
            print(f"{current_bar_data.name} - {log_msg}")

            if pnl > 0: self.winning_trades +=1
            else: self.losing_trades +=1
            self.total_trades +=1
            
            self.trades.append({
                'symbol': self.symbol, 'entry_time': pos_details['entry_time'], 'exit_time': current_bar_data.name,
                'entry_price': entry_price, 'exit_price': exit_price, 'qty': qty,
                'pnl': pnl, 'type': entry_type, 'exit_reason': exit_reason
            })
            del self.positions[self.symbol]

            if self.trade_logger: self.trade_logger.log_trade(self.strategy.name, self.symbol, "BACKTEST", "SELL", qty, exit_price, "MARKET", status=exit_reason, remarks=f"Capital: {self.current_capital:.2f}, Trade PnL: {pnl:.2f}")


    def run(self):
        if self.data.empty:
            print("Cannot run backtest: Data is empty or not loaded correctly.")
            return None

        print(f"--- Running Backtest for Strategy: {self.strategy.name} on {self.symbol} ---")
        
        for timestamp, current_bar in self.data.iterrows():
            self._check_sl_tp(current_bar) # Check SL/TP first

            if not self.positions.get(self.symbol): # Only consider new entry signals if no position
                data_for_signal = self.data[self.data.index <= timestamp] # Data up to current bar
                
                # Strategy's generate_signals method should return a dict like:
                # {'action': 'BUY'/'SELL', 'price': (optional price), 'sl': (optional sl), 'tp': (optional tp)}
                # or None/{} if no signal.
                signal_output = self.strategy.generate_signals(historical_data=data_for_signal)

                if signal_output and isinstance(signal_output, dict) and signal_output.get('action') in ['BUY', 'SELL']:
                    self._execute_signal(signal_output, current_bar)
                
        self._generate_summary()
        print(f"--- Backtest Finished for Strategy: {self.strategy.name} on {self.symbol} ---")
        return self.trades

    def _generate_summary(self):
        final_capital = self.current_capital
        unrealized_pnl = 0.0
        if self.positions.get(self.symbol):
            pos_details = self.positions[self.symbol]
            last_close_price = self.data['close'].iloc[-1]
            if pos_details['entry_type'] == 'LONG':
                unrealized_pnl = (last_close_price - pos_details['avg_price']) * pos_details['qty']
            # Add for SHORT if implemented
            final_capital += unrealized_pnl
            print(f"Note: Backtest ended with an open position for {self.symbol}. Qty: {pos_details['qty']} at {pos_details['avg_price']:.2f}. Last close: {last_close_price:.2f}. Unrealized PnL: {unrealized_pnl:.2f}")

        realized_pnl_from_trades = sum(t['pnl'] for t in self.trades)
        # Total PNL should be final_capital - initial_capital, which accounts for realized and unrealized.
        total_pnl = final_capital - self.initial_capital
        
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        print("--- Backtest Summary ---")
        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Initial Capital: {self.initial_capital:.2f}")
        print(f"Final Capital: {final_capital:.2f}")
        print(f"Total P&L (Realized + Unrealized): {total_pnl:.2f}")
        print(f"Realized P&L (from closed trades): {realized_pnl_from_trades:.2f}")
        print(f"Unrealized P&L (from open positions): {unrealized_pnl:.2f}")
        print(f"Total Trades Closed: {self.total_trades}")
        print(f"Winning Trades: {self.winning_trades}")
        print(f"Losing Trades: {self.losing_trades}")
        print(f"Win Rate: {win_rate:.2f}%")
        
        # Calculate total brokerage from closed trades
        total_brokerage = 0
        for t in self.trades:
            entry_trade_value = t['entry_price'] * t['qty']
            exit_trade_value = t['exit_price'] * t['qty']
            total_brokerage += self._calculate_brokerage(entry_trade_value) + self._calculate_brokerage(exit_trade_value)
        print(f"Total Brokerage Paid (Estimated from closed trades): {total_brokerage:.2f}")


        if self.trade_logger:
            self.trade_logger.log_daily_summary( # This logs as a single "daily" summary for the whole backtest period
                realized_pnl = realized_pnl_from_trades,
                unrealized_pnl = unrealized_pnl,
                capital_start = self.initial_capital,
                capital_end = final_capital,
                trades_count = self.total_trades,
                winning_trades = self.winning_trades,
                losing_trades = self.losing_trades
            )

# Example usage (for testing this file directly)
if __name__ == '__main__':
    print("BacktestEngine class defined. This __main__ block is for basic testing.")
    
    # --- Mock Objects for standalone testing ---
    # Redefine mocks here as they might not be available if relative imports failed
    class MockTradeLoggerForTest:
        def __init__(self, log_dir="logs_backtest_test"):
            self.log_dir = log_dir
            os.makedirs(self.log_dir, exist_ok=True)
            self.trade_log_file = os.path.join(self.log_dir, "test_trades.csv")
            self.summary_file = os.path.join(self.log_dir, "test_summary.csv")
            # Clear/Create files with headers
            with open(self.trade_log_file, 'w') as f: f.write("Timestamp,Strategy,Symbol,Exchange,Action,Quantity,Price,OrderType,StopLoss,Target,OrderID,Status,Remarks\n")
            with open(self.summary_file, 'w') as f: f.write("Date,RealizedPnL,UnrealizedPnL,TotalPnL,CapitalStartOfDay,CapitalEndOfDay,TradesCount,WinningTrades,LosingTrades\n")
            print(f"MockTradeLoggerForTest: Log files will be in {os.path.abspath(self.log_dir)}")

        def log_trade(self, strategy_name, symbol, exchange, action, quantity, price, order_type, stop_loss=None, target=None, order_id=None, status='PENDING', remarks=''):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            log_entry = f"{timestamp},{strategy_name},{symbol},{exchange},{action},{quantity},{price:.2f},{order_type},{stop_loss if stop_loss else 'N/A'},{target if target else 'N/A'},{order_id if order_id else 'N/A'},{status},{remarks}\n"
            # print(f"LOG_TRADE: {log_entry.strip()}")
            with open(self.trade_log_file, 'a') as f: f.write(log_entry)

        def log_daily_summary(self, realized_pnl, unrealized_pnl, capital_start, capital_end, trades_count, winning_trades, losing_trades):
            date_today = datetime.now().strftime('%Y-%m-%d') # For backtest summary, this date is just "today"
            total_pnl = realized_pnl + unrealized_pnl
            log_entry = f"{date_today},{realized_pnl:.2f},{unrealized_pnl:.2f},{total_pnl:.2f},{capital_start:.2f},{capital_end:.2f},{trades_count},{winning_trades},{losing_trades}\n"
            # print(f"LOG_SUMMARY: {log_entry.strip()}")
            with open(self.summary_file, 'a') as f: f.write(log_entry)
    
    class MockStrategyForTest:
        def __init__(self, name, params=None):
            self.name = name
            self.params = params or {}
        
        def generate_signals(self, historical_data):
            if len(historical_data) < 2: return None
            current_close = historical_data['close'].iloc[-1]
            prev_close = historical_data['close'].iloc[-2]
            
            # Simple Crossover-like logic for testing
            if current_close > prev_close * 1.01: # Buy if price increases by 1%
                 return {'action': 'BUY', 'price': current_close} # SL/TP will use engine defaults
            elif current_close < prev_close * 0.99: # Sell if price decreases by 1% (to close long)
                return {'action': 'SELL', 'price': current_close, 'reason': 'STRATEGY_CLOSE_CONDITION'}
            return None

    # --- Create dummy CSV data ---
    dummy_data_dir = "temp_historical_data" # Create in cwd for easy cleanup
    os.makedirs(dummy_data_dir, exist_ok=True)
    dummy_csv_file = os.path.join(dummy_data_dir, "DUMMY_TEST_EQ.csv")
    
    header = "Date,Open,High,Low,Close,Volume\n" # Using 'Date' as commonly found
    data_rows = [ # Timestamps need to be parsable by pd.to_datetime
        "2023-01-01 09:15:00,100,102,99,100,1000\n",  # Start
        "2023-01-02 09:15:00,100,102,99,101.5,1200\n",# BUY signal (101.5 > 100 * 1.01)
        "2023-01-03 09:15:00,101.5,104,101,103,1100\n",# Hold (TP might hit if default is small)
        "2023-01-04 09:15:00,103,103,95,98,1500\n",   # SELL signal (98 < 103 * 0.99) or SL hit
        "2023-01-05 09:15:00,98,99,97,98.5,1300\n",  # BUY signal
        "2023-01-06 09:15:00,98.5,105,98,104,1400\n", # TP hit (if bought at 98.5, TP e.g. 98.5 * 1.04 = 102.44)
    ]
    with open(dummy_csv_file, 'w') as f:
        f.write(header)
        for row in data_rows:
            f.write(row)
    print(f"Dummy CSV created at: {os.path.abspath(dummy_csv_file)}")

    # --- Test BacktestEngine ---
    if os.path.exists(dummy_csv_file):
        print("\n--- Running Mock Backtest from __main__ ---")
        mock_logger_instance = MockTradeLoggerForTest()
        # If BaseStrategy was not imported, MockStrategyForTest will be used.
        mock_strategy_instance = MockStrategyForTest(name="TestMockStrategy")
        
        engine = BacktestEngine(
            historical_data_source=dummy_csv_file,
            strategy=mock_strategy_instance, # Pass the instance
            initial_capital=100000,
            start_date="2023-01-01",
            end_date="2023-01-06", # Ensure this covers all data
            trade_logger=mock_logger_instance, # Pass the instance
            symbol="DUMMY_TEST_EQ",
            stop_loss_percent=2.0, 
            target_percent=4.0,
            qty_per_trade=10, # Fixed quantity
            brokerage_percent=0.01, # 0.01% brokerage
            slippage_percent=0.005 # 0.005% slippage
        )
        if not engine.data.empty:
            engine.run()
        else:
            print("Failed to initialize engine with data, cannot run mock backtest from __main__.")
        
        # Basic cleanup (optional)
        # import shutil
        # shutil.rmtree(dummy_data_dir)
        # shutil.rmtree(mock_logger_instance.log_dir)
        # print(f"Cleaned up dummy data and log directories: {dummy_data_dir}, {mock_logger_instance.log_dir}")

    else:
        print(f"Dummy CSV file {dummy_csv_file} not found. Cannot run mock test from __main__.")

```
