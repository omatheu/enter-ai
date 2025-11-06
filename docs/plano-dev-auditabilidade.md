# 🔍 SISTEMA DE AUDITORIA INTELIGENTE E AUTOMÁTICA

## 1. VISÃO GERAL

Sistema que **rastreia automaticamente cada decisão** tomada durante o processamento e gera uma **descrição auditável** da execução.

### 1.1 O que é Auditado?

```
Para cada requisição:
├─ Que estratégia foi usada para cada campo?
├─ Qual foi o resultado?
├─ Por que essa estratégia foi escolhida?
├─ Quanto custou (em tokens/LLM)?
├─ Quanto tempo levou?
├─ Qual foi a confiança do resultado?
└─ Como isso contribuiu para a decisão final?
```

### 1.2 Exemplo de Saída com Auditoria

```json
{
  "label": "carteira_oab",
  "results": {
    "nome": "JOANA D'ARC",
    "inscricao": "101943",
    ...
  },
  "metadata": {
    "elapsed_seconds": 2.3,
    "cost_estimate": "$0.0023",
    "llm_calls": 1
  },
  "audit_trail": {
    "summary": "Extracted 7 fields with 6 via heuristics + 1 via LLM. Cache miss. High confidence.",
    "decision_log": [
      {
        "field": "nome",
        "strategy": "heuristic",
        "substrategy": "position_based",
        "confidence": 0.95,
        "description": "Found in first line (all caps). Position-based heuristic with 95% confidence.",
        "alternatives_tried": [],
        "cost": 0,
        "time_ms": 12
      },
      {
        "field": "inscricao",
        "strategy": "heuristic",
        "substrategy": "regex_pattern",
        "confidence": 0.98,
        "description": "Matched regex pattern for 6-digit number after 'Inscrição'. High confidence match.",
        "alternatives_tried": [],
        "cost": 0,
        "time_ms": 8
      },
      {
        "field": "telefone_profissional",
        "strategy": "llm",
        "substrategy": "semantic_extraction",
        "confidence": 0.60,
        "description": "No heuristic pattern found. Called LLM to understand context and extract. Result: null (field empty in document).",
        "alternatives_tried": ["regex_phone_pattern"],
        "cost": 0.00023,
        "time_ms": 1200,
        "llm_reasoning": "Field marked as 'Telefone Profissional' in document but no value present. Returned null correctly."
      }
    ],
    "process_flow": "cache_miss → pdf_extract(200ms) → heuristics_60pct(80ms) → llm_batch_1call(1200ms) → validation(50ms) → audit_logging(20ms)",
    "efficiency_score": 0.92,
    "audit_notes": [
      "✅ High coverage: 85.7% fields extracted via heuristics (low cost)",
      "✅ Strategic LLM use: 1 call for 1 ambiguous field only",
      "✅ Fast processing: 2.3s (well below 10s limit)",
      "⚠️ One null field: 'telefone_profissional' empty in source document"
    ]
  }
}
```

---

## 2. ARQUITETURA DE AUDITORIA

### 2.1 Componentes Principais

```
┌─────────────────────────────────────┐
│   AUDIT MANAGER (Central)           │
│   - Inicia contexto de auditoria    │
│   - Coleta eventos de cada módulo   │
│   - Gera relatório final            │
└──────────────┬──────────────────────┘
               │
    ┌──────────┴──────────┬──────────────┐
    │                     │              │
    ▼                     ▼              ▼
┌──────────┐      ┌──────────────┐   ┌─────────────┐
│Heuristic │      │ LLM Extractor│   │  Validator  │
│Event Log │      │ Event Log    │   │ Event Log   │
└──────────┘      └──────────────┘   └─────────────┘
    │                     │              │
    └──────────┬──────────┴──────────────┘
               │
    ┌──────────▼────────────┐
    │ Audit Report Builder  │
    │ - Formata eventos     │
    │ - Gera descrição      │
    │ - Calcula métricas    │
    └──────────┬────────────┘
               │
    ┌──────────▼────────────┐
    │  Audit Trail (JSON)   │
    │  - decision_log       │
    │  - process_flow       │
    │  - efficiency_score   │
    │  - audit_notes        │
    └───────────────────────┘
```

