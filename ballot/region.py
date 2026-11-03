import json,re
out={}
for f in ['STS20','STR70','STR71']:
  d=json.load(open(f'fl/fl_{f}.json',encoding='utf-8'))
  agg={}
  for r in d['rows']:
    if r['Typ']=='INT': continue
    c=r['Candidate/Committee'].split('(')[0].strip()
    a=float(r['Amount'] or 0); z=re.findall(r'\d{5}',r['City State Zip']); z=z[-1] if z else ''
    t=agg.setdefault(c,[0,0,0]); t[0]+=a
    if z[:3]=='342': t[1]+=a
    if z[:3] in ('335','336'): t[2]+=a
  for c,(t,m,h) in agg.items():
    print(f,c,round(t),'342xx',round(100*m/t,1),'hills',round(100*h/t,1),'region',round(100*(m+h)/t,1)); out[c]=round(100*(m+h)/t,1)
json.dump(out,open('region_share.json','w'))
