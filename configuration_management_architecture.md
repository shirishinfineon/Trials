# Configuration Management Architecture

This document describes the architecture for the `Configuration Manager` module, including its responsibilities, configuration structure, integration with Excel for strategy parameters, loading mechanisms, and how other modules access configuration data.

## 1. `Configuration Manager` Responsibilities

The `Configuration Manager` is responsible for loading, storing, and providing access to all configuration parameters required by the trading system.

*   **Role:**
    *   Acts as a central repository for all system settings.
    *   Decouples configuration data from the application logic, allowing changes to settings without code modification.
    *   Provides a consistent interface for other modules to fetch configuration values.

*   **Support for Different Configuration Sources:**
    *   **Primary Source:** Configuration files (e.g., YAML, JSON). This is the recommended approach for runtime.
    *   **Secondary/User-Facing Source (e.g., Excel):** Users can manage certain parameters (especially for strategies) in Excel. These will be converted into the primary configuration file format for system use.
    *   Environment variables (for sensitive data like API keys or overriding specific settings).

## 2. Configuration Structure and Formats

*   **Recommended Primary Configuration File Format:**
    *   **YAML (.yaml or .yml):** Recommended for its human-readability and ability to represent complex hierarchical data structures. JSON is also a viable alternative.
    *   Multiple YAML files can be used for better organization (e.g., `main_config.yaml`, `strategies.yaml`, `risk_config.yaml`, `broker_config.yaml`). The `Configuration Manager` would be responsible for loading and merging these.

*   **Structure of Configuration Files:**
    *   Files will be organized into logical sections.

    ```yaml
    # Example: main_config.yaml

    system:
      logging_level: INFO
      data_directory: /data/market_data/
      # ... other system-wide settings

    backtest:
      start_date: 2023-01-01
      end_date: 2023-12-31
      initial_capital: 100000
      commission_per_trade: 5.0
      slippage_percentage: 0.001

    broker_interface: # For live trading
      name: "PaperTrader" # or "InteractiveBrokers", "Binance"
      api_key: ${BROKER_API_KEY} # Example of using env variable substitution
      api_secret: ${BROKER_API_SECRET}
      # ... other broker-specific settings

    active_strategies:
      - strategy_id: MACross_EURUSD_1H
        enabled: true
        # Parameters for this specific instance are here or in a separate strategy config file
        # referenced by strategy_id or by a direct include mechanism.
        # See section 3 for parameter details.

    risk_manager:
      max_portfolio_drawdown_pct: 20
      max_position_size_pct_of_equity: 5
      # ... other risk settings
    ```

    ```yaml
    # Example: strategies_parameters.yaml (can be generated from Excel)

    strategies:
      MACross_EURUSD_1H:
        module: "strategies.moving_average_cross"
        class: "MovingAverageCrossStrategy"
        parameters:
          instrument: "EUR/USD"
          timeframe: "1H"
          short_window: 20
          long_window: 50
          stop_loss_pct: 1.5
          take_profit_pct: 3.0

      RSIOversold_BTCUSD_4H:
        module: "strategies.rsi_oversold"
        class: "RSIOversoldStrategy"
        parameters:
          instrument: "BTC/USD"
          timeframe: "4H"
          rsi_period: 14
          oversold_threshold: 30
          overbought_threshold: 70
          stop_loss_atr_multiplier: 2.0
          take_profit_atr_multiplier: 4.0
    ```

## 3. Excel Integration for Strategy Parameters and Customizations

To allow users to manage strategy parameters in Excel, while ensuring system stability by not reading Excel files directly at runtime:

*   **Workflow:**
    1.  **User Edits Excel:** The user maintains an Excel spreadsheet where each row (or a set of rows/columns) might represent a strategy configuration or a parameter set.
    2.  **Excel Structure Example:**
        | strategy_id          | enabled | module_path                    | class_name                 | instrument | timeframe | param_name_1   | param_value_1 | param_name_2   | param_value_2 | ... |
        |----------------------|---------|--------------------------------|----------------------------|------------|-----------|----------------|---------------|----------------|---------------|-----|
        | MACross_EURUSD_1H    | TRUE    | strategies.moving_average_cross| MovingAverageCrossStrategy | EUR/USD    | 1H        | short_window   | 20            | long_window    | 50            | ... |
        | RSIOversold_BTCUSD_4H| TRUE    | strategies.rsi_oversold        | RSIOversoldStrategy        | BTC/USD    | 4H        | rsi_period     | 14            | oversold_threshold | 30            | ... |
        | MyCustomStrategy_XYZ | FALSE   | strategies.custom              | MyStrategy                 | XYZ/USD    | 1D        | my_param       | "value"       | another_param  | 123.45        | ... |

    3.  **Conversion Process (Offline/Pre-Runtime):**
        *   A dedicated **helper script** (e.g., Python script using libraries like `pandas` and `PyYAML` or `openpyxl`) is provided.
        *   The user runs this script, pointing it to their Excel file.
        *   The script reads the Excel sheet, validates the data (e.g., checks for required columns, data types), and converts it into the system's primary configuration format (e.g., `strategies_parameters.yaml` as shown above).
        *   This generated YAML file is then used by the `Configuration Manager`.
    4.  **No Direct Runtime Excel Reading:** The core trading system **does not** have a direct dependency on Excel libraries and does not read `.xlsx` files during its main operational loop (backtesting or live trading). This enhances stability, simplifies dependencies, and makes configuration management more robust and version-controllable.

