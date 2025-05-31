# Portfolio and P&L Tracking Architecture

This document outlines the architecture for the `Portfolio Manager` module, detailing its responsibilities in tracking positions, cash, portfolio value, and calculating Profit & Loss (P&L).

## 1. `Portfolio Manager` Responsibilities

The `Portfolio Manager` is the central module for maintaining the current state and historical performance of the trading portfolio.

*   **Core Functions:**
    *   **Position Tracking:** Maintains a real-time record of all open positions, including instrument, quantity, average entry price, and other relevant metrics.
    *   **Cash Management:** Tracks the current cash balance, updated by trades, commissions, fees, deposits, and withdrawals.
    *   **Portfolio Value Calculation:** Continuously calculates the total value of the portfolio (sum of cash and market value of all open positions).
    *   **P&L Calculation:** Calculates both realized P&L (from closed trades) and unrealized P&L (mark-to-market for open positions).
    *   **Historical Performance Tracking:** Stores or provides data for historical performance metrics (e.g., daily P&L, equity curve).

*   **Receiving Updates:**
    *   The primary source of updates is the `Execution Engine` (or `BacktestExecutionEngine`). After a trade is executed (simulated or real), the `Execution Engine` sends a `FillEvent` or `TradeRecord` to the `Portfolio Manager`.
        *   **Interface:** `PortfolioManager.update_trade(trade_record)`
    *   It also receives market data updates from the `Data Handler` to mark open positions to market.
        *   **Interface:** `PortfolioManager.on_market_data(market_data_event)`

## 2. Position Management

Accurate position management is critical for knowing current exposure and calculating P&L.

*   **Data Structure for a `Position`:**
    ```
    Position {
        instrument_id: string (e.g., "EUR/USD", "AAPL")
        quantity: float (positive for long, negative for short)
        average_entry_price: float
        current_market_price: float
        market_value: float (quantity * current_market_price for equities/futures, or contract_size * quantity * current_market_price for FX)
        unrealized_pnl: float
        realized_pnl_on_close: float (temporary, for the P&L of the part being closed)
        last_update_timestamp: datetime
        strategy_id_opener: string (ID of the strategy that initiated the position)
        trade_ids: list[string] (IDs of trades that built this position)
        target_price: float (optional, from strategy or execution)
        stop_loss_price: float (optional, from strategy or execution)
        # Other relevant fields like initial margin, maintenance margin (for futures/options)
    }
    ```

*   **Creating, Updating, and Closing Positions:**
    *   **Creation:** When a `TradeRecord` for a new instrument (or a new strategy if tracking per strategy per instrument) is received, a new `Position` object is created.
    *   **Updating (Increasing Position):** If a `TradeRecord` adds to an existing position (e.g., buying more of an already long instrument, pyramiding), the `quantity` and `average_entry_price` are updated.
        *   `new_total_quantity = old_quantity + trade_quantity`
        *   `new_avg_price = ((old_avg_price * old_quantity) + (trade_price * trade_quantity)) / new_total_quantity`
    *   **Updating (Decreasing/Closing Position):** If a `TradeRecord` reduces an existing position:
        *   Realized P&L is calculated for the closed portion: `realized_pnl = (trade_price - average_entry_price) * closed_quantity` (adjust for shorts).
        *   The `quantity` of the position is reduced.
        *   If `quantity` becomes zero, the position is considered closed and can be moved to a list of closed positions.
        *   If partially closed, `average_entry_price` usually remains the same.

*   **Handling Multiple Positions in the Same Instrument:**
    *   **Default:** The system will typically maintain one consolidated position per instrument (e.g., if long 100 EUR/USD and a new BUY signal for 50 EUR/USD comes, the position becomes long 150 EUR/USD). The `average_entry_price` reflects the weighted average.
    *   **Strategy-Specific Positions (Optional Advanced):** For advanced tracking or if strategies must not co-mingle positions, the `Position` key could be a tuple of `(instrument_id, strategy_id)`. This means `StrategyA` holding AAPL and `StrategyB` holding AAPL would be two separate `Position` objects. This significantly increases complexity in margin and overall risk calculation. The initial design will assume a consolidated position per instrument.
    *   Pyramiding (as discussed in Execution Management) is a form of updating an existing consolidated position.

## 3. Cash Management

*   **Tracking Available Cash:**
    *   A simple float variable `cash_balance` within the `Portfolio Manager`.
    *   Initialized with a starting capital amount at the beginning of a trading session or backtest.

*   **How Cash is Updated:**
    *   **Buys:** `cash_balance -= trade_quantity * trade_price`
    *   **Sells:** `cash_balance += trade_quantity * trade_price` (for actual sales, not short selling initiation which might involve margin)
    *   **Commissions:** `cash_balance -= commission_amount`
    *   **Fees:** `cash_balance -= fee_amount` (e.g., exchange fees, financing costs for overnight positions)
    *   **Deposits/Withdrawals:** (Manual operations for live trading) `cash_balance += deposit_amount` or `cash_balance -= withdrawal_amount`.

