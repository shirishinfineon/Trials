# algo_trading_system/strategies/sma_crossover_strategy.py
import pandas as pd
from .base_strategy import BaseStrategy # Assuming BaseStrategy is in the same directory

class SmaCrossoverStrategy(BaseStrategy):
    def __init__(self, name, broker_api, logger, params=None):
        super().__init__(name, broker_api, logger, params)
        self.short_window = self.params.get('short_window', 20)
        self.long_window = self.params.get('long_window', 50)
        
        if not isinstance(self.short_window, int) or not isinstance(self.long_window, int) or \
           self.short_window <= 0 or self.long_window <= 0:
            raise ValueError("SMA window parameters (short_window, long_window) must be positive integers.")
        if self.short_window >= self.long_window:
            raise ValueError("Short SMA window must be less than Long SMA window.")

        # To keep track of the previous state of SMAs to detect crossover
        self.short_sma_prev = None
        self.long_sma_prev = None
        self.data_buffer = pd.DataFrame() # To accumulate enough data for SMA calculation

        print(f"SmaCrossoverStrategy '{self.name}' initialized with Short Window: {self.short_window}, Long Window: {self.long_window}")

    def generate_signals(self, historical_data: pd.DataFrame):
        """
        Generates trading signals based on SMA crossover.
        Requires historical_data to have a 'close' column.
        The BacktestEngine passes data up to the current point in time.
        """
        if historical_data.empty or 'close' not in historical_data.columns:
            # Log this or handle as per strategy design
            # print(f"{self.name}: Historical data is empty or missing 'close' column.")
            return None 

        # For SMA calculation, we need at least `long_window` periods of data.
        # The historical_data passed from BacktestEngine is cumulative.
        if len(historical_data) < self.long_window:
            # print(f"{self.name}: Not enough data for SMA calculation. Need {self.long_window}, have {len(historical_data)}")
            return None # Not enough data to calculate long SMA

        # Calculate SMAs using the provided historical_data
        short_sma = historical_data['close'].rolling(window=self.short_window).mean().iloc[-1]
        long_sma = historical_data['close'].rolling(window=self.long_window).mean().iloc[-1]
        
        current_price = historical_data['close'].iloc[-1] # For signal price or SL/TP base

        signal = None
        # Check for crossover only if we have previous SMA values
        if self.short_sma_prev is not None and self.long_sma_prev is not None:
            # BUY signal: Short SMA crosses above Long SMA
            if self.short_sma_prev <= self.long_sma_prev and short_sma > long_sma:
                print(f"{historical_data.index[-1]} - {self.name}: BUY signal. Short SMA ({short_sma:.2f}) crossed above Long SMA ({long_sma:.2f})")
                signal = {'action': 'BUY', 'price': current_price}
                
                # Add SL/TP based on strategy parameters if they exist
                sl_percentage = self.params.get('stop_loss_percent') # e.g., 2 for 2%
                tp_percentage = self.params.get('target_percent')   # e.g., 4 for 4%

                if sl_percentage:
                    signal['sl_price'] = current_price * (1 - (sl_percentage / 100.0))
                if tp_percentage:
                    signal['tp_price'] = current_price * (1 + (tp_percentage / 100.0))
                
            # SELL signal: Short SMA crosses below Long SMA (to close a long position or open short)
            elif self.short_sma_prev >= self.long_sma_prev and short_sma < long_sma:
                print(f"{historical_data.index[-1]} - {self.name}: SELL signal. Short SMA ({short_sma:.2f}) crossed below Long SMA ({long_sma:.2f})")
                signal = {
                    'action': 'SELL',
                    'price': current_price,
                    'reason': 'SMA_CROSS_DOWN'
                }
                # If short selling, SL/TP would be calculated differently:
                # sl_percentage = self.params.get('stop_loss_percent') 
                # tp_percentage = self.params.get('target_percent')
                # if sl_percentage: signal['sl_price'] = current_price * (1 + (sl_percentage / 100.0))
                # if tp_percentage: signal['tp_price'] = current_price * (1 - (tp_percentage / 100.0))
        
        # Update previous SMA values for the next iteration
        self.short_sma_prev = short_sma
        self.long_sma_prev = long_sma
        
        return signal

    def execute_trade(self, signal: dict, symbol: str, quantity: int, 
                          exchange: str = None, product: str = None, order_type: str = None,
                          stop_loss_price: float = None, # Actual price for SL
                          target_price: float = None     # Actual price for TP
                         ):
            """
            Executes a trade in a LIVE environment using the broker API.
            This method is called by the live trading loop.
            'signal' is a dictionary expected to contain at least {'action': 'BUY'/'SELL'}.
            It can optionally contain 'price' for LIMIT orders.
            'stop_loss_price' and 'target_price' are actual price levels.
            """
            if not self.broker_api:
                msg = f"{self.name}: Broker API not available. Cannot execute live trade."
                print(msg)
                if self.logger: self.logger.log_trade(self.name, symbol, exchange or 'NSE', signal.get('action', 'UNKNOWN'), quantity, signal.get('price',0), order_type or self.params.get('default_order_type', 'MARKET'), status="FAILURE", remarks="Broker API unavailable")
                return None

            action = signal.get('action')
            if not action or action.upper() not in ["BUY", "SELL"]:
                msg = f"{self.name}: Invalid or missing action in signal: {action}"
                print(msg)
                if self.logger: self.logger.log_trade(self.name, symbol, exchange or 'NSE', str(action), quantity, 0, order_type, status="REJECTED", remarks=msg)
                return None

            # Get defaults from strategy params if not provided in method call
            current_exchange = exchange or self.params.get('default_exchange', 'NSE')
            current_product = product or self.params.get('default_product_type', 'MIS') # Get from strategy params
            current_order_type = order_type or self.params.get('default_order_type', 'MARKET') # Get from strategy params
            
            # Price for LIMIT orders, from signal or None for MARKET
            limit_price = signal.get('price') 

            order_params = {
                "variety": "regular", # Could be 'amo'. BO/CO varieties are more complex.
                "exchange": current_exchange.upper(),
                "tradingsymbol": symbol,
                "transaction_type": action.upper(),
                "quantity": quantity,
                "product": current_product.upper(),
                "order_type": current_order_type.upper(),
            }

            if order_params["order_type"] == "LIMIT":
                if not limit_price:
                    msg = f"{self.name}: Limit price not provided for LIMIT order. Symbol: {symbol}"
                    print(msg)
                    if self.logger: self.logger.log_trade(self.name, symbol, current_exchange, action, quantity, 0, current_order_type, status="REJECTED", remarks=msg)
                    return None
                order_params["price"] = limit_price
            
            # Handling SL/SL-M orders: these require a trigger_price.
            # The 'stop_loss_price' argument to this function is used as the trigger_price.
            if order_params["order_type"] in ["SL", "SL-M"]:
                # For a BUY SL order, trigger_price is the stop loss buy price.
                # For a SELL SL order (to exit a long), trigger_price is the stop loss sell price.
                if not stop_loss_price: # stop_loss_price here means the trigger price for SL/SL-M
                    msg = f"{self.name}: Trigger price (stop_loss_price) not provided for {current_order_type} order. Symbol: {symbol}"
                    print(msg)
                    if self.logger: self.logger.log_trade(self.name, symbol, current_exchange, action, quantity, 0, current_order_type, status="REJECTED", remarks=msg)
                    return None
                order_params["trigger_price"] = stop_loss_price
                # SL-M orders usually don't need a limit price, SL orders do.
                # KiteConnect handles this; if it's an SL order, it might also need a limit price slightly away from trigger.
                # For simplicity, if it's SL and limit_price is also given, we pass it.
                if order_params["order_type"] == "SL" and limit_price:
                     order_params["price"] = limit_price # Price at which SL order will be placed once triggered

            # Note: Zerodha's place_order also has 'squareoff', 'stoploss', 'trailing_stoploss' params
            # which are typically used for BO/CO order varieties.
            # We are not using those directly here for regular/SL/SL-M orders.
            # Target orders (LIMIT sell for a long position) would be separate LIMIT orders.

            log_remarks = f"Placing live {action} order. Prod: {current_product}, Type: {current_order_type}."
            if limit_price: log_remarks += f" LimitPx: {limit_price}."
            if order_params.get("trigger_price"): log_remarks += f" TriggerPx: {order_params['trigger_price']}."
            if target_price: log_remarks += f" Target (for monitoring): {target_price}." # Logged for info, not placed as part of this order

            print(f"{self.name}: {log_remarks} For {quantity} {symbol}.")

            try:
                order_id = self.broker_api.place_order(**order_params)
                if order_id:
                    final_remarks = f"Order ID: {order_id}."
                    if target_price: final_remarks += f" Target (for monitoring): {target_price}."
                    if stop_loss_price and not order_params["order_type"] in ["SL", "SL-M"]:
                        final_remarks += f" SL (for monitoring): {stop_loss_price}."


                    print(f"{self.name}: Live order placement successful. {final_remarks}")
                    if self.logger:
                        self.logger.log_trade(
                            strategy_name=self.name, symbol=symbol, exchange=current_exchange,
                            action=action, quantity=quantity, 
                            price=limit_price or order_params.get("trigger_price", 0), # Log limit or trigger if available
                            order_type=current_order_type, order_id=order_id, status="PLACED_LIVE",
                            remarks=final_remarks
                        )
                    return order_id
                else:
                    msg = f"{self.name}: Live order placement failed. No Order ID received. Symbol: {symbol}"
                    print(msg)
                    if self.logger: self.logger.log_trade(self.name, symbol, current_exchange, action, quantity, limit_price or 0, current_order_type, status="FAILURE_LIVE", remarks="No Order ID")
                    return None
            except Exception as e:
                msg = f"{self.name}: Exception during live order placement for {symbol}: {e}"
                print(msg)
                if self.logger: self.logger.log_trade(self.name, symbol, current_exchange, action, quantity, limit_price or 0, current_order_type, status="EXCEPTION_LIVE", remarks=str(e))
                return None

# Example of how parameters might be defined in config.py and passed
# EXAMPLE_STRATEGY_PARAMS = {
#     "short_window": 10,
#     "long_window": 30,
#     # "default_sl_percent": 1.5, # Example: 1.5% stop loss
#     # "default_tp_percent": 3.0  # Example: 3% target profit
# }
