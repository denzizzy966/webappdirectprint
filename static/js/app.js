let bridge = null;
let currentTheme = localStorage.getItem('theme') || 'dark';
let installedPrinters = [];
let activePools = {};

// Terapkan tema
document.documentElement.setAttribute('data-theme', currentTheme);

function toggleTheme() {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', currentTheme);
    localStorage.setItem('theme', currentTheme);
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.id !== 'themeBtn') btn.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(sec => sec.style.display = 'none');

    const targetSec = document.getElementById(`tab-${tabId}`);
    if (targetSec) targetSec.style.display = 'block';

    const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => 
        btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(tabId)
    );
    if (activeBtn) activeBtn.classList.add('active');

    if (tabId === 'printers') loadPrinters();
    if (tabId === 'scales') { loadScales(); loadControlPorts(); pollScaleTerminal(); }
    if (tabId === 'serial') loadSerialPorts();
    if (tabId === 'history') loadPrintHistory();
    if (tabId === 'settings') { loadSettings(); loadPrinterPools(); }
}

function addLog(msg, type = 'info') {
    const box = document.getElementById('logBox');
    if (!box) return;
    const div = document.createElement('div');
    div.className = `log-entry ${type}`;
    const now = new Date().toLocaleTimeString();
    div.innerHTML = `<span class="time">[${now}]</span> ${msg}`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function clearLogs() {
    const box = document.getElementById('logBox');
    if (box) box.innerHTML = '';
}

// ────────────────────────────────────────────────────────────
// Inisialisasi Bridge Client
// ────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', async () => {
    const currentPort = window.location.port ? parseInt(window.location.port, 10) : 18212;
    const currentHost = window.location.hostname || '127.0.0.1';
    bridge = new HardwareBridge({ host: currentHost, port: currentPort });

    bridge.onConnect(() => {
        addLog(`Berhasil terhubung ke WebSocket Daemon di port ${currentPort}.`, 'success');
        document.getElementById('serviceStatus').innerHTML = '<span class="badge badge-success">🟢 ONLINE</span>';
        loadSystemStatus();
        loadPrinters();
        loadScales();
    });

    bridge.onDisconnect(() => {
        addLog('Koneksi ke Bridge Daemon terputus. Mencoba reconnect otomatis...', 'error');
        document.getElementById('serviceStatus').innerHTML = '<span class="badge badge-danger">🔴 OFFLINE</span>';
    });

    // Reactive weight stream dari WebSocket
    bridge.onWeightChange((scales) => {
        if (scales && scales.length > 0) {
            const active = scales.find(s => s.connected && s.port !== 'SIM') || scales.find(s => s.connected) || scales[0];
            updateLcdDisplay(active);
            updateScaleTable(scales);
        }
    });

    // Jalur Ganda: SSE (Server-Sent Events) stream untuk update instan tanpa lag
    try {
        const sse = new EventSource('/api/stream');
        sse.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.scales && data.scales.length > 0) {
                    const active = data.scales.find(s => s.connected && s.port !== 'SIM') || data.scales.find(s => s.connected) || data.scales[0];
                    updateLcdDisplay(active);
                    updateScaleTable(data.scales);
                }
            } catch (err) {}
        };
    } catch (e) {
        console.warn('SSE fallback:', e);
    }

    // Polling periodik (500ms) sebagai safety net
    setInterval(loadScales, 500);
    setInterval(() => {
        const tabScales = document.getElementById('tab-scales');
        if (tabScales && tabScales.style.display !== 'none') {
            pollScaleTerminal();
        }
    }, 400);

    await bridge.connect();
    loadSystemStatus();
    loadPrinters();
    loadControlPorts();
    loadScales();
    loadPrintHistory();
});

// ────────────────────────────────────────────────────────────
// System Status
// ────────────────────────────────────────────────────────────

async function loadSystemStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        document.getElementById('statDefaultPrinter').textContent = data.default_printer || '(Belum ada)';
        document.getElementById('statOs').textContent = data.os_details || data.os;
    } catch (e) {
        console.warn('Gagal memuat status sistem:', e);
    }
}

// ────────────────────────────────────────────────────────────
// Printers Controller
// ────────────────────────────────────────────────────────────

