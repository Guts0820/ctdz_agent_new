const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const teacherSource = fs.readFileSync(path.join(__dirname, '../js/teacher.js'), 'utf8');
const apiSource = fs.readFileSync(path.join(__dirname, '../js/api.js'), 'utf8');

function loadTeacherPage(api = {}) {
    const elements = new Map();
    const element = id => {
        if (!elements.has(id)) {
            const classes = new Set(['hidden']);
            elements.set(id, {
                classList: {
                    add: value => classes.add(value),
                    remove: value => classes.delete(value),
                    contains: value => classes.has(value)
                },
                disabled: false,
                innerHTML: '',
                textContent: ''
            });
        }
        return elements.get(id);
    };
    const context = {
        App: { showModal() {} },
        Api: api,
        MockData: { currentUser: { id: 'T001' } },
        console,
        document: { getElementById: element }
    };
    vm.runInNewContext(teacherSource + '\nglobalThis.__TeacherPage = TeacherPage;', context);
    return { page: context.__TeacherPage, element };
}

test('teacher page exposes camera and file upload entry with required metadata', () => {
    assert.match(teacherSource, /capture="environment"/);
    assert.match(teacherSource, /teacher-question-file/);
    assert.match(teacherSource, /teacher-import-grade/);
    assert.match(teacherSource, /teacher-import-semester/);
    assert.match(teacherSource, /openQuestionImport/);
});

test('teacher question import validates image size/type and prevents duplicate submits', () => {
    assert.match(teacherSource, /10 \* 1024 \* 1024/);
    assert.match(teacherSource, /image\/jpeg/);
    assert.match(teacherSource, /_questionImportBusy/);
    assert.match(teacherSource, /if \(this\._questionImportBusy\) return/);
});

test('teacher upload API uses multipart form data without forcing JSON content type', () => {
    assert.match(apiSource, /async uploadTeacherQuestionImportPreview/);
    assert.match(apiSource, /new FormData\(\)/);
    assert.match(apiSource, /formData\.append\('image'/);
    assert.match(apiSource, /question-imports\/preview/);
    assert.doesNotMatch(apiSource, /uploadTeacherQuestionImportPreview[\s\S]{0,800}Content-Type/);
});

test('teacher import shows independent upload, OCR and LLM states', () => {
    assert.match(teacherSource, /import-stage-upload/);
    assert.match(teacherSource, /import-stage-ocr/);
    assert.match(teacherSource, /import-stage-llm/);
    assert.match(teacherSource, /_setQuestionImportStage\('ocr'/);
    assert.match(teacherSource, /_setQuestionImportStage\('llm'/);
});

test('teacher review exposes editable fields, comparison details and all decisions', () => {
    assert.match(teacherSource, /question-review-modal/);
    assert.match(teacherSource, /question-review-question-/);
    assert.match(teacherSource, /question-review-answer-/);
    assert.match(teacherSource, /llm_solve_steps/);
    assert.match(teacherSource, /comparison_reason/);
    for (const decision of ['teacher', 'llm', 'existing', 'skip']) {
        assert.match(teacherSource, new RegExp(`choice\\('${decision}'`));
    }
});

test('teacher review requires explicit conflict decisions and disables invalid LLM choices', () => {
    const { page } = loadTeacherPage();
    page.openQuestionReview({
        import_id: 'TQI-1',
        grade: 3,
        items: [
            { item_id: 'agreed', question_text: '1+1=', teacher_answer: '2', llm_answer: '2', comparison_status: 'agreed' },
            { item_id: 'conflict', question_text: '2+2=', teacher_answer: '5', llm_answer: '4', comparison_status: 'conflict' },
            { item_id: 'uncertain', question_text: 'x', teacher_answer: 'a', llm_answer: 'b', comparison_status: 'uncertain' },
            { item_id: 'failed', question_text: '3+3=', teacher_answer: '6', llm_answer: null, comparison_status: 'llm_failed' }
        ]
    });

    assert.deepEqual(Array.from(page._questionReviewItems, item => item.decision), ['teacher', null, null, 'teacher']);
    assert.match(page._validateQuestionReview(), /第 2 题尚未选择/);
    page.onQuestionReviewDecision(3, 'llm');
    assert.equal(page._questionReviewItems[3].decision, 'teacher');
});

test('teacher review shows a decision summary before confirmation', () => {
    assert.match(teacherSource, /question-review-summary/);
    assert.match(teacherSource, /采用教师答案/);
    assert.match(teacherSource, /采用 LLM 答案/);
    assert.match(teacherSource, /复用题库答案/);
    assert.match(teacherSource, /跳过本题/);
    assert.match(teacherSource, /_questionReviewReadyToConfirm/);
});

test('teacher confirm API posts edited items and keeps confirmed question IDs', () => {
    assert.match(apiSource, /async confirmTeacherQuestionImport/);
    assert.match(apiSource, /question-imports\/.*\/confirm/);
    assert.match(teacherSource, /question_text:/);
    assert.match(teacherSource, /teacher_answer:/);
    assert.match(teacherSource, /_confirmedQuestionIds/);
    assert.match(teacherSource, /result\.items/);
});

test('teacher review sends confirmation only after summary acknowledgement', async () => {
    const calls = [];
    const api = {
        async confirmTeacherQuestionImport(importId, teacherId, items) {
            calls.push({ importId, teacherId, items });
            return { items: [{ item_id: 'ITEM-1', decision: 'teacher', question_id: 'Q-NEW', result: 'created' }] };
        }
    };
    const { page } = loadTeacherPage(api);
    page.openQuestionReview({
        import_id: 'TQI-1',
        grade: 3,
        items: [{ item_id: 'ITEM-1', question_text: '1+1=', teacher_answer: '2', llm_answer: '2', comparison_status: 'agreed' }]
    });
    page.onQuestionReviewText(0, 'question_text', '1 + 1 =');

    await page.confirmQuestionReview();
    assert.equal(calls.length, 0);
    assert.equal(page._questionReviewReadyToConfirm, true);

    await page.confirmQuestionReview();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].items[0].question_text, '1 + 1 =');
    assert.deepEqual(Array.from(page._confirmedQuestionIds), ['Q-NEW']);
});

test('batch selection uses the teacher question bank and handles empty or failed states', () => {
    assert.match(apiSource, /async getTeacherQuestions/);
    assert.match(apiSource, /\/v1\/teacher\/questions/);
    assert.match(teacherSource, /loadBatchQuestions/);
    assert.match(teacherSource, /题库暂无可布置题目，请先录入题目/);
    assert.match(teacherSource, /加载题库失败/);
    assert.match(teacherSource, /_confirmedQuestionIds\.includes/);
    assert.match(teacherSource, /_updateBatchCreateButton/);
    assert.match(teacherSource, /disabled>确认创建/);
});
