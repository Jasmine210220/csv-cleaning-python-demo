"""Fixed-scope CSV cleanup demo. Python 3.10+, standard library only."""
import argparse
import csv
import html
import json
import re
from datetime import datetime
from pathlib import Path

FIELDS = ['order_id', 'order_date', 'product', 'quantity']
DATE_FORMATS = [(r'\d{2}/\d{2}/\d{4}', '%d/%m/%Y'),
                (r'\d{4}-\d{2}-\d{2}', '%Y-%m-%d')]


def normalize_date(value):
    if not value:
        return value, 'MISSING_DATE'
    for pattern, fmt in DATE_FORMATS:
        if re.fullmatch(pattern, value):
            try:
                return datetime.strptime(value, fmt).date().isoformat(), 'OK'
            except ValueError:
                break
    return value, 'INVALID_DATE'


def process(paths):
    if not 1 <= len(paths) <= 2:
        raise ValueError('Provide 1 or 2 CSV files.')
    if sum(p.stat().st_size for p in paths) > 10_000_000:
        raise ValueError('Combined input exceeds 10 MB.')
    sources, seen, clean, audit = [], {}, [], []
    for path in paths:
        with path.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != FIELDS:
                raise ValueError(f'{path.name}: expected columns in this order: {FIELDS}')
            rows = list(reader)
        sources.append({'file': path.name, 'rows': rows})
    count = sum(len(s['rows']) for s in sources)
    if count > 5000:
        raise ValueError('Combined input exceeds 5,000 rows.')
    for source in sources:
        for line, row in enumerate(source['rows'], 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'{source["file"]}:{line}: malformed CSV row')
            key = row['order_id']
            if not key or key != key.strip():
                raise ValueError(f'{source["file"]}:{line}: missing or whitespace-padded order_id')
            if key in seen:
                if row != seen[key]:
                    raise ValueError(f'Conflicting duplicate {key}: review source data before processing.')
                audit.append({'source_file': source['file'], 'source_row': line,
                              'order_id': key, 'issue': 'DUPLICATE_REMOVED', 'original_date': row['order_date']})
                continue
            seen[key] = dict(row)
            date, status = normalize_date(row['order_date'])
            clean.append({**row, 'order_date': date, 'date_status': status})
            if status != 'OK':
                audit.append({'source_file': source['file'], 'source_row': line,
                              'order_id': key, 'issue': status, 'original_date': row['order_date']})
    report = {'input_files': len(paths), 'input_rows': count, 'output_rows': len(clean),
              'duplicates_removed': count-len(clean),
              'dates_normalized': sum(1 for row in clean if row['date_status']=='OK' and row['order_date'] != seen[row['order_id']]['order_date']),
              'date_issues': sum(row['date_status'] != 'OK' for row in clean),
              'data_origin': 'Synthetic demonstration data; no client records.'}
    return sources, clean, audit, report


def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def table(rows, fields):
    return '<table><thead><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in fields)+'</tr></thead><tbody>'+''.join(
        '<tr>'+''.join('<td class="'+('warning' if row.get('date_status','OK')!='OK' and key in ('order_date','date_status') else '')+'">'+html.escape(str(row.get(key,'')))+'</td>' for key in fields)+'</tr>' for row in rows)+'</tbody></table>'


def render_html(sources, clean, report, mode):
    before = mode == 'before'
    title = 'Before: two overlapping CSV exports' if before else 'After: one checked output file'
    body = ''.join('<section><h2>'+html.escape(s['file'])+' <small>'+str(len(s['rows']))+' rows</small></h2>'+table(s['rows'], FIELDS)+'</section>' for s in sources) if before else '<section><h2>cleaned.csv <small>'+str(len(clean))+' unique orders</small></h2>'+table(clean, FIELDS+['date_status'])+'</section>'
    notes = 'Duplicate orders: ORD-1003 and ORD-1006. Dates use DD/MM/YYYY or YYYY-MM-DD. One invalid date and one blank require review.' if before else 'Invalid and missing dates remain visible. Original values are preserved; nothing is guessed. Full source-row details are saved in audit.csv.'
    cards = [('INPUT FILES',report['input_files']),('INPUT ROWS',report['input_rows']),('OUTPUT ROWS',report['output_rows']),('DUPLICATES REMOVED',report['duplicates_removed'])]
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><title>CSV cleanup demo</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f4f7f5;color:#152c27;font:16px Arial,sans-serif}.page{width:1100px;margin:auto;padding:38px 42px}.eyebrow{font-weight:bold;font-size:13px;letter-spacing:2px;color:#367b5b}h1{font-size:34px;margin:14px 0 10px}p{color:#52665f;line-height:1.5}header{margin-bottom:24px}.cards{display:flex;gap:12px;margin:24px 0}.card{background:#e5eee8;border-radius:10px;padding:14px 18px;flex:1}.card b{display:block;font-size:28px;margin-top:7px}.card span{font-size:11px;letter-spacing:1px}section{background:white;border:1px solid #dbe5df;border-radius:12px;padding:18px 22px;margin:14px 0}h2{font-size:18px;margin:0 0 12px}small{float:right;font-size:13px;font-weight:normal;color:#63736c}table{width:100%;border-collapse:collapse;font-size:15px;text-align:left}th{background:#203e33;color:white;font-size:13px;padding:10px}td{padding:9px 10px;border-bottom:1px solid #e8eeea}td.warning{background:#fff1d4;color:#805009}footer{font-size:13px;color:#61736b;margin-top:18px}.note{border-left:4px solid #c79332;padding:10px 16px;background:#fff6e5;font-size:14px;line-height:1.5}.rules{font-size:15px;color:#355f4c}
    </style><main class="page"><header><div class="eyebrow">PYTHON DATA CLEANING / SYNTHETIC DEMO</div><h1>'''+title+'''</h1><div class="rules">01 Append matching tables &nbsp; / &nbsp; 02 Remove duplicate IDs &nbsp; / &nbsp; 03 Normalize dates</div></header>'''+('' if before else '<div class="cards">'+''.join('<div class="card"><span>'+label+'</span><b>'+str(value)+'</b></div>' for label,value in cards)+'</div>')+body+'<div class="note">'+notes+'</div><footer>Generated from actual CSV files by clean_csv.py. Synthetic data only; no customer results or performance claims.</footer></main></html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', nargs='+', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('results'))
    args = parser.parse_args()
    try:
        sources, clean, audit, report = process(args.inputs)
        # Never overwrite source files or previously generated deliverables.
        args.output.mkdir(parents=True, exist_ok=False)
        write_csv(args.output/'cleaned.csv', clean, FIELDS+['date_status'])
        write_csv(args.output/'audit.csv', audit, ['source_file','source_row','order_id','issue','original_date'])
        (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        for mode in ('before','after'):
            (args.output/f'{mode}.html').write_text(render_html(sources,clean,report,mode), encoding='utf-8')
        print(json.dumps(report, indent=2))
    except (ValueError, OSError, csv.Error) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
