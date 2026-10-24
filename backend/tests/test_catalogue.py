"""Public API behaviour, real templates, and fail-closed file boundaries."""

import json
import shutil
import unittest

import yaml
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.api.modules import get_catalogue
from app.main import app
from app.services.catalogue import Catalogue, DATA_ROOT

MODULE = '/api/modules/darkness-beneath-the-hill'


class TestCatalogue(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_real_module_and_public_fields(self):
        page = self.client.get('/api/modules').json()
        self.assertEqual((page['total'], page['page'], page['pageSize']), (1, 1, 3))
        item = page['items'][0]
        self.assertEqual(item, self.client.get(MODULE).json())
        self.assertEqual(item['id'], 'darkness-beneath-the-hill')
        self.assertEqual(item['title'], '岭下暗影')
        self.assertEqual(set(item), {'runtimeProfile', 'id', 'caseNumber', 'title', 'englishTitle', 'status', 'cover', 'introduction', 'era', 'location', 'playStyle', 'originalPlayers', 'contentNote'})
        self.assertNotIn('斯西亚', json.dumps(item, ensure_ascii=False))
        cover = self.client.get(item['cover'])
        self.assertEqual(cover.status_code, 200)
        self.assertEqual(cover.headers['content-type'], 'image/webp')
        self.assertEqual(cover.content, (DATA_ROOT / 'modules/darkness-beneath-the-hill/assets/module-cover-v1.webp').read_bytes())

    def test_real_ten_investigators_and_portraits(self):
        response = self.client.get(MODULE + '/investigators')
        self.assertEqual(response.status_code, 200)
        catalogue = response.json()
        self.assertEqual(catalogue['module'], {'id': 'darkness-beneath-the-hill', 'title': '岭下暗影'})
        self.assertEqual(len(catalogue['items']), 10)
        for summary in catalogue['items']:
            detail = self.client.get(MODULE + '/investigators/' + summary['id'])
            self.assertEqual(detail.status_code, 200, detail.text)
            data = detail.json()
            self.assertEqual(summary, {key: data[key] for key in summary})
            self.assertEqual(set(data['attributes']), {'STR', 'CON', 'SIZ', 'DEX', 'APP', 'INT', 'POW', 'EDU'})
            self.assertNotIn('<a ', json.dumps(data))
            self.assertTrue(all(not key.startswith('source') for key in data))
            self.assertNotIn('attacks', data)
            self.assertNotIn('customization', data)
            portrait = self.client.get(summary['portrait']['url'])
            self.assertEqual(portrait.status_code, 200)
            self.assertEqual(portrait.headers['content-type'], 'image/png')
            self.assertEqual(portrait.content, (DATA_ROOT / 'characters' / summary['id'] / 'assets/portrait.png').read_bytes())
        chris = self.client.get(MODULE + '/investigators/chris').json()
        self.assertEqual(chris['resources'], dict(hp=10, hpMax=10, san=55, mp=11, mpMax=11, luck=60))
        self.assertEqual(chris['attributes']['EDU'], 90)
        self.assertIsNone(next(s for s in chris['background'] if s['title'] == '思想与信念')['text'])
        skills = {s['name']: s['value'] for s in chris['skills']}
        self.assertEqual(skills['科学（地质学）'], 80)
        geraldine = self.client.get(MODULE + '/investigators/geraldine').json()
        self.assertEqual(next(s['value'] for s in geraldine['skills'] if s['name'] == '历史'), 9)

    def test_nested_equipment_units_and_unknowns_are_preserved(self):
        david = self.client.get(MODULE + '/investigators/david').json()
        equipment = {item['name']: item for item in david['equipment']}
        self.assertIsNone(equipment['撬锁器']['quantity'])
        self.assertEqual(equipment['手铐']['quantity'], 2)
        self.assertIn('单位：双', equipment['手铐']['note'])
        self.assertIn('收纳于：魔术道具箱', equipment['手铐']['note'])
        self.assertIn('单位：小撮', equipment['闪光粉']['note'])
        self.assertIn('特例尚未实现', equipment['手铐万用钥匙']['note'])
        jessica = self.client.get(MODULE + '/investigators/jessica').json()
        self.assertTrue(any(item['kind'] == 'owned' for item in jessica['equipment']))

    def test_unknown_entries_and_private_assets_are_not_available(self):
        for path in ['/api/modules/missing', '/api/modules/missing/cover', '/api/modules/missing/investigators',
                     MODULE + '/investigators/missing', MODULE + '/investigators/missing/portrait',
                     MODULE + '/assets/story.md', '/data/characters/chris/character.yaml',
                     '/api/modules/darkness_beneath_the_hill', MODULE + '/investigators/%2E%2E%2Fchris/portrait']:
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_pagination_validation(self):
        for query in ['page=0', 'page=-1', 'page_size=0', 'page_size=31', 'page=abc']:
            self.assertEqual(self.client.get('/api/modules?' + query).status_code, 422)
        self.assertEqual(self.client.get('/api/modules?page=999').json()['page'], 1)


class TestCatalogueFailures(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'data'
        self.root.mkdir()
        shutil.copyfile(DATA_ROOT / 'module-catalogue.json', self.root / 'module-catalogue.json')
        self.registry = json.loads((self.root / 'module-catalogue.json').read_text())
        shutil.copytree(DATA_ROOT / 'characters', self.root / 'characters')
        package = self.root / 'modules/darkness-beneath-the-hill'
        package.mkdir(parents=True)
        shutil.copyfile(DATA_ROOT / 'modules/darkness-beneath-the-hill/manifest.yaml', package / 'manifest.yaml')
        (package / 'assets').mkdir()
        for name in ('index.yaml', 'module-cover-v1.webp'):
            shutil.copyfile(DATA_ROOT / 'modules/darkness-beneath-the-hill/assets' / name, package / 'assets' / name)
        app.dependency_overrides[get_catalogue] = lambda: Catalogue(self.root)
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def save_registry(self):
        (self.root / 'module-catalogue.json').write_text(json.dumps(self.registry))

    def assert_unavailable(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json(), {'detail': 'Catalogue temporarily unavailable'})
        self.assertNotIn(str(self.root), response.text)

    def test_empty_catalogue(self):
        self.registry['modules'] = []
        self.save_registry()
        self.assertEqual(self.client.get('/api/modules?page=50').json(), {'items': [], 'page': 1, 'pageSize': 3, 'total': 0})

    def test_seven_published_items_paginate_without_fake_rows(self):
        base = self.registry['modules'][0]
        self.registry['modules'] = [dict(base, id=f'published-{i}') for i in range(7)]
        self.save_registry()
        for page, count in [(1, 3), (2, 3), (3, 1), (99, 1)]:
            result = self.client.get(f'/api/modules?page={page}').json()
            self.assertEqual(result['total'], 7)
            self.assertEqual(len(result['items']), count)
            self.assertEqual(result['page'], min(page, 3))

    def test_unpublished_character_and_module(self):
        self.registry['modules'][0]['investigatorIds'] = ['chris']
        self.save_registry()
        self.assertEqual(len(self.client.get(MODULE + '/investigators').json()['items']), 1)
        self.assertEqual(self.client.get(MODULE + '/investigators/david').status_code, 404)
        self.registry['modules'] = []
        self.save_registry()
        self.assertEqual(self.client.get(MODULE + '/cover').status_code, 404)

    def test_bad_registry_and_duplicate_ids(self):
        self.registry['modules'].append(dict(self.registry['modules'][0]))
        self.save_registry()
        self.assert_unavailable('/api/modules')
        (self.root / 'module-catalogue.json').write_text('{broken')
        self.assert_unavailable('/api/modules')

    def test_path_traversal_and_symlink_cover(self):
        root = self.root / 'modules/darkness-beneath-the-hill'
        index_path = root / 'assets/index.yaml'
        index = yaml.safe_load(index_path.read_text())
        index['assets']['module_cover']['file'] = '../../module-catalogue.json'
        index_path.write_text(yaml.safe_dump(index))
        self.assert_unavailable(MODULE + '/cover')
        index['assets']['module_cover']['file'] = 'escape.webp'
        index_path.write_text(yaml.safe_dump(index))
        (root / 'assets/escape.webp').symlink_to(self.root / 'module-catalogue.json')
        self.assert_unavailable(MODULE + '/cover')

    def test_cover_must_match_published_asset_and_have_cover_kind(self):
        self.registry['modules'][0]['coverAsset'] = 'bg_winscott_house'
        self.save_registry()
        self.assert_unavailable(MODULE + '/cover')
        self.registry['modules'][0]['coverAsset'] = 'module_cover'
        self.save_registry()
        path = self.root / 'modules/darkness-beneath-the-hill/assets/index.yaml'
        index = yaml.safe_load(path.read_text())
        index['assets']['module_cover']['kind'] = 'scene_background'
        path.write_text(yaml.safe_dump(index))
        self.assert_unavailable(MODULE + '/cover')

    def test_invalid_yaml_and_manifest_id(self):
        manifest = self.root / 'modules/darkness-beneath-the-hill/manifest.yaml'
        manifest.write_text('!!python/object/apply:os.system [echo not-executed]')
        self.assert_unavailable(MODULE)
        manifest.write_text('id: different\ntitle: hidden')
        self.assert_unavailable(MODULE)

    def test_character_background_portrait_and_directory_escapes(self):
        character = self.root / 'characters/chris/character.yaml'
        original = character.read_text()
        character.write_text(original.replace('background: background.md', 'background: ../../module-catalogue.json'))
        self.assert_unavailable(MODULE + '/investigators/chris')
        character.write_text(original)
        portrait = self.root / 'characters/chris/assets/portrait.png'
        portrait.unlink()
        portrait.symlink_to(self.root / 'module-catalogue.json')
        self.assert_unavailable(MODULE + '/investigators/chris/portrait')
        shutil.rmtree(self.root / 'characters/chris')
        (self.root / 'characters/chris').symlink_to(DATA_ROOT / 'characters/chris', target_is_directory=True)
        self.assert_unavailable(MODULE + '/investigators/chris')

    def test_unknown_values_are_not_zero_or_invented(self):
        character = self.root / 'characters/chris/character.yaml'
        character.write_text(character.read_text().replace('age: 39', 'age: null').replace('  luck: 60', '  luck: null').replace('  科学（地质学）: 80', '  科学（地质学）: null'))
        result = self.client.get(MODULE + '/investigators/chris').json()
        self.assertIsNone(result['age'])
        self.assertIsNone(result['resources']['luck'])
        self.assertIsNone(next(s['value'] for s in result['skills'] if s['name'] == '科学（地质学）'))

    def test_root_symlinks_cannot_escape_data(self):
        shutil.rmtree(self.root / 'modules')
        (self.root / 'modules').symlink_to(DATA_ROOT / 'modules', target_is_directory=True)
        self.assert_unavailable(MODULE + '/cover')

    def test_live_file_updates_and_invalid_numbers(self):
        manifest = self.root / 'modules/darkness-beneath-the-hill/manifest.yaml'
        manifest.write_text(manifest.read_text().replace('title: 岭下暗影', 'title: 已更新标题'))
        self.assertEqual(self.client.get(MODULE).json()['title'], '已更新标题')
        character = self.root / 'characters/chris/character.yaml'
        character.write_text(character.read_text().replace('  hp: 10', '  hp: invalid'))
        self.assert_unavailable(MODULE + '/investigators/chris')

    def test_missing_files_and_empty_resource_shape_fail_closed(self):
        character = self.root / 'characters/chris/character.yaml'
        character.write_text(character.read_text().replace('initial_resources:', 'initial_resources: null\nunused_resources:'))
        self.assert_unavailable(MODULE + '/investigators/chris')
        character.unlink()
        self.assert_unavailable(MODULE + '/investigators/chris')
