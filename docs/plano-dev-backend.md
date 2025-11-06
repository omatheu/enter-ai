# 🎯 SUMÁRIO EXECUTIVO E PLANO DE IMPLEMENTAÇÃO BACKEND

## 1. CONTEXTO GERAL

## ⚠️ ARMADILHAS COMUNS (EVITE!)

| Armadilha | Por quê | Solução |
|-----------|---------|---------|
| 1 chamada LLM por campo | Caro! N × custo | Batch: 1 chamada para todos |
| Enviar PDF inteiro para LLM | Muitos tokens! | Extrair só trechos relevantes |
| Sem validação | Erros passam | Validar: CPF, email, enum |
| Hardcode por label | Não escala | Genérico: funciona para qualquer |
| Sem cache | Reprocessa tudo | Cache: reusar resultados |
| Sem testes | Surpresas tarde | Teste em todos 6 exemplos |


### 1.1 O Desafio
Criar um **sistema de extração de dados estruturados de PDFs** que seja:
- **Rápido**: <10 segundos por requisição
- **Preciso**: 80%+ de acurácia
- **Econômico**: Minimizar custos de chamadas LLM
- **Adaptativo**: Desconhecer labels e schemas antecipadamente
- **Resiliente**: Tratar edge cases e variabilidade de layout

### 1.2 Restrições do Problema
- PDFs são single-page (já com OCR, texto embutido)
- Labels são desconhecidos antecipadamente
- Schema completo por label é fixo, mas recebemos subsets parciais
- Documentos do mesmo label têm layouts variáveis (especialmente contratos/faturas)
- **IMPORTANTE**: Sistema NÃO valida veracidade de dados

### 1.3 Requisito Crítico: SEM VALIDAÇÃO DE VERACIDADE
```
❌ Validar se CPF realmente existe
❌ Validar se email está ativo
❌ Validar se valores são legais/apropriados
❌ Validar qualquer aspecto semântico do dado

✅ Validar se o valor esta correto: comparar com o valor original.
```

---

## 2. ANÁLISE DO PROBLEMA

### 2.1 Cinco Desafios Técnicos Mapeados

#### Desafio 1: Redução de Custo LLM (50-95% economia possível)
**Problema**: Cada chamada LLM custa. Chamar para cada campo = caro.

**Solução Proposta**:
- ✅ Batch extraction: 1 chamada para N campos, não N chamadas
- ✅ Heurísticas primeiro: 60-80% dos campos via regex/template
- ✅ Cache por PDF: reusar resultados
- ✅ Context minimization: enviar o minímo de chars (sem perder a qualidade do contexto), não PDF inteiro
- ✅ Few-shot examples: usar exemplos do dataset no prompt

**Impacto**: De 100 chamadas → ~2-5 chamadas (98% economia)

---

#### Desafio 2: Variabilidade de Layout (60-80% reduz com aprendizado)
**Problema**: Mesmo label tem layouts diferentes (posição, formatação).

**Solução Proposta**:
- ✅ Template patterns por label: armazenar layouts típicos
- ✅ Heurísticas flexíveis: regex genéricos, não específicos
- ✅ Schema learning: após processar alguns docs, aprender padrões
- ✅ LLM para desambiguar: quando heurística encontra múltiplos matches

**Impacto**: Primeira requisição adapta, próximas usam padrões aprendidos (é importante que o sistema valide se o padrão aprendido ajudou ou não, ou seja, não seguir cegamente o 'aprendizado' anterior)

---

#### Desafio 3: Acurácia com Variabilidade (80% → 88%+ possível)
**Problema**: Manter 80%+ de acurácia mesmo com layouts diferentes.

**Solução Proposta**:
- ✅ Validação básica (tipo-checking): número? email? enum?
- ✅ Error recovery: retry com LLM se validação básica falha
- ✅ Confidence scoring: atribuir confiança por campo
- ✅ Enum matching: se schema menciona "pode ser X, Y, Z", procurar essas
- ✅ Context awareness: usar descrição do schema como hint

**Impacto**: Reduz falsos positivos e melhora precisão

---

