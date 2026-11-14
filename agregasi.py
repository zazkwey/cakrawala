"""
Agregasi data FIRMS -> file kecil untuk aplikasi.

Satu kali baca, dua jenis keluaran, untuk beberapa wilayah:

    kalender_<wilayah>.csv   sensor, jenis, tahun, bulan, pita, n
    peta_<wilayah>.csv       sensor, tahun, lat, lon, n

Jalankan dari folder C:\\NASA :
    py agregasi.py
"""

import glob
import os

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

KOTAK = 0.25          # ukuran sel peta dalam derajat (~25 km)
MODIS_AMBANG_RENDAH = 30
MODIS_AMBANG_TINGGI = 80
UKURAN_CHUNK = 500_000

NAMA_SENSOR = {
    "M-C61": "MODIS",
    "SV-C2": "VIIRS_SNPP",
    "J1V-C2": "VIIRS_NOAA20",
    "J2V-C2": "VIIRS_NOAA21",
}

# ----------------------------------------------------------------- pembantu


def sensor_dari_nama(path):
    for kode, nama in NAMA_SENSOR.items():
        if kode in path:
            return nama
    return "TIDAK_DIKENAL"


def pita_kepercayaan(seri):
    """Samakan confidence MODIS (angka 0-100) dan VIIRS (huruf) jadi l/n/h."""
    if seri.dtype == object:
        return seri.astype(str).str.strip().str.lower().str[0]

    angka = pd.to_numeric(seri, errors="coerce")
    hasil = pd.Series("n", index=seri.index, dtype=object)
    hasil[angka < MODIS_AMBANG_RENDAH] = "l"
    hasil[angka >= MODIS_AMBANG_TINGGI] = "h"
    hasil[angka.isna()] = "?"
    return hasil


def buang_nrt_tumpang_tindih(df):
    """Jika (sensor, tahun, bulan) sudah ada di 'archive', buang versi 'nrt'-nya."""
    sudah_archive = (
        df[df["jenis"] == "archive"][["sensor", "tahun", "bulan"]]
        .drop_duplicates()
        .assign(_ada_archive=True)
    )
    gabung = df.merge(sudah_archive, on=["sensor", "tahun", "bulan"], how="left")
    bersih = gabung[~((gabung["jenis"] == "nrt") & (gabung["_ada_archive"] == True))]
    return bersih.drop(columns=["_ada_archive"])


# -------------------------------------------------------------------- utama


def main():
    berkas = sorted(glob.glob(os.path.join("**", "fire_*.csv"), recursive=True))
    if not berkas:
        print("Tidak ada file fire_*.csv. Jalankan dari folder C:\\NASA")
        return

    print(f"Ditemukan {len(berkas)} file - {len(WILAYAH)} wilayah - "
          f"sel peta {KOTAK} derajat\n")

    kalender = {w: [] for w in WILAYAH}
    peta = {w: [] for w in WILAYAH}

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

            potongan = potongan.assign(
                tahun=tanggal.dt.year,
                bulan=tanggal.dt.month,
                pita=pita_kepercayaan(potongan["confidence"]),
                lat=(potongan["latitude"] / KOTAK).round() * KOTAK,
                lon=(potongan["longitude"] / KOTAK).round() * KOTAK,
            ).dropna(subset=["tahun", "bulan"])

            potongan["tahun"] = potongan["tahun"].astype(int)
            potongan["bulan"] = potongan["bulan"].astype(int)

            for w, kotak in WILAYAH.items():
                if kotak is None:
                    bagian = potongan
                else:
                    lat_min, lat_max, lon_min, lon_max = kotak
                    bagian = potongan[
                        potongan["latitude"].between(lat_min, lat_max)
                        & potongan["longitude"].between(lon_min, lon_max)
                    ]
                if not len(bagian):
                    continue

                k = (bagian.groupby(["tahun", "bulan", "pita"])
                     .size().rename("n").reset_index())
                k["sensor"] = sensor
                k["jenis"] = jenis
                kalender[w].append(k)

                # Simpan jenis & bulan sementara untuk deduplikasi NRT vs Archive
                p = (bagian.groupby(["tahun", "bulan", "lat", "lon"])
                     .size().rename("n").reset_index())
                p["sensor"] = sensor
                p["jenis"] = jenis
                peta[w].append(p)

            print(f"    ... {total:,} baris", end="\r", flush=True)

        print(f"    selesai: {total:,} baris" + " " * 20)

    print("\n" + "=" * 62)
    print("FILE HASIL")

    for w in WILAYAH:
        if not kalender[w]:
            print(f"  {w:20s} (tidak ada data)")
            continue

        k_gabung = (pd.concat(kalender[w], ignore_index=True)
                    .groupby(["sensor", "jenis", "tahun", "bulan", "pita"],
                             as_index=False)["n"].sum())
        k = buang_nrt_tumpang_tindih(k_gabung)

        p_gabung = (pd.concat(peta[w], ignore_index=True)
                    .groupby(["sensor", "jenis", "tahun", "bulan", "lat", "lon"],
                             as_index=False)["n"].sum())
        p_bersih = buang_nrt_tumpang_tindih(p_gabung)
        p = (p_bersih.groupby(["sensor", "tahun", "lat", "lon"],
                              as_index=False)["n"].sum())

        fk, fp = f"kalender_{w}.csv", f"peta_{w}.csv"
        k.to_csv(fk, index=False)
        p.to_csv(fp, index=False)

        print(f"  {fk:28s} {len(k):>8,} baris  "
              f"{os.path.getsize(fk) / 1e6:6.2f} MB")
        print(f"  {fp:28s} {len(p):>8,} baris  "
              f"{os.path.getsize(fp) / 1e6:6.2f} MB")

    print("=" * 62)
    print("Kalau ada file peta lebih dari 20 MB, naikkan KOTAK jadi 0.5")
    print("di baris atas skrip ini, lalu jalankan ulang.")


if __name__ == "__main__":
    main()