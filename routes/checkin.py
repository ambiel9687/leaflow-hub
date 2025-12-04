#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check-in routes for Leaflow Auto Check-in Control Panel
"""

import threading
from datetime import datetime

from flask import Blueprint, request, jsonify

from config import logger, TIMEZONE
from database import db, account_cache, data_cache
from services import scheduler
from utils import token_required

checkin_bp = Blueprint('checkin', __name__)


@checkin_bp.route('/api/checkin/clear', methods=['POST'])
@token_required
def clear_checkin_history():
    """Clear checkin history"""
    try:
        data = request.get_json()
        clear_type = data.get('type', 'today')

        if clear_type == 'today':
            today = datetime.now(TIMEZONE).date()
            db.execute('DELETE FROM checkin_history WHERE DATE(checkin_date) = DATE(?)', (today,))
            db.execute('UPDATE accounts SET last_checkin_date = NULL WHERE DATE(last_checkin_date) = DATE(?)', (today,))
            message = 'Today\'s checkin history cleared'
        elif clear_type == 'all':
            db.execute('DELETE FROM checkin_history')
            db.execute('UPDATE accounts SET last_checkin_date = NULL')
            message = 'All checkin history cleared'
        else:
            return jsonify({'message': 'Invalid clear type'}), 400

        account_cache.refresh_from_db(db)
        data_cache.invalidate()

        logger.info(f"Checkin history cleared ({clear_type}) and cache refreshed")

        return jsonify({'message': message})
    except Exception as e:
        logger.error(f"Clear checkin history error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400


@checkin_bp.route('/api/checkin/manual/<int:account_id>', methods=['POST'])
@token_required
def manual_checkin(account_id):
    """Trigger manual check-in"""
    try:
        threading.Thread(target=scheduler.perform_checkin, args=(account_id,), daemon=True).start()
        return jsonify({'message': 'Manual check-in triggered'})
    except Exception as e:
        logger.error(f"Manual checkin error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400


@checkin_bp.route('/api/checkin/history/<int:account_id>', methods=['GET'])
@token_required
def get_checkin_history(account_id):
    """Get checkin history for a specific account (last 10 days by default)"""
    try:
        days = request.args.get('days', 10, type=int)
        history = db.fetchall('''
            SELECT ch.id, ch.success, ch.message, ch.retry_times, ch.created_at, ch.checkin_date
            FROM checkin_history ch
            WHERE ch.account_id = ?
              AND ch.checkin_date >= DATE(?, '-' || ? || ' days')
            ORDER BY ch.created_at DESC
        ''', (account_id, datetime.now(TIMEZONE).date(), days))
        return jsonify(history or [])
    except Exception as e:
        logger.error(f"Get checkin history error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400


@checkin_bp.route('/api/checkin/delete', methods=['POST'])
@token_required
def delete_checkin_records():
    """Delete specific checkin records"""
    try:
        data = request.get_json()
        record_ids = data.get('ids', [])

        if not record_ids:
            return jsonify({'message': 'No records specified'}), 400

        placeholders = ','.join(['?' for _ in record_ids])
        db.execute(f'DELETE FROM checkin_history WHERE id IN ({placeholders})', record_ids)

        data_cache.invalidate()
        logger.info(f"Deleted checkin records: {record_ids}")

        return jsonify({'message': f'Deleted {len(record_ids)} records'})
    except Exception as e:
        logger.error(f"Delete checkin records error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400