#### Desafio 4: Performance <10s Garantido (2-5s possível)
**Problema**: LLM é lento. Precisa otimizar tempo de resposta.

**Solução Proposta**:
- ✅ Async processing: LLM em background, resposta rápida em foreground
- ✅ Early exit: se consegue responder com cache + heurística, não chamar LLM
- ✅ Profiling: medir cada componente
- ✅ Parallel heuristics: processar múltiplos campos em paralelo
- ✅ Contexto mínimo: extrair só trechos relevantes do PDF

**Impacto**: Primeira requisição 2-5s, cache hits <1s

---

#### Desafio 5: Adaptabilidade a Labels Desconhecidos (100% escalável)
**Problema**: Labels novos podem aparecer na avaliação.

**Solução Proposta**:
- ✅ Sem hardcoding: sistema genérico funciona para qualquer label
- ✅ Dynamic learning: primeira requisição descobre padrões
- ✅ Generic prompts: não mencionam labels específicos
- ✅ Pattern discovery: após 2-3 PDFs de um label, aprender layout

**Impacto**: Novo label funciona desde primeira requisição

---

### 2.2 Quando Precisar de Contexto Textual (LLM)?

#### Você PRECISA de LLM quando:

1. **Heurística encontra ambiguidade**
   - Exemplo: 3 datas no PDF, qual é "data_assinatura"?
   - Solução: LLM lê contexto ("Assinado em...") e desambigua

2. **Heurística não encontra padrão**
   - Exemplo: campo é texto livre (descrição, comentários)
   - Solução: LLM compreende contexto semântico

3. **Campo requer compreensão semântica**
   - Exemplo: "tipo_de_operacao" (precisa entender o que é operação)
   - Solução: LLM interpreta o contexto do documento

#### Você NÃO precisa de LLM quando:

- ✅ Heurística encontra 1 match unívoco
- ✅ Campo tem padrão claro (inscrição = número 6-dígitos)
- ✅ Campo em posição consistente (nome sempre primeira linha)
- ✅ Enums bem definidos (ADVOGADO, SUPLEMENTAR, etc)

**Implicação prática**: Heurísticas resolvem 60-80% dos campos

---

## 3. REQUISITOS FUNCIONAIS

### 3.1 Requisitos Principais

#### RF1: Extração de Dados
- **O quê**: Sistema extrai campos do PDF conforme schema solicitado
- **Como**: Via heurísticas + LLM (conforme necessidade)
- **Entrada**: (label, extraction_schema, pdf)
- **Saída**: JSON com {campo → valor_extraído}
- **Validação**: Apenas tipo-checking (não veracidade)

#### RF2: Cache de Resultados
- **O quê**: PDFs já processados retornam resultado em cache
- **Escopo**: Por PDF (hash do conteúdo)
- **Duração**: Apenas durante sessão (in-memory)
- **Impacto**: <100ms para requisições cached

#### RF3: Schema Learning
- **O quê**: Sistema aprende padrões para cada label
- **O que aprende**:
  - Campos vistos
  - Posições típicas
  - Formatos comuns
  - Fontes bem-sucedidas (heurística vs LLM)
- **Impacto**: Próximas requisições do label usam padrões

#### RF4: Heurísticas Inteligentes
- **O quê**: Extrair campos sem chamar LLM
- **Técnicas**:
  - Regex para padrões (números, emails, datas, etc)
  - Template matching por posição
  - Enum matching (procurar valores específicos)
  - Keyword detection
- **Confiança**: ~60-80% dos campos

#### RF5: Validação Básica (Tipo-Checking)
- **O quê**: Validar se valor extraído é do tipo esperado
- **Valida**:
  - É número? (para campos numéricos)
  - É email? (validar @ e domínio)
  - É telefone? (validar dígitos)
  - É data? (validar formato DD/MM/YYYY)
  - É enum? (validar contra lista de valores)
- **NÃO valida**: Veracidade, existência, legalidade

#### RF6: Error Recovery
- **O quê**: Se validação falha, tentar novamente com LLM
- **Fluxo**:
  1. Heurística extrai valor
  2. Validação falha
  3. Retry com LLM (prompt mais específico)
  4. Se LLM também falha → null

