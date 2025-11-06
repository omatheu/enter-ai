# audit/audit_manager.py
"""
Sistema de auditoria inteligente e automática
Rastreia cada decisão do backend e gera relatórios
"""

import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum


class StrategyType(str, Enum):
    """Tipos de estratégia de extração"""
    CACHE = "cache"
    HEURISTIC = "heuristic"
    LLM = "llm"
    NULL = "null"
    VALIDATION_FAILED = "validation_failed"
    ERROR = "error"


@dataclass
class AuditEvent:
    """Evento auditável individual"""
    field_name: str
    strategy: str  # StrategyType
    substrategy: str  # "regex_pattern", "semantic_extraction", etc
    confidence: float  # 0.0-1.0
    value: Any
    time_ms: float
    cost: float = 0.0
    description: str = ""
    alternatives_tried: List[str] = field(default_factory=list)
    llm_reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


class FieldDecisionLog(dict):
    """Log de decisão estruturado (dict com campos)"""
    def __init__(
        self,
        field: str,
        strategy: str,
        substrategy: str,
        confidence: float,
        description: str,
        alternatives_tried: List[str] = None,
        cost: float = 0.0,
        time_ms: float = 0.0,
        llm_reasoning: Optional[str] = None,
        value: Optional[Any] = None
    ):
        super().__init__()
        self['field'] = field
        self['strategy'] = strategy
        self['substrategy'] = substrategy
        self['confidence'] = confidence
        self['description'] = description
        self['alternatives_tried'] = alternatives_tried or []
        self['cost'] = cost
        self['time_ms'] = time_ms
        if llm_reasoning:
            self['llm_reasoning'] = llm_reasoning
        if value is not None:
            self['value'] = str(value) if not isinstance(value, (str, int, float, bool, type(None))) else value


class AuditTrail(dict):
    """Auditoria completa estruturada"""
    def __init__(
        self,
        summary: str,
        decision_log: List[FieldDecisionLog],
        process_flow: str,
        efficiency_score: float,
        audit_notes: List[str]
    ):
        super().__init__()
        self['summary'] = summary
        self['decision_log'] = decision_log
        self['process_flow'] = process_flow
        self['efficiency_score'] = efficiency_score
        self['audit_notes'] = audit_notes


