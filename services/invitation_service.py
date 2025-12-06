#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Invitation code service for Leaflow Auto Check-in Control Panel
"""

import re
import json
import html
import traceback
from urllib.parse import unquote

from config import logger


class InvitationService:
    """邀请码服务"""

    INVITATION_LIST_URL = "https://leaflow.net/invitation-codes"
    INVITATION_CREATE_URL = "https://leaflow.net/api/invitation-codes"

    @staticmethod
    def get_invitation_codes(session):
        """
        获取邀请码列表

        Args:
            session: 已认证的 requests.Session 对象

        Returns:
            tuple: (success: bool, data: dict or str)
                   成功时 data 包含 { codes: [...], stats: {...} }
                   失败时 data 为错误信息
        """
        try:
            # 1. 先访问页面获取 version 和 cookies
            logger.info("Fetching invitation codes page...")
            response = session.get(InvitationService.INVITATION_LIST_URL, timeout=30)

            if response.status_code != 200:
                logger.error(f"Get invitation page failed: HTTP {response.status_code}")
                return False, f"获取页面失败: HTTP {response.status_code}"

            # 2. 清理并更新重复的 cookies
            InvitationService._cleanup_cookies(session, response)

            # 3. 解析 version
            version = InvitationService._extract_version(response.text)
            if not version:
                logger.error("Cannot extract version from page")
                return False, "无法获取页面版本信息"
            logger.info(f"Got version: {version}")

            # 4. 获取 XSRF-TOKEN
            xsrf_token = InvitationService._get_xsrf_token(session, response)
            if not xsrf_token:
                logger.error("Cannot get XSRF-TOKEN")
                return False, "无法获取 XSRF-TOKEN"

            # 5. 发送 Inertia AJAX 请求
            headers = {
                'x-inertia': 'true',
                'x-inertia-version': version,
                'x-xsrf-token': xsrf_token,
                'x-requested-with': 'XMLHttpRequest',
                'accept': 'text/html, application/xhtml+xml',
            }

            ajax_response = session.get(
                InvitationService.INVITATION_LIST_URL,
                headers=headers,
                timeout=30
            )

            if ajax_response.status_code != 200:
                logger.error(f"Get invitation codes failed: HTTP {ajax_response.status_code}")
                return False, f"获取邀请码失败: HTTP {ajax_response.status_code}"

            # 6. 解析响应
            return InvitationService._parse_invitation_response(ajax_response.text)

        except Exception as e:
            logger.error(f"Get invitation codes error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, f"获取邀请码失败: {str(e)}"

    @staticmethod
    def create_invitation_code(session, max_uses=1, note=""):
        """
        创建邀请码

        Args:
            session: 已认证的 requests.Session 对象
            max_uses: 最大使用次数，默认 1
            note: 备注，默认空

        Returns:
            tuple: (success: bool, data: dict or str)
                   成功时 data 包含新创建的邀请码信息
                   失败时 data 为错误信息
        """
        try:
            # 1. 先访问页面获取 version 和 cookies
            logger.info("Fetching invitation page for create...")
            response = session.get(InvitationService.INVITATION_LIST_URL, timeout=30)

            if response.status_code != 200:
                logger.error(f"Get invitation page failed: HTTP {response.status_code}")
                return False, f"获取页面失败: HTTP {response.status_code}"

            # 2. 清理并更新重复的 cookies
            InvitationService._cleanup_cookies(session, response)

            # 3. 解析 version
            version = InvitationService._extract_version(response.text)
            if not version:
                logger.error("Cannot extract version from page")
                return False, "无法获取页面版本信息"

            # 4. 获取 XSRF-TOKEN
            xsrf_token = InvitationService._get_xsrf_token(session, response)
            if not xsrf_token:
                logger.error("Cannot get XSRF-TOKEN")
                return False, "无法获取 XSRF-TOKEN"

            # 5. 发送创建请求
            headers = {
                'x-inertia': 'true',
                'x-inertia-version': version,
                'x-xsrf-token': xsrf_token,
                'x-requested-with': 'XMLHttpRequest',
                'content-type': 'application/json',
                'accept': 'application/json, text/plain, */*',
            }

            create_response = session.post(
                InvitationService.INVITATION_CREATE_URL,
                headers=headers,
                json={'max_uses': max_uses, 'note': note},
                timeout=30
            )

            logger.info(f"Create invitation code response status: {create_response.status_code}")

            if create_response.status_code not in (200, 201):
                logger.error(f"Create invitation code failed: HTTP {create_response.status_code}")
                # 尝试解析错误信息
                try:
                    error_data = create_response.json()
                    error_msg = error_data.get('message', str(error_data))
                    return False, f"创建失败: {error_msg}"
                except Exception:
                    return False, f"创建失败: HTTP {create_response.status_code}"

            # 6. 解析创建结果
            try:
                result = create_response.json()
                logger.info(f"Created invitation code: {result.get('code')}")
                return True, result
            except json.JSONDecodeError:
                logger.error("Cannot parse create response as JSON")
                return False, "响应解析失败"

        except Exception as e:
            logger.error(f"Create invitation code error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, f"创建邀请码失败: {str(e)}"

    @staticmethod
    def _cleanup_cookies(session, response):
        """清理并更新重复的 cookies"""
        for cookie_name in ['XSRF-TOKEN', 'leaflow_session', 'shared_api_cookie']:
            if cookie_name in response.cookies:
                for cookie in list(session.cookies):
                    if cookie.name == cookie_name:
                        session.cookies.clear(cookie.domain, cookie.path, cookie.name)
                session.cookies.set(cookie_name, response.cookies[cookie_name], domain='leaflow.net')

    @staticmethod
    def _get_xsrf_token(session, response):
        """获取 XSRF-TOKEN"""
        xsrf_token = response.cookies.get('XSRF-TOKEN')
        if not xsrf_token:
            cookies_dict = session.cookies.get_dict()
            xsrf_token = cookies_dict.get('XSRF-TOKEN')
        if xsrf_token:
            xsrf_token = unquote(xsrf_token)
        return xsrf_token

    @staticmethod
    def _extract_version(html_content):
        """从响应中提取 Inertia version"""
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
    def _parse_invitation_response(response_text):
        """解析邀请码列表响应"""
        try:
            data = json.loads(response_text)
            props = data.get('props', {})

            # 提取邀请码列表
            codes_data = props.get('codes', {})
            codes = codes_data.get('data', [])

            # 提取统计信息
            stats = props.get('stats', {})

            # 提取设置（价格等）
            settings = props.get('settings', {})

            result = {
                'codes': codes,
                'stats': {
                    'total': stats.get('total', 0),
                    'active': stats.get('active', 0),
                    'available': stats.get('available', 0),
                    'total_uses': stats.get('total_uses', 0)
                },
                'settings': {
                    'price': settings.get('price', 10),
                    'allow_user_generation': settings.get('allow_user_generation', True)
                },
                'pagination': {
                    'current_page': codes_data.get('current_page', 1),
                    'last_page': codes_data.get('last_page', 1),
                    'total': codes_data.get('total', 0)
                }
            }

            logger.info(f"Parsed {len(codes)} invitation codes, stats: {result['stats']}")
            return True, result

        except json.JSONDecodeError:
            if 'login' in response_text.lower():
                return False, "登录已过期，请更新 Cookie"
            return False, "响应解析失败"
        except Exception as e:
            logger.error(f"Parse invitation response error: {e}")
            return False, f"解析失败: {str(e)}"

    # ========== 数据库缓存方法 ==========

    @staticmethod
    def get_cached_codes(db, account_id):
        """
        从数据库获取缓存的邀请码列表

        Args:
            db: 数据库实例
            account_id: 账户 ID

        Returns:
            list: 邀请码列表，无缓存返回空列表
        """
        try:
            codes = db.fetchall(
                '''SELECT * FROM invitation_codes
                   WHERE account_id = ?
                   ORDER BY created_at DESC''',
                (account_id,)
            )
            return codes if codes else []
        except Exception as e:
            logger.error(f"Get cached invitation codes error: {e}")
            return []

    @staticmethod
    def save_codes_to_db(db, account_id, codes):
        """
        保存邀请码到数据库（UPSERT）

        Args:
            db: 数据库实例
            account_id: 账户 ID
            codes: 邀请码列表（来自 API 响应）
        """
        try:
            for code_data in codes:
                code = code_data.get('code')
                if not code:
                    continue

                # 检查是否已存在
                existing = db.fetchone(
                    'SELECT id FROM invitation_codes WHERE account_id = ? AND code = ?',
                    (account_id, code)
                )

                if existing:
                    # 更新现有记录
                    db.execute(
                        '''UPDATE invitation_codes SET
                           max_uses = ?,
                           used_count = ?,
                           remaining_uses = ?,
                           is_active = ?,
                           is_available = ?,
                           note = ?,
                           leaflow_id = ?,
                           updated_at = CURRENT_TIMESTAMP
                           WHERE account_id = ? AND code = ?''',
                        (
                            code_data.get('max_uses', 1),
                            code_data.get('used_count', 0),
                            code_data.get('remaining_uses', 1),
                            1 if code_data.get('is_active', True) else 0,
                            1 if code_data.get('is_available', True) else 0,
                            code_data.get('note', ''),
                            code_data.get('id'),
                            account_id,
                            code
                        )
                    )
                else:
                    # 插入新记录
                    db.execute(
                        '''INSERT INTO invitation_codes
                           (account_id, code, max_uses, used_count, remaining_uses,
                            is_active, is_available, note, leaflow_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (
                            account_id,
                            code,
                            code_data.get('max_uses', 1),
                            code_data.get('used_count', 0),
                            code_data.get('remaining_uses', 1),
                            1 if code_data.get('is_active', True) else 0,
                            1 if code_data.get('is_available', True) else 0,
                            code_data.get('note', ''),
                            code_data.get('id')
                        )
                    )

            logger.info(f"Saved {len(codes)} invitation codes for account {account_id}")
        except Exception as e:
            logger.error(f"Save invitation codes to DB error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

    @staticmethod
    def save_single_code(db, account_id, code_data):
        """
        保存单个新创建的邀请码到数据库

        Args:
            db: 数据库实例
            account_id: 账户 ID
            code_data: 邀请码数据（来自创建 API 响应）
        """
        try:
            code = code_data.get('code')
            if not code:
                return

            db.execute(
                '''INSERT INTO invitation_codes
                   (account_id, code, max_uses, used_count, remaining_uses,
                    is_active, is_available, note, leaflow_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    account_id,
                    code,
                    code_data.get('max_uses', 1),
                    code_data.get('used_count', 0),
                    code_data.get('remaining_uses', code_data.get('max_uses', 1)),
                    1 if code_data.get('is_active', True) else 0,
                    1 if code_data.get('is_available', True) else 0,
                    code_data.get('note', ''),
                    code_data.get('id')
                )
            )
            logger.info(f"Saved new invitation code {code} for account {account_id}")
        except Exception as e:
            logger.error(f"Save single invitation code error: {e}")

    @staticmethod
    def format_cached_codes(cached_codes):
        """
        将数据库缓存格式转换为 API 响应格式

        Args:
            cached_codes: 数据库查询结果

        Returns:
            list: 格式化的邀请码列表
        """
        result = []
        for row in cached_codes:
            result.append({
                'id': row.get('leaflow_id') or row.get('id'),
                'code': row.get('code'),
                'max_uses': row.get('max_uses') or 1,
                'used_count': row.get('used_count') or 0,
                'remaining_uses': row.get('remaining_uses') or 1,
                'is_active': bool(row.get('is_active', 1)),
                'is_available': bool(row.get('is_available', 1)),
                'note': row.get('note', ''),
                'created_at': row.get('created_at'),  # 创建时间
            })
        return result

    @staticmethod
    def calculate_stats(codes):
        """
        根据邀请码列表计算统计信息

        Args:
            codes: 邀请码列表

        Returns:
            dict: 统计信息
        """
        total = len(codes)
        active = sum(1 for c in codes if c.get('is_active', True))
        available = sum(1 for c in codes if c.get('is_available', True) and (c.get('remaining_uses') or 0) > 0)
        total_uses = sum(c.get('used_count') or 0 for c in codes)

        return {
            'total': total,
            'active': active,
            'available': available,
            'total_uses': total_uses
        }

    @staticmethod
    def update_sync_time(db, account_id):
        """
        更新账户的邀请码同步时间

        Args:
            db: 数据库实例
            account_id: 账户 ID
        """
        try:
            db.execute(
                'UPDATE accounts SET invitation_synced_at = CURRENT_TIMESTAMP WHERE id = ?',
                (account_id,)
            )
            logger.info(f"Updated invitation sync time for account {account_id}")
        except Exception as e:
            logger.error(f"Update invitation sync time error: {e}")

    @staticmethod
    def has_synced(db, account_id):
        """
        检查账户是否已同步过邀请码

        Args:
            db: 数据库实例
            account_id: 账户 ID

        Returns:
            bool: 是否已同步过
        """
        try:
            account = db.fetchone(
                'SELECT invitation_synced_at FROM accounts WHERE id = ?',
                (account_id,)
            )
            return account and account.get('invitation_synced_at') is not None
        except Exception as e:
            logger.error(f"Check invitation sync status error: {e}")
            return False
