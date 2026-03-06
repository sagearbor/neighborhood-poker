/**
 * Poker Blinds Timer — Google Apps Script
 *
 * Setup:
 *   1. Extensions > Apps Script
 *   2. Paste this into Code.gs
 *   3. Create HTML file named "TimerDialog" and paste timer_dialog.html
 *   4. Save, select initializeTimer from dropdown, click Run, authorize
 *   5. Reload the spreadsheet — "🃏 Poker Timer" menu appears
 */

var SHEET_NAME = '⏱ Blinds Timer';
var DATA_START_ROW = 7; // 1-indexed row where level data begins

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🃏 Poker Timer')
    .addItem('▶ Start Timer', 'startTimer')
    .addItem('🔄 Reset / Restart', 'startTimer')
    .addToUi();
}

function initializeTimer() {
  resetTimerProperties();
  SpreadsheetApp.getActive().toast(
    'Done! Reload the spreadsheet tab — the 🃏 Poker Timer menu will appear.'
  );
}

function resetTimerProperties() {
  PropertiesService.getDocumentProperties().deleteAllProperties();
}

// ── Read blind schedule from sheet ──────────────────────────────────────────

function getBlindSchedule() {
  var ss = SpreadsheetApp.getActive();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) return [];

  var lastRow = sheet.getLastRow();
  if (lastRow < DATA_START_ROW) return [];

  var data = sheet.getRange(DATA_START_ROW, 1, lastRow - DATA_START_ROW + 1, 4).getValues();
  var levels = [];

  for (var i = 0; i < data.length; i++) {
    var row = data[i];
    var levelLabel = String(row[0]).trim();
    if (!levelLabel) continue;

    var isBreak = levelLabel.toUpperCase().indexOf('BREAK') !== -1;
    var duration = parseInt(row[3]) || 20;

    levels.push({
      label: levelLabel,
      small: isBreak ? 0 : (parseInt(row[1]) || 0),
      big:   isBreak ? 0 : (parseInt(row[2]) || 0),
      duration: duration,
      isBreak: isBreak
    });
  }
  return levels;
}

// ── Open the timer dialog ────────────────────────────────────────────────────

function startTimer() {
  var levels = getBlindSchedule();
  if (levels.length === 0) {
    SpreadsheetApp.getUi().alert('No blind schedule found in the "⏱ Blinds Timer" tab.');
    return;
  }

  // Inject schedule into HTML template as JSON
  var template = HtmlService.createTemplateFromFile('TimerDialog');
  template.levelsJson = JSON.stringify(levels);

  var html = template.evaluate()
    .setWidth(820)
    .setHeight(620)
    .setTitle('Poker Blinds Timer');

  SpreadsheetApp.getUi().showModelessDialog(html, 'Poker Blinds Timer');
}
