"""
PlantNet300K 物种名英→中批量翻译脚本
=====================================
使用 googletrans / deep-translator 将 1081 个拉丁学名批量翻译为中文。

前置依赖:
    pip install deep-translator    # 推荐，使用 Google 翻译（免费、无需API Key）

输入:
    data/plantnet300K_species_id_2_name.json  # species_id → 拉丁学名

输出:
    data/plantnet300K_species_id_2_chinese.json  # species_id → 中文名

用法:
    # 方式1：使用 deep-translator（推荐，免费）
    python manual/scripts/translate_species_names.py --method deep-translator

    # 方式2：使用离线词典（无需网络，仅限常见物种）
    python manual/scripts/translate_species_names.py --method dictionary

    # 方式3：使用 OpenAI API（质量最高，需 API Key）
    python manual/scripts/translate_species_names.py --method openai --api-key sk-xxx
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent.parent
NAME_MAP_PATH = ROOT / "data" / "plantnet300K_species_id_2_name.json"
OUT_PATH = ROOT / "data" / "plantnet300K_species_id_2_chinese.json"

# ============================================================
# 离线植物学词典（属名级别，补充常见种的中文名）
# 来源：中国植物志 / iPlant / Wikipedia
# ============================================================
PLANT_DICT = {
    # 属名
    "Lactuca": "莴苣属",
    "Pelargonium": "天竺葵属",
    "Cirsium": "蓟属",
    "Mercurialis": "山靛属",
    "Phyllanthus": "叶下珠属",
    "Hypericum": "金丝桃属",
    "Egeria": "水蕴草属",
    "Ibicella": "角胡麻属",
    "Tradescantia": "紫露草属",
    "Lamium": "野芝麻属",
    "Lavandula": "薰衣草属",
    "Striga": "独脚金属",
    "Melilotus": "草木樨属",
    "Trifolium": "三叶草属",
    "Asystasia": "十万错属",
    "Nymphaea": "睡莲属",
    "Dryopteris": "鳞毛蕨属",
    "Nephrolepis": "肾蕨属",
    "Osmunda": "紫萁属",
    "Achyranthes": "牛膝属",
    "Lithodora": "石芥花属",
    "Humulus": "葎草属",
    "Vaccaria": "王不留行属",
    "Spergularia": "拟漆姑属",
    "Moehringia": "种草草属",
    "Calendula": "金盏花属",
    "Carthamus": "红花属",
    "Helminthotheca": "刚毛菊属",
    "Hyoseris": "猪菊苣属",
    "Limbarda": "碱菀属",
    "Sedum": "景天属",
    "Alliaria": "葱芥属",
    "Boscia": "山柑属",
    "Fibigia": "翅籽芥属",
    "Maerua": "山柑藤属",
    "Acalypha": "铁苋菜属",
    "Galega": "山羊豆属",
    "Lupinus": "羽扇豆属",
    "Punica": "石榴属",
    "Alcea": "蜀葵属",
    "Althaea": "药葵属",
    "Hunnemannia": "金杯罂粟属",
    "Papaver": "罂粟属",
    "Goniolimon": "驼舌草属",
    "Adonis": "侧金盏花属",
    "Anemone": "银莲花属",
    "Oldenlandia": "耳草属",
    "Hyoscyamus": "天仙子属",
    "Daphne": "瑞香属",
    "Berula": "天山泽芹属",
    "Chaerophyllum": "细叶芹属",
    "Daucus": "胡萝卜属",
    "Meum": "波罗的月桂属",
    "Thapsia": "毒胡萝卜属",
    "Centranthus": "距药草属",
    "Fedia": "荷包草属",
    "Pancratium": "全能花属",
    "Anthericum": "吊兰属",
    "Butomus": "花蔺属",
    "Danthonia": "扁芒草属",
    "Leersia": "假稻属",
    "Phalaris": "虉草属",
    "Oncostema": "海葱属",
    "Elodea": "伊乐藻属",
    "Neotinea": "新缇尼兰属",
    "Ophrys": "蜂兰属",
    "Groenlandia": "格陵兰眼子菜属",
    "Myosoton": "鹅肠菜属",
    "Casuarina": "木麻黄属",
    "Falcaria": "镰刀芹属",
    "Wigandia": "维甘花属",
    "Epipactis": "火烧兰属",
    "Thesium": "百蕊草属",
    "Acacia": "金合欢属",
    "Freesia": "香雪兰属",
    "Diatelia": "蒂亚兰属",
    "Cenchrus": "蒺藜草属",
    "Schefflera": "鹅掌柴属",
    "Smilax": "菝葜属",
    "Aizoon": "长生花属",
    "Zannichellia": "角果藻属",
    "Secale": "黑麦属",
    "Crotalaria": "猪屎豆属",
    "Dalbergia": "黄檀属",
    "Barbarea": "山芥属",
    "Myosurus": "鼠尾巴属",
    "Fragaria": "草莓属",
    "Duchesnea": "蛇莓属",
    "Guizotia": "小葵子属",
    "Tagetes": "万寿菊属",
    "Lapsana": "稻槎菜属",
    "Arthraxon": "荩草属",
    "Microchloa": "小草属",
    "Harpachne": "镰稃草属",
    "Cedrela": "洋椿属",
    "Aeschynomene": "合萌属",
    "Prosopis": "牧豆树属",
    "Cordyla": "心轴木属",
    "Gomphocarpus": "钉头果属",
    "Trachelospermum": "络石属",
    "Gymnosporia": "裸实属",
    "Conostomium": "锥果草属",
    "Mussaenda": "玉叶金花属",
    "Morinda": "巴戟天属",
    "Pilocarpus": "毛果芸香属",
    "Gynura": "菊三七属",
    "Aspilia": "三裂芒属",
    "Schkuhria": "蛇眼菊属",
    "Montanoa": "山雏菊属",
    "Triadica": "乌桕属",
    "Petiveria": "蒜叶草属",
    "Peperomia": "椒草属",
    "Guaiacum": "愈创木属",
    "Mecardonia": "过长沙属",
    "Browallia": "蓝英花属",
    "Aristea": "爵床鸢尾属",
    "Erianthemum": "毛冠木属",
    "Cucurbita": "南瓜属",
    "Luffa": "丝瓜属",
    "Lagenaria": "葫芦属",
    "Barringtonia": "玉蕊属",
    "Couroupita": "炮弹树属",
    "Raphia": "酒椰属",
    "Zamioculcas": "雪铁芋属",
    "Kniphofia": "火炬花属",
    "Vanilla": "香荚兰属",
    "Ansellia": "豹斑兰属",
    "Macrosyringion": "长管花属",
    "Pyracantha": "火棘属",
    "Aizoanthemum": "假海马齿属",
    "Phedimus": "费菜属",
    "Cereus": "天轮柱属",
    "Liriodendron": "鹅掌楸属",
    "Atocion": "裸茎蝇子草属",
    "Aegopodium": "羊角芹属",
    "Patzkea": "帕茨克草属",
    "Perovskia": "分药花属",
    "Erechtites": "菊芹属",
    "Nothofagus": "南山毛榉属",
    "Collomia": "粘毛草属",
    "Cymbalaria": "蔓柳穿鱼属",
    "Cytinus": "簇花草属",
    "Dorotheanthus": "彩虹菊属",
    "Dryas": "仙女木属",
    "Empetrum": "岩高兰属",
    "Erucastrum": "芝麻菜属",
    "Geropogon": "老翁须属",
    "Hebe": "赫柏属",
    "Helicodiceros": "螺旋魔芋属",
    "Hippophae": "沙棘属",
    "Dierama": "天使钓竿属",
    "Iva": "假苍耳属",
    "Lathraea": "齿鳞草属",
    "Limnanthes": "沼花属",
    "Maianthemum": "舞鹤草属",
    "Narthecium": "纳茜菜属",
    "Noccaea": "山菥蓂属",
    "Nymphoides": "荇菜属",
    "Oreopteris": "山蕨属",
    "Sasa": "赤竹属",
    "Sagittaria": "慈姑属",
    "Holodiscus": "全盘花属",
    "Diascia": "二距花属",
    "Metasequoia": "水杉属",
    "Telekia": "心叶菊属",
    "Viscaria": "粘蝇草属",
    "Adenostyles": "腺梗菜属",
    "Eritrichium": "齿缘草属",
    "Honckenya": "海滨蚤缀属",
    "Trinia": "伞序芹属",
    "Cobaea": "电灯花属",
    "Calycanthus": "夏蜡梅属",
    "Aralia": "楤木属",
    "Clethra": "山柳属",
    "Corispermum": "虫实属",
    "Tetraclinis": "四鳞柏属",
    "Paederota": "足柄草属",
    "Rhodothamnus": "杜鹃花属",
    "Astydamia": "星序芹属",
    "Bellium": "小雏菊属",
    "Vismia": "金丝桃果属",
    "Xylopia": "木瓣树属",
    "Pogonophora": "须药树属",
    "Sagotia": "萨戈木属",
    "Bonafousia": "波那花属",
    "Guarea": "格木属",
    "Anthurium": "花烛属",
    "Dracontium": "龙木芋属",
    "Declieuxia": "德克里木属",
    "Mauritia": "毛里求斯榈属",
    "Urera": "刺痒藤属",
    "Pereskia": "木麒麟属",
    "Aciotis": "顶药花属",
    "Guatteria": "爪瓣花属",
    "Cryptostegia": "隐冠藤属",
    "Aphelandra": "单药花属",
    "Piriqueta": "皮里花属",
    "Breynia": "黑面神属",
    "Kigelia": "腊肠树属",
    "Cryptopus": "隐足兰属",
    "Eranthemum": "喜花草属",
    "Alocasia": "海芋属",
    "Faujasia": "福贾菊属",
    "Fernelia": "费内尔木属",
    "Geniostoma": "髯管花属",
    "Hernandia": "莲叶桐属",
    "Leonitis": "狮耳花属",
    "Paederia": "鸡屎藤属",
    "Antirhea": "毛茶属",
    "Pongamia": "水黄皮属",
    "Stemodia": "离瓣母草属",
    "Stoebe": "斯托草属",
    "Strongylodon": "碧玉藤属",
    "Trimezia": "三须鸢尾属",
    "Vangueria": "万果茜属",
    "Vepris": "南非芸香属",
    "Zaleya": "裂盖马齿苋属",
    "Bismarckia": "霸王榈属",
    "Zamia": "泽米铁属",
    "Dendrobium": "石斛属",
    "Nandina": "南天竹属",
    "Falcataria": "镰木属",
    "Bourreria": "布氏木属",
    "Entada": "榼藤属",
    "Fittonia": "网纹草属",
    "Illicium": "八角属",
    "Neolamarckia": "团花属",
    "Pilosocereus": "毛柱属",
    "Selenicereus": "月光仙人掌属",
    "Chamerion": "柳兰属",
    "Comptonia": "香蕨木属",
    "Conoclinium": "锥托泽兰属",
    "Dalea": "戴尔豆属",
    "Diervilla": "黄锦带属",
    "Mertensia": "滨紫草属",
    "Mitella": "唢呐草属",
    "Balsamorhiza": "香根菊属",
    "Calochortus": "蝴蝶百合属",
    "Cerbera": "海芒果属",
    "Dubouzetia": "杜布木属",
    "Atractocarpus": "纺锤果属",
    "Nepenthes": "猪笼草属",
    "Dracophyllum": "龙叶树属",
    "Anisocampium": "安蕨属",
    "Lithops": "生石花属",
    "Neobuxbaumia": "新布氏柱属",
    "Eucryphia": "香枫属",
    "Rumohra": "革叶蕨属",
    "Oxydendrum": "酸模树属",
    "Lycoris": "石蒜属",
    "Garrya": "丝缨花属",
    "Loropetalum": "檵木属",
    "Liriope": "山麦冬属",
    "Abeliophyllum": "朝鲜白连翘属",
    "Heteromorpha": "异形芹属",
    "Lapageria": "智利风铃花属",
    "Maurandya": "蔓桐花属",
    "Limonia": "木苹果属",
    "Calodendrum": "好望角栗属",
    "Maytenus": "美登木属",
    "Melampodium": "黑足菊属",
    "Mazus": "通泉草属",
    "Freycinetia": "藤露兜属",
    "Dischidia": "眼树莲属",
    "Schinopsis": "破斧木属",
    "Herbertia": "鸢尾葵属",
    "Keckiella": "凯氏玄参属",
    "Lyonothamnus": "铁木属",
    "Nyctaginia": "夜香紫茉莉属",
    "Stanleya": "史坦利芥属",
    "Xylococcus": "熊果属",
    "Brodiaea": "紫灯花属",
    "Calylophus": "花管月见草属",
    "Elephantopus": "地胆草属",
    "Hackelia": "假鹤虱属",
    "Haplophyton": "单叶夹竹桃属",
    "Aextoxicon": "智利常绿树属",
    "Cyrtanthus": "曲花属",
    "Wodyetia": "狐尾椰子属",
    "Coryphantha": "顶花球属",
    "Stenocactus": "多棱球属",
    "Tephrocactus": "纸刺仙人掌属",
    "Pterocephalus": "翼首花属",
    "Cyanotis": "蓝耳草属",
    "Othonna": "肉叶菊属",
    "Rhodanthe": "鳞托菊属",
    "Uncinia": "钩状薹草属",
    "Margaritopsis": "珍珠木属",
    "Angostura": "安古树属",
    "Coussapoa": "库萨波属",
    "Cyphostemma": "葡萄瓮属",
    "Stenanona": "狭瓣木属",
    "Alibertia": "阿里木属",

    # 常见种补充（属名 + 种加词组合）
    "Lactuca virosa": "毒莴苣",
    "Lactuca sativa": "莴苣",
    "Lactuca serriola": "野莴苣",
    "Hypericum perforatum": "贯叶连翘",
    "Hypericum calycinum": "大萼金丝桃",
    "Punica granatum": "石榴",
    "Papaver rhoeas": "虞美人",
    "Papaver somniferum": "罂粟",
    "Papaver orientale": "东方罂粟",
    "Papaver nudicaule": "冰岛罂粟",
    "Daucus carota": "野胡萝卜",
    "Fragaria vesca": "野草莓",
    "Fragaria virginiana": "弗吉尼亚草莓",
    "Fragaria chiloensis": "智利草莓",
    "Fragaria moschata": "麝香草莓",
    "Secale cereale": "黑麦",
    "Cucurbita pepo": "西葫芦",
    "Cucurbita maxima": "笋瓜",
    "Cucurbita moschata": "南瓜",
    "Cucurbita ficifolia": "无花果叶瓜",
    "Luffa acutangula": "棱角丝瓜",
    "Luffa cylindrica": "丝瓜",
    "Lagenaria siceraria": "葫芦",
    "Nymphaea alba": "白睡莲",
    "Nymphaea lotus": "埃及白睡莲",
    "Nymphaea nouchali": "延药睡莲",
    "Nymphaea candida": "雪白睡莲",
    "Nymphaea mexicana": "黄睡莲",
    "Nymphaea odorata": "香睡莲",
    "Nymphaea tetragona": "睡莲",
    "Nymphaea ampla": "大花睡莲",
    "Nymphaea rubra": "红睡莲",
    "Hippophae rhamnoides": "沙棘",
    "Illicium verum": "八角",
    "Illicium floridanum": "佛罗里达八角",
    "Illicium anisatum": "日本莽草",
    "Zamioculcas zamiifolia": "雪铁芋",
    "Metasequoia glyptostroboides": "水杉",
    "Liriodendron tulipifera": "北美鹅掌楸",
    "Liriodendron chinensis": "鹅掌楸",
    "Smilax china": "菝葜",
    "Smilax glabra": "光叶菝葜",
    "Smilax aspera": "粗糙菝葜",
    "Smilax rotundifolia": "圆叶菝葜",
    "Smilax herbacea": "草本菝葜",
    "Smilax bona-nox": "夜花菝葜",
    "Vanilla planifolia": "香荚兰",
    "Vanilla pompona": "蓬蓬香荚兰",
    "Dendrobium nobile": "石斛",
    "Dendrobium chrysotoxum": "鼓槌石斛",
    "Dendrobium aphyllum": "无叶石斛",
    "Dendrobium anosmum": "檀香石斛",
    "Dendrobium kingianum": "金氏石斛",
    "Dendrobium thyrsiflorum": "密花石斛",
    "Calendula officinalis": "金盏花",
    "Calendula arvensis": "野金盏花",
    "Calendula stellata": "星花金盏花",
    "Carthamus tinctorius": "红花",
    "Carthamus lanatus": "毛红花",
    "Carthamus caeruleus": "蓝红花",
    "Tagetes erecta": "万寿菊",
    "Tagetes patula": "孔雀草",
    "Tagetes minuta": "小花万寿菊",
    "Tagetes lucida": "甜万寿菊",
    "Tagetes tenuifolia": "细叶万寿菊",
    "Tagetes lemmonii": "莱氏万寿菊",
    "Cedrela odorata": "西班牙柏木",
    "Cedrela fissilis": "巴西桃花心木",
    "Humulus lupulus": "啤酒花",
    "Lavandula angustifolia": "狭叶薰衣草",
    "Lavandula stoechas": "法国薰衣草",
    "Lavandula dentata": "齿叶薰衣草",
    "Lavandula latifolia": "宽叶薰衣草",
    "Lavandula multifida": "裂叶薰衣草",
    "Lavandula canariensis": "加那利薰衣草",
    "Lavandula pinnata": "羽叶薰衣草",
    "Anemone coronaria": "罂粟牡丹",
    "Anemone nemorosa": "林地银莲花",
    "Anemone pulsatilla": "白头翁",
    "Anemone hepatica": "獐耳细辛",
    "Anemone blanda": "希腊银莲花",
    "Anemone hupehensis": "打破碗花花",
    "Anemone narcissiflora": "水仙银莲花",
    "Anemone ranunculoides": "黄银莲花",
    "Anemone canadensis": "加拿大银莲花",
    "Anemone virginiana": "弗吉尼亚银莲花",
    "Anemone patens": "帕滕银莲花",
    "Anemone sylvestris": "林生银莲花",
    "Anemone pratensis": "草地银莲花",
    "Melilotus officinalis": "黄香草木樨",
    "Melilotus albus": "白花草木樨",
    "Melilotus indicus": "印度草木樨",
    "Melilotus altissimus": "高草木樨",
    "Trifolium pratense": "红三叶",
    "Trifolium repens": "白三叶",
    "Trifolium hybridum": "杂三叶",
    "Trifolium incarnatum": "绛三叶",
    "Trifolium alexandrinum": "埃及三叶草",
    "Trifolium fragiferum": "草莓三叶草",
    "Trifolium arvense": "石三叶草",
    "Trifolium campestre": "草原三叶草",
    "Trifolium subterraneum": "地三叶草",
    "Trifolium resupinatum": "波斯三叶草",
    "Trifolium medium": "中型三叶草",
    "Trifolium rubens": "红三叶草",
    "Trifolium alpestre": "高山三叶草",
    "Trifolium alpinum": "阿尔卑斯三叶草",
    "Lupinus albus": "白羽扇豆",
    "Lupinus luteus": "黄羽扇豆",
    "Lupinus angustifolius": "狭叶羽扇豆",
    "Lupinus polyphyllus": "多叶羽扇豆",
    "Lupinus arboreus": "树羽扇豆",
    "Lupinus perennis": "多年生羽扇豆",
    "Lupinus nootkatensis": "努特卡羽扇豆",
    "Lupinus texensis": "得克萨斯羽扇豆",
    "Lupinus argenteus": "银羽扇豆",
    "Lupinus bicolor": "双色羽扇豆",
    "Lupinus albifrons": "银叶羽扇豆",
    "Acacia dealbata": "银荆",
    "Acacia mearnsii": "黑荆",
    "Acacia melanoxylon": "黑木金合欢",
    "Acacia longifolia": "长叶金合欢",
    "Acacia pycnantha": "密花金合欢",
    "Acacia saligna": "柳叶金合欢",
    "Acacia mangium": "马占相思",
    "Acacia auriculiformis": "大叶相思",
    "Acacia confusa": "台湾相思",
    "Acacia farnesiana": "鸭皂树",
    "Acacia nilotica": "阿拉伯金合欢",
    "Acacia baileyana": "贝利氏金合欢",
    "Acacia podalyriifolia": "珍珠金合欢",
    "Acacia retinodes": "湿地金合欢",
    "Acacia tortilis": "扭枝金合欢",
    "Acacia seyal": "塞伊耳金合欢",
    "Acacia caven": "卡文金合欢",
    "Acacia xanthophloea": "黄皮金合欢",
    "Acacia simplex": "单叶金合欢",
    "Acacia spirorbis": "螺旋金合欢",
    "Acacia heterophylla": "异叶金合欢",
    "Acacia pravissima": "极弯金合欢",
    "Acacia redolens": "芳香金合欢",
    "Acacia rigidula": "硬叶金合欢",
    "Crotalaria juncea": "菽麻",
    "Crotalaria retusa": "凹叶猪屎豆",
    "Crotalaria spectabilis": "大托叶猪屎豆",
    "Crotalaria pallida": "猪屎豆",
    "Crotalaria incana": "毛猪屎豆",
    "Crotalaria verrucosa": "疣果猪屎豆",
    "Crotalaria laburnifolia": "金链花叶猪屎豆",
    "Dalbergia sissoo": "印度黄檀",
    "Dalbergia latifolia": "宽叶黄檀",
    "Dalbergia melanoxylon": "非洲黑木",
    "Dalbergia retusa": "微凹黄檀",
    "Prosopis juliflora": "柔花牧豆树",
    "Prosopis glandulosa": "腺牧豆树",
    "Prosopis pallida": "淡色牧豆树",
    "Prosopis alba": "白牧豆树",
    "Prosopis farcta": "胖牧豆树",
    "Alcea rosea": "蜀葵",
    "Alcea setosa": "刚毛蜀葵",
    "Alcea biennis": "二年生蜀葵",
    "Althaea officinalis": "药蜀葵",
    "Althaea cannabina": "大麻叶药葵",
    "Casuarina equisetifolia": "木麻黄",
    "Casuarina cunninghamiana": "细枝木麻黄",
    "Epipactis helleborine": "火烧兰",
    "Epipactis palustris": "沼泽火烧兰",
    "Epipactis atrorubens": "暗红火烧兰",
    "Epipactis gigantea": "大花火烧兰",
    "Pelargonium graveolens": "香叶天竺葵",
    "Pelargonium capitatum": "头状天竺葵",
    "Pelargonium peltatum": "盾叶天竺葵",
    "Pelargonium zonale": "马蹄纹天竺葵",
    "Pelargonium odoratissimum": "极香天竺葵",
    "Pelargonium crispum": "皱叶天竺葵",
    "Pelargonium inquinans": "猩红天竺葵",
    "Pelargonium sidoides": "南非天竺葵",
    "Pelargonium tomentosum": "绒毛天竺葵",
    "Pelargonium grandiflorum": "大花天竺葵",
    "Sedum acre": "苦味景天",
    "Sedum album": "白景天",
    "Sedum rubens": "红景天",
    "Sedum rupestre": "岩生景天",
    "Sedum hispanicum": "西班牙景天",
    "Sedum dasyphyllum": "毛叶景天",
    "Sedum palmeri": "帕氏景天",
    "Sedum morganianum": "玉珠帘",
    "Sedum lineare": "佛甲草",
    "Sedum sarmentosum": "垂盆草",
    "Sedum kamtschaticum": "费菜",
    "Sedum adolphii": "金景天",
    "Sedum rubrotinctum": "虹之玉",
    "Daphne mezereum": "欧洲瑞香",
    "Daphne odora": "瑞香",
    "Daphne laureola": "桂叶瑞香",
    "Daphne gnidium": "地中海瑞香",
    "Daphne cneorum": "蔷薇瑞香",
    "Daphne sericea": "绢毛瑞香",
    "Nepenthes mirabilis": "奇异猪笼草",
    "Nepenthes alata": "翼状猪笼草",
    "Nepenthes truncata": "截形猪笼草",
    "Nepenthes vieillardii": "维氏猪笼草",
    "Tradescantia zebrina": "吊竹梅",
    "Tradescantia pallida": "紫竹梅",
    "Tradescantia spathacea": "蚌花",
    "Tradescantia fluminensis": "白花紫露草",
    "Tradescantia virginiana": "弗吉尼亚紫露草",
    "Tradescantia sillamontana": "白雪姬",
    "Tradescantia occidentalis": "西方紫露草",
    "Tradescantia ohiensis": "俄亥俄紫露草",
    "Tradescantia cerinthoides": "蜡叶紫露草",
    "Ophrys apifera": "蜜蜂兰",
    "Ophrys insectifera": "蝇兰",
    "Ophrys lutea": "黄蜂兰",
    "Ophrys speculum": "镜兰",
    "Ophrys tenthredinifera": "叶蜂兰",
    "Ophrys bombyliflora": "熊蜂兰",
    "Ophrys fusca": "褐蜂兰",
    "Ophrys scolopax": "山鹬兰",
    "Ophrys bertolonii": "伯氏蜂兰",
    "Ophrys fuciflora": "大黄蜂兰",
    "Ophrys aranifera": "蜘蛛兰",
    "Ophrys sphegodes": "早蜘蛛兰",
    "Lycoris radiata": "石蒜",
    "Lycoris squamigera": "鹿葱",
    "Pyracantha coccinea": "火棘",
    "Pyracantha rogersiana": "罗氏火棘",
    "Schefflera arboricola": "鹅掌藤",
    "Schefflera actinophylla": "澳洲鸭脚木",
    "Schefflera heptaphylla": "七叶鹅掌柴",
    "Schefflera morototoni": "山麻疯树",
    "Alocasia macrorrhizos": "海芋",
    "Alocasia cucullata": "尖尾芋",
    "Alocasia odora": "香海芋",
    "Alocasia cuprea": "铜叶海芋",
    "Alocasia micholitziana": "米氏海芋",
    "Alocasia sanderiana": "桑德海芋",
    "Alocasia lauterbachiana": "劳氏海芋",
    "Alocasia wentii": "文氏海芋",
    "Alocasia zebrina": "斑马海芋",
    "Alocasia reginula": "黑天鹅海芋",
    "Alocasia baginda": "巴氏海芋",
    "Alocasia longiloba": "长裂海芋",
    "Nandina domestica": "南天竹",
    "Loropetalum chinense": "檵木",
    "Liriope muscari": "阔叶山麦冬",
    "Calycanthus floridus": "美国夏蜡梅",
    "Calycanthus occidentalis": "加州夏蜡梅",
    "Oxydendrum arboreum": "酸模树",
    "Fittonia albivenis": "网纹草",
    "Trachelospermum jasminoides": "络石",
    "Trachelospermum asiaticum": "亚洲络石",
    "Peperomia pellucida": "草胡椒",
    "Peperomia obtusifolia": "圆叶椒草",
    "Peperomia argyreia": "西瓜皮椒草",
    "Peperomia caperata": "皱叶椒草",
    "Peperomia rotundifolia": "圆叶椒草",
    "Peperomia prostrata": "串珠椒草",
    "Peperomia ferreyrae": "幸福豆",
    "Peperomia graveolens": "红背椒草",
    "Peperomia clusiifolia": "匙叶椒草",
    "Peperomia dolabriformis": "斧叶椒草",
    "Peperomia polybotrya": "荷叶椒草",
    "Peperomia magnoliifolia": "木兰叶椒草",
    "Peperomia verticillata": "轮叶椒草",
    "Aralia elata": "辽东楤木",
    "Aralia spinosa": "刺楤木",
    "Aralia californica": "加州楤木",
    "Aralia nudicaulis": "裸茎楤木",
    "Aralia racemosa": "总状楤木",
    "Eucryphia cordifolia": "心叶香枫",
    "Garrya elliptica": "椭圆丝缨花",
    "Phalaris arundinacea": "虉草",
    "Phalaris canariensis": "加那利虉草",
    "Phalaris aquatica": "水生虉草",
    "Oldenlandia corymbosa": "伞房花耳草",
    "Achyranthes aspera": "土牛膝",
    "Morinda citrifolia": "海滨木巴戟",
    "Neolamarckia cadamba": "团花",
    "Limonia acidissima": "木苹果",
    "Guaiacum officinale": "愈创木",
    "Guaiacum sanctum": "神圣愈创木",
    "Barringtonia asiatica": "棋盘脚",
    "Barringtonia acutangula": "锐棱玉蕊",
    "Couroupita guianensis": "炮弹树",
    "Cereus repandus": "秘鲁天轮柱",
    "Cereus hildmannianus": "仙人山",
    "Cereus jamacaru": "牙买加天轮柱",
    "Selenicereus grandiflorus": "大花月光仙人掌",
    "Selenicereus anthonyanus": "鱼骨令箭",
    "Pereskia aculeata": "木麒麟",
    "Pereskia grandifolia": "大叶木麒麟",
    "Zamia furfuracea": "鳞秕泽米铁",
    "Zamia pumila": "矮泽米铁",
    "Osmunda regalis": "欧紫萁",
    "Osmunda cinnamomea": "桂皮紫萁",
    "Osmunda claytoniana": "绒紫萁",
    "Dryopteris filix-mas": "欧洲鳞毛蕨",
    "Dryopteris affinis": "近亲鳞毛蕨",
    "Dryopteris dilatata": "广布鳞毛蕨",
    "Dryopteris erythrosora": "红盖鳞毛蕨",
    "Dryopteris intermedia": "中间鳞毛蕨",
    "Dryopteris carthusiana": "刺叶鳞毛蕨",
    "Dryopteris cristata": "冠鳞毛蕨",
    "Nephrolepis exaltata": "波士顿蕨",
    "Nephrolepis cordifolia": "心叶肾蕨",
    "Nephrolepis biserrata": "长叶肾蕨",
    "Nephrolepis falcata": "镰叶肾蕨",
    "Rumohra adiantiformis": "革叶蕨",
    "Sagittaria sagittifolia": "慈姑",
    "Sagittaria latifolia": "宽叶慈姑",
    "Sagittaria graminea": "禾叶慈姑",
    "Sagittaria lancifolia": "披针叶慈姑",
    "Sagittaria montevidensis": "蒙特维多慈姑",
    "Maianthemum bifolium": "舞鹤草",
    "Maianthemum canadense": "加拿大舞鹤草",
    "Maianthemum racemosum": "总状舞鹤草",
    "Maianthemum stellatum": "星花舞鹤草",
    "Maianthemum trifolium": "三叶舞鹤草",
    "Kniphofia uvaria": "火炬花",
    "Kniphofia linearifolia": "线叶火炬花",
    "Perovskia atriplicifolia": "俄罗斯鼠尾草",
    "Perovskia abrotanoides": "青蒿叶分药花",
    "Adonis vernalis": "春福寿草",
    "Adonis aestivalis": "夏福寿草",
    "Adonis annua": "秋福寿草",
    "Adonis flammea": "火红福寿草",
    "Adonis microcarpa": "小果福寿草",
    "Adonis pyrenaica": "比利牛斯福寿草",
    "Barbarea vulgaris": "山芥",
    "Barbarea verna": "春山芥",
    "Barbarea intermedia": "中间山芥",
    "Barbarea orthoceras": "直果山芥",
    "Barbarea rupicola": "岩生山芥",
    "Erechtites hieraciifolius": "菊芹",
    "Entada phaseoloides": "榼藤",
    "Entada gigas": "巨榼藤",
    "Pancratium maritimum": "海滨全能花",
    "Pancratium illyricum": "伊利里亚全能花",
    "Spergularia rubra": "红拟漆姑",
    "Aegopodium podagraria": "羊角芹",
    "Mazus pumilus": "通泉草",
    "Paederia foetida": "鸡屎藤",
    "Elephantopus elatus": "高地胆草",
    "Browallia americana": "美洲蓝英花",
    "Browallia speciosa": "大花蓝英花",
    "Balsamorhiza sagittata": "箭叶香根菊",
    "Adlumia fungosa": "蕈树",
    "Myosoton aquaticum": "鹅肠菜",
    "Petiveria alliacea": "蒜臭木",
    "Clethra alnifolia": "桤木叶山柳",
    "Empetrum nigrum": "岩高兰",
    "Empetrum rubrum": "红岩高兰",
    "Cobaea scandens": "电灯花",
    "Aphelandra squarrosa": "斑马花",
    "Aphelandra scabra": "粗糙单药花",
    "Aphelandra sinclairiana": "辛克莱单药花",
    "Eranthemum pulchellum": "喜花草",
    "Leonitis nepetifolia": "荆芥叶狮耳花",
    "Cenchrus ciliaris": "水牛草",
    "Cenchrus echinatus": "蒺藜草",
    "Cenchrus setaceus": "紫狼尾草",
    "Cenchrus purpureus": "象草",
    "Cenchrus clandestinus": "隐花狼尾草",
    "Holodiscus discolor": "全盘花",
    "Maurandya barclayana": "巴氏蔓桐花",
    "Triadica sebifera": "乌桕",
    "Abeliophyllum distichum": "朝鲜白连翘",
    "Chamerion latifolium": "宽叶柳兰",
    "Freycinetia cumingiana": "库氏藤露兜",
    "Strongylodon macrobotrys": "碧玉藤",
    "Wodyetia bifurcata": "狐尾椰子",
    "Lithops aucampiae": "日轮玉",
    "Lithops karasmontana": "花纹玉",
    "Lithops fulviceps": "微纹玉",
    "Lithops marmorata": "大理石玉",
    "Lithops olivacea": "橄榄玉",
    "Lithops pseudotruncatella": "曲玉",
    "Angostura granulosa": "粒状安古树",
}


def remove_author(scientific_name: str) -> str:
    """去除拉丁学名中的命名人部分"""
    parts = scientific_name.split()
    if parts and re.match(r'^[A-Z][a-z]*\.?$', parts[-1]):
        parts = parts[:-1]
    return ' '.join(parts)


def translate_dictionary(species_id_to_name: dict[str, str]) -> dict[str, str]:
    """使用离线词典翻译"""
    result = {}
    for sid, sname in species_id_to_name.items():
        # 精确匹配种名
        if sname in PLANT_DICT:
            result[sid] = PLANT_DICT[sname]
            continue

        # 匹配去作者后的规范名
        canonical = remove_author(sname)
        if canonical in PLANT_DICT:
            result[sid] = PLANT_DICT[canonical]
            continue

        # 匹配属名（第一个词）
        genus = sname.split()[0] if sname.split() else ""
        if genus in PLANT_DICT:
            genus_cn = PLANT_DICT[genus]
            # 种加词保留，形成"属名+种"的中文名
            specific = sname.split()[1] if len(sname.split()) > 1 else ""
            if specific:
                result[sid] = f"{genus_cn.replace('属', '')}（{specific}）"
            else:
                result[sid] = genus_cn
        else:
            result[sid] = sname  # 未匹配到，保留拉丁名
    return result


def translate_deep_translator(species_id_to_name: dict[str, str],
                               delay: float = 1.5) -> dict[str, str]:
    """使用 deep-translator (Google 翻译) 批量翻译"""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("请先安装: pip install deep-translator")
        raise

    result = {}
    # 先尝试离线词典覆盖常见物种
    result.update(translate_dictionary(species_id_to_name))
    already_translated = set(result.keys())

    # 对未翻译的进行批量 API 翻译
    to_translate = {k: v for k, v in species_id_to_name.items()
                    if k not in already_translated}

    print(f"  离线词典命中: {len(already_translated)} 条")
    print(f"  待API翻译:     {len(to_translate)} 条")

    names = list(to_translate.values())
    ids = list(to_translate.keys())

    batch_size = 10  # 每次发送10个用换行分隔
    for i in range(0, len(names), batch_size):
        batch_names = names[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]

        try:
            text = "\n".join(batch_names)
            translated_text = GoogleTranslator(source="en", target="zh-CN").translate(text)
            translated_names = translated_text.split("\n")

            for sid, cn_name in zip(batch_ids, translated_names):
                result[sid] = cn_name.strip()

        except Exception as e:
            print(f"  ✗ 批次 {i // batch_size + 1} 翻译失败: {e}")
            for sid, sname in zip(batch_ids, batch_names):
                if sid not in result:
                    result[sid] = remove_author(sname)

        if i + batch_size < len(names):
            time.sleep(delay)

    return result


def translate_openai(species_id_to_name: dict[str, str],
                     api_key: str, model: str = "gpt-3.5-turbo") -> dict[str, str]:
    """使用 OpenAI API 批量翻译（质量最高）"""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    result = {}
    # 先覆盖离线词典
    result.update(translate_dictionary(species_id_to_name))
    already_translated = set(result.keys())

    to_translate = {k: v for k, v in species_id_to_name.items()
                    if k not in already_translated}

    print(f"  离线词典命中: {len(already_translated)} 条")
    print(f"  待API翻译:     {len(to_translate)} 条")

    names = list(to_translate.values())
    ids = list(to_translate.keys())

    batch_size = 50
    for i in range(0, len(names), batch_size):
        batch = names[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]

        prompt = ("将以下植物拉丁学名翻译为中文物种名（仅返回中文名，每行一个）：\n" +
                  "\n".join(batch))

        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是植物学翻译助手。将拉丁学名译为中文，每行一个，不要编号。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            translated = resp.choices[0].message.content.strip().split("\n")
            for sid, cn_name in zip(batch_ids, translated):
                result[sid] = cn_name.strip().lstrip("0123456789. -)）")
        except Exception as e:
            print(f"  ✗ 批次 {i // batch_size + 1} 失败: {e}")
            for sid, sname in zip(batch_ids, batch):
                if sid not in result:
                    result[sid] = remove_author(sname)
        time.sleep(1)

    return result


def main():
    parser = argparse.ArgumentParser(description="物种名英→中批量翻译")
    parser.add_argument("--method", type=str, default="dictionary",
                        choices=["dictionary", "deep-translator", "openai"],
                        help="翻译方式（默认 dictionary）")
    parser.add_argument("--api-key", type=str, default="",
                        help="OpenAI API Key（仅 method=openai 时需要）")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="API 调用间隔（秒）")
    args = parser.parse_args()

    print("=" * 60)
    print(f"[翻译引擎] {args.method}")

    with open(NAME_MAP_PATH, "r", encoding="utf-8") as f:
        species_id_to_name = json.load(f)
    print(f"[输入] {len(species_id_to_name)} 个物种")

    if args.method == "dictionary":
        result = translate_dictionary(species_id_to_name)
    elif args.method == "deep-translator":
        result = translate_deep_translator(species_id_to_name, delay=args.delay)
    elif args.method == "openai":
        if not args.api_key:
            print("错误：使用 OpenAI 翻译需提供 --api-key")
            return
        result = translate_openai(species_id_to_name, args.api_key)

    # 统计覆盖率
    translated = sum(1 for v in result.values() if any('一' <= c <= '鿿' for c in v))
    print(f"\n[结果] 翻译覆盖率: {translated}/{len(result)} ({100 * translated / len(result):.1f}%)")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[输出] {OUT_PATH}")
    print("=" * 60)

    # 预览
    print("\n[预览前20条]")
    for i, (sid, cn) in enumerate(list(result.items())[:20]):
        sname = species_id_to_name.get(sid, "")
        print(f"  {sname:45s} → {cn}")


if __name__ == "__main__":
    main()
