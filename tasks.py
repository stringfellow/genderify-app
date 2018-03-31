#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime, timedelta

from genderify.gender_finder import Genderifier


def clean_up_db():
    """Set any expired tokens to 'failed'."""
    timeout = (datetime.utcnow() - timedelta(seconds=3600)).isoformat()
    conn = sqlite3.connect('tasks.db')
    curs = conn.cursor()
    curs.execute(
        "UPDATE tasks SET state = 'failed' "
        "WHERE state = 'waiting' AND timestamp < ?",
        (timeout,)
    )
    conn.commit()
    conn.close()
    print(f"Timing out for less than {timeout}")


def process_tasks():
    """Process all the tasks."""


if __name__ == '__main__':
    clean_up_db()
