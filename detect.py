from ultralytics import YOLO

# Загружаем модель
model = YOLO("best.pt")

print("Детектор здорового латука")

while True:
	print("Введите путь к фото (или перетащите файл в окно терминала):")
	img_path = input("→ ").strip().strip("'").strip('"')

	# save=False → не сохраняет картинки
	# verbose=False → отключает логи и прогресс-бары YOLO
	results = model(img_path, save=False, conf=0.25, verbose=False)

	print("\n🏷 Найденные метки:")
	for result in results:
			boxes = result.boxes
			if boxes is not None and len(boxes) > 0:
					for i, cls_id in enumerate(boxes.cls):
							cls_name = result.names[int(cls_id)]
							conf = boxes.conf[i]
							print(f"{cls_name}: {conf:.2%}")
			else:
					print("Объекты не обнаружены.")
