# Skyx Gestão

Sistema local em **React 18**, com API Python e banco SQLite, baseado no briefing fornecido. A interface inclui temas claro/escuro e layouts para desktop e celular. Não há senha padrão: o primeiro acesso cria o administrador.

## Iniciar neste computador

Execute `iniciar.bat` e acesse **http://localhost:8000**. Mantenha a janela do servidor aberta. No primeiro acesso, crie seu administrador e escolha se deseja incluir dados de demonstração. Os projetos de demonstração são identificados na interface e podem ser excluídos.

As bibliotecas React e React DOM estão em `web/vendor`, servidas localmente. A interface compilada está em `web/app.js`; não depende de CDN durante o uso. Python e bibliotecas de criptografia já foram preparados neste computador.

## Desenvolvimento

* Interface: `web/app.jsx` e `web/styles.css`.
* API e persistência: `server.py`.
* Compilar JSX: `data\node.exe build.cjs` neste computador, ou `node build.cjs` com Node instalado.
* Instalar dependência em outro computador: `python -m pip install -r requirements.txt`.
* Iniciar: `python server.py`.
* Testes de API: `python -m unittest discover -s tests -v`.
* Testes de navegador: `python tests/browser_check.py` (requer Playwright e Chrome).

## Funcionalidades

Dashboard com indicadores calculados, projetos e fluxo de nove etapas, demandas classificadas, tarefas com responsáveis e progresso, Kanban com arrastar/soltar e seleção acessível, cronograma, comentários, biblioteca com upload/download, registro manual de versões/commits/changelog, ambientes de acesso, cofre criptografado, equipe e cinco perfis, notificações, auditoria, painel executivo, relatório CSV e impressão em PDF, tema escuro, assistente local por regras e conector configurável de IA.

Cada perfil tem permissões verificadas na API. Administradores gerenciam usuários; gestores gerenciam o portfólio; programadores trabalham nos projetos autorizados e atualizam estágio, percentual e próxima etapa; clientes registram demandas e comentários nos projetos autorizados; visualizadores têm acesso de leitura. A associação de equipe, responsável ou autorização explícita concede acesso ao projeto. A consulta a credenciais é restrita à equipe técnica e auditada.

Demandas e tarefas aceitam até 20 anexos, com 8 MB por arquivo e limite total de aproximadamente 8 MB por envio. A conversão da demanda em projeto ocorre em uma transação e copia seus anexos para a biblioteca do projeto. A auditoria registra os valores anteriores e novos de estágio, progresso, prazo, responsável e próxima etapa. A central também cria alertas de prazos próximos e vencidos.

Sessões HttpOnly/SameSite duram 8 horas, alterações exigem token CSRF, senhas usam PBKDF2-SHA256 com salt e 600 mil iterações. O login limita tentativas. O usuário pode ativar TOTP/2FA, trocar a senha e revogar outras sessões.

## Configuração do servidor

| Variável | Uso |
| --- | --- |
| `SKYX_HOST` | Padrão `127.0.0.1`. |
| `SKYX_PORT` | Padrão `8000`. |
| `SKYX_DATA_DIR` | Diretório do SQLite, backups e chave do cofre. Padrão `data`. |
| `SKYX_SECURE_COOKIE` | Defina `1` ao servir por HTTPS. |
| `SKYX_MONITOR_HOSTS` | Domínios HTTPS autorizados para verificações, separados por vírgula. Ex.: `app.exemplo.com,api.exemplo.com`. Autorize somente serviços de confiança. |
| `SKYX_AI_URL` | Endpoint HTTPS compatível com Chat Completions. |
| `SKYX_AI_KEY` | Chave do provedor de IA, exclusivamente no ambiente do servidor. |
| `SKYX_AI_MODEL` | Modelo disponibilizado pelo provedor. |

O assistente, sem provedor configurado, apresenta análise real de atrasos e um plano padrão **por regras**, claramente identificado. Com provedor configurado, envia apenas projetos e tarefas acessíveis ao usuário; não envia senhas nem arquivos. A geração de checklist é um modelo de cinco tarefas revisáveis.

O System Monitor faz verificações HTTP sob demanda em domínios autorizados. Não simula servidores online. Status de API, banco remoto, backup remoto e monitoramento contínuo dependem de agentes/serviços externos e não estão conectados.

## Dados, backup e restauração

`data/skyx.sqlite3` contém os registros e os documentos. `data/vault.key` é a chave das credenciais, que usam Fernet. Restrinja o acesso a esse diretório no sistema operacional. O restante do SQLite não é criptografado em repouso; use volume criptografado se necessário.

O servidor cria backup ao iniciar e a cada 24 horas enquanto está ativo, retendo os 30 arquivos mais recentes em `data/backups`. Também há backup manual em Configurações. Preserve uma cópia segura de `vault.key` separadamente: sem ela, as credenciais não podem ser recuperadas.

Para restaurar: pare o servidor, preserve o banco atual, copie o backup escolhido para `data/skyx.sqlite3` e restaure a chave correspondente. Os arquivos SQLite `-wal` e `-shm`, se existentes, devem ser tratados junto com a cópia atual após encerrar todas as conexões. Reinicie e valide o acesso. Backups locais não substituem cópias externas.

## Limites e implantação

Esta entrega executa localmente. A publicação e integração ao site institucional exigem domínio, servidor e HTTPS. O servidor HTTP padrão do Python é voltado ao ambiente local; para produção, adapte a API a um servidor de aplicação adequado, configure proxy HTTPS, políticas de backup externo e gestão segura da chave do cofre.

Integrações GitHub/GitLab/Bitbucket, deploy automático, chat interno, financeiro, contratos, mobile e demais itens da seção “Funcionalidades futuras” não estão conectados. Versões são registradas manualmente. Controle prévio de dispositivos autorizados, alertas externos de segurança e infraestrutura não foram implementados. Notificações internas cobrem criações e alterações; próximos prazos são calculados no dashboard. Atualizações são consultadas a cada 30 segundos.

O briefing não contém logotipo oficial, paleta exata ou telas de referência: a identidade visual foi criada para o portal com azul profundo, verde-água e superfícies claras.
