"""Produce a plain white report while retaining the report's text, tables and figures."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from copy import deepcopy
from io import BytesIO
from lxml import etree as E
from PIL import Image
import json

base=Path(__file__).resolve().parent
source=base/'TerraGuavd_Project_Report_Refined_Cover_PlantUML_Light.docx'
dest=base/'TerraGuavd_Project_Report_Plain.docx'
with ZipFile(source) as z:parts={n:z.read(n) for n in z.namelist()}
N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','a':'http://schemas.openxmlformats.org/drawingml/2006/main','wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing','pic':'http://schemas.openxmlformats.org/drawingml/2006/picture'}
q=lambda tag:'{'+N['w']+'}'+tag
root=E.fromstring(parts['word/document.xml']);body=root.find(q('body'))
rels=E.fromstring(parts['word/_rels/document.xml.rels']);targets={e.get('Id'):'word/'+e.get('Target') for e in rels}
text=lambda x:''.join(x.xpath('.//w:t/text()',namespaces=N))
old_table_text=[text(t) for t in root.xpath('//w:tbl',namespaces=N)]
old_prose=[text(p) for p in body if p.tag==q('p') and text(p) and not p.xpath('.//w:fldSimple[contains(@w:instr,"PAGE")]',namespaces=N)]
bg=root.find(q('background'))
if bg is not None:root.remove(bg)

def para(value,size=24,bold=False,space=160):
 p=E.Element(q('p'));pr=E.SubElement(p,q('pPr'));E.SubElement(pr,q('jc'),{q('val'):'center'});E.SubElement(pr,q('spacing'),{q('after'):str(space)})
 run=E.SubElement(p,q('r'));rp=E.SubElement(run,q('rPr'));E.SubElement(rp,q('rFonts'),{q('ascii'):'Times New Roman',q('hAnsi'):'Times New Roman'})
 E.SubElement(rp,q('sz'),{q('val'):str(size)})
 if bold:E.SubElement(rp,q('b'))
 E.SubElement(run,q('t')).text=value
 return p

# Replace the full-page cover and chapter art with actual editable text.
chapter_names=['Introduction','Literature Review','System Analysis','System Design','Conclusion']
cover_anchor=None
for p in list(body):
 s=p.find('w:pPr/w:sectPr',N)
 if s is None:continue
 headers=[targets.get(h.get('{'+N['r']+'}id'),'') for h in s.findall(q('headerReference'))]
 approved=next((h for h in headers if 'headerTGApprovedPage' in h),None)
 if approved:
  number=int(approved.split('ApprovedPage')[1].split('.')[0])
  if number==0:cover_anchor=p
  else:
   title=para(f'Chapter {number}',36,True,240);pr=title.find(q('pPr'));pr.find(q('spacing')).set(q('before'),'3600')
   p.addprevious(title);p.addprevious(para(chapter_names[number-1],44,True,240))
 if p.find(q('pPr')) is not None and not text(p):
  spacing=p.find('w:pPr/w:spacing',N)
  if spacing is not None:spacing.set(q('line'),'1');spacing.set(q('lineRule'),'exact')
assert cover_anchor is not None
cover=[
 ('Kingdom of Saudi Arabia',24,False,70),('Ministry of Education',24,False,70),
 ('Prince Sattam Bin Abdulaziz University',26,True,70),
 ('College of Computer Engineering and Sciences',24,False,70),('Department of Software Engineering',24,False,700),
 ('TerraGuavd',44,True,260),('UAV-Based Landmine Detection System',36,True,320),
 ('Graduation Project Report',28,False,300),
 ('A UAV-based software platform for mission monitoring, sensor-data processing,',22,False,60),
 ('detection management, and field visualization.',22,False,500),
 ('Submitted by',24,True,160),
 ('Abdulmajeed Theeb Alqahtani — 445050242',24,False,100),
 ('Mnsour Mohammad Aldossari — 445050244',24,False,100),
 ('Osama Abdulmohsen bin Julayyil — 445050009',24,False,100),
 ('Omar Saeed Alghamdi — 444050891',24,False,320),
 ('Bachelor’s Degree in Software Engineering',24,False,300),
 ('Supervised by',24,True,100),('Dr. Mawal Ali Abdo Mohammad',26,False,300),('September 2026',24,False,100)]
for line,size,bold,space in cover:cover_anchor.addprevious(para(line,size,bold,space))

# A real footer replaces page-number fields mixed into body paragraphs.
for field in root.xpath('//w:fldSimple[contains(@w:instr,"PAGE") and not(contains(@w:instr,"PAGEREF"))]',namespaces=N):field.getparent().remove(field)
footer=E.Element(q('ftr'),nsmap={'w':N['w']});p=E.SubElement(footer,q('p'));pr=E.SubElement(p,q('pPr'));E.SubElement(pr,q('jc'),{q('val'):'center'});E.SubElement(pr,q('spacing'),{q('before'):'0',q('after'):'0',q('line'):'200',q('lineRule'):'exact'})
field=E.SubElement(p,q('fldSimple'),{q('instr'):' PAGE '});run=E.SubElement(field,q('r'));rp=E.SubElement(run,q('rPr'));E.SubElement(rp,q('sz'),{q('val'):'18'});E.SubElement(run,q('t')).text='1'
empty=E.Element(q('ftr'),nsmap={'w':N['w']});E.SubElement(empty,q('p'))
parts['word/footerPlain.xml']=E.tostring(footer,encoding='UTF-8',xml_declaration=True,standalone=True)
parts['word/footerPlainCover.xml']=E.tostring(empty,encoding='UTF-8',xml_declaration=True,standalone=True)
for rid,name in [('rIdPlainFooter','footerPlain.xml'),('rIdPlainCoverFooter','footerPlainCover.xml')]:E.SubElement(rels,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',Id=rid,Type=N['r']+'/footer',Target=name)
for i,s in enumerate(root.xpath('//w:sectPr',namespaces=N)):
 for e in s.findall(q('headerReference'))+s.findall(q('footerReference'))+s.findall(q('pgBorders'))+s.findall(q('titlePg')):s.remove(e)
 for kind in ['default','first','even']:s.insert(0,E.Element(q('footerReference'),{q('type'):kind,'{'+N['r']+'}id':'rIdPlainCoverFooter' if i==0 else 'rIdPlainFooter'}))
ct=E.fromstring(parts['[Content_Types].xml'])
for name in ['footerPlain.xml','footerPlainCover.xml']:E.SubElement(ct,'{http://schemas.openxmlformats.org/package/2006/content-types}Override',PartName='/word/'+name,ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml')

# Strip decorative frames from legacy grouped images while retaining every image.
for index,draw in enumerate(root.xpath('//w:body//w:drawing[.//a:blip]',namespaces=N)):
 blips=draw.xpath('.//a:blip',namespaces=N)
 if len(blips)!=1:continue
 rid=blips[0].get('{'+N['r']+'}embed')
 parent_p=draw
 while parent_p is not None and parent_p.tag!=q('p'):parent_p=parent_p.getparent()
 if parent_p is None or text(parent_p) or len(parent_p.xpath('.//a:blip',namespaces=N))>1:continue
 extent=draw.find('.//wp:extent',N)
 if extent is None:continue
 cx=int(extent.get('cx'));cy=int(extent.get('cy'))
 if rid=='rId63':cx=round(cx*.93);cy=round(cy*.93)
 pic=draw.find('.//pic:pic',N)
 if pic is None:continue
 pic=deepcopy(pic)
 for b in pic.xpath('.//a:blip',namespaces=N):
  for c in list(b):b.remove(c)
 for e in pic.xpath('.//a:srcRect',namespaces=N):e.getparent().remove(e)
 for e in pic.xpath('.//a:xfrm',namespaces=N):
  off=e.find('a:off',N)
  if off is not None:off.set('x','0');off.set('y','0')
  ext=e.find('a:ext',N)
  if ext is not None:ext.set('cx',str(cx));ext.set('cy',str(cy))
 p=draw
 while p is not None and p.tag!=q('p'):p=p.getparent()
 if p is None:continue
 for child in list(p):
  if child.tag!=q('pPr'):p.remove(child)
 pr=p.find(q('pPr'))
 if pr is None:pr=E.SubElement(p,q('pPr'))
 jc=pr.find(q('jc'))
 if jc is None:jc=E.SubElement(pr,q('jc'))
 jc.set(q('val'),'center')
 new=E.SubElement(E.SubElement(p,q('r')),q('drawing'));inline=E.SubElement(new,'{'+N['wp']+'}inline',distT='0',distB='0',distL='0',distR='0')
 E.SubElement(inline,'{'+N['wp']+'}extent',cx=str(cx),cy=str(cy));E.SubElement(inline,'{'+N['wp']+'}docPr',id=str(80000+index),name='Report figure')
 data=E.SubElement(E.SubElement(inline,'{'+N['a']+'}graphic'),'{'+N['a']+'}graphicData',uri=N['pic']);data.append(pic)

# Re-rendered PlantUML graphics have a white canvas in this plain edition.
mapping={'rId21':'02-sequence-area-and-plan','rId22':'03-sequence-start-and-telemetry','rId23':'04-sequence-target-and-assessment','rId24':'activity-area-assignment','rId25':'05-activity-mission-lifecycle','rId26':'activity-target-analysis','rId27':'08-domain-classes','rId58':'architecture','rId63':'database-erd'}
for rid,stem in mapping.items():
 im=Image.open(base/'plantuml-plain'/(stem+'.png')).convert('RGB');buf=BytesIO();im.save(buf,format='JPEG' if targets[rid].endswith(('.jpg','.jpeg')) else 'PNG',quality=96);parts[targets[rid]]=buf.getvalue()

def plain_format(x):
 for node in x.xpath('//w:color',namespaces=N):
  node.attrib.clear();node.set(q('val'),'000000')
 for node in x.xpath('//w:shd | //w:highlight | //w:pBdr',namespaces=N):node.getparent().remove(node)
 for border in x.xpath('//w:tblBorders/* | //w:tcBorders/*',namespaces=N):
  for attr in [q('themeColor'),q('themeTint'),q('themeShade')]:border.attrib.pop(attr,None)
  border.set(q('color'),'808080')
 for table in x.xpath('//w:tbl',namespaces=N):
  rows=table.findall(q('tr'))
  if not rows:continue
  for cell in rows[0].findall(q('tc')):
   pr=cell.find(q('tcPr'))
   if pr is None:pr=E.SubElement(cell,q('tcPr'))
   E.SubElement(pr,q('shd'),{q('fill'):'F0F0F0',q('val'):'clear'})
plain_format(root)
# Discard empty paragraphs left behind by the old decorative/page-number layer.
for p in list(body):
 if p.tag==q('p') and not text(p) and not p.xpath('.//w:sectPr | .//w:drawing | .//w:pict | .//w:br | .//w:bookmarkStart',namespaces=N):body.remove(p)
for name in ['word/styles.xml','word/numbering.xml']:
 if name in parts:
  xml=E.fromstring(parts[name]);plain_format(xml);parts[name]=E.tostring(xml,encoding='UTF-8',xml_declaration=True,standalone=True)
settings=E.fromstring(parts['word/settings.xml'])
for n in settings.findall(q('displayBackgroundShape')):settings.remove(n)
f=settings.find(q('updateFields'))
if f is None:f=E.SubElement(settings,q('updateFields'))
f.set(q('val'),'true')
assert old_table_text==[text(t) for t in root.xpath('//w:tbl',namespaces=N)]
new_prose=[text(p) for p in body if p.tag==q('p')]
missing=[t for t in old_prose if t not in new_prose]
assert not missing,repr(missing)
for name,xml in [('word/document.xml',root),('word/settings.xml',settings),('word/_rels/document.xml.rels',rels),('[Content_Types].xml',ct)]:parts[name]=E.tostring(xml,encoding='UTF-8',xml_declaration=True,standalone=True)
with ZipFile(dest,'w',ZIP_DEFLATED) as z:
 for name,value in parts.items():z.writestr(name,value)
(base/'plain-report-validation.json').write_text(json.dumps({'source':str(source),'output':str(dest),'body_prose_preserved':True,'table_text_preserved':True,'theme_removed':True,'editable_cover':True,'plain_chapter_pages':5},indent=2),encoding='utf-8')
print(dest.name)
