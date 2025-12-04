#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check-in service for Leaflow Auto Check-in Control Panel
"""

import re
import requests

from config import logger


class LeafLowCheckin:
    """Leaflow check-in service"""

    def __init__(self):
        self.checkin_url = "https://checkin.leaflow.net"
        self.main_site = "https://leaflow.net"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    def create_session(self, token_data):
        """Create session with authentication"""
        session = requests.Session()

        session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        if 'cookies' in token_data:
            for name, value in token_data['cookies'].items():
                session.cookies.set(name, value)

        if 'headers' in token_data:
            session.headers.update(token_data['headers'])

        return session

    def test_authentication(self, session, account_name):
        """Test if authentication is valid"""
        try:
            test_urls = [
                f"{self.main_site}/dashboard",
                f"{self.main_site}/profile",
                f"{self.main_site}/user",
                self.checkin_url,
            ]

            for url in test_urls:
                response = session.get(url, timeout=30)

                if response.status_code == 200:
                    content = response.text.lower()
                    if any(indicator in content for indicator in ['dashboard', 'profile', 'user', 'logout', 'welcome']):
                        logger.info(f"✅ [{account_name}] Authentication valid")
                        return True, "Authentication successful"
                elif response.status_code in [301, 302, 303]:
                    location = response.headers.get('location', '')
                    if 'login' not in location.lower():
                        logger.info(f"✅ [{account_name}] Authentication valid (redirect)")
                        return True, "Authentication successful (redirect)"

            return False, "Authentication failed - no valid authenticated pages found"

        except Exception as e:
            return False, f"Authentication test error: {str(e)}"

    def perform_checkin(self, session, account_name):
        """Perform check-in"""
        logger.info(f"🎯 [{account_name}] Performing checkin...")

        try:
            response = session.get(self.checkin_url, timeout=30)

            if response.status_code == 200:
                result = self.analyze_and_checkin(session, response.text, self.checkin_url, account_name)
                if result[0]:
                    return result

            api_endpoints = [
                f"{self.checkin_url}/api/checkin",
                f"{self.checkin_url}/checkin",
                f"{self.main_site}/api/checkin",
                f"{self.main_site}/checkin"
            ]

            for endpoint in api_endpoints:
                try:
                    response = session.get(endpoint, timeout=30)
                    if response.status_code == 200:
                        success, message = self.check_checkin_response(response.text)
                        if success:
                            return True, message

                    response = session.post(endpoint, data={'checkin': '1'}, timeout=30)
                    if response.status_code == 200:
                        success, message = self.check_checkin_response(response.text)
                        if success:
                            return True, message

                except Exception as e:
                    logger.debug(f"[{account_name}] API endpoint {endpoint} failed: {str(e)}")
                    continue

            return False, "All checkin methods failed"

        except Exception as e:
            return False, f"Checkin error: {str(e)}"

    def analyze_and_checkin(self, session, html_content, page_url, account_name):
        """Analyze page and perform check-in"""
        if self.already_checked_in(html_content):
            return True, "Already checked in today"

        if not self.is_checkin_page(html_content):
            return False, "Not a checkin page"

        try:
            checkin_data = {'checkin': '1', 'action': 'checkin', 'daily': '1'}

            csrf_token = self.extract_csrf_token(html_content)
            if csrf_token:
                checkin_data['_token'] = csrf_token
                checkin_data['csrf_token'] = csrf_token

            response = session.post(page_url, data=checkin_data, timeout=30)

            if response.status_code == 200:
                return self.check_checkin_response(response.text)

        except Exception as e:
            logger.debug(f"[{account_name}] POST checkin failed: {str(e)}")

        return False, "Failed to perform checkin"

    def already_checked_in(self, html_content):
        """Check if already checked in"""
        content_lower = html_content.lower()
        indicators = [
            'already checked in', '今日已签到', 'checked in today',
            'attendance recorded', '已完成签到', 'completed today'
        ]
        return any(indicator in content_lower for indicator in indicators)

    def is_checkin_page(self, html_content):
        """Check if it's a check-in page"""
        content_lower = html_content.lower()
        indicators = ['check-in', 'checkin', '签到', 'attendance', 'daily']
        return any(indicator in content_lower for indicator in indicators)

    def extract_csrf_token(self, html_content):
        """Extract CSRF token"""
        patterns = [
            r'name=["\']_token["\'][^>]*value=["\']([^"\']+)["\']',
            r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)["\']',
            r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def check_checkin_response(self, html_content):
        """Check check-in response"""
        content_lower = html_content.lower()

        success_indicators = [
            'check-in successful', 'checkin successful', '签到成功',
            'attendance recorded', 'earned reward', '获得奖励',
            'success', '成功', 'completed'
        ]

        if any(indicator in content_lower for indicator in success_indicators):
            reward_patterns = [
                r'获得奖励[^\d]*(\d+\.?\d*)\s*元',
                r'earned.*?(\d+\.?\d*)\s*(credits?|points?)',
                r'(\d+\.?\d*)\s*(credits?|points?|元)'
            ]

            for pattern in reward_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    reward = match.group(1)
                    return True, f"Check-in successful! Earned {reward} credits"

            return True, "Check-in successful!"

        return False, "Checkin response indicates failure"
