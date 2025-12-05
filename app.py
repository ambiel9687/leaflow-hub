#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leaflow Auto Check-in Control Panel
Main application entry point
"""

from flask import Flask, send_from_directory
from flask_cors import CORS

from config import JWT_SECRET_KEY, PORT, logger
from routes import register_blueprints
from services import scheduler
from services.batch_redeem_service import batch_redeem_scheduler

# Create Flask app
app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = JWT_SECRET_KEY
CORS(app, supports_credentials=True)

# Register all blueprints
register_blueprints(app)


@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('static', 'index.html')


@app.route('/static/<path:path>')
def static_files(path):
    """Serve static files"""
    return send_from_directory('static', path)


if __name__ == '__main__':
    # Start the schedulers
    scheduler.start()
    batch_redeem_scheduler.start()
    logger.info(f"Starting Leaflow Auto Check-in Control Panel on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
