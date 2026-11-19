"""Extract a small, labeled evidence sheet from the actual comparison movie."""
import subprocess
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'workspace/godot-benchmark/frames';folder.mkdir(exist_ok=True)
samples=[(.4,'contact'),(.9,'passing'),(1.5,'weight / swing'),(2.1,'next contact'),(3.9,'stop'),(5.8,'surprise'),(10.,'speaking / elbow'),(15.1,'listener reaction')]
sheet=Image.new('RGB',(1280,800),'#152331');draw=ImageDraw.Draw(sheet)
for i,(seconds,label) in enumerate(samples):
    path=folder/f'{i:02}.png'
    subprocess.run(['ffmpeg','-y','-v','error','-ss',str(seconds),'-i',str(ROOT/'output/godot-benchmark.mp4'),'-frames:v','1',str(path)],check=True)
    with Image.open(path) as image:sheet.paste(image.resize((320,180)),((i%4)*320,(i//4)*400+30))
    draw.text(((i%4)*320+8,(i//4)*400+8),f'{seconds:.1f}s  {label}',fill='white')
    # Original/new movie comparison uses exactly the same timeline and audio.
    comparison=folder/f'comparison_{i:02}.png'
    subprocess.run(['ffmpeg','-y','-v','error','-ss',str(seconds),'-i',str(ROOT/'output/godot-comparison.mp4'),'-frames:v','1',str(comparison)],check=True)
    with Image.open(comparison) as image:sheet.paste(image.resize((320,90)),((i%4)*320,(i//4)*400+235))
sheet.save(ROOT/'workspace/godot-benchmark/review-sheet.png')
