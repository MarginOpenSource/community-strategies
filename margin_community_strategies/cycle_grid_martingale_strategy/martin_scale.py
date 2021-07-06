####################################################################
# Cyclic grid strategy based on martingale
# Copyright © 2021 Jerry Fedorenko aka VM
# ver. 0.7rc
# See readme.md for detail
# Communication with the author and support on
# https://discord.com/channels/600652551486177292/601329819371831296
##################################################################
"""
##################################################################
Disclaimer

All risks and possible losses associated with use of this strategy lie with you.
Strongly recommended that you test the strategy in the demo mode before using real bidding.
##################################################################
Install all needed packages, see import section below,
it must be installed into /margin-linux/resources/python/lib/python3.7/site-packages/
and 'save' strategy in margin should not return any error.

Set correct ID_EXCHANGE
Check and correct parameter at the top of script.

Set ROUND_FLOAT which correspond to the correct number of
zeros after the point for the first coins on the exchange.

Set custom fee = 0% in margin terminal

Verify init message in Strategy output window for no error
##################################################################
Additional function setup, depending from OS:

Place additional files into that place and update path in cfg.py:
/.margin/fund_rate.db
/margin-linux/resources/python/lib/python3.7/site-packages/cfg.py
/margin-linux/resources/python/lib/python3.7/site-packages/get_command_tlg.py

* Telegram notification
- Create Telegram bot
- Get token and channel_id for your bot
- Specify this data into cfg.py

! Next function can not be use under Windows. I faced a problem use sqlite3 module
in margin environment under Windows. You can try or resolve it.

* Telegram control
- Check the owner and run permission for get_command_tlg.py
- Try start it from cmd terminal, if any error - fix it.
- If get_command_tlg.py start, check passed, stop it from any process manager.
- When strategy started, you can send stop command from Telegram.
  In Telegram bot select message from desired strategy and Reply with text message 'stop'
  When strategy ends current cycle it not run next, but stay holding for manual action from
  margin interface. Only 'stop' command implemented now.
"""

##################################################################

import json
import math
from multiprocessing import Process, Queue

import platform
import sqlite3
import statistics
import subprocess as sp
import time
from datetime import datetime
import requests
from margin_strategy_sdk import *

import cfg

################################################################
# Exchange setup and parameter settings
################################################################
EXCHANGE = ('Demo-OKEX',  # 0
            'Binance',    # 1
            'Bitfinex',   # 2
            'OKEX',       # 3
            'Kraken',     # 4
            'Huobi',      # 5
            'YObit')      # 6
##################################################################

# Exchange setup
'''
# Bitfinex
ID_EXCHANGE = 2  # For collection of statistics
FEE_IN_PAIR = True  # Fee pays in pair
FEE_MAKER = 0.1  # standard exchange Fee for maker
FEE_TAKER = 0.17  # standard exchange Fee for taker
# '''
# OKEX
ID_EXCHANGE = 3  # For collection of statistics
FEE_IN_PAIR = True  # Fee pays in pair
FEE_MAKER = 0.08  # standard exchange Fee for maker
FEE_TAKER = 0.1  # standard exchange Fee for taker
# '''
# Trade parameter
START_ON_BUY = True  # First cycle direction
AMOUNT_FIRST = 0.0  # Deposit for Sell cycle in first currency
USE_ALL_FIRST_FUND = True  # Use all available fund for first current
AMOUNT_SECOND = 500  # Deposit for Buy cycle in second currency
PRICE_SHIFT = 0.05  # No market shift price in % from current bid/ask price
PROFIT = 0.25  # 0.15 - 0.85
PROFIT_MAX = 0.85  # If set it is maximum adapted cycle profit
PROFIT_K = 0.75  # k for place profit in relation to BB value
OVER_PRICE = 15  # 5-25% Max overlap price in one direction
ORDER_Q = 10  # Order quantity in one direction
GRID_MAX_COUNT = 5  # Max count for one moment place grid orders
MARTIN = 5  # 5-20, % increments volume of orders in the grid
SHIFT_GRID_THRESHOLD = 0.10  # % max price drift from 0 grid order before replace
SHIFT_GRID_DELAY = 30  # sec delay for shift grid action
# Other
ROUND_FLOAT = 1000000  # Floor round 0.00000 = 0.00x
STATUS_DELAY = 60  # Minute between sending Tlg message about current status
# Parameter for calculate grid over price in set_trade_condition()
ADAPTIVE_TRADE_CONDITION = True
KB = 2.0  # Bollinger k for Buy cycle -> low price
KT = 2.5  # Bollinger k for Sell cycle -> high price
MIN_DIFF = 0.05  # % min price difference for one step, min over price = MIN_DIFF * ORDER_Q
# Parameter for calculate price of grid orders by logarithmic scale
# If -1 function is disabled, can take a value from 0 to infinity (in practice no more 1000)
# When 0 - logarithmic scale, increase parameter the result is approaching linear
LINEAR_GRID_K = 50  # See 'Model of logarithmic grid.ods' for detail
# Average Directional Index with +DI and -DI for Reverse conditions analise
ADX_CANDLE_SIZE_IN_MINUTES = 1
ADX_NUMBER_OF_CANDLES = 60
ADX_PERIOD = 14
ADX_THRESHOLD = 30  # ADX value that indicates a strong trend
ADX_PRICE_THRESHOLD = 0.15  # % Max price drift before release Hold reverse cycle
#
MARTIN = (MARTIN + 100) / 100


def send_telegram(queue_to_tlg) -> None:
    url = cfg.url
    token = cfg.token
    channel_id = cfg.channel_id
    url += token
    method = url + '/sendMessage'
    while True:
        text = queue_to_tlg.get()
        requests.post(method, data={'chat_id': channel_id, 'text': text})


def save_to_db(queue_to_db) -> None:
    connection_analytic = sqlite3.connect(cfg.margin_path + 'funds_rate.db')
    cursor_analytic = connection_analytic.cursor()
    while True:
        data = queue_to_db.get()
        if data.get('stop_signal'):
            break
        cursor_analytic.execute("insert into t_funds values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (ID_EXCHANGE,
                                 None,
                                 data.get('f_currency'),
                                 data.get('s_currency'),
                                 data.get('f_funds'),
                                 data.get('s_funds'),
                                 data.get('avg_rate'),
                                 data.get('cycle_buy'),
                                 data.get('f_depo'),
                                 data.get('s_depo'),
                                 data.get('f_profit'),
                                 data.get('s_profit'),
                                 datetime.utcnow(),
                                 PRICE_SHIFT,
                                 PROFIT,
                                 data.get('over_price'),
                                 ORDER_Q,
                                 MARTIN,
                                 LINEAR_GRID_K,
                                 ADAPTIVE_TRADE_CONDITION,
                                 KB,
                                 KT,
                                 data.get('cycle_time')))
        connection_analytic.commit()
    connection_analytic.close()


