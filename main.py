import cv2
import numpy as np
import json
import os
import glob
import sys
from PyQt6.QtWidgets import QApplication
import threading
import socket
import queue
import subprocess # Для запуска редактора как отдельного процесса

class VideoMaskPlayer:
    def __init__(self, app):
        self.video_path = "/home/kolpachkov/Projects/TRO/2.mov"
        self.cap = None
        self.masks = []
        self.apply_mask = False # Изначально маска выключена, пока не придут данные
        self.is_playing = True
        self.is_fullscreen = False
        self.app = app
        self.width = 1280  # Размеры по умолчанию
        self.height = 720
        
        # Очередь для безопасной передачи данных между потоками
        self.mask_queue = queue.Queue()
        
    def _start_socket_server(self):
        """Запускает сервер в фоновом потоке для приема масок."""
        HOST, PORT = "localhost", 12345
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((HOST, PORT))
            s.listen()
            print(f"Сервер слушает на {HOST}:{PORT}")
            while True:
                conn, addr = s.accept()
                with conn:
                    print(f"Подключился {addr}")
                    data = b''
                    while True:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        data += chunk
                    if data:
                        try:

                            shapes_data = json.loads(data.decode('utf-8'))
                            self.mask_queue.put(shapes_data)
                            print(f"Получены новые маски от клиента ({len(shapes_data)} шт.)")
                        except json.JSONDecodeError:
                            print("Ошибка: получены некорректные JSON данные")

    def set_mask_from_editor(self, shapes_data):
        """Устанавливает маски, полученные от редактора через сокет."""
        self.masks = []
        for i, shape_data in enumerate(shapes_data):
            if shape_data.get('is_closed'):
                points_list = shape_data['points']
                points = np.array(
                    [[int(x * self.width), int(y * self.height)] for x, y in points_list],
                    dtype=np.int32
                )
                self.masks.append({
                    'points': points,
                    'name': f"Editor_Shape_{i+1}",
                    'file': "Editor"
                })
        print(f"Маски из редактора установлены. Всего масок: {len(self.masks)}")
        self.apply_mask = True 
        
    def check_for_new_masks(self):
        """Проверяет очередь на наличие новых масок и применяет их."""
        try:
            new_masks_data = self.mask_queue.get_nowait()
            self.set_mask_from_editor(new_masks_data)
        except queue.Empty:
            # Если очередь пуста, ничего не делаем
            pass

    def load_video(self, video_path):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            print(f"Ошибка: Не удалось открыть видео файл {video_path}")
            return False
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Видео загружено: {self.width}x{self.height}")
        return True

    def apply_all_masks(self, frame):
        if not self.masks or not self.apply_mask:
            return frame
        combined_mask = np.zeros((self.height, self.width), dtype=np.uint8)
        for mask_data in self.masks:
            points = mask_data['points']
            cv2.fillPoly(combined_mask, [points], 255)
        return cv2.bitwise_and(frame, frame, mask=combined_mask)

    def toggle_mask(self):
        self.apply_mask = not self.apply_mask
        status = "ВКЛ" if self.apply_mask else "ВЫКЛ"
        print(f"Все маски: {status}")
        
    def toggle_fullscreen(self):
        """Переключение полноэкранного режима"""
        self.is_fullscreen = not self.is_fullscreen
        
        if self.is_fullscreen:
            cv2.setWindowProperty('Video Mask Player', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            print("Полноэкранный режим ВКЛ")
        else:
            cv2.setWindowProperty('Video Mask Player', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
            cv2.resizeWindow('Video Mask Player', 1200, 800)
            print("Полноэкранный режим ВЫКЛ")

    def run(self):
        if not self.cap:
            print("Ошибка: Видео не загружено")
            return

        server_thread = threading.Thread(target=self._start_socket_server, daemon=True)
        server_thread.start()

        cv2.namedWindow('Video Mask Player', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Video Mask Player', 1200, 800)
        
        print("\n=== УПРАВЛЕНИЕ ===")
        print("SPACE - Пауза/Продолжить")
        print("M - Вкл/Выкл маску")
        print("E - Открыть редактор масок")
        print("Q - Выход")
        print("==================\n")

        editor_process = None

        while True:
            # Проверяем, не пришли ли новые маски
            self.check_for_new_masks()

            if self.is_playing:
                ret, frame = self.cap.read()
                if not ret:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
            
            if 'frame' in locals():
                display_frame = frame.copy()
                if self.apply_mask and self.masks:
                    display_frame = self.apply_all_masks(display_frame)
                
                cv2.imshow('Video Mask Player', display_frame)
            
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break
            elif key == ord(' '):
                self.is_playing = not self.is_playing
            elif key == ord('m'):
                self.toggle_mask()
            elif key == ord('f'): # <-- Вот исправленная строка
                self.toggle_fullscreen()
            elif key == ord('e'):
                # Запускаем редактор как совершенно отдельный процесс
                if editor_process is None or editor_process.poll() is not None:
                    print("Запускаем редактор масок...")
                    editor_process = subprocess.Popen([sys.executable, 'shape_editor.py'])
                else:
                    print("Редактор уже запущен.")
        
        self.cap.release()
        cv2.destroyAllWindows()

def main():
    app = QApplication(sys.argv) 
    player = VideoMaskPlayer(app)
    
    video_path = "/home/kolpachkov/Projects/TRO/2.mov"
    if not os.path.exists(video_path) or not player.load_video(video_path):
        print("Основное видео не найдено. Пожалуйста, проверьте путь.")
        return

    player.run()

if __name__ == "__main__":
    main()