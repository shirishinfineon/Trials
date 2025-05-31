# Execution and Order Management in a Backtesting Environment

This document describes the process of handling trading signals, simulating order creation, trade execution (including slippage and commissions), managing Target/Stop-Loss (T/SL) orders, and squaring off positions within a backtesting context. The `BacktestExecutionEngine` is central to this process, working closely with a `SimulatedBrokerAdapter` and the `Portfolio Manager`.

## 1. Receiving Signals

*   **Source:** `Strategy Engine`
*   **Target:** `BacktestExecutionEngine`
*   **Process:**
    *   The `Strategy Engine` generates `TradingSignal` objects (e.g., BUY_MARKET_EURUSD_100_UNITS, SELL_LIMIT_AAPL_10_SHARES_AT_150).
    *   These signals are passed to the `BacktestExecutionEngine`, typically via a direct method call or an event queue (e.g., `BacktestExecutionEngine.process_signal(signal)`).
    *   The `TradingSignal` object contains:
        *   `strategy_id`: Identifier of the strategy that generated the signal.
        *   `instrument`: The financial instrument to be traded.
        *   `action`: BUY, SELL, (potentially SHORT, COVER for more advanced scenarios).
        *   `order_type`: MARKET, LIMIT.
        *   `quantity`: Amount to trade.
        *   `limit_price` (if LIMIT order).
        *   `signal_id`: Unique ID for the signal.
        *   `target_price` (optional, for T/SL).
        *   `stop_loss_price` (optional, for T/SL).

## 2. Order Creation (Simulation)

*   **Responsibility:** `BacktestExecutionEngine`
*   **Process:**
    *   Upon receiving a `TradingSignal`, the `BacktestExecutionEngine` translates it into an internal `Order` object.
    *   The `Order` object includes:
        *   `order_id`: Unique ID for this order.
        *   `signal_id`: ID of the originating signal.
        *   `instrument`, `action`, `order_type`, `quantity`, `limit_price`.
        *   `status`: PENDING_SUBMISSION, SUBMITTED, (later FILLED, CANCELLED).
        *   `creation_timestamp`: Time the signal was received/order created.
        *   `target_price`, `stop_loss_price` (carried over from the signal or determined by Execution Engine rules).

*   **Order Types in Simulation:**
    *   **Market Orders:** Assumed to be filled at a price derived from the *next available* market data after the order is "placed".
    *   **Limit Orders:** Will only be filled if the market price reaches the `limit_price`. The simulation needs to check against subsequent market data.

*   **Pyramiding/Stacking Positions (User Query):**
    *   "if you have already bought a call option, will the system buy more call option if there is another buy signal from strategy?"
    *   This is a configurable behavior, typically managed by the `BacktestExecutionEngine` in conjunction with rules from the `Risk Manager` or strategy parameters.
    *   **Configuration Options:**
        1.  **Allow Pyramiding:** If a new BUY signal for an existing long position (or SELL for short) is received, a new order is created to increase the position size.
        2.  **Disallow Pyramiding:** Ignore new signals in the same direction for an instrument if a position is already open.
        3.  **Max Position Size:** Allow pyramiding up to a certain maximum position size (checked against `Portfolio Manager` and `Risk Manager`).
    *   This setting can be global or strategy-specific. The `BacktestExecutionEngine` will query the `Portfolio Manager` for current positions before deciding to create a new order that adds to an existing position.

## 3. Trade Simulation

*   **Responsibility:** `BacktestExecutionEngine` using the `SimulatedBrokerAdapter`.
*   **Process:**
    *   The `BacktestExecutionEngine` holds the newly created `Order` objects.
    *   As new market data (`MarketDataEvent`) arrives from the `Data Handler` (via the main backtesting loop), the `BacktestExecutionEngine` iterates through its pending orders.
    *   **Market Order Fill:**
        *   Typically filled at the **open price of the next bar** after the order was created.
        *   Alternative: Fill at the current bar's close or a volume-weighted average price (VWAP) if data is granular enough (more complex).
    *   **Limit Order Fill:**
        *   For a BUY LIMIT order, if the next bar's low <= `limit_price`, the order is filled. Fill price is typically `min(next_bar.open, limit_price)`.
        *   For a SELL LIMIT order, if the next bar's high >= `limit_price`, the order is filled. Fill price is typically `max(next_bar.open, limit_price)`.
        *   Unfilled limit orders persist until filled or cancelled (e.g., by strategy logic or end-of-day rule).

*   **Slippage Simulation (Conceptual):**
    *   **Basic:** A fixed percentage or a random variable around the fill price.
        *   E.g., `simulated_fill_price = ideal_fill_price * (1 + slippage_factor)`.
    *   **Advanced:** Based on order size and historical volatility/liquidity (more complex, for later).
    *   Slippage is applied by the `SimulatedBrokerAdapter` when confirming a fill.

*   **Commission Simulation (Conceptual):**
    *   **Basic:** A fixed amount per trade/share or a percentage of trade value.
    *   Applied by the `SimulatedBrokerAdapter` and deducted from cash in the `Portfolio Manager`.
    *   Configuration: `commission_per_share`, `min_commission_per_trade`, `commission_percentage`.

## 4. Target and Stop-Loss (T/SL) Management

