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
    """Get all accounts with today's checkin info"""
    from datetime import datetime
    from config import TIMEZONE

    try:
        today = datetime.now(TIMEZONE).date()

        # 获取账号列表及今日签到信息
        accounts = db.fetchall('''
            SELECT a.id, a.name, a.enabled, a.checkin_time_start, a.checkin_time_end,
                   a.check_interval, a.retry_count, a.created_at,
                   a.leaflow_uid, a.leaflow_name, a.leaflow_email, a.leaflow_created_at,
                   a.current_balance, a.total_consumed, a.balance_updated_at,
                   ch.success as today_success, ch.message as today_message,
                   ch.created_at as today_checkin_time
            FROM accounts a
            LEFT JOIN (
                SELECT account_id, success, message, created_at,
                       ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY created_at DESC) as rn
                FROM checkin_history
                WHERE DATE(checkin_date) = DATE(?)
            ) ch ON a.id = ch.account_id AND ch.rn = 1
        ''', (today,))
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


@accounts_bp.route('/api/accounts/<int:account_id>/refresh-balance', methods=['POST'])
@token_required
def refresh_account_balance(account_id):
    """Refresh balance info for a single account"""
    from datetime import datetime
    from config import TIMEZONE
    from services import BalanceService
    from services.checkin_service import LeafLowCheckin

    try:
        account = db.fetchone('SELECT * FROM accounts WHERE id = ?', (account_id,))
        if not account:
            return jsonify({'message': 'Account not found'}), 404

        # 解析 token_data 并创建 session
        token_data = json.loads(account['token_data'])
        leaflow_checkin = LeafLowCheckin()
        session = leaflow_checkin.create_session(token_data)

        # 获取余额信息
        success, result = BalanceService.fetch_balance_info(session)

        if not success:
            return jsonify({'message': f'Failed to fetch balance: {result}'}), 400

        # 更新数据库
        db.execute('''
            UPDATE accounts SET
                leaflow_uid = ?,
                leaflow_name = ?,
                leaflow_email = ?,
                leaflow_created_at = ?,
                current_balance = ?,
                total_consumed = ?,
                balance_updated_at = ?
            WHERE id = ?
        ''', (
            result['leaflow_uid'],
            result['leaflow_name'],
            result['leaflow_email'],
            result['leaflow_created_at'],
            result['current_balance'],
            result['total_consumed'],
            datetime.now(TIMEZONE),
            account_id
        ))

        account_cache.refresh_from_db(db)
        data_cache.invalidate()

        logger.info(f"Account {account['name']} balance refreshed: {result['current_balance']}")

        return jsonify({
            'message': 'Balance refreshed successfully',
            'balance': result
        })

    except Exception as e:
        logger.error(f"Refresh balance error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 500


@accounts_bp.route('/api/accounts/refresh-all-balance', methods=['POST'])
@token_required
def refresh_all_balances():
    """Refresh balance info for all enabled accounts"""
    from datetime import datetime
    from config import TIMEZONE
    from services import BalanceService
    from services.checkin_service import LeafLowCheckin

    try:
        accounts = db.fetchall('SELECT * FROM accounts WHERE enabled = 1')

        if not accounts:
            return jsonify({'message': 'No enabled accounts found'}), 404

        results = {
            'total': len(accounts),
            'success': 0,
            'failed': 0,
            'details': []
        }

        leaflow_checkin = LeafLowCheckin()

        for account in accounts:
            try:
                token_data = json.loads(account['token_data'])
                session = leaflow_checkin.create_session(token_data)

                success, result = BalanceService.fetch_balance_info(session)

                if success:
                    db.execute('''
                        UPDATE accounts SET
                            leaflow_uid = ?,
                            leaflow_name = ?,
                            leaflow_email = ?,
                            leaflow_created_at = ?,
                            current_balance = ?,
                            total_consumed = ?,
                            balance_updated_at = ?
                        WHERE id = ?
                    ''', (
                        result['leaflow_uid'],
                        result['leaflow_name'],
                        result['leaflow_email'],
                        result['leaflow_created_at'],
                        result['current_balance'],
                        result['total_consumed'],
                        datetime.now(TIMEZONE),
                        account['id']
                    ))

                    results['success'] += 1
                    results['details'].append({
                        'name': account['name'],
                        'success': True,
                        'balance': result['current_balance']
                    })
                    logger.info(f"Account {account['name']} balance refreshed: {result['current_balance']}")
                else:
                    results['failed'] += 1
                    results['details'].append({
                        'name': account['name'],
                        'success': False,
                        'error': result
                    })
                    logger.warning(f"Account {account['name']} balance refresh failed: {result}")

            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'name': account['name'],
                    'success': False,
                    'error': str(e)
                })
                logger.error(f"Account {account['name']} balance refresh error: {e}")

        account_cache.refresh_from_db(db)
        data_cache.invalidate()

        return jsonify({
            'message': f"Refreshed {results['success']}/{results['total']} accounts",
            'results': results
        })

    except Exception as e:
        logger.error(f"Refresh all balances error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 500
