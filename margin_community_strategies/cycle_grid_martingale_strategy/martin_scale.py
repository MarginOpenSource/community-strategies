##################################################################
# Cycle grid martingale strategy
# Copyright © 2021 Jerry Fedorenko aka VM
# ver. 0.2b
# See readme.md for detail
# Communication with the author and support on
# https://discord.com/channels/600652551486177292/601329819371831296
##################################################################
"""
Ready for use basic strategy 'as is'.
Install all needed packages, see import section,
it must be installed into /margin-linux/resources/python/lib/python3.7/site-packages/
and 'save' strategy in margin should not return any error.

Set correct ID_EXCHANGE
Check and correct parameter at the top of script.
In margin set custom fee = 0%
Verify init print for correct depo amount
##################################################################
Additional function setup, depending from OS

Uncomment commented block marked as # Uncomment for * ...
and remove pass if necessary
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
- Try start it from terminal, if any error - fix it.
- If get_command_tlg.py start, check passed, stop it from any process manager.
- When strategy started, you can send stop command from Telegram.
  In Telegram bot select message from desired strategy and Reply with text message 'stop'
  When strategy ends current cycle it not run next, but stay holding for manual action from
  margin interface. Only 'stop' command implemented now.

* Balance data collection for external analytics
- no action needed
"""

##################################################################

import json
# import multiprocessing as mp  # Uncomment for * Telegram notification
# import platform  # Uncomment for * Telegram control
# import sqlite3  # Uncomment for * Balance data collection for external analytics
import statistics
# import subprocess as sp  # Uncomment for * Telegram control
import time
# from datetime import datetime  # Uncomment for * Balance data collection for external analytics

# import requests  # Uncomment for * Telegram notification
from margin_strategy_sdk import *

# import cfg  # Uncomment for * all additional function

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
ID_EXCHANGE = 0  # For collection of statistics
START_ON_BUY = True  # First cycle direction
AMOUNT_FIRST = 0.0  # Deposit for Sell cycle in first currency
USE_ALL_FIRST_FUND = True  # Use all available fund for first current
AMOUNT_SECOND = 500  # Deposit for Buy cycle in second currency
PRICE_SHIFT = 0.05  # No market shift price in % from current bid/ask price
PROFIT = 0.45  # 0.15 - 0.85
OVER_PRICE = 10  # 5-25% Max overlap price in one direction
ORDER_Q = 10  # Order quantity in one direction
GRID_MAX_COUNT = 5  # Max count for one moment place grid orders
MARTIN = 5  # 5-20, % increments volume of orders in the grid
FEE_IN_PAIR = True  # Fee pays in pair
FEE_MAKER = 0.10  # standard exchange Fee for maker
FEE_TAKER = 0.17  # standard exchange Fee for taker
SHIFT_GRID_THRESHOLD = 0.10  # % max price drift from 0 grid order before replace
SHIFT_GRID_DELAY = 15  # sec delay for shift grid action
ROUND_FLOAT_F = 10000000  # Floor round 0.00000 = 0.00x for first currency
ROUND_FLOAT_S = 10000  # Floor round 0.00000 = 0.00x for second currency
# For set_trade_condition
ADAPTIVE_TRADE_CONDITION = True
KB = 2  # Bollinger k for Buy cycle -> low price
KT = 2  # Bollinger k for Sell cycle -> high price
MIN_DIFF = 0.15  # % min price difference for one step, min over price = MIN_DIFF * ORDER_Q
#
MARTIN = (MARTIN + 100) / 100


