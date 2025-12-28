# core/sheet_assembler.py
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QPixmap
from PySide6.QtCore import Qt, QRectF, QPointF

# --- CONSTANTES DE IMPRESSÃO ---
DPI = 300
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297

# Conversão mm -> px em 300 DPI
def mm_to_px_300(mm):
    return int((mm * DPI) / 25.4)

class SheetAssembler:
    """
    Responsável por pegar uma lista de QImages (cartões) e montá-los
    em uma folha A4 com marcas de corte (Imposição).
    """
    def __init__(self, target_w_mm: float, target_h_mm: float):
        self.target_w_mm = target_w_mm
        self.target_h_mm = target_h_mm
        
        # --- CONSTANTES DE MARGEM ---
        # Margem de segurança da impressora (onde ela não imprime)
        self.printer_margin_mm = 4.0 
        
        # Configuração das Marcas de Corte
        self.mark_gap_mm = 2.0  # Distância da arte
        self.mark_len_mm = 3.0  # Comprimento do traço
        
        # Espaço extra necessário em cada borda para caber as marcas
        # (Margem Impressora + Gap da Marca + Tamanho da Marca)
        self.edge_reserve_mm = self.printer_margin_mm + self.mark_gap_mm + self.mark_len_mm
        
        # Conversão para Pixels
        self.card_w_px = mm_to_px_300(target_w_mm)
        self.card_h_px = mm_to_px_300(target_h_mm)
        self.mark_len = mm_to_px_300(self.mark_len_mm)
        self.mark_gap = mm_to_px_300(self.mark_gap_mm)
        
        # Dimensões Totais da Folha (Canvas real)
        full_a4_short_px = mm_to_px_300(A4_WIDTH_MM)
        full_a4_long_px = mm_to_px_300(A4_HEIGHT_MM)
        
        # Dimensões ÚTEIS (Canvas menos as reservas de borda)
        # É aqui que definimos onde os cartões podem "morar"
        reserve_px = mm_to_px_300(self.edge_reserve_mm * 2) # *2 pois é Esq+Dir
        
        usable_short_px = full_a4_short_px - reserve_px
        usable_long_px = full_a4_long_px - reserve_px

        # --- SIMULAÇÃO INTELIGENTE (Baseada na Área Útil) ---
        
        # Cenário A: Retrato (Folha em pé)
        # Usamos a dimensão ÚTIL para calcular capacidade...
        cols_p = usable_short_px // self.card_w_px
        rows_p = usable_long_px // self.card_h_px
        cap_p = cols_p * rows_p
        
        # Cenário B: Paisagem (Folha deitada)
        cols_l = usable_long_px // self.card_w_px
        rows_l = usable_short_px // self.card_h_px
        cap_l = cols_l * rows_l
        
        # Decisão
        if cap_l > cap_p:
            # Venceu Paisagem
            self.sheet_w = full_a4_long_px  # Canvas continua sendo o tamanho total
            self.sheet_h = full_a4_short_px
            self.cols = cols_l
            self.rows = rows_l
            self.capacity = cap_l
            print(f"[SheetAssembler] PAISAGEM (Área Útil: {usable_long_px}x{usable_short_px}px)")
        else:
            # Venceu Retrato
            self.sheet_w = full_a4_short_px
            self.sheet_h = full_a4_long_px
            self.cols = cols_p
            self.rows = rows_p
            self.capacity = cap_p
            print(f"[SheetAssembler] RETRATO (Área Útil: {usable_short_px}x{usable_long_px}px)")

        # Calcula margens para centralizar o bloco na página REAL
        total_grid_w = self.cols * self.card_w_px
        total_grid_h = self.rows * self.card_h_px
        
        self.margin_left = (self.sheet_w - total_grid_w) // 2
        self.margin_top = (self.sheet_h - total_grid_h) // 2

    def render_sheet(self, cards: list[QImage]) -> QImage:
        """
        Recebe uma lista de cartões (até o limite da capacidade)
        e retorna uma QImage única da folha A4 montada.
        """
        # 1. Cria a folha em branco
        sheet = QImage(self.sheet_w, self.sheet_h, QImage.Format_ARGB32)
        sheet.fill(Qt.GlobalColor.white)
        
        painter = QPainter(sheet)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 2. Desenha os Cartões na Grade
        # Iteramos pelas posições da grade para desenhar na ordem
        idx = 0
        limit = len(cards)
        
        for r in range(self.rows):
            for c in range(self.cols):
                if idx >= limit:
                    break
                
                # Pega a imagem original
                original_img = cards[idx]
                
                # Calcula posição X, Y na folha
                x = self.margin_left + (c * self.card_w_px)
                y = self.margin_top + (r * self.card_h_px)
                
                # Redimensiona para o tamanho alvo (High Quality) e desenha
                # Obs: Convertemos QImage para QPixmap para desenhar (melhor performance no Qt)
                scaled_pix = QPixmap.fromImage(original_img).scaled(
                    self.card_w_px, self.card_h_px,
                    Qt.AspectRatioMode.IgnoreAspectRatio, # Já garantimos proporção na UI
                    Qt.TransformationMode.SmoothTransformation
                )
                
                painter.drawPixmap(x, y, scaled_pix)
                idx += 1

        # 3. Desenha as Marcas de Corte (Crop Marks)
        self._draw_crop_marks(painter)
        
        painter.end()
        return sheet

    def _draw_crop_marks(self, painter: QPainter):
        """
        Desenha linhas pretas finas indicando onde cortar.
        Lógica: Corte Seco (cartões encostados).
        Marcas ficam FORA da área da grade, afastadas pelo mark_gap.
        """
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidth(2) # Linha fina, mas visível em 300 DPI
        painter.setPen(pen)

        # Limites do bloco de cartões
        grid_start_x = self.margin_left
        grid_end_x = self.margin_left + (self.cols * self.card_w_px)
        
        grid_start_y = self.margin_top
        grid_end_y = self.margin_top + (self.rows * self.card_h_px)

        # --- MARCAS VERTICAIS (Topo e Base) ---
        # Desenha uma marca para cada linha de corte vertical (incluindo as bordas externas)
        for c in range(self.cols + 1):
            x = grid_start_x + (c * self.card_w_px)
            
            # Marca Superior
            p1_top = QPointF(x, grid_start_y - self.mark_gap)
            p2_top = QPointF(x, grid_start_y - self.mark_gap - self.mark_len)
            painter.drawLine(p1_top, p2_top)
            
            # Marca Inferior
            p1_btm = QPointF(x, grid_end_y + self.mark_gap)
            p2_btm = QPointF(x, grid_end_y + self.mark_gap + self.mark_len)
            painter.drawLine(p1_btm, p2_btm)

        # --- MARCAS HORIZONTAIS (Esquerda e Direita) ---
        for r in range(self.rows + 1):
            y = grid_start_y + (r * self.card_h_px)
            
            # Marca Esquerda
            p1_lft = QPointF(grid_start_x - self.mark_gap, y)
            p2_lft = QPointF(grid_start_x - self.mark_gap - self.mark_len, y)
            painter.drawLine(p1_lft, p2_lft)
            
            # Marca Direita
            p1_rgt = QPointF(grid_end_x + self.mark_gap, y)
            p2_rgt = QPointF(grid_end_x + self.mark_gap + self.mark_len, y)
            painter.drawLine(p1_rgt, p2_rgt)