---

## 3. IMPLEMENTAÇÃO PRÁTICA

### 3.1 Modelos Pydantic para Auditoria

```python
# schema/audit_models.py
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

class AuditEvent:
    """Evento auditável (simples, rápido)"""
    def __init__(
        self,
        field_name: str,
        strategy: str,  # "heuristic", "llm", "cache", "null"
        substrategy: str,  # "regex_pattern", "position_based", "semantic_extraction", etc
        confidence: float,  # 0.0-1.0
        value: Any,
        time_ms: float,
        cost: float = 0.0,
        description: str = "",
        alternatives_tried: List[str] = None,
        llm_reasoning: str = ""
    ):
        self.field_name = field_name
        self.strategy = strategy
        self.substrategy = substrategy
        self.confidence = confidence
        self.value = value
        self.time_ms = time_ms
        self.cost = cost
        self.description = description
        self.alternatives_tried = alternatives_tried or []
        self.llm_reasoning = llm_reasoning

class FieldDecisionLog(BaseModel):
    """Log de decisão para um campo (para output JSON)"""
    field: str
    strategy: str  # "heuristic", "llm", "cache", "null"
    substrategy: str
    confidence: float
    description: str
    alternatives_tried: List[str] = []
    cost: float
    time_ms: float
    llm_reasoning: Optional[str] = None
    value: Optional[Any] = None  # Para auditoria de valor final

class AuditTrail(BaseModel):
    """Auditoria completa de uma extração"""
    summary: str  # Resumo em português
    decision_log: List[FieldDecisionLog]
    process_flow: str  # Descrição do fluxo: cache_miss → pdf_extract → heuristics → llm → validation
    efficiency_score: float  # 0.0-1.0 (quanto % foi resolvido sem LLM?)
    audit_notes: List[str]  # Observações: ✅, ⚠️, ❌

class ExtractionResultWithAudit(BaseModel):
    """Resultado final com auditoria integrada"""
    label: str
    results: Dict[str, Optional[Any]]
    metadata: Dict[str, Any]  # elapsed_seconds, cost_estimate, llm_calls, etc
    audit_trail: AuditTrail
```

### 3.2 Audit Manager - Classe Central

