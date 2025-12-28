# core/worker.py
from PySide6.QtCore import QThread, Signal, QObject, QMutex
from pathlib import Path
import os
import math
from core.naming import build_output_filename

class RenderWorker(QThread):
    """
    O Operário. Recebe uma FATIA da lista de cartões e processa um por um.
    Não sabe nada sobre o total global, apenas faz o seu trabalho.
    """
    # Avisa que terminou UM cartão (manda o nome do arquivo)
    card_finished = Signal(str)
    # Avisa se deu erro
    error_occurred = Signal(str)

    def __init__(self, renderer, chunk_plain, chunk_rich, output_dir, pattern, start_index):
        super().__init__()
        self.renderer = renderer
        self.chunk_plain = chunk_plain
        self.chunk_rich = chunk_rich
        self.output_dir = output_dir
        self.pattern = pattern
        self.start_index = start_index # Apenas para debug interno se precisar
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        # Cada worker tem seu próprio set de nomes usados para evitar colisão local,
        # mas idealmente o pattern deve garantir unicidade global.
        used_names = set() 

        try:
            for i, row_plain in enumerate(self.chunk_plain):
                if not self._is_running:
                    break

                # 1. Define nome
                filename = build_output_filename(self.pattern, row_plain, used_names)
                out_path = self.output_dir / f"{filename}.png"

                # 2. Renderiza
                row_rich = self.chunk_rich[i]
                self.renderer.render_row(row_plain, row_rich, out_path)

                # 3. Avisa o gerente que terminou este arquivo
                self.card_finished.emit(f"{filename}.png")

        except Exception as e:
            import traceback
            self.error_occurred.emit(f"Erro na thread: {str(e)}\n{traceback.format_exc()}")


class RenderManager(QObject):
    """
    O Gerente. 
    1. Calcula quantos workers usar.
    2. Divide o trabalho (fatiamento).
    3. Recebe os avisos dos workers e mantém a contagem global (1/30, 2/30...).
    """
    progress_updated = Signal(int)      # 0 a 100%
    log_updated = Signal(str)           # Mensagens para o painel
    finished_process = Signal()         # Acabou tudo
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
        
        # 1. Cálculo de Threads (CPU - 2, mínimo 1)
        cpu_count = os.cpu_count() or 4
        num_workers = max(1, cpu_count - 2)
        
        # Se tiver poucos cartões (ex: 3), não precisa abrir 10 threads
        num_workers = min(num_workers, self.total_cards)

        self.log_updated.emit(f"🚀 Iniciando motor com {num_workers} threads paralelas...")

        # 2. Fatiamento (Chunking) da lista
        # Ex: 100 cartões, 4 workers -> chunks de 25
        chunk_size = math.ceil(self.total_cards / num_workers)
        
        for i in range(num_workers):
            start = i * chunk_size
            end = start + chunk_size
            
            # Pega a fatia correspondente das duas listas
            chunk_p = self.rows_plain[start:end]
            chunk_r = self.rows_rich[start:end]
            
            if not chunk_p:
                continue # Acabaram os cartões

            worker = RenderWorker(
                self.renderer, 
                chunk_p, 
                chunk_r, 
                self.output_dir, 
                self.pattern,
                start_index=start
            )
            
            # Conecta sinais do worker ao gerente
            worker.card_finished.connect(self._on_worker_card_finished)
            worker.error_occurred.connect(self.error_occurred)
            worker.finished.connect(self._check_all_finished) # Verifica se acabou a thread
            
            self.workers.append(worker)
            worker.start()

    def stop(self):
        """Para tudo imediatamente."""
        self._is_running = False
        self.log_updated.emit("🛑 Parando threads...")
        for w in self.workers:
            w.stop()
            w.quit()
            w.wait() # Aguarda encerramento seguro

    def _on_worker_card_finished(self, filename):
        if not self._is_running:
            return

        # O Gerente centraliza a contagem!
        self.cards_done += 1
        
        # Atualiza porcentagem
        percent = int((self.cards_done / self.total_cards) * 100)
        self.progress_updated.emit(percent)
        
        # Log sequencial e organizado
        self.log_updated.emit(f"[{self.cards_done}/{self.total_cards}] Concluído: {filename}")

    def _check_all_finished(self):
        """
        Chamado sempre que UMA thread morre. 
        Verifica se TODAS morreram para decretar o fim do processo.
        """
        if all(w.isFinished() for w in self.workers):
            # Garante 100% no final (arredondamentos)
            if self._is_running:
                self.progress_updated.emit(100)
                self.finished_process.emit()