async function loadPrinters() {
    const tbody = document.getElementById('printerTableBody');
    const select = document.getElementById('targetPrinterSelect');
    const badgeBar = document.getElementById('poolBadgeBar');
    try {
        const res = await fetch('/api/printers');
        const data = await res.json();
        installedPrinters = data.printers || [];
        activePools = data.pools || {};

        tbody.innerHTML = '';
        select.innerHTML = '';

        // Render Pool Badge Bar
        if (badgeBar) {
            const poolKeys = Object.keys(activePools);
            if (poolKeys.length === 0) {
                badgeBar.innerHTML = '<span style="font-weight: 600; font-size: 0.9rem; color: var(--text-muted);">🎯 Target Label:</span> <span class="badge badge-warning">Belum diatur</span>';
            } else {
                badgeBar.innerHTML = '<span style="font-weight: 600; font-size: 0.9rem; color: var(--text-muted);">🎯 Target Label:</span> ' +
                    poolKeys.map(k => `<span class="badge badge-primary" style="cursor: pointer; margin-right: 0.35rem;" title="Terarah ke: ${activePools[k]}" onclick="switchTab('settings')"><b>${k}</b> ➔ ${activePools[k]}</span>`).join('');
            }
        }

        if (installedPrinters.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Tidak ada printer yang terdeteksi.</td></tr>';
            return;
        }

        installedPrinters.forEach(p => {
            const tr = document.createElement('tr');
            const defBadge = p.is_default ? '<span class="badge badge-primary">DEFAULT</span> ' : '';
            const netBadge = p.is_network ? '<span class="badge badge-warning">NETWORK</span> ' : '<span class="badge badge-success">LOCAL</span> ';
            
            tr.innerHTML = `
                <td><b>${defBadge}${p.name}</b></td>
                <td><span class="badge badge-success">${p.status}</span></td>
                <td>${netBadge}${p.driver || '-'}</td>
                <td><code>${p.port || '-'}</code></td>
                <td>
                    <button class="btn btn-secondary" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;" onclick="testPrintSpecific('${p.name}')">Test Cetak</button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        // 1. Group Target Pool / Label (imTigger style)
        const poolKeys = Object.keys(activePools);
        if (poolKeys.length > 0) {
            const optGroupPools = document.createElement('optgroup');
            optGroupPools.label = '🎯 Printer Pool / Label Target';
            poolKeys.forEach(k => {
                const opt = document.createElement('option');
                opt.value = k;
                opt.textContent = `🎯 ${k} ➔ [${activePools[k]}]`;
                optGroupPools.appendChild(opt);
            });
            select.appendChild(optGroupPools);
        }

        // 2. Group Printer Fisik
        const optGroupPhysical = document.createElement('optgroup');
        optGroupPhysical.label = '🖨️ Printer Fisik Terpasang';
        installedPrinters.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.name;
            opt.textContent = `${p.is_default ? '⭐ ' : ''}${p.name} (${p.is_network ? 'TCP' : 'Local'})`;
            if (p.is_default && poolKeys.length === 0) opt.selected = true;
            optGroupPhysical.appendChild(opt);
        });
        select.appendChild(optGroupPhysical);

        addLog(`Terdeteksi ${installedPrinters.length} printer fisik & ${poolKeys.length} printer pool.`);
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" style="color: var(--danger); text-align: center;">Gagal memuat printer: ${e.message}</td></tr>`;
    }
}

async function testPrintReceipt() {
    const printer = document.getElementById('targetPrinterSelect').value;
    addLog(`Mengirim pengujian struk thermal ESC/POS ke: ${printer}...`);
    try {
        const res = await fetch(`/api/print/test-receipt?printer=${encodeURIComponent(printer)}`, { method: 'POST' });
        const json = await res.json();
        if (json.status === 'success') {
            addLog(`✅ Cetak Struk Berhasil! (${json.result.bytes_sent} bytes)`, 'success');
        } else {
            addLog(`❌ Cetak Struk Gagal: ${json.detail || json.message}`, 'error');
        }
        loadPrintHistory();
    } catch (e) {
        addLog(`❌ Error cetak struk: ${e.message}`, 'error');
    }
}

async function testPrintZpl() {
    const printer = document.getElementById('targetPrinterSelect').value;
    addLog(`Mengirim pengujian barcode ZPL ke: ${printer}...`);
    try {
        const res = await fetch(`/api/print/test-label?printer=${encodeURIComponent(printer)}`, { method: 'POST' });
        const json = await res.json();
        if (json.status === 'success') {
            addLog(`✅ Cetak Label Barcode ZPL Berhasil!`, 'success');
        } else {
            addLog(`❌ Cetak ZPL Gagal: ${json.detail || json.message}`, 'error');
        }
        loadPrintHistory();
    } catch (e) {
        addLog(`❌ Error cetak ZPL: ${e.message}`, 'error');
    }
}

async function testOpenDrawer() {
    const printer = document.getElementById('targetPrinterSelect').value;
    addLog(`Mengirim pulsa pembuka laci kasir ke: ${printer}...`);
    try {
        const res = await fetch('/api/cashdrawer/open', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ printer: printer, pin: 2 })
        });
        const json = await res.json();
        if (json.status === 'success') {
            addLog(`✅ Pulsa laci uang berhasil dikirim!`, 'success');
        } else {
            addLog(`❌ Gagal buka laci: ${json.detail || json.message}`, 'error');
        }
    } catch (e) {
        addLog(`❌ Error laci kasir: ${e.message}`, 'error');
    }
}

async function sendCustomRaw() {
    const printer = document.getElementById('targetPrinterSelect').value;
    const text = document.getElementById('customRawInput').value;
    if (!text) {
        alert('Teks / data tidak boleh kosong!');
        return;
    }
    addLog(`Mengirim custom data (${text.length} karakter) ke: ${printer}...`);
    try {
        const res = await fetch('/api/print/raw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ printer: printer, data: text, doc_name: 'Custom_Print' })
        });
        const json = await res.json();
        if (json.status === 'success') {
            addLog(`✅ Data RAW berhasil dicetak! (${json.result.bytes_sent} bytes)`, 'success');
        } else {
            addLog(`❌ Cetak Gagal: ${json.detail || json.message}`, 'error');
        }
        loadPrintHistory();
    } catch (e) {
        addLog(`❌ Error kirim custom raw: ${e.message}`, 'error');
    }
}

