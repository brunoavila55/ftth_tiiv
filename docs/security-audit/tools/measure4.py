import sys, io, time, resource
sys.path.insert(0, "/home/bruno/projects/ftth_tiiv/backend")
from PIL import Image
from app.modules.attachments.service import generate_thumbnail_image, inspect_file_content
W = 9400  # 88.4 Mpx  (< MAX_IMAGE_PIXELS=89.478.485)
img = Image.new("L", (W, W), 128)
buf = io.BytesIO(); img.save(buf, format="PNG", optimize=False, compress_level=9); data = buf.getvalue()
del img
print(f"PNG {W}x{W} = {W*W/1e6:.1f} Mpx, tamanho do arquivo = {len(data)/1024:.0f} KiB (limite de upload = 10 MiB)")
print("passa em inspect_file_content:", inspect_file_content(data))
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
t0=time.perf_counter(); out = generate_thumbnail_image(data, "image/png"); dt=time.perf_counter()-t0
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
print(f"generate_thumbnail_image: {dt:.2f}s, thumb={'ok' if out else None}, RSS pico {peak:.0f} MiB (antes {base:.0f} MiB) => +{peak-base:.0f} MiB por upload")
# acima de 2x o limite -> exceção não capturada
W2 = 14000
hdr = Image.new("1", (W2, W2), 0); b2 = io.BytesIO(); hdr.save(b2, format="PNG"); d2 = b2.getvalue()
print(f"\nPNG {W2}x{W2} ({W2*W2/1e6:.0f} Mpx), {len(d2)/1024:.1f} KiB")
try:
    generate_thumbnail_image(d2, "image/png"); print("sem exceção")
except BaseException as e:
    print("EXCEÇÃO NÃO CAPTURADA em generate_thumbnail_image:", type(e).__name__)
