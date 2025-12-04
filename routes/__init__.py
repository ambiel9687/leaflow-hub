#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Routes module for Leaflow Auto Check-in Control Panel
"""

from .auth import auth_bp
from .accounts import accounts_bp
from .checkin import checkin_bp
from .notification import notification_bp


def register_blueprints(app):
    """Register all blueprints to the Flask app"""
    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(checkin_bp)
    app.register_blueprint(notification_bp)
