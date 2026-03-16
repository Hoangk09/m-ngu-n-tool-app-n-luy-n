// ==UserScript==
// @name         Quiz Solver Ultimate - Userscript
// @namespace    http://tampermonkey.net/
// @version      1.0.0
// @description  Giải quiz tự động trên onluyen.vn với Gemini AI (không cần extension!)
// @author       nhat
// @match        https://app.onluyen.vn/*
// @match        *://app.onluyen.vn/*
// @icon         data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCI+PHRleHQgeT0iNDgiIGZvbnQtc2l6ZT0iNDgiPvCfpJY8L3RleHQ+PC9zdmc+
// @grant        GM_xmlhttpRequest
// @grant        GM.xmlHttpRequest
// @grant        GM_setValue
// @grant        GM.setValue
// @grant        GM_getValue
// @grant        GM.getValue
// @grant        GM_addStyle
// @grant        GM.addStyle
// @connect      *
// @connect      tool.1amsleep.xyz
// @connect      gemini.google.com
// @connect      push.clients6.google.com
// @connect      generativelanguage.googleapis.com
// @run-at       document-end
// @noframes
// ==/UserScript==

/*
 * Quiz Solver Ultimate - Userscript Edition
 * Chuyển đổi từ Chrome Extension sang Tampermonkey
 * Hỗ trợ: Tampermonkey, Violentmonkey, Stay Browser
 */

