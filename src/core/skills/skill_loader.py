"""
SkillLoader - загрузка и парсинг SKILL.md файлов.

Поддерживает формат Anthropic Skills:
- YAML frontmatter для metadata
- Markdown контент для инструкций
"""
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import yaml
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Skill:
    """
    Represents a loaded Skill from SKILL.md.
    """
    name: str
    description: str
    content: str  # Markdown content after frontmatter
    metadata: Dict[str, any] = field(default_factory=dict)
    skill_dir: Optional[Path] = None  # Directory where skill is located
    
    def get_instructions(self) -> str:
        """
        Получить полные инструкции skill (description + content).
        
        Returns:
            Полный текст инструкций
        """
        return f"{self.description}\n\n{self.content}"


class SkillLoader:
    """
    Загрузчик для SKILL.md файлов.
    
    Поддерживает формат Anthropic Skills с YAML frontmatter.
    """
    
    # Pattern для разделения YAML frontmatter и markdown контента
    FRONTMATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n(.*)$',
        re.DOTALL | re.MULTILINE
    )
    
    def __init__(self, skills_dir: Optional[Path] = None):
        """
        Инициализация SkillLoader.
        
        Args:
            skills_dir: Директория с skills (по умолчанию: skills/ в корне проекта)
        """
        if skills_dir is None:
            # Default: skills/ в корне проекта
            project_root = Path(__file__).parent.parent.parent.parent
            skills_dir = project_root / "skills"
        
        self.skills_dir = Path(skills_dir)
        logger.info(f"[SkillLoader] Initialized with skills_dir: {self.skills_dir}")
    
    def load_skill(self, skill_name: str) -> Skill:
        """
        Загрузить skill по имени.
        
        Args:
            skill_name: Имя skill (название директории)
            
        Returns:
            Загруженный Skill объект
            
        Raises:
            FileNotFoundError: Если skill не найден
            ValueError: Если SKILL.md невалиден
        """
        skill_dir = self.skills_dir / skill_name
        
        if not skill_dir.exists():
            raise FileNotFoundError(f"Skill directory not found: {skill_dir}")
        
        skill_md_path = skill_dir / "SKILL.md"
        
        if not skill_md_path.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")
        
        return self._parse_skill_file(skill_md_path, skill_dir)
    
    def load_all_skills(self) -> List[Skill]:
        """
        Загрузить все skills из skills_dir.
        
        Returns:
            Список всех загруженных skills
        """
        if not self.skills_dir.exists():
            logger.warning(f"[SkillLoader] Skills directory does not exist: {self.skills_dir}")
            return []
        
        skills = []
        
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md_path = skill_dir / "SKILL.md"
            
            if not skill_md_path.exists():
                logger.warning(f"[SkillLoader] Skipping {skill_dir.name}: SKILL.md not found")
                continue
            
            try:
                skill = self._parse_skill_file(skill_md_path, skill_dir)
                skills.append(skill)
            except Exception as e:
                logger.error(f"[SkillLoader] Failed to load skill {skill_dir.name}: {e}")
                continue
        
        logger.info(f"[SkillLoader] Loaded {len(skills)} skills")
        return skills
    
    def _parse_skill_file(self, skill_md_path: Path, skill_dir: Path) -> Skill:
        """
        Парсить SKILL.md файл.
        
        Args:
            skill_md_path: Путь к SKILL.md
            skill_dir: Директория skill
            
        Returns:
            Parsed Skill объект
            
        Raises:
            ValueError: Если файл невалиден
        """
        content = skill_md_path.read_text(encoding="utf-8")
        
        # Проверяем наличие frontmatter
        match = self.FRONTMATTER_PATTERN.match(content)
        
        if not match:
            raise ValueError(
                f"Invalid SKILL.md format in {skill_md_path}: "
                "missing YAML frontmatter (--- ... ---)"
            )
        
        yaml_str = match.group(1)
        markdown_content = match.group(2).strip()
        
        # Парсим YAML
        try:
            frontmatter = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            raise ValueError(
                f"Invalid YAML frontmatter in {skill_md_path}: {e}"
            )
        
        if not frontmatter:
            raise ValueError(f"Empty YAML frontmatter in {skill_md_path}")
        
        # Извлекаем обязательные поля
        name = frontmatter.get("name")
        if not name:
            raise ValueError(f"Missing 'name' in frontmatter of {skill_md_path}")
        
        description = frontmatter.get("description", "")
        if isinstance(description, str):
            # Убираем лишние пробелы из многострочного описания
            description = description.strip()
        
        metadata = frontmatter.get("metadata", {})
        
        # Создаём Skill объект
        skill = Skill(
            name=name,
            description=description,
            content=markdown_content,
            metadata=metadata,
            skill_dir=skill_dir
        )
        
        logger.debug(f"[SkillLoader] Loaded skill: {skill.name}")
        return skill
