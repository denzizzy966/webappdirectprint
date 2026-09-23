# 🔌 Integrasi Laravel

Panduan memasang Hardware Bridge pada aplikasi Laravel (Blade, Livewire,
Vue/Inertia), untuk **direct print** maupun **timbangan digital**.

---

## 1. Pemasangan SDK

Salin SDK ke folder publik aplikasi:

```bash
cp static/js/hardware-bridge.js /path/ke/laravel/public/js/hardware-bridge.js
```

Muat di layout utama:

```blade
{{-- resources/views/layouts/app.blade.php --}}
<script src="{{ asset('js/hardware-bridge.js') }}"></script>
```

Salinan siap pakai juga tersedia di folder [`laravel/`](../../laravel/) pada
repositori ini, bersama `cara-pakai.html` sebagai halaman demo.

---

## 2. Simpan Alamat Server PDF di Konfigurasi

Jangan menyebar IP server ke berkas JavaScript.

```php
// config/app.php
'pdf_base_url' => env('PDF_BASE_URL', 'http://192.168.3.25/produksi/ProduksiPDF/'),
```

```
# .env
PDF_BASE_URL=http://192.168.3.25/produksi/ProduksiPDF/
```

```blade
{{-- layout --}}
<meta name="pdf-base-url" content="{{ config('app.pdf_base_url') }}">
```

```js
const PDF_BASE = document.querySelector('meta[name="pdf-base-url"]').content;
```

---

## 3. Cetak PDF dari URL Server

Pola paling umum untuk dokumen produksi yang sudah tersimpan di server.

```blade
@foreach ($daftarProduksi as $p)
  <tr>
    <td>{{ $p->no_produksi }}</td>
    <td>
      <button type="button" class="btn btn-sm btn-primary btn-cetak"
              data-no="{{ $p->no_produksi }}">🖨️ Cetak Label</button>
    </td>
  </tr>
@endforeach

<script>
document.querySelectorAll('.btn-cetak').forEach(btn => {
    btn.addEventListener('click', async () => {
        const no = btn.dataset.no;
        btn.disabled = true;
        try {
            const r = await HardwareBridge.printPdf(
                'asset_label',
                PDF_BASE + encodeURIComponent(no) + '.pdf',
                'Produksi_' + no,
                { dpi: 203 }
            );
            if (r.status !== 'success') throw new Error(r.detail || 'Gagal');
            HardwareBridge.toast('✅ Label ' + no + ' terkirim', '#16a34a');
        } catch (e) {
            HardwareBridge.toast('❌ ' + e.message, '#cd2b2b');
        } finally {
            btn.disabled = false;
        }
    });
});
</script>
```

Detail lengkap (encoding URL, batch, retry, jangkauan jaringan):
[../direct-print/03-pdf-dari-url.md](../direct-print/03-pdf-dari-url.md).

---

## 4. Cetak PDF yang Dibuat dompdf (Base64)

Dipakai bila berkas PDF berada di balik autentikasi, atau dibuat saat itu juga.

### Controller

```php
<?php
namespace App\Http\Controllers;

use App\Models\Produksi;
use Barryvdh\DomPDF\Facade\Pdf;

class CetakProduksiController extends Controller
{
    public function labelBase64(string $noProduksi)
    {
        $produksi = Produksi::where('no_produksi', $noProduksi)->firstOrFail();

        $pdf = Pdf::loadView('produksi.label', compact('produksi'))
                  ->setPaper([0, 0, 170.08, 70.87], 'landscape');  // 60 x 25 mm

        return response()->json([
            'nama'   => $noProduksi,
            'base64' => base64_encode($pdf->output()),
        ]);
    }
}
```

```php
// routes/web.php
Route::get('/produksi/{no}/label-base64', [CetakProduksiController::class, 'labelBase64'])
     ->middleware('auth');
```

### Browser

```js
async function cetakLabelDompdf(noProduksi, printer = 'asset_label') {
    const r = await fetch('/produksi/' + encodeURIComponent(noProduksi) + '/label-base64', {
        headers: { 'Accept': 'application/json' },
        credentials: 'same-origin'
    });
    if (!r.ok) throw new Error('Gagal mengambil PDF: HTTP ' + r.status);

    const { base64 } = await r.json();

    const res = await HardwareBridge.printPdf(
        printer,
        'base64:' + base64,
        'Label_' + noProduksi,
        { dpi: 203 }
    );
    if (res.status !== 'success') throw new Error(res.detail || 'Gagal mencetak');
    return res.result;
}
```

