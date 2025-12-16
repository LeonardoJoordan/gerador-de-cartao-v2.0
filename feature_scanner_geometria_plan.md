# Feature Plan: Scanner de Inventário Universal (Blueprint)

**Arquivo:** `feature_scanner_geometria_plan.md`
**Status:** Planta Aprovada
**Zona de Atuação:** ZONA 1 (Core)
**Objetivo:** Implementar o `svg_scanner.py` como um extrator de alta fidelidade que desmonta o SVG em geometrias, estilos e arquivos de imagem físicos.

---

## 1. Mapa da Estrutura (A Planta Baixa)

O arquivo `core/svg_scanner.py` deixará de ser um script simples para se tornar um **Processador de Elementos**.

### 1.1 Entidades de Dados (O Mobiliário)
Definição exata das classes que transportarão os dados extraídos.

* **`ScannedObject` (Classe Base)**
    * *Propósito:* Dados comuns a qualquer elemento visual.
    * *Campos:* `id` (str), `x` (float), `y` (float), `w` (float), `h` (float), `z_index` (int).
    * *Nota:* `z_index` representa a ordem de leitura no SVG (0 = fundo, N = topo).

* **`ScannedText` (Herda de Object)**
    * *Propósito:* Clone digital do elemento `<text>`.
    * *Campos Específicos:* `text` (str), `font_family` (str), `font_size` (float), `font_weight` (str), `font_style` (str), `fill` (str), `align` (str).
    * *Regra:* Se o SVG não tiver width definido, `w`=0.

* **`ScannedRect` (Herda de Object)**
    * *Propósito:* Delimitador de área para layout (Container).
    * *Campos Específicos:* Nenhum (apenas geometria).
    * *Regra:* Ignora cor e borda do retângulo original. Serve apenas como "placeholder de espaço".

* **`ScannedImage` (Herda de Object)**
    * *Propósito:* Referência a um arquivo de imagem físico.
    * *Campos Específicos:* `src_relative_path` (str).
    * *Regra:* Não armazena bytes em memória. Aponta para `assets/arquivo.png`.

* **`ScanResult` (O Container Final)**
    * *Propósito:* O pacote entregue ao final do processo.
    * *Campos:* `texts` (List[ScannedText]), `rects` (List[ScannedRect]), `images` (List[ScannedImage]).

### 1.2 Componentes Lógicos (As Engrenagens)

* **`_parse_styles(element) -> dict`**
    * *Função:* O "tradutor de CSS".
    * *Responsabilidade:* Ler atributo `style="..."` E atributos diretos (`font-size="..."`).
    * *Prioridade:* Atributo direto > CSS Inline > Default.
    * *Conversão:* Transforma `pt` para `px` (fator 1.333) para normalizar tudo em pixels.

* **`_extract_image_file(element, output_dir) -> str`**
    * *Função:* O "extrator de ativos".
    * *Responsabilidade:*
        1. Identificar se é Base64 ou Link.
        2. Se Base64: Decodificar e salvar em disco.
        3. Se Link Local: Copiar para a pasta de destino.
    * *Destino:* Sempre salva em `{model_dir}/assets/`.

* **`scan_svg(path, output_dir) -> ScanResult`**
    * *Função:* O "Mestre de Obras".
    * *Fluxo:*
        1. Cria pasta `assets/` se não existir.
        2. Itera sobre XML nodes recursivamente.
        3. Mantém contador `z_index`.
        4. Despacha para o parser correto baseada na tag (`rect`, `text`, `image`).

---

## 2. Fluxo de Execução (O Roteiro da Obra)

Como o sistema processa um arquivo SVG ("input.svg"):

1.  **Inicialização:**
    * O `Scanner` recebe o caminho do SVG e o diretório onde salvar assets.
    * Zera o contador `z_index = 0`.

2.  **Varredura (Loop):**
    * Encontra `<image id="fundo">`:
        * Chama `_extract_image_file`.
        * Salva `fundo.png` em `assets/`.
        * Cria `ScannedImage(id='fundo', z=0, src='assets/fundo.png')`.
    * Encontra `<rect id="area_msg">`:
        * Lê `x, y, w, h`.
        * Cria `ScannedRect(id='area_msg', z=1, ...)`.
    * Encontra `<text id="txt_msg">`:
        * Lê conteúdo e chama `_parse_styles`.
        * Cria `ScannedText(id='txt_msg', z=2, font='Arial', ...)`.

3.  **Entrega:**
    * Retorna o objeto `ScanResult` populado.

---

## 3. Checklist de Construção (Ordem de Serviço)

Esta é a sequência exata de codificação para não haver erro de dependência.

### Fase 1: Fundação (Estruturas)
- [ ] **Passo 1.1:** Importar `dataclasses`, `pathlib`, `base64`, `shutil`, `re`.
- [ ] **Passo 1.2:** Definir a classe base `ScannedObject`.
- [ ] **Passo 1.3:** Definir as classes filhas `ScannedText`, `ScannedRect`, `ScannedImage`.
- [ ] **Passo 1.4:** Definir a classe container `ScanResult`.

### Fase 2: Mecânica Fina (Helpers)
- [ ] **Passo 2.1:** Implementar `_parse_styles`. Deve passar no teste de conversão `12pt -> 16px`.
- [ ] **Passo 2.2:** Implementar `_extract_image_file`. Deve suportar Base64 e Link.

### Fase 3: Montagem Principal (Scanner)
- [ ] **Passo 3.1:** Implementar assinatura `scan_svg(svg_path: Path, output_assets_dir: Path)`.
- [ ] **Passo 3.2:** Implementar loop de iteração XML com suporte a namespace SVG.
- [ ] **Passo 3.3:** Conectar parsers e popular listas.

### Fase 4: Acabamento (Integração)
- [ ] **Passo 4.1:** Garantir que erros de leitura não quebrem o processo todo (try/except nos elementos individuais).
- [ ] **Passo 4.2:** Validação final com SVG de teste.

---

## 4. Dependências de Zona

- **Leitura:** Apenas arquivos SVG.
- **Escrita:** Apenas na pasta `models/{slug}/assets/`.
- **Imports Proibidos:** Nenhuma dependência de `ui.*` ou `playwright.*`.