#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cache classes for Leaflow Auto Check-in Control Panel
"""

import threading
import time
from config import logger


class AccountCache:
    """Account cache with 5-minute expiration"""

    def __init__(self):
        self.cache = {}
        self.last_update = None
        self.cache_duration = 300  # 5 minutes cache
        self.lock = threading.Lock()

    def get_accounts(self, force_refresh=False):
        """Get cached accounts list"""
        with self.lock:
            now = time.time()
            if force_refresh or not self.last_update or (now - self.last_update) > self.cache_duration:
                return None
            return list(self.cache.values())

    def update_cache(self, accounts):
        """Update cache with accounts"""
        with self.lock:
            self.cache = {acc['id']: acc for acc in accounts}
            self.last_update = time.time()

    def invalidate(self):
        """Invalidate cache"""
        with self.lock:
            self.cache = {}
            self.last_update = None

    def refresh_from_db(self, db):
        """Refresh cache from database"""
        try:
            accounts_list = db.fetchall('SELECT * FROM accounts WHERE enabled = 1')
            if accounts_list:
                self.update_cache(accounts_list)
                logger.info(f"Account cache refreshed with {len(accounts_list)} accounts")
            else:
                self.invalidate()
        except Exception as e:
            logger.error(f"Error refreshing account cache: {e}")


class DataCache:
    """Generic data cache with configurable expiration"""

    def __init__(self, cache_duration=300):
        self.cache = {}
        self.cache_duration = cache_duration
        self.lock = threading.Lock()

    def get(self, key):
        """Get cached data"""
        with self.lock:
            if key in self.cache:
                data, timestamp = self.cache[key]
                if time.time() - timestamp < self.cache_duration:
                    return data
                else:
                    del self.cache[key]
            return None

    def set(self, key, data):
        """Set cache data"""
        with self.lock:
            self.cache[key] = (data, time.time())

    def invalidate(self, key=None):
        """Invalidate cache"""
        with self.lock:
            if key:
                self.cache.pop(key, None)
            else:
                self.cache.clear()

    def invalidate_pattern(self, pattern):
        """Invalidate cache entries matching pattern"""
        with self.lock:
            keys_to_remove = [k for k in self.cache.keys() if pattern in k]
            for key in keys_to_remove:
                self.cache.pop(key, None)


# Initialize cache instances
account_cache = AccountCache()
data_cache = DataCache(cache_duration=60)  # 1 minute cache