function testPrintSpecific(printerName) {
    document.getElementById('targetPrinterSelect').value = printerName;
    testPrintReceipt();
}

// ────────────────────────────────────────────────────────────
// Scale Controller & Interactive Testing Console
// ────────────────────────────────────────────────────────────

let terminalLastLogId = 0;
let terminalLogBuffer = [];
let isScalePaused = false;

function updateLcdDisplay(scaleData) {
    if (!scaleData) return;

    const weightVal = document.getElementById('lcdWeightVal');
    const unitVal = document.getElementById('lcdUnitVal');
    const connBadge = document.getElementById('conn-badge');
    const stableBadge = document.getElementById('stable-badge');
    const ageBadge = document.getElementById('age-badge');
    const detailStatus = document.getElementById('scaleDetailStatus');
    const statWeight = document.getElementById('statWeight');

    // Legacy badge fallback
    const legacyStableBadge = document.getElementById('lcdStableBadge');
    const legacyStateBadge = document.getElementById('lcdStateBadge');
    const legacyScaleName = document.getElementById('lcdScaleName');

    const isConnected = !!scaleData.connected;
    const w = (scaleData.weight !== null && scaleData.weight !== undefined) ? scaleData.weight.toFixed(2) : '--.--';
    const u = scaleData.unit || 'g';

    if (weightVal) weightVal.textContent = isConnected ? w : '--.--';
    if (unitVal) unitVal.textContent = u;
    if (statWeight) statWeight.textContent = isConnected ? `${w} ${u}` : '0.00 g';

    if (connBadge) {
        if (isConnected) {
            connBadge.className = 'badge badge-success';
            connBadge.textContent = 'Terhubung';
        } else if (scaleData.state === 'paused' || scaleData.state === 'standby') {
            connBadge.className = 'badge badge-warning';
            connBadge.textContent = 'Dilepas';
        } else {
            connBadge.className = 'badge badge-danger';
            connBadge.textContent = 'Terputus';
        }
    }

    if (stableBadge) {
        if (isConnected) {
            stableBadge.style.display = 'inline-block';
            if (scaleData.stable) {
                stableBadge.className = 'badge badge-success';
                stableBadge.textContent = 'Stabil';
            } else {
                stableBadge.className = 'badge badge-warning';
                stableBadge.textContent = 'Dinamis';
            }
        } else {
            stableBadge.style.display = 'none';
        }
    }

    if (ageBadge) {
        if (isConnected && scaleData.age !== undefined) {
            ageBadge.style.display = 'inline-block';
            ageBadge.textContent = `${Number(scaleData.age).toFixed(1)}s`;
        } else {
            ageBadge.style.display = 'none';
        }
    }

    if (detailStatus) {
        detailStatus.textContent = scaleData.status_detail || (isConnected ? `${scaleData.name || 'Timbangan'} aktif` : 'Timbangan tidak terhubung');
    }

    if (legacyStableBadge) {
        legacyStableBadge.className = scaleData.stable ? 'badge badge-success' : 'badge badge-warning';
        legacyStableBadge.textContent = scaleData.stable ? 'STABIL' : 'BERGERAK';
    }
    if (legacyStateBadge) {
        legacyStateBadge.className = isConnected ? 'badge badge-success' : 'badge badge-danger';
        legacyStateBadge.textContent = (scaleData.state || 'OFFLINE').toUpperCase();
    }
    if (legacyScaleName) {
        legacyScaleName.textContent = `${scaleData.name || ''} [${scaleData.port || ''}]`;
    }
}

async function loadControlPorts() {
    const sel = document.getElementById('ctrlPort');
    if (!sel) return;
    try {
        const res = await fetch('/api/ports');
        const ports = await res.json();
        const prevVal = sel.value;
        sel.innerHTML = '';

        // Option 1: Simulator
        const simOpt = document.createElement('option');
        simOpt.value = 'SIM';
        simOpt.textContent = 'SIM — Simulator Mode (mock data)';
        sel.appendChild(simOpt);

        let selected = false;
        ports.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.device;
            opt.textContent = `${p.device}: ${p.description || 'Serial Device'}${p.connected ? ' (terhubung)' : ''}`;
            if (p.connected) {
                opt.selected = true;
                selected = true;
            } else if (!selected && prevVal && p.device === prevVal) {
                opt.selected = true;
                selected = true;
            }
            sel.appendChild(opt);
        });

        if (!selected && (prevVal === 'SIM' || !prevVal)) {
            simOpt.selected = true;
        }
    } catch (e) {
        console.warn('Gagal memuat ports control:', e);
    }
}

function onProtocolPresetChange() {
    const proto = document.getElementById('ctrlProtocol')?.value || 'auto';
    const baudSel = document.getElementById('ctrlBaud');
    const frameSel = document.getElementById('ctrlFrame');

    if (proto === 'and') {
        if (baudSel) baudSel.value = '2400';
        if (frameSel) frameSel.value = '7E';
    } else {
        if (baudSel) baudSel.value = '9600';
        if (frameSel) frameSel.value = '8N';
    }

    const grpMettler = document.getElementById('cmds-mettler');
    const grpShinko = document.getElementById('cmds-shinko');
    const grpAnd = document.getElementById('cmds-and');

    if (grpMettler) grpMettler.style.display = (proto === 'mettler' || proto === 'auto') ? 'flex' : 'none';
    if (grpShinko) grpShinko.style.display = (proto === 'shinko') ? 'flex' : 'none';
    if (grpAnd) grpAnd.style.display = (proto === 'and') ? 'flex' : 'none';
}

