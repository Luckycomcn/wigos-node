// Display names for codelist concepts, per UI language.
//
// This is a DISPLAY layer only. `opt.label` is what goes into the WMDR2 record
// (see conceptFromOption in batch/common.js), so it must stay the WMO English
// wording: a record saved in Chinese has to read the same as one saved in
// English. Everything here is consulted at render time, by `codelistText()`.
//
// Three sources, in order:
//
//  1. `NAMES[scheme][notation][locale]` below — the closed lists a station
//     record cannot avoid (facility type, WMO region, reporting status...), plus
//     the units. Curated, small, reviewable.
//  2. Country and territory names, taken from Intl.DisplayNames in the active
//     locale. 416 of the 440 entries in ISO3166 + TerritoryName are plain
//     countries, so this covers them in all five languages without a word list.
//     The remaining WMO-local issuer codes (20000+ = WWW land-station, GAW,
//     GCW, ships, radar, space) have no ISO 3166 equivalent and need entries
//     here if they are to be translated.
//  3. Nothing: the English label is shown. This is deliberate for the large
//     observational codelists, where 348 of 961 labels are chemical formulae
//     and many more are Latin taxa — translating those would be wrong, not
//     missing.
//
// `NOSCHEME` holds notations that mean the same in every codelist.

import iso3166 from "./iso3166.json";

// ---------------------------------------------------------------------------
// 1. Curated names

// Shared by several schemes: the "no value" notations.
const NOSCHEME = {
  unknown: { "zh-CN": "未知", fr: "Inconnu", ru: "Неизвестно", ar: "غير معروف", es: "Desconocido" },
  inapplicable: { "zh-CN": "不适用", fr: "Sans objet", ru: "Неприменимо", ar: "لا ينطبق", es: "No aplicable" },
  missing: { "zh-CN": "缺失", fr: "Manquant", ru: "Отсутствует", ar: "مفقود", es: "Faltante" },
};