*   **Mapping Excel to YAML:**
    *   The helper script will map columns from the Excel sheet to the structured YAML format.
    *   For instance, `strategy_id` becomes the key for a strategy's configuration block.
    *   `module_path` and `class_name` define how to load the strategy.
    *   Columns like `param_name_1`, `param_value_1`, `param_name_2`, `param_value_2` can be pivoted into a nested `parameters` dictionary within the YAML. More sophisticated mapping can be designed if parameters are fixed per strategy type.

## 4. Loading Configuration

*   **Startup Loading:**
    *   When the main application (Orchestrator) starts, it instantiates the `Configuration Manager`.
    *   The `Configuration Manager` reads the main configuration file(s) (e.g., `main_config.yaml`, and the generated `strategies_parameters.yaml`).
    *   It parses these files and stores the settings internally, often in a nested dictionary-like structure.
    *   It should handle environment variable substitution for sensitive data (e.g., `${BROKER_API_KEY}` being replaced by the actual key).

*   **Reloading Configuration:**
    *   **Limited Support:** Reloading configuration dynamically while the system is running live trading is complex and potentially risky.
        *   Changes to some parameters (e.g., logging level) might be safe to reload.
        *   Changes to strategy parameters or broker connections might require restarting specific modules or even the entire application to take effect correctly and avoid inconsistent states.
    *   **Backtesting:** For backtesting, configuration is typically fixed for the duration of a single backtest run.
    *   **Implementation:** If dynamic reloading is implemented for specific safe parameters, it would involve the `Configuration Manager` re-reading files and potentially notifying relevant modules of changes (Observer pattern). This is an advanced feature.

## 5. Accessing Configuration Data

*   **Interface for Accessing Settings:**
    *   The `Configuration Manager` provides getter methods for other modules.
    *   **General Settings:** `config_manager.get_setting(key_path: str, default_value=None)`
        *   `key_path` could be a dot-separated path, e.g., `"system.logging_level"` or `"broker_interface.name"`.
    *   **Strategy Parameters:** `config_manager.get_strategy_params(strategy_id: str) -> dict`
        *   Returns the dictionary of parameters for the specified `strategy_id`.
    *   **Active Strategies List:** `config_manager.get_active_strategies_config() -> list[dict]`
        *   Returns a list of configurations for all strategies marked as `enabled: true`.

*   **How Modules Use It:**
    *   During initialization, modules request their necessary configuration from the `Configuration Manager`.
    *   Example (`Strategy Engine`):
        ```python
        # Pseudocode
        # class StrategyEngine:
        #   def __init__(self, config_manager):
        #     self.config_manager = config_manager
        #     self.active_strategy_configs = self.config_manager.get_active_strategies_config()
        #     self.load_strategies()
        #
        #   def load_strategies(self):
        #     for strat_config in self.active_strategy_configs:
        #       if strat_config.get('enabled', False):
        #         strategy_id = strat_config['strategy_id']
        #         params = self.config_manager.get_strategy_params(strategy_id).get('parameters', {})
        #         # ... load and instantiate strategy class with params ...
        ```

## 6. Types of Configurations to Manage

The `Configuration Manager` will handle various types of settings:

*   **System-Wide Settings:**
    *   `logging_level` (DEBUG, INFO, WARNING, ERROR)
    *   `data_directory` (for historical data, logs)
    *   `timezone`
*   **Broker Connection Details (Live Trading):**
    *   `api_key`, `api_secret`, `account_id` (ideally sourced from environment variables or secure vault and substituted into config)
    *   `broker_url` (e.g., REST API endpoint, WebSocket URL)
    *   `paper_trading_mode` (true/false)
*   **Backtesting Parameters:**
    *   `start_date`, `end_date`
    *   `initial_capital`
    *   `commission_model` (e.g., fixed per trade, percentage)
    *   `slippage_model`
*   **Strategy Configurations:**
    *   List of active/enabled strategies.
    *   For each strategy:
        *   `strategy_id` (unique identifier)
        *   `module` and `class` name for loading.
        *   Specific parameters: e.g., `instrument`, `timeframe`, `moving_average_periods`, `rsi_thresholds`, `stop_loss_percentage`, `take_profit_target`.
*   **Risk Parameters:**
    *   `max_total_portfolio_drawdown_pct`
    *   `max_daily_drawdown_pct`
    *   `max_risk_per_trade_pct_of_equity`
    *   `max_position_size_pct_of_equity` (per instrument or overall)
    *   List of restricted instruments.

This architecture ensures that configurations are managed systematically, are easy to update (especially for users familiar with Excel for strategy tuning), and are accessible to all parts of the system in a controlled manner.
