# ENTER AI - Document Extraction API

Sistema de extração inteligente de dados de documentos PDF usando IA, desenvolvido como projeto Fellowship ENTER AI.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Tecnologias](#tecnologias)
- [Pré-requisitos](#pré-requisitos)
- [Instalação e Execução](#instalação-e-execução)
  - [Opção 1: Docker (Recomendado)](#opção-1-docker-recomendado)
  - [Opção 2: Ambiente Local](#opção-2-ambiente-local)
- [Uso da API](#uso-da-api)
- [Frontend](#frontend)
- [Testes](#testes)
- [Estrutura do Projeto](#estrutura-do-projeto)

---

## 🎯 Visão Geral

Este projeto é uma API de extração de dados de documentos PDF que utiliza:
- **Extração de texto**: PDFPlumber para parsing de PDFs
- **IA Generativa**: OpenAI GPT para extração inteligente de campos
- **Schemas flexíveis**: Definição customizável de campos a serem extraídos
- **Interface web**: Frontend interativo para testes

### Funcionalidades

- ✅ Extração de campos estruturados de PDFs
- ✅ Suporte para múltiplos tipos de documentos (Carteira OAB, Telas de Sistema, etc.)
- ✅ Modo Batch: processar múltiplos PDFs de uma vez
- ✅ Modo Single: processar um PDF por vez
- ✅ Export de resultados em JSON e CSV
- ✅ Interface web moderna e responsiva

---

## 🛠️ Tecnologias

### Backend
- **Python 3.12**
- **FastAPI**: Framework web moderno e rápido
- **PDFPlumber**: Extração de texto e tabelas de PDFs
- **OpenAI API**: Modelos GPT para extração inteligente
- **Pydantic**: Validação de dados e serialização

### Frontend
- **HTML5 + CSS3 + JavaScript**: Interface web pura (sem frameworks)
- **Design responsivo**: Funciona em desktop e mobile

### DevOps
- **Docker & Docker Compose**: Containerização
- **Nginx**: Servidor web para frontend

---

## 📦 Pré-requisitos

### Para Docker (Recomendado)
- Docker Engine 20.10+
- Docker Compose 1.29+

### Para Ambiente Local
- Python 3.12+
- Node.js 18+ (opcional, apenas para frontend)
- OpenAI API Key

---

## 🚀 Instalação e Execução

### Opção 1: Docker (Recomendado)

#### 1. Clone o repositório
```bash
git clone <repository-url>
cd enter-ai
```

#### 2. Configure a API Key
Certifique-se de que o arquivo `backend/.env` existe e contém sua OpenAI API Key:
```bash
# backend/.env
OPENAI_API_KEY=sk-your-openai-api-key-here
```

#### 3. Inicie os serviços
```bash
docker-compose up --build
```

#### 4. Acesse a aplicação
- **Frontend**: http://localhost:8080
- **Backend API**: http://localhost:8001
- **Documentação da API**: http://localhost:8001/docs

#### Comandos úteis
```bash
# Parar os serviços
docker-compose down

# Ver logs
docker-compose logs -f

# Rebuildar apenas o backend
docker-compose up --build backend

# Rodar em segundo plano
docker-compose up -d
```

---

### Opção 2: Ambiente Local

#### Backend

1. **Navegue até o diretório do backend**
```bash
cd backend
```

2. **Crie e ative o ambiente virtual**
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

4. **Configure a API Key**
```bash
cp .env.example .env
# Edite .env e adicione sua OPENAI_API_KEY
```

5. **Inicie o servidor**
```bash
uvicorn main:app --reload --port 8001
```

A API estará disponível em http://localhost:8001

#### Frontend

1. **Navegue até o diretório do frontend**
```bash
cd frontend
```

2. **Sirva os arquivos estáticos**

Opção A - Python SimpleHTTPServer:
```bash
python3 -m http.server 8080
```

Opção B - Node.js http-server:
```bash
npx http-server -p 8080
```

O frontend estará disponível em http://localhost:8080

---

## 📡 Uso da API

### Endpoint: POST /extract

Extrai campos de um documento PDF.

#### Exemplo com cURL:
```bash
curl -X POST http://localhost:8001/extract \
  -F "label=carteira_oab" \
  -F "extraction_schema={\"nome\":\"Nome do profissional\",\"inscricao\":\"Número de inscrição\"}" \
  -F "pdf_file=@./docs/files/oab_1.pdf"
```

#### Exemplo com HTTPie:
```bash
http --form POST :8001/extract \
  label=carteira_oab \
  extraction_schema='{"nome": "Nome do profissional", "inscricao": "Número de inscrição"}' \
  pdf_file@./docs/files/oab_1.pdf
```

#### Resposta:
```json
{
  "label": "carteira_oab",
  "results": [
    {
      "field_name": "nome",
      "value": "JOANA D'ARC",
      "source": "llm",
      "confidence": 0.0
    },
    {
      "field_name": "inscricao",
      "value": "101943",
      "source": "llm",
      "confidence": 0.0
    }
  ],
  "flat": {
    "nome": "JOANA D'ARC",
    "inscricao": "101943"
  },
  "metadata": {
    "model": "gpt-5-mini",
    "prompt_tokens": 210,
    "completion_tokens": 40,
    "total_tokens": 250,
    "duration_ms": 2400,
    "source": "mixed",
    "extracted_at": "2025-11-06T15:30:00",
    "profiling": {
      "pdf_text_ms": 8,
      "heuristics_ms": 2,
      "llm_ms": 2100,
      "total_ms": 2400
    }
  }
}
```
> O frontend utiliza o objeto `flat` para mostrar o JSON “limpo”, mas o payload completo mantém `results` (com fonte/confiança) e `metadata.profiling`.

---

## 🎨 Frontend

O frontend oferece duas interfaces:

### 1. Modo Batch (Padrão)
- Upload de múltiplos PDFs
- Schema em formato array (matching dataset.json)
- Processamento em lote
- Resumo agregado dos resultados

### 2. Modo Single
- Upload de um único PDF
- Schema em formato objeto simples
- Ideal para testes rápidos

### Funcionalidades
- ✅ Drag & drop de arquivos
- ✅ Validação de schemas JSON
- ✅ Visualização simultânea (JSON achatado + detalhes completos)
- ✅ Export para JSON e CSV
- ✅ Exemplos pré-carregados
- ✅ Métricas de performance (tempo, custo, tokens) e progresso em tempo real no modo batch

---

## 🧪 Testes

### Testes Automatizados
```bash
cd backend
source .venv/bin/activate
pytest
```

### Testes Manuais

#### 1. Script de exemplo (usa dataset.json)
```bash
cd backend
source .venv/bin/activate
python3 scripts/run_example.py
```

#### 2. Frontend web
Acesse http://localhost:8080 e:
1. Clique em "Load Example"
2. Faça upload dos PDFs correspondentes
3. Clique em "Extract Data"

---

## 🧱 Arquitetura & Trade-offs

- **Heurísticas primeiro**: campos padronizados (CPF, seccional, subseção, etc.) são extraídos via regex flexíveis. Apenas valores de baixa confiança entram no lote LLM.
- **Contexto compacto**: o texto do PDF é reduzido a janelas relevantes (com normalização de acentos) antes de chamar o LLM e durante o recovery. Isso mantém o total de tokens e o `duration_ms` dentro da meta de 2–5 s.
- **Cache multinível**: resultados completos (label+schema) e conteúdo dos PDFs ficam em memória. A primeira execução aprende padrões; as seguintes respondem instantaneamente.
- **Recuperação paralela**: quando um campo crítico falha, as tentativas de recuperação são disparadas em paralelo (heurísticas relaxadas → prompt dedicado → contexto expandido). As decisões são logadas como `Field <nome> | recovery_success`.
- **Observabilidade**: `metadata.profiling` acompanha cada resposta, enquanto o backend escreve logs estruturados para cache hits, heurísticas, LLM e recovery (`docker-compose logs -f backend`).
- **UX responsiva**: o frontend mostra o JSON achatado (`flat`), mantêm os detalhes para exportações e processa lotes com até três uploads simultâneos, exibindo progresso parcial.

---

## 📁 Estrutura do Projeto

```
enter-ai/
├── backend/
│   ├── app/
│   │   ├── extractors/       # Lógica de extração
│   │   ├── services/          # Orquestração
│   │   ├── models.py          # Modelos Pydantic
│   │   └── config.py          # Configurações
│   ├── tests/                 # Testes automatizados
│   ├── scripts/               # Scripts utilitários
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env                   # Configurações (não versionado)
│   └── main.py                # Entry point da API
├── frontend/
│   ├── index.html             # Interface web
│   └── public/                # Assets estáticos
├── docs/
│   ├── data/
│   │   └── dataset.json       # Dataset de exemplos
│   └── files/                 # PDFs de exemplo
├── docker-compose.yml
├── nginx.conf
└── README.md
```

---

## 🔧 Configuração Avançada

### Variáveis de Ambiente (backend/.env)

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here
```

### Modelos Suportados
- Todos da OPEN AI

---

## 📝 Notas de Desenvolvimento

### Modo de Desenvolvimento com Docker

O docker-compose.yml inclui volumes para hot-reload:
```yaml
volumes:
  - ./backend/app:/app/app  # Alterações no código refletem automaticamente
```

Para produção, comente esta linha.

### Troubleshooting

**Problema**: API não carrega configurações
**Solução**: Verifique se o arquivo `.env` está no diretório `backend/`

**Problema**: Modelo não disponível
**Solução**: Verifique sua conta OpenAI e atualize `OPENAI_MODEL` no `.env`

**Problema**: CORS errors no frontend
**Solução**: Certifique-se de que o Nginx está configurado corretamente (nginx.conf)

---

## 📄 Licença

Este projeto foi desenvolvido como parte do Fellowship ENTER AI.

---

## 👤 Autor

**Matheus** - Fellowship ENTER AI 2025

---

## 🙏 Agradecimentos

- ENTER AI pelo desafio e oportunidade
- OpenAI pela API de IA
- Comunidade open source pelas ferramentas incríveis
