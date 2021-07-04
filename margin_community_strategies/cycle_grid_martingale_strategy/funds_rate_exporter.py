#!/usr/bin/env python3

####################################################################
# Config for prometheus_client
# Copyright © 2021 Jerry Fedorenko aka VM
# ver. 0.7rc
# See readme.md for detail
# Communication with the author and support on
# https://discord.com/channels/600652551486177292/601329819371831296
####################################################################

import time
import sqlite3
import psutil

from prometheus_client import start_http_server, Gauge
from datetime import datetime

# !!!!!!!!!!!!!!!!!!! SETUP  !!!!!!!!!!!!!!!!!!!!!!!!!!!!

# path to .db
DATABASE = '/home/ubuntu/.margin/funds_rate.db'

# external port for prometheus
PORT = 8000

# sec delay for .db polling
SLEEP_TIME_S = 60

# Server name
VPS_NAME = 'hetzner_00'

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

# TIME = datetime(2021, 6, 1, 0, 0, 0)
TIME = datetime.now()

# Metric declare
SUM_F_PROFIT = Gauge("margin_f_profit", "first profit", ['exchange', 'pair', 'vps_name'])
SUM_S_PROFIT = Gauge("margin_s_profit", "second profit", ['exchange', 'pair', 'vps_name'])
LAST_RATE = Gauge("margin_last_rate", "pair last rate", ['exchange', 'pair', 'vps_name'])
SUM_PROFIT = Gauge("margin_sum_profit", "sum profit on last rate", ['exchange', 'pair', 'vps_name'])

CYCLE_COUNT = Gauge("margin_cycle_count", "cycle count", ['exchange', 'pair', 'vps_name'])
BUY_COUNT = Gauge("margin_buy_count", "cycle buy count", ['exchange', 'pair', 'vps_name'])
SELL_COUNT = Gauge("margin_sell_count", "cycle sell count", ['exchange', 'pair', 'vps_name'])
BUY_TIME = Gauge("margin_buy_time", "cycle buy time", ['exchange', 'pair', 'vps_name'])
SELL_TIME = Gauge("margin_sell_time", "cycle sell time", ['exchange', 'pair', 'vps_name'])

BUY_INTEREST = Gauge("margin_buy_interest", "sum buy interest", ['exchange', 'pair', 'vps_name'])
SELL_INTEREST = Gauge("margin_sell_interest", "sum sell interest", ['exchange', 'pair', 'vps_name'])

F_BALANCE = Gauge("margin_f_balance", "first balance amount", ['exchange', 'pair', 'vps_name'])
S_BALANCE = Gauge("margin_s_balance", "second balance amount", ['exchange', 'pair', 'vps_name'])
TOTAL_BALANCE = Gauge("margin_balance", "total balance amount by last rate", ['exchange', 'pair', 'vps_name'])

# VPS control
VPS_CPU = Gauge("margin_vps_cpu", "average cpu load", ['vps_name'])
VPS_MEMORY = Gauge("margin_vps_memory", "average memory use in %", ['vps_name'])

''' Cycle parameters for future use
PRICE_SHIFT = Gauge("margin_price_shift", "price shift", ['exchange', 'pair'])
PROFIT = Gauge("margin_profit", "profit", ['exchange', 'pair'])
OVER_PRICE = Gauge("margin_over_price", "over price", ['exchange', 'pair'])
ORDER_Q = Gauge("margin_order_q", "order_q", ['exchange', 'pair'])
MARTIN = Gauge("margin_martin", "martin", ['exchange', 'pair'])
LINEAR_GRID_K = Gauge("margin_linear_grid_k", "linear_grid_k", ['exchange', 'pair'])
ADAPTIVE_TRADE_CONDITION = Gauge("margin_adaptive_trade_condition", "adaptive_trade_condition", ['exchange', 'pair'])
KB = Gauge("margin_kb", "bollinger band k bottom", ['exchange', 'pair'])
KT = Gauge("margin_kt", "bollinger band k top", ['exchange', 'pair'])
'''


