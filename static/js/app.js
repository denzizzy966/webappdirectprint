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
    if (tabId === 'scales') { loadScales(); loadControlPorts(); pollScaleTerminal(); renderTerminalLogs(); }
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
            const active = getActiveConsoleScale(scales);
            if (active) updateLcdDisplay(active);
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
                    const active = getActiveConsoleScale(data.scales);
                    if (active) updateLcdDisplay(active);
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
    initSandboxDirectPrint();
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

// ────────────────────────────────────────────────────────────
// Sandbox & Direct Print Testing Controller
// ────────────────────────────────────────────────────────────

const SAMPLE_BASE64_PDF = `JVBERi0xLjcKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZwovT3V0bGluZXMgMiAwIFIKL1BhZ2VzIDMgMCBSID4+CmVuZG9iagoyIDAgb2JqCjw8IC9UeXBlIC9PdXRsaW5lcyAvQ291bnQgMCA+PgplbmRvYmoKMyAwIG9iago8PCAvVHlwZSAvUGFnZXMKL0tpZHMgWzYgMCBSCl0KL0NvdW50IDEKL1Jlc291cmNlcyA8PAovUHJvY1NldCA0IDAgUgovRm9udCA8PCAKL0YxIDggMCBSCi9GMiA5IDAgUgovRjMgMTAgMCBSCj4+Ci9YT2JqZWN0IDw8IAovSTEgMTEgMCBSCi9JMiAxMiAwIFIKPj4KPj4KL01lZGlhQm94IFswLjAwMCAwLjAwMCAxNzAuMDc5IDcwLjg2Nl0KID4+CmVuZG9iago0IDAgb2JqClsvUERGIC9UZXh0IC9JbWFnZUMgXQplbmRvYmoKNSAwIG9iago8PAovUHJvZHVjZXIgKP7/AGQAbwBtAHAAZABmACAAMgAuADAALgAzACAAKwAgAEMAUABEAEYpCi9DcmVhdGlvbkRhdGUgKEQ6MjAyNjA5MTgxNTQ1MTUrMDcnMDAnKQovTW9kRGF0ZSAoRDoyMDI2MDkxODE1NDUxNSswNycwMCcpCi9UaXRsZSAo/v8AQwBlAHQAYQBrKQo+PgplbmRvYmoKNiAwIG9iago8PCAvVHlwZSAvUGFnZQovTWVkaWFCb3ggWzAuMDAwIDAuMDAwIDE3MC4wNzkgNzAuODY2XQovUGFyZW50IDMgMCBSCi9Db250ZW50cyA3IDAgUgo+PgplbmRvYmoKNyAwIG9iago8PCAvRmlsdGVyIC9GbGF0ZURlY29kZQovTGVuZ3RoIDE3NSA+PgpzdHJlYW0KeJxtjj8LwkAMxff7FG/UoenlrrleVlGLfxCEgw7ipOgkot9/8FpbdTCBl0Dye4mxZK3Frz6vZpZQRwqVhyhFG5HOKJcOkRzSBThMwmZ6RFpjkczDsAx8To59G0lZ4DOgHqcbypXD/G72nbXUVFmG6zbd29pDyQ7W26bweVJwls+RjFVCaj1YSNiPH32xpkWPYdfiH1o7ZI06HqxJBrKKIYiigHaRq2PlEX8BtyA8NQplbmRzdHJlYW0KZW5kb2JqCjggMCBvYmoKPDwgL1R5cGUgL0ZvbnQKL1N1YnR5cGUgL1R5cGUxCi9OYW1lIC9GMQovQmFzZUZvbnQgL1RpbWVzLVJvbWFuCi9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nCj4+CmVuZG9iago5IDAgb2JqCjw8IC9UeXBlIC9Gb250Ci9TdWJ0eXBlIC9UeXBlMQovTmFtZSAvRjIKL0Jhc2VGb250IC9IZWx2ZXRpY2EtQm9sZAovRW5jb2RpbmcgL1dpbkFuc2lFbmNvZGluZwo+PgplbmRvYmoKMTAgMCBvYmoKPDwgL1R5cGUgL0ZvbnQKL1N1YnR5cGUgL1R5cGUxCi9OYW1lIC9GMwovQmFzZUZvbnQgL0hlbHZldGljYQovRW5jb2RpbmcgL1dpbkFuc2lFbmNvZGluZwo+PgplbmRvYmoKMTEgMCBvYmoKPDwKL1R5cGUgL1hPYmplY3QKL1N1YnR5cGUgL0ltYWdlCi9XaWR0aCAyNzEKL0hlaWdodCAyNwovRmlsdGVyIC9GbGF0ZURlY29kZQovRGVjb2RlUGFybXMgPDwgL1ByZWRpY3RvciAxNSAvQ29sb3JzIDEgL0NvbHVtbnMgMjcxIC9CaXRzUGVyQ29tcG9uZW50IDg+PgovQ29sb3JTcGFjZSAvRGV2aWNlR3JheQovQml0c1BlckNvbXBvbmVudCA4Ci9MZW5ndGggNzY+PgpzdHJlYW0KWIXt0EERACAMwLD5Nw3fVQE8EgW9zmGb1wGf8aP8KD/Kj/Kj/Cg/yo/yo/woP8qP8qP8KD/Kj/Kj/Cg/yo/yo/woP8qP8qMuSnF6EAplbmRzdHJlYW0KZW5kb2JqCjEyIDAgb2JqCjw8Ci9UeXBlIC9YT2JqZWN0Ci9TdWJ0eXBlIC9JbWFnZQovV2lkdGggMjcxCi9IZWlnaHQgMjcKL1NNYXNrIDExIDAgUgovRmlsdGVyIC9GbGF0ZURlY29kZQovRGVjb2RlUGFybXMgPDwgL1ByZWRpY3RvciAxNSAvQ29sb3JzIDEgL0NvbHVtbnMgMjcxIC9CaXRzUGVyQ29tcG9uZW50IDg+PgovQ29sb3JTcGFjZSAgWyAvSW5kZXhlZCAvRGV2aWNlUkdCIDI0IDEzIDAgUiBdCi9CaXRzUGVyQ29tcG9uZW50IDgKL0xlbmd0aCA4ODA+PgpzdHJlYW0KWIW9mIt2oyAQhhlTcROlROy2+/5PulwFZLgZG04PxWEYyJd/AEOILiD/htsHGQf5MIygbLpNx2EYyXCztTGGtTJOg6pNWw23/t6BuAja+EfHUe0p6HJjSTCjjXAfvN1EmPSjWw8SwU4BykE9ftgZ3Xr8cBltJFh53B5kfKiG6ZdtULV8lF2Pke4OYW2MqjZtPVz7Bw7EWozRDgkczBA7tZ8xcrB217BxZuWwpBHUFMxGCGeUDp/KjTvjbo8LUIwH2Ve32AnfxuOZ4bHGPJIIIp3CPYqR7OshFR64Pkj0bcmanuZxlxY4rQ+W00cUQVByRE5TfdR5cEI9DyjxMPrs5MH8kmev8zoP7czL+ZKLECDnKQ+zD3z264MfeayL7aKv5ct6wf4hUh4US0lMH9CeL1DSB5YvFOcBMQ/hPo24cj9t0AfCgx/yBZSlRR9NPHL64J37Kbefhnkec8hD2RecB4t4zAUetHU/5bIfMB4C58FTHqKeL7y0n9KjPqBfH/p8War5UucR6gMu0ceRx9R7/4DAAXryxaYku4pHIV/YeR6t9w+fLzxIh5THIk+uc/vHkQdFeTzxfOnQx3PZeYgKD3XBk6dMUR+RQ8Rjre2nT3cBQ3nQjD4iLpfvp2TyRpbqYzp9vggzVscRPfqA/nzhNR68ncdc0EeaLyzi8ZnwmLP7R/n9BbmPkdb72LoU9CF69fGG97kL9o+lZT/l+XzhJ3hAhkdG7fqRxQ55HhBFmJIr34HHHckXbEN14anTB8N5NOsjvI8tCA/6Bn3wvD6Ww/4BJX1g+dLEg6b6WI758jSr0Dc6/TvDY+UIj7XCA3l/OXne1vMl4gEdPPr2DzRfxAX6uLtEqPGgO4/oFYbX9eF/H+O2i73Mw3XNzfkyX76ftugDMvkCmD6gkceqI//6+XJ8RYILeKjd5bX7mH134J4HC99fJudwlgfdBU/Mj2/h+XKJPravjWybamzmeTO1/L/91bVzMDXfNu5Gqdq0dadsKJctMH59/0j7P2KdN+PwbRxscCBmVBpht/+4xh7HBLcRSDrFFj269fjhzk7QH0EOJfUojbEnFvp21FAgPfPyq0w966W2sOaYNtBxZa3jzwL6rWilCC3RadJ4qdRl2RRBL+aMTPZy7feUK11Z0/h5WtywXGsOTtWfbPwHSDxzZwplbmRzdHJlYW0KZW5kb2JqCjEzIDAgb2JqCjw8IC9GaWx0ZXIgL0ZsYXRlRGVjb2RlCi9MZW5ndGggNjUgPj4Kc3RyZWFtCnicDYoBDQAxDAKZjc5LcTYcdiZWG98nJOS4MDPfTESQ3BGSvKUT2yYBHAlYTpL+MqmjBXR3Vd2qfsbn+gH7qiVRCmVuZHN0cmVhbQplbmRvYmoKeHJlZgowIDE0CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAwOSAwMDAwMCBuIAowMDAwMDAwMDc0IDAwMDAwIG4gCjAwMDAwMDAxMjAgMDAwMDAgbiAKMDAwMDAwMDMzMiAwMDAwMCBuIAowMDAwMDAwMzY5IDAwMDAwIG4gCjAwMDAwMDA1NDAgMDAwMDAgbiAKMDAwMDAwMDY0MiAwMDAwMCBuIAowMDAwMDAwODg5IDAwMDAwIG4gCjAwMDAwMDA5OTggMDAwMDAgbiAKMDAwMDAwMTExMCAwMDAwMCBuIAowMDAwMDAxMjE4IDAwMDAwIG4gCjAwMDAwMDE1MzcgMDAwMDAgbiAKMDAwMDAwMjY5OCAwMDAwMCBuIAp0cmFpbGVyCjw8Ci9TaXplIDE0Ci9Sb290IDEgMCBSCi9JbmZvIDUgMCBSCi9JRFs8ZGFiNzcxMTYzMmQ5NTc0NDlhMDUyNTI3N2FmOGY3Nzg+PGRhYjc3MTE2MzJkOTU3NDQ5YTA1MjUyNzdhZjhmNzc4Pl0KPj4Kc3RhcnR4cmVmCjI4MzUKJSVFT0YK`.trim();

function switchSandboxTab(tabName) {
    document.querySelectorAll('.subtab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.sandbox-panel').forEach(p => p.style.display = 'none');

    const targetBtn = document.getElementById(`btnSubtab${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`);
    if (targetBtn) targetBtn.classList.add('active');

    const targetPanel = document.getElementById(`panel-${tabName}`);
    if (targetPanel) targetPanel.style.display = 'block';
}

function initSandboxDirectPrint() {
    loadDefaultBase64Sample();
}

function loadDefaultBase64Sample() {
    const input = document.getElementById('sandboxBase64Input');
    if (input) {
        input.value = SAMPLE_BASE64_PDF;
        updateSandboxBase64Preview();
    }
}

function updateSandboxBase64Preview() {
    const frame = document.getElementById('sandboxBase64PreviewFrame');
    const input = document.getElementById('sandboxBase64Input');
    if (!frame || !input) return;

    let b64 = input.value.trim();
    if (!b64) {
        frame.src = 'about:blank';
        return;
    }

    if (b64.includes(';base64,')) {
        b64 = b64.split(';base64,')[1];
    } else if (b64.startsWith('base64:')) {
        b64 = b64.substring(7);
    }
    b64 = b64.replace(/\s+/g, '');
    frame.src = `data:application/pdf;base64,${b64}`;
}

