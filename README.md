# User Analytics — Documentação Técnica

Sistema de análise de usuários orientado a eventos, consumindo a API pública
[JSONPlaceholder](https://jsonplaceholder.typicode.com), com interface web em Flask,
exportação em CSV e Excel, e simulação de envio de relatório via POST.

---

## Sumário

1. [Arquitetura do sistema](#1-arquitetura-do-sistema)
2. [Fluxo de eventos](#2-fluxo-de-eventos)
3. [Linguagens, bibliotecas e ferramentas](#3-linguagens-bibliotecas-e-ferramentas)
4. [Decisões técnicas](#4-decisões-técnicas)
5. [Problemas e soluções](#5-problemas-e-soluções)
6. [Como executar](#6-como-executar)
7. [Como testar](#7-como-testar)

---

## 1. Arquitetura do sistema

O projeto segue uma arquitetura em camadas com separação estrita de responsabilidades.
Cada módulo conhece apenas a camada imediatamente abaixo — nunca a acima — eliminando
acoplamento cruzado e facilitando substituições e testes isolados.

```
user-analytics/
├── main.py                        # Entrypoint — inicializa o servidor Flask
├── config.py                      # Fonte única de verdade para constantes
├── requirements.txt
│
├── api/                           # Camada de comunicação com API externa
│   ├── client.py                  # HTTP client com cache em memória e retry
│   └── endpoints.py               # Funções de domínio por recurso da API
│
├── analytics/                     # Camada de negócio — cálculo de métricas
│   └── metrics.py                 # Função pura, sem I/O, sem efeitos colaterais
│
├── export/                        # Camada de saída — geração e envio de relatórios
│   ├── csv_exporter.py            # Serialização para CSV com BOM UTF-8
│   ├── xlsx_exporter.py           # Serialização para Excel com formatação
│   └── report_sender.py           # Simulação do POST para /reports
│
├── ui/                            # Camada de interface
│   ├── interface.py               # Rotas Flask (handlers finos, sem lógica de negócio)
│   └── templates/
│       └── index.html             # SPA com JavaScript orientado a eventos
│
└── tests/
    ├── test_metrics.py            # 15 testes unitários — analytics
    └── test_exporter.py           # 15 testes unitários — export
```

### Diagrama de dependências

```
main.py
  └── ui/interface.py
        ├── api/endpoints.py
        │     └── api/client.py
        ├── analytics/metrics.py
        └── export/
              ├── csv_exporter.py
              ├── xlsx_exporter.py
              └── report_sender.py
                    └── api/endpoints.py
```

Nenhuma seta aponta para cima. `analytics/` e `export/` não importam nada de `ui/`.
`api/client.py` não importa nada das outras camadas. Essa direção única é garantida
por convenção e verificável pela ausência de imports circulares.

---

## 2. Fluxo de eventos

O sistema é inteiramente orientado a eventos: nenhuma ação ocorre sem que uma
interação do usuário ou o carregamento inicial a dispare.

### 2.1 Carregamento inicial (Task 1)

```
DOMContentLoaded
  └── loadUsers()
        └── GET /api/users          (Flask)
              └── api.get_users()   (aiohttp + cache)
                    └── GET /users  (JSONPlaceholder)
        └── Popula <select>
        └── Atualiza status bar
```

### 2.2 Seleção de usuário (Task 2)

```
evento: change em #userSelect
  └── onUserChange(userId)
        └── GET /api/users/:id/posts?min_chars=0&min_posts=5   (Flask)
              └── api.get_posts_with_comments()
                    ├── GET /posts?userId=:id
                    └── asyncio.gather(GET /comments?postId=N ...)  ← paralelo
              └── analytics.compute_metrics()
        └── render(user, data)
        └── Habilita botões de exportação
```

### 2.3 Alteração de filtros (Task 3)

```
evento: input em #minChars ou #minPosts
  └── debounce(350ms)
        └── fetchAndRender()        ← mesma função da Task 2
              └── GET /api/users/:id/posts?min_chars=X&min_posts=Y
                    └── cache hit → sem nova requisição à API externa
                    └── compute_metrics() recalcula com novos parâmetros
        └── render() atualiza métricas e tabela
```

### 2.4 Exportação (Task 4)

```
evento: click em #btnCsv
  └── window.location.href = /api/export/csv?user_id=...
        └── Flask busca posts (cache), calcula métricas, gera bytes CSV
        └── Response com Content-Disposition: attachment

evento: click em #btnXlsx
  └── window.location.href = /api/export/xlsx?user_id=...
        └── Flask busca posts (cache), calcula métricas, gera bytes .xlsx
        └── send_file() com mimetype correto
```

### 2.5 Envio do relatório (Task 5)

```
evento: click em #btnSend
  └── POST /api/report/send  { user_id, user_name, min_chars, min_posts }
        └── Flask recalcula métricas
        └── export.send_report()
              └── POST /posts  (JSONPlaceholder — proxy de /reports)
        └── Retorna { success: true, response: { id: ... } }
  └── Toast com id retornado pela API
```

---

## 3. Linguagens, bibliotecas e ferramentas

| Componente | Escolha | Justificativa |
|---|---|---|
| Linguagem | Python 3.12 | Type hints nativos, `asyncio` maduro, ecossistema rico |
| Framework web | Flask 3 | Leve, sem opinião sobre estrutura, ideal para APIs finas |
| HTTP assíncrono | aiohttp | Suporte nativo a `asyncio.gather` para requisições paralelas |
| Excel | openpyxl | Controle fino sobre estilos sem dependência de LibreOffice |
| Testes | pytest | Fixtures, parametrização, classes de teste organizadas |
| Frontend | Vanilla JS (ES2020) | Sem dependências de build — `async/await`, módulos de objeto |

### Dependências

```
aiohttp>=3.9.0
flask>=3.0.0
openpyxl>=3.1.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

---

## 4. Decisões técnicas

### 4.1 Arquitetura em camadas com módulos independentes

Cada módulo tem uma única responsabilidade e pode ser testado, substituído ou
reutilizado sem tocar nos demais. `analytics/metrics.py`, por exemplo, é uma
função pura: recebe dados, devolve um `dataclass` imutável — sem Flask, sem
aiohttp, sem I/O. Isso permite rodar os 15 testes de métricas sem subir o servidor.

### 4.2 `UserMetrics` como dataclass frozen

O resultado do cálculo de métricas é um `dataclass(frozen=True)`. Isso impede
mutação acidental após o cálculo e documenta explicitamente a intenção de que
o objeto é um valor, não um estado mutável. É o mesmo princípio de imutabilidade
aplicado nos arrays NumPy do pipeline de treinamento.

### 4.3 Cache em memória com TTL por chave

A classe `MemoryCache` armazena cada URL já requisitada com um timestamp.
Ao chamar `client.get(path)`, a URL completa é usada como chave — se o valor
existir e não estiver expirado (TTL padrão: 5 minutos), a requisição HTTP é
evitada. Isso é especialmente relevante para os filtros: ao alterar `min_chars`
ou `min_posts`, os dados já enriquecidos dos posts são servidos do cache,
e apenas `compute_metrics()` é executado novamente.

### 4.4 Requisições paralelas com `asyncio.gather`

Ao selecionar um usuário, os comentários de todos os seus posts são buscados
em paralelo via `asyncio.gather`. Com 10 posts e latência média de 200ms por
requisição, o tempo total cai de ~2s (sequencial) para ~200ms (paralelo).

### 4.5 Debounce nos inputs de filtro

Os campos `min_chars` e `min_posts` usam debounce de 350ms no frontend. Sem
isso, cada tecla dispararia uma requisição ao servidor. O debounce agrupa as
alterações e envia apenas a requisição final após o usuário pausar a digitação.

### 4.6 Flask síncrono com bridge para código assíncrono

Flask 3 suporta rotas assíncronas, mas exige `async def` em todas as rotas e
um ASGI server (como Hypercorn). Para manter a simplicidade de execução com
`python main.py`, foi implementado o helper `_run(coro)` que executa corrotinas
no event loop via `asyncio.run()`. A camada assíncrona (`aiohttp`) fica contida
em `api/`, transparente para o Flask.

### 4.7 Separação entre `raw_total` e `total_posts`

O status "Ativo/Inativo" é calculado sobre o total real de posts do usuário
(`raw_total`), não sobre o total filtrado. Isso respeita a semântica do case:
o filtro de caracteres é um recorte de visualização, não uma redefinição do
perfil do usuário.

### 4.8 BOM UTF-8 no CSV

O CSV é gerado com BOM (`\ufeff`) para garantir que o Excel abra o arquivo
corretamente ao dar duplo-clique, sem exibir caracteres especiais corrompidos.
Ferramentas que não entendem BOM (como `csv.reader` do Python) o ignoram
automaticamente ao usar `encoding='utf-8-sig'`.

---

## 5. Problemas e soluções

### P1: `asyncio` em contexto síncrono Flask

**Problema:** Flask por padrão não gerencia event loops. Chamar `asyncio.run()`
dentro de uma rota funciona na maioria dos casos, mas falha quando um loop já
está ativo (ex: ambiente de testes ou Jupyter).

**Solução:** O helper `_run()` detecta se há um loop ativo e, nesse caso,
executa a corrotina em uma thread separada via `ThreadPoolExecutor`, evitando
o erro `This event loop is already running`.

### P2: A rota `/reports` não existe no JSONPlaceholder

**Problema:** O case pede um POST para `/reports`, mas essa rota não existe
na API pública.

**Solução:** O POST é feito para `/posts`, que aceita qualquer payload e devolve
o objeto com um `id` gerado — comportamento idêntico ao esperado de um endpoint
`/reports`. O mapeamento está documentado em `api/endpoints.py`.

### P3: Exportação de arquivo via `window.location.href`

**Problema:** Disparar o download de um arquivo via `fetch()` exige criar um
Blob, um URL temporário e clicar nele programaticamente — código verboso e
frágil em alguns navegadores.

**Solução:** Redirecionar `window.location.href` para a rota de exportação.
O Flask responde com `Content-Disposition: attachment`, o navegador interpreta
como download automático e não navega para fora da página.

### P4: Acoplamento entre status e filtro de posts

**Problema:** Uma implementação ingênua calcularia `is_active` com base no
`total_posts` já filtrado. Isso causaria um bug onde aumentar `min_chars`
tornaria um usuário inativo sem que ele tivesse mudado.

**Solução:** `compute_metrics()` recebe `raw_total = len(posts)` antes de
aplicar qualquer filtro e usa esse valor para calcular `is_active`. O filtro
afeta apenas `filtered_posts`, `avg_chars` e `avg_comments`.

---

## 6. Como executar

```bash
# 1. Clonar e entrar no diretório
git clone <https://github.com/joaovitorshenriques/user-analytics>

# 2. Criar ambiente virtual (recomendado)
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Iniciar o servidor
python main.py
```

Acesse [http://127.0.0.1:5000](http://127.0.0.1:5000) no navegador.

### Variáveis de configuração

Todas as configurações estão em `config.py`. As principais:

| Variável | Padrão | Descrição |
|---|---|---|
| `FLASK_PORT` | `5000` | Porta do servidor |
| `FLASK_DEBUG` | `True` | Modo debug do Flask |
| `CACHE_TTL_SECONDS` | `300` | TTL do cache em memória |
| `DEFAULT_MIN_POSTS` | `5` | Limiar padrão para status ativo |
| `REQUEST_TIMEOUT` | `10` | Timeout HTTP em segundos |
| `MAX_RETRIES` | `3` | Tentativas em falha transitória |

---

## 7. Como testar

```bash
# Rodar todos os testes
pytest tests/ -v

# Rodar apenas métricas
pytest tests/test_metrics.py -v

# Rodar apenas exportadores
pytest tests/test_exporter.py -v

# Com cobertura (requer pytest-cov)
pip install pytest-cov
pytest tests/ --cov=. --cov-report=term-missing
```

### Cobertura dos testes

**`test_metrics.py` — 15 testes**

| Classe | O que testa |
|---|---|
| `TestFiltering` | Filtro por min_chars: sem filtro, filtro parcial, boundary exato, filtro total, lista vazia |
| `TestAverages` | Média de chars e comentários: post único, múltiplos posts, após filtro |
| `TestActiveStatus` | Status ativo/inativo, limiar exato, status baseado em raw_total não filtrado |
| `TestUserMetrics` | Imutabilidade do dataclass, preservação dos thresholds no resultado |

**`test_exporter.py` — 15 testes**

| Classe | O que testa |
|---|---|
| `TestCsvExporter` | Tipo bytes, BOM UTF-8, cabeçalho, valores, múltiplas linhas, lista vazia, escaping de vírgulas |
| `TestXlsxExporter` | Tipo bytes, cabeçalho, valores, contagem de linhas, título da aba, lista vazia |
| `TestBuildReportRow` | Chaves do dicionário, propagação do status |