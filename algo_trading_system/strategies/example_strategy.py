# algo_trading_system/strategies/example_strategy.py
from .base_strategy import BaseStrategy
import random # For simple signal generation in this example

class ExampleStrategy(BaseStrategy):
    def __init__(self, broker_api, logger, params=None):
        # Example parameters: {'rsi_period': 14, 'ma_period': 50}
        default_params = {'mode': 'optimistic'} # Example default
        if params:
            default_params.update(params)

        super().__init__(name="ExampleStrategy", broker_api=broker_api, logger=logger, params=default_params)

    def generate_signals(self, historical_data=None):
        """
        Generates a random BUY, SELL, or HOLD signal for demonstration.
        In a real strategy, this would involve technical indicators, market data analysis, etc.
        
        Args:
            historical_data (pd.DataFrame, optional): Not used in this simple example
                                                     but available for more complex strategies.
        """
        # Simple random signal for demonstration
        # In a real strategy, you'd analyze historical_data or live ticks
        # For example, if historical_data is available:
        # if historical_data is not None and not historical_data.empty:
        #     latest_close = historical_data['close'].iloc[-1]
        #     # ... some logic based on latest_close ...

        if self.params.get('mode') == 'optimistic':
            signals = ['BUY', 'HOLD'] # More likely to buy
        elif self.params.get('mode') == 'pessimistic':
            signals = ['SELL', 'HOLD'] # More likely to sell
        else:
            signals = ['BUY', 'SELL', 'HOLD']
            
        signal = random.choice(signals)
        print(f"{self.name}: Generated signal: {signal} (using mode: {self.params.get('mode')})")
        return signal

    def execute_trade(self, signal, symbol, quantity, exchange='NSE', product='CNC', order_type='MARKET', stop_loss=None, target=None):
        """
        Executes a trade based on the generated signal using the broker API.
        Logs the trade attempt and result via the logger.
        """
        print(f"{self.name}: Attempting to execute trade: {signal} {quantity} of {symbol} on {exchange}")
        
        if not self.broker_api:
            print(f"{self.name}: Error - Broker API not available.")
            if self.logger:
                self.logger.log_trade(
                    strategy_name=self.name, symbol=symbol, exchange=exchange, action=signal, 
                    quantity=quantity, price=0, order_type=order_type, 
                    stop_loss=stop_loss, target=target, order_id=None, 
                    status='FAILED', remarks='Broker API not available'
                )
            return None

        # In a real scenario, get current market price for market orders or use limit price
        # For mock, we might not have a live price feed easily available here.
        # The broker_api.place_order might handle price for MARKET orders internally.
        mock_execution_price = 100.0 # Placeholder if needed for logging before actual execution

        order_id = self.broker_api.place_order(
            exchange=exchange,
            tradingsymbol=symbol,
            transaction_type=signal, # Assuming signal is 'BUY' or 'SELL'
            quantity=quantity,
            product=product,
            order_type=order_type,
            price=None if order_type == 'MARKET' else mock_execution_price, # Price needed for LIMIT, etc.
            # variety='regular', # Default in mock broker
            # trigger_price=None # For SL-M orders
        )

        if order_id:
            print(f"{self.name}: Trade executed successfully. Order ID: {order_id}")
            if self.logger:
                self.logger.log_trade(
                    strategy_name=self.name, symbol=symbol, exchange=exchange, action=signal, 
                    quantity=quantity, price=mock_execution_price, # Log estimated or actual fill price
                    order_type=order_type, stop_loss=stop_loss, target=target, 
                    order_id=order_id, status='PLACED', # Or 'EXECUTED' if broker confirms immediately
                    remarks=f"Trade placed via {self.name}"
                )
        else:
            print(f"{self.name}: Trade execution failed.")
            if self.logger:
                self.logger.log_trade(
                    strategy_name=self.name, symbol=symbol, exchange=exchange, action=signal, 
                    quantity=quantity, price=mock_execution_price, order_type=order_type,
                    stop_loss=stop_loss, target=target, order_id=None, 
                    status='FAILED', remarks=f"Broker rejected order or error in placement"
                )
        return order_id

if __name__ == '__main__':
    # This is for direct testing of the strategy file.
    # In the main application, these would be initialized and passed from elsewhere.
    
    # Mock Broker API
    class MockBroker:
        def place_order(self, **kwargs):
            print(f"MockBroker: Placing order with details: {kwargs}")
            return f"mock_order_{random.randint(1000,9999)}"

    # Mock Logger
    class MockLogger:
        def log_trade(self, **kwargs):
            print(f"MockLogger: Logging trade: {kwargs}")
        def update_trade_status(self, **kwargs):
            print(f"MockLogger: Updating trade status: {kwargs}")
            
    mock_broker = MockBroker()
    mock_logger = MockLogger()

    # Test optimistic strategy
    print("\n--- Testing Optimistic ExampleStrategy ---")
    optimistic_params = {'mode': 'optimistic'}
    strategy_opt = ExampleStrategy(broker_api=mock_broker, logger=mock_logger, params=optimistic_params)
    # Simulate live run
    strategy_opt.run_live(symbol="TESTOPT", quantity_per_trade=10, stop_loss_points=5, target_points=10)
    
    # Test pessimistic strategy
    print("\n--- Testing Pessimistic ExampleStrategy ---")
    pessimistic_params = {'mode': 'pessimistic'}
    strategy_pess = ExampleStrategy(broker_api=mock_broker, logger=mock_logger, params=pessimistic_params)
    # Simulate live run
    strategy_pess.run_live(symbol="TESTPESS", quantity_per_trade=5)

    # Example of generating a signal directly
    # print("\n--- Generating a single signal ---")
    # signal = strategy_opt.generate_signals()
    # print(f"Generated signal: {signal}")
    # if signal in ['BUY', 'SELL']:
    #     strategy_opt.execute_trade(signal, "TESTINFY", 1, exchange="NSE", product="CNC", order_type="MARKET")

    # Example of backtest (requires historical_data as DataFrame)
    # print("\n--- Example Backtest Run (conceptual) ---")
    # try:
    #     import pandas as pd
    #     # Create dummy historical data for the backtest example
    #     dummy_data = pd.DataFrame({
    #         'timestamp': pd.to_datetime(['2023-01-01 09:15:00', '2023-01-01 09:16:00', '2023-01-01 09:17:00']),
    #         'open': [100, 101, 102],
    #         'high': [102, 102, 103],
    #         'low': [99, 100, 101],
    #         'close': [101, 102, 100], # Example: price drops at the end
    #         'volume': [1000, 1200, 1100]
    #     })
    #     strategy_opt.run_backtest(historical_data=dummy_data, symbol="TESTBACK", quantity_per_trade=1)
    # except ImportError:
    #     print("Pandas not installed. Skipping backtest example that uses DataFrame.")
    # except Exception as e:
    #     print(f"Error during backtest example: {e}")
