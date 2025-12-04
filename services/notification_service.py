#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notification service for Leaflow Auto Check-in Control Panel
"""

import json
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime

import requests

from config import logger, TIMEZONE
from database import db


class NotificationService:
    """Service for sending notifications through multiple channels"""

    @staticmethod
    def send_notification(title, content, account_name=None):
        """Send notification through configured channels"""
        try:
            settings = db.fetchone('SELECT * FROM notification_settings WHERE id = 1')
            if not settings or not settings.get('enabled'):
                logger.info("Notifications disabled")
                return

            # Send Telegram notification
            if settings.get('telegram_enabled') and settings.get('telegram_bot_token') and settings.get('telegram_user_id'):
                NotificationService.send_telegram(
                    settings['telegram_bot_token'],
                    settings['telegram_user_id'],
                    title,
                    content,
                    settings.get('telegram_host', '')
                )

            # Send WeChat Work notification
            if settings.get('wechat_enabled') and settings.get('wechat_webhook_key'):
                NotificationService.send_wechat(
                    settings['wechat_webhook_key'],
                    title,
                    content,
                    settings.get('wechat_host', '')
                )

            # Send WxPusher notification
            if settings.get('wxpusher_enabled') and settings.get('wxpusher_app_token') and settings.get('wxpusher_uid'):
                NotificationService.send_wxpusher(
                    settings['wxpusher_app_token'],
                    settings['wxpusher_uid'],
                    title,
                    content,
                    settings.get('wxpusher_host', '')
                )

            # Send DingTalk notification
            if settings.get('dingtalk_enabled') and settings.get('dingtalk_access_token') and settings.get('dingtalk_secret'):
                NotificationService.send_dingtalk(
                    settings['dingtalk_access_token'],
                    settings['dingtalk_secret'],
                    title,
                    content,
                    settings.get('dingtalk_host', '')
                )

        except Exception as e:
            logger.error(f"Notification error: {e}")

    @staticmethod
    def send_telegram(token, chat_id, title, content, custom_host=''):
        """Send Telegram notification"""
        try:
            base_url = custom_host.rstrip('/') if custom_host else "https://api.telegram.org"
            url = f"{base_url}/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": f"📢 {title}\n\n{content}",
                "disable_web_page_preview": True
            }

            response = requests.post(url=url, data=data, timeout=30)
            result = response.json()

            if result.get("ok"):
                logger.info("Telegram notification sent successfully")
            else:
                logger.error(f"Telegram notification failed: {result.get('description')}")
        except Exception as e:
            logger.error(f"Telegram notification error: {e}")

    @staticmethod
    def send_wechat(webhook_key, title, content, custom_host=''):
        """Send WeChat Work notification"""
        try:
            base_url = custom_host.rstrip('/') if custom_host else "https://qyapi.weixin.qq.com"
            url = f"{base_url}/cgi-bin/webhook/send?key={webhook_key}"
            headers = {"Content-Type": "application/json;charset=utf-8"}
            data = {"msgtype": "text", "text": {"content": f"【{title}】\n\n{content}"}}

            response = requests.post(
                url=url,
                data=json.dumps(data),
                headers=headers,
                timeout=15
            ).json()

            if response.get("errcode") == 0:
                logger.info("WeChat Work notification sent successfully")
            else:
                logger.error(f"WeChat Work notification failed: {response.get('errmsg')}")
        except Exception as e:
            logger.error(f"WeChat Work notification error: {e}")

    @staticmethod
    def send_wxpusher(app_token, uid, title, content, custom_host=''):
        """Send WxPusher notification"""
        try:
            base_url = custom_host.rstrip('/') if custom_host else "https://wxpusher.zjiecode.com"
            url = f"{base_url}/api/send/message"

            html_content = f"""
            <div style="padding: 10px; color: #2c3e50; background: #ffffff;">
                <h2 style="color: inherit; margin: 0;">{title}</h2>
                <div style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 5px; color: #2c3e50;">
                    <pre style="white-space: pre-wrap; word-wrap: break-word; margin: 0; color: inherit;">{content}</pre>
                </div>
                <div style="margin-top: 10px; color: #7f8c8d; font-size: 12px;">
                    发送时间: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}
                </div>
            </div>
            """

            data = {
                "appToken": app_token,
                "content": html_content,
                "summary": title[:20],
                "contentType": 2,
                "uids": [uid],
                "verifyPayType": 0
            }

            response = requests.post(url, json=data, timeout=30)
            result = response.json()

            if result.get("code") == 1000:
                logger.info("WxPusher notification sent successfully")
            else:
                logger.error(f"WxPusher notification failed: {result.get('msg')}")
        except Exception as e:
            logger.error(f"WxPusher notification error: {e}")

    @staticmethod
    def send_dingtalk(access_token, secret, title, content, custom_host=''):
        """Send DingTalk robot notification"""
        try:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f'{timestamp}\n{secret}'
            hmac_code = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

            base_url = custom_host.rstrip('/') if custom_host else "https://oapi.dingtalk.com"
            url = f'{base_url}/robot/send?access_token={access_token}&timestamp={timestamp}&sign={sign}'

            data = {
                "msgtype": "text",
                "text": {
                    "content": f"【{title}】\n{content}"
                },
                "at": {
                    "isAtAll": False
                }
            }

            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, json=data, headers=headers, timeout=30)
            result = response.json()

            if result.get("errcode") == 0:
                logger.info("DingTalk notification sent successfully")
            else:
                logger.error(f"DingTalk notification failed: {result.get('errmsg')}")
        except Exception as e:
            logger.error(f"DingTalk notification error: {e}")
