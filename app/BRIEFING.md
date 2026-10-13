# Cobertura do briefing Sky X

| Seção | Entrega e observações |
| --- | --- |
| 1. Conceito | Portal React com login individual, API e persistência SQLite. Integração ao domínio institucional depende de implantação. |
| 2. Dashboard | Projetos ativos, desenvolvimento, testes, aprovação/homologação, alertas de prazos, atividades e próximas entregas. Atualização a cada 30 segundos. |
| 3. Nova demanda | Nome, descrição, objetivo, problema, 19 tipos, prioridade, prazo, área, solicitante, anexos, referências e observações. Conversão transacional em projeto. |
| 4. Ficha do projeto | Descrição, objetivo, responsável, equipe, início, prazo, status, percentual, prioridade, atualização e próxima etapa. |
| 5. Status | Nove etapas do briefing e progresso percentual. Responsáveis técnicos podem atualizar o andamento dos projetos autorizados. |
| 6. Cronograma | Linha do tempo por projeto, marcos editáveis e cronograma geral ordenado por entrega. |
| 7. Acesso ao sistema | URLs, ambiente, versão, usuário de teste e cofre Fernet com consulta auditada. Status HTTP mediante verificação. |
| 8. Versões | Registro manual de versão, branch, commit, ambiente e changelog com autor e data. Sincronização Git ainda não integrada. |
| 9. Tarefas | Responsável, prioridade, prazo, status, percentual, observações técnicas, anexos, esforço estimado e data de conclusão. |
| 10. Kanban | Cinco colunas, movimentação por arrastar e soltar ou seletor acessível. |
| 11. Assistente | Análise local de portfólio e atrasos; checklist padrão revisável. Conector generativo exige endpoint, modelo e chave do provedor. |
| 12. Notificações | Criações, alterações, comentários e alertas internos de prazos próximos/vencidos. Sem push, e-mail ou telemetria externa. |
| 13. Comentários | Comunicação vinculada ao projeto, incluindo orientação, pendência, feedback, alteração e aprovação. |
| 14. Documentação | Biblioteca por projeto com upload, categorias, download autorizado e exclusão conforme permissão. |
| 15. Acesso | Administrador, gestor, programador, cliente e visualização; autorização aplicada no servidor. |
| 16. Segurança | Hash de senha, sessões HttpOnly, CSRF, TOTP/2FA, expiração, limite de tentativas, IP e revogação de sessões. Cofre criptografado. Backup local diário. Não inclui allowlist prévia de dispositivos, alertas externos ou criptografia integral do banco. |
| 17. Monitor | Cadastro de ambientes e checagem HTTP real sob demanda para domínios autorizados. Monitoramento contínuo de infraestrutura e agentes de banco/API não conectados. |
| 18. Executivo | Totais, conclusão, atrasos, etapas, áreas, responsáveis e esforço aberto por pessoa; exportação CSV e impressão/PDF. Não há série histórica mensal de snapshots. |
| 19. Auditoria | Login, criação, alteração, exclusão, consultas ao cofre e downloads, com autor/IP/data; valores anteriores e novos nos principais campos de andamento. |
| 20. Arquitetura | React, API Python, SQLite, autenticação e regras de acesso. Estrutura preparada para evolução; servidor atual destinado à execução local. |
| 21. Centro de comando | Navegação integrada entre demandas, projetos, equipe, execução, documentação e ambientes. |
| 22. Futuro | Mobile nativo, contratos, financeiro, chat, deploy automático, integrações Git, agentes e demais itens futuros não implementados. CSV/PDF e ambientes já disponíveis. |
| 23. Visão final | Identidade própria, responsiva, em azul profundo/verde-água, com temas claro e escuro. O documento não fornece telas ou identidade gráfica oficial para reprodução literal. |

## Verificação

Oito testes automatizados de API cobrem autenticação/CSRF, 2FA/sessões, isolamento de acesso, ciclo de tarefas e documentos, criptografia/auditoria do cofre, validação de URLs, conversão de demanda com anexos e atualização restrita por programadores.

O teste de navegador usa banco temporário e percorre as 13 áreas de navegação, primeiro acesso, autenticação, demanda com anexo, conversão para projeto, persistência após recarga, comentários, criação/conclusão de tarefa, temas e layout de 390 px. Capturas ficam em `data/qa`.

Os bancos de teste são separados do banco de entrega. O ambiente entregue aguarda a criação do administrador pelo usuário.