```python
# audit/audit_manager.py
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from schema.audit_models import AuditEvent, FieldDecisionLog, AuditTrail, ExtractionResultWithAudit

class AuditManager:
    """Gerencia auditoria de toda a extração"""
    
    def __init__(self, request_id: str = None):
        self.request_id = request_id or f"req_{datetime.now().timestamp()}"
        self.events: List[AuditEvent] = []
        self.start_time = time.time()
        self.llm_call_count = 0
        self.total_cost = 0.0
        self.cache_hit = False
        self.pdf_extract_time = 0.0
    
    def log_event(
        self,
        field_name: str,
        strategy: str,
        substrategy: str,
        confidence: float,
        value: Any,
        time_ms: float,
        cost: float = 0.0,
        description: str = "",
        alternatives_tried: List[str] = None,
        llm_reasoning: str = ""
    ):
        """Registra um evento de auditoria"""
        event = AuditEvent(
            field_name=field_name,
            strategy=strategy,
            substrategy=substrategy,
            confidence=confidence,
            value=value,
            time_ms=time_ms,
            cost=cost,
            description=description,
            alternatives_tried=alternatives_tried,
            llm_reasoning=llm_reasoning
        )
        self.events.append(event)
        self.total_cost += cost
        
        if strategy == "llm":
            self.llm_call_count += 1
    
    def generate_summary(self) -> str:
        """Gera sumário em linguagem natural"""
        if not self.events:
            return "No events recorded"
        
        total_fields = len(self.events)
        heuristic_fields = sum(1 for e in self.events if e.strategy == "heuristic")
        llm_fields = sum(1 for e in self.events if e.strategy == "llm")
        cache_fields = sum(1 for e in self.events if e.strategy == "cache")
        null_fields = sum(1 for e in self.events if e.strategy == "null")
        
        avg_confidence = sum(e.confidence for e in self.events) / total_fields if total_fields > 0 else 0
        
        summary = f"Extracted {total_fields} fields with "
        parts = []
        
        if heuristic_fields > 0:
            parts.append(f"{heuristic_fields} via heuristics")
        if llm_fields > 0:
            parts.append(f"{llm_fields} via LLM")
        if cache_fields > 0:
            parts.append(f"{cache_fields} from cache")
        if null_fields > 0:
            parts.append(f"{null_fields} null/not found")
        
        summary += " + ".join(parts) + ". "
        
        if self.cache_hit:
            summary += "Cache hit (fast processing). "
        else:
            summary += "Cache miss. "
        
        summary += f"Average confidence: {avg_confidence:.1%}. "
        
        if avg_confidence > 0.85:
            summary += "High confidence results."
        elif avg_confidence > 0.70:
            summary += "Moderate confidence results."
        else:
            summary += "Low confidence - manual review recommended."
        
        return summary
    
    def generate_decision_log(self) -> List[FieldDecisionLog]:
        """Gera log de decisões estruturado"""
        return [
            FieldDecisionLog(
                field=event.field_name,
                strategy=event.strategy,
                substrategy=event.substrategy,
                confidence=event.confidence,
                description=event.description,
                alternatives_tried=event.alternatives_tried,
                cost=event.cost,
                time_ms=event.time_ms,
                llm_reasoning=event.llm_reasoning if event.llm_reasoning else None,
                value=str(event.value) if event.value is not None else None
            )
            for event in self.events
        ]
    
    def generate_process_flow(self) -> str:
        """Descreve o fluxo de processamento"""
        flow_steps = []
        
        if self.cache_hit:
            flow_steps.append("cache_hit")
        else:
            flow_steps.append("cache_miss")
        
        if self.pdf_extract_time > 0:
            flow_steps.append(f"pdf_extract({self.pdf_extract_time:.0f}ms)")
        
        # Agrupar estratégias
        has_heuristics = any(e.strategy == "heuristic" for e in self.events)
        has_llm = any(e.strategy == "llm" for e in self.events)
        
        if has_heuristics:
            heuristic_time = sum(e.time_ms for e in self.events if e.strategy == "heuristic")
            flow_steps.append(f"heuristics({heuristic_time:.0f}ms)")
        
        if has_llm:
            llm_time = sum(e.time_ms for e in self.events if e.strategy == "llm")
            flow_steps.append(f"llm_batch_{self.llm_call_count}_call({llm_time:.0f}ms)")
        
        validation_time = 50  # Estimativa
        flow_steps.append(f"validation({validation_time}ms)")
        flow_steps.append("audit_logging(20ms)")
        
        return " → ".join(flow_steps)
    
    def calculate_efficiency_score(self) -> float:
        """
        Calcula score de eficiência (0.0-1.0)
        Baseado em: % de campos via heurística, tempo economizado, custo economizado
        """
        if not self.events:
            return 0.0
        
        total_fields = len(self.events)
        heuristic_fields = sum(1 for e in self.events if e.strategy == "heuristic")
        cache_fields = sum(1 for e in self.events if e.strategy == "cache")
        
        # Heurística é mais eficiente que LLM
        efficiency = (heuristic_fields + cache_fields) / total_fields
        
        # Bônus se tem alta confiança
        avg_confidence = sum(e.confidence for e in self.events) / total_fields
        if avg_confidence > 0.85:
            efficiency *= 1.1
        
        return min(1.0, efficiency)
    
    def generate_audit_notes(self) -> List[str]:
        """Gera observações estruturadas"""
        notes = []
        
        # Análise de cobertura
        total_fields = len(self.events)
        heuristic_fields = sum(1 for e in self.events if e.strategy == "heuristic")
        heuristic_pct = (heuristic_fields / total_fields * 100) if total_fields > 0 else 0
        
        if heuristic_pct >= 80:
            notes.append(f"✅ High coverage: {heuristic_pct:.1f}% fields extracted via heuristics (low cost)")
        elif heuristic_pct >= 60:
            notes.append(f"✅ Good coverage: {heuristic_pct:.1f}% fields via heuristics")
        else:
            notes.append(f"⚠️ Low coverage: {heuristic_pct:.1f}% fields via heuristics (more LLM needed)")
        
        # Análise de LLM
        if self.llm_call_count > 0:
            llm_fields = sum(1 for e in self.events if e.strategy == "llm")
            notes.append(f"✅ Strategic LLM use: {self.llm_call_count} call(s) for {llm_fields} field(s)")
        else:
            notes.append("✅ Zero LLM calls (pure heuristics/cache)")
        
        # Análise de confiança
        avg_confidence = sum(e.confidence for e in self.events) / total_fields if total_fields > 0 else 0
        if avg_confidence > 0.85:
            notes.append(f"✅ High confidence: {avg_confidence:.1%} average confidence")
        elif avg_confidence > 0.70:
            notes.append(f"⚠️ Moderate confidence: {avg_confidence:.1%} (verify critical fields)")
        else:
            notes.append(f"❌ Low confidence: {avg_confidence:.1%} (manual review recommended)")
        
        # Análise de campos nulos
        null_fields = [e for e in self.events if e.strategy == "null"]
        if null_fields:
            fields_list = ", ".join([f"'{e.field_name}'" for e in null_fields])
            notes.append(f"⚠️ Null fields: {fields_list} empty in source document")
        
        # Análise de custo
        if self.total_cost > 0:
            notes.append(f"💰 Processing cost: ${self.total_cost:.6f}")
        
        return notes
    
    def generate_audit_trail(self) -> AuditTrail:
        """Gera auditoria completa"""
        return AuditTrail(
            summary=self.generate_summary(),
            decision_log=self.generate_decision_log(),
            process_flow=self.generate_process_flow(),
            efficiency_score=self.calculate_efficiency_score(),
            audit_notes=self.generate_audit_notes()
        )
    
    def get_elapsed_time(self) -> float:
        """Tempo total de processamento"""
        return time.time() - self.start_time
    
    def get_cost_estimate(self) -> str:
        """Estimativa de custo em formato legível"""
        return f"${self.total_cost:.6f}"
```

