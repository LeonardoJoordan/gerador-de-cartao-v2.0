# core/worker.py
from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtGui import QImage
from pathlib import Path
import os
import math
from core.naming import build_output_filename
from core.sheet_assembler import SheetAssembler

class PageRenderWorker(QThread):
    """
    O Operário de Folhas.
    Diferente das versões anteriores, este worker recebe PACOTES DE FOLHAS.
    Ele é totalmente responsável por:
    1. Renderizar os cartões daquela folha.
    2. Montar a folha (usando SheetAssembler).
    3. Salvar o arquivo final.
    
    Isso elimina completamente a necessidade de sincronização ou buffers no Gerente.
    """
    # Emite: (numero_cartoes_processados, nome_arquivo_gerado, msg_log)
    page_finished = Signal(int, str, str) 
    error_occurred = Signal(str)

    def __init__(self, tasks, renderer, output_dir, imposition_settings):
        super().__init__()
        self.tasks = tasks # Lista de pacotes de página
        self.renderer = renderer
        self.output_dir = output_dir
        
        # Cada worker tem seu próprio montador para segurança total de thread
        w_mm = imposition_settings.get("target_w_mm", 100)
        h_mm = imposition_settings.get("target_h_mm", 150)
        self.assembler = SheetAssembler(w_mm, h_mm)
        
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            for page_task in self.tasks:
                if not self._is_running: break

                # page_task contém: 
                # { "page_num": int, "cards": [ (row_plain, row_rich, filename), ... ] }
                
                page_num = page_task["page_num"]
                cards_data = page_task["cards"]
                
                # 1. Renderiza os cartões desta folha em memória
                card_images = []
                for (r_plain, r_rich, fname) in cards_data:
                    img = self.renderer.render_to_qimage(r_plain, r_rich)
                    card_images.append(img)
                
                # 2. Monta a folha usando o Assembler
                sheet_img = self.assembler.render_sheet(card_images)
                
                # 3. Salva
                # Padrão de nome: NOME_DO_PRIMEIRO_ARQUIVO_Folha_XX.png
                # Ou pega o padrão do gerenciador. Vamos usar um padrão limpo.
                # Como 'cards_data' tem o nome individual, vamos pegar o prefixo comum ou usar o padrão.
                # Simplificação: Usamos o nome do primeiro cartão como base ou um nome genérico da tarefa.
                
                # Para manter consistência com o Manager, o nome do arquivo foi passado na task?
                # Vamos ajustar o Manager para mandar o nome da folha.
                out_name = page_task["output_filename"]
                out_path = self.output_dir / out_name
                
                sheet_img.save(str(out_path))
                
                # 4. Reporta sucesso
                msg = f"🖨️  FOLHA {page_num:02d} OK ({len(card_images)} itens)"
                self.page_finished.emit(len(card_images), out_name, msg)
                
                # Limpa memória explicitamente (embora Python faça garbage collection)
                card_images.clear()
                del sheet_img

        except Exception as e:
            import traceback
            self.error_occurred.emit(f"Erro no Worker: {str(e)}\n{traceback.format_exc()}")


class DirectRenderWorker(QThread):
    """
    Operário Clássico (Um cartão = Um arquivo).
    Usado quando a imposição está DESLIGADA.
    """
    card_finished = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, chunk_data, renderer, output_dir):
        super().__init__()
        self.chunk_data = chunk_data # Lista de (row_plain, row_rich, filename)
        self.renderer = renderer
        self.output_dir = output_dir
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            for (row_plain, row_rich, filename) in self.chunk_data:
                if not self._is_running: break
                
                out_path = self.output_dir / f"{filename}.png"
                self.renderer.render_row(row_plain, row_rich, out_path)
                self.card_finished.emit(f"{filename}.png")
        except Exception as e:
            self.error_occurred.emit(str(e))