#### RF7: LLM Integration
- **Modelo**: gpt-5-mini (OpenAI)
- **Modo**: Batch extraction (todos os campos em 1 chamada)
- **Contexto**: Texto do PDF + schema descriptions
- **Resposta**: JSON com {campo → valor}
- **Fallback**: Se parsing falha, retry com prompt mais rigoroso

#### RF8: Tratamento de Edge Cases
- **Campo não existe no PDF**: Retornar null ✓
- **Campo não tem padrão**: Tentar LLM
- **PDF corrompido/texto inválido**: Erro claro
- **Schema vazio/inválido**: Erro claro
- **Múltiplos matches em heurística**: Desambiguar com LLM

---

### 3.2 Requisitos Não-Funcionais

#### RNF1: Performance
- **Tempo total**: < 10s por requisição (média)
- **Tempo heurística**: ~200-500ms
- **Tempo LLM**: ~1-3s (chamada + parsing)
- **Tempo cache**: ~50-100ms
- **Target após otimizações**: 2-5s média

#### RNF2: Precisão
- **Target**: 80%+ de campos corretos
- **Definição**: Campo está 100% igual ao PDF (case-insensitive para validação)
- **Avaliação**: 1 caractere errado = campo errado

#### RNF3: Custo Econômico
- **Target**: Minimizar custo LLM
- **Métrica**: $ por documento
- **Target**: $0.001-0.003 por doc (vs $0.01 sem otimização)
- **Redução esperada**: 50-95% de economia

#### RNF4: Escalabilidade
- **Adaptável**: Funciona com labels desconhecidos
- **Genérico**: Sem hardcoding específico por label
- **Learning**: Sistema melhora com uso

#### RNF5: Confiabilidade
- **Processamento serial**: Cada requisição é independente
- **Sem estado compartilhado**: Exceto cache de sessão
- **Recuperação**: Error handling gracioso, mensagens claras

#### RNF6: Disponibilidade
- **API status**: Checar conexão OpenAI
- **Timeouts**: 10s max por requisição
- **Retry logic**: Implementado para falhas transientes

#### RNF7: Segurança
- **Validação de entrada**: Schema JSON, PDF válido
- **Rate limiting**: Opcional (conforme necessário)
- **Sem armazenamento persistente**: Cache apenas em sessão

#### RNF8: Manutenibilidade
- **Código limpo**: Modular, bem documentado
- **Sem hardcoding**: Genérico por design
- **Testável**: Cada componente testável isoladamente
- **Extensível**: Fácil adicionar novos labels/campos

---

## 4. ARQUITETURA BACKEND

### 4.1 Componentes Principais

```
┌──────────────────────────────────────┐
│        FASTAPI ENDPOINT              │
│        POST /extract                 │
└────────────────┬─────────────────────┘
                 │
        ┌────────▼─────────┐
        │  REQUEST HANDLER │
        │  (validate input)│
        └────────┬─────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌────────┐ ┌──────────┐ ┌────────────┐
│ Cache  │ │ PDF      │ │ Schema     │
│Manager │ │ Extractor│ │ Learner    │
└─┬──────┘ └────┬─────┘ └─────┬──────┘
  │             │             │
  │        ┌────▼────┐        │
  │        │  Text   │        │
  │        │ Extract │        │
  │        └────┬────┘        │
  │             │             │
  │    ┌────────▼────────┐    │
  │    │ For each field: │    │
  │    └────────┬────────┘    │
  │             │             │
  │    ┌────────▼──────────┐  │
  │    │ 1. Heuristics    │  │
  │    │ 2. Validate      │  │
  │    │ 3. If fail: LLM  │  │
  │    └────────┬──────────┘  │
  │             │             │
  │    ┌────────▼──────────┐  │
  │    │ LLM Extractor    │  │
  │    │ (batch call)     │  │
  │    └────────┬──────────┘  │
  │             │             │
  │    ┌────────▼──────────┐  │
  │    │ Validator        │  │
  │    │ (type-checking)  │  │
  │    └────────┬──────────┘  │
  │             │             │
  └─────────────┼──────────────┘
                │
        ┌───────▼──────────┐
        │ RESPONSE BUILDER │
        │ (format output)  │
        └────────┬─────────┘
                 │
        ┌────────▼──────────┐
        │  RESPONSE JSON    │
        │ {results, meta}   │
        └───────────────────┘
```

