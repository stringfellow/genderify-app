#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import sqlite3
from datetime import datetime, timedelta

from celery import Celery

from genderify.gender_finder import Genderifier

celery_app = Celery('tasks', broker='amqp://localhost//')
log = logging.getLogger(__name__)


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
    print("Timing out for less than {}".format(timeout))


@celery_app.task
def process_task(task_id):
    """Process all the tasks."""
    conn = sqlite3.connect('tasks.db')
    curs = conn.cursor()
    print("TASK ID: {}".format(task_id))
    curs.execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
    )
    row = curs.fetchone()
    row = dict(zip([d[0] for d in curs.description], row))
    log.info("Running for row %s", row)
    with Genderifier(
        spotify_token=row['token'],
        db_file_path='genderify.db',
    ) as genderifier:
        genderifier.set_artists_batch_from_spotify_public_playlist(
            user_id=row['username'], playlist_id=row['playlist_id']
        )
        genderifier.genderise_batch()
        report = genderifier.get_report()
        log.info("Done for row, report = %s", report)
        curs.execute(
            "UPDATE tasks "
            "SET female = ?, male = ?, unknown = ?, state = ?, "
            "playlist_name = ?, playlist_description = ?"
            "WHERE id = ?",
            (
                report['female'],
                report['male'],
                report['unknown'] + report['nonbinary'],
                'processed',
                genderifier.playlist_name,
                genderifier.playlist_description,
                row['id'],
            )
        )
        conn.commit()
        log.info("Updated.")
    conn.close()
    log.info("Done, bye!")