const NAMES = {
  FacilityType: {
    airFixed: { "zh-CN": "空中（固定）", es: "Aéreo (fijo)", fr: "Aérien (fixe)", ru: "Воздушный (стационарный)", ar: "جوي (ثابت)" },
    airMobile: { "zh-CN": "空中（移动）", es: "Aéreo (móvil)", fr: "Aérien (mobile)", ru: "Воздушный (подвижный)", ar: "جوي (متحرك)" },
    lakeRiverFixed: { "zh-CN": "湖/河（固定）", es: "Lago/río (fijo)", fr: "Lac/rivière (fixe)", ru: "Озеро/река (стационарный)", ar: "بحيرة/نهر (ثابت)" },
    lakeRiverMobile: { "zh-CN": "湖/河（移动）", es: "Lago/río (móvil)", fr: "Lac/rivière (mobile)", ru: "Озеро/река (подвижный)", ar: "بحيرة/نهر (متحرك)" },
    landFixed: { "zh-CN": "陆地（固定）", es: "Tierra (fijo)", fr: "Terre (fixe)", ru: "Наземный (стационарный)", ar: "بري (ثابت)" },
    landMobile: { "zh-CN": "陆地（移动）", es: "Tierra (móvil)", fr: "Terre (mobile)", ru: "Наземный (подвижный)", ar: "بري (متحرك)" },
    landOnIce: { "zh-CN": "陆地（冰上）", es: "Tierra (sobre hielo)", fr: "Terre (sur glace)", ru: "Наземный (на льду)", ar: "بري (على الجليد)" },
    seaFixed: { "zh-CN": "海上（固定）", es: "Mar (fijo)", fr: "Mer (fixe)", ru: "Морской (стационарный)", ar: "بحري (ثابت)" },
    seaMobile: { "zh-CN": "海上（移动）", es: "Mar (móvil)", fr: "Mer (mobile)", ru: "Морской (подвижный)", ar: "بحري (متحرك)" },
    seaOnIce: { "zh-CN": "海上（冰上）", es: "Mar (sobre hielo)", fr: "Mer (sur glace)", ru: "Морской (на льду)", ar: "بحري (على الجليد)" },
    spaceBased: { "zh-CN": "天基", es: "Espacial", fr: "Spatial", ru: "Космический", ar: "فضائي" },
    underwaterFixed: { "zh-CN": "水下（固定）", es: "Submarino (fijo)", fr: "Sous-marin (fixe)", ru: "Подводный (стационарный)", ar: "تحت الماء (ثابت)" },
    underwaterMobile: { "zh-CN": "水下（移动）", es: "Submarino (móvil)", fr: "Sous-marin (mobile)", ru: "Подводный (подвижный)", ar: "تحت الماء (متحرك)" },
  },
  WMORegion: {
    africa: { "zh-CN": "非洲", es: "África", fr: "Afrique", ru: "Африка", ar: "أفريقيا" },
    antarctica: { "zh-CN": "南极洲", es: "Antártida", fr: "Antarctique", ru: "Антарктика", ar: "أنتاركتيكا" },
    asia: { "zh-CN": "亚洲", es: "Asia", fr: "Asie", ru: "Азия", ar: "آسيا" },
    europe: { "zh-CN": "欧洲", es: "Europa", fr: "Europe", ru: "Европа", ar: "أوروبا" },
    northCentralAmericaCaribbean: {
      "zh-CN": "北美洲、中美洲和加勒比",
      es: "Norteamérica, Centroamérica y el Caribe",
      fr: "Amérique du Nord, Amérique centrale et Caraïbes",
      ru: "Северная Америка, Центральная Америка и Карибский бассейн",
      ar: "أمريكا الشمالية وأمريكا الوسطى ومنطقة الكاريبي",
    },
    southAmerica: { "zh-CN": "南美洲", es: "Sudamérica", fr: "Amérique du Sud", ru: "Южная Америка", ar: "أمريكا الجنوبية" },
    southWestPacific: { "zh-CN": "西南太平洋", es: "Pacífico sudoccidental", fr: "Pacifique sud-ouest", ru: "Юго-западная часть Тихого океана", ar: "جنوب غرب المحيط الهادئ" },
  },
  ReportingStatus: {
    closed: { "zh-CN": "已关闭", es: "Cerrada", fr: "Fermée", ru: "Закрыта", ar: "مغلقة" },
    nonReporting: { "zh-CN": "未上报", es: "Sin reporte", fr: "Non déclarante", ru: "Не передаёт данные", ar: "غير مُبلِّغة" },
    operational: { "zh-CN": "运行中", es: "Operativa", fr: "Opérationnelle", ru: "Действующая", ar: "تشغيلية" },
    partlyOperational: { "zh-CN": "部分运行", es: "Parcialmente operativa", fr: "Partiellement opérationnelle", ru: "Частично действующая", ar: "تشغيلية جزئياً" },
    planned: { "zh-CN": "计划中", es: "Planificada", fr: "Prévue", ru: "Планируемая", ar: "مخططة" },
    preOperational: { "zh-CN": "试运行", es: "Preoperativa", fr: "Préopérationnelle", ru: "Предэксплуатационная", ar: "قبل التشغيل" },
    standBy: { "zh-CN": "待命", es: "En espera", fr: "En veille", ru: "В режиме ожидания", ar: "في وضع الاستعداد" },
  },
  SourceOfObservation: {
    automaticReading: { "zh-CN": "仪器自动读数", es: "Lectura automática instrumental", fr: "Lecture automatique instrumentale", ru: "Автоматический приборный отсчёт", ar: "قراءة آلية بالأجهزة" },
    humanObservation: { "zh-CN": "人工观测", es: "Observación humana", fr: "Observation humaine", ru: "Визуальное наблюдение", ar: "ملاحظة بشرية" },
    manualReading: { "zh-CN": "仪器人工读数", es: "Lectura manual instrumental", fr: "Lecture manuelle instrumentale", ru: "Ручной приборный отсчёт", ar: "قراءة يدوية بالأجهزة" },
  },
  Geometry: {
    area: { "zh-CN": "面", es: "Área", fr: "Surface", ru: "Площадь", ar: "مساحة" },
    line: { "zh-CN": "线", es: "Línea", fr: "Ligne", ru: "Линия", ar: "خط" },
    point: { "zh-CN": "点", es: "Punto", fr: "Point", ru: "Точка", ar: "نقطة" },
    totalColumn: { "zh-CN": "总柱", es: "Columna total", fr: "Colonne totale", ru: "Общий столб", ar: "عمود كلي" },
    verticalProfile: { "zh-CN": "垂直廓线", es: "Perfil vertical", fr: "Profil vertical", ru: "Вертикальный профиль", ar: "مقطع رأسي" },
    volume: { "zh-CN": "体", es: "Volumen", fr: "Volume", ru: "Объём", ar: "حجم" },
  },
  ReferenceSurfaceType: {
    artificialGround: { "zh-CN": "人工地面", es: "Suelo artificial", fr: "Sol artificiel", ru: "Искусственная поверхность", ar: "أرض اصطناعية" },
    deck: { "zh-CN": "甲板", es: "Cubierta", fr: "Pont", ru: "Палуба", ar: "سطح السفينة" },
    naturalGround: { "zh-CN": "自然地面", es: "Suelo natural", fr: "Sol naturel", ru: "Естественная поверхность", ar: "أرض طبيعية" },
    roofTerrace: { "zh-CN": "屋顶或平台", es: "Tejado o terraza", fr: "Toit ou terrasse", ru: "Крыша или терраса", ar: "سطح أو شرفة" },
    seaSurface: { "zh-CN": "海面", es: "Superficie del mar", fr: "Surface de la mer", ru: "Поверхность моря", ar: "سطح البحر" },
  },
  InstrumentOperatingStatus: {
    inactive: { "zh-CN": "未使用 / 停用", es: "Fuera de servicio / inactivo", fr: "Hors service / inactif", ru: "Не используется / неактивен", ar: "خارج الخدمة / غير نشط" },
    operational: { "zh-CN": "运行中", es: "Operativo", fr: "Opérationnel", ru: "Действующий", ar: "تشغيلي" },
    testing: { "zh-CN": "测试 / 调试", es: "Pruebas / puesta en servicio", fr: "Essais / mise en service", ru: "Испытания / ввод в эксплуатацию", ar: "اختبار / تشغيل تجريبي" },
  },
  // Issuer codes that have no ISO 3166 equivalent: the WWW and programme
  // identifiers a WIGOS ID may be built on instead of a country.
  IssuerOfIdentifier: {
    "20000": { "zh-CN": "WWW 陆地台站（SI=0）", es: "Estación terrestre WWW (SI=0)", fr: "Station terrestre WWW (SI=0)", ru: "Наземная станция ВМО (SI=0)", ar: "محطة أرضية WWW (SI=0)" },
    "20001": { "zh-CN": "WWW 陆地台站（SI=1，复用标识）", es: "Estación terrestre WWW (SI=1, identificador reutilizado)", fr: "Station terrestre WWW (SI=1, identifiant réutilisé)", ru: "Наземная станция ВМО (SI=1, повторно используемый)", ar: "محطة أرضية WWW (SI=1، معرّف معاد استخدامه)" },
    "20002": { "zh-CN": "WWW 海上平台", es: "Plataforma marina WWW", fr: "Plateforme marine WWW", ru: "Морская платформа ВМО", ar: "منصة بحرية WWW" },
    "20003": { "zh-CN": "船舶（ITU 呼号）", es: "Buque (indicativo UIT)", fr: "Navire (indicatif UIT)", ru: "Судно (радиопозывной МСЭ)", ar: "سفينة (رمز نداء ITU)" },
    "20004": { "zh-CN": "船舶（国家编号）", es: "Buque (ID nacional)", fr: "Navire (ID national)", ru: "Судно (национальный номер)", ar: "سفينة (معرّف وطني)" },
    "20005": { "zh-CN": "AMDAR 航空器", es: "Aeronave AMDAR", fr: "Aéronef AMDAR", ru: "Воздушное судно AMDAR", ar: "طائرة AMDAR" },
    "20006": { "zh-CN": "ICAO 机场", es: "Aeródromo OACI", fr: "Aérodrome OACI", ru: "Аэродром ИКАО", ar: "مطار ICAO" },
    "20007": { "zh-CN": "IMO 船舶编号", es: "Número de buque OMI", fr: "Numéro de navire OMI", ru: "Номер судна ИМО", ar: "رقم سفينة IMO" },
    "20008": { "zh-CN": "GAW 台站", es: "Estación GAW", fr: "Station GAW", ru: "Станция ГСА", ar: "محطة GAW" },
    "20009": { "zh-CN": "WMO 空间计划", es: "Programa espacial de la OMM", fr: "Programme spatial de l'OMM", ru: "Космическая программа ВМО", ar: "برنامج الفضاء التابع للمنظمة" },
    "20010": { "zh-CN": "WMO 天气雷达", es: "Radar meteorológico de la OMM", fr: "Radar météorologique de l'OMM", ru: "Метеорологический радиолокатор ВМО", ar: "رادار الطقس التابع للمنظمة" },
    "21000": { "zh-CN": "GCW 台站", es: "Estación GCW", fr: "Station GCW", ru: "Станция GCW", ar: "محطة GCW" },
    "21009": { "zh-CN": "WMO 空间计划（卫星）", es: "Programa espacial de la OMM (satélite)", fr: "Programme spatial de l'OMM (satellite)", ru: "Космическая программа ВМО (спутник)", ar: "برنامج الفضاء (ساتل)" },
    "21010": { "zh-CN": "WRD 台站", es: "Estación WRD", fr: "Station WRD", ru: "Станция WRD", ar: "محطة WRD" },
    "21011": { "zh-CN": "ABO-MR 航空器", es: "Aeronave ABO-MR", fr: "Aéronef ABO-MR", ru: "Воздушное судно ABO-MR", ar: "طائرة ABO-MR" },
    "21016": { "zh-CN": "WHOS 台站", es: "Estación WHOS", fr: "Station WHOS", ru: "Станция WHOS", ar: "محطة WHOS" },
    "22000": { "zh-CN": "GOOS/OceanOPS 海洋系统", es: "Sistema marino GOOS/OceanOPS", fr: "Système marin GOOS/OceanOPS", ru: "Морская система GOOS/OceanOPS", ar: "نظام بحري GOOS/OceanOPS" },
    "22001": { "zh-CN": "GRUAN 台站", es: "Estación GRUAN", fr: "Station GRUAN", ru: "Станция GRUAN", ar: "محطة GRUAN" },
    "23000": { "zh-CN": "CTBTO 台站", es: "Estación CTBTO", fr: "Station CTBTO", ru: "Станция CTBTO", ar: "محطة CTBTO" },
    "23001": { "zh-CN": "Copernicus-C3S 台站", es: "Estación Copernicus-C3S", fr: "Station Copernicus-C3S", ru: "Станция Copernicus-C3S", ar: "محطة Copernicus-C3S" },
  },
};

