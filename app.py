"""
Kalender Aktivitas Kebakaran — harmonisasi MODIS & VIIRS
NASA Space Apps Challenge 2026 · Local Event Yogyakarta
"""

import time

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
         "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

st.set_page_config(page_title="Kalender Kebakaran", layout="wide")
st.title("Kalender Aktivitas Kebakaran")
st.caption("Harmonisasi MODIS & VIIRS · data titik api NASA FIRMS · 2000–2026")


# ======================================================================
# 1. BACA DATA
# ======================================================================

AREA = {
    "Indonesia": "indonesia",
    "Kalimantan": "kalimantan",
    "Kalimantan Tengah": "kalimantan_tengah",
    "Sumatera": "sumatera",
    "Riau": "riau",
    "Papua": "papua",
}

kolom_kiri, kolom_kanan = st.columns(2)
with kolom_kiri:
    nama_area = st.selectbox("Area", list(AREA.keys()),
                             index=list(AREA).index("Kalimantan Tengah"))
with kolom_kanan:
    satuan = st.radio("Satuan kalender", ["Skala VIIRS", "Skala MODIS"],
                      horizontal=True)

d = pd.read_csv(f"kalender_{AREA[nama_area]}.csv")


# ======================================================================
# 2. SUSUN JADI TABEL tahun-bulan x sensor
# ======================================================================

# PILIHAN METODE: semua pita kepercayaan dipakai (l, n, h).
# Kalau mau menyaring, ganti baris di bawah ini, misalnya:
#     d = d[d["pita"].isin(["n", "h"])]

per_sensor = (
    d.groupby(["tahun", "bulan", "sensor"])["n"].sum()
    .unstack("sensor")
    .fillna(0)
)

for s in ["MODIS", "VIIRS_SNPP", "VIIRS_NOAA20"]:
    if s not in per_sensor.columns:
        per_sensor[s] = 0.0

# Gabungkan dua satelit VIIRS jadi satu kolom.
# S-NPP dipakai lebih dulu; NOAA-20 mengisi saat S-NPP tidak ada
# (S-NPP berhenti 2 November 2026).
per_sensor["VIIRS"] = per_sensor["VIIRS_SNPP"].where(
    per_sensor["VIIRS_SNPP"] > 0, per_sensor["VIIRS_NOAA20"]
)


# ======================================================================
# 3. HITUNG RASIO DARI PERIODE TUMPANG-TINDIH
# ======================================================================

# Hanya bulan-bulan ketika KEDUA sensor sama-sama mendeteksi.
tumpang = per_sensor[(per_sensor["MODIS"] > 0) & (per_sensor["VIIRS"] > 0)]

# PILIHAN METODE: rasio dihitung dari TOTAL, bukan rata-rata rasio bulanan.
# Alasan: bulan dengan sedikit kebakaran menghasilkan rasio yang liar
# (3 banding 1 = 3,0), dan merata-ratakannya memberi bobot sama pada
# bulan sepi dan bulan puncak. Total memberi bobot sesuai aktivitas.
rasio = tumpang["VIIRS"].sum() / tumpang["MODIS"].sum()


# ======================================================================
# 4. HARMONISASI
# ======================================================================

# Aturan: pakai VIIRS bila ada (lebih tajam); bila tidak ada,
# naikkan MODIS dengan rasio supaya setara skala VIIRS.
harmoni_viirs = per_sensor["VIIRS"].where(
    per_sensor["VIIRS"] > 0, per_sensor["MODIS"] * rasio
)

if satuan == "Skala MODIS":
    harmoni = harmoni_viirs / rasio
    mentah = per_sensor["MODIS"] + per_sensor["VIIRS"]
else:
    harmoni = harmoni_viirs
    mentah = per_sensor["MODIS"] + per_sensor["VIIRS"]


# ======================================================================
# 5. TAMPILKAN
# ======================================================================

# ---- angka pembuka: yang membuat orang berhenti menggulir ----
per_tahun = harmoni.groupby("tahun").sum()
per_bulan = harmoni.groupby("bulan").sum()

tahun_ini = int(per_tahun.index.max())
peringkat = int((per_tahun > per_tahun.loc[tahun_ini]).sum()) + 1
musim = per_bulan.loc[[8, 9, 10]].sum() / per_bulan.sum() * 100
bulan_puncak = BULAN[int(per_bulan.idxmax()) - 1]

