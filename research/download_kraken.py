import io,zipfile,urllib.request, pathlib,json,hashlib
BASE='https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_Full.zip.part'
PART=2097152000
class Remote(io.RawIOBase):
 def __init__(self): self.pos=0; self.size=4*PART+1157945626
 def seekable(self): return True
 def tell(self): return self.pos
 def seek(self,o,w=0):
  self.pos=o if w==0 else self.pos+o if w==1 else self.size+o
  return self.pos
 def read(self,n=-1):
  if n<0:n=self.size-self.pos
  out=b''
  while n:
   part=self.pos//PART; off=self.pos%PART; take=min(n,PART-off)
   import subprocess
   b=subprocess.check_output(['curl','-fSs','--retry','2','--max-time','120','-r',f'{off}-{off+take-1}',BASE+f'{part:02}'])
   if len(b)!=take:raise ValueError('Incomplete range')
   out+=b;self.pos+=take;n-=take
  return out
pathlib.Path(__import__('sys').argv[1]).mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(Remote()) as z:
 names=[n for n in z.namelist() if n.upper().split('/')[-1] in ('XXBTZEUR_1.CSV','XXBTZEUR_240.CSV','XBTEUR_1.CSV','XBTEUR_240.CSV','MANIFEST.JSON')]
 print(names,flush=True)
 for name in names:
  info=z.getinfo(name);print(name,info.file_size,info.compress_size,flush=True)
  b=z.read(name);p=pathlib.Path(__import__('sys').argv[1])/pathlib.Path(name).name;p.write_bytes(b)
  print('saved',str(p),hashlib.sha256(b).hexdigest(),flush=True)
