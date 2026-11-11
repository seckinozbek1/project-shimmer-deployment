# Shimmer kullanım kılavuzu

Shimmer bir belgeyi ve sizin yazdığınız kuralları okur, belgenin bu kurallara nerede uymadığını bildirir. Belgenin kendi sayılarından çıkarılabilecek her şeyi Python hesaplar. Geriye kalan sorular bir dil modeline sorulur ve modelin yazdığı her şey açıkça işaretlenir.

Bu kılavuz kurulumdan ilk sonuçları okumaya kadar size yol gösterir. Her ekranın ayrıntısı [işletim kılavuzunda](RUNBOOK.md), kuralların nasıl yazılacağı [girdi biçiminde](INPUT_FORMAT.md), bir çalışmanın yazdığı dosyaların tamamı [çıktı biçiminde](OUTPUT_FORMAT.md) anlatılıyor. Bu üç belge İngilizcedir.

## Kurulum

Python 3.12'ye ve bu deponun bir kopyasına ihtiyacınız var. Windows'ta deponun klasöründe şu komutları çalıştırın:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux veya macOS'ta aynı komutlarda `python3.12 -m venv .venv` ve `.venv/bin/python` kullanın. Paketler birkaç gigabayt yer tutar, çünkü aralarında PyTorch da var.

Kurulumu model, ekran kartı ya da sağlayıcı anahtarı olmadan denemek için deponun yeni bir kopyasında şu komutu çalıştırın. Komuta deponun dışında yeni bir klasör verin:

```powershell
py -3.12 tools/clean_install_check.py --venv ..\shimmer_check_env
```

Bu komut yeni bir ortam kurar, paketleri yükler, örnek vakada Shimmer'ın hesaplama bölümünü modelsiz çalıştırır, konsolu açıp kapatır. Her adımın sonucunu yazar ve ancak hepsi geçerse 0 koduyla biter. Modelli bir inceleme hakkında hiçbir şey söylemez.

## Üç kullanım yolu

- Demo: kurulum yok, kayıtlı örnekler. Konsol, iki örnek vakanın kayıtlı sonuçlarıyla açılır; kurulacak ya da yazılacak bir şey yoktur. Belgeleriniz hiçbir yere gitmez, çünkü demo yalnızca kayıtlı örnekleri gösterir. Bu sürümde henüz yok.
- Kendi bilgisayarınızda (güçlü ekran kartlı). Shimmer belgelerinizi bilgisayarınızdaki modellerle inceler. Belgeleriniz bilgisayarınızda kalır. Ayarlarda tanımlı model dosyalarının model önbelleğinde olması ve CUDA destekli bir ekran kartı gerekir; yukarıdaki paketlerin içinde bu dosyalar yoktur. Ölçtüğümüz bütün çalışmalarda 24 GB belleği olan kiralık bir ekran kartı kullandık. 8 GB'lık bir dizüstü kartında bir çalışma saatler sürer. Neyin eksik olduğunu görmek için `python scripts/preflight.py --check-startup --backend-profile local` komutunu çalıştırın; bu komut hiçbir şeyi değiştirmez.
- Kiralık bulut makinesinde. Çalışma için bir makine kiralanır, iş bitince kapatılır. Belgeleriniz kiralanan makineye gider ve makineyle birlikte silinir. Bu sürümde henüz konsoldan başlatılamaz; kiralık bir çalışma şimdilik `docs/CLOUD_RUN_PREPARATION.md` dosyasındaki işletim araçlarıyla başlatılıyor.

Başlatma penceresindeki **Cloud** seçeneği bunlardan ayrı bir şeydir: bilgisayarınızdaki modeller yerine sağlayıcıların modellerini kullanır. Bu durumda belgelerinizin metni sağlayıcılara gider ve her çağrı ücretlidir. Anthropic ve OpenAI anahtarlarının deponun dışındaki bir dosyada durması gerekir. Shimmer bu dosyayı `SHIMMER_CONFIG_PATH` değişkeninden, deponun yanındaki `../api_keys/config.py` dosyasından ya da `.env_path` dosyasında yazan yoldan bulur. Anahtarı asla depoya koymayın.

## Konsolu açma

