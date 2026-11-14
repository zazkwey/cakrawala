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
# 1. BACA DATA (DENGAN CACHE)
# ======================================================================

@st.cache_data
def muat_kalender(kode_area):
    df = pd.read_csv(f"kalender_{kode_area}.csv")
    # Pengaman ganda: jika archive dan nrt tumpang-tindih di bulan yang sama, buang nrt
    if "jenis" in df.columns:
        sudah_archive = (
            df[df["jenis"] == "archive"][["sensor", "tahun", "bulan"]]
            .drop_duplicates()
            .assign(_ada_archive=True)
        )
        df = df.merge(sudah_archive, on=["sensor", "tahun", "bulan"], how="left")
        df = df[~((df["jenis"] == "nrt") & (df["_ada_archive"] == True))]
        df = df.drop(columns=["_ada_archive"])
    return df


@st.cache_data
def muat_peta(kode_area):
    return pd.read_csv(f"peta_{kode_area}.csv")


AREA = {
    "Indonesia": "indonesia",
    "Kalimantan": "kalimantan",
    "Kalimantan Tengah": "kalimantan_tengah",
    "Sumatera": "sumatera",
    "Riau": "riau",
    "Papua": "papua",
}

kolom_kiri, kolom_tengah, kolom_kanan = st.columns([1.2, 1, 1.3])
with kolom_kiri:
    nama_area = st.selectbox("Area", list(AREA.keys()),
                             index=list(AREA).index("Kalimantan Tengah"))
with kolom_tengah:
    satuan = st.radio("Satuan kalender", ["Skala VIIRS", "Skala MODIS"],
                      horizontal=True)
with kolom_kanan:
    filter_pita = st.radio(
        "Tingkat kepercayaan",
        ["Semua (l, n, h)", "Sedang & tinggi (n, h)"],
        horizontal=True,
    )

d = muat_kalender(AREA[nama_area])
if filter_pita == "Sedang & tinggi (n, h)":
    d = d[d["pita"].isin(["n", "h"])]


# ======================================================================
# 2. SUSUN JADI TABEL tahun-bulan x sensor
# ======================================================================

per_sensor = (
    d.groupby(["tahun", "bulan", "sensor"])["n"].sum()
    .unstack("sensor")
    .fillna(0)
)

kolom_viirs = ["VIIRS_SNPP", "VIIRS_NOAA20", "VIIRS_NOAA21"]
for s in ["MODIS"] + kolom_viirs:
    if s not in per_sensor.columns:
        per_sensor[s] = 0.0

# Gabungkan satelit-satelit VIIRS dengan mengambil cakupan terbanyak di tiap bulan.
# Menghindari bug saat S-NPP berhenti 2 Nov 2026 (2 hari S-NPP tidak menimpa
# satu bulan penuh data NOAA-20).
per_sensor["VIIRS"] = per_sensor[kolom_viirs].max(axis=1)


# ======================================================================
# 3. HITUNG RASIO DARI PERIODE TUMPANG-TINDIH
# ======================================================================

# Hanya bulan-bulan ketika KEDUA sensor sama-sama mendeteksi.
tumpang = per_sensor[(per_sensor["MODIS"] > 0) & (per_sensor["VIIRS"] > 0)]

# Rasio dihitung dari TOTAL, bukan rata-rata rasio bulanan, agar bulan
# sepi tidak menghasilkan rasio ekstrem yang membebani rata-rata.
rasio = (
    tumpang["VIIRS"].sum() / tumpang["MODIS"].sum()
    if len(tumpang) and tumpang["MODIS"].sum() > 0
    else 1.0
)


# ======================================================================
# 4. HARMONISASI
# ======================================================================

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

per_tahun = harmoni.groupby("tahun").sum()
per_bulan = harmoni.groupby("bulan").sum()

jumlah_tahun = len(per_tahun)
tahun_ini = int(per_tahun.index.max())
peringkat = int((per_tahun > per_tahun.loc[tahun_ini]).sum()) + 1
musim = per_bulan.loc[per_bulan.index.isin([8, 9, 10])].sum() / per_bulan.sum() * 100
bulan_puncak = BULAN[int(per_bulan.idxmax()) - 1]

h1, h2, h3 = st.columns(3)
h1.metric("Kebakaran terjadi di Agu–Okt", f"{musim:.0f}%",
          help=f"Bagian dari seluruh deteksi {jumlah_tahun} tahun yang jatuh di tiga bulan ini")
h2.metric(f"Peringkat {tahun_ini} dalam {jumlah_tahun} tahun", f"ke-{peringkat}",
          help="Semakin kecil, semakin parah")
h3.metric("Bulan terparah sepanjang sejarah", bulan_puncak)

