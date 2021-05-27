===============================
Cycle grid martingale strategy
===============================

The motto of the project
------------------------
Started and forgot

Regardless of exchange overloads, network connection lost, hardware fault.

Trade idea
----------
Martingale Strategy is to create a grid of increasing volume orders and when they perform
creation of one take profit order of the total volume in the opposite direction at the price
of the overlapping Fee and the specified profit.

This allows you to increase the initial deposit using price fluctuations in any trend.

If all the grid orders are filled, reverse and start the cycle in another direction.

In the cycle to sell, the profit accumulates in the first currency.
In the cycle to buy, the profit accumulates in the second coin.

Functionality
-------------
* Create grid and take profit orders
* Reverse algo if all grid orders are filling
* Calculation of separate MAKER and TAKER fee
* Run auto shift grid orders (customizable) if the price is gone (before take profit placed) 
* Fractional creation of grid for increase productivity (customizable)
* Adaptive overlap price for grid on current market conditions (customizable)
* Save funding change in sqlite3 .db for external analytics (not Windows ver.)
* Adaptive for exchange performance
* Telegram notification
* external control from Telegram bot

Planned
-------
* Get stability in pump/dump situation (it's real)
* Full auto recovery after any reason crash, restart etc.
* Adaptive PROFIT param for current trade conditions
* External collect analytics for all exchange and trade pair
* Create install and user manual, FAQ
* Add logarithm price option for grid
* Check last ticker price before place take profit order 

Tested
------
On margin 4.2.2 Linux, VPS UBUNTU 20.04 4*vCPU 8Gb
Exchange: Demo-OKEX, Bitfinex

+ Volume and price correct for grid and take profit order
+ Reverse work
+ Shift grid
+ Auto overlap price for grid is correct
+ Export into funds_rate.db
+ Telegram notification

NOT Tested
----------
- partially filled order logic not complete tested

Known issue
-----------
* not work with more than one pair, margin is freeze (wait margin fix)
* on Bitfinex missed or incorrect reply status of placed or canceled orders (need margin func)

Target
------
* Extended testing capabilities
* Optimization ideas
* Several users is more reaction from margin support
* Resources for development
* Quickly get fault tolerance profitable system