---

## 4. INTEGRAÇÃO COM EXTRACTORS

### 4.1 Heuristic Extractor com Auditoria

```python
# extractors/heuristics.py
class HeuristicExtractor:
    
    @staticmethod
    def extract_with_audit(
        field_name: str,
        field_description: str,
        text: str,
        audit_manager
    ) -> tuple[Optional[Any], str]:
        """
        Extrai campo com auditoria
        Retorna: (valor, strategy)
        """
        
        # Tentar regex
        patterns = HeuristicExtractor.get_patterns_for_field(field_name, field_description)
        
        for pattern_name, pattern in patterns.items():
            matches = re.findall(pattern, text)
            
            if len(matches) == 1:
                # Match unívoco!
                value = matches[0]
                
                audit_manager.log_event(
                    field_name=field_name,
                    strategy="heuristic",
                    substrategy=pattern_name,  # "email_pattern", "phone_pattern", etc
                    confidence=0.95,
                    value=value,
                    time_ms=time.time() * 1000,  # Simplificado
                    description=f"Found 1 match via {pattern_name} regex. High confidence.",
                    alternatives_tried=[]
                )
                
                return value, "heuristic"
            
            elif len(matches) > 1:
                # Múltiplos matches
                audit_manager.log_event(
                    field_name=field_name,
                    strategy="ambiguous",  # Marcador especial
                    substrategy=pattern_name,
                    confidence=0.5,  # Baixa confiança por ambiguidade
                    value=None,
                    time_ms=10,
                    description=f"Found {len(matches)} matches via {pattern_name}. Ambiguous - needs LLM.",
                    alternatives_tried=[pattern_name]
                )
                
                return None, "ambiguous"
        
        # Sem match
        audit_manager.log_event(
            field_name=field_name,
            strategy="no_heuristic",
            substrategy="no_pattern_match",
            confidence=0.0,
            value=None,
            time_ms=15,
            description=f"No heuristic pattern matched. Needs semantic extraction.",
            alternatives_tried=list(patterns.keys())
        )
        
        return None, "no_heuristic"
```

### 4.2 LLM Extractor com Auditoria

