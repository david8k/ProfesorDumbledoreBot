#!/usr/bin/python
# -*- coding: utf-8 -*-

############################################################################
#                                                                          #
# Profesor Dumbledore Bot                                                  # 
# Copyright (C) 2019 - Pikaping                                            #
#                                                                          #
# This program is free software: you can redistribute it and/or modify     #
# it under the terms of the GNU Affero General Public License as           #
# published by the Free Software Foundation, either version 3 of the       #
# License, or (at your option) any later version.                          #
#                                                                          #
# This program is distributed in the hope that it will be useful,          #
# but WITHOUT ANY WARRANTY; without even the implied warranty of           #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the            #
# GNU Affero General Public License for more details.                      #
#                                                                          #
# You should have received a copy of the GNU Affero General Public License #
# along with this program.  If not, see <https://www.gnu.org/licenses/>.   #
#                                                                          #
############################################################################

import logging
import threading

from profdumbledorebot.mwt import MWT
from profdumbledorebot.model import User
from profdumbledorebot.db import get_session
from sqlalchemy.sql.expression import and_, or_
from profdumbledorebot.sql.support import get_unique_from_query

LOCK = threading.RLock()


@MWT(timeout=60)
def get_user(user_id):
    try:
        session = get_session()
        return get_unique_from_query(session.query(User).filter(User.id == user_id))
    finally:
        session.close()


def get_real_user(user_id):
    try:
        session = get_session()
        return get_unique_from_query(session.query(User).filter(User.id == user_id))
    finally:
        session.close()


@MWT(timeout=60*60)
def get_user_by_name(username):
    try:    
        session = get_session()
        return get_unique_from_query(session.query(User).filter(User.alias == username))
    finally:
        session.close()


@MWT(timeout=60)
def has_fc(user_id):
    try:
        session = get_session()
        fc = get_unique_from_query(session.query(User.friend_id).filter(User.id == user_id))
        if fc:
            return True
        return False
    finally:
        session.close()


def set_user(user_id):
    with LOCK:
        session = get_session()
        user = User(id=user_id)
        session.add(user)
        session.commit()
        session.close()
        return


def update_fclist(user_id):
    with LOCK:
        session = get_session()
        user = get_unique_from_query(session.query(User).filter(User.id == user_id))
        user.fclists = not user.fclists
        session.commit()
        session.close()


def update_mentions(user_id):
    with LOCK:
        session = get_session()
        user = get_unique_from_query(session.query(User).filter(User.id == user_id))
        user.alerts = not user.alerts
        session.commit()
        session.close()


def del_user(user_id):
    with LOCK:
        session = get_session()
        session.query(User).filter(User.id == user_id).delete()
        session.commit()
        session.close()
        return


def ban_user(user_id, flag):
    with LOCK:
        session = get_session()
        user = get_unique_from_query(session.query(User).filter(User.id == user_id))
        user.flag = flag
        user.banned = True
        session.commit()
        session.close()


def unban_user(user_id):
    with LOCK:
        session = get_session()
        user = get_unique_from_query(session.query(User).filter(User.id == user_id))
        user.flag = ""
        user.banned = False
        session.commit()
        session.close()


def commit_user(user_id, alias=None, level=None, profession=None, house=None, team=None, validation=None):
    with LOCK:
        session = get_session()
        user = get_unique_from_query(session.query(User).filter(User.id == user_id))
        if alias:
            user.alias = alias
        if level:
            user.level = level
        if house:
            user.house = house
        if validation:
            user.validation = validation
        if profession:
            user.profession = profession
        if team:
            user.team = team
        session.commit()
        session.close()


def set_fc(fc, user_id):
    with LOCK:
        session = get_session()
        user = get_unique_from_query(session.query(User).filter(User.id == user_id))
        user.friend_id = fc
        session.commit()
        session.close()

