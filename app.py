import streamlit as st
import pdfplumber
from pypdf import PdfReader, PdfWriter
import re
import io
import zipfile

# ─────────────────────────────────────────────
# SAYFA YAPILANDIRMASI
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="PDF Bölme Uygulaması",
    page_icon="📄",
    layout="centered"
)

st.title("📄 PDF Bölme & Öğrenci No İsimlendirme")
st.markdown("Yükleyeceğiniz PDF belgesindeki her sayfa ayrı bir PDF olarak kaydedilir. "
            "Dosya ismi, sayfadaki öğrenci numarasından otomatik oluşturulur.")

st.divider()

# ─────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────

def ogrenci_no_bul(sayfa_metni: str, ogrenci_no_regex: str) -> str | None:
    """
    Sayfadan öğrenci numarasını regex ile çeker.
    Bulamazsa None döner.
    """
    if not sayfa_metni:
        return None
    try:
        eslesmeler = re.findall(ogrenci_no_regex, sayfa_metni, re.IGNORECASE)
        if eslesmeler:
            # Parantezli grup varsa ilk grubu, yoksa tam eşleşmeyi al
            ilk = eslesmeler[0]
            return ilk.strip() if isinstance(ilk, str) else ilk[0].strip()
    except re.error:
        st.error("❌ Geçersiz regex deseni!")
    return None


def sayfa_metnini_al(pdf_bytes: bytes, sayfa_indeksi: int) -> str:
    """pdfplumber ile belirtilen sayfanın metnini çeker."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            sayfa = pdf.pages[sayfa_indeksi]
            metin = sayfa.extract_text()
            return metin if metin else ""
    except Exception:
        return ""


def pdf_bolucusu(
    pdf_bytes: bytes,
    sayfa_basina_belge: int,
    regex_deseni: str,
    bilinemyen_prefix: str
) -> list[dict]:
    """
    PDF'i sayfaları gruplandırarak böler.
    Her grup için öğrenci numarasını ilk sayfadan alır.
    Döner: [{"isim": "...", "bytes": b"..."}]
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    toplam_sayfa = len(reader.pages)
    belgeler = []
    bilinemyen_sayac = 1

    for baslangic in range(0, toplam_sayfa, sayfa_basina_belge):
        bitis = min(baslangic + sayfa_basina_belge, toplam_sayfa)

        # İlk sayfanın metnini al → öğrenci no bul
        ilk_sayfa_metin = sayfa_metnini_al(pdf_bytes, baslangic)
        ogrenci_no = ogrenci_no_bul(ilk_sayfa_metin, regex_deseni)

        if ogrenci_no:
            dosya_adi = f"{ogrenci_no}.pdf"
        else:
            dosya_adi = f"{bilinemyen_prefix}_{bilinemyen_sayac}.pdf"
            bilinemyen_sayac += 1

        # Yeni PDF yaz
        writer = PdfWriter()
        for i in range(baslangic, bitis):
            writer.add_page(reader.pages[i])

        tampon = io.BytesIO()
        writer.write(tampon)
        tampon.seek(0)

        belgeler.append({
            "isim": dosya_adi,
            "bytes": tampon.read(),
            "sayfa_aralik": f"Sayfa {baslangic + 1}–{bitis}",
            "ogrenci_no": ogrenci_no or "Bulunamadı"
        })

    return belgeler


