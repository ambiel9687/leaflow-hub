#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Authentication routes for Leaflow Auto Check-in Control Panel
"""

import re
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, make_response, current_app
import jwt

from config import ADMIN_USERNAME, ADMIN_PASSWORD, TIMEZONE, logger
from database import db
from utils import token_required

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    """Handle login requests"""
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No data provided'}), 400

        username = data.get('username')
        password = data.get('password')

        logger.info(f"Login attempt for user: {username}")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            token = jwt.encode({
                'user': username,
                'exp': datetime.utcnow() + timedelta(days=7)
            }, current_app.config['SECRET_KEY'], algorithm='HS256')

            logger.info(f"Login successful for user: {username}")
            return jsonify({'token': token, 'message': 'Login successful'})

        logger.warning(f"Login failed for user: {username}")
        return jsonify({'message': 'Invalid credentials'}), 401

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'message': 'Login error'}), 500


@auth_bp.route('/api/verify', methods=['GET'])
@token_required
def verify_token():
    """Verify if token is valid"""
    return jsonify({'valid': True})


@auth_bp.route('/api/dashboard', methods=['GET'])
@token_required
def dashboard():
    """Get dashboard statistics"""
    try:
        total_accounts = db.fetchone('SELECT COUNT(*) as count FROM accounts', use_cache=True)
        enabled_accounts = db.fetchone('SELECT COUNT(*) as count FROM accounts WHERE enabled = 1', use_cache=True)

        today = datetime.now(TIMEZONE).date()

        today_checkins = db.fetchall('''
            SELECT a.name, ch.success, ch.message, ch.created_at, ch.retry_times
            FROM checkin_history ch
            JOIN accounts a ON ch.account_id = a.id
            WHERE DATE(ch.checkin_date) = DATE(?)
            ORDER BY ch.created_at DESC
            LIMIT 20
        ''', (today,))

        total_checkins = db.fetchone('SELECT COUNT(*) as count FROM checkin_history', use_cache=True)
        successful_checkins = db.fetchone('SELECT COUNT(*) as count FROM checkin_history WHERE success = 1', use_cache=True)

        total_count = total_checkins['count'] if total_checkins else 0
        success_count = successful_checkins['count'] if successful_checkins else 0
        success_rate = round(success_count / total_count * 100, 2) if total_count > 0 else 0

        # 统计总余额和总消费
        balance_stats = db.fetchone('''
            SELECT
                COALESCE(SUM(CAST(current_balance AS DECIMAL(10,2))), 0) as total_balance,
                COALESCE(SUM(CAST(total_consumed AS DECIMAL(10,2))), 0) as total_consumed
            FROM accounts
            WHERE current_balance IS NOT NULL
        ''', use_cache=True)

        # 统计今日签到总额（从成功签到的 message 中提取）
        today_success_records = db.fetchall('''
            SELECT message FROM checkin_history
            WHERE DATE(checkin_date) = DATE(?) AND success = 1
        ''', (today,))

        today_checkin_amount = 0.0
        if today_success_records:
            for record in today_success_records:
                msg = record.get('message', '') or ''
                # 匹配数字，如 "+0.5"、"0.5 credits"、"获得 0.5"
                match = re.search(r'(\d+\.?\d*)\s*(credits?|元)?', msg, re.IGNORECASE)
                if match:
                    today_checkin_amount += float(match.group(1))

        total_balance = float(balance_stats['total_balance']) if balance_stats else 0
        total_consumed = float(balance_stats['total_consumed']) if balance_stats else 0

        return jsonify({
            'total_accounts': total_accounts['count'] if total_accounts else 0,
            'enabled_accounts': enabled_accounts['count'] if enabled_accounts else 0,
            'today_checkins': today_checkins or [],
            'total_checkins': total_count,
            'successful_checkins': success_count,
            'success_rate': success_rate,
            'total_balance': total_balance,
            'total_consumed': total_consumed,
            'today_checkin_amount': today_checkin_amount
        })

    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return jsonify({'error': 'Failed to load dashboard data'}), 500
