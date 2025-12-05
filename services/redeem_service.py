#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redeem code service for Leaflow Auto Check-in Control Panel
"""

import re
import json
import html
import traceback
from urllib.parse import unquote

from config import logger


class RedeemService:
    """兑换码服务"""

    BALANCE_URL = "https://leaflow.net/balance"
    REDEEM_URL = "https://leaflow.net/balance/redeem"

    @staticmethod
    def redeem_code(session, code):
        """
        执行兑换码兑换

        Args:
            session: 已认证的 requests.Session 对象
            code: 兑换码字符串

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # 1. 记录请求前的 cookies 状态（调试用）
            logger.info(f"Session cookies before request: {list(session.cookies.keys())}")

            # 2. 获取 balance 页面
            response = session.get(RedeemService.BALANCE_URL, timeout=30)

            if response.status_code != 200:
                logger.error(f"Get balance page failed: HTTP {response.status_code}")
                return False, f"获取页面失败: HTTP {response.status_code}"

            # 3. 记录响应的 cookies（调试用）
            logger.info(f"Response cookies: {list(response.cookies.keys())}")
            logger.info(f"Session cookies after request: {list(session.cookies.keys())}")

            # 3.5 清理并更新重复的 cookies（修复 CSRF 验证失败问题）
            # requests.Session 在收到 Set-Cookie 时会追加而不是替换，导致 cookies 重复
            for cookie_name in ['XSRF-TOKEN', 'leaflow_session', 'shared_api_cookie']:
                if cookie_name in response.cookies:
                    # 遍历删除所有同名 cookie
                    for cookie in list(session.cookies):
                        if cookie.name == cookie_name:
                            session.cookies.clear(cookie.domain, cookie.path, cookie.name)
                    # 设置新的 cookie
                    session.cookies.set(cookie_name, response.cookies[cookie_name], domain='leaflow.net')
            logger.info(f"Session cookies after cleanup: {list(session.cookies.keys())}")

            # 4. 解析 version
            version = RedeemService._extract_version(response.text)
            if not version:
                logger.error("Cannot extract version from page")
                return False, "无法获取页面版本信息"
            logger.info(f"Got version: {version}")

            # 5. 获取最新的 XSRF-TOKEN（必须从响应的 cookies 获取）
            xsrf_token = response.cookies.get('XSRF-TOKEN')
            if xsrf_token:
                logger.info("Got XSRF-TOKEN from response cookies")
            else:
                # 如果响应中没有，从 session 获取
                cookies_dict = session.cookies.get_dict()
                xsrf_token = cookies_dict.get('XSRF-TOKEN')
                if xsrf_token:
                    logger.info("Got XSRF-TOKEN from session cookies dict")

            if not xsrf_token:
                logger.error("Cannot get XSRF-TOKEN")
                return False, "无法获取 XSRF-TOKEN"

            xsrf_token = unquote(xsrf_token)
            logger.info(f"Using XSRF-TOKEN: {xsrf_token[:30]}...")

            # 6. 发送兑换请求（使用 session 会自动携带更新后的 cookies）
            headers = {
                'x-inertia': 'true',
                'x-inertia-version': version,
                'x-xsrf-token': xsrf_token,
                'x-requested-with': 'XMLHttpRequest',
                'content-type': 'application/json',
            }

            logger.info(f"Sending redeem request with code: {code}")
            logger.info(f"Request headers: {headers}")

            redeem_response = session.post(
                RedeemService.REDEEM_URL,
                headers=headers,
                json={'code': code},
                timeout=30
            )
            logger.info(f"Redeem response status: {redeem_response.status_code}")

            # 7. 解析结果
            return RedeemService._parse_redeem_response(redeem_response.text)

        except Exception as e:
            logger.error(f"Redeem code error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, f"兑换失败: {str(e)}"

    @staticmethod
    def _extract_version(html_content):
        """从响应中提取 version"""
        try:
            # 方法1: 从 data-page JSON 中提取
            pattern = r'data-page="([^"]+)"'
            match = re.search(pattern, html_content)
            if match:
                json_str = html.unescape(match.group(1))
                data = json.loads(json_str)
                if data.get('version'):
                    return data['version']

            # 方法2: 直接匹配 version 字段
            version_pattern = r'"version"\s*:\s*"([a-f0-9]+)"'
            match = re.search(version_pattern, html_content)
            if match:
                return match.group(1)

            return None
        except Exception as e:
            logger.error(f"Extract version error: {e}")
            return None

    @staticmethod
    def _parse_redeem_response(response_text):
        """解析兑换响应"""
        try:
            # 尝试解析 JSON
            data = json.loads(response_text)
            flash = data.get('props', {}).get('flash', {})

            # 优先检查 success
            if flash.get('success'):
                return True, flash['success']

            # 检查 error
            if flash.get('error'):
                return False, flash['error']

            # 检查 message（通常是超时等错误）
            if flash.get('message'):
                return False, flash['message']

            return False, "未知响应"

        except json.JSONDecodeError:
            # 如果不是 JSON，可能是 HTML 错误页
            if 'login' in response_text.lower():
                return False, "登录已过期，请更新 Cookie"
            return False, "响应解析失败"
        except Exception as e:
            logger.error(f"Parse redeem response error: {e}")
            return False, f"解析失败: {str(e)}"

    @staticmethod
    def extract_amount(message):
        """
        从兑换成功消息中提取金额

        Args:
            message: 成功消息，如 "兑换成功！获得 ¥5.00000000 余额"

        Returns:
            str: 提取的金额字符串，如 "5.00000000"，失败返回空字符串
        """
        if not message:
            return ''

        # 匹配 ¥ 后面的数字
        match = re.search(r'¥?([\d.]+)', message)
        if match:
            return match.group(1)
        return ''
