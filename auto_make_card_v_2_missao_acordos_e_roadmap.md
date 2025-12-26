# Gerador de Cartão em Lote v3.0 — Missão, Acordos de Trabalho e Roadmap

> **Este arquivo é a referência-mãe do projeto.**
> Deve ser relido sempre que um novo chat for iniciado ou quando retomarmos o desenvolvimento após pausa.

---

## 1. Missão do Projeto

Criar um **gerador de cartões tipograficamente profissional**, robusto e previsível, capaz de:

- Gerar cartões em lote a partir de dados tabulares (Google Sheets → Ctrl+V)
- Usar **modelos criados em SVG** como base visual e semântica
- Suportar tipografia avançada:
  - negrito parcial, itálico, sublinhado
  - quebra automática de linha
  - alinhamento (left, center, right, justify)
  - recuo da primeira linha de parágrafo
  - line-height controlado
- Funcionar em **Linux e Windows**, inclusive em máquinas modestas
- Ter arquitetura clara, modular e extensível

O projeto **não busca atalhos** nem soluções improvisadas: a prioridade é **previsibilidade, clareza e controle**.

---

## 2. Acordos Fundamentais de Trabalho (como trabalhamos juntos)

Esses pontos são **obrigatórios** para o bom andamento do projeto.

### 2.1 Papéis

- **ChatGPT**: escreve, propõe e analisa o código
- **Usuário (Leo)**: copia, cola, ajusta e executa o código localmente

Isso significa que:
- O ChatGPT **nunca assume** que pode editar arquivos diretamente
- Toda instrução de código deve ser **cirúrgica**

### 2.2 Forma correta de passar instruções de código

Sempre usar este padrão:

- Informar **arquivo exato**
- Informar **classe / função / método**
- Informar **onde exatamente inserir ou remover código**

Exemplo correto:

> Arquivo: `app_window.py`  
> Classe: `MainWindow`  
> Método: `_on_generate_clicked`  
> Abaixo da linha:
> ```python
> self.log_panel.append("Overlay FULL gerado")
> ```
> adicione:
> ```python
> ...
> ```

Nunca:
- “adicione no lugar certo”
- “ajuste essa parte”
- “modifique o fluxo” sem indicar **onde**

### 2.3 Alinhamento antes de implementar

- **Não prever intenções** do usuário
- **Perguntar antes** de assumir decisões
- Debater arquitetura **antes** de codar

Frase-chave válida:
> "Antes de implementar, preciso confirmar X e Y"

---

## 3. Arquitetura Consolidada (Fonte da Verdade)

### 3.1 Pipeline Oficial (não mudar sem consenso)

```
SVG (modelo)
  ↓
Scanner SVG (camadas + placeholders)
  ↓
ModelV2 (estrutura lógica)
  ↓
HTML/CSS + Playwright
  → overlay.png (TRANSPARENTE, texto puro)
  ↓
Pillow (alpha composite)
  → final.png
```

### 3.2 Responsabilidades de cada tecnologia

- **SVG / Inkscape**
  - Criação visual do modelo
  - Texto-base (ex: "Ponta Grossa - PR, {data} de 2025")

- **HTML/CSS (Playwright)**
  - Tipografia
  - Quebra de linha
  - Justificação
  - Negrito parcial

- **Pillow**
  - Apenas composição de imagens
  - Nunca tipografia

---

## 4. Conceitos-Chave do Sistema

### 4.1 Boxes (elementos de texto)

- Cada box representa uma área de texto no cartão
- Possui:
  - `id`
  - posição (x, y, w, h)
  - propriedades tipográficas (align, indent, line-height)

### 4.2 Placeholders

- Identificados sempre por `{nome}`
- Exemplo: `{nome}`, `{data}`
- Um box pode conter **vários placeholders**
- Placeholders:
  - recebem HTML vindo da tabela (Sheets)
  - herdam estilo do box

### 4.3 IDs vs Placeholders (regra oficial)

- **ID** → identifica o box
- **{placeholder}** → identifica dado variável

Na tabela:
- `{nome}` → coluna de placeholder
- `nome` → coluna editável por ID (se habilitado)

O sistema:
- escaneia **ambos**
- não ignora nenhum

---

## 5. Estado Atual do Projeto (checkpoint confirmado)

### 5.1 O que já está funcionando

- ✅ Scanner de SVG (camadas + placeholders)
- ✅ ModelV2 estruturado
- ✅ Resolução de placeholders
- ✅ Render tipográfico via HTML/CSS
- ✅ Overlay transparente correto
- ✅ Composição final com Pillow
- ✅ Geração de imagem final real (`final.png`)

### 5.2 O que **não é bug** neste estágio

- Fonte fallback (Times-like)
- Texto preto
- Modelo visual fake

Tudo isso é **esperado** até o template definitivo ser configurado.

---

## 6. Roadmap Oficial (Mapa de Tarefas Futuras)

### Fase 1 — Template V2 definitivo

- [ ] Consolidar `template_v2.json` como fonte da verdade
- [ ] Definir por box:
  - fonte
  - tamanho
  - cor
  - alinhamento default
- [ ] Eliminar valores hardcoded no engine

### Fase 2 — UI de configuração de boxes

- [ ] Listar boxes detectadas
- [ ] Checkboxes / selects para:
  - align
  - justify
  - indent_px
  - line-height
- [ ] Prioridade: UI > modelo SVG

### Fase 3 — Geração em lote real

- [ ] Loop por todas as linhas válidas da tabela
- [ ] Gerar overlay por linha
- [ ] Compor imagem final por linha
- [ ] Nomear arquivos via `naming.py`

### Fase 4 — Paste avançado (Sheets)

- [ ] Preservar:
  - negrito
  - itálico
  - sublinhado
- [ ] Sanitização de HTML

### Fase 5 — Polimento

- [ ] Logs mais claros
- [ ] Validações de modelo
- [ ] Empacotamento (Linux / Windows)

---

## 7. Regra de Ouro do Projeto

> **Clareza > velocidade**  
> **Arquitetura > atalhos**  
> **Alinhamento > código**

Se algo parecer confuso, o projeto **para**, conversa-se, e só depois continua.

---

📌 **Este arquivo deve ser reutilizado como prompt-base** para qualquer novo chat sobre o Gerador de Cartão em Lote v3.0.