### 4.2 Stack Recomendado

```
Backend:
├─ Framework: FastAPI
├─ Language: Python 3.9+
├─ Async: asyncio + aiohttp
├─ PDF: pdfplumber
├─ LLM: OpenAI API (gpt-4o-mini)
├─ Validation: Pydantic
├─ Cache: In-memory dict (sessão)
└─ Logging: Built-in + structured

Dependencies (requirements.txt):
├─ fastapi==0.104.1
├─ uvicorn==0.24.0
├─ pydantic==2.5.0
├─ pdfplumber==0.10.3
├─ openai==1.3.0
├─ python-dotenv==1.0.0
├─ aiohttp==3.9.1
└─ (opcional) sqlalchemy, redis para persistência
```

---

## 5. PLANO DE IMPLEMENTAÇÃO COMPLETO (8-10 HORAS)

### FASE 1: MVP SIMPLES (2-3 horas)
**Objetivo**: Sistema funcional, sem otimizações

#### 1.1 Setup Inicial (30 min)
- [ ] Setup venv + requirements.txt
- [ ] Configurar variáveis de ambiente (OPENAI_API_KEY)
- [ ] Setup logging básico  

#### 1.2 Modelos Pydantic (30 min)
- [ ] ExtractionRequest: (label, schema, pdf_path)
- [ ] ExtractionResult: (label, results, metadata)
- [ ] FieldResult: (field_name, value, source, confidence)

#### 1.3 PDF Extractor (45 min)
```python
# extractors/pdf_extractor.py
class PDFExtractor:
    @staticmethod
    def extract_text(pdf_path: str) -> str:
        """Extrai texto com pdfplumber"""
        
    @staticmethod
    def extract_tables(pdf_path: str) -> list:
        """Extrai tabelas se existirem"""
```

#### 1.4 LLM Extractor - Simples (45 min)
```python
# extractors/llm_extractor.py
class LLMExtractor:
    @staticmethod
    async def extract_fields(
        text: str,
        label: str,
        schema: Dict[str, str]
    ) -> Dict[str, Optional[Any]]:
        """
        Chama OpenAI para extrair TODOS os campos de uma vez
        Entrada: texto do PDF, schema
        Saída: {campo → valor}
        """
```

#### 1.5 FastAPI Endpoint (30 min)
```python
# main.py
@app.post("/extract")
async def extract(
    label: str = Form(...),
    extraction_schema: str = Form(...),
    pdf_file: UploadFile = File(...)
):
    """Endpoint simples: extract PDF conforme schema"""
```

#### 1.6 Testes Iniciais (15 min)
- [ ] Testar com 1 exemplo do dataset
- [ ] Verificar time, output format
- [ ] Checklist básico: funciona? tempo OK?

**Saída Fase 1**: Sistema funcional, mas lento e caro
- Precisão: ~70%
- Tempo: ~8-10s
- Custo: Alto (1 LLM call/requisição)

---

### FASE 2: OTIMIZAÇÕES (2-3 horas) ⭐ CRÍTICA
**Objetivo**: Reduzir custo LLM em 50-95%, manter precisão 80%+

#### 2.1 Heuristics Engine (1 hora)
```python
# extractors/heuristics.py
class HeuristicExtractor:
    PATTERNS = {
        "cpf": r"\d{3}\.\d{3}\.\d{3}-\d{2}",
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "telefone": r"(\+55)?\s*(\d{2})\s*9?\d{4}-?\d{4}",
        "data": r"\d{1,2}/\d{1,2}/\d{4}",
        # ... mais patterns
    }
    
    @staticmethod
    def extract_by_field_name(field: str, text: str) -> Optional[Any]:
        """Tenta usar nome do campo para adivinhar padrão"""
        
    @staticmethod
    def extract_by_description(desc: str, text: str) -> Optional[Any]:
        """Tenta usar descrição para adivinhar padrão"""
        
    @staticmethod
    def extract_enum_values(desc: str, text: str) -> Optional[str]:
        """Se descrição menciona 'pode ser X, Y, Z', procura por elas"""
```

