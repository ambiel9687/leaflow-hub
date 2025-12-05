#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scheduler service for Leaflow Auto Check-in Control Panel
"""

import json
import time
import random
import threading
import traceback
from datetime import datetime

from config import logger, TIMEZONE
from database import db, account_cache
from .checkin_service import LeafLowCheckin
from .notification_service import NotificationService


class CheckinScheduler:
    """Check-in task scheduler"""

    def __init__(self):
        self.scheduler_thread = None
        self.running = False
        self.leaflow_checkin = LeafLowCheckin()
        self.checkin_tasks = {}
        self._cached_settings = None
        self._settings_cache_time = None
        # 余额定时刷新配置
        self.last_balance_refresh = None  # 上次刷新时间戳
        self.balance_refresh_interval = 2 * 60 * 60  # 2小时（秒）

    def _get_checkin_settings(self):
        """Get global checkin settings with cache"""
        now = time.time()
        # Cache settings for 60 seconds
        if self._cached_settings and self._settings_cache_time and (now - self._settings_cache_time) < 60:
            return self._cached_settings

        settings = db.fetchone('SELECT * FROM checkin_settings WHERE id = 1')
        if settings:
            self._cached_settings = settings
            self._settings_cache_time = now
            return settings

        # Return default settings
        return {
            'checkin_time': '05:30',
            'retry_count': 2,
            'random_delay_min': 0,
            'random_delay_max': 30
        }

    def start(self):
        """Start the scheduler"""
        if not self.running:
            self.running = True
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.scheduler_thread.start()
            logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Scheduler stopped")

    def _run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            try:
                now = datetime.now(TIMEZONE)
                current_date = now.date()

                accounts = account_cache.get_accounts()
                if accounts is None:
                    accounts_list = db.fetchall('SELECT * FROM accounts WHERE enabled = 1')
                    if accounts_list:
                        account_cache.update_cache(accounts_list)
                        accounts = accounts_list
                    else:
                        accounts = []

                for account in accounts:
                    try:
                        account_id = account['id']

                        last_checkin_date = account.get('last_checkin_date')
                        if last_checkin_date:
                            if isinstance(last_checkin_date, str):
                                last_checkin_date = datetime.strptime(last_checkin_date, '%Y-%m-%d').date()
                            if last_checkin_date == current_date:
                                continue

                        # Use global checkin settings
                        settings = self._get_checkin_settings()
                        checkin_time_str = settings.get('checkin_time', '05:30')
                        checkin_hour, checkin_minute = map(int, checkin_time_str.split(':'))
                        checkin_time = now.replace(hour=checkin_hour, minute=checkin_minute, second=0, microsecond=0)

                        # Check if current time is past the checkin time
                        if now >= checkin_time:
                            task_key = f"{account_id}_{current_date}"

                            if task_key not in self.checkin_tasks:
                                self.checkin_tasks[task_key] = {
                                    'last_check': None,
                                    'completed': False,
                                    'retry_count': 0
                                }

                            task = self.checkin_tasks[task_key]

                            # Only trigger once per day (no check_interval needed)
                            if not task['completed'] and task['last_check'] is None:
                                task['last_check'] = now
                                threading.Thread(
                                    target=self.perform_checkin_with_delay,
                                    args=(account_id, task_key),
                                    daemon=True
                                ).start()
                    except Exception as e:
                        logger.error(f"Error processing account {account.get('id', 'unknown')}: {e}")
                        continue

                expired_keys = []
                for key in self.checkin_tasks:
                    if not key.endswith(str(current_date)):
                        expired_keys.append(key)
                for key in expired_keys:
                    del self.checkin_tasks[key]

                # 每2小时刷新所有账号余额
                self._periodic_balance_refresh()

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                logger.error(traceback.format_exc())

            time.sleep(30)

    def perform_checkin_with_delay(self, account_id, task_key):
        """Perform check-in with random delay"""
        try:
            # Use global settings for random delay
            settings = self._get_checkin_settings()
            delay_min = settings.get('random_delay_min', 0)
            delay_max = settings.get('random_delay_max', 30)
            delay = random.randint(delay_min, delay_max)
            logger.info(f"Account {account_id} waiting {delay}s before checkin (range: {delay_min}-{delay_max}s)")
            time.sleep(delay)

            success = self.perform_checkin(account_id)

            if task_key in self.checkin_tasks:
                self.checkin_tasks[task_key]['completed'] = success

        except Exception as e:
            logger.error(f"Checkin with delay error: {e}")
            logger.error(traceback.format_exc())

    def perform_checkin(self, account_id, retry_attempt=0):
        """Perform check-in for an account with retry mechanism"""
        try:
            account = db.fetchone('SELECT * FROM accounts WHERE id = ?', (account_id,))
            if not account or not account.get('enabled'):
                return False

            current_date = datetime.now(TIMEZONE).date()

            existing_checkin = db.fetchone('''
                SELECT id FROM checkin_history
                WHERE account_id = ? AND checkin_date = ?
            ''', (account_id, current_date))

            if existing_checkin:
                logger.info(f"Account {account['name']} already checked in today")
                return True

            token_data = json.loads(account['token_data'])

            session = self.leaflow_checkin.create_session(token_data)

            auth_result = self.leaflow_checkin.test_authentication(session, account['name'])
            if not auth_result[0]:
                success = False
                message = f"Authentication failed: {auth_result[1]}"
            else:
                success, message = self.leaflow_checkin.perform_checkin(session, account['name'])

            # Use global settings for retry count
            settings = self._get_checkin_settings()
            retry_count = settings.get('retry_count', 2)
            if not success and retry_attempt < retry_count:
                logger.info(f"Retrying checkin for {account['name']} (attempt {retry_attempt + 1}/{retry_count})")
                time.sleep(5)
                return self.perform_checkin(account_id, retry_attempt + 1)

            db.execute('''
                INSERT INTO checkin_history (account_id, success, message, checkin_date, retry_times)
                VALUES (?, ?, ?, ?, ?)
            ''', (account_id, success, message, current_date, retry_attempt))

            if success:
                db.execute('''
                    UPDATE accounts SET last_checkin_date = ?
                    WHERE id = ?
                ''', (current_date, account_id))
                account_cache.refresh_from_db(db)

                # 签到成功后刷新余额信息
                self._refresh_balance_after_checkin(session, account_id, account['name'])

            logger.info(f"Check-in for {account['name']}: {'Success' if success else 'Failed'} - {message}")

            notification_title = f"Leaflow签到结果 - {account['name']}"
            status_emoji = '✅' if success else '❌'
            notification_content = f"状态: {status_emoji} {'成功' if success else '失败'}\n消息: {message}\n重试次数: {retry_attempt}"
            NotificationService.send_notification(notification_title, notification_content, account['name'])

            return success

        except Exception as e:
            logger.error(f"Check-in error for account {account_id}: {e}")
            logger.error(traceback.format_exc())

            try:
                account = db.fetchone('SELECT name FROM accounts WHERE id = ?', (account_id,))
                if account:
                    NotificationService.send_notification(
                        f"Leaflow签到错误 - {account['name']}",
                        f"错误: {str(e)}",
                        account['name']
                    )
            except:
                pass

            return False

    def _refresh_balance_after_checkin(self, session, account_id, account_name):
        """签到成功后刷新余额（不影响签到流程）"""
        try:
            from .balance_service import BalanceService
            BalanceService.refresh_account_balance(db, session, account_id, account_name)
        except Exception as e:
            # 余额刷新失败不影响签到结果
            logger.error(f"[{account_name}] Balance refresh error after checkin: {e}")

    def _periodic_balance_refresh(self):
        """定期刷新所有账号余额（每2小时）"""
        now = time.time()

        # 检查是否到达刷新时间
        if self.last_balance_refresh and (now - self.last_balance_refresh) < self.balance_refresh_interval:
            return

        self.last_balance_refresh = now
        logger.info("Starting periodic balance refresh for all accounts...")

        # 在后台线程中执行，避免阻塞主调度器
        threading.Thread(target=self._refresh_all_balances, daemon=True).start()

    def _refresh_all_balances(self):
        """刷新所有启用账号的余额"""
        from .balance_service import BalanceService

        try:
            accounts = db.fetchall('SELECT * FROM accounts WHERE enabled = 1')

            if not accounts:
                logger.info("No enabled accounts to refresh balance")
                return

            success_count = 0
            fail_count = 0

            for account in accounts:
                try:
                    token_data = json.loads(account['token_data'])
                    session = self.leaflow_checkin.create_session(token_data)

                    success, _ = BalanceService.refresh_account_balance(
                        db, session, account['id'], account['name']
                    )

                    if success:
                        success_count += 1
                    else:
                        fail_count += 1

                    # 每个账号间随机等待 500-1500ms，避免请求过快
                    time.sleep(random.uniform(0.5, 1.5))

                except Exception as e:
                    fail_count += 1
                    logger.error(f"Refresh balance error for {account['name']}: {e}")

            logger.info(f"Periodic balance refresh completed: {success_count} success, {fail_count} failed")

        except Exception as e:
            logger.error(f"Refresh all balances error: {e}")
            logger.error(traceback.format_exc())


# Initialize scheduler instance
scheduler = CheckinScheduler()
