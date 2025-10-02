import sys
import numpy as np
import json
import socket
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QPushButton,
                             QVBoxLayout, QHBoxLayout, QLabel, QMessageBox,
                             QFileDialog)
from PyQt6.QtGui import QPainter, QPen, QColor, QPolygon, QBrush
from PyQt6.QtCore import Qt, QPoint

# ... (Классы Shape и CanvasWidget остаются без изменений, как в предыдущем ответе) ...
class Shape:
    """
    Класс для представления одной фигуры
    """
    def __init__(self):
        self.points = []  # Точки фигуры
        self.is_closed = False  # Замкнута ли фигура
        self.color = self.generate_color()  # Уникальный цвет для каждой фигуры

    def generate_color(self):
        """Генерирует случайный цвет для фигуры"""
        colors = [
            QColor("#FF6B6B"), QColor("#4ECDC4"), QColor("#45B7D1"),
            QColor("#96CEB4"), QColor("#FFEAA7"), QColor("#DDA0DD"),
            QColor("#98D8C8"), QColor("#F7DC6F"), QColor("#BB8FCE")
        ]
        # Простая логика, чтобы избежать выхода за пределы списка при большом количестве точек
        return colors[np.random.randint(0, len(colors))]


    def add_point(self, point):
        """Добавляет точку к фигуре"""
        self.points.append(point)

    def close(self):
        """Замыкает фигуру"""
        if len(self.points) > 2:
            self.is_closed = True
            return True
        return False

    def get_numpy_points(self):
        """Возвращает точки в формате NumPy"""
        if not self.points:
            return None
        points_list = [[point.x(), point.y()] for point in self.points]
        return np.array(points_list, dtype=np.int32)

    def to_dict(self):
        """Конвертирует фигуру в словарь для JSON"""
        return {
            'points': [[point.x(), point.y()] for point in self.points],
            'is_closed': self.is_closed,
            'color': {
                'red': self.color.red(),
                'green': self.color.green(),
                'blue': self.color.blue(),
                'alpha': self.color.alpha()
            }
        }

class CanvasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.shapes = []
        self.current_shape = None
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background-color: #333;")
        self.last_width = self.width()
        self.last_height = self.height()
        
    def save_to_json(self, filename):
        """Сохраняет все фигуры в JSON файл"""
        data = {
            'shapes': [self.shape_to_dict(shape) for shape in self.shapes],
            'metadata': {
                'total_shapes': len(self.shapes),
                'closed_shapes': len([s for s in self.shapes if s.is_closed]),
                'canvas_size': {
                    'width': self.width(),
                    'height': self.height()
                }
            }
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка сохранения: {e}")
            return False

    def shape_to_dict(self, shape):
        """Конвертирует фигуру в словарь для JSON с относительными координатами"""
        width = self.width()
        height = self.height()
        if width == 0 or height == 0:
             return { 'points': [], 'is_closed': shape.is_closed, 'color': {} }

        return {
            'points': [[point.x() / width, point.y() / height] for point in shape.points],
            'is_closed': shape.is_closed,
            'color': {
                'red': shape.color.red(),
                'green': shape.color.green(),
                'blue': shape.color.blue(),
                'alpha': shape.color.alpha()
            }
        }

    def load_from_json(self, filename):
        """Загружает фигуры из JSON файла"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.shapes = []
            width = self.width()
            height = self.height()
            for shape_data in data.get('shapes', []):
                shape = Shape()
                for point in shape_data['points']:
                    shape.add_point(QPoint(int(point[0] * width), int(point[1] * height)))
                if shape_data.get('is_closed', False):
                    shape.close()
                color_data = shape_data.get('color', {})
                if color_data:
                    shape.color = QColor(
                        color_data.get('red', 255),
                        color_data.get('green', 255),
                        color_data.get('blue', 255),
                        color_data.get('alpha', 255)
                    )
                self.shapes.append(shape)

            self.current_shape = None
            self.update()
            print(f"Загружено {len(self.shapes)} фигур из {filename}")
            return True

        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            return False

    def resizeEvent(self, event):
        """Обработчик изменения размера виджета"""
        if self.shapes and hasattr(self, 'last_width') and self.last_width > 0 and self.last_height > 0:
             self.rescale_shapes(event.oldSize().width(), event.oldSize().height())
        self.last_width = self.width()
        self.last_height = self.height()
        super().resizeEvent(event)

    def rescale_shapes(self, old_width, old_height):
        """Пересчитывает координаты точек фигур при изменении размера виджета"""
        new_width = self.width()
        new_height = self.height()

        for shape in self.shapes:
            new_points = []
            for point in shape.points:
                relative_x = point.x() / old_width
                relative_y = point.y() / old_height
                new_points.append(QPoint(int(relative_x * new_width), int(relative_y * new_height)))
            shape.points = new_points
        self.update()


    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.current_shape is None:
                self.current_shape = Shape()
                self.shapes.append(self.current_shape)
                if not hasattr(self, 'last_width') or self.last_width == 0:
                     self.last_width = self.width()
                     self.last_height = self.height()
            self.current_shape.add_point(event.pos())
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            if self.current_shape and not self.current_shape.is_closed:
                if self.current_shape.close():
                    print(f"Фигура {len(self.shapes)} замкнута. Вершин: {len(self.current_shape.points)}")
                else:
                    if len(self.current_shape.points) < 3 and self.current_shape in self.shapes:
                        self.shapes.remove(self.current_shape)
                        print("Фигура удалена - недостаточно точек для замыкания")
            self.current_shape = None
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for i, shape in enumerate(self.shapes):
            if not shape.points: continue
            
            point_color = shape.color.lighter(150)
            painter.setPen(QPen(point_color, 8, Qt.PenStyle.SolidLine))
            for point in shape.points:
                painter.drawPoint(point)

            line_color = shape.color.lighter(100)
            painter.setPen(QPen(line_color, 2, Qt.PenStyle.SolidLine))
            if len(shape.points) > 1:
                painter.drawPolyline(QPolygon(shape.points))

            if shape.is_closed and len(shape.points) > 2:
                painter.drawLine(shape.points[-1], shape.points[0])
                fill_color = QColor(shape.color)
                fill_color.setAlpha(80)
                brush = QBrush(fill_color)
                painter.setBrush(brush)
                polygon = QPolygon(shape.points)
                painter.drawPolygon(polygon)
                
                if shape.points:
                    center_x = sum(p.x() for p in shape.points) // len(shape.points)
                    center_y = sum(p.y() for p in shape.points) // len(shape.points)
                    painter.setPen(QPen(Qt.GlobalColor.white, 1))
                    painter.drawText(center_x - 10, center_y, f"{i+1}")
    
    def close_current_shape(self):
        if self.current_shape and not self.current_shape.is_closed:
            if self.current_shape.close():
                print(f"Фигура {len(self.shapes)} замкнута.")
                self.current_shape = None
                self.update()
                return True
        return False

    def clear_all(self):
        self.shapes = []
        self.current_shape = None
        self.update()
        print("Все фигуры удалены.")
    
    def delete_last_shape(self):
        if self.shapes:
            removed_shape = self.shapes.pop()
            if self.current_shape == removed_shape:
                self.current_shape = None
            self.update()
            print(f"Удалена фигура. Осталось фигур: {len(self.shapes)}")
        else:
            print("Нет фигур для удаления.")
    
    def get_all_shapes_as_numpy(self):
        shapes_data = []
        for i, shape in enumerate(self.shapes):
            if shape.is_closed and len(shape.points) > 2:
                points_np = shape.get_numpy_points()
                if points_np is not None:
                    shapes_data.append({'id': i, 'points': points_np, 'color': shape.color})
        return shapes_data


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Редактор форм для маски")
        self.canvas = CanvasWidget()

        # Создаем кнопки
        self.btn_close = QPushButton("Замкнуть текущую фигуру")
        self.btn_new = QPushButton("Новая фигура")
        self.btn_delete_last = QPushButton("Удалить последнюю фигуру")
        self.btn_clear = QPushButton("Очистить все")
        self.btn_info = QPushButton("Инструкция")
        
        # ================== ИЗМЕНЕНИЕ 1: Текст кнопки ==================
        self.btn_send = QPushButton("Отправить и Очистить")

        # Информационная метка
        self.info_label = QLabel("Левый клик - добавить точку | Правый клик - завершить фигуру")
        self.info_label.setStyleSheet("color: #ccc; padding: 5px;")

        # Привязываем функции
        self.btn_close.clicked.connect(self.canvas.close_current_shape)
        self.btn_new.clicked.connect(self.start_new_shape)
        self.btn_delete_last.clicked.connect(self.canvas.delete_last_shape)
        self.btn_clear.clicked.connect(self.canvas.clear_all)
        self.btn_info.clicked.connect(self.show_instructions)
        self.btn_send.clicked.connect(self.send_shapes)

        # Компоновка интерфейса
        button_layout1 = QHBoxLayout()
        button_layout1.addWidget(self.btn_close)
        button_layout1.addWidget(self.btn_new)
        button_layout1.addWidget(self.btn_delete_last)

        button_layout2 = QHBoxLayout()
        button_layout2.addWidget(self.btn_clear)
        button_layout2.addWidget(self.btn_info)
        button_layout2.addWidget(self.btn_send)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.canvas)
        main_layout.addWidget(self.info_label)
        main_layout.addLayout(button_layout1)
        main_layout.addLayout(button_layout2)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def start_new_shape(self):
        self.canvas.close_current_shape()
        self.canvas.current_shape = None
        print("Готов к рисованию новой фигуры.")

    def send_shapes(self):
        """Собирает, сериализует и отправляет данные, а затем очищает холст."""
        shapes_data = [shape.to_dict() for shape in self.canvas.shapes if shape.is_closed]
        
        if not self.canvas.shapes or not any(s.is_closed for s in self.canvas.shapes):
            QMessageBox.warning(self, "Ошибка", "Нет замкнутых фигур для отправки.")
            return
            
        width = self.canvas.width()
        height = self.canvas.height()
        for shape_dict in shapes_data:
            shape_dict['points'] = [[p[0] / width, p[1] / height] for p in shape_dict['points']]

        try:
            json_data = json.dumps(shapes_data).encode('utf-8')
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка сериализации данных: {e}")
            return

        HOST, PORT = "localhost", 12345
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((HOST, PORT))
                sock.sendall(json_data)
            
            QMessageBox.information(self, "Успех", "Маски успешно отправлены!")
            
            # ================== ИЗМЕНЕНИЕ 2: Очистка вместо закрытия ==================
            self.canvas.clear_all()

        except ConnectionRefusedError:
            QMessageBox.critical(self, "Ошибка", "Не удалось подключиться к основному приложению. Убедитесь, что оно запущено.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при отправке: {e}")

    def show_instructions(self):
        instructions = """
        ИНСТРУКЦИЯ:
        • ЛЕВЫЙ КЛИК - добавить точку к текущей фигуре
        • ПРАВЫЙ КЛИК - завершить текущую фигуру и начать новую
        • "Отправить и Очистить" - передает все замкнутые фигуры в основное приложение и очищает холст для создания новых.
        """
        QMessageBox.information(self, "Инструкция", instructions.strip())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())