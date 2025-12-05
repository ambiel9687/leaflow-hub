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
                                <button class="btn btn-success btn-sm" onclick="manualCheckin(${account.id})">签到</button>
                                <button class="btn btn-primary btn-sm" onclick="showRedeemModal(${account.id}, '${escapedName}')">兑换</button>
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
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #a0aec0;">加载中...</td></tr>';

            try {
                const history = await apiCall(`/api/checkin/history/${accountId}`);

                tbody.innerHTML = '';

                if (history && history.length > 0) {
                    history.forEach(record => {
                        const tr = document.createElement('tr');
                        const statusText = record.success ? '成功' : '失败';
                        const statusClass = record.success ? 'badge-success' : 'badge-danger';
                        const time = record.created_at ? new Date(record.created_at).toLocaleString() : '-';
                        const retryTimes = record.retry_times || 0;

                        tr.innerHTML = `
                            <td><input type="checkbox" class="history-checkbox" value="${record.id}"></td>
                            <td><span class="badge ${statusClass}">${statusText}</span></td>
                            <td>${record.message || '-'}</td>
                            <td>${retryTimes > 0 ? retryTimes : '-'}</td>
                            <td>${time}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #a0aec0;">暂无签到记录</td></tr>';
                }
            } catch (error) {
                console.error('Failed to load checkin history:', error);
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #e53e3e;">加载失败</td></tr>';
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
            const modals = ['addAccountModal', 'editAccountModal', 'checkinHistoryModal', 'notificationModal', 'checkinSettingsModal', 'redeemModal'];
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