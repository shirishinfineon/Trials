# algo_trading_system/data_management/trade_logger.py
import csv
import os
from datetime import datetime

class TradeLogger:
    def __init__(self, trade_log_file='trades.csv', daily_summary_file='daily_summary.csv'):
        self.trade_log_file = trade_log_file
        self.daily_summary_file = daily_summary_file
        self._initialize_trade_log()
        self._initialize_daily_summary()

    def _initialize_trade_log(self):
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(self.trade_log_file), exist_ok=True)
        if not os.path.exists(self.trade_log_file):
            with open(self.trade_log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Timestamp', 'Strategy', 'Symbol', 'Exchange', 
                    'Action', 'Quantity', 'Price', 'OrderType', 
                    'StopLoss', 'Target', 'OrderID', 'Status', 'Remarks'
                ])
        print(f"Trade log initialized: {self.trade_log_file}")

    def _initialize_daily_summary(self):
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(self.daily_summary_file), exist_ok=True)
        if not os.path.exists(self.daily_summary_file):
            with open(self.daily_summary_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Date', 'RealizedPnL', 'UnrealizedPnL', 'TotalPnL', 
                    'CapitalStartOfDay', 'CapitalEndOfDay', 'TradesCount', 'WinningTrades', 'LosingTrades'
                ])
        print(f"Daily summary log initialized: {self.daily_summary_file}")

    def log_trade(self, strategy_name, symbol, exchange, action, quantity, price, 
                  order_type, stop_loss=None, target=None, order_id=None, status='PENDING', remarks=''):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        trade_data = [
            timestamp, strategy_name, symbol, exchange, action, quantity, price,
            order_type, stop_loss, target, order_id, status, remarks
        ]
        try:
            with open(self.trade_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(trade_data)
            print(f"Trade logged: {action} {quantity} {symbol} by {strategy_name}")
            return True
        except Exception as e:
            print(f"Error logging trade: {e}")
            return False

    def update_trade_status(self, order_id, new_status, remarks=''):
        # This is a simplified update. For robust updates, you might read the CSV,
        # update in memory (e.g. using pandas), and rewrite.
        # For now, we'll just log a new entry indicating an update.
        print(f"Updating trade status for OrderID {order_id} to {new_status}. This is a simplified log entry.")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        update_data = [
            timestamp, 'SYSTEM_UPDATE', '-', '-', 'UPDATE_STATUS', 0, 0.0,
            '-', None, None, order_id, new_status, f"Previous status update: {remarks}"
        ]
        try:
            with open(self.trade_log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(update_data)
            print(f"Trade status update logged for OrderID {order_id}.")
            return True
        except Exception as e:
            print(f"Error logging trade status update: {e}")
            return False

    def log_daily_summary(self, realized_pnl, unrealized_pnl, capital_start, capital_end, 
                          trades_count, winning_trades, losing_trades):
        date_today = datetime.now().strftime('%Y-%m-%d')
        total_pnl = realized_pnl + unrealized_pnl
        summary_data = [
            date_today, realized_pnl, unrealized_pnl, total_pnl,
            capital_start, capital_end, trades_count, winning_trades, losing_trades
        ]
        try:
            # Check if an entry for today already exists, if so, update it (optional, simple append for now)
            # More robust would be to read, find if date exists, update row or append.
            with open(self.daily_summary_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(summary_data)
            print(f"Daily summary logged for {date_today}.")
            return True
        except Exception as e:
            print(f"Error logging daily summary: {e}")
            return False

if __name__ == '__main__':
    # Example Usage: Create logs in a 'logs' subdirectory
    # Ensure 'logs' directory exists or is created by the logger
    
    # Define log file paths within a 'logs' directory
    logs_dir = "logs"
    trade_log_path = os.path.join(logs_dir, "test_trades.csv")
    daily_summary_path = os.path.join(logs_dir, "test_daily_summary.csv")

    # The TradeLogger class now handles directory creation for log files
    logger = TradeLogger(trade_log_file=trade_log_path, daily_summary_file=daily_summary_path)

    # Log a sample trade
    logger.log_trade(
        strategy_name='ExampleStrategy1', 
        symbol='INFY', 
        exchange='NSE', 
        action='BUY', 
        quantity=10, 
        price=1500.50,
        order_type='LIMIT',
        stop_loss=1480.00,
        target=1550.00,
        order_id='ORDER123',
        status='EXECUTED',
        remarks='Entry based on crossover'
    )

    logger.log_trade(
        strategy_name='ExampleStrategy2', 
        symbol='RELIANCE', 
        exchange='NSE', 
        action='SELL', 
        quantity=5, 
        price=2600.75,
        order_type='MARKET',
        stop_loss=2650.00,
        target=2500.00,
        order_id='ORDER456',
        status='EXECUTED',
        remarks='Breakdown signal'
    )
    
    logger.update_trade_status(order_id='ORDER123', new_status='TARGET_HIT', remarks='Target price reached')

    # Log daily summary
    logger.log_daily_summary(
        realized_pnl=1250.75, 
        unrealized_pnl= -200.50, 
        capital_start=100000.00, 
        capital_end=101050.25,
        trades_count=5,
        winning_trades=3,
        losing_trades=2
    )
    
    print(f"Sample logs created: {logger.trade_log_file}, {logger.daily_summary_file}")
    
    # To clean up, you might want to remove the 'logs' directory and its contents
    # For example:
    # if os.path.exists(logs_dir):
    #     import shutil
    #     shutil.rmtree(logs_dir)
    #     print(f"Cleaned up {logs_dir} directory.")
