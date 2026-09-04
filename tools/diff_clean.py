import numpy as np
from PIL import Image
import os
for f in sorted(os.listdir("shots/verify_clean")):
    old = os.path.join("shots", f)
    new = os.path.join("shots/verify_clean", f)
    if not os.path.exists(old):
        continue
    a = np.asarray(Image.open(new).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(old).convert("RGB"), dtype=np.int16)
    d = np.abs(a - b)
    print(f"{f}: mean|d|={d.mean():.3f} px>10: {(d.max(axis=2)>10).mean()*100:.2f}%")