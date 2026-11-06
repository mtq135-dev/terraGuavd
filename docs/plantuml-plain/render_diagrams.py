from pathlib import Path
import subprocess, shutil, re
from lxml import etree
from PIL import Image, ImageDraw, ImageFont

import argparse, tempfile
p=argparse.ArgumentParser()
p.add_argument('--jar',required=True)
p.add_argument('--java',default='java')
args=p.parse_args()
root=Path(__file__).resolve().parent
figs=root
work=tempfile.TemporaryDirectory(prefix='terraguavd_uml_')
tmp=Path(work.name)
jar=tmp/'plantuml.jar'
shutil.copyfile(Path(args.jar).resolve(),jar)
java=args.java
sources=[str(p.relative_to(root)) for p in sorted(figs.glob('*.puml')) if p.stem!='01-use-cases']
for args in [['-tsvg'],['-tpng','-Sdpi=180']]:
    subprocess.run([java,'-Djava.awt.headless=true','-jar',str(jar),'-charset','UTF-8',*args,'-nometadata',*sources],check=True,timeout=60,cwd=root)
for p in figs.glob('*.svg'):
    s=p.read_text(encoding='utf-8')
    assert 'Syntax Error' not in s and 'An error has occurred' not in s,p

# Preserve all 14 original goals and inherited shared associations in five views.
blocks=re.findall(r'@startuml.*?@enduml',(figs/'01-use-cases.puml').read_text(encoding='utf-8'),re.S)
assert len(blocks)==5
S='http://www.w3.org/2000/svg'
W,H=1220,1100;GAP=30
scale=2
fontroot=Path(r'C:\Windows\Fonts')
class Drawing:
    def __init__(self,w,h):
        self.w,self.h=w,h
        self.svg=etree.Element('{'+S+'}svg',nsmap={None:S},width=str(w),height=str(h),viewBox=f'0 0 {w} {h}')
        self.image=Image.new('RGB',(round(w*scale),round(h*scale)),'white');self.draw=ImageDraw.Draw(self.image)
        self.shape('rect',x=0,y=0,width=w,height=h,fill='white')
    def shape(self,tag,**a):return etree.SubElement(self.svg,'{'+S+'}'+tag,**{k:str(v) for k,v in a.items()})
    def rect(self,x,y,w,h,fill='#F6F8FA',stroke='#A6B2BE'):
        self.shape('rect',x=x,y=y,width=w,height=h,rx=5,fill=fill,stroke=stroke,**{'stroke-width':1.5})
        self.draw.rounded_rectangle(tuple(round(v*scale) for v in (x,y,x+w,y+h)),radius=10,fill=fill,outline=stroke,width=3)
    def line(self,x1,y1,x2,y2,color='#455361',dashed=False):
        a={'stroke-dasharray':'8 6'} if dashed else {}
        self.shape('line',x1=x1,y1=y1,x2=x2,y2=y2,stroke=color,**{'stroke-width':2,**a})
        if dashed:
            import math
            dist=math.hypot(x2-x1,y2-y1)
            for k in range(0,int(dist),14):
                lo=k/dist;hi=min(k+8,dist)/dist
                self.draw.line(tuple(round(v*scale) for v in (x1+(x2-x1)*lo,y1+(y2-y1)*lo,x1+(x2-x1)*hi,y1+(y2-y1)*hi)),fill=color,width=4)
        else:self.draw.line(tuple(round(v*scale) for v in (x1,y1,x2,y2)),fill=color,width=4)
    def ellipse(self,cx,cy,rx,ry):
        self.shape('ellipse',cx=cx,cy=cy,rx=rx,ry=ry,fill='white',stroke='#455361',**{'stroke-width':1.5})
        self.draw.ellipse(tuple(round(v*scale) for v in (cx-rx,cy-ry,cx+rx,cy+ry)),fill='white',outline='#455361',width=3)
    def text(self,x,y,label,size=28,bold=False,center=True):
        lines=label.replace('\\n','\n').splitlines()
        for j,t in enumerate(lines):
            baseline=y+(j-(len(lines)-1)/2)*(size+5)
            e=self.shape('text',x=x,y=baseline,fill='#182532',**{'font-family':'Arial','font-size':size,'font-weight':'bold' if bold else 'normal','text-anchor':'middle' if center else 'start'})
            e.text=t
            f=ImageFont.truetype(str(fontroot/('arialbd.ttf' if bold else 'arial.ttf')),round(size*scale))
            self.draw.text((round(x*scale),round(baseline*scale)),t,font=f,fill='#182532',anchor='ms' if center else 'ls')
    def paste(self,other,x,y):
        e=etree.SubElement(self.svg,'{'+S+'}svg',x=str(x),y=str(y),width=str(other.w),height=str(other.h),viewBox=f'0 0 {other.w} {other.h}')
        for child in other.svg:e.append(etree.fromstring(etree.tostring(child)))
        self.image.paste(other.image,(round(x*scale),round(y*scale)))
    def save(self,path):
        Path(str(path)+'.svg').write_bytes(etree.tostring(self.svg,xml_declaration=True,encoding='UTF-8'))
        self.image.save(str(path)+'.png',dpi=(180,180))
