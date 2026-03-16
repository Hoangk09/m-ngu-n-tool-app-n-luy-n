// ==UserScript==
// @name         Quiz Solver Ultimate
// @namespace    http://tampermonkey.net/
// @version      1.0.0
// @description  Giải quiz tự động trên onluyen.vn với Gemini AI
// @author       nhat
// @match        https://app.onluyen.vn/*
// @icon         data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHRleHQgeT0iNDgiIGZvbnQtc2l6ZT0iNDgiPvCfpJY8L3RleHQ+PC9zdmc+
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_addStyle
// @grant        unsafeWindow
// @run-at       document-end
// ==/UserScript==

(function () {
    'use strict';

    console.log('🤖 Quiz Solver Userscript loaded!');

    // ==================== CONSTANTS ====================
    const API_BASE = 'https://tool.1amsleep.xyz';

    // ==================== STATE ====================
    const state = {
        isRunning: false,
        currentQuestion: 0,
        geminiApiKey: GM_getValue('geminiApiKey', null),
        solverConfig: GM_getValue('solverConfig', {
            delayMin: 3,
            delayMax: 8,
            autoSubmit: true,
            geminiModel: '2.5-flash'
        }),
        user: GM_getValue('user', null)
    };

    // ==================== STYLES ====================
    GM_addStyle(`
        #quiz-solver-panel {
            position: fixed;
            top: 20px;
            right: 20px;
            width: 320px;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
            color: #fff;
            font-family: 'Segoe UI', sans-serif;
            z-index: 999999;
            padding: 15px;
        }
        
        #quiz-solver-panel.minimized {
            width: 50px;
            height: 50px;
            padding: 0;
            overflow: hidden;
        }
        
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .panel-title {
            font-size: 1.1rem;
            font-weight: bold;
            color: #00d4ff;
        }
        
        .btn-minimize {
            background: transparent;
            border: none;
            color: #888;
            cursor: pointer;
            font-size: 1.2rem;
            padding: 0;
            width: 30px;
            height: 30px;
        }
        
        .minimized .panel-header {
            border: none;
            margin: 0;
            padding: 0;
            justify-content: center;
        }
        
        .minimized .panel-title {
            display: none;
        }
        
        .minimized .btn-minimize {
            font-size: 1.5rem;
        }
        
        .minimized .panel-content {
            display: none;
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            margin-bottom: 10px;
        }
        
        .status-idle {
            background: rgba(200,200,200,0.2);
            color: #aaa;
        }
        
        .status-running {
            background: rgba(0,200,0,0.2);
            color: #0f0;
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        .solver-btn {
            width: 100%;
            padding: 10px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            margin-bottom: 8px;
            transition: all 0.3s;
        }
        
        .solver-btn:hover {
            transform: translateY(-1px);
        }
        
        .btn-start {
            background: linear-gradient(135deg, #00c853, #00e676);
            color: white;
        }
        
        .btn-stop {
            background: linear-gradient(135deg, #ff1744, #ff5252);
            color: white;
        }
        
        .btn-settings {
            background: rgba(255,255,255,0.1);
            color: #00d4ff;
        }
        
        .logs-container {
            max-height: 150px;
            overflow-y: auto;
            background: rgba(0,0,0,0.3);
            padding: 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            margin-top: 10px;
        }
        
        .log-item {
            padding: 2px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        
        .settings-modal {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1a1a2e;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.7);
            z-index: 1000000;
            min-width: 350px;
            display: none;
        }
        
        .settings-modal.active {
            display: block;
        }
        
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 999999;
            display: none;
        }
        
        .modal-overlay.active {
            display: block;
        }
        
        .settings-group {
            margin-bottom: 15px;
        }
        
        .settings-label {
            display: block;
            color: #00d4ff;
            margin-bottom: 5px;
            font-size: 0.9rem;
        }
        
        .settings-input {
            width: 100%;
            padding: 8px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            color: #fff;
        }
        
        .modal-buttons {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
    `);

    // ==================== UI CREATION ====================
    function createUI() {
        // Main panel
        const panel = document.createElement('div');
        panel.id = 'quiz-solver-panel';
        panel.innerHTML = `
            <div class="panel-header">
                <div class="panel-title">🤖 Quiz Solver</div>
                <button class="btn-minimize" onclick="this.closest('#quiz-solver-panel').classList.toggle('minimized')">_</button>
            </div>
            <div class="panel-content">
                <div class="status-badge status-idle" id="status-badge">⚪ Đang chờ</div>
                <button class="solver-btn btn-start" id="btn-start">▶️ BẮT ĐẦU GIẢI</button>
                <button class="solver-btn btn-stop" id="btn-stop" style="display:none;">⏹️ DỪNG LẠI</button>
                <button class="solver-btn btn-settings" id="btn-settings">⚙️ Cài đặt</button>
                <div class="logs-container" id="logs"></div>
            </div>
        `;
        document.body.appendChild(panel);

        // Settings modal
        const modalOverlay = document.createElement('div');
        modalOverlay.className = 'modal-overlay';
        modalOverlay.id = 'modal-overlay';
        document.body.appendChild(modalOverlay);

        const modal = document.createElement('div');
        modal.className = 'settings-modal';
        modal.id = 'settings-modal';
        modal.innerHTML = `
            <h3 style="color: #00d4ff; margin-bottom: 15px;">⚙️ Cài Đặt</h3>
            <div class="settings-group">
                <label class="settings-label">Gemini API Key:</label>
                <input type="password" class="settings-input" id="input-api-key" placeholder="AIza..." value="${state.geminiApiKey || ''}">
            </div>
            <div class="settings-group">
                <label class="settings-label">Gemini Model:</label>
                <select class="settings-input" id="input-model">
                    <option value="2.5-flash" ${state.solverConfig.geminiModel === '2.5-flash' ? 'selected' : ''}>Gemini 2.5 Flash</option>
                    <option value="2.5-pro" ${state.solverConfig.geminiModel === '2.5-pro' ? 'selected' : ''}>Gemini 2.5 Pro</option>
                    <option value="3.0-pro" ${state.solverConfig.geminiModel === '3.0-pro' ? 'selected' : ''}>Gemini 3.0 Pro</option>
                </select>
            </div>
            <div class="settings-group">
                <label class="settings-label">Delay (giây):</label>
                <input type="number" class="settings-input" id="input-delay-min" placeholder="Min" value="${state.solverConfig.delayMin}" style="width: 45%; display: inline-block;">
                -
                <input type="number" class="settings-input" id="input-delay-max" placeholder="Max" value="${state.solverConfig.delayMax}" style="width: 45%; display: inline-block;">
            </div>
            <div class="modal-buttons">
                <button class="solver-btn btn-start" id="btn-save-settings">Lưu</button>
                <button class="solver-btn btn-settings" id="btn-cancel-settings">Hủy</button>
            </div>
        `;
        document.body.appendChild(modal);

        // Event listeners
        document.getElementById('btn-start').addEventListener('click', startSolver);
        document.getElementById('btn-stop').addEventListener('click', stopSolver);
        document.getElementById('btn-settings').addEventListener('click', openSettings);
        document.getElementById('btn-save-settings').addEventListener('click', saveSettings);
        document.getElementById('btn-cancel-settings').addEventListener('click', closeSettings);
        modalOverlay.addEventListener('click', closeSettings);
    }

    // ==================== SETTINGS ====================
    function openSettings() {
        document.getElementById('settings-modal').classList.add('active');
        document.getElementById('modal-overlay').classList.add('active');
    }

    function closeSettings() {
        document.getElementById('settings-modal').classList.remove('active');
        document.getElementById('modal-overlay').classList.remove('active');
    }

    function saveSettings() {
        state.geminiApiKey = document.getElementById('input-api-key').value;
        state.solverConfig.geminiModel = document.getElementById('input-model').value;
        state.solverConfig.delayMin = parseInt(document.getElementById('input-delay-min').value);
        state.solverConfig.delayMax = parseInt(document.getElementById('input-delay-max').value);

        GM_setValue('geminiApiKey', state.geminiApiKey);
        GM_setValue('solverConfig', state.solverConfig);

        log('✅ Đã lưu cài đặt');
        closeSettings();
    }

    // ==================== LOGGING ====================
    function log(message) {
        console.log(message);
        const logsEl = document.getElementById('logs');
        if (logsEl) {
            const logItem = document.createElement('div');
            logItem.className = 'log-item';
            logItem.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            logsEl.insertBefore(logItem, logsEl.firstChild);

            // Keep only last 50 logs
            while (logsEl.children.length > 50) {
                logsEl.removeChild(logsEl.lastChild);
            }
        }
    }

    function updateStatus(text, isRunning) {
        const badge = document.getElementById('status-badge');
        if (badge) {
            badge.textContent = text;
            badge.className = 'status-badge ' + (isRunning ? 'status-running' : 'status-idle');
        }
    }

    // ==================== CONTINUATION IN NEXT MESSAGE ====================
    // Due to length, I'll split the userscript into parts
    // This part contains: Metadata, Styles, UI, Settings
    // Next part will contain: Solver Logic, Gemini Integration, Quiz Detection

    console.log('Quiz Solver UI created');
    createUI();
    log('🎉 Quiz Solver đã sẵn sàng!');

})();
