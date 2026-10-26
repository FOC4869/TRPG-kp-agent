#!/usr/bin/env python3
"""Explicit, backed-up correction of missing template equipment; stop web first.

Without --apply this only lists proposed changes. Existing entries (including
zero-quantity consumed/dropped items) are never refilled. No model or dice.
"""
import argparse
import copy
from datetime import datetime
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.services.catalogue import Catalogue
from kp_agent.game_tools import JsonStore
from kp_agent.owned_tools import Content, template_inventory, projection


def prepare_update(game,catalogue):
    """Return an updated copy plus newly added IDs; never mutate input."""
    updated=copy.deepcopy(game)
    module=game['creation']['moduleId'];person=game['creation']['investigatorId']
    _,raw=catalogue.character(module,person)
    inventory=updated['campaignState']['inventory'];known=set(game.get('templateEquipmentIds',[]))
    added=[]
    for key,item in template_inventory(raw).items():
        if key not in inventory and key not in known:
            inventory[key]=item;added.append(key)
    detail=catalogue.investigator(module,person).model_dump()
    updated['investigator']['equipment']=copy.deepcopy(detail['equipment'])
    updated['initialInvestigator']['equipment']=copy.deepcopy(detail['equipment'])
    updated['templateEquipmentIds']=sorted(known | set(template_inventory(raw)))
    return updated,added


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--saves',required=True,type=Path)
    p.add_argument('--investigator',required=True)
    p.add_argument('--apply',action='store_true')
    args=p.parse_args();catalogue=Catalogue();content=Content(catalogue);store=JsonStore(args.saves)
    backup=args.saves/('equipment-backups-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    try:
        for path in sorted(args.saves.glob('*/game.json')):
            game=store.load(path.parent.name)
            if game.get('keeperWorkflow')!='agent-rag-v3' or game['creation']['investigatorId']!=args.investigator:continue
            content.validate(game)
            if any(t['stage']!='completed' for t in game['turns']):
                print(game['gameId'],'skipped: unfinished turn');continue
            updated,added=prepare_update(game,catalogue)
            if not added:
                print(game['gameId'],'unchanged');continue
            print(game['gameId'],'add',','.join(added),'apply' if args.apply else 'dry-run')
            if args.apply:
                backup.mkdir(exist_ok=True)
                shutil.copyfile(path,backup/(game['gameId']+'.json'))
                updated['version']+=1
                updated.setdefault('equipmentCorrections',[]).append({'addedIds':added,'reason':'original character card equipment omitted from earlier import'})
                content.validate(updated);store.save(updated)
    finally:store.close()


if __name__=='__main__':main()
