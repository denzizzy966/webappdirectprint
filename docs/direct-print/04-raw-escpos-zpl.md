# 4. Cetak RAW: ESC/POS, ZPL, TSPL & Laci Kasir

Endpoint `POST /api/print/raw` mengirim byte **apa adanya** ke printer tanpa
melewati driver grafis. Inilah cara tercepat mencetak struk thermal dan label
barcode.

---

## 4.1 Format Data yang Diterima

`printer_manager.print_raw()` menentukan format `data` seperti ini:

| Urutan | Kondisi | Perlakuan |
|--------|---------|-----------|
| 1 | Mengandung `;base64,` (data URI) | Decode potongan setelah `;base64,` |
| 2 | Diawali `base64:` | Decode setelah prefiks |
| 3 | String valid Base64 (`validate=True`) | Di-decode menjadi byte |
| 4 | Sisanya | Di-encode memakai `printers.default_encoding` (bawaan `cp437`) |

> ⚠️ **Perangkap pada urutan ke-3:** teks pendek yang kebetulan terdiri dari
> karakter Base64 saja (mis. `TEST`, `AAAA`, `Halo`) akan **ikut di-decode** dan
> menghasilkan cetakan sampah. Untuk teks polos yang berisiko demikian, sisipkan
> newline (`\n`) atau perintah ESC di awal — atau kirim dengan prefiks
> `base64:` setelah Anda meng-encode sendiri.

---

## 4.2 ESC/POS — Struk Thermal (EPSON, POS-58, POS-80)

```js
const ESC = '\x1B', GS = '\x1D';

let s = '';
s += ESC + '@';                    // inisialisasi
s += ESC + 'a' + '\x01';           // rata tengah
s += GS  + '!' + '\x11';           // teks ukuran ganda
s += 'TOKO REJEKI JAYA\n';
s += GS  + '!' + '\x00';           // kembali normal
s += 'Jl. Pahlawan No. 123\n';
s += ESC + 'a' + '\x00';           // rata kiri
s += '-'.repeat(32) + '\n';
s += '1x Kopi Latte          25.000\n';
s += '1x Roti Bakar          18.000\n';
s += '-'.repeat(32) + '\n';
s += 'TOTAL:                 43.000\n';
s += '\n\n\n';
s += GS + 'V' + '\x42' + '\x00';   // potong kertas + feed

await HardwareBridge.printRaw('receipt', s, 'Struk_Kasir');
```

### Tabel Perintah ESC/POS yang Sering Dipakai

| Fungsi | Byte | Literal JavaScript |
|--------|------|---------------------|
| Inisialisasi | `1B 40` | `'\x1B@'` |
| Rata kiri / tengah / kanan | `1B 61 n` | `'\x1Ba\x00'` / `'\x1Ba\x01'` / `'\x1Ba\x02'` |
| Tebal nyala / mati | `1B 45 n` | `'\x1BE\x01'` / `'\x1BE\x00'` |
| Garis bawah nyala / mati | `1B 2D n` | `'\x1B-\x01'` / `'\x1B-\x00'` |
| Ukuran normal | `1D 21 00` | `'\x1D!\x00'` |
| Tinggi ganda | `1D 21 01` | `'\x1D!\x01'` |
| Lebar ganda | `1D 21 10` | `'\x1D!\x10'` |
| Lebar + tinggi ganda | `1D 21 11` | `'\x1D!\x11'` |
| Potong penuh | `1D 56 00` | `'\x1DV\x00'` |
| Potong sebagian | `1D 56 01` | `'\x1DV\x01'` |
| Potong + feed | `1D 56 42 00` | `'\x1DV\x42\x00'` |
| Buka laci pin 2 | `1B 70 00 19 FA` | `'\x1Bp\x00\x19\xFA'` |
| Buka laci pin 5 | `1B 70 01 19 FA` | `'\x1Bp\x01\x19\xFA'` |

Konstanta yang sama tersedia di sisi Python pada
[`app/printer/escpos_builder.py`](../../app/printer/escpos_builder.py)
(`EscPosBuilder.INIT`, `.ALIGN_CENTER`, `.CUT_FULL`, `.DRAWER_KICK`, dst.),
termasuk pembantu `qr_code()`, `barcode_code128()`, `row()`, dan `separator()`.

---

## 4.3 ZPL — Label Barcode (Zebra, Godex G500)

```js
const zpl = [
    '^XA',
    '^PW450',                                    // lebar cetak (dot)
    '^LL300',                                    // panjang label (dot)
    '^FO30,30^A0N,32,32^FDPRODUK SAMPEL^FS',
    '^FO30,75^A0N,24,24^FDBerat: 125.50 g^FS',
    '^FO30,110^BY2,2,60^BCN,60,Y,N,N^FDPRD-2026-001^FS',
    '^FO30,220^A0N,20,20^FDTanggal: 19/09/2026^FS',
    '^XZ'
].join('\n');

await HardwareBridge.printRaw('asset_label', zpl, 'Label_ZPL');
```

