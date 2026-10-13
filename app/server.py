"""Skyx Gestão: API local, autenticação, SQLite e arquivos privados."""
from __future__ import annotations
import base64, hashlib, hmac, ipaddress, json, mimetypes, os, secrets, sqlite3, struct, sys, threading, time, urllib.request, urllib.parse, uuid
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('SKYX_DATA_DIR', ROOT / 'data'))
sys.path.insert(0, str(ROOT / 'data' / 'packages'))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'skyx.sqlite3'
LOCK = threading.RLock()
STAGES = ['Ideia', 'Análise', 'Planejamento', 'Desenvolvimento', 'Testes', 'Homologação', 'Aprovação', 'Publicação', 'Concluído']
TASK_STAGES = ['Backlog', 'A fazer', 'Em desenvolvimento', 'Em testes', 'Concluído']
ROLES = ['Administrador', 'Gestor', 'Programador', 'Cliente', 'Visualização']
KINDS = ['projects', 'demands', 'tasks', 'comments', 'documents', 'versions', 'environments', 'milestones', 'credentials']

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return uuid.uuid4().hex
class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try: return super().__exit__(*args)
        finally: self.close()
def connect():
    c = sqlite3.connect(DB, timeout=20, factory=ClosingConnection)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c
def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
def check_password(password, stored): return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)
def valid_password(value):
    if not isinstance(value, str) or len(value) < 12: raise ValueError('Use uma senha com pelo menos 12 caracteres.')
