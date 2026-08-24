const StudentPage = {
    _correctionCases: {},

    render() {
        return `
        <div class="min-h-screen pb-20">
            ${this.renderHeader()}
            <div class="p-4">
                <div id="student-content"></div>
            </div>
            ${this.renderBottomNav()}
        </div>`;
    },
    
    renderHeader() {
        const user = MockData.currentUser;
        return `
        <div class="gradient-primary text-white p-4 rounded-b-3xl shadow-lg">
            <div class="flex items-center justify-between">
                <div>
                    <div class="text-sm opacity-80">欢迎回来</div>
                    <div class="text-xl font-bold">${user.name}</div>
                    <div class="text-sm opacity-80">${user.grade}年级 · ${user.class}</div>
                </div>
                <div class="relative">
                    <button onclick="StudentPage.toggleUserMenu()" class="w-14 h-14 bg-white/20 rounded-full flex items-center justify-center text-2xl hover:bg-white/30 transition">
                        ${user.avatar}
                    </button>
                    <div id="user-menu" class="hidden absolute right-0 top-full mt-2 bg-white rounded-xl shadow-lg border py-2 w-48 z-50">
                        <div class="px-4 py-2 border-b">
                            <div class="text-sm font-medium text-gray-800">${user.name}</div>
                            <div class="text-xs text-gray-500">${user.id}</div>
                        </div>
                        <button onclick="StudentPage.showAccountInfo()" class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2">
                            👤 账号信息
                        </button>
                        <button onclick="StudentPage.showSettings()" class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2">
                            ⚙️ 设置
                        </button>
                        <div class="border-t my-1"></div>
                        <button onclick="App.logout()" class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2">
                            🚪 退出登录
                        </button>
                    </div>
                </div>
            </div>
            <div class="mt-4 grid grid-cols-4 gap-2 text-center text-sm">
                <div class="bg-white/20 rounded-lg p-2">
                    <div class="font-bold text-lg" id="stat-total">-</div>
                    <div class="text-xs opacity-80">总题数</div>
                </div>
                <div class="bg-white/20 rounded-lg p-2">
                    <div class="font-bold text-lg" id="stat-rate">-</div>
                    <div class="text-xs opacity-80">正确率</div>
                </div>
                <div class="bg-white/20 rounded-lg p-2">
                    <div class="font-bold text-lg" id="stat-wrong">-</div>
                    <div class="text-xs opacity-80">错题数</div>
                </div>
                <div class="bg-white/20 rounded-lg p-2">
                    <div class="font-bold text-lg" id="stat-reviewed">-</div>
                    <div class="text-xs opacity-80">已订正</div>
                </div>
            </div>
        </div>`;
    },

    _loadHomeStats() {
        var _u = MockData.currentUser || {};
        var sid = _u.userId || _u.id || 'S-0001';
        if (StudentPage._homeStats) {
            setTimeout(function() { StudentPage._updateStatsDisplay(); }, 100);
        } else {
            Api.fetch('/student/' + sid + '/stats').then(function(stats) {
                StudentPage._homeStats = stats;
                setTimeout(function() { StudentPage._updateStatsDisplay(); }, 100);
            }).catch(function() {
                StudentPage._homeStats = {total_questions:0,correct_rate:0,total_mistakes:0,reviewed_mistakes:0};
                setTimeout(function() { StudentPage._updateStatsDisplay(); }, 100);
            });
        }
    },

    _updateStatsDisplay() {
        var s = StudentPage._homeStats || {};
        var el = document.getElementById('stat-total');
        if (el) el.textContent = s.total_questions || 0;
        el = document.getElementById('stat-rate');
        if (el) el.textContent = (s.correct_rate || 0) + '%';
        el = document.getElementById('stat-wrong');
        if (el) el.textContent = s.total_mistakes || 0;
        el = document.getElementById('stat-reviewed');
        if (el) el.textContent = s.reviewed_mistakes || 0;
    },

    toggleUserMenu() {
        const menu = document.getElementById('user-menu');
        if (menu) {
            menu.classList.toggle('hidden');
        }
    },

    showAccountInfo() {
        this.toggleUserMenu();
        const user = MockData.currentUser;
        App.showModal('👤 账号信息', `
            <div class="text-center mb-4">
                <div class="text-5xl mb-2">${user.avatar}</div>
                <div class="font-bold text-lg">${user.name}</div>
                <div class="text-sm text-gray-500">${user.id}</div>
            </div>
            <div class="space-y-2">
                <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                    <span class="text-gray-600">班级</span>
                    <span class="font-medium">${user.class}</span>
                </div>
                <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                    <span class="text-gray-600">年级</span>
                    <span class="font-medium">${user.grade}年级</span>
                </div>
            </div>
        `);
    },

    showSettings() {
        this.toggleUserMenu();
        App.showModal('⚙️ 设置', `
            <div class="space-y-3">
                <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span>消息通知</span>
                    <input type="checkbox" checked class="w-5 h-5">
                </div>
                <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span>声音提示</span>
                    <input type="checkbox" checked class="w-5 h-5">
                </div>
                <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span>自动播放动画</span>
                    <input type="checkbox" class="w-5 h-5">
                </div>
            </div>
            <p class="text-xs text-gray-500 mt-4 text-center">更多设置功能正在开发中...</p>
        `);
    },

    renderBottomNav() {
        return `
        <div class="fixed bottom-0 left-0 right-0 bg-white shadow-lg border-t">
            <div class="flex justify-around py-2">
                <button onclick="StudentPage.navigate('home')" id="nav-home" class="nav-btn flex flex-col items-center px-3 py-2 rounded-lg transition">
                    <span class="text-2xl">🏠</span>
                    <span class="text-xs mt-1">首页</span>
                </button>
                <button onclick="StudentPage.navigate('camera')" id="nav-camera" class="nav-btn flex flex-col items-center px-3 py-2 rounded-lg transition">
                    <span class="text-2xl">📷</span>
                    <span class="text-xs mt-1">拍照</span>
                </button>
                <button onclick="StudentPage.navigate('mistakes')" id="nav-mistakes" class="nav-btn flex flex-col items-center px-3 py-2 rounded-lg transition">
                    <span class="text-2xl">📝</span>
                    <span class="text-xs mt-1">错题本</span>
                </button>
                <button onclick="StudentPage.navigate('path')" id="nav-path" class="nav-btn flex flex-col items-center px-3 py-2 rounded-lg transition">
                    <span class="text-2xl">🛤️</span>
                    <span class="text-xs mt-1">学习路径</span>
                </button>
                <button onclick="StudentPage.navigate('report')" id="nav-report" class="nav-btn flex flex-col items-center px-3 py-2 rounded-lg transition">
                    <span class="text-2xl">📊</span>
                    <span class="text-xs mt-1">成长报告</span>
                </button>
            </div>
        </div>`;
    },
    
    navigate(page) {
        document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('tab-active'));
        const navMap = { home: 'nav-home', camera: 'nav-camera', mistakes: 'nav-mistakes', path: 'nav-path', report: 'nav-report' };
        const activeBtn = document.getElementById(navMap[page]);
        if (activeBtn) activeBtn.classList.add('tab-active');
        
        const content = document.getElementById('student-content');
        const renderMap = {
            home: this.renderHome,
            camera: this.renderCamera,
            mistakes: this.renderMistakes,
            path: this.renderPath,
            report: this.renderReport
        };
        content.innerHTML = renderMap[page]();
        if (page === 'report') this.initReportCharts();
        if (page === 'path') this.initPathCharts();
    },
    
    renderHome() {
        StudentPage._loadHomeStats();
        StudentPage._loadHomeRecommend();
        return `
        <div class="space-y-4">
            <div onclick="StudentPage.navigate('camera')" class="card-hover bg-gradient-to-r from-purple-500 to-indigo-600 text-white rounded-2xl p-5 cursor-pointer shadow-soft">
                <div class="flex items-center gap-4">
                    <div class="w-16 h-16 bg-white/20 rounded-2xl flex items-center justify-center text-3xl">
                        📷
                    </div>
                    <div>
                        <div class="font-bold text-lg">拍照录入作业</div>
                        <div class="text-sm opacity-90">拍下今日作业，开始学习</div>
                    </div>
                </div>
            </div>
            
            <div class="grid grid-cols-2 gap-3">
                <div onclick="StudentPage.navigate('mistakes')" class="card-hover bg-white rounded-2xl p-4 cursor-pointer shadow-soft border border-gray-100">
                    <div class="text-3xl mb-2">📝</div>
                    <div class="font-bold">错题本</div>
                    <div class="text-sm text-gray-500" id="mistake-count-hint">查看错题本</div>
                </div>
                <div onclick="StudentPage.navigate('path')" class="card-hover bg-white rounded-2xl p-4 cursor-pointer shadow-soft border border-gray-100">
                    <div class="text-3xl mb-2">🛤️</div>
                    <div class="font-bold">学习路径</div>
                    <div class="text-sm text-gray-500" id="path-count-hint">查看学习路径</div>
                </div>
                <div onclick="StudentPage.navigate('report')" class="card-hover bg-white rounded-2xl p-4 cursor-pointer shadow-soft border border-gray-100">
                    <div class="text-3xl mb-2">📊</div>
                    <div class="font-bold">成长报告</div>
                    <div class="text-sm text-gray-500">查看能力评估</div>
                </div>
                <div onclick="StudentPage.showReviewPlan()" class="card-hover bg-white rounded-2xl p-4 cursor-pointer shadow-soft border border-gray-100">
                    <div class="text-3xl mb-2">📅</div>
                    <div class="font-bold">复习计划</div>
                    <div class="text-sm text-gray-500">基于掌握度智能推荐</div>
                </div>
            </div>
            
            <div class="bg-white rounded-2xl p-4 shadow-soft border border-gray-100">
                <div class="flex items-center justify-between mb-3">
                    <div class="font-bold">📚 今日推荐</div>
                    <span class="text-xs text-gray-400">基于你的学习情况</span>
                </div>
                <div id="home-recommend-container" class="space-y-2">
                    <div class="text-xs text-gray-400 text-center py-2">加载中...</div>
                </div>
            </div>
        </div>`;
    },

    _loadHomeRecommend() {
        var self = this;
        setTimeout(async function() {
            var container = document.getElementById('home-recommend-container');
            if (!container) return;
            try {
                var user = MockData.currentUser || {};
                var sid = user.userId || user.id || 'S-0001';
                var weakResult = await Api.fetch('/students/' + sid + '/weak?threshold=60');
                var items = (weakResult.weak_points || []).slice(0, 5);
                if (items.length === 0) {
                    var kpResult = await Api.fetch('/knowledge_points?page=1&page_size=5');
                    items = (kpResult.data || []).map(function(k) { return { knowledge_id: k.id, title: k.title, mastery_level: 0 }; });
                }
                container.innerHTML = items.map(function(item, i) {
                    return '<div class="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">' +
                        '<div class="w-8 h-8 rounded-full bg-red-100 text-red-600 flex items-center justify-center font-bold text-sm">' + (i+1) + '</div>' +
                        '<div class="flex-1"><div class="font-medium text-sm">' + (item.title || item.knowledge_id) + '</div>' +
                        '<div class="text-xs text-gray-500">' + (item.mastery_level ? '掌握度 ' + item.mastery_level + '%' : '建议学习') + '</div></div>' +
                        '<button onclick="StudentPage.startLearning(\'' + item.knowledge_id + '\')" class="text-xs bg-purple-100 text-purple-600 px-2 py-1 rounded">学习</button>' +
                        '</div>';
                }).join('');
                if (items.length === 0) container.innerHTML = '<div class="text-xs text-gray-400 text-center py-2">暂无推荐</div>';
            } catch(e) {
                container.innerHTML = '<div class="text-xs text-gray-400 text-center py-2">加载失败</div>';
            }
        }, 100);
    },

    renderCamera() {
        this._ocrUploadRound = OcrUploadPolicy.startRound();
        return `
        <div class="space-y-4">
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3 text-lg">📷 拍照录入作业</div>
                <div class="text-sm text-gray-500 mb-4">拍下今日的数学作业照片，系统将自动识别题目</div>
                
                <div class="camera-frame h-64 flex items-center justify-center mb-4 bg-gray-50">
                    <div class="text-center text-gray-400">
                        <div class="text-5xl mb-2">📸</div>
                        <div>点击拍照</div>
                        <div class="text-xs mt-1">或从相册选择</div>
                    </div>
                </div>
                
                <div class="flex gap-3">
                    <button onclick="StudentPage.takePhoto()" class="flex-1 bg-purple-600 text-white rounded-xl py-3 font-medium">
                        📸 拍照
                    </button>
                    <button onclick="StudentPage.selectImage()" class="flex-1 bg-gray-100 text-gray-700 rounded-xl py-3 font-medium">
                        🖼️ 相册
                    </button>
                </div>
            </div>
            
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">📋 订正流程说明</div>
                <div class="space-y-3">
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0">1</div>
                        <div>
                            <div class="font-medium text-sm">拍照录入</div>
                            <div class="text-xs text-gray-500">系统自动识别题目内容</div>
                        </div>
                    </div>
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0">2</div>
                        <div>
                            <div class="font-medium text-sm">智能批改</div>
                            <div class="text-xs text-gray-500">自动判对错，标记错题</div>
                        </div>
                    </div>
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0">3</div>
                        <div>
                            <div class="font-medium text-sm">错因分析</div>
                            <div class="text-xs text-gray-500">告知错误原因（预留接口）</div>
                        </div>
                    </div>
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0">4</div>
                        <div>
                            <div class="font-medium text-sm">订正重做</div>
                            <div class="text-xs text-gray-500">做错继续订正，做对进入错题本</div>
                        </div>
                    </div>
                    <div class="flex items-start gap-3">
                        <div class="w-8 h-8 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0">5</div>
                        <div>
                            <div class="font-medium text-sm">计入错题本</div>
                            <div class="text-xs text-gray-500">错题自动加入复习计划</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div onclick="StudentPage.takePhoto()" class="bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-2xl p-4 cursor-pointer shadow-soft">
                <div class="font-bold">🎯 拍照录入作业</div>
                <div class="text-sm opacity-90">查看系统识别和批改示例</div>
            </div>
        </div>`;
    },
    
    takePhoto() {
        this._openImagePicker(true);
    },

    selectImage() {
        this._openImagePicker(false);
    },

    _openImagePicker(useCamera, isReupload = false) {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        if (useCamera) input.capture = 'environment';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (!file) return;
            if (isReupload && !OcrUploadPolicy.beginReupload(this._ensureOcrUploadRound())) {
                return;
            }
            this._handleImageUpload(file);
        };
        input.click();
    },

    _ensureOcrUploadRound() {
        if (!this._ocrUploadRound) {
            this._ocrUploadRound = OcrUploadPolicy.startRound();
        }
        return this._ocrUploadRound;
    },

    _handleImageUpload(file) {
        if (!file) return;
        // 显示加载中
        const loadDiv = document.createElement('div');
        loadDiv.className = 'ocr-loading-overlay fixed inset-0 bg-black/50 z-50 flex items-center justify-center';
        loadDiv.innerHTML = '<div class="bg-white rounded-2xl p-8 text-center"><div class="text-4xl mb-3">分析中...</div><div class="font-medium">正在识别图片</div></div>';
        document.body.appendChild(loadDiv);

        const reader = new FileReader();
        reader.onload = async () => {
            try {
                const user = MockData.currentUser || {};
                const studentId = user.userId || user.id || 'S-0001';
                const gradeValue = user.grade || '三年级';
                const gradeNames = ['零年级', '一年级', '二年级', '三年级', '四年级', '五年级', '六年级'];
                const grade = typeof gradeValue === 'number' ? gradeNames[gradeValue] : gradeValue;
                const gatewayResponse = await Api.submitImage(studentId, reader.result, grade || '三年级');
                loadDiv.remove();
                if (gatewayResponse && gatewayResponse.status === 'success' && gatewayResponse.data) {
                    this._ocrUploadRound = null;
                    this._showSubmissionResult(gatewayResponse.data, reader.result);
                    return;
                }
                if (gatewayResponse && gatewayResponse.data && gatewayResponse.data.ocr) {
                    this._showSubmissionResult(gatewayResponse.data, reader.result);
                    return;
                }
                if (gatewayResponse) {
                    const data = gatewayResponse.data || gatewayResponse;
                    const rawMarkdown = data.markdown || '';
                    const confidence = parseFloat(data.confidence || 0);
                    const confidencePct = (confidence * 100).toFixed(0);
                    const engine = data.engine || '';

                    if (!OcrUploadPolicy.isAccepted(confidence)) {
                        this._showLowConfidenceUploadDialog(confidence);
                        return;
                    }
                    this._ocrUploadRound = null;

                    // 提取纯文本（去掉 markdown 标题标记）
                    const cleanText = rawMarkdown
                        .replace(/^##\s+.*$/gm, '')
                        .replace(/^###\s+.*$/gm, '')
                        .replace(/^---$/gm, '')
                        .replace(/\$\$/g, '')
                        .trim();

                    // 置信度颜色
                    var confColor = confidence >= 0.7 ? 'text-green-600 bg-green-50' :
                                    confidence >= 0.4 ? 'text-yellow-600 bg-yellow-50' :
                                    'text-red-600 bg-red-50';

                    var confEmoji = confidence >= 0.7 ? '🟢' : confidence >= 0.4 ? '🟡' : '🔴';

                    var resultHTML = '';
                    if (cleanText) {
                        // 按换行拆分，过滤空行
                        var lines = cleanText.split('\n').filter(function(l) { return l.trim(); });
                        resultHTML = '<div class="bg-gray-50 rounded-xl p-4 text-lg text-center font-mono text-gray-800">' +
                            lines.map(function(l) { return '<div class="py-1">' + l + '</div>'; }).join('') +
                            '</div>';
                    } else {
                        resultHTML = '<div class="bg-gray-50 rounded-xl p-4 text-center text-gray-400">(未识别到文字内容)</div>';
                    }

                    var div = document.createElement('div');
                    div.className = 'fixed inset-0 bg-black/50 z-50 flex items-end';
                    div.innerHTML =
                        '<div class="bg-white w-full max-h-[85vh] rounded-t-3xl overflow-auto">' +
                        // 头部
                        '<div class="sticky top-0 bg-white px-5 py-4 border-b z-10">' +
                            '<div class="flex items-center justify-between">' +
                                '<div class="font-bold text-lg">📷 OCR 识别结果</div>' +
                                '<span class="text-xs px-2 py-1 rounded-full ' + confColor + '">' + confEmoji + ' ' + confidencePct + '%</span>' +
                            '</div>' +
                            '<div class="text-xs text-gray-400 mt-1">引擎：' + (engine || '未知') + '</div>' +
                        '</div>' +
                        // 图片预览
                        '<div class="px-5 pt-4">' +
                            '<div class="bg-gray-100 rounded-xl overflow-hidden">' +
                                '<img src="' + reader.result + '" class="w-full max-h-48 object-contain" alt="上传图片">' +
                            '</div>' +
                        '</div>' +
                        // 识别结果
                        '<div class="p-5 space-y-4">' +
                            '<div>' +
                                '<div class="text-sm font-medium text-gray-500 mb-2">📝 识别内容</div>' +
                                resultHTML +
                            '</div>' +
                            // 原始 markdown（可折叠）
                            (rawMarkdown !== cleanText && rawMarkdown.length > cleanText.length ? '' +
                            '<details class="bg-gray-50 rounded-xl p-3">' +
                                '<summary class="text-xs text-gray-400 cursor-pointer">查看原始识别结果</summary>' +
                                '<pre class="text-xs text-gray-500 mt-2 whitespace-pre-wrap">' + rawMarkdown + '</pre>' +
                            '</details>' : '') +
                            // 按钮
                            '<button onclick="StudentPage.takePhoto()" class="w-full bg-purple-600 text-white rounded-xl py-3 font-medium">' +
                                '📸 继续拍照' +
                            '</button>' +
                            '<button onclick="this.closest(\'.fixed\').remove(); StudentPage.navigate(\'home\')" class="w-full bg-gray-100 text-gray-700 rounded-xl py-3">' +
                                '返回首页' +
                            '</button>' +
                        '</div>' +
                        '</div>';
                    document.body.appendChild(div);
                } else this._showOcrServiceFailureDialog();
            } catch (e) {
                loadDiv.remove();
                const message = e && e.message ? e.message : '网关未返回有效结果';
                this._showOcrServiceFailureDialog(message);
            }
        };
        reader.readAsDataURL(file);
    },

    _escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },

    _showSubmissionResult(data, imageData) {
        const safe = this._escapeHtml.bind(this);
        const recognizedQuestion = data.original_question || data.ocr?.analysis_input?.question?.text || '';
        const recognizedAnswer = data.student_write || data.ocr?.analysis_input?.student_answer?.text || '';
        const feedbackDeferred = data.answer_released === false || data.question_pending_review;
        const tags = Array.isArray(data.error_tags) && data.error_tags.length
            ? data.error_tags.map(function(tag) { return '<li><b>' + safe(tag.level3 || tag.error_id) + '</b>（' + safe(tag.level1) + ' / ' + safe(tag.level2) + '）</li>'; }).join('')
            : '<li>暂无可确认的具体错因</li>';
        const hints = Array.isArray(data.hints) && data.hints.length
            ? data.hints.map(function(item) { return '<li>' + safe(item) + '</li>'; }).join('')
            : '<li>暂无提示</li>';
        const practices = Array.isArray(data.practice_list) && data.practice_list.length
            ? data.practice_list.map(function(item) {
                return '<div class="p-3 border rounded-xl"><div class="font-medium">' + safe(item.question_description) + '</div><div class="text-xs text-gray-500 mt-1">难度：' + safe(item.difficulty) + ' · 答案：' + safe(item.answer) + '</div><div class="text-xs text-gray-600 mt-1">' + safe(item.solution) + '</div></div>';
            }).join('')
            : '<div class="text-sm text-gray-500">暂无已核验变式题' + (data.practice_fallback_reason ? '：' + safe(data.practice_fallback_reason) : '') + '</div>';
        const wrong = data.judge_result === 'wrong';
        if (wrong && data.mistake_case_id) {
            this._correctionCases[data.mistake_case_id] = {
                mistake_case_id: data.mistake_case_id,
                question_text: data.original_question || '',
                student_answer: data.student_write || ''
            };
        }
        const statusText = data.judge_result === 'correct' ? '判定正确' : wrong ? '判定错误' : '暂无法判定';
        const statusClass = data.judge_result === 'correct' ? 'text-green-700 bg-green-50' : wrong ? 'text-red-700 bg-red-50' : 'text-yellow-700 bg-yellow-50';
        const answerExplanation = data.answer_released === false ? '<div class="text-sm text-gray-500">完整答案暂未放行，请先完成引导订正。</div>' : safe(data.final_answer_explanation || '暂无完整讲解');
        const dialog = document.createElement('div');
        dialog.className = 'submission-result-dialog fixed inset-0 bg-black/50 z-50 flex items-end';
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        dialog.innerHTML = '<div class="bg-white w-full max-h-[90vh] rounded-t-3xl overflow-auto">' +
            '<div class="sticky top-0 bg-white px-5 py-4 border-b flex items-center justify-between"><div class="font-bold text-lg">拍照判题结果</div><span class="px-2 py-1 rounded-full text-xs ' + statusClass + '">' + statusText + '</span></div>' +
            '<div class="p-5 space-y-4">' +
            (imageData ? '<img src="' + safe(imageData) + '" class="w-full max-h-40 object-contain bg-gray-100 rounded-xl" alt="提交的作业图片">' : '') +
            '<div class="p-3 rounded-xl bg-gray-50"><div class="text-xs text-gray-500">识别题目</div><div class="text-sm mt-1 whitespace-pre-wrap">' + safe(recognizedQuestion || '未返回题干') + '</div><div class="text-xs text-gray-500 mt-3">识别作答</div><div class="text-sm mt-1 whitespace-pre-wrap">' + safe(recognizedAnswer || '未返回作答') + '</div></div>' +
            (data.question_pending_review ? '<div class="text-sm text-amber-700 bg-amber-50 rounded-xl p-3">该题是新识别题目，已加入待审核题库；教师审核前不显示完整答案和错因。</div>' : '') +
            (feedbackDeferred ? '' : '<div class="p-3 rounded-xl bg-gray-50"><div class="text-xs text-gray-500">错因标签</div><ul class="list-disc pl-5 mt-1 text-sm space-y-1">' + tags + '</ul></div>' +
            '<div class="p-3 rounded-xl bg-blue-50"><div class="text-xs text-gray-500">关联知识点</div><div class="font-medium mt-1">' + safe(data.knowledge_scope || data.knowledge_id || '未确定') + '</div><div class="text-sm mt-2">' + safe(data.knowledge_explanation || '暂无知识点讲解') + '</div></div>' +
            '<div class="p-3 rounded-xl bg-amber-50"><div class="text-xs text-gray-500">教学提示</div><ul class="list-disc pl-5 mt-1 text-sm space-y-1">' + hints + '</ul></div>' +
            '<div class="p-3 rounded-xl bg-purple-50"><div class="text-xs text-gray-500">引导讲解</div><div class="text-sm mt-1 whitespace-pre-wrap">' + safe(data.guided_explanation || data.explanation || '暂无引导讲解') + '</div><div class="text-xs text-gray-500 mt-3">完整讲解</div><div class="text-sm mt-1 whitespace-pre-wrap">' + answerExplanation + '</div></div>' +
            '<div><div class="font-medium mb-2">变式练习 · ' + safe(data.teaching_mode || '') + '</div><div class="space-y-2">' + practices + '</div></div>') +
            (data.review_plan ? '<div class="text-sm text-green-700 bg-green-50 rounded-xl p-3">已生成复习计划：' + safe(data.review_plan.review_plan_id || '') + '</div>' : '') +
            (data.fallback_used ? '<div class="text-xs text-gray-500">本次部分内容使用降级方案：' + safe(data.fallback_reason || '下游服务未提供完整结果') + '</div>' : '') +
            (wrong && data.mistake_case_id ? '<button type="button" class="w-full bg-red-500 text-white rounded-xl py-3 font-medium" onclick="StudentPage.doCorrection(\'' + safe(data.mistake_case_id) + '\')">立即订正</button>' : '') +
            '<button type="button" class="w-full bg-purple-600 text-white rounded-xl py-3 font-medium" onclick="this.closest(\'.submission-result-dialog\').remove()">完成</button>' +
            '</div></div>';
        document.body.appendChild(dialog);
    },

    _showLowConfidenceUploadDialog(confidence) {
        const existingDialog = document.querySelector('.ocr-confidence-dialog');
        if (existingDialog) existingDialog.remove();

        const retryState = OcrUploadPolicy.lowConfidenceState(this._ensureOcrUploadRound());
        const confidencePct = (confidence * 100).toFixed(0);
        const action = retryState.canRetry
            ? '<button type="button" data-ocr-retry class="w-full bg-purple-600 text-white rounded-xl py-3 font-medium" onclick="StudentPage.retryOcrUpload()">重新上传（还可重传 ' + retryState.remainingReuploads + ' 次）</button>'
            : '<button type="button" data-ocr-home class="w-full bg-gray-800 text-white rounded-xl py-3 font-medium" onclick="this.closest(\'.ocr-confidence-dialog\').remove(); StudentPage.navigate(\'home\')">返回首页</button>';
        const limitHint = retryState.canRetry
            ? '请保持画面稳定、光线充足并让题目完整入镜。'
            : '本轮已达到 3 次重新上传上限，请返回首页后重新开始。';
        const dialog = document.createElement('div');
        dialog.className = 'ocr-confidence-dialog fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center sm:justify-center';
        dialog.setAttribute('role', 'alertdialog');
        dialog.setAttribute('aria-modal', 'true');
        dialog.setAttribute('aria-labelledby', 'ocr-confidence-title');
        dialog.innerHTML =
            '<div class="bg-white w-full sm:max-w-md rounded-t-3xl sm:rounded-2xl p-6 space-y-4">' +
                '<div class="flex items-start gap-3">' +
                    '<span class="text-2xl" aria-hidden="true">⚠️</span>' +
                    '<div><h2 id="ocr-confidence-title" class="font-bold text-lg text-gray-900">照片模糊，请重新上传</h2>' +
                    '<p class="text-sm text-gray-600 mt-1">识别置信度为 ' + confidencePct + '%，未达到 80% 的判题要求。</p></div>' +
                '</div>' +
                '<p class="text-sm text-gray-500">' + limitHint + '</p>' +
                action +
            '</div>';
        document.body.appendChild(dialog);
        const primaryButton = dialog.querySelector('[data-ocr-retry], [data-ocr-home]');
        if (primaryButton) primaryButton.focus();
    },

    retryOcrUpload() {
        const retryState = OcrUploadPolicy.lowConfidenceState(this._ensureOcrUploadRound());
        if (!retryState.canRetry) return;
        const dialog = document.querySelector('.ocr-confidence-dialog');
        if (dialog) dialog.remove();
        this._openImagePicker(true, true);
    },

    _showOcrServiceFailureDialog(message) {
        const dialog = document.createElement('div');
        dialog.className = 'fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center sm:justify-center';
        dialog.setAttribute('role', 'alertdialog');
        dialog.setAttribute('aria-modal', 'true');
        dialog.innerHTML =
            '<div class="bg-white w-full sm:max-w-md rounded-t-3xl sm:rounded-2xl p-6 space-y-4">' +
                '<h2 class="font-bold text-lg text-gray-900">暂时无法识别照片</h2>' +
                '<p class="text-sm text-gray-600">' + this._escapeHtml(message || '识别服务未返回有效结果，本次照片不会进入判题模块。') + '</p>' +
                '<button type="button" class="w-full bg-purple-600 text-white rounded-xl py-3 font-medium" onclick="this.closest(\'.fixed\').remove(); StudentPage.selectImage()">重新选择照片</button>' +
            '</div>';
        document.body.appendChild(dialog);
    },

    doCorrection(mistakeCaseId) {
        var item = this._correctionCases[mistakeCaseId];
        if (!item) {
            alert('未找到对应错题，请刷新错题本后重试');
            return;
        }
        var safe = this._escapeHtml.bind(this);
        const correctionDiv = document.createElement('div');
        correctionDiv.id = 'mistake-correction-dialog';
        correctionDiv.className = 'fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4';
        correctionDiv.innerHTML = `
            <div class="bg-white rounded-2xl p-5 w-full max-w-sm">
                <div class="text-center mb-4">
                    <div class="text-4xl mb-2">✏️</div>
                    <div class="font-bold text-lg">订正练习</div>
                    <div class="text-sm text-gray-500">重新完成这道错题</div>
                </div>
                <div class="p-4 bg-gray-50 rounded-xl mb-4">
                    <div class="font-medium">${safe(item.question_text)}</div>
                    <div class="text-xs text-red-600 mt-2">上次答案：${safe(item.student_answer || '未记录')}</div>
                </div>
                <input id="correction-answer" type="text" placeholder="输入你的答案" class="w-full border rounded-xl px-4 py-3 mb-4 text-center text-lg">
                <div id="correction-feedback" class="hidden text-sm rounded-xl p-3 mb-3"></div>
                <button id="correction-submit" onclick="StudentPage.checkCorrection('${safe(mistakeCaseId)}')" class="w-full bg-purple-600 text-white rounded-xl py-3 font-medium">提交答案</button>
                <button onclick="this.closest('.fixed').remove()" class="w-full mt-2 text-gray-500 py-2">取消</button>
            </div>
        `;
        document.body.appendChild(correctionDiv);
    },
    
    async checkCorrection(mistakeCaseId) {
        const answer = document.getElementById('correction-answer').value;
        if (!answer.trim()) {
            alert('请输入订正答案');
            return;
        }
        var item = this._correctionCases[mistakeCaseId];
        if (!item) return;
        var button = document.getElementById('correction-submit');
        var feedback = document.getElementById('correction-feedback');
        button.disabled = true;
        button.textContent = '判定中...';
        try {
            var result = await Api.submitMistakeCorrection(mistakeCaseId, item.question_text, answer.trim());
            feedback.classList.remove('hidden', 'bg-red-50', 'text-red-700', 'bg-green-50', 'text-green-700');
            feedback.classList.add(result.is_correct ? 'bg-green-50' : 'bg-red-50');
            feedback.classList.add(result.is_correct ? 'text-green-700' : 'text-red-700');
            feedback.textContent = (result.is_correct ? '订正正确，错题已完成。' : '答案仍不正确，请根据反馈继续订正。') +
                ' 教学难度：' + result.teaching_difficulty + '。' + (result.step_feedback || '');
            if (result.is_correct) {
                delete this._correctionCases[mistakeCaseId];
                this._homeStats = null;
                button.textContent = '完成';
                button.onclick = function() {
                    var dialog = document.getElementById('mistake-correction-dialog');
                    if (dialog) dialog.remove();
                    StudentPage.navigate('mistakes');
                };
                return;
            }
        } catch (error) {
            feedback.classList.remove('hidden');
            feedback.className = 'text-sm rounded-xl p-3 mb-3 bg-red-50 text-red-700';
            feedback.textContent = '订正提交失败：' + (error.message || '请重试');
        }
        button.disabled = false;
        button.textContent = '再次提交';
    },
    
    showReviewPlan() {
        const user = MockData.currentUser;
        if (!user) return;
        const studentId = user.id;

        const planDiv = document.createElement('div');
        planDiv.className = 'fixed inset-0 bg-black/50 z-50 flex items-end';
        planDiv.id = 'review-plan-modal';
        planDiv.innerHTML = `
            <div class="bg-white w-full max-h-[85vh] rounded-t-3xl overflow-auto">
                <div class="sticky top-0 bg-white p-4 border-b flex items-center justify-between">
                    <div class="font-bold text-lg">📅 我的复习计划</div>
                    <button onclick="document.getElementById('review-plan-modal').remove()" class="text-gray-400 hover:text-gray-600">✕</button>
                </div>
                <div class="p-4">
                    <div id="review-plan-content">
                        <div class="text-center py-8">
                            <div class="text-4xl mb-3">📊</div>
                            <div class="font-medium mb-2">准备生成复习计划</div>
                            <div class="text-sm text-gray-500">基于你的知识图谱掌握度数据</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(planDiv);
        this.loadReviewPlans(studentId);
    },

    async loadReviewPlans(studentId) {
        const content = document.getElementById('review-plan-content');
        if (!content) return;

        content.innerHTML = `
            <div class="space-y-3">
                <div onclick="StudentPage.generateNewPlan('${studentId}')" class="card-hover gradient-primary text-white rounded-2xl p-4 cursor-pointer shadow-soft">
                    <div class="flex items-center gap-3">
                        <div class="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center text-2xl">✨</div>
                        <div>
                            <div class="font-bold">生成今日复习计划</div>
                            <div class="text-sm opacity-90">基于你的掌握度智能推荐题目</div>
                        </div>
                    </div>
                </div>
                <div class="text-xs text-gray-500 text-center mt-4">
                    💡 系统会根据你在知识图谱中的掌握度数据，为你生成个性化复习计划
                </div>
            </div>
        `;
    },

    async generateNewPlan(studentId) {
        const content = document.getElementById('review-plan-content');
        if (!content) return;

        content.innerHTML = `
            <div class="space-y-3">
                <div class="p-4 bg-purple-50 border border-purple-200 rounded-xl">
                    <div class="font-medium text-sm mb-3">📝 设置复习计划</div>
                    <div class="text-xs text-gray-600 mb-3">请选择题目数量（1-30题）</div>
                    <div class="grid grid-cols-5 gap-2 mb-3" id="plan-count-options">
                        ${[5, 10, 15, 20, 25].map(n => `
                            <button class="plan-count-btn py-2 rounded-lg text-sm border ${n === 10 ? 'bg-purple-600 text-white border-purple-600' : 'bg-white border-gray-200 text-gray-700'}" data-count="${n}">${n}</button>
                        `).join('')}
                    </div>
                    <div class="flex gap-2">
                        <button id="confirm-plan-btn" class="flex-1 bg-purple-600 text-white py-2 rounded-xl text-sm font-medium">
                            生成计划 (10题)
                        </button>
                        <button onclick="StudentPage.loadReviewPlans('${studentId}')" class="px-4 bg-gray-100 text-gray-600 py-2 rounded-xl text-sm">
                            取消
                        </button>
                    </div>
                </div>
            </div>
        `;

        let selectedCount = 10;
        const countBtns = content.querySelectorAll('.plan-count-btn');
        const confirmBtn = document.getElementById('confirm-plan-btn');
        
        countBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                selectedCount = parseInt(btn.dataset.count);
                countBtns.forEach(b => {
                    b.classList.remove('bg-purple-600', 'text-white', 'border-purple-600');
                    b.classList.add('bg-white', 'border-gray-200', 'text-gray-700');
                });
                btn.classList.remove('bg-white', 'border-gray-200', 'text-gray-700');
                btn.classList.add('bg-purple-600', 'text-white', 'border-purple-600');
                confirmBtn.textContent = `生成计划 (${selectedCount}题)`;
            });
        });

        const doGenerate = async () => {
            content.innerHTML = `
                <div class="text-center py-8">
                    <div class="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                    <div class="text-sm text-gray-600">正在计算优先级并生成计划...</div>
                    <div class="text-xs text-gray-400 mt-1">请稍候</div>
                </div>
            `;

            try {
                const plan = await Api.createReviewPlan(studentId, 'question_count', selectedCount);

                content.innerHTML = `
                    <div class="space-y-3">
                        <div class="p-4 bg-green-50 border border-green-200 rounded-xl">
                            <div class="flex items-center gap-2 mb-2">
                                <span class="text-2xl">🎉</span>
                                <span class="font-bold text-green-700">复习计划已生成！</span>
                            </div>
                            <div class="text-sm text-gray-600">
                                共 ${plan.items ? plan.items.length : 0} 道题目
                            </div>
                        </div>
                        ${plan.items && plan.items.length > 0 ? `
                            <div class="bg-white rounded-xl p-3 border">
                                <div class="font-medium text-sm mb-2">📝 推荐题目</div>
                                <div class="space-y-2 max-h-60 overflow-auto">
                                    ${plan.items.map((item, i) => `
                                        <div class="flex items-center gap-2 p-2 bg-gray-50 rounded-lg text-sm">
                                            <span class="w-6 h-6 bg-purple-100 text-purple-600 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0">${i + 1}</span>
                                            <div class="flex-1 min-w-0">
                                                <div class="truncate">题目 ${item.question_id}</div>
                                                <div class="text-xs text-gray-500">知识点: ${(item.knowledge_point_ids || []).slice(0, 3).join(', ')}${(item.knowledge_point_ids || []).length > 3 ? '...' : ''}</div>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}
                        <button onclick="StudentPage.startReviewPractice('${plan.id}', '${studentId}')" class="w-full gradient-primary text-white py-3 rounded-xl font-medium">
                            🚀 开始练习
                        </button>
                        <button onclick="StudentPage.loadReviewPlans('${studentId}')" class="w-full bg-gray-100 text-gray-600 py-2 rounded-xl text-sm">
                            重新生成
                        </button>
                    </div>
                `;
            } catch (error) {
                console.error('Failed to generate plan:', error);
                content.innerHTML = `
                    <div class="text-center py-8">
                        <div class="text-4xl mb-3">❌</div>
                        <div class="font-medium mb-1">生成失败</div>
                        <div class="text-sm text-gray-500 mb-4">${error.message || '请检查后端服务是否启动'}</div>
                        <button onclick="StudentPage.loadReviewPlans('${studentId}')" class="bg-gray-100 text-gray-600 px-4 py-2 rounded-xl text-sm">重试</button>
                    </div>
                `;
            }
        };

        confirmBtn.addEventListener('click', doGenerate);
    },

    async startReviewPractice(planId, studentId) {
        const content = document.getElementById('review-plan-content');
        if (!content) return;

        content.innerHTML = `
            <div class="text-center py-8">
                <div class="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                <div class="text-sm text-gray-600">正在启动练习会话...</div>
            </div>
        `;

        try {
            const session = await Api.startReviewSession(planId);
            this.currentSession = session;
            this.showPracticeUI(session, planId, studentId);
        } catch (error) {
            console.error('Failed to start session:', error);
            content.innerHTML = `
                <div class="text-center py-8">
                    <div class="text-4xl mb-3">❌</div>
                    <div class="font-medium mb-1">启动失败</div>
                    <div class="text-sm text-gray-500 mb-4">${error.message || '请检查后端服务'}</div>
                    <button onclick="StudentPage.loadReviewPlans('${studentId}')" class="bg-gray-100 text-gray-600 px-4 py-2 rounded-xl text-sm">返回</button>
                </div>
            `;
        }
    },

    showPracticeUI(session, planId, studentId) {
        const content = document.getElementById('review-plan-content');
        if (!content) return;

        const currentQ = session.current_question;
        const isOpen = currentQ && currentQ.question_type === 'open';
        const options = currentQ && currentQ.options && currentQ.options.length > 0 ? currentQ.options : [];

        content.innerHTML = `
            <div class="space-y-4">
                <div class="flex items-center justify-between">
                    <div class="font-bold">✏️ 练习中</div>
                    <div class="text-sm text-gray-500">剩余 ${session.remaining_items_count || 0} 题</div>
                </div>
                <div class="bg-white rounded-xl p-4 border">
                    <div class="text-xs text-gray-500 mb-2">题目 ${currentQ ? currentQ.id : '加载中'} · ${isOpen ? '开放题' : '选择题'}</div>
                    <div class="font-medium mb-4">${currentQ ? (currentQ.prompt || '题目内容加载中...') : '加载中...'}</div>
                    ${isOpen ? `
                    <textarea id="open-answer-input" class="w-full p-3 border rounded-xl text-sm" rows="3" placeholder="请输入答案（多个空用中文逗号隔开，如：百万位，万位）"></textarea>
                    <div class="text-xs text-gray-400 mt-1">💡 小数保留两位，多个答案用中文逗号隔开</div>
                    ` : `
                    <div class="space-y-2">
                        ${options.map((opt, i) => `
                            <label class="quiz-option-label flex items-center gap-3 p-3 border rounded-xl cursor-pointer hover:bg-gray-50 transition" data-idx="${i}">
                                <input type="radio" name="quiz-option" value="${i}" class="w-4 h-4 quiz-radio">
                                <span class="text-sm">${opt}</span>
                            </label>
                        `).join('')}
                    </div>
                    `}
                    <button id="submit-answer-btn" class="w-full mt-4 bg-purple-600 text-white py-2.5 rounded-xl text-sm font-medium">
                        提交答案
                    </button>
                </div>
                <button onclick="StudentPage.pauseAndExit('${session.session_id}')" class="w-full bg-gray-100 text-gray-600 py-2 rounded-xl text-sm">
                    退出练习
                </button>
            </div>
        `;

        this._isOpenQuestion = isOpen;
        this._selectedOption = null;
        this._quizRadios = content.querySelectorAll('.quiz-radio');
        this._quizLabels = content.querySelectorAll('.quiz-option-label');

        this._quizRadios.forEach((radio, idx) => {
            radio.addEventListener('change', () => {
                this._selectedOption = idx;
                this._quizLabels.forEach(l => {
                    l.classList.remove('border-purple-500', 'bg-purple-50');
                });
                this._quizLabels[idx].classList.add('border-purple-500', 'bg-purple-50');
            });
        });

        const submitBtn = document.getElementById('submit-answer-btn');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => {
                if (this._isOpenQuestion) {
                    const input = document.getElementById('open-answer-input');
                    if (!input || !input.value.trim()) {
                        alert('请输入你的答案');
                        return;
                    }
                    this._openAnswer = input.value.trim();
                } else if (this._selectedOption === null) {
                    alert('请先选择一个选项');
                    return;
                }
                this.submitAnswer(session.session_id, currentQ.id, planId, studentId);
            });
        }
    },

    async submitAnswer(sessionId, questionId, planId, studentId) {
        const btn = document.getElementById('submit-answer-btn');
        btn.disabled = true;
        btn.textContent = '提交中...';

        // 诊断日志
        console.log('[submitAnswer]', {
            sessionId, questionId,
            selectedOption: this._selectedOption,
            openAnswer: this._openAnswer,
            isOpenQuestion: this._isOpenQuestion
        });

        try {
            const result = await Api.submitAttempt(sessionId, questionId,
                this._selectedOption, this._openAnswer);

            const isCorrect = result.is_correct;
            const isOpenQuestion = this._isOpenQuestion;
            var correctAnswerDisplay = '';
            if (!isCorrect) {
                if (isOpenQuestion) {
                    var q = this.currentSession?.current_question;
                    correctAnswerDisplay = q ? (q.answer || '').toString() : '';
                } else {
                    var idx = 0; // the question's correct_option wasn't returned
                    correctAnswerDisplay = String.fromCharCode(65 + idx);
                }
            }

            let feedbackHtml = '';
            if (isCorrect) {
                feedbackHtml = `
                    <div class="p-4 bg-green-50 border border-green-200 rounded-xl text-center">
                        <div class="text-3xl mb-2">✅</div>
                        <div class="font-bold text-green-700">回答正确！</div>
                        <button onclick="StudentPage.nextQuestion('${sessionId}', ${result.session_completed}, '${planId}', '${studentId}')" class="w-full mt-4 bg-purple-600 text-white py-2 rounded-xl text-sm">
                            ${result.session_completed ? '查看结果 →' : '下一题 →'}
                        </button>
                    </div>
                `;
            } else {
                var correctionBtn = result.session_completed
                    ? '<button onclick="StudentPage.showCorrectionModal(\'' + result.attempt_id + '\', 0, \'' + sessionId + '\', \'' + planId + '\', \'' + studentId + '\')" class="w-full bg-orange-500 text-white py-2 rounded-xl text-sm mb-2">✏️ 订正</button>'
                    : '<div class="text-xs text-gray-400 mb-2">完成全部题目后可订正</div>';
                feedbackHtml = `
                    <div class="p-4 bg-red-50 border border-red-200 rounded-xl text-center">
                        <div class="text-3xl mb-2">❌</div>
                        <div class="font-bold text-red-700">回答错误</div>
                        <div class="text-sm text-gray-500 mt-1 mb-3">正确答案：${correctAnswerDisplay}</div>
                        ${correctionBtn}
                        <button onclick="StudentPage.nextQuestion('${sessionId}', ${result.session_completed}, '${planId}', '${studentId}')" class="w-full bg-gray-100 text-gray-600 py-2 rounded-xl text-sm">
                            ${result.session_completed ? '查看结果 →' : '下一题 →'}
                        </button>
                    </div>
                `;
            }

            const wrapper = document.createElement('div');
            wrapper.id = 'feedback-overlay';
            wrapper.className = 'fixed inset-0 bg-black/30 flex items-end z-50 p-4';
            wrapper.innerHTML = `
                <div class="bg-white w-full rounded-2xl p-4 max-w-sm mx-auto">
                    ${feedbackHtml}
                </div>
            `;
            document.body.appendChild(wrapper);
        } catch (error) {
            console.error('Failed to submit answer:', error);
            alert('提交失败: ' + (error.message || '请重试') + '\n\n请打开F12→Console查看详细日志');
        } finally {
            btn.disabled = false;
            btn.textContent = '提交答案';
        }
    },

    async nextQuestion(sessionId, sessionCompleted, planId, studentId) {
        const overlay = document.getElementById('feedback-overlay');
        if (overlay) overlay.remove();

        if (sessionCompleted) {
            const content = document.getElementById('review-plan-content');
            content.innerHTML = `
                <div class="text-center py-12">
                    <div class="text-6xl mb-4">🎉</div>
                    <div class="font-bold text-xl mb-2">练习完成！</div>
                    <div class="text-sm text-gray-500 mb-6">你已完成本次复习计划的所有题目</div>
                    <button onclick="document.getElementById('review-plan-modal').remove()" class="gradient-primary text-white px-6 py-2 rounded-xl">
                        返回首页
                    </button>
                </div>
            `;
            return;
        }

        try {
            const session = await Api.getReviewSession(sessionId);
            this.showPracticeUI(session, planId, studentId);
        } catch (error) {
            console.error('Failed to get session:', error);
            alert('获取下一题失败');
        }
    },

    async showCorrectionModal(attemptId, correctOption, sessionId, planId, studentId) {
        // 选择题用选项索引，开放题用文字输入
        const isOpen = this._isOpenQuestion;
        let selectedOption = 0, answer = '';

        if (isOpen) {
            answer = prompt('请输入你的订正答案：', '');
            if (!answer || !answer.trim()) { alert('请输入订正答案'); return; }
        } else {
            const correctLabel = String.fromCharCode(65 + correctOption);
            const note = prompt('订正说明', '正确答案是 ' + correctLabel + '，已理解');
            if (!note) { alert('请输入订正说明'); return; }
            selectedOption = correctOption;
            answer = note;
        }

        try {
            await Api.submitCorrection(attemptId, selectedOption, answer);

            const overlay = document.getElementById('feedback-overlay');
            if (overlay) overlay.remove();

            alert('✅ 订正成功！');
            this.nextQuestion(sessionId, false, planId, studentId);
        } catch (error) {
            alert('订正失败: ' + (error.message || '请重试'));
        }
    },

    async pauseAndExit(sessionId) {
        try {
            const result = await Api.pauseReviewSession(sessionId);
            if (confirm('会话已暂停（用时 ' + Math.floor((result.elapsed_seconds || 0) / 60) + ' 分钟）。确定退出吗？')) {
                document.getElementById('review-plan-modal').remove();
            }
        } catch (error) {
            if (confirm('确定退出练习吗？')) {
                document.getElementById('review-plan-modal').remove();
            }
        }
    },
    
    renderMistakes() {
        // 异步加载真实错题数据
        var self = this;
        setTimeout(async function() {
            var container = document.getElementById('mistakes-content');
            if (!container) return;
            try {
                var user = MockData.currentUser || {};
                var sid = user.userId || user.id || 'S-0001';
                var result = await Api.fetch('/student/' + sid + '/wrong-answers');
                var items = result.data || [];
                // 题目文字优先用接口返回的question_text
                var qTextMap = {};
                for (var i = 0; i < items.length; i++) {
                    if (items[i].question_text) qTextMap[items[i].question_id] = items[i].question_text;
                }
                var uncorrected = items.filter(function(m) { return !m.reviewed; });
                var corrected = items.filter(function(m) { return m.reviewed; });
                var info = { uncorrected: uncorrected, corrected: corrected, qTextMap: qTextMap };
                self._mistakesData = info;
                StudentPage._renderMistakesContent(info);
            } catch(e) {
                container.innerHTML = '<div class="text-center text-gray-400 py-8">加载失败: ' + (e.message || '') + '</div>';
            }
        }, 50);

        return `
        <div class="space-y-4">
            <button onclick="StudentPage.navigate('home')" class="flex items-center gap-2 text-gray-600 py-2">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                <span class="text-sm">返回首页</span>
            </button>
            <div id="mistakes-content">
                <div class="text-center text-gray-400 py-8">加载中...</div>
            </div>
        </div>`;
    },

    _renderMistakesContent(info) {
        var container = document.getElementById('mistakes-content');
        if (!container) return;
        var uncorrected = info.uncorrected;
        var corrected = info.corrected;
        var qTextMap = info.qTextMap;
        var html = '';
        // 统计卡片
        html += '<div class="bg-white rounded-2xl p-4 shadow-soft"><div class="flex gap-4 mb-4">' +
            '<div class="flex-1 text-center p-3 bg-red-50 rounded-xl">' +
                '<div class="text-2xl font-bold text-red-600">' + uncorrected.length + '</div>' +
                '<div class="text-xs text-red-500">待订正</div></div>' +
            '<div class="flex-1 text-center p-3 bg-green-50 rounded-xl">' +
                '<div class="text-2xl font-bold text-green-600">' + corrected.length + '</div>' +
                '<div class="text-xs text-green-500">已订正</div></div>' +
            '</div></div>';
        // 待订正
        if (uncorrected.length > 0) {
            html += '<div class="bg-white rounded-2xl p-4 shadow-soft mt-4"><div class="font-bold mb-3">📝 待订正错题</div><div class="space-y-3">';
            uncorrected.forEach(function(m) {
                StudentPage._correctionCases[m.mistake_case_id || m.id] = m;
                var qText = qTextMap[m.question_id] || m.question_id;
                var date = (m.last_wrong_time || '').substring(0, 10);
                html += '<div class="p-3 bg-red-50 rounded-xl border border-red-100">' +
                    '<div class="flex items-start justify-between gap-2 mb-2"><div class="flex-1">' +
                    '<div class="font-medium text-sm">' + qText + '</div>' +
                    '<div class="text-xs text-gray-500 mt-1">做错 ' + (m.wrong_count || 1) + ' 次 · ' + date + '</div></div>' +
                    '<span class="badge bg-red-200 text-red-700 flex-shrink-0">#' + m.id + '</span></div>' +
                    '<div class="bg-white p-2 rounded text-xs mb-2"><span class="text-gray-500">你的答案: </span><span class="text-red-600 font-medium">' + (m.student_answer || '(未记录)') + '</span></div>' +
                    '<div class="bg-orange-50 p-2 rounded text-xs text-orange-700">💡 错因: ' + (m.error_type || '未分类') + '</div>' +
                    '<button onclick="StudentPage.doCorrection(\'' + (m.mistake_case_id || m.id) + '\')" class="w-full mt-3 bg-red-500 text-white rounded-lg py-2 text-sm">立即订正</button>' +
                    '</div>';
            });
            html += '</div></div>';
        }
        // 已订正
        if (corrected.length > 0) {
            html += '<div class="bg-white rounded-2xl p-4 shadow-soft mt-4"><div class="font-bold mb-3">✅ 已订正错题</div><div class="space-y-3">';
            corrected.forEach(function(m) {
                var qText = qTextMap[m.question_id] || m.question_id;
                html += '<div class="p-3 bg-gray-50 rounded-xl"><div class="flex items-center justify-between gap-2 mb-1">' +
                    '<div class="font-medium text-sm">' + qText + '</div>' +
                    '<span class="badge bg-green-100 text-green-600">已订正</span></div>' +
                    '<div class="text-xs text-gray-500">日期 ' + (m.date || '').substring(0, 10) + '</div></div>';
            });
            html += '</div></div>';
        }
        if (uncorrected.length === 0 && corrected.length === 0) {
            html += '<div class="bg-white rounded-2xl p-8 shadow-soft text-center text-gray-400 mt-4"><div class="text-4xl mb-2">📭</div><div>暂无错题记录</div></div>';
        }
        container.innerHTML = html;
    },

    renderPath() {
        setTimeout(async function() {
            var container = document.getElementById('path-items-container');
            if (!container) return;
            try {
                var user = MockData.currentUser || {};
                var sid = user.userId || user.id || 'S-0001';
                var result = await Api.getLearningPath(sid);
                var items = Array.isArray(result.data) ? result.data : [];
                if (items.length === 0) {
                    container.innerHTML = '<div class="bg-white rounded-2xl p-8 shadow-soft text-center text-gray-500">' +
                        '<div class="text-4xl mb-3">🧭</div>' +
                        '<div class="font-medium text-gray-700">暂无学习路径</div>' +
                        '<div class="text-sm mt-2">' + StudentPage._escapePathText(result.empty_state || '完成一次作答后生成个性化路径') + '</div>' +
                        '</div>';
                    return;
                }

                container.innerHTML = items.map(function(item, index) {
                    var stage = StudentPage._pathStageMeta(item.stage);
                    var prerequisites = Array.isArray(item.prerequisites) ? item.prerequisites : [];
                    var prerequisiteHtml = prerequisites.length > 0
                        ? '<div class="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-600"><span class="font-medium">前置知识：</span>' +
                            prerequisites.map(function(prerequisite) {
                                var mastery = typeof prerequisite.mastery_level === 'number'
                                    ? '（掌握度 ' + StudentPage._formatPathNumber(prerequisite.mastery_level) + '%）'
                                    : '';
                                return StudentPage._escapePathText(prerequisite.title || prerequisite.knowledge_id || '') + mastery;
                            }).join('、') +
                          '</div>'
                        : '';
                    return '<div class="bg-white rounded-2xl p-4 shadow-soft">' +
                        '<div class="flex items-start gap-3">' +
                            '<div class="w-10 h-10 rounded-full ' + stage.numberClass + ' flex items-center justify-center font-bold flex-shrink-0">' + (item.sequence || index + 1) + '</div>' +
                            '<div class="flex-1">' +
                                '<div class="flex items-center justify-between">' +
                                    '<div class="font-bold pr-2">' + StudentPage._escapePathText(item.title || item.knowledge_id || '未命名知识点') + '</div>' +
                                    '<span class="badge ' + stage.badgeClass + '">' + stage.label + '</span>' +
                                '</div>' +
                                '<div class="text-sm text-gray-600 mt-2">' + StudentPage._escapePathText(item.reason || '根据当前学习情况推荐') + '</div>' +
                                '<div class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500 mt-2">' +
                                    '<span>掌握度 ' + StudentPage._formatPathNumber(item.mastery_level) + '%</span>' +
                                    '<span>预计 ' + (item.estimated_minutes || 0) + ' 分钟</span>' +
                                '</div>' +
                                prerequisiteHtml +
                                '<button onclick="StudentPage.startPathLearning(\'' + StudentPage._pathActionId(item.knowledge_id) + '\')" class="mt-3 bg-indigo-500 text-white text-xs px-4 py-2 rounded-lg">开始学习</button>' +
                            '</div></div></div>';
                }).join('');
            } catch(e) {
                container.innerHTML = '<div class="bg-white rounded-2xl p-8 shadow-soft text-center">' +
                    '<div class="text-4xl mb-3">⚠️</div>' +
                    '<div class="font-medium text-gray-700">学习路径加载失败</div>' +
                    '<div class="text-sm text-gray-500 mt-2">' + StudentPage._escapePathText(e.message || '请检查网络或服务状态') + '</div>' +
                    '<button onclick="StudentPage.navigate(\'path\')" class="mt-4 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg text-sm">重试</button>' +
                    '</div>';
            }
        }, 50);

        return `
        <div class="space-y-4">
            <div class="bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-2xl p-4">
                <div class="font-bold text-lg">🛤️ 学习路径推荐</div>
                <div class="text-sm opacity-90 mt-1">按当前掌握度、复习优先级和前置关系生成</div>
            </div>
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">💡 学习路径说明</div>
                <div class="text-sm text-gray-600 space-y-2">
                    <div>• 按序完成知识点，前置知识会优先出现</div>
                    <div>• 每项展示推荐原因、当前掌握度和预计学习时间</div>
                </div>
            </div>
            <div id="path-items-container" class="space-y-3">
                <div class="text-center text-gray-400 py-4">加载中...</div>
            </div>
        </div>`;
    },

    _pathStageMeta(stage) {
        var stages = {
            prerequisite: { label: '前置学习', badgeClass: 'bg-amber-100 text-amber-700', numberClass: 'bg-amber-100 text-amber-700' },
            remedial: { label: '重点补弱', badgeClass: 'bg-red-100 text-red-600', numberClass: 'bg-red-100 text-red-600' },
            consolidation: { label: '巩固提升', badgeClass: 'bg-blue-100 text-blue-700', numberClass: 'bg-blue-100 text-blue-700' },
            extension: { label: '拓展学习', badgeClass: 'bg-green-100 text-green-700', numberClass: 'bg-green-100 text-green-700' }
        };
        return stages[stage] || { label: '建议学习', badgeClass: 'bg-gray-100 text-gray-600', numberClass: 'bg-gray-100 text-gray-600' };
    },

    _formatPathNumber(value) {
        var numericValue = Number(value);
        return Number.isFinite(numericValue) ? numericValue.toFixed(1).replace(/\.0$/, '') : '-';
    },

    _escapePathText(value) {
        return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    },

    _pathActionId(knowledgeId) {
        return encodeURIComponent(String(knowledgeId || '')).replace(/'/g, '%27');
    },

    startPathLearning(encodedKnowledgeId) {
        return this.startLearning(decodeURIComponent(encodedKnowledgeId));
    },
    
    async startLearning(knowledgeId) {
        var modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4';
        modal.innerHTML = '<div class="bg-white rounded-2xl w-full max-w-md max-h-[75vh] overflow-auto p-5">' +
            '<div class="text-center py-4"><div class="text-2xl mb-2">⏳</div><div class="text-gray-500">加载知识点...</div></div>' +
            '</div>';
        document.body.appendChild(modal);

        try {
            var kp = await Api.fetch('/knowledge_points/' + knowledgeId);
            var title = kp.title || knowledgeId;
            modal.querySelector('.bg-white').innerHTML =
                '<div class="flex items-center justify-between mb-4">' +
                    '<div class="font-bold text-lg">📖 ' + title + '</div>' +
                    '<button onclick="this.closest(\'.fixed\').remove()" class="text-gray-400 text-xl">&times;</button>' +
                '</div>' +
                '<div class="space-y-3 mb-4">' +
                    '<div class="p-3 bg-blue-50 rounded-xl"><div class="text-xs text-gray-500 mb-1">知识点讲解</div><div class="text-sm">' + (kp.content || kp.description || '暂无') + '</div></div>' +
                    '<div class="p-3 bg-yellow-50 rounded-xl"><div class="text-xs text-gray-500 mb-1">常见错误</div><div class="text-sm">' + (kp.common_mistakes || '暂无') + '</div></div>' +
                    '<div class="p-3 bg-green-50 rounded-xl"><div class="text-xs text-gray-500 mb-1">教学要点</div><div class="text-sm">' + (kp.teaching_points || '暂无') + '</div></div>' +
                    (kp.key_formulas ? '<div class="p-3 bg-purple-50 rounded-xl"><div class="text-xs text-gray-500 mb-1">关键公式</div><div class="text-sm font-mono">' + kp.key_formulas + '</div></div>' : '') +
                '</div>' +
                '<button onclick="var m=this.closest(\'.fixed\'); m.remove(); StudentPage.navigate(\'home\'); setTimeout(function(){ StudentPage.showReviewPlan(); }, 300)" class="w-full bg-purple-600 text-white rounded-xl py-3 font-medium mb-2">' +
                    '📝 进入复习计划' +
                '</button>' +
                '<button onclick="this.closest(\'.fixed\').remove()" class="w-full bg-gray-100 text-gray-700 rounded-xl py-3">关闭</button>';
        } catch (e) {
            modal.querySelector('.bg-white').innerHTML =
                '<div class="text-center py-4"><div class="text-4xl mb-2">❌</div><div class="text-gray-500">加载失败</div>' +
                '<button onclick="this.closest(\'.fixed\').remove()" class="w-full mt-4 bg-gray-100 py-2 rounded-xl text-sm">关闭</button></div>';
        }
    },
    
    renderReport() {
        var user = MockData.currentUser || {};
        var today = new Date().toISOString().substring(0, 10);
        var html = `
        <div class="space-y-4 pb-24">
            <div class="gradient-primary text-white rounded-2xl p-5 shadow-soft">
                <div class="text-sm opacity-90">📊 成长报告</div>
                <div class="text-xl font-bold mt-1">${user.name || '同学'}的学习分析</div>
                <div class="text-sm opacity-80 mt-1">报告时间: ${today}</div>
            </div>
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">🎯 五维能力雷达</div>
                <div class="flex justify-center">
                    <canvas id="report-radar" width="280" height="280"></canvas>
                </div>
                <div id="report-dimensions" class="grid grid-cols-5 gap-1 mt-2 text-center text-xs text-gray-500"></div>
            </div>
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">📈 知识点掌握总览</div>
                <div id="report-overview-container" class="space-y-2">
                    <div class="text-xs text-gray-400 text-center py-4">加载中...</div>
                </div>
            </div>
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">⚠️ 薄弱知识点</div>
                <div id="report-weak-container" class="space-y-2">
                    <div class="text-xs text-gray-400 text-center py-2">加载中...</div>
                </div>
            </div>
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">💪 已掌握知识点</div>
                <div id="report-mastered-container" class="grid grid-cols-2 gap-2">
                    <div class="text-xs text-gray-400 text-center py-2 col-span-2">加载中...</div>
                </div>
            </div>
        </div>`;

        // 异步加载
        var sid = user.userId || user.id || 'S-0001';
        setTimeout(function() {
            // 五维雷达图 + 掌握度总览
            Api.fetch('/students/' + sid + '/mastery').then(function(data) {
                var items = data.mastery_data || [];

                // --- 五维能力映射 ---
                var dims = { '运算能力':[], '逻辑思维':[], '空间想象':[], '应用理解':[], '学习韧性':[] };
                var mapping = {
                    '运算能力': ['加','减','乘','除','算','法','口算','竖式','进位','退位','混合运算'],
                    '逻辑思维': ['规律','推理','排列','数位','顺序','比较','大小'],
                    '空间想象': ['图形','周长','面积','体','形','角','长度','单位','厘米','米','分米'],
                    '应用理解': ['应用','问题','实际','情境','生活','购物','时间','货币','统计'],
                    '学习韧性': []  // 由最近连续正确/错误次数计算
                };
                for (var d in dims) {
                    if (d === '学习韧性') continue;
                    var keywords = mapping[d];
                    var scores = [];
                    for (var i = 0; i < items.length; i++) {
                        var title = (items[i].title || items[i].knowledge_id || '');
                        for (var j = 0; j < keywords.length; j++) {
                            if (title.indexOf(keywords[j]) >= 0) { scores.push(items[i].mastery_level || 0); break; }
                        }
                    }
                    dims[d] = scores.length > 0 ? Math.round(scores.reduce(function(a,b){return a+b;},0)/scores.length) : 50;
                }
                // 学习韧性 = (1 - 错题数/总题数) * 100，或默认50
                dims['学习韧性'] = 50;

                var dimLabels = Object.keys(dims);
                var dimValues = dimLabels.map(function(k) { return dims[k]; });
                var dimColors = ['#f5576c','#4facfe','#43e97b','#f093fb','#ffa726'];

                // 雷达图
                setTimeout(function() {
                    var ctx = document.getElementById('report-radar');
                    if (ctx && typeof Chart !== 'undefined') {
                        new Chart(ctx, { type:'radar', data:{ labels:dimLabels, datasets:[{
                            label:'能力评分', data:dimValues,
                            backgroundColor:'rgba(102,126,234,0.2)',
                            borderColor:'rgba(102,126,234,1)', borderWidth:2,
                            pointBackgroundColor:dimColors
                        }]}, options:{ scales:{ r:{ beginAtZero:true, max:100, ticks:{stepSize:20} } } } });
                    }
                }, 200);

                // 维度标签
                var dimEl = document.getElementById('report-dimensions');
                if (dimEl) dimEl.innerHTML = dimLabels.map(function(k,i){ return '<div><span style="color:'+dimColors[i]+'">●</span> '+k+'<br>'+dimValues[i]+'</div>'; }).join('');

                // --- 掌握度总览 ---
                var c = document.getElementById('report-overview-container');
                if (!c) return;
                if (items.length === 0) {
                    c.innerHTML = '<div class="text-xs text-gray-400 text-center py-2">暂无数据</div>';
                    return;
                }
                items.sort(function(a, b) { return (a.mastery_level || 0) - (b.mastery_level || 0); });
                var weak = items.filter(function(i) { return (i.mastery_level || 0) < 60; }).length;
                var mid = items.filter(function(i) { var m = i.mastery_level || 0; return m >= 60 && m < 80; }).length;
                var good = items.filter(function(i) { return (i.mastery_level || 0) >= 80; }).length;
                var avg = items.length > 0 ? Math.round(items.reduce(function(s, i) { return s + (i.mastery_level || 0); }, 0) / items.length) : 0;
                c.innerHTML =
                    '<div class="grid grid-cols-4 gap-2 mb-3">' +
                        '<div class="text-center p-2 bg-red-50 rounded-lg"><div class="font-bold text-red-600">' + weak + '</div><div class="text-xs text-red-500">薄弱</div></div>' +
                        '<div class="text-center p-2 bg-yellow-50 rounded-lg"><div class="font-bold text-yellow-600">' + mid + '</div><div class="text-xs text-yellow-500">学习中</div></div>' +
                        '<div class="text-center p-2 bg-green-50 rounded-lg"><div class="font-bold text-green-600">' + good + '</div><div class="text-xs text-green-500">已掌握</div></div>' +
                        '<div class="text-center p-2 bg-blue-50 rounded-lg"><div class="font-bold text-blue-600">' + avg + '%</div><div class="text-xs text-blue-500">平均掌握度</div></div>' +
                    '</div>' +
                    items.slice(0, 10).map(function(k) {
                        var lvl = k.mastery_level || 0;
                        var barColor = lvl >= 80 ? 'bg-green-500' : lvl >= 60 ? 'bg-yellow-500' : 'bg-red-500';
                        return '<div class="flex items-center gap-2"><div class="text-xs w-20 truncate">' + (k.title || k.knowledge_id) + '</div>' +
                            '<div class="flex-1 bg-gray-200 rounded-full h-2"><div class="' + barColor + ' h-2 rounded-full" style="width:' + lvl + '%"></div></div>' +
                            '<div class="text-xs w-10 text-right">' + lvl + '%</div></div>';
                    }).join('');
            }).catch(function() {});

            // 薄弱知识点
            Api.fetch('/students/' + sid + '/weak?threshold=60').then(function(data) {
                var items = data.weak_points || [];
                var c = document.getElementById('report-weak-container');
                if (!c) return;
                if (items.length === 0) {
                    c.innerHTML = '<div class="text-xs text-gray-400 text-center py-2">暂无薄弱知识点 🎉</div>';
                    return;
                }
                c.innerHTML = items.map(function(k) {
                    var lvl = k.mastery_level || 0;
                    return '<div class="p-3 bg-red-50 rounded-xl border border-red-100">' +
                        '<div class="flex items-center justify-between mb-1">' +
                            '<span class="font-medium text-sm">' + (k.title || k.knowledge_id) + '</span>' +
                            '<span class="badge bg-red-200 text-red-700">' + lvl + '%</span>' +
                        '</div>' +
                        '<div class="w-full bg-gray-200 rounded-full h-2">' +
                            '<div class="bg-red-500 h-2 rounded-full" style="width:' + lvl + '%"></div>' +
                        '</div></div>';
                }).join('');
            }).catch(function() {});

            // 已掌握知识点
            Api.fetch('/students/' + sid + '/mastery').then(function(data) {
                var items = (data.mastery_data || []).filter(function(m) { return (m.mastery_level || 0) >= 80; });
                var c = document.getElementById('report-mastered-container');
                if (!c) return;
                if (items.length === 0) {
                    c.innerHTML = '<div class="text-xs text-gray-400 text-center py-2 col-span-2">暂无已掌握知识点</div>';
                    return;
                }
                c.innerHTML = items.map(function(k) {
                    return '<div class="p-2 bg-green-50 rounded-lg text-center">' +
                        '<div class="text-sm font-medium">' + (k.title || k.knowledge_id) + '</div>' +
                        '<div class="text-xs text-green-600">' + (k.mastery_level || 0) + '%</div></div>';
                }).join('');
            }).catch(function() {});
        }, 100);

        return html;
    },

    initReportCharts() {
        // 五维雷达图需要后端聚合计算，原型阶段暂不展示
    },

    _initReportChartsOld() {
        setTimeout(() => {
            const radarCtx = document.getElementById('radarChart');
            if (radarCtx) {
                new Chart(radarCtx, {
                    type: 'radar',
                    data: {
                        labels: ['运算能力', '逻辑思维', '空间想象', '语言推理', '学习韧性'],
                        datasets: [{
                            label: '能力评分',
                            data: MockData.fiveDimensionScores.dimensions.map(d => d.score),
                            backgroundColor: 'rgba(102, 126, 234, 0.2)',
                            borderColor: 'rgba(102, 126, 234, 1)',
                            borderWidth: 2,
                            pointBackgroundColor: 'rgba(102, 126, 234, 1)'
                        }]
                    },
                    options: {
                        scales: {
                            r: {
                                beginAtZero: true,
                                max: 100
                            }
                        }
                    }
                });
            }
            
            const barCtx = document.getElementById('barChart');
            if (barCtx) {
                new Chart(barCtx, {
                    type: 'bar',
                    data: {
                        labels: MockData.fiveDimensionScores.dimensions.map(d => d.label),
                        datasets: [{
                            label: '当前水平',
                            data: MockData.fiveDimensionScores.dimensions.map(d => d.score),
                            backgroundColor: ['#f5576c', '#ffc107', '#28a745', '#17a2b8', '#6f42c1']
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        scales: { x: { beginAtZero: true, max: 100 } }
                    }
                });
            }
        }, 100);
    },
    
    initPathCharts() {}
};