```python
# extractors/llm_extractor.py
class LLMExtractor:
    
    @staticmethod
    async def extract_fields_with_audit(
        text: str,
        label: str,
        schema: Dict[str, str],
        fields_to_extract: List[str],  # Quais campos precisam LLM
        audit_manager
    ) -> Dict[str, Any]:
        """
        Extrai campos via LLM com auditoria
        """
        
        start_time = time.time()
        
        # Construir prompt
        fields_desc = "\n".join([
            f"- {field}: {schema[field]}"
            for field in fields_to_extract
        ])
        
        prompt = f"""...prompt com contexto..."""
        
        # Chamar LLM
        response = await openai.ChatCompletion.acreate(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Estimar custo
        tokens_in = len(prompt.split())
        tokens_out = len(response.choices[0].message.content.split())
        cost = (tokens_in * 0.15 + tokens_out * 0.60) / 1_000_000
        
        # Parse resultado
        result = json.loads(response.choices[0].message.content)
        
        # Log auditoria para cada campo
        for field in fields_to_extract:
            value = result.get(field)
            
            audit_manager.log_event(
                field_name=field,
                strategy="llm",
                substrategy="semantic_extraction",
                confidence=0.85,  # Padrão para LLM
                value=value,
                time_ms=elapsed_ms / len(fields_to_extract),  # Distribuir tempo
                cost=cost / len(fields_to_extract),  # Distribuir custo
                description=f"Extracted via LLM semantic analysis.",
                llm_reasoning=f"LLM interpreted context and extracted '{field}' value: {value}"
            )
        
        return result
```

### 4.3 Validator com Auditoria

```python
# extractors/validator.py
class Validator:
    
    @staticmethod
    def validate_with_audit(
        field_name: str,
        value: Any,
        field_description: str,
        original_source: str,  # "heuristic" ou "llm"
        audit_manager
    ) -> tuple[bool, Optional[Any]]:
        """
        Valida com log de auditoria
        """
        
        if value is None:
            audit_manager.log_event(
                field_name=field_name,
                strategy="null",
                substrategy="value_is_none",
                confidence=0.0,
                value=None,
                time_ms=5,
                description="Field returned as null (not found in document)"
            )
            return True, None
        
        # Validações específicas
        is_valid, cleaned = Validator._validate_format(field_name, value, field_description)
        
        if not is_valid:
            audit_manager.log_event(
                field_name=field_name,
                strategy="validation_failed",
                substrategy=f"{original_source}_invalid_format",
                confidence=0.0,
                value=value,
                time_ms=10,
                description=f"Validation failed: {field_name} value '{value}' does not match expected format",
                llm_reasoning=f"Original source: {original_source}. Format mismatch detected."
            )
            return False, None
        
        return True, cleaned
```

---

## 5. INTEGRAÇÃO COM MAIN ENDPOINT

### 5.1 Endpoint Modificado

