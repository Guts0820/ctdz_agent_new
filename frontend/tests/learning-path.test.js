const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const studentSource = fs.readFileSync(path.join(__dirname, '../js/student.js'), 'utf8');
const apiSource = fs.readFileSync(path.join(__dirname, '../js/api.js'), 'utf8');
const pathSection = studentSource.slice(
    studentSource.indexOf('    renderPath()'),
    studentSource.indexOf('    async startLearning('),
);

test('student learning path loads only the DataHub learning path contract', () => {
    assert.match(apiSource, /async getLearningPath\(studentId\)/);
    assert.match(apiSource, /\/datahub\/learning_path\//);
    assert.match(pathSection, /Api\.getLearningPath\(sid\)/);
    assert.doesNotMatch(pathSection, /knowledge_points\?grade=/);
    assert.doesNotMatch(pathSection, /\/students\/.*\/weak/);
});

test('student learning path renders server ordering, stages and recommendation details', () => {
    for (const field of ['sequence', 'stage', 'reason', 'mastery_level', 'estimated_minutes', 'prerequisites']) {
        assert.match(pathSection, new RegExp(`item\\.${field}`));
    }
    assert.match(pathSection, /_pathStageMeta/);
    assert.match(pathSection, /startPathLearning/);
});

test('student learning path has explicit empty and retry states without mock fallback', () => {
    assert.match(pathSection, /完成一次作答后生成个性化路径/);
    assert.match(pathSection, /学习路径加载失败/);
    assert.match(pathSection, /重试/);
    assert.doesNotMatch(pathSection, /MockData\.knowledge/);
});

test('starting a path node enters the real knowledge learning and review flows', () => {
    const startSection = studentSource.slice(
        studentSource.indexOf('    startPathLearning('),
        studentSource.indexOf('    renderReport()'),
    );
    assert.match(startSection, /decodeURIComponent\(encodedKnowledgeId\)/);
    assert.match(startSection, /this\.startLearning\(decodeURIComponent/);
    assert.match(startSection, /Api\.fetch\('\/knowledge_points\/' \+ knowledgeId\)/);
    assert.match(startSection, /StudentPage\.showReviewPlan\(\)/);
});
