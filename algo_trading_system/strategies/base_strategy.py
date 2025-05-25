# algo_trading_system/strategies/base_strategy.py
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, name, broker_api, logger, params=None):
        self.name = name
        self.broker_api = broker_api
        self.logger = logger
        self.params = params if params else {}
        print(f"Strategy '{self.name}' initialized with params: {self.params}")

    @abstractmethod
    def generate_signals(self, historical_data=None):
        """
        Generates trading signals based on historical data or real-time ticks.
        This method should be implemented by each specific strategy.

        Args:
            historical_data (pd.DataFrame, optional): DataFrame containing historical
                                                     market data (OHLCV). Required for
                                                     backtesting or strategies that need
                                                     a lookback period.

        Returns:
            (str or None): A signal like 'BUY', 'SELL', 'HOLD', or None.
                           Or a more complex object representing the signal.
        """
        pass

    @abstractmethod
    def execute_trade(self, signal, symbol, quantity, exchange='NSE', product='CNC', order_type='MARKET', stop_loss=None, target=None):
        """
        Executes a trade based on the generated signal.
        Logs the trade attempt and result.
        """
        pass
        
    def run_backtest(self, historical_data, symbol, quantity_per_trade, exchange='NSE', product='CNC', order_type='MARKET'):
        """
        Runs a backtest of the strategy using historical data.
        This is a generic backtesting loop; can be customized.
        """
        print(f"Running backtest for strategy '{self.name}' on {symbol}...")
        if historical_data is None or historical_data.empty:
            print("Error: Historical data is required for backtesting.")
            return

        # Simplified backtesting loop example:
        for i in range(len(historical_data)):
            # For simplicity, assume generate_signals can use a slice of data up to current point
            # More realistic would be to pass data window to generate_signals
            current_data_point = historical_data.iloc[[i]] # Or a window: historical_data.iloc[:i+1]
            signal = self.generate_signals(historical_data=current_data_point) 

            if signal == 'BUY' or signal == 'SELL':
                print(f"Backtest: {current_data_point.get('timestamp', 'N/A')} - Signal: {signal} for {symbol}")
                # In a real backtest, you'd simulate order execution, track portfolio, P&L, etc.
                # For now, just log the signal intention
                if self.logger:
                    self.logger.log_trade(
                        strategy_name=self.name,
                        symbol=symbol,
                        exchange=exchange,
                        action=signal,
                        quantity=quantity_per_trade,
                        price=current_data_point['close'].iloc[0] if 'close' in current_data_point else 0, # Example price
                        order_type=order_type,
                        status='BACKTEST_SIGNAL',
                        remarks=f"Signal at {current_data_point.get('timestamp', 'N/A')}"
                    )
            elif signal == 'HOLD':
                pass # print(f"Backtest: {current_data_point.get('timestamp', 'N/A')} - Signal: HOLD")

        print(f"Backtest for strategy '{self.name}' completed.")


    def run_live(self, symbol, quantity_per_trade, exchange='NSE', product='CNC', order_type='MARKET', stop_loss_points=None, target_points=None):
        """
        Runs the strategy in a live trading environment (simulated for now).
        This would typically involve a loop that fetches real-time data.
        """
        print(f"Running live strategy '{self.name}' for {symbol} (simulated)...")
        # Placeholder for live trading logic (e.g., using a WebSocket for ticks)
        # For now, simulate a few ticks or a single signal generation
        
        # Example: Generate one signal based on some (mock) current market condition
        # In reality, this would come from live market data feed
        signal = self.generate_signals(historical_data=None) # Pass appropriate data if needed

        if signal == 'BUY' or signal == 'SELL':
            print(f"Live: Signal {signal} for {symbol}. Attempting to execute trade.")
            
            # Determine stop-loss and target prices if applicable
            # This is a simplified example; actual price fetching for SL/TP would be needed
            current_price_for_trade = 100 # Mock price; get this from market data in real scenario
            
            sl_price = None
            tp_price = None

            if stop_loss_points:
                sl_price = current_price_for_trade - stop_loss_points if signal == 'BUY' else current_price_for_trade + stop_loss_points
            if target_points:
                tp_price = current_price_for_trade + target_points if signal == 'BUY' else current_price_for_trade - target_points

            self.execute_trade(
                signal=signal, 
                symbol=symbol, 
                quantity=quantity_per_trade,
                exchange=exchange,
                product=product,
                order_type=order_type,
                stop_loss=sl_price,
                target=tp_price
            )
        elif signal: # HOLD or other non-action signals
             print(f"Live: Signal {signal} for {symbol}. No action taken.")
        else:
            print(f"Live: No signal generated for {symbol}.")
            
        print(f"Live strategy '{self.name}' iteration complete (simulated).")
