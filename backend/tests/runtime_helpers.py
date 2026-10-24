"""Pin historical route regressions without changing production defaults."""
import json
from pathlib import Path
import shutil
from app.services.catalogue import Catalogue, DATA_ROOT


class HistoricalCatalogue(Catalogue):
    def __init__(self, root):
        super().__init__()
        self.runtime_root = Path(root) / 'historical-runtime'
        if not self.runtime_root.exists():
            shutil.copytree(DATA_ROOT / 'runtime', self.runtime_root)
            index = json.loads((self.runtime_root / 'index.json').read_text())
            for entry in index['profiles']:
                if entry['moduleId'] == 'darkness-beneath-the-hill':
                    entry['current'] = 'darkness-solo-mvp-v2.json'
                    entry['retained'] = []
            (self.runtime_root / 'index.json').write_text(json.dumps(index))

    def subroot(self, name):
        return self.runtime_root if name == 'runtime' else super().subroot(name)