#### 2.2 Validator (45 min)
```python
# extractors/validator.py
class Validator:
    @staticmethod
    def validate_cpf(value: str) -> bool: pass
    
    @staticmethod
    def validate_email(value: str) -> bool: pass
    
    @staticmethod
    def validate_phone(value: str) -> bool: pass
    
    @staticmethod
    def validate_date(value: str) -> bool: pass
    
    @staticmethod
    def validate_enum(value: str, allowed: list) -> bool: pass
    
    @staticmethod
    def validate_field(
        field_name: str,
        value: Any,
        field_description: str = ""
    ) -> tuple[bool, Optional[Any]]:
        """Valida tipo/formato, não veracidade"""
```

#### 2.3 Cache Manager (30 min)
```python
# cache/memory_cache.py
class MemoryCache:
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
    
    def get_pdf_result(self, pdf_hash: str) -> Optional[Dict]:
        """Retorna resultado se PDF já foi processado"""
        
    def set_pdf_result(self, pdf_hash: str, result: Dict):
        """Cacheia resultado para futuras requisições"""
```

#### 2.4 Schema Learner (30 min)
```python
# schema/patterns.py
class SchemaLearner:
    def __init__(self):
        self.learned: Dict[str, Dict] = {}
    
    def learn_from_result(
        self,
        label: str,
        schema: Dict,
        results: Dict,
        source_analysis: Dict  # campo → "llm", "heuristic"
    ):
        """Aprende padrões para este label"""
        
    def get_patterns(self, label: str) -> Dict:
        """Retorna padrões aprendidos"""
        
    def suggest_source_for_field(self, label: str, field: str) -> str:
        """Sugere qual source usar (heuristic vs llm)"""
```

#### 2.5 Refactor Main Extractor (30 min)
```python
# main.py - Atualizar fluxo
@app.post("/extract")
async def extract(...):
    """
    Novo fluxo:
    1. Check cache by PDF
    2. Learn patterns for label
    3. For each field:
       - Try heuristic
       - If success + validation OK → use
       - Else → mark for LLM
    4. Batch call LLM for remaining fields
    5. Validate LLM results
    6. Cache result
    7. Return
    """
```

#### 2.6 Testes Otimizados (30 min)
- [ ] Testar com todos 6 exemplos
- [ ] Medir: tempo < 5s? precisão >= 80%?
- [ ] Contar chamadas LLM: devem ser << 1 por requisição
- [ ] Estimar custo: deve ser ~50% menos que Fase 1

**Saída Fase 2**: Sistema otimizado
- Precisão: 80-85%
- Tempo: 2-5s
- Custo: 50% reduzido
- LLM calls: 0.3-0.5 por requisição (vs 1.0 na Fase 1)

---

### FASE 3: VALIDAÇÃO & ACURÁCIA (1-2 horas)
**Objetivo**: Garantir 80%+ acurácia consistentemente

#### 3.1 Error Recovery (30 min)
```python
# extractors/error_recovery.py
async def extract_with_recovery(
    field: str,
    description: str,
    text: str,
    llm_extractor
) -> tuple[Any, str]:
    """
    Tenta extrair com múltiplas estratégias até sucesso:
    1. Heurística
    2. Template
    3. LLM com prompt específico
    4. LLM com contexto expandido
    5. Return null
    """
```

#### 3.2 Confidence Scoring (30 min)
```python
# schema/confidence.py
class ConfidenceScorer:
    @staticmethod
    def score_extraction(
        field: str,
        value: str,
        description: str,
        source: str,
        context: str = ""
    ) -> float:
        """
        Score 0.0-1.0 baseado em:
        - Source (cache=1.0, llm=0.85, heuristic=0.6)
        - Validation result
        - Field commonality
        - Context matching
        """
    
    @staticmethod
    def should_retry_with_llm(confidence: float, field: str) -> bool:
        """Decide se deve chamar LLM para refinar"""
```