views=[];all_ids=set();actors=[]
for block in blocks:
    d=Drawing(W,H)
    role=re.search(r'actor "([^"]+)"',block).group(1);actors.append(role)
    group=re.search(r'rectangle "([^"]+)"',block).group(1)
    cases={cid:label for label,cid in re.findall(r'usecase "([^"]+)" as (\w+)',block)}
    all_ids.update(cases)
    ids=list(cases);specific=[i for i in ids if not i.startswith('C')];shared=[i for i in ids if i.startswith('C')]
    assert len(specific)==2
    d.rect(300,25,900,1030)
    d.text(750,70,group,30,True)
    d.text(750,118,'Role-specific goals',24,True)
    d.text(750,423,'Shared access within permissions',24,True)
    positions={specific[0]:185,specific[1]:325}
    positions.update(dict(zip(shared,[505,645,785,925])))
    d.ellipse(140,433,15,15);d.line(140,448,140,510);d.line(104,473,176,473)
    d.line(140,510,108,552);d.line(140,510,172,552);d.text(140,602,role,28,True)
    linked=[i for i in ids if i!='C3']
    d.line(176,473,260,473);d.line(260,min(positions[i] for i in linked),260,max(positions[i] for i in linked))
    for cid,label in cases.items():
        cy=positions[cid]
        if cid!='C3':d.line(260,cy,400,cy)
        d.ellipse(730,cy,330,54);d.text(730,cy+9,label,28)
    if 'C3' in cases:
        # Preserve the original report-permission extension to mission viewing.
        ya,yb=positions['C3'],positions['C2']
        for coords in [(1060,ya,1160,ya),(1160,ya,1160,yb),(1160,yb,1060,yb)]:d.line(*coords,dashed=True)
        d.line(1060,yb,1074,yb-7);d.line(1060,yb,1074,yb+7)
        d.text(1100,(ya+yb)/2-15,'«extend»\\n[report\\npermission]',20)
    scope='Assigned missions only' if role in ['Mission Operator','Field Personnel'] else 'Missions visible through effective permissions'
    d.text(750,1027,scope,22)
    views.append(d)
assert len(actors)==5 and len(set(actors))==5
assert all_ids=={'A1','A2','S1','S2','O1','O2','D1','D2','F1','F2','C1','C2','C3','C4'}
conditions=Drawing(W,H)
conditions.rect(25,25,W-50,1030)
conditions.text(60,90,'Access conditions',34,True,False)
paras=[
'Five role views describe the same TerraGuavd system.\\nRepeated shared cases represent the same functions.',
'Every operation is subject to backend permissions\\nand mission access. Account restrictions may remove\\npermissions within a role.',
'Mission Operators access assigned missions.\\nField Personnel access missions listing them.',
'Report access requires report permission.\\nField Personnel cannot export reports.',
'Field stop requests create alerts for the assigned\\noperator; they never command the aircraft directly.',
'Administrator and Supervisor roles do not grant\\nflight control.',
'Live 3D is read-only and requires an active mission\\nwith its matching vehicle reservation.',
'Synthetic potential targets are unverified.\\nSurveyed ground is not cleared or safe.'
]
y=160
for p in paras:
    lines=p.count('\\n')+1
    for j,line in enumerate(p.split('\\n')):conditions.text(60,y+j*34,line,28,False,False)
    y+=lines*34+37
