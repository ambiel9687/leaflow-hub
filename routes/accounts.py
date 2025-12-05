#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Accounts routes for Leaflow Auto Check-in Control Panel
"""

import json
import time
import random
import threading

from flask import Blueprint, request, jsonify

from config import logger
from database import db, account_cache, data_cache
from utils import token_required, parse_cookie_string

accounts_bp = Blueprint('accounts', __name__)

# 全局进度状态
refresh_progress = {
    'running': False,
    'total': 0,
    'completed': 0,
    'success': 0,
    'failed': 0,
    'current_account': ''
}


@accounts_bp.route('/api/accounts', methods=['GET'])
@token_required
def get_accounts():
    """Get all accounts with today's checkin info"""
    from datetime import datetime
    from config import TIMEZONE

    try:
        today = datetime.now(TIMEZONE).date()

        # 获取账号列表及今日签到信息
        accounts = db.fetchall('''
            SELECT a.id, a.name, a.enabled, a.checkin_time_start, a.checkin_time_end,
                   a.check_interval, a.retry_count, a.created_at,
                   a.leaflow_uid, a.leaflow_name, a.leaflow_email, a.leaflow_created_at,
                   a.current_balance, a.total_consumed, a.balance_updated_at,
                   ch.success as today_success, ch.message as today_message,
                   ch.created_at as today_checkin_time
            FROM accounts a
            LEFT JOIN (
                SELECT account_id, success, message, created_at,
                       ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY created_at DESC) as rn
                FROM checkin_history
                WHERE DATE(checkin_date) = DATE(?)
            ) ch ON a.id = ch.account_id AND ch.rn = 1
        ''', (today,))
        return jsonify(accounts or [])
    except Exception as e:
        logger.error(f"Get accounts error: {e}")
        return jsonify({'error': 'Failed to load accounts'}), 500