```python
# main.py
from audit.audit_manager import AuditManager

@app.post("/extract")
async def extract(
    label: str = Form(...),
    extraction_schema: str = Form(...),
    pdf_file: UploadFile = File(...),
    include_audit: bool = Query(True, description="Include audit trail in response")
):
    """Endpoint com auditoria integrada"""
    
    # Iniciar audit manager
    audit_manager = AuditManager()
    
    try:
        # 1. PARSE INPUT
        schema = json.loads(extraction_schema)
        
        # 2. SAVE TEMP FILE
        temp_path = f"/tmp/{pdf_file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await pdf_file.read())
        
        # 3. EXTRACT TEXT
        start_pdf = time.time()
        text = PDFExtractor.extract_text(temp_path)
        audit_manager.pdf_extract_time = (time.time() - start_pdf) * 1000
        
        # 4. CHECK CACHE
        pdf_hash = hashlib.md5(text.encode()).hexdigest()
        cached_result = cache_manager.get_result(pdf_hash)
        
        if cached_result:
            # Cache hit!
            audit_manager.cache_hit = True
            
            # Log cache hit
            for field in schema.keys():
                if field in cached_result:
                    audit_manager.log_event(
                        field_name=field,
                        strategy="cache",
                        substrategy="pdf_cache_hit",
                        confidence=1.0,
                        value=cached_result[field],
                        time_ms=5,
                        description=f"Retrieved from cache"
                    )
            
            results = cached_result
        else:
            # Cache miss - processar
            results = {}
            
            # 5. LEARN PATTERNS
            learned = schema_learner.get_patterns(label)
            
            # 6. FOR EACH FIELD
            fields_for_llm = []
            
            for field, description in schema.items():
                # Tentar heurística
                heuristic_value, heuristic_status = HeuristicExtractor.extract_with_audit(
                    field, description, text, audit_manager
                )
                
                if heuristic_status == "heuristic":
                    # Validar
                    is_valid, cleaned = Validator.validate_with_audit(
                        field, heuristic_value, description, "heuristic", audit_manager
                    )
                    
                    if is_valid:
                        results[field] = cleaned
                        continue
                
                # Marcar para LLM
                fields_for_llm.append((field, description))
            
            # 7. LLM BATCH CALL
            if fields_for_llm:
                llm_schema = {f: schema[f] for f, _ in fields_for_llm}
                llm_results = await LLMExtractor.extract_fields_with_audit(
                    text, label, llm_schema,
                    [f for f, _ in fields_for_llm],
                    audit_manager
                )
                
                # Validar resultados LLM
                for field in llm_results:
                    is_valid, cleaned = Validator.validate_with_audit(
                        field, llm_results[field], schema[field], "llm", audit_manager
                    )
                    results[field] = cleaned if is_valid else None
            
            # 8. CACHE RESULT
            cache_manager.set_result(pdf_hash, results)
        
        # 9. LEARN FROM RESULT
        source_analysis = {
            event.field_name: event.strategy
            for event in audit_manager.events
        }
        schema_learner.learn_from_result(label, schema, results, source_analysis)
        
        # 10. BUILD RESPONSE
        response = {
            "label": label,
            "results": results,
            "metadata": {
                "elapsed_seconds": round(audit_manager.get_elapsed_time(), 2),
                "cost_estimate": audit_manager.get_cost_estimate(),
                "llm_calls": audit_manager.llm_call_count
            }
        }
        
        # 11. ADD AUDIT TRAIL (se solicitado)
        if include_audit:
            response["audit_trail"] = audit_manager.generate_audit_trail().dict()
        
        return response
        
    except Exception as e:
        # Log erro na auditoria
        audit_manager.log_event(
            field_name="ERROR",
            strategy="error",
            substrategy="processing_failed",
            confidence=0.0,
            value=None,
            time_ms=0,
            description=f"Processing failed: {str(e)}"
        )
        
        return {
            "error": str(e),
            "audit_trail": audit_manager.generate_audit_trail().dict() if include_audit else None
        }
```

---

## 6. EXEMPLOS DE OUTPUT COM AUDITORIA

