#!/bin/bash
# Скрипт для локального тестирования production образа

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Тестирование production образа локально ===${NC}"

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker не установлен${NC}"
    exit 1
fi

# Имя образа
IMAGE_NAME="universal-multiagent"
IMAGE_TAG="latest"

# Проверяем наличие образа
if ! docker images | grep -q "${IMAGE_NAME}.*${IMAGE_TAG}"; then
    echo -e "${YELLOW}Образ не найден. Собираем...${NC}"
    ./scripts/build-prod.sh
fi

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Файл .env не найден. Используйте .env.example как шаблон.${NC}"
    exit 1
fi

echo -e "${GREEN}Запускаем контейнер...${NC}"
echo -e "${YELLOW}Приложение будет доступно на http://localhost:8000${NC}"
echo -e "${YELLOW}Нажмите Ctrl+C для остановки${NC}"

# Запускаем контейнер
docker run -it --rm \
    -p 8000:8000 \
    --env-file .env \
    -e APP_ENV=production \
    -e DATA_DIR=/app/data \
    -v $(pwd)/data:/app/data \
    ${IMAGE_NAME}:${IMAGE_TAG}



