#!/usr/bin/env python3
# -*- coding: utf-8 -*-
####################################################################
# Cyclic grid strategy based on martingale
# See README.md for detail
####################################################################
__author__ = "Jerry Fedorenko"
__copyright__ = "Copyright © 2021 Jerry Fedorenko aka VM"
__license__ = "MIT"
__version__ = "1.2.7"
__maintainer__ = "Jerry Fedorenko"
__contact__ = "https://github.com/DogsTailFarmer"
"""
##################################################################
Disclaimer

All risks and possible losses associated with use of this strategy lie with you.
Strongly recommended that you test the strategy in the demo mode before using real bidding.
##################################################################
For standalone use set SYMBOL parameter at the TOP of this file

Check and set parameter at the TOP part of script

Verify init message in Strategy output window for no error
"""
################################################################
import toml
# noinspection PyUnresolvedReferences
import sys
import martin_binance.executor as ex
from martin_binance.executor import *  # lgtm [py/polluting-import]
################################################################
# Exchange setup and parameter settings
################################################################
# Set trading pair for STANDALONE mode, for margin mode takes from terminal
ex.SYMBOL = 'AAABBB'
# Exchange setup, see list of exchange in ms_cfg.toml
ex.ID_EXCHANGE = 10  # See ms_cfg.toml Use for collection of statistics *and get client connection*
ex.FEE_IN_PAIR = True  # Fee pays in pair
ex.FEE_MAKER = Decimal('0.1')  # standard exchange Fee for maker
ex.FEE_TAKER = Decimal('0.17')  # standard exchange Fee for taker
ex.FEE_SECOND = False  # On KRAKEN fee always in second coin
ex.FEE_BNB_IN_PAIR = False  # Binance fee in BNB and BNB is base asset
ex.FEE_FTX = False  # https://help.ftx.com/hc/en-us/articles/360024479432-Fees
ex.GRID_MAX_COUNT = 5  # Maximum counts for placed grid orders
ex.EXTRA_CHECK_ORDER_STATE = False  # Additional check for filled order(s), for (OKEX, )
# Trade parameter
ex.START_ON_BUY = False  # First cycle direction
ex.AMOUNT_FIRST = Decimal('50.0')  # Deposit for Sale cycle in first currency
ex.USE_ALL_FIRST_FUND = False  # Use all available fund for first current
ex.AMOUNT_SECOND = Decimal('1000000.0')  # Deposit for Buy cycle in second currency
ex.PRICE_SHIFT = 0.05  # 'No market' shift price in % from current bid/ask price
# Round pattern, set pattern 1.0123456789 or if not set used exchange settings
ex.ROUND_BASE = str()
ex.ROUND_QUOTE = str()
ex.PROFIT = Decimal('0.15')  # 0.15 - 0.85
ex.PROFIT_MAX = Decimal('0.85')  # If set it is maximum adapted cycle profit
ex.PROFIT_REVERSE = Decimal('0.5')  # 0.0 - 0.75, In Reverse cycle revenue portion of profit
ex.OVER_PRICE = Decimal('0.9')  # Overlap price in one direction
ex.ORDER_Q = 8  # Target grid orders quantity in moment
ex.MARTIN = Decimal('10')  # 5-20, % increments volume of orders in the grid
ex.SHIFT_GRID_DELAY = 15  # sec delay for shift grid action
# Other
ex.STATUS_DELAY = 5  # Minute between sending Tlg message about current status, 0 - disable
ex.GRID_ONLY = False  # Only place grid orders for buy/sell asset
ex.LOG_LEVEL_NO_PRINT = []  # LogLevel.DEBUG Print for level over this list member
# Parameter for calculate grid over price and grid orders quantity in set_trade_condition()
# If ADAPTIVE_TRADE_CONDITION = True, ORDER_Q / OVER_PRICE determines the density of grid orders
ex.ADAPTIVE_TRADE_CONDITION = True
ex.BB_CANDLE_SIZE_IN_MINUTES = 60
ex.BB_NUMBER_OF_CANDLES = 20
ex.KBB = 2.0  # k for Bollinger Band
ex.PROFIT_K = 2 * 0.75 / ex.KBB  # k for place profit in relation to BB value
# Parameter for calculate price of grid orders by logarithmic scale
# If -1 function is disabled, can take a value from 0 to infinity (in practice no more 1000)
# When 0 - logarithmic scale, increase parameter the result is approaching linear
ex.LINEAR_GRID_K = 100  # See 'Model of logarithmic grid.ods' for detail
# Average Directional Index with +DI and -DI for Reverse conditions analise
ex.ADX_CANDLE_SIZE_IN_MINUTES = 1
ex.ADX_NUMBER_OF_CANDLES = 60
ex.ADX_PERIOD = 14
ex.ADX_THRESHOLD = 40  # ADX value that indicates a strong trend
ex.ADX_PRICE_THRESHOLD = 0.05  # % Max price drift before release Hold reverse cycle
# Start first as Reverse cycle, also set appropriate AMOUNT
ex.REVERSE = False
ex.REVERSE_TARGET_AMOUNT = Decimal('0')
ex.REVERSE_INIT_AMOUNT = Decimal('0')
ex.REVERSE_STOP = False  # Stop after ending reverse cycle
################################################################
#                 DO NOT EDIT UNDER THIS LINE                ###
################################################################
config = None
if ex.CONFIG_FILE.exists():
    config = toml.load(str(ex.CONFIG_FILE))
ex.HEAD_VERSION = __version__
ex.EXCHANGE = config.get('exchange')
ex.VPS_NAME = config.get('Exporter').get('vps_name')
# Telegram parameters
telegram = config.get('Telegram')
ex.TELEGRAM_URL = config.get('telegram_url')
for tlg in telegram:
    if ex.ID_EXCHANGE in tlg.get('id_exchange'):
        ex.TOKEN = tlg.get('token')
        ex.CHANNEL_ID = tlg.get('channel_id')
        ex.INLINE_BOT = tlg.get('inline')
        break


if __name__ == "__main__" and STANDALONE:
    import logging.handlers
    # For autoload last state
    ex.LOAD_LAST_STATE = 1 if len(sys.argv) > 1 else 0
    #
    log_file = Path(ex.LOG_PATH, f"{ex.ID_EXCHANGE}_{ex.SYMBOL}.log")
    ex.LAST_STATE_FILE = Path(ex.LAST_STATE_PATH, f"{ex.ID_EXCHANGE}_{ex.SYMBOL}.json")
    #
    logger = logging.getLogger('logger')
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=1000000, backupCount=10)
    handler.setFormatter(logging.Formatter(fmt="[%(asctime)s: %(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    try:
        loop.create_task(main(ex.SYMBOL))
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            loop.run_until_complete(ask_exit())
        except asyncio.CancelledError:
            pass
        except Exception as _err:
            print(f"Error: {_err}")
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
