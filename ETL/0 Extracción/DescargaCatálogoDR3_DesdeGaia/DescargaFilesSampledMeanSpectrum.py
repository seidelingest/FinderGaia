import os
import requests
import time
from tqdm import tqdm

# ==================================
# CONFIGURACIÓN
# ==================================

BASE_URL = "https://cdn.gea.esac.esa.int/Gaia/gdr3/Spectroscopy/xp_sampled_mean_spectrum/"
LOCAL_MD5 = "_MD5SUM_SampledMeanSpace.txt"
OUTPUT_DIR = r"O:\Catalogo Gaia\DR3\xp_sampled_mean_spectrum"

CHUNK_SIZE = 1024 * 1024  # 1 MB

os.makedirs(OUTPUT_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})

# ==================================
# Leer lista de ficheros
# ==================================

def get_file_list():

    if not os.path.exists(LOCAL_MD5):
        raise Exception("MD5SUM.txt no encontrado localmente.")

    files = []

    with open(LOCAL_MD5, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 2 and parts[1].endswith(".csv.gz"):
                files.append(parts[1])

    print(f"Total ficheros detectados: {len(files)}")
    return files


# ==================================
# Descargar con reanudación
# ==================================

def download_file(filename):

    url = BASE_URL + filename
    file_path = os.path.join(OUTPUT_DIR, filename)

    # Obtener tamaño remoto
    head = session.head(url, timeout=30)
    head.raise_for_status()
    remote_size = int(head.headers.get("content-length", 0))

    local_size = 0
    if os.path.exists(file_path):
        local_size = os.path.getsize(file_path)

        if local_size == remote_size:
            print(f"[SKIP] Completo: {filename}")
            return

        elif local_size < remote_size:
            print(f"[RESUME] {filename} ({local_size}/{remote_size})")
        else:
            print(f"[WARNING] Tamaño local mayor que remoto. Reiniciando.")
            local_size = 0

    headers = {}
    if local_size > 0:
        headers["Range"] = f"bytes={local_size}-"

    with session.get(url, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()

        mode = "ab" if local_size > 0 else "wb"

        with open(file_path, mode) as f:
            with tqdm(
                total=remote_size,
                initial=local_size,
                unit="B",
                unit_scale=True,
                desc=filename,
                leave=False
            ) as pbar:
                for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))


# ==================================
# MAIN
# ==================================

if __name__ == "__main__":

    files = get_file_list()
    total_files = len(files)

    start_time = time.time()

    for index, filename in enumerate(files, start=1):

        file_start = time.time()

        try:
            print("=" * 80)
            print(f"[{index}/{total_files}] {filename}")

            download_file(filename)

            file_time = time.time() - file_start
            elapsed = time.time() - start_time

            files_done = index
            files_remaining = total_files - files_done

            avg_time = elapsed / files_done
            eta_seconds = avg_time * files_remaining

            eta_h = int(eta_seconds // 3600)
            eta_m = int((eta_seconds % 3600) // 60)
            eta_s = int(eta_seconds % 60)

            print(f"[OK] Tiempo fichero: {file_time:.2f}s")
            print(f"[GLOBAL] Transcurrido: {elapsed/3600:.2f}h")
            print(f"[GLOBAL] ETA estimado: {eta_h}h {eta_m}m {eta_s}s")

        except Exception as e:
            print(f"[ERROR] {filename}: {e}")
            continue

    total_time = time.time() - start_time
    print("=" * 80)
    print("Proceso finalizado.")
    print(f"Tiempo total: {total_time/3600:.2f} horas")