// ---------------------------------------------------------------------------
// 2. Units
//
// 286 entries, but they are compositional: 179 are "<unit> per <unit>" and most
// of the rest is a single unit word, so the vocabulary is ~200 words rather
// than 286 sentences. Words are translated once, plurals folded onto the
// singular, and "per" becomes 每 / par / на / لكل / por.
const UNIT_WORDS = {
  "metric ton": { "zh-CN": "吨", es: "tonelada", fr: "tonne", ru: "тонна", ar: "طن" },
  ton: { "zh-CN": "吨", es: "tonelada", fr: "tonne", ru: "тонна", ar: "طن" },
  tonne: { "zh-CN": "吨", es: "tonelada", fr: "tonne", ru: "тонна", ar: "طن" },
  metre: { "zh-CN": "米", es: "metro", fr: "mètre", ru: "метр", ar: "متر" },
  metre__plural: { "zh-CN": "米", es: "metros", fr: "mètres", ru: "метры", ar: "أمتار" },
  kilometre: { "zh-CN": "千米", es: "kilómetro", fr: "kilomètre", ru: "километр", ar: "كيلومتر" },
  kilometre__plural: { "zh-CN": "千米", es: "kilómetros", fr: "kilomètres", ru: "километры", ar: "كيلومترات" },
  centimetre: { "zh-CN": "厘米", es: "centímetro", fr: "centimètre", ru: "сантиметр", ar: "سنتيمتر" },
  centimetre__plural: { "zh-CN": "厘米", es: "centímetros", fr: "centimètres", ru: "сантиметры", ar: "سنتيمترات" },
  millimetre: { "zh-CN": "毫米", es: "milímetro", fr: "millimètre", ru: "миллиметр", ar: "مليمتر" },
  millimetre__plural: { "zh-CN": "毫米", es: "milímetros", fr: "millimètres", ru: "миллиметры", ar: "مليمترات" },
  micrometre: { "zh-CN": "微米", es: "micrómetro", fr: "micromètre", ru: "микрометр", ar: "ميكرومتر" },
  nanometre: { "zh-CN": "纳米", es: "nanómetro", fr: "nanomètre", ru: "нанометр", ar: "نانومتر" },
  decimetre: { "zh-CN": "分米", es: "decímetro", fr: "décimètre", ru: "дециметр", ar: "دسيمتر" },
  "geopotential metre": { "zh-CN": "位势米", es: "metro geopotencial", fr: "mètre géopotentiel", ru: "геопотенциальный метр", ar: "متر جهدي" },
  "nautical mile": { "zh-CN": "海里", es: "milla náutica", fr: "mille marin", ru: "морская миля", ar: "ميل بحري" },
  foot: { "zh-CN": "英尺", es: "pie", fr: "pied", ru: "фут", ar: "قدم" },
  inch: { "zh-CN": "英寸", es: "pulgada", fr: "pouce", ru: "дюйм", ar: "بوصة" },
  "square metre": { "zh-CN": "平方米", es: "metro cuadrado", fr: "mètre carré", ru: "квадратный метр", ar: "متر مربع" },
  "square metre__plural": { "zh-CN": "平方米", es: "metros cuadrados", fr: "mètres carrés", ru: "квадратные метры", ar: "أمتار مربعة" },
  "square centimetre": { "zh-CN": "平方厘米", es: "centímetro cuadrado", fr: "centimètre carré", ru: "квадратный сантиметр", ar: "سنتيمتر مربع" },
  "cubic metre": { "zh-CN": "立方米", es: "metro cúbico", fr: "mètre cube", ru: "кубический метр", ar: "متر مكعب" },
  "cubic metre__plural": { "zh-CN": "立方米", es: "metros cúbicos", fr: "mètres cubes", ru: "кубические метры", ar: "أمتار مكعبة" },
  "cubic centimetre": { "zh-CN": "立方厘米", es: "centímetro cúbico", fr: "centimètre cube", ru: "кубический сантиметр", ar: "سنتيمتر مكعب" },
  "cubic millimetre": { "zh-CN": "立方毫米", es: "milímetro cúbico", fr: "millimètre cube", ru: "кубический миллиметр", ar: "مليمتر مكعب" },
  "cubic micrometre": { "zh-CN": "立方微米", es: "micrómetro cúbico", fr: "micromètre cube", ru: "кубический микрометр", ar: "ميكرومتر مكعب" },
  "cubic metre at 20 degrees": { "zh-CN": "20 °C 下的立方米", es: "metro cúbico a 20 grados", fr: "mètre cube à 20 degrés", ru: "кубический метр при 20 °C", ar: "متر مكعب عند 20 درجة" },
  "cubic metre at 25 degrees": { "zh-CN": "25 °C 下的立方米", es: "metro cúbico a 25 grados", fr: "mètre cube à 25 degrés", ru: "кубический метр при 25 °C", ar: "متر مكعب عند 25 درجة" },
  litre: { "zh-CN": "升", es: "litro", fr: "litre", ru: "литр", ar: "لتر" },
  millilitre: { "zh-CN": "毫升", es: "mililitro", fr: "millilitre", ru: "миллилитр", ar: "مليلتر" },
  hectare: { "zh-CN": "公顷", es: "hectárea", fr: "hectare", ru: "гектар", ar: "هكتار" },
  second: { "zh-CN": "秒", es: "segundo", fr: "seconde", ru: "секунда", ar: "ثانية" },
  "second__plural": { "zh-CN": "秒", es: "segundos", fr: "secondes", ru: "секунды", ar: "ثوانٍ" },
  minute: { "zh-CN": "分", es: "minuto", fr: "minute", ru: "минута", ar: "دقيقة" },
  hour: { "zh-CN": "小时", es: "hora", fr: "heure", ru: "час", ar: "ساعة" },
  day: { "zh-CN": "天", es: "día", fr: "jour", ru: "сутки", ar: "يوم" },
  week: { "zh-CN": "周", es: "semana", fr: "semaine", ru: "неделя", ar: "أسبوع" },
  month: { "zh-CN": "月", es: "mes", fr: "mois", ru: "месяц", ar: "شهر" },
  year: { "zh-CN": "年", es: "año", fr: "an", ru: "год", ar: "سنة" },
  gram: { "zh-CN": "克", es: "gramo", fr: "gramme", ru: "грамм", ar: "غرام" },
  "gram__plural": { "zh-CN": "克", es: "gramos", fr: "grammes", ru: "граммы", ar: "غرامات" },
  kilogram: { "zh-CN": "千克", es: "kilogramo", fr: "kilogramme", ru: "килограмм", ar: "كيلوغرام" },
  "kilogram__plural": { "zh-CN": "千克", es: "kilogramos", fr: "kilogrammes", ru: "килограммы", ar: "كيلوغرامات" },
  milligram: { "zh-CN": "毫克", es: "miligramo", fr: "milligramme", ru: "миллиграмм", ar: "ميليغرام" },
  "milligram__plural": { "zh-CN": "毫克", es: "miligramos", fr: "milligrammes", ru: "миллиграммы", ar: "ميليغرامات" },
  microgram: { "zh-CN": "微克", es: "microgramo", fr: "microgramme", ru: "микрограмм", ar: "ميكروغرام" },
  "microgram__plural": { "zh-CN": "微克", es: "microgramos", fr: "microgrammes", ru: "микрограммы", ar: "ميكروغرامات" },
  nanogram: { "zh-CN": "纳克", es: "nanogramo", fr: "nanogramme", ru: "нанограмм", ar: "نانوغرام" },
  "nanogram__plural": { "zh-CN": "纳克", es: "nanogramos", fr: "nanogrammes", ru: "нанограммы", ar: "نانوغرامات" },
  "microgram C": { "zh-CN": "微克碳", es: "microgramo de C", fr: "microgramme de C", ru: "микрограмм C", ar: "ميكروغرام كربون" },
  "microgram N": { "zh-CN": "微克氮", es: "microgramo de N", fr: "microgramme de N", ru: "микрограмм N", ar: "ميكروغرام نيتروجين" },
  "microgram S": { "zh-CN": "微克硫", es: "microgramo de S", fr: "microgramme de S", ru: "микрограмм S", ar: "ميكروغرام كبريت" },
  "microgram CI": { "zh-CN": "微克氯", es: "microgramo de Cl", fr: "microgramme de Cl", ru: "микрограмм Cl", ar: "ميكروغرام كلور" },
  "milligram N": { "zh-CN": "毫克氮", es: "miligramo de N", fr: "milligramme de N", ru: "миллиграмм N", ar: "ميليغرام نيتروجين" },
  "milligram S": { "zh-CN": "毫克硫", es: "miligramo de S", fr: "milligramme de S", ru: "миллиграмм S", ar: "ميليغرام كبريت" },
  kelvin: { "zh-CN": "开尔文", es: "kelvin", fr: "kelvin", ru: "кельвин", ar: "كلفن" },
  "kelvin__plural": { "zh-CN": "开尔文", es: "kelvins", fr: "kelvins", ru: "кельвины", ar: "كلفنات" },
  mole: { "zh-CN": "摩尔", es: "mol", fr: "mole", ru: "моль", ar: "مول" },
  "mole__plural": { "zh-CN": "摩尔", es: "moles", fr: "moles", ru: "моли", ar: "مولات" },
  millimole: { "zh-CN": "毫摩尔", es: "milimol", fr: "millimole", ru: "миллимоль", ar: "ميليمول" },
  "millimole__plural": { "zh-CN": "毫摩尔", es: "milimoles", fr: "millimoles", ru: "миллимоли", ar: "ميليمولات" },
  micromole: { "zh-CN": "微摩尔", es: "micromol", fr: "micromole", ru: "микромоль", ar: "ميكرومول" },
  "micromole__plural": { "zh-CN": "微摩尔", es: "micromoles", fr: "micromoles", ru: "микромоли", ar: "ميكرومولات" },
  nanomole: { "zh-CN": "纳摩尔", es: "nanomol", fr: "nanomole", ru: "наномоль", ar: "نانومول" },
  "nanomole__plural": { "zh-CN": "纳摩尔", es: "nanomoles", fr: "nanomoles", ru: "наномоли", ar: "نانومولات" },
  picomole: { "zh-CN": "皮摩尔", es: "picomol", fr: "picomole", ru: "пикомоль", ar: "بيكومول" },
  "picomole__plural": { "zh-CN": "皮摩尔", es: "picomoles", fr: "picomoles", ru: "пикомоли", ar: "بيكومولات" },
  femtomole: { "zh-CN": "飞摩尔", es: "femtomol", fr: "femtomole", ru: "фемтомоль", ar: "فيمتومول" },
  ampere: { "zh-CN": "安培", es: "amperio", fr: "ampère", ru: "ампер", ar: "أمبير" },
  candela: { "zh-CN": "坎德拉", es: "candela", fr: "candela", ru: "кандела", ar: "شمعة" },
  coulomb: { "zh-CN": "库仑", es: "culombio", fr: "coulomb", ru: "кулон", ar: "كولوم" },
  farad: { "zh-CN": "法拉", es: "faradio", fr: "farad", ru: "фарад", ar: "فاراد" },
  gray: { "zh-CN": "戈瑞", es: "gray", fr: "gray", ru: "грей", ar: "غراي" },
  henry: { "zh-CN": "亨利", es: "henrio", fr: "henry", ru: "генри", ar: "هنري" },
  hertz: { "zh-CN": "赫兹", es: "hercio", fr: "hertz", ru: "герц", ar: "هرتز" },
  joule: { "zh-CN": "焦耳", es: "julio", fr: "joule", ru: "джоуль", ar: "جول" },
  "joule__plural": { "zh-CN": "焦耳", es: "julios", fr: "joules", ru: "джоули", ar: "جولات" },
  lumen: { "zh-CN": "流明", es: "lumen", fr: "lumen", ru: "люмен", ar: "لومن" },
  lux: { "zh-CN": "勒克斯", es: "lux", fr: "lux", ru: "люкс", ar: "لوكس" },
  newton: { "zh-CN": "牛顿", es: "newton", fr: "newton", ru: "ньютон", ar: "نيوتن" },
  "newton__plural": { "zh-CN": "牛顿", es: "newtons", fr: "newtons", ru: "ньютоны", ar: "نيوتنات" },
  ohm: { "zh-CN": "欧姆", es: "ohmio", fr: "ohm", ru: "ом", ar: "أوم" },
  parsec: { "zh-CN": "秒差距", es: "pársec", fr: "parsec", ru: "парсек", ar: "فرسخ فلكي" },
  pascal: { "zh-CN": "帕斯卡", es: "pascal", fr: "pascal", ru: "паскаль", ar: "باسكال" },
  "pascal__plural": { "zh-CN": "帕斯卡", es: "pascales", fr: "pascals", ru: "паскали", ar: "باسكال" },
  radian: { "zh-CN": "弧度", es: "radián", fr: "radian", ru: "радиан", ar: "راديان" },
  "radian__plural": { "zh-CN": "弧度", es: "radianes", fr: "radians", ru: "радианы", ar: "راديانات" },
  siemens: { "zh-CN": "西门子", es: "siemens", fr: "siemens", ru: "сименс", ar: "سيمنز" },
  sievert: { "zh-CN": "希沃特", es: "sievert", fr: "sievert", ru: "зиверт", ar: "سيفرت" },
  steradian: { "zh-CN": "球面度", es: "estereorradián", fr: "stéradian", ru: "стерадиан", ar: "ستراديان" },
  tesla: { "zh-CN": "特斯拉", es: "tesla", fr: "tesla", ru: "тесла", ar: "تسلا" },
  volt: { "zh-CN": "伏特", es: "voltio", fr: "volt", ru: "вольт", ar: "فولت" },
  "volt squared": { "zh-CN": "伏特平方", es: "voltio al cuadrado", fr: "volt au carré", ru: "вольт в квадрате", ar: "فولت مربع" },
  watt: { "zh-CN": "瓦特", es: "vatio", fr: "watt", ru: "ватт", ar: "واط" },
  "watt__plural": { "zh-CN": "瓦特", es: "vatios", fr: "watts", ru: "ватты", ar: "واط" },
  weber: { "zh-CN": "韦伯", es: "weber", fr: "weber", ru: "вебер", ar: "ويبر" },
  becquerel: { "zh-CN": "贝可勒尔", es: "bequerelio", fr: "becquerel", ru: "беккерель", ar: "بيكريل" },
  "becquerel__plural": { "zh-CN": "贝可勒尔", es: "bequerelios", fr: "becquerels", ru: "беккерели", ar: "بيكريل" },
  "becquerel second": { "zh-CN": "贝可勒尔·秒", es: "bequerelio segundo", fr: "becquerel seconde", ru: "беккерель·секунда", ar: "بيكريل ثانية" },
  "becquerel seconds": { "zh-CN": "贝可勒尔·秒", es: "bequerelios segundo", fr: "becquerels secondes", ru: "беккерель·секунды", ar: "بيكريل ثوانٍ" },
  millibecquerel: { "zh-CN": "毫贝可勒尔", es: "milibequerelio", fr: "millibecquerel", ru: "миллибеккерель", ar: "ميليبيكريل" },
  "millibecquerel__plural": { "zh-CN": "毫贝可勒尔", es: "milibequerelios", fr: "millibecquerels", ru: "миллибеккерели", ar: "ميليبيكريل" },
  "degree Celsius": { "zh-CN": "摄氏度", es: "grado Celsius", fr: "degré Celsius", ru: "градус Цельсия", ar: "درجة مئوية" },
  "degree Celsius (°C)": { "zh-CN": "摄氏度（°C）", es: "grado Celsius (°C)", fr: "degré Celsius (°C)", ru: "градус Цельсия (°C)", ar: "درجة مئوية (°C)" },
  "degrees Celsius": { "zh-CN": "摄氏度", es: "grados Celsius", fr: "degrés Celsius", ru: "градуса Цельсия", ar: "درجات مئوية" },
  degree: { "zh-CN": "度", es: "grado", fr: "degré", ru: "градус", ar: "درجة" },
  "degree__plural": { "zh-CN": "度", es: "grados", fr: "degrés", ru: "градусы", ar: "درجات" },
  "degree (angle)": { "zh-CN": "度（角度）", es: "grado (ángulo)", fr: "degré (angle)", ru: "градус (угол)", ar: "درجة (زاوية)" },
  "degrees true": { "zh-CN": "真方位度", es: "grados verdaderos", fr: "degrés vrais", ru: "градусы истинные", ar: "درجات حقيقية" },
  "second (angle)": { "zh-CN": "秒（角度）", es: "segundo (ángulo)", fr: "seconde (angle)", ru: "секунда (угол)", ar: "ثانية (زاوية)" },
  "minute (angle)": { "zh-CN": "分（角度）", es: "minuto (ángulo)", fr: "minute (angle)", ru: "минута (угол)", ar: "دقيقة (زاوية)" },
  "minute (time)": { "zh-CN": "分（时间）", es: "minuto (tiempo)", fr: "minute (temps)", ru: "минута (время)", ar: "دقيقة (زمن)" },
  "square degree (angle)": { "zh-CN": "平方度（角度）", es: "grado cuadrado (ángulo)", fr: "degré carré (angle)", ru: "квадратный градус (угол)", ar: "درجة مربعة (زاوية)" },
  "per cent": { "zh-CN": "百分比", es: "por ciento", fr: "pour cent", ru: "процент", ar: "بالمئة" },
  "per mille": { "zh-CN": "千分比", es: "por mil", fr: "pour mille", ru: "промилле", ar: "بالألف" },
  "parts per thousand": { "zh-CN": "千分率", es: "partes por mil", fr: "parties par millier", ru: "промилле", ar: "أجزاء بالألف" },
  "parts per million": { "zh-CN": "百万分率", es: "partes por millón", fr: "parties par million", ru: "миллионные доли", ar: "أجزاء بالمليون" },
  "parts per billion": { "zh-CN": "十亿分率", es: "partes por mil millones", fr: "parties par milliard", ru: "миллиардные доли", ar: "أجزاء بالمليار" },
  "parts per trillion": { "zh-CN": "万亿分率", es: "partes por billón", fr: "parties par billion", ru: "триллионные доли", ar: "أجزاء بالتريليون" },
  parts: { "zh-CN": "份", es: "partes", fr: "parties", ru: "части", ar: "أجزاء" },
  "million by volume": { "zh-CN": "百万分体积比", es: "millón por volumen", fr: "million par volume", ru: "миллионная доля по объёму", ar: "مليون بالحجم" },
  "billion by volume": { "zh-CN": "十亿分体积比", es: "mil millones por volumen", fr: "milliard par volume", ru: "миллиардная доля по объёму", ar: "مليار بالحجم" },
  "trillion by volume": { "zh-CN": "万亿分体积比", es: "billón por volumen", fr: "billion par volume", ru: "триллионная доля по объёму", ar: "تريليون بالحجم" },
  dimensionless: { "zh-CN": "无量纲", es: "adimensional", fr: "sans dimension", ru: "безразмерный", ar: "بلا أبعاد" },
  thousand: { "zh-CN": "千", es: "mil", fr: "mille", ru: "тысяча", ar: "ألف" },
  knot: { "zh-CN": "节", es: "nudo", fr: "nœud", ru: "узел", ar: "عقدة" },
  "knot__plural": { "zh-CN": "节", es: "nudos", fr: "nœuds", ru: "узлы", ar: "عقد" },
  bar: { "zh-CN": "巴", es: "bar", fr: "bar", ru: "бар", ar: "بار" },
  millibar: { "zh-CN": "毫巴", es: "milibar", fr: "millibar", ru: "миллибар", ar: "ميليبار" },
  nanobar: { "zh-CN": "纳巴", es: "nanobar", fr: "nanobar", ru: "нанобар", ar: "نانوبار" },
  centibar: { "zh-CN": "厘巴", es: "centibar", fr: "centibar", ru: "сантибар", ar: "سنتيبار" },
  "centibar__plural": { "zh-CN": "厘巴", es: "centibares", fr: "centibars", ru: "сантибары", ar: "سنتيبار" },
  decibar: { "zh-CN": "分巴", es: "decibar", fr: "décibar", ru: "децибар", ar: "دسيبار" },
  hectopascal: { "zh-CN": "百帕", es: "hectopascal", fr: "hectopascal", ru: "гектопаскаль", ar: "هكتوباسكال" },
  "hectopascal__plural": { "zh-CN": "百帕", es: "hectopascales", fr: "hectopascals", ru: "гектопаскали", ar: "هكتوباسكال" },
  kilopascal: { "zh-CN": "千帕", es: "kilopascal", fr: "kilopascal", ru: "килопаскаль", ar: "كيلوباسكال" },
  decipascal: { "zh-CN": "分帕", es: "decipascal", fr: "décipascal", ru: "деципаскаль", ar: "دسيباسكال" },
  "decipascal__plural": { "zh-CN": "分帕", es: "decipascales", fr: "décipascals", ru: "деципаскали", ar: "دسيباسكال" },
  dekapascal: { "zh-CN": "十帕", es: "decapascal", fr: "décapascal", ru: "декапаскаль", ar: "ديكاباسكال" },
  hertz_plural: { "zh-CN": "赫兹", es: "hercios", fr: "hertz", ru: "герцы", ar: "هرتز" },
  kilohertz: { "zh-CN": "千赫兹", es: "kilohercio", fr: "kilohertz", ru: "килогерц", ar: "كيلوهرتز" },
  megahertz: { "zh-CN": "兆赫兹", es: "megahercio", fr: "mégahertz", ru: "мегагерц", ar: "ميغاهرتز" },
  gigahertz: { "zh-CN": "吉赫兹", es: "gigahercio", fr: "gigahertz", ru: "гигагерц", ar: "غيغاهرتز" },
  terahertz: { "zh-CN": "太赫兹", es: "terahercio", fr: "térahertz", ru: "терагерц", ar: "تيراهرتز" },
  decibel: { "zh-CN": "分贝", es: "decibelio", fr: "décibel", ru: "децибел", ar: "ديسيبل" },
  "decibel__plural": { "zh-CN": "分贝", es: "decibelios", fr: "décibels", ru: "децибелы", ar: "ديسيبل" },
  "Radar reflectivity in decibel": { "zh-CN": "雷达反射率（分贝）", es: "Reflectividad radar en decibelios", fr: "Réflectivité radar en décibels", ru: "Радиолокационная отражаемость в децибелах", ar: "انعكاسية الرادار بالديسيبل" },
  "electron volt": { "zh-CN": "电子伏特", es: "electronvoltio", fr: "électronvolt", ru: "электронвольт", ar: "إلكترون فولت" },
  "astronomical unit": { "zh-CN": "天文单位", es: "unidad astronómica", fr: "unité astronomique", ru: "астрономическая единица", ar: "وحدة فلكية" },
  "unified atomic mass unit": { "zh-CN": "统一原子质量单位", es: "unidad de masa atómica unificada", fr: "unité de masse atomique unifiée", ru: "унифицированная атомная единица массы", ar: "وحدة كتلة ذرية موحدة" },
  "acceleration due to gravity": { "zh-CN": "重力加速度", es: "aceleración debida a la gravedad", fr: "accélération due à la gravité", ru: "ускорение свободного падения", ar: "تسارع الجاذبية" },
  "standard acceleration due to gravity": { "zh-CN": "标准重力加速度", es: "aceleración estándar debida a la gravedad", fr: "accélération standard due à la gravité", ru: "стандартное ускорение свободного падения", ar: "تسارع الجاذبية القياسي" },
  "milligal": { "zh-CN": "毫伽", es: "miligal", fr: "milligal", ru: "миллигал", ar: "ميليغال" },
  "millimetre of mercury": { "zh-CN": "毫米汞柱", es: "milímetro de mercurio", fr: "millimètre de mercure", ru: "миллиметр ртутного столба", ar: "مليمتر زئبق" },
  "Dobson Unit": { "zh-CN": "多布森单位", es: "unidad Dobson", fr: "unité Dobson", ru: "единица Добсона", ar: "وحدة دوبسون" },
  "Eötvös": { "zh-CN": "厄特沃什", es: "Eötvös", fr: "Eötvös", ru: "Этвёш", ar: "إيوتفوش" },
  "Hazen unit": { "zh-CN": "哈曾色度单位", es: "unidad Hazen", fr: "unité Hazen", ru: "единица Хазена", ar: "وحدة هازن" },
  "N units": { "zh-CN": "N 单位", es: "unidades N", fr: "unités N", ru: "единицы N", ar: "وحدات N" },
  "Potential Vorticity Unit": { "zh-CN": "位涡单位", es: "unidad de vorticidad potencial", fr: "unité de vorticité potentielle", ru: "единица потенциальной завихрённости", ar: "وحدة الدوامة الكامنة" },
  "pH unit": { "zh-CN": "pH 单位", es: "unidad de pH", fr: "unité de pH", ru: "единица pH", ar: "وحدة pH" },
  "practical salinity unit": { "zh-CN": "实用盐度单位", es: "unidad práctica de salinidad", fr: "unité pratique de salinité", ru: "практическая единица солёности", ar: "وحدة ملوحة عملية" },
  "nephelometric turbidity unit": { "zh-CN": "散射浊度单位", es: "unidad nefelométrica de turbidez", fr: "unité néphélométrique de turbidité", ru: "нефелометрическая единица мутности", ar: "وحدة عكورة نيفيلومترية" },
  "colony-forming unit": { "zh-CN": "菌落形成单位", es: "unidad formadora de colonias", fr: "unité formant colonie", ru: "колониеобразующая единица", ar: "وحدة مكوّنة للمستعمرات" },
  "most probable number index number in 1 millilitre": { "zh-CN": "每毫升最大可能数指数", es: "número más probable por mililitro", fr: "nombre le plus probable par millilitre", ru: "наиболее вероятное число в 1 мл", ar: "العدد الأكثر احتمالاً في 1 مل" },
  "eights of sky covered by cloud": { "zh-CN": "云量（八分制）", es: "octavos de cielo cubierto", fr: "huitièmes de ciel couvert", ru: "восьмые доли покрытия неба", ar: "أثمان السماء المغطاة" },
  "kilocalory": { "zh-CN": "千卡", es: "kilocaloría", fr: "kilocalorie", ru: "килокалория", ar: "كيلوكالوري" },
  "microsiemens": { "zh-CN": "微西门子", es: "microsiemens", fr: "microsiemens", ru: "микросименс", ar: "ميكروسيمنز" },
  "millisiemens": { "zh-CN": "毫西门子", es: "milisiemens", fr: "millisiemens", ru: "миллисименс", ar: "ميليسيمنز" },
  "millisievert": { "zh-CN": "毫希沃特", es: "milisievert", fr: "millisievert", ru: "миллизиверт", ar: "ميليسيفرت" },
  "millivolt": { "zh-CN": "毫伏", es: "milivoltio", fr: "millivolt", ru: "милливольт", ar: "ميليفولت" },
  "nanotesla squared": { "zh-CN": "纳特斯拉平方", es: "nanotesla al cuadrado", fr: "nanotesla au carré", ru: "нанотесла в квадрате", ar: "نانوتسلا مربع" },
  "picotesla squared": { "zh-CN": "皮特斯拉平方", es: "picotesla al cuadrado", fr: "picotesla au carré", ru: "пикотесла в квадрате", ar: "بيكوتسلا مربع" },
  "metre squared": { "zh-CN": "米的平方", es: "metro al cuadrado", fr: "mètre au carré", ru: "метр в квадрате", ar: "متر مربع" },
  "metre to the fourth power": { "zh-CN": "米的四次方", es: "metro a la cuarta potencia", fr: "mètre à la puissance quatre", ru: "метр в четвёртой степени", ar: "متر للقوة الرابعة" },
  "metre to the two thirds power": { "zh-CN": "米的二分之三次方", es: "metro a la potencia dos tercios", fr: "mètre à la puissance deux tiers", ru: "метр в степени две трети", ar: "متر للقوة ثلثين" },
  "metres to the two thirds power": { "zh-CN": "米的二分之三次方", es: "metros a la potencia dos tercios", fr: "mètres à la puissance deux tiers", ru: "метры в степени две трети", ar: "أمتار للقوة ثلثين" },
  "millimetre to the sixth power": { "zh-CN": "毫米的六次方", es: "milímetro a la sexta potencia", fr: "millimètre à la puissance six", ru: "миллиметр в шестой степени", ar: "مليمتر للقوة السادسة" },
  "millimetres to the sixth power": { "zh-CN": "毫米的六次方", es: "milímetros a la sexta potencia", fr: "millimètres à la puissance six", ru: "миллиметры в шестой степени", ar: "مليمترات للقوة السادسة" },
  "inverse centimetre": { "zh-CN": "每厘米", es: "centímetro inverso", fr: "centimètre inverse", ru: "обратный сантиметр", ar: "سنتيمتر معكوس" },
  "inverse metre": { "zh-CN": "每米", es: "metro inverso", fr: "mètre inverse", ru: "обратный метр", ar: "متر معكوس" },
  "kelvin metre": { "zh-CN": "开尔文·米", es: "kelvin metro", fr: "kelvin mètre", ru: "кельвин·метр", ar: "كلفن متر" },
  "kelvin metres": { "zh-CN": "开尔文·米", es: "kelvin metros", fr: "kelvin mètres", ru: "кельвин·метры", ar: "كلفن أمتار" },
  "kelvin square metre": { "zh-CN": "开尔文·平方米", es: "kelvin metro cuadrado", fr: "kelvin mètre carré", ru: "кельвин·квадратный метр", ar: "كلفن متر مربع" },
  "kelvin square metres": { "zh-CN": "开尔文·平方米", es: "kelvin metros cuadrados", fr: "kelvin mètres carrés", ru: "кельвин·квадратные метры", ar: "كلفن أمتار مربعة" },
  "radian second": { "zh-CN": "弧度·秒", es: "radián segundo", fr: "radian seconde", ru: "радиан·секунда", ar: "راديان ثانية" },
  "square metre second": { "zh-CN": "平方米·秒", es: "metro cuadrado segundo", fr: "mètre carré seconde", ru: "квадратный метр·секунда", ar: "متر مربع ثانية" },
  "square metres second": { "zh-CN": "平方米·秒", es: "metros cuadrados segundo", fr: "mètres carrés seconde", ru: "квадратные метры·секунда", ar: "أمتار مربعة ثانية" },
  "square second": { "zh-CN": "秒的平方", es: "segundo al cuadrado", fr: "seconde au carré", ru: "секунда в квадрате", ar: "ثانية مربعة" },
  "second squared": { "zh-CN": "秒的平方", es: "segundo al cuadrado", fr: "seconde au carré", ru: "секунда в квадрате", ar: "ثانية مربعة" },
  "square kilogram": { "zh-CN": "平方千克", es: "kilogramo al cuadrado", fr: "kilogramme au carré", ru: "квадратный килограмм", ar: "كيلوغرام مربع" },
  megametre: { "zh-CN": "兆米", es: "megámetro", fr: "mégamètre", ru: "мегаметр", ar: "ميغامتر" },
  microbar: { "zh-CN": "微巴", es: "microbar", fr: "microbar", ru: "микробар", ar: "ميكروبار" },
  "per second squared": { "zh-CN": "每秒平方", es: "por segundo al cuadrado", fr: "par seconde au carré", ru: "в секунду в квадрате", ar: "لكل ثانية مربعة" },
  "per square kilogram": { "zh-CN": "每平方千克", es: "por kilogramo al cuadrado", fr: "par kilogramme au carré", ru: "на квадратный килограмм", ar: "لكل كيلوغرام مربع" },
  "per meg": { "zh-CN": "每兆", es: "por mega", fr: "par méga", ru: "на мега", ar: "لكل ميغا" },
  "per megametre": { "zh-CN": "每兆米", es: "por megámetro", fr: "par mégamètre", ru: "на мегаметр", ar: "لكل ميغامتر" },
  "steradian centimetre": { "zh-CN": "球面度·厘米", es: "estereorradián centímetro", fr: "stéradian centimètre", ru: "стерадиан·сантиметр", ar: "ستراديان سنتيمتر" },
  "steradian metre": { "zh-CN": "球面度·米", es: "estereorradián metro", fr: "stéradian mètre", ru: "стерадиан·метр", ar: "ستراديان متر" },
  "100 metres": { "zh-CN": "100 米", es: "100 metros", fr: "100 mètres", ru: "100 метров", ar: "100 متر" },
  "1000 metres": { "zh-CN": "1000 米", es: "1000 metros", fr: "1000 mètres", ru: "1000 метров", ar: "1000 متر" },
  "3 hours": { "zh-CN": "3 小时", es: "3 horas", fr: "3 heures", ru: "3 часа", ar: "3 ساعات" },
  "12 hours": { "zh-CN": "12 小时", es: "12 horas", fr: "12 heures", ru: "12 часов", ar: "12 ساعة" },
  "second (microbar": { "zh-CN": "秒·微巴（", es: "segundo (microbar", fr: "seconde (microbar", ru: "секунда (микробар", ar: "ثانية (ميكروبار" },
  "second)": { "zh-CN": "秒）", es: "segundo)", fr: "seconde)", ru: "секунда)", ar: "ثانية)" },
};

