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

                        start_time_str = account.get('checkin_time_start', '06:30')
                        end_time_str = account.get('checkin_time_end', '06:40')
                        check_interval = account.get('check_interval', 60)

                        start_hour, start_minute = map(int, start_time_str.split(':'))
                        end_hour, end_minute = map(int, end_time_str.split(':'))

                        start_time = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
                        end_time = now.replace(hour=end_hour, minute=end_minute, second=59, microsecond=999999)

                        if start_time <= now <= end_time:
                            task_key = f"{account_id}_{current_date}"

                            if task_key not in self.checkin_tasks:
                                self.checkin_tasks[task_key] = {
                                    'last_check': None,
                                    'completed': False,
                                    'retry_count': 0
                                }

                            task = self.checkin_tasks[task_key]

                            if not task['completed']:
                                if task['last_check'] is None or \
                                   (now - task['last_check']).total_seconds() >= check_interval:
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

            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                logger.error(traceback.format_exc())

            time.sleep(30)

    def perform_checkin_with_delay(self, account_id, task_key):
        """Perform check-in with random delay"""
        try:
            delay = random.randint(0, 30)
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

            retry_count = account.get('retry_count', 2)
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


# Initialize scheduler instance
scheduler = CheckinScheduler()
