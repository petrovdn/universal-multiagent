# Исследование: Оптимизация выбора инструментов для AI-агента

## Проблема

При работе агента возникают сбои из-за невозможности найти нужные инструменты. Текущая система использует keyword matching, что ненадёжно и плохо масштабируется.

### Текущие ограничения в коде:

- **Лимит описаний**: `desc = cap.description[:200]` (200 символов)
- **Лимит инструментов**: `final_result = result[:7]` (максимум 7)
- **Метод выбора**: Rule-based keyword matching в `_get_relevant_tools`

---

## Исследованные решения

### 1. AnyTool — Universal Tool-Use Layer

**GitHub**: https://github.com/HKUDS/AnyTool

AnyTool решает три ключевые проблемы:

#### Проблема 1: Tool Context Overload
Текущие MCP агенты загружают ВСЕ инструменты при каждом шаге.

**Решение — Smart Tool RAG:**

| Компонент | Что делает |
|-----------|------------|
| Multi-Stage Pipeline | server selection → name matching → semantic search → LLM ranking |
| Long-Term Memory | Pre-computed embeddings на диске |
| Adaptive Selection | LLM-ranking только при большом числе кандидатов |
| Lazy Init | Сервер запускается только когда нужен конкретный tool |

#### Проблема 2: Tool Quality Issues
Плохие описания, нет сигналов надёжности, security gaps.

**Решение — Self-Evolving Quality Tracking:**

| Компонент | Что делает |
|-----------|------------|
| Description Quality Check | LLM оценивает качество описания |
| Performance-Based Ranking | Отслеживает success rate |
| Self-Healing | Автопереключение на альтернативу при ошибке |

#### Конфигурация AnyTool:

```json
{
  "tool_search": {
    "search_mode": "hybrid",
    "max_tools": 20,
    "enable_llm_filter": true,
    "llm_filter_threshold": 50,
    "enable_cache_persistence": true
  },
  "tool_quality": {
    "enabled": true,
    "enable_persistence": true,
    "auto_evaluate_descriptions": true,
    "evolve_interval": 5
  }
}
```

---

### 2. RAG-MCP (arXiv:2505.03275)

Академическое исследование семантического выбора инструментов.

**Результаты:**

| Метод | Точность выбора | Prompt Tokens |
|-------|-----------------|---------------|
| Blank (все инструменты) | 13.62% | 2133 |
| Actual Match (keyword) | 18.20% | 1646 |
| **RAG-MCP** | **43.13%** | **1084** |

Точность выросла в 3 раза, prompt сократился на 50%.

---

### 3. Anthropic Skills

**Спецификация**: https://agentskills.io/specification  
**GitHub**: https://github.com/anthropics/skills

Skills — стандартный формат для модульного хранения процедурного знания.

#### Структура:

```
skill-name/
├── SKILL.md          # Обязательно
├── scripts/          # Опционально
├── references/       # Опционально
└── assets/           # Опционально
```

#### Формат SKILL.md:

```yaml
---
name: onec-salary
description: >
  Работа с зарплатой из 1С:Бухгалтерия. Используй когда пользователь 
  спрашивает о зарплате, оплате труда, расчетах с персоналом.
metadata:
  version: "1.0"
---

## Когда активировать
Ключевые слова: "зарплата", "1С", "оплата труда"

## Приоритетный инструмент
`onec_get_salary_by_employee_month`

## Workflow
1. Определи период
2. Вызови инструмент
3. Представь результат
```

#### Progressive Disclosure:

1. **Metadata (~100 tokens)** — загружается для всех skills при старте
2. **Instructions (< 5000 tokens)** — только когда skill активирован
3. **Resources** — по требованию

---

## Рекомендуемая архитектура: AnyTool + Skills