async function testPrintBase64Pdf() {
    const printer = document.getElementById('targetPrinterSelect').value;
    const b64 = document.getElementById('sandboxBase64Input').value.trim();
    const dpi = parseInt(document.getElementById('sandboxBase64Dpi').value, 10) || 203;
    const orientation = document.getElementById('sandboxBase64Orientation').value || 'auto';
    const fit = document.getElementById('sandboxBase64Fit').value || 'fit_page';

    if (!b64) {
        alert('Data string Base64 PDF tidak boleh kosong!');
        return;
    }

    addLog(`🖨️ Mengirim Base64 PDF (${b64.length} karakter) ke printer: ${printer} (DPI: ${dpi}, Fit: ${fit})...`);
    try {
        const res = await fetch('/api/print/pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                printer: printer,
                pdf_data: b64,
                dpi: dpi,
                orientation: orientation,
                fit: fit,
                doc_name: 'Test_Label_Base64'
            })
        });
        const json = await res.json();
        if (json.status === 'success') {
            addLog(`✅ Cetak Base64 PDF Berhasil! Spooled ke "${json.result.printer}" (${json.result.bytes_sent || 'OK'} bytes)`, 'success');
        } else {
            addLog(`❌ Cetak Base64 PDF Gagal: ${json.detail || json.message || JSON.stringify(json)}`, 'error');
        }
        loadPrintHistory();
    } catch (e) {
        addLog(`❌ Error cetak Base64 PDF: ${e.message}`, 'error');
    }
}

async function testPrintBase64PdfSDK() {
    if (!bridge) {
        alert('HardwareBridge SDK belum siap!');
        return;
    }
    const printer = document.getElementById('targetPrinterSelect').value;
    const b64 = document.getElementById('sandboxBase64Input').value.trim();
    const dpi = parseInt(document.getElementById('sandboxBase64Dpi').value, 10) || 203;
    const orientation = document.getElementById('sandboxBase64Orientation').value || 'auto';
    const fit = document.getElementById('sandboxBase64Fit').value || 'fit_page';

    if (!b64) {
        alert('Data string Base64 PDF tidak boleh kosong!');
        return;
    }

    addLog(`⚡ Mengirim Base64 PDF via HardwareBridge JS SDK ke: ${printer}...`);
    try {
        const res = await bridge.printPdf({
            printer: printer,
            pdf_data: b64,
            dpi: dpi,
            orientation: orientation,
            fit: fit,
            doc_name: 'Test_SDK_Label'
        });
        if (res.success || res.status === 'success') {
            addLog(`✅ [SDK] Cetak Base64 Berhasil! Printer: ${res.printer || printer}`, 'success');
        } else {
            addLog(`❌ [SDK] Cetak Base64 Gagal: ${res.error || res.message}`, 'error');
        }
        loadPrintHistory();
    } catch (e) {
        addLog(`❌ [SDK] Error: ${e.message}`, 'error');
    }
}