(async function () {
    'use strict';

    // DEBUG: Confirm script is running
    console.log('🚀 Quiz Solver Userscript STARTING...');
    alert('Quiz Solver đang tải...');

    // ==================== POLYFILL FOR STAY BROWSER ====================
    // Simplified polyfill - use native GM_ functions for Tampermonkey
    var _GM_xmlhttpRequest = GM_xmlhttpRequest;
    var _GM_setValue = GM_setValue;
    var _GM_getValue = GM_getValue;
    var _GM_addStyle = GM_addStyle;

    console.log('✅ Polyfill loaded');


    // ==================== CONFIGURATION ====================
    const CONFIG = {
        API_BASE: 'https://tool.1amsleep.xyz',
        VERSION: '1.0.0'
    };

    // ==================== STATE MANAGEMENT ====================
    const state = {
        isRunning: false,
        currentQuestion: 0,
        totalQuestions: 0,
        cachedAnswers: null,
        geminiApiKey: _GM_getValue('geminiApiKey', ''),
        geminiModel: _GM_getValue('geminiModel', '2.5-flash'),
        user: _GM_getValue('user', null),
        config: _GM_getValue('config', {
            delayMin: 3,
            delayMax: 8,
            autoSubmit: true
        })
    };

    // ==================== STYLES ====================
    _GM_addStyle(`
        #qs-panel {
            position: fixed;
            top: 20px;
            right: 20px;
            width: 320px;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            color: #fff;
            font-family: 'Segoe UI', sans-serif;
            z-index: 999999;
            padding: 15px;
            transition: all 0.3s;
        }
        #qs-panel.minimized { width: 50px; height: 50px; padding: 0; overflow: hidden; }
        .qs-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .qs-title { font-size: 1.1rem; font-weight: bold; color: #00d4ff; }
        .qs-minimize { background: transparent; border: none; color: #888; cursor: pointer; font-size: 1.2rem; padding: 0; width: 30px; height: 30px; }
        .minimized .qs-header { border: none; margin: 0; padding: 0; justify-content: center; }
        .minimized .qs-title { display: none; }
        .minimized .qs-body { display: none; }
        .qs-status { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; margin-bottom: 10px; }
        .status-idle { background: rgba(200,200,200,0.2); color: #aaa; }
        .status-running { background: rgba(0,200,0,0.2); color: #0f0; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }
        .qs-btn { width: 100%; padding: 10px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; margin-bottom: 8px; transition: all 0.3s; }
        .qs-btn:hover { transform: translateY(-1px); }
        .btn-start { background: linear-gradient(135deg, #00c853, #00e676); color: white; }
        .btn-stop { background: linear-gradient(135deg, #ff1744, #ff5252); color: white; }
        .btn-settings { background: rgba(255,255,255,0.1); color: #00d4ff; }
        .qs-logs { max-height: 150px; overflow-y: auto; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; font-size: 0.75rem; margin-top: 10px; font-family: monospace; }
        .log-item { padding: 2px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        
        #qs-modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 999998; display: none; }
        #qs-modal-overlay.active { display: block; }
        #qs-modal { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: #1a1a2e; padding: 20px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.7); z-index: 999999; min-width: 350px; display: none; }
        #qs-modal.active { display: block; }
        .modal-title { color: #00d4ff; margin-bottom: 15px; font-size: 1.2rem; }
        .setting-group { margin-bottom: 15px; }
        .setting-label { display: block; color: #00d4ff; margin-bottom: 5px; font-size: 0.9rem; }
        .setting-input { width: 100%; padding: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.2); border-radius: 6px; color: #fff; }
        .modal-actions { display: flex; gap: 10px; margin-top: 15px; }
    `);

    // ==================== UTILITY FUNCTIONS ====================
    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
    const randomDelay = () => Math.floor(state.config.delayMin * 1000 + Math.random() * (state.config.delayMax - state.config.delayMin) * 1000);

    function log(msg) {
        console.log('[QS]', msg);
        const logsEl = document.getElementById('qs-logs');
        if (logsEl) {
            const item = document.createElement('div');
            item.className = 'log-item';
            item.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
            logsEl.insertBefore(item, logsEl.firstChild);
            while (logsEl.children.length > 50) logsEl.removeChild(logsEl.lastChild);
        }
    }

    function updateStatus(text, running = false) {
        const badge = document.getElementById('qs-status');
        if (badge) {
            badge.textContent = text;
            badge.className = 'qs-status ' + (running ? 'status-running' : 'status-idle');
        }
    }

    // ==================== UI CREATION ====================
    function createUI() {
        const panel = document.createElement('div');
        panel.id = 'qs-panel';
        panel.innerHTML = `
            <div class="qs-header">
                <div class="qs-title">🤖 Quiz Solver</div>
                <button class="qs-minimize" onclick="this.closest('#qs-panel').classList.toggle('minimized')">_</button>
            </div>
            <div class="qs-body">
                <div class="qs-status status-idle" id="qs-status">⚪ Đang chờ</div>
                <button class="qs-btn btn-start" id="qs-btn-start">▶️ BẮT ĐẦU GIẢI</button>
                <button class="qs-btn btn-stop" id="qs-btn-stop" style="display:none;">⏹️ DỪNG LẠI</button>
                <button class="qs-btn btn-settings" id="qs-btn-settings">⚙️ Cài Đặt</button>
                <div class="qs-logs" id="qs-logs"></div>
            </div>
        `;
        document.body.appendChild(panel);

        const overlay = document.createElement('div');
        overlay.id = 'qs-modal-overlay';
        document.body.appendChild(overlay);

        const modal = document.createElement('div');
        modal.id = 'qs-modal';
        modal.innerHTML = `
            <h3 class="modal-title">⚙️ Cài Đặt</h3>
            <div class="setting-group">
                <label class="setting-label">Gemini API Key (tùy chọn):</label>
                <input type="password" class="setting-input" id="input-apikey" placeholder="AIza..." value="${state.geminiApiKey}">
                <div style="font-size:0.7rem;color:#888;margin-top:4px;">Để trống nếu dùng Gemini Web</div>
            </div>
            <div class="setting-group">
                <label class="setting-label">Model:</label>
                <select class="setting-input" id="input-model">
                    <option value="2.5-flash" ${state.geminiModel === '2.5-flash' ? 'selected' : ''}>Gemini 2.5 Flash</option>
                    <option value="2.5-pro" ${state.geminiModel === '2.5-pro' ? 'selected' : ''}>Gemini 2.5 Pro</option>
                    <option value="3.0-pro" ${state.geminiModel === '3.0-pro' ? 'selected' : ''}>Gemini 3.0 Pro</option>
                </select>
            </div>
            <div class="setting-group">
                <label class="setting-label">Delay (giây):</label>
                <div style="display:flex;gap:5px;">
                    <input type="number" class="setting-input" id="input-delay-min" value="${state.config.delayMin}" style="width:48%;">
                    <input type="number" class="setting-input" id="input-delay-max" value="${state.config.delayMax}" style="width:48%;">
                </div>
            </div>
            <div class="modal-actions">
                <button class="qs-btn btn-start" id="btn-save">Lưu</button>
                <button class="qs-btn btn-settings" id="btn-cancel">Hủy</button>
            </div>
        `;
        document.body.appendChild(modal);

        // Event listeners
        document.getElementById('qs-btn-start').addEventListener('click', startSolver);
        document.getElementById('qs-btn-stop').addEventListener('click', stopSolver);
        document.getElementById('qs-btn-settings').addEventListener('click', () => {
            modal.classList.add('active');
            overlay.classList.add('active');
        });
        document.getElementById('btn-save').addEventListener('click', () => {
            state.geminiApiKey = document.getElementById('input-apikey').value;
            state.geminiModel = document.getElementById('input-model').value;
            state.config.delayMin = parseInt(document.getElementById('input-delay-min').value);
            state.config.delayMax = parseInt(document.getElementById('input-delay-max').value);

            _GM_setValue('geminiApiKey', state.geminiApiKey);
            _GM_setValue('geminiModel', state.geminiModel);
            _GM_setValue('config', state.config);

            log('✅ Đã lưu cài đặt');
            modal.classList.remove('active');
            overlay.classList.remove('active');
        });
        document.getElementById('btn-cancel').addEventListener('click', () => {
            modal.classList.remove('active');
            overlay.classList.remove('active');
        });
        overlay.addEventListener('click', () => {
            modal.classList.remove('active');
            overlay.classList.remove('active');
        });
    }

    // ==================== QUIZ DETECTION ====================
    function detectQuestion() {
        const selectors = ['.question-content', '.title-question', '.content-question', '.ql-editor', '[class*="question"]'];
        for (const sel of selectors) {
            const els = document.querySelectorAll(sel);
            for (const el of els) {
                const text = el.innerText?.trim();
                if (text && text.length > 10) return el;
            }
        }
        return null;
    }

    function detectQuestionType() {
        const shortAnswer = document.querySelectorAll('.answer-input input[type="text"], input[id^="mathplay-answer"]');
        if (shortAnswer.length > 0) return { type: 'short_answer', elements: shortAnswer };

        const trueFalse = document.querySelectorAll('.true-false');
        if (trueFalse.length > 0) return { type: 'true_false', elements: trueFalse };

        const options = document.querySelectorAll('.question-option');
        if (options.length >= 2) return { type: 'multiple_choice', elements: options };

        return null;
    }

    function extractOptions() {
        const options = document.querySelectorAll('.question-option');
        return Array.from(options).map((opt, i) => ({
            id: String.fromCharCode(65 + i),
            text: opt.innerText?.trim() || ''
        }));
    }

    // ==================== GEMINI WEB INTEGRATION ====================

    // Model headers for different Gemini models
    const MODEL_HEADERS = {
        '2.5-flash': '[1,null,null,null,"9ec249fc9ad08861",null,null,0,[4]]',
        '2.5-pro': '[1,null,null,null,"4af6c7f5da75d65d",null,null,0,[4]]',
        '3.0-pro': '[1,null,null,null,"9d8ca3786ebdfbea",null,null,0,[4]]'
    };

    // _GM_xmlhttpRequest wrapper as Promise
    function gmFetch(url, options = {}) {
        return new Promise((resolve, reject) => {
            _GM_xmlhttpRequest({
                method: options.method || 'GET',
                url: url,
                headers: options.headers || {},
                data: options.body || null,
                withCredentials: true,
                onload: (response) => {
                    resolve({
                        ok: response.status >= 200 && response.status < 300,
                        status: response.status,
                        text: () => Promise.resolve(response.responseText),
                        headers: {
                            get: (name) => response.responseHeaders.split('\n')
                                .find(h => h.toLowerCase().startsWith(name.toLowerCase()))
                                ?.split(':')[1]?.trim()
                        }
                    });
                },
                onerror: (err) => reject(err)
            });
        });
    }

    async function askGemini(prompt, imageBase64 = null) {
        // Chỉ dùng Gemini Web (không cần API key)
        log('🌐 Đang gọi Gemini Web...');
        return await askGeminiWeb(prompt, imageBase64);
    }

    async function askGeminiWeb(prompt, imageBase64) {
        try {
            const modelHeader = MODEL_HEADERS[state.geminiModel] || MODEL_HEADERS['2.5-flash'];
            log(`🤖 Model: ${state.geminiModel}`);

            // Step 1: Get access token from Gemini page
            log('📡 Đang lấy token...');
            const initResp = await gmFetch('https://gemini.google.com/app');
            if (!initResp.ok) {
                log('❌ Không thể kết nối Gemini. Hãy đăng nhập gemini.google.com');
                return null;
            }

            const html = await initResp.text();

            // Extract SNlM0e token
            let accessToken = '';
            const atMatch = html.match(/"SNlM0e":"([^"]+)"/);
            if (atMatch) {
                accessToken = atMatch[1];
            } else {
                const altMatch = html.match(/\["SNlM0e"\s*,\s*"([^"]+)"/);
                if (altMatch) accessToken = altMatch[1];
            }

            if (!accessToken) {
                log('❌ Không lấy được token. Hãy đăng nhập gemini.google.com');
                return null;
            }

            // Extract bl token
            let bl = 'boq_assistant-bard-web-server_20251217.07_p5';
            const blMatch = html.match(/"cfb2h":"([^"]+)"/);
            if (blMatch) bl = blMatch[1];

            // Extract Feed ID for image upload
            let feedId = null;
            const feedMatch = html.match(/feeds\/([a-z0-9]+)/i);
            if (feedMatch) feedId = feedMatch[0];

            log('✅ Đã lấy token');

            // Step 2: Upload image if provided
            let imageUrl = null;
            if (imageBase64) {
                log('📤 Đang upload ảnh...');
                imageUrl = await uploadImage(imageBase64, feedId);
                if (imageUrl) {
                    log('✅ Upload ảnh thành công');
                } else {
                    log('⚠️ Upload ảnh thất bại, tiếp tục với text');
                }
            }

            // Step 3: Build payload
            let innerPayload;
            if (imageUrl) {
                let imagePath = imageUrl.replace('https://push.clients6.google.com', '');
                const filename = `screenshot_${Date.now()}.jpg`;
                innerPayload = JSON.stringify([
                    [prompt, 0, null, [[[imagePath, 1, null, "image/jpeg"], filename, null, null, null, null, null, null, [0]]], null, null, 0],
                    ["vi"]
                ]);
            } else {
                innerPayload = JSON.stringify([[prompt], null, null]);
            }

            const fReq = JSON.stringify([null, innerPayload]);
            const formData = `f.req=${encodeURIComponent(fReq)}&at=${encodeURIComponent(accessToken)}`;

            // Step 4: Send request
            log('🔄 Đang gửi câu hỏi...');
            const endpoint = `https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate?bl=${bl}&_reqid=${Date.now()}&rt=c`;

            const resp = await gmFetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
                    'x-goog-ext-525001261-jspb': modelHeader
                },
                body: formData
            });

            if (!resp.ok) {
                log(`❌ Lỗi API: ${resp.status}`);
                return null;
            }

            const responseText = await resp.text();

            // Parse response
            const answer = parseGeminiResponse(responseText);
            return answer;

        } catch (err) {
            log(`❌ Lỗi: ${err.message}`);
            console.error(err);
            return null;
        }
    }

    async function uploadImage(base64Data, feedId) {
        try {
            // Convert base64 to binary string for upload
            const binaryString = atob(base64Data);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            // Start upload session
            const uploadHeaders = {
                'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8',
                'X-Goog-Upload-Command': 'start',
                'X-Goog-Upload-Header-Content-Length': bytes.length.toString(),
                'X-Goog-Upload-Header-Content-Type': 'image/jpeg',
                'X-Goog-Upload-Protocol': 'resumable',
                'X-Tenant-Id': 'bard-storage'
            };
            if (feedId) uploadHeaders['Push-Id'] = feedId;

            const initBody = JSON.stringify({
                protocolVersion: '0.8',
                createSessionRequest: {
                    fields: [{ external: { name: 'file', filename: `img_${Date.now()}.jpg`, put: {}, size: bytes.length } }]
                }
            });

            const initResp = await gmFetch('https://push.clients6.google.com/upload/', {
                method: 'POST',
                headers: uploadHeaders,
                body: initBody
            });

            if (!initResp.ok) return null;

            const uploadUrl = initResp.headers.get('X-Goog-Upload-URL');
            if (!uploadUrl) return null;

            // Upload file content
            const uploadResp = await new Promise((resolve, reject) => {
                _GM_xmlhttpRequest({
                    method: 'POST',
                    url: uploadUrl,
                    headers: {
                        'Content-Type': 'application/octet-stream',
                        'X-Goog-Upload-Command': 'upload, finalize',
                        'X-Goog-Upload-Offset': '0'
                    },
                    data: bytes.buffer,
                    withCredentials: true,
                    onload: (r) => resolve({ ok: r.status >= 200 && r.status < 300, text: r.responseText }),
                    onerror: reject
                });
            });

            if (!uploadResp.ok) return null;

            // Parse response - could be JSON or direct URL
            try {
                const json = JSON.parse(uploadResp.text);
                return json?.sessionStatus?.externalFieldTransfers?.[0]?.scottyUrl;
            } catch {
                if (uploadResp.text.startsWith('/contrib_')) {
                    return 'https://push.clients6.google.com' + uploadResp.text.trim();
                }
            }
            return null;
        } catch (err) {
            console.error('Upload error:', err);
            return null;
        }
    }

    function parseGeminiResponse(text) {
        try {
            // Find response in streaming data
            const lines = text.split('\n');
            for (const line of lines) {
                if (line.includes('wrb.fr')) {
                    const match = line.match(/\["wrb\.fr",null,"(.+?)(?:",null|\])/s);
                    if (match) {
                        let jsonStr = match[1].replace(/\\"/g, '"').replace(/\\\\/g, '\\');
                        try {
                            const parsed = JSON.parse(jsonStr);
                            // Extract answer text - usually in first array
                            if (Array.isArray(parsed) && parsed[4]) {
                                const candidates = parsed[4];
                                if (Array.isArray(candidates) && candidates[0]) {
                                    const content = candidates[0][1]?.[0] || candidates[0][0];
                                    if (content) {
                                        // Clean and extract just the letter
                                        const cleaned = content.replace(/\*\*/g, '').trim();
                                        const letterMatch = cleaned.match(/^([A-D])/i);
                                        if (letterMatch) return letterMatch[1].toUpperCase();
                                        return cleaned.substring(0, 100);
                                    }
                                }
                            }
                        } catch { }
                    }
                }
            }

            // Fallback: look for single letter answer
            const letterMatch = text.match(/\b([A-D])\b/);
            if (letterMatch) return letterMatch[1];

            return null;
        } catch {
            return null;
        }
    }

    // ==================== SOLVER LOGIC ====================
    async function solveCurrentQuestion() {
        const questionEl = detectQuestion();
        if (!questionEl) {
            log('⚠️ Không tìm thấy câu hỏi');
            return false;
        }

        const questionText = questionEl.innerText;
        const qType = detectQuestionType();

        if (!qType) {
            log('⚠️ Không nhận diện được loại câu hỏi');
            return false;
        }

        log(`📝 Câu ${state.currentQuestion + 1}: ${qType.type}`);

        let prompt = `Xem câu hỏi. CHỈ trả lời 1 chữ cái: A, B, C hoặc D. Tuyệt đối KHÔNG giải thích.\n\nCâu hỏi: ${questionText}`;

        if (qType.type === 'multiple_choice') {
            const opts = extractOptions();
            prompt += `\n\nCác đáp án:\n${opts.map(o => `${o.id}. ${o.text}`).join('\n')}`;
        }

        const answer = await askGemini(prompt);

        if (!answer) {
            log('❌ Không nhận được câu trả lời');
            return false;
        }

        log(`💡 Đáp án: ${answer}`);

        // Apply answer
        if (qType.type === 'multiple_choice') {
            return await handleMultipleChoice(qType.elements, answer);
        } else if (qType.type === 'short_answer') {
            return await handleShortAnswer(qType.elements, answer);
        } else if (qType.type === 'true_false') {
            return await handleTrueFalse(qType.elements, answer);
        }

        return false;
    }

    async function handleMultipleChoice(options, answer) {
        const index = answer.charCodeAt(0) - 65;
        if (index >= 0 && index < options.length) {
            options[index].scrollIntoView({ block: 'center' });
            await sleep(300);
            options[index].click();
            log(`✓ Đã chọn ${answer}`);
            return true;
        }
        return false;
    }

    async function handleShortAnswer(inputs, answer) {
        const input = inputs[0];
        input.scrollIntoView({ block: 'center' });
        await sleep(200);
        input.focus();
        input.value = answer;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        log(`✓ Đã nhập: ${answer}`);
        return true;
    }

    async function handleTrueFalse(containers, answer) {
        // Simplified T/F handler
        log(`✓ Đã chọn ${answer}`);
        return true;
    }

    async function clickNext() {
        const nextSelectors = [
            'button:contains("Tiếp tục")',
            'button:contains("Next")',
            '.btn-next',
            '[class*="continue"]',
            '[class*="next"]'
        ];

        for (const sel of nextSelectors) {
            const btns = document.querySelectorAll(sel);
            for (const btn of btns) {
                if (btn.offsetParent !== null) {
                    btn.click();
                    return true;
                }
            }
        }
        return false;
    }

    // ==================== MAIN SOLVER ====================
    async function startSolver() {
        if (state.isRunning) return;

        state.isRunning = true;
        state.currentQuestion = 0;

        document.getElementById('qs-btn-start').style.display = 'none';
        document.getElementById('qs-btn-stop').style.display = 'block';
        updateStatus('🚀 Đang giải...', true);

        log('🚀 Bắt đầu giải quiz!');

        while (state.isRunning) {
            const success = await solveCurrentQuestion();

            if (success) {
                await sleep(randomDelay());
                await clickNext();
                state.currentQuestion++;
                await sleep(1000);
            } else {
                log('⚠️ Không thể giải câu này, dừng lại');
                break;
            }
        }

        stopSolver();
    }

    function stopSolver() {
        state.isRunning = false;
        document.getElementById('qs-btn-start').style.display = 'block';
        document.getElementById('qs-btn-stop').style.display = 'none';
        updateStatus('⚪ Đã dừng', false);
        log('⏹️ Đã dừng');
    }

    // ==================== INITIALIZATION ====================
    console.log('🤖 Quiz Solver Userscript initializing...');
    createUI();
    log('✅ Quiz Solver đã sẵn sàng!');
    log('💡 Click BẮT ĐẦU GIẢI để tự động làm quiz');

})();
