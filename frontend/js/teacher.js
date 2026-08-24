const TeacherPage = {
    currentClassName: null,
    currentStudents: [],
    currentClassData: null,
    currentClassMastery: [],
    isLoading: false,

    render() {
        return `
        <div class="min-h-screen bg-gray-50">
            ${this.renderHeader()}
            <div class="p-4">
                <div id="teacher-content">
                    <div class="flex items-center justify-center py-20">
                        <div class="text-center">
                            <div class="text-4xl mb-4">⏳</div>
                            <div class="text-gray-500">加载中...</div>
                        </div>
                    </div>
                </div>
            </div>
            ${this.renderTabBar()}
        </div>`;
    },

    renderHeader() {
        const user = MockData.currentUser;
        const allClasses = (user && user.realClasses) || [];
        const className = this.currentClassName || (allClasses.length > 0 ? allClasses[0] : '加载中...');
        const hasMultipleClasses = allClasses.length > 1;
        const studentCount = this.currentStudents.length;

        return `
        <div class="gradient-success text-white p-4">
            <div class="flex items-center justify-between">
                <div>
                    <div class="text-sm opacity-90">教师工作台</div>
                    <div class="flex items-center gap-2">
                        <div class="text-xl font-bold">${className}</div>
                        ${hasMultipleClasses ? `
                            <button onclick="TeacherPage.showClassSelector()" class="text-sm bg-white/20 px-2 py-0.5 rounded-lg flex items-center gap-1">
                                <span>切换</span>
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                                </svg>
                            </button>
                        ` : ''}
                    </div>
                </div>
                <div class="relative">
                    <button onclick="TeacherPage.toggleUserMenu()" class="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center text-2xl hover:bg-white/30 transition">
                        ${user ? user.avatar : '👩‍🏫'}
                    </button>
                    <div id="user-menu" class="hidden absolute right-0 top-full mt-2 bg-white rounded-xl shadow-lg border py-2 w-48 z-50">
                        <div class="px-4 py-2 border-b">
                            <div class="text-sm font-medium text-gray-800">${user.name}</div>
                            <div class="text-xs text-gray-500">${user.id}</div>
                        </div>
                        <button onclick="TeacherPage.showAccountInfo()" class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2">
                            👤 账号信息
                        </button>
                        <button onclick="TeacherPage.showSettings()" class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2">
                            ⚙️ 设置
                        </button>
                        <div class="border-t my-1"></div>
                        <button onclick="App.logout()" class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2">
                            🚪 退出登录
                        </button>
                    </div>
                </div>
            </div>
            <div class="mt-4 grid grid-cols-4 gap-2 text-center text-xs">
                <div class="bg-white/20 rounded-lg p-2">
                    <div class="font-bold text-lg">${studentCount}</div>
                    <div>学生数</div>
                </div>
                <div class="bg-white/20 rounded-lg p-2">
                    <div class="font-bold text-lg">${studentCount}</div>
                    <div>今日作业</div>
                </div>
                <div class="bg-white/20 rounded-lg p-2">
                    <div class="font-bold text-lg">${Math.floor(studentCount * 0.85)}</div>
                    <div>已提交</div>
                </div>
                <div class="bg-white/20 rounded-lg p-2">
                    <div class="font-bold text-lg">${Math.floor(studentCount * 0.15)}</div>
                    <div>待批改</div>
                </div>
            </div>
        </div>`;
    },

    toggleUserMenu() {
        const menu = document.getElementById('user-menu');
        if (menu) menu.classList.toggle('hidden');
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
                    <span class="text-gray-600">科目</span>
                    <span class="font-medium">${user.subject}</span>
                </div>
                <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                    <span class="text-gray-600">管理班级</span>
                    <span class="font-medium">${user.classes.join('、')}</span>
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

    async showClassSelector() {
        const user = MockData.currentUser;
        if (!user) return;

        const allClasses = user.realClasses || [];

        try {
            const result = await Api.getClasses();
            const classData = result.data || [];

            App.showModal('📚 选择班级', `<div class="space-y-2">
                ${classData.map(c => `
                    <button onclick="TeacherPage.switchClass('${c.class_name}')" class="w-full p-3 ${this.currentClassName === c.class_name ? 'bg-green-100 border-green-500' : 'bg-gray-50'} border rounded-xl text-left flex items-center justify-between">
                        <div>
                            <div class="font-medium">${c.class_name}</div>
                            <div class="text-xs text-gray-500">${c.grade}年级 · ${c.student_count}名学生</div>
                        </div>
                        ${this.currentClassName === c.class_name ? '<span class="text-green-600">✓</span>' : ''}
                    </button>
                `).join('')}
            </div>`);
        } catch (error) {
            console.error('Failed to load classes:', error);
            App.showModal('📚 选择班级', `<div class="text-gray-500 text-center">加载班级列表失败</div>`);
        }
    },

    async switchClass(className) {
        App.closeModal();
        this.currentClassName = className;
        
        const content = document.getElementById('role-content');
        if (content) {
            content.innerHTML = this.render();
        }
        
        await this.loadClassData(className);
        try {
            const masteryResult = await Api.getClassMastery(className);
            this.currentClassMastery = masteryResult.mastery_data || [];
        } catch (e) {
            console.error('Failed to load class mastery:', e);
            this.currentClassMastery = [];
        }
        
        if (content) {
            content.innerHTML = this.render();
        }
        
        this.navigate('dashboard');
    },

    async loadClassData(className) {
        try {
            const result = await Api.getClassStudents(className);
            this.currentStudents = result.data || [];
            this.currentClassName = className;
        } catch (error) {
            console.error('Failed to load class data:', error);
            this.currentStudents = [];
        }
    },

    async init() {
        const user = MockData.currentUser;
        if (!user) return;

        this.isLoading = true;
        const content = document.getElementById('role-content');
        if (content) {
            content.innerHTML = this.render();
        }

        try {
            const classesResult = await Api.getClasses(user.role === 'teacher' ? user.id : null);
            const classes = classesResult.data || [];

            if (user.role === 'teacher') {
                user.realClasses = classes.map(c => c.class_name);
            }

            let targetClass = null;
            if (classes.length > 0) {
                targetClass = classes[0].class_name;
            }

            if (targetClass) {
                await this.loadClassData(targetClass);
                try {
                    const masteryResult = await Api.getClassMastery(targetClass);
                    this.currentClassMastery = masteryResult.mastery_data || [];
                } catch (e) {
                    console.error('Failed to load class mastery:', e);
                    this.currentClassMastery = [];
                }
            }
        } catch (error) {
            console.error('Failed to load classes:', error);
        }

        this.isLoading = false;
        await this.loadBatches();
        if (content) {
            content.innerHTML = this.render();
        }

        await new Promise(resolve => setTimeout(resolve, 100));
        this.navigate('dashboard');
    },

    renderTabBar() {
        return `
        <div class="fixed bottom-0 left-0 right-0 bg-white shadow-lg border-t">
            <div class="flex justify-around py-2">
                <button onclick="TeacherPage.navigate('dashboard')" id="t-dashboard" class="t-nav flex flex-col items-center px-2 py-2 rounded-lg transition">
                    <span class="text-xl">📊</span><span class="text-xs">仪表盘</span>
                </button>
                <button onclick="TeacherPage.navigate('review')" id="t-review" class="t-nav flex flex-col items-center px-2 py-2 rounded-lg transition">
                    <span class="text-xl">📅</span><span class="text-xs">复习计划</span>
                </button>
                <button onclick="TeacherPage.navigate('assignments')" id="t-assignments" class="t-nav flex flex-col items-center px-2 py-2 rounded-lg transition">
                    <span class="text-xl">📋</span><span class="text-xs">作业</span>
                </button>
                <button onclick="TeacherPage.navigate('mistakes')" id="t-mistakes" class="t-nav flex flex-col items-center px-2 py-2 rounded-lg transition">
                    <span class="text-xl">⚠️</span><span class="text-xs">错题分析</span>
                </button>
                <button onclick="TeacherPage.navigate('mastery')" id="t-mastery" class="t-nav flex flex-col items-center px-2 py-2 rounded-lg transition">
                    <span class="text-xl">📈</span><span class="text-xs">掌握度</span>
                </button>
            </div>
        </div>`;
    },

    navigate(page) {
        document.querySelectorAll('.t-nav').forEach(btn => btn.classList.remove('tab-active'));
        const navMap = { dashboard: 't-dashboard', assignments: 't-assignments', mistakes: 't-mistakes', mastery: 't-mastery', review: 't-review' };
        const activeBtn = document.getElementById(navMap[page]);
        if (activeBtn) activeBtn.classList.add('tab-active');

        const content = document.getElementById('teacher-content');
        const renderMap = {
            dashboard: () => this.renderDashboard(),
            assignments: () => this.renderAssignments(),
            mistakes: () => this.renderMistakes(),
            mastery: () => this.renderMastery(),
            review: () => this.renderReviewPlans()
        };
        content.innerHTML = renderMap[page]();
        if (page === 'dashboard') this.initDashboardCharts();
        if (page === 'mistakes') this.initMistakesCharts();
        if (page === 'mastery') this.initMasteryCharts();
        if (page === 'review') this.initReviewPlans();
    },

    renderDashboard() {
        const students = this.currentStudents;
        const className = this.currentClassName || '';
        const studentCount = students.length;
        const classMastery = this.currentClassMastery || [];

        const weakPoints = classMastery.filter(m => m.avg_mastery < 60);
        const avgMastery = classMastery.length > 0
            ? Math.round(classMastery.reduce((sum, m) => sum + m.avg_mastery, 0) / classMastery.length)
            : 0;
        const masteredPoints = classMastery.filter(m => m.avg_mastery >= 80);

        const avatarForGender = (gender) => {
            if (gender === '男') return '👦';
            if (gender === '女') return '👧';
            return '👤';
        };

        return `
        <div class="space-y-4 pb-24">
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">📊 班级概况</div>
                <div class="grid grid-cols-2 gap-3">
                    <div class="p-3 bg-blue-50 rounded-xl">
                        <div class="text-sm text-gray-600">班级人数</div>
                        <div class="text-2xl font-bold text-blue-600">${studentCount}</div>
                    </div>
                    <div class="p-3 bg-green-50 rounded-xl">
                        <div class="text-sm text-gray-600">平均掌握度</div>
                        <div class="text-2xl font-bold text-green-600">${avgMastery}%</div>
                    </div>
                    <div class="p-3 bg-orange-50 rounded-xl">
                        <div class="text-sm text-gray-600">薄弱知识点</div>
                        <div class="text-2xl font-bold text-orange-600">${weakPoints.length}</div>
                    </div>
                    <div class="p-3 bg-purple-50 rounded-xl">
                        <div class="text-sm text-gray-600">已掌握知识点</div>
                        <div class="text-2xl font-bold text-purple-600">${masteredPoints.length}</div>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="flex items-center justify-between mb-3">
                    <div class="font-bold">👥 学生状态</div>
                    <div class="text-xs text-gray-400">← 左右滑动查看更多 →</div>
                </div>
                <p class="text-xs text-gray-500 mb-3">每个圆圈代表一个学生，点击查看详情</p>
                <div class="student-scroll overflow-x-auto whitespace-nowrap pb-2">
                    ${students.length > 0 ? students.map(s => `
                        <div onclick="TeacherPage.viewStudentDetail('${s.id}')" class="student-circle inline-flex flex-col items-center p-2 rounded-xl hover:bg-gray-100 transition cursor-pointer" style="width: 70px;">
                            <div class="w-12 h-12 rounded-full flex items-center justify-center text-2xl bg-blue-100">
                                ${avatarForGender(s.gender)}
                            </div>
                            <div class="text-xs mt-1 text-center truncate w-full">${s.name}</div>
                        </div>
                    `).join('') : '<div class="text-gray-400 text-sm py-4 text-center w-full">暂无学生数据</div>'}
                </div>
                <div class="flex gap-4 mt-3 text-xs">
                    <div class="flex items-center gap-1">
                        <div class="w-3 h-3 rounded-full bg-blue-400"></div>
                        <span>学生</span>
                    </div>
                    <div class="flex items-center gap-1">
                        <span>共${studentCount}人</span>
                    </div>
                </div>
            </div>

            ${weakPoints.length > 0 ? `
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="flex items-center justify-between mb-3">
                    <div class="font-bold">⚠️ 班级薄弱知识点</div>
                    <span class="text-xs text-gray-400">数据来源：知识图谱</span>
                </div>
                <div class="space-y-2">
                    ${weakPoints.slice(0, 5).map(m => `
                        <div class="p-3 bg-orange-50 rounded-xl">
                            <div class="flex items-center gap-2">
                                <div class="flex-1">
                                    <div class="font-medium text-sm">${m.title}</div>
                                    <div class="text-xs text-gray-500">${m.student_count}名学生掌握</div>
                                </div>
                                <div class="text-right">
                                    <div class="font-bold text-orange-600">${m.avg_mastery}%</div>
                                    <div class="text-xs text-gray-400">平均掌握度</div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
            ` : ''}
        </div>`;
    },

    async viewStudentDetail(studentId) {
        try {
            const studentResult = await Api.getStudent(studentId);
            const masteryResult = await Api.getStudentMastery(studentId);

            const masteryData = masteryResult.mastery_data || [];
            const weakPoints = masteryData.filter(m => m.mastery_level < 60);
            const avgMastery = masteryData.length > 0
                ? Math.round(masteryData.reduce((sum, m) => sum + m.mastery_level, 0) / masteryData.length)
                : 0;

            const avatar = studentResult.gender === '女' ? '👧' : '👦';

            App.showModal(`👤 ${studentResult.name}`, `
                <div class="text-center mb-4">
                    <div class="text-5xl mb-2">${avatar}</div>
                    <div class="font-bold">${studentResult.name}</div>
                    <div class="text-sm text-gray-500">${studentResult.class_name} · ${studentResult.school}</div>
                </div>
                <div class="space-y-2">
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>学生ID</span>
                        <span class="font-medium">${studentResult.id}</span>
                    </div>
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>年级</span>
                        <span class="font-medium">${studentResult.grade}年级</span>
                    </div>
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>平均掌握度</span>
                        <span class="font-medium ${avgMastery >= 80 ? 'text-green-600' : avgMastery >= 60 ? 'text-yellow-600' : 'text-red-600'}">${avgMastery}%</span>
                    </div>
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>薄弱知识点</span>
                        <span class="text-red-600 font-medium">${weakPoints.length}个</span>
                    </div>
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>已掌握知识点</span>
                        <span class="text-green-600 font-medium">${masteryData.filter(m => m.mastery_level >= 80).length}个</span>
                    </div>
                </div>
                <button onclick="TeacherPage.viewStudentReport('${studentId}')" class="w-full mt-4 bg-purple-100 text-purple-600 py-2 rounded-lg text-sm">
                    查看完整成长报告 →
                </button>
            `);
        } catch (error) {
            console.error('Failed to load student detail:', error);
            App.showModal('❌ 错误', '<div>加载学生详情失败，请检查API连接。</div>');
        }
    },

    viewStudentReport(studentId) {
        App.closeModal();
        window.open('http://localhost:3002/growth_report.html', '_blank');
    },

    initDashboardCharts() {
        setTimeout(() => {
            const ctx = document.getElementById('classChart');
            if (ctx) {
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: ['周一', '周二', '周三', '周四', '周五'],
                        datasets: [{
                            label: '提交率',
                            data: [85, 90, 88, 82, 95],
                            borderColor: '#11998e',
                            backgroundColor: 'rgba(17, 153, 142, 0.1)',
                            tension: 0.3,
                            fill: true
                        }, {
                            label: '正确率',
                            data: [78, 75, 80, 72, 85],
                            borderColor: '#f5576c',
                            backgroundColor: 'rgba(245, 87, 108, 0.1)',
                            tension: 0.3,
                            fill: true
                        }]
                    },
                    options: {
                        scales: { y: { beginAtZero: true, max: 100 } }
                    }
                });
            }
        }, 100);
    },

    renderAssignments() {
        const batches = this.batches || [];
        const statusLabel = { locked: '🔒 未放行', partial: '🟡 部分放行', released: '✅ 已放行' };
        const statusColor = { locked: 'bg-red-100 text-red-700', partial: 'bg-yellow-100 text-yellow-700', released: 'bg-green-100 text-green-600' };

        return `
        <div class="space-y-4 pb-20">
            <div onclick="TeacherPage.showCreateBatchModal()" class="card-hover gradient-primary text-white rounded-2xl p-4 cursor-pointer shadow-soft">
                <div class="flex items-center gap-3">
                    <div class="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center text-2xl">📤</div>
                    <div>
                        <div class="font-bold">创建作业批次</div>
                        <div class="text-sm opacity-90">从题库选题，创建批次后答案默认锁定</div>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-2xl p-4 shadow-soft border border-dashed border-green-300">
                <div class="flex items-center justify-between gap-3">
                    <div class="flex items-center gap-3 min-w-0">
                        <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center text-2xl shrink-0">📷</div>
                        <div class="min-w-0">
                            <div class="font-bold text-gray-800">录入标准答案题目</div>
                            <div class="text-sm text-gray-500 truncate">上传包含题目和教师答案的图片，先预览复核再入库</div>
                        </div>
                    </div>
                    <button type="button" onclick="TeacherPage.openQuestionImport()" class="shrink-0 px-3 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700">开始录入</button>
                </div>
            </div>

            <input id="teacher-question-camera" type="file" accept="image/jpeg,image/png,image/webp,image/bmp" capture="environment" class="hidden" onchange="TeacherPage.handleQuestionImportFile(this.files[0])">
            <input id="teacher-question-file" type="file" accept="image/jpeg,image/png,image/webp,image/bmp" class="hidden" onchange="TeacherPage.handleQuestionImportFile(this.files[0])">

            <div id="question-import-modal" class="hidden fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                <div class="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-5">
                    <div class="flex items-center justify-between mb-4">
                        <div>
                            <div class="font-bold text-lg text-gray-800">录入标准答案题目</div>
                            <div class="text-xs text-gray-500 mt-1">图片仅用于本次识别，不会在前端保存</div>
                        </div>
                        <button type="button" onclick="TeacherPage.closeQuestionImport()" class="text-gray-400 hover:text-gray-700 text-xl" title="关闭">×</button>
                    </div>
                    <div class="grid grid-cols-2 gap-3 mb-4">
                        <label class="text-sm text-gray-700">适用年级 <span class="text-red-500">*</span>
                            <select id="teacher-import-grade" class="mt-1 w-full border rounded-lg p-2" required>
                                <option value="">请选择年级</option>
                                <option value="1">一年级</option><option value="2">二年级</option><option value="3">三年级</option>
                                <option value="4">四年级</option><option value="5">五年级</option><option value="6">六年级</option>
                            </select>
                        </label>
                        <label class="text-sm text-gray-700">适用学期
                            <select id="teacher-import-semester" class="mt-1 w-full border rounded-lg p-2">
                                <option value="">不指定</option><option value="上学期">上学期</option><option value="下学期">下学期</option>
                            </select>
                        </label>
                    </div>
                    <div class="grid grid-cols-2 gap-3 mb-4">
                        <button type="button" onclick="TeacherPage.chooseQuestionCamera()" class="py-3 border border-green-300 text-green-700 rounded-lg hover:bg-green-50">📷 拍照</button>
                        <button type="button" onclick="TeacherPage.chooseQuestionFile()" class="py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">▣ 选择图片</button>
                    </div>
                    <div id="question-import-file-name" class="text-sm text-gray-500 bg-gray-50 rounded-lg p-3 mb-4">尚未选择图片</div>
                    <div id="question-import-error" class="hidden text-sm text-red-600 bg-red-50 rounded-lg p-3 mb-4"></div>
                    <div class="space-y-2 mb-5" aria-live="polite">
                        <div class="flex items-center gap-2 text-sm" id="import-stage-upload"><span class="stage-icon">○</span><span>上传图片</span><span class="stage-detail text-gray-400"></span></div>
                        <div class="flex items-center gap-2 text-sm" id="import-stage-ocr"><span class="stage-icon">○</span><span>OCR 识别题目和教师答案</span><span class="stage-detail text-gray-400"></span></div>
                        <div class="flex items-center gap-2 text-sm" id="import-stage-llm"><span class="stage-icon">○</span><span>LLM 独立解题复核</span><span class="stage-detail text-gray-400"></span></div>
                    </div>
                    <button id="question-import-submit" type="button" onclick="TeacherPage.submitQuestionImport()" disabled class="w-full py-3 bg-gray-300 text-white rounded-lg font-medium cursor-not-allowed">上传并生成预览</button>
                </div>
            </div>

            ${batches.length === 0 ? `
            <div class="bg-white rounded-2xl p-8 shadow-soft text-center text-gray-400">
                <div class="text-4xl mb-2">📋</div>
                <div>暂无作业批次</div>
            </div>` : batches.map(b => `
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="flex items-center justify-between mb-3">
                    <div>
                        <div class="font-bold">${b.batch_id}</div>
                        <div class="text-xs text-gray-500">${b.batch_date} · ${b.question_count}道题</div>
                    </div>
                    <span class="badge ${statusColor[b.release_status] || ''}">${statusLabel[b.release_status] || b.release_status}</span>
                </div>
                ${b.release_status === 'locked' ? `
                <div class="flex gap-2">
                    <button onclick="TeacherPage.releaseBatch('${b.batch_id}')" class="flex-1 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600">
                        🔓 一键放行全部
                    </button>
                    <button onclick="TeacherPage.showPartialReleaseModal('${b.batch_id}', ${b.question_count})" class="flex-1 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600">
                        🔍 精细放行
                    </button>
                </div>` : b.release_status === 'partial' ? `
                <div class="flex gap-2">
                    <button onclick="TeacherPage.releaseBatch('${b.batch_id}')" class="flex-1 py-2 bg-green-500 text-white rounded-lg text-sm font-medium hover:bg-green-600">
                        🔓 放行剩余题目
                    </button>
                </div>` : `
                <div class="text-sm text-green-600">全部题目答案已对学生可见</div>`}
            </div>
            `).join('')}

            <div id="batch-modal" class="hidden fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
                <div class="bg-white rounded-2xl w-11/12 max-w-md max-h-96 overflow-y-auto p-4">
                    <div class="font-bold mb-3">创建作业批次</div>
                    <div id="batch-question-list" class="space-y-2 mb-4">
                        <div class="text-gray-400 text-sm">加载题目中...</div>
                    </div>
                    <div class="flex gap-2">
                        <button onclick="TeacherPage.confirmCreateBatch()" class="flex-1 py-2 gradient-primary text-white rounded-lg font-medium">确认创建</button>
                        <button onclick="document.getElementById('batch-modal').classList.add('hidden')" class="py-2 px-4 bg-gray-200 rounded-lg">取消</button>
                    </div>
                </div>
            </div>

            <div id="partial-modal" class="hidden fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
                <div class="bg-white rounded-2xl w-11/12 max-w-md max-h-96 overflow-y-auto p-4">
                    <div class="font-bold mb-3">精细放行 - 选择题目</div>
                    <div id="partial-question-list" class="space-y-2 mb-4"></div>
                    <div class="flex gap-2">
                        <button onclick="TeacherPage.confirmPartialRelease()" class="flex-1 py-2 bg-blue-500 text-white rounded-lg font-medium">确认放行选中题目</button>
                        <button onclick="document.getElementById('partial-modal').classList.add('hidden')" class="py-2 px-4 bg-gray-200 rounded-lg">取消</button>
                    </div>
                </div>
            </div>
        </div>`;
    },

    // ============ 批次管理方法 ============

    batches: [],
    _selectedQuestions: [],
    _partialBatchId: null,
    _partialQuestions: [],
    _questionImportFile: null,
    _questionImportBusy: false,
    _pendingQuestionImportPreview: null,

    async loadBatches() {
        try {
            const user = MockData.currentUser || {};
            const result = await Api.getHomeworkBatches(user.id, user.realClasses?.[0]);
            this.batches = result.data || [];
        } catch (error) {
            console.error('Failed to load homework batches:', error);
            this.batches = [];
        }
    },

    openQuestionImport() {
        const modal = document.getElementById('question-import-modal');
        if (!modal) return;
        modal.classList.remove('hidden');
        this._questionImportFile = null;
        this._questionImportBusy = false;
        this._pendingQuestionImportPreview = null;
        const grade = document.getElementById('teacher-import-grade');
        const userGrade = MockData.currentUser?.grade;
        if (grade && userGrade >= 1 && userGrade <= 6) grade.value = String(userGrade);
        this._resetQuestionImportStages();
    },

    closeQuestionImport() {
        if (this._questionImportBusy) return;
        const modal = document.getElementById('question-import-modal');
        if (modal) modal.classList.add('hidden');
        this._questionImportFile = null;
    },

    chooseQuestionCamera() {
        if (this._questionImportBusy) return;
        const input = document.getElementById('teacher-question-camera');
        if (input) {
            input.value = '';
            input.click();
        }
    },

    chooseQuestionFile() {
        if (this._questionImportBusy) return;
        const input = document.getElementById('teacher-question-file');
        if (input) {
            input.value = '';
            input.click();
        }
    },

    handleQuestionImportFile(file) {
        if (!file) return;
        const errorEl = document.getElementById('question-import-error');
        const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/bmp'];
        const maxSize = 10 * 1024 * 1024;
        if (!allowedTypes.includes(file.type)) {
            this._showQuestionImportError('仅支持 JPEG、PNG、WebP 和 BMP 图片。');
            return;
        }
        if (file.size > maxSize) {
            this._showQuestionImportError('图片不能超过 10 MB，请压缩后重新选择。');
            return;
        }
        if (errorEl) errorEl.classList.add('hidden');
        this._questionImportFile = file;
        this._pendingQuestionImportPreview = null;
        const nameEl = document.getElementById('question-import-file-name');
        if (nameEl) nameEl.textContent = `${file.name || '已选择图片'} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
        const submit = document.getElementById('question-import-submit');
        if (submit) {
            submit.disabled = false;
            submit.textContent = '上传并生成预览';
            submit.className = 'w-full py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium';
        }
    },

    _showQuestionImportError(message, clearFile = true) {
        const errorEl = document.getElementById('question-import-error');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.classList.remove('hidden');
        }
        if (clearFile) {
            this._questionImportFile = null;
            const nameEl = document.getElementById('question-import-file-name');
            if (nameEl) nameEl.textContent = '尚未选择图片';
        }
        const submit = document.getElementById('question-import-submit');
        if (submit && clearFile) {
            submit.disabled = true;
            submit.textContent = '上传并生成预览';
            submit.className = 'w-full py-3 bg-gray-300 text-white rounded-lg font-medium cursor-not-allowed';
        }
    },

    _resetQuestionImportStages() {
        const nameEl = document.getElementById('question-import-file-name');
        if (nameEl) nameEl.textContent = '尚未选择图片';
        const errorEl = document.getElementById('question-import-error');
        if (errorEl) errorEl.classList.add('hidden');
        const submit = document.getElementById('question-import-submit');
        if (submit) {
            submit.disabled = true;
            submit.textContent = '上传并生成预览';
            submit.className = 'w-full py-3 bg-gray-300 text-white rounded-lg font-medium cursor-not-allowed';
        }
        ['upload', 'ocr', 'llm'].forEach(stage => {
            const el = document.getElementById(`import-stage-${stage}`);
            if (!el) return;
            el.className = 'flex items-center gap-2 text-sm';
            el.querySelector('.stage-icon').textContent = '○';
            el.querySelector('.stage-detail').textContent = '';
        });
    },

    _setQuestionImportStage(stage, state, detail = '') {
        const el = document.getElementById(`import-stage-${stage}`);
        if (!el) return;
        const colors = { active: 'text-blue-600', done: 'text-green-600', error: 'text-red-600' };
        el.className = `flex items-center gap-2 text-sm ${colors[state] || ''}`;
        el.querySelector('.stage-icon').textContent = state === 'done' ? '✓' : state === 'error' ? '!' : '…';
        el.querySelector('.stage-detail').textContent = detail;
    },

    async submitQuestionImport() {
        if (this._questionImportBusy) return;
        if (this._pendingQuestionImportPreview) {
            this.openQuestionReview(this._pendingQuestionImportPreview);
            return;
        }
        const file = this._questionImportFile;
        const grade = document.getElementById('teacher-import-grade')?.value;
        const semester = document.getElementById('teacher-import-semester')?.value || '';
        const teacherId = MockData.currentUser?.id;
        if (!file) return this._showQuestionImportError('请先选择标准答案图片。');
        if (!grade) return this._showQuestionImportError('请选择题目适用年级。');
        if (!teacherId) return this._showQuestionImportError('未识别当前教师账号，请重新登录。');

        this._questionImportBusy = true;
        const submit = document.getElementById('question-import-submit');
        if (submit) {
            submit.disabled = true;
            submit.textContent = '正在生成预览...';
            submit.className = 'w-full py-3 bg-blue-500 text-white rounded-lg font-medium cursor-wait';
        }
        this._setQuestionImportStage('upload', 'active', '正在上传');
        this._setQuestionImportStage('ocr', 'active', '等待识别');
        this._setQuestionImportStage('llm', 'active', '等待复核');
        try {
            const preview = await Api.uploadTeacherQuestionImportPreview(file, teacherId, Number(grade), semester);
            this._setQuestionImportStage('upload', 'done', '已完成');
            this._setQuestionImportStage('ocr', 'done', `${preview.items?.length || 0} 道题`);
            this._setQuestionImportStage('llm', 'done', '预览已生成');
            this._questionImportFile = null;
            this._questionImportBusy = false;
            if (submit) {
                submit.textContent = '进入复核';
                submit.disabled = false;
                submit.className = 'w-full py-3 bg-green-600 text-white rounded-lg font-medium';
            }
            this._pendingQuestionImportPreview = preview;
        } catch (error) {
            this._questionImportBusy = false;
            this._setQuestionImportStage('upload', 'error', '失败');
            this._setQuestionImportStage('ocr', 'error', '未完成');
            this._setQuestionImportStage('llm', 'error', '未完成');
            this._showQuestionImportError(error.message || '上传失败，请稍后重试。', false);
            if (submit) {
                submit.disabled = false;
                submit.textContent = '重新生成预览';
                submit.className = 'w-full py-3 bg-green-600 text-white rounded-lg font-medium';
            }
        }
    },

    openQuestionReview(preview) {
        // C2 will replace this handoff with the editable question review screen.
        this.closeQuestionImport();
        this._pendingQuestionImportPreview = preview;
        this.showQuestionImportNotice(`已识别 ${preview.items?.length || 0} 道题，下一步进入逐题复核。`);
    },

    showQuestionImportNotice(message) {
        if (typeof App?.showModal === 'function') App.showModal('题目录入预览', `<div class="text-sm text-gray-700">${message}</div>`);
    },

    async showCreateBatchModal() {
        const modal = document.getElementById('batch-modal');
        if (!modal) return;
        modal.classList.remove('hidden');

        const listEl = document.getElementById('batch-question-list');
        listEl.innerHTML = '<div class="text-gray-400 text-sm">加载题目中...</div>';

        try {
            const grade = MockData.currentUser?.grade || 3;
            const result = await Api.getQuestionsForBatch(grade, null, 1, 20);
            const questions = result.data || [];
            this._availableQuestions = questions.slice(0, 8);

            listEl.innerHTML = this._availableQuestions.map((q, i) => `
                <label class="flex items-center gap-2 p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                    <input type="checkbox" class="batch-q-check" data-index="${i}" onchange="TeacherPage._onQuestionToggle()">
                    <span class="text-sm flex-1">${q.text || q.name || q.id}</span>
                    <span class="text-xs text-gray-400">${q.id}</span>
                </label>
            `).join('');
        } catch (e) {
            listEl.innerHTML = '<div class="text-red-500 text-sm">加载失败: ' + e.message + '</div>';
        }
    },

    _onQuestionToggle() {
        const checks = document.querySelectorAll('.batch-q-check:checked');
        this._selectedQuestions = Array.from(checks).map(cb => this._availableQuestions[parseInt(cb.dataset.index)]);
    },

    async confirmCreateBatch() {
        if (this._selectedQuestions.length === 0) {
            alert('请至少选择一道题目');
            return;
        }

        const user = MockData.currentUser;
        const className = this.currentClassName || '';
        const questionIds = this._selectedQuestions.map(q => q.id);

        try {
            const result = await Api.createHomeworkBatch(
                className, user?.id || 'T-001', new Date().toISOString().split('T')[0], questionIds
            );
            alert('批次创建成功: ' + result.batch_id + '\n状态: 答案已锁定(locked)\n题目数: ' + result.question_count);
            this.batches.unshift(result);
            document.getElementById('batch-modal').classList.add('hidden');
            this._selectedQuestions = [];
            this.navigate('assignments');
        } catch (e) {
            alert('创建失败: ' + e.message);
        }
    },

    async releaseBatch(batchId) {
        if (!confirm('确认放行批次 ' + batchId + ' 的全部答案？放行后学生将能看到完整答案。')) return;
        try {
            await Api.releaseHomeworkBatch(batchId);
            alert('已全部放行');
            const b = this.batches.find(x => x.batch_id === batchId);
            if (b) b.release_status = 'released';
            this.navigate('assignments');
        } catch (e) {
            alert('放行失败: ' + e.message);
        }
    },

    async showPartialReleaseModal(batchId, questionCount) {
        this._partialBatchId = batchId;
        this._partialQuestions = [];

        const modal = document.getElementById('partial-modal');
        if (!modal) return;
        modal.classList.remove('hidden');

        const listEl = document.getElementById('partial-question-list');
        try {
            const result = await Api.getQuestionsForBatch(null, null, 1, questionCount);
            const questions = (result.data || []).slice(0, questionCount);

            listEl.innerHTML = questions.map((q, i) => `
                <label class="flex items-center gap-2 p-2 border rounded-lg cursor-pointer hover:bg-gray-50">
                    <input type="checkbox" class="partial-q-check" data-index="${i}" data-qid="${q.id}">
                    <span class="text-sm flex-1">${q.text || q.name || q.id}</span>
                    <span class="text-xs text-gray-400">${q.id}</span>
                </label>
            `).join('');
            this._partialAvailableQuestions = questions;
        } catch (e) {
            listEl.innerHTML = '<div class="text-red-500 text-sm">加载失败</div>';
        }
    },

    async confirmPartialRelease() {
        const checks = document.querySelectorAll('.partial-q-check:checked');
        const qids = Array.from(checks).map(cb => cb.dataset.qid);

        if (qids.length === 0) {
            alert('请至少选择一道要放行的题目');
            return;
        }

        try {
            await Api.releaseHomeworkBatchPartial(this._partialBatchId, qids);
            alert('已放行 ' + qids.length + ' 道题目');
            const b = this.batches.find(x => x.batch_id === this._partialBatchId);
            if (b) b.release_status = 'partial';
            document.getElementById('partial-modal').classList.add('hidden');
            this.navigate('assignments');
        } catch (e) {
            alert('放行失败: ' + e.message);
        }
    },

    renderMistakes() {
        // 异步加载真实高频错题
        var cn = encodeURIComponent(this.currentClassName || '');
        setTimeout(function() {
            Api.fetch('/class/' + cn + '/mistake-stats').then(function(data) {
                var items = data.data || [];
                var c = document.getElementById('mistake-top5');
                if (!c) return;
                if (items.length === 0) {
                    c.innerHTML = '<div class="text-gray-400 text-sm text-center py-4">暂无错题数据</div>';
                    return;
                }
                c.innerHTML = items.map(function(m, i) {
                    return '<div class="p-3 bg-red-50 rounded-xl">' +
                        '<div class="flex items-center gap-3">' +
                            '<span class="w-8 h-8 bg-red-500 text-white rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0">' + (i+1) + '</span>' +
                            '<div class="flex-1"><div class="font-medium text-sm">' + (m.knowledge_id) + '</div>' +
                            '<div class="text-xs text-gray-500">' + (m.error_types || []).join(', ') + '</div></div>' +
                            '<div class="text-right"><div class="text-xl font-bold text-red-600">' + m.error_count + '</div><div class="text-xs text-gray-400">次</div></div>' +
                        '</div>' +
                        '<div class="w-full bg-white rounded-full h-1.5 mt-2"><div class="bg-red-500 h-1.5 rounded-full" style="width:' + Math.min(m.error_count * 10, 100) + '%"></div></div>' +
                    '</div>';
                }).join('');
            }).catch(function() {});
        }, 100);

        return `
        <div class="space-y-4 pb-24">
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">⚠️ 高频错题TOP5</div>
                <div id="mistake-top5" class="space-y-2">
                    <div class="text-gray-400 text-sm text-center py-4">加载中...</div>
                </div>
            </div>
        </div>`;
    },

    initMistakesCharts() {
        // 原型阶段简化：高频错题已通过 API 展示，真实数据来自 /api/class/{name}/mistake-stats
    },

    generatePractice(knowledgeId) {
        alert(`为知识点 ${knowledgeId} 生成练习\n\n将基于错题生成针对性练习题。\n\n（此功能需对接题库和错因分析模块）`);
    },

    renderMastery() {
        return `
        <div class="space-y-4 pb-24">
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">📈 知识点掌握度趋势</div>
                <canvas id="masteryLineChart" height="200"></canvas>
            </div>

            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">📊 各知识点掌握度</div>
                ${this.currentClassMastery.length === 0 ? '<div class="text-gray-400 text-sm text-center py-4">暂无数据</div>' : ''}
                <div class="space-y-3">
                    ${this.currentClassMastery.map(m => {
                        var pct = Math.round(m.avg_mastery || 0);
                        var color = pct >= 80 ? 'text-green-600' : pct >= 60 ? 'text-yellow-600' : 'text-red-600';
                        var barColor = pct >= 80 ? 'bg-green-500' : pct >= 60 ? 'bg-yellow-500' : 'bg-red-500';
                        var badge = pct >= 80 ? '已掌握' : pct >= 60 ? '学习中' : '薄弱';
                        var badgeColor = pct >= 80 ? 'bg-green-100 text-green-600' : pct >= 60 ? 'bg-yellow-100 text-yellow-600' : 'bg-red-100 text-red-600';
                        return '<div class="p-3 bg-gray-50 rounded-xl">' +
                            '<div class="flex items-center justify-between mb-1">' +
                                '<div class="font-medium text-sm">' + (m.title || m.knowledge_id) + '</div>' +
                                '<div class="flex items-center gap-2">' +
                                    '<span class="font-bold ' + color + '">' + pct + '%</span>' +
                                    '<span class="badge ' + badgeColor + '">' + badge + '</span>' +
                                '</div>' +
                            '</div>' +
                            '<div class="w-full bg-gray-200 rounded-full h-2">' +
                                '<div class="' + barColor + ' h-2 rounded-full" style="width:' + pct + '%"></div>' +
                            '</div>' +
                        '</div>';
                    }).join('')}
                </div>
            </div>

            <div class="bg-white rounded-2xl p-4 shadow-soft mb-4">
                <div class="font-bold mb-3">🎯 需重点关注的知识点</div>
                ${this.currentClassMastery.filter(m => (m.avg_mastery || 0) < 60).length === 0 ?
                    '<div class="text-gray-400 text-sm text-center py-4">暂无薄弱知识点 🎉</div>' : ''}
                <div class="space-y-2">
                    ${this.currentClassMastery.filter(m => (m.avg_mastery || 0) < 60).map(m => `
                        <div class="p-3 bg-red-50 rounded-xl border border-red-100">
                            <div class="flex items-center justify-between">
                                <div>
                                    <div class="font-medium text-sm">${m.title || m.knowledge_id}</div>
                                    <div class="text-xs text-red-500">班级平均掌握度 ${Math.round(m.avg_mastery || 0)}% · ${m.student_count || 0}人</div>
                                </div>
                                <button onclick="TeacherPage.viewDetail('${m.knowledge_id}')" class="bg-red-500 text-white text-xs px-3 py-1 rounded-lg flex-shrink-0">查看详情</button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>`;
    },

    initMasteryCharts() {
        setTimeout(() => {
            const d = TeacherPage.currentClassMastery || [];
            console.log('[mastery chart] data count:', d.length);
            const ctx = document.getElementById('masteryLineChart');
            if (ctx && d.length > 0) {
                new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: d.map(k => k.title || k.knowledge_id),
                        datasets: [{
                            label: '平均掌握度',
                            data: d.map(k => Math.round(k.avg_mastery || 0)),
                            borderColor: '#11998e',
                            backgroundColor: 'rgba(17, 153, 142, 0.2)',
                            tension: 0.3,
                            fill: true,
                            pointBackgroundColor: d.map(k =>
                                (k.avg_mastery || 0) >= 80 ? '#28a745' : (k.avg_mastery || 0) >= 60 ? '#ffc107' : '#dc3545'
                            )
                        }]
                    },
                    options: {
                        scales: { y: { beginAtZero: true, max: 100 } }
                    }
                });
            }
        }, 100);
    },

    async viewDetail(knowledgeId) {
        // 创建弹窗
        var modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4';
        modal.innerHTML = '<div class="bg-white rounded-2xl w-full max-w-md max-h-[70vh] overflow-auto p-5">' +
            '<div class="text-center py-4"><div class="text-2xl mb-2">⏳</div><div class="text-gray-500">加载中...</div></div>' +
            '</div>';
        document.body.appendChild(modal);

        try {
            var kp = await Api.fetch('/knowledge_points/' + knowledgeId);
            var qList = [];
            try {
                var questions = await Api.fetch('/questions?knowledge_id=' + encodeURIComponent(knowledgeId) + '&page=1&page_size=5');
                qList = questions.data || [];
            } catch (e) {
                // 题目查询失败时降级，不影响知识点详情查看
                qList = [];
            }
            modal.querySelector('.bg-white').innerHTML =
                '<div class="flex items-center justify-between mb-4">' +
                    '<div class="font-bold text-lg">' + (kp.title || knowledgeId) + '</div>' +
                    '<button onclick="this.closest(\'.fixed\').remove()" class="text-gray-400 text-xl">&times;</button>' +
                '</div>' +
                '<div class="space-y-3">' +
                    '<div class="p-3 bg-blue-50 rounded-xl"><div class="text-xs text-gray-500">年级</div><div class="font-medium">' + (kp.grade || '—') + '年级 · ' + (kp.semester || '—') + '</div></div>' +
                    '<div class="p-3 bg-blue-50 rounded-xl"><div class="text-xs text-gray-500">内容</div><div class="text-sm">' + (kp.content || kp.description || '暂无') + '</div></div>' +
                    '<div class="p-3 bg-yellow-50 rounded-xl"><div class="text-xs text-gray-500">常见错误</div><div class="text-sm">' + (kp.common_mistakes || '暂无') + '</div></div>' +
                    '<div class="p-3 bg-green-50 rounded-xl"><div class="text-xs text-gray-500">教学要点</div><div class="text-sm">' + (kp.teaching_points || '暂无') + '</div></div>' +
                    '<div class="p-3 bg-gray-50 rounded-xl"><div class="text-xs text-gray-500">关联题目 (' + qList.length + '题)</div>' +
                        qList.slice(0, 5).map(function(q) {
                            return '<div class="text-sm mt-1 text-gray-700">' + (q.text || q.name || q.id) + '</div>';
                        }).join('') +
                    '</div>' +
                '</div>' +
                '<button onclick="this.closest(\'.fixed\').remove()" class="w-full mt-4 bg-gray-100 py-2 rounded-xl text-sm">关闭</button>';
        } catch (e) {
            modal.querySelector('.bg-white').innerHTML =
                '<div class="text-center py-4"><div class="text-4xl mb-2">❌</div><div class="text-gray-500">加载失败</div>' +
                '<div class="text-xs text-gray-400 mt-1">' + (e.message || '') + '</div>' +
                '<button onclick="this.closest(\'.fixed\').remove()" class="w-full mt-4 bg-gray-100 py-2 rounded-xl text-sm">关闭</button></div>';
        }
    },

    reviewPlansState: {
        generating: false,
        plans: [],
        currentPlan: null,
        priorityResults: null
    },

    renderReviewPlans() {
        const students = this.currentStudents;
        const plans = this.reviewPlansState.plans;
        const generating = this.reviewPlansState.generating;

        return `
        <div class="space-y-4 pb-24">
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">📅 复习计划管理</div>
                <div class="text-sm text-gray-500 mb-4">为学生生成个性化复习计划，基于知识图谱掌握度数据</div>

                <div class="grid grid-cols-2 gap-3 mb-4">
                    <div class="p-3 bg-blue-50 rounded-xl text-center">
                        <div class="text-2xl font-bold text-blue-600">${students.length}</div>
                        <div class="text-xs text-gray-500">班级学生</div>
                    </div>
                    <div class="p-3 bg-purple-50 rounded-xl text-center">
                        <div class="text-2xl font-bold text-purple-600">${plans.length}</div>
                        <div class="text-xs text-gray-500">已生成计划</div>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">🎯 生成复习计划</div>
                <div id="generate-plan-area">
                    ${students.length > 0 ? `
                        <div class="mb-3">
                            <label class="text-sm text-gray-600 block mb-1">选择学生</label>
                            <select id="rp-student-select" class="w-full border rounded-xl px-3 py-2 text-sm bg-gray-50">
                                <option value="">-- 选择学生 --</option>
                                ${students.map(s => `
                                    <option value="${s.id}">${s.name} (${s.id})</option>
                                `).join('')}
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="text-sm text-gray-600 block mb-1">生成模式</label>
                            <div class="flex gap-2">
                                <label class="flex-1 flex items-center gap-2 p-2 border rounded-xl cursor-pointer">
                                    <input type="radio" name="rp-mode" value="question_count" checked>
                                    <span class="text-sm">按题量</span>
                                </label>
                                <label class="flex-1 flex items-center gap-2 p-2 border rounded-xl cursor-pointer">
                                    <input type="radio" name="rp-mode" value="time_limit">
                                    <span class="text-sm">按时间</span>
                                </label>
                            </div>
                        </div>
                        <div class="mb-4">
                            <label id="rp-count-label" class="text-sm text-gray-600 block mb-1">题目数量</label>
                            <input id="rp-count-input" type="number" min="1" max="30" value="10" class="w-full border rounded-xl px-3 py-2 text-sm bg-gray-50">
                        </div>
                        <button onclick="TeacherPage.generateReviewPlan()" id="rp-generate-btn" class="w-full ${generating ? 'bg-gray-400' : 'gradient-primary'} text-white rounded-xl py-3 font-medium ${generating ? '' : 'hover:opacity-90'} transition" ${generating ? 'disabled' : ''}>
                            ${generating ? '生成中...' : '🚀 生成复习计划'}
                        </button>
                    ` : '<div class="text-center text-gray-400 py-4">请先加载班级学生数据</div>'}
                </div>
            </div>

            ${plans.length > 0 ? `
            <div class="bg-white rounded-2xl p-4 shadow-soft">
                <div class="font-bold mb-3">📋 已生成的复习计划</div>
                <div class="space-y-3">
                    ${plans.map(plan => `
                        <div class="p-3 border rounded-xl ${plan.status === 'not_started' ? 'border-blue-200 bg-blue-50' : plan.status === 'in_progress' ? 'border-green-200 bg-green-50' : 'border-gray-200'}">
                            <div class="flex items-center justify-between mb-2">
                                <div class="font-medium text-sm">学生: ${plan.student_id}</div>
                                <span class="badge ${plan.status === 'not_started' ? 'bg-blue-100 text-blue-600' : plan.status === 'in_progress' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-600'}">
                                    ${plan.status === 'not_started' ? '未开始' : plan.status === 'in_progress' ? '进行中' : '已完成'}
                                </span>
                            </div>
                            <div class="text-xs text-gray-500 mb-2">
                                模式: ${plan.mode === 'question_count' ? '按题量' : '按时间'} · 
                                题数: ${plan.items ? plan.items.length : 0} · 
                                日期: ${plan.business_date}
                            </div>
                            ${plan.items && plan.items.length > 0 ? `
                                <div class="text-xs text-gray-500 mb-2">
                                    题目预览: ${plan.items.slice(0, 3).map(i => i.question_id).join(', ')}${plan.items.length > 3 ? '...' : ''}
                                </div>
                            ` : ''}
                            <button onclick="TeacherPage.viewPlanDetail('${plan.id}')" class="text-xs bg-purple-500 text-white px-3 py-1.5 rounded-lg">查看详情</button>
                        </div>
                    `).join('')}
                </div>
            </div>
            ` : ''}
        </div>`;
    },

    initReviewPlans() {
        document.querySelectorAll('input[name="rp-mode"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                const mode = e.target.value;
                const label = document.getElementById('rp-count-label');
                const input = document.getElementById('rp-count-input');
                if (mode === 'question_count') {
                    label.textContent = '题目数量';
                    input.type = 'number';
                    input.min = '1'; input.max = '30'; input.value = '10';
                } else {
                    label.textContent = '时间限制（分钟）';
                    input.type = 'number';
                    input.min = '1'; input.max = '120'; input.value = '30';
                }
            });
        });
    },

    async generateReviewPlan() {
        const studentSelect = document.getElementById('rp-student-select');
        if (!studentSelect || !studentSelect.value) {
            App.showModal('❌ 提示', '<div class="text-center">请先选择一个学生</div>');
            return;
        }

        const studentId = studentSelect.value;
        const mode = document.querySelector('input[name="rp-mode"]:checked').value;
        const countInput = document.getElementById('rp-count-input');
        const value = parseInt(countInput.value) || 10;

        this.reviewPlansState.generating = true;
        document.getElementById('rp-generate-btn').textContent = '生成中...';
        document.getElementById('rp-generate-btn').disabled = true;

        try {
            App.showLoading('正在计算优先级并生成复习计划...');
            const plan = await Api.createReviewPlan(
                studentId,
                mode,
                mode === 'question_count' ? value : null,
                mode === 'time_limit' ? value : null
            );

            this.reviewPlansState.plans.unshift(plan);
            this.reviewPlansState.currentPlan = plan;

            App.hideLoading();
            App.showModal('✅ 生成成功', `
                <div class="text-center mb-4">
                    <div class="text-5xl mb-2">🎉</div>
                    <div class="font-bold text-lg">复习计划已生成</div>
                </div>
                <div class="space-y-2 text-sm">
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>计划ID</span>
                        <span class="font-medium">${plan.id}</span>
                    </div>
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>学生</span>
                        <span class="font-medium">${plan.student_id}</span>
                    </div>
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>题目数量</span>
                        <span class="font-medium">${plan.items ? plan.items.length : 0} 题</span>
                    </div>
                </div>
                <button onclick="TeacherPage.startPractice('${plan.id}')" class="w-full mt-4 bg-purple-600 text-white py-2 rounded-lg text-sm">
                    开始练习 →
                </button>
                <button onclick="App.closeModal(); TeacherPage.navigate('review')" class="w-full mt-2 bg-gray-100 text-gray-600 py-2 rounded-lg text-sm">
                    返回列表
                </button>
            `);
        } catch (error) {
            console.error('Failed to generate review plan:', error);
            App.hideLoading();
            App.showModal('❌ 生成失败', `<div class="text-center text-sm">${error.message || '请检查后端服务是否启动'}</div>`);
        } finally {
            this.reviewPlansState.generating = false;
            const btn = document.getElementById('rp-generate-btn');
            if (btn) {
                btn.textContent = '🚀 生成复习计划';
                btn.disabled = false;
            }
        }
    },

    viewPlanDetail(planId) {
        const plan = this.reviewPlansState.plans.find(p => p.id === planId);
        if (!plan) return;

        const itemsHtml = (plan.items || []).map((item, i) => `
            <div class="p-2 bg-gray-50 rounded-lg mb-1 text-sm">
                <div class="flex items-center justify-between">
                    <span class="font-medium">第${i + 1}题: ${item.question_id}</span>
                    <span class="badge bg-blue-100 text-blue-600">优先级: ${item.priority_score ? item.priority_score.toFixed(1) : 'N/A'}</span>
                </div>
                <div class="text-xs text-gray-500">知识点: ${(item.knowledge_point_ids || []).join(', ')}</div>
            </div>
        `).join('');

        App.showModal(`📋 复习计划详情`, `
            <div class="space-y-3">
                <div class="flex justify-between p-2 bg-gray-50 rounded-lg text-sm">
                    <span>计划ID</span>
                    <span class="font-medium">${plan.id}</span>
                </div>
                <div class="flex justify-between p-2 bg-gray-50 rounded-lg text-sm">
                    <span>学生</span>
                    <span class="font-medium">${plan.student_id}</span>
                </div>
                <div class="flex justify-between p-2 bg-gray-50 rounded-lg text-sm">
                    <span>模式</span>
                    <span class="font-medium">${plan.mode === 'question_count' ? '按题量' : '按时间'}</span>
                </div>
                <div class="flex justify-between p-2 bg-gray-50 rounded-lg text-sm">
                    <span>题目数</span>
                    <span class="font-medium">${plan.items ? plan.items.length : 0} 题</span>
                </div>
                <div class="flex justify-between p-2 bg-gray-50 rounded-lg text-sm">
                    <span>状态</span>
                    <span class="font-medium">${plan.status}</span>
                </div>
                <div class="mt-3">
                    <div class="text-sm font-medium mb-2">📝 题目列表</div>
                    ${itemsHtml || '<div class="text-gray-400 text-sm">暂无题目</div>'}
                </div>
                <button onclick="TeacherPage.startPractice('${plan.id}')" class="w-full mt-4 bg-purple-600 text-white py-2 rounded-lg text-sm">
                    🚀 开始练习
                </button>
            </div>
        `);
    },

    async startPractice(planId) {
        App.closeModal();
        try {
            App.showLoading('正在启动练习会话...');
            const session = await Api.startReviewSession(planId);
            App.hideLoading();

            const plan = this.reviewPlansState.plans.find(p => p.id === planId);
            const studentName = plan ? plan.student_id : '';

            App.showModal('✏️ 开始答题', `
                <div class="text-center mb-4">
                    <div class="text-5xl mb-2">📝</div>
                    <div class="font-bold text-lg">练习会话已启动</div>
                    <div class="text-sm text-gray-500">学生: ${studentName}</div>
                </div>
                <div class="space-y-2 text-sm">
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>会话ID</span>
                        <span class="font-medium">${session.session_id}</span>
                    </div>
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>当前题目</span>
                        <span class="font-medium">${session.current_question ? session.current_question.id : '加载中...'}</span>
                    </div>
                    <div class="flex justify-between p-2 bg-gray-50 rounded-lg">
                        <span>剩余题目</span>
                        <span class="font-medium">${session.remaining_items_count || 'N/A'} 题</span>
                    </div>
                </div>
                <div class="text-xs text-gray-500 mt-4 text-center">
                    💡 此会话可通过学生端继续答题
                </div>
            `);
        } catch (error) {
            console.error('Failed to start practice:', error);
            App.hideLoading();
            App.showModal('❌ 启动失败', `<div class="text-center text-sm">${error.message || '请检查后端服务'}</div>`);
        }
    }
};
