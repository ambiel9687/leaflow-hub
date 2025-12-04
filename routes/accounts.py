#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Accounts routes for Leaflow Auto Check-in Control Panel
"""

import json

from flask import Blueprint, request, jsonify

from config import logger
from database import db, account_cache, data_cache
from utils import token_required, parse_cookie_string

accounts_bp = Blueprint('accounts', __name__)


@accounts_bp.route('/api/accounts', methods=['GET'])
@token_required
def get_accounts():
    """Get all accounts"""
    try:
        accounts = db.fetchall('''
            SELECT id, name, enabled, checkin_time_start, checkin_time_end,
                   check_interval, retry_count, created_at
            FROM accounts
        ''')
        return jsonify(accounts or [])
    except Exception as e:
        logger.error(f"Get accounts error: {e}")
        return jsonify({'error': 'Failed to load accounts'}), 500


@accounts_bp.route('/api/accounts', methods=['POST'])
@token_required
def add_account():
    """Add a new account"""
    try:
        data = request.get_json()
        name = data.get('name')
        cookie_input = data.get('token_data', data.get('cookie_data', ''))
        checkin_time_start = data.get('checkin_time_start', '06:30')
        checkin_time_end = data.get('checkin_time_end', '06:40')
        check_interval = data.get('check_interval', 60)
        retry_count = data.get('retry_count', 2)

        if not name or not cookie_input:
            return jsonify({'message': 'Name and cookie data are required'}), 400

        if isinstance(cookie_input, str):
            token_data = parse_cookie_string(cookie_input)
        else:
            token_data = cookie_input

        db.execute('''
            INSERT INTO accounts (name, token_data, checkin_time_start, checkin_time_end, check_interval, retry_count)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, json.dumps(token_data), checkin_time_start, checkin_time_end, check_interval, retry_count))

        account_cache.refresh_from_db(db)
        data_cache.invalidate()

        logger.info(f"Account '{name}' added and cache refreshed")

        return jsonify({'message': 'Account added successfully'})

    except ValueError as e:
        return jsonify({'message': f'Invalid cookie format: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Add account error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400


@accounts_bp.route('/api/accounts/<int:account_id>', methods=['PUT'])
@token_required
def update_account(account_id):
    """Update an account"""
    try:
        data = request.get_json()

        updates = []
        params = []

        if 'enabled' in data:
            updates.append('enabled = ?')
            params.append(1 if data['enabled'] else 0)

        if 'checkin_time_start' in data:
            updates.append('checkin_time_start = ?')
            params.append(data['checkin_time_start'])

        if 'checkin_time_end' in data:
            updates.append('checkin_time_end = ?')
            params.append(data['checkin_time_end'])

        if 'check_interval' in data:
            updates.append('check_interval = ?')
            params.append(data['check_interval'])

        if 'retry_count' in data:
            updates.append('retry_count = ?')
            params.append(data['retry_count'])

        if 'token_data' in data or 'cookie_data' in data:
            cookie_input = data.get('token_data', data.get('cookie_data', ''))
            if isinstance(cookie_input, str):
                token_data = parse_cookie_string(cookie_input)
            else:
                token_data = cookie_input
            updates.append('token_data = ?')
            params.append(json.dumps(token_data))

        if updates:
            params.append(account_id)
            query = f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?"
            db.execute(query, params)

            account_cache.refresh_from_db(db)
            data_cache.invalidate()

            logger.info(f"Account {account_id} updated and cache refreshed")

            return jsonify({'message': 'Account updated successfully'})

        return jsonify({'message': 'No updates provided'}), 400

    except Exception as e:
        logger.error(f"Update account error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400


@accounts_bp.route('/api/accounts/<int:account_id>', methods=['DELETE'])
@token_required
def delete_account(account_id):
    """Delete an account"""
    try:
        db.execute('DELETE FROM checkin_history WHERE account_id = ?', (account_id,))
        db.execute('DELETE FROM accounts WHERE id = ?', (account_id,))

        account_cache.refresh_from_db(db)
        data_cache.invalidate()

        logger.info(f"Account {account_id} deleted and cache refreshed")

        return jsonify({'message': 'Account deleted successfully'})
    except Exception as e:
        logger.error(f"Delete account error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400
