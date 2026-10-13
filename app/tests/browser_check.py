import os, sys, tempfile, threading, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'data'/'packages'))
os.environ['SKYX_DATA_DIR']=tempfile.mkdtemp(prefix='skyx-browser-')
import server
from playwright.sync_api import sync_playwright
server.init()
http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
threading.Thread(target=http.serve_forever,daemon=True).start()
out=ROOT/'data'/'qa';out.mkdir(exist_ok=True)
errors=[]
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{http.server_port}')
        page.get_by_label('Nome completo').fill('Alex Morgan')
        page.get_by_label('E-mail profissional').fill('qa@skyx.local')
        page.get_by_label('Senha',exact=True).fill('SkyxTesteSeguro2026!')
        page.get_by_role('button',name='Criar meu ambiente').click()
        page.get_by_role('heading',name='Visão geral.').wait_for()
        page.screenshot(path=str(out/'dashboard-desktop.png'),full_page=True)
        for title in ['Projetos','Demandas','Minhas tarefas','Quadro Kanban','Cronograma','Painel executivo','Assistente Skyx','Documentação','Equipe & acessos','System Monitor','Histórico & auditoria','Configurações']:
            page.locator('nav').get_by_role('button',name=title,exact=False).click()
            page.locator('main h1').wait_for()
            assert page.locator('main').inner_text(),title
        page.locator('nav').get_by_role('button',name='Demandas').click()
        page.get_by_role('button',name='Nova demanda',exact=True).click()
        page.get_by_label('Nome / título').fill('Demanda validada no navegador')
        page.get_by_label('Área solicitante').fill('Operações')
        page.locator('input[name="attachments"]').set_input_files({'name':'briefing-qa.txt','mimeType':'text/plain','buffer':b'Requisitos de validacao'})
        page.get_by_role('button',name='Salvar demanda',exact=True).click()
        page.get_by_role('button',name='Demanda validada no navegador',exact=True).wait_for()
        demand_row=page.get_by_role('row').filter(has_text='Demanda validada no navegador')
        demand_row.get_by_role('button',name='Criar projeto').click()
        page.get_by_role('button',name='Salvar projeto',exact=True).click()
        demand_row.get_by_text('Convertida',exact=True).wait_for()
        page.reload()
        page.locator('nav').get_by_role('button',name='Demandas').click()
        page.get_by_role('button',name='Demanda validada no navegador',exact=True).wait_for()
        page.locator('nav').get_by_role('button',name='Projetos',exact=True).click()
        page.get_by_role('button',name='Sistema de Ocorrências',exact=True).click()
        for tab in ['Tarefas','Cronograma','Comentários','Documentação','Versões','Acesso ao sistema','Visão geral']:
            page.locator('.tabs').get_by_role('button',name=tab).click()
        page.locator('.tabs').get_by_role('button',name='Comentários').click()
        page.locator('textarea[name="comment"]').fill('Fluxo de colaboração validado.')
        page.get_by_role('button',name='Enviar comentário').click()
        page.get_by_text('Fluxo de colaboração validado.',exact=True).wait_for()
        page.locator('.tabs').get_by_role('button',name='Tarefas').click()
        page.get_by_role('button',name='Nova tarefa',exact=True).click()
        page.get_by_label('Nome / título').fill('Tarefa criada no navegador')
        page.get_by_role('button',name='Salvar tarefa',exact=True).click()
        page.get_by_role('button',name='Concluir Tarefa criada no navegador',exact=True).click()
        page.locator('.task-row').filter(has_text='Tarefa criada no navegador').get_by_text('Concluído',exact=True).wait_for()
        page.locator('.tabs').get_by_role('button',name='Visão geral').click()
        page.screenshot(path=str(out/'project-desktop.png'),full_page=True)
        page.get_by_role('button',name='Alternar tema').click()
        page.screenshot(path=str(out/'project-dark.png'),full_page=True)
        page.get_by_role('button',name='Alternar tema').click()
        page.set_viewport_size({'width':390,'height':844})
        page.get_by_role('button',name='Abrir menu').click()
        page.locator('nav').get_by_role('button',name='Visão geral',exact=True).click()
        page.wait_for_timeout(350)
        page.screenshot(path=str(out/'dashboard-mobile.png'),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile overflow'
        browser.close()
    assert not errors,errors
    print(json.dumps({'result':'PASS','pages':13,'checks':['first-run setup','login','navigation','demand creation with attachment','atomic conversion to project','persistence after reload','project tabs','comments','task creation and completion','dark theme','390px mobile layout'],'browserErrors':errors}),flush=True)
finally:
    http.shutdown();http.server_close()