### 6.1 Exemplo 1: Sucesso com Mix Heurística+LLM

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
    "cost_estimate": "$0.0023",
    "llm_calls": 1
  },
  "audit_trail": {
    "summary": "Extracted 7 fields with 6 via heuristics + 1 via LLM. Cache miss. High confidence.",
    "decision_log": [
      {
        "field": "nome",
        "strategy": "heuristic",
        "substrategy": "position_based",
        "confidence": 0.95,
        "description": "Found in first line (all caps). Position-based heuristic with 95% confidence.",
        "alternatives_tried": [],
        "cost": 0.0,
        "time_ms": 12,
        "value": "JOANA D'ARC"
      },
      {
        "field": "inscricao",
        "strategy": "heuristic",
        "substrategy": "regex_pattern",
        "confidence": 0.98,
        "description": "Matched regex pattern for 6-digit number after 'Inscrição'. High confidence match.",
        "alternatives_tried": [],
        "cost": 0.0,
        "time_ms": 8,
        "value": "101943"
      },
      {
        "field": "telefone_profissional",
        "strategy": "llm",
        "substrategy": "semantic_extraction",
        "confidence": 0.85,
        "description": "No heuristic pattern found. Called LLM to understand context and extract.",
        "alternatives_tried": ["regex_phone_pattern"],
        "cost": 0.00023,
        "time_ms": 1200,
        "llm_reasoning": "Field marked as 'Telefone Profissional' in document but no value present. Correctly returned null.",
        "value": null
      }
    ],
    "process_flow": "cache_miss → pdf_extract(200ms) → heuristics(100ms) → llm_batch_1_call(1200ms) → validation(50ms) → audit_logging(20ms)",
    "efficiency_score": 0.92,
    "audit_notes": [
      "✅ High coverage: 85.7% fields extracted via heuristics (low cost)",
      "✅ Strategic LLM use: 1 call for 1 field requiring semantic analysis",
      "✅ High confidence: 92% average confidence",
      "⚠️ One null field: 'telefone_profissional' empty in source document",
      "💰 Processing cost: $0.000230"
    ]
  }
}
```

### 6.2 Exemplo 2: Cache Hit

```json
{
  "label": "carteira_oab",
  "results": {
    "nome": "JOANA D'ARC",
    ...
  },
  "metadata": {
    "elapsed_seconds": 0.08,
    "cost_estimate": "$0.0000",
    "llm_calls": 0
  },
  "audit_trail": {
    "summary": "Retrieved 7 fields from cache. All from previous extraction.",
    "decision_log": [
      {
        "field": "nome",
        "strategy": "cache",
        "substrategy": "pdf_cache_hit",
        "confidence": 1.0,
        "description": "Retrieved from cache (same PDF processed before)",
        "alternatives_tried": [],
        "cost": 0.0,
        "time_ms": 5,
        "value": "JOANA D'ARC"
      },
      ...
    ],
    "process_flow": "cache_hit → return_cached_results(80ms)",
    "efficiency_score": 1.0,
    "audit_notes": [
      "✅ Perfect efficiency: 100% cache hit",
      "✅ Ultra-fast processing: 80ms total",
      "✅ Zero cost: No LLM calls",
      "💰 Processing cost: $0.000000"
    ]
  }
}
```

### 6.3 Exemplo 3: Com Problemas (Low Confidence)

```json
{
  "label": "tela_sistema",
  "results": {
    "tipo_de_operacao": "EMPRESTIMO_PESSOAL",
    "sistema": null,
    ...
  },
  "audit_trail": {
    "summary": "Extracted 5 fields with 3 via heuristics + 2 via LLM. Moderate confidence.",
    "decision_log": [
      {
        "field": "tipo_de_operacao",
        "strategy": "llm",
        "substrategy": "semantic_extraction",
        "confidence": 0.72,
        "description": "Multiple operation types found in document. Called LLM to disambiguate.",
        "alternatives_tried": ["keyword_pattern", "enum_matching"],
        "cost": 0.00034,
        "time_ms": 800,
        "llm_reasoning": "Document mentions 'Operação: Empréstimo Pessoal' and 'Tipo: Crédito'. LLM chose primary operation type.",
        "value": "EMPRESTIMO_PESSOAL"
      },
      {
        "field": "sistema",
        "strategy": "null",
        "substrategy": "no_pattern_match",
        "confidence": 0.0,
        "description": "No 'sistema' field found in document despite being in schema.",
        "alternatives_tried": ["keyword_system", "position_based"],
        "cost": 0.0,
        "time_ms": 30,
        "value": null
      }
    ],
    "process_flow": "cache_miss → pdf_extract(250ms) → heuristics(120ms) → llm_batch_2_calls(2100ms) → validation(80ms)",
    "efficiency_score": 0.68,
    "audit_notes": [
      "⚠️ Moderate coverage: 60% fields via heuristics (1 field needed LLM disambiguation)",
      "⚠️ Moderate confidence: 68% average confidence (verify critical fields)",
      "❌ Missing field: 'sistema' not found in document",
      "💰 Processing cost: $0.000450"
    ]
  }
}
```

---

## 7. RECURSOS ADICIONAIS DA AUDITORIA

### 7.1 Query Parameter para Controlar Auditoria

```python
@app.post("/extract")
async def extract(
    ...,
    include_audit: bool = Query(True),  # Inclui audit_trail?
    audit_level: str = Query("standard", enum=["minimal", "standard", "detailed"])
):
    """
    audit_level:
    - "minimal": Apenas summary + efficiency_score
    - "standard": Summary + decision_log + efficiency_score
    - "detailed": Tudo + timestamps + raw events
    """
    
    if audit_level == "minimal":
        return {
            "label": label,
            "results": results,
            "metadata": metadata,
            "audit_trail": {
                "summary": audit_manager.generate_summary(),
                "efficiency_score": audit_manager.calculate_efficiency_score()
            }
        }
    
    elif audit_level == "detailed":
        return {
            "label": label,
            "results": results,
            "metadata": metadata,
            "audit_trail": audit_manager.generate_audit_trail().dict(),
            "raw_events": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "field": e.field_name,
                    "event": e.strategy
                }
                for e in audit_manager.events
            ]
        }
    
    else:  # standard
        return {
            "label": label,
            "results": results,
            "metadata": metadata,
            "audit_trail": audit_manager.generate_audit_trail().dict()
        }
