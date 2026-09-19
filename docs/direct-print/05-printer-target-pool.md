# 5. Memilih Printer Tujuan: Nama, Alias Pool & Printer Jaringan

---

## 5.1 Tiga Field yang Setara

Ketiga field berikut berarti sama persis. Bridge memakai yang pertama terisi
(`printer` → `target` → `pool`):

```json
{ "printer": "Godex G500 GZPL" }
{ "target":  "asset_label" }
{ "pool":    "asset_label" }
```

`target` dan `pool` ada demi kompatibilitas dengan skrip
`webapp-hardware-bridge` (imTigger) yang sudah dipakai di ERPNext.

---

## 5.2 Cara Bridge Menerjemahkan Nama Printer

`printer_manager.resolve_printer(target, job_type)` mencoba berurutan:

| Urutan | Pemeriksaan | Contoh |
|--------|-------------|--------|
| 1 | Cocok dengan kunci `pools` (tidak peduli besar-kecil huruf) | `asset_label` → `Godex G500 GZPL` |
| 2 | Cocok persis dengan nama printer fisik di OS | `Godex G500 GZPL` |
| 3 | Cocok dengan nama printer jaringan di `network_printers` | `Printer Dapur` |
| 4 | Pencocokan sebagian nama printer fisik | `godex` → `Godex G500 GZPL` |
| 5 | Bawaan sesuai jenis job | PDF → `default_doc_printer`, lalu pool `invoice`/`asset_label`/`doc` |
| 6 | `default_raw_printer`, lalu pool `receipt`/`label`/`raw` | |
| 7 | Printer bawaan sistem operasi | |
| 8 | Printer fisik pertama yang terdeteksi | |

Artinya `printer` boleh dikosongkan (`null`) — bridge akan memilih sendiri
berdasarkan konfigurasi.

> `job_type` ditentukan otomatis oleh endpoint: `/api/print/pdf` dan
> `/api/print/image` memakai jalur dokumen, `/api/print/raw` memakai jalur raw.

---

## 5.3 Mengatur Pool

### Lewat `bridge_config.json`

```json
{
  "printers": {
    "default_raw_printer": "Godex G500 GZPL",
    "default_doc_printer": "Godex G500 GZPL",
    "default_encoding": "cp437",
    "pools": {
      "asset_label":  "Godex G500 GZPL",
      "label":        "Godex G500 GZPL",
      "barcode":      "Godex G500 GZPL",
      "receipt":      "EPSON TM-T82",
      "invoice":      "HP LaserJet Pro",
      "packing_slip": "Godex G500 GZPL",
      "kitchen":      "Printer Dapur"
    }
  }
}
```

Perubahan pada berkas ini dibaca saat bridge dijalankan ulang.

### Lewat Dashboard

`http://127.0.0.1:18212` → tab **Pengaturan** → **Printer Pool**. Perubahan
disimpan langsung ke `bridge_config.json` dan berlaku seketika.

### Lewat API

```bash
curl -X POST http://127.0.0.1:18212/api/printers/pools \
  -H "Content-Type: application/json" \
  -d '{
        "pools": {
          "asset_label": "Godex G500 GZPL",
          "invoice":     "HP LaserJet Pro"
        },
        "default_raw_printer": "Godex G500 GZPL",
        "default_doc_printer": "HP LaserJet Pro"
      }'
```

---

## 5.4 Kenapa Sebaiknya Memakai Alias, Bukan Nama Printer

Kode aplikasi web dipakai oleh banyak PC dengan printer berbeda-beda.

```js
// ❌ Terikat pada satu PC — pecah saat printer diganti atau di PC lain
await HardwareBridge.printPdf('Godex G500 GZPL', url);

// ✅ Alias — tiap PC memetakannya sendiri di bridge_config.json
await HardwareBridge.printPdf('asset_label', url);
```

Alias yang disarankan untuk lingkungan produksi:

| Alias | Dokumen |
|-------|---------|
| `asset_label` | Label aset / label produksi |
| `label`, `barcode` | Label barcode umum |
| `receipt` | Struk kasir thermal |
| `invoice` | Faktur A4 |
| `packing_slip` | Surat jalan |
| `kitchen` | Printer dapur (jaringan) |

---

## 5.5 Melihat Printer yang Terdeteksi

```bash
curl http://127.0.0.1:18212/api/printers
```

```json
{
  "status": "success",
  "default": "Godex G500 GZPL",
  "default_raw": "Godex G500 GZPL",
  "default_doc": "Godex G500 GZPL",
  "pools": { "asset_label": "Godex G500 GZPL" },
  "count": 4,
  "printers": [
    {
      "name": "Godex G500 GZPL",
      "is_default": true,
      "status": "Ready",
      "driver": "GoDEX G500 GZPL",
      "port": "USB001",
      "is_network": false,
      "ip": null,
      "network_port": 9100
    }
  ]
}
```

Di JavaScript:

```js
const { printers, pools, default: bawaan } = await HardwareBridge.getPrinters();
printers.forEach(p => console.log(p.name, p.port, p.driver));
```

Mengisi dropdown pilihan printer:

```js
async function isiDropdownPrinter(selector) {
    const el = document.querySelector(selector);
    const { printers, pools } = await HardwareBridge.getPrinters();

    el.innerHTML = '';

    const grupAlias = document.createElement('optgroup');
    grupAlias.label = 'Alias / Pool';
    Object.entries(pools).forEach(([alias, fisik]) => {
        if (!fisik) return;
        const o = document.createElement('option');
        o.value = alias;
        o.textContent = alias + '  →  ' + fisik;
        grupAlias.appendChild(o);
    });
    if (grupAlias.children.length) el.appendChild(grupAlias);

    const grupFisik = document.createElement('optgroup');
    grupFisik.label = 'Printer Fisik';
    printers.forEach(p => {
        const o = document.createElement('option');
        o.value = p.name;
        o.textContent = p.name + (p.is_default ? '  (bawaan)' : '');
        grupFisik.appendChild(o);
    });
    el.appendChild(grupFisik);
}
```

---

## 5.6 Printer Jaringan (TCP 9100)

```json
{
  "printers": {
    "network_printers": [
      { "name": "Printer Dapur", "ip": "192.168.1.200", "port": 9100, "type": "escpos" }
    ]
  }
}
```

Printer jaringan muncul di `/api/printers` dengan `is_network: true` dan
hanya dipakai pada jalur **RAW**. Untuk mencetak PDF ke printer jaringan,
pasanglah printer itu sebagai printer Windows/CUPS biasa lalu rujuk namanya.

---

## 5.7 Mengingat Pilihan Operator di Browser

```js
const KUNCI = 'printer_produksi';

function simpanPrinterPilihan(nama) {
    localStorage.setItem(KUNCI, nama);
}

function ambilPrinterPilihan(bawaan = 'asset_label') {
    return localStorage.getItem(KUNCI) || bawaan;
}

await HardwareBridge.printPdf(ambilPrinterPilihan(), url, 'Label_Produksi');
```