async function connectActiveScale() {
    const port = document.getElementById('ctrlPort')?.value || 'SIM';
    const protocol = document.getElementById('ctrlProtocol')?.value || 'auto';
    const baud = parseInt(document.getElementById('ctrlBaud')?.value || '9600', 10);
    const frame = document.getElementById('ctrlFrame')?.value || '8N';
    const interval = parseFloat(document.getElementById('ctrlInterval')?.value || '0.5');

    const databits = parseInt(frame[0], 10) || 8;
    const parity = frame[1] || 'N';

    addLog(`Menghubungkan ke ${port} (Protokol: ${protocol}, Baud: ${baud}, Frame: ${frame})...`);
    try {
        const res = await fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                port: port,
                protocol: protocol,
                baud: baud,
                databits: databits,
                parity: parity,
                stopbits: 1,
                poll_interval: interval
            })
        });
        const data = await res.json();
        if (data.ok || data.status === 'success') {
            addLog(`✅ Terhubung ke ${data.name || port}!`, 'success');
        } else {
            addLog(`❌ Gagal terhubung: ${data.detail || data.message || 'Error'}`, 'error');
        }
        await loadControlPorts();
        await loadScales();
        await pollScaleTerminal();
    } catch (e) {
        addLog(`❌ Error connect scale: ${e.message}`, 'error');
    }
}

async function disconnectActiveScale() {
    const port = document.getElementById('ctrlPort')?.value || 'SIM';
    addLog(`Memutuskan koneksi timbangan ${port}...`);
    try {
        const res = await fetch('/api/disconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ port: port })
        });
        const data = await res.json();
        addLog(`🔌 ${data.message || 'Koneksi ditutup.'}`);
        await loadControlPorts();
        await loadScales();
        await pollScaleTerminal();
    } catch (e) {
        addLog(`❌ Error disconnect: ${e.message}`, 'error');
    }
}

async function scanBaudActiveScale() {
    const port = document.getElementById('ctrlPort')?.value || 'SIM';
    addLog(`🔍 Memindai baud rate otomatis untuk ${port}...`);
    try {
        const res = await fetch(`/api/scale/scan-baud?port=${encodeURIComponent(port)}`, { method: 'POST' });
        const data = await res.json();
        if (data.ok && data.baud) {
            addLog(`✅ Baud rate ditemukan: ${data.baud}`, 'success');
            const baudSel = document.getElementById('ctrlBaud');
            if (baudSel) baudSel.value = String(data.baud);
            alert(`Baud rate ditemukan: ${data.baud}`);
        } else {
            addLog(`⚠️ ${data.message || 'Baud rate tidak merespons.'}`, 'warn');
            alert(data.message || 'Tidak ada respons dari timbangan.');
        }
        await loadScales();
    } catch (e) {
        addLog(`❌ Error scan baud: ${e.message}`, 'error');
    }
}

async function togglePausePort() {
    const btn = document.getElementById('btnCtrlPause');
    const port = document.getElementById('ctrlPort')?.value || 'SIM';
    if (!isScalePaused) {
        addLog(`Melepas port ${port} untuk aplikasi lain (Delphi/Web Serial)...`);
        try {
            const res = await fetch(`/api/scale/pause?scale=${encodeURIComponent(port)}`, { method: 'POST' });
            const data = await res.json();
            isScalePaused = true;
            if (btn) btn.innerHTML = '▶️ Sambung Lagi';
            addLog(`⏸️ Port dilepas. Bebas dibuka oleh Delphi atau browser.`, 'warn');
            await loadScales();
        } catch (e) {
            addLog(`❌ Error pause: ${e.message}`, 'error');
        }
    } else {
        addLog(`Menyambungkan kembali port ${port}...`);
        try {
            const res = await fetch(`/api/scale/resume?scale=${encodeURIComponent(port)}`, { method: 'POST' });
            const data = await res.json();
            isScalePaused = false;
            if (btn) btn.innerHTML = '⏸️ Lepas Port';
            addLog(`▶️ Port disambungkan kembali.`, 'success');
            await loadScales();
        } catch (e) {
            addLog(`❌ Error resume: ${e.message}`, 'error');
        }
    }
}

async function restartScaleService() {
    addLog('Merestart service timbangan & memindai port...');
    try {
        await resumeScale();
        await loadControlPorts();
        await loadScales();
        addLog('✅ Service timbangan direfresh.', 'success');
    } catch (e) {
        addLog(`❌ Error restart: ${e.message}`, 'error');
    }
}

async function sendScaleCmd(cmd) {
    const port = document.getElementById('ctrlPort')?.value || 'SIM';
    addLog(`Mengirim perintah [${cmd}] ke ${port}...`);
    try {
        const res = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ port: port, command: cmd })
        });
        const data = await res.json();
        if (data.status === 'success' || data.ok) {
            addLog(`✅ Perintah [${cmd}] terkirim`, 'success');
        } else {
            addLog(`❌ Gagal kirim perintah [${cmd}]`, 'error');
        }
        await pollScaleTerminal();
    } catch (e) {
        addLog(`❌ Error kirim perintah: ${e.message}`, 'error');
    }
}