Windows'ta `start_shimmer.bat` dosyasını çalıştırın. Küçük bir pencere açılır. Bu pencere yalnızca İngilizcedir. Local (güçlü ekran kartlı kendi bilgisayarınız) veya Cloud (sağlayıcı modelleri) seçeneğini seçin, **Check and start** düğmesine basın ve eksik olarak bildirilen bir şey varsa okuyun. Konsol tarayıcınızda açılır. **Copy access token** düğmesine basıp erişim belirtecini konsola yapıştırın. Küçük pencereyi açık tutun, Shimmer'ı durdurmak için **Stop Shimmer** düğmesini kullanın. Tarayıcıyı kapatmak sunucuyu durdurmaz.

Linux veya macOS'ta `./shimmer.sh` komutunu çalıştırıp 3 numaralı seçeneği seçin. Erişim belirteci bir kez gösterilir, ardından sunucu başlar.

Konsolun dört sayfası vardır: **Çalışmalar**, **Gönder**, **Ajanlar** ve **Test değişiklikleri**. Konsolun dilini sayfanın üstündeki **Çıktı dili** alanından değiştirirsiniz. Konsol İngilizce açılır, Türkçe seçince bu kılavuzdaki adlar görünür.

## İnceleme başlatma

İncelenecek belgeye ve bir Markdown dosyasına yazılmış kurallarınıza ihtiyacınız var. Bir kural şöyle görünür:

```
## CONV-P01 Line arithmetic [required] [conformance]

The line total must equal the quantity times the unit price.
```

Kural, belgenin kendi etiketlerini anar: burada `line total`, `quantity` ve `unit price`. Shimmer kuralın belgenin hangi bölümüne uyduğunu bu etiketlerden anlar. Kural yazmanın gerisi [girdi biçiminin](INPUT_FORMAT.md) 3 ile 5. bölümlerinde.

Belgeleri Markdown olarak yazmak en iyisidir. Word `.docx` dosyası da olur: bütün izlenen değişiklikler kabul edilmiş gibi okunur, başlık stilleri bölüm sayılır. İnceleme sayıları düz metinden değil, etiketli satırlardan (`Quantity: 4 box`) ve tablolardan okur.

**Gönder** sayfasında sırayla şunları yapın:

1. **Görev** alanında **İnceleme: belge yükleyin** seçeneğini seçin.
2. **Dosya seç** düğmesine basıp belgeyi, kurallarınızı ve varsa kaynak malzemeyi ekleyin.
3. Her dosyaya bir rol verin: **İncelenecek belge**, **Kaynak malzemesi veya inceleme kuralları** ya da **Karşılaştırılacak önceki sürüm**.
4. **Gizlilik** alanında **Normal: belgelerin hassas olmadığını beyan ediyorum** seçeneğini seçin. Gizlilik katmanı kapalı geldiği için hassas seçeneği kabul edilmez. Hassas belgeleri Normal çalışmayla göndermeyin.
5. **Çıktı dili** alanını seçin, **Planı incele** düğmesine basın, planı okuyun ve **Onayla ve başlat** düğmesine basın.

Çalışma **Çalışmalar** sayfasında görünür. Aynı anda tek çalışma yürür ve Local bir çalışma uzun sürebilir. Çalışmanın bitmesi her sorunun bulunduğu anlamına gelmez. Bulunanlara olduğu kadar reddedilenlere ve denetlenmeden kalanlara da bakın.

Sonuçlar `output/runs/` altında her çalışmanın kendi klasöründedir. `_run_summary.md` dosyası dizindir ve her belgenin ayrı bir klasörü vardır. İşe şu dosyalardan başlayın:

| Dosya | İçeriği |
|---|---|
| `reviewed_document.md` | Belgenizin tamamı, her bulgu ilgili yerinde |
| `document_summary.md` | Bulguların özeti |
| `review_findings.md` | Önerilen her değişiklik ve gerekçesi |
| `tracked_changes.docx` | Değişiklikler, izlenen değişiklikleri olan bir Word dosyası olarak |
| `review_data.json` | Öteki dosyaların dayandığı ana kayıt |

## Birkaç turlu bir müzakereyi inceleme

Çok turlu çalışma bir metnin art arda gelen sürümlerini sırayla okur. Vakayı bir vaka bildirimi dosyasında tanımlarsınız: turlar ve her turun belgeleri, taraflar, konular ve her tarafın tutumunu dile getiren metin parçaları. Alanların tamamı [girdi biçiminin](INPUT_FORMAT.md) 12. bölümünde.

