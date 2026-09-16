import datetime
from typing import List, Tuple, Optional

class EscPosBuilder:
    """Helper untuk menyusun perintah printer thermal ESC/POS dalam bentuk bytes."""

    ESC = b'\x1b'
    GS = b'\x1d'

    INIT = ESC + b'@'
    CUT_FULL = GS + b'V\x00'
    CUT_PARTIAL = GS + b'V\x01'
    CUT_FEED = GS + b'V\x42\x00'
    DRAWER_KICK = ESC + b'p\x00\x19\xfa'
    DRAWER_KICK_PIN5 = ESC + b'p\x01\x19\xfa'

    ALIGN_LEFT = ESC + b'a\x00'
    ALIGN_CENTER = ESC + b'a\x01'
    ALIGN_RIGHT = ESC + b'a\x02'

    BOLD_ON = ESC + b'E\x01'
    BOLD_OFF = ESC + b'E\x00'

    UNDERLINE_ON = ESC + b'-\x01'
    UNDERLINE_OFF = ESC + b'-\x00'

    TXT_NORMAL = GS + b'!\x00'
    TXT_2HEIGHT = GS + b'!\x01'
    TXT_2WIDTH = GS + b'!\x10'
    TXT_4SQUARE = GS + b'!\x11'

    def __init__(self, encoding: str = 'cp437', char_width: int = 48):
        self.encoding = encoding
        self.char_width = char_width
        self.buffer = bytearray()
        self.initialize()

    def initialize(self) -> 'EscPosBuilder':
        self.buffer.extend(self.INIT)
        return self

    def text(self, s: str) -> 'EscPosBuilder':
        self.buffer.extend(s.encode(self.encoding, errors='replace'))
        return self

    def line(self, s: str = '') -> 'EscPosBuilder':
        if s:
            self.text(s)
        self.buffer.extend(b'\n')
        return self

    def feed(self, lines: int = 1) -> 'EscPosBuilder':
        self.buffer.extend(b'\n' * max(1, lines))
        return self

    def align(self, alignment: str = 'left') -> 'EscPosBuilder':
        a = alignment.lower()
        if a == 'center':
            self.buffer.extend(self.ALIGN_CENTER)
        elif a == 'right':
            self.buffer.extend(self.ALIGN_RIGHT)
        else:
            self.buffer.extend(self.ALIGN_LEFT)
        return self

    def bold(self, state: bool = True) -> 'EscPosBuilder':
        self.buffer.extend(self.BOLD_ON if state else self.BOLD_OFF)
        return self

    def size(self, scale: str = 'normal') -> 'EscPosBuilder':
        s = scale.lower()
        if s == 'double':
            self.buffer.extend(self.TXT_4SQUARE)
        elif s == '2height':
            self.buffer.extend(self.TXT_2HEIGHT)
        elif s == '2width':
            self.buffer.extend(self.TXT_2WIDTH)
        else:
            self.buffer.extend(self.TXT_NORMAL)
        return self

    def separator(self, char: str = '-') -> 'EscPosBuilder':
        self.line(char * self.char_width)
        return self

    def double_separator(self) -> 'EscPosBuilder':
        return self.separator('=')

    def row(self, col1: str, col2: str, col1_width: Optional[int] = None) -> 'EscPosBuilder':
        """Membuat 2 kolom (misal: Nama Barang di kiri, Harga di kanan)."""
        w = self.char_width
        if col1_width is None:
            col1_width = w - len(col2)
        pad = max(1, w - len(col1) - len(col2))
        self.line(f"{col1}{' ' * pad}{col2}")
        return self

    def cut(self, partial: bool = False) -> 'EscPosBuilder':
        self.feed(3)
        self.buffer.extend(self.CUT_PARTIAL if partial else self.CUT_FEED)
        return self

    def cash_drawer(self, pin: int = 2) -> 'EscPosBuilder':
        self.buffer.extend(self.DRAWER_KICK if pin == 2 else self.DRAWER_KICK_PIN5)
        return self

    def qr_code(self, data: str, size: int = 6) -> 'EscPosBuilder':
        """Menyisipkan perintah QR Code native ESC/POS (Model 2)."""
        data_bytes = data.encode('utf-8')
        length = len(data_bytes) + 3
        pL = length % 256
        pH = length // 256

        # 1. Select Model 2
        self.buffer.extend(self.GS + b'(k\x04\x00\x31\x41\x32\x00')
        # 2. Set module size (1-16)
        size_byte = bytes([max(1, min(16, size))])
        self.buffer.extend(self.GS + b'(k\x03\x00\x31\x43' + size_byte)
        # 3. Set error correction level (L=48, M=49, Q=50, H=51)
        self.buffer.extend(self.GS + b'(k\x03\x00\x31\x45\x31')
        # 4. Store data in symbol storage area
        self.buffer.extend(self.GS + b'(k' + bytes([pL, pH]) + b'\x31\x50\x30' + data_bytes)
        # 5. Print the symbol
        self.buffer.extend(self.GS + b'(k\x03\x00\x31\x51\x30')
        return self

    def barcode_code128(self, data: str, height: int = 60) -> 'EscPosBuilder':
        """Barcode Code 128 (GS k 73 len {B data)."""
        data_bytes = data.encode('ascii', errors='ignore')
        # GS h (height)
        self.buffer.extend(self.GS + b'h' + bytes([max(20, min(255, height))]))
        # GS w (width 2)
        self.buffer.extend(self.GS + b'w\x02')
        # GS H 2 (print text below)
        self.buffer.extend(self.GS + b'H\x02')
        # GS k 73 len {B data (Code Set B)
        payload = b'{B' + data_bytes
        self.buffer.extend(self.GS + b'k\x49' + bytes([len(payload)]) + payload)
        return self

    def to_bytes(self) -> bytes:
        return bytes(self.buffer)

    @classmethod
    def generate_sample_receipt(cls, store_name: str = "TOKO SERBA ADA", char_width: int = 42) -> bytes:
        """Menghasilkan contoh struk belanja pengujian printer thermal."""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        builder = cls(char_width=char_width)
        builder.align('center')
        builder.size('double').bold().line(store_name).bold(False).size('normal')
        builder.line("Jl. Jenderal Sudirman No. 123")
        builder.line("Telp: 0812-3456-7890")
        builder.separator()
        builder.align('left')
        builder.line(f"No. Trx : TRX-{int(datetime.datetime.now().timestamp())}")
        builder.line(f"Kasir   : Operator")
        builder.line(f"Waktu   : {now}")
        builder.double_separator()

        # Items
        builder.row("1x Kopi Arabika 250g", "45.000")
        builder.row("2x Roti Bakar Cokelat", "30.000")
        builder.row("1x Air Mineral 600ml", "5.000")
        builder.separator()

        # Totals
        builder.row("Subtotal:", "80.000")
        builder.row("PPN (11%):", "8.800")
        builder.bold().size('2height').row("TOTAL:", "88.800").size('normal').bold(False)
        builder.separator()
        builder.row("Tunai:", "100.000")
        builder.row("Kembalian:", "11.200")
        builder.separator()

        # QR & Footer
        builder.align('center')
        builder.feed(1)
        builder.qr_code("https://github.com/imTigger/webapp-hardware-bridge", size=5)
        builder.feed(1)
        builder.bold().line("TERIMA KASIH ATAS KUNJUNGAN ANDA").bold(False)
        builder.line("Barang yang sudah dibeli")
        builder.line("tidak dapat ditukar/dikembalikan")
        builder.cut()
        return builder.to_bytes()

    @classmethod
    def generate_sample_zpl(cls, title: str = "PRODUK SAMPEL", code: str = "PRD-2026-001", weight_str: str = "125.50 g") -> bytes:
        """Menghasilkan contoh label barcode ZPL (Zebra / Godex G500)."""
        zpl = f"""^XA
^PW450
^LL300
^FO30,30^A0N,32,32^FD{title}^FS
^FO30,75^A0N,24,24^FDBerat: {weight_str}^FS
^FO30,110^BY2,2,60^BCN,60,Y,N,N^FD{code}^FS
^FO30,220^A0N,20,20^FDTanggal: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}^FS
^XZ"""
        return zpl.encode('utf-8')