def send_telegram(text: str) -> None:
    # Uncomment for * Telegram notification
    """
    url = cfg.url
    token = cfg.token
    channel_id = cfg.channel_id
    url += token
    method = url + '/sendMessage'
    requests.post(method, data={'chat_id': channel_id, 'text': text})
    """
    pass  # Comment or remove


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
        self.previous_funds = ''  # tmp save previous funds data
        self.take_profit_order_hold = {}  # Save unreleased take profit order
        self.tp_hold = False  # Flag for replace take profit order
        self.tp_cancel = False  # Cancel tp order after success place
        self.tlg_header = ''  # Header for Telegram message
        self.last_shift_time = None
        self.avg_rate = None  # Flow average rate for trading pair
        self.grid_hold = {}  # Save for later create grid orders
        self.start_hold = False  # Hold start if exist not accepted grid order(s)
        self.cancel_order_id = None  # Exist canceled not confirmed order
        self.over_price = OVER_PRICE  # Adaptive over price
        self.grid_save = []  # List of save grid orders for later place
        self.grid_save_flag = False  # Flag when place last part of grid orders
        self.part_amount_first = 0.0  # Amount of partially filled order
        self.part_amount_second = 0.0  # Amount of partially filled order
        self.part_place_tp = False  # When part fill grid order place tp if price go a way
        # Uncomment for * Telegram notification
        # self.py_path = cfg.py_path  # Path where .py module placed. Setup in cfg.py
        # self.db_path = cfg.margin_path  # Path where .db file placed. Setup in cfg.py
        self.command = None  # External command from Telegram

    def init(self) -> None:
        # print('Start Init section')
        self.command = None
        tcm = self.get_trading_capability_manager()
        self.f_currency = self.get_first_currency()
        self.s_currency = self.get_second_currency()
        self.tlg_header = '{}, {}/{}. '.format(EXCHANGE[ID_EXCHANGE], self.f_currency, self.s_currency)
        last_price = self.get_buffered_ticker().last_price
        # Init var for analytic
        # Uncomment for * Balance data collection for external analytics
        # self.connection_analytic = sqlite3.connect(self.db_path + 'funds_rate.db')
        # self.cursor_analytic = self.connection_analytic.cursor()
        if self.cycle_buy:
            if self.deposit_second > self.get_buffered_funds()[self.s_currency].available:
                print('Not enough second coin for Buy cycle!')
            first_order_vlm = self.deposit_second * 1 * (1 - MARTIN) / (1 - pow(MARTIN, ORDER_Q))
            first_order_vlm /= last_price
        else:
            if USE_ALL_FIRST_FUND:
                self.deposit_first = self.get_buffered_funds()[self.f_currency].available
            else:
                if self.deposit_first > self.get_buffered_funds()[self.f_currency].available:
                    print('Not enough first coin for Sell cycle!')
            first_order_vlm = self.deposit_first * 1 * (1 - MARTIN) / (1 - pow(MARTIN, ORDER_Q))
        if self.cycle_buy and first_order_vlm < tcm.get_min_buy_amount(last_price):
            print('Total deposit {} {} not enough for min amount for {} orders.'
                  .format(AMOUNT_SECOND, self.s_currency, ORDER_Q))
        elif not self.cycle_buy and first_order_vlm < tcm.get_min_sell_amount(last_price):
            print('Total deposit {} {} not enough for min amount for {} orders.'
                  .format(self.deposit_first, self.f_currency, ORDER_Q))

    def get_strategy_config(self) -> StrategyConfig:
        s = StrategyConfig()
        s.required_data_updates = {StrategyConfig.ORDER_BOOK,
                                   StrategyConfig.FUNDS}
        s.normalize_exchange_buy_amounts = True
        return s

    def save_strategy_state(self) -> Dict[str, str]:
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
        self.cycle_buy = bool(strategy_state.get('cycle_buy', START_ON_BUY))
        self.grid_orders_id = json.loads(strategy_state.get('grid_orders_id', []))
        # self.orders = json.loads(strategy_state.get('orders', []))
        # self.tp_order_id = strategy_state.get('tp_order_id', 0)
        self.sum_amount_first = float(strategy_state.get('sum_amount_first', 0.0))
        self.sum_amount_second = float(strategy_state.get('sum_amount_second', 0.0))
        self.deposit_first = float(strategy_state.get('deposit_first', 0.0))
        self.deposit_second = float(strategy_state.get('deposit_second', 0.0))
        self.sum_profit_first = float(strategy_state.get('sum_profit_first', 0.0))
        self.sum_profit_second = float(strategy_state.get('sum_profit_second', 0.0))
        self.cycle_buy_count = int(strategy_state.get('cycle_buy_count', 0))
        self.cycle_sell_count = int(strategy_state.get('cycle_sell_count', 0))

    def place_grid(self, buy_side: bool, depo: float):
        self.last_shift_time = None
        self.grid_save_flag = False
        tcm = self.get_trading_capability_manager()
        if buy_side:
            max_bid_price = self.get_buffered_order_book().bids[0].price
            base_price = max_bid_price - PRICE_SHIFT * max_bid_price / 100
        else:
            min_ask_price = self.get_buffered_order_book().asks[0].price
            base_price = min_ask_price + PRICE_SHIFT * min_ask_price / 100
        # TODO Add logarithm price option
        delta_price = (self.over_price * base_price) / (100 * (ORDER_Q - 1))
        funds = self.get_buffered_funds()
        if buy_side:
            fund = funds[self.s_currency].available
        else:
            fund = funds[self.f_currency].available
        if depo <= fund:
            self.grid_hold.clear()
            for i in range(ORDER_Q):
                if buy_side:
                    price = base_price - i * delta_price
                else:
                    price = base_price + i * delta_price
                price = tcm.round_price(price, RoundingType.ROUND)
                amount = depo * pow(MARTIN, i) * (1 - MARTIN) / (1 - pow(MARTIN, ORDER_Q))
                if buy_side:
                    amount /= price
                amount = tcm.round_amount(amount, RoundingType.FLOOR)
                assert (tcm.is_limit_order_valid(buy_side, amount, price))
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

    def place_profit_order(self, by_market=False):
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
            # Check funds available
            funds = self.get_buffered_funds()
            buy_side = not self.cycle_buy
            if buy_side and self.sum_amount_second > funds[self.s_currency].available:
                # Save take profit order and wait update balance
                self.take_profit_order_hold = {'buy_side': buy_side,
                                               'amount': self.sum_amount_second}
                print('Hold Buy take profit order, wait funding')
            elif not buy_side and self.sum_amount_first > funds[self.f_currency].available:
                # Save take profit order and wait update balance
                self.take_profit_order_hold = {'buy_side': buy_side,
                                               'amount': self.sum_amount_first}
                print('Hold Sell take profit order, wait funding')
            else:
                # Calculate take profit order
                tcm = self.get_trading_capability_manager()
                # Retreat of courses
                price = self.sum_amount_second / self.sum_amount_first
                if not FEE_IN_PAIR:
                    if by_market:
                        fee = FEE_TAKER
                    else:
                        fee = FEE_MAKER
                    if buy_side:
                        price -= fee * price / 100
                    else:
                        price += fee * price / 100
                if self.cycle_buy:
                    price += (FEE_MAKER + PROFIT) * price / 100
                    price = tcm.round_price(price, RoundingType.CEIL)
                    amount = self.sum_amount_first
                else:
                    price -= (FEE_MAKER + PROFIT) * price / 100
                    price = tcm.round_price(price, RoundingType.FLOOR)
                    amount = self.sum_amount_second / price
                amount = tcm.round_amount(amount, RoundingType.FLOOR)
                # Create take profit order
                # TODO Before place order check for last_price
                assert (tcm.is_limit_order_valid(buy_side, amount, price))
                self.message_log('Create {} take profit order, vlm:{}, price:{}'
                                 .format('Buy' if buy_side else 'Sell', amount, price))
                self.tp_wait_id = self.place_limit_order(buy_side, amount, price)

    def start(self) -> None:
        self.shift_grid_threshold = None
        if self.grid_save:
            self.grid_save.clear()
        if self.grid_orders_id:
            # Exist not accepted grid order(s), wait msg from exchange
            self.start_hold = True
        elif self.orders:
            # Sequential removal orders from grid
            self.cancel_order(self.orders[0].id)
        else:
            self.avg_rate = self.get_buffered_ticker().last_price
            self.message_log('Complete {} buy cycle and {} sell cycle.\n'
                             'For all cycles profit:\n'
                             'First: {}\n'
                             'Second: {}\n'
                             'Summary: {}'
                             .format(self.cycle_buy_count, self.cycle_sell_count,
                                     self.sum_profit_first, self.sum_profit_second,
                                     self.sum_profit_first * self.avg_rate + self.sum_profit_second), tlg=True)
            # TODO Save profit data for statistic
            # Check and start Telegram control
            # Uncomment for * Telegram control
            '''
            if platform.system() == 'Linux':
                try:
                    # Check if get_command_tlg already started. Can be edit for other OS then Linux!
                    sp.check_output('ps -eo cmd| grep -v grep | grep get_command_tlg', shell=True)
                    print('Telegram control service already started')
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
            '''
            if self.command == 'stop':
                self.message_log('Stop, waiting manual action', tlg=True)
            else:
                # Init variable
                self.sum_amount_first = 0
                self.sum_amount_second = 0
                self.part_amount_first = 0
                self.part_amount_second = 0
                if self.cycle_buy:
                    amount = self.deposit_second
                    amount = int(amount * ROUND_FLOAT_S) / ROUND_FLOAT_S
                    self.message_log('Start Buy cycle with {} {} depo'
                                     .format(amount, self.s_currency), tlg=True)
                else:
                    if USE_ALL_FIRST_FUND:
                        fund = self.get_buffered_funds()[self.f_currency].available
                        if fund > self.deposit_first:
                            self.deposit_first = fund
                            self.message_log('Use all available fund for first currency')
                    amount = self.deposit_first
                    amount = int(amount * ROUND_FLOAT_F) / ROUND_FLOAT_F
                    self.message_log('Start Sell cycle with {} {} depo'
                                     .format(amount, self.f_currency), tlg=True)
                if ADAPTIVE_TRADE_CONDITION:
                    try:
                        self.set_trade_conditions()
                    except Exception as ex:
                        self.message_log('Do not set over price by {}'.format(ex), log_level=LogLevel.ERROR)
                self.place_grid(self.cycle_buy, amount)
            # print('End Start section')

    def on_new_order_book(self, order_book: OrderBook) -> None:
        if self.shift_grid_threshold and self.last_shift_time and not self.part_place_tp:
            if time.time() - self.last_shift_time > SHIFT_GRID_DELAY:
                if ((self.cycle_buy and order_book.bids[0].price >= self.shift_grid_threshold) or
                        (not self.cycle_buy and order_book.asks[0].price <= self.shift_grid_threshold)):
                    self.message_log('Shift grid')
                    self.start()
        elif self.part_place_tp:
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
                self.take_profit_order_hold.clear()
                self.place_profit_order()
            else:
                self.message_log('Exist unreleased take profit order')
        if self.grid_hold:
            if self.grid_hold['buy_side']:
                available_fund = funds[self.s_currency].available
            else:
                available_fund = funds[self.f_currency].available
            if available_fund >= self.grid_hold['depo']:
                self.place_grid(self.grid_hold['buy_side'],
                                self.grid_hold['depo'])
            else:
                self.message_log('Exist unreleased grid orders')
        # Save funds update to .db for external analytics
        # Uncomment for * Balance data collection for external analytics
        '''
        f_funds = funds[self.f_currency].total_for_currency
        s_funds = funds[self.s_currency].total_for_currency
        funds = str(f_funds) + str(s_funds)
        if funds != self.previous_funds:
            # print('Save funds update to .db')
            # start_time = time.time()
            try:
                self.cursor_analytic.execute("insert into t_funds values(?,?,?,?,?,?,?,?)",
                                             (ID_EXCHANGE, None, self.f_currency, self.s_currency, f_funds, s_funds,
                                              self.avg_rate, datetime.utcnow()))
                self.connection_analytic.commit()
            except Exception as exception:
                self.message_log('Error write funds to .db' + str(exception), LogLevel.ERROR)
            # end_time = time.time()
            # diff = end_time - start_time
            # print('Execution time is {}'.format(diff))
            self.previous_funds = funds
        '''

    def stop(self) -> None:
        # Uncomment for * all .db operation
        # self.connection_analytic.close()
        pass  # Comment or remove

    def message_log(self, msg: str, log_level=LogLevel.INFO, tlg=False) -> None:
        print(msg)
        write_log(log_level, msg)
        msg = self.tlg_header + msg
        if tlg:
            # Uncomment for * Telegram notification
            # mp.Process(target=send_telegram, args=(msg,)).start()
            pass  # Comment or remove

    def set_trade_conditions(self) -> None:
        # Bottom BB as sma-kb*stdev
        # Top BB as as sma+kt*stdev
        # For Buy cycle over_price as 100*(Ticker.last_price - bbb) / Ticker.last_price
        # For Sell cycle over_price as 100*(tbb - Ticker.last_price) / Ticker.last_price
        candle_close = []
        candle = self.get_buffered_recent_candles(candle_size_in_minutes=60, number_of_candles=20)
        for i in candle:
            candle_close.append(i.close)
        sma = statistics.mean(candle_close)
        st_dev = statistics.stdev(candle_close)
        last_price = self.get_buffered_ticker().last_price
        # print('sma={}, st_dev={}, last price={}'.format(sma, st_dev, last_price))
        tbb = sma + KT * st_dev
        bbb = sma - KT * st_dev
        # print('tbb={}, bbb={}'.format(tbb, bbb))
        if self.cycle_buy:
            over_price = 100*(last_price - bbb) / last_price
        else:
            over_price = 100 * (tbb - last_price) / last_price
        over_price = round(over_price, 2)
        # print('over_price={}'.format(over_price))
        if over_price < MIN_DIFF * ORDER_Q:
            self.over_price = MIN_DIFF * ORDER_Q
        elif over_price > OVER_PRICE:
            self.over_price = OVER_PRICE
        else:
            self.over_price = over_price
        self.message_log('For {} cycle set {}% over price'.format('Buy' if self.cycle_buy else 'Sell',
                                                                  self.over_price), tlg=True)

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
                    # Remove grid order with =id from cycle order list
                    for i, o in enumerate(self.orders):
                        if o.id == update.original_order.id:
                            del self.orders[i]
                            break
                    if not self.orders and not self.grid_save:
                        # Ended grid order, calculate depo and Reverse
                        if self.cycle_buy:
                            self.deposit_first = self.sum_amount_first
                        else:
                            self.deposit_second = self.sum_amount_second
                        # Reverse
                        self.cycle_buy = not self.cycle_buy
                        self.message_log('Reverse', tlg=True)
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
                            self.start()
                    else:
                        self.place_profit_order()
                elif self.tp_order_id == update.original_order.id:
                    # Filled take profit order, restart
                    self.tp_order_id = None
                    if self.cycle_buy:
                        self.cycle_buy_count += 1
                    else:
                        self.cycle_sell_count += 1
                    self.message_log('Restart', tlg=True)
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
                        profit_second = trade_amount_second - self.sum_amount_second
                        self.message_log('Cycle profit second {}'.format(profit_second))
                        self.sum_profit_second += profit_second
                        self.deposit_second += profit_second
                    else:
                        profit_first = trade_amount_first - self.sum_amount_first
                        self.message_log('Cycle profit first {}'.format(profit_first))
                        self.sum_profit_first += profit_first
                        self.deposit_first += profit_first
                    # Restart
                    self.start()
                else:
                    self.message_log('There is a partially executed order. Waiting for filling or adjust yourself.',
                                     tlg=True)
            elif update.status == OrderUpdate.PARTIALLY_FILLED:
                self.shift_grid_threshold = None
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
        if place_order_id in self.grid_orders_id:
            if order.remaining_amount == 0.0:
                self.shift_grid_threshold = None
                # Get actual parameter of last trade order
                market_order = self.get_buffered_completed_trades()
                fact_amount_first = 0
                fact_amount_second = 0
                for i, o in enumerate(market_order):
                    if o.order_id == order.id:
                        fact_amount_first += market_order[i].amount
                        # Retreat of courses
                        fact_amount_second += market_order[i].amount * market_order[i].price
                if FEE_IN_PAIR:
                    if self.cycle_buy:
                        fact_amount_first -= FEE_TAKER * fact_amount_first / 100
                    else:
                        fact_amount_second -= FEE_TAKER * fact_amount_second / 100
                # Calculate cycle sum trading for both currency
                self.sum_amount_first += fact_amount_first
                self.sum_amount_second += fact_amount_second
                # Place take profit order
                self.place_profit_order(by_market=True)
            else:
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
                if not self.grid_save_flag:
                    self.last_shift_time = time.time()
                    self.message_log('Grid orders place successfully')
                if self.start_hold:
                    self.message_log('Release hold Start and place grid orders')
                    self.start_hold = False
                    self.start()
        elif place_order_id == self.tp_wait_id:
            # TODO Check if take profit order execute by market
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
