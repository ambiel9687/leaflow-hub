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
                    
                    document.getElementById('loginContainer').style.display = 'none';
                    document.getElementById('dashboard').style.display = 'block';
                    
                    loadDashboard();
                    loadAccounts();
                    loadNotificationSettings();
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
            
            // 检查是否已登录
            if (authToken) {
                // 验证token是否有效
                fetch('/api/verify', {
                    headers: {
                        'Authorization': 'Bearer ' + authToken
                    }
                }).then(response => {
                    if (response.ok) {
                        // Token有效，直接显示控制面板
                        document.getElementById('loginContainer').style.display = 'none';
                        document.getElementById('dashboard').style.display = 'block';
                        loadDashboard();
                        loadAccounts();
                        loadNotificationSettings();
                    } else {
                        // Token无效，清除并显示登录页面
                        localStorage.removeItem('authToken');
                        authToken = null;
                        document.getElementById('loginContainer').style.display = 'flex';
                        document.getElementById('dashboard').style.display = 'none';
                    }
                }).catch(error => {
                    console.error('Token check error:', error);
                    localStorage.removeItem('authToken');
                    authToken = null;
                    document.getElementById('loginContainer').style.display = 'flex';
                    document.getElementById('dashboard').style.display = 'none';
                });
            } else {
                // 没有token，显示登录页面
                document.getElementById('loginContainer').style.display = 'flex';
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

                const tbody = document.getElementById('todayCheckins');
                tbody.innerHTML = '';
                
                if (data.today_checkins && data.today_checkins.length > 0) {
                    data.today_checkins.forEach(checkin => {
                        const tr = document.createElement('tr');
                        const statusText = checkin.success ? '成功' : '失败';
                        const statusClass = checkin.success ? 'badge-success' : 'badge-danger';
                        const time = checkin.created_at ? new Date(checkin.created_at).toLocaleTimeString() : '-';
                        const retryTimes = checkin.retry_times || 0;
                        const retryBadge = retryTimes > 0 ? `<span class="badge badge-info">${retryTimes}</span>` : '-';
                        
                        tr.innerHTML = `
                            <td>${checkin.name || '-'}</td>
                            <td><span class="badge ${statusClass}">${statusText}</span></td>
                            <td>${checkin.message || '-'}</td>
                            <td>${retryBadge}</td>
                            <td>${time}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #a0aec0;">暂无记录</td></tr>';
                }
            } catch (error) {
                console.error('Failed to load dashboard:', error);
            }
        }

        async function loadAccounts() {
            try {
                const accounts = await apiCall('/api/accounts');
                if (!accounts) return;

                const tbody = document.getElementById('accountsList');
                tbody.innerHTML = '';
                
                if (accounts && accounts.length > 0) {
                    accounts.forEach(account => {
                        const tr = document.createElement('tr');
                        const interval = account.check_interval || 60;
                        const retryCount = account.retry_count || 2;
                        
                        tr.innerHTML = `
                            <td>${account.name}</td>
                            <td>
                                <label class="switch">
                                    <input type="checkbox" ${account.enabled ? 'checked' : ''} onchange="toggleAccount(${account.id}, this.checked)">
                                    <span class="slider"></span>
                                </label>
                            </td>
                            <td>
                                <div class="time-range-input">
                                    <input type="time" value="${account.checkin_time_start || '06:30'}" onchange="updateAccountTime(${account.id}, 'start', this.value)">
                                    <span>-</span>
                                    <input type="time" value="${account.checkin_time_end || '06:40'}" onchange="updateAccountTime(${account.id}, 'end', this.value)">
                                </div>
                            </td>
                            <td>
                                <div class="interval-input">
                                    <input type="number" value="${interval}" min="30" max="3600" onchange="updateAccountInterval(${account.id}, this.value)">
                                    <span>秒</span>
                                </div>
                            </td>
                            <td>
                                <div class="interval-input">
                                    <input type="number" value="${retryCount}" min="0" max="5" onchange="updateAccountRetry(${account.id}, this.value)">
                                    <span>次</span>
                                </div>
                            </td>
                            <td>
                                <button class="btn btn-success btn-sm" onclick="manualCheckin(${account.id})">立即签到</button>
                                <button class="btn btn-info btn-sm" onclick="showEditAccountModal(${account.id}, '${account.name}')">修改</button>
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

        async function updateAccountTime(id, type, value) {
            try {
                const data = {};
                if (type === 'start') {
                    data.checkin_time_start = value;
                } else {
                    data.checkin_time_end = value;
                }
                
                await apiCall(`/api/accounts/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
            } catch (error) {
                showToast('操作失败', 'error');
            }
        }

        async function updateAccountInterval(id, value) {
            try {
                await apiCall(`/api/accounts/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify({ check_interval: parseInt(value) })
                });
            } catch (error) {
                showToast('操作失败', 'error');
            }
        }
        
        async function updateAccountRetry(id, value) {
            try {
                await apiCall(`/api/accounts/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify({ retry_count: parseInt(value) })
                });
            } catch (error) {
                showToast('操作失败', 'error');
            }
        }

        async function manualCheckin(id) {
            if (confirm('确定立即执行签到吗？')) {
                try {
                    await apiCall(`/api/checkin/manual/${id}`, { method: 'POST' });
                    showToast('签到任务已触发', 'success');
                    setTimeout(loadDashboard, 2000);
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
                } catch (error) {
                    showToast('操作失败: ' + error.message, 'error');
                }
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
                
                setTimeout(loadNotificationSettings, 500);
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
        
        function showEditAccountModal(accountId, accountName) {
            document.getElementById('editAccountId').value = accountId;
            document.getElementById('editAccountModal').style.display = 'flex';
        }

        function closeModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
            
            if (modalId === 'addAccountModal') {
                document.getElementById('accountName').value = '';
                document.getElementById('checkinTimeStart').value = '06:30';
                document.getElementById('checkinTimeEnd').value = '06:40';
                document.getElementById('checkInterval').value = '60';
                document.getElementById('retryCount').value = '2';
                document.getElementById('tokenData').value = '';
            } else if (modalId === 'editAccountModal') {  
                document.getElementById('editAccountId').value = '';
                document.getElementById('editTokenData').value = '';
            }
        }

        async function addAccount() {
            try {
                const account = {
                    name: document.getElementById('accountName').value,
                    checkin_time_start: document.getElementById('checkinTimeStart').value,
                    checkin_time_end: document.getElementById('checkinTimeEnd').value,
                    check_interval: parseInt(document.getElementById('checkInterval').value),
                    retry_count: parseInt(document.getElementById('retryCount').value),
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
        
        async function updateAccountCookie() {
            try {
                const accountId = document.getElementById('editAccountId').value;
                const tokenData = document.getElementById('editTokenData').value;
                
                if (!tokenData) {
                    showToast('请输入Cookie数据', 'error');
                    return;
                }
                
                await apiCall(`/api/accounts/${accountId}`, {
                    method: 'PUT',
                    body: JSON.stringify({ token_data: tokenData })
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
            const modals = ['addAccountModal', 'editAccountModal'];
            modals.forEach(modalId => {
                const modal = document.getElementById(modalId);
                if (event.target == modal) {
                    closeModal(modalId);
                }
            });
        }

        // 定期刷新dashboard数据
        setInterval(() => {
            if (authToken && document.getElementById('dashboard').style.display === 'block') {
                loadDashboard();
            }
        }, 60000); // 每分钟刷新一次