h1, h2, h3 = st.columns(3)
h1.metric(f"Kebakaran terjadi di Agu–Okt", f"{musim:.0f}%",
          help="Bagian dari seluruh deteksi 26 tahun yang jatuh di tiga bulan ini")
h2.metric(f"Peringkat {tahun_ini} dalam 26 tahun", f"ke-{peringkat}",
          help="Semakin kecil, semakin parah")
h3.metric("Bulan terparah sepanjang sejarah", bulan_puncak)

st.markdown(
    f"""
Kebakaran gambut Indonesia tidak menyebar seperti kebakaran hutan biasa.
Apinya **membara di bawah permukaan** — tanpa nyala, pada suhu jauh lebih
rendah, dan bisa bertahan berbulan-bulan setelah asap di permukaan hilang.

Jejak panas permukaannya kecil. Justru karena itu, satelit dengan piksel
besar sering **melewatkannya**.

> *[ISI SENDIRI — satu paragraf: kenapa ini penting bagi orang yang tinggal
> di sana, dan apa yang bisa dilakukan petugas dengan kalender ini.]*
"""
)

with st.expander("Bagaimana dua sensor ini disatukan"):
    st.markdown(
        f"""
NASA mendeteksi titik api dengan dua instrumen berbeda:

| | piksel | mulai |
|---|---|---|
| **MODIS** (Terra, Aqua) | ~1 km | 2000 |
| **VIIRS** (Suomi NPP, NOAA-20) | ~375 m | 2012 |

Piksel VIIRS luasnya sekitar **tujuh kali lebih kecil**, jadi api yang sama
mengisi bagian yang jauh lebih besar dari satu piksel dan terdeteksi lebih
mudah. Akibatnya, pada wilayah dan periode yang sama VIIRS mencatat
**{rasio:.2f}× lebih banyak** titik api daripada MODIS — diukur dari
**{len(tumpang)} bulan** ketika keduanya beroperasi bersamaan.

Selisih itu berasal dari sensornya, bukan dari jumlah kebakaran. Menjumlahkan
keduanya mentah-mentah akan memunculkan lonjakan palsu pada 2012, saat VIIRS
mulai mengudara. Rasio di atas dipakai untuk menghapus lonjakan itu.
        """
    )


def jadi_kalender(seri):
    """Ubah seri (tahun, bulan) jadi grid tahun x bulan."""
    g = seri.unstack("bulan").reindex(columns=range(1, 13)).fillna(0)
    g.columns = BULAN
    return g


def gambar(grid, judul):
    fig = px.imshow(
        grid,
        labels=dict(x="Bulan", y="Tahun", color="Titik api"),
        color_continuous_scale="Reds",   # satu warna, terang -> gelap
        aspect="auto",
    )
    fig.update_yaxes(dtick=1)
    fig.update_layout(title=judul, margin=dict(l=0, r=0, t=40, b=0), height=620)
    return fig


tab1, tabp, tab2, tab3, tab4 = st.tabs(
    ["Kalender harmonisasi", "Peta", "Bulan berjalan",
     "Sebelum vs sesudah", "Data"]
)

with tab1:
    # penggeser rentang tahun
    th_min = int(harmoni.index.get_level_values("tahun").min())
    th_maks = int(harmoni.index.get_level_values("tahun").max())
    dari, sampai = st.slider("Rentang tahun", th_min, th_maks,
                             (th_min, th_maks))

    pilih_tahun = harmoni[
        harmoni.index.get_level_values("tahun").isin(range(dari, sampai + 1))
    ]
    st.plotly_chart(gambar(jadi_kalender(pilih_tahun),
                           f"Setelah harmonisasi — {satuan.lower()}"),
                    width='stretch')


