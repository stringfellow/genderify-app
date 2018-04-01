#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
import json
import logging

import sqlite3
from flask import Flask, render_template, request, jsonify
app = Flask(__name__)

log = logging.getLogger(__name__)


@app.route("/")
def home():
    """Where you paste a playlist URL."""
    return render_template('home.jinja')


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
    if result:
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
    conn.close()
    log.info("Saved new task for {} - {}".format(username, pl_id))
    return jsonify({
        'status': 'OK',
        'redirect': '/result/{}/{}'.format(username, pl_id)
    })


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
    else:
        context = {'state': 'error', 'error': "No row found."}
    return render_template('result.jinja', context=context)
