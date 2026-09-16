import re
from typing import Dict, Any, Optional

PROTOCOLS = {
    'mettler': {
        'label': 'Mettler Toledo (MT-SICS)',
        'poll': 'SI\r\n',
        'stable': 'S\r\n',
        'continuous': 'SIR\r\n',
        'stop': '@\r\n',
        'zero': 'Z\r\n',
        'tare': 'T\r\n'
    },
    'shinko': {
        'label': 'Shinko / ViBRA',
        'poll': 'O9\r\n',
        'stable': 'O8\r\n',
        'continuous': 'O1\r\n',
        'stop': 'O0\r\n',
        'zero': 'Z\r\n',
        'tare': 'T\r\n'
    },
    'and': {
        'label': 'A&D Company',
        'poll': 'Q\r\n',
        'stable': 'S\r\n',
        'continuous': 'SIR\r\n',
        'stop': 'C\r\n',
        'zero': 'Z\r\n',
        'tare': 'TR\r\n'
    },
    'generic': {
        'label': 'Generic / Auto-detect',
        'poll': '\r\n',
        'stable': '\r\n',
        'continuous': '',
        'stop': '',
        'zero': 'Z\r\n',
        'tare': 'T\r\n'
    }
}

# Regex untuk mencocokkan string timbangan standar
WEIGHT_RE = re.compile(
    r'^\s*(?P<cmd>S|SI|SIR|T|TA)\s+(?P<st>[SD])\s+(?P<val>[-+]?[0-9]*\.?[0-9]+)\s*(?P<unit>\S+)?\s*$'
)
AD_RE = re.compile(
    r'^\s*(?P<st>ST|US|QT|OL)\s*,?\s*(?P<val>[-+]?[0-9]*\.?[0-9]+)?\s*(?P<unit>\S+)?\s*$'
)
SHINKO_RE = re.compile(
    r'^\s*(?P<sign>[-+])\s*(?P<val>[0-9]*\.?[0-9]+)\s+(?P<unit>[A-Za-z%]+)\s+(?P<st>[SUDM])\s*$'
)
PLAIN_RE = re.compile(
    r'^\s*(?P<sign>[-+])?\s*(?P<val>[0-9]*\.?[0-9]+)\s*'
    r'(?P<unit>g|kg|mg|ct|oz|ozt|dwt|GN|tl|tlt|tlh|mo|msg|tola|baht|%)?\s*$',
    re.IGNORECASE,
)

STATUS_MAP = {
    'I': 'Sibuk / Perintah tidak dapat dijalankan (S I)',
    '+': 'OVERLOAD — Beban melebihi kapasitas timbangan (S +)',
    '-': 'UNDERLOAD — Cek pan/piringan timbangan (S -)',
}

def parse_scale_line(line: str) -> Dict[str, Any]:
    """Mengurai (parse) sebaris teks dari timbangan digital menjadi format terstruktur."""
    cleaned = line.strip()
    if not cleaned:
        return {'kind': 'empty'}

    # 1. Mettler Toledo MT-SICS (e.g. "S S     125.40 g" atau "S D     125.40 g")
    m = WEIGHT_RE.match(line)
    if m:
        try:
            return {
                'kind': 'weight',
                'protocol': 'mettler',
                'weight': float(m.group('val')),
                'unit': m.group('unit') or 'g',
                'stable': m.group('st') == 'S',
                'raw': cleaned
            }
        except ValueError:
            pass

    # 2. A&D Protocol (e.g. "ST,+00125.40  g" atau "US,+00125.40  g")
    m = AD_RE.match(line)
    if m:
        if m.group('st') == 'OL' or m.group('val') is None:
            return {'kind': 'status', 'status': f'OVERLOAD ({cleaned})', 'raw': cleaned}
        try:
            return {
                'kind': 'weight',
                'protocol': 'and',
                'weight': float(m.group('val')),
                'unit': m.group('unit') or 'g',
                'stable': m.group('st') in ('ST', 'QT'),
                'raw': cleaned
            }
        except ValueError:
            pass

    # 3. Shinko / ViBRA (e.g. "+ 00125.40 g S")
    m = SHINKO_RE.match(line)
    if m:
        try:
            val = float(m.group('val'))
            if m.group('sign') == '-':
                val = -val
            return {
                'kind': 'weight',
                'protocol': 'shinko',
                'weight': val,
                'unit': m.group('unit').lower(),
                'stable': m.group('st') == 'S',
                'raw': cleaned
            }
        except ValueError:
            pass

    # Status khusus & ACK (Shinko A00, Mettler dsb)
    if re.fullmatch(r'A\d{2}', cleaned):
        return {'kind': 'ack', 'raw': cleaned}
    if re.fullmatch(r'E\d{1,2}', cleaned):
        return {'kind': 'status', 'status': f'Respons error timbangan ({cleaned})', 'raw': cleaned}
    t = cleaned.split()
    if len(t) == 2 and t[0] == 'S' and t[1] in STATUS_MAP:
        return {'kind': 'status', 'status': STATUS_MAP[t[1]], 'raw': cleaned}
    if len(t) == 2 and t[0] in ('Z', 'ZI') and t[1] == 'A':
        return {'kind': 'status', 'status': 'Zero Berhasil (Z A)', 'raw': cleaned}
    if len(t) == 2 and t[0] in ('T', 'TA') and t[1] == 'A':
        return {'kind': 'status', 'status': 'Tare Berhasil (T A)', 'raw': cleaned}

    # 4. Fallback: Plain / Generic weight string (e.g. "125.40 g" atau "125.40")
    m = PLAIN_RE.match(line)
    if m:
        try:
            val = float(m.group('val'))
            if m.group('sign') == '-':
                val = -val
            return {
                'kind': 'weight',
                'protocol': 'generic',
                'weight': val,
                'unit': m.group('unit') or 'g',
                'stable': True,
                'raw': cleaned
            }
        except ValueError:
            pass

    return {'kind': 'unknown', 'raw': line}
