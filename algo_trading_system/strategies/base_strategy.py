# algo_trading_system/strategies/base_strategy.py
from abc import ABC, abstractmethod
import pandas as pd # Ensure pandas is imported if not already

# Assuming BacktestEngine will be importable from core
# Adjust path if necessary based on your project structure and how it's run
try:
    from ..core.backtest_engine import BacktestEngine
except ImportError:
    print("Could not import BacktestEngine in BaseStrategy. Ensure it's accessible.")
    BacktestEngine = None # Placeholder if import fails, real run from main.py should ensure it's available

class BaseStrategy(ABC):
    def __init__(self, name, broker_api, logger, params=None): # logger is TradeLogger
        self.name = name
        self.broker_api = broker_api # For live trading
        self.logger = logger       # For logging trades (passed to BacktestEngine)
        self.params = params if params else {}
        # print(f"Strategy '{self.name}' initialized with params: {self.params}") # Keep or remove startup print

    @abstractmethod
    def generate_signals(self, historical_data: pd.DataFrame):
        """
        Generates trading signals based on historical data.
        This method should be implemented by each specific strategy.

        Args:
            historical_data (pd.DataFrame): DataFrame containing historical
                                             market data (OHLCV) with a DateTimeIndex.
                                             The BacktestEngine will pass data up to the current point in time.

        Returns:
            (dict or None): A dictionary representing the signal, e.g.,
                            {'action': 'BUY', 'price': entry_price, 'sl': sl_price, 'tp': tp_price}
                            or {'action': 'SELL', 'price': exit_price}
                            Return None or {} if no signal.
        """
        pass

    @abstractmethod
    def execute_trade(self, signal, symbol, quantity, exchange='NSE', product='CNC', order_type='MARKET', stop_loss=None, target=None):
        """
        Executes a trade based on the generated signal in a LIVE environment.
        This method is primarily for live trading. Backtesting simulates trades.
        Logs the trade attempt and result.
        """
        pass
        
    def run_backtest(self, 
                     historical_data_source, # Path to CSV or DataFrame
                     symbol, 
                     initial_capital,
                     start_date,
                     end_date,
                     qty_per_trade, # Can be made more dynamic later
                     stop_loss_percent=None, # Default SL %
                     target_percent=None,    # Default TP %
                     brokerage_percent=0.0,
                     slippage_percent=0.0):
        """
        Runs a backtest of the strategy using the BacktestEngine.

        Args:
            historical_data_source (str or pd.DataFrame): Path to CSV data file or DataFrame.
            symbol (str): The trading symbol.
            initial_capital (float): Starting capital for the backtest.
            start_date (str or datetime): Backtest start date.
            end_date (str or datetime): Backtest end date.
            qty_per_trade (int): Quantity for each trade (can be made dynamic later).
            stop_loss_percent (float, optional): Default stop-loss if not set by strategy signals.
            target_percent (float, optional): Default target if not set by strategy signals.
            brokerage_percent (float, optional): Brokerage fee per trade.
            slippage_percent (float, optional): Slippage per trade.
        """
        print(f"--- Preparing backtest for strategy '{self.name}' on {symbol} ---")

        if BacktestEngine is None:
            print("ERROR: BacktestEngine class not imported. Cannot run backtest.")
            if self.logger:
                self.logger.log_trade(self.name, symbol, "BACKTEST", "SETUP_FAIL", 0,0,"-", status="FAILURE", remarks="BacktestEngine not available")
            return None
        
        if self.logger is None:
            print("WARNING: TradeLogger not provided to strategy. Backtest results might not be fully logged.")
            # Optionally, create a dummy logger here if essential, but better to ensure it's passed.

        engine = BacktestEngine(
            historical_data_source=historical_data_source,
            strategy=self, # Pass the instance of the current strategy
            initial_capital=initial_capital,
            start_date=start_date,
            end_date=end_date,
            trade_logger=self.logger, # Pass the strategy's logger to the engine
            symbol=symbol,
            stop_loss_percent=stop_loss_percent,
            target_percent=target_percent,
            brokerage_percent=brokerage_percent,
            slippage_percent=slippage_percent,
            qty_per_trade=qty_per_trade
        )
        
        results = engine.run() # This will execute the backtest
        
        if results is not None:
            print(f"--- Backtest completed for strategy '{self.name}' on {symbol}. Total trades logged: {len(results)} ---")
        else:
            print(f"--- Backtest for strategy '{self.name}' on {symbol} encountered issues or produced no trades. ---")
        
        return results # The BacktestEngine.run() returns the list of trades

    # run_live method can remain as is for now, it's for future live trading logic.
    def run_live(self, symbol: str, quantity_per_trade: int, 
                 exchange: str = None, product: str = None, order_type: str = None): # Removed SL/TP points from here
        """
        Placeholder for running the strategy in a live trading environment.
        This would typically involve a loop that fetches real-time data.
        SL/TP prices should come from the signal generated by generate_signals.
        """
        print(f"Running live strategy '{self.name}' for {symbol} (simulated iteration)...")
        
        # In a real live trading loop, you'd get live market data here.
        # For this example, we'll assume generate_signals can work with None or mock data if needed for a single pass.
        # Or, you might fetch a small amount of recent historical data to feed to generate_signals.
        mock_live_data = None # Replace with actual live data fetching logic
        
        signal_details = self.generate_signals(historical_data=mock_live_data) 

        if signal_details and isinstance(signal_details, dict) and signal_details.get('action') in ['BUY', 'SELL']:
            action = signal_details.get('action')
            print(f"Live: Signal {action} for {symbol}. Attempting to execute trade.")
            
            # Extract SL/TP prices from the signal if present
            sl_price_from_signal = signal_details.get('sl_price')
            tp_price_from_signal = signal_details.get('tp_price') # Target for monitoring/separate order

            # Determine order type for entry. If SL is present, we might place an SL order for entry,
            # or a market/limit order for entry and then a separate SL order.
            # For now, let's assume the primary order_type is for entry (e.g. MARKET or LIMIT).
            # If strategy wants to place an SL order directly as entry, it should specify order_type='SL' in signal.
            
            effective_order_type = signal_details.get('order_type_for_entry') or order_type or self.params.get('default_order_type', 'MARKET')
            limit_price_for_entry = signal_details.get('price') # Price for LIMIT entry

            # If the strategy is to place an SL order immediately after a MARKET/LIMIT entry,
            # that would be a second call to execute_trade or a more complex order type (BO/CO).
            # Here, we pass sl_price_from_signal to execute_trade. If effective_order_type is SL/SL-M,
            # execute_trade will use sl_price_from_signal as the trigger_price.
            
            self.execute_trade(
                signal=signal_details, # Pass the whole signal dict
                symbol=symbol, 
                quantity=quantity_per_trade,
                exchange=exchange, # Or get from params/signal
                product=product,   # Or get from params/signal
                order_type=effective_order_type, # E.g. MARKET, LIMIT, or SL/SL-M for entry
                stop_loss_price=sl_price_from_signal, # Used as trigger if order_type is SL/SL-M
                target_price=tp_price_from_signal # Logged by execute_trade, or used for separate target order
            )
            
            # Further logic could follow, e.g., if entry order was MARKET/LIMIT,
            # and sl_price_from_signal is set, place a separate SL order.
            # if effective_order_type in ['MARKET', 'LIMIT'] and sl_price_from_signal:
            #     print(f"Live: Entry order placed. Now consider placing separate SL order at {sl_price_from_signal}")
            #     # self.execute_trade({'action': 'SELL' if action=='BUY' else 'BUY', ...}, order_type='SL-M', stop_loss_price=sl_price_from_signal)

        elif signal_details: 
             print(f"Live: Signal {signal_details} for {symbol}. No trade action taken.")
        else:
            print(f"Live: No signal generated for {symbol}.")
            
        print(f"Live strategy '{self.name}' iteration complete (simulated).")
