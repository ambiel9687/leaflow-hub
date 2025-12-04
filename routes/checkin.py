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
