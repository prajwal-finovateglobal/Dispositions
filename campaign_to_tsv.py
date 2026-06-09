"""
Read campaign_data JSON (one JSON object per line), decode meta_data and Unicode,
and print tab-separated lines like:
  +919005652028	SSF6054800	उषा देवी	243	छह सौ सत्तर	...
"""
import json
import re

def decode_unicode_escapes(s):
    """Decode literal \\uXXXX in string (for double-escaped Unicode from JSON)."""
    if not isinstance(s, str):
        return s
    return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)


def safe_json_load(line):
    try:
        return json.loads(line)
    except Exception as e:
        print(f"Could not parse line (starts with {line[:30]}...): {e}", file=__import__('sys').stderr)
        return None


def load_campaign_data(filename):
    data = []
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = safe_json_load(line)
            if item is None:
                continue
            if 'meta_data' in item and isinstance(item['meta_data'], str):
                try:
                    item['meta_data'] = json.loads(item['meta_data'])
                except Exception:
                    pass
            meta = item.get('meta_data')
            if isinstance(meta, dict):
                for k, v in meta.items():
                    if isinstance(v, str) and '\\u' in v:
                        meta[k] = decode_unicode_escapes(v)
            data.append(item)
    return data


TSV_COLS = [
    'contact_to', 'Uid', 'Name', 'campaign_id', 'EMI_In_Words',
    'dpdDaysWords', 'token_applicable', 'villageNameWords', 'overdueAmountWords'
]


def row_to_tsv(item):
    meta = item.get('meta_data', {}) if isinstance(item.get('meta_data'), dict) else {}
    parts = []
    for col in TSV_COLS:
        val = item.get('contact_to', '') if col == 'contact_to' else meta.get(col, '')
        parts.append(str(val) if val is not None else '')
    return '\t'.join(parts)


if __name__ == "__main__":
    import sys
    filename = sys.argv[1] if len(sys.argv) > 1 else "/Users/apple/Downloads/campaign_data-4.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else None  # optional output file

    data = load_campaign_data(filename)
    lines = [row_to_tsv(item) for item in data]

    if out_path:
        with open(out_path, "w", encoding="utf-8") as out:
            for line in lines:
                out.write(line + "\n")
        print(f"Wrote {len(lines)} rows to {out_path}", file=sys.stderr)
    else:
        for line in lines:
            print(line)
