#!/bin/bash
# Скрипт для синхронизации изменений из dev (main) ветки в production ветку

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Синхронизация изменений в production ===${NC}"

# Проверяем, что мы не в production ветке
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "production" ]; then
    echo -e "${YELLOW}Предупреждение: Вы находитесь в production ветке${NC}"
    echo -e "${YELLOW}Переключаемся на main для синхронизации...${NC}"
    git checkout main
    CURRENT_BRANCH="main"
fi

# Определяем source ветку (main или dev)
SOURCE_BRANCH=${1:-main}
TARGET_BRANCH="production"

echo -e "${GREEN}Источник: ${SOURCE_BRANCH}${NC}"
echo -e "${GREEN}Цель: ${TARGET_BRANCH}${NC}"

# Проверяем наличие незакоммиченных изменений
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}Ошибка: Есть незакоммиченные изменения${NC}"
    echo -e "${YELLOW}Пожалуйста, закоммитьте или отмените изменения перед синхронизацией${NC}"
    exit 1
fi

# Получаем последние изменения
echo -e "${GREEN}Получаем последние изменения из репозитория...${NC}"
git fetch origin

# Переключаемся на production
echo -e "${GREEN}Переключаемся на ветку ${TARGET_BRANCH}...${NC}"
git checkout $TARGET_BRANCH

# Обновляем production ветку
echo -e "${GREEN}Обновляем ${TARGET_BRANCH}...${NC}"
git pull origin $TARGET_BRANCH 2>/dev/null || echo "Ветка ${TARGET_BRANCH} еще не существует в origin"

# Мержим изменения из source ветки
echo -e "${GREEN}Мержим изменения из ${SOURCE_BRANCH}...${NC}"
if git merge $SOURCE_BRANCH --no-edit; then
    echo -e "${GREEN}✓ Изменения успешно смержены${NC}"
else
    echo -e "${RED}✗ Обнаружены конфликты при мерже${NC}"
    echo -e "${YELLOW}Пожалуйста, разрешите конфликты вручную:${NC}"
    echo -e "${YELLOW}  1. Исправьте конфликты в файлах${NC}"
    echo -e "${YELLOW}  2. Выполните: git add <файлы>${NC}"
    echo -e "${YELLOW}  3. Выполните: git commit${NC}"
    exit 1
fi

# Показываем статус
echo -e "${GREEN}=== Статус после синхронизации ===${NC}"
git status --short

echo -e "${GREEN}=== Готово! ===${NC}"
echo -e "${YELLOW}Для отправки в Railway выполните:${NC}"
echo -e "${YELLOW}  git push origin production${NC}"