class Strategy(StrategyBase):
    ##############################################################
    # strategy logic methods
    ##############################################################
    def __init__(self):
        super(Strategy, self).__init__()
        self.cycle_buy = START_ON_BUY  # Direction (Buy/Sell) for current cycle
        self.grid_orders_id = []  # List of initial grid order id
        self.orders = []  # List of open grid orders
        self.tp_order_id = None  # Take profit order id
        self.tp_wait_id = None  # Internal id for placed take profit order
        self.sum_amount_first = 0.0  # Sum buy/sell in first currency for current cycle
        self.sum_amount_second = 0.0  # Sum buy/sell in second currency for current cycle
        self.deposit_first = AMOUNT_FIRST  # Calculated operational deposit
        self.deposit_second = AMOUNT_SECOND  # Calculated operational deposit
        self.sum_profit_first = 0.0  # Sum profit from start to now()
        self.sum_profit_second = 0.0  # Sum profit from start to now()
        self.cycle_buy_count = 0  # Count for buy cycle
        self.cycle_sell_count = 0  # Count for sell cycle
        self.shift_grid_threshold = None  # Price level of shift grid threshold for current cycle
        self.f_currency = ''  # First currency name
        self.s_currency = ''  # Second currency name
        self.connection_analytic = None  # Connection to .db
        self.cursor_analytic = None  # Cursor for .db
        self.take_profit_order_hold = {}  # Save unreleased take profit order
        self.tp_hold = False  # Flag for replace take profit order
        self.tp_cancel = False  # Cancel tp order after success place
        self.tlg_header = ''  # Header for Telegram message
        self.last_shift_time = None
        self.avg_rate = None  # Flow average rate for trading pair
        self.grid_hold = {}  # Save for later create grid orders
        self.start_hold = False  # Hold start if exist not accepted grid order(s)
        self.cancel_order_id = None  # Exist canceled not confirmed order
        self.over_price = None  # Adaptive over price
        self.grid_save = []  # List of save grid orders for later place
        self.grid_save_flag = False  # Flag when place last part of grid orders
        self.part_amount_first = 0.0  # Amount of partially filled order
        self.part_amount_second = 0.0  # Amount of partially filled order
        self.part_place_tp = False  # When part fill grid order place tp if price go a way
        self.py_path = cfg.py_path  # Path where .py module placed. Setup in cfg.py
        self.db_path = cfg.margin_path  # Path where .db file placed. Setup in cfg.py
        self.command = None  # External input command from Telegram
        self.start_after_shift = False  # Flag set before shift, clear into Start()
        self.queue_to_db = Queue()  # Queue for save data to .db
        self.pr_db = None  # Process for save data to .db
        self.queue_to_tlg = Queue()  # Queue for sending message to Telegram
        self.pr_tlg = None  # Process for sending message to Telegram
        self.restart = None  # Set after execute take profit order and restart cycle
        self.profit_first = 0.0  # Cycle profit
        self.profit_second = 0.0  # Cycle profit
        self.status_time = None  # Last time sending status message
        self.cycle_time = None  # Cycle start time
        self.cycle_time_reverse = None  # Reverse cycle start time
        self.reverse = False  # After reverse cycle, no loss over_price calculation
        self.reverse_target_amount = None  # Return amount for initial reverse cycle with profit
        self.reverse_hold = False  # Exist unreleased reverse state
        self.reverse_price = 0.0  # Price when execute last grid order and hold reverse cycle

    def init(self) -> None:
        # print('Start Init section')
        # Check setup parameter
        if PRICE_SHIFT >= SHIFT_GRID_THRESHOLD:
            print('Error: PRICE_SHIFT >= SHIFT_GRID_THRESHOLD, fix it')
        self.command = None
        tcm = self.get_trading_capability_manager()
        self.f_currency = self.get_first_currency()
        self.s_currency = self.get_second_currency()
        self.tlg_header = '{}, {}/{}. '.format(EXCHANGE[ID_EXCHANGE], self.f_currency, self.s_currency)
        self.status_time = time.time()
        self.cycle_time = datetime.utcnow()
        self.start_after_shift = True
        self.over_price = OVER_PRICE
        last_price = self.get_buffered_ticker().last_price
        # Init var for analytic
        self.connection_analytic = sqlite3.connect(self.db_path + 'funds_rate.db')
        self.cursor_analytic = self.connection_analytic.cursor()
        df = self.get_buffered_funds()[self.f_currency].available
        if USE_ALL_FIRST_FUND and df > 0 and self.cycle_buy:
            print('Check USE_ALL_FIRST_FUND parameter. You may have loss on first Reverse cycle.')
        if self.cycle_buy:
            if self.deposit_second > self.get_buffered_funds()[self.s_currency].available:
                print('Not enough second coin for Buy cycle!')
            first_order_vlm = self.deposit_second * 1 * (1 - MARTIN) / (1 - pow(MARTIN, ORDER_Q))
            first_order_vlm /= last_price
        else:
            if USE_ALL_FIRST_FUND:
                self.deposit_first = df
            else:
                if self.deposit_first > df:
                    print('Not enough first coin for Sell cycle!')
            first_order_vlm = self.deposit_first * 1 * (1 - MARTIN) / (1 - pow(MARTIN, ORDER_Q))
        if self.cycle_buy and first_order_vlm < tcm.get_min_buy_amount(last_price):
            print('Total deposit {} {} not enough for min amount for {} orders.'
                  .format(AMOUNT_SECOND, self.s_currency, ORDER_Q))
        elif not self.cycle_buy and first_order_vlm < tcm.get_min_sell_amount(last_price):
            print('Total deposit {} {} not enough for min amount for {} orders.'
                  .format(self.deposit_first, self.f_currency, ORDER_Q))
        # Create processes for save to .db and send Telegram message
        self.pr_db = Process(target=save_to_db, args=(self.queue_to_db,), daemon=True)
        self.pr_tlg = Process(target=send_telegram, args=(self.queue_to_tlg,), daemon=True)

    def get_strategy_config(self) -> StrategyConfig:
        s = StrategyConfig()
        s.required_data_updates = {StrategyConfig.ORDER_BOOK,
                                   StrategyConfig.FUNDS}
        s.normalize_exchange_buy_amounts = True
        return s

    def save_strategy_state(self) -> Dict[str, str]:
        if (time.time() - self.status_time) / 60 > STATUS_DELAY:
            if self.command == 'stop':
                self.message_log('Stop, waiting manual action', tlg=True)
            else:
                orders = self.get_buffered_open_orders()
                order_buy = len([i for i in orders if i.buy is True])
                order_sell = len([i for i in orders if i.buy is False])
                last_price = self.get_buffered_ticker().last_price
                ct = datetime.utcnow() - self.cycle_time
                self.message_log('{}{}{} cycle with {} buy and {} sell active orders.\n'
                                 'Over price: {:.2f}\n'
                                 'Last price: {}\n'
                                 'From start {}'
                                 .format('Buy' if self.cycle_buy else 'Sell',
                                         ' Reverse' if self.reverse else '',
                                         ' Hold reverse' if self.reverse_hold else '',
                                         order_buy, order_sell, self.over_price, last_price,
                                         str(ct).rsplit('.')[0]), tlg=True)
        if self.reverse_hold:
            last_price = self.get_buffered_ticker().last_price
            if self.cycle_buy:
                price_diff = 100 * (self.reverse_price - last_price) / self.reverse_price
            else:
                price_diff = 100 * (last_price - self.reverse_price) / self.reverse_price
            if price_diff > ADX_PRICE_THRESHOLD:
                # Reverse
                self.cycle_buy = not self.cycle_buy
                self.reverse = True
                self.reverse_hold = False
                print('Release Hold reverse cycle')
                self.start()

        return {'cycle_buy': str(self.cycle_buy),
                'grid_orders_id': json.dumps(self.grid_orders_id),
                # TODO Save orders
                # 'orders': json.dumps(self.orders),
                'tp_order_id': str(self.tp_order_id),
                'sum_amount_first': str(self.sum_amount_first),
                'sum_amount_second': str(self.sum_amount_second),
                'deposit_first': str(self.deposit_first),
                'deposit_second': str(self.deposit_second),
                'sum_profit_first': str(self.sum_profit_first),
                'sum_profit_second': str(self.sum_profit_second),
                'cycle_buy_count': str(self.cycle_buy_count),
                'cycle_sell_count': str(self.cycle_sell_count)
                }

    def restore_strategy_state(self, strategy_state: Dict[str, str]) -> None:
        # TODO Restore algo after crash
        print('Restore_state')
        print("\n".join("{}\t{}".format(k, v) for k, v in strategy_state.items()))

    def place_grid(self, buy_side: bool, depo: float) -> None:
        self.last_shift_time = None
        self.grid_save_flag = False
        tcm = self.get_trading_capability_manager()
        if buy_side:
            max_bid_price = self.get_buffered_order_book().bids[0].price
            base_price = max_bid_price - PRICE_SHIFT * max_bid_price / 100
        else:
            min_ask_price = self.get_buffered_order_book().asks[0].price
            base_price = min_ask_price + PRICE_SHIFT * min_ask_price / 100
        if ADAPTIVE_TRADE_CONDITION or self.reverse:
            try:
                self.set_trade_conditions(buy_side, depo, base_price)
            except Exception as ex:
                self.message_log('Do not set over price: {}'.format(ex), log_level=LogLevel.ERROR)
        delta_price = (self.over_price * base_price) / (100 * (ORDER_Q - 1))
        funds = self.get_buffered_funds()
        if buy_side:
            fund = funds[self.s_currency].available
        else:
            fund = funds[self.f_currency].available
        if depo <= fund:
            self.grid_hold.clear()
            for i in range(ORDER_Q):
                if self.reverse:
                    price_k = 1 - math.log(ORDER_Q - i, ORDER_Q)
                elif LINEAR_GRID_K >= 0:
                    price_k = 1 - math.log(ORDER_Q - i, ORDER_Q + LINEAR_GRID_K)
                else:
                    price_k = 1
                if buy_side:
                    price = base_price - i * delta_price * price_k
                else:
                    price = base_price + i * delta_price * price_k
                price = tcm.round_price(price, RoundingType.ROUND)
                amount = depo * pow(MARTIN, i) * (1 - MARTIN) / (1 - pow(MARTIN, ORDER_Q))
                if buy_side:
                    amount /= price
                amount = tcm.round_amount(amount, RoundingType.FLOOR)
                # create order for grid
                if i < GRID_MAX_COUNT:
                    waiting_order_id = self.place_limit_order(buy_side, amount, price)
                    self.grid_orders_id.append(waiting_order_id)
                else:
                    self.grid_save.append({'buy_side': buy_side, 'amount': amount, 'price': price})
            if buy_side:
                self.shift_grid_threshold = base_price + SHIFT_GRID_THRESHOLD * base_price / 100
            else:
                self.shift_grid_threshold = base_price - SHIFT_GRID_THRESHOLD * base_price / 100
            self.message_log('Placed grid order, shift grid threshold: {:f}'
                             .format(self.shift_grid_threshold))
        else:
            self.grid_hold = {'buy_side': buy_side,
                              'depo': depo}
            self.message_log('Hold grid orders for {} {} depo. Current fund is {}'
                             .format('Buy' if buy_side else 'Sell', depo, fund))

    def place_profit_order(self, by_market=False) -> None:
        self.take_profit_order_hold.clear()
        if self.tp_wait_id or self.cancel_order_id:
            # Wait confirm or cancel old and replace them
            self.tp_hold = True
            print('Wait take profit order, replace not confirmed')
        elif self.tp_order_id:
            # Cancel take profit order, place new
            self.tp_hold = True
            self.cancel_order_id = self.tp_order_id
            self.cancel_order(self.tp_order_id)
            print('Hold take profit order, replace existing')
        else:
            buy_side = not self.cycle_buy
            # Calculate take profit order
            tp = self.calc_profit_order(buy_side, by_market=by_market)
            price = tp.get('price')
            amount = tp.get('amount')
            profit = tp.get('profit')
            # Check funds available
            funds = self.get_buffered_funds()
            if buy_side and amount * price > funds[self.s_currency].available:
                # Save take profit order and wait update balance
                self.take_profit_order_hold = {'buy_side': buy_side,
                                               'amount': amount * price}
                print('Hold take profit order for\n'
                      'Buy {} {} by {}, wait {} {}'
                      .format(amount, self.f_currency, price, amount * price, self.s_currency))
            elif not buy_side and amount > funds[self.f_currency].available:
                # Save take profit order and wait update balance
                self.take_profit_order_hold = {'buy_side': buy_side,
                                               'amount': amount}
                print('Hold take profit order for\n'
                      'Sell {} {} by {}, wait funding'
                      .format(amount, self.f_currency, price))
            else:
                # Create take profit order
                self.message_log('Create {} take profit order,\n'
                                 'vlm: {}, price: {}, profit: {}%'
                                 .format('Buy' if buy_side else 'Sell', amount, price, profit))
                self.tp_wait_id = self.place_limit_order(buy_side, amount, price)

    def start(self) -> None:
        self.shift_grid_threshold = None
        self.part_place_tp = False
        # Cancel take profit order in all state
        self.take_profit_order_hold.clear()
        self.tp_hold = False
        if self.tp_order_id:
            self.tp_cancel = True
            if not self.cancel_order_id:
                self.cancel_order_id = self.tp_order_id
                self.cancel_order(self.tp_order_id)
        elif self.tp_wait_id:
            # Wait tp order and cancel in on_cancel_order_success and restart
            self.tp_cancel = True
        else:
            self.grid_save.clear()
            if self.grid_orders_id:
                # Exist not accepted grid order(s), wait msg from exchange
                self.start_hold = True
            elif self.orders:
                # Sequential removal orders from grid
                self.cancel_order(self.orders[0].id)
            else:
                if not self.pr_db.is_alive():
                    print('Start process for .db save')
                    try:
                        self.pr_db.start()
                    except AssertionError as error:
                        self.message_log(str(error), log_level=LogLevel.ERROR)
                if not self.pr_tlg.is_alive():
                    print('Start process for Telegram send')
                    try:
                        self.pr_tlg.start()
                    except AssertionError as error:
                        self.message_log(str(error), log_level=LogLevel.ERROR)
                # Check and start Telegram control
                if platform.system() == 'Linux':
                    try:
                        # Check if get_command_tlg already started. Can be edit for other OS then Linux!
                        sp.check_output('ps -eo cmd| grep -v grep | grep get_command_tlg', shell=True)
                        # print('Telegram control service already started')
                    except sp.CalledProcessError:
                        print('Start Telegram control service')
                        sp.Popen([self.py_path + 'get_command_tlg.py'])
                    # Get command for next cycle
                    bot_id = self.tlg_header.split('.')[0]
                    self.cursor_analytic.execute('SELECT max(message_id), text_in, bot_id\
                                                  FROM t_control WHERE bot_id=:bot_id', {'bot_id': bot_id})
                    row = self.cursor_analytic.fetchone()
                    if row[0]:
                        # Analyse and execute received command
                        self.command = row[1]
                        # Remove applied command from .db
                        self.cursor_analytic.execute('UPDATE t_control SET apply = 1 WHERE message_id=:message_id',
                                                     {'message_id': row[0]})
                        self.connection_analytic.commit()
                else:
                    print('For {} Telegram control not released'.format(platform.system()))
                # Save initial funds and cycle statistics to .db for external analytics
                if self.restart and not self.reverse:
                    # Not save data inside of reverse cycle
                    print('Save data to .db')
                    df = self.deposit_first - self.profit_first
                    ds = self.deposit_second - self.profit_second
                    ct = datetime.utcnow() - self.cycle_time
                    ct = ct.total_seconds()
                    data_to_db = {'f_currency': self.f_currency,
                                  's_currency': self.s_currency,
                                  'f_funds': self.get_buffered_funds()[self.f_currency].total_for_currency,
                                  's_funds': self.get_buffered_funds()[self.s_currency].total_for_currency,
                                  'avg_rate': self.avg_rate,
                                  'cycle_buy': self.cycle_buy,
                                  'f_depo': df,
                                  's_depo': ds,
                                  'f_profit': self.profit_first,
                                  's_profit': self.profit_second,
                                  'over_price': self.over_price,
                                  'cycle_time': ct}
                    self.queue_to_db.put(data_to_db)
                self.restart = None
                self.avg_rate = self.get_buffered_ticker().last_price
                if not self.start_after_shift and not self.reverse:
                    self.message_log('Complete {} buy cycle and {} sell cycle.\n'
                                     'For all cycles profit:\n'
                                     'First: {}\n'
                                     'Second: {}\n'
                                     'Summary: {}'
                                     .format(self.cycle_buy_count, self.cycle_sell_count,
                                             self.sum_profit_first, self.sum_profit_second,
                                             self.sum_profit_first * self.avg_rate + self.sum_profit_second), tlg=True)
                if self.command == 'stop' and not self.reverse:
                    self.message_log('Stop, waiting manual action', tlg=True)
                else:
                    # Init variable
                    self.sum_amount_first = 0.0
                    self.sum_amount_second = 0.0
                    self.part_amount_first = 0.0
                    self.part_amount_second = 0.0
                    self.profit_first = 0.0
                    self.profit_second = 0.0
                    self.cycle_time = datetime.utcnow()
                    if self.cycle_buy:
                        self.deposit_second = int(self.deposit_second * ROUND_FLOAT) / ROUND_FLOAT
                        amount = self.deposit_second
                        self.message_log('Start{} Buy cycle with {} {} depo'
                                         .format(' Reverse' if self.reverse else '',
                                                 amount, self.s_currency), tlg=True)
                    else:
                        if USE_ALL_FIRST_FUND:
                            fund = self.get_buffered_funds()[self.f_currency].available
                            if fund > self.deposit_first:
                                self.deposit_first = fund
                                self.message_log('Use all available fund for first currency')
                        self.deposit_first = int(self.deposit_first * ROUND_FLOAT) / ROUND_FLOAT
                        amount = self.deposit_first
                        self.message_log('Start{} Sell cycle with {} {} depo'
                                         .format(' Reverse' if self.reverse else '',
                                                 amount, self.f_currency), tlg=True)
                    self.start_after_shift = False
                    self.place_grid(self.cycle_buy, amount)
                # print('End Start section')

    def on_new_order_book(self, order_book: OrderBook) -> None:
        if self.shift_grid_threshold and self.last_shift_time and not self.part_place_tp:
            if time.time() - self.last_shift_time > SHIFT_GRID_DELAY:
                if ((self.cycle_buy and order_book.bids[0].price >= self.shift_grid_threshold) or
                        (not self.cycle_buy and order_book.asks[0].price <= self.shift_grid_threshold)):
                    self.message_log('Shift grid')
                    self.start_after_shift = True
                    self.start()
        elif self.part_place_tp and self.shift_grid_threshold:
            if ((self.cycle_buy and order_book.bids[0].price >= self.shift_grid_threshold) or
                    (not self.cycle_buy and order_book.asks[0].price <= self.shift_grid_threshold)):
                self.shift_grid_threshold = None
                self.part_place_tp = False
                print('Place take profit after part fill grid order')
                self.place_profit_order()

    def on_new_funds(self, funds: Dict[str, FundsEntry]) -> None:
        if self.take_profit_order_hold:
            if self.take_profit_order_hold['buy_side']:
                available_fund = funds[self.s_currency].available
            else:
                available_fund = funds[self.f_currency].available
            if available_fund >= self.take_profit_order_hold['amount']:
                self.place_profit_order()
            else:
                print('Exist unreleased take profit order')
        if self.grid_hold:
            if self.grid_hold['buy_side']:
                available_fund = funds[self.s_currency].available
            else:
                available_fund = funds[self.f_currency].available
            if available_fund >= self.grid_hold['depo']:
                self.place_grid(self.grid_hold['buy_side'],
                                self.grid_hold['depo'])
            else:
                print('Exist unreleased grid orders')

    def stop(self) -> None:
        data_to_db = {'stop_signal': True}
        self.queue_to_db.put(data_to_db)
        self.pr_tlg.kill()
        self.connection_analytic.close()

    def message_log(self, msg: str, log_level=LogLevel.INFO, tlg=False) -> None:
        print(msg)
        write_log(log_level, msg)
        msg = self.tlg_header + msg
        if tlg:
            self.status_time = time.time()
            self.queue_to_tlg.put(msg)

    def bollinger_band(self, candle_size_in_minutes: int, number_of_candles: int) -> Dict[str, float]:
        # Bottom BB as sma-kb*stdev
        # Top BB as as sma+kt*stdev
        # For Buy cycle over_price as 100*(Ticker.last_price - bbb) / Ticker.last_price
        # For Sell cycle over_price as 100*(tbb - Ticker.last_price) / Ticker.last_price
        candle_close = []
        candle = self.get_buffered_recent_candles(candle_size_in_minutes=candle_size_in_minutes,
                                                  number_of_candles=number_of_candles)
        for i in candle:
            candle_close.append(i.close)
        sma = statistics.mean(candle_close)
        st_dev = statistics.stdev(candle_close)
        # print('sma={}, st_dev={}, last price={}'.format(sma, st_dev, last_price))
        tbb = sma + KT * st_dev
        bbb = sma - KB * st_dev
        # print('tbb={}, bbb={}'.format(tbb, bbb))
        return {'tbb': tbb, 'bbb': bbb}

    def set_trade_conditions(self, buy_side: bool, depo: float, base_price: float) -> None:
        if self.reverse:
            over_price = self.calc_over_price(buy_side, depo, base_price)
        else:
            bb = self.bollinger_band(60, 20)
            last_price = self.get_buffered_ticker().last_price
            if buy_side:
                bbb = bb.get('bbb')
                over_price = 100*(last_price - bbb) / last_price
            else:
                tbb = bb.get('tbb')
                over_price = 100 * (tbb - last_price) / last_price
        if over_price < MIN_DIFF * ORDER_Q:
            self.over_price = MIN_DIFF * ORDER_Q
        elif over_price > OVER_PRICE and not self.reverse:
            self.over_price = OVER_PRICE
        else:
            self.over_price = over_price
        self.message_log('For{} {} cycle set {:.2f}% over price'.format(' Reverse' if self.reverse else '',
                                                                        'Buy' if buy_side else 'Sell',
                                                                        self.over_price), tlg=True)

    def set_profit(self) -> float:
        bb = self.bollinger_band(15, 20)
        tbb = bb.get('tbb')
        bbb = bb.get('bbb')
        last_price = self.get_buffered_ticker().last_price
        if self.cycle_buy:
            profit = PROFIT_K * 100 * (tbb - last_price) / last_price
        else:
            profit = PROFIT_K * 100 * (last_price - bbb) / last_price
        profit = round(profit, 2)
        if profit < PROFIT:
            profit = PROFIT
        elif profit > PROFIT_MAX:
            profit = PROFIT_MAX
        return profit

    def calc_profit_order(self, buy_side: bool, by_market=False) -> Dict[str, float]:
        tcm = self.get_trading_capability_manager()
        sum_amount_first = self.sum_amount_first
        sum_amount_second = self.sum_amount_second
        # Calculate take profit order
        if PROFIT_MAX:
            profit = self.set_profit()
        else:
            profit = PROFIT
        # Retreat of courses
        price = sum_amount_second / sum_amount_first
        if not FEE_IN_PAIR:
            if by_market:
                fee = FEE_TAKER
            else:
                fee = FEE_MAKER
            if buy_side:
                price -= fee * price / 100
            else:
                price += fee * price / 100
        if buy_side:
            price -= (FEE_MAKER + profit) * price / 100
            price = tcm.round_price(price, RoundingType.FLOOR)
            amount = sum_amount_second / price
        else:
            price += (FEE_MAKER + profit) * price / 100
            price = tcm.round_price(price, RoundingType.CEIL)
            amount = sum_amount_first
        amount = int(amount * ROUND_FLOAT) / ROUND_FLOAT
        amount = tcm.round_amount(amount, RoundingType.FLOOR)
        return {'price': price, 'amount': amount, 'profit': profit}

    def calc_over_price(self, buy_side: bool, depo: float, base_price: float) -> float:
        # Calculate over price for depo refund after Reverse cycle
        # Search y = kx + b and calculate over_price fot target return amount
        over_price = 0.0
        b = self.calc_grid_avg(buy_side, depo, base_price, over_price)
        over_price = 30
        grid_amount_30 = self.calc_grid_avg(buy_side, depo, base_price, over_price)
        k = (grid_amount_30 - b) / over_price
        over_price = (self.reverse_target_amount - b) / k
        return over_price

    def adx(self, adx_candle_size_in_minutes: int, adx_number_of_candles: int, adx_period: int) -> Dict[str, float]:
        # Average Directional Index
        # Math from https://blog.quantinsti.com/adx-indicator-python/
        # Test data
        # high = [90, 95, 105, 120, 140, 165, 195, 230, 270, 315, 365]
        # low = [82, 85, 93, 106, 124, 147, 175, 208, 246, 289, 337]
        # close = [87, 87, 97, 114, 133, 157, 186, 223, 264, 311, 350]
        ##############################################################
        high = []
        low = []
        close = []
        candle = self.get_buffered_recent_candles(candle_size_in_minutes=adx_candle_size_in_minutes,
                                                  number_of_candles=adx_number_of_candles)
        for i in candle:
            high.append(i.high)
            low.append(i.low)
            close.append(i.close)
        dm_pos = []
        dm_neg = []
        tr_arr = []
        dm_pos_smooth = []
        dm_neg_smooth = []
        tr_smooth = []
        di_pos = []
        di_neg = []
        dx = []
        n = 1
        n_max = len(high) - 1
        while n <= n_max:
            m_pos = high[n] - high[n - 1]
            m_neg = low[n - 1] - low[n]
            _m_pos = 0
            _m_neg = 0
            if m_pos > 0 and m_pos > m_neg:
                _m_pos = m_pos
            if m_neg > 0 and m_neg > m_pos:
                _m_neg = m_neg
            dm_pos.append(_m_pos)
            dm_neg.append(_m_neg)
            tr = max(high[n], close[n - 1]) - min(low[n], close[n - 1])
            tr_arr.append(tr)
            if n == adx_period:
                dm_pos_smooth.append(sum(dm_pos))
                dm_neg_smooth.append(sum(dm_neg))
                tr_smooth.append(sum(tr_arr))
            if n > adx_period:
                dm_pos_smooth.append((dm_pos_smooth[-1] - dm_pos_smooth[-1] / adx_period) + _m_pos)
                dm_neg_smooth.append((dm_neg_smooth[-1] - dm_neg_smooth[-1] / adx_period) + _m_neg)
                tr_smooth.append((tr_smooth[-1] - tr_smooth[-1] / adx_period) + tr)
            if n >= adx_period:
                # Calculate +DI, -DI and DX
                di_pos.append(100 * dm_pos_smooth[-1] / tr_smooth[-1])
                di_neg.append(100 * dm_neg_smooth[-1] / tr_smooth[-1])
                dx.append(100 * abs(di_pos[-1] - di_neg[-1]) / abs(di_pos[-1] + di_neg[-1]))
            n += 1
        _adx = statistics.mean(dx[len(dx) - adx_period::])
        return {'adx': _adx, '+DI': di_pos[-1], '-DI': di_neg[-1]}

    def calc_grid_avg(self, buy_side: bool, depo: float, base_price: float, over_price: float) -> float:
        # Calculate return average amount in second coin for grid orders with fixed initial parameters
        tcm = self.get_trading_capability_manager()
        delta_price = (over_price * base_price) / (100 * (ORDER_Q - 1))
        avg_amount = 0.0
        for i in range(ORDER_Q):
            price_k = 1 - math.log(ORDER_Q - i, ORDER_Q)
            if buy_side:
                price = base_price - i * delta_price * price_k
            else:
                price = base_price + i * delta_price * price_k
            price = tcm.round_price(price, RoundingType.ROUND)
            amount = depo * pow(MARTIN, i) * (1 - MARTIN) / (1 - pow(MARTIN, ORDER_Q))
            amount = tcm.round_amount(amount, RoundingType.FLOOR)
            if buy_side:
                amount /= price
                avg_amount += amount
            else:
                avg_amount += amount * price
        return avg_amount

    def suspend(self) -> None:
        pass

    def unsuspend(self) -> None:
        pass

    ##############################################################
    # private update methods
    ##############################################################

    def on_order_update(self, update: OrderUpdate) -> None:
        print('Order {}: '.format(update.original_order.id), update.status)
        if update.status in [OrderUpdate.ADAPTED,
                             OrderUpdate.NO_CHANGE,
                             OrderUpdate.REAPPEARED,
                             OrderUpdate.DISAPPEARED,
                             OrderUpdate.CANCELED,
                             OrderUpdate.OTHER_CHANGE]:
            pass
        else:
            self.shift_grid_threshold = None
            self.part_place_tp = False
            result_trades = update.resulting_trades
            trade_amount_first = 0
            trade_amount_second = 0
            for i in result_trades:
                # Calculate sum trade amount for both currency
                trade_amount_first += i.amount
                trade_amount_second += i.amount * i.price
                print('i={}, first: {}, price: {}'.format(i.id, i.amount, i.price))
            # Retreat of courses
            self.avg_rate = trade_amount_second / trade_amount_first
            self.message_log('Order update {}\nFirst: {}, second: {}'
                             .format(update.status, trade_amount_first, trade_amount_second))
            if update.status == OrderUpdate.FILLED or update.status == OrderUpdate.ADAPTED_AND_FILLED:
                if any(i.id == update.original_order.id for i in self.orders):
                    self.part_place_tp = False
                    # Calculate trade amount with Fee for grid order for both currency
                    if FEE_IN_PAIR:
                        if self.cycle_buy:
                            trade_amount_first -= FEE_MAKER * trade_amount_first / 100
                            print('For grid order First - fee: {}'.format(trade_amount_first))
                        else:
                            trade_amount_second -= FEE_MAKER * trade_amount_second / 100
                            print('For grid order Second - fee: {}'.format(trade_amount_second))
                    # Calculate cycle sum trading for both currency
                    self.sum_amount_first += trade_amount_first + self.part_amount_first
                    self.sum_amount_second += trade_amount_second + self.part_amount_second
                    self.part_amount_first = 0
                    self.part_amount_second = 0
                    print('Sum_amount_first: {}\n'
                          'Sum_amount_second: {}'
                          .format(self.sum_amount_first, self.sum_amount_second))
                    # Remove grid order with =id from cycle order list
                    for i, o in enumerate(self.orders):
                        if o.id == update.original_order.id:
                            del self.orders[i]
                            break
                    if not self.orders and not self.grid_save:
                        # Ended grid order, calculate depo and Reverse
                        if self.reverse:
                            self.message_log('End reverse cycle', tlg=True)
                            self.reverse = False
                            self.restart = True
                            # Calculate profit and time for Reverse cycle
                            self.cycle_time = self.cycle_time_reverse
                            if self.cycle_buy:
                                self.profit_first = self.sum_amount_first - self.deposit_first
                                self.message_log('Reverse cycle profit first {}'.format(self.profit_first))
                                self.sum_profit_first += self.profit_first
                                self.cycle_sell_count += 1
                            else:
                                self.profit_second = self.sum_amount_second - self.deposit_second
                                self.message_log('Reverse cycle profit second {}'.format(self.profit_second))
                                self.sum_profit_second += self.profit_second
                                self.cycle_buy_count += 1
                            self.cycle_time_reverse = None
                            self.reverse_target_amount = None
                        else:
                            adx = self.adx(ADX_CANDLE_SIZE_IN_MINUTES, ADX_NUMBER_OF_CANDLES, ADX_PERIOD)
                            # print('adx: {}, +DI: {}, -DI: {}'.format(adx.get('adx'), adx.get('+DI'), adx.get('-DI')))
                            trend_up = adx.get('adx') > ADX_THRESHOLD and adx.get('+DI') > adx.get('-DI')
                            trend_down = adx.get('adx') > ADX_THRESHOLD and adx.get('-DI') > adx.get('+DI')
                            self.cycle_time_reverse = self.cycle_time
                            # Calculate target return amount
                            tp = self.calc_profit_order(not self.cycle_buy)
                            if self.cycle_buy:
                                self.reverse_target_amount = tp.get('amount') * tp.get('price')
                            else:
                                self.reverse_target_amount = tp.get('amount')
                            self.message_log('Target return amount: {}'.format(self.reverse_target_amount))
                            if (self.cycle_buy and trend_down) or (not self.cycle_buy and trend_up):
                                self.message_log('Start reverse cycle', tlg=True)
                                self.reverse = True
                            else:
                                self.message_log('Hold reverse cycle')
                                self.reverse_price = self.get_buffered_ticker().last_price
                                self.reverse_hold = True
                                self.place_profit_order()
                        if self.cycle_buy:
                            self.deposit_first = self.sum_amount_first
                        else:
                            self.deposit_second = self.sum_amount_second
                        if not self.reverse_hold:
                            # Reverse
                            self.cycle_buy = not self.cycle_buy
                            self.start()
                    else:
                        self.place_profit_order()
                elif self.tp_order_id == update.original_order.id:
                    # Filled take profit order, restart
                    self.tp_order_id = None
                    if self.reverse_hold:
                        self.reverse_hold = False
                        self.cycle_time_reverse = None
                    # Calculate trade amount with Fee for take profit order for both currency
                    if FEE_IN_PAIR:
                        if self.cycle_buy:
                            trade_amount_second -= FEE_MAKER * trade_amount_second / 100
                            print('For take profit order Second - fee: {}'.format(trade_amount_second))
                        else:
                            trade_amount_first -= FEE_MAKER * trade_amount_first / 100
                            print('For take profit order First - fee: {}'.format(trade_amount_first))
                    # Calculate cycle and total profit, refresh depo
                    if self.cycle_buy:
                        self.profit_second = trade_amount_second - self.sum_amount_second
                        self.message_log('Cycle profit second {}'.format(self.profit_second))
                        self.deposit_second += self.profit_second
                        if not self.reverse:
                            # Take account profit only for non reverse cycle
                            self.sum_profit_second += self.profit_second
                        self.cycle_buy_count += 1
                    else:
                        self.profit_first = trade_amount_first - self.sum_amount_first
                        self.message_log('Cycle profit first {}'.format(self.profit_first))
                        self.deposit_first += self.profit_first
                        if not self.reverse:
                            # Take account profit only for non reverse cycle
                            self.sum_profit_first += self.profit_first
                        self.cycle_sell_count += 1
                    self.message_log('Restart', tlg=True)
                    self.restart = True
                    self.start()
                else:
                    self.message_log('There is a partially executed order. Waiting for filling or adjust yourself.',
                                     tlg=True)
            elif update.status == OrderUpdate.PARTIALLY_FILLED:
                self.shift_grid_threshold = None
                self.part_place_tp = False
                order_trade = update.original_order
                if self.tp_order_id == order_trade.id:
                    # This was take profit order
                    if FEE_IN_PAIR:
                        if self.cycle_buy:
                            trade_amount_second -= FEE_MAKER * trade_amount_second / 100
                        else:
                            trade_amount_first -= FEE_MAKER * trade_amount_first / 100
                    if self.cycle_buy:
                        print('TP order part.fill Second - fee: {}'.format(trade_amount_second))
                    else:
                        print('TP order part.fill First - fee: {}'.format(trade_amount_first))
                    # Consider if grid order filled
                    self.part_amount_first -= trade_amount_first
                    self.part_amount_second -= trade_amount_second
                else:
                    # This was grid order
                    if FEE_IN_PAIR:
                        if self.cycle_buy:
                            trade_amount_first -= FEE_MAKER * trade_amount_first / 100
                        else:
                            trade_amount_second -= FEE_MAKER * trade_amount_second / 100
                    if self.cycle_buy:
                        print('Grid order part.fill First - fee: {}'.format(trade_amount_first))
                    else:
                        print('Grid order part.fill Second - fee: {}'.format(trade_amount_second))
                    # Increase trade result and if next fill order is grid decrease trade result
                    self.sum_amount_first += trade_amount_first
                    self.sum_amount_second += trade_amount_second
                    self.part_amount_first -= trade_amount_first
                    self.part_amount_second -= trade_amount_second
                    if self.tp_order_id:
                        # Replace take profit order
                        self.place_profit_order()
                    else:
                        # Get min trade amount
                        tcm = self.get_trading_capability_manager()
                        if self.cycle_buy:
                            min_trade_amount = tcm.get_min_sell_amount(self.avg_rate)
                            amount = self.sum_amount_first
                            amount = tcm.round_amount(amount, RoundingType.FLOOR)
                            print('Sell amount: {}, min sell amount: {}'.format(amount, min_trade_amount))
                        else:
                            min_trade_amount = tcm.get_min_buy_amount(self.avg_rate)
                            amount = self.sum_amount_second / self.avg_rate
                            amount = tcm.round_amount(amount, RoundingType.FLOOR)
                            print('Buy amount: {}, min buy amount: {}'.format(amount, min_trade_amount))
                        price = self.sum_amount_second / self.sum_amount_first
                        if amount >= min_trade_amount:
                            # Wait full filling grid order or price way out for place TP
                            self.part_place_tp = True
                            # Calculate price when place TP order
                            if self.cycle_buy:
                                price += 2 * FEE_TAKER * price / 100
                                price = tcm.round_price(price, RoundingType.CEIL)
                            else:
                                price -= 2 * FEE_TAKER * price / 100
                                price = tcm.round_price(price, RoundingType.FLOOR)
                            self.shift_grid_threshold = price
                        else:
                            # Partially trade too small, ignore
                            if self.cycle_buy:
                                self.deposit_second += self.part_amount_second
                            else:
                                self.deposit_first += self.part_amount_first
                            if self.cycle_buy:
                                price += 2 * SHIFT_GRID_THRESHOLD * price / 100
                                price = tcm.round_price(price, RoundingType.CEIL)
                            else:
                                price -= 2 * SHIFT_GRID_THRESHOLD * price / 100
                                price = tcm.round_price(price, RoundingType.FLOOR)
                            self.shift_grid_threshold = price

    def on_place_order_success(self, place_order_id: int, order: Order) -> None:
        if order.remaining_amount == 0.0:
            self.shift_grid_threshold = None
            # Get actual parameter of last trade order
            market_order = self.get_buffered_completed_trades()
            fact_amount_first = 0
            fact_amount_second = 0
            for i, o in enumerate(market_order):
                if o.order_id == order.id:
                    fact_amount_first += market_order[i].amount
                    fact_amount_second += market_order[i].amount * market_order[i].price
            self.avg_rate = fact_amount_second / fact_amount_first
            if place_order_id in self.grid_orders_id:
                self.message_log('Grid order {} execute by market'.format(order.id))
                if FEE_IN_PAIR:
                    if self.cycle_buy:
                        fact_amount_first -= FEE_TAKER * fact_amount_first / 100
                    else:
                        fact_amount_second -= FEE_TAKER * fact_amount_second / 100
                # Calculate cycle sum trading for both currency
                self.sum_amount_first += fact_amount_first
                self.sum_amount_second += fact_amount_second
                try:
                    self.grid_orders_id.remove(place_order_id)
                except ValueError:
                    self.message_log('Can not remove waiting grid id from list', log_level=LogLevel.ERROR)
                self.message_log('Waiting order count is: {}'.format(len(self.grid_orders_id)))
                # Place take profit order
                self.place_profit_order(by_market=True)
            elif place_order_id == self.tp_wait_id:
                self.tp_wait_id = None
                self.tp_order_id = None
                if self.reverse_hold:
                    self.reverse_hold = False
                    self.cycle_time_reverse = None
                self.message_log('Take profit order {} execute by market'.format(order.id))
                if FEE_IN_PAIR:
                    if not self.cycle_buy:
                        fact_amount_first -= FEE_TAKER * fact_amount_first / 100
                    else:
                        fact_amount_second -= FEE_TAKER * fact_amount_second / 100
                # Take profit order execute by market, restart
                if self.cycle_buy:
                    self.cycle_buy_count += 1
                else:
                    self.cycle_sell_count += 1
                # Calculate cycle and total profit, refresh depo
                if self.cycle_buy:
                    self.profit_second = fact_amount_second - self.sum_amount_second
                    self.message_log('Cycle profit second {}'.format(self.profit_second))
                    self.deposit_second += self.profit_second
                    if not self.reverse:
                        # Take account profit only for non reverse cycle
                        self.sum_profit_second += self.profit_second
                else:
                    self.profit_first = fact_amount_first - self.sum_amount_first
                    self.message_log('Cycle profit first {}'.format(self.profit_first))
                    self.deposit_first += self.profit_first
                    if not self.reverse:
                        # Take account profit only for non reverse cycle
                        self.sum_profit_first += self.profit_first
                self.message_log('Restart after take profit execute by market', tlg=True)
                self.restart = True
                self.start()
            else:
                self.message_log('Did not have waiting order id for {}'.format(place_order_id), LogLevel.ERROR)
        else:
            if place_order_id in self.grid_orders_id:
                self.orders.append(order)
                if self.cycle_buy:
                    self.orders.sort(key=lambda x: x.price, reverse=True)
                else:
                    self.orders.sort(key=lambda x: x.price, reverse=False)
                try:
                    self.grid_orders_id.remove(place_order_id)
                except ValueError:
                    self.message_log('Can not remove waiting grid id from list', log_level=LogLevel.ERROR)
                self.message_log('Waiting order count is: {}'.format(len(self.grid_orders_id)))
                if not self.grid_orders_id:
                    if self.grid_save_flag:
                        self.grid_save_flag = False
                        self.message_log('Grid orders place successfully')
                    else:
                        self.last_shift_time = time.time()
                    if self.start_hold:
                        self.message_log('Release hold Start and place grid orders')
                        self.start_hold = False
                        self.start()
            elif place_order_id == self.tp_wait_id:
                self.tp_wait_id = None
                self.tp_order_id = order.id
                if self.tp_hold or self.tp_cancel:
                    self.cancel_order_id = self.tp_order_id
                    self.cancel_order(self.tp_order_id)
                else:
                    # Place last part of grid orders
                    self.grid_save_flag = True
                    for i in self.grid_save:
                        waiting_order_id = self.place_limit_order(i['buy_side'], i['amount'], i['price'])
                        self.grid_orders_id.append(waiting_order_id)
                    self.grid_save.clear()
            else:
                self.message_log('Did not have waiting order id for {}'.format(place_order_id), LogLevel.ERROR)

    def on_place_order_error_string(self, place_order_id: int, error: str) -> None:
        # FIXME Order placed in fact but MarketInterface returned null order!
        # Search orders on exchange and correct # self.get_buffered_open_orders()?
        if place_order_id in self.grid_orders_id:
            self.grid_orders_id.remove(place_order_id)
        else:
            self.tp_wait_id = None
        msg = 'On place order {} error {}'.format(place_order_id, error)
        self.message_log(msg, LogLevel.ERROR, tlg=True)
        # self.exit(ExitReason.ERROR, error)

    def on_cancel_order_success(self, order_id: int, canceled_order: Order) -> None:
        if any(i.id == order_id for i in self.orders):
            # Remove grid order with =id from cycle order list
            for i, o in enumerate(self.orders):
                if o.id == order_id:
                    del self.orders[i]
                    break
            self.start()
        elif order_id == self.cancel_order_id:
            self.cancel_order_id = None
            self.tp_order_id = None
            if self.tp_hold:
                self.tp_hold = False
                self.place_profit_order()
            if self.tp_cancel:
                # Reverse
                self.tp_cancel = False
                self.start()

    def on_cancel_order_error_string(self, order_id: int, error: str) -> None:
        msg = 'On cancel order {} error {}'.format(order_id, error)
        self.message_log(msg, LogLevel.ERROR, tlg=True)
        # FIXME Need additional check on exchange
        if any(i.id == order_id for i in self.orders):
            # Remove grid order with =id from cycle order list
            for i, o in enumerate(self.orders):
                if o.id == order_id:
                    del self.orders[i]
                    break
            self.start()
        elif order_id == self.cancel_order_id:
            self.cancel_order_id = None
            self.tp_order_id = None
            if self.tp_hold:
                self.tp_hold = False
                self.place_profit_order()
            if self.tp_cancel:
                # Reverse
                self.tp_cancel = False
                self.start()
