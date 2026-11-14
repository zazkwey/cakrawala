"""
Agregasi & Harmonisasi Spasial-Temporal Data FIRMS -> file kecil untuk aplikasi.

Menggabungkan deteksi MODIS (~1 km) dan VIIRS (~375 m) pada hari dan sel
~1,1 km (0,01 derajat) yang sama menjadi satu entitas titik api terpadu
('HARMONISASI'), sekaligus mempertahankan data asli per sensor.

Keluaran per wilayah:
    kalender_<wilayah>.csv   sensor, jenis, tahun, bulan, pita, n
    peta_<wilayah>.csv       sensor, tahun, lat, lon, n

Jalankan dari folder :
    py agregasi.py
"""

import glob
import os

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- pengaturan

# Kotak wilayah: (lat_min, lat_max, lon_min, lon_max). None = seluruh data.
# Catatan: batas kotak persegi ikut mencakup sebagian wilayah daratan negara
# tetangga di perbatasan (mis. Sarawak/Sabah pada kotak Kalimantan).
WILAYAH = {
    "indonesia":         None,
    "kalimantan":        (-4.2, 7.4, 108.8, 119.3),
    "kalimantan_tengah": (-3.5, 0.0, 111.0, 115.5),
    "sumatera":          (-6.0, 6.0, 95.0, 107.0),
    "riau":              (-1.5, 3.0, 100.0, 104.5),
    "papua":             (-9.0, 0.0, 130.0, 141.0),
}

KOTAK_FUSI = 0.01     # resolusi pencocokan MODIS-VIIRS (~1,1 km)
KOTAK_PETA = 0.25     # ukuran sel peta tampilan (~25 km)
MODIS_AMBANG_RENDAH = 30
MODIS_AMBANG_TINGGI = 80
UKURAN_CHUNK = 500_000

NAMA_SENSOR = {
    "M-C61": "MODIS",
    "SV-C2": "VIIRS_SNPP",
    "J1V-C2": "VIIRS_NOAA20",
    "J2V-C2": "VIIRS_NOAA21",
}

PITA_KE_ANGKA = {"?": 0, "l": 1, "n": 2, "h": 3}
ANGKA_KE_PITA = {0: "?", 1: "l", 2: "n", 3: "h"}

# ----------------------------------------------------------------- pembantu


def sensor_dari_nama(path):
    for kode, nama in NAMA_SENSOR.items():
        if kode in path:
            return nama
    return "TIDAK_DIKENAL"


def pita_ke_kode(seri):
    """Ubah confidence MODIS (0-100) dan VIIRS (l/n/h) jadi angka 0..3."""
    if seri.dtype == object:
        huruf = seri.astype(str).str.strip().str.lower().str[0]
        return huruf.map(PITA_KE_ANGKA).fillna(0).astype("int8")

    angka = pd.to_numeric(seri, errors="coerce")
    kode = np.full(len(seri), 2, dtype="int8")  # default 'n' (2)
    kode[angka < MODIS_AMBANG_RENDAH] = 1       # 'l'
    kode[angka >= MODIS_AMBANG_TINGGI] = 3      # 'h'
    kode[angka.isna()] = 0                      # '?'
    return kode


# -------------------------------------------------------------------- utama


def main():
    berkas = sorted(glob.glob(os.path.join("**", "fire_*.csv"), recursive=True))
    if not berkas:
        print("Tidak ada file fire_*.csv. Jalankan dari folder C:\\NASA")
        return

    print(f"Ditemukan {len(berkas)} file - {len(WILAYAH)} wilayah - "
          f"fusi {KOTAK_FUSI}° (~1 km) - peta {KOTAK_PETA}° (~25 km)\n")

    kumpulan_event = []

    for path in berkas:
        sensor = sensor_dari_nama(path)
        jenis = "nrt" if "_nrt_" in os.path.basename(path).lower() else "archive"
        print(f"[{sensor} | {jenis}] {os.path.basename(path)}")
        total = 0

        pembaca = pd.read_csv(
            path,
            usecols=["latitude", "longitude", "acq_date", "confidence"],
            chunksize=UKURAN_CHUNK,
        )

        for potongan in pembaca:
            total += len(potongan)
            tanggal = pd.to_datetime(potongan["acq_date"], errors="coerce")
            valid = tanggal.notna() & potongan["latitude"].notna() & potongan["longitude"].notna()
            potongan = potongan[valid]
            tanggal = tanggal[valid]

            if not len(potongan):
                continue

            df_chunk = pd.DataFrame({
                "sensor": sensor,
                "jenis": jenis,
                "tgl_int": (tanggal.dt.year * 10000 + tanggal.dt.month * 100 + tanggal.dt.day).astype("int32"),
                "tahun": tanggal.dt.year.astype("int16"),
                "bulan": tanggal.dt.month.astype("int8"),
                "lat_id": np.round(potongan["latitude"].to_numpy() / KOTAK_FUSI).astype("int32"),
                "lon_id": np.round(potongan["longitude"].to_numpy() / KOTAK_FUSI).astype("int32"),
                "pita_kode": pita_ke_kode(potongan["confidence"]),
            })

            # Kompres duplikat dalam chunk yang sama
            df_chunk = (
                df_chunk.groupby(["sensor", "jenis", "tgl_int", "tahun", "bulan", "lat_id", "lon_id"], as_index=False)
                ["pita_kode"].max()
            )
            kumpulan_event.append(df_chunk)
            print(f"    ... {total:,} baris", end="\r", flush=True)

        print(f"    selesai: {total:,} baris" + " " * 20)

    if not kumpulan_event:
        print("Tidak ada data valid yang terbaca.")
        return

    print("\nMenggabungkan dan melakukan deduplikasi spasial-temporal (~1 km)...")
    semua = pd.concat(kumpulan_event, ignore_index=True)

    # 1. Buang NRT jika bulan & sensor tersebut sudah punya data Archive
    sudah_archive = (
        semua[semua["jenis"] == "archive"][["sensor", "tahun", "bulan"]]
        .drop_duplicates()
        .assign(_ada_archive=True)
    )
    semua = semua.merge(sudah_archive, on=["sensor", "tahun", "bulan"], how="left")
    semua = semua[~((semua["jenis"] == "nrt") & (semua["_ada_archive"] == True))].drop(columns=["_ada_archive"])

    # 2. Deduplikasi per sensor pada grid 1 km harian
    per_sensor_1km = (
        semua.groupby(["sensor", "tgl_int", "tahun", "bulan", "lat_id", "lon_id"], as_index=False)
        .agg(pita_kode=("pita_kode", "max"), jenis=("jenis", "first"))
    )

    # 3. FUSI HARMONISASI: gabungkan MODIS + semua satelit VIIRS pada hari & sel 1 km yang sama
    harmoni_1km = (
        per_sensor_1km.groupby(["tgl_int", "tahun", "bulan", "lat_id", "lon_id"], as_index=False)
        .agg(pita_kode=("pita_kode", "max"), jenis=("jenis", "first"))
    )
    harmoni_1km["sensor"] = "HARMONISASI"

    gabungan_final = pd.concat([per_sensor_1km, harmoni_1km], ignore_index=True)
    gabungan_final["lat_asli"] = gabungan_final["lat_id"] * KOTAK_FUSI
    gabungan_final["lon_asli"] = gabungan_final["lon_id"] * KOTAK_FUSI
    gabungan_final["lat_peta"] = np.round(gabungan_final["lat_asli"] / KOTAK_PETA) * KOTAK_PETA
    gabungan_final["lon_peta"] = np.round(gabungan_final["lon_asli"] / KOTAK_PETA) * KOTAK_PETA
    gabungan_final["pita"] = gabungan_final["pita_kode"].map(ANGKA_KE_PITA)

    print("\n" + "=" * 62)
    print("FILE HASIL")

    for w, kotak in WILAYAH.items():
        if kotak is None:
            bagian = gabungan_final
        else:
            lat_min, lat_max, lon_min, lon_max = kotak
            bagian = gabungan_final[
                gabungan_final["lat_asli"].between(lat_min, lat_max)
                & gabungan_final["lon_asli"].between(lon_min, lon_max)
            ]

        if not len(bagian):
            print(f"  {w:20s} (tidak ada data)")
            continue

        k = (
            bagian.groupby(["sensor", "jenis", "tahun", "bulan", "pita"], as_index=False)
            .size()
            .rename(columns={"size": "n"})
        )
        p = (
            bagian.groupby(["sensor", "tahun", "lat_peta", "lon_peta"], as_index=False)
            .size()
            .rename(columns={"lat_peta": "lat", "lon_peta": "lon", "size": "n"})
        )

        fk, fp = f"kalender_{w}.csv", f"peta_{w}.csv"
        k.to_csv(fk, index=False)
        p.to_csv(fp, index=False)

        print(f"  {fk:28s} {len(k):>8,} baris  {os.path.getsize(fk) / 1e6:6.2f} MB")
        print(f"  {fp:28s} {len(p):>8,} baris  {os.path.getsize(fp) / 1e6:6.2f} MB")

    print("=" * 62)
    print("Selesai! Jalankan: streamlit run app.py")


if __name__ == "__main__":
    main()