# core/worker.py
from PySide6.QtCore import QThread, Signal, QObject
from pathlib import Path
import os
import math
from core.naming import build_output_filename

class RenderWorker(QThread):
    """
    O Operário. 
    Agora ele é 'burro' quanto aos nomes: recebe o nome do arquivo pronto
    do gerente e apenas executa a renderização.
    """
    card_finished = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, renderer, chunk_plain, chunk_rich, chunk_filenames, output_dir):
        super().__init__()
        self.renderer = renderer
        self.chunk_plain = chunk_plain
        self.chunk_rich = chunk_rich
        self.chunk_filenames = chunk_filenames # [NOVO] Lista de nomes já decididos
        self.output_dir = output_dir
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            # Itera sobre os dados e os nomes pré-calculados em paralelo
            for i, row_plain in enumerate(self.chunk_plain):
                if not self._is_running:
                    break

                # 1. Pega o nome que o Gerente definiu
                filename = self.chunk_filenames[i]
                out_path = self.output_dir / f"{filename}.png"

                # 2. Renderiza
                row_rich = self.chunk_rich[i]
                self.renderer.render_row(row_plain, row_rich, out_path)

                # 3. Avisa
                self.card_finished.emit(f"{filename}.png")

        except Exception as e:
            import traceback
            self.error_occurred.emit(f"Erro na thread: {str(e)}\n{traceback.format_exc()}")


class RenderManager(QObject):
    """
    O Gerente.
    Agora centraliza a decisão dos nomes para evitar colisões entre threads.
    """
    progress_updated = Signal(int)
    log_updated = Signal(str)
    finished_process = Signal()
    error_occurred = Signal(str)

    def __init__(self, renderer, rows_plain, rows_rich, output_dir, filename_pattern):
        super().__init__()
        self.renderer = renderer
        self.rows_plain = rows_plain
        self.rows_rich = rows_rich
        self.output_dir = output_dir
        self.pattern = filename_pattern
        
        self.workers = []
        self.total_cards = len(rows_plain)
        self.cards_done = 0
        self._is_running = False

    def start(self):
        self._is_running = True
        self.cards_done = 0
        
        # 1. [NOVO] Pré-cálculo dos nomes (Single Threaded)
        # Garante unicidade global antes de dividir o trabalho
        self.log_updated.emit("📋 Calculando nomes de arquivos...")
        all_filenames = []
        used_names = set()
        
        for row in self.rows_plain:
            # O naming.py vai cuidar de adicionar _01, _02 aqui,
            # pois estamos passando o mesmo set 'used_names' para todos.
            fname = build_output_filename(self.pattern, row, used_names)
            all_filenames.append(fname)

        # 2. Cálculo de Threads
        cpu_count = os.cpu_count() or 4
        num_workers = max(1, cpu_count - 2)
        num_workers = min(num_workers, self.total_cards)

        self.log_updated.emit(f"🚀 Iniciando motor com {num_workers} threads paralelas...")

        # 3. Fatiamento (Chunking) das 3 listas: Plain, Rich e Filenames
        chunk_size = math.ceil(self.total_cards / num_workers)
        
        for i in range(num_workers):
            start = i * chunk_size
            end = start + chunk_size
            
            chunk_p = self.rows_plain[start:end]
            chunk_r = self.rows_rich[start:end]
            chunk_f = all_filenames[start:end] # A fatia de nomes correspondente
            
            if not chunk_p:
                continue

            worker = RenderWorker(
                self.renderer, 
                chunk_p, 
                chunk_r, 
                chunk_f, # Passa os nomes prontos
                self.output_dir
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

    def _on_worker_card_finished(self, filename):
        if not self._is_running:
            return

        self.cards_done += 1
        percent = int((self.cards_done / self.total_cards) * 100)
        self.progress_updated.emit(percent)
        
        # O log continua sequencial na ordem de CHEGADA (quem terminar primeiro aparece)
        self.log_updated.emit(f"[{self.cards_done}/{self.total_cards}] Concluído: {filename}")

    def _check_all_finished(self):
        if all(w.isFinished() for w in self.workers):
            if self._is_running:
                self.progress_updated.emit(100)
                self.finished_process.emit()