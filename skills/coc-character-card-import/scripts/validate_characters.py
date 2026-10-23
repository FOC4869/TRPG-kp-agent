#!/usr/bin/env python3
"""Read-only validation of standalone CoC character directories (format 1.0)."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ID = re.compile(r'[a-z0-9][a-z0-9_-]*\Z')
DICE = re.compile(r'[+-]?(?:[1-9]\d*[dD][1-9]\d*|\d+)(?:[+-](?:[1-9]\d*[dD][1-9]\d*|\d+))*\Z')
SECTIONS = {'appearance', 'traits', 'beliefs', 'people', 'places', 'treasured', 'history'}


class Check:
    def __init__(self, directory, image_module):
        self.directory = directory
        self.Image = image_module
        self.errors = []
        self.warnings = []
        self.issue_fields = set()

    def error(self, field, message):
        self.errors.append(f'{field}: {message}')

    def text(self, value, field):
        if not isinstance(value, str) or not value.strip():
            self.error(field, 'expected a non-empty string')
            return False
        return True

    def obj(self, value, field):
        if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
            self.error(field, 'expected a mapping with string keys')
            return {}
        return value

    def seq(self, value, field):
        if not isinstance(value, list):
            self.error(field, 'expected a list')
            return []
        return value

    def unknown(self, field):
        if field not in self.issue_fields:
            self.error(field, 'unknown value needs a source_issues entry with this exact field')
        else:
            self.warnings.append(f'{field}: unknown; retained for review')

    def number(self, value, field, *, nullable=False, integer=True, negative=False):
        if value is None and nullable:
            self.unknown(field)
            return
        valid = type(value) is int if integer else type(value) in (int, float)
        if not valid or (not negative and value < 0):
            self.error(field, 'expected ' + ('integer' if integer else 'number') + ('' if negative else ' >= 0'))
        elif not integer:
            import math
            if not math.isfinite(value):
                self.error(field, 'expected a finite number')

    def identifier(self, value, field, seen=None):
        if not isinstance(value, str) or not ID.fullmatch(value):
            self.error(field, 'expected lowercase letters/digits, hyphens or underscores')
            return
        if seen is not None:
            if value in seen:
                self.error(field, f'duplicate id {value}')
            seen.add(value)

    def file(self, value, field):
        if not self.text(value, field):
            return None
        relative = Path(value)
        # Backslashes/drive paths are rejected consistently on Unix and Windows.
        if relative.is_absolute() or '..' in relative.parts or '\\' in value or ':' in value:
            self.error(field, 'expected an internal relative path')
            return None
        file = self.directory / relative
        components = [self.directory.joinpath(*relative.parts[:i]) for i in range(1, len(relative.parts)+1)]
        if self.directory.is_symlink() or any(p.is_symlink() for p in components):
            self.error(field, 'symbolic links are not supported')
            return None
        try:
            if not file.resolve().is_relative_to(self.directory.resolve()) or not file.is_file():
                raise ValueError('file missing or outside character directory')
        except (OSError, ValueError, RuntimeError) as exc:
            self.error(field, str(exc))
            return None
        return file

    def issues(self, value):
        seen = set()
        for i, raw in enumerate(self.seq(value, 'source_issues')):
            f = f'source_issues[{i}]'
            issue = self.obj(raw, f)
            self.identifier(issue.get('id'), f+'.id', seen)
            if self.text(issue.get('field'), f+'.field'):
                self.issue_fields.add(issue['field'])
            self.text(issue.get('note'), f+'.note')
            if issue.get('status') != 'needs_review':
                self.error(f+'.status', 'expected needs_review')
            if issue.get('source_text') is not None and not isinstance(issue['source_text'], str):
                self.error(f+'.source_text', 'expected string or null')
            self.warnings.append(f'{issue.get("field", "?")}: {issue.get("note", "needs review")}')

    def equipment(self, value, field='starting_equipment', seen=None):
        seen = set() if seen is None else seen
        for i, raw in enumerate(self.seq(value, field)):
            f = f'{field}[{i}]'
            item = self.obj(raw, f)
            self.identifier(item.get('id'), f+'.id', seen)
            self.text(item.get('name'), f+'.name')
            if 'quantity' not in item:
                self.error(f+'.quantity', 'required, use null if unknown')
            elif item['quantity'] is not None:
                if type(item['quantity']) is not int or item['quantity'] <= 0:
                    self.error(f+'.quantity', 'expected positive integer or null')
            for key in ('contents_unspecified', 'details_unspecified', 'licensed'):
                if key in item and not (key == 'licensed' and item[key] is None) and type(item[key]) is not bool:
                    self.error(f+'.'+key, 'expected boolean' + (' or null' if key == 'licensed' else ''))
            for key in ('unit', 'container'):
                if key in item:
                    self.text(item[key], f+'.'+key)
            if 'placement' in item and item['placement'] != 'owned_asset':
                self.error(f+'.placement', 'expected owned_asset')
            if item.get('ammunition') is not None:
                self.number(item['ammunition'], f+'.ammunition')
            if item.get('length') is not None:
                length = self.obj(item['length'], f+'.length')
                self.number(length.get('value'), f+'.length.value', integer=False)
                self.text(length.get('unit'), f+'.length.unit')
            if 'contents' in item:
                self.equipment(item['contents'], f+'.contents', seen)
            effect_ids = set()
            if 'special_effects' in item:
                for j, raw_effect in enumerate(self.seq(item['special_effects'], f+'.special_effects')):
                    ef = f'{f}.special_effects[{j}]'
                    effect = self.obj(raw_effect, ef)
                    self.identifier(effect.get('id'), ef+'.id', effect_ids)
                    self.text(effect.get('description'), ef+'.description')
                    if effect.get('status') != 'requires_runtime_implementation':
                        self.error(ef+'.status', 'expected requires_runtime_implementation')
                    if 'target' in effect:
                        self.text(effect['target'], ef+'.target')
                    if 'success_chance_percent' in effect:
                        chance = effect['success_chance_percent']
                        self.number(chance, ef+'.success_chance_percent', integer=False)
                        if type(chance) in (int, float) and chance > 100:
                            self.error(ef+'.success_chance_percent', 'must be <= 100')

    def validate(self, raw):
        d = self.obj(raw, 'character')
        required = {'schema_version', 'version', 'id', 'name', 'age', 'occupation', 'background', 'source', 'assets',
                    'attributes', 'initial_resources', 'authored_derived', 'skills', 'attacks', 'starting_equipment',
                    'starting_money', 'customization', 'source_issues'}
        for key in sorted(required - d.keys()):
            self.error(key, 'required field missing')
        self.issues(d.get('source_issues'))
        if d.get('schema_version') != '1.0':
            self.error('schema_version', 'expected string "1.0"')
        if not isinstance(d.get('version'), str) or not re.fullmatch(r'\d+\.\d+\.\d+', d['version']):
            self.error('version', 'expected string major.minor.patch')
        self.identifier(d.get('id'), 'id')
        if d.get('id') != self.directory.name:
            self.error('id', 'must match directory name')
        self.text(d.get('name'), 'name')
        self.number(d.get('age'), 'age', nullable=True)
        if d.get('occupation') is None:
            self.unknown('occupation')
        else:
            self.text(d['occupation'], 'occupation')
        if 'aliases' in d:
            for alias in self.seq(d['aliases'], 'aliases'):
                self.text(alias, 'aliases[]')
        source = self.obj(d.get('source'), 'source')
        self.text(source.get('description'), 'source.description')
        entries = [(source, 'source')]
        if 'pages' in source:
            pages = self.seq(source['pages'], 'source.pages')
            if not pages:
                self.error('source.pages', 'must not be empty')
            entries.extend((self.obj(page, 'source.pages[]'), 'source.pages[]') for page in pages)
        for entry, field in entries:
            if field != 'source':
                self.text(entry.get('label'), field+'.label')
            if 'image_number' in entry:
                self.number(entry['image_number'], field+'.image_number')
                if type(entry['image_number']) is int and entry['image_number'] == 0:
                    self.error(field+'.image_number', 'must be positive')
        for group, keys in [('attributes', {'STR','CON','SIZ','DEX','INT','APP','POW','EDU'}),
                            ('initial_resources', {'hp','san','mp','luck'}),
                            ('authored_derived', {'hp_max','mp_max','mov','build','db'})]:
            values = self.obj(d.get(group), group)
            for key in sorted(keys):
                if key not in values:
                    self.error(group+'.'+key, 'required key missing')
                elif key == 'db':
                    if values[key] is None:
                        self.unknown(group+'.db')
                    elif not isinstance(values[key], str) or not DICE.fullmatch(values[key]):
                        self.error(group+'.db', 'expected dice/integer expression string')
                else:
                    self.number(values[key], group+'.'+key, nullable=True, negative=key=='build')
        skills = self.obj(d.get('skills'), 'skills')
        for key, value in skills.items():
            self.text(key, 'skills key')
            self.number(value, 'skills.'+key)
        for resource in ('hp', 'mp'):
            value = self.obj(d.get('initial_resources'), 'initial_resources').get(resource)
            maximum = self.obj(d.get('authored_derived'), 'authored_derived').get(resource+'_max')
            if type(value) is int and type(maximum) is int and value > maximum:
                self.warnings.append(f'initial_resources.{resource}: exceeds authored maximum; check source, do not auto-correct')
        seen = set()
        for i, raw_attack in enumerate(self.seq(d.get('attacks'), 'attacks')):
            f = f'attacks[{i}]'
            attack = self.obj(raw_attack, f)
            self.identifier(attack.get('id'), f+'.id', seen)
            self.text(attack.get('label'), f+'.label')
            skill = attack.get('skill')
            if not isinstance(skill, str) or skill not in skills:
                self.error(f+'.skill', 'must reference a skills key')
            damage = self.obj(attack.get('damage'), f+'.damage')
            if damage.get('status') == 'needs_review':
                if damage.get('base', 'missing') is not None or damage.get('add_damage_bonus', 'missing') is not None:
                    self.error(f+'.damage', 'unresolved damage must have null base and add_damage_bonus')
                if 'source_expression' not in damage or (damage['source_expression'] is not None and not isinstance(damage['source_expression'], str)):
                    self.error(f+'.damage.source_expression', 'expected original string or null')
                if f'attacks.{attack.get("id")}.damage' not in self.issue_fields:
                    self.error(f+'.damage', 'needs matching source_issues field attacks.<id>.damage')
            else:
                if 'status' in damage:
                    self.error(f+'.damage.status', 'unsupported status')
                if not isinstance(damage.get('base'), str) or not DICE.fullmatch(damage['base']):
                    self.error(f+'.damage.base', 'expected dice/integer expression string')
                if type(damage.get('add_damage_bonus')) is not bool:
                    self.error(f+'.damage.add_damage_bonus', 'expected boolean')
        self.equipment(d.get('starting_equipment'))
        money = self.obj(d.get('starting_money'), 'starting_money')
        self.text(money.get('currency'), 'starting_money.currency')
        if money.get('currency') == 'unknown':
            self.unknown('starting_money.currency')
        self.number(money.get('amount'), 'starting_money.amount', integer=False, nullable=True)
        if d.get('background') != 'background.md':
            self.error('background', 'expected background.md')
        background = self.file(d.get('background'), 'background')
        body = background.read_text(encoding='utf-8') if background else ''
        anchors = re.findall(r'<a\s+id=[\"\x27]([^\"\x27]+)[\"\x27]\s*></a>', body)
        if len(anchors) != len(set(anchors)):
            self.error('background', 'duplicate anchors')
        for key in sorted(SECTIONS - set(anchors)):
            self.error('background', 'missing anchor '+key)
        if isinstance(d.get('name'), str) and not any(line.strip() == '# '+d['name'] for line in body.splitlines()):
            self.error('background', 'missing character name as H1')
        seen = set()
        for i, raw_custom in enumerate(self.seq(d.get('customization'), 'customization')):
            f = f'customization[{i}]'
            custom = self.obj(raw_custom, f)
            key = custom.get('section')
            if not isinstance(key, str) or key not in SECTIONS or key in seen:
                self.error(f+'.section', 'expected unique standard section key')
            else:
                seen.add(key)
            if custom.get('anchor') != key or custom.get('anchor') not in anchors:
                self.error(f+'.anchor', 'must match section and an existing background anchor')
            if custom.get('editable') is not True:
                self.error(f+'.editable', 'expected true')
        assets = self.obj(d.get('assets'), 'assets')
        for key, raw_asset in assets.items():
            self.identifier(key, 'assets key')
            asset = self.obj(raw_asset, 'assets.'+key)
            file = self.file(asset.get('file'), 'assets.'+key+'.file')
            self.text(asset.get('media_type'), 'assets.'+key+'.media_type')
            if key == 'portrait' and (asset.get('file') != 'assets/portrait.png' or asset.get('media_type') != 'image/png'):
                self.error('assets.portrait', 'expected assets/portrait.png and image/png')
            if file and isinstance(asset.get('media_type'), str) and asset['media_type'].startswith('image/'):
                try:
                    with self.Image.open(file) as image:
                        if key == 'portrait' and image.format != 'PNG':
                            self.error('assets.portrait', 'file is not a PNG')
                        image.verify()
                except (OSError, ValueError, self.Image.DecompressionBombError) as exc:
                    self.error('assets.'+key, f'image decode failed: {exc}')
        if 'portrait' not in assets:
            self.unknown('assets.portrait')
        return d.get('id')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path, help='One character directory or its parent root')
    args = parser.parse_args()
    try:
        import yaml
        from PIL import Image
    except ImportError:
        print('ERROR: Pillow and PyYAML are required; install in an isolated Python environment.', file=sys.stderr)
        return 2

    class UniqueLoader(yaml.SafeLoader):
        pass

    def unique_mapping(loader, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise yaml.constructor.ConstructorError(None, None, 'mapping keys must be strings', key_node.start_mark)
            if key in result:
                raise yaml.constructor.ConstructorError(None, None, f'duplicate YAML key: {key}', key_node.start_mark)
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

    def reject_cycles(value, active=None):
        if not isinstance(value, (dict, list)):
            return
        active = set() if active is None else active
        if id(value) in active:
            raise ValueError('cyclic YAML aliases are unsupported')
        active.add(id(value))
        for child in (value.values() if isinstance(value, dict) else value):
            reject_cycles(child, active)
        active.remove(id(value))

    root = args.path.absolute()
    if root.is_symlink() or not root.is_dir():
        print(f'ERROR: expected a real directory: {root}', file=sys.stderr)
        return 1
    directories = [root] if (root/'character.yaml').exists() or (root/'background.md').exists() else sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('.'))
    if not directories:
        print('ERROR: no character directories found', file=sys.stderr)
        return 1
    errors = warnings = 0
    seen = set()
    for directory in directories:
        check = Check(directory, Image)
        try:
            if directory.is_symlink() or (directory/'character.yaml').is_symlink():
                raise ValueError('symbolic-link character directories/files are unsupported')
            data = yaml.load((directory/'character.yaml').read_text(encoding='utf-8'), Loader=UniqueLoader)
            reject_cycles(data)
            ident = check.validate(data)
            if isinstance(ident, str):
                if ident in seen:
                    check.error('id', f'duplicate character ID: {ident}')
                seen.add(ident)
        except (OSError, UnicodeError, yaml.YAMLError, ValueError, RecursionError) as exc:
            check.error('character', str(exc))
        for kind, messages in [('ERROR', check.errors), ('WARN', check.warnings)]:
            for message in messages:
                print(f'{kind} {directory.name}: {message}')
        errors += len(check.errors)
        warnings += len(check.warnings)
    print(f'{len(directories)} character(s), {errors} error(s), {warnings} warning(s)')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