```

### 7.2 Endpoint de Auditoria Histórica

```python
@app.get("/audit/{request_id}")
async def get_audit_history(request_id: str):
    """
    Retorna histórico de auditoria de um request anterior
    (se persistência estiver configurada)
    """
    audit_record = audit_storage.get(request_id)
    
    if not audit_record:
        return {"error": "Request audit not found"}
    
    return {
        "request_id": request_id,
        "timestamp": audit_record.timestamp,
        "label": audit_record.label,
        "audit_trail": audit_record.audit_trail,
        "metrics": {
            "total_time": audit_record.total_time,
            "total_cost": audit_record.total_cost,
            "efficiency": audit_record.efficiency_score
        }
    }
```

### 7.3 Dashboard de Métricas

```python
@app.get("/metrics")
async def get_metrics():
    """
    Retorna métricas agregadas da sessão
    """
    return {
        "total_requests": len(audit_history),
        "average_precision": statistics.mean([a.avg_confidence for a in audit_history]),
        "average_time": statistics.mean([a.total_time for a in audit_history]),
        "average_cost": statistics.mean([a.total_cost for a in audit_history]),
        "cache_hit_rate": sum(1 for a in audit_history if a.cache_hit) / len(audit_history),
        "average_efficiency": statistics.mean([a.efficiency_score for a in audit_history]),
        "llm_calls_total": sum(a.llm_call_count for a in audit_history),
        "cost_saved_vs_pure_llm": calculate_savings()
    }
```

---

## 8. BENEFÍCIOS DA AUDITORIA

### 8.1 Para Desenvolvimento

```
✅ Debugar problemas: exatamente o que aconteceu em cada step
✅ Otimização: identificar gargalos
✅ Validação: confirmar que estratégia correta foi escolhida
✅ Testes: verificar comportamento esperado
```

### 8.2 Para Operação

```
✅ Compliance: rastreamento completo de decisões
✅ Auditoria: explicar por que resultados foram retornados
✅ Investigação: quando algo dá errado, saber exatamente por quê
✅ Otimização: dados reais de performance e custo
```

### 8.3 Para Usuário

```
✅ Transparência: ver como sistema chegou ao resultado
✅ Confiança: conhecer nível de confiança de cada campo
✅ Explicabilidade: entender decisões do sistema
✅ Ajustes: dados para melhorar prompts/heurísticas
```

---

## 9. IMPLEMENTAÇÃO GRADUAL

### Fase 1: Auditoria Básica (1h)
- [x] AuditManager simples
- [x] Log eventos básicos
- [x] Summary em texto
- [x] Decision log estruturado

### Fase 2: Auditoria Completa (1h)
- [x] Process flow description
- [x] Efficiency scoring
- [x] Audit notes com análise
- [x] Integração com extractors

### Fase 3: Auditoria Avançada (1-2h, opcional)
- [x] Persistência de auditoria
- [x] Endpoint de histórico
- [x] Dashboard de métricas
- [x] Diferentes níveis de detalhe
- [x] Análise comparativa

---

## 10. CÓDIGO DE EXEMPLO COMPLETO

Ver arquivo: `SISTEMA_AUDITORIA_BACKEND.py` (próximo arquivo)

---

## RESUMO

Sistema de auditoria que:

✅ **Automático**: Rastreia automaticamente cada decisão
✅ **Transparente**: Descreve exatamente o que foi feito
✅ **Inteligente**: Gera descrições em linguagem natural
✅ **Auditável**: Completo rastreamento para compliance
✅ **Actionável**: Dados para otimização contínua

Resultado: Backend não só funciona bem, mas **explica como está funcionando!** 🔍