presentation=figs/'presentation';presentation.mkdir(exist_ok=True)
parts=[]
for letter,pair in zip('abc',[(views[0],views[1]),(views[2],views[3]),(views[4],conditions)]):
    page=Drawing(W*2+GAP,H)
    page.paste(pair[0],0,0);page.paste(pair[1],W+GAP,0)
    page.save(presentation/f'01-use-cases-{letter}');parts.append(page)
combined=Drawing(W*2+GAP,H*3+GAP*2)
for i,page in enumerate(parts):combined.paste(page,0,i*(H+GAP))
combined.save(figs/'01-use-cases')

# Present the long lifecycle flow in two separately rendered continuation panels.
stem='05-activity-mission-lifecycle'
shutil.copyfile(figs/(stem+'.svg'),tmp/(stem+'-full.svg'))
shutil.copyfile(figs/(stem+'.png'),tmp/(stem+'-full.png'))
raw=(figs/(stem+'.puml')).read_text(encoding='utf-8')
split=raw.index('while (No terminal outcome?)')
head=raw[:raw.index('start\n')]
panels=[raw[:split]+'(A)\ndetach\n@enduml\n',head+'(A)\n'+raw[split:]]
panelpaths=[]
for i,panel in enumerate(panels):
    pp=tmp/f'lifecycle-panel-{i}.puml';pp.write_text(panel,encoding='utf-8');panelpaths.append(str(pp))
for args in [['-tsvg'],['-tpng','-Sdpi=180']]:
    subprocess.run([java,'-Djava.awt.headless=true','-jar',str(jar),'-charset','UTF-8',*args,'-nometadata',*panelpaths],check=True,timeout=60,cwd=root)
svgs=[etree.fromstring((tmp/f'lifecycle-panel-{i}.svg').read_bytes()) for i in range(2)]
sizes=[tuple(map(float,s.get('viewBox').split()[2:])) for s in svgs]
images=[Image.open(tmp/f'lifecycle-panel-{i}.png').convert('RGB') for i in range(2)]
scale=images[0].width/sizes[0][0]
w=max(v[0] for v in sizes)
header=65;gap=40;footer=30
panel_h=max(v[1] for v in sizes)
outw=2*w+gap;outh=header+panel_h+footer
canvas=Image.new('RGB',(round(outw*scale),round(outh*scale)),'white')
draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype(r'C:\Windows\Fonts\arialbd.ttf',round(23*scale))
for x,title in [(0,'A  Planning and startup'),(w+gap,'B  Execution and outcome')]:draw.text((round((x+15)*scale),round(12*scale)),title,font=font,fill='#172535')
for i,img in enumerate(images):canvas.paste(img,(round((i*(w+gap)+(w-sizes[i][0])/2)*scale),round(header*scale)))
draw.line((round((w+gap/2)*scale),0,round((w+gap/2)*scale),canvas.height),fill='#B0BBC6',width=2)
canvas.save(figs/(stem+'.png'),dpi=(180,180))
S='http://www.w3.org/2000/svg'
out=etree.Element('{'+S+'}svg',nsmap={None:S},width=str(outw),height=str(outh),viewBox=f'0 0 {outw} {outh}')
etree.SubElement(out,'{'+S+'}rect',width='100%',height='100%',fill='white')
for x,title in [(15,'A  Planning and startup'),(w+gap+15,'B  Execution and outcome')]:
    t=etree.SubElement(out,'{'+S+'}text',x=str(x),y='35',attrib={'font-family':'Arial','font-size':'23','font-weight':'bold','fill':'#172535'});t.text=title
for i,svg in enumerate(svgs):
    pw,ph=sizes[i]
    nested=etree.SubElement(out,'{'+S+'}svg',x=str(i*(w+gap)+(w-pw)/2),y=str(header),width=str(pw),height=str(ph),viewBox=f'0 0 {pw} {ph}',overflow='hidden')
    for child in svg:nested.append(etree.fromstring(etree.tostring(child)))
etree.SubElement(out,'{'+S+'}line',x1=str(w+gap/2),x2=str(w+gap/2),y1='0',y2=str(outh),stroke='#B0BBC6')
(figs/(stem+'.svg')).write_bytes(etree.tostring(out,xml_declaration=True,encoding='UTF-8'))
print('Rendered 8 SVGs and 8 PNGs; Figure 5 arranged as two consecutive panels.')