**Gönder** sayfasında yukarıdaki gibi inceleme görevini ve Normal gizliliği seçin, sonra **Gelişmiş dosya alımı ve inceleme seçenekleri** bölümünü açın. **Çok turlu konum analizi (modellerle doğrulanmadı)** kutusunu işaretleyin ve bildirimi **Vaka bildirimi JSON (yalnızca çok turlu analiz)** alanına yapıştırın.

Böyle bir çalışma değişiklik önermez, iki dosya yazar:

- `version_changes.md`, sonraki her sürümün klasöründe: önceki sürümden bu yana neyin değiştiğini cümle cümle, tablolarda hücre hücre gösterir. Belgede olmayan bir maddeye ya da fıkraya yapılan atıfları da listeler. Hepsini Python yazar.
- `case_positions.md`, son turun klasöründe: tarafların her konudaki tutumunu gösterir. Bir tutumun öteki tarafa yaklaşıp yaklaşmadığı, bir modele sorulmadıkça `unknown` olarak kalır. Her satır onu Python'un mu modelin mi yazdığını söyler.

Eksiksiz bir örnek `benchmark/dev_cases/host_agreement_three_rounds/` klasöründe: üç tura yayılan kurgusal bir anlaşma. Metinler izlenen değişiklikleri olan Word dosyaları, heyetlerin notları Markdown. Bu yalnızca bir örnektir, Shimmer'ın ne kadar iyi çalıştığını kanıtlamaz.

## Bir bulguyu okuma

Aşağıdaki değişiklik önerisi aynı örnekten geliyor. Orada Ek II'deki bir tablonun toplamı artık tutmuyor. Çıktı dili İngilizce olduğu için metin İngilizcedir:

> Unit u16-annex-ii-annual-contribution-of-the-host (Annex II. Annual contribution of the host state) under rule CONV-005 (operator's id CONV-H05): the values under 'annual contribution' (1200000.0 + 400000.0 + 200000.0 + 300000.0 EUR) add up to 2100000.0 EUR, but the stated total annual contribution is 2200000.0 EUR. Computed in code from the figures in this unit, not judged by a model. Rule CONV-005 (operator's id CONV-H05); cited passage REF-0219.

Şu sırayla okuyun:

- **Birim** (`Unit`) bulgunun ilgili olduğu belge parçasıdır, çoğunlukla bir bölüm.
- **Kural** iki kez geçer. `CONV-005` Shimmer'ın verdiği numara, `CONV-H05` sizin verdiğiniz numaradır.
- **Sayılar** Python'undur, birimleriyle birlikte en başta gelir. Ardından bir modelin cümlesi geliyorsa tırnak içinde ve modelin adıyla verilir. Yalnızca o alıntı modelindir.
- **REF numarası**, örneğin `REF-0219`, bulgunun dayandığı metin parçasını gösterir. Konsolda üzerine basarak o parçayı okuyabilirsiniz.

Bulgu sizin denetleyeceğiniz bir öneridir, karar değildir. Çalışmanın hesaplamayı reddettiği yerlere ve denetlemeden bıraktığı kurallara da bakın. `reviewed_document.md` bunları açıkça yazar.

## Neyi Python hesaplar, neyi model yazar

| | Python'un hesapladığı | Modelin yazdığı |
|---|---|---|
| Kapsamı | Toplamlar, çarpımlar, aralıklar, eksik alanlar, önceki sürümden farklar | Python'un çözemediği her şey: sözcüklerin ne demek olduğu, iki metin parçasının çelişip çelişmediği gibi |
| Her seferinde aynı sonuç | Evet | Hayır, elle denetlenecek bir ipucu sayın |
| Değişiklik önerisine dönüşür mü | Evet | Asla |
| Nasıl anlarsınız | Python'un sayılarını ve kaynaklarını taşır | Şu işareti taşır: "Bir model tarafından yazıldı. Değişikliğe dönüştürülmedi. Python tarafından denetlenmedi." |

Local çalışmada Shimmer'ın hiçbir parçası internete çıkmaz. Her çalışma, modele yapılan her çağrının yanıtını kendi `audit/model_replies/` klasörüne kaydeder. Böylece modele ne sorulduğunu ve ne yanıt verdiğini görebilirsiniz.