#### 3.3 Teste em Todos 6 Exemplos (30 min)
- [ ] Executar extraction em todos 6 exemplos
- [ ] Anotar erros encontrados
- [ ] Calcular precisão média
- [ ] Verify: 80%+ alcançado?

**Saída Fase 3**: Sistema validado
- Precisão: 85%+ confirmada
- Edge cases tratados
- Error recovery funcional

---

### FASE 4: PERFORMANCE (1-2 horas)
**Objetivo**: <10s garantido, otimizar para 2-5s média

#### 4.1 Profiling (30 min)
```python
# utils/profiling.py
def profile_extraction(extraction_time):
    """Mede tempo de cada componente"""
    - PDF text extraction: XXms
    - Heuristics: XXms
    - LLM call: XXms
    - Validation: XXms
    - Total: XXms
```

#### 4.2 Optimizações de Performance (45 min)
- [ ] Se PDF extraction lenta: otimizar pdfplumber
- [ ] Se heuristics lenta: parallelizar
- [ ] Se LLM lenta: reduzir context, usar async melhor
- [ ] Se validation lenta: cachear regras

#### 4.3 Async/Await Refinement (15 min)
- [ ] Verificar que LLM é truly async
- [ ] Não bloqueia main thread
- [ ] Outras operações podem rodar em paralelo

#### 4.4 Teste de Performance (15 min)
- [ ] Rodar em todos 6 exemplos
- [ ] Medir: min, max, average
- [ ] Verify: 100% < 10s? Average < 5s?

**Saída Fase 4**: Sistema rápido
- Tempo: 2-5s média garantido
- Máximo: 10s em todos casos

---

### FASE 5: POLISH & DOCUMENTAÇÃO (2 horas)
**Objetivo**: Pronto para entrega profissional

#### 5.1 Edge Cases Finais (30 min)
- [ ] Campo não existe no PDF → null ✓
- [ ] PDF corrompido → erro claro
- [ ] Schema vazio → erro claro
- [ ] Texto inválido/garbled → recovery gracioso

#### 5.2 Logging Robusto (30 min)
```python
# Adicionar logging em cada componente
logger.info(f"Extracting {field}: trying heuristic")
logger.info(f"Heuristic failed, calling LLM")
logger.info(f"LLM returned {value}, validating")
logger.info(f"Field extracted successfully via {source}")
```

#### 5.3 README Completo (30 min)
**Incluir**:
- Descrição do desafio
- Desafios técnicos mapeados (5 principais)
- Soluções propostas para cada
- Trade-offs considerados
- Arquitetura de solução
- Como instalar e usar
- Exemplos de uso (curl, Python client)
- Métricas nos 6 exemplos (tempo, precisão, custo)

#### 5.4 Git & Cleanup (30 min)
- [ ] Commits descritivos em cada fase
- [ ] .gitignore apropriado
- [ ] Code cleanup (remover debug prints)
- [ ] Repository público no GitHub

**Saída Fase 5**: Pronto para entrega

---

## 6. ESPECIFICAÇÃO TÉCNICA DETALHADA

### 6.1 Fluxo de Extração por Campo (Corrigido)