function updateSandboxUrlPreview() {
    const url = document.getElementById('sandboxPdfUrlInput').value.trim();
    const frame = document.getElementById('sandboxUrlPreviewFrame');
    if (frame && url) {
        frame.src = url;
    }
}

function loadSampleInvoiceToSandbox() {
    const input = document.getElementById('sandboxPdfUrlInput');
    if (input) {
        input.value = '/static/sample_invoice.pdf';
        updateSandboxUrlPreview();
    }
}

function handleSandboxFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    addLog(`📁 Membaca berkas lokal: ${file.name} (${Math.round(file.size / 1024)} KB)...`);
    const reader = new FileReader();
    reader.onload = function(e) {
        const dataUrl = e.target.result;
        const b64 = dataUrl.split(',')[1];
        
        // Pindahkan ke editor Base64 dan switch tab
        const b64Input = document.getElementById('sandboxBase64Input');
        if (b64Input) {
            b64Input.value = b64;
            updateSandboxBase64Preview();
        }
        switchSandboxTab('base64');
        addLog(`✅ Berkas ${file.name} berhasil dimuat ke tab Base64 PDF. Siap dicetak!`, 'success');
    };
    reader.readAsDataURL(file);
}

async function testPrintFilePdf() {
    const printer = document.getElementById('targetPrinterSelect').value;
    const url = document.getElementById('sandboxPdfUrlInput').value.trim();
    const dpi = parseInt(document.getElementById('sandboxFileDpi').value, 10) || 203;
    const fit = document.getElementById('sandboxFileFit').value || 'fit_page';

    if (!url) {
        alert('URL berkas PDF tidak boleh kosong!');
        return;
    }

    let fullUrl = url;
    if (url.startsWith('/')) {
        fullUrl = window.location.origin + url;
    }

    addLog(`🖨️ Mengirim berkas PDF (${fullUrl}) ke printer: ${printer}...`);
    try {
        const res = await fetch('/api/print/pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                printer: printer,
                pdf_data: fullUrl,
                dpi: dpi,
                fit: fit,
                doc_name: 'Test_Invoice_Doc'
            })
        });
        const json = await res.json();
        if (json.status === 'success') {
            addLog(`✅ Cetak PDF Dokumen Berhasil! Spooled ke "${json.result.printer}"`, 'success');
        } else {
            addLog(`❌ Cetak PDF Gagal: ${json.detail || json.message}`, 'error');
        }
        loadPrintHistory();
    } catch (e) {
        addLog(`❌ Error cetak berkas PDF: ${e.message}`, 'error');
    }
}