```
┌─────────────────────────────────────────────────────────┐
│                    User Query                            │
└───────────────────────┬─────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│           AnyTool Smart Tool RAG                         │
│  Stage 1: Server Selection                               │
│  Stage 2: Tool Name Matching                             │
│  Stage 3: Semantic Search (vector similarity)            │
│  Stage 4: LLM Ranking (если >50 кандидатов)              │
└───────────────────────┬─────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│           Skills Layer (процедурное знание)                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐               │
│  │onec-salary │ │slides-fmt  │ │projectlad  │               │
│  │SKILL.md    │ │SKILL.md    │ │SKILL.md    │               │
│  └────────────┘ └────────────┘ └────────────┘               │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│           Main ReAct Agent (минимальный prompt)          │
│  - Получает: selected tools + active skill instructions │
└───────────────────────┬─────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│           Tool Quality Tracking                          │
│  - Success/failure rates                                 │
│  - Auto-switching on failure                             │
└───────────────────────┬─────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│           CapabilityRegistry + MCP Providers             │
└─────────────────────────────────────────────────────────┘
```

### Разделение ответственности:

| Компонент | Источник | Роль |
|-----------|----------|------|
| Smart Tool RAG | AnyTool | ВЫБОР правильных инструментов |
| Skills | Anthropic | ИНСТРУКЦИИ как использовать |
| Quality Tracking | AnyTool | ОБУЧЕНИЕ системы со временем |

---

## Ожидаемые улучшения

| Метрика | Текущая система | После внедрения |
|---------|-----------------|-----------------|
| Точность выбора tool | ~18% (keyword) | ~40-50% (RAG + quality) |
| Prompt tokens | ~2000+ фиксированно | ~800-1200 динамически |
| Добавление интеграции | Изменение main_agent.py | Добавление SKILL.md |
| Восстановление при ошибке | Manual | Auto-switching |
| Слабая LLM для планирования | Сложно | Да |

---

## План внедрения

### Этап 1: Smart Tool RAG

Заменить `_get_relevant_tools` на semantic search с embedding cache.

```python
class SmartToolSelector:
    """Smart tool selection based on AnyTool's RAG approach."""
    
    def __init__(self, capabilities: List[ActionCapability]):
        self.capabilities = capabilities
        self.embedding_cache = EmbeddingCache("data/tool_embeddings")
        self.quality_tracker = ToolQualityTracker("data/tool_quality")
        
    async def select_tools(
        self, 
        query: str, 
        max_tools: int = 7,
        use_llm_filter: bool = True
    ) -> List[ActionCapability]:
        # Stage 1: Semantic search
        candidates = await self._semantic_search(query, top_k=50)
        
        # Stage 2: Quality-based ranking
        candidates = self._rank_by_quality(candidates)
        
        # Stage 3: LLM filter (if needed)
        if len(candidates) > max_tools and use_llm_filter:
            candidates = await self._llm_filter(query, candidates, max_tools)
        
        return candidates[:max_tools]
```

### Этап 2: Skills

Вынести специфическую логику (1С, ProjectLad, Slides) в SKILL.md файлы.

```
skills/
├── onec-salary/
│   └── SKILL.md
├── projectlad/
│   └── SKILL.md
├── slides-formatting/
│   └── SKILL.md
├── sheets-analysis/
│   └── SKILL.md
└── calendar-scheduling/
    └── SKILL.md
```

### Этап 3: Quality Tracking

Добавить отслеживание success rate и auto-switching.

```python
@dataclass
class ToolQualityRecord:
    name: str
    call_count: int = 0
    success_count: int = 0
    description_score: float = 1.0
    last_error: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        if self.call_count == 0:
            return 0.5  # neutral for new tools
        return self.success_count / self.call_count
```

---

## Ссылки

- **AnyTool**: https://github.com/HKUDS/AnyTool
- **RAG-MCP Paper**: https://arxiv.org/abs/2505.03275
- **Anthropic Skills Spec**: https://agentskills.io/specification
- **Skills GitHub**: https://github.com/anthropics/skills
- **MCP Protocol**: https://docs.anthropic.com/en/docs/mcp
- **MCP Safety Audit**: https://arxiv.org/abs/2504.03767

---

*Документ создан: Январь 2026*
