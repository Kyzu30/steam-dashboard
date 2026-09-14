"""CSV Steam -> SQLite. Chạy từ bất kỳ thư mục nào."""
import argparse, csv, hashlib, json, math, sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def number(value, integer=False):
    try:
        n = float(str(value).strip())
        if not math.isfinite(n) or n < 0 or (integer and not n.is_integer()):
            return None
        return int(n) if integer else n
    except (ValueError, TypeError):
        return None

def date_value(value):
    for fmt in ('%b %d, %Y', '%Y-%m-%d', '%B %d, %Y', '%b %Y', '%Y'):
        try:
            return datetime.strptime(str(value).strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None

def prepare(source, output, demo=False):
    csv.field_size_limit(10_000_000)
    records, genre_rows, seen = [], [], set()
    report = dict(input_rows=0, dropped_invalid_identity=0, dropped_duplicate_id=0,
                  unknown_price=0, unknown_date=0, unknown_genre=0)
    with source.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, strict=True)

        if reader.fieldnames and "DiscountDLC count" in reader.fieldnames:
            headers = list(reader.fieldnames)
            index = headers.index("DiscountDLC count")
            headers[index:index + 1] = ["Discount", "DLC count"]
            reader.fieldnames = headers

        required = {'AppID', 'Name', 'Release date', 'Price', 'Genres'}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError('CSV thiếu cột: ' + ', '.join(sorted(missing)))
        for row in reader:
            report['input_rows'] += 1
            if None in row or any(row.get(k) is None for k in required):
                raise ValueError(f'CSV sai số cột tại dòng {reader.line_num}.')
            appid, name = number(row['AppID'], True), row['Name'].strip()
            if not appid or not name:
                report['dropped_invalid_identity'] += 1
                continue
            if appid in seen:
                report['dropped_duplicate_id'] += 1
                continue
            seen.add(appid)
            price, release = number(row['Price']), date_value(row['Release date'])
            genres = sorted(set(x.strip() for x in row['Genres'].split(',') if x.strip()))
            if price is None: report['unknown_price'] += 1
            if release is None: report['unknown_date'] += 1
            if not genres: report['unknown_genre'] += 1
            records.append((appid, name, release, int(release[:4]) if release else None,
                            price, ', '.join(genres), number(row.get('Positive'), True),
                            number(row.get('Negative'), True)))
            genre_rows.extend((appid, g) for g in genres)
    if not records:
        raise ValueError('Không có dòng hợp lệ; database cũ được giữ nguyên.')
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix('.tmp.db')
    temp.unlink(missing_ok=True)
    with sqlite3.connect(temp) as db:
        db.executescript('''CREATE TABLE games (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, release_date TEXT, year INTEGER,
          price REAL, genres TEXT, positive INTEGER, negative INTEGER);
          CREATE TABLE game_genres (game_id INTEGER, genre TEXT, PRIMARY KEY(game_id,genre));
          CREATE INDEX genre_index ON game_genres(genre,game_id);
          CREATE INDEX year_index ON games(year);
          CREATE INDEX price_index ON games(price);
          CREATE TABLE metadata (content TEXT);''')
        db.executemany('INSERT INTO games VALUES (?,?,?,?,?,?,?,?)', records)
        db.executemany('INSERT INTO game_genres VALUES (?,?)', genre_rows)
        report.update(output_rows=len(records), source_file=source.name,
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            imported_at=datetime.now(timezone.utc).isoformat(), demo=demo,
            source_url='Synthetic test fixture' if demo else 'https://www.kaggle.com/datasets/fronkongames/steam-games-dataset')
        db.execute('INSERT INTO metadata VALUES (?)', (json.dumps(report),))
    db.close()
    temp.replace(output)
    output.with_name('cleaning_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=ROOT/'data/raw/games.csv')
    parser.add_argument('--output', type=Path, default=ROOT/'data/games.db')
    parser.add_argument('--demo', action='store_true', help='Chỉ dùng cho CSV mẫu giả lập')
    args = parser.parse_args()
    prepare(args.input, args.output, args.demo)