@accounts_bp.route('/api/accounts', methods=['POST'])
@token_required
def add_account():
    """Add a new account"""
    try:
        data = request.get_json()
        name = data.get('name')
        cookie_input = data.get('token_data', data.get('cookie_data', ''))

        if not name or not cookie_input:
            return jsonify({'message': 'Name and cookie data are required'}), 400

        if isinstance(cookie_input, str):
            token_data = parse_cookie_string(cookie_input)
        else:
            token_data = cookie_input

        db.execute('''
            INSERT INTO accounts (name, token_data)
            VALUES (?, ?)
        ''', (name, json.dumps(token_data)))

        account_cache.refresh_from_db(db)
        data_cache.invalidate()

        logger.info(f"Account '{name}' added and cache refreshed")

        return jsonify({'message': 'Account added successfully'})

    except ValueError as e:
        return jsonify({'message': f'Invalid cookie format: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Add account error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400


@accounts_bp.route('/api/accounts/<int:account_id>', methods=['PUT'])
@token_required
def update_account(account_id):
    """Update an account"""
    try:
        data = request.get_json()

        updates = []
        params = []

        if 'enabled' in data:
            updates.append('enabled = ?')
            params.append(1 if data['enabled'] else 0)

        if 'token_data' in data or 'cookie_data' in data:
            cookie_input = data.get('token_data', data.get('cookie_data', ''))
            if isinstance(cookie_input, str):
                token_data = parse_cookie_string(cookie_input)
            else:
                token_data = cookie_input
            updates.append('token_data = ?')
            params.append(json.dumps(token_data))

        if updates:
            params.append(account_id)
            query = f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?"
            db.execute(query, params)

            account_cache.refresh_from_db(db)
            data_cache.invalidate()

            logger.info(f"Account {account_id} updated and cache refreshed")

            return jsonify({'message': 'Account updated successfully'})

        return jsonify({'message': 'No updates provided'}), 400

    except Exception as e:
        logger.error(f"Update account error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400


@accounts_bp.route('/api/accounts/<int:account_id>', methods=['DELETE'])
@token_required
def delete_account(account_id):
    """Delete an account"""
    try:
        db.execute('DELETE FROM checkin_history WHERE account_id = ?', (account_id,))
        db.execute('DELETE FROM accounts WHERE id = ?', (account_id,))

        account_cache.refresh_from_db(db)
        data_cache.invalidate()

        logger.info(f"Account {account_id} deleted and cache refreshed")

        return jsonify({'message': 'Account deleted successfully'})
    except Exception as e:
        logger.error(f"Delete account error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 400


@accounts_bp.route('/api/accounts/<int:account_id>/refresh-balance', methods=['POST'])
@token_required
def refresh_account_balance(account_id):
    """Refresh balance info for a single account"""
    from datetime import datetime
    from config import TIMEZONE
    from services import BalanceService
    from services.checkin_service import LeafLowCheckin

    try:
        account = db.fetchone('SELECT * FROM accounts WHERE id = ?', (account_id,))
        if not account:
            return jsonify({'message': 'Account not found'}), 404

        # 解析 token_data 并创建 session
        token_data = json.loads(account['token_data'])
        leaflow_checkin = LeafLowCheckin()
        session = leaflow_checkin.create_session(token_data)

        # 获取余额信息
        success, result = BalanceService.fetch_balance_info(session)

        if not success:
            return jsonify({'message': f'Failed to fetch balance: {result}'}), 400

        # 更新数据库
        db.execute('''
            UPDATE accounts SET
                leaflow_uid = ?,
                leaflow_name = ?,
                leaflow_email = ?,
                leaflow_created_at = ?,
                current_balance = ?,
                total_consumed = ?,
                balance_updated_at = ?
            WHERE id = ?
        ''', (
            result['leaflow_uid'],
            result['leaflow_name'],
            result['leaflow_email'],
            result['leaflow_created_at'],
            result['current_balance'],
            result['total_consumed'],
            datetime.now(TIMEZONE),
            account_id
        ))

        account_cache.refresh_from_db(db)
        data_cache.invalidate()

        logger.info(f"Account {account['name']} balance refreshed: {result['current_balance']}")

        return jsonify({
            'message': 'Balance refreshed successfully',
            'balance': result
        })

    except Exception as e:
        logger.error(f"Refresh balance error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 500


@accounts_bp.route('/api/accounts/refresh-all-balance', methods=['POST'])
@token_required
def refresh_all_balances():
    """异步刷新所有启用账号的余额"""
    global refresh_progress

    if refresh_progress['running']:
        return jsonify({'message': '刷新任务正在进行中', 'status': 'running'}), 400

    try:
        accounts = db.fetchall('SELECT * FROM accounts WHERE enabled = 1')

        if not accounts:
            return jsonify({'message': 'No enabled accounts found'}), 404

        # 初始化进度状态
        refresh_progress['running'] = True
        refresh_progress['total'] = len(accounts)
        refresh_progress['completed'] = 0
        refresh_progress['success'] = 0
        refresh_progress['failed'] = 0
        refresh_progress['current_account'] = ''

        def do_refresh():
            """后台执行刷新任务"""
            global refresh_progress
            from datetime import datetime
            from config import TIMEZONE
            from services import BalanceService
            from services.checkin_service import LeafLowCheckin

            try:
                leaflow_checkin = LeafLowCheckin()

                for account in accounts:
                    refresh_progress['current_account'] = account['name']

                    try:
                        token_data = json.loads(account['token_data'])
                        session = leaflow_checkin.create_session(token_data)

                        success, result = BalanceService.fetch_balance_info(session)

                        if success:
                            db.execute('''
                                UPDATE accounts SET
                                    leaflow_uid = ?,
                                    leaflow_name = ?,
                                    leaflow_email = ?,
                                    leaflow_created_at = ?,
                                    current_balance = ?,
                                    total_consumed = ?,
                                    balance_updated_at = ?
                                WHERE id = ?
                            ''', (
                                result['leaflow_uid'],
                                result['leaflow_name'],
                                result['leaflow_email'],
                                result['leaflow_created_at'],
                                result['current_balance'],
                                result['total_consumed'],
                                datetime.now(TIMEZONE),
                                account['id']
                            ))
                            refresh_progress['success'] += 1
                            logger.info(f"Account {account['name']} balance refreshed: {result['current_balance']}")
                        else:
                            refresh_progress['failed'] += 1
                            logger.warning(f"Account {account['name']} balance refresh failed: {result}")

                    except Exception as e:
                        refresh_progress['failed'] += 1
                        logger.error(f"Account {account['name']} balance refresh error: {e}")

                    refresh_progress['completed'] += 1

                    # 每个账号间随机等待 300-1000ms
                    time.sleep(random.uniform(0.3, 1.0))

                account_cache.refresh_from_db(db)
                data_cache.invalidate()
                logger.info(f"All balances refresh completed: {refresh_progress['success']}/{refresh_progress['total']}")

            except Exception as e:
                logger.error(f"Refresh all balances error: {e}")
            finally:
                refresh_progress['running'] = False
                refresh_progress['current_account'] = ''

        # 启动后台线程
        thread = threading.Thread(target=do_refresh, daemon=True)
        thread.start()

        return jsonify({'message': '余额刷新任务已启动', 'status': 'started'})

    except Exception as e:
        refresh_progress['running'] = False
        logger.error(f"Refresh all balances error: {e}")
        return jsonify({'message': f'Error: {str(e)}'}), 500


@accounts_bp.route('/api/accounts/refresh-progress', methods=['GET'])
@token_required
def get_refresh_progress():
    """获取刷新进度"""
    return jsonify(refresh_progress)


@accounts_bp.route('/api/accounts/<int:account_id>/redeem', methods=['POST'])
@token_required
def redeem_code(account_id):
    """为指定账号执行兑换码兑换"""
    from services.redeem_service import RedeemService
    from services.checkin_service import LeafLowCheckin

    try:
        data = request.get_json()
        code = data.get('code', '').strip()

        if not code:
            return jsonify({'message': '请输入兑换码'}), 400

        # 获取账号
        account = db.fetchone('SELECT * FROM accounts WHERE id = ?', (account_id,))
        if not account:
            return jsonify({'message': '账号不存在'}), 404

        # 创建 session 并执行兑换
        token_data = json.loads(account['token_data'])
        leaflow_checkin = LeafLowCheckin()
        session = leaflow_checkin.create_session(token_data)

        success, message = RedeemService.redeem_code(session, code)

        # 提取金额并记录历史
        amount = RedeemService.extract_amount(message) if success else ''

        db.execute('''
            INSERT INTO redeem_history (account_id, code, success, message, amount)
            VALUES (?, ?, ?, ?, ?)
        ''', (account_id, code, success, message, amount))

        if success:
            logger.info(f"Account {account['name']} redeem success: {message}")
            # 清除缓存以刷新余额显示
            data_cache.invalidate()
            return jsonify({
                'success': True,
                'message': message,
                'amount': amount
            })
        else:
            logger.warning(f"Account {account['name']} redeem failed: {message}")
            return jsonify({
                'success': False,
                'message': message
            }), 400

    except Exception as e:
        logger.error(f"Redeem code error: {e}")
        return jsonify({'message': f'兑换失败: {str(e)}'}), 500


@accounts_bp.route('/api/accounts/<int:account_id>/redeem-history', methods=['GET'])
@token_required
def get_redeem_history(account_id):
    """获取账号的兑换历史"""
    try:
        history = db.fetchall('''
            SELECT id, code, success, message, amount, created_at
            FROM redeem_history
            WHERE account_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (account_id,))
        return jsonify(history or [])
    except Exception as e:
        logger.error(f"Get redeem history error: {e}")
        return jsonify({'error': 'Failed to load redeem history'}), 500


# ============ 批量兑换 API ============

@accounts_bp.route('/api/accounts/<int:account_id>/batch-redeem', methods=['POST'])
@token_required
def create_batch_redeem(account_id):
    """创建批量兑换任务"""
    from services.batch_redeem_service import batch_redeem_scheduler

    try:
        data = request.get_json()
        codes = data.get('codes', [])

        if not codes:
            return jsonify({'success': False, 'message': '请输入兑换码'}), 400

        # 去重并过滤空值
        codes = list(dict.fromkeys([c.strip() for c in codes if c.strip()]))

        if not codes:
            return jsonify({'success': False, 'message': '没有有效的兑换码'}), 400

        # 检查账号是否存在
        account = db.fetchone('SELECT id, name FROM accounts WHERE id = ?', (account_id,))
        if not account:
            return jsonify({'success': False, 'message': '账号不存在'}), 404

        # 创建任务
        result = batch_redeem_scheduler.create_task(account_id, codes)

        if result['success']:
            logger.info(f"Batch redeem task created for account {account['name']}: {len(codes)} codes")
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Create batch redeem error: {e}")
        return jsonify({'success': False, 'message': f'创建任务失败: {str(e)}'}), 500


@accounts_bp.route('/api/accounts/<int:account_id>/batch-redeem', methods=['GET'])
@token_required
def get_batch_redeem_status(account_id):
    """获取批量兑换任务状态"""
    from services.batch_redeem_service import batch_redeem_scheduler

    try:
        result = batch_redeem_scheduler.get_task_status(account_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Get batch redeem status error: {e}")
        return jsonify({'task': None, 'progress': [], 'error': str(e)}), 500


@accounts_bp.route('/api/batch-redeem/<int:task_id>/cancel', methods=['POST'])
@token_required
def cancel_batch_redeem(task_id):
    """取消批量兑换任务"""
    from services.batch_redeem_service import batch_redeem_scheduler

    try:
        result = batch_redeem_scheduler.cancel_task(task_id)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Cancel batch redeem error: {e}")
        return jsonify({'success': False, 'message': f'取消失败: {str(e)}'}), 500


@accounts_bp.route('/api/batch-redeem/<int:task_id>/pause', methods=['POST'])
@token_required
def pause_batch_redeem(task_id):
    """暂停批量兑换任务"""
    from services.batch_redeem_service import batch_redeem_scheduler

    try:
        result = batch_redeem_scheduler.pause_task(task_id)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Pause batch redeem error: {e}")
        return jsonify({'success': False, 'message': f'暂停失败: {str(e)}'}), 500


@accounts_bp.route('/api/batch-redeem/<int:task_id>/resume', methods=['POST'])
@token_required
def resume_batch_redeem(task_id):
    """恢复批量兑换任务"""
    from services.batch_redeem_service import batch_redeem_scheduler

    try:
        result = batch_redeem_scheduler.resume_task(task_id)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Resume batch redeem error: {e}")
        return jsonify({'success': False, 'message': f'恢复失败: {str(e)}'}), 500


# ============ 邀请码 API ============

@accounts_bp.route('/api/accounts/<int:account_id>/invitation-codes', methods=['GET'])
@token_required
def get_invitation_codes(account_id):
    """获取账户的邀请码列表（支持缓存）"""
    from services.invitation_service import InvitationService
    from services.checkin_service import LeafLowCheckin

    try:
        # 获取 refresh 参数
        refresh = request.args.get('refresh', 'false').lower() == 'true'

        # 获取账号
        account = db.fetchone('SELECT * FROM accounts WHERE id = ?', (account_id,))
        if not account:
            return jsonify({'success': False, 'message': '账号不存在'}), 404

        # 如果不需要刷新，检查是否已同步过
        if not refresh and InvitationService.has_synced(db, account_id):
            # 已同步过，返回数据库缓存（即使为空）
            cached_codes = InvitationService.get_cached_codes(db, account_id)
            codes = InvitationService.format_cached_codes(cached_codes)
            stats = InvitationService.calculate_stats(codes)
            logger.info(f"Returning {len(codes)} cached invitation codes for account {account_id}")
            return jsonify({
                'success': True,
                'codes': codes,
                'stats': stats,
                'settings': {'price': 10, 'allow_user_generation': True},
                'cached': True
            })

        # 创建 session 调用 API
        token_data = json.loads(account['token_data'])
        leaflow_checkin = LeafLowCheckin()
        session = leaflow_checkin.create_session(token_data)

        # 获取邀请码列表
        success, result = InvitationService.get_invitation_codes(session)

        if success:
            # 保存到数据库缓存（即使为空列表）
            InvitationService.save_codes_to_db(db, account_id, result['codes'])
            # 更新同步时间（标记已同步过）
            InvitationService.update_sync_time(db, account_id)

            return jsonify({
                'success': True,
                'codes': result['codes'],
                'stats': result['stats'],
                'settings': result['settings'],
                'cached': False
            })
        else:
            return jsonify({'success': False, 'message': result}), 400

    except Exception as e:
        logger.error(f"Get invitation codes error: {e}")
        return jsonify({'success': False, 'message': f'获取邀请码失败: {str(e)}'}), 500


@accounts_bp.route('/api/accounts/<int:account_id>/invitation-codes', methods=['POST'])
@token_required
def create_invitation_code(account_id):
    """为账户创建新邀请码"""
    from services.invitation_service import InvitationService
    from services.checkin_service import LeafLowCheckin

    try:
        # 获取账号
        account = db.fetchone('SELECT * FROM accounts WHERE id = ?', (account_id,))
        if not account:
            return jsonify({'success': False, 'message': '账号不存在'}), 404

        # 创建 session
        token_data = json.loads(account['token_data'])
        leaflow_checkin = LeafLowCheckin()
        session = leaflow_checkin.create_session(token_data)

        # 创建邀请码（固定 max_uses=1）
        success, result = InvitationService.create_invitation_code(session, max_uses=1)

        if success:
            logger.info(f"Account {account['name']} created invitation code: {result.get('code')}")
            # 保存到数据库缓存
            InvitationService.save_single_code(db, account_id, result)
            return jsonify({
                'success': True,
                'code': result
            })
        else:
            return jsonify({'success': False, 'message': result}), 400

    except Exception as e:
        logger.error(f"Create invitation code error: {e}")
        return jsonify({'success': False, 'message': f'创建邀请码失败: {str(e)}'}), 500