```python
async def extract_field(
    field_name: str,
    field_description: str,
    text: str,
    llm_extractor,
    cache_data: dict,
    learned_patterns: dict
) -> tuple[Any, str]:  # (valor, source)
    """
    Extrai campo com fluxo correto.
    
    Fluxo de decisão:
    1. CACHE? → return valor cacheado
    2. HEURÍSTICA SEGURA (1 match unívoco)?
        - SIM + validação OK? → return valor
        - NÃO ou validação falha? → marcar para LLM
    3. LLM (contexto para desambiguar/extrair)
        - Chamar com contexto relevante
        - Parse resposta
        - Validar resultado
    4. RETURN (valor ou null)
    """
    
    # 1. CACHE
    if field_name in cache_data:
        return cache_data[field_name], "cache"
    
    # 2. HEURÍSTICA
    heuristic_matches = apply_heuristic(field_name, field_description, text)
    
    if len(heuristic_matches) == 1:
        # 1 match unívoco
        value = heuristic_matches[0]
        if validate_format(field_name, value):
            return value, "heuristic"
        # Falha validação, tenta LLM
    
    elif len(heuristic_matches) > 1:
        # Múltiplos matches: ambiguidade
        # Precisa LLM para desambiguar
        pass
    
    # 3. LLM (se chegou aqui)
    llm_value = await llm_extractor.extract_single_field(
        text=text,
        field_name=field_name,
        field_description=field_description
    )
    
    if llm_value is not None and validate_format(field_name, llm_value):
        return llm_value, "llm"
    
    # 4. RETURN null
    return None, "null"
```

### 6.2 Requisição HTTP

```
POST /extract HTTP/1.1
Content-Type: multipart/form-data

label: carteira_oab
extraction_schema: {
  "nome": "Nome do profissional...",
  "inscricao": "Número de inscrição...",
  ...
}
pdf_file: [binary PDF data]
```

### 6.3 Resposta HTTP

```json
{
  "label": "carteira_oab",
  "results": {
    "nome": "JOANA D'ARC",
    "inscricao": "101943",
    "seccional": "PR",
    "subsecao": "CONSELHO SECCIONAL - PARANÁ",
    "categoria": "SUPLEMENTAR",
    "telefone_profissional": null,
    "situacao": "SITUAÇÃO REGULAR"
  },
  "metadata": {
    "elapsed_seconds": 2.3,
    "text_length": 1245,
    "heuristics_used": 5,
    "llm_calls": 1,
    "fields_null": 1,
    "source": "mixed",
    "fields_sources": {
      "nome": "heuristic",
      "inscricao": "heuristic",
      "seccional": "heuristic",
      "subsecao": "heuristic",
      "categoria": "heuristic",
      "telefone_profissional": "null",
      "situacao": "llm"
    },
    "confidence_scores": {
      "nome": 0.95,
      "inscricao": 0.98,
      "seccional": 0.99,
      "subsecao": 0.90,
      "categoria": 0.99,
      "telefone_profissional": 0.0,
      "situacao": 0.85
    }
  }
}
```

### 6.4 Estrutura de Pastas

```
project/
├── main.py                          # FastAPI app
├── config.py                        # Configuration
├── requirements.txt                 # Dependencies
├── README.md                        # Documentation
│
├── extractors/
│   ├── __init__.py
│   ├── pdf_extractor.py            # Extração de texto
│   ├── llm_extractor.py            # LLM integration
│   ├── heuristics.py               # Padrões e regras
│   ├── validator.py                # Validação tipo-checking
│   ├── error_recovery.py           # Error handling
│   └── confidence.py               # Confidence scoring
│
├── schema/
│   ├── __init__.py
│   ├── models.py                   # Pydantic models
│   ├── patterns.py                 # Schema learner
│   └── confidence.py               # Confidence scoring
│
├── cache/
│   ├── __init__.py
│   └── memory_cache.py             # In-memory cache
│
├── utils/
│   ├── __init__.py
│   ├── profiling.py                # Performance metrics
│   ├── logging.py                  # Logging setup
│   └── helpers.py                  # Utility functions
│
├── tests/
│   ├── __init__.py
│   ├── test_extraction.py          # Integration tests
│   ├── test_heuristics.py          # Unit tests
│   └── test_validator.py           # Unit tests
│
└── data/
    └── examples/                   # 6 exemplos do dataset
```

---

## 7. MÉTRICAS DE SUCESSO

### 7.1 Métricas por Fase

| Métrica | Fase 1 | Fase 2 | Fase 3 | Fase 4 | Fase 5 |
|---------|--------|--------|--------|--------|--------|
| Funcionalidade | ✅ | ✅ | ✅ | ✅ | ✅ |
| Precisão | 70% | 80% | 85%+ | 85%+ | 85%+ |
| Tempo | 8-10s | 2-5s | 2-5s | 2-5s | 2-5s |
| Custo | Alto | Médio | Médio | Médio | Médio |
| LLM calls | 1.0/req | 0.3-0.5/req | 0.3-0.5/req | 0.3-0.5/req | 0.3-0.5/req |
| Cache hits | 0% | 0% | 0% | Crescente | Crescente |

