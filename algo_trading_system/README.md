# Algo Trading System

This project is an algorithmic trading system designed for Indian stock brokers like Zerodha and Upstox.

## Features (Planned)

*   Broker integration (Zerodha, Upstox)
*   Authentication and login
*   Current positions tracking
*   Trade logging (local storage, Excel-compatible format)
*   Daily P&L and capital tracking
*   Multiple strategy support
*   Backtesting capabilities
*   Target and stop-loss parameters

## Setup (Initial)

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd algo_trading_system
    ```

2.  **Create a Python virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies (initially none, will be updated):**
    ```bash
    # pip install -r requirements.txt 
    # (requirements.txt will be added later)
    ```

4.  **Configure the system:**
    *   Copy `config.py.example` to `config.py` (if `config.py.example` is provided later).
    *   **Important:** Edit `algo_trading_system/config.py` to add your API keys and other necessary configurations.
        **DO NOT commit your `config.py` file with sensitive credentials.** It is already included in `.gitignore`.

5.  **Run the application (placeholder):**
    ```bash
    python main.py
    ```

## Disclaimer

Trading in financial markets involves significant risk. This software is for educational and experimental purposes only and should not be used for live trading without thorough testing and understanding the risks involved. The developers are not responsible for any financial losses.