// Words the unit codelist uses in the plural but which the table above holds
// only in the singular. Folding them here keeps ~80 compound labels
// ("hectopascals per hour") translatable without a second copy of every unit.
const PLURALS = {
  becquerels: "becquerel",
  centibars: "centibar",
  centimetres: "centimetre",
  days: "day",
  decibels: "decibel",
  decipascals: "decipascal",
  degrees: "degree",
  grams: "gram",
  hectares: "hectare",
  hectopascals: "hectopascal",
  hours: "hour",
  joules: "joule",
  kelvins: "kelvin",
  kilograms: "kilogram",
  kilometres: "kilometre",
  knots: "knot",
  litres: "litre",
  metres: "metre",
  micrograms: "microgram",
  micromoles: "micromole",
  milligrams: "milligram",
  millibecquerels: "millibecquerel",
  millilitres: "millilitre",
  millimetres: "millimetre",
  millimoles: "millimole",
  minutes: "minute",
  moles: "mole",
  months: "month",
  nanograms: "nanogram",
  nanomoles: "nanomole",
  newtons: "newton",
  pascals: "pascal",
  picomoles: "picomole",
  radians: "radian",
  seconds: "second",
  "square metres": "square metre",
  "cubic metres": "cubic metre",
  steradians: "steradian",
  volts: "volt",
  watts: "watt",
  weeks: "week",
  years: "year",
};

