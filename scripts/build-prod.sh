#!/bin/bash
# Скрипт для локальной сборки production образа

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Сборка production образа ===${NC}"

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker не установлен. Установите Docker для сборки образа.${NC}"
    exit 1
fi

# Имя образа
IMAGE_NAME="universal-multiagent"
IMAGE_TAG="latest"

echo -e "${GREEN}Собираем Docker образ...${NC}"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo -e "${GREEN}✓ Образ собран: ${IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo -e "${YELLOW}Для запуска локально используйте:${NC}"
echo -e "${YELLOW}  docker run -p 8000:8000 --env-file .env ${IMAGE_NAME}:${IMAGE_TAG}${NC}"