## 4. P&L Calculation

*   **Realized P&L:**
    *   Calculated when a position (or part of it) is closed.
    *   Formula for a long position: `(exit_price - average_entry_price) * quantity_closed - commissions_for_that_portion`
    *   Formula for a short position: `(average_entry_price - exit_price) * quantity_closed - commissions_for_that_portion`
    *   Accumulated daily, weekly, monthly, etc., for reporting.

*   **Unrealized P&L (Mark-to-Market):**
    *   Calculated for all open positions based on the latest available market prices.
    *   Formula for a long position: `(current_market_price - average_entry_price) * quantity_open`
    *   Formula for a short position: `(average_entry_price - current_market_price) * quantity_open`
    *   **Frequency of Update:** This should be updated whenever new `MarketDataEvent` is received by the `Portfolio Manager` from the `Data Handler`. For active trading systems, this means on every tick or bar update for relevant instruments. This ensures the portfolio value and unrealized P&L are always current.

*   **Overall Portfolio P&L:**
    *   `Total P&L = Sum of all Realized P&L + Sum of all Unrealized P&L for open positions.`
    *   **Portfolio Equity/Value:** `Starting Capital + Total P&L` or more simply `Current Cash + Sum of Market Value of all Open Positions`.

## 5. Logging Requirements (Portfolio Specific)

Addressing user's request for logging "P&L, capital and other imp details".

*   **Responsibility:** While the `Portfolio Manager` calculates these values, the `Trade Logger` (or a specialized `PortfolioLogger`) would be responsible for persisting them. The `Portfolio Manager` would emit events or provide data to the logger.
*   **Information to Log:**
    *   **Trade Confirmations:** Details of each fill (instrument, quantity, price, direction, commissions, resulting position).
    *   **Position Updates:** Significant changes to positions (e.g., opening, closing, substantial increase/decrease).
    *   **Daily P&L Snapshot:** At the end of each trading day (simulated or real):
        *   Total Realized P&L for the day.
        *   Total Unrealized P&L at day-end.
        *   Total Portfolio Value/Equity.
        *   Cash Balance.
    *   **Periodic Portfolio Snapshot:** (e.g., hourly, or on significant changes)
        *   Full list of open positions with their mark-to-market values and unrealized P&L.
        *   Current cash.
        *   Total portfolio value.
    *   **Significant Drawdown Events:** Log when portfolio value drops by a certain percentage from its peak (High Water Mark).
    *   **Cash Transactions:** Deposits, withdrawals, interest, fees.

## 6. Data Structures

*   **`PortfolioSnapshot`:** Represents the state of the portfolio at a specific point in time.
    ```
    PortfolioSnapshot {
        timestamp: datetime
        cash: float
        total_portfolio_value: float (equity)
        total_realized_pnl: float (cumulative)
        total_unrealized_pnl: float
        positions: list[Position] // List of current open positions
        high_water_mark: float // Peak portfolio value achieved
    }
    ```
*   **`Position`:** As defined in section 2.
*   **`TradeRecord` (Portfolio's view):** This is essentially the `FillEvent` received from the `Execution Engine`.
    ```
    TradeRecord { // or FillEvent
        trade_id: string
        order_id: string
        strategy_id: string
        instrument_id: string
        timestamp: datetime
        action: string // BUY, SELL
        quantity: float
        fill_price: float
        commission: float
        fees: float
        # Other relevant details like venue, slippage
    }
    ```

## 7. Interface with other Modules

*   **`Execution Engine`:**
    *   **Input:** Receives `TradeRecord` / `FillEvent` from the `Execution Engine`.
    *   **Interface:** `PortfolioManager.update_trade(trade_record)`

*   **`Data Handler`:**
    *   **Input:** Receives `MarketDataEvent` (tick or bar data) from the `Data Handler`.
    *   **Interface:** `PortfolioManager.on_market_data(market_data_event)` (This triggers mark-to-market updates for all relevant open positions).

*   **`Reporting Engine`:**
    *   **Output:** Provides data (e.g., `PortfolioSnapshot`, historical P&L, position details) to the `Reporting Engine`.
    *   **Interface:**
        *   `PortfolioManager.get_current_snapshot()`
        *   `PortfolioManager.get_historical_pnl(start_date, end_date)`
        *   `PortfolioManager.get_all_positions()`
        *   `PortfolioManager.get_trade_history_for_instrument(instrument_id)` (though `TradeLogger` might be better for full history)

*   **`Risk Manager`:**
    *   **Output:** Provides current portfolio state (positions, cash, value) to the `Risk Manager` for assessment.
    *   **Interface:** `PortfolioManager.get_current_portfolio_state()` (could return a `PortfolioSnapshot` or a simplified version for risk assessment).
    *   **Input (Potentially):** May receive instructions from `Risk Manager` (e.g., "liquidate_position_X" if a severe risk limit is breached, though this is more likely to go via the `Execution Engine`).

This architecture ensures that the `Portfolio Manager` acts as a reliable source of truth for all portfolio-related information, essential for performance tracking, risk management, and reporting.
