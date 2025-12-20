# Руководство по участию в проекте

Спасибо за интерес к проекту Pillow Bot! 

## Как внести вклад

1. Форкните репозиторий
2. Создайте ветку для вашей функции (`git checkout -b feature/AmazingFeature`)
3. Зафиксируйте изменения (`git commit -m 'Add some AmazingFeature'`)
4. Отправьте изменения в ветку (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

## Установка для разработки

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/pillow-bot.git
cd pillow-bot
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

4. Добавьте токен бота в `.env`:
```
BOT_TOKEN=your_bot_token_here
```

5. Запустите бота:
```bash
python bot.py
```

## Правила кода

- Следуйте стилю PEP 8
- Добавляйте комментарии к новым функциям
- Обновляйте документацию при добавлении новых функций



