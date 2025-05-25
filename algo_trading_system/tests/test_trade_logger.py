# algo_trading_system/tests/test_trade_logger.py
import unittest
import os
import csv
from datetime import datetime
# Adjust import path based on how you run tests (e.g., from root or tests folder)
# This assumes running tests from the root directory of the project.
from data_management.trade_logger import TradeLogger # If running from root
# If running directly from tests/ folder, and data_management is sibling to tests' parent:
# import sys
# sys.path.append(os.path.join(os.path.dirname(__file__), '..')) # Add project root to sys.path
# from data_management.trade_logger import TradeLogger


class TestTradeLogger(unittest.TestCase):
    def setUp(self):
        self.test_trade_log_file = "test_trades_temp.csv"
        self.test_daily_summary_file = "test_daily_summary_temp.csv"
        # Ensure no old test files are present
        if os.path.exists(self.test_trade_log_file):
            os.remove(self.test_trade_log_file)
        if os.path.exists(self.test_daily_summary_file):
            os.remove(self.test_daily_summary_file)
            
        self.logger = TradeLogger(trade_log_file=self.test_trade_log_file, 
                                  daily_summary_file=self.test_daily_summary_file)

    def tearDown(self):
        # Clean up created files after tests
        if os.path.exists(self.test_trade_log_file):
            os.remove(self.test_trade_log_file)
        if os.path.exists(self.test_daily_summary_file):
            os.remove(self.test_daily_summary_file)

    def test_01_initialize_trade_log(self):
        self.assertTrue(os.path.exists(self.test_trade_log_file))
        with open(self.test_trade_log_file, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(header, [
                'Timestamp', 'Strategy', 'Symbol', 'Exchange', 
                'Action', 'Quantity', 'Price', 'OrderType', 
                'StopLoss', 'Target', 'OrderID', 'Status', 'Remarks'
            ])

    def test_02_initialize_daily_summary(self):
        self.assertTrue(os.path.exists(self.test_daily_summary_file))
        with open(self.test_daily_summary_file, 'r') as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(header, [
                'Date', 'RealizedPnL', 'UnrealizedPnL', 'TotalPnL', 
                'CapitalStartOfDay', 'CapitalEndOfDay', 'TradesCount', 'WinningTrades', 'LosingTrades'
            ])

    def test_03_log_trade(self):
        self.logger.log_trade(
            strategy_name='TestStrategy', symbol='TEST', exchange='NSE', action='BUY',
            quantity=10, price=100.0, order_type='LIMIT', order_id='ORDER001', status='EXECUTED'
        )
        with open(self.test_trade_log_file, 'r') as f:
            reader = csv.reader(f)
            next(reader) # Skip header
            log_entry = next(reader)
            self.assertEqual(log_entry[1], 'TestStrategy')
            self.assertEqual(log_entry[2], 'TEST')
            self.assertEqual(log_entry[4], 'BUY')
            self.assertEqual(log_entry[10], 'ORDER001')

    def test_04_log_daily_summary(self):
        self.logger.log_daily_summary(
            realized_pnl=100.0, unrealized_pnl=50.0, capital_start=10000, capital_end=10150,
            trades_count=2, winning_trades=1, losing_trades=1
        )
        with open(self.test_daily_summary_file, 'r') as f:
            reader = csv.reader(f)
            next(reader) # Skip header
            log_entry = next(reader)
            self.assertEqual(log_entry[1], '100.0') # PnL
            self.assertEqual(log_entry[4], '10000') # Capital Start

    def test_05_update_trade_status(self):
        self.logger.log_trade( # First log a trade
            strategy_name='TestStrategyUpd', symbol='TESTUPD', exchange='NSE', action='BUY',
            quantity=5, price=200.0, order_type='MARKET', order_id='ORDER002', status='PLACED'
        )
        self.logger.update_trade_status(order_id='ORDER002', new_status='EXECUTED', remarks='Filled')
        
        with open(self.test_trade_log_file, 'r') as f:
            lines = list(csv.reader(f))
        
        # Last entry should be the update
        last_entry = lines[-1]
        self.assertEqual(last_entry[1], 'SYSTEM_UPDATE') # strategy_name for updates
        self.assertEqual(last_entry[10], 'ORDER002') # order_id
        self.assertEqual(last_entry[11], 'EXECUTED') # new_status
        self.assertIn('Filled', last_entry[12]) # remarks

if __name__ == '__main__':
    unittest.main()