class RenderManager(QObject):
    """
    O Gerente Logístico.
    Agora ele PREPARA os pacotes antes de chamar os operários.
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
        
        self.imposition_settings = imposition_settings or {"enabled": False}
        self.is_imposition = self.imposition_settings.get("enabled", False)
        
        self.workers = []
        self.total_cards = len(rows_plain)
        self.cards_done = 0
        self._is_running = False

    def start(self):
        self._is_running = True
        self.cards_done = 0
        self.workers = []
        
        self.log_updated.emit("📋 Planejando produção...")
        
        # 1. Gera todos os nomes de arquivo virtuais
        all_tasks_data = [] # Lista de tuplas (plain, rich, filename)
        used_names = set()
        for i, row in enumerate(self.rows_plain):
            fname = build_output_filename(self.pattern, row, used_names)
            all_tasks_data.append( (self.rows_plain[i], self.rows_rich[i], fname) )

        cpu_count = os.cpu_count() or 4
        # Usa (Núcleos - 2) para deixar o sistema respirar
        num_threads = max(1, cpu_count - 2)

        if self.is_imposition:
            self._start_imposition_mode(all_tasks_data, num_threads)
        else:
            self._start_direct_mode(all_tasks_data, num_threads)

    def _start_imposition_mode(self, all_data, num_threads):
        # 1. Instancia um assembler temporário só para descobrir a capacidade da folha
        w_mm = self.imposition_settings.get("target_w_mm", 100)
        h_mm = self.imposition_settings.get("target_h_mm", 150)
        temp_asm = SheetAssembler(w_mm, h_mm)
        capacity = temp_asm.capacity
        
        total_pages = math.ceil(len(all_data) / capacity)
        self.log_updated.emit(f"📚 Modo Imposição: {len(all_data)} cartões cabem em {total_pages} folhas (Capacidade: {capacity}/fl).")
        self.log_updated.emit(f"🚀 Distribuindo trabalho para {num_threads} threads...")

        # 2. Cria os pacotes de PÁGINAS (Jobs)
        # pages_jobs será uma lista de dicionários
        pages_jobs = []
        
        # Nome base para as folhas (limpa chaves do padrão)
        safe_pattern = self.pattern.replace("{", "").replace("}", "")

        for page_idx in range(total_pages):
            start_idx = page_idx * capacity
            end_idx = min(start_idx + capacity, len(all_data))
            
            page_cards = all_data[start_idx:end_idx]
            page_num = page_idx + 1
            
            job = {
                "page_num": page_num,
                "output_filename": f"{safe_pattern}_Folha_{page_num:02d}.png",
                "cards": page_cards
            }
            pages_jobs.append(job)

        # 3. Distribui os pacotes de páginas entre as threads (Round Robin ou Chunk)
        # Vamos dividir a lista de páginas igualmente
        chunk_size = math.ceil(total_pages / num_threads)
        
        for i in range(num_threads):
            start = i * chunk_size
            end = start + chunk_size
            worker_tasks = pages_jobs[start:end]
            
            if not worker_tasks: continue
            
            w = PageRenderWorker(worker_tasks, self.renderer, self.output_dir, self.imposition_settings)
            w.page_finished.connect(self._on_page_finished)
            w.error_occurred.connect(self.error_occurred)
            w.finished.connect(self._check_all_finished)
            
            self.workers.append(w)
            w.start()

    def _start_direct_mode(self, all_data, num_threads):
        self.log_updated.emit(f"🚀 Modo Direto: Processando {len(all_data)} arquivos em {num_threads} threads...")
        
        chunk_size = math.ceil(len(all_data) / num_threads)
        
        for i in range(num_threads):
            start = i * chunk_size
            end = start + chunk_size
            chunk = all_data[start:end]
            
            if not chunk: continue
            
            w = DirectRenderWorker(chunk, self.renderer, self.output_dir)
            w.card_finished.connect(self._on_direct_card_finished)
            w.error_occurred.connect(self.error_occurred)
            w.finished.connect(self._check_all_finished)
            
            self.workers.append(w)
            w.start()

    def stop(self):
        self._is_running = False
        self.log_updated.emit("🛑 Parando threads...")
        for w in self.workers:
            w.stop()
            w.quit()
            w.wait()

    def _on_page_finished(self, num_cards, filename, msg):
        if not self._is_running: return
        self.cards_done += num_cards
        self.log_updated.emit(msg)
        self._update_progress()

    def _on_direct_card_finished(self, filename):
        if not self._is_running: return
        self.cards_done += 1
        self.log_updated.emit(f"[{self.cards_done}/{self.total_cards}] Salvo: {filename}")
        self._update_progress()

    def _update_progress(self):
        # Garante que não passe de 100%
        done = min(self.cards_done, self.total_cards)
        percent = int((done / self.total_cards) * 100)
        self.progress_updated.emit(percent)

    def _check_all_finished(self):
        if all(w.isFinished() for w in self.workers):
            if self._is_running:
                self.progress_updated.emit(100)
                self.finished_process.emit()
                self.log_updated.emit("✅ Processo finalizado com sucesso!")