Pada 203 dpi, 1 mm ≈ 8 dot. Label 60 × 25 mm ≈ `^PW480` dan `^LL200`.

> Printer harus dipasang dengan **driver ZPL/raw pass-through** (mis.
> "Godex G500 GZPL"). Bila dipasang sebagai driver grafis Windows biasa, perintah
> ZPL akan tercetak sebagai teks mentah.

---

## 4.4 TSPL — Label (TSC, beberapa seri Godex)

```js
const tspl = [
    'SIZE 60 mm, 25 mm',
    'GAP 2 mm, 0 mm',
    'DIRECTION 1',
    'CLS',
    'TEXT 50,30,"3",0,1,1,"PRODUK PILIHAN"',
    'BARCODE 50,70,"128",60,1,0,2,2,"PRD-998877"',
    'PRINT 1',
    ''
].join('\n');

await HardwareBridge.printRaw('label', tspl, 'Label_TSPL');
```

---

## 4.5 Laci Kasir (Cash Drawer)

```js
// Cara 1 — endpoint khusus
await HardwareBridge.openCashDrawer('receipt', 2);   // pin 2 (paling umum), atau 5

// Cara 2 — sisipkan pulsa di akhir struk agar laci terbuka bersamaan cetak
s += '\x1Bp\x00\x19\xFA';
await HardwareBridge.printRaw('receipt', s, 'Struk_Dan_Laci');
```

REST:

```bash
curl -X POST http://127.0.0.1:18212/api/cashdrawer/open \
  -H "Content-Type: application/json" \
  -d '{"printer":"receipt","pin":2}'
```

---

## 4.6 Endpoint Uji Bawaan

Berguna untuk memastikan printer benar-benar merespons, tanpa menulis kode.

```bash
# Struk contoh ESC/POS
curl -X POST "http://127.0.0.1:18212/api/print/test-receipt?printer=receipt"

# Label barcode contoh ZPL
curl -X POST "http://127.0.0.1:18212/api/print/test-label?printer=asset_label"
```

Tersedia juga di **Dashboard Bridge** (`http://127.0.0.1:18212`) → kartu
**Sandbox** → tab **Struk ESC/POS** dan **RAW Kustom**.

---

## 4.7 Mengirim Byte Biner yang Rumit

Bila string JavaScript menyulitkan (mis. data gambar bitmap ESC/POS), susun byte
di `Uint8Array` lalu kirim sebagai Base64:

```js
function kirimRawBiner(printer, bytes, docName = 'Raw_Biner') {
    let biner = '';
    const CHUNK = 0x8000;
    for (let i = 0; i < bytes.length; i += CHUNK) {
        biner += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
    }
    return HardwareBridge.printRaw(printer, 'base64:' + btoa(biner), docName);
}

const perintah = new Uint8Array([0x1B, 0x40, 0x1B, 0x61, 0x01, /* ... */ 0x1D, 0x56, 0x00]);
await kirimRawBiner('receipt', perintah);
```

---

## 4.8 Printer Jaringan (TCP Port 9100)

Printer yang terdaftar di `bridge_config.json` pada `printers.network_printers`
dicetak lewat socket mentah, bukan spooler OS:

```json
{
  "printers": {
    "network_printers": [
      { "name": "Printer Dapur", "ip": "192.168.1.200", "port": 9100, "type": "escpos" }
    ],
    "pools": { "kitchen": "Printer Dapur" }
  }
}
```

```js
await HardwareBridge.printRaw('kitchen', pesananDapurEscPos, 'Order_Dapur');
```

> Jalur jaringan **hanya berlaku untuk `/api/print/raw`**. `print_pdf` dan
> `print_image` selalu melalui backend OS (Windows Spooler / CUPS), sehingga
> printer jaringan harus dipasang sebagai printer OS bila ingin dipakai untuk PDF.

---

## 4.9 Encoding Teks

`printers.default_encoding` di `bridge_config.json` menentukan encoding untuk
teks polos (bawaan `cp437`). Untuk karakter Indonesia yang tidak ada di cp437,
pilihan yang umum:

| Encoding | Cocok untuk |
|----------|-------------|
| `cp437` | Bawaan, aman untuk ASCII |
| `cp850` | Eropa Barat |
| `cp1252` | Windows Latin-1 |
| `utf-8` | Printer modern yang mendukung UTF-8 |

Karakter yang tidak terpetakan diganti (`errors="replace"`), bukan menggagalkan
job cetak.
