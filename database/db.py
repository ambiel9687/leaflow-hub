#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database module for Leaflow Auto Check-in Control Panel
"""

import os
import sqlite3
import threading
import time
import traceback

from config import (
    DB_TYPE, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    MAX_MYSQL_RETRIES, DATA_DIR, logger
)
from .cache import data_cache, account_cache


class Database:
    def __init__(self):
        self.lock = threading.Lock()
        self.conn = None
        self.pool = None
        self.last_ping = time.time()
        self.last_actual_ping = time.time()
        self.ping_check_interval = 300  # Check every 5 minutes
        self.ping_actual_interval = 1800  # 30 minutes actual ping interval
        self.db_type = None
        self.retry_count = 0
        self.max_retries = MAX_MYSQL_RETRIES
        self.connect()
        self.init_tables()
        self.start_keepalive()

    def start_keepalive(self):
        """Start MySQL keepalive thread"""
        if self.db_type == 'mysql':
            thread = threading.Thread(target=self._keepalive_worker, daemon=True)
            thread.start()
            logger.info("MySQL intelligent keepalive thread started")

    def _keepalive_worker(self):
        """Intelligent keepalive worker thread"""
        while True:
            try:
                time.sleep(self.ping_check_interval)

                with self.lock:
                    if self.conn and self.db_type == 'mysql':
                        current_time = time.time()
                        if current_time - self.last_actual_ping >= self.ping_actual_interval:
                            try:
                                self.conn.ping(reconnect=True)
                                self.last_actual_ping = current_time
                                logger.debug("MySQL keepalive ping executed (30min interval)")
                            except Exception as e:
                                logger.error(f"MySQL ping failed, reconnecting: {e}")
                                self.reconnect_with_retry()
                                self.last_actual_ping = current_time
                        else:
                            remaining = self.ping_actual_interval - (current_time - self.last_actual_ping)
                            logger.debug(f"Keepalive check: Next ping in {remaining:.0f} seconds")

            except Exception as e:
                logger.error(f"Keepalive worker error: {e}")

    def _ensure_connection(self):
        """Ensure connection is available (smart ping)"""
        if self.db_type == 'mysql':
            current_time = time.time()
            if current_time - self.last_actual_ping >= self.ping_actual_interval:
                try:
                    self.conn.ping(reconnect=True)
                    self.last_actual_ping = current_time
                    logger.debug("Connection ping on query execution")
                except Exception as e:
                    logger.error(f"Connection ping failed: {e}")
                    self.reconnect_with_retry()
                    self.last_actual_ping = current_time

    def calculate_retry_delay(self, attempt):
        """Calculate retry delay (exponential backoff)"""
        base_delay = 3
        max_delay = 24
        delay = min(base_delay * (2 ** attempt), max_delay)
        return delay

    def reconnect_with_retry(self):
        """Reconnect to MySQL using exponential backoff strategy"""
        if self.db_type != 'mysql':
            self.reconnect()
            return

        for attempt in range(self.max_retries):
            try:
                logger.info(f"MySQL reconnection attempt {attempt + 1}/{self.max_retries}")

                if self.conn:
                    try:
                        self.conn.close()
                    except:
                        pass

                import pymysql
                self.conn = pymysql.connect(
                    host=DB_HOST,
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    charset='utf8mb4',
                    autocommit=True,
                    connect_timeout=10,
                    read_timeout=30,
                    write_timeout=30,
                    max_allowed_packet=64*1024*1024
                )

                self.last_actual_ping = time.time()
                self.retry_count = 0

                data_cache.invalidate()
                account_cache.invalidate()

                logger.info("MySQL reconnected successfully, cache cleared")
                return

            except Exception as e:
                logger.error(f"MySQL reconnection attempt {attempt + 1} failed: {e}")

                if attempt < self.max_retries - 1:
                    delay = self.calculate_retry_delay(attempt)
                    logger.info(f"Waiting {delay} seconds before next retry...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} MySQL reconnection attempts failed")
                    raise

    def reconnect(self):
        """Reconnect to database (legacy compatibility)"""
        try:
            if self.db_type == 'mysql':
                self.reconnect_with_retry()
            else:
                if self.conn:
                    try:
                        self.conn.close()
                    except:
                        pass
                self.connect()
                data_cache.invalidate()
                account_cache.invalidate()
                logger.info("Database reconnected successfully, cache cleared")
        except Exception as e:
            logger.error(f"Database reconnection failed: {e}")
            raise

    def connect(self):
        """Establish database connection with retry mechanism"""
        if DB_TYPE == 'mysql':
            import pymysql

            for attempt in range(self.max_retries):
                try:
                    logger.info(f"Connecting to MySQL: {DB_HOST}:{DB_PORT}/{DB_NAME} as {DB_USER} (attempt {attempt + 1}/{self.max_retries})")
                    self.conn = pymysql.connect(
                        host=DB_HOST,
                        port=DB_PORT,
                        user=DB_USER,
                        password=DB_PASSWORD,
                        database=DB_NAME,
                        charset='utf8mb4',
                        autocommit=True,
                        connect_timeout=10,
                        read_timeout=30,
                        write_timeout=30,
                        max_allowed_packet=64*1024*1024
                    )
                    self.db_type = 'mysql'
                    self.last_actual_ping = time.time()
                    self.retry_count = 0
                    logger.info("Successfully connected to MySQL database")
                    return

                except Exception as e:
                    logger.error(f"MySQL connection attempt {attempt + 1} failed: {e}")

                    if attempt < self.max_retries - 1:
                        delay = self.calculate_retry_delay(attempt)
                        logger.info(f"Waiting {delay} seconds before next retry...")
                        time.sleep(delay)
                    else:
                        logger.error("All MySQL connection attempts failed, falling back to SQLite")
                        os.makedirs(DATA_DIR, exist_ok=True)
                        self.conn = sqlite3.connect(f'{DATA_DIR}/leaflow_checkin.db', check_same_thread=False)
                        self.conn.row_factory = sqlite3.Row
                        self.db_type = 'sqlite'
                        logger.info("Successfully connected to SQLite database (fallback)")
        else:
            logger.info("Using SQLite database")
            os.makedirs(DATA_DIR, exist_ok=True)
            self.conn = sqlite3.connect(f'{DATA_DIR}/leaflow_checkin.db', check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.db_type = 'sqlite'
            logger.info("Successfully connected to SQLite database")

    def init_tables(self):
        """Initialize database tables"""
        with self.lock:
            try:
                cursor = self.conn.cursor()

                if self.db_type == 'mysql':
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS accounts (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            name VARCHAR(255) UNIQUE NOT NULL,
                            token_data TEXT NOT NULL,
                            enabled BOOLEAN DEFAULT TRUE,
                            checkin_time_start VARCHAR(5) DEFAULT '06:30',
                            checkin_time_end VARCHAR(5) DEFAULT '06:40',
                            check_interval INT DEFAULT 60,
                            retry_count INT DEFAULT 2,
                            last_checkin_date DATE DEFAULT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                        )
                    ''')

                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS checkin_history (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            account_id INT NOT NULL,
                            success BOOLEAN NOT NULL,
                            message TEXT,
                            checkin_date DATE NOT NULL,
                            retry_times INT DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
                            INDEX idx_checkin_date (checkin_date),
                            INDEX idx_account_date (account_id, checkin_date)
                        )
                    ''')

                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS notification_settings (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            enabled BOOLEAN DEFAULT FALSE,
                            telegram_enabled BOOLEAN DEFAULT FALSE,
                            telegram_bot_token VARCHAR(255) DEFAULT '',
                            telegram_user_id VARCHAR(255) DEFAULT '',
                            telegram_host VARCHAR(255) DEFAULT '',
                            wechat_enabled BOOLEAN DEFAULT FALSE,
                            wechat_webhook_key VARCHAR(255) DEFAULT '',
                            wechat_host VARCHAR(255) DEFAULT '',
                            wxpusher_enabled BOOLEAN DEFAULT FALSE,
                            wxpusher_app_token VARCHAR(255) DEFAULT '',
                            wxpusher_uid VARCHAR(255) DEFAULT '',
                            wxpusher_host VARCHAR(255) DEFAULT '',
                            dingtalk_enabled BOOLEAN DEFAULT FALSE,
                            dingtalk_access_token VARCHAR(255) DEFAULT '',
                            dingtalk_secret VARCHAR(255) DEFAULT '',
                            dingtalk_host VARCHAR(255) DEFAULT '',
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                        )
                    ''')

                    # Add new fields if not exist
                    new_fields = [
                        ("accounts", "retry_count", "INT DEFAULT 2"),
                        ("checkin_history", "retry_times", "INT DEFAULT 0"),
                        ("notification_settings", "telegram_enabled", "BOOLEAN DEFAULT FALSE"),
                        ("notification_settings", "telegram_host", "VARCHAR(255) DEFAULT ''"),
                        ("notification_settings", "wechat_enabled", "BOOLEAN DEFAULT FALSE"),
                        ("notification_settings", "wechat_host", "VARCHAR(255) DEFAULT ''"),
                        ("notification_settings", "wxpusher_enabled", "BOOLEAN DEFAULT FALSE"),
                        ("notification_settings", "wxpusher_app_token", "VARCHAR(255) DEFAULT ''"),
                        ("notification_settings", "wxpusher_uid", "VARCHAR(255) DEFAULT ''"),
                        ("notification_settings", "wxpusher_host", "VARCHAR(255) DEFAULT ''"),
                        ("notification_settings", "dingtalk_enabled", "BOOLEAN DEFAULT FALSE"),
                        ("notification_settings", "dingtalk_access_token", "VARCHAR(255) DEFAULT ''"),
                        ("notification_settings", "dingtalk_secret", "VARCHAR(255) DEFAULT ''"),
                        ("notification_settings", "dingtalk_host", "VARCHAR(255) DEFAULT ''")
                    ]

                    for table_name, field_name, field_type in new_fields:
                        try:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {field_name} {field_type}")
                        except:
                            pass

                else:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS accounts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name VARCHAR(255) UNIQUE NOT NULL,
                            token_data TEXT NOT NULL,
                            enabled BOOLEAN DEFAULT 1,
                            checkin_time_start VARCHAR(5) DEFAULT '06:30',
                            checkin_time_end VARCHAR(5) DEFAULT '06:40',
                            check_interval INTEGER DEFAULT 60,
                            retry_count INTEGER DEFAULT 2,
                            last_checkin_date DATE DEFAULT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')

                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS checkin_history (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            account_id INTEGER NOT NULL,
                            success BOOLEAN NOT NULL,
                            message TEXT,
                            checkin_date DATE NOT NULL,
                            retry_times INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
                        )
                    ''')

                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS notification_settings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            enabled BOOLEAN DEFAULT 0,
                            telegram_enabled BOOLEAN DEFAULT 0,
                            telegram_bot_token TEXT DEFAULT '',
                            telegram_user_id TEXT DEFAULT '',
                            telegram_host TEXT DEFAULT '',
                            wechat_enabled BOOLEAN DEFAULT 0,
                            wechat_webhook_key TEXT DEFAULT '',
                            wechat_host TEXT DEFAULT '',
                            wxpusher_enabled BOOLEAN DEFAULT 0,
                            wxpusher_app_token TEXT DEFAULT '',
                            wxpusher_uid TEXT DEFAULT '',
                            wxpusher_host TEXT DEFAULT '',
                            dingtalk_enabled BOOLEAN DEFAULT 0,
                            dingtalk_access_token TEXT DEFAULT '',
                            dingtalk_secret TEXT DEFAULT '',
                            dingtalk_host TEXT DEFAULT '',
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')

                # Initialize notification settings
                cursor.execute('SELECT COUNT(*) as cnt FROM notification_settings')
                result = cursor.fetchone()

                if self.db_type == 'mysql':
                    count = result[0] if result else 0
                else:
                    count = result['cnt'] if result else 0

                if count == 0:
                    if self.db_type == 'mysql':
                        cursor.execute('''
                            INSERT INTO notification_settings
                            (enabled) VALUES (FALSE)
                        ''')
                    else:
                        cursor.execute('''
                            INSERT INTO notification_settings
                            (enabled) VALUES (0)
                        ''')
                        self.conn.commit()

                logger.info("Database tables initialized successfully")

            except Exception as e:
                logger.error(f"Error initializing tables: {e}")
                logger.error(traceback.format_exc())
                raise

    def execute(self, query, params=None, use_cache=False, cache_key=None):
        """Execute a database query with connection retry and optional caching"""
        if use_cache and cache_key and query.strip().upper().startswith('SELECT'):
            cached_data = data_cache.get(cache_key)
            if cached_data is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_data

        with self.lock:
            max_retries = self.max_retries if self.db_type == 'mysql' else 3

            for attempt in range(max_retries):
                try:
                    if self.db_type == 'mysql':
                        self._ensure_connection()

                    cursor = self.conn.cursor()

                    if self.db_type == 'mysql' and query:
                        query = query.replace('?', '%s')

                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)

                    if self.db_type == 'sqlite':
                        self.conn.commit()

                    if use_cache and cache_key and query.strip().upper().startswith('SELECT'):
                        data_cache.set(cache_key, cursor)

                    if self.db_type == 'mysql':
                        self.retry_count = 0

                    return cursor

                except Exception as e:
                    logger.error(f"Database execute error (attempt {attempt + 1}): {e}")

                    if self.db_type == 'mysql' and attempt < max_retries - 1:
                        delay = self.calculate_retry_delay(attempt)
                        logger.info(f"Retrying database operation in {delay} seconds...")
                        time.sleep(delay)

                        try:
                            self.reconnect_with_retry()
                        except:
                            pass
                    elif attempt == max_retries - 1:
                        raise

    def fetchone(self, query, params=None, use_cache=False):
        """Fetch one row from database with optional caching"""
        cache_key = None
        if use_cache:
            cache_key = f"fetchone_{hash(query)}_{hash(str(params))}"
            cached_data = data_cache.get(cache_key)
            if cached_data is not None:
                return cached_data

        cursor = self.execute(query, params)
        result = cursor.fetchone()

        if result:
            if self.db_type == 'mysql':
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    if isinstance(result, tuple):
                        result = dict(zip(columns, result))
            elif self.db_type == 'sqlite':
                result = dict(result) if result else None

        if use_cache and cache_key:
            data_cache.set(cache_key, result)

        return result

    def fetchall(self, query, params=None, use_cache=False):
        """Fetch all rows from database with optional caching"""
        cache_key = None
        if use_cache:
            cache_key = f"fetchall_{hash(query)}_{hash(str(params))}"
            cached_data = data_cache.get(cache_key)
            if cached_data is not None:
                return cached_data

        cursor = self.execute(query, params)
        results = cursor.fetchall()

        if results:
            if self.db_type == 'mysql':
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    results = [dict(zip(columns, row)) for row in results]
            elif self.db_type == 'sqlite':
                results = [dict(row) for row in results]

        results = results or []

        if use_cache and cache_key:
            data_cache.set(cache_key, results)

        return results

    def __del__(self):
        """Cleanup connection"""
        try:
            if self.conn:
                self.conn.close()
        except:
            pass


# Initialize database instance
try:
    db = Database()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise
