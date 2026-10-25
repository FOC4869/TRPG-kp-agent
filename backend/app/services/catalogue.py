"""Read-only, explicitly published projections. No agent, rules or game state."""

import json
import re
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

DATA_ROOT = Path(__file__).resolve().parents[2] / 'data'
Identifier = Annotated[str, Field(pattern=r'^[a-z0-9]+(?:[-_][a-z0-9]+)*$')]
Number = Annotated[int, Field(ge=0)]


class CatalogueUnavailable(Exception):
    """Invalid local content, intentionally without client-visible diagnostics."""


class CatalogueNotFound(Exception):
    pass


class DTO(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class PublicModule(DTO):
    runtimeProfile: str | None = None
    id: Identifier
    caseNumber: str
    title: str
    englishTitle: str | None = None
    status: Literal['preview', 'coming-soon']
    cover: str
    introduction: list[str]
    era: str
    location: str
    playStyle: str
    originalPlayers: str
    contentNote: str | None = None


class Publication(DTO):
    runtimeProfile: str | None = None
    id: Identifier
    directory: Identifier
    manifestId: Identifier
    caseNumber: str
    status: Literal['preview', 'coming-soon']
    coverAsset: Identifier
    introduction: list[str]
    era: str
    location: str
    playStyle: str
    originalPlayers: str
    contentNote: str | None = None
    investigatorIds: list[Identifier]


class Registry(DTO):
    modules: list[Publication]


class ModulePage(DTO):
    items: list[PublicModule]
    page: int
    pageSize: int
    total: int


class Portrait(DTO):
    url: str


class InvestigatorSummary(DTO):
    id: Identifier
    name: str
    displayName: str
    occupation: str
    age: Number | None
    portrait: Portrait


class ModuleReference(DTO):
    id: str
    title: str


class InvestigatorCatalogue(DTO):
    module: ModuleReference
    items: list[InvestigatorSummary]


class Resources(DTO):
    hp: Number | None
    hpMax: Number | None
    san: Number | None
    mp: Number | None
    mpMax: Number | None
    luck: Number | None


class Skill(DTO):
    name: str
    value: Number | None
    highlighted: bool


class Background(DTO):
    title: str
    text: str | None


class Equipment(DTO):
    name: str
    quantity: Number | None
    kind: Literal['carried', 'owned']
    note: str


class Cash(DTO):
    amount: Annotated[int | float, Field(ge=0)]
    currency: str


class InvestigatorDetail(InvestigatorSummary):
    overview: str
    resources: Resources
    attributes: dict[Literal['STR', 'CON', 'SIZ', 'DEX', 'APP', 'INT', 'POW', 'EDU'], Number | None]
    skills: list[Skill]
    background: list[Background]
    equipment: list[Equipment]
    cash: Cash | None


def safe_file(root: Path, relative: str) -> Path:
    """Reject absolute, parent and symlink escapes, even for local configuration."""
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise CatalogueUnavailable()
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise CatalogueUnavailable()
    return resolved


def read_text(root: Path, relative: str) -> str:
    path = safe_file(root, relative)
    if path.stat().st_size > 1_000_000:
        raise CatalogueUnavailable()
    return path.read_text(encoding='utf-8')


def background_sections(text: str) -> list[Background]:
    # React renders these strings as text. Anchors are structure, never HTML output.
    text = re.sub(r'<a\s+id="[^"]+"></a>\s*', '', text)
    parts = re.split(r'^## (.+)\n', text, flags=re.MULTILINE)
    blank = {'（原卡留空，供玩家填写。）', '（原卡未提供此栏目内容，供玩家填写。）'}
    return [Background(title=parts[i].strip(), text=None if parts[i + 1].strip() in blank else parts[i + 1].strip() or None)
            for i in range(1, len(parts), 2)]


def equipment_items(items: list, container: str = '', owned: bool = False, depth: int = 0) -> list[Equipment]:
    if depth > 8:
        raise CatalogueUnavailable()
    result = []
    for item in items:
        kind = 'owned' if owned or item.get('placement') == 'owned_asset' else 'carried'
        notes = [f'收纳于：{container}'] if container else []
        if item.get('unit'):
            notes.append(f'单位：{item["unit"]}')
        for key, label in [('contents_unspecified', '内容未提供'), ('details_unspecified', '细节未提供')]:
            if item.get(key):
                notes.append(label)
        for key, label in [('length', '长度'), ('ammunition', '弹药'), ('combat_profile', '武器参数')]:
            if key in item:
                value = item[key]
                if value is None:
                    notes.append(f'{label}未提供')
                elif key == 'length':
                    notes.append(f'长度：{value["value"]} {value["unit"]}')
        if item.get('licensed') is False:
            notes.append('无持枪许可')
        for effect in item.get('special_effects', []):
            notes.append(f'{effect["description"]}（仅原卡描述，特例尚未实现）')
        result.append(Equipment(name=item['name'], quantity=item.get('quantity'), kind=kind, note='；'.join(notes)))
        result.extend(equipment_items(item.get('contents', []), f'{container} / {item["name"]}' if container else item['name'], kind == 'owned', depth + 1))
    return result


class Catalogue:
    def __init__(self, root: Path = DATA_ROOT):
        self.root = root

    def subroot(self, directory: str) -> Path:
        root = (self.root / directory).resolve()
        if not root.is_relative_to(self.root.resolve()):
            raise CatalogueUnavailable()
        return root

    def publications(self) -> list[Publication]:
        data = Registry.model_validate(json.loads(read_text(self.root, 'module-catalogue.json')))
        ids = [item.id for item in data.modules]
        if len(ids) != len(set(ids)) or any(len(p.investigatorIds) != len(set(p.investigatorIds)) for p in data.modules):
            raise CatalogueUnavailable()
        return data.modules

    def publication(self, module_id: str) -> Publication:
        for item in self.publications():
            if item.id == module_id:
                return item
        raise CatalogueNotFound()

    def module(self, module_id: str) -> PublicModule:
        p = self.publication(module_id)
        manifest = yaml.safe_load(read_text(self.subroot('modules'), f'{p.directory}/manifest.yaml'))
        if manifest['id'] != p.manifestId:
            raise CatalogueUnavailable()
        self.cover(module_id)
        return PublicModule(id=p.id, caseNumber=p.caseNumber, title=manifest['title'], englishTitle=manifest.get('original_title'),
                            runtimeProfile=p.runtimeProfile, status=p.status, cover=f'/api/modules/{p.id}/cover', introduction=p.introduction,
                            era=p.era, location=p.location, playStyle=p.playStyle, originalPlayers=p.originalPlayers, contentNote=p.contentNote)

    def modules(self, page: int, page_size: int) -> ModulePage:
        entries = self.publications()
        total = len(entries)
        current = min(page, max(1, (total + page_size - 1) // page_size))
        selected = entries[(current - 1) * page_size:current * page_size]
        return ModulePage(items=[self.module(p.id) for p in selected], page=current, pageSize=page_size, total=total)

    def cover(self, module_id: str) -> Path:
        p = self.publication(module_id)
        manifest_path = safe_file(self.subroot('modules'), f'{p.directory}/manifest.yaml')
        root = manifest_path.parent
        manifest = yaml.safe_load(read_text(root, manifest_path.name))
        if manifest['id'] != p.manifestId or manifest['presentation']['cover'] != p.coverAsset:
            raise CatalogueUnavailable()
        index = yaml.safe_load(read_text(root, manifest['files']['assets']))
        asset = index['assets'][p.coverAsset]
        cover_formats = {'.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml'}
        suffix = Path(asset['file']).suffix.lower()
        if (index['path_base'] != 'assets/' or asset['kind'] != 'module_cover'
                or cover_formats.get(suffix) != asset['media_type']):
            raise CatalogueUnavailable()
        return safe_file(root, f'assets/{asset["file"]}')

    def character(self, module_id: str, investigator_id: str) -> tuple[Path, dict]:
        p = self.publication(module_id)
        if p.status != 'preview' or investigator_id not in p.investigatorIds:
            raise CatalogueNotFound()
        # Verify the id directory itself remains inside characters, including symlinks.
        path = safe_file(self.subroot('characters'), f'{investigator_id}/character.yaml')
        root = path.parent
        raw = yaml.safe_load(read_text(root, path.name))
        if raw['id'] != investigator_id or raw['schema_version'] != '1.0':
            raise CatalogueUnavailable()
        return root, raw

    def portrait(self, module_id: str, investigator_id: str) -> Path:
        root, raw = self.character(module_id, investigator_id)
        portrait = raw['assets']['portrait']
        portrait_formats = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml'}
        if portrait_formats.get(Path(portrait['file']).suffix.lower()) != portrait['media_type']:
            raise CatalogueUnavailable()
        return safe_file(root, portrait['file'])

    def summary(self, module_id: str, investigator_id: str) -> InvestigatorSummary:
        _, raw = self.character(module_id, investigator_id)
        self.portrait(module_id, investigator_id)
        return InvestigatorSummary(id=raw['id'], name=raw['name'], displayName=raw.get('aliases', [raw['name']])[0],
                                   occupation=raw['occupation'], age=raw.get('age'),
                                   portrait=Portrait(url=f'/api/modules/{module_id}/investigators/{investigator_id}/portrait'))

    def investigators(self, module_id: str) -> InvestigatorCatalogue:
        module = self.module(module_id)
        if module.status != 'preview':
            raise CatalogueNotFound()
        return InvestigatorCatalogue(module=ModuleReference(id=module.id, title=module.title),
                                     items=[self.summary(module_id, i) for i in self.publication(module_id).investigatorIds])

    def investigator(self, module_id: str, investigator_id: str) -> InvestigatorDetail:
        self.module(module_id)
        root, raw = self.character(module_id, investigator_id)
        sections = background_sections(read_text(root, raw['background']))
        overview = next((s.text for s in sections if s.title == '特质' and s.text), '暂无人物概览。')
        initial, derived = raw['initial_resources'], raw['authored_derived']
        skills = raw['skills']
        top = sorted(skills, key=lambda k: skills[k] if skills[k] is not None else -1, reverse=True)[:4]
        return InvestigatorDetail(**self.summary(module_id, investigator_id).model_dump(), overview=overview,
                                  resources=Resources(hp=initial.get('hp'), hpMax=derived.get('hp_max'), san=initial.get('san'),
                                                      mp=initial.get('mp'), mpMax=derived.get('mp_max'), luck=initial.get('luck')),
                                  attributes={key: raw['attributes'].get(key) for key in ('STR', 'CON', 'SIZ', 'DEX', 'APP', 'INT', 'POW', 'EDU')},
                                  skills=[Skill(name=k, value=v, highlighted=k in top) for k, v in skills.items()],
                                  background=sections, equipment=equipment_items(raw.get('starting_equipment', [])),
                                  cash=Cash.model_validate(raw['starting_money']) if raw.get('starting_money') else None)