function loadRawTemplate(type) {
    const input = document.getElementById('customRawInput');
    if (!input) return;

    if (type === 'zpl') {
        input.value = `^XA\n^FO50,50^ADN,36,20^FDHARDWARE BRIDGE UNIVERSAL^FS\n^FO50,100^BY3\n^BCN,100,Y,N,N\n^FD1234567890^FS\n^FO50,230^ADN,18,10^FDTanggal: 19/09/2026 - Godex / Zebra OK^FS\n^XZ`;
    } else if (type === 'tspl') {
        input.value = `SIZE 60 mm, 25 mm\nGAP 2 mm, 0 mm\nDIRECTION 1\nCLS\nTEXT 50,30,"3",0,1,1,"PRODUK PILIHAN"\nBARCODE 50,70,"128",60,1,0,2,2,"PRD-998877"\nPRINT 1\n`;
    } else if (type === 'escpos') {
        input.value = `\x1b\x40\x1b\x61\x01\x1d\x21\x11TOKO REJEKI JAYA\n\x1d\x21\x00Jl. Pahlawan No. 123\n--------------------------------\n1x Kopi Latte          25.000\n1x Roti Bakar          18.000\n--------------------------------\nTOTAL:                 43.000\n\x1b\x61\x01Terima Kasih!\n\n\n\x1d\x56\x42\x00`;
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
    const sel = document.getElementById('targetPrinterSelect');
    if (sel) sel.value = printerName;
    const sandbox = document.getElementById('sandboxCard');
    if (sandbox) sandbox.scrollIntoView({ behavior: 'smooth' });
    addLog(`🎯 Target pengujian diarahkan ke printer: ${printerName}`);
}

// ────────────────────────────────────────────────────────────
// Scale Controller & Interactive Testing Console
// ────────────────────────────────────────────────────────────

let terminalLastLogId = 0;
let terminalLogBuffer = [];
let isScalePaused = false;
let currentSelectedScalePort = null;
let lastKnownScales = [];

function getActiveConsoleScale(scales) {
    if (!scales || scales.length === 0) return null;
    lastKnownScales = scales;

    // 1. Cek port yang sedang dipilih pengguna
    if (currentSelectedScalePort) {
        const match = scales.find(s =>
            (s.port && s.port.toLowerCase() === currentSelectedScalePort.toLowerCase()) ||
            (s.name && s.name.toLowerCase() === currentSelectedScalePort.toLowerCase())
        );
        if (match) return match;
    }

    // 2. Cek nilai pada dropdown #ctrlPort
    const selPort = document.getElementById('ctrlPort')?.value;
    if (selPort) {
        const match = scales.find(s =>
            (s.port && s.port.toLowerCase() === selPort.toLowerCase()) ||
            (s.name && s.name.toLowerCase() === selPort.toLowerCase())
        );
        if (match) {
            currentSelectedScalePort = match.port || selPort;
            return match;
        }
    }

    // 3. Fallback: timbangan fisik pertama yang terhubung, atau simulator, atau elemen pertama
    const active = scales.find(s => s.connected && s.port !== 'SIM') ||
                   scales.find(s => s.connected) ||
                   scales[0];
    if (active) {
        currentSelectedScalePort = active.port;
        const ctrlPortEl = document.getElementById('ctrlPort');
        if (ctrlPortEl && ctrlPortEl.value !== active.port) {
            for (let opt of ctrlPortEl.options) {
                if (opt.value.toLowerCase() === active.port.toLowerCase()) {
                    ctrlPortEl.value = opt.value;
                    break;
                }
            }
        }
    }
    return active;
}

function updateLcdDisplay(scaleData) {
    if (!scaleData) return;

    const weightVal = document.getElementById('lcdWeightVal');
    const unitVal = document.getElementById('lcdUnitVal');
    const connBadge = document.getElementById('conn-badge');
    const stableBadge = document.getElementById('stable-badge');
    const ageBadge = document.getElementById('age-badge');
    const detailStatus = document.getElementById('scaleDetailStatus');
    const statWeight = document.getElementById('statWeight');
    const lcdScaleTitle = document.getElementById('lcdScaleTitle');

    // Connection bar status
    const ctrlStatusDot = document.getElementById('ctrlStatusDot');
    const ctrlStatusText = document.getElementById('ctrlStatusText');
    const ctrlSubStatusText = document.getElementById('ctrlSubStatusText');

    const isConnected = !!scaleData.connected;
    const w = (scaleData.weight !== null && scaleData.weight !== undefined) ? Number(scaleData.weight).toFixed(2) : '--.--';
    const u = scaleData.unit || 'g';

    if (lcdScaleTitle) {
        lcdScaleTitle.textContent = `🎯 ${scaleData.name || 'Timbangan'} [${scaleData.port || ''}]`;
    }

    if (weightVal) weightVal.textContent = isConnected ? w : '--.--';
    if (unitVal) unitVal.textContent = u;
    if (statWeight) statWeight.textContent = isConnected ? `${w} ${u}` : '0.00 g';

    if (ctrlStatusDot) {
        ctrlStatusDot.textContent = isConnected ? '🟢' : (scaleData.state === 'paused' || scaleData.state === 'standby' ? '🟡' : '🔴');
    }
    if (ctrlStatusText) {
        ctrlStatusText.textContent = `${scaleData.name || 'Timbangan'} [${scaleData.port || ''}] — ${isConnected ? 'Terhubung' : 'Terputus'}`;
    }
    if (ctrlSubStatusText) {
        ctrlSubStatusText.textContent = isConnected
            ? `Protokol: ${(scaleData.protocol || 'auto').toUpperCase()} • Baud: ${scaleData.baud || 9600} • Data: ${scaleData.databits || 8}${scaleData.parity || 'N'}1`
            : 'Pilih port atau klik baris pada tabel di bawah untuk beralih timbangan';
    }

    if (connBadge) {
        if (isConnected) {
            connBadge.className = 'badge badge-success';
            connBadge.textContent = '🟢 Terhubung';
        } else if (scaleData.state === 'paused' || scaleData.state === 'standby') {
            connBadge.className = 'badge badge-warning';
            connBadge.textContent = '🟡 Dilepas';
        } else {
            connBadge.className = 'badge badge-danger';
            connBadge.textContent = '🔴 Terputus';
        }
    }

    if (stableBadge) {
        if (isConnected) {
            stableBadge.style.display = 'inline-block';
            if (scaleData.stable) {
                stableBadge.className = 'badge badge-success';
                stableBadge.textContent = '🔒 Stabil';
            } else {
                stableBadge.className = 'badge badge-warning';
                stableBadge.textContent = '⚡ Dinamis';
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
        detailStatus.textContent = scaleData.status_detail || (isConnected ? `${scaleData.name || 'Timbangan'} aktif di ${scaleData.port}` : 'Timbangan tidak terhubung');
    }
}

async function loadControlPorts() {
    const sel = document.getElementById('ctrlPort');
    if (!sel) return;
    try {
        const [resPorts, resScales] = await Promise.all([
            fetch('/api/ports').then(r => r.json()).catch(() => []),
            fetch('/api/scales').then(r => r.json()).catch(() => ({ scales: [] }))
        ]);
        const ports = Array.isArray(resPorts) ? resPorts : (resPorts.ports || []);
        const scales = resScales.scales || [];
        lastKnownScales = scales;

        const prevVal = currentSelectedScalePort || sel.value;
        sel.innerHTML = '';

        const addedPorts = new Set();

        // 1. Timbangan yang terdaftar di konfigurasi bridge
        scales.forEach(sc => {
            if (sc.port && !addedPorts.has(sc.port.toUpperCase())) {
                addedPorts.add(sc.port.toUpperCase());
                const opt = document.createElement('option');
                opt.value = sc.port;
                const statusDot = sc.connected ? '🟢' : '🔴';
                opt.textContent = `${sc.port}: ${sc.name} (${statusDot} ${sc.connected ? 'Terhubung' : 'Terputus'})`;
                sel.appendChild(opt);
            }
        });

        // 2. Deteksi port fisik yang terpasang di sistem
        ports.forEach(p => {
            const dev = p.device;
            if (dev && !addedPorts.has(dev.toUpperCase())) {
                addedPorts.add(dev.toUpperCase());
                const opt = document.createElement('option');
                opt.value = dev;
                const statusDot = p.connected ? '🟢' : '⚪';
                opt.textContent = `${dev}: ${p.description || 'Serial Device'} (${statusDot} ${p.connected ? 'Terhubung' : 'Bebas'})`;
                sel.appendChild(opt);
            }
        });

        // 3. Mode simulator jika belum ada di list
        if (!addedPorts.has('SIM')) {
            const simOpt = document.createElement('option');
            simOpt.value = 'SIM';
            simOpt.textContent = 'SIM: Simulator Mode (Virtual)';
            sel.appendChild(simOpt);
        }

        // Pulihkan pilihan sebelumnya
        let matched = false;
        if (prevVal) {
            for (let opt of sel.options) {
                if (opt.value.toLowerCase() === prevVal.toLowerCase()) {
                    opt.selected = true;
                    currentSelectedScalePort = opt.value;
                    matched = true;
                    break;
                }
            }
        }
        if (!matched && sel.options.length > 0) {
            sel.options[0].selected = true;
            currentSelectedScalePort = sel.options[0].value;
        }
    } catch (e) {
        console.warn('Gagal memuat ports control:', e);
    }
}

function onSelectedPortChange() {
    const sel = document.getElementById('ctrlPort');
    if (!sel) return;
    const newPort = sel.value;
    currentSelectedScalePort = newPort;

    // Reset log terminal untuk port baru
    terminalLastLogId = 0;
    terminalLogBuffer = [];
    clearTerminalLogs();

    // Sinkronkan preset protokol dan baud jika port dikenali di tabel timbangan
    if (lastKnownScales && lastKnownScales.length > 0) {
        const matched = lastKnownScales.find(s => s.port && s.port.toLowerCase() === newPort.toLowerCase());
        if (matched) {
            if (matched.protocol) {
                const protoSel = document.getElementById('ctrlProtocol');
                if (protoSel) {
                    protoSel.value = matched.protocol.toLowerCase();
                    onProtocolPresetChange();
                }
            }
            if (matched.baud) {
                const baudSel = document.getElementById('ctrlBaud');
                if (baudSel) baudSel.value = String(matched.baud);
            }
            updateLcdDisplay(matched);
        }
        updateScaleTable(lastKnownScales);
    }

    // Segera polling state untuk port terpilih
    pollScaleTerminal();
}

function selectScalePort(port) {
    if (!port) return;
    currentSelectedScalePort = port;
    const sel = document.getElementById('ctrlPort');
    if (sel) {
        let found = false;
        for (let opt of sel.options) {
            if (opt.value.toLowerCase() === port.toLowerCase()) {
                sel.value = opt.value;
                found = true;
                break;
            }
        }
        if (!found) {
            const newOpt = document.createElement('option');
            newOpt.value = port;
            newOpt.textContent = port;
            newOpt.selected = true;
            sel.appendChild(newOpt);
        }
    }
    onSelectedPortChange();

    // Scroll jika konsol berada di luar viewport
    const topBar = document.getElementById('lcdScaleTitle');
    if (topBar) {
        topBar.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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

    if (grpMettler) grpMettler.style.display = (proto === 'mettler' || proto === 'auto') ? 'grid' : 'none';
    if (grpShinko) grpShinko.style.display = (proto === 'shinko') ? 'grid' : 'none';
    if (grpAnd) grpAnd.style.display = (proto === 'and') ? 'grid' : 'none';
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
    const port = currentSelectedScalePort || document.getElementById('ctrlPort')?.value || 'SIM';
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
    renderTerminalLogs();
}

function renderTerminalLogs() {
    const term = document.getElementById('scaleLogTerminal');
    if (!term) return;
    const showHex = document.getElementById('chkShowHex')?.checked || false;
    const autoscroll = document.getElementById('chkAutoscroll')?.checked !== false;

    if (!terminalLogBuffer || terminalLogBuffer.length === 0) {
        term.innerHTML = '<div style="color: #64748b; font-style: italic; display: flex; align-items: center; justify-content: center; height: 100%; min-height: 280px;">/* Menunggu data serial masuk dari port terpilih... */</div>';
        return;
    }

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
    const port = currentSelectedScalePort || document.getElementById('ctrlPort')?.value || 'SIM';
    try {
        const res = await fetch(`/api/scale/state?port=${encodeURIComponent(port)}&since=${terminalLastLogId}`);
        if (!res.ok) return;
        const state = await res.json();

        // Safety check: jika user beralih port lain saat request sedang jalan, abaikan respon lama
        if (currentSelectedScalePort && state.port && 
            state.port.toLowerCase() !== currentSelectedScalePort.toLowerCase() &&
            !(currentSelectedScalePort.toUpperCase() === 'SIM' && state.sim)) {
            return;
        }

        // Update metrics
        const elLines = document.getElementById('st-lines');
        const elBytes = document.getElementById('st-bytes');
        const elRate = document.getElementById('st-rate');
        if (elLines) elLines.textContent = state.rx_lines !== undefined ? state.rx_lines : 0;
        if (elBytes) elBytes.textContent = state.rx_bytes !== undefined ? state.rx_bytes : 0;
        if (elRate) elRate.textContent = state.bytes_per_sec !== undefined ? state.bytes_per_sec : 0;

        // Update Connection Status Bar
        const btnConn = document.getElementById('btnCtrlConnect');
        const btnDisc = document.getElementById('btnCtrlDisconnect');

        if (state.connected) {
            if (btnConn) btnConn.disabled = true;
            if (btnDisc) btnDisc.disabled = false;
        } else {
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
    if (!scales || scales.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Tidak ada timbangan terdaftar</td></tr>';
        return;
    }
    scales.forEach(s => {
        const tr = document.createElement('tr');
        const isActiveConsole = currentSelectedScalePort && (
            (s.port && s.port.toLowerCase() === currentSelectedScalePort.toLowerCase()) ||
            (s.name && s.name.toLowerCase() === currentSelectedScalePort.toLowerCase())
        );

        if (isActiveConsole) {
            tr.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
            tr.style.borderLeft = '4px solid #10b981';
        } else {
            tr.style.borderLeft = '4px solid transparent';
        }
        tr.style.cursor = 'pointer';
        tr.onclick = () => selectScalePort(s.port);

        const isFreeForJs = !s.connected && (s.status_detail && (s.status_detail.includes('Startup nonaktif') || s.status_detail.includes('port bebas')));
        let connBadge = '';
        if (s.connected) {
            connBadge = '<span class="badge badge-success">🟢 Terhubung</span>';
        } else if (s.state === 'paused') {
            connBadge = '<span class="badge badge-warning">⏸️ Dilepas (Bebas)</span>';
        } else if (isFreeForJs) {
            connBadge = '<span class="badge badge-warning" title="Port COM bebas untuk Web Serial JS browser">⚪ Bebas untuk JS</span>';
        } else {
            connBadge = '<span class="badge badge-danger">🔴 Terputus</span>';
        }

        const consoleBadge = isActiveConsole
            ? '<span class="badge badge-success" style="font-weight: 700; font-size: 0.78rem; padding: 4px 8px;">🎯 AKTIF DI KONSOL</span>'
            : `<button class="btn btn-secondary" style="font-size: 0.75rem; padding: 3px 10px;" onclick="event.stopPropagation(); selectScalePort('${s.port}')">Pilih Timbangan</button>`;

        const weightFormatted = (s.weight !== null && s.weight !== undefined) ? Number(s.weight).toFixed(2) : '--.--';
        const weightColor = s.connected ? '#10b981' : '#94a3b8';
        const stabilityIcon = s.connected
            ? (s.stable ? '<span style="color:#10b981; font-weight: bold; margin-left: 4px;" title="Stabil">✓</span>' : '<span style="color:#f59e0b; font-weight: bold; margin-left: 4px;" title="Dinamis">~</span>')
            : '';

        tr.innerHTML = `
            <td>${consoleBadge}</td>
            <td><b>${s.name}</b></td>
            <td><code style="background: rgba(255,255,255,0.06); padding: 3px 7px; border-radius: 4px; font-weight: 600;">${s.port}</code></td>
            <td><span class="badge badge-secondary">${(s.protocol || 'auto').toUpperCase()} • ${s.baud || 9600}</span></td>
            <td>${connBadge}</td>
            <td><b style="font-family: 'Consolas', monospace; font-size: 1.05rem; color: ${weightColor};">${weightFormatted} ${s.unit || 'g'}</b> ${stabilityIcon}</td>
            <td style="text-align: center;">
                <button class="btn btn-primary" style="font-size: 0.75rem; padding: 4px 12px; font-weight: 600;" onclick="event.stopPropagation(); selectScalePort('${s.port}')" title="Kendalikan timbangan ini di konsol atas">🔍 Uji di Konsol</button>
            </td>
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
        lastKnownScales = scales;
        if (scales.length > 0) {
            const active = getActiveConsoleScale(scales);
            if (active) {
                updateLcdDisplay(active);
            }
            updateScaleTable(scales);
        }
    } catch (e) {
        console.warn('Gagal memuat timbangan:', e);
    }
}

async function sendZero() {
    const port = currentSelectedScalePort || document.getElementById('ctrlPort')?.value || 'SIM';
    addLog(`Mengirim perintah ZERO ke timbangan ${port}...`);
    try {
        const res = await fetch(`/api/scale/zero?scale=${encodeURIComponent(port)}`, { method: 'POST' });
        const json = await res.json();
        addLog(json.status === 'success' || json.ok ? `✅ Zero berhasil (${port})` : `❌ Gagal Zero: ${json.message || ''}`);
        await pollScaleTerminal();
    } catch (e) {
        addLog(`❌ Error Zero: ${e.message}`, 'error');
    }
}

async function sendTare() {
    const port = currentSelectedScalePort || document.getElementById('ctrlPort')?.value || 'SIM';
    addLog(`Mengirim perintah TARE ke timbangan ${port}...`);
    try {
        const res = await fetch(`/api/scale/tare?scale=${encodeURIComponent(port)}`, { method: 'POST' });
        const json = await res.json();
        addLog(json.status === 'success' || json.ok ? `✅ Tare berhasil (${port})` : `❌ Gagal Tare: ${json.message || ''}`);
        await pollScaleTerminal();
    } catch (e) {
        addLog(`❌ Error Tare: ${e.message}`, 'error');
    }
}

async function readStableWeight() {
    const port = currentSelectedScalePort || document.getElementById('ctrlPort')?.value || 'SIM';
    addLog(`Menunggu pembacaan STABIL dari timbangan ${port} (maks 5 detik)...`);
    try {
        const res = await fetch(`/api/scale/stable-read?scale=${encodeURIComponent(port)}&timeout=5.0`, { method: 'POST' });
        const json = await res.json();
        if (json.status === 'success' || json.ok) {
            addLog(`🔒 BERAT STABIL TERKUNCI [${port}]: ${json.data.weight} ${json.data.unit} (${json.elapsed_seconds}s)`, 'success');
        } else {
            addLog(`⚠️ Timbangan ${port} belum stabil: ${json.message || json.error}`, 'warn');
        }
    } catch (e) {
        addLog(`❌ Error stable read: ${e.message}`, 'error');
    }
}

async function pauseScale() {
    const port = currentSelectedScalePort || document.getElementById('ctrlPort')?.value || 'SIM';
    addLog(`Melepas port serial (${port}) untuk Delphi / aplikasi lain...`);
    try {
        const res = await fetch(`/api/scale/pause?scale=${encodeURIComponent(port)}`, { method: 'POST' });
        const json = await res.json();
        addLog(`⏸️ Port serial ${port} dilepas sementara. Delphi sekarang bisa membuka port COM.`);
        loadScales();
    } catch (e) {
        addLog(`❌ Error pause: ${e.message}`, 'error');
    }
}

async function resumeScale() {
    const port = currentSelectedScalePort || document.getElementById('ctrlPort')?.value || 'SIM';
    addLog(`Menyambungkan kembali port serial (${port})...`);
    try {
        const res = await fetch(`/api/scale/resume?scale=${encodeURIComponent(port)}`, { method: 'POST' });
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
            if (document.getElementById('cfgScalePort')) {
                document.getElementById('cfgScalePort').value = cfg.server.scale_port || '';
            }
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
    const rawScalePort = document.getElementById('cfgScalePort') ? document.getElementById('cfgScalePort').value.trim() : '';
    const scalePort = rawScalePort ? parseInt(rawScalePort, 10) : null;
    const mode = document.getElementById('cfgSharingMode').value;
    const idle = parseFloat(document.getElementById('cfgIdleRelease').value);
    const scaleStartup = document.getElementById('cfgScaleStartup') ? (document.getElementById('cfgScaleStartup').value === 'true') : false;

    try {
        const getRes = await fetch('/api/config');
        const cfg = await getRes.json();
        cfg.server.host = host;
        cfg.server.port = port;
        cfg.server.scale_port = (scalePort && scalePort !== port) ? scalePort : null;
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
