# Gerador de Cartão em Lote v3.0

Gerador de cartões tipograficamente avançado, baseado em modelos SVG e renderização HTML/CSS.

## 🎯 Objetivo
Criar cartões personalizados em lote com:
- tipografia profissional (justify, indent, bold parcial)
- modelos reutilizáveis
- pipeline previsível e multiplataforma

## 🧱 Pipeline
SVG (modelo)
→ Scanner (boxes + placeholders)
→ HTML/CSS (Playwright)
→ overlay.png
→ Pillow
→ final.png


## 🛠 Tecnologias
- Python 3.10+
- PySide6
- Playwright (Chromium headless)
- Pillow

## 📌 Status
Projeto em desenvolvimento ativo (V2).
Pipeline de renderização e composição já funcional.
