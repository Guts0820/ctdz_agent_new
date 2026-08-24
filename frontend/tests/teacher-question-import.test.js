const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const teacherSource = fs.readFileSync(path.join(__dirname, '../js/teacher.js'), 'utf8');
const apiSource = fs.readFileSync(path.join(__dirname, '../js/api.js'), 'utf8');

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
