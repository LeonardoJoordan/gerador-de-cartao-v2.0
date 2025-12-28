# core/worker.py
from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtGui import QImage
from pathlib import Path
import os
import math
from core.naming import build_output_filename
from core.sheet_assembler import SheetAssembler

class RenderWorker(QThread):
    """
    O Operário. 
    Suporta dois modos:
    1. Direto: Renderiza e salva no disco.
    2. Imposição: Renderiza e devolve a QImage para o gerente montar a folha.
    """
    # Se salvar direto, emite (filename, None). Se imposição, emite (filename, QImage)
    card_finished = Signal(str, object) 
    error_occurred = Signal(str)

    def __init__(self, renderer, chunk_plain, chunk_rich, chunk_filenames, output_dir, imposition_mode=False):
        super().__init__()
        self.renderer = renderer
        self.chunk_plain = chunk_plain
        self.chunk_rich = chunk_rich
        self.chunk_filenames = chunk_filenames
        self.output_dir = output_dir
        self.imposition_mode = imposition_mode
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            for i, row_plain in enumerate(self.chunk_plain):
                if not self._is_running:
                    break

                filename = self.chunk_filenames[i]
                row_rich = self.chunk_rich[i]

                if self.imposition_mode:
                    # Modo Imposição: Devolve a imagem para o gerente
                    img = self.renderer.render_to_qimage(row_plain, row_rich)
                    self.card_finished.emit(filename, img)
                else:
                    # Modo Direto: Salva e avisa
                    out_path = self.output_dir / f"{filename}.png"
                    self.renderer.render_row(row_plain, row_rich, out_path)
                    self.card_finished.emit(f"{filename}.png", None)

        except Exception as e:
            import traceback
            self.error_occurred.emit(f"Erro na thread: {str(e)}\n{traceback.format_exc()}")


class RenderManager(QObject):
    """
    O Gerente.
    Gerencia workers e, se necessário, acumula cartões para montar folhas A4 (SheetAssembler).
    """
    progress_updated = Signal(int)
    log_updated = Signal(str)
    finished_process = Signal()
    error_occurred = Signal(str)

    def __init__(self, renderer, rows_plain, rows_rich, output_dir, filename_pattern, imposition_settings=None):
        super().__init__()
        self.renderer = renderer
        self.rows_plain = rows_plain
        self.rows_rich = rows_rich
        self.output_dir = output_dir
        self.pattern = filename_pattern
        
        # Configuração de Imposição
        self.imposition_settings = imposition_settings or {"enabled": False}
        self.is_imposition = self.imposition_settings.get("enabled", False)
        self.assembler = None
        self.page_buffer = [] # Lista de QImages aguardando montagem
        self.page_counter = 1

        if self.is_imposition:
            w_mm = self.imposition_settings.get("target_w_mm", 100)
            h_mm = self.imposition_settings.get("target_h_mm", 150)
            self.assembler = SheetAssembler(w_mm, h_mm)

        self.workers = []
        self.total_cards = len(rows_plain)
        self.cards_done = 0
        self._is_running = False

    def start(self):
        self._is_running = True
        self.cards_done = 0
        self.page_counter = 1
        self.page_buffer = []
        
        self.log_updated.emit("📋 Calculando nomes de arquivos...")
        all_filenames = []
        used_names = set()
        
        for row in self.rows_plain:
            fname = build_output_filename(self.pattern, row, used_names)
            all_filenames.append(fname)

        cpu_count = os.cpu_count() or 4
        # Se for imposição, cuidado com memória: limitamos a 2 threads para não estourar RAM com QImages
        num_workers = 2 if self.is_imposition else max(1, cpu_count - 2)
        num_workers = min(num_workers, self.total_cards)

        mode_str = "IMPOSIÇÃO (A4)" if self.is_imposition else "DIRETO (PNG)"
        self.log_updated.emit(f"🚀 Iniciando motor [{mode_str}] com {num_workers} threads...")

        chunk_size = math.ceil(self.total_cards / num_workers)
        
        for i in range(num_workers):
            start = i * chunk_size
            end = start + chunk_size
            
            chunk_p = self.rows_plain[start:end]
            chunk_r = self.rows_rich[start:end]
            chunk_f = all_filenames[start:end]
            
            if not chunk_p: continue

            worker = RenderWorker(
                self.renderer, chunk_p, chunk_r, chunk_f, self.output_dir,
                imposition_mode=self.is_imposition
            )
            
            worker.card_finished.connect(self._on_worker_card_finished)
            worker.error_occurred.connect(self.error_occurred)
            worker.finished.connect(self._check_all_finished)
            
            self.workers.append(worker)
            worker.start()

    def stop(self):
        self._is_running = False
        self.log_updated.emit("🛑 Parando threads...")
        for w in self.workers:
            w.stop()
            w.quit()
            w.wait()

    def _on_worker_card_finished(self, filename, qimage_result):
        if not self._is_running:
            return

        self.cards_done += 1
        
        if self.is_imposition and qimage_result:
            # Acumula no buffer
            self.page_buffer.append(qimage_result)
            
            # Se encheu a folha, salva
            if len(self.page_buffer) >= self.assembler.capacity:
                self._flush_page()
        else:
            # Modo direto, só loga
            self.log_updated.emit(f"[{self.cards_done}/{self.total_cards}] Salvo: {filename}")

        percent = int((self.cards_done / self.total_cards) * 100)
        self.progress_updated.emit(percent)

    def _flush_page(self):
        """Monta e salva uma folha com o que tiver no buffer."""
        if not self.page_buffer: return
        
        try:
            sheet_img = self.assembler.render_sheet(self.page_buffer)
            
            # Nome da folha: padrao_Folha_01.png
            safe_pattern = self.pattern.replace("{", "").replace("}", "")
            out_name = f"{safe_pattern}_Folha_{self.page_counter:02d}.png"
            out_path = self.output_dir / out_name
            
            sheet_img.save(str(out_path))
            self.log_updated.emit(f"🖨️  FOLHA GERADA: {out_name} ({len(self.page_buffer)} itens)")
            
            self.page_counter += 1
            self.page_buffer.clear() # Limpa para a próxima
        except Exception as e:
            self.error_occurred.emit(f"Erro ao salvar folha: {e}")

    def _check_all_finished(self):
        if all(w.isFinished() for w in self.workers):
            if self._is_running:
                # Se sobrou algo no buffer (última página incompleta), salva agora
                if self.is_imposition and self.page_buffer:
                    self._flush_page()

                self.progress_updated.emit(100)
                self.finished_process.emit()