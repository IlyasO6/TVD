"""Empremta del codi: per saber amb quin codi s'ha executat una avaluació.

Motiu: una execució de la bateria posterior a la v3 (descartada) va donar 68 respostes idèntiques a les de
la v3 perquè Colab va executar el codi
anterior (mòduls ja carregats a la memòria o fitxers de Drive encara no sincronitzats). Amb l'empremta:
- `loaded_fingerprint()`: la del codi que hi ha a la memòria (es calcula en importar el paquet);
- `disk_fingerprint()`: la dels fitxers que hi ha ara al disc;
si no coincideixen, el codi a la memòria és antic i cal tornar a carregar els mòduls. L'empremta es desa amb
els resultats i es mostra en començar, per comparar-la amb la del codi esperat.
"""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ("recomanador", "recomanador_llm")


def disk_fingerprint():
    """Hash dels fitxers .py dels dos paquets (sense proves ni __pycache__) i del JSON de dades."""
    digest = hashlib.sha1()
    files = sorted(p for package in PACKAGES for p in (ROOT / package).glob("*.py"))
    for path in files + [ROOT / "house_data_v2.json"]:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))  # igual a Windows i a Colab (Linux)
    return digest.hexdigest()[:10]


_LOADED = disk_fingerprint()


def loaded_fingerprint():
    return _LOADED
