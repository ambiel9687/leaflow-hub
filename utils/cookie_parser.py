#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cookie parser utility for Leaflow Auto Check-in Control Panel
"""

import json
import re


def parse_cookie_string(cookie_input):
    """Parse cookie string in various formats"""
    cookie_input = cookie_input.strip()

    # Try to parse as JSON first
    if cookie_input.startswith('{'):
        try:
            data = json.loads(cookie_input)
            if 'cookies' in data:
                return data
            else:
                return {'cookies': data}
        except json.JSONDecodeError:
            pass

    # Parse as semicolon-separated cookie string
    cookies = {}
    cookie_pairs = re.split(r';\s*', cookie_input)

    for pair in cookie_pairs:
        if '=' in pair:
            key, value = pair.split('=', 1)
            key = key.strip()
            value = value.strip()
            if key:
                cookies[key] = value

    if cookies:
        return {'cookies': cookies}

    raise ValueError("Invalid cookie format")
