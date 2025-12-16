# project_master.md

**Status:** LEI SUPREMA (Ativo)
**Versão:** 3.0 (Zoneamento Arquitetural)
**Contexto:** Gerador de Cartões Tipográficos (AutoMakeCard V2)

> **PARA A IA:** Este arquivo é o MAPA DO TERRITÓRIO. Antes de qualquer modificação, identifique em qual ZONA você está pisando. Violar fronteiras entre zonas é erro crítico.

---

## 1. O Mapa do Território (Zoneamento Estrito)

O projeto é um complexo industrial dividido em **4 Zonas Soberanas**. Cada zona tem responsabilidades exclusivas e fronteiras rígidas.

### 🏛️ ZONA 1: O Núcleo (Core Domain)
**Analogia:** O Arquivo Central e o Estado Maior.
**Diretório:** `/core` (model_v2, template_v2, svg_scanner)
**Responsabilidade:** Definir **O QUE** deve ser feito.
- Guarda a Lógica de Negócio (Regras de precedência de texto).
- Guarda a Verdade dos Dados (JSON).
- Realiza a importação de matéria-prima (SVG).
**🚫 PROIBIDO:**
- Importar qualquer coisa de `/ui`.
- Executar renderização pesada (apenas prepara os dados).

### 🏭 ZONA 2: O Chão de Fábrica (Workers)
**Analogia:** O Maquinário Pesado.
**Diretório:** `/core/typography_engine.py`, `/core/compositor.py`
**Responsabilidade:** Executar **COMO** fazer (força bruta).
- `TypographyEngine`: Operário que desenha texto (Playwright).
- `Compositor`: Operário que cola imagens (Pillow).
**🚫 PROIBIDO:**
- Tomar decisões de negócio (ex: "se o nome for longo, diminua a fonte"). O Operário apenas obedece ordens explícitas.
- Manter estado persistente entre jobs (devem ser stateless).

### 🗼 ZONA 3: A Torre de Controle (Controller)
**Analogia:** O Gerente de Operações.
**Diretório:** `/core/pipeline.py` (Orquestrador)
**Responsabilidade:** **COORDENAR** o fluxo.
- Recebe o pedido da UI.
- Busca o plano na Zona 1.
- Despacha tarefas para a Zona 2.
- Devolve o relatório final.
**✅ PERMITIDO:** É o único elemento que pode importar de Zona 1 e Zona 2.

### 🖥️ ZONA 4: O Painel de Comando (UI)
**Analogia:** A Recepção e os Botões.
**Diretório:** `/ui` (Qt/PySide6)
**Responsabilidade:** **INTERAGIR** com o humano.
- Exibir tabelas e formulários.
- Capturar cliques.
**🚫 PROIBIDO:**
- Conter loops de geração ("for row in table...").
- Manipular arquivos diretamente.
- Instanciar Workers (Playwright/Pillow).
- **A UI só fala com a Zona 3 (Controller).**

---

## 2. A Espinha Dorsal de Dados (Flow of Truth)

Como a informação trafega pelas ruas do quartel. O fluxo é unidirecional.

### O Ciclo da Verdade (SVG vs JSON)
1.  **Importação (Evento Raro):** O sistema lê o **SVG** (Input) → Extrai geometria → Grava no **JSON**.
2.  **Operação (Dia a dia):** O sistema lê **APENAS o JSON**. O SVG torna-se irrelevante após a importação.
3.  **Ajuste:** Se o layout muda, atualiza-se o SVG e roda-se a Importação novamente.
    * *Conclusão:* **JSON é a Persistência. SVG é o Transporte.**

### O Ciclo de Geração (Runtime)
1.  **UI (Zona 4):** Coleta dados da tabela + Configurações. Chama `Pipeline.run()`.
2.  **Pipeline (Zona 3):**
    * Carrega `TemplateV2` (Zona 1).
    * Resolve Placeholders via `ModelV2` (Zona 1).
    * Envia para `TypographyEngine` (Zona 2) → Retorna `overlay.png`.
    * Envia para `Compositor` (Zona 2) → Retorna `final.png`.
3.  **UI (Zona 4):** Recebe sinal de "Concluído" e exibe log.

---

## 3. Especificações de Materiais (Tech Stack)

Para garantir a estabilidade estrutural:

| Componente | Material (Lib) | Regra de Uso |
|---|---|---|
| **Linguagem** | Python 3.10+ | Type Hints (`def func(a: int) -> str:`) são **OBRIGATÓRIOS**. |
| **Interface** | PySide6 | Separar Widgets (`panels/`) de Janelas (`dialogs/`). |
| **Render Texto** | Playwright (Sync) | Reutilizar contexto do browser. Nunca abrir/fechar por cartão. |
| **Render Imagem** | Pillow (PIL) | Usar apenas para `alpha_composite`. |
| **Config** | JSON | Snake_case para chaves. |

---

## 4. Protocolo de Manutenção (Como expandir)

Ao criar nova funcionalidade, siga o roteiro de instalação:

1.  **Definição (Zona 1):** Onde os dados disso ficam no JSON?
2.  **Mecanismo (Zona 2):** Quem processa isso? (Novo motor ou motor existente?)
3.  **Ordem (Zona 3):** Em que momento do pipeline isso é acionado?
4.  **Botão (Zona 4):** Onde o usuário ativa isso?

---

## 5. Checklist de Validação (AI Self-Correction)

Antes de gerar código, verifique:
- [ ] Estou colocando lógica de negócio na UI? (❌ PARE)
- [ ] Estou fazendo a UI chamar o Playwright direto? (❌ PARE)
- [ ] Estou criando um loop na UI que deveria estar no Pipeline? (❌ PARE)
- [ ] O código respeita a hierarquia de imports (UI -> Core)? (✅ Prossiga)