### 7.2 Metas Finais

```
✅ Precisão: 85%+ (meta: 80%)
✅ Tempo: 2-5s (meta: <10s)
✅ Custo: $0.001-0.003/doc (meta: mínimo)
✅ Código: Limpo, modular, bem documentado
✅ README: Excelente, com desafios + soluções
✅ GitHub: Público com commits descritivos
```

---

## 8. IMPORTANT: O QUE NÃO FAZER

### ❌ Armadilhas Comuns

1. **Uma chamada LLM por campo**
   - ❌ Caro! N campos = N chamadas
   - ✅ Batch: 1 chamada para N campos

2. **Enviar PDF inteiro para LLM**
   - ❌ Muitos tokens!
   - ✅ Extrair trechos relevantes (2000 chars)

3. **Sem validação de formato**
   - ❌ Heurística pode achar lixo
   - ✅ Validar: é número? é email?

4. **Validar veracidade dos dados**
   - ❌ Fora do escopo
   - ✅ Apenas tipo-checking

5. **Hardcoding por label**
   - ❌ Não escala
   - ✅ Genérico: funciona para qualquer label

6. **Sem cache**
   - ❌ Reprocessa tudo
   - ✅ Cache: reusar resultados

7. **Sem logging**
   - ❌ Impossível debugar
   - ✅ Log cada decisão

---

## 9. ESTIMATIVAS REALISTAS

### Tempo Total: 8-10 horas

```
Fase 1 (MVP):        2-3 horas
Fase 2 (Otimizar):   2-3 horas
Fase 3 (Validar):    1-2 horas
Fase 4 (Performance):1-2 horas
Fase 5 (Polish):     1-2 horas
─────────────────
TOTAL:               8-10 horas
```

### Recursos

```
Linguagem:    Python 3.9+
Framework:    FastAPI
LLM:          OpenAI (gpt-5-mini)
API Key:      Fornecido (com budget)
Tempo:        8-10 horas
Deadline:     07/NOV, meio-dia
```

---

## 10. CHECKLIST FINAL

### Funcionais
- [ ] Extração de campos via heurísticas + LLM
- [ ] Cache de PDFs processados
- [ ] Schema learning por label
- [ ] Validação de tipo-checking
- [ ] Error recovery
- [ ] LLM batch extraction
- [ ] Tratamento de edge cases
- [ ] Endpoint /extract funcional

### Não-Funcionais
- [ ] Tempo < 10s por requisição
- [ ] Precisão 80%+
- [ ] Custo otimizado (50%+ economia)
- [ ] Adaptável a labels desconhecidos
- [ ] Código limpo e modular
- [ ] Sem hardcoding
- [ ] Logging completo
- [ ] Performance profiling

### Documentação
- [ ] README com desafios + soluções
- [ ] Trade-offs documentados
- [ ] Como instalar e usar
- [ ] Exemplos de uso
- [ ] Métricas nos 6 exemplos
- [ ] GitHub público

### Testes
- [ ] Todos 6 exemplos funcionam
- [ ] Precisão 80%+ confirmada
- [ ] Tempo < 10s confirmado
- [ ] Edge cases testados

---

## 11. PRÓXIMOS PASSOS IMEDIATOS

1. **Setup** (15 min): Clone repo, setup venv, configure API key
2. **Fase 1** (2h): Implemente MVP simples com LLM
3. **Teste**: Valide com 1 exemplo
4. **Fase 2** (2h): Adicione heurísticas + cache
5. **Teste**: Validate tempo < 5s, precisão 80%
6. **Fase 3-5** (4h): Validação, performance, polish
7. **Entrega**: README + GitHub

**Total até pronto**: 8-10 horas ✅

---

Você agora tem um **plano backend completo, estruturado e pronto para implementação**. Boa sorte! 🚀