"""Lihat tahun-tahun terparah menurut tiap sensor, Kalimantan Tengah."""

import pandas as pd

d = pd.read_csv("agregat_kalteng.csv")

print("=" * 55)
print("10 TAHUN TERPARAH MENURUT MODIS  (Kalimantan Tengah)")
print("=" * 55)
modis = d[d.sensor == "MODIS"].groupby("tahun")["n"].sum()
print(modis.sort_values(ascending=False).head(10).to_string())

print()
print("=" * 55)
print("TOTAL DETEKSI PER TAHUN, SEMUA SENSOR")
print("=" * 55)
tabel = d.groupby(["tahun", "sensor"])["n"].sum().unstack("sensor").fillna(0)
print(tabel.astype(int).to_string())

print()
print("=" * 55)
print("PUNCAK BULANAN — bulan mana yang paling sering terbakar")
print("=" * 55)
bulanan = d[d.sensor == "MODIS"].groupby("bulan")["n"].sum()
for bulan, n in bulanan.items():
    bar = "#" * int(n / bulanan.max() * 40)
    print(f"  {int(bulan):2d}  {int(n):>8,}  {bar}")
