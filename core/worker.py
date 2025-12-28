# core/worker.py
from PySide6.QtCore import QThread, Signal
from pathlib import Path
from core.naming import build_output_filename

class RenderWorker(QThread):
    # Sinais para comunicar com a Interface (UI)
    progress_updated = Signal(int)      # Envia porcentagem (0-100)
    log_updated = Signal(str)           # Envia mensagem de texto
    finished_process = Signal()         # Avisa que acabou tudo
    error_occurred = Signal(str)        # Avisa se deu erro crítico

    def __init__(self, renderer, rows_plain, rows_rich, output_dir, filename_pattern):
        super().__init__()
        self.renderer = renderer
        self.rows_plain = rows_plain
        self.rows_rich = rows_rich
        self.output_dir = output_dir
        self.pattern = filename_pattern
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        """O código aqui roda em paralelo, sem travar a janela."""
        total = len(self.rows_plain)
        used_names = set()
        
        try:
            for i, row_plain in enumerate(self.rows_plain):
                if not self._is_running:
                    self.log_updated.emit("Processo cancelado pelo usuário.")
                    break

                # 1. Define nome
                filename = build_output_filename(self.pattern, row_plain, used_names)
                out_path = self.output_dir / f"{filename}.png"

                # 2. Renderiza (o trabalho pesado)
                row_rich = self.rows_rich[i]
                self.renderer.render_row(row_plain, row_rich, out_path)

                # 3. Notifica progresso
                # (i + 1) pois o índice começa em 0
                percent = int(((i + 1) / total) * 100)
                self.progress_updated.emit(percent)
                self.log_updated.emit(f"[{i+1}/{total}] Gerado: {filename}.png")

        except Exception as e:
            import traceback
            self.error_occurred.emit(f"Erro fatal no worker: {str(e)}\n{traceback.format_exc()}")
        
        self.finished_process.emit()