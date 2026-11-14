"""
Agregasi spasial data FIRMS -> file kecil untuk peta.

Membaca semua CSV FIRMS di folder ini dan menghitung jumlah titik api
per KOTAK 0,25 derajat (sekitar 25 km) per sensor per tahun.

Koordinat dibulatkan ke pusat kotak, lalu dihitung. Hanya kotak yang
pernah ada apinya yang disimpan, jadi filenya tetap kecil.

Hasil:
    peta_indonesia.csv
    peta_kalteng.csv

Jalankan dari C:\\NASA :
    py agregasi_peta.py
"""

import glob
import os

import pandas as pd

# Ukuran kotak dalam derajat. 0.25 ~ 25 km.
# Kalau filenya terlalu besar, naikkan ke 0.5.
KOTAK = 0.25

KALTENG = {"lat_min": -3.5, "lat_max": 0.0, "lon_min": 111.0, "lon_max": 115.5}
UKURAN_CHUNK = 500_000

NAMA_SENSOR = {
    "M-C61": "MODIS",
    "SV-C2": "VIIRS_SNPP",
    "J1V-C2": "VIIRS_NOAA20",
}


def sensor_dari_nama(path):
    for kode, nama in NAMA_SENSOR.items():
        if kode in path:
            return nama
    return "TIDAK_DIKENAL"


def ke_kotak(seri):
    """Bulatkan koordinat ke pusat kotak."""
    return (seri / KOTAK).round() * KOTAK


def proses_file(path):
    sensor = sensor_dari_nama(path)
    kumpulan_id, kumpulan_kt = [], []
    total = 0

    pembaca = pd.read_csv(
        path,
        usecols=["latitude", "longitude", "acq_date"],
        chunksize=UKURAN_CHUNK,
    )

    for potongan in pembaca:
        total += len(potongan)

        tahun = pd.to_datetime(potongan["acq_date"], errors="coerce").dt.year
        potongan = potongan.assign(
            tahun=tahun,
            lat=ke_kotak(potongan["latitude"]),
            lon=ke_kotak(potongan["longitude"]),
        ).dropna(subset=["tahun"])

        kumpulan_id.append(
            potongan.groupby(["tahun", "lat", "lon"]).size().rename("n")
        )

        kt = potongan[
            potongan["latitude"].between(KALTENG["lat_min"], KALTENG["lat_max"])
            & potongan["longitude"].between(KALTENG["lon_min"], KALTENG["lon_max"])
        ]
        if len(kt):
            kumpulan_kt.append(
                kt.groupby(["tahun", "lat", "lon"]).size().rename("n")
            )

        print(f"    ... {total:,} baris", end="\r", flush=True)

    def gabung(kumpulan):
        if not kumpulan:
            return pd.DataFrame(columns=["tahun", "lat", "lon", "n", "sensor"])
        h = pd.concat(kumpulan).groupby(level=[0, 1, 2]).sum().reset_index()
        h["sensor"] = sensor
        return h

    print(f"    selesai: {total:,} baris" + " " * 20)
    return gabung(kumpulan_id), gabung(kumpulan_kt)


def main():
    berkas = sorted(glob.glob(os.path.join("**", "fire_*.csv"), recursive=True))
    if not berkas:
        print("Tidak ada file fire_*.csv. Jalankan dari folder C:\\NASA")
        return

    print(f"Ditemukan {len(berkas)} file. Kotak {KOTAK} derajat.\n")

    semua_id, semua_kt = [], []
    for path in berkas:
        print(f"[{sensor_dari_nama(path)}] {os.path.basename(path)}")
        ind, kt = proses_file(path)
        semua_id.append(ind)
        semua_kt.append(kt)

    indonesia = pd.concat(semua_id, ignore_index=True)
    kalteng = pd.concat(semua_kt, ignore_index=True)

    urut = ["sensor", "tahun", "lat", "lon", "n"]
    indonesia[urut].to_csv("peta_indonesia.csv", index=False)
    kalteng[urut].to_csv("peta_kalteng.csv", index=False)

    print("\n" + "=" * 58)
    print("FILE HASIL")
    for nama in ["peta_indonesia.csv", "peta_kalteng.csv"]:
        mb = os.path.getsize(nama) / 1_000_000
        n = sum(1 for _ in open(nama, encoding="utf-8")) - 1
        print(f"  {nama:22s} {n:>9,} baris   {mb:6.2f} MB")
    print()
    print("Kalau salah satu file lebih dari 20 MB, ubah KOTAK jadi 0.5")
    print("di baris atas skrip ini, lalu jalankan ulang.")
    print("=" * 58)


if __name__ == "__main__":
    main()
