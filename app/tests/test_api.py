import sys, os, tempfile, unittest, threading, json, urllib.request, urllib.error, http.cookiejar
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['SKYX_DATA_DIR'] = tempfile.mkdtemp(prefix='skyx-tests-')
import server

class Client:
    def __init__(self, port):
        self.base = f'http://127.0.0.1:{port}/api/'
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = ''
    def call(self, path, method='GET', data=None, csrf=True):
        req = urllib.request.Request(self.base+path, data=json.dumps(data).encode() if data is not None else None, method=method, headers={'Content-Type':'application/json', 'X-CSRF-Token':self.csrf if csrf else ''})
        try:
            with self.opener.open(req) as res: return res.status, json.load(res)
        except urllib.error.HTTPError as err:
            with err: return err.code, json.load(err)
    def login(self, email, password, code=''):
        status, data = self.call('login', 'POST', {'email':email, 'password':password, 'code':code})
        if status == 200: self.csrf = data['csrf']
        return status, data

class SecurityAndWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.init()
        cls.http = server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()
        cls.port = cls.http.server_port
        cls.admin = Client(cls.port)
        cls.admin.call('setup','POST',{'name':'Admin Teste','email':'admin@teste.local','password':'SenhaSegura123!','demo':False})
        cls.admin.login('admin@teste.local','SenhaSegura123!')
    @classmethod
    def tearDownClass(cls): cls.http.shutdown();cls.http.server_close()
    def project(self):
        status, result = self.admin.call('projects','POST',{'name':'Projeto restrito','status':'Ideia','progress':0,'priority':'Alta','team':[]})
        self.assertEqual(status,201,result)
        return result['id']
    def test_auth_and_csrf(self):
        self.assertEqual(Client(self.port).call('state')[0],401)
        self.assertEqual(self.admin.call('projects','POST',{'name':'X'},csrf=False)[0],403)
        self.assertEqual(self.admin.call('setup','POST',{})[0],409)
    def test_project_task_document_lifecycle(self):
        pid=self.project()
        status,t=self.admin.call('tasks','POST',{'name':'Validar entrega','projectId':pid,'status':'A fazer','deadline':'2026-10-15'})
        self.assertEqual(status,201)
        self.assertEqual(self.admin.call('tasks/'+t['id'],'PATCH',{'status':'Concluído'})[0],200)
        state=self.admin.call('state')[1]
        task=next(x for x in state['tasks'] if x['id']==t['id'])
        self.assertEqual(task['progress'],100)
        self.assertIn('completedAt',task)
        self.assertEqual(self.admin.call('documents','POST',{'name':'nota.txt','projectId':pid,'content':'b2s='})[0],201)
        self.assertEqual(self.admin.call('projects/'+pid,'DELETE')[0],200)
        self.assertFalse(any(x['projectId']==pid for x in self.admin.call('state')[1]['tasks']))
    def test_permission_isolation(self):
        pid=self.project()
        email='reader'+server.uid()+'@teste.local'
        status,result=self.admin.call('users','POST',{'name':'Leitor','email':email,'password':'SenhaSegura123!','role':'Visualização','projects':[]})
        self.assertEqual(status,201)
        reader=Client(self.port);reader.login(email,'SenhaSegura123!')
        self.assertNotIn(pid,[p['id'] for p in reader.call('state')[1]['projects']])
        self.assertEqual(reader.call('projects/'+pid,'PATCH',{'name':'Intrusão'})[0],404)
        self.admin.call('users/'+result['id'],'PATCH',{'projects':[pid]})
        reader.login(email,'SenhaSegura123!')
        self.assertIn(pid,[p['id'] for p in reader.call('state')[1]['projects']])
        self.assertEqual(reader.call('tasks','POST',{'name':'Intrusão','projectId':pid})[0],403)
    def test_vault_encryption_and_audit(self):
        pid=self.project()
        status,r=self.admin.call('credentials','POST',{'name':'Teste','projectId':pid,'username':'teste','secret':'NuncaEmTextoClaro'})
        self.assertEqual(status,201,r)
        state=self.admin.call('state')[1]
        self.assertNotIn('secret',next(x for x in state['credentials'] if x['id']==r['id']))
        with server.connect() as c:
            stored=c.execute('SELECT payload FROM records WHERE id=?',(r['id'],)).fetchone()[0]
            self.assertNotIn('NuncaEmTextoClaro',stored)
        self.assertEqual(self.admin.call('credentials/'+r['id']+'/reveal','POST',{})[1]['secret'],'NuncaEmTextoClaro')
        self.assertTrue(any(a['action']=='Credencial consultada' for a in self.admin.call('state')[1]['audit']))
    def test_2fa_and_session_revocation(self):
        email='dev'+server.uid()+'@teste.local'
        self.admin.call('users','POST',{'name':'Dev','email':email,'password':'SenhaSegura123!','role':'Programador'})
        dev=Client(self.port);dev.login(email,'SenhaSegura123!')
        secret=dev.call('security','POST',{'action':'setup2fa'})[1]['secret']
        self.assertEqual(dev.call('security','POST',{'action':'confirm2fa','code':server.totp(secret)})[0],200)
        other=Client(self.port)
        self.assertEqual(other.login(email,'SenhaSegura123!')[0],401)
        self.assertEqual(other.login(email,'SenhaSegura123!',server.totp(secret))[0],200)
        dev.call('security','POST',{'action':'revoke'})
        self.assertEqual(other.call('state')[0],401)
    def test_validation_and_monitor_allowlist(self):
        pid=self.project()
        self.assertEqual(self.admin.call('projects/'+pid,'PATCH',{'deadline':'invalid'})[0],400)
        self.assertEqual(self.admin.call('environments','POST',{'projectId':pid,'name':'Unsafe','url':'javascript:alert(1)'})[0],400)
        status,e=self.admin.call('environments','POST',{'projectId':pid,'name':'Local','url':'http://127.0.0.1'})
        self.assertEqual(status,201)
        self.assertEqual(self.admin.call('monitor/'+e['id'],'POST',{})[0],400)

    def test_demand_conversion_preserves_attachments(self):
        status,d=self.admin.call('demands','POST',{'name':'Demanda anexada','newAttachments':[{'name':'briefing.txt','content':'b2s='}]})
        self.assertEqual(status,201,d)
        state=self.admin.call('state')[1]
        demand=next(x for x in state['demands'] if x['id']==d['id'])
        self.assertNotIn('content',demand['attachments'][0])
        status,p=self.admin.call('projects','POST',{'name':'Convertido','status':'Ideia','demandId':d['id']})
        self.assertEqual(status,201,p)
        state=self.admin.call('state')[1]
        self.assertEqual(next(x for x in state['demands'] if x['id']==d['id'])['status'],'Convertida')
        self.assertTrue(any(x['projectId']==p['id'] and x['name']=='briefing.txt' for x in state['documents']))
        self.assertEqual(self.admin.call('projects','POST',{'name':'Duplicado','status':'Ideia','demandId':d['id']})[0],409)
    def test_programmer_can_update_progress_not_permissions(self):
        pid=self.project();email='programmer'+server.uid()+'@teste.local'
        self.admin.call('users','POST',{'name':'Programador','email':email,'password':'SenhaSegura123!','role':'Programador','projects':[pid]})
        dev=Client(self.port);dev.login(email,'SenhaSegura123!')
        self.assertEqual(dev.call('projects/'+pid,'PATCH',{'status':'Testes','progress':80,'nextStep':'Homologação'})[0],200)
        self.assertEqual(dev.call('projects/'+pid,'PATCH',{'team':['intruder']})[0],403)
        audit=self.admin.call('state')[1]['audit']
        self.assertTrue(any('progress: 0 → 80' in a['action'] for a in audit))

if __name__=='__main__': unittest.main()
