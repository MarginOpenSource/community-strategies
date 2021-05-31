#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Get message from Telegram bot and parse it into .db
# Copyright © 2021 Jerry Fedorenko aka VM

import sqlite3
import time

import requests

import cfg


def telegram_get(offset=None):
    command_list = []
    url = cfg.url
    token = cfg.token
    channel_id = cfg.channel_id
    url += token
    method = url + '/getUpdates'
    res = requests.post(method, data={'chat_id': channel_id, 'offset': offset})
    if res.status_code == 200:
        result = res.json().get('result')
        for i in result:
            update_id = i.get('update_id')
            message_id = i.get('message').get('message_id')
            text_in = i.get('message').get('text')
            try:
                reply_to_message = i.get('message').get('reply_to_message').get('text')
            except AttributeError:
                reply_to_message = None
            if reply_to_message:
                command_list.append({'update_id': update_id, 'message_id': message_id,
                                     'text_in': text_in, 'reply_to_message': reply_to_message})
        return command_list


connection_control = sqlite3.connect(cfg.margin_path + 'funds_rate.db')
cursor_control = connection_control.cursor()
offset_id = None
while True:
    x = telegram_get(offset_id)
    if x:
        offset_id = x[-1].get('update_id')
        offset_id += 1
        for n in x:
            a = n.get('reply_to_message')
            if a:
                bot_id = a.split('.')[0]
                cursor_control.execute('insert into t_control values(?,?,?,?)',
                                       (n['message_id'], n['text_in'], bot_id, None))
        connection_control.commit()
    time.sleep(10)
