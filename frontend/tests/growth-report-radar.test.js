const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const studentSource = fs.readFileSync(path.join(__dirname, '../js/student.js'), 'utf8');
const apiSource = fs.readFileSync(path.join(__dirname, '../js/api.js'), 'utf8');
const reportSection = studentSource.slice(
    studentSource.indexOf('    renderReport()'),
    studentSource.indexOf('    initPathCharts()'),
);

test('student growth report uses the single DataHub report contract', () => {
    assert.match(apiSource, /async getGrowthReport\(studentId\)/);
    assert.match(apiSource, /\/datahub\/growth_report\//);
    assert.match(reportSection, /Api\.getGrowthReport\(studentId\)/);
    assert.doesNotMatch(reportSection, /\/students\/.*\/mastery/);
    assert.doesNotMatch(reportSection, /\/students\/.*\/weak/);
    assert.doesNotMatch(reportSection, /fiveDimensionScores/);
});

test('student growth report renders backend dimensions without inventing scores', () => {
    assert.match(reportSection, /radar\.dimensions/);
    assert.match(reportSection, /typeof item\.score === 'number'/);
    assert.match(reportSection, /积累中/);
    assert.match(reportSection, /sample_count/);
    assert.match(reportSection, /_formatReportStatus/);
    assert.match(reportSection, /mastery_overview/);
    assert.match(reportSection, /weak_knowledge_areas/);
});

test('student growth report destroys previous radar charts and exposes retry state', () => {
    assert.match(reportSection, /_reportRadarChart\.destroy\(\)/);
    assert.match(reportSection, /_renderGrowthReportError/);
    assert.match(reportSection, /成长报告加载失败/);
    assert.match(reportSection, /StudentPage\.navigate\(\\?'report\\?'\)/);
});