st.markdown(
    """
Kebakaran gambut Indonesia tidak menyebar seperti kebakaran hutan biasa.
Apinya **membara di bawah permukaan** — tanpa nyala, pada suhu jauh lebih
rendah, dan bisa bertahan berbulan-bulan setelah asap di permukaan hilang.

Jejak panas permukaannya kecil. Justru karena itu, satelit dengan piksel
besar sering **melewatkannya**.

> Ini sangat penting bagi orang yang tinggal di dekatnya karena bla bla plis tambahin krpc
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

*Catatan spasial: penyaringan wilayah menggunakan batas kotak koordinat (bounding box),
sehingga area perbatasan darat negara tetangga ikut tercakup secara agregat.*
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
        color_continuous_scale="Reds",
        aspect="auto",
    )
    fig.update_yaxes(dtick=1)
    fig.update_layout(title=judul, margin=dict(l=0, r=0, t=40, b=0), height=620)
    return fig


tab1, tabp, tab2, tab3, tab4 = st.tabs(
    ["Kalender harmonisasi", "Peta", "Perbandingan bulanan",
     "Sebelum vs sesudah", "Data"]
)

with tab1:
    th_min = int(harmoni.index.get_level_values("tahun").min())
    th_maks = int(harmoni.index.get_level_values("tahun").max())
    dari, sampai = st.slider("Rentang tahun", th_min, th_maks,
                             (th_min, th_maks))

    pilih_tahun = harmoni[
        harmoni.index.get_level_values("tahun").isin(range(dari, sampai + 1))
    ]
    st.plotly_chart(gambar(jadi_kalender(pilih_tahun),
                           f"Setelah harmonisasi — {satuan.lower()}"),
                    width="stretch")


with tabp:
    try:
        p = muat_peta(AREA[nama_area])
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

        puncak = max(1, int(
            sensor_p.groupby(["tahun", "lat", "lon"])["n"].sum().max()
        ))

        pusat_lat = float(sensor_p["lat"].mean())
        pusat_lon = float(sensor_p["lon"].mean())
        lebar = sensor_p["lat"].max() - sensor_p["lat"].min()
        zoom = 4 if lebar > 8 else (5 if lebar > 3 else 6)

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
                putar = st.button("▶  Putar animasi", width="stretch")

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
    # ---- perbandingan bulan pilihan dibanding median historis ----
    semua_tahun = sorted(harmoni.index.get_level_values("tahun").unique())
    tahun_terbaru = int(semua_tahun[-1])
    bulan_terbaru = int(harmoni.loc[tahun_terbaru].index.max())

    p1, p2 = st.columns(2)
    with p1:
        tahun_pilih = st.selectbox(
            "Tahun", semua_tahun, index=len(semua_tahun) - 1, key="tab2_tahun"
        )
    with p2:
        bulan_tersedia = sorted(harmoni.loc[tahun_pilih].index.unique())
        bulan_nama = st.selectbox(
            "Bulan",
            [BULAN[b - 1] for b in bulan_tersedia],
            index=len(bulan_tersedia) - 1,
            key="tab2_bulan",
        )
        bulan_pilih = BULAN.index(bulan_nama) + 1

    nilai_kini = float(harmoni.loc[(tahun_pilih, bulan_pilih)])

    # Median bulan yang sama dari seluruh tahun lain dalam dataset
    sejarah = harmoni[
        (harmoni.index.get_level_values("bulan") == bulan_pilih)
        & (harmoni.index.get_level_values("tahun") != tahun_pilih)
    ]
    median_sejarah = float(sejarah.median()) if len(sejarah) else 0.0

    st.subheader(f"{BULAN[bulan_pilih - 1]} {tahun_pilih}")

    k1, k2, k3 = st.columns(3)
    k1.metric("Titik api terpilih", f"{nilai_kini:,.0f}")
    k2.metric(f"Median historis {BULAN[bulan_pilih - 1]}",
              f"{median_sejarah:,.0f}")

    if median_sejarah > 0:
        selisih = (nilai_kini - median_sejarah) / median_sejarah * 100
        k3.metric("Selisih dari median", f"{selisih:+.0f}%",
                  delta=f"{selisih:+.0f}%")
        if selisih > 50:
            st.error(f"Aktivitas kebakaran **jauh di atas** median historis "
                     f"untuk bulan {BULAN[bulan_pilih - 1]}.")
        elif selisih < -50:
            st.success("Aktivitas kebakaran jauh di bawah median historis.")
        else:
            st.info("Aktivitas kebakaran mendekati median historis.")

    banding = sejarah.droplevel("bulan").rename("historis").to_frame()
    banding.loc[tahun_pilih] = nilai_kini
    banding = banding.sort_index()
    st.bar_chart(banding, height=320)
    st.caption(
        f"Jumlah titik api bulan {BULAN[bulan_pilih - 1]} di tiap tahun."
    )
    if tahun_pilih == tahun_terbaru and bulan_pilih == bulan_terbaru:
        st.warning(
            f"**Catatan:** bulan {BULAN[bulan_pilih - 1]} {tahun_pilih} belum "
            f"selesai — datanya berhenti pada tanggal unduhan, sehingga "
            f"angkanya cenderung lebih rendah dibanding bulan-bulan penuh sebelumnya."
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
    st.dataframe(grid, width="stretch")
    st.download_button(
        "Unduh CSV",
        grid.to_csv().encode("utf-8"),
        file_name=f"kalender_{nama_area.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )