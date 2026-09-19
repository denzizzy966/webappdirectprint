# 📡 Referensi API Lengkap

Alamat dasar: `http://127.0.0.1:18212` (fallback otomatis `12212`).
Dokumentasi interaktif bawaan FastAPI: `http://127.0.0.1:18212/docs`.

> Endpoint **cetak** dijelaskan lengkap beserta contoh di
> [direct-print/06-referensi-api-print.md](direct-print/06-referensi-api-print.md).
> Halaman ini adalah daftar menyeluruh semua endpoint.

---

## 1. Printer & Cetak

| Metode | Endpoint | Keterangan |
|--------|----------|------------|
| GET | `/api/printers` | Daftar printer OS + jaringan, beserta pool & printer bawaan |
| GET | `/api/printers/pools` | Pemetaan alias pool saja |
| POST | `/api/printers/pools` | Simpan pemetaan pool & printer bawaan |
| POST | `/api/print/raw` | Cetak ESC/POS, ZPL, TSPL, teks polos |
| POST | `/api/print/pdf` | Cetak PDF dari URL / Base64 / path berkas |
| POST | `/api/print/image` | Cetak gambar PNG / JPG / BMP (Base64) |
| POST | `/api/print/pdf-to-zpl` | Ubah PDF menjadi perintah ZPL raster **tanpa mencetak** |
| POST | `/api/cashdrawer/open` | Pulsa buka laci kasir (`pin` 2 atau 5) |
| POST | `/api/print/test-receipt` | Struk ESC/POS contoh (`?printer=`) |
| POST | `/api/print/test-label` | Label ZPL contoh (`?printer=`) |
| GET | `/api/print/history` | 100 job cetak terakhir (memori, hilang saat restart) |

---

## 2. Timbangan & Serial

| Metode | Endpoint | Keterangan |
|--------|----------|------------|
| GET | `/api/scales` | Daftar timbangan + status. `?format=list` mengembalikan array polos |
| GET | `/api/scale-list` | Sama seperti di atas, selalu array |
| GET | `/api/weight` | Berat saat ini (cepat, non-blocking). `?scale=` atau `?port=` |
| GET/POST | `/api/stable-read`, `/api/scale/stable-read` | Menunggu berat stabil. `?timeout=` (bawaan 10 detik) |
| POST | `/api/scale/zero` | Perintah Zero |
| POST | `/api/scale/tare` | Perintah Tare |
| POST | `/api/command`, `/api/scale/command` | Perintah teks kustom (`SI`, `S`, `Z`, dst.) |
| POST | `/api/connect`, `/api/scale/connect` | Sambungkan port dengan protokol/baud tertentu |
| POST | `/api/disconnect`, `/api/scale/disconnect` | Putuskan koneksi |
| GET | `/api/state`, `/api/scale/state` | Status detail + log RX/TX delta (`?since=`) |
| POST | `/api/scale/scan-baud` | Pindai baud rate otomatis (9600, 4800, 2400, 1200, 19200) |
| POST | `/api/scale/pause` | Lepas port serial agar bisa dipakai aplikasi lain |
| POST | `/api/scale/resume` | Sambungkan kembali port yang di-pause |
| POST | `/api/scale/startup-config` | `{ "enable_scale_at_startup": true/false }` |
| GET | `/api/ports` | Daftar port serial + flag `connected` |
| GET | `/api/serial/ports` | Daftar port serial fisik (bentuk terbungkus) |
| GET | `/api/stream` | SSE, update berat tiap 0,3 detik |

### Contoh `/api/weight`

```json
{
  "status": "success",
  "ok": true,
  "name": "Shinko 1",
  "port": "COM5",
  "weight": 125.5,
  "raw_weight": "  125.50 g",
  "unit": "g",
  "stable": true,
  "age": 0.12,
  "data": { }
}
```

### Contoh `/api/stable-read`

Sukses:

```json
{ "status": "success", "ok": true, "weight": 125.5, "unit": "g", "stable": true, "elapsed": 1.82 }
```

Timeout — **tetap HTTP 200**, jadi periksa `ok` / `status`:

```json
{
  "status": "timeout",
  "ok": false,
  "stable": false,
  "elapsed": 10.0,
  "error": "Timbangan 'Shinko 1' belum stabil dalam 10.0 detik."
}
```

Penjelasan lengkap timbangan: [06-timbangan-serial.md](06-timbangan-serial.md).

---

## 3. Sistem & Konfigurasi

| Metode | Endpoint | Keterangan |
|--------|----------|------------|
| GET | `/api/status` | Versi, sistem operasi, printer bawaan, jumlah printer & timbangan |
| GET | `/api/config` | Seluruh isi `bridge_config.json` |
| POST | `/api/config` | **Timpa** seluruh konfigurasi |
| GET | `/` | Dashboard web |
| GET | `/docs` | Swagger UI bawaan FastAPI |

### Contoh `/api/status`

```json
{
  "status": "online",
  "app": "WebApp Hardware Bridge Universal",
  "version": "2.1.0",
  "os": "win32",
  "os_details": "Windows-11-10.0.26200-SP0",
  "python_version": "3.12.4 ...",
  "default_printer": "Godex G500 GZPL",
  "total_printers": 5,
  "total_scales": 3,
  "connected_scale_ports": ["COM5 (Shinko 1)"],
  "scales": []
}
```

Endpoint ini juga berguna sebagai **health check** untuk mengetahui bridge sudah
berjalan sebelum mengirim job cetak.

---

## 4. Unduhan SDK & Skrip

| Metode | Endpoint | Isi |
|--------|----------|-----|
| GET | `/api/download/hardware-bridge.js` | SDK JavaScript universal |
| GET | `/api/download/erpnext-client-script.js` | Client Script ERPNext (POS & Sales Invoice) |
| GET | `/api/download/erpnext-pos-script.js` | Auto-print & laci kasir untuk POS Awesome |
| GET | `/api/download/all-scripts.zip` | Paket lengkap SDK + seluruh panduan `docs/` |

---

## 5. WebSocket

`ws://127.0.0.1:18212/ws`

Rute yang juga diterima: `/`, `/printer`, `/serial/DISPLAY`, `/serial/WEIGH`
(kompatibilitas `webapp-hardware-bridge` milik imTigger).

| `action` | Payload | Keterangan |
|----------|---------|------------|
| `getPrinters` | — | Daftar printer + pool |
| `print` | `{ printer, type, data, docName }` | `type`: `raw` \| `pdf` \| `image` |
| `openCashDrawer` | `{ printer, pin }` | Pulsa laci kasir |
| `getWeight` | `{ scale }` | Berat saat ini |
| `zero`, `tare` | `{ scale }` | Perintah timbangan |
| `subscribeScale` | — | Stream `scale_update` tiap 0,3 detik |
| `unsubscribeScale` | — | Hentikan stream |
| `getSerialPorts` | — | Daftar port serial |
| `ping` | — | Balasan `pong` |

Selain itu, pesan yang memuat `file_content` (atau `type` bernilai
`asset_label`/`pdf`) ditangani langsung sebagai cetak PDF dan **mendukung `qty`**
— lihat [direct-print/06-referensi-api-print.md](direct-print/06-referensi-api-print.md) §6.5.

---

## 6. Pola Respons

| Situasi | Kode HTTP | Bentuk |
|---------|-----------|--------|
| Cetak berhasil | 200 | `{ "status": "success", "result": { } }` |
| Cetak gagal | **500** | `{ "detail": "pesan galat" }` |
| Timbangan tidak ditemukan | 404 | `{ "detail": "Timbangan '...' tidak ditemukan" }` |
| Pembacaan stabil timeout | **200** | `{ "status": "timeout", "ok": false, "error": "..." }` |
| Payload tidak valid | 422 | Galat validasi Pydantic |

Karena kegagalan cetak berupa HTTP 500 (bukan galat jaringan), `fetch()` tetap
resolve. Selalu periksa:

```js
const res  = await fetch(url, opt);
const json = await res.json();
if (!res.ok || json.status !== 'success') {
    throw new Error(json.detail || json.message || 'Operasi gagal');
}
```
