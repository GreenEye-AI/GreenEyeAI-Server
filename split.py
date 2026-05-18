from PIL import Image

img = Image.open('stream.jpg')

x1, y1 = (130, 100)
x2, y2 = (x1+738, y1+551)

# 1. Нормализуем координаты (на случай, если x2 < x1 или y2 < y1)
x_left, x_right = sorted([x1, x2])
y_top, y_bottom = sorted([y1, y2])

# 2. Параметры сетки
cols, rows = 5, 4
tile_w = (x_right - x_left) / cols
tile_h = (y_bottom - y_top) / rows

# 3. Вычисляем точные границы разрезов (избегаем зазоров и наложений)
x_bounds = [int(round(x_left + i * tile_w)) for i in range(cols + 1)]
y_bounds = [int(round(y_top + i * tile_h)) for i in range(rows + 1)]
x_bounds[-1], y_bounds[-1] = x_right, y_bottom  # Фиксируем правый нижний угол

idx = 1
for r in range(rows):
	for c in range(cols):
		# (left, upper, right, lower)
		box = (x_bounds[c], y_bounds[r], x_bounds[c+1], y_bounds[r+1])
		tile = img.crop(box)
				
		# Формат JPEG требует режима RGB (RGBA/Grayscale вызовут ошибку)
		if tile.mode != 'RGB':
			tile = tile.convert('RGB')
		tile.save(f'temp/{idx}.jpg')
		idx += 1