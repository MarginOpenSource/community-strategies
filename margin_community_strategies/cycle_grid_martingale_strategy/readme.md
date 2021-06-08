# Cyclic grid strategy based on martingale


## The motto of the project

**_Started and forgot_**

Regardless of exchange overloads, network connection lost, hardware fault.

## Reference

[Trade idea](#trade-idea)

[Functionality](#functionality)

[How it's work](#how-its-work)

[Planned](#planned)

[Tested](#tested)

[NOT Tested](#not-tested)

[Known issue](#known-issue)

[Target](#target)

Communication with the author and support in [margin group on Discord](https://discord.com/channels/600652551486177292/601329819371831296)

## Trade idea
Create a grid of increasing volume orders and when they perform
creation of one take profit order in the opposite direction.

Its volume is equal to the sum of the executed grid orders,
and the price compensates the fee and provides the specified profit.

What is the chip? After each grid order executed, the price of the take profit order
approaches the price of the grid, which requires less bounce to perform it.

If all grid orders filled, then reverse and start the cycle in another direction.

This allows you to increase the initial deposit using price fluctuations in any trend.

In the cycle to sell, the profit accumulates in the first currency.
In the cycle to buy, the profit accumulates in the second coin.

## Functionality
* Create grid and take profit orders
* Logarithm price option for grid orders (customizable)
* Reverse algo if all grid orders are filling
* Calculation of separate MAKER and TAKER fee
* Shift grid orders (customizable) if the price is go way (before take profit placed) 
* Fractional creation of grid for increase productivity (customizable)
* Adaptive overlap price for grid on current market conditions (customizable)
* Save funding change, cycle parameter and result in sqlite3 .db for external analytics (not Windows ver.)
* Telegram notification
* External control from Telegram bot (now **stop** command realised)

## How it's work
_Setup all mentioned parameter at the top of martin_scale.py_  
### Place grid
The main parameters for the strategy are grid parameters. Specify the trade direction for the first cycle.
If START_ON_BUY = True, a grid of buy orders will be placed and take profit will be for sale.

Specify the deposit size for the first cycle in the desired currency, and the number of grid orders.
These are related parameters, there is a limit on the minimum size of the order,
so a many orders if the deposit is insufficient will not pass the verification during initialization.

The size of the order in the grid calculated according to the law of geometric progression,
while the MARTIN parameter is a coefficient of progression.
The first order, the price of which is closest to the current one is the smallest in volume.

To avoid the execution of the first order "by market," its price set with a slight offset,
which is determined by the parameter PRICE_SHIFT.


#### Adaptive overlap price for grid
The range of prices that overlaps the grid of orders affects profitability directly 
and must correspond to market conditions. If it is too wide, the cycle time will be too long,
and most of the deposit will not be involved in turnover. With a small overlap, the entire order
grid will be executed in a short time, and the algorithm will be reversed,
while the profit on the cycle not fixed.

The overlap range can be fixed. Then it is defined by OVER_PRICE = xx and ADAPTIVE_TRADE_CONDITION = False.

For automatic market adjustment, ADAPTIVE_TRADE_CONDITION = True. In this case, the instant value
of the Bollinger Band on 20 * 1 hour candles used to calculate the overlap range. The maximum and minimum
values are limited by the parameters OVER_PRICE and MIN_DIFF * ORDER_Q, respectively.

For fine-tuning separately for Buy and Sell cycles there are KB and KT parameters. By default, value
2.0 is used to calculate Bollinger curves.

The over price value updated before the start of the new cycle.

#### Fractional creation of grid
For successful trading, the speed of the bot response to price fluctuations is important.
When testing on Bitfinex, I noticed that when placed a group of orders,
the first 5 are placed quickly, and the remaining ones with a significant delay. Also, the more orders,
the longer it takes to shift the grid.

Therefore, I added the parameter GRID_MAX_COUNT, which specifies the number of initial orders to be placed.
Then, two options performed, one of the placed grid orders executed, and after successful creation
of the take profit order, the missing grid orders added, or the grid shift function triggered.

#### Shift grid orders
It happens that when place a grid, the price goes in the opposite direction. There is no point
in waiting in this case, we need to move the grid after the price.
For this there are SHIFT_GRID_THRESHOLD and SHIFT_GRID_DELAY. Configure them or leave the default values.

#### Logarithm price option
You can increase the share of the deposit in turnover when calculating the price for grid orders using not a linear,
but a logarithmic distribution. The density of orders near the current price will be higher,
which increases the likelihood of their execution.

Use LINEAR_GRID_K parameter and see 'Model of logarithmic grid.ods' for detail.

#### Reverse
It happens that all grid orders completed. Then we believe that we successfully bought the asset,
turn over the algorithm and start trading the other way. The entire amount of currency purchased
becomes a deposit for the next cycle.

### Place take profit
As the grid orders executed, the volume of the take profit order sums up their volume,
price averaged and increased to override the fees and earn the specified profit.

Do not set PROFIT too large. This reduces the probability of executing a take profit order
with small price fluctuations. I settled on a value of about 0.5%

#### Restart
When take profit order executed the cycle results recorded, the deposit increased by the cycle profit,
and bot restarted.

### Fee options
To correctly count fees for MAKER and TAKER, you must set the custom fee level = 0.0% in
the margin settings and set the FEE_MAKER and FEE_TAKER parameters.

For a third currency fee, such as BNB on Binance, set FEE_IN_PAIR = False

### Telegram notification
Basic information about the state of the bot, for example, about the start and results of the cycle,
can be sent to Telegram bot.

+ Create Telegram bot
+ Get token and channel_id for your bot
+ Specify this data into cfg.py

### Telegram control
To stop the bot for maintenance or in other cases, it is necessary to send the bot a command
to complete the cycle and stop.

+ Check the owner and run permission for get_command_tlg.py
+ Try start it from terminal, if any error - fix it.
+ If get_command_tlg.py start, check passed, stop it from any process manager.
+ When strategy started, you can send stop command from Telegram.
  In Telegram bot select message from desired strategy and Reply with text message 'stop'
  When strategy ends current cycle it not run next, but stay holding for manual action from
  margin interface. Only 'stop' command implemented now.

### Save data for external analytics
All data collected into funds_rate.db
It Sqlite3 db with very simple structure, in table t_funds each row is the result of one
cycle with parameters and result.

You can connect to funds_rate.db from Excel, for example, via odbc and process them as you wish.

Cycle time, yield, funds, correlation with cycle parameters,
all this for all pairs and exchanges where this bot launched.

## Planned
* Get stability in pump/dump situation (it's real)
* Full auto recovery after any reason crash, restart etc.
* Adaptive PROFIT param for current trade conditions
* Check last ticker price and trend before place take profit order


## Tested
On margin 4.2.2 Linux, VPS UBUNTU 20.04 4*vCPU 8Gb
Exchange: Demo-OKEX, Bitfinex

+ Volume and price correct for grid and take profit order
+ Reverse work
+ Shift grid
+ Auto overlap price for grid is correct
+ Export into funds_rate.db
+ Telegram notification
+ control from Telegram message
+ partially filled order logic

## NOT Tested

## Known issue
* on Bitfinex missed or incorrect reply status of placed or canceled orders (need margin function)
* On Bitfinex margin freeze without error if more than one bot started. On Demo-OKEX no problem.

## Target
* Extended testing capabilities
* Optimization ideas
* Several users is more reaction from margin support
* Resources for development
* Quickly get fault tolerance profitable system
