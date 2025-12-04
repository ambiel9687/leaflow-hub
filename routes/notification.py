#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notification routes for Leaflow Auto Check-in Control Panel
"""

from datetime import datetime

from flask import Blueprint, request, jsonify

from config import logger
from database import db, data_cache
from services import NotificationService
from utils import token_required

notification_bp = Blueprint('notification', __name__)


@notification_bp.route('/api/notification', methods=['GET'])
@token_required
def get_notification_settings():
    """Get notification settings"""
    try:
        settings = db.fetchone('SELECT * FROM notification_settings WHERE id = 1')
        if settings:
            for key in ['enabled', 'telegram_enabled', 'wechat_enabled', 'wxpusher_enabled', 'dingtalk_enabled']:
                if key in settings:
                    settings[key] = bool(settings.get(key, 0))

            string_fields = [
                'telegram_bot_token', 'telegram_user_id', 'telegram_host',
                'wechat_webhook_key', 'wechat_host',
                'wxpusher_app_token', 'wxpusher_uid', 'wxpusher_host',
                'dingtalk_access_token', 'dingtalk_secret', 'dingtalk_host'
            ]
            for field in string_fields:
                settings[field] = settings.get(field, '') or ''

            logger.info(f"Loaded notification settings: {settings}")
            return jsonify(settings)
        else:
            default_settings = {
                'id': 1,
                'enabled': False,
                'telegram_enabled': False,
                'telegram_bot_token': '',
                'telegram_user_id': '',
                'telegram_host': '',
                'wechat_enabled': False,
                'wechat_webhook_key': '',
                'wechat_host': '',
                'wxpusher_enabled': False,
                'wxpusher_app_token': '',
                'wxpusher_uid': '',
                'wxpusher_host': '',
                'dingtalk_enabled': False,
                'dingtalk_access_token': '',
                'dingtalk_secret': '',
                'dingtalk_host': ''
            }
            return jsonify(default_settings)
    except Exception as e:
        logger.error(f"Get notification settings error: {e}")
        return jsonify({'error': 'Failed to load settings'}), 500


@notification_bp.route('/api/notification', methods=['PUT'])
@token_required
def update_notification_settings():
    """Update notification settings"""
    try:
        data = request.get_json()
        logger.info(f"Updating notification settings with data: {data}")

        enabled = 1 if data.get('enabled', False) else 0
        telegram_enabled = 1 if data.get('telegram_enabled', False) else 0
        telegram_bot_token = data.get('telegram_bot_token', '') or ''
        telegram_user_id = data.get('telegram_user_id', '') or ''
        telegram_host = data.get('telegram_host', '') or ''
        wechat_enabled = 1 if data.get('wechat_enabled', False) else 0
        wechat_webhook_key = data.get('wechat_webhook_key', '') or ''
        wechat_host = data.get('wechat_host', '') or ''
        wxpusher_enabled = 1 if data.get('wxpusher_enabled', False) else 0
        wxpusher_app_token = data.get('wxpusher_app_token', '') or ''
        wxpusher_uid = data.get('wxpusher_uid', '') or ''
        wxpusher_host = data.get('wxpusher_host', '') or ''
        dingtalk_enabled = 1 if data.get('dingtalk_enabled', False) else 0
        dingtalk_access_token = data.get('dingtalk_access_token', '') or ''
        dingtalk_secret = data.get('dingtalk_secret', '') or ''
        dingtalk_host = data.get('dingtalk_host', '') or ''

        existing = db.fetchone('SELECT id FROM notification_settings WHERE id = 1')

        if existing:
            db.execute('''
                UPDATE notification_settings
                SET enabled = ?, telegram_enabled = ?, telegram_bot_token = ?, telegram_user_id = ?, telegram_host = ?,
                    wechat_enabled = ?, wechat_webhook_key = ?, wechat_host = ?,
                    wxpusher_enabled = ?, wxpusher_app_token = ?, wxpusher_uid = ?, wxpusher_host = ?,
                    dingtalk_enabled = ?, dingtalk_access_token = ?, dingtalk_secret = ?, dingtalk_host = ?,
                    updated_at = ?
                WHERE id = 1
            ''', (
                enabled, telegram_enabled, telegram_bot_token, telegram_user_id, telegram_host,
                wechat_enabled, wechat_webhook_key, wechat_host,
                wxpusher_enabled, wxpusher_app_token, wxpusher_uid, wxpusher_host,
                dingtalk_enabled, dingtalk_access_token, dingtalk_secret, dingtalk_host,
                datetime.now()
            ))
            logger.info("Notification settings updated successfully")
        else:
            db.execute('''
                INSERT INTO notification_settings
                (id, enabled, telegram_enabled, telegram_bot_token, telegram_user_id, telegram_host,
                 wechat_enabled, wechat_webhook_key, wechat_host,
                 wxpusher_enabled, wxpusher_app_token, wxpusher_uid, wxpusher_host,
                 dingtalk_enabled, dingtalk_access_token, dingtalk_secret, dingtalk_host)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                enabled, telegram_enabled, telegram_bot_token, telegram_user_id, telegram_host,
                wechat_enabled, wechat_webhook_key, wechat_host,
                wxpusher_enabled, wxpusher_app_token, wxpusher_uid, wxpusher_host,
                dingtalk_enabled, dingtalk_access_token, dingtalk_secret, dingtalk_host
            ))
            logger.info("Notification settings created successfully")

        data_cache.invalidate_pattern('notification')

        updated_settings = db.fetchone('SELECT * FROM notification_settings WHERE id = 1')
        logger.info(f"Verified settings after update: {updated_settings}")

        return jsonify({'message': 'Notification settings updated successfully'})
    except Exception as e:
        logger.error(f"Update notification settings error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400


@notification_bp.route('/api/test/notification', methods=['POST'])
@token_required
def test_notification():
    """Test notification settings"""
    try:
        NotificationService.send_notification(
            "测试通知",
            "这是来自Leaflow自动签到系统的测试通知。如果您收到此消息，说明您的通知设置正常工作！",
            "系统测试"
        )
        return jsonify({'message': 'Test notification sent'})
    except Exception as e:
        logger.error(f"Test notification error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400