def zip_olustur(belgeler: list[dict]) -> bytes:
    """Tüm PDF'leri tek bir ZIP içine paketler."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as zf:
        for belge in belgeler:
            zf.writestr(belge["isim"], belge["bytes"])
    tampon.seek(0)
    return tampon.read()


# ─────────────────────────────────────────────
# AYARLAR PANELİ
# ─────────────────────────────────────────────

with st.expander("⚙️ Ayarlar", expanded=True):
    col1, col2 = st.columns(2)

    with col1:
        sayfa_basina = st.number_input(
            "Her belgede kaç sayfa var?",
            min_value=1, max_value=50, value=1, step=1,
            help="Eğer her öğrencinin sınavı 1 sayfaysa 1 girin. 2 sayfaysa 2 girin."
        )

    with col2:
        bilinemyen_on_ek = st.text_input(
            "Öğrenci no bulunamazsa ön ek:",
            value="bilinmeyen",
            help="Örn: 'bilinmeyen' → bilinmeyen_1.pdf, bilinmeyen_2.pdf"
        )

    regex_deseni = st.text_input(
        "Öğrenci numarası için Regex deseni:",
        value=r"(\d{9,11})",
        help=(
            "Varsayılan: 9–11 haneli sayıları arar. "
            "Örnek özel desen: r'Öğrenci No[:\\s]*(\\d+)' "
            "→ 'Öğrenci No: 210201034' ifadesinden numarayı çeker."
        )
    )
    st.caption(f"🔍 Aktif desen: `{regex_deseni}`")

st.divider()

# ─────────────────────────────────────────────
# DOSYA YÜKLEME
# ─────────────────────────────────────────────

yuklenen = st.file_uploader(
    "📂 PDF dosyasını buraya sürükle veya seç",
    type=["pdf"],
    help="Birden fazla öğrencinin bulunduğu toplu PDF dosyasını yükleyin."
)

if yuklenen:
    pdf_verisi = yuklenen.read()

    # Önizleme bilgisi
    with pdfplumber.open(io.BytesIO(pdf_verisi)) as oncizleme:
        toplam = len(oncizleme.pages)

    st.info(
        f"📋 **{yuklenen.name}** yüklendi — "
        f"**{toplam} sayfa** | "
        f"Sayfa başına **{sayfa_basina}** sayfa → "
        f"yaklaşık **{toplam // sayfa_basina}** belge oluşacak"
    )

    # İlk sayfanın metnini göster (debug için)
    with st.expander("🔎 İlk Sayfanın Ham Metni (öğrenci no tespiti için kontrol et)"):
        ilk_metin = sayfa_metnini_al(pdf_verisi, 0)
        if ilk_metin:
            st.text(ilk_metin[:2000])
        else:
            st.warning("İlk sayfadan metin çekilemedi. PDF taranmış görüntü olabilir.")

    st.divider()

    # ─────────────────────────────────────────────
    # İŞLEM BUTONU
    # ─────────────────────────────────────────────

    if st.button("🚀 PDF'leri Böl ve İndir", type="primary", use_container_width=True):
        with st.spinner("PDF bölünüyor, öğrenci numaraları tespit ediliyor..."):
            try:
                belgeler = pdf_bolucusu(
                    pdf_bytes=pdf_verisi,
                    sayfa_basina_belge=int(sayfa_basina),
                    regex_deseni=regex_deseni,
                    bilinemyen_prefix=bilinemyen_on_ek
                )

                bulunan = sum(1 for b in belgeler if b["ogrenci_no"] != "Bulunamadı")
                bulunamayan = len(belgeler) - bulunan

                # Sonuç özeti
                c1, c2, c3 = st.columns(3)
                c1.metric("📄 Toplam Belge", len(belgeler))
                c2.metric("✅ No Tespit Edilen", bulunan)
                c3.metric("⚠️ No Bulunamayan", bulunamayan)

                # Tablo
                st.subheader("📋 Oluşturulan Dosyalar")
                for belge in belgeler:
                    durum = "✅" if belge["ogrenci_no"] != "Bulunamadı" else "⚠️"
                    st.write(
                        f"{durum} **{belge['isim']}** "
                        f"— {belge['sayfa_aralik']} "
                        f"— Öğrenci No: `{belge['ogrenci_no']}`"
                    )

                # ZIP indir
                zip_verisi = zip_olustur(belgeler)

                st.success(f"🎉 {len(belgeler)} adet PDF başarıyla oluşturuldu!")

                st.download_button(
                    label="📦 Tümünü ZIP Olarak İndir",
                    data=zip_verisi,
                    file_name="ogrenci_pdf_leri.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )

            except Exception as hata:
                st.error(f"❌ Bir hata oluştu: {hata}")
                st.exception(hata)

else:
    st.markdown("""
    ### 📌 Nasıl Çalışır?

    1. **⚙️ Ayarlar** kısmından belge başına düşen sayfa sayısını belirtin
    2. Öğrenci numarasının formatına uygun **regex desenini** girin
    3. PDF dosyanızı yükleyin
    4. **"PDF'leri Böl"** butonuna tıklayın
    5. Tüm dosyaları **ZIP olarak indirin**

    ---

    ### 🔍 Regex Örnekleri

    | Durum | Desen |
    |-------|-------|
    | Sadece 9 haneli sayı | `(\\d{9})` |
    | 9–11 haneli herhangi bir sayı | `(\\d{9,11})` |
    | "Öğrenci No: 123456789" formatı | `Öğrenci No[:\\s]*(\\d+)` |
    | "No: 123456789" formatı | `No[:\\s]*(\\d+)` |
    | Barkod / QR sonrası sayı | `(2\\d{8})` |
    """)

st.divider()
st.caption("📄 PDF Bölme Uygulaması · Streamlit ile yapılmıştır")