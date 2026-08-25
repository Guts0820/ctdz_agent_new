const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '../js/teacher.js'), 'utf8');
const reportSection = source.slice(source.indexOf('    async viewStudentReport'), source.indexOf('    initDashboardCharts'));
const batchSection = source.slice(source.indexOf('    renderAssignments()'), source.indexOf('    renderMistakes()'));
const partialSection = source.slice(source.indexOf('    async showPartialReleaseModal'), source.indexOf('    async confirmPartialRelease'));

test('teacher report opens in the current page through DataHub', () => {
    assert.match(reportSection, /Api\.getGrowthReport\(studentId\)/);
    assert.doesNotMatch(reportSection, /localhost:3002/);
    assert.match(reportSection, /mastery_overview/);
    assert.match(reportSection, /weak_knowledge_areas/);
});

test('batch cards and partial release use current batch question details', () => {
    assert.match(batchSection, /question_details/);
    assert.match(partialSection, /this\.batches.*find/);
    assert.doesNotMatch(partialSection, /getQuestionsForBatch/);
});