def public_user(row): return {k: row[k] for k in ['id', 'name', 'email', 'role', 'active']} | {'twoFactor': bool(row['totp']), 'projects': json.loads(row['projects'])}
def totp(secret, at=None):
    msg = struct.pack('>Q', int((at or time.time()) // 30))
    digest = hmac.new(base64.b32decode(secret), msg, hashlib.sha1).digest()
    offset = digest[-1] & 15
    return str((struct.unpack('>I', digest[offset:offset+4])[0] & 0x7fffffff) % 1000000).zfill(6)
def valid_totp(secret, code): return any(hmac.compare_digest(totp(secret, time.time()+i*30), str(code)) for i in [-1, 0, 1])
def cipher():
    from cryptography.fernet import Fernet
    path = DATA / 'vault.key'
    with LOCK:
        if not path.exists(): path.write_bytes(Fernet.generate_key())
    return Fernet(path.read_bytes())
def init():
    with connect() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT,email TEXT UNIQUE,password TEXT,role TEXT,active INTEGER DEFAULT 1,projects TEXT DEFAULT '[]',totp TEXT, pending_totp TEXT);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),expires REAL,csrf TEXT,ip TEXT,agent TEXT,created TEXT);
        CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,kind TEXT,project_id TEXT,payload TEXT,created TEXT,updated TEXT,author TEXT);
        CREATE INDEX IF NOT EXISTS records_kind ON records(kind);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,user_name TEXT,action TEXT,target TEXT,project_id TEXT,ip TEXT,created TEXT);
        CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,title TEXT,project_id TEXT,created TEXT);
        CREATE TABLE IF NOT EXISTS notification_reads(notification_id TEXT,user_id TEXT,PRIMARY KEY(notification_id,user_id));
        CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY,count INTEGER,until REAL);
        ''')
def record(row): return json.loads(row['payload']) | {'id': row['id'], 'projectId': row['project_id'], 'createdAt': row['created'], 'updatedAt': row['updated'], 'authorId': row['author']}
def add_record(c, kind, p, author, project=None):
    ident, stamp = uid(), now()
    c.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?)', (ident, kind, project, json.dumps(p, ensure_ascii=False), stamp, stamp, author))
    return ident
def can_project(user, project, c):
    if user['role'] in ['Administrador', 'Gestor']: return True
    if not project: return False
    row = c.execute("SELECT payload FROM records WHERE id=? AND kind='projects'", (project,)).fetchone()
    if not row: return False
    p = json.loads(row[0])
    return project in json.loads(user['projects']) or user['id'] in p.get('team', []) or p.get('owner') == user['id']
def can_read(user, row, c):
    return can_project(user, row['id'] if row['kind'] == 'projects' else row['project_id'], c) or (row['kind'] == 'demands' and row['author'] == user['id'])
def safe_record(row):
    r = record(row)
    for field in ['secret', 'content']: r.pop(field, None)
    if 'attachments' in r: r['attachments'] = [{k: v for k, v in a.items() if k != 'content'} for a in r['attachments']]
    return r
def seed(c, user):
    names = [('Sistema de Ocorrências', 'Segurança', 'Testes', 80, 5, 'Alta', 'OC'), ('Skyx Education', 'Educação', 'Desenvolvimento', 62, 18, 'Alta', 'ED'), ('Portal de Serviços Municipais', 'Prefeitura', 'Homologação', 92, 3, 'Média', 'PM'), ('Mobilidade Inteligente', 'Mobilidade', 'Planejamento', 25, 25, 'Média', 'MI'), ('Skyx Events', 'Eventos', 'Desenvolvimento', 48, -2, 'Urgente', 'EV'), ('Dashboard Operacional', 'Operações', 'Concluído', 100, -5, 'Baixa', 'DO')]
    for i, (name, area, status, progress, days, priority, code) in enumerate(names):
        p = add_record(c, 'projects', {'name': name, 'description': 'Projeto de demonstração para apresentar o fluxo de gestão da Sky X. Edite ou exclua para cadastrar os projetos reais.', 'objective': 'Centralizar operações e simplificar a experiência dos usuários.', 'area': area, 'status': status, 'progress': progress, 'priority': priority, 'owner': user, 'team': [user], 'start': (datetime.now()-timedelta(days=24)).date().isoformat(), 'deadline': (datetime.now()+timedelta(days=days)).date().isoformat(), 'nextStep': 'Validar entregas com a equipe responsável', 'code': code, 'demo': True}, user)
        for j, title in enumerate(['Estruturar requisitos e arquitetura', 'Implementar autenticação', 'Desenvolver dashboard', 'Validar fluxos e testes']):
            add_record(c, 'tasks', {'name': title, 'status': TASK_STAGES[min(4, (i+j)%5)], 'priority': priority, 'owner': user, 'deadline': (datetime.now()+timedelta(days=days+j)).date().isoformat(), 'progress': 100 if (i+j)%5 == 4 else 25, 'description': 'Tarefa de demonstração.', 'estimatedHours': 8}, user, p)
        add_record(c, 'milestones', {'name': 'Demanda e requisitos definidos', 'date': (datetime.now()-timedelta(days=20)).date().isoformat(), 'done': True}, user, p)
        add_record(c, 'milestones', {'name': 'Entrega e validação final', 'date': (datetime.now()+timedelta(days=days)).date().isoformat(), 'done': status == 'Concluído'}, user, p)
    for name, area, priority in [('Assistente para atendimento interno', 'Operações', 'Alta'), ('Integração com serviços municipais', 'Prefeitura', 'Média'), ('Aplicativo de inspeção em campo', 'Segurança', 'Alta')]:
        add_record(c, 'demands', {'name': name, 'description': 'Demanda de demonstração para avaliação técnica.', 'area': area, 'priority': priority, 'status': 'Em análise', 'type': 'Novo sistema', 'requester': user}, user)

class APIError(Exception):
    def __init__(self, status, message): self.status, self.message = status, message

class Handler(BaseHTTPRequestHandler):
    server_version = 'Skyx'
    def log_message(self, fmt, *args): pass
    def reply(self, status, body, headers=None):
        data = json.dumps(body, ensure_ascii=False).encode() if not isinstance(body, bytes) else body
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'same-origin')
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)
    def body(self):
        size = int(self.headers.get('Content-Length', 0))
        if size > 12_000_000: raise APIError(413, 'Arquivo muito grande. Limite de 8 MB.')
        try:
            data = json.loads(self.rfile.read(size) or '{}')
            if not isinstance(data, dict): raise ValueError()
            return data
        except (ValueError, UnicodeError): raise APIError(400, 'JSON inválido.')
    def session(self, c):
        cookies = dict(part.strip().split('=', 1) for part in self.headers.get('Cookie', '').split(';') if '=' in part)
        token = cookies.get('skyx_session', '')
        s = c.execute('SELECT * FROM sessions WHERE token=? AND expires>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        if not s: raise APIError(401, 'Sua sessão expirou. Entre novamente.')
        user = c.execute('SELECT * FROM users WHERE id=? AND active=1', (s['user_id'],)).fetchone()
        if not user: raise APIError(401, 'Acesso desativado.')
        if self.command != 'GET' and not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), s['csrf']): raise APIError(403, 'Token de segurança inválido.')
        return user, s
    def audit(self, c, u, action, target='', project=None):
        c.execute('INSERT INTO audit(user_id,user_name,action,target,project_id,ip,created) VALUES(?,?,?,?,?,?,?)', (u['id'], u['name'], action, target, project, self.client_address[0], now()))
    def notify(self, c, title, project=None): c.execute('INSERT INTO notifications VALUES(?,?,?,?)', (uid(), title, project, now()))
    def do_GET(self): self.handle_request()
    def do_POST(self): self.handle_request()
    def do_PATCH(self): self.handle_request()
    def do_DELETE(self): self.handle_request()
    def handle_request(self):
        try:
            if not self.path.startswith('/api/'):
                if self.command != 'GET': raise APIError(405, 'Método inválido.')
                self.static(); return
            if self.command != 'GET':
                origin = self.headers.get('Origin')
                if origin and urllib.parse.urlparse(origin).netloc != self.headers.get('Host'): raise APIError(403, 'Origem não autorizada.')
            with LOCK, connect() as c: self.api(c)
        except APIError as exc: self.reply(exc.status, {'error': exc.message})
        except (ValueError, KeyError, TypeError) as exc: self.reply(400, {'error': str(exc) or 'Dados inválidos.'})
        except sqlite3.IntegrityError: self.reply(409, {'error': 'Já existe um registro com estes dados.'})
        except Exception as exc:
            print(type(exc).__name__, str(exc), file=sys.stderr)
            self.reply(500, {'error': 'Não foi possível concluir. Consulte o log do servidor.'})
    def static(self):
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        file = (ROOT / 'web' / (path.lstrip('/') or 'index.html')).resolve()
        if not file.is_relative_to((ROOT / 'web').resolve()) or not file.is_file(): raise APIError(404, 'Arquivo não encontrado.')
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(file)[0] or 'application/octet-stream')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(file.stat().st_size))
        self.end_headers(); self.wfile.write(file.read_bytes())
    def api(self, c):
        path = urllib.parse.urlparse(self.path).path
        method = self.command
        b = self.body() if method in ['POST', 'PATCH'] else {}
        if path == '/api/bootstrap' and method == 'GET':
            self.reply(200, {'setupRequired': c.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0}); return
        if path == '/api/setup' and method == 'POST':
            if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]: raise APIError(409, 'A configuração inicial já foi concluída.')
            valid_password(b.get('password'))
            email = str(b.get('email', '')).strip().lower()
            if '@' not in email or not b.get('name', '').strip(): raise ValueError('Informe nome e e-mail válidos.')
            ident = uid()
            c.execute('INSERT INTO users(id,name,email,password,role) VALUES(?,?,?,?,?)', (ident, b['name'].strip(), email, password_hash(b['password']), 'Administrador'))
            if b.get('demo'): seed(c, ident)
            self.reply(201, {'ok': True}); return
        if path == '/api/login' and method == 'POST':
            key = self.client_address[0] + ':' + str(b.get('email', '')).lower()
            attempt = c.execute('SELECT * FROM attempts WHERE key=?', (key,)).fetchone()
            if attempt and attempt['count'] >= 5 and attempt['until'] > time.time(): raise APIError(429, 'Muitas tentativas. Aguarde 15 minutos.')
            u = c.execute('SELECT * FROM users WHERE email=? AND active=1', (str(b.get('email', '')).strip().lower(),)).fetchone()
            if not u or not check_password(str(b.get('password', '')), u['password']) or (u['totp'] and not valid_totp(u['totp'], b.get('code', ''))):
                count = attempt['count']+1 if attempt and attempt['until'] > time.time() else 1
                c.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?)', (key, count, time.time()+900)); c.commit()
                raise APIError(401, 'E-mail, senha ou código de autenticação inválido.')
            c.execute('DELETE FROM attempts WHERE key=?', (key,))
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            c.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
            c.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), u['id'], time.time()+28800, csrf, self.client_address[0], self.headers.get('User-Agent', '')[:300], now()))
            self.audit(c, u, 'Login realizado')
            secure = '; Secure' if os.environ.get('SKYX_SECURE_COOKIE') == '1' else ''
            self.reply(200, {'user': public_user(u), 'csrf': csrf}, {'Set-Cookie': f'skyx_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{secure}'}); return
        u, session = self.session(c)
        manager = u['role'] in ['Administrador', 'Gestor']
        writer = u['role'] in ['Administrador', 'Gestor', 'Programador']
        if path == '/api/me': self.reply(200, {'user': public_user(u), 'csrf': session['csrf']}); return
        if path == '/api/logout' and method == 'POST':
            c.execute('DELETE FROM sessions WHERE token=?', (session['token'],))
            self.reply(200, {'ok': True}, {'Set-Cookie': 'skyx_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict'}); return
        if path == '/api/state' and method == 'GET':
            for row in c.execute("SELECT * FROM records WHERE kind IN ('projects','tasks')").fetchall():
                p = record(row)
                deadline = p.get('deadline')
                if deadline and p.get('status') != 'Concluído':
                    remaining = (datetime.strptime(deadline, '%Y-%m-%d').date()-datetime.now().date()).days
                    if remaining <= 7:
                        title = ('Prazo vencido: ' if remaining < 0 else 'Prazo próximo: ') + p['name']
                        alert_id = 'deadline:'+p['id']+':'+deadline+('late' if remaining < 0 else 'soon')
                        c.execute('INSERT OR IGNORE INTO notifications VALUES(?,?,?,?)', (alert_id, title, row['id'] if row['kind']=='projects' else row['project_id'], now()))
            result = {k: [] for k in KINDS}
            for row in c.execute('SELECT * FROM records ORDER BY created DESC').fetchall():
                if can_read(u, row, c) and (row['kind'] != 'credentials' or writer): result[row['kind']].append(safe_record(row))
            users = c.execute('SELECT * FROM users').fetchall()
            relevant = {u['id']}
            for p in result['projects']: relevant.update(p.get('team', [])); relevant.add(p.get('owner'))
            result['users'] = [public_user(x) if u['role'] == 'Administrador' else {k: x[k] for k in ['id', 'name', 'role', 'active']} for x in users if manager or x['id'] in relevant]
            result['notifications'] = [dict(x) for x in c.execute('SELECT n.*, EXISTS(SELECT 1 FROM notification_reads r WHERE r.notification_id=n.id AND r.user_id=?) AS read FROM notifications n ORDER BY created DESC LIMIT 200', (u['id'],)).fetchall() if manager or can_project(u, x['project_id'], c)]
            result['audit'] = [dict(x) for x in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 300').fetchall() if manager or can_project(u, x['project_id'], c)]
            result['serverTime'] = now()
            result['integrations'] = {'ai': bool(os.environ.get('SKYX_AI_URL') and os.environ.get('SKYX_AI_KEY')), 'git': False}
            self.reply(200, result); return
        if path == '/api/notifications/read' and method == 'POST':
            for row in c.execute('SELECT * FROM notifications').fetchall():
                if manager or can_project(u, row['project_id'], c): c.execute('INSERT OR IGNORE INTO notification_reads VALUES(?,?)', (row['id'], u['id']))
            self.reply(200, {'ok': True}); return
        if path == '/api/users' and method == 'POST':
            if u['role'] != 'Administrador': raise APIError(403, 'Apenas administradores gerenciam usuários.')
            valid_password(b.get('password'))
            if b.get('role') not in ROLES or '@' not in b.get('email', '') or not b.get('name', '').strip(): raise ValueError('Revise os dados do usuário.')
            ident = uid()
            c.execute('INSERT INTO users(id,name,email,password,role,projects) VALUES(?,?,?,?,?,?)', (ident, b['name'], b['email'].lower().strip(), password_hash(b['password']), b['role'], json.dumps(b.get('projects', []))))
            self.audit(c, u, 'Usuário criado', b['name']); self.reply(201, {'id': ident}); return
        if path.startswith('/api/users/') and method == 'PATCH':
            if u['role'] != 'Administrador': raise APIError(403, 'Acesso restrito ao administrador.')
            ident = path.split('/')[-1]
            old = c.execute('SELECT * FROM users WHERE id=?', (ident,)).fetchone()
            if not old: raise APIError(404, 'Usuário não encontrado.')
            role = b.get('role', old['role']); active = int(bool(b.get('active', old['active'])))
            if role not in ROLES: raise ValueError('Perfil inválido.')
            if ident == u['id'] and (role != 'Administrador' or not active): raise ValueError('Você não pode remover o próprio acesso de administrador.')
            c.execute('UPDATE users SET role=?,active=?,projects=? WHERE id=?', (role, active, json.dumps(b.get('projects', json.loads(old['projects']))), ident))
            if b.get('password'):
                valid_password(b['password']); c.execute('UPDATE users SET password=? WHERE id=?', (password_hash(b['password']), ident))
            c.execute('DELETE FROM sessions WHERE user_id=?', (ident,))
            self.audit(c, u, 'Permissões de usuário alteradas', old['name']); self.reply(200, {'ok': True}); return
        if path == '/api/security' and method == 'GET':
            sessions = [dict(x) for x in c.execute('SELECT token,ip,agent,created,expires FROM sessions WHERE user_id=? AND expires>?', (u['id'], time.time())).fetchall()]
            for s in sessions: s['current'] = s['token'] == session['token']; s.pop('token')
            backups = sorted((DATA / 'backups').glob('*.sqlite3')) if (DATA / 'backups').exists() else []
            self.reply(200, {'sessions': sessions, 'twoFactor': bool(u['totp']), 'lastBackup': datetime.fromtimestamp(backups[-1].stat().st_mtime, timezone.utc).isoformat() if backups else None}); return
        if path == '/api/security' and method == 'POST':
            action = b.get('action')
            if action == 'revoke': c.execute('DELETE FROM sessions WHERE user_id=? AND token<>?', (u['id'], session['token']))
            elif action == 'password':
                if not check_password(b.get('current', ''), u['password']): raise ValueError('Senha atual incorreta.')
                valid_password(b.get('password')); c.execute('UPDATE users SET password=? WHERE id=?', (password_hash(b['password']), u['id']))
                c.execute('DELETE FROM sessions WHERE user_id=? AND token<>?', (u['id'], session['token']))
            elif action == 'setup2fa':
                if u['totp']: raise ValueError('A autenticação em dois fatores já está ativa.')
                secret = base64.b32encode(secrets.token_bytes(20)).decode()
                c.execute('UPDATE users SET pending_totp=? WHERE id=?', (secret, u['id']))
                self.reply(200, {'secret': secret, 'uri': f'otpauth://totp/Skyx:{urllib.parse.quote(u["email"])}?secret={secret}&issuer=Skyx'}); return
            elif action == 'confirm2fa':
                if not u['pending_totp'] or not valid_totp(u['pending_totp'], b.get('code', '')): raise ValueError('Código inválido.')
                c.execute('UPDATE users SET totp=pending_totp,pending_totp=NULL WHERE id=?', (u['id'],))
            elif action == 'disable2fa':
                if not u['totp'] or not valid_totp(u['totp'], b.get('code', '')) or not check_password(b.get('current', ''), u['password']): raise ValueError('Senha ou código inválido.')
                c.execute('UPDATE users SET totp=NULL,pending_totp=NULL WHERE id=?', (u['id'],))
            else: raise ValueError('Ação inválida.')
            self.audit(c, u, 'Configuração de segurança: '+action); self.reply(200, {'ok': True}); return
        if path == '/api/backup' and method == 'POST':
            if u['role'] != 'Administrador': raise APIError(403, 'Acesso restrito ao administrador.')
            backup(); self.audit(c, u, 'Backup manual realizado'); self.reply(200, {'ok': True}); return
        if path == '/api/assistant' and method == 'POST':
            if not writer: raise APIError(403, 'Acesso restrito à equipe técnica.')
            prompt = str(b.get('prompt', '')).strip()[:6000]
            if not prompt: raise ValueError('Descreva a análise desejada.')
            projects = [record(r) for r in c.execute("SELECT * FROM records WHERE kind='projects'").fetchall() if can_read(u, r, c)]
            tasks = [record(r) for r in c.execute("SELECT * FROM records WHERE kind='tasks'").fetchall() if can_read(u, r, c)]
            overdue = [t for t in tasks if t.get('deadline', '9999') < datetime.now().date().isoformat() and t.get('status') != 'Concluído']
            if os.environ.get('SKYX_AI_URL') and os.environ.get('SKYX_AI_KEY'):
                url = os.environ['SKYX_AI_URL']
                if not url.startswith('https://'): raise ValueError('A URL da IA deve usar HTTPS.')
                payload = {'model': os.environ.get('SKYX_AI_MODEL', ''), 'messages': [{'role': 'system', 'content': 'Você é o assistente de gestão Skyx. Responda em português. Não invente dados. Dados autorizados: '+json.dumps({'projects': projects, 'tasks': tasks}, ensure_ascii=False)}, {'role': 'user', 'content': prompt}]}
                req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer '+os.environ['SKYX_AI_KEY']})
                try:
                    with urllib.request.urlopen(req, timeout=40) as response: answer = json.load(response)['choices'][0]['message']['content']
                except Exception: raise APIError(502, 'O provedor de IA não respondeu. Verifique a configuração no servidor.')
                mode = 'IA conectada'
            else:
                answer = f'VISÃO DO PORTFÓLIO\n{len(projects)} projetos acessíveis • {len(tasks)} tarefas • {len(overdue)} tarefas em atraso.\n\nPRIORIDADES\n' + ('\n'.join('• '+t['name']+' — prazo '+t['deadline'] for t in overdue[:8]) or 'Nenhuma tarefa em atraso neste momento.') + '\n\nPLANO INICIAL PARA SUA DEMANDA\n1. Validar o objetivo e os critérios de aceite.\n2. Mapear usuários, permissões e dados necessários.\n3. Elaborar o protótipo e revisar com o solicitante.\n4. Implementar os módulos e as integrações.\n5. Executar testes e homologação.\n6. Publicar e acompanhar os indicadores.\n\nEste plano é um modelo por regras. Conecte um provedor nas variáveis do servidor para análise generativa específica da ideia.'
                mode = 'Análise local por regras'
            self.audit(c, u, 'Assistente consultado'); self.reply(200, {'answer': answer, 'mode': mode}); return
        if path.startswith('/api/monitor/') and method == 'POST':
            if not manager: raise APIError(403, 'Apenas gestores verificam serviços.')
            row = c.execute("SELECT * FROM records WHERE id=? AND kind='environments'", (path.split('/')[-1],)).fetchone()
            if not row: raise APIError(404, 'Ambiente não encontrado.')
            p = record(row); parsed = urllib.parse.urlparse(p.get('url', ''))
            allowed = os.environ.get('SKYX_MONITOR_HOSTS', '').split(',')
            if parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.username or parsed.port not in [None, 443]: raise ValueError('Autorize o domínio HTTPS em SKYX_MONITOR_HOSTS no servidor antes da verificação.')
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *args): return None
            start = time.monotonic()
            try:
                with urllib.request.build_opener(NoRedirect).open(urllib.request.Request(p['url'], method='HEAD'), timeout=8) as res: status = 'Online' if res.status < 400 else 'Offline'
            except Exception: status = 'Indisponível'
            payload = json.loads(row['payload']) | {'serverStatus': status, 'checkedAt': now(), 'latency': round((time.monotonic()-start)*1000)}
            c.execute('UPDATE records SET payload=?,updated=? WHERE id=?', (json.dumps(payload), now(), row['id']))
            self.audit(c, u, 'Disponibilidade verificada', p.get('name'), row['project_id'])
            self.reply(200, payload); return
        parts = path.strip('/').split('/')
        if len(parts) < 2 or parts[1] not in KINDS: raise APIError(404, 'Rota não encontrada.')
        kind = parts[1]; ident = parts[2] if len(parts) > 2 else None
        old = c.execute('SELECT * FROM records WHERE id=? AND kind=?', (ident, kind)).fetchone() if ident else None
        if ident and (not old or not can_read(u, old, c)): raise APIError(404, 'Registro não encontrado.')
        if len(parts) == 4 and parts[3] == 'download' and kind == 'documents' and method == 'GET':
            p = record(old)
            self.audit(c, u, 'Documento baixado', p.get('name'), old['project_id'])
            data = base64.b64decode(p['content']); self.reply(200, data, {'Content-Type': 'application/octet-stream', 'Content-Disposition': "attachment; filename*=UTF-8''"+urllib.parse.quote(p['name'])}); return
        if len(parts) == 5 and parts[3] == 'attachments' and method == 'GET':
            attachment = next((a for a in record(old).get('attachments', []) if a['id'] == parts[4]), None)
            if not attachment: raise APIError(404, 'Anexo não encontrado.')
            self.audit(c, u, 'Anexo baixado', attachment['name'], old['project_id'])
            self.reply(200, base64.b64decode(attachment['content']), {'Content-Type': 'application/octet-stream', 'Content-Disposition': "attachment; filename*=UTF-8''"+urllib.parse.quote(attachment['name'])}); return
        if len(parts) == 4 and parts[3] == 'reveal' and kind == 'credentials' and method == 'POST':
            if not writer: raise APIError(403, 'Acesso restrito à equipe técnica.')
            self.audit(c, u, 'Credencial consultada', record(old).get('name'), old['project_id'])
            self.reply(200, {'secret': cipher().decrypt(record(old)['secret'].encode()).decode()}); return
        if method not in ['POST', 'PATCH', 'DELETE']: raise APIError(405, 'Método não permitido.')
        if not writer and not (kind == 'demands' and method == 'POST' and u['role'] == 'Cliente') and not (kind == 'comments' and method == 'POST' and u['role'] == 'Cliente'): raise APIError(403, 'Seu perfil permite apenas acompanhamento.')
        if kind in ['projects', 'environments', 'credentials'] and not manager:
            if not (kind == 'projects' and method == 'PATCH' and u['role'] == 'Programador' and set(b).issubset({'status', 'progress', 'nextStep'})):
                raise APIError(403, 'Esta operação exige um gestor.')
        if method == 'DELETE':
            if not manager and (not old or old['author'] != u['id']): raise APIError(403, 'Você só pode excluir os próprios registros.')
            if kind == 'projects': c.execute('DELETE FROM records WHERE project_id=?', (ident,))
            c.execute('DELETE FROM records WHERE id=?', (ident,))
            self.audit(c, u, 'Excluído: '+kind, record(old).get('name', ''), old['project_id'] or ident)
            self.reply(200, {'ok': True}); return
        if method == 'PATCH' and not old: raise APIError(404, 'Registro não encontrado.')
        project = old['project_id'] if old else b.get('projectId')
        if kind not in ['projects', 'demands']:
            if not project or not c.execute("SELECT id FROM records WHERE id=? AND kind='projects'", (project,)).fetchone() or not can_project(u, project, c): raise APIError(403, 'Selecione um projeto autorizado.')
        if kind == 'demands' and method == 'PATCH' and not manager: raise APIError(403, 'Apenas gestores avaliam demandas.')
        p = (json.loads(old['payload']) if old else {}) | {k: v for k, v in b.items() if k not in ['id', 'projectId', 'authorId', 'createdAt', 'updatedAt']}
        new_attachments = p.pop('newAttachments', [])
        if new_attachments:
            if kind not in ['demands', 'tasks']: raise ValueError('Anexos disponíveis em demandas e tarefas.')
            previous = json.loads(old['payload']).get('attachments', []) if old else []
            for a in new_attachments:
                content = base64.b64decode(a.get('content', ''), validate=True)
                if not content or len(content) > 8_000_000: raise ValueError('Limite de 8 MB por anexo.')
                if not isinstance(a.get('name'), str) or len(a['name']) > 250: raise ValueError('Nome de arquivo inválido.')
                previous.append({'id': uid(), 'name': a['name'], 'size': len(content), 'content': a['content']})
            if len(previous) > 20: raise ValueError('Limite de 20 anexos por registro.')
            p['attachments'] = previous
        elif old: p['attachments'] = json.loads(old['payload']).get('attachments', [])
        else: p.pop('attachments', None)
        if not isinstance(p.get('name'), str) or not p['name'].strip() or len(p['name']) > 200: raise ValueError('Informe um título com até 200 caracteres.')
        if kind in ['projects', 'tasks']:
            stages = STAGES if kind == 'projects' else TASK_STAGES
            if p.get('status') not in stages: raise ValueError('Status inválido.')
            p['progress'] = max(0, min(100, int(p.get('progress', 0))))
            if p['status'] == 'Concluído': p['progress'] = 100; p['completedAt'] = p.get('completedAt') or now()
            else: p.pop('completedAt', None)
            owner = p.get('owner')
            if owner and not c.execute('SELECT id FROM users WHERE id=? AND active=1', (owner,)).fetchone(): raise ValueError('Responsável inválido.')
        for field in ['start', 'deadline', 'date']:
            if p.get(field): datetime.strptime(p[field], '%Y-%m-%d')
        if p.get('start') and p.get('deadline') and p['start'] > p['deadline']: raise ValueError('O prazo deve ser posterior à data inicial.')
        if kind == 'environments':
            if urllib.parse.urlparse(p.get('url', '')).scheme not in ['https', 'http']: raise ValueError('Informe uma URL HTTP ou HTTPS válida.')
            for field in ['serverStatus', 'checkedAt', 'latency']: p.pop(field, None)
        if kind == 'credentials' and b.get('secret'): p['secret'] = cipher().encrypt(b['secret'].encode()).decode()
        if kind == 'credentials' and not p.get('secret'): raise ValueError('Informe a senha de teste.')
        if kind == 'documents':
            try: content = base64.b64decode(p.get('content', ''), validate=True)
            except Exception: raise ValueError('Arquivo inválido.')
            if not content or len(content) > 8_000_000: raise ValueError('O arquivo deve ter até 8 MB.')
            p['size'] = len(content)
        demand = None
        if kind == 'projects' and not old and p.get('demandId'):
            demand = c.execute("SELECT * FROM records WHERE id=? AND kind='demands'", (p['demandId'],)).fetchone()
            if not demand or not can_read(u, demand, c): raise ValueError('Demanda não encontrada.')
            if record(demand).get('status') == 'Convertida': raise APIError(409, 'Esta demanda já foi convertida em projeto.')
        if old: c.execute('UPDATE records SET payload=?,updated=? WHERE id=?', (json.dumps(p, ensure_ascii=False), now(), ident))
        else: ident = add_record(c, kind, p, u['id'], project)
        if demand:
            d = json.loads(demand['payload']) | {'status': 'Convertida', 'linkedProjectId': ident}
            c.execute('UPDATE records SET payload=?,updated=? WHERE id=?', (json.dumps(d, ensure_ascii=False), now(), demand['id']))
            for a in d.get('attachments', []): add_record(c, 'documents', {'name': a['name'], 'content': a['content'], 'size': a['size'], 'category': 'Briefing'}, u['id'], ident)
        title = ('Atualizado: ' if old else 'Criado: ') + p['name']
        if old:
            before = json.loads(old['payload'])
            changes = [f'{k}: {before.get(k, "—")} → {p.get(k, "—")}' for k in ['status', 'progress', 'deadline', 'owner', 'nextStep'] if before.get(k) != p.get(k)]
            if changes: title += ' (' + '; '.join(changes) + ')'
        self.audit(c, u, title, kind, project or (ident if kind == 'projects' else None)); self.notify(c, title, project or (ident if kind == 'projects' else None))
        self.reply(200 if old else 201, {'id': ident})

def backup():
    folder = DATA / 'backups'; folder.mkdir(exist_ok=True)
    target = folder / (datetime.now().strftime('%Y-%m-%d-%H%M%S')+'.sqlite3')
    with connect() as source, sqlite3.connect(target) as dest: source.backup(dest)
    files = sorted(folder.glob('*.sqlite3'))
    for old in files[:-30]: old.unlink()
def backup_loop():
    while True:
        try: backup()
        except Exception as exc: print('Backup:', exc, file=sys.stderr)
        time.sleep(86400)
if __name__ == '__main__':
    init()
    threading.Thread(target=backup_loop, daemon=True).start()
    host, port = os.environ.get('SKYX_HOST', '127.0.0.1'), int(os.environ.get('SKYX_PORT', '8000'))
    print(f'Skyx Gestão disponível em http://{host}:{port}', flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
