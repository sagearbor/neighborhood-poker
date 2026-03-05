/**
 * Poker Blinds Timer — Google Apps Script
 * Bound to the poker tournament spreadsheet.
 *
 * Setup:
 *   1. Extensions > Apps Script
 *   2. Paste this into Code.gs
 *   3. Create HTML file "TimerDialog" and paste timer_dialog.html
 *   4. Save, run initializeTimer(), authorize when prompted
 *   5. Reload the spreadsheet — "Poker Timer" menu appears
 */

var SHEET_NAME = '⏱ Blinds Timer';
var HEADER_ROW = 6;   // 1-indexed row where the header is
var DATA_START = 7;    // 1-indexed row where data begins
var PROP_KEY_LEVEL = 'currentLevel';
var PROP_KEY_PAUSED = 'isPaused';
var PROP_KEY_REMAINING = 'remainingSeconds';

// ─── Menu ────────────────────────────────────────────────────────────────────

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('\uD83C\uDCCF Poker Timer')
    .addItem('\u25B6 Start Timer', 'startTimer')
    .addItem('\u23F8 Pause / Resume', 'togglePause')
    .addItem('\u23ED Next Level', 'nextLevel')
    .addItem('\uD83D\uDD04 Reset Timer', 'resetTimer')
    .addToUi();
}

function initializeTimer() {
  onOpen();
  resetTimer();
  SpreadsheetApp.getActive().toast('Poker Timer initialized! Use the menu to start.');
}

// ─── Timer actions ───────────────────────────────────────────────────────────

function startTimer() {
  var props = PropertiesService.getDocumentProperties();
  props.setProperty(PROP_KEY_LEVEL, '0');
  props.setProperty(PROP_KEY_PAUSED, 'false');
  props.deleteProperty(PROP_KEY_REMAINING);

  var html = HtmlService.createHtmlOutputFromFile('TimerDialog')
    .setWidth(800)
    .setHeight(600)
    .setTitle('Poker Blinds Timer');
  SpreadsheetApp.getUi().showModelessDialog(html, 'Poker Blinds Timer');
}

function togglePause() {
  var props = PropertiesService.getDocumentProperties();
  var paused = props.getProperty(PROP_KEY_PAUSED) === 'true';
  props.setProperty(PROP_KEY_PAUSED, paused ? 'false' : 'true');
}

function nextLevel() {
  var props = PropertiesService.getDocumentProperties();
  var current = parseInt(props.getProperty(PROP_KEY_LEVEL) || '0', 10);
  props.setProperty(PROP_KEY_LEVEL, String(current + 1));
  props.setProperty(PROP_KEY_PAUSED, 'false');
  props.deleteProperty(PROP_KEY_REMAINING);
}

function resetTimer() {
  var props = PropertiesService.getDocumentProperties();
  props.setProperty(PROP_KEY_LEVEL, '0');
  props.setProperty(PROP_KEY_PAUSED, 'false');
  props.deleteProperty(PROP_KEY_REMAINING);
}

// ─── Data helpers (called from client-side) ──────────────────────────────────

function getBlindSchedule() {
  var sheet = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  var lastRow = sheet.getLastRow();
  if (lastRow < DATA_START) return [];

  var range = sheet.getRange(DATA_START, 1, lastRow - DATA_START + 1, 5); // A-E
  var values = range.getValues();
  var schedule = [];

  for (var i = 0; i < values.length; i++) {
    var row = values[i];
    var levelLabel = String(row[0]).trim();
    if (!levelLabel) continue;

    var isBreak = levelLabel.toUpperCase().indexOf('BREAK') >= 0;
    var duration = parseInt(row[4], 10) || 0; // Column E = Duration (min)

    schedule.push({
      level: levelLabel,
      smallBlind: isBreak ? '' : row[1],
      bigBlind: isBreak ? '' : row[2],
      duration: duration,
      isBreak: isBreak
    });
  }
  return schedule;
}

function getTimerState() {
  var props = PropertiesService.getDocumentProperties();
  return {
    levelIndex: parseInt(props.getProperty(PROP_KEY_LEVEL) || '0', 10),
    paused: props.getProperty(PROP_KEY_PAUSED) === 'true',
    remainingSeconds: props.getProperty(PROP_KEY_REMAINING)
      ? parseInt(props.getProperty(PROP_KEY_REMAINING), 10)
      : null
  };
}

function saveRemainingSeconds(seconds) {
  PropertiesService.getDocumentProperties()
    .setProperty(PROP_KEY_REMAINING, String(seconds));
}

function advanceLevel() {
  nextLevel();
}

function snoozeTimer() {
  var props = PropertiesService.getDocumentProperties();
  var remaining = parseInt(props.getProperty(PROP_KEY_REMAINING) || '0', 10);
  props.setProperty(PROP_KEY_REMAINING, String(remaining + 120));
  props.setProperty(PROP_KEY_PAUSED, 'false');
}

function pauseResume() {
  togglePause();
}
