"""Read-only validation of explicitly published runtime profiles; no model or saves."""
from app.services.catalogue import Catalogue
from .content import Content


def main():
    catalogue = Catalogue()
    content = Content(catalogue)
    for publication in catalogue.publications():
        if publication.runtimeProfile:
            module = content.for_module(publication.id)
            print(f"OK {publication.id}: {module.profile['id']} {module.profile['version']}")
            _, entry = content.registration(publication.id)
            versions = [module] + [content.load(publication, entry, r['source']) for r in entry.get('retained', [])]
            for migration in entry.get('compatible', []):
                target = next((v for v in versions if v.fingerprint == migration['targetHash']), None)
                if target is None or not target.compatible: raise ValueError('Invalid migration target/source')
            for retained in versions[1:]:
                print(f"OK retained {publication.id}: {retained.profile['version']}")


if __name__ == '__main__': main()