// A number inside a unit label ("milligrams per cubic metre at 25 degrees")
// stays as it is; only the words around it are translated.
const NUMERIC = /^[+-]?\d+(?:\.\d+)?$/;

// The words of a unit label, or null when any of them is unknown. A plural
// that the table holds under `<word>__plural` reads from there, so
// "hectopascals per hour" keeps its plural ending in the languages that
// inflect for it.
function unitWord(word) {
  const cleaned = word.trim();
  const singular = PLURALS[cleaned];
  return UNIT_WORDS[cleaned] || (singular && UNIT_WORDS[`${singular}__plural`]) || (singular && UNIT_WORDS[singular]) || null;
}

// ---------------------------------------------------------------------------

const isPlainObject = (value) => value && typeof value === "object" && !Array.isArray(value);

const displayNames = (() => {
  const cache = new Map();
  return (locale) => {
    if (cache.has(locale)) return cache.get(locale);
    let names = null;
    try {
      names = new Intl.DisplayNames([locale], { type: "region" });
    } catch {
      names = null;
    }
    cache.set(locale, names);
    return names;
  };
})();

// alpha-2 -> alpha-3, so a country entered as "156" can still be found by
// someone who types "CHN".
const ALPHA3_OF = new Map(Object.entries(iso3166.alpha3).map(([alpha3, alpha2]) => [alpha2, alpha3]));