async function sendManualScaleCmd() {
    const input = document.getElementById('manualCmdInput');
    if (!input) return;
    const cmd = input.value.trim();
    if (!cmd) return;
    input.value = '';
    await sendScaleCmd(cmd);
}

function clearTerminalLogs() {
    terminalLogBuffer = [];
    const term = document.getElementById('scaleLogTerminal');
    if (term) term.innerHTML = '';
}

function renderTerminalLogs() {
    const term = document.getElementById('scaleLogTerminal');
    if (!term) return;
    const showHex = document.getElementById('chkShowHex')?.checked || false;
    const autoscroll = document.getElementById('chkAutoscroll')?.checked !== false;

    let html = '';
    terminalLogBuffer.forEach(entry => {
        const t = entry.time || '';
        const dir = entry.dir || 'INFO';
        const msg = (entry.msg || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        const hex = entry.hex ? ` <span style="color: #64748b; font-size: 0.72rem;">[HEX: ${entry.hex}]</span>` : '';

        if (dir === 'TX') {
            html += `<div><span style="color: #60a5fa;">[${t}] TX &gt; ${msg}</span>${showHex ? hex : ''}</div>`;
        } else if (dir === 'RX') {
            html += `<div><span style="color: #4ade80;">[${t}] RX &lt; ${msg}</span>${showHex ? hex : ''}</div>`;
        } else {
            html += `<div><span style="color: #fbbf24;">[${t}] * ${msg}</span></div>`;
        }
    });

    term.innerHTML = html;
    if (autoscroll) {
        term.scrollTop = term.scrollHeight;
    }
}

async function pollScaleTerminal() {
    const port = document.getElementById('ctrlPort')?.value || 'SIM';
    try {
        const res = await fetch(`/api/scale/state?port=${encodeURIComponent(port)}&since=${terminalLastLogId}`);
        if (!res.ok) return;
        const state = await res.json();

        // Update metrics
        const elLines = document.getElementById('st-lines');
        const elBytes = document.getElementById('st-bytes');
        const elRate = document.getElementById('st-rate');
        if (elLines) elLines.textContent = state.rx_lines !== undefined ? state.rx_lines : 0;
        if (elBytes) elBytes.textContent = state.rx_bytes !== undefined ? state.rx_bytes : 0;
        if (elRate) elRate.textContent = state.bytes_per_sec !== undefined ? state.bytes_per_sec : 0;

        // Update Connection Status Bar
        const dot = document.getElementById('ctrlStatusDot');
        const text = document.getElementById('ctrlStatusText');
        const btnConn = document.getElementById('btnCtrlConnect');
        const btnDisc = document.getElementById('btnCtrlDisconnect');

        if (state.connected) {
            if (dot) dot.textContent = '🟢';
            if (text) text.textContent = `${state.port || port} (${state.baud || 9600} ${state.databits || 8}${state.parity || 'N'}1) — terhubung`;
            if (btnConn) btnConn.disabled = true;
            if (btnDisc) btnDisc.disabled = false;
        } else if (state.state === 'paused' || state.state === 'standby') {
            if (dot) dot.textContent = '🟡';
            if (text) text.textContent = `${state.port || port} — port dilepas (standby)`;
            if (btnConn) btnConn.disabled = false;
            if (btnDisc) btnDisc.disabled = true;
        } else {
            if (dot) dot.textContent = '🔴';
            if (text) text.textContent = `${state.port || port} — terputus`;
            if (btnConn) btnConn.disabled = false;
            if (btnDisc) btnDisc.disabled = true;
        }

        // Update LCD Display
        updateLcdDisplay(state);

        // Update Terminal Logs
        if (state.log && state.log.length > 0) {
            terminalLogBuffer.push(...state.log);
            if (terminalLogBuffer.length > 250) {
                terminalLogBuffer = terminalLogBuffer.slice(-250);
            }
            if (state.log_last_id) {
                terminalLastLogId = state.log_last_id;
            }
            renderTerminalLogs();
        }
    } catch (e) {
        // Silently catch poll errors
    }
}

let scaleStartupEnabled = false;

function updateScaleStartupUI(enabled) {
    scaleStartupEnabled = (enabled !== false);
    const badge = document.getElementById('scaleStartupBadge');
    const btn = document.getElementById('toggleScaleStartupBtn');
    if (badge) {
        if (scaleStartupEnabled) {
            badge.className = 'badge badge-success';
            badge.innerHTML = '🟢 AKTIF (Auto-Connect)';
        } else {
            badge.className = 'badge badge-warning';
            badge.innerHTML = '⚪ NONAKTIF (Port Bebas untuk JS)';
        }
    }
    if (btn) {
        if (scaleStartupEnabled) {
            btn.className = 'btn btn-secondary';
            btn.innerHTML = '⚪ Matikan di Startup';
            btn.title = 'Bebaskan port COM agar bisa dipakai browser JS langsung (Web Serial)';
        } else {
            btn.className = 'btn btn-success';
            btn.innerHTML = '🟢 Aktifkan di Startup';
            btn.title = 'Sambungkan otomatis ke timbangan setiap kali bridge berjalan';
        }
    }
    const select = document.getElementById('cfgScaleStartup');
    if (select) {
        select.value = scaleStartupEnabled ? 'true' : 'false';
    }
}

async function toggleScaleStartup() {
    const targetState = !scaleStartupEnabled;
    const confirmMsg = targetState
        ? 'Aktifkan koneksi timbangan di startup?\n\nBridge akan otomatis membuka port serial timbangan saat aplikasi berjalan.'
        : 'Matikan koneksi timbangan di startup?\n\nPort serial COM akan langsung dilepas dan dibebaskan untuk browser/aplikasi JavaScript lain (Web Serial API).';

    if (!confirm(confirmMsg)) return;

    addLog(`Mengubah setelan startup timbangan ke: ${targetState ? 'AKTIF' : 'NONAKTIF'}...`);
    try {
        const res = await fetch('/api/scale/startup-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable_scale_at_startup: targetState })
        });
        const json = await res.json();
        if (json.status === 'success') {
            updateScaleStartupUI(targetState);
            addLog(`✅ Setelan startup timbangan berhasil diubah: ${targetState ? 'AKTIF' : 'NONAKTIF (Port Bebas untuk JS)'}`, 'success');
            await loadScales();
        } else {
            addLog(`❌ Gagal mengubah setelan: ${json.detail || json.message}`, 'error');
        }
    } catch (e) {
        addLog(`❌ Error mengubah startup timbangan: ${e.message}`, 'error');
    }
}

