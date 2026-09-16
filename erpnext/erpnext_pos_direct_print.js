/**
 * ERPNext POS & POS Awesome: Auto Direct Print & Auto Drawer Kick on Checkout
 * 
 * Cara Penggunaan di ERPNext POS:
 * Script ini mendengarkan event submit pembayaran POS untuk langsung:
 * 1. Menendang laci uang (Open Cash Drawer).
 * 2. Mencetak struk thermal ke printer USB kasir tanpa dialog browser.
 */

frappe.provide('frappe.pos');

$(document).on('pos_invoice_submitted', function(event, invoice_doc) {
    if (!invoice_doc) return;

    console.log('[HardwareBridge] Invoice disubmit:', invoice_doc.name);

    // 1. Buka laci kasir otomatis
    fetch('http://127.0.0.1:18212/api/cashdrawer/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ printer: 'receipt', pin: 2 })
    }).catch(() => {});

    // 2. Format Struk Thermal ESC/POS
    let receipt = "\x1b\x40"; // ESC @ (Init)
    receipt += "\x1b\x61\x01\x1d\x21\x11" + (invoice_doc.company || "STRUK KASIR") + "\n\x1d\x21\x00";
    receipt += "----------------------------------------\n";
    receipt += "\x1b\x61\x00";
    receipt += "No: " + invoice_doc.name + "\n";
    receipt += "Tgl: " + invoice_doc.posting_date + " " + (invoice_doc.posting_time || "") + "\n";
    receipt += "Kasir: " + (invoice_doc.owner || "") + "\n";
    receipt += "----------------------------------------\n";

    (invoice_doc.items || []).forEach(item => {
        const itemLine = `${item.qty}x ${item.item_name || item.item_code}`;
        const priceLine = Number(item.amount).toLocaleString('id-ID');
        const pad = Math.max(1, 40 - itemLine.length - priceLine.length);
        receipt += itemLine + " ".repeat(pad) + priceLine + "\n";
    });

    receipt += "----------------------------------------\n";
    receipt += "\x1b\x61\x02";
    receipt += "TOTAL: Rp " + Number(invoice_doc.grand_total).toLocaleString('id-ID') + "\n";
    if (invoice_doc.paid_amount) {
        receipt += "DIBAYAR: Rp " + Number(invoice_doc.paid_amount).toLocaleString('id-ID') + "\n";
        receipt += "KEMBALI: Rp " + Number(invoice_doc.change_amount || 0).toLocaleString('id-ID') + "\n";
    }
    receipt += "----------------------------------------\n";
    receipt += "\x1b\x61\x01";
    receipt += "Terima Kasih!\n\n\n";
    receipt += "\x1d\x56\x42\x00"; // Cut

    // 3. Kirim ke Bridge lokal di PC Kasir (menggunakan target pool 'receipt')
    fetch('http://127.0.0.1:18212/api/print/raw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            printer: 'receipt', // Target pool 'receipt' otomatis diarahkan ke printer kasir yang disetting
            data: receipt,
            doc_name: invoice_doc.name
        })
    }).then(res => res.json()).then(res => {
        console.log('[HardwareBridge] Status cetak POS:', res);
    }).catch(err => {
        console.warn('[HardwareBridge] Gagal mencetak struk POS:', err);
    });
});
