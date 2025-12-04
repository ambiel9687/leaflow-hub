#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Authentication utilities for Leaflow Auto Check-in Control Panel
"""

from functools import wraps
from flask import request, jsonify, current_app
import jwt

from config import logger


def token_required(f):
    """JWT authentication decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            if token.startswith('Bearer '):
                token = token[7:]
            jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return jsonify({'message': 'Token validation failed!'}), 401

    return decorated
