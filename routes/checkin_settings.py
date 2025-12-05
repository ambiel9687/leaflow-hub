#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Checkin settings routes for Leaflow Auto Check-in Control Panel
"""

from datetime import datetime

from flask import Blueprint, request, jsonify

from config import logger
from database import db, data_cache
from utils import token_required

checkin_settings_bp = Blueprint('checkin_settings', __name__)


@checkin_settings_bp.route('/api/checkin-settings', methods=['GET'])
@token_required
def get_checkin_settings():
    """Get global checkin settings"""
    try:
        settings = db.fetchone('SELECT * FROM checkin_settings WHERE id = 1')
        if settings:
            return jsonify(settings)
        else:
            default_settings = {
                'id': 1,
                'checkin_time': '05:30',
                'retry_count': 2,
                'random_delay_min': 0,
                'random_delay_max': 30
            }
            return jsonify(default_settings)
    except Exception as e:
        logger.error(f"Get checkin settings error: {e}")
        return jsonify({'error': 'Failed to load settings'}), 500


@checkin_settings_bp.route('/api/checkin-settings', methods=['PUT'])
@token_required
def update_checkin_settings():
    """Update global checkin settings"""
    try:
        data = request.get_json()
        logger.info(f"Updating checkin settings with data: {data}")

        checkin_time = data.get('checkin_time', '05:30')
        retry_count = int(data.get('retry_count', 2))
        random_delay_min = int(data.get('random_delay_min', 0))
        random_delay_max = int(data.get('random_delay_max', 30))

        # Validate parameters
        if random_delay_min > random_delay_max:
            return jsonify({'message': '随机延迟最小值不能大于最大值'}), 400

        if retry_count < 0 or retry_count > 5:
            return jsonify({'message': '重试次数必须在 0-5 之间'}), 400

        if random_delay_min < 0 or random_delay_max > 300:
            return jsonify({'message': '随机延迟必须在 0-300 秒之间'}), 400

        existing = db.fetchone('SELECT id FROM checkin_settings WHERE id = 1')

        if existing:
            db.execute('''
                UPDATE checkin_settings
                SET checkin_time = ?, retry_count = ?,
                    random_delay_min = ?, random_delay_max = ?,
                    updated_at = ?
                WHERE id = 1
            ''', (
                checkin_time, retry_count,
                random_delay_min, random_delay_max,
                datetime.now()
            ))
            logger.info("Checkin settings updated successfully")
        else:
            db.execute('''
                INSERT INTO checkin_settings
                (id, checkin_time, retry_count, random_delay_min, random_delay_max)
                VALUES (1, ?, ?, ?, ?)
            ''', (
                checkin_time, retry_count,
                random_delay_min, random_delay_max
            ))
            logger.info("Checkin settings created successfully")

        data_cache.invalidate()

        return jsonify({'message': '签到设置保存成功'})
    except Exception as e:
        logger.error(f"Update checkin settings error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400