class AuditManager:
    """Gerenciador central de auditoria"""
    
    def __init__(self, request_id: str = None, verbose: bool = False):
        """
        Inicializa audit manager
        
        Args:
            request_id: ID único do request para rastreamento
            verbose: Log eventos em tempo real
        """
        self.request_id = request_id or f"req_{datetime.now().timestamp()}"
        self.events: List[AuditEvent] = []
        self.start_time = time.time()
        self.llm_call_count = 0
        self.total_cost = 0.0
        self.cache_hit = False
        self.pdf_extract_time = 0.0
        self.verbose = verbose
        
        if self.verbose:
            print(f"[AUDIT] Iniciado request {self.request_id}")
    
    def log_event(
        self,
        field_name: str,
        strategy: str,
        substrategy: str,
        confidence: float,
        value: Any = None,
        time_ms: float = 0.0,
        cost: float = 0.0,
        description: str = "",
        alternatives_tried: List[str] = None,
        llm_reasoning: str = ""
    ):
        """
        Registra um evento de auditoria
        
        Args:
            field_name: Nome do campo
            strategy: Estratégia usada (cache, heuristic, llm, null, etc)
            substrategy: Sub-estratégia (regex_pattern, semantic_extraction, etc)
            confidence: Confiança 0.0-1.0
            value: Valor extraído
            time_ms: Tempo de processamento
            cost: Custo em $
            description: Descrição em português
            alternatives_tried: Estratégias tentadas antes
            llm_reasoning: Raciocínio do LLM (se aplicável)
        """
        event = AuditEvent(
            field_name=field_name,
            strategy=strategy,
            substrategy=substrategy,
            confidence=confidence,
            value=value,
            time_ms=time_ms,
            cost=cost,
            description=description,
            alternatives_tried=alternatives_tried or [],
            llm_reasoning=llm_reasoning
        )
        
        self.events.append(event)
        self.total_cost += cost
        
        if strategy == StrategyType.LLM or strategy == "llm":
            self.llm_call_count += 1
        
        if self.verbose:
            print(f"[AUDIT] {field_name}: {strategy}/{substrategy} (conf={confidence:.0%})")
    
    def generate_summary(self) -> str:
        """Gera sumário em linguagem natural português"""
        if not self.events:
            return "Nenhum evento registrado"
        
        total_fields = len(self.events)
        heuristic_fields = sum(1 for e in self.events if e.strategy == StrategyType.HEURISTIC)
        llm_fields = sum(1 for e in self.events if e.strategy == StrategyType.LLM)
        cache_fields = sum(1 for e in self.events if e.strategy == StrategyType.CACHE)
        null_fields = sum(1 for e in self.events if e.strategy == StrategyType.NULL)
        
        avg_confidence = sum(e.confidence for e in self.events) / total_fields if total_fields > 0 else 0
        
        summary = f"Extração de {total_fields} campos com "
        parts = []
        
        if cache_fields > 0:
            parts.append(f"{cache_fields} do cache")
        if heuristic_fields > 0:
            parts.append(f"{heuristic_fields} via heurísticas")
        if llm_fields > 0:
            parts.append(f"{llm_fields} via LLM")
        if null_fields > 0:
            parts.append(f"{null_fields} nulos")
        
        summary += " + ".join(parts) + ". "
        
        if self.cache_hit:
            summary += "Cache ativado (processamento rápido). "
        else:
            summary += "Cache miss. "
        
        summary += f"Confiança média: {avg_confidence:.0%}. "
        
        if avg_confidence > 0.85:
            summary += "Resultados com alta confiança."
        elif avg_confidence > 0.70:
            summary += "Resultados com confiança moderada."
        else:
            summary += "Resultados com baixa confiança - revisão manual recomendada."
        
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
                value=event.value
            )
            for event in self.events
        ]
    
    def generate_process_flow(self) -> str:
        """Descreve o fluxo de processamento em ASCII"""
        flow_steps = []
        
        # Cache status
        if self.cache_hit:
            flow_steps.append("cache_hit")
        else:
            flow_steps.append("cache_miss")
        
        # PDF extraction
        if self.pdf_extract_time > 0:
            flow_steps.append(f"pdf_extract({self.pdf_extract_time:.0f}ms)")
        
        # Agrupar estratégias por tipo
        has_heuristics = any(e.strategy == StrategyType.HEURISTIC for e in self.events)
        has_llm = any(e.strategy == StrategyType.LLM for e in self.events)
        
        if has_heuristics:
            heuristic_time = sum(
                e.time_ms for e in self.events 
                if e.strategy == StrategyType.HEURISTIC
            )
            flow_steps.append(f"heuristics({heuristic_time:.0f}ms)")
        
        if has_llm:
            llm_time = sum(
                e.time_ms for e in self.events 
                if e.strategy == StrategyType.LLM
            )
            flow_steps.append(f"llm_batch_{self.llm_call_count}_call({llm_time:.0f}ms)")
        
        # Validação e logging
        flow_steps.append("validation(50ms)")
        flow_steps.append("audit_logging(20ms)")
        
        return " → ".join(flow_steps)
    
    def calculate_efficiency_score(self) -> float:
        """
        Calcula score de eficiência (0.0-1.0)
        Baseado em: % resolvido sem LLM + confiança
        """
        if not self.events:
            return 0.0
        
        total_fields = len(self.events)
        efficient_fields = sum(
            1 for e in self.events 
            if e.strategy in [StrategyType.HEURISTIC, StrategyType.CACHE]
        )
        
        # Score base: percentual de campos via heurística/cache
        efficiency = efficient_fields / total_fields
        
        # Bônus se alta confiança
        avg_confidence = sum(e.confidence for e in self.events) / total_fields
        if avg_confidence > 0.85:
            efficiency = min(1.0, efficiency * 1.05)
        
        return efficiency
    
    def generate_audit_notes(self) -> List[str]:
        """Gera observações estruturadas com análise"""
        notes = []
        
        if not self.events:
            return ["ℹ️ Nenhum evento para analisar"]
        
        # === ANÁLISE DE COBERTURA ===
        total_fields = len(self.events)
        heuristic_fields = sum(1 for e in self.events if e.strategy == StrategyType.HEURISTIC)
        cache_fields = sum(1 for e in self.events if e.strategy == StrategyType.CACHE)
        efficient_pct = (heuristic_fields + cache_fields) / total_fields * 100
        
        if efficient_pct >= 80:
            notes.append(f"✅ Alta cobertura: {efficient_pct:.1f}% campos via heurísticas/cache (baixo custo)")
        elif efficient_pct >= 60:
            notes.append(f"✅ Boa cobertura: {efficient_pct:.1f}% campos via heurísticas")
        else:
            notes.append(f"⚠️ Cobertura baixa: {efficient_pct:.1f}% campos via heurísticas (mais LLM necessário)")
        
        # === ANÁLISE DE LLM ===
        llm_fields = sum(1 for e in self.events if e.strategy == StrategyType.LLM)
        
        if self.llm_call_count > 0:
            notes.append(f"✅ Uso estratégico de LLM: {self.llm_call_count} call(s) para {llm_fields} campo(s)")
        else:
            notes.append("✅ Zero chamadas LLM (heurísticas/cache apenas)")
        
        # === ANÁLISE DE CONFIANÇA ===
        avg_confidence = sum(e.confidence for e in self.events) / total_fields if total_fields > 0 else 0
        
        if avg_confidence > 0.85:
            notes.append(f"✅ Alta confiança: {avg_confidence:.0%} de confiança média")
        elif avg_confidence > 0.70:
            notes.append(f"⚠️ Confiança moderada: {avg_confidence:.0%} (verifique campos críticos)")
        else:
            notes.append(f"❌ Confiança baixa: {avg_confidence:.0%} (revisão manual recomendada)")
        
        # === ANÁLISE DE CAMPOS NULOS ===
        null_events = [e for e in self.events if e.strategy == StrategyType.NULL]
        if null_events:
            fields_list = ", ".join([f"'{e.field_name}'" for e in null_events])
            notes.append(f"ℹ️ Campos nulos: {fields_list} vazios no documento")
        
        # === ANÁLISE DE CUSTO ===
        if self.total_cost > 0:
            notes.append(f"💰 Custo de processamento: ${self.total_cost:.6f}")
        else:
            notes.append("💰 Sem custos: processamento via heurísticas/cache")
        
        # === ANÁLISE DE PERFORMANCE ===
        elapsed = self.get_elapsed_time()
        if elapsed < 1:
            notes.append(f"⚡ Performance ultra-rápida: {elapsed*1000:.0f}ms")
        elif elapsed < 5:
            notes.append(f"⚡ Performance rápida: {elapsed:.1f}s")
        elif elapsed < 10:
            notes.append(f"ℹ️ Performance aceitável: {elapsed:.1f}s")
        else:
            notes.append(f"⚠️ Performance lenta: {elapsed:.1f}s (acima de 10s)")
        
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
        """Retorna tempo total de processamento em segundos"""
        return time.time() - self.start_time
    
    def get_cost_estimate(self) -> str:
        """Retorna estimativa de custo em formato legível"""
        return f"${self.total_cost:.6f}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte audit trail para dicionário (para JSON)"""
        audit_trail = self.generate_audit_trail()
        return dict(audit_trail)


