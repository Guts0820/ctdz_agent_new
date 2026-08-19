const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const { OcrUploadPolicy } = require('../js/ocr-upload-policy.js');

test('only allows OCR results at or above the 0.95 confidence threshold', () => {
    assert.equal(OcrUploadPolicy.isAccepted(0.95), true);
    assert.equal(OcrUploadPolicy.isAccepted(0.949), false);
});

test('allows at most three reuploads after a low-confidence initial upload', () => {
    const round = OcrUploadPolicy.startRound();

    assert.deepEqual(OcrUploadPolicy.lowConfidenceState(round), {
        canRetry: true,
        remainingReuploads: 3,
    });

    assert.equal(OcrUploadPolicy.beginReupload(round), true);
    assert.equal(OcrUploadPolicy.beginReupload(round), true);
    assert.equal(OcrUploadPolicy.beginReupload(round), true);
    assert.deepEqual(OcrUploadPolicy.lowConfidenceState(round), {
        canRetry: false,
        remainingReuploads: 0,
    });
    assert.equal(OcrUploadPolicy.beginReupload(round), false);
});

test('student upload flow checks the policy before displaying OCR results', () => {
    const studentPageSource = fs.readFileSync(
        path.join(__dirname, '../js/student.js'),
        'utf8',
    );

    assert.match(studentPageSource, /OcrUploadPolicy\.isAccepted\(confidence\)/);
    assert.match(studentPageSource, /_showLowConfidenceUploadDialog/);
    assert.match(studentPageSource, /retryOcrUpload/);
});

test('student upload submits the image through the gateway and renders the teaching result', () => {
    const studentPageSource = fs.readFileSync(
        path.join(__dirname, '../js/student.js'),
        'utf8',
    );
    const apiSource = fs.readFileSync(path.join(__dirname, '../js/api.js'), 'utf8');

    assert.match(apiSource, /async submitImage\(studentId, image, grade\)/);
    assert.match(apiSource, /this\.fetch\('\/v1\/submit'/);
    assert.match(studentPageSource, /Api\.submitImage\(studentId, reader\.result/);
    assert.match(studentPageSource, /_showSubmissionResult/);
    assert.match(studentPageSource, /error_tags/);
    assert.match(studentPageSource, /knowledge_explanation/);
    assert.match(studentPageSource, /practice_list/);
    assert.match(studentPageSource, /guided_explanation/);
    assert.doesNotMatch(studentPageSource, /fetch\(['"]http:\/\/127\.0\.0\.1:8089\/v1\/recognize/);
});

test('api client preserves gateway error details', () => {
    const apiSource = fs.readFileSync(path.join(__dirname, '../js/api.js'), 'utf8');
    assert.match(apiSource, /errorBody\.detail/);
    assert.match(apiSource, /API请求失败: ' \+ response\.status \+ detail/);
});
