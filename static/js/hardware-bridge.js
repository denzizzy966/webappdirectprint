/**
 * WebApp Hardware Bridge Universal Client SDK (JavaScript)
 * Library untuk integrasi Silent Direct Print (ESC/POS, ZPL, PDF) dan Timbangan Digital ke Browser / Laravel / Vue / ERPNext.
 * 
 * Sepenuhnya kompatibel dengan TimbanganSvc (drop-in replacement).
 * 
 * Penggunaan Singkat:
 *   <script src="/js/hardware-bridge.js"></script>
 *   
 *   // 1. Timbang stabil ke input field (Laravel Blade, Livewire, Vue, React, dsb.)
 *   HardwareBridge.timbangKeInput('#berat', { scale: 'Timbangan Gram' });
 *   
 *   // 2. Tampilkan berat live real-time
 *   HardwareBridge.liveWeight('#berat-live', { scale: 'Timbangan Gram' });
 *   
 *   // 3. Silent Direct Print Struk (ESC/POS)
 *   await HardwareBridge.printRaw("EPSON TM-T82", rawEscPosData);
 *   
 *   // 4. Silent Direct Print PDF Faktur / Barcode
 *   await HardwareBridge.printPdf("Godex G500", base64Pdf);
 */

(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        const lib = factory();
        root.HardwareBridge = lib;
        root.TimbanganSvc = lib; // Alias drop-in 100% kompatibel dengan TimbanganSvc
    }
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    const DEFAULT_HOST = '127.0.0.1';
    const DEFAULT_PORT = 18212;
    const FALLBACK_PORT = 12212;

    class HardwareBridge {
        constructor(options = {}) {
            // Default selalu 127.0.0.1:18212 (bridge lokal pada PC klien)
            let defHost = DEFAULT_HOST;
            let defPort = DEFAULT_PORT;

            // Hanya jika halaman browser sendiri dibuka langsung pada port bridge (misal dashboard bawaan)
            if (typeof window !== 'undefined' && window.location) {
                if (window.location.port === '18212' || window.location.port === '12212') {
                    defHost = window.location.hostname || DEFAULT_HOST;
                    defPort = parseInt(window.location.port, 10);
                }
            }

            this.host = options.host || defHost;
            this.port = options.port || defPort;
            this.scaleHost = options.scaleHost || this.host;
            this.scalePort = options.scalePort || this.port; // Default sama dengan port utama (jadi 1 port)
            this.useSecure = options.secure || (typeof window !== 'undefined' && window.location && window.location.protocol === 'https:');
            this.autoReconnect = options.autoReconnect !== false;
            this.reconnectInterval = options.reconnectInterval || 3000;

            this.ws = null;
            this.isConnected = false;
            this.callbacks = new Map();
            this.weightListeners = [];
            this.connectListeners = [];
            this.disconnectListeners = [];
        }

        get wsUrl() {
            const proto = this.useSecure ? 'wss://' : 'ws://';
            return `${proto}${this.host}:${this.port}/ws`;
        }

        get httpUrl() {
            const proto = this.useSecure ? 'https://' : 'http://';
            return `${proto}${this.host}:${this.port}/api`;
        }

        get scaleWsUrl() {
            const proto = this.useSecure ? 'wss://' : 'ws://';
            return `${proto}${this.scaleHost}:${this.scalePort}/ws`;
        }

        get scaleHttpUrl() {
            const proto = this.useSecure ? 'https://' : 'http://';
            return `${proto}${this.scaleHost}:${this.scalePort}/api`;
        }

        connect() {
            return new Promise((resolve) => {
                try {
                    this.ws = new WebSocket(this.wsUrl);
                } catch (e) {
                    return resolve(false);
                }

                const connTimeout = setTimeout(() => {
                    if (!this.isConnected) {
                        resolve(false);
                    }
                }, 2500);

                this.ws.onopen = () => {
                    clearTimeout(connTimeout);
                    this.isConnected = true;
                    this.connectListeners.forEach(fn => fn());
                    if (this.weightListeners.length > 0) {
                        this.ws.send(JSON.stringify({ action: 'subscribeScale' }));
                    }
                    resolve(true);
                };

                this.ws.onclose = () => {
                    this.isConnected = false;
                    this.disconnectListeners.forEach(fn => fn());
                    if (this.autoReconnect) {
                        setTimeout(() => this.connect().catch(() => {}), this.reconnectInterval);
                    }
                };

                this.ws.onerror = () => {};

                this.ws.onmessage = (event) => {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.action === 'scale_update' && msg.scales) {
                            this.weightListeners.forEach(fn => fn(msg.scales));
                        } else if (msg.action) {
                            const cb = this.callbacks.get(msg.action);
                            if (cb) {
                                cb(msg);
                                this.callbacks.delete(msg.action);
                            }
                        }
                    } catch (e) {
                        console.error('[HardwareBridge] Gagal parse WS message:', e);
                    }
                };
            });
        }

        _sendWs(payload) {
            return new Promise((resolve, reject) => {
                if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
                    return reject(new Error('WebSocket tidak terhubung ke Hardware Bridge'));
                }
                const action = payload.action;
                this.callbacks.set(action, (res) => {
                    if (res.status === 'success') resolve(res);
                    else reject(new Error(res.message || 'Operasi gagal'));
                });
                this.ws.send(JSON.stringify(payload));
                setTimeout(() => {
                    if (this.callbacks.has(action)) {
                        this.callbacks.delete(action);
                        reject(new Error(`Timeout menunggu respons action ${action}`));
                    }
                }, 10000);
            });
        }

        // ────────────────────────────────────────────────────────────
        // Printer API (Instance Methods)
        // ────────────────────────────────────────────────────────────

        async getPrinters() {
            if (this.isConnected) return await this._sendWs({ action: 'getPrinters' });
            const res = await fetch(`${this.httpUrl}/printers`);
            return await res.json();
        }

        async getPrinterPools() {
            const res = await fetch(`${this.httpUrl}/printers/pools`);
            return await res.json();
        }

        async printRaw(printerName, rawData, docName = 'Silent_Raw') {
            if (this.isConnected) {
                return await this._sendWs({
                    action: 'print',
                    printer: printerName,
                    type: 'raw',
                    data: rawData,
                    docName: docName
                });
            }
            const res = await fetch(`${this.httpUrl}/print/raw`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ printer: printerName, data: rawData, doc_name: docName })
            });
            return await res.json();
        }

        async printPdf(printerName, pdfDataOrUrl, docName = 'Silent_PDF', options = {}) {
            if (this.isConnected) {
                return await this._sendWs({
                    action: 'print',
                    printer: printerName,
                    type: 'pdf',
                    data: pdfDataOrUrl,
                    docName: docName,
                    options: options
                });
            }
            const res = await fetch(`${this.httpUrl}/print/pdf`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ printer: printerName, pdf_data: pdfDataOrUrl, doc_name: docName, options: options })
            });
            return await res.json();
        }

        async printImage(printerName, imageBase64, docName = 'Silent_Image') {
            if (this.isConnected) {
                return await this._sendWs({
                    action: 'print',
                    printer: printerName,
                    type: 'image',
                    data: imageBase64,
                    docName: docName
                });
            }
            const res = await fetch(`${this.httpUrl}/print/image`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ printer: printerName, image_data: imageBase64, doc_name: docName })
            });
            return await res.json();
        }

        async openCashDrawer(printerName, pin = 2) {
            if (this.isConnected) {
                return await this._sendWs({
                    action: 'openCashDrawer',
                    printer: printerName,
                    pin: pin
                });
            }
            const res = await fetch(`${this.httpUrl}/cashdrawer/open`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ printer: printerName, pin: pin })
            });
            return await res.json();
        }

        // ────────────────────────────────────────────────────────────
        // Scale API (Instance Methods)
        // ────────────────────────────────────────────────────────────

        async getWeight(scaleName = null) {
            if (this.isConnected) {
                return await this._sendWs({ action: 'getWeight', scale: scaleName });
            }
            const url = scaleName ? `${this.httpUrl}/weight?scale=${encodeURIComponent(scaleName)}` : `${this.httpUrl}/weight`;
            const res = await fetch(url);
            return await res.json();
        }

        async getStableWeight(scaleName = null, timeout = 10.0) {
            const url = scaleName ? 
                `${this.httpUrl}/stable-read?scale=${encodeURIComponent(scaleName)}&timeout=${timeout}` : 
                `${this.httpUrl}/stable-read?timeout=${timeout}`;
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scale: scaleName, timeout: timeout })
            });
            return await res.json();
        }

        async zero(scaleName = null) {
            if (this.isConnected) return await this._sendWs({ action: 'zero', scale: scaleName });
            const url = scaleName ? `${this.httpUrl}/scale/zero?scale=${encodeURIComponent(scaleName)}` : `${this.httpUrl}/scale/zero`;
            const res = await fetch(url, { method: 'POST' });
            return await res.json();
        }

        async tare(scaleName = null) {
            if (this.isConnected) return await this._sendWs({ action: 'tare', scale: scaleName });
            const url = scaleName ? `${this.httpUrl}/scale/tare?scale=${encodeURIComponent(scaleName)}` : `${this.httpUrl}/scale/tare`;
            const res = await fetch(url, { method: 'POST' });
            return await res.json();
        }

        onWeightChange(callback) {
            if (typeof callback === 'function') {
                this.weightListeners.push(callback);
                if (this.isConnected && this.ws) {
                    this.ws.send(JSON.stringify({ action: 'subscribeScale' }));
                }
            }
        }

        onConnect(callback) {
            if (typeof callback === 'function') this.connectListeners.push(callback);
        }

        onDisconnect(callback) {
            if (typeof callback === 'function') this.disconnectListeners.push(callback);
        }
    }

    // ────────────────────────────────────────────────────────────
    // Static Helper Methods & TimbanganSvc Drop-In API
    // ────────────────────────────────────────────────────────────

    HardwareBridge.SERVICE_URL = `http://${DEFAULT_HOST}:${DEFAULT_PORT}`;
    HardwareBridge.SCALE_SERVICE_URL = null; // Port/URL terpisah untuk timbangan jika diset (default: null / jadi 1 port dengan SERVICE_URL)
    HardwareBridge.MAX_AGE_S = 5;
    HardwareBridge.STABLE_TIMEOUT_S = 10;
    HardwareBridge.onError = null;

    // Helper untuk mengubah port/URL jika port timbangan & print dipisahkan
    HardwareBridge.setPort = function (port) {
        HardwareBridge.SERVICE_URL = `http://${DEFAULT_HOST}:${port}`;
    };

    HardwareBridge.setScalePort = function (port) {
        HardwareBridge.SCALE_SERVICE_URL = `http://${DEFAULT_HOST}:${port}`;
    };

    HardwareBridge.configure = function (opts = {}) {
        if (opts.serviceUrl) HardwareBridge.SERVICE_URL = opts.serviceUrl;
        if (opts.port) HardwareBridge.SERVICE_URL = `http://${opts.host || DEFAULT_HOST}:${opts.port}`;
        if (opts.scaleUrl) HardwareBridge.SCALE_SERVICE_URL = opts.scaleUrl;
        if (opts.scalePort) HardwareBridge.SCALE_SERVICE_URL = `http://${opts.scaleHost || opts.host || DEFAULT_HOST}:${opts.scalePort}`;
    };

    // HTTP Helper internal
    async function apiRequest(path, body, timeoutMs) {
        const isScalePath = path.startsWith('/api/scale') || path.startsWith('/api/weight') || path.startsWith('/api/stream') ||
                            path.startsWith('/scale') || path.startsWith('/weight') || path.startsWith('/stream');
        
        // Jika endpoint timbangan dan SCALE_SERVICE_URL dikonfigurasi terpisah, gunakan url timbangan
        const primaryUrl = (isScalePath && HardwareBridge.SCALE_SERVICE_URL) ? HardwareBridge.SCALE_SERVICE_URL : HardwareBridge.SERVICE_URL;

        const urlsToTry = [primaryUrl];
        if (!isScalePath && !primaryUrl.includes(String(FALLBACK_PORT))) {
            urlsToTry.push(`http://${DEFAULT_HOST}:${FALLBACK_PORT}`);
        }

        let lastErr = null;
        for (const baseUrl of urlsToTry) {
            const ctrl = new AbortController();
            const t = setTimeout(() => ctrl.abort(), timeoutMs || 8000);
            try {
                const opt = { signal: ctrl.signal };
                if (body) {
                    opt.method = 'POST';
                    opt.headers = { 'Content-Type': 'application/json' };
                    opt.body = JSON.stringify(body);
                }
                const r = await fetch(baseUrl + path, opt);
                if (r.ok || r.status === 404 || r.status === 409 || r.status === 500) {
                    const data = await r.json();
                    if (!isScalePath) HardwareBridge.SERVICE_URL = baseUrl; // Cache working URL
                    return data;
                }
            } catch (e) {
                lastErr = e;
            } finally {
                clearTimeout(t);
            }
        }
        throw lastErr || new Error('Gagal menghubungi Hardware Bridge di ' + primaryUrl);
    }

    HardwareBridge.api = apiRequest;

    function reportError(msg) {
        if (typeof HardwareBridge.onError === 'function') {
            HardwareBridge.onError(msg);
        } else {
            toast(msg, '#cd2b2b');
        }
    }

    function toast(msg, bg) {
        try {
            if (typeof document === 'undefined') return;
            const d = document.createElement('div');
            d.textContent = msg;
            d.style.cssText =
                'position:fixed;right:16px;bottom:16px;z-index:2147483647;' +
                'max-width:360px;padding:10px 16px;border-radius:8px;color:#fff;' +
                'font:14px/1.4 system-ui,sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.25);' +
                'background:' + (bg || '#1e4976');
            document.body.appendChild(d);
            setTimeout(() => d.remove(), 4000);
        } catch (e) {}
    }
    HardwareBridge.toast = toast;

    function resolveEl(target) {
        if (typeof document === 'undefined') return null;
        return typeof target === 'string' ? document.querySelector(target) : target;
    }

    function toGram(value, unit, legacyToGram) {
        if (value == null) return 0;
        const u = String(unit || '').toLowerCase().trim();
        if (u === 'kg') return value * 1000;
        if (u === 'mg') return value / 1000;
        if (u === 'g' || u === '') {
            return (!u && legacyToGram) ? value * 1000 : value;
        }
        return value; // ct, dwt, oz, dll
    }
    HardwareBridge.toGram = toGram;

    // 1. listScales() -> Mengambil array timbangan terdaftar
    HardwareBridge.listScales = async function () {
        const res = await apiRequest('/api/scales');
        return Array.isArray(res) ? res : (res.scales || []);
    };

    // 2. getWeight(scale) -> Mengambil berat terkini secara instan
    HardwareBridge.getWeight = async function (scale) {
        const q = scale ? `?scale=${encodeURIComponent(scale)}` : '';
        return await apiRequest(`/api/weight${q}`);
    };

    // 3. stableRead(scale, timeoutS) -> Menunggu hingga berat stabil
    HardwareBridge.stableRead = async function (scale, timeoutS) {
        const timeout = timeoutS || HardwareBridge.STABLE_TIMEOUT_S;
        const body = { scale: scale || null, timeout: timeout };
        return await apiRequest('/api/stable-read', body, (timeout + 3) * 1000);
    };

    /**
     * 4. pickScale(preferred)
     * Logika cerdas untuk memilih timbangan saat ada 1, 2, atau lebih timbangan terhubung:
     * - Jika `preferred` diisi: mencocokkan Nama (exact / case-insensitive), Port (COM3/COM5), atau substring.
     * - Jika `preferred` kosong: otomatis memilih timbangan FISIK pertama yang online (bukan SIM).
     */
    HardwareBridge.pickScale = async function (preferred) {
        let scales;
        try {
            scales = await HardwareBridge.listScales();
        } catch (e) {
            throw new Error('Hardware Bridge tidak jalan di PC ini. Pastikan aplikasi/service Hardware Bridge aktif (port 18212).');
        }

        const connected = scales.filter(s => s.connected && s.port !== 'SIM');
        const available = connected.length > 0 ? connected : scales.filter(s => s.connected);

        if (preferred) {
            const prefStr = String(preferred).trim().toLowerCase();
            // a. Exact / Case-insensitive match on name
            let hit = available.find(s => s.name.toLowerCase() === prefStr);
            // b. Match on port (e.g. "COM5" atau "/dev/ttyUSB0")
            if (!hit) hit = available.find(s => s.port && s.port.toLowerCase() === prefStr);
            // c. Substring match on name (e.g. "gram", "koli", "mettler", "shinko")
            if (!hit) hit = available.find(s => s.name.toLowerCase().includes(prefStr));

            if (hit) return hit;
            throw new Error(`Timbangan "${preferred}" tidak terhubung. Periksa kabel USB atau dashboard bridge.`);
        }

        if (!available.length) {
            throw new Error('Tidak ada timbangan terhubung — cek kabel/adaptor USB timbangan.');
        }
        return available[0];
    };

    /**
     * 5. populateScaleSelect(targetSelect, opts)
     * Mengisi dropdown <select> dengan daftar timbangan aktif secara dinamis.
     * Sangat berguna jika di meja operator terdapat 2 timbangan (misal Timbangan Gram & Timbangan Koli).
     */
    HardwareBridge.populateScaleSelect = async function (targetSelect, opts = {}) {
        const el = resolveEl(targetSelect);
        if (!el) return [];
        try {
            const scales = await HardwareBridge.listScales();
            const connected = scales.filter(s => s.connected);
            el.innerHTML = '';

            if (connected.length === 0) {
                const opt = document.createElement('option');
                opt.value = '';
                opt.textContent = '-- Tidak ada timbangan terhubung --';
                el.appendChild(opt);
                return [];
            }

            connected.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.name;
                const isSim = s.port === 'SIM';
                opt.textContent = `${s.name} [${s.port || 'Auto'}]${isSim ? ' (Virtual)' : ''}`;
                const isSel = opts.selected && (
                    s.name.toLowerCase() === String(opts.selected).toLowerCase() ||
                    (s.port && s.port.toLowerCase() === String(opts.selected).toLowerCase())
                );
                if (isSel) opt.selected = true;
                el.appendChild(opt);
            });

            if (typeof opts.onChange === 'function') {
                el.addEventListener('change', () => opts.onChange(el.value));
            }
            return connected;
        } catch (e) {
            el.innerHTML = '<option value="">-- Hardware Bridge Offline --</option>';
            return [];
        }
    };

    /**
     * 6. timbangKeInput(target, opts)
     * Mengambil nilai STABIL dan menulis ke elemen <input>.
     * Memicu event 'input' & 'change' (bubbles) agar Livewire (wire:model),
     * Vue (v-model), React, dan jQuery langsung mendeteksi perubahannya!
     * 
     * Opsi:
     *   - scale: nama timbangan tertentu atau port (misal 'Timbangan Gram', 'COM5', null = auto)
     *   - alerts: tampilkan toast progres & sukses (default: false)
     *   - stable_timeout: batas waktu tunggu stabil dalam detik (default: 10)
     *   - decimals: jumlah digit desimal (default: 2)
     *   - to_gram: konversi otomatis ke gram (default: true)
     */
    HardwareBridge.timbangKeInput = async function (target, opts = {}) {
        const el = resolveEl(target);
        if (!el) {
            reportError('Elemen input tidak ditemukan: ' + target);
            return null;
        }
        try {
            const s = await HardwareBridge.pickScale(opts.scale);
            if (opts.alerts) toast(`Menunggu nilai STABIL dari ${s.name} [${s.port || ''}]...`);
            const r = await HardwareBridge.stableRead(s.name, opts.stable_timeout);
            if (!r.ok) throw new Error(r.error || r.message || 'Pembacaan stabil gagal');

            const gram = toGram(r.weight, r.unit, opts.to_gram !== false);
            if (gram <= 0 && !opts.allow_zero) {
                toast('Berat 0 atau timbangan kosong — periksa timbangan', '#8a5a00');
                return null;
            }

            const dec = opts.decimals == null ? 2 : opts.decimals;
            el.value = gram.toFixed(dec);
            el.dispatchEvent(new Event('input',  { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));

            if (opts.alerts) toast(`${gram.toFixed(dec)} ${r.unit || 'g'} (stabil)`, '#1e9e46');
            return gram;
        } catch (e) {
            reportError(e.message);
            return null;
        }
    };

    /**
     * 7. liveWeight(target, opts)
     * Menampilkan angka berat live real-time pada elemen (refresh setiap 0.5 dtk).
     * Mengembalikan fungsi stop() untuk mematikan interval.
     */
    HardwareBridge.liveWeight = function (target, opts = {}) {
        const el = resolveEl(target);
        let scaleName = opts.scale || null;
        let stopped = false;

        const tick = async () => {
            if (stopped) return;
            try {
                if (!scaleName) {
                    const picked = await HardwareBridge.pickScale(opts.scale);
                    scaleName = picked.name;
                }
                const r = await HardwareBridge.getWeight(scaleName);
                if (el) {
                    if (r.ok && r.weight != null) {
                        const age = r.age != null ? r.age : (r.data && r.data.age != null ? r.data.age : 0);
                        const basi = age > HardwareBridge.MAX_AGE_S;
                        const dec = opts.decimals == null ? 2 : opts.decimals;
                        const suffix = opts.suffix == null ? (` ${r.unit || 'g'}`) : opts.suffix;
                        el.textContent = toGram(r.weight, r.unit, opts.to_gram !== false).toFixed(dec)
                            + suffix
                            + (basi ? ' (BASI)' : (r.stable === false ? ' (dinamis)' : ''));
                    } else {
                        el.textContent = '-- (terputus)';
                        scaleName = opts.scale || null; // Coba cari ulang timbangan
                    }
                }
                if (typeof opts.onUpdate === 'function') opts.onUpdate(r);
            } catch (e) {
                if (el) el.textContent = '-- (bridge mati)';
                scaleName = opts.scale || null;
            }
        };

        tick();
        const timer = setInterval(tick, opts.interval || 500);
        return function stop() { stopped = true; clearInterval(timer); };
    };

    /**
     * 8. attachIndicator(target)
     * Menempelkan badge indikator status koneksi ke elemen (hijau = online, merah = error).
     */
    HardwareBridge.attachIndicator = function (target) {
        const el = resolveEl(target);
        if (!el) return function () {};
        let stopped = false;

        const tick = async () => {
            if (stopped) return;
            try {
                const scales = await HardwareBridge.listScales();
                const on = scales.filter(s => s.connected && s.port !== 'SIM');
                if (on.length) {
                    el.textContent = '🟢 ' + on.map(s => `${s.name} [${s.port}]`).join(', ');
                    el.style.color = '#1e9e46';
                } else {
                    const sim = scales.filter(s => s.connected && s.port === 'SIM');
                    if (sim.length) {
                        el.textContent = '🟡 Simulator Aktif (Timbangan fisik belum terhubung)';
                        el.style.color = '#b08800';
                    } else {
                        el.textContent = '🔴 Timbangan tidak terhubung';
                        el.style.color = '#cd2b2b';
                    }
                }
            } catch (e) {
                el.textContent = '🔴 Hardware Bridge offline';
                el.style.color = '#cd2b2b';
            }
        };

        tick();
        const timer = setInterval(tick, 5000);
        return function stop() { stopped = true; clearInterval(timer); };
    };

    /**
     * 9. timbangDialog(onUse, opts)
     * Modal dialog interaktif mandiri (tanpa dependensi Bootstrap/Tailwind).
     * Jika ada 2 timbangan atau lebih, dialog otomatis menyediakan selector dropdown switch!
     */
    HardwareBridge.timbangDialog = async function (onUse, opts = {}) {
        if (typeof document === 'undefined') return;

        let availableScales = [];
        try {
            const all = await HardwareBridge.listScales();
            availableScales = all.filter(s => s.connected);
        } catch (e) {}

        const ov = document.createElement('div');
        ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:2147483646;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(2px)';

        let selectHtml = '';
        if (availableScales.length > 1) {
            selectHtml = '<div style="margin-bottom:12px;font-size:13px;text-align:left;">' +
                '<label style="display:block;margin-bottom:4px;color:#555;font-weight:600">Pilih Timbangan Aktif:</label>' +
                '<select data-sel style="width:100%;padding:6px 8px;border:1px solid #ccc;border-radius:6px;font-size:13px;background:#fcfcfc">' +
                availableScales.map(s => `<option value="${s.name}" ${(opts.scale === s.name || opts.scale === s.port) ? 'selected' : ''}>${s.name} [${s.port || 'Auto'}]</option>`).join('') +
                '</select></div>';
        }

        ov.innerHTML =
            '<div style="background:#fff;border-radius:12px;padding:22px 26px;min-width:330px;max-width:92vw;font-family:system-ui,-apple-system,sans-serif;text-align:center;box-shadow:0 12px 35px rgba(0,0,0,.25)">' +
            '<h3 style="margin:0 0 14px;font-size:18px;color:#1c2733;font-weight:700">' + (opts.title || '⚖️ Timbang Berat') + '</h3>' +
            selectHtml +
            '<div data-w style="font-size:46px;font-weight:800;color:#1e6fd9;letter-spacing:-1px;margin:10px 0">--</div>' +
            '<div data-st style="color:#666;font-size:13px;min-height:1.4em;margin:6px 0 16px">Menghubungi bridge...</div>' +
            '<div style="display:flex;gap:10px;justify-content:center">' +
            '<button data-ok style="flex:1;padding:10px 16px;border:0;border-radius:8px;background:#1e6fd9;color:#fff;font-size:14px;font-weight:600;cursor:pointer">Gunakan Berat (stabil)</button>' +
            '<button data-x style="padding:10px 14px;border:1px solid #ccc;border-radius:8px;background:#fff;color:#444;font-size:14px;cursor:pointer">Batal</button>' +
            '</div></div>';

        document.body.appendChild(ov);

        const $w = ov.querySelector('[data-w]');
        const $st = ov.querySelector('[data-st]');
        const $sel = ov.querySelector('[data-sel]');
        let activeScale = $sel ? $sel.value : (opts.scale || null);
        let busy = false;
        let stopLive = null;

        function startListening(scale) {
            if (stopLive) stopLive();
            stopLive = HardwareBridge.liveWeight($w, {
                scale: scale,
                onUpdate: r => {
                    if (r && r.ok) {
                        $st.textContent = r.stable ? '🟢 Nilai Stabil' : '🟡 Menunggu Stabil...';
                        $st.style.color = r.stable ? '#1e9e46' : '#d97706';
                    }
                }
            });
        }

        startListening(activeScale);

        if ($sel) {
            $sel.addEventListener('change', () => {
                activeScale = $sel.value;
                $st.textContent = 'Beralih ke ' + activeScale + '...';
                startListening(activeScale);
            });
        }

        const close = () => {
            if (stopLive) stopLive();
            ov.remove();
        };

        ov.querySelector('[data-x]').onclick = close;
        ov.querySelector('[data-ok]').onclick = async () => {
            if (busy) return;
            busy = true;
            $st.textContent = 'Menunggu nilai STABIL...';
            $st.style.color = '#1e6fd9';
            try {
                const s = await HardwareBridge.pickScale(activeScale);
                const r = await HardwareBridge.stableRead(s.name, opts.stable_timeout);
                if (!r.ok) throw new Error(r.error || r.message || 'Gagal membaca stabil');
                const gram = toGram(r.weight, r.unit, opts.to_gram !== false);
                if (gram <= 0 && !opts.allow_zero) {
                    $st.textContent = 'Berat 0 — letakkan beban di timbangan';
                    $st.style.color = '#d97706';
                    return;
                }
                close();
                if (typeof onUse === 'function') onUse(gram, s);
            } catch (e) {
                $st.textContent = 'Gagal: ' + e.message;
                $st.style.color = '#cd2b2b';
            } finally {
                busy = false;
            }
        };
    };

    // ────────────────────────────────────────────────────────────
    // Direct Print Helpers (Static)
    // ────────────────────────────────────────────────────────────

    HardwareBridge.getPrinters = async function () {
        return await apiRequest('/api/printers');
    };

    HardwareBridge.printRaw = async function (printerName, rawData, docName = 'DirectPrint_Raw') {
        return await apiRequest('/api/print/raw', {
            printer: printerName,
            data: rawData,
            doc_name: docName
        });
    };

    HardwareBridge.printPdf = async function (printerName, pdfDataOrUrl, docName = 'DirectPrint_PDF', options = {}) {
        return await apiRequest('/api/print/pdf', {
            printer: printerName,
            pdf_data: pdfDataOrUrl,
            doc_name: docName,
            options: options
        });
    };

    HardwareBridge.printImage = async function (printerName, imageBase64, docName = 'DirectPrint_Image') {
        return await apiRequest('/api/print/image', {
            printer: printerName,
            image_data: imageBase64,
            doc_name: docName
        });
    };

    HardwareBridge.openCashDrawer = async function (printerName, pin = 2) {
        return await apiRequest('/api/cashdrawer/open', {
            printer: printerName,
            pin: pin
        });
    };

    return HardwareBridge;
}));
