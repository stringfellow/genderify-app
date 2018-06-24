#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
import logging

import sqlite3
from flask import Flask, render_template, request, jsonify

from genderify.gender_finder import Genderifier

from tasks import process_task

app = Flask(__name__)
log = logging.getLogger(__name__)


@app.route("/")
def home():
    """Where you paste a playlist URL."""
    return render_template('home.jinja')


@app.route("/playlists")
def playlists():
    """Playlists with their splits."""
    return render_template('playlists.jinja')


@app.route("/callback")
def spotify_token():
    """Where spotify auth redirects to."""
    return render_template('callback.jinja')


@app.route("/submit", methods=('POST',))
def save():
    """Save the request."""
    uid = request.form['state']
    username, pl_id = uid.split(':')
    token = request.form['access_token']
    conn = sqlite3.connect('tasks.db')
    curs = conn.cursor()
    curs.execute(
        "SELECT * FROM tasks WHERE username = ? AND playlist_id = ? "
        "AND state = 'waiting' "
        "ORDER BY timestamp DESC",
        (username, pl_id)
    )
    result = curs.fetchone()

    with Genderifier(
        spotify_token=token,
        db_file_path='genderify.db',
    ) as genderifier:
        playlist = genderifier.get_playlist(username, pl_id)

    try:
        last_updated = max([
            datetime.strptime(item['added_at'], '%Y-%m-%dT%H:%M:%SZ')
            for item in playlist['tracks']['items']
        ])
        last_checked = datetime.strptime(result[1], '%Y-%m-%dT%H:%M:%S.%f')
        re_check = last_checked < last_updated
        log.info(
            'Playlist {} {} checked: {}, last updated: {}, recheck: {}'.format(
                username, pl_id, last_checked, last_updated, re_check
            )
        )
    except (KeyError, IndexError, TypeError, ValueError) as err:
        log.exception(err)
        re_check = True

    if not re_check:
        conn.close()
        return jsonify({
            'status': 'OK',
            'redirect': '/result/{}/{}'.format(username, pl_id)
        })
    curs.execute(
        "INSERT INTO tasks (timestamp, username, playlist_id, token, state) "
        "VALUES (?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), username, pl_id, token, "waiting")
    )
    conn.commit()
    curs.execute("SELECT id FROM tasks ORDER BY id DESC LIMIT 1")
    task_id = curs.fetchone()[0]
    conn.close()
    log.info("Saved new task for {} - {}".format(username, pl_id))
    process_task.delay(task_id)
    return jsonify({
        'status': 'OK',
        'redirect': '/result/{}/{}'.format(username, pl_id)
    })


@app.route("/requeue/<task_id>")
def requeue(task_id):
    """Just force a re-queue."""
    process_task.delay(int(task_id))
    return jsonify({'status': 'OK'})


@app.route("/result/<username>/<pl_id>")
def results(username, pl_id):
    """Show results, if we got them..."""
    conn = sqlite3.connect('tasks.db')
    curs = conn.cursor()
    curs.execute(
        "SELECT * FROM tasks WHERE username = ? and playlist_id = ? "
        "ORDER BY timestamp DESC",
        (username, pl_id)
    )
    result = curs.fetchone()
    if result:
        result = dict(zip([d[0] for d in curs.description], result))
        context = result
        if result['state'] == 'waiting':
            curs.execute(
                "SELECT * FROM tasks WHERE state = 'waiting' "
                "ORDER BY timestamp DESC"
            )
            rows = curs.fetchall()
            total = len(rows)
            for ix, row in enumerate(rows):
                if row[2] == username and row[3] == pl_id:
                    break
            context.update({
                "total": total,
                "index": ix + 1
            })
        elif result['state'] == 'processed':
            context['total'] = sum([
                result['female'],
                result['male'],
                result['unknown'],
            ])
    else:
        context = {'state': 'error', 'error': "No row found."}
    return render_template('result.jinja', context=context)