with tabp:
    # ---- peta sebaran titik api ----
    try:
        p = pd.read_csv(f"peta_{AREA[nama_area]}.csv")
    except FileNotFoundError:
        p = None
        st.warning(
            f"File `peta_{AREA[nama_area]}.csv` belum ada. "
            f"Jalankan `py agregasi.py` dulu."
        )

    if p is not None:
        sensor_tersedia = sorted(p["sensor"].unique())
        kiri, kanan = st.columns([1, 2])
        with kiri:
            sensor_peta = st.selectbox(
                "Sensor", sensor_tersedia,
                index=(sensor_tersedia.index("VIIRS_SNPP")
                       if "VIIRS_SNPP" in sensor_tersedia else 0),
                key="sensor_peta",
            )
        with kanan:
            mode = st.radio(
                "Tampilan", ["Gabungan beberapa tahun", "Satu tahun"],
                horizontal=True, key="mode_peta",
            )
            gaya = st.radio(
                "Gaya penanda", ["Nyala api", "Titik"],
                horizontal=True, key="gaya_peta",
            )

        p_min, p_maks = int(p["tahun"].min()), int(p["tahun"].max())
        sensor_p = p[p["sensor"] == sensor_peta]

        # Skala dikunci ke sel tersibuk dalam SATU tahun, supaya tahun sepi
        # benar-benar terlihat sepi saat animasi berjalan. Tanpa ini setiap
        # tahun akan tampak sama parahnya.
        puncak = max(1, int(
            sensor_p.groupby(["tahun", "lat", "lon"])["n"].sum().max()
        ))

        # Kamera juga dikunci, supaya petanya tidak melompat tiap ganti tahun.
        pusat_lat = float(sensor_p["lat"].mean())
        pusat_lon = float(sensor_p["lon"].mean())
        lebar = sensor_p["lat"].max() - sensor_p["lat"].min()
        zoom = 4 if lebar > 8 else (5 if lebar > 3 else 6)

        # Gradien nyala: gelap -> merah -> jingga -> kuning.
        # Dipakai di atas peta gelap, jadi bacanya tetap "makin terang
        # berarti makin banyak" — satu arah, bukan pelangi.
        NYALA = [
            [20, 0, 0, 0], [128, 17, 0, 140], [189, 48, 7, 180],
            [230, 95, 10, 210], [247, 150, 25, 235], [255, 214, 90, 255],
        ]

        def susun_peta(df, gaya):
            """Bangun satu bingkai peta dari tabel lat/lon/n."""
            d2 = df.copy()

            if gaya == "Nyala api":
                lapis = pdk.Layer(
                    "HeatmapLayer",
                    data=d2,
                    get_position=["lon", "lat"],
                    get_weight="n",
                    aggregation="SUM",
                    color_range=[c[:3] for c in NYALA[1:]],
                    radius_pixels=55,
                    intensity=1.0,
                    threshold=0.03,
                )
                peta_dasar = "dark"
            else:
                bagian = (d2["n"] / puncak).clip(0, 1) ** 0.5
                # radius dalam meter; akar kuadrat supaya sel kecil terlihat
                d2["radius"] = 2_500 + bagian * 17_500
                d2["r"] = 255 - bagian * 90
                d2["g"] = 200 - bagian * 185
                d2["b"] = 160 - bagian * 145
                lapis = pdk.Layer(
                    "ScatterplotLayer",
                    data=d2,
                    get_position=["lon", "lat"],
                    get_radius="radius",
                    get_fill_color=["r", "g", "b", 190],
                    pickable=True,
                    auto_highlight=True,
                    stroked=False,
                )
                peta_dasar = "light"

            return pdk.Deck(
                layers=[lapis],
                initial_view_state=pdk.ViewState(
                    latitude=pusat_lat, longitude=pusat_lon,
                    zoom=zoom, pitch=0,
                ),
                map_style=peta_dasar,
                tooltip={"text": "{n} titik api di sel ini"},
            )

        def ambil(th_a, th_b):
            return (sensor_p[sensor_p["tahun"].between(th_a, th_b)]
                    .groupby(["lat", "lon"], as_index=False)["n"].sum())

        if mode == "Satu tahun":
            s1, s2 = st.columns([4, 1])
            with s1:
                satu = st.slider("Tahun", p_min, p_maks, p_maks,
                                 key="tahun_tunggal")
            with s2:
                st.write("")
                putar = st.button("▶  Putar animasi", width='stretch')

            wadah = st.empty()
            label = st.empty()

            if putar:
                for th in range(p_min, p_maks + 1):
                    bingkai = ambil(th, th)
                    label.subheader(f"{th}")
                    if len(bingkai):
                        wadah.pydeck_chart(susun_peta(bingkai, gaya))
                    time.sleep(0.45)
                label.subheader(f"{p_maks}  ·  selesai")
                titik = ambil(p_maks, p_maks)
            else:
                label.subheader(f"{satu}")
                titik = ambil(satu, satu)
                if len(titik):
                    wadah.pydeck_chart(susun_peta(titik, gaya))
            th_dari = th_sampai = satu
        else:
            th_dari, th_sampai = st.slider(
                "Rentang tahun", p_min, p_maks, (p_min, p_maks),
                key="tahun_peta",
            )
            titik = ambil(th_dari, th_sampai)
            if len(titik):
                st.pydeck_chart(susun_peta(titik, gaya))

        if len(titik) == 0:
            st.info("Tidak ada deteksi pada pilihan ini.")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Sel dengan titik api", f"{len(titik):,}")
            m2.metric("Total deteksi", f"{int(titik['n'].sum()):,}")
            m3.metric("Sel terpadat", f"{int(titik['n'].max()):,}")

        st.caption(
            f"Tiap lingkaran = satu sel 0,25° (±25 km); ukuran dan "
            f"kepekatannya mengikuti jumlah deteksi {sensor_peta}. "
            f"**Skala dikunci ke tahun tersibuk**, jadi tahun sepi memang "
            f"terlihat sepi saat animasi berjalan. Peta menampilkan deteksi "
            f"mentah per sensor, bukan angka harmonisasi: harmonisasi dipakai "
            f"untuk membandingkan **waktu**, peta menunjukkan **tempat**."
        )


