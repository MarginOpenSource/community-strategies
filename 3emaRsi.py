from margin_strategy_sdk import *

##################################################################
# 3 Ema & Rsi Buy/Sell Bot
# This strategy uses 3 emas and Rsi to determine buy/sell trades.
# Version 3.67 - Ema/Rsi bot
# Created 2020 by Maritimer
# Disclaimer - By using this source code you acknowledge that you are
# solely responsible for your losses
##################################################################

# Overrides
class Strategy(StrategyBase):
    def __init__(self) -> None:
        super(Strategy, self).__init__()
        self.strategy_state = dict()

    ############# USER DEFINED SETTINGS ##########################################
    # Generic strategy settings
    asset_amount = 0.005  # Amount of asset to buy per trade cycle.
    buy_trade = True  # Start strategy on buy, False starts in Sell mode.
    stop_strat = False  # stop strat after any trade.
    trade_immediately = False  # Buy/sell immediately, does not wait for signals.
    sell_on_profit = True  # Sell with guaranteed profit only.
    sell_on_profit_gain = 0.30  # Only sells above this profit threshold (1 = 1%).
    sell_immediately_profit = False  # sell immediately once price crosses profit price.
    buy_on_profit = False  # Trigger minimum effective gain after a sell.
    buy_on_profit_gain = 1  # Minimum effective gain after sell (1 = 1%).
    buy_on_profit_immediately = False  # Buy immediately once price goes below minimum gain.
    stop_loss = True  # Enable/disable stop loss.
    exit_on_stop_loss = True  # Stop the strat if the stop loss is triggered.
    stop_loss_setting = 1  # Stop Loss, The % below the last buy price (1 = 1%).

    ### OTHER SETTINGS ###
    candle_period = 60  # Candle period in minutes (1 hour = 60)
    candle_size = 125  # number of candles to start the strat.
    ema_short = 5  # ema short candlesize.
    ema_long = 13  # ema long candlesize.
    ema_trend = 34  # ema trend candlesize.
    ema_on = True  # use ema indicator.
    ema_trend_on = True  # use trend indicator.
    rsi = 14  # rsi candlesize.
    rsi_buy = 50  # rsi buy trigger - highest rsi to buy.
    rsi_sell = 50  # rsi sell trigger - lowest rsi to sell.
    rsi_overbought = 80  # rsi overbought.
    rsi_oversold = 20  # rsi oversold.
    rsi_on = True  # use rsi indicator.
    ################################################################################
    ##            DO NOT MAKE ANY MODIFICATIONS BELOW THIS LINE!!                 ##
    ################################################################################
    # Strategy variables
    last_buy_price = 0  # last buy price
    last_sell_price = 0  # last sell price
    last_candle_vwap = 0  # last vwap price

    # Output settings
    OUTPUT_DP = 2  # The number of decimal places for outputs figures

    # Strategy settings
    sell_price = 0  # Used for calculating trailing sell
    buy_price = 0  # Used for calculating trailing buy

    TRAILING_SELL_SETTING = 0.05  # Trailing sell setting (1 = 1%)
    TRAILING_BUY_SETTING = 0.08  # Trailing buy setting (1 = 1%)

    sl_price = 0  # The calculated price that invokes the stop loss
    min_gain_price = 0  # The calculated price that invokes min. eff. gain.
    price_trigger_counter = 0
    mp_price = 0
    prev_ticker_price = 0
    profit_price_reached = False
    trade_trigger = False
    order_trigger = 0

    last_candle_open = 0  # current candle
    current_candle_low_price = 0
    current_candle_high_price = 0  # temporary until margin candle def is fixed

    # ema variables
    emashort_price = 0
    emalong_price = 0
    ematrend_price = 0
    prev_emashort_price = 0
    prev_emalong_price = 0
    prev_ematrend_price = 0
    ema_count = 0
    prev_ema_long_candle = 0
    ema_long_switch = True

    # rsi variables
    rsi_plus = 0
    rsi_minus = 0
    rsi_avg_plus = 0
    rsi_avg_minus = 0
    rsi_gain = 0
    rsi_loss = 0
    rsi_rs = 0
    rsi_result = 0
    rsi_count = 0
    prev_rsi_result = 0
    prev_rsi_gain = 0
    prev_rsi_loss = 0


    # Override default strategy config
    def init(self) -> None:
        print("Strategy init function!")
        assert self.ema_short < self.ema_long
        assert self.ema_long < self.ema_trend
        assert self.candle_size > self.ema_trend
        if self.rsi_on is False and self.ema_on is False:
            raise ValueError("** Both rsi_on and ema_on flags cant be False **")
        # assert self.sell_immediately_profit and self.sell_on_profit is False

    def get_strategy_config(self) -> StrategyConfig:
        s = StrategyConfig()
        s.required_data_updates = {StrategyConfig.TICKER}
        s.normalize_exchange_buy_amounts = True
        return s

    def start(self) -> None:
        print("Strategy start function!")
        print("Version 3.67 - 3emaRsi")

    def save_strategy_state(self) -> Dict[str, str]:
        return self.strategy_state

    def restore_strategy_state(self, strategy_state: Dict[str, str]) -> None:
        self.strategy_state = strategy_state

    # def stop(self) -> None:
    #   print("Strategy stop function!")

    def suspend(self) -> None:
        print("Strategy suspend called")

    def unsuspend(self) -> None:
        print("Strategy unsuspend called")
        self.last_candle_open = 0  # force new full ema calculation

    def on_place_order_success(self, place_order_id: int, order: Order) -> None:
        print("#########################################")
        print("*** [{}] order executed at: {}, amount = {} {} ***".format("BUY" if order.buy else "SELL",
                                                                          round(order.price, 6), order.amount,
                                                                          self.get_first_currency()))
        if order.buy:
            self.last_buy_price = order.price
        self.order_trigger = 1
        # else
        #    self.order_trigger = 0
        #    #self.last_buy_price = 0

    def on_place_order_error_string(self: StrategyBase, place_order_id: int, error: str) -> None:
        print("XXX Order could not be complete, aborting strategy... XXX")
        self.exit(ExitReason.ERROR, error)

    def on_new_ticker(self, ticker: Ticker) -> None:
        # get current price
        tlp = ticker.last_price

        if self.prev_ticker_price != tlp:
            self.candle_close = []
            self.candle_high = []
            self.candle_low = []
            self.candle_vwap = []
            self.candle_open = []
            self.ema_candle = []
            candles: List[Candle] = self.get_buffered_recent_candles(self.candle_period, 2 * self.candle_size, include_current_building_candle=True)
            for candle in candles:
                self.candle_open.append(candle.open)
                self.candle_close.append(candle.close)
                self.candle_high.append(candle.high)
                self.candle_low.append(candle.low)
                self.candle_vwap.append(candle.vwap)

            if self.last_candle_open != self.candle_open[-1]:  # new candle start
                self.last_candle_open = self.candle_open[-1]
                self.prev_emashort_price = self.emashort_price
                self.prev_ematrend_price = self.ematrend_price
                self.prev_rsi_result = self.rsi_result
                self.prev_rsi_gain = self.rsi_gain
                self.prev_rsi_loss = self.rsi_loss

            else:  # for Rsi need to reinstate gain/loss from up to previous candle.
                self.rsi_gain = self.prev_rsi_gain
                self.rsi_loss = self.prev_rsi_loss

            # if buy mode use .low candle otherwise use .High candle info
            if self.buy_trade:
                self.ema_candle = self.candle_low

            else:
                self.ema_candle = self.candle_high

            if self.ema_long_switch:  # ema_long candle switch between low/high triggered
                self.ema_long_switch = False
                self.prev_emalong_price = 0  # start a new fresh ema long
                print("ema_long_switch condition met")

            if self.prev_emashort_price == 0:
                self.emashort_price = self.ema(self.candle_close, self.ema_short, 0, True)
            else:
                self.emashort_price = self.ema(self.candle_close, self.ema_short, self.prev_emashort_price, False)

            if self.prev_emalong_price == 0:
                self.emalong_price = self.ema(self.ema_candle, self.ema_long, 0, True)
                self.prev_ema_long_candle = self.ema_candle[-1]
                self.prev_emalong_price = self.emalong_price
                self.prev_emalong_price = 0
            else:
                if self.prev_ema_long_candle != self.ema_candle[-1]:
                    self.prev_ema_long_candle = self.ema_candle[-1]
                    self.emalong_price = self.ema(self.ema_candle, self.ema_long, self.prev_emalong_price, False)
                    self.prev_emalong_price = self.emalong_price
                    self.prev_emalong_price = 0

            if self.prev_ematrend_price == 0:
                self.ematrend_price = self.ema(self.candle_close, self.ema_trend, 0, True)
            else:
                self.ematrend_price = self.ema(self.candle_close, self.ema_trend, self.prev_ematrend_price, False)

            # calculate rsi
            if self.rsi_result == 0:  # initiate rsi_result
                self.rsi_result, self.rsi_gain, self.rsi_loss = self.calculate_rsi(self.candle_close, self.rsi * 3 + 1,
                                                                                   self.rsi_gain, self.rsi_loss, 0,
                                                                                   True)
                self.prev_rsi_gain = self.rsi_gain
                self.prev_rsi_loss = self.rsi_loss
            else:
                self.rsi_result, self.rsi_gain, self.rsi_loss = self.calculate_rsi(self.candle_close, self.rsi,
                                                                                   self.rsi_gain, self.rsi_loss,
                                                                                   self.candle_close[-2], False)

            print("S {:.9f} :L {:.9f} :T {:.9f} :R {:.2f}".format(self.emashort_price, self.emalong_price,
                                                                    self.ematrend_price, self.rsi_result))

        # let's trade
        if self.buy_trade:  # Buy
            # check for buy trigger
            if self.order_trigger == 0:  # Waiting for buy trigger
                if self.prev_ticker_price != tlp:
                    print("Waiting for buy signal: {:.9f}".format(tlp))

                # buy triggers
                self.trade_trigger = False
                if self.rsi_oversold < self.rsi_result < self.rsi_buy if self.rsi_on else True:
                    if self.prev_rsi_result < self.rsi_result if self.rsi_on else True:
                        if self.emalong_price < self.prev_emalong_price if self.ema_on else True:
                            if self.prev_emashort_price < self.emashort_price if self.ema_on else True:
                                if self.emashort_price > self.emalong_price if self.ema_on else True:
                                    if self.prev_emashort_price < self.prev_emalong_price if self.ema_on else True:
                                        if tlp <= self.min_gain_price if self.buy_on_profit is True else True:
                                            self.trade_trigger = True

                if tlp > self.ematrend_price and self.ema_trend_on: self.trade_trigger = False  # dont buy if price higher ematrend
                if self.ematrend_price == 0 and self.ema_trend_on: self.trade_trigger = False  # dont want to buy without a trend

                if self.buy_on_profit is True and tlp <= self.min_gain_price:
                    if self.buy_on_profit_immediately is True:
                        self.trade_trigger = True


                if self.trade_immediately: self.trade_trigger = True  # buy immediately

                # buy trigger activated
                if self.trade_trigger:
                    self.place_market_order(True, self.asset_amount)
                    self.order_trigger = 2

            # order was completed
            if self.order_trigger == 1:
                if self.sell_on_profit is True:
                    self.mp_price = self.last_buy_price + (self.last_buy_price * (self.sell_on_profit_gain / 100))
                    print("** Setting min profit price to: {:.9f} **".format(self.mp_price))

                # set stop loss
                if self.stop_loss is True:
                    self.sl_price = self.last_buy_price - (self.last_buy_price * (self.stop_loss_setting / 100))
                    print("** Setting stop loss to: {:.9f} **".format(self.sl_price))

                if self.trade_immediately is True:
                    self.trade_immediately = False
                    print("** trade_immediately has been turned off.")
                print("###########################################")

                self.buy_trade = False
                self.profit_price_reached = False
                self.order_trigger = 0
                self.ema_long_switch = True

                # Stop Strat after buy
                if self.stop_strat:
                    super().exit(ExitReason.FINISHED_SUCCESSFULLY, 'Exiting on Buy.')

        else:  # sell
            if self.order_trigger == 0:
                # strat started in Sell mode
                if self.last_buy_price == 0:
                    print("###########################################")
                    # check minimum gain
                    if self.mp_price == 0 and self.sell_on_profit is True:
                        self.mp_price = tlp + (
                                    tlp * (self.sell_on_profit_gain / 100))  # calculate profit from starting price
                        print("** Setting min sell price to: {:.9f} **".format(self.mp_price))
                    else:
                        print("** Minimum sell price disabled **")

                    if self.rsi_result == 0:
                        self.rsi_result = 100

                        # set stop loss
                    if self.stop_loss is True:
                        self.sl_price = tlp - (tlp * (self.stop_loss_setting / 100))
                        print("** Setting stop loss to: {:.9f} **".format(self.sl_price))
                    else:
                        print("** Stop loss disabled **")

                    print("###########################################")
                    self.last_buy_price = tlp

                if self.prev_ticker_price != tlp:
                    print("Waiting for Sell signal: {:.9f} **".format(tlp))

                # check stop loss trigger
                if tlp < self.sl_price and self.stop_loss:
                    if self.buy_trade is False:
                        self.place_market_order(False, self.asset_amount)
                        print("**** Stop loss triggered ****")
                        self.sl_price = 0  # reset stop loss price
                        self.sell_price = 0  # reset trailing sell price
                        self.buy_trade = True
                        self.order_trigger = 1

                    if self.exit_on_stop_loss is True:
                        super().exit(ExitReason.FINISHED_SUCCESSFULLY, 'Exiting on stop loss trigger.')

                if self.prev_ticker_price != tlp:  # this condition is used just for the print function
                    if self.mp_price <= tlp and self.sell_on_profit is True and self.profit_price_reached is False:
                        self.profit_price_reached = True
                        print("** Profit price {:.9f} reached at: {:.9f} **".format(self.mp_price, tlp))
                    else:
                        self.profit_price_reached = False

                # sell triggers
                self.trade_trigger = False
                if self.buy_trade is False:
                    if self.mp_price <= tlp:  # price is higher than minimum profit price
                        if self.rsi_sell < self.rsi_result < self.rsi_overbought if self.rsi_on else True:
                            if self.prev_rsi_result > self.rsi_result if self.rsi_on else True:
                                if self.emalong_price > self.prev_emalong_price if self.ema_on else True:
                                    if self.prev_emashort_price > self.emashort_price if self.ema_on else True:
                                        if self.emashort_price < self.emalong_price if self.ema_on else True:
                                            if self.prev_emashort_price > self.prev_emalong_price if self.ema_on else True:
                                                self.trade_trigger = True

                    if tlp < self.ematrend_price and self.ema_trend_on: self.trade_trigger = False
                    if self.sell_immediately_profit is True and tlp >= self.mp_price: self.trade_trigger = True  # if in profit sell immediately
                    if self.trade_immediately: self.trade_trigger = True  # override trigger signals

                    if self.trade_trigger is True:
                        self.place_market_order(False, self.asset_amount)
                        self.order_trigger = 2

            if self.order_trigger == 1:
                self.last_sell_price = ticker.last_price
                # self.last_sell_price = order.price

                # Reset trailing sell settings
                self.sell_price = 0
                self.order_trigger = 0
                self.buy_trade = True
                self.ema_long_switch = True
                if self.buy_on_profit is True:
                    self.min_gain_price = tlp - (tlp * (self.buy_on_profit_gain / 100))
                    print("** Setting Min. Eff. Gain to : {:.9f} **".format(self.min_gain_price))
                else:
                    print("** Min. Eff. Gain is disabled **")

                if self.trade_immediately is True:
                    self.trade_immediately = False
                    print("** trade_immediately has been turned off.")
                print("#########################################")
                # Should the strat stop or continue
                if self.stop_strat:
                    super().exit(ExitReason.FINISHED_SUCCESSFULLY, 'Exiting on Sell.')

        # waiting for order to complete
        if self.order_trigger == 2:
            print("** Waiting for order to complete. **")
        self.prev_ticker_price = ticker.last_price

    def sma(self, candles, candle_size):
        # Calculates Simple Moving Average
        if len(candles) < candle_size:
            return None
        return sum(candles[-candle_size:]) / float(candle_size)

    def ema(self, candles, candle_size, previous_ema, first_run):
        # calculate ema
        if len(candles) * 2 < candle_size + 1:
            raise ValueError("ema - data is too short")
        c = 2.0 / float(candle_size + 1)
        if first_run:
            current_ema = self.sma(candles[-candle_size * 2:-candle_size], candle_size)
            for value in candles[-candle_size:]:
                current_ema = c * (value - current_ema) + current_ema

        else:

            # print("Size {:.9f}".format(candle_size))
            # for value in candles[-candle_size:]:
            # if candle_size == 10 : print("candles {:.9f}".format(value))

            # current_ema = self.sma(candles[-candle_size:], candle_size)

            # if candle_size== 10: print("averageema {:.9f}".format(current_ema))
            current_ema = c * (candles[-1] - previous_ema) + previous_ema
            # current_ema = c * (current_price - previous_ema) + previous_ema

        return current_ema

    def calculate_rsi(self, symbol, n, avg_up, avg_down, rs_previous_price, first_run):
        # calculate rsi
        # print("rsiCalled")
        current_price = 0
        previous_price = 0
        rs_avg_up = 0
        rs_avg_down = 0
        if first_run:  # first run
            # print("firstrun")
            avg_down = 0
            avg_up = 0
            length = len(symbol) - 1

            if length < n + 1:
                raise ValueError("rsi - data is too short")

            x = n
            # print("data {:.9f} - {:.9f}".format(x+1,symbol[-x-1]))
            while x > 0:
                previous_price = symbol[-x - 1]
                current_price = symbol[-x]
                # print("data {:.9f} - {:.9f}".format(x,current_price))
                if current_price > previous_price:
                    rs_avg_up += current_price - previous_price
                else:
                    rs_avg_down += abs(current_price - previous_price)
                # print("avgup {:.9f} - avgdown {:.9f}".format(rs_avg_up,rs_avg_down))
                x -= 1

            # Calculate average gain and loss
            if rs_avg_up != 0:
                avg_up = rs_avg_up / float(n)
            if rs_avg_down != 0:
                avg_down = rs_avg_down / float(n)

        else:  # after first run
            # print("secondrun")
            # previous_price = symbol[-2]
            current_price = symbol[-1]
            # current_price = rs_current_price
            # print("data {:.9f} - {:.9f}".format(rs_previous_price,current_price))
            if current_price > rs_previous_price:
                rs_avg_up = current_price - rs_previous_price
            else:
                rs_avg_down = abs(current_price - rs_previous_price)

            avg_up = ((avg_up * (n - 1)) + rs_avg_up) / float(n)
            avg_down = ((avg_down * (n - 1)) + rs_avg_down) / float(n)

        # Calculate relative strength
        if avg_down == 0:
            rsi = 100
        else:
            rs = avg_up / float(avg_down)
            # Calculate rsi
            # print("avg {:.9f} - {:.9f}".format(avg_up,avg_down))
            rsi = 100 - (100 / (1 + rs))

        # print(rsi)
        return rsi, avg_up, avg_down