Alternatif render HTML di browser (tanpa mengubah backend):
[../direct-print/02-html-ke-base64.md](../direct-print/02-html-ke-base64.md).

---

## 5. Timbangan pada Form Livewire

`HardwareBridge.timbangKeInput()` memicu event `input` dan `change` dengan
`bubbles: true`, sehingga `wire:model` ikut diperbarui tanpa binding tambahan.

```blade
{{-- resources/views/livewire/transaksi-gudang.blade.php --}}
<div class="card p-4">
    <h4>Penerimaan Barang Gudang</h4>

    <div class="mb-3">
        <label class="form-label">Timbangan Aktif:</label>
        <select id="scale-selector" class="form-select"></select>
    </div>

    <div class="mb-3">
        <label class="form-label">Berat Bersih (gram):</label>
        <div class="input-group">
            <input type="text" id="input-berat" wire:model="berat_bersih" class="form-control" readonly>
            <button type="button" class="btn btn-success" onclick="ambilTimbangan()">⚖️ Timbang Stabil</button>
        </div>
        <small class="text-muted">
            Live: <b id="live-stream">--</b> &bull; Bridge: <span id="status-badge"></span>
        </small>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function () {
    HardwareBridge.attachIndicator('#status-badge');
    HardwareBridge.populateScaleSelect('#scale-selector', {
        onChange: s => HardwareBridge.liveWeight('#live-stream', { scale: s })
    });
    HardwareBridge.liveWeight('#live-stream');
});

function ambilTimbangan() {
    HardwareBridge.timbangKeInput('#input-berat', {
        scale:    document.querySelector('#scale-selector').value,
        alerts:   true,
        decimals: 2
    });
}
</script>
```

Panduan multi-timbangan lengkap: [../06-timbangan-serial.md](../06-timbangan-serial.md).

---

## 6. Vue / Inertia

```vue
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';

const berat   = ref(0);
const printer = ref('asset_label');
let stopLive  = null;

onMounted(() => {
    stopLive = window.HardwareBridge.liveWeight('#live-berat', { decimals: 2 });
});

onBeforeUnmount(() => {
    if (stopLive) stopLive();          // hentikan polling saat komponen dilepas
});

async function timbang() {
    const s = await window.HardwareBridge.pickScale();
    const r = await window.HardwareBridge.stableRead(s.name, 15);
    if (r.ok) berat.value = window.HardwareBridge.toGram(r.weight, r.unit, true);
}

async function cetak(noProduksi) {
    const base = document.querySelector('meta[name="pdf-base-url"]').content;
    const res  = await window.HardwareBridge.printPdf(
        printer.value,
        base + encodeURIComponent(noProduksi) + '.pdf',
        'Produksi_' + noProduksi,
        { dpi: 203 }
    );
    if (res.status !== 'success') throw new Error(res.detail);
}
</script>

<template>
  <div>
    <span id="live-berat">--</span>
    <button @click="timbang">⚖️ Timbang</button>
    <button @click="cetak('PRD-2026-0012')">🖨️ Cetak</button>
  </div>
</template>
```

> Jangan lupa memanggil fungsi penghenti dari `liveWeight()` pada
> `onBeforeUnmount`, supaya polling tidak terus berjalan di latar belakang.

---

## 7. Memeriksa Bridge Sebelum Dipakai

```js
async function bridgeAktif(timeoutMs = 1500) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
        return (await fetch('http://127.0.0.1:18212/api/status', { signal: ctrl.signal })).ok;
    } catch {
        return false;
    } finally {
        clearTimeout(t);
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    if (!await bridgeAktif()) {
        HardwareBridge.toast(
            '⚠️ Hardware Bridge belum berjalan di PC ini. Jalankan INSTALL.bat dari paket portable.',
            '#b45309'
        );
    }
});
```

---

## 8. Catatan Penerapan

| Hal | Catatan |
|-----|---------|
| HTTPS | Halaman `https://` memblokir panggilan ke `http://127.0.0.1`. Lihat [../08-troubleshooting.md](../08-troubleshooting.md) §4 |
| Alias printer | Pakai alias (`asset_label`, `receipt`) agar kode tidak terikat printer tiap PC |
| Sesi & cookie | Bridge **tidak** mengirim cookie saat mengunduh URL PDF. Untuk berkas terproteksi, pakai jalur Base64 |
| Versi SDK | Salin ulang `hardware-bridge.js` setiap kali bridge diperbarui |
| Nama job | Isi `doc_name` dengan nomor dokumen agar mudah ditelusuri di antrean printer dan `/api/print/history` |
