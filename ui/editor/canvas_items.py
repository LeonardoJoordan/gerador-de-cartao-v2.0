# ui/editor/canvas_items.py
from PySide6.QtWidgets import (QGraphicsLineItem, QGraphicsRectItem, QGraphicsTextItem, 
                               QGraphicsItem, QInputDialog, QLineEdit)
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QTextCursor, QTextBlockFormat

# --- CONFIGURAÇÃO DE UNIDADES ---
DPI = 96

def mm_to_px(mm):
    return (mm * DPI) / 25.4

def px_to_mm(px):
    return (px * 25.4) / DPI

# --- 1. A Linha Guia Editável ---
class Guideline(QGraphicsLineItem):
    def __init__(self, position_px, is_vertical=True):
        super().__init__()
        self.is_vertical = is_vertical
        
        if is_vertical:
            self.setLine(0, -10000, 0, 10000)
            self.setPos(position_px, 0)
        else:
            self.setLine(-10000, 0, 10000, 0)
            self.setPos(0, position_px)

        pen = QPen(QColor("#00bcd4"), 1, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self.setPen(pen)

        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(10)

    def mouseDoubleClickEvent(self, event):
        rect = self.scene().sceneRect()
        
        if self.is_vertical:
            axis_name = "Horizontal (X)"
            total_px = rect.width()
            current_px = self.pos().x()
        else:
            axis_name = "Vertical (Y)"
            total_px = rect.height()
            current_px = self.pos().y()

        total_mm = px_to_mm(total_px)
        current_mm = px_to_mm(current_px)

        label = (f"Posição (mm). Total disponível: {total_mm:.2f} mm\n"
                 f"Pode usar contas: '100/2', '{total_mm:.0f}-10', etc.")
        
        expression, ok = QInputDialog.getText(
            None, 
            f"Editar Guia {axis_name}", 
            label, 
            QLineEdit.EchoMode.Normal,
            f"{current_mm:.2f}"
        )

        if ok and expression:
            try:
                sanitized = expression.replace(",", ".")
                allowed_chars = set("0123456789.+-*/() ")
                if not set(sanitized).issubset(allowed_chars):
                    raise ValueError("Caracteres inválidos")
                
                final_val_mm = float(eval(sanitized))
                new_px = mm_to_px(final_val_mm)
                
                if self.is_vertical:
                    self.setPos(new_px, 0)
                else:
                    self.setPos(0, new_px)
                
                self.scene().update()
            except Exception as e:
                print(f"Erro na conta: {e}")

        super().mouseDoubleClickEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            curr_pos = value
            if self.is_vertical:
                return QPointF(curr_pos.x(), 0)
            else:
                return QPointF(0, curr_pos.y())
        return super().itemChange(change, value)


# --- 2. A Caixa Inteligente (Texto) ---
class DesignerBox(QGraphicsRectItem):
    SNAP_DISTANCE = 15

    def __init__(self, x, y, w, h, text="Placeholder"):
        super().__init__(0, 0, w, h)
        self.setPos(x, y) 
        
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        
        self.setPen(QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(255, 255, 255, 50)))
        self.setZValue(100)

        # Estado interno
        self.vertical_align = "top" # top, center, bottom

        self.text_item = QGraphicsTextItem(text, self)
        self.text_item.setFont(QFont("Arial", 16))
        self.text_item.setDefaultTextColor(Qt.GlobalColor.black)
        
        self.text_item.document().contentsChanged.connect(self.recalculate_text_position)

        self.text_item.setTextWidth(w) 
        self.text_item.setPos(0, 0)

    def set_vertical_alignment(self, align_str):
        self.vertical_align = align_str
        self.recalculate_text_position()

    def recalculate_text_position(self):
        self.text_item.setTextWidth(self.rect().width())
        
        doc_h = self.text_item.document().size().height()
        box_h = self.rect().height()
        
        y = 0
        if self.vertical_align == "center":
            y = (box_h - doc_h) / 2
        elif self.vertical_align == "bottom":
            y = box_h - doc_h
            
        self.text_item.setPos(0, y)

    def set_alignment(self, align_str):
        option = self.text_item.document().defaultTextOption()
        if align_str == "center": option.setAlignment(Qt.AlignmentFlag.AlignCenter)
        elif align_str == "right": option.setAlignment(Qt.AlignmentFlag.AlignRight)
        elif align_str == "justify": option.setAlignment(Qt.AlignmentFlag.AlignJustify)
        else: option.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.text_item.document().setDefaultTextOption(option)

    def set_block_format(self, indent=None, line_height=None):
        cursor = QTextCursor(self.text_item.document())
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextBlockFormat()
        if indent is not None: 
            fmt.setTextIndent(indent)
        if line_height is not None:
            fmt.setLineHeight(line_height * 100.0, 1)
        cursor.mergeBlockFormat(fmt)
        self.text_item.document().setDefaultBlockFormat(fmt)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            new_pos = value
            rect = self.rect()
            w, h = rect.width(), rect.height()
            
            x_candidates = [(new_pos.x(), 0), (new_pos.x() + w/2, w/2), (new_pos.x() + w, w)]
            y_candidates = [(new_pos.y(), 0), (new_pos.y() + h/2, h/2), (new_pos.y() + h, h)]
            
            best_x, best_y = new_pos.x(), new_pos.y()
            min_dist_x, min_dist_y = self.SNAP_DISTANCE, self.SNAP_DISTANCE

            for item in self.scene().items():
                if isinstance(item, Guideline):
                    if item.is_vertical:
                        for (cx, offset) in x_candidates:
                            if abs(cx - item.x()) < min_dist_x:
                                min_dist_x = abs(cx - item.x())
                                best_x = item.x() - offset
                    else:
                        for (cy, offset) in y_candidates:
                            if abs(cy - item.y()) < min_dist_y:
                                min_dist_y = abs(cy - item.y())
                                best_y = item.y() - offset
            return QPointF(best_x, best_y)
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        if self.isSelected():
            self.setPen(QPen(Qt.GlobalColor.blue, 2, Qt.PenStyle.DashLine))
            self.setBrush(QBrush(QColor(0, 100, 255, 30)))
        else:
            self.setPen(QPen(Qt.GlobalColor.gray, 1, Qt.PenStyle.DotLine))
            self.setBrush(QBrush(QColor(255, 255, 255, 10)))
        super().paint(painter, option, widget)