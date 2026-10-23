# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Read-only content contract checks, not an event executor."""
from pathlib import Path
import collections
import hashlib
import yaml
r=Path(__file__).resolve().parent.parent
def read(n):return yaml.safe_load((r/n).read_text())
d=read('rulings.yaml')['decisions'];issues=read('issues.yaml')['issues'];loc=read('locations.yaml');events=read('events.yaml')['events'];characters=read('characters.yaml')['characters']
assert set(d)==set(issues) and len(d)==16
assert all(x['status']=='resolved' and x['resolution']['decision']==id for id,x in issues.items())
for table in [events,characters,read("clues.yaml")["clues"]]:
 for x in table.values():
  if 'adjudication' in x:assert x['adjudication'] in d
assert characters['ssyaa_hrisss']['stats']['HP']==(characters['ssyaa_hrisss']['attributes']['CON']+characters['ssyaa_hrisss']['attributes']['SIZ'])//10==11
assert characters['ssyaa_hrisss']['printed_hp']==20
assert characters['ghast']['sanity']=={'success':'0','failure':'1D8'}
assert read('endings.yaml')['rewards']['abandon_josh']['printed']=='-1D6+1'
assert read('endings.yaml')['rewards']['abandon_josh']['san_loss']=='1D6+1'
assert d['insufficient_portal_resources']['failed_payment'].startswith('先验证全部')
assert d['unavailable_ghast']['spawn_new'] is False
assert set(d['unavailable_ghast']['eligible'])==set(read('characters.yaml')['instances'])
assert d['toxic_gas_sequence']['breath_hold_exempt_rounds']==[1] and d['toxic_gas_sequence']['con_per_round']==1
assert d['cliff_reaction_order']['push_limit']==1
ids=loc['locations'];conns=loc['connections'];g=collections.defaultdict(set)
for edge in conns:
 assert edge['from_location'] in ids and edge['to_location'] in ids
 if 'traversal' in edge:assert edge['traversal']['automatic_walk'] is False
 g[edge['from_location']].add(edge['to_location'])
 if edge['bidirectional']:g[edge['to_location']].add(edge['from_location'])
def reach(start,removed=None):
 seen={start};todo=[start]
 while todo:
  for target in g[todo.pop()]:
   if target!=removed and target not in seen:seen.add(target);todo.append(target)
 return seen
reachable=reach('winscott_house')
expected=set(ids)-{'john_hay_library','providence_athenaeum','underground_complex'}
assert expected<=reachable,expected-reachable
assert 'fungus_area' not in reach('winscott_house','cliff_lower'),'Do not bypass vertical gate'
assert 'portal_exit_cavern' not in reach('winscott_house','portal_area')
assert 'portal_exit_cavern' not in g['serpent_lair']
assert 'cliff_lower' not in g['cliff_upper'] or next(e for e in conns if e['from_location']=='cliff_upper' and e['to_location']=='cliff_lower')['traversal']['height_feet']==20
assert ids['cage_area']['parent']=='serpent_lair'

assert read("manifest.yaml")["runtime_compatible"] is False


m=read("manifest.yaml")
assert m["files"]["rulings"]=="rulings.yaml"
assert m["rules"]["profile_sha256"]==hashlib.sha256((r/"rulings.yaml").read_bytes()).hexdigest(),"Rulings changed without updating content digest"

print("PASS: 16 decisions, adopted values, references, graph gates and profile digest")