/**
 * Every code a country entry answers to: the notation the codelist uses (the
 * numeric ISO code, usually) and the ISO alpha-3. WMO-local issuer codes
 * (20000+) have no alpha-3 and come back alone.
 */
export function countryCodes(notation) {
  const alpha2 = iso3166.numeric[notation] || iso3166.alpha3[notation];
  const alpha3 = alpha2 && ALPHA3_OF.get(alpha2);
  return alpha3 && alpha3 !== notation ? [notation, alpha3] : [notation];
}

// Country and territory names, whatever the codelist calls them.
function countryName(notation, locale) {
  const names = displayNames(locale);
  if (!names) return null;
  const code = iso3166.numeric[notation] || iso3166.alpha3[notation];
  if (!code) return null;
  try {
    const name = names.of(code);
    // Intl echoes the code back when it has no name for it.
    return name && name !== code ? name : null;
  } catch {
    return null;
  }
}

// Unit labels are composed, not listed: "watts per square metre per
// steradian" is three known words and a preposition. So rather than 286
// entries, the label is tokenised against the vocabulary above and rebuilt in
// the target language. Chinese joins a product with "·" and a ratio with "/"
// (瓦特/平方米), which is the convention in that language and avoids having to
// reorder the "per" phrase; the others keep the preposition between words.
const PRODUCT_JOIN = { "zh-CN": "·", fr: " ", ru: "·", ar: " ", es: " " };

