# ⚙️ Referensi Konfigurasi `bridge_config.json`

Berkas konfigurasi berada di folder yang sama dengan `app.py` (atau di samping
`HardwareBridge.exe` untuk paket portable). Bila tidak ada, bridge membuatnya
dari nilai bawaan pada [`app/config.py`](../app/config.py).

> Pada build PyInstaller, bila `bridge_config.json` tidak ditemukan di samping
> executable, bridge memakai `_internal/bridge_config.json`.

---

## Contoh Lengkap

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 18212,
    "scale_port": null,
    "cors_origins": ["*"],
    "enable_tray": true,
    "sharing_mode": "continuous",
    "idle_release_seconds": 4.0,
    "pause_auto_resume_seconds": 600,
    "enable_scale_at_startup": false
  },
  "printers": {
    "default_raw_printer": "Godex G500 GZPL",
    "default_doc_printer": "Godex G500 GZPL",
    "default_encoding": "cp437",
    "pools": {
      "asset_label":  "Godex G500 GZPL",
      "label":        "Godex G500 GZPL",
      "barcode":      "Godex G500 GZPL",
      "receipt":      "Godex G500 GZPL",
      "invoice":      "Microsoft Print to PDF",
      "kitchen":      "Network POS Printer (Contoh)",
      "packing_slip": "Godex G500 GZPL"
    },
    "network_printers": [
      { "name": "Network POS Printer (Contoh)", "ip": "192.168.1.200", "port": 9100, "type": "escpos" }
    ]
  },
  "scales": [
    {
      "name": "Shinko 1",
      "port": "/dev/ttyUSB0",
      "protocol": "shinko",
      "baud": 9600,
      "databits": 8,
      "parity": "N",
      "stopbits": 1,
      "poll_interval": 0.5,
      "autoconnect": true
    }
  ]
}
```

---

## Bagian `server`

| Kunci | Tipe | Bawaan | Keterangan |
|-------|------|--------|------------|
| `host` | string | `"0.0.0.0"` | Antarmuka yang didengarkan. `127.0.0.1` = hanya PC ini; `0.0.0.0` = bisa diakses dari jaringan |
| `port` | int | `18212` | Port HTTP & WebSocket utama. Bila terpakai, bridge otomatis mencoba `12212` (dan sebaliknya) |
| `scale_port` | int / null | `null` | Port terpisah khusus timbangan. `null` = satu port untuk semuanya |
| `cors_origins` | array | `["*"]` | Asal yang diizinkan. Persempit di lingkungan produksi |
| `enable_tray` | bool | `true` | Ikon system tray Windows. Dapat dimatikan lewat argumen `--no-tray` |
| `sharing_mode` | string | `"continuous"` | Mode berbagi port serial timbangan |
| `idle_release_seconds` | float | `4.0` | Lama diam sebelum port serial dilepas (mode berbagi) |
| `pause_auto_resume_seconds` | int | `600` | Port serial yang di-pause tersambung lagi otomatis setelah sekian detik |
| `enable_scale_at_startup` | bool | `false` | `false` menjaga port COM tetap bebas untuk Web Serial API browser atau aplikasi Delphi |

### Kapan Memakai `scale_port` Terpisah

Bila aplikasi lama Anda sudah memanggil timbangan di port tertentu sementara
cetak memakai port lain:

```json
{ "server": { "port": 18212, "scale_port": 12212 } }
```

Bridge menjalankan dua listener uvicorn dengan aplikasi yang sama. Di sisi
JavaScript:

```js
HardwareBridge.configure({ port: 18212, scalePort: 12212 });
```

---

## Bagian `printers`

| Kunci | Tipe | Keterangan |
|-------|------|------------|
| `default_raw_printer` | string | Tujuan bawaan job RAW (ESC/POS, ZPL). Juga menjadi nilai `/api/printers` → `default` |
| `default_doc_printer` | string | Tujuan bawaan job PDF & gambar |
| `default_encoding` | string | Encoding teks polos pada jalur RAW. Bawaan `cp437`; alternatif `cp850`, `cp1252`, `utf-8` |
| `pools` | objek | Pemetaan alias → nama printer fisik |
| `network_printers` | array | Printer TCP port 9100 (**hanya untuk job RAW**) |

### `pools`

Kunci bebas ditentukan sendiri. Beberapa nama punya arti khusus sebagai
cadangan otomatis saat `printer` tidak diisi:

| Jenis Job | Urutan Cadangan |
|-----------|-----------------|
| PDF / gambar | `default_doc_printer` → `invoice` → `asset_label` → `doc` → lalu jalur RAW di bawah |
| RAW | `default_raw_printer` → `receipt` → `label` → `raw` → printer bawaan OS → printer pertama |

Penjelasan lengkap: [direct-print/05-printer-target-pool.md](direct-print/05-printer-target-pool.md).

### `network_printers`

| Kunci | Keterangan |
|-------|------------|
| `name` | Nama yang dirujuk dari `pools` atau field `printer` |
| `ip` | Alamat IP printer |
| `port` | Bawaan `9100` |
| `type` | Label informasi saja (mis. `escpos`) |

> Printer jaringan **hanya** dipakai pada `/api/print/raw`. Untuk PDF, pasang
> printer tersebut sebagai printer Windows/CUPS biasa.

---

## Bagian `scales`

Berupa array; tiap elemen satu timbangan.

| Kunci | Tipe | Bawaan | Keterangan |
|-------|------|--------|------------|
| `name` | string | — | Nama yang dirujuk dari API (`?scale=Shinko 1`) |
| `port` | string | — | `COM5` (Windows), `/dev/ttyUSB0` (Linux), atau `SIM` untuk simulator |
| `protocol` | string | `mettler` | `shinko`, `mettler`, `avery`, `auto`, dsb. |
| `baud` | int | `9600` | Baud rate |
| `databits` | int | `8` | Bit data |
| `parity` | string | `"N"` | `N`, `E`, `O` |
| `stopbits` | int | `1` | Bit stop |
| `poll_interval` | float | `0.5` | Jeda polling (detik) |
| `autoconnect` | bool | `false` | Sambung otomatis saat bridge dijalankan |

Detail protokol dan pemilihan multi-timbangan:
[06-timbangan-serial.md](06-timbangan-serial.md).

---

## Menerapkan Perubahan

| Cara | Berlaku |
|------|---------|
| Ubah berkas langsung | Setelah bridge dijalankan ulang (tray → **Restart Service**) |
| Dashboard → Pengaturan | Seketika, langsung disimpan ke berkas |
| `POST /api/config` | Seketika untuk sebagian besar nilai |
| `POST /api/printers/pools` | Seketika, hanya bagian pool & printer bawaan |

```bash
# Baca konfigurasi aktif
curl http://127.0.0.1:18212/api/config

# Ubah hanya pemetaan pool
curl -X POST http://127.0.0.1:18212/api/printers/pools \
  -H "Content-Type: application/json" \
  -d '{"pools":{"asset_label":"Godex G500 GZPL"},"default_doc_printer":"Godex G500 GZPL"}'
```

> `POST /api/config` menimpa **seluruh** isi konfigurasi. Ambil dulu dengan
> `GET /api/config`, ubah bagian yang perlu, lalu kirim kembali utuh.

---

## Catatan Keamanan

Bawaan `host: "0.0.0.0"` dan `cors_origins: ["*"]` membuat bridge dapat diakses
oleh siapa pun di jaringan yang sama, **tanpa autentikasi**. Untuk PC yang
terhubung ke jaringan yang lebih luas:

```json
{
  "server": {
    "host": "127.0.0.1",
    "cors_origins": ["http://erp.perusahaan.local", "http://192.168.3.25"]
  }
}
```

`host: "127.0.0.1"` sudah cukup untuk pemakaian normal, karena aplikasi web
memanggil bridge dari browser di PC yang sama.