function updateScaleTable(scales) {
    const tbody = document.getElementById('scaleTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    scales.forEach(s => {
        const tr = document.createElement('tr');
        const isFreeForJs = !s.connected && (s.status_detail && (s.status_detail.includes('Startup nonaktif') || s.status_detail.includes('port bebas')));
        const connBadge = s.connected
            ? '<span class="badge badge-success">🟢 Terhubung</span>'
            : (isFreeForJs
                ? '<span class="badge badge-warning" title="Port COM bebas untuk Web Serial JS browser">⚪ Bebas untuk JS</span>'
                : '<span class="badge badge-danger">🔴 Terputus</span>');

        tr.innerHTML = `
            <td><b>${s.name}</b></td>
            <td><code>${s.port}</code></td>
            <td>${s.protocol.toUpperCase()}</td>
            <td><span class="badge ${s.state === 'online' ? 'badge-success' : (s.state === 'standby' || s.state === 'paused' ? 'badge-warning' : 'badge-secondary')}">${s.state}</span></td>
            <td>${connBadge}</td>
            <td><b>${s.weight !== null ? s.weight : '--.--'} ${s.unit}</b> ${s.stable ? '✓' : '~'}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function loadScales() {
    try {
        const res = await fetch('/api/scales');
        const json = await res.json();
        if (json.enable_scale_at_startup !== undefined) {
            updateScaleStartupUI(json.enable_scale_at_startup);
        }
        const scales = json.scales || [];
        if (scales.length > 0) {
            const active = scales.find(s => s.connected && s.port !== 'SIM') || scales.find(s => s.connected) || scales[0];
            updateLcdDisplay(active);
            updateScaleTable(scales);
        }
    } catch (e) {
        console.warn('Gagal memuat timbangan:', e);
    }
}

async function sendZero() {
    addLog('Mengirim perintah ZERO ke timbangan...');
    try {
        const res = await fetch('/api/scale/zero', { method: 'POST' });
        const json = await res.json();
        addLog(json.status === 'success' ? '✅ Zero berhasil' : '❌ Gagal Zero');
    } catch (e) {
        addLog(`❌ Error Zero: ${e.message}`, 'error');
    }
}

async function sendTare() {
    addLog('Mengirim perintah TARE ke timbangan...');
    try {
        const res = await fetch('/api/scale/tare', { method: 'POST' });
        const json = await res.json();
        addLog(json.status === 'success' ? '✅ Tare berhasil' : '❌ Gagal Tare');
    } catch (e) {
        addLog(`❌ Error Tare: ${e.message}`, 'error');
    }
}

async function readStableWeight() {
    addLog('Menunggu pembacaan STABIL dari timbangan (maks 5 detik)...');
    try {
        const res = await fetch('/api/scale/stable-read?timeout=5.0', { method: 'POST' });
        const json = await res.json();
        if (json.status === 'success') {
            addLog(`🔒 BERAT STABIL TERKUNCI: ${json.data.weight} ${json.data.unit} (${json.elapsed_seconds}s)`, 'success');
        } else {
            addLog(`⚠️ Timbangan belum stabil: ${json.message}`, 'warn');
        }
    } catch (e) {
        addLog(`❌ Error stable read: ${e.message}`, 'error');
    }
}

async function pauseScale() {
    addLog('Melepas port serial untuk Delphi / aplikasi lain...');
    try {
        const res = await fetch('/api/scale/pause', { method: 'POST' });
        const json = await res.json();
        addLog('⏸️ Port serial dilepas sementara. Delphi sekarang bisa membuka port COM.');
        loadScales();
    } catch (e) {
        addLog(`❌ Error pause: ${e.message}`, 'error');
    }
}

async function resumeScale() {
    addLog('Menyambungkan kembali port serial...');
    try {
        const res = await fetch('/api/scale/resume', { method: 'POST' });
        const json = await res.json();
        addLog(`▶️ ${json.message || 'Port serial disambungkan kembali.'}`, 'success');
        await loadScales();
        setTimeout(loadScales, 400);
        setTimeout(loadScales, 1200);
    } catch (e) {
        addLog(`❌ Error resume: ${e.message}`, 'error');
    }
}

// ────────────────────────────────────────────────────────────
// Serial Ports Controller
// ────────────────────────────────────────────────────────────

async function loadSerialPorts() {
    const tbody = document.getElementById('serialTableBody');
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">Memindai port serial...</td></tr>';
    try {
        const res = await fetch('/api/serial/ports');
        const json = await res.json();
        const ports = json.ports || [];
        tbody.innerHTML = '';
        if (ports.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">Tidak ada port serial fisik terdeteksi.</td></tr>';
            return;
        }
        ports.forEach(p => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><code><b>${p.device}</b></code></td>
                <td>${p.description}</td>
                <td>${p.manufacturer || '-'}</td>
                <td><code>${p.vid && p.pid ? `${p.vid}:${p.pid}` : '-'}</code></td>
            `;
            tbody.appendChild(tr);
        });
        addLog(`Ditemukan ${ports.length} port serial di komputer.`);
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="4" style="color: var(--danger); text-align: center;">Gagal memuat serial ports: ${e.message}</td></tr>`;
    }
}

// ────────────────────────────────────────────────────────────
// Job History Controller
// ────────────────────────────────────────────────────────────

async function loadPrintHistory() {
    const tbody = document.getElementById('historyTableBody');
    try {
        const res = await fetch('/api/print/history');
        const json = await res.json();
        const history = json.history || [];
        tbody.innerHTML = '';
        if (history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">Belum ada riwayat job.</td></tr>';
            return;
        }
        history.slice().reverse().forEach(h => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>#${h.id}</td>
                <td><b>${h.type}</b></td>
                <td>${h.printer}</td>
                <td><small>${h.time}</small></td>
                <td>${h.bytes} B</td>
                <td><span class="badge ${h.success ? 'badge-success' : 'badge-danger'}">${h.success ? 'SUKSES' : 'GAGAL'}</span></td>
                <td><small>${h.message || '-'}</small></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.warn('Gagal memuat history:', e);
    }
}

// ────────────────────────────────────────────────────────────
// Settings & Printer Pool Controller
// ────────────────────────────────────────────────────────────

async function loadSettings() {
    try {
        const res = await fetch('/api/config');
        const cfg = await res.json();
        if (cfg.server) {
            if (document.getElementById('cfgHost')) document.getElementById('cfgHost').value = cfg.server.host || '127.0.0.1';
            if (document.getElementById('cfgPort')) document.getElementById('cfgPort').value = cfg.server.port || 18212;
            if (document.getElementById('cfgSharingMode')) document.getElementById('cfgSharingMode').value = cfg.server.sharing_mode || 'continuous';
            if (document.getElementById('cfgIdleRelease')) document.getElementById('cfgIdleRelease').value = cfg.server.idle_release_seconds || 4.0;
            if (document.getElementById('cfgScaleStartup')) {
                document.getElementById('cfgScaleStartup').value = (cfg.server.enable_scale_at_startup !== false) ? 'true' : 'false';
            }
        }
    } catch (e) {
        console.warn('Gagal memuat config server:', e);
    }
}

async function loadPrinterPools() {
    const tbody = document.getElementById('poolTableBody');
    const newSelect = document.getElementById('newPoolPrinter');
    const defRawSelect = document.getElementById('cfgDefaultRawPrinter');
    const defDocSelect = document.getElementById('cfgDefaultDocPrinter');

    try {
        if (installedPrinters.length === 0) {
            const pRes = await fetch('/api/printers');
            const pData = await pRes.json();
            installedPrinters = pData.printers || [];
        }

        const res = await fetch('/api/printers/pools');
        const data = await res.json();
        activePools = data.pools || {};
        const defRaw = data.default_raw_printer || '';
        const defDoc = data.default_doc_printer || '';

        function fillPrinterOptions(sel, selectedValue) {
            if (!sel) return;
            sel.innerHTML = '';
            installedPrinters.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.name;
                opt.textContent = `${p.is_default ? '⭐ ' : ''}${p.name}`;
                if (p.name === selectedValue) opt.selected = true;
                sel.appendChild(opt);
            });
            if (selectedValue && !installedPrinters.some(p => p.name === selectedValue)) {
                const opt = document.createElement('option');
                opt.value = selectedValue;
                opt.textContent = `⚠️ ${selectedValue} (Custom/Network)`;
                opt.selected = true;
                sel.appendChild(opt);
            }
        }

        fillPrinterOptions(newSelect, installedPrinters[0]?.name || '');
        fillPrinterOptions(defRawSelect, defRaw);
        fillPrinterOptions(defDocSelect, defDoc);

        renderPoolTable();
    } catch (e) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="3" style="color: var(--danger); text-align: center;">Gagal memuat printer pools: ${e.message}</td></tr>`;
    }
}