// "at 25 degrees" — the one phrase in the codelist that isn't a unit.
const AT_DEGREES = {
  "zh-CN": (n) => `（${n} 度下）`,
  fr: (n) => ` à ${n} degrés`,
  ru: (n) => ` при ${n} градусах`,
  ar: (n) => ` عند ${n} درجة`,
  es: (n) => ` a ${n} grados`,
};

// Lower-cased vocabulary, so "Volt squared" and "nanoTesla squared" (the
// codelist is inconsistent about case) find their entry.
const UNIT_INDEX = new Map(
  Object.entries(UNIT_WORDS).map(([word, names]) => [word.toLowerCase(), names])
);

// A single word or a multi-word entry ("cubic metre"), longest match first.
function lookupWord(tokens, start, locale) {
  for (let end = Math.min(tokens.length, start + 5); end > start; end--) {
    const phrase = tokens.slice(start, end).join(" ");
    const lower = phrase.toLowerCase();
    const names = UNIT_INDEX.get(lower) || UNIT_INDEX.get(PLURALS[lower]) || UNIT_INDEX.get(`${PLURALS[lower]}__plural`);
    if (names?.[locale]) return { text: names[locale], end };
  }
  return null;
}

// One "per"-separated segment, e.g. "square metres" or "12 hours".
function unitSegment(segment, locale) {
  const tokens = segment.trim().split(/\s+/).filter(Boolean);
  const parts = [];
  for (let i = 0; i < tokens.length; ) {
    const token = tokens[i];
    if (NUMERIC.test(token)) {
      parts.push(token);
      i += 1;
      continue;
    }
    const hit = lookupWord(tokens, i, locale);
    if (!hit) return null;
    parts.push(hit.text);
    i = hit.end;
  }
  return parts.length ? parts.join(PRODUCT_JOIN[locale] ?? " ") : null;
}