*   **Determination of T/SL Levels:**
    *   **From Strategy Parameters:** The `TradingSignal` may include `target_price` and `stop_loss_price` defined by the strategy logic (e.g., fixed pips/percentage, ATR-based, support/resistance levels).
    *   **Execution Engine Default:** If not provided by the strategy, the `BacktestExecutionEngine` might apply a default T/SL based on configuration (e.g., a 2% stop-loss for all trades).
    *   These T/SL levels are stored with the `Order` and subsequently with the `Position` object in the `Portfolio Manager`.

*   **Monitoring T/SL Levels:**
    *   The `BacktestExecutionEngine` (or a dedicated T/SL monitoring component within it) tracks open positions (obtained from `Portfolio Manager`).
    *   For each open position with T/SL levels, it checks incoming `MarketDataEvent`:
        *   **Stop-Loss:** If long, and `market_data.low <= stop_loss_price`, the SL is triggered. If short, and `market_data.high >= stop_loss_price`, SL is triggered.
        *   **Target Profit:** If long, and `market_data.high >= target_price`, TP is triggered. If short, and `market_data.low <= target_price`, TP is triggered.
    *   Priority: Typically, the stop-loss price is checked first within a bar. If both SL and TP are hit in the same bar, the outcome might depend on simulation rules (e.g., worst-case fill for SL).

*   **Simulation of T/SL Order Execution:**
    *   When a T/SL level is hit, a market order is simulated to close the position.
    *   Fill price is typically the T/SL price itself, or the next bar's open if a more conservative fill is desired (simulating delay). Slippage can also be applied.
    *   The `BacktestExecutionEngine` generates a `FillEvent` for this closure.

## 5. Position Squaring Logic

*   **Responsibility:** `BacktestExecutionEngine`, potentially triggered by `Strategy Engine` or configuration.
*   **Triggers for Squaring Off:**
    1.  **Reversal Signal:** A BUY signal is received for an instrument where a SHORT position is currently held (or vice-versa).
        *   **Configurable Behavior:**
            *   Square existing position then open new: Two trades - one to close, one to open.
            *   Net out: Adjust existing position directly (e.g., if short 100, and BUY 150 signal, result is long 50).
    2.  **Explicit Strategy Request:** A strategy might generate a specific "CLOSE_POSITION" signal for an instrument.
    3.  **End-of-Day (EOD):** A configurable rule in the `BacktestExecutionEngine` to close all open positions at the end of the simulated trading day.
    4.  **Target/Stop-Loss Hit:** As described above.
    5.  **Margin Call Simulation:** (Advanced) If portfolio margin drops below a threshold, positions are liquidated by the `Risk Manager` via the `BacktestExecutionEngine`.

*   **Process:**
    *   When a squaring condition is met, the `BacktestExecutionEngine` creates a market order to close the relevant portion or the entirety of the existing position.
    *   This order is then processed like any other simulated market order.

## 6. Interaction with `Portfolio Manager`

*   **Process:**
    1.  When the `SimulatedBrokerAdapter` confirms a fill (either for opening a new position, closing an existing one, or a T/SL execution), it generates a `FillEvent` or `TradeRecord`.
    2.  This `FillEvent` contains: `order_id`, `instrument`, `fill_price`, `fill_quantity`, `direction` (BUY/SELL), `timestamp`, `commission_paid`, `slippage_amount`.
    3.  The `BacktestExecutionEngine` receives this `FillEvent`.
    4.  The `BacktestExecutionEngine` then calls an update method on the `Portfolio Manager`.
        *   **Interface Name (Conceptual):** `PortfolioManager.update_trade(fill_event)`
    5.  The `Portfolio Manager` uses this information to:
        *   Create new positions or update existing ones.
        *   Adjust cash balance (debiting for buys/commissions, crediting for sells).
        *   Calculate realized P&L for closed trades.
        *   Update overall portfolio value.

## 7. Broker Interface for Backtesting (`SimulatedBrokerAdapter`)

*   **Role:**
    *   Acts as a stand-in for a real broker's API during backtesting.
    *   It takes `Order` objects from the `BacktestExecutionEngine`.
    *   It does *not* interact with any external market.
    *   Based on the incoming market data (passed to it or to the `BacktestExecutionEngine`), it decides if and how an order would have been filled.
*   **Responsibilities:**
    *   **Order Matching Logic:** Implements the rules for when market and limit orders are considered filled (e.g., next bar's open, price crossing limit).
    *   **Fill Price Calculation:** Determines the execution price.
    *   **Slippage Simulation:** Applies configured slippage models.
    *   **Commission Calculation:** Applies configured commission models.
    *   **Generating Execution Reports:** Creates `FillEvent` or `ExecutionReport` objects and sends them back to the `BacktestExecutionEngine`.
    *   **Maintaining an Order Book (Simplified):** For limit orders, it needs to keep track of active limit orders to match against incoming market prices.
*   **Interface (Conceptual, called by `BacktestExecutionEngine`):**
    *   `SimulatedBrokerAdapter.place_order(order)`
    *   `SimulatedBrokerAdapter.process_market_data(market_data_event)` (This method would trigger checks for limit order fills and T/SL).
*   **Output:** `FillEvent` back to the `BacktestExecutionEngine`.

This detailed process ensures that the backtesting environment can realistically simulate trading operations, providing valuable feedback on strategy performance.
