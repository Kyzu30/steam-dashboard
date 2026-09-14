"""Flask web client + đúng 3 API GET. Không bật debug khi chia sẻ Ngrok."""
import csv, io, json, math, sqlite3
from pathlib import Path
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from waitress import serve

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder='static')
app.config['DATABASE'] = ROOT/'data/games.db'
CORS(app, resources={r'/api/*': {'origins': '*'}}, supports_credentials=False)

@app.get('/')
def home():
    return app.send_static_file('index.html')

def connection():
    path = Path(app.config['DATABASE'])
    if not path.exists():
        raise FileNotFoundError('Chưa có dữ liệu. Hãy chạy prepare_data.py trước.')
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db

@app.errorhandler(ValueError)
def bad_input(exc):
    return jsonify(error=str(exc)), 400

@app.errorhandler(FileNotFoundError)
def missing_data(exc):
    return jsonify(error=str(exc)), 503

@app.errorhandler(sqlite3.Error)
def database_error(exc):
    app.logger.exception('Database error')
    return jsonify(error='Database không hợp lệ. Hãy nhập lại CSV bằng prepare_data.py.'), 503

def numeric(key, default=None, integer=False, minimum=0, maximum=None):
    raw = request.args.get(key, '')
    if raw == '': return default
    try:
        n = float(raw)
        if not math.isfinite(n) or n < minimum or (integer and not n.is_integer()) or (maximum is not None and n > maximum):
            raise ValueError()
        return int(n) if integer else n
    except ValueError:
        raise ValueError(f'Tham số {key} không hợp lệ.')

def filters():
    clauses, values = ['1=1'], []
    search = request.args.get('search', '').strip()
    if search:
        clauses.append('instr(lower(g.name), lower(?)) > 0'); values.append(search)
    genre = request.args.get('genre', '').strip()
    if genre:
        clauses.append('EXISTS (SELECT 1 FROM game_genres x WHERE x.game_id=g.id AND x.genre=?)'); values.append(genre)
    for low, high, column, integer in [('min_price','max_price','price',False), ('year_from','year_to','year',True)]:
        a, b = numeric(low, integer=integer), numeric(high, integer=integer)
        if a is not None and b is not None and a > b: raise ValueError(f'{low} phải nhỏ hơn hoặc bằng {high}.')
        for val, op in [(a, '>='), (b, '<=')]:
            if val is not None: clauses.append(f'g.{column} {op} ?'); values.append(val)
    mode = request.args.get('price_type', '')
    if mode not in ('', 'free', 'paid', 'unknown'): raise ValueError('price_type phải là free, paid hoặc unknown.')
    if mode: clauses.append({'free':'g.price=0','paid':'g.price>0','unknown':'g.price IS NULL'}[mode])
    return ' AND '.join(clauses), values

@app.get('/api/filters')
def get_filters():
    db = connection()
    try:
        genres = [r[0] for r in db.execute('SELECT DISTINCT genre FROM game_genres ORDER BY genre')]
        bounds = dict(db.execute('SELECT MIN(year) year_min, MAX(year) year_max, MAX(price) price_max FROM games').fetchone())
        return jsonify(genres=genres, bounds=bounds, metadata=json.loads(db.execute('SELECT content FROM metadata').fetchone()[0]))
    finally: db.close()

@app.get('/api/games')
def get_games():
    where, values = filters()
    sort = request.args.get('sort', 'name')
    sorts = {'name':'g.name COLLATE NOCASE, g.id', 'price_asc':'g.price IS NULL, g.price, g.id', 'newest':'g.year IS NULL, g.year DESC, g.id'}
    if sort not in sorts: raise ValueError('sort không hợp lệ.')
    page, size = numeric('page',1,True,1,1000000), numeric('page_size',12,True,1,100)
    fmt = request.args.get('format','json')
    if fmt not in ('json','csv'): raise ValueError('format phải là json hoặc csv.')
    db = connection()
    try:
        total = db.execute('SELECT COUNT(*) FROM games g WHERE '+where, values).fetchone()[0]
        query = 'SELECT g.* FROM games g WHERE '+where+' ORDER BY '+sorts[sort]
        if fmt == 'csv':
            # Export toàn bộ kết quả lọc, không chỉ trang hiện tại. Quote + ngăn công thức bảng tính.
            stream = io.StringIO(); writer = csv.writer(stream)
            writer.writerow(['id','name','release_date','year','price','genres','positive','negative'])
            for row in db.execute(query, values):
                writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in row])
            return Response('\ufeff'+stream.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=steam-games.csv'})
        rows = [dict(r) for r in db.execute(query+' LIMIT ? OFFSET ?', values+[size,(page-1)*size])]
        return jsonify(items=rows,total=total,page=page,page_size=size,pages=(total+size-1)//size)
    finally: db.close()

@app.get('/api/stats')
def get_stats():
    where, values = filters(); db = connection()
    try:
        summary = dict(db.execute('SELECT COUNT(*) total, AVG(g.price) average_price, SUM(g.price=0) free, SUM(g.price>0) paid, SUM(g.price IS NULL) unknown_price, SUM(g.year IS NULL) unknown_year FROM games g WHERE '+where, values).fetchone())
        for k in ('free','paid','unknown_price','unknown_year'): summary[k] = summary[k] or 0
        genres = [dict(r) for r in db.execute('SELECT x.genre label, COUNT(*) value FROM games g JOIN game_genres x ON g.id=x.game_id WHERE '+where+' GROUP BY x.genre ORDER BY value DESC, label LIMIT 10', values)]
        years = [dict(r) for r in db.execute('SELECT g.year label, COUNT(*) value FROM games g WHERE '+where+' AND g.year IS NOT NULL GROUP BY g.year ORDER BY g.year', values)]
        return jsonify(summary=summary,genres=genres,years=years,pricing=[{'label':label,'value':summary[key]} for label,key in [('Miễn phí','free'),('Trả phí','paid'),('Chưa rõ giá','unknown_price')]])
    finally: db.close()

if __name__ == '__main__':
    print('Steam Atlas: http://127.0.0.1:5000', flush=True)
    serve(app, host='127.0.0.1', port=5000)