def read_sqlite_table(sql_conn):
    cursor = sql_conn.cursor()
    # Aggregate score for pair on exchange
    cursor.execute('SELECT tex.name, tf.id_exchange,\
                    tf.f_currency, tf.s_currency,\
                    count(*) as cycle_count,\
                    sum(f_profit) as sum_f_profit,\
                    sum(s_profit) as sum_s_profit\
                    FROM t_funds as tf LEFT JOIN t_exchange tex USING(id_exchange)\
                    GROUP BY tex.name, tf.id_exchange, tf.f_currency, tf.s_currency')
    records = cursor.fetchall()
    for row in records:
        exchange = str(row[0])
        id_exchange = int(row[1])
        f_currency = str(row[2])
        s_currency = str(row[3])
        pair = f_currency + "/" + s_currency
        cycle_count = int(row[4])
        CYCLE_COUNT.labels(exchange, pair, VPS_NAME).set(cycle_count)
        sum_f_profit = float(row[5])
        SUM_F_PROFIT.labels(exchange, pair, VPS_NAME).set(sum_f_profit)
        sum_s_profit = float(row[6])
        SUM_S_PROFIT.labels(exchange, pair, VPS_NAME).set(sum_s_profit)

        # Last rate
        cursor.execute('SELECT rate\
                        FROM t_funds\
                        WHERE id_exchange=:id_exchange\
                        AND f_currency=:f_currency\
                        AND s_currency=:s_currency\
                        GROUP BY id_exchange, f_currency, s_currency\
                        HAVING id = MAX(id)',
                       {'id_exchange': id_exchange, 'f_currency': f_currency, 's_currency': s_currency})
        last_rate_row = cursor.fetchone()
        if last_rate_row:
            last_rate = float(last_rate_row[0])
            LAST_RATE.labels(exchange, pair, VPS_NAME).set(last_rate)
        else:
            last_rate = 0.0
        # Sum profit
        sum_profit = sum_f_profit * last_rate + sum_s_profit
        SUM_PROFIT.labels(exchange, pair, VPS_NAME).set(sum_profit)

        # Sum interest income and cycle count, calculated by each buy and sell cycle
        cursor.execute('SELECT count(*), sum(100 * s_profit / s_depo), sum(cycle_time)\
                        FROM t_funds\
                        WHERE id_exchange=:id_exchange\
                        AND f_currency=:f_currency\
                        AND s_currency=:s_currency\
                        AND cycle_buy = 1',
                       {'id_exchange': id_exchange, 'f_currency': f_currency, 's_currency': s_currency})
        cycle_buy_row = cursor.fetchone()

        cycle_buy_count = int(cycle_buy_row[0]) if cycle_buy_row[0] else 0
        cycle_buy_interest = float(cycle_buy_row[1]) if cycle_buy_row[1] else 0.0
        cycle_buy_time = float(cycle_buy_row[2]) if cycle_buy_row[2] else 0.0

        cursor.execute('SELECT count(*), sum(100 * f_profit / f_depo), sum(cycle_time)\
                        FROM t_funds\
                        WHERE id_exchange=:id_exchange\
                        AND f_currency=:f_currency\
                        AND s_currency=:s_currency\
                        AND cycle_buy = 0',
                       {'id_exchange': id_exchange, 'f_currency': f_currency, 's_currency': s_currency})
        cycle_sell_row = cursor.fetchone()

        cycle_sell_count = int(cycle_sell_row[0]) if cycle_sell_row[0] else 0
        cycle_sell_interest = float(cycle_sell_row[1]) if cycle_sell_row[1] else 0.0
        cycle_sell_time = float(cycle_sell_row[2]) if cycle_sell_row[2] else 0.0

        BUY_COUNT.labels(exchange, pair, VPS_NAME).set(cycle_buy_count)
        BUY_TIME.labels(exchange, pair, VPS_NAME).set(cycle_buy_time)
        BUY_INTEREST.labels(exchange, pair, VPS_NAME).set(cycle_buy_interest)

        SELL_COUNT.labels(exchange, pair, VPS_NAME).set(cycle_sell_count)
        SELL_TIME.labels(exchange, pair, VPS_NAME).set(cycle_sell_time)
        SELL_INTEREST.labels(exchange, pair, VPS_NAME).set(cycle_sell_interest)

        # Balance amount
        cursor.execute('SELECT f_balance, s_balance\
                        FROM t_funds\
                        WHERE id_exchange=:id_exchange\
                        AND f_currency=:f_currency\
                        AND s_currency=:s_currency\
                        AND timestamp >:timestamp\
                        ORDER BY id',
                       {'id_exchange': id_exchange, 'f_currency': f_currency,
                        's_currency': s_currency, 'timestamp': TIME})
        balance_row = cursor.fetchall()

        if not balance_row:
            cursor.execute('SELECT f_balance, s_balance\
                            FROM t_funds\
                            WHERE id_exchange=:id_exchange\
                            AND f_currency=:f_currency\
                            AND s_currency=:s_currency\
                            GROUP BY id_exchange, f_currency, s_currency\
                            HAVING id = MAX(id)\
                            ORDER BY id',
                           {'id_exchange': id_exchange, 'f_currency': f_currency, 's_currency': s_currency})
        balance_row = cursor.fetchall()

        for bri in balance_row:
            f_balance = bri[0]
            s_balance = bri[1]
            balance = f_balance * last_rate + s_balance
            F_BALANCE.labels(exchange, pair, VPS_NAME).set(f_balance)
            S_BALANCE.labels(exchange, pair, VPS_NAME).set(s_balance)
            TOTAL_BALANCE.labels(exchange, pair, VPS_NAME).set(balance)

    cursor.close()


if __name__ == '__main__':
    # Start up the server to expose the metrics.
    start_http_server(PORT)
    sqlite_connection = None
    try:
        sqlite_connection = sqlite3.connect(DATABASE)
    except sqlite3.Error as error:
        print("SQLite error", error)
    while True:
        read_sqlite_table(sqlite_connection)
        VPS_CPU.labels(VPS_NAME).set(psutil.getloadavg()[1])
        VPS_MEMORY.labels(VPS_NAME).set(psutil.virtual_memory()[2])
        TIME = datetime.now()
        time.sleep(SLEEP_TIME_S)
