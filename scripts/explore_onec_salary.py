"""
Скрипт разведки структуры проводок по зарплате в 1С:Бухгалтерия.
Проверяет доступные сущности для получения данных по счету 70 (зарплата).
"""
import asyncio
import httpx
import base64
import json
from pathlib import Path
import sys

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config_loader import get_onec_config


async def explore_salary_structure():
    """Разведка структуры данных по зарплате в 1С."""
    try:
        config = get_onec_config()
        if not config:
            print("❌ Конфигурация 1С не найдена. Настройте подключение через /api/integrations/onec/config")
            return
        
        base_url = config.odata_base_url
        username = config.username
        password = config.password
        
        # Подготовка Basic Auth
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        print("=" * 80)
        print("РАЗВЕДКА СТРУКТУРЫ ДАННЫХ ПО ЗАРПЛАТЕ В 1С:БУХГАЛТЕРИЯ")
        print("=" * 80)
        print(f"URL: {base_url}")
        print()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Проверить справочник сотрудников
            print("1. Проверка справочника сотрудников (Catalog_ФизическиеЛица)...")
            print("-" * 80)
            try:
                response = await client.get(
                    f"{base_url}/Catalog_ФизическиеЛица",
                    headers=headers,
                    params={"$top": 5, "$select": "Ref_Key,Description"}
                )
                if response.status_code == 200:
                    data = response.json()
                    employees = data.get("value", [])
                    print(f"✅ Найдено сотрудников: {len(employees)}")
                    for emp in employees[:3]:
                        print(f"   - {emp.get('Description', 'N/A')} (GUID: {emp.get('Ref_Key', 'N/A')[:36]}...)")
                else:
                    print(f"❌ Ошибка: {response.status_code}")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
            print()
            
            # 2. Проверить документы операций (Document_ОперацияБух)
            print("2. Проверка документов операций (Document_ОперацияБух)...")
            print("-" * 80)
            try:
                response = await client.get(
                    f"{base_url}/Document_ОперацияБух",
                    headers=headers,
                    params={"$top": 1, "$orderby": "Date desc"}
                )
                if response.status_code == 200:
                    data = response.json()
                    operations = data.get("value", [])
                    print(f"✅ Найдено документов: {len(operations)}")
                    if operations:
                        op = operations[0]
                        print(f"   Структура документа:")
                        print(f"   - Date: {op.get('Date', 'N/A')}")
                        print(f"   - Number: {op.get('Number', 'N/A')}")
                        print(f"   - Posted: {op.get('Posted', 'N/A')}")
                        print(f"   - Содержание: {op.get('Содержание', 'N/A')}")
                        # Показываем первые 20 ключей для понимания структуры
                        print(f"   Доступные поля (первые 20):")
                        for i, key in enumerate(list(op.keys())[:20]):
                            print(f"     - {key}")
                else:
                    print(f"❌ Ошибка: {response.status_code} - {response.text[:200]}")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
            print()
            
            # 3. Проверить альтернативные варианты
            print("3. Проверка альтернативных сущностей...")
            print("-" * 80)
            
            alternative_entities = [
                "Document_Операция",
                "InformationRegister_ХозрасчетныйОстатки",
                "AccumulationRegister_ВзаиморасчетыСРаботникамиОрганизаций",
            ]
            
            for entity_name in alternative_entities:
                try:
                    response = await client.get(
                        f"{base_url}/{entity_name}",
                        headers=headers,
                        params={"$top": 1}
                    )
                    if response.status_code == 200:
                        print(f"✅ {entity_name} - доступен")
                    else:
                        print(f"❌ {entity_name} - недоступен ({response.status_code})")
                except Exception as e:
                    print(f"❌ {entity_name} - ошибка: {str(e)[:100]}")
            print()
            
            # 4. Попробовать получить метаданные
            print("4. Получение метаданных OData...")
            print("-" * 80)
            try:
                response = await client.get(
                    f"{base_url}/$metadata",
                    headers=headers
                )
                if response.status_code == 200:
                    print(f"✅ Метаданные получены (размер: {len(response.text)} байт)")
                    print("   Примечание: Метаданные в XML формате, для анализа потребуется парсинг")
                else:
                    print(f"❌ Ошибка получения метаданных: {response.status_code}")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
            print()
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(explore_salary_structure())
