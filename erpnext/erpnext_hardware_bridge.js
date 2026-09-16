/**
 * ERPNext Client Script: Integrasi Hardware Bridge (Direct Print & Timbangan)
 *
 * Pasang script ini di ERPNext:
 * 1. Buka Desk ERPNext -> Ketik "Client Script" di Awesome Bar.
 * 2. Klik "New Client Script".
 * 3. Pilih DocType target: misal "POS Invoice" atau "Sales Invoice".
 * 4. Paste isi script ini dan klik Save & Enable.
 */

// URL Hardware Bridge (Default port 18212, kompatibel juga dengan 12212)
const BRIDGE_URL = window.HARDWARE_BRIDGE_URL || 'http://127.0.0.1:18212';

frappe.ui.form.on('POS Invoice', {
    refresh: function (frm) {
        // ────────────────────────────────────────────────────────────
        // 1. Tombol Direct Print (Silent Print)
        // ────────────────────────────────────────────────────────────
        if (!frm.is_new()) {
            frm.add_custom_button(__('🖨️ Cetak Struk (Direct Print)'), function () {
                directPrintInvoice(frm);
            }, __('Aksi Cepat'));

            frm.add_custom_button(__('💵 Buka Laci Kasir'), function () {
                openCashDrawer();
            }, __('Aksi Cepat'));
        }

        // ────────────────────────────────────────────────────────────
        // 2. Tombol Ambil Berat Timbangan Digital
        // ────────────────────────────────────────────────────────────
        frm.add_custom_button(__('⚖️ Timbang Item Aktif'), function () {
            fetchScaleWeight(frm);
        }, __('Aksi Cepat'));
    }
});

// Handler untuk child table Item pada POS Invoice / Sales Invoice
frappe.ui.form.on('POS Invoice Item', {
    items_add: function (frm, cdt, cdn) {
        // Otomatis tawarkan timbang jika item memerlukan berat
    },
    custom_btn_timbang: function (frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        frappe.show_alert({ message: __('Membaca timbangan...'), indicator: 'blue' });
        
        fetch(`${BRIDGE_URL}/api/scale/stable-read?timeout=4.0`, { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    frappe.model.set_value(cdt, cdn, 'qty', data.data.weight);
                    frappe.show_alert({
                        message: __('Berat terkunci: {0} {1}', [data.data.weight, data.data.unit]),
                        indicator: 'green'
                    });
                } else {
                    frappe.msgprint(__('Timbangan belum stabil: {0}', [data.message]));
                }
            })
            .catch(err => {
                frappe.msgprint(__('Gagal menghubungi Hardware Bridge di PC Anda. Pastikan bridge aktif di {0}', [BRIDGE_URL]));
            });
    }
});

/**
 * Mengirim perintah cetak langsung ke printer kasir tanpa memunculkan dialog browser.
 */
function directPrintInvoice(frm) {
    frappe.show_alert({ message: __('Mengirim ke printer kasir...'), indicator: 'blue' });

    // 1. Format Struk Thermal ESC/POS (Plain Text / Raw)
    const company = frm.doc.company || 'TOKO SAYA';
    const invoiceNo = frm.doc.name;
    const date = frm.doc.posting_date + ' ' + (frm.doc.posting_time || '');
    const grandTotal = format_currency(frm.doc.grand_total, frm.doc.currency);

    let receipt = "";
    receipt += "\x1b\x40";          // Init printer
    receipt += "\x1b\x61\x01";      // Rata tengah
    receipt += "\x1d\x21\x11";      // Dobel tinggi & lebar
    receipt += company + "\n";
    receipt += "\x1d\x21\x00";      // Normal
    receipt += "----------------------------------------\n";
    receipt += "\x1b\x61\x00";      // Rata kiri
    receipt += "No Inv : " + invoiceNo + "\n";
    receipt += "Waktu  : " + date + "\n";
    receipt += "Kasir  : " + frappe.session.user_fullname + "\n";
    receipt += "========================================\n";

    // Rincian Item
    (frm.doc.items || []).forEach(item => {
        const itemLine = `${item.qty}x ${item.item_name}`;
        const priceLine = format_currency(item.amount, frm.doc.currency);
        const pad = Math.max(1, 40 - itemLine.length - priceLine.length);
        receipt += itemLine + " ".repeat(pad) + priceLine + "\n";
    });

    receipt += "----------------------------------------\n";
    receipt += "\x1b\x61\x02";      // Rata kanan
    receipt += "TOTAL: " + grandTotal + "\n";
    receipt += "----------------------------------------\n";
    receipt += "\x1b\x61\x01";      // Rata tengah
    receipt += "Terima Kasih Atas Kunjungan Anda!\n";
    receipt += "\n\n\n";
    receipt += "\x1d\x56\x42\x00";  // Potong kertas (Cut)

    // 2. Kirim ke Bridge Lokal di PC Client
    fetch(`${BRIDGE_URL}/api/print/raw`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            printer: 'receipt', // Target pool 'receipt' (bisa dipetakan di Dashboard Bridge)
            data: receipt,
            doc_name: invoiceNo
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            frappe.show_alert({ message: __('Struk berhasil dicetak!'), indicator: 'green' });
        } else {
            frappe.msgprint(__('Gagal mencetak struk: {0}', [data.detail || data.message]));
        }
    })
    .catch(err => {
        frappe.msgprint(__('Hardware Bridge offline atau tidak dapat diakses di {0}', [BRIDGE_URL]));
    });
}

/**
 * Membuka laci kasir (Cash Drawer Kick)
 */
function openCashDrawer() {
    fetch(`${BRIDGE_URL}/api/cashdrawer/open`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ printer: 'receipt', pin: 2 })
    })
    .then(res => res.json())
    .then(data => {
        frappe.show_alert({ message: __('Laci kasir terbuka!'), indicator: 'green' });
    })
    .catch(err => {
        frappe.msgprint(__('Gagal membuka laci kasir. Cek koneksi bridge.'));
    });
}

/**
 * Membaca berat timbangan dan mengisi field form
 */
function fetchScaleWeight(frm) {
    frappe.show_alert({ message: __('Menimbang... Harap tunggu stabil'), indicator: 'blue' });
    fetch(`${BRIDGE_URL}/api/scale/stable-read?timeout=4.0`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                frappe.msgprint({
                    title: __('Hasil Timbangan'),
                    indicator: 'green',
                    message: `<b>Berat:</b> ${data.data.weight} ${data.data.unit}<br><b>Status:</b> Stabil (${data.elapsed_seconds} detik)`
                });
            } else {
                frappe.msgprint(__('Timbangan belum stabil: {0}', [data.message]));
            }
        })
        .catch(err => {
            frappe.msgprint(__('Hardware Bridge tidak terdeteksi di {0}', [BRIDGE_URL]));
        });
}