// "per second (same as hertz)" -> "per second" + note "same as hertz";
// "(metric) ton per hectare" -> note "metric" + "ton per hectare". Returns the
// label to work on and the notes to put back afterwards.
function splitNotes(label) {
  let body = label.trim();
  let trailing = null;
  let leading = null;
  const note = /^(.*?)\s*\(([^()]*)\)\s*$/.exec(body);
  if (note) {
    body = note[1];
    trailing = note[2];
  }
  const prefix = /^\(([^()]*)\)\s*(.+)$/.exec(body);
  if (prefix) {
    leading = prefix[1];
    body = prefix[2];
  }
  return { body, leading, trailing };
}

// The few parenthetical notes the unit codelist uses, so a composed label
// doesn't drop them ("per second (same as hertz)", "(metric) ton per hectare").
const NOTES = {
  angle: { "zh-CN": "角度", fr: "angle", ru: "угол", ar: "زاوية", es: "ángulo" },
  metric: { "zh-CN": "公制", fr: "métrique", ru: "метрическая", ar: "متري", es: "métrico" },
  "same as hertz": { "zh-CN": "同赫兹", fr: "identique au hertz", ru: "то же, что герц", ar: "مثل هرتز", es: "igual que el hercio" },
};

// A parenthetical note, which may itself be a compound ("microbar per
// second"). Null when it can't be composed, so the English label is kept.
function noteText(note, locale) {
  const listed = NOTES[note.toLowerCase()]?.[locale];
  if (listed) return listed;
  return unitName(note, locale)?.text ?? null;
}

/**
 * A unit label in `locale`, or null when part of it is outside the vocabulary
 * (the caller then shows the English label).
 */
function unitName(label, locale) {
  // Whole labels first: "second (angle)" and friends are listed as they stand.
  if (UNIT_WORDS[label]?.[locale]) return { text: UNIT_WORDS[label][locale] };

  const { body: whole, leading, trailing } = splitNotes(label);
  let body = whole;

  // A trailing "at N degrees" applies to the whole quantity.
  let temperature = "";
  const at = /\s+at\s+(\d+)\s+degrees$/.exec(body);
  if (at) {
    temperature = AT_DEGREES[locale](at[1]);
    body = body.slice(0, at.index);
  }

  // "per cubic metre" leads with the preposition; "per kilometre per
  // steradian" leads and then repeats it.
  const leadingPer = /^per\s+/i.test(body);
  const segments = (leadingPer ? body.replace(/^per\s+/i, "") : body).split(/\s+per\s+/i);

  const words = segments.map((segment) => unitSegment(segment, locale));
  if (words.some((word) => word === null)) return null;

  let text;
  if (leadingPer) {
    // The preposition leads in every language; Chinese repeats it rather than
    // using the "/" of a ratio.
    const rest = words.filter(Boolean);
    text = locale === "zh-CN" ? `每${rest.join("每")}` : `${PER[locale]} ${rest.join(` ${PER[locale]} `)}`;
  } else {
    const joiner = locale === "zh-CN" ? "/" : ` ${PER[locale]} `;
    text = words.filter(Boolean).join(joiner);
  }
  if (!text) return null;

  if (leading) {
    const note = noteText(leading, locale);
    if (!note) return null;
    text = `${note} ${text}`;
  }
  if (trailing) {
    const note = noteText(trailing, locale);
    if (!note) return null;
    text = `${text}（${note}）`;
  }
  return { text: `${text}${temperature}` };
}

/**
 * The display label of a codelist concept, in `locale`.
 *
 * Returns the English label unchanged when there is no name for it — which is
 * the intended outcome for the observational codelists, not a gap.
 */
export function codelistText(scheme, option, locale) {
  if (!option) return "";
  if (!locale || locale === "en") return option.label;

  const notation = option.code;
  const entry = NAMES[scheme]?.[notation];
  if (entry?.[locale]) return entry[locale];

  const generic = NOSCHEME[notation];
  if (generic?.[locale]) return generic[locale];

  // The issuer codelist the station form uses is ISO3166, which also carries
  // the WMO-local 20000+ codes.
  if (scheme === "ISO3166" || scheme === "TerritoryName") {
    const country = countryName(notation, locale);
    if (country) return country;
    const issuer = NAMES.IssuerOfIdentifier[notation];
    if (issuer?.[locale]) return issuer[locale];
  }

  if (scheme === "unit") {
    const composed = unitName(option.label, locale);
    if (composed) return composed.text;
  }

  return option.label;
}

/** True when `codelistText` has a translation for this concept. */
export const hasCodelistText = (scheme, option, locale) =>
  !!option && (locale === "en" || codelistText(scheme, option, locale) !== option.label);

export { NAMES as CODELIST_NAMES, UNIT_WORDS, NOSCHEME, isPlainObject };