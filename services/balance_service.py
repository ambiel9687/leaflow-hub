#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Balance service for Leaflow Auto Check-in Control Panel
Handles fetching and parsing balance information from Leaflow
"""

import re
import json
import html
from datetime import datetime

from config import logger


def convert_iso_datetime(iso_str):
    """将 ISO 8601 日期格式转换为 MySQL 兼容格式"""
    if not iso_str:
        return ''
    try:
        # 处理 2025-08-09T05:51:00.000000Z 格式
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, AttributeError):
        return iso_str


class BalanceService:
    """余额信息获取与解析服务"""

    BALANCE_URL = "https://leaflow.net/balance/records"

    @staticmethod
    def fetch_balance_info(session):
        """
        从 balance/records 页面获取余额信息

        Args:
            session: 已认证的 requests.Session 对象

        Returns:
            tuple: (success: bool, data: dict | error_msg: str)
        """
        try:
            response = session.get(BalanceService.BALANCE_URL, timeout=30)

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            return BalanceService.parse_balance_data(response.text)

        except Exception as e:
            logger.error(f"Fetch balance error: {e}")
            return False, str(e)

    @staticmethod
    def parse_balance_data(html_content):
        """
        解析 HTML 中 data-page 属性的 JSON 数据

        Args:
            html_content: HTML 页面内容

        Returns:
            tuple: (success: bool, data: dict | error_msg: str)
        """
        try:
            # 匹配 data-page 属性
            pattern = r'data-page="([^"]+)"'
            match = re.search(pattern, html_content)

            if not match:
                return False, "data-page attribute not found"

            # HTML 实体解码
            json_str = html.unescape(match.group(1))
            data = json.loads(json_str)

            # 提取用户信息: props.auth.user
            user = data.get('props', {}).get('auth', {}).get('user')

            if not user:
                return False, "User data not found in response"

            balance_info = {
                'leaflow_uid': user.get('id'),
                'leaflow_name': user.get('name', ''),
                'leaflow_email': user.get('email', ''),
                'leaflow_created_at': convert_iso_datetime(user.get('created_at', '')),
                'current_balance': user.get('current_balance', '0'),
                'total_consumed': user.get('total_consumed', '0')
            }

            return True, balance_info

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return False, f"JSON parse error: {e}"
        except Exception as e:
            logger.error(f"Parse balance data error: {e}")
            return False, str(e)
