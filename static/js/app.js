// 全局变量
        let authToken = localStorage.getItem('authToken');

        // 主题管理
        function initTheme() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-theme', savedTheme);
            updateThemeIcon(savedTheme);
        }

        function toggleTheme() {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
        }

        function updateThemeIcon(theme) {
            const icon = document.querySelector('.theme-icon');
            if (icon) {
                icon.textContent = theme === 'dark' ? '☀️' : '🌙';
            }
        }

        // 初始化主题（立即执行）
        initTheme();

        // 时间格式化工具函数
        function formatRelativeTime(dateString) {
            if (!dateString) return '';

            // 北京时间（UTC+8）
            const now = new Date();

            // 如果数据库存储的是UTC时间，需要转换为北京时间
            let date = new Date(dateString);

            // 如果时间字符串不包含时区信息，假定为UTC时间，需要加8小时转为北京时间
            // SQLite CURRENT_TIMESTAMP 返回UTC时间
            if (!dateString.includes('+') && !dateString.includes('Z')) {
                // 假定为UTC时间，转换为北京时间
                date = new Date(date.getTime() + 8 * 3600000);
            }

            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) return '刚刚';
            if (diffMins < 60) return `${diffMins}分钟前`;
            if (diffHours < 24) return `${diffHours}小时前`;
            if (diffDays < 7) return `${diffDays}天前`;

            // 超过7天显示具体日期（北京时间）
            return date.toLocaleDateString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                timeZone: 'Asia/Shanghai'
            });
        }

        // Toast notification function
        function showToast(message, type = 'info') {
            const toast = document.getElementById('toast');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            toast.style.display = 'block';
            
            setTimeout(() => {
                toast.style.display = 'none';
            }, 3000);
        }

        // 显示登录错误
        function showLoginError(message) {
            const errorDiv = document.getElementById('loginError');
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }

        // 处理登录
        async function handleLogin() {
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            if (!username || !password) {
                showLoginError('请输入用户名和密码');
                return;
            }
            
            const loginBtn = document.getElementById('loginBtn');
            loginBtn.disabled = true;
            loginBtn.textContent = '登录中...';

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ username, password })
                });

                const data = await response.json();
                
                if (response.ok && data.token) {
                    authToken = data.token;
                    localStorage.setItem('authToken', authToken);
                    showToast('登录成功', 'success');

                    // 移除防闪烁样式，让 JS 设置生效
                    var antiFlickerStyle = document.getElementById('anti-flicker-style');
                    if (antiFlickerStyle) {
                        antiFlickerStyle.remove();
                    }

                    document.getElementById('loginContainer').style.display = 'none';
                    document.getElementById('dashboard').style.display = 'block';
                    document.getElementById('dashboard').style.visibility = 'visible';

                    loadDashboard();
                    loadAccounts();
                } else {
                    showLoginError(data.message || '用户名或密码错误');
                }
            } catch (error) {
                console.error('Login error:', error);
                showLoginError('登录失败：' + error.message);
            } finally {
                loginBtn.disabled = false;
                loginBtn.textContent = '登录';
            }
        }

        // 监听回车键
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('username').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    handleLogin();
                }
            });
            
            document.getElementById('password').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    handleLogin();
                }
            });
            
            // 移除防闪烁样式的辅助函数
            function removeAntiFlickerStyle() {
                var antiFlickerStyle = document.getElementById('anti-flicker-style');
                if (antiFlickerStyle) {
                    antiFlickerStyle.remove();
                }
            }

            // 检查是否已登录
            if (authToken) {
                // 验证token是否有效
                fetch('/api/verify', {
                    headers: {
                        'Authorization': 'Bearer ' + authToken
                    }
                }).then(response => {
                    removeAntiFlickerStyle();
                    if (response.ok) {
                        // Token有效，直接显示控制面板
                        document.getElementById('loginContainer').style.display = 'none';
                        document.getElementById('dashboard').style.display = 'block';
                        document.getElementById('dashboard').style.visibility = 'visible';
                        loadDashboard();
                        loadAccounts();
                    } else {
                        // Token无效，清除并显示登录页面
                        localStorage.removeItem('authToken');
                        authToken = null;
                        document.getElementById('loginContainer').style.display = 'flex';
                        document.getElementById('loginContainer').style.visibility = 'visible';
                        document.getElementById('dashboard').style.display = 'none';
                    }
                }).catch(error => {
                    removeAntiFlickerStyle();
                    console.error('Token check error:', error);
                    localStorage.removeItem('authToken');
                    authToken = null;
                    document.getElementById('loginContainer').style.display = 'flex';
                    document.getElementById('loginContainer').style.visibility = 'visible';
                    document.getElementById('dashboard').style.display = 'none';
                });
            } else {
                // 没有token，显示登录页面
                removeAntiFlickerStyle();
                document.getElementById('loginContainer').style.display = 'flex';
                document.getElementById('loginContainer').style.visibility = 'visible';
                document.getElementById('dashboard').style.display = 'none';
            }
        });

        function logout() {
            localStorage.removeItem('authToken');
            authToken = null;
            location.reload();
        }

        async function apiCall(url, options = {}) {
            try {
                const response = await fetch(url, {
                    ...options,
                    headers: {
                        'Authorization': 'Bearer ' + authToken,
                        'Content-Type': 'application/json',
                        ...options.headers
                    }
                });

                if (response.status === 401) {
                    logout();
                    return;
                }

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.message || 'Request failed');
                }
                return data;
            } catch (error) {
                console.error('API call error:', error);
                throw error;
            }
        }

        async function loadDashboard() {
            try {
                const data = await apiCall('/api/dashboard');
                if (!data) return;

                document.getElementById('totalAccounts').textContent = data.total_accounts || 0;
                document.getElementById('activeAccounts').textContent = data.enabled_accounts || 0;
                document.getElementById('totalCheckins').textContent = data.total_checkins || 0;
                document.getElementById('successRate').textContent = (data.success_rate || 0) + '%';

                const totalBalance = data.total_balance || 0;
                const totalConsumed = data.total_consumed || 0;
                const todayAmount = data.today_checkin_amount || 0;

                document.getElementById('totalBalance').textContent = '¥' + totalBalance.toFixed(2);
                document.getElementById('totalConsumed').textContent = '¥' + totalConsumed.toFixed(2);
                document.getElementById('todayCheckinAmount').textContent = '¥' + todayAmount.toFixed(2);

                // 计算使用率：总消费 / (总余额 + 总消费)
                const totalAmount = totalBalance + totalConsumed;
                const usageRate = totalAmount > 0 ? (totalConsumed / totalAmount * 100).toFixed(1) : 0;
                document.getElementById('usageRate').textContent = usageRate + '%';
            } catch (error) {
                console.error('Failed to load dashboard:', error);
            }
        }

        // 全局存储账号数据，供编辑时使用
        let accountsData = [];

        async function loadAccounts() {
            try {
                const accounts = await apiCall('/api/accounts');
                if (!accounts) return;

                accountsData = accounts;
                const tbody = document.getElementById('accountsList');
                tbody.innerHTML = '';

                if (accounts && accounts.length > 0) {
                    accounts.forEach(account => {
                        const tr = document.createElement('tr');

                        // 今日签到状态
                        let todayCheckinHtml = '';
                        if (account.today_success !== null && account.today_success !== undefined) {
                            const statusClass = account.today_success ? 'badge-success' : 'badge-danger';
                            const message = account.today_message || '';
                            let displayText = account.today_success ? '成功' : '失败';

                            // 如果成功，尝试提取额度信息
                            if (account.today_success && message) {
                                const creditMatch = message.match(/(\d+\.?\d*)\s*(credits?|元)/i);
                                if (creditMatch) {
                                    displayText = `+${creditMatch[1]}`;
                                }
                            }

                            todayCheckinHtml = `<span class="badge ${statusClass} clickable" onclick="showCheckinHistory(${account.id}, '${account.name}')" title="${message}">${displayText}</span>`;
                        } else {
                            todayCheckinHtml = `<span class="badge badge-secondary clickable" onclick="showCheckinHistory(${account.id}, '${account.name}')">未签到</span>`;
                        }

                        // 基础信息列
                        let basicInfoHtml = '';
                        if (account.leaflow_email) {
                            const displayName = account.leaflow_name || account.name;
                            const displayEmail = account.leaflow_email || '-';
                            basicInfoHtml = `
                                <div class="info-display">
                                    <div class="info-name" title="${displayName}">${displayName}</div>
                                    <div class="info-sub" title="${displayEmail}">${displayEmail}</div>
                                </div>
                            `;
                        } else {
                            basicInfoHtml = `<span class="badge badge-secondary">未获取</span>`;
                        }

                        // 余额信息列
                        let balanceInfoHtml = '';
                        if (account.current_balance) {
                            const balance = parseFloat(account.current_balance).toFixed(2);
                            const consumed = parseFloat(account.total_consumed || 0).toFixed(2);
                            balanceInfoHtml = `
                                <div class="balance-display">
                                    <div class="balance-amount">余额: ¥${balance}</div>
                                    <div class="balance-consumed">消费: ¥${consumed}</div>
                                </div>
                            `;
                        } else {
                            balanceInfoHtml = `<span class="badge badge-secondary">未获取</span>`;
                        }

                        // 名称列：展示 leaflow_uid 和创建时间距今天数
                        let nameColumnHtml = '';
                        if (account.leaflow_uid) {
                            const daysAgo = calcDaysAgo(account.leaflow_created_at);
                            const daysText = daysAgo !== null ? `${daysAgo} 天` : '-';
                            nameColumnHtml = `
                                <div class="info-display">
                                    <div class="info-name">UID: ${account.leaflow_uid}</div>
                                    <div class="info-sub">注册: ${daysText}</div>
                                </div>
                            `;
                        } else {
                            nameColumnHtml = `<span class="badge badge-secondary">${account.name}</span>`;
                        }

                        // 转义账号名中的特殊字符
                        const escapedName = account.name.replace(/'/g, "\\'").replace(/"/g, '\\"');

                        // 动态生成邀请码按钮文本
                        const invitationTotal = account.invitation_total || 0;
                        const invitationUsed = account.invitation_used || 0;
                        const invitationText = invitationTotal > 0
                            ? `🎫 邀请码(${invitationUsed}/${invitationTotal})`
                            : '🎫 邀请码';

                        tr.innerHTML = `
                            <td>${nameColumnHtml}</td>
                            <td>${basicInfoHtml}</td>
                            <td>${balanceInfoHtml}</td>
                            <td>
                                <label class="switch">
                                    <input type="checkbox" ${account.enabled ? 'checked' : ''} onchange="toggleAccount(${account.id}, this.checked)">
                                    <span class="slider"></span>
                                </label>
                            </td>
                            <td>${todayCheckinHtml}</td>
                            <td>
                                <button class="btn btn-warning btn-sm" onclick="refreshBalance(${account.id})" title="刷新余额">刷新</button>
                                <button class="btn btn-secondary btn-sm" onclick="showInvitationModal(${account.id}, '${escapedName}')">${invitationText}</button>
                                <button class="btn btn-primary btn-sm" onclick="showRedeemModal(${account.id}, '${escapedName}')">兑换</button>
                                <button class="btn btn-success btn-sm" onclick="manualCheckin(${account.id})">签到</button>
                                <button class="btn btn-info btn-sm" onclick="showEditAccountModal(${account.id})">修改</button>
                                <button class="btn btn-danger btn-sm" onclick="deleteAccount(${account.id})">删除</button>
                            </td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #a0aec0;">暂无账号</td></tr>';
                }
            } catch (error) {
                console.error('Failed to load accounts:', error);
            }
        }

        async function loadNotificationSettings() {
            try {
                const settings = await apiCall('/api/notification');
                if (!settings) return;

                // 主开关
                document.getElementById('notifyEnabled').checked = settings.enabled === true || settings.enabled === 1;
                
                // Telegram设置
                document.getElementById('telegramEnabled').checked = settings.telegram_enabled === true || settings.telegram_enabled === 1;
                document.getElementById('tgBotToken').value = settings.telegram_bot_token || '';
                document.getElementById('tgUserId').value = settings.telegram_user_id || '';
                document.getElementById('telegramHost').value = settings.telegram_host || '';
                
                // 企业微信设置
                document.getElementById('wechatEnabled').checked = settings.wechat_enabled === true || settings.wechat_enabled === 1;
                document.getElementById('wechatKey').value = settings.wechat_webhook_key || '';
                document.getElementById('wechatHost').value = settings.wechat_host || '';
                
                // WxPusher设置
                document.getElementById('wxpusherEnabled').checked = settings.wxpusher_enabled === true || settings.wxpusher_enabled === 1;
                document.getElementById('wxpusherAppToken').value = settings.wxpusher_app_token || '';
                document.getElementById('wxpusherUid').value = settings.wxpusher_uid || '';
                document.getElementById('wxpusherHost').value = settings.wxpusher_host || '';
                
                // 钉钉设置
                document.getElementById('dingtalkEnabled').checked = settings.dingtalk_enabled === true || settings.dingtalk_enabled === 1;
                document.getElementById('dingtalkAccessToken').value = settings.dingtalk_access_token || '';
                document.getElementById('dingtalkSecret').value = settings.dingtalk_secret || '';
                document.getElementById('dingtalkHost').value = settings.dingtalk_host || '';
            } catch (error) {
                console.error('Failed to load notification settings:', error);
            }
        }

        async function toggleAccount(id, enabled) {
            try {
                await apiCall(`/api/accounts/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify({ enabled })
                });
                loadAccounts();
            } catch (error) {
                showToast('操作失败', 'error');
            }
        }


        async function manualCheckin(id) {
            if (confirm('确定立即执行签到吗？')) {
                try {
                    await apiCall(`/api/checkin/manual/${id}`, { method: 'POST' });
                    showToast('签到任务已触发', 'success');
                    setTimeout(() => {
                        loadDashboard();
                        loadAccounts();
                    }, 2000);
                } catch (error) {
                    showToast('操作失败', 'error');
                }
            }
        }

        async function deleteAccount(id) {
            if (confirm('确定删除此账号吗？')) {
                try {
                    await apiCall(`/api/accounts/${id}`, { method: 'DELETE' });
                    showToast('账号删除成功', 'success');
                    loadAccounts();
                } catch (error) {
                    showToast('操作失败', 'error');
                }
            }
        }

        async function clearCheckinHistory(type) {
            const message = type === 'today' ? '确定清空今日签到记录吗？' : '确定清空所有签到记录吗？';
            if (confirm(message)) {
                try {
                    await apiCall('/api/checkin/clear', {
                        method: 'POST',
                        body: JSON.stringify({ type })
                    });
                    showToast('清空成功', 'success');
                    loadDashboard();
                    loadAccounts();
                } catch (error) {
                    showToast('操作失败: ' + error.message, 'error');
                }
            }
        }

        // 签到历史弹窗相关函数
        async function showCheckinHistory(accountId, accountName) {
            document.getElementById('historyAccountId').value = accountId;
            document.getElementById('historyModalTitle').textContent = `${accountName} - 签到历史`;
            document.getElementById('selectAllHistory').checked = false;
            document.getElementById('checkinHistoryModal').style.display = 'flex';

            await loadCheckinHistory(accountId);
        }

        async function loadCheckinHistory(accountId) {
            const tbody = document.getElementById('historyList');
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #a0aec0;">加载中...</td></tr>';

            try {
                const history = await apiCall(`/api/checkin/history/${accountId}`);

                tbody.innerHTML = '';

                if (history && history.length > 0) {
                    history.forEach(record => {
                        const tr = document.createElement('tr');
                        const statusText = record.success ? '成功' : '失败';
                        const statusClass = record.success ? 'badge-success' : 'badge-danger';
                        const time = record.created_at ? new Date(record.created_at).toLocaleString() : '-';

                        // 精简消息展示
                        let displayMsg = '-';
                        if (record.success) {
                            // 成功：提取金额显示
                            const creditMatch = (record.message || '').match(/(\d+\.?\d*)\s*(credits?|元)/i);
                            displayMsg = creditMatch ? `+${creditMatch[1]}` : '签到成功';
                        } else {
                            // 失败：显示原因，超过30字截断
                            const msg = record.message || '签到失败';
                            displayMsg = msg.length > 30 ? msg.substring(0, 30) + '...' : msg;
                        }

                        tr.innerHTML = `
                            <td><input type="checkbox" class="history-checkbox" value="${record.id}"></td>
                            <td><span class="badge ${statusClass}">${statusText}</span></td>
                            <td title="${record.message || ''}">${displayMsg}</td>
                            <td class="text-small text-muted">${time}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #a0aec0;">暂无签到记录</td></tr>';
                }
            } catch (error) {
                console.error('Failed to load checkin history:', error);
                tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #e53e3e;">加载失败</td></tr>';
            }
        }

        function toggleSelectAllHistory() {
            const selectAll = document.getElementById('selectAllHistory').checked;
            document.querySelectorAll('.history-checkbox').forEach(cb => {
                cb.checked = selectAll;
            });
        }

        async function deleteSelectedHistory() {
            const selectedIds = [];
            document.querySelectorAll('.history-checkbox:checked').forEach(cb => {
                selectedIds.push(parseInt(cb.value));
            });

            if (selectedIds.length === 0) {
                showToast('请选择要删除的记录', 'error');
                return;
            }

            if (!confirm(`确定删除选中的 ${selectedIds.length} 条记录吗？`)) {
                return;
            }

            try {
                await apiCall('/api/checkin/delete', {
                    method: 'POST',
                    body: JSON.stringify({ ids: selectedIds })
                });
                showToast('删除成功', 'success');

                const accountId = document.getElementById('historyAccountId').value;
                await loadCheckinHistory(accountId);
                loadAccounts();
                loadDashboard();
            } catch (error) {
                showToast('删除失败: ' + error.message, 'error');
            }
        }

        async function saveNotificationSettings() {
            try {
                const settings = {
                    enabled: document.getElementById('notifyEnabled').checked,
                    telegram_enabled: document.getElementById('telegramEnabled').checked,
                    telegram_bot_token: document.getElementById('tgBotToken').value,
                    telegram_user_id: document.getElementById('tgUserId').value,
                    telegram_host: document.getElementById('telegramHost').value,
                    wechat_enabled: document.getElementById('wechatEnabled').checked,
                    wechat_webhook_key: document.getElementById('wechatKey').value,
                    wechat_host: document.getElementById('wechatHost').value,
                    wxpusher_enabled: document.getElementById('wxpusherEnabled').checked,
                    wxpusher_app_token: document.getElementById('wxpusherAppToken').value,
                    wxpusher_uid: document.getElementById('wxpusherUid').value,
                    wxpusher_host: document.getElementById('wxpusherHost').value,
                    dingtalk_enabled: document.getElementById('dingtalkEnabled').checked,
                    dingtalk_access_token: document.getElementById('dingtalkAccessToken').value,
                    dingtalk_secret: document.getElementById('dingtalkSecret').value,
                    dingtalk_host: document.getElementById('dingtalkHost').value
                };

                await apiCall('/api/notification', {
                    method: 'PUT',
                    body: JSON.stringify(settings)
                });
                showToast('设置保存成功', 'success');
                closeModal('notificationModal');
            } catch (error) {
                showToast('操作失败: ' + error.message, 'error');
            }
        }

        async function testNotification() {
            try {
                await apiCall('/api/test/notification', { method: 'POST' });
                showToast('测试通知已发送', 'info');
            } catch (error) {
                showToast('发送失败: ' + error.message, 'error');
            }
        }

        function showAddAccountModal() {
            document.getElementById('addAccountModal').style.display = 'flex';
        }

        function showNotificationModal() {
            document.getElementById('notificationModal').style.display = 'flex';
            loadNotificationSettings();
        }
        
        function showEditAccountModal(accountId) {
            const account = accountsData.find(a => a.id === accountId);
            if (!account) {
                showToast('账号数据未找到', 'error');
                return;
            }

            document.getElementById('editAccountId').value = accountId;
            document.getElementById('editAccountTitle').textContent = `修改账号 - ${account.name}`;
            document.getElementById('editTokenData').value = '';
            document.getElementById('editAccountModal').style.display = 'flex';
        }

        function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';

            if (modalId === 'addAccountModal') {
                document.getElementById('accountName').value = '';
                document.getElementById('tokenData').value = '';
            } else if (modalId === 'editAccountModal') {
                document.getElementById('editAccountId').value = '';
                document.getElementById('editTokenData').value = '';
            } else if (modalId === 'checkinHistoryModal') {
                document.getElementById('historyAccountId').value = '';
                document.getElementById('historyList').innerHTML = '';
                document.getElementById('selectAllHistory').checked = false;
            } else if (modalId === 'redeemModal') {
                document.getElementById('redeemAccountId').value = '';
                document.getElementById('redeemCode').value = '';
                document.getElementById('redeemHistorySection').style.display = 'none';
                document.getElementById('redeemHistoryList').innerHTML = '';
            } else if (modalId === 'invitationModal') {
                document.getElementById('invitationAccountId').value = '';
                document.getElementById('invitationList').innerHTML = '<div class="invitation-loading">加载中...</div>';
            }
        }

        async function addAccount() {
            try {
                const account = {
                    name: document.getElementById('accountName').value,
                    token_data: document.getElementById('tokenData').value
                };

                if (!account.name || !account.token_data) {
                    showToast('请填写完整信息', 'error');
                    return;
                }

                await apiCall('/api/accounts', {
                    method: 'POST',
                    body: JSON.stringify(account)
                });

                showToast('账号添加成功', 'success');
                closeModal('addAccountModal');
                loadAccounts();
            } catch (error) {
                showToast('格式无效: ' + error.message, 'error');
            }
        }
        
        async function updateAccount() {
            try {
                const accountId = document.getElementById('editAccountId').value;
                const data = {};

                const tokenData = document.getElementById('editTokenData').value.trim();
                if (tokenData) {
                    data.token_data = tokenData;
                }

                if (Object.keys(data).length === 0) {
                    showToast('请输入新的 Cookie 数据', 'warning');
                    return;
                }

                await apiCall(`/api/accounts/${accountId}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });

                showToast('账号修改成功', 'success');
                closeModal('editAccountModal');
                loadAccounts();
            } catch (error) {
                showToast('修改失败: ' + error.message, 'error');
            }
        }

        // Close modal when clicking outside
        window.onclick = function(event) {
            const modals = ['addAccountModal', 'editAccountModal', 'checkinHistoryModal', 'notificationModal', 'checkinSettingsModal', 'redeemModal', 'invitationModal'];
            modals.forEach(modalId => {
                const modal = document.getElementById(modalId);
                if (event.target == modal) {
                    closeModal(modalId);
                }
            });
        }

        // 签到设置相关函数
        function showCheckinSettingsModal() {
            document.getElementById('checkinSettingsModal').style.display = 'flex';
            loadCheckinSettings();
        }

        async function loadCheckinSettings() {
            try {
                const settings = await apiCall('/api/checkin-settings');
                if (!settings) return;

                document.getElementById('globalCheckinTime').value = settings.checkin_time || '05:30';
                document.getElementById('globalRetryCount').value = settings.retry_count || 2;
                document.getElementById('globalRandomDelayMin').value = settings.random_delay_min || 0;
                document.getElementById('globalRandomDelayMax').value = settings.random_delay_max || 30;
            } catch (error) {
                console.error('Failed to load checkin settings:', error);
            }
        }

        async function saveCheckinSettings() {
            try {
                const settings = {
                    checkin_time: document.getElementById('globalCheckinTime').value,
                    retry_count: parseInt(document.getElementById('globalRetryCount').value),
                    random_delay_min: parseInt(document.getElementById('globalRandomDelayMin').value),
                    random_delay_max: parseInt(document.getElementById('globalRandomDelayMax').value)
                };

                // 前端验证
                if (settings.random_delay_min > settings.random_delay_max) {
                    showToast('随机延迟最小值不能大于最大值', 'error');
                    return;
                }

                await apiCall('/api/checkin-settings', {
                    method: 'PUT',
                    body: JSON.stringify(settings)
                });
                showToast('签到设置保存成功', 'success');
                closeModal('checkinSettingsModal');
            } catch (error) {
                showToast('保存失败: ' + error.message, 'error');
            }
        }

        // 刷新单个账号余额
        async function refreshBalance(accountId) {
            try {
                showToast('正在刷新余额...', 'info');

                const result = await apiCall(`/api/accounts/${accountId}/refresh-balance`, {
                    method: 'POST'
                });

                if (result && result.balance) {
                    showToast(`余额刷新成功: ¥${parseFloat(result.balance.current_balance).toFixed(2)}`, 'success');
                } else {
                    showToast('余额刷新成功', 'success');
                }
                loadAccounts();
                loadDashboard();
            } catch (error) {
                showToast('余额刷新失败: ' + error.message, 'error');
            }
        }

        // 刷新所有账号余额（异步）
        async function refreshAllBalances() {
            if (!confirm('确定刷新所有启用账号的余额吗？')) {
                return;
            }

            try {
                const result = await apiCall('/api/accounts/refresh-all-balance', {
                    method: 'POST'
                });

                if (result.status === 'running') {
                    showToast('刷新任务正在进行中，请稍候...', 'warning');
                    return;
                }

                showToast('余额刷新任务已启动...', 'info');
                pollRefreshProgress();
            } catch (error) {
                showToast('余额刷新失败: ' + error.message, 'error');
            }
        }

        // 轮询刷新进度
        function pollRefreshProgress() {
            const interval = setInterval(async () => {
                try {
                    const progress = await apiCall('/api/accounts/refresh-progress');

                    if (progress.running) {
                        showToast(`正在刷新 ${progress.completed}/${progress.total}...`, 'info');
                    } else {
                        clearInterval(interval);
                        const status = progress.success === progress.total ? 'success' : 'warning';
                        showToast(`刷新完成: ${progress.success}/${progress.total} 成功`, status);
                        loadAccounts();
                        loadDashboard();
                    }
                } catch (error) {
                    clearInterval(interval);
                    showToast('获取刷新进度失败', 'error');
                }
            }, 3000);
        }

        // 计算距离当前时间的天数
        function calcDaysAgo(dateStr) {
            if (!dateStr) return null;
            const date = new Date(dateStr);
            const now = new Date();
            const diffTime = now - date;
            const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
            return diffDays;
        }

        // 定期刷新dashboard数据
        setInterval(() => {
            if (authToken && document.getElementById('dashboard').style.display === 'block') {
                loadDashboard();
            }
        }, 60000); // 每分钟刷新一次

        // ========== 兑换码相关函数 ==========

        // 显示兑换码弹窗
        async function showRedeemModal(accountId, accountName) {
            document.getElementById('redeemAccountId').value = accountId;
            document.getElementById('redeemModalTitle').textContent = `🎁 ${accountName} - 兑换码`;
            document.getElementById('redeemCode').value = '';
            document.getElementById('redeemModal').style.display = 'flex';

            // 加载兑换历史
            await loadRedeemHistory(accountId);
        }

        // 兑换倒计时定时器
        let redeemCountdownTimer = null;

        // 格式化金额（去除尾部多余的0）
        const formatAmount = (amount) => {
            if (!amount) return '';
            return parseFloat(amount).toString();
        };

        // 解析数据库时间（UTC）为 Date 对象
        const parseDbTimeAsUTC = (dateStr) => {
            if (!dateStr) return null;
            // 数据库存储的是 UTC 时间，格式如 "2025-12-05 08:48:00"
            // 需要添加 Z 后缀表示 UTC
            const isoStr = dateStr.replace(' ', 'T') + 'Z';
            const date = new Date(isoStr);
            return isNaN(date.getTime()) ? null : date;
        };

        // 加载兑换历史
        async function loadRedeemHistory(accountId) {
            const historySection = document.getElementById('redeemHistorySection');
            const historyList = document.getElementById('redeemHistoryList');
            const countdownSection = document.getElementById('redeemCountdownSection');

            // 清除之前的倒计时
            if (redeemCountdownTimer) {
                clearInterval(redeemCountdownTimer);
                redeemCountdownTimer = null;
            }

            try {
                const history = await apiCall(`/api/accounts/${accountId}/redeem-history`);

                if (history && history.length > 0) {
                    historySection.style.display = 'block';

                    // 检查最近一小时内是否有成功兑换
                    const now = new Date();
                    const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
                    const recentSuccess = history.find(record => {
                        if (!record.success) return false;
                        const recordTime = parseDbTimeAsUTC(record.created_at);
                        return recordTime && recordTime > oneHourAgo;
                    });

                    // 显示倒计时
                    if (recentSuccess && countdownSection) {
                        const recordTime = parseDbTimeAsUTC(recentSuccess.created_at);
                        const nextRedeemTime = new Date(recordTime.getTime() + 60 * 60 * 1000);

                        const updateCountdown = () => {
                            const remaining = nextRedeemTime.getTime() - new Date().getTime();
                            if (remaining <= 0) {
                                countdownSection.style.display = 'none';
                                clearInterval(redeemCountdownTimer);
                                redeemCountdownTimer = null;
                            } else {
                                const minutes = Math.floor(remaining / 60000);
                                const seconds = Math.floor((remaining % 60000) / 1000);
                                countdownSection.innerHTML = `<span style="color: var(--text-primary); font-size: 13px;">⏰ 下次可兑换: ${minutes}分${seconds}秒</span>`;
                                countdownSection.style.display = 'block';
                            }
                        };

                        updateCountdown();
                        redeemCountdownTimer = setInterval(updateCountdown, 1000);
                    } else if (countdownSection) {
                        countdownSection.style.display = 'none';
                    }

                    // 格式化时间为北京时间（含年份）
                    const formatBeijingTime = (dateStr) => {
                        const date = parseDbTimeAsUTC(dateStr);
                        if (!date) return dateStr || '-';
                        return date.toLocaleString('zh-CN', {
                            timeZone: 'Asia/Shanghai',
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit'
                        });
                    };

                    // 显示记录：兑换码 → 状态 → 金额/原因 → 时间
                    historyList.innerHTML = history.slice(0, 5).map(record => {
                        const statusClass = record.success ? 'badge-success' : 'badge-danger';
                        const statusText = record.success ? '成功' : '失败';
                        const resultText = record.success
                            ? (record.amount ? `+¥${formatAmount(record.amount)}` : '')
                            : (record.message || '');
                        const time = formatBeijingTime(record.created_at);
                        // 消息颜色使用 text-secondary 确保暗黑模式可见
                        const resultColor = 'var(--text-secondary)';

                        return `
                            <div style="display: flex; flex-wrap: wrap; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border-color); font-size: 12px; gap: 6px;">
                                <code style="background: var(--bg-secondary); color: var(--text-primary); padding: 2px 6px; border-radius: 4px; font-size: 11px;">${record.code}</code>
                                <span class="badge ${statusClass}" style="font-size: 10px;">${statusText}</span>
                                <span style="color: ${resultColor}; font-size: 11px; flex: 1;">${resultText}</span>
                                <span style="color: var(--text-muted); font-size: 10px;">${time}</span>
                            </div>
                        `;
                    }).join('');
                } else {
                    historySection.style.display = 'none';
                    historyList.innerHTML = '';
                    if (countdownSection) countdownSection.style.display = 'none';
                }
            } catch (error) {
                console.error('Failed to load redeem history:', error);
                historySection.style.display = 'none';
                if (countdownSection) countdownSection.style.display = 'none';
            }
        }

        // 提交兑换
        async function submitRedeem() {
            const btn = document.querySelector('#redeemForm .btn-full');
            if (btn.disabled) return;

            const accountId = document.getElementById('redeemAccountId').value;
            const code = document.getElementById('redeemCode').value.trim();

            if (!code) {
                showToast('请输入兑换码', 'error');
                return;
            }

            // 防抖：禁用按钮
            btn.disabled = true;
            btn.textContent = '兑换中...';

            try {
                const result = await apiCall(`/api/accounts/${accountId}/redeem`, {
                    method: 'POST',
                    body: JSON.stringify({ code: code })
                });

                if (result.success) {
                    showToast(result.message, 'success');
                    closeModal('redeemModal');
                    // 刷新余额显示
                    loadAccounts();
                    loadDashboard();
                } else {
                    showToast(result.message || '兑换失败', 'error');
                    // 刷新兑换历史
                    await loadRedeemHistory(accountId);
                }
            } catch (error) {
                showToast('兑换失败: ' + error.message, 'error');
                // 刷新兑换历史
                await loadRedeemHistory(accountId);
            } finally {
                // 恢复按钮状态
                btn.disabled = false;
                btn.textContent = '兑换';
            }
        }

        // ============ 批量兑换功能 ============

        let batchRedeemTimer = null;
        let batchCountdownTimer = null;
        let currentBatchTaskId = null;

        // Tab 切换
        function switchRedeemTab(tab) {
            // 更新 Tab 按钮状态
            document.querySelectorAll('.redeem-tabs .tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelector(`.redeem-tabs .tab-btn[data-tab="${tab}"]`).classList.add('active');

            // 更新 Tab 内容显示
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(tab === 'single' ? 'singleRedeemTab' : 'batchRedeemTab').classList.add('active');

            // 切换到批量 Tab 时加载任务状态
            if (tab === 'batch') {
                const accountId = document.getElementById('redeemAccountId').value;
                loadBatchRedeemStatus(accountId);
            }
        }

        // 解析兑换码输入（支持换行和逗号分隔）
        function parseBatchCodes(input) {
            if (!input) return [];
            return input
                .split(/[\n,]+/)
                .map(code => code.trim())
                .filter(code => code.length > 0);
        }

        // 更新兑换码计数
        function updateBatchCodeCount() {
            const codes = parseBatchCodes(document.getElementById('batchRedeemCodes').value);
            document.getElementById('batchCodeCount').textContent = codes.length;
        }

        // 加载批量兑换任务状态
        async function loadBatchRedeemStatus(accountId) {
            try {
                const data = await apiCall(`/api/accounts/${accountId}/batch-redeem`);

                if (!data.task) {
                    // 没有任务，显示输入区域
                    document.getElementById('batchProgressSection').style.display = 'none';
                    document.getElementById('batchRedeemCodes').disabled = false;
                    updateBatchButtons(null);
                    return;
                }

                const task = data.task;
                currentBatchTaskId = task.id;

                // 显示进度区域
                document.getElementById('batchProgressSection').style.display = 'block';

                // 更新状态徽章
                const statusBadge = document.getElementById('batchStatusBadge');
                statusBadge.className = 'batch-status-badge ' + task.status;
                const statusTexts = {
                    'pending': '等待中',
                    'running': '运行中',
                    'paused': '已暂停',
                    'completed': '已完成',
                    'cancelled': '已取消'
                };
                statusBadge.textContent = statusTexts[task.status] || task.status;

                // 更新进度数字
                document.getElementById('batchCurrentIndex').textContent = task.current_index;
                document.getElementById('batchTotalCount').textContent = task.total_count;
                document.getElementById('batchSuccessCount').textContent = task.success_count;
                document.getElementById('batchFailCount').textContent = task.fail_count;

                // 更新倒计时
                updateBatchCountdown(task.next_execute_at, task.status);

                // 渲染兑换码列表
                renderBatchCodeList(data.progress);

                // 更新按钮状态
                updateBatchButtons(task.status);

                // 如果任务正在运行，禁用输入并开始轮询
                if (task.status === 'running' || task.status === 'paused') {
                    document.getElementById('batchRedeemCodes').disabled = true;
                    if (task.status === 'running') {
                        startBatchProgressPolling(accountId);
                    }
                } else {
                    document.getElementById('batchRedeemCodes').disabled = false;
                    stopBatchProgressPolling();
                }

            } catch (error) {
                console.error('Load batch redeem status error:', error);
            }
        }

        // 更新倒计时显示
        function updateBatchCountdown(nextExecuteAt, status) {
            const countdownEl = document.getElementById('batchNextExecute');

            if (batchCountdownTimer) {
                clearInterval(batchCountdownTimer);
                batchCountdownTimer = null;
            }

            if (!nextExecuteAt || status !== 'running') {
                countdownEl.style.display = 'none';
                return;
            }

            const updateCountdown = () => {
                // 清理时间字符串，移除微秒部分
                let cleanTime = nextExecuteAt;
                if (cleanTime && cleanTime.includes('.')) {
                    cleanTime = cleanTime.split('.')[0];
                }
                const nextTime = new Date(cleanTime.replace(' ', 'T') + '+08:00');

                // 检查时间有效性
                if (isNaN(nextTime.getTime())) {
                    countdownEl.style.display = 'none';
                    return;
                }

                const now = new Date();
                const remaining = nextTime.getTime() - now.getTime();

                if (remaining <= 0) {
                    countdownEl.innerHTML = '⏳ 即将执行下一个兑换码...';
                } else {
                    const hours = Math.floor(remaining / 3600000);
                    const minutes = Math.floor((remaining % 3600000) / 60000);
                    const seconds = Math.floor((remaining % 60000) / 1000);

                    let timeStr = '';
                    if (hours > 0) timeStr += `${hours}小时`;
                    if (minutes > 0 || hours > 0) timeStr += `${minutes}分`;
                    timeStr += `${seconds}秒`;

                    countdownEl.innerHTML = `⏰ 下次执行: ${timeStr}后`;
                }
                countdownEl.style.display = 'block';
            };

            updateCountdown();
            batchCountdownTimer = setInterval(updateCountdown, 1000);
        }

        // 渲染兑换码列表
        function renderBatchCodeList(progress) {
            const listEl = document.getElementById('batchCodeList');

            if (!progress || progress.length === 0) {
                listEl.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">暂无兑换记录</div>';
                return;
            }

            listEl.innerHTML = progress.map(item => {
                let statusClass = '';
                let statusIcon = '';
                let message = '';

                switch (item.status) {
                    case 'success':
                        statusClass = 'success';
                        statusIcon = '✅';
                        message = item.amount ? `+¥${item.amount}` : (item.message || '成功');
                        break;
                    case 'failed':
                        statusClass = 'failed';
                        statusIcon = '❌';
                        message = item.message || '失败';
                        break;
                    case 'waiting':
                        statusClass = 'waiting';
                        statusIcon = '⏰';
                        // 计算倒计时
                        if (item.next_execute_at) {
                            message = formatWaitingTime(item.next_execute_at);
                        } else {
                            message = '等待执行';
                        }
                        break;
                    case 'executing':
                        statusClass = 'executing';
                        statusIcon = '🔄';
                        message = '执行中...';
                        break;
                    default:
                        statusClass = 'pending';
                        statusIcon = '⏳';
                        message = item.message || '等待中';
                }

                return `
                    <div class="batch-code-item ${statusClass}">
                        <span class="status-icon">${statusIcon}</span>
                        <code title="${item.code}">${item.code}</code>
                        <span class="status-message" title="${message}">${message}</span>
                    </div>
                `;
            }).join('');
        }

        // 格式化等待时间
        function formatWaitingTime(nextExecuteAt) {
            if (!nextExecuteAt) return '等待执行';

            let cleanTime = nextExecuteAt;
            if (cleanTime.includes('.')) {
                cleanTime = cleanTime.split('.')[0];
            }
            const nextTime = new Date(cleanTime.replace(' ', 'T') + '+08:00');

            if (isNaN(nextTime.getTime())) {
                return '等待执行';
            }

            const now = new Date();
            const remaining = nextTime.getTime() - now.getTime();

            if (remaining <= 0) {
                return '即将执行';
            }

            const hours = Math.floor(remaining / 3600000);
            const minutes = Math.floor((remaining % 3600000) / 60000);
            const seconds = Math.floor((remaining % 60000) / 1000);

            let timeStr = '';
            if (hours > 0) timeStr += `${hours}时`;
            if (minutes > 0 || hours > 0) timeStr += `${minutes}分`;
            timeStr += `${seconds}秒后`;

            return timeStr;
        }

        // 更新按钮状态
        function updateBatchButtons(status) {
            const startBtn = document.getElementById('startBatchBtn');
            const pauseBtn = document.getElementById('pauseBatchBtn');
            const resumeBtn = document.getElementById('resumeBatchBtn');
            const cancelBtn = document.getElementById('cancelBatchBtn');

            // 隐藏所有
            startBtn.style.display = 'none';
            pauseBtn.style.display = 'none';
            resumeBtn.style.display = 'none';
            cancelBtn.style.display = 'none';

            switch (status) {
                case 'running':
                    pauseBtn.style.display = 'inline-block';
                    cancelBtn.style.display = 'inline-block';
                    break;
                case 'paused':
                    resumeBtn.style.display = 'inline-block';
                    cancelBtn.style.display = 'inline-block';
                    break;
                case 'completed':
                case 'cancelled':
                case null:
                default:
                    startBtn.style.display = 'inline-block';
                    break;
            }
        }

        // 开始批量兑换
        async function startBatchRedeem() {
            const accountId = document.getElementById('redeemAccountId').value;
            const codesInput = document.getElementById('batchRedeemCodes').value;
            const codes = parseBatchCodes(codesInput);

            if (codes.length === 0) {
                showToast('请输入至少一个兑换码', 'error');
                return;
            }

            const btn = document.getElementById('startBatchBtn');
            btn.disabled = true;
            btn.textContent = '创建中...';

            try {
                const result = await apiCall(`/api/accounts/${accountId}/batch-redeem`, {
                    method: 'POST',
                    body: JSON.stringify({ codes })
                });

                if (result.success) {
                    currentBatchTaskId = result.task_id;
                    showToast(`批量兑换任务已创建，共 ${result.total_count} 个兑换码`, 'success');
                    loadBatchRedeemStatus(accountId);
                } else {
                    showToast(result.message || '创建任务失败', 'error');
                }
            } catch (error) {
                showToast('创建任务失败: ' + error.message, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = '开始批量兑换';
            }
        }

        // 暂停批量兑换
        async function pauseBatchRedeem() {
            if (!currentBatchTaskId) return;

            try {
                const result = await apiCall(`/api/batch-redeem/${currentBatchTaskId}/pause`, {
                    method: 'POST'
                });

                if (result.success) {
                    showToast('任务已暂停', 'info');
                    stopBatchProgressPolling();
                    const accountId = document.getElementById('redeemAccountId').value;
                    loadBatchRedeemStatus(accountId);
                } else {
                    showToast(result.message || '暂停失败', 'error');
                }
            } catch (error) {
                showToast('暂停失败: ' + error.message, 'error');
            }
        }

        // 恢复批量兑换
        async function resumeBatchRedeem() {
            if (!currentBatchTaskId) return;

            try {
                const result = await apiCall(`/api/batch-redeem/${currentBatchTaskId}/resume`, {
                    method: 'POST'
                });

                if (result.success) {
                    showToast('任务已恢复', 'success');
                    const accountId = document.getElementById('redeemAccountId').value;
                    loadBatchRedeemStatus(accountId);
                } else {
                    showToast(result.message || '恢复失败', 'error');
                }
            } catch (error) {
                showToast('恢复失败: ' + error.message, 'error');
            }
        }

        // 取消批量兑换
        async function cancelBatchRedeem() {
            if (!currentBatchTaskId) return;

            if (!confirm('确定要取消批量兑换任务吗？已执行的兑换不会撤销。')) {
                return;
            }

            try {
                const result = await apiCall(`/api/batch-redeem/${currentBatchTaskId}/cancel`, {
                    method: 'POST'
                });

                if (result.success) {
                    showToast('任务已取消', 'info');
                    stopBatchProgressPolling();
                    currentBatchTaskId = null;
                    const accountId = document.getElementById('redeemAccountId').value;
                    loadBatchRedeemStatus(accountId);
                } else {
                    showToast(result.message || '取消失败', 'error');
                }
            } catch (error) {
                showToast('取消失败: ' + error.message, 'error');
            }
        }

        // 开始轮询任务进度
        function startBatchProgressPolling(accountId) {
            stopBatchProgressPolling();
            batchRedeemTimer = setInterval(() => {
                loadBatchRedeemStatus(accountId);
            }, 5000);
        }

        // 停止轮询
        function stopBatchProgressPolling() {
            if (batchRedeemTimer) {
                clearInterval(batchRedeemTimer);
                batchRedeemTimer = null;
            }
            if (batchCountdownTimer) {
                clearInterval(batchCountdownTimer);
                batchCountdownTimer = null;
            }
        }

        // 扩展 closeModal 以清理批量兑换定时器
        const originalCloseModal = window.closeModal;
        window.closeModal = function(modalId) {
            if (modalId === 'redeemModal') {
                stopBatchProgressPolling();
            }
            if (typeof originalCloseModal === 'function') {
                originalCloseModal(modalId);
            } else {
                document.getElementById(modalId).style.display = 'none';
            }
        };

        // ========== 邀请码相关函数 ==========

        // 显示邀请码弹窗
        async function showInvitationModal(accountId, accountName) {
            document.getElementById('invitationAccountId').value = accountId;
            document.getElementById('invitationModalTitle').textContent = `🎫 ${accountName} - 邀请码`;
            document.getElementById('invitationModal').style.display = 'flex';

            // 加载邀请码列表（使用缓存）
            await loadInvitationCodes(accountId, false);
        }

        // 刷新邀请码列表（强制从服务器获取）
        async function refreshInvitationCodes() {
            const accountId = document.getElementById('invitationAccountId').value;
            if (!accountId) {
                showToast('账号信息丢失', 'error');
                return;
            }

            const refreshBtn = document.getElementById('refreshInvitationBtn');
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = '🔄 刷新中...';

            try {
                await loadInvitationCodes(accountId, true);
                showToast('邀请码已刷新', 'success');
            } finally {
                refreshBtn.disabled = false;
                refreshBtn.innerHTML = '🔄 刷新';
            }
        }

        // 加载邀请码列表
        async function loadInvitationCodes(accountId, refresh = false) {
            const listEl = document.getElementById('invitationList');
            const totalEl = document.getElementById('invitationTotal');
            const availableEl = document.getElementById('invitationAvailable');
            const totalUsesEl = document.getElementById('invitationTotalUses');
            const priceEl = document.getElementById('invitationPrice');
            const generateBtn = document.getElementById('generateInvitationBtn');

            // 显示加载状态
            listEl.innerHTML = '<div class="invitation-loading">加载中...</div>';
            generateBtn.disabled = true;

            try {
                // 构建 URL，支持 refresh 参数
                const url = refresh
                    ? `/api/accounts/${accountId}/invitation-codes?refresh=true`
                    : `/api/accounts/${accountId}/invitation-codes`;

                const result = await apiCall(url);

                if (!result.success) {
                    listEl.innerHTML = `<div class="invitation-error">${result.message || '加载失败'}</div>`;
                    return;
                }

                // 更新统计信息
                totalEl.textContent = result.stats.total || 0;
                availableEl.textContent = result.stats.available || 0;
                totalUsesEl.textContent = result.stats.total_uses || 0;

                // 更新价格
                if (result.settings && result.settings.price) {
                    priceEl.textContent = result.settings.price;
                }

                // 启用生成按钮（如果允许）
                generateBtn.disabled = !result.settings?.allow_user_generation;

                // 渲染邀请码列表
                const codes = result.codes || [];

                if (codes.length === 0) {
                    listEl.innerHTML = '<div class="invitation-empty">暂无邀请码，点击上方按钮生成</div>';
                    return;
                }

                listEl.innerHTML = codes.map(code => {
                    const isAvailable = code.is_available && code.remaining_uses > 0;
                    const statusClass = isAvailable ? 'available' : 'used';
                    const statusText = isAvailable ? '可用' : '已用完';
                    const inviteUrl = `https://leaflow.net/invite/${code.code}`;
                    const createdTime = formatRelativeTime(code.created_at);

                    return `
                        <div class="invitation-item ${statusClass}">
                            <div class="invitation-main">
                                <code class="invitation-code">${code.code}</code>
                                <span class="invitation-usage">使用次数 ${code.used_count || 0}/${code.max_uses}</span>
                                <span class="invitation-time">创建于 ${createdTime}</span>
                                <span class="invitation-status ${statusClass}">${statusText}</span>
                            </div>
                            <div class="invitation-actions">
                                <button class="btn btn-sm btn-copy" onclick="copyToClipboard('${code.code}')" title="复制邀请码">
                                    📋 复制码
                                </button>
                                <button class="btn btn-sm btn-copy-link" onclick="copyToClipboard('${inviteUrl}')" title="复制邀请链接">
                                    🔗 复制链接
                                </button>
                            </div>
                        </div>
                    `;
                }).join('');

            } catch (error) {
                console.error('Load invitation codes error:', error);
                listEl.innerHTML = `<div class="invitation-error">加载失败: ${error.message}</div>`;
            } finally {
                generateBtn.disabled = false;
            }
        }

        // 创建邀请码
        async function createInvitationCode() {
            const accountId = document.getElementById('invitationAccountId').value;
            const btn = document.getElementById('generateInvitationBtn');

            if (!accountId) {
                showToast('账号信息丢失', 'error');
                return;
            }

            // 确认消费
            const price = document.getElementById('invitationPrice').textContent;
            if (!confirm(`生成邀请码将消耗 ¥${price} 余额，确定继续吗？`)) {
                return;
            }

            btn.disabled = true;
            btn.textContent = '生成中...';

            try {
                const result = await apiCall(`/api/accounts/${accountId}/invitation-codes`, {
                    method: 'POST'
                });

                if (result.success) {
                    showToast(`邀请码创建成功: ${result.code.code}`, 'success');

                    // 延迟1秒后刷新邀请码列表（确保后端数据已更新）
                    setTimeout(async () => {
                        await loadInvitationCodes(accountId, true); // 强制刷新，不使用缓存
                        loadAccounts(); // 更新账户列表
                        loadDashboard(); // 更新仪表盘
                    }, 1000);
                } else {
                    showToast(result.message || '创建失败', 'error');
                }
            } catch (error) {
                showToast('创建失败: ' + error.message, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = '生成邀请码';
            }
        }

        // 复制到剪贴板
        async function copyToClipboard(text) {
            try {
                // 优先使用 Clipboard API
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(text);
                    showToast('已复制到剪贴板', 'success');
                    return;
                }
            } catch (error) {
                console.warn('Clipboard API failed, using fallback:', error);
            }

            // 降级方案：使用 textarea
            try {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.left = '-9999px';
                textarea.style.top = '-9999px';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                textarea.setSelectionRange(0, text.length);
                const success = document.execCommand('copy');
                document.body.removeChild(textarea);

                if (success) {
                    showToast('已复制到剪贴板', 'success');
                } else {
                    showToast('复制失败，请手动复制', 'error');
                }
            } catch (error) {
                console.error('Copy failed:', error);
                showToast('复制失败，请手动复制', 'error');
            }
        }