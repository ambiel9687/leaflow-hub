#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch redeem scheduler service for Leaflow Auto Check-in Control Panel
"""

import json
import time
import threading
import traceback
from datetime import datetime, timedelta

from config import logger, TIMEZONE
from database import db, data_cache
from .redeem_service import RedeemService
from .checkin_service import LeafLowCheckin


class BatchRedeemScheduler:
    """批量兑换调度器"""

    SUCCESS_INTERVAL = 70 * 60  # 成功间隔 70 分钟
    FAIL_INTERVAL = 60          # 失败间隔 1 分钟
    CHECK_INTERVAL = 120         # 轮询间隔 120 秒

    def __init__(self):
        self.running = False
        self.scheduler_thread = None
        self.paused_tasks = set()  # 暂停的任务 ID 集合
        self.cancelled_tasks = set()  # 取消的任务 ID 集合
        self.leaflow_checkin = LeafLowCheckin()
        self._lock = threading.Lock()

    def start(self):
        """启动调度器"""
        if not self.running:
            self.running = True
            self.restore_tasks()
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()
            logger.info("Batch redeem scheduler started")

    def stop(self):
        """停止调度器"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Batch redeem scheduler stopped")

    def restore_tasks(self):
        """应用启动时恢复未完成任务"""
        try:
            tasks = db.fetchall('''
                SELECT * FROM batch_redeem_tasks
                WHERE status IN ('pending', 'running')
            ''')

            if not tasks:
                return

            for task in tasks:
                task_id = task['id']
                # pending 任务改为 running 并立即开始
                if task['status'] == 'pending':
                    now = datetime.now(TIMEZONE)
                    db.execute('''
                        UPDATE batch_redeem_tasks
                        SET status = 'running', next_execute_at = ?, updated_at = ?
                        WHERE id = ?
                    ''', (now, now, task_id))
                    logger.info(f"Restored pending batch task {task_id} -> running")
                else:
                    logger.info(f"Restored running batch task {task_id}, next_execute_at: {task.get('next_execute_at')}")

        except Exception as e:
            logger.error(f"Restore batch tasks error: {e}")
            logger.error(traceback.format_exc())

    def _scheduler_loop(self):
        """主调度循环"""
        while self.running:
            try:
                self._process_tasks()
            except Exception as e:
                logger.error(f"Batch redeem scheduler error: {e}")
                logger.error(traceback.format_exc())

            time.sleep(self.CHECK_INTERVAL)

    def _process_tasks(self):
        """处理所有待执行的任务"""
        now = datetime.now(TIMEZONE)

        # 查询需要执行的任务
        tasks = db.fetchall('''
            SELECT * FROM batch_redeem_tasks
            WHERE status = 'running'
            AND (next_execute_at IS NULL OR next_execute_at <= ?)
        ''', (now,))

        if not tasks:
            return

        for task in tasks:
            task_id = task['id']

            # 检查是否被暂停或取消
            with self._lock:
                if task_id in self.paused_tasks:
                    continue
                if task_id in self.cancelled_tasks:
                    self.cancelled_tasks.discard(task_id)
                    continue

            # 检查是否已完成
            current_index = task['current_index']
            total_count = task['total_count']

            if current_index >= total_count:
                self._complete_task(task_id)
                continue

            # 执行单次兑换
            threading.Thread(
                target=self._execute_single_redeem,
                args=(task,),
                daemon=True
            ).start()

    def _execute_single_redeem(self, task):
        """执行单次兑换"""
        task_id = task['id']
        account_id = task['account_id']
        current_index = task['current_index']

        try:
            # 解析兑换码列表
            codes = json.loads(task['codes'])
            if current_index >= len(codes):
                self._complete_task(task_id)
                return

            code = codes[current_index]
            logger.info(f"Batch task {task_id}: executing redeem {current_index + 1}/{len(codes)}, code: {code}")

            # 获取账户信息
            account = db.fetchone('SELECT * FROM accounts WHERE id = ?', (account_id,))
            if not account:
                logger.error(f"Batch task {task_id}: account {account_id} not found")
                self._fail_task(task_id, "账户不存在")
                return

            # 创建 session
            token_data = json.loads(account['token_data'])
            session = self.leaflow_checkin.create_session(token_data)

            # 执行兑换
            success, message = RedeemService.redeem_code(session, code)
            amount = RedeemService.extract_amount(message) if success else ''

            # 记录兑换历史
            db.execute('''
                INSERT INTO redeem_history (account_id, code, success, message, amount)
                VALUES (?, ?, ?, ?, ?)
            ''', (account_id, code, success, message, amount))

            logger.info(f"Batch task {task_id}: code {code} -> {'success' if success else 'failed'}: {message}")

            # 更新任务进度
            self._update_task_progress(task_id, success, current_index + 1, len(codes))

            # 刷新缓存
            data_cache.invalidate()

        except Exception as e:
            logger.error(f"Batch task {task_id} execute error: {e}")
            logger.error(traceback.format_exc())
            # 出错按失败处理
            self._update_task_progress(task_id, False, task['current_index'] + 1, task['total_count'])

    def _update_task_progress(self, task_id, success, new_index, total_count):
        """更新任务进度"""
        now = datetime.now(TIMEZONE)

        # 计算下次执行时间
        if new_index >= total_count:
            # 已完成所有兑换
            next_execute_at = None
            status = 'completed'
            completed_at = now
        else:
            # 根据成功/失败设置不同间隔
            interval = self.SUCCESS_INTERVAL if success else self.FAIL_INTERVAL
            next_execute_at = now + timedelta(seconds=interval)
            status = 'running'
            completed_at = None

        # 更新数据库
        if success:
            db.execute('''
                UPDATE batch_redeem_tasks
                SET current_index = ?, success_count = success_count + 1,
                    next_execute_at = ?, status = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
            ''', (new_index, next_execute_at, status, now, completed_at, task_id))
        else:
            db.execute('''
                UPDATE batch_redeem_tasks
                SET current_index = ?, fail_count = fail_count + 1,
                    next_execute_at = ?, status = ?, updated_at = ?, completed_at = ?
                WHERE id = ?
            ''', (new_index, next_execute_at, status, now, completed_at, task_id))

        if status == 'completed':
            logger.info(f"Batch task {task_id} completed")

    def _complete_task(self, task_id):
        """标记任务完成"""
        now = datetime.now(TIMEZONE)
        db.execute('''
            UPDATE batch_redeem_tasks
            SET status = 'completed', completed_at = ?, updated_at = ?
            WHERE id = ?
        ''', (now, now, task_id))
        logger.info(f"Batch task {task_id} marked as completed")

    def _fail_task(self, task_id, reason):
        """标记任务失败"""
        now = datetime.now(TIMEZONE)
        db.execute('''
            UPDATE batch_redeem_tasks
            SET status = 'cancelled', completed_at = ?, updated_at = ?
            WHERE id = ?
        ''', (now, now, task_id))
        logger.error(f"Batch task {task_id} failed: {reason}")

    # ============ 公开 API 方法 ============

    def create_task(self, account_id, codes):
        """
        创建批量兑换任务

        Args:
            account_id: 账户 ID
            codes: 兑换码列表

        Returns:
            dict: {'success': bool, 'task_id': int, 'message': str}
        """
        try:
            # 检查是否有未完成的任务
            existing = db.fetchone('''
                SELECT id FROM batch_redeem_tasks
                WHERE account_id = ? AND status IN ('pending', 'running', 'paused')
            ''', (account_id,))

            if existing:
                return {
                    'success': False,
                    'message': '该账户已有进行中的批量兑换任务',
                    'existing_task_id': existing['id']
                }

            now = datetime.now(TIMEZONE)
            codes_json = json.dumps(codes, ensure_ascii=False)

            db.execute('''
                INSERT INTO batch_redeem_tasks
                (account_id, status, codes, total_count, next_execute_at, created_at, updated_at)
                VALUES (?, 'running', ?, ?, ?, ?, ?)
            ''', (account_id, codes_json, len(codes), now, now, now))

            # 获取新创建的任务 ID
            task = db.fetchone('''
                SELECT id FROM batch_redeem_tasks
                WHERE account_id = ? AND status = 'running'
                ORDER BY id DESC LIMIT 1
            ''', (account_id,))

            task_id = task['id'] if task else None

            logger.info(f"Created batch redeem task {task_id} for account {account_id} with {len(codes)} codes")

            return {
                'success': True,
                'task_id': task_id,
                'total_count': len(codes),
                'message': '批量兑换任务已创建'
            }

        except Exception as e:
            logger.error(f"Create batch task error: {e}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'创建任务失败: {str(e)}'
            }

    def cancel_task(self, task_id):
        """取消任务"""
        try:
            task = db.fetchone('SELECT * FROM batch_redeem_tasks WHERE id = ?', (task_id,))
            if not task:
                return {'success': False, 'message': '任务不存在'}

            if task['status'] in ('completed', 'cancelled'):
                return {'success': False, 'message': '任务已结束'}

            with self._lock:
                self.cancelled_tasks.add(task_id)
                self.paused_tasks.discard(task_id)

            now = datetime.now(TIMEZONE)
            db.execute('''
                UPDATE batch_redeem_tasks
                SET status = 'cancelled', completed_at = ?, updated_at = ?
                WHERE id = ?
            ''', (now, now, task_id))

            logger.info(f"Batch task {task_id} cancelled")
            return {'success': True, 'message': '任务已取消'}

        except Exception as e:
            logger.error(f"Cancel batch task error: {e}")
            return {'success': False, 'message': f'取消失败: {str(e)}'}

    def pause_task(self, task_id):
        """暂停任务"""
        try:
            task = db.fetchone('SELECT * FROM batch_redeem_tasks WHERE id = ?', (task_id,))
            if not task:
                return {'success': False, 'message': '任务不存在'}

            if task['status'] != 'running':
                return {'success': False, 'message': '只能暂停运行中的任务'}

            with self._lock:
                self.paused_tasks.add(task_id)

            now = datetime.now(TIMEZONE)
            db.execute('''
                UPDATE batch_redeem_tasks
                SET status = 'paused', updated_at = ?
                WHERE id = ?
            ''', (now, task_id))

            logger.info(f"Batch task {task_id} paused")
            return {'success': True, 'message': '任务已暂停'}

        except Exception as e:
            logger.error(f"Pause batch task error: {e}")
            return {'success': False, 'message': f'暂停失败: {str(e)}'}

    def resume_task(self, task_id):
        """恢复任务"""
        try:
            task = db.fetchone('SELECT * FROM batch_redeem_tasks WHERE id = ?', (task_id,))
            if not task:
                return {'success': False, 'message': '任务不存在'}

            if task['status'] != 'paused':
                return {'success': False, 'message': '只能恢复暂停的任务'}

            with self._lock:
                self.paused_tasks.discard(task_id)

            now = datetime.now(TIMEZONE)
            db.execute('''
                UPDATE batch_redeem_tasks
                SET status = 'running', next_execute_at = ?, updated_at = ?
                WHERE id = ?
            ''', (now, now, task_id))

            logger.info(f"Batch task {task_id} resumed")
            return {'success': True, 'message': '任务已恢复'}

        except Exception as e:
            logger.error(f"Resume batch task error: {e}")
            return {'success': False, 'message': f'恢复失败: {str(e)}'}

    def get_task_status(self, account_id):
        """
        获取账户的批量兑换任务状态

        Returns:
            dict: 任务状态和进度信息
        """
        try:
            # 获取最新的任务（包括已完成的，便于查看历史）
            task = db.fetchone('''
                SELECT * FROM batch_redeem_tasks
                WHERE account_id = ?
                ORDER BY id DESC LIMIT 1
            ''', (account_id,))

            if not task:
                return {'task': None, 'progress': []}

            # 获取兑换码列表
            codes = json.loads(task['codes'])

            # 获取每个兑换码的执行结果（直接用 code 列表查询）
            codes_placeholder = ','.join(['?' for _ in codes])
            history = db.fetchall(f'''
                SELECT code, success, message, amount, created_at
                FROM redeem_history
                WHERE account_id = ?
                AND code IN ({codes_placeholder})
                ORDER BY created_at DESC
            ''', (account_id, *codes))

            # 构建兑换码结果映射
            history_map = {}
            for record in history:
                code = record['code']
                if code not in history_map:
                    history_map[code] = record

            # 格式化 next_execute_at
            next_execute_str = None
            if task['next_execute_at']:
                next_exec = task['next_execute_at']
                if isinstance(next_exec, datetime):
                    next_execute_str = next_exec.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    next_execute_str = str(next_exec).split('.')[0] if '.' in str(next_exec) else str(next_exec)

            # 构建进度列表
            progress = []
            for i, code in enumerate(codes):
                if code in history_map:
                    record = history_map[code]
                    progress.append({
                        'code': code,
                        'index': i,
                        'status': 'success' if record['success'] else 'failed',
                        'message': record['message'],
                        'amount': record.get('amount', ''),
                        'time': str(record['created_at']) if record['created_at'] else None
                    })
                elif i < task['current_index']:
                    # 已执行但未找到记录（理论上不应该发生）
                    progress.append({
                        'code': code,
                        'index': i,
                        'status': 'unknown',
                        'message': '记录丢失'
                    })
                elif i == task['current_index'] and task['status'] == 'running':
                    # 当前待执行的兑换码 - 显示等待执行
                    progress.append({
                        'code': code,
                        'index': i,
                        'status': 'waiting',
                        'message': '等待执行',
                        'next_execute_at': next_execute_str
                    })
                else:
                    progress.append({
                        'code': code,
                        'index': i,
                        'status': 'pending',
                        'message': '等待中'
                    })

            return {
                'task': {
                    'id': task['id'],
                    'account_id': task['account_id'],
                    'status': task['status'],
                    'total_count': task['total_count'],
                    'current_index': task['current_index'],
                    'success_count': task['success_count'],
                    'fail_count': task['fail_count'],
                    'next_execute_at': next_execute_str,
                    'created_at': str(task['created_at']) if task['created_at'] else None,
                    'completed_at': str(task['completed_at']) if task['completed_at'] else None
                },
                'progress': progress
            }

        except Exception as e:
            logger.error(f"Get task status error: {e}")
            logger.error(traceback.format_exc())
            return {'task': None, 'progress': [], 'error': str(e)}


# 初始化单例
batch_redeem_scheduler = BatchRedeemScheduler()