function renderPoolTable() {
    const tbody = document.getElementById('poolTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const keys = Object.keys(activePools);
    if (keys.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">Belum ada alias pool yang terdaftar. Tambahkan mapping di bawah.</td></tr>';
        return;
    }

    keys.forEach(key => {
        const tr = document.createElement('tr');
        const currentMapped = activePools[key];

        let selectHtml = `<select class="pool-row-select" data-key="${key}" onchange="updatePoolMapping('${key}', this.value)" style="width: 100%;">`;
        installedPrinters.forEach(p => {
            const isSel = p.name === currentMapped ? 'selected' : '';
            selectHtml += `<option value="${p.name}" ${isSel}>${p.is_default ? '⭐ ' : ''}${p.name}</option>`;
        });
        if (currentMapped && !installedPrinters.some(p => p.name === currentMapped)) {
            selectHtml += `<option value="${currentMapped}" selected>⚠️ ${currentMapped} (Custom/Network)</option>`;
        }
        selectHtml += `</select>`;

        tr.innerHTML = `
            <td>
                <span class="badge badge-primary" style="font-size: 0.95rem;">🎯 <b>${key}</b></span>
            </td>
            <td>${selectHtml}</td>
            <td style="text-align: center;">
                <button class="btn btn-danger" style="padding: 0.25rem 0.6rem; font-size: 0.8rem;" onclick="deletePoolMapping('${key}')">🗑️ Hapus</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function updatePoolMapping(key, val) {
    activePools[key] = val;
}

function addPoolMapping() {
    const keyInput = document.getElementById('newPoolKey');
    const printerSelect = document.getElementById('newPoolPrinter');
    const rawKey = keyInput.value.trim().toLowerCase().replace(/[^a-z0-9_\-]/g, '_');
    const printer = printerSelect.value;

    if (!rawKey) {
        alert('Nama Label / Target Pool tidak boleh kosong!');
        keyInput.focus();
        return;
    }

    activePools[rawKey] = printer;
    keyInput.value = '';
    renderPoolTable();
    addLog(`Menambahkan mapping pool: ${rawKey} ➔ ${printer}. Klik "Simpan Konfigurasi" untuk menyimpan.`, 'info');
}

function deletePoolMapping(key) {
    if (confirm(`Hapus pemetaan pool "${key}"?`)) {
        delete activePools[key];
        renderPoolTable();
        addLog(`Menghapus mapping pool: ${key}. Klik "Simpan Konfigurasi" untuk menyimpan.`, 'warning');
    }
}

async function savePrinterPools() {
    const defRaw = document.getElementById('cfgDefaultRawPrinter')?.value || '';
    const defDoc = document.getElementById('cfgDefaultDocPrinter')?.value || '';

    document.querySelectorAll('.pool-row-select').forEach(sel => {
        const key = sel.getAttribute('data-key');
        if (key) activePools[key] = sel.value;
    });

    try {
        const res = await fetch('/api/printers/pools', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pools: activePools,
                default_raw_printer: defRaw,
                default_doc_printer: defDoc
            })
        });
        const json = await res.json();
        if (json.status === 'success') {
            alert('✅ Konfigurasi Printer Pool & Default Printer berhasil disimpan!');
            addLog('✅ Pemetaan Printer Pool berhasil disimpan ke konfigurasi sistem.', 'success');
            loadPrinters();
            loadPrinterPools();
            loadSystemStatus();
        } else {
            alert('❌ Gagal menyimpan printer pools: ' + (json.detail || json.message));
        }
    } catch (e) {
        alert('❌ Error simpan pool: ' + e.message);
    }
}

async function saveSettings() {
    const host = document.getElementById('cfgHost').value;
    const port = parseInt(document.getElementById('cfgPort').value, 10);
    const mode = document.getElementById('cfgSharingMode').value;
    const idle = parseFloat(document.getElementById('cfgIdleRelease').value);
    const scaleStartup = document.getElementById('cfgScaleStartup') ? (document.getElementById('cfgScaleStartup').value === 'true') : false;

    try {
        const getRes = await fetch('/api/config');
        const cfg = await getRes.json();
        cfg.server.host = host;
        cfg.server.port = port;
        cfg.server.sharing_mode = mode;
        cfg.server.idle_release_seconds = idle;
        cfg.server.enable_scale_at_startup = scaleStartup;

        const postRes = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cfg)
        });
        const res = await postRes.json();
        if (res.status === 'success') {
            updateScaleStartupUI(scaleStartup);
            alert('Konfigurasi berhasil disimpan! Silakan restart bridge jika mengubah host atau port.');
            addLog('Konfigurasi berhasil disimpan.', 'success');
            loadScales();
        } else {
            alert('Gagal menyimpan konfigurasi.');
        }
    } catch (e) {
        alert('Error menyimpan: ' + e.message);
    }
}

// ────────────────────────────────────────────────────────────
// Documentation & SDK Helpers
// ────────────────────────────────────────────────────────────

function copyCodeSnippet(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const text = el.innerText;
    navigator.clipboard.writeText(text).then(() => {
        addLog(`📋 Kode dari #${elementId} berhasil disalin ke clipboard!`, 'success');
        alert('Kode berhasil disalin ke clipboard!');
    }).catch(err => {
        console.error('Gagal copy:', err);
    });
}

function copySdkUrl() {
    const url = `${window.location.origin}/static/js/hardware-bridge.js`;
    navigator.clipboard.writeText(url).then(() => {
        addLog(`📋 URL SDK berhasil disalin: ${url}`, 'success');
        alert(`URL SDK berhasil disalin:\n${url}\n\nTempelkan di <script src="${url}"></script> pada aplikasi web Anda.`);
    }).catch(err => {
        console.error('Gagal copy:', err);
    });
}
