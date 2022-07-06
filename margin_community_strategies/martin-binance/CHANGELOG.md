## v1.1.0 - 2022-06-16
### Added for new features
* FTX exchange for STANDALONE mode added
* updating grid if market conditions change

### Update
* Grafana template
* code refactoring

## v1.0rc7 - 2022-03-01
### Added for new features
* control and structure update for funds_rate.db for future updates
* alerting for mismatch of number of orders to strategy status

### Fixed
* updated balance value for direct cycle for analytics

### Update
* refined calculation of order parameters for grid, taking into account rounding of price and volume value and
correction of parameters of the last order
* Binance API for /api/v3/exchangeInfo

## v1.0rc6.1 - 2022-01-19
### Update
* refactoring funds_rate_exporter.py
* readme.md, add 'For developer' chapter

## v1.0rc6 - 2022-01-11
### Fixed
* handler for cancel order - part filled - correct cancel non-filled part 
* release hold grid after check, not place grid
* remove extra messages about receiving the command through the Telegram
* incorrect balance in USD for assets in trading pair (for analytics)

### Update
* set min profit for TP also when calculate it before reverse
* Grafana dashboard template, some improvement

### Added for new features
* some cycle parameters for export into analytic
* STANDALONE mode (Binance) get asset balances from Funding wallet for analytics

## v1.0rc5 - 2021-12-27
### Fixed
* Set min profit for TP when executing only the penultimate order of the grid

### Added for new features
* Modified and tested for macOS

## v1.0rc4 - 2021-12-23
### Update
* Readme.md

### Added for new features
* Cycle end alert and manual action waiting
* Set min profit for TP when executing the penultimate order of the grid

### Fixed
* TypeError: unsupported operand type(s) for -: 'float' and 'NoneType' At: /executor.py(615):


## v1.0rc2 - 2021-12-21
### Fixed
* margin Windows full functional
* refactoring service process threading

## v1.0rc0 - 2021-12-07
* Added direct access to Binance SPOT API
* Migrate to Decimal() calculation for necessary precision
* Added stop-loss checkpoint for possible bug
* Split logic and initial trading setup
* Added buy/sell asset with grid options

### Fixed
* Full code refactoring

### Update
* Readme.md

## v0.8rc - 2021-07-29
### Added for new features.
* Auto calculate round float multiplier
* Added fee processing for second currency only, like as KRAKEN
* For analytic subsystem added consolidated asset valuation
* Additional check for Error when place and cancel order
* Recovery state logic implemented
* For ADAPTIVE_TRADE_CONDITION adaptive calculate grid orders quantity

### Fixed
* Message 'Waiting ending cycle for manual action' instead of 'Stop...'

### Changed for existing functionality.
* Code refactoring
* Place grid orders by part block for first ORDER_Q count and one by one for next

### Update
* Readme.md

## v0.7rc - 2021-06-04
### Added for new features.
* Send Telegram messages periodically that bot still alive
* Added adaptive profit calculate based on Bollinger band
* Added config for [prometheus_client](https://github.com/prometheus/client_python)
* Added 'no loss' over price calculate for Reverse cycle grid
* Added Average Directional Index analysis to optimize Reverse solution

### Fixed
* Difference k for top and bottom BB line

### Update
* Readme.md

## v0.5b - 2021-06-08
### Added for new features
* Calculate price of grid orders by logarithmic scale
* Added cycle result data for save into t_funds

### Update
* Readme.md

### Fixed
* Refactoring and optimise calculate and place take profit order
* Optimise saving funds and cycle data to .db

## v0.4b - 2021-05-29
### Added for new features.
* Check if the take profit order execute by market and process it
* Optimize send Telegram message and save to .db function

## v0.3b - 2021-05-28
### Added for new features.
* Create public edition

## v0.2b - 2021-05-28
### Fixed
* Fix funds call error

### Added for new features.
* Commented service functions
* Added setup info into docstring

## v0.7a - 2021-05-26
### Added for new features.
* External control from Telegram bot

## v0.6a - 2021-05-23

### Added for new features
### Changed for changes in existing functionality
### Deprecated for soon-to-be removed features
### Removed for now removed features
### Fixed for any bug fixes
### Security 