# ============================================================================
# EXEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    # Simular auditoria de uma extração
    
    audit = AuditManager(verbose=True)
    
    # Simular eventos
    audit.log_event(
        field_name="nome",
        strategy="heuristic",
        substrategy="position_based",
        confidence=0.95,
        value="JOANA D'ARC",
        time_ms=12,
        cost=0.0,
        description="Encontrado na primeira linha (maiúsculas). Heurística baseada em posição."
    )
    
    audit.log_event(
        field_name="inscricao",
        strategy="heuristic",
        substrategy="regex_pattern",
        confidence=0.98,
        value="101943",
        time_ms=8,
        cost=0.0,
        description="Combinado com padrão regex para número 6-dígitos após 'Inscrição'."
    )
    
    audit.log_event(
        field_name="telefone",
        strategy="llm",
        substrategy="semantic_extraction",
        confidence=0.60,
        value=None,
        time_ms=1200,
        cost=0.00023,
        description="Nenhum padrão heurístico encontrado. Chamado LLM para análise semântica.",
        alternatives_tried=["regex_phone_pattern"],
        llm_reasoning="Campo marcado como 'Telefone Profissional' mas vazio no documento. Retornou null corretamente."
    )
    
    # Gerar relatório
    print("\n" + "="*80)
    print("AUDITORIA GERADA")
    print("="*80)
    
    audit_trail = audit.generate_audit_trail()
    
    print(f"\n📋 SUMÁRIO:\n{audit_trail['summary']}")
    print(f"\n⚙️ FLUXO DE PROCESSAMENTO:\n{audit_trail['process_flow']}")
    print(f"\n📊 SCORE DE EFICIÊNCIA: {audit_trail['efficiency_score']:.0%}")
    
    print("\n📝 LOG DE DECISÕES:")
    for i, decision in enumerate(audit_trail['decision_log'], 1):
        print(f"\n  {i}. Campo: {decision['field']}")
        print(f"     Estratégia: {decision['strategy']} ({decision['substrategy']})")
        print(f"     Confiança: {decision['confidence']:.0%}")
        print(f"     Tempo: {decision['time_ms']}ms | Custo: ${decision['cost']:.6f}")
        print(f"     Descrição: {decision['description']}")
    
    print("\n📋 OBSERVAÇÕES:")
    for note in audit_trail['audit_notes']:
        print(f"  {note}")
    
    print(f"\n⏱️ Tempo total: {audit.get_elapsed_time():.2f}s")
    print(f"💰 Custo estimado: {audit.get_cost_estimate()}")
    
    print("\n" + "="*80)
    print("JSON COMPLETO (para resposta HTTP)")
    print("="*80)
    
    response = {
        "label": "carteira_oab",
        "results": {
            "nome": "JOANA D'ARC",
            "inscricao": "101943",
            "telefone": None
        },
        "metadata": {
            "elapsed_seconds": round(audit.get_elapsed_time(), 2),
            "cost_estimate": audit.get_cost_estimate(),
            "llm_calls": audit.llm_call_count
        },
        "audit_trail": audit.to_dict()
    }
    
    print(json.dumps(response, indent=2, ensure_ascii=False))