with tab2:
    # ---- bulan berjalan dibanding median historis ----
    # Ini yang diminta challenge: bandingkan aktivitas bulan berjalan
    # dengan median historis bulan yang sama.
    tahun_akhir = int(harmoni.index.get_level_values("tahun").max())
    terakhir = harmoni.loc[tahun_akhir]
    bulan_akhir = int(terakhir.index.max())

    nilai_kini = float(terakhir.loc[bulan_akhir])

    # median bulan yang sama, dari semua tahun SEBELUMNYA
    sejarah = harmoni[
        (harmoni.index.get_level_values("bulan") == bulan_akhir)
        & (harmoni.index.get_level_values("tahun") < tahun_akhir)
    ]
    median_sejarah = float(sejarah.median())

    st.subheader(f"{BULAN[bulan_akhir - 1]} {tahun_akhir}")

    k1, k2, k3 = st.columns(3)
    k1.metric("Bulan ini", f"{nilai_kini:,.0f}")
    k2.metric(f"Median {BULAN[bulan_akhir - 1]} ({th_min}–{tahun_akhir - 1})",
              f"{median_sejarah:,.0f}")

    if median_sejarah > 0:
        selisih = (nilai_kini - median_sejarah) / median_sejarah * 100
        k3.metric("Selisih dari median", f"{selisih:+.0f}%",
                  delta=f"{selisih:+.0f}%")
        if selisih > 50:
            st.error(f"Aktivitas kebakaran **jauh di atas** median historis "
                     f"untuk bulan {BULAN[bulan_akhir - 1]}.")
        elif selisih < -50:
            st.success("Aktivitas kebakaran jauh di bawah median historis.")
        else:
            st.info("Aktivitas kebakaran mendekati median historis.")

    # perbandingan bulan ini terhadap semua tahun
    banding = sejarah.droplevel("bulan").rename("historis").to_frame()
    banding.loc[tahun_akhir] = nilai_kini
    st.bar_chart(banding, height=320)
    st.caption(
        f"Jumlah titik api bulan {BULAN[bulan_akhir - 1]} di tiap tahun. "
        f"Batang terakhir adalah bulan berjalan."
    )
    st.warning(
        f"**Keterbatasan:** bulan {BULAN[bulan_akhir - 1]} {tahun_akhir} belum "
        f"selesai — datanya berhenti pada tanggal unduhan. Median dihitung dari "
        f"bulan-bulan penuh, jadi perbandingan ini bukan setara dan cenderung "
        f"**merendahkan** aktivitas bulan berjalan."
    )

with tab3:
    st.markdown(
        "Tanpa harmonisasi, grafik melonjak tajam saat VIIRS mulai mengudara "
        "pada 2012 — lonjakan itu **palsu**, berasal dari sensornya, bukan "
        "dari kebakarannya."
    )
    tahunan = pd.DataFrame({
        "Dijumlahkan mentah": mentah.groupby("tahun").sum(),
        "Setelah harmonisasi": harmoni.groupby("tahun").sum(),
    })
    st.line_chart(tahunan)

with tab4:
    grid = jadi_kalender(harmoni).round(0).astype(int)
    st.dataframe(grid, width='stretch')
    st.download_button(
        "Unduh CSV",
        grid.to_csv().encode("utf-8"),
        file_name=f"kalender_{nama_area.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )
