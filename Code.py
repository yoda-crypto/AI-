import math

import streamlit as st

st.set_page_config(page_title="生成AI 総合詳細リスク判定ツール", page_icon="🛡")


# =========================================================
# 回答を調べる小さな関数
#   y(a, "A-1") … 「はい」と答えた
#   n(a, "A-1") … 「いいえ」と答えた
#   （クイック診断で聞かれなかった質問は、どちらでもない扱い）
# =========================================================
def y(a, k):
    return a.get(k) is True


def n(a, k):
    return a.get(k) is False


# =========================================================
# ルートごとの質問・スコア規則
#
# 質問:   (ID, 質問文, クイック診断でも聞くか)
# 規則:   (条件, 点数, 種類, 理由の文章)
#   種類: "legal"=法的危険度 / "flame"=倫理・炎上リスク / "good"=安全に働く要素（点数を引く）
# =========================================================
ROUTES = {
    "A": {
        "name": "ルートA：他人の著作権侵害",
        "short": "他人の著作権",
        "laws": ["著作権法 第21条（複製権）・第27条（翻案権）", "著作権法 第30条の4（非享受目的の利用）",
                 "類似性＋依拠性の要件（裁判例）"],
        "questions": [
            ("A-1", "【直接参照】既存のイラスト・写真・文章を、AIに直接読み込ませて（Img2Img等）生成しましたか？", False),
            ("A-2", "【プロンプト指定】プロンプトに、特定の作家名・既存キャラクター名・特定の作品タイトルを入力しましたか？", True),
            ("A-3", "【表現の類似性】生成物は、既存作品の「具体的表現（キャラデザイン・構図・文章の言い回し）」と酷似していますか？", True),
            ("A-4", "【作風の一致】似ているのは「絵柄・色使い・雰囲気・アイデア」だけですか？（具体的な表現は似ていない）", False),
            ("A-5", "【署名・透かし】生成画像に、元作品の「サイン（署名）」や「ウォーターマーク（透かし文字列）」が潰れて出力されていますか？", False),
            ("A-6", "【データの公開性】参照したデータは、未公表作品（限定公開・有料ファンクラブ限定コンテンツ等）ですか？", False),
            ("A-7", "【利用目的】SNS公開・商用利用・コンテスト応募など、公開や商用で使いますか？（「いいえ」＝非公開の私的利用）", True),
            ("A-8", "【オプトアウト認識】参照した作家が「AI学習拒否（オプトアウト）」を表明していることを、事前に知っていましたか？", False),
        ],
        "rules": [
            (lambda a: y(a, "A-3"), 80, "legal",
             "生成物が既存作品の具体的表現と酷似しています。類似性が認められ、依拠性もあれば、著作権侵害になります。"),
            (lambda a: y(a, "A-5"), 80, "legal",
             "元作品の署名や透かしが出力されていることは、その作品を学習・参照していた強い証拠（依拠性）になりえます。"),
            (lambda a: y(a, "A-1"), 45, "legal",
             "既存作品を直接読み込ませているため、依拠性が認められやすい状態です。"),
            (lambda a: y(a, "A-2"), 20, "legal",
             "特定の作家名・キャラ名・作品名を指定しているため、依拠性が疑われやすい状態です。"),
            (lambda a: y(a, "A-6"), 25, "legal",
             "未公表・限定公開の作品を使うと、権利者の利益を害しやすく、問題になりやすいです。"),
            (lambda a: y(a, "A-7"), 10, "legal",
             "公開・商用で使うと、権利者から指摘されたときの影響が大きくなります。"),
            (lambda a: y(a, "A-4") and y(a, "A-7"), 40, "flame",
             "絵柄・作風だけの模倣は、現行法では著作権侵害になりにくいです。ただし、クリエイターの反発や炎上のリスクがあります。（→ 中3論文の検討課題）"),
            (lambda a: y(a, "A-4") and not y(a, "A-7"), 10, "flame",
             "作風の模倣です。非公開の私的利用にとどまるため、問題になる可能性は低めです。"),
            (lambda a: y(a, "A-8") and y(a, "A-7"), 30, "flame",
             "オプトアウト（AI学習拒否）の表明を知りながら公開・商用で使うのは、法的義務はなくても、炎上や信頼低下につながりやすいです。"),
            (lambda a: y(a, "A-8") and not y(a, "A-7"), 10, "flame",
             "オプトアウトの表明を知っていました。非公開でも、作家の意思は尊重しましょう。"),
        ],
    },
    "B": {
        "name": "ルートB：自分の著作権帰属",
        "short": "自分の著作権",
        "laws": ["著作権法 第2条1項1号（著作物＝思想・感情の創作的表現）", "文化庁『AIと著作権に関する考え方』（創作的寄与）"],
        "questions": [
            ("B-1", "【プロンプト粒度】プロンプトで、構図・色彩・照明・カメラアングルなどを詳細に指定しましたか？（「いいえ」＝単語数個）", False),
            ("B-2", "【生成試行回数】数十〜数千回の試行錯誤と選別を行いましたか？（「いいえ」＝1〜数回で採用）", True),
            ("B-3", "【構造制御ツール】ControlNet、OpenPose、または自作のラフスケッチをベースに生成しましたか？", False),
            ("B-4", "【手作業の加筆・編集】人間が、大幅な手描き加筆・色調補正・リライト・レイヤー合成を行いましたか？", True),
            ("B-5", "【作業時間・レイヤー数】加筆・編集作業に、「1時間以上」または「10レイヤー以上」を費やしましたか？", False),
        ],
        # Bは「著作権獲得率」を計算します（危険度ではありません）
        "gain": {"B-1": (8, "プロンプトを詳細に指定しています。ただし、これだけでは創作的寄与とは認められにくいです。"),
                 "B-2": (7, "多数の試行と選別をしています。ただし、選択行為だけでは認められにくいとされています。"),
                 "B-3": (15, "自作のラフや構造制御ツールを使っており、人間の構成の関与を示せます。"),
                 "B-4": (50, "人間が大幅に加筆・編集した部分は、創作的寄与として認められやすいです。"),
                 "B-5": (20, "作業時間やレイヤー数が多いことは、創作的寄与を説明する材料になります。")},
    },
    "C": {
        "name": "ルートC：利用規約・ライセンス契約",
        "short": "利用規約",
        "laws": ["各サービスの利用規約・ライセンス", "民法 第415条（債務不履行）など契約上の責任"],
        "questions": [
            ("C-1", "【サービス利用規約】無料プランなど、商用利用不可の制限があるAIサービスで生成しましたか？", True),
            ("C-2", "【投稿先・提出先の規約】投稿先のSNS・コンテスト・学校などに、「AI禁止」または「AI明記義務」がありますか？", True),
            ("C-3", "【モデル固有ライセンス】RAILライセンスなどで禁止されている特定用途（医療・政治・宗教など）に利用しますか？", False),
            ("C-4", "【API・企業契約】入力データがモデルの再学習に使われない、プライバシー契約（API契約など）を結んでいますか？", False),
        ],
        "rules": [
            (lambda a: y(a, "C-1"), 60, "legal",
             "商用利用が禁止された条件で生成した作品を商用に使うと、規約違反になります。サービスの規約を確認してください。"),
            (lambda a: y(a, "C-2"), 40, "legal",
             "投稿先に「AI禁止」や「AI明記義務」があります。規定に従わないと、削除やアカウント停止の対象になりえます。"),
            (lambda a: y(a, "C-3"), 60, "legal",
             "モデルのライセンスで禁止された用途に使うと、ライセンス違反になります。"),
            (lambda a: n(a, "C-4"), 20, "legal",
             "再学習されない契約がない場合、入力した内容が学習に使われる可能性があります。個人情報や秘密は入力しないでください。"),
        ],
    },
    "D": {
        "name": "ルートD：肖像権・パブリシティ権・人権",
        "short": "肖像権・人権",
        "laws": ["肖像権（裁判例で認められた権利）・プライバシー権", "パブリシティ権（最高裁判決）",
                 "名誉毀損（刑法 第230条、民法 第709条・第710条）"],
        "questions": [
            ("D-1", "【実在人物の使用】実在する人物（有名人・芸能人・一般人）の容姿や声にそっくりな生成物ですか？", True),
            ("D-2", "【対象者の属性】モデルにした人物は「私人（友人・一般人など）」ですか？（「いいえ」＝公人・有名人）", False),
            ("D-3", "【音声ディープフェイク】実在人物の音声データをAIに学習させて、歌唱・発話を生成しましたか？", False),
            ("D-4", "【経済的利用】画像・音声を、本人の許諾なく、商品の販売・宣伝・集客に利用しますか？", True),
            ("D-5", "【名誉・信用毀損】対象の人物が、犯罪行為や不快な行為をしていると誤認させる内容ですか？", True),
        ],
        "rules": [
            (lambda a: y(a, "D-1"), 30, "legal",
             "実在人物にそっくりな生成物です。公開や利用の仕方によっては、肖像権などの問題になります。"),
            (lambda a: y(a, "D-1") and y(a, "D-2"), 10, "legal",
             "私人は、肖像権・プライバシーの保護が強く、本人の同意が特に重要です。"),
            (lambda a: y(a, "D-1") and n(a, "D-2"), 10, "legal",
             "有名人・公人の場合は、顔や名前が持つ経済的価値を守る「パブリシティ権」が問題になります。"),
            (lambda a: y(a, "D-3"), 45, "flame",
             "実在人物の声の合成は、現行法で保護の枠組みがはっきりしていません。悪用や炎上のリスクが高い領域です。（→ 中3論文の検討課題）"),
            (lambda a: y(a, "D-4"), 40, "legal",
             "本人の許諾なく、販売・宣伝・集客に使うと、肖像権・パブリシティ権の侵害になりやすいです。"),
            (lambda a: y(a, "D-5"), 80, "legal",
             "犯罪や不快な行為をしていると誤認させる内容は、名誉毀損・信用毀損にあたるおそれがあります。"),
        ],
    },
    "E": {
        "name": "ルートE：モデル追加学習（LoRA等）責任",
        "short": "LoRA追加学習",
        "laws": ["著作権法 第30条の4ただし書（著作権者の利益を不当に害する場合）",
                 "不正競争防止法（営業上の利益を侵害する行為の観点）"],
        "questions": [
            ("E-1", "【ターゲット限定】特定1人の作家、または特定の1作品だけの画像を、数十〜数百枚集めて追加学習しましたか？", True),
            ("E-2", "【取得経路】海賊版サイトや、無断転載アカウントから一括スクレイピングした画像データですか？", False),
            ("E-3", "【モデルの配布】作成したLoRA等のモデルファイル（.safetensors）を、ネット上で無償配布・有償販売しましたか？", True),
            ("E-4", "【モデルの命名・タグ】配布モデルの名称やプロンプトタグに、元の作家の固有名詞や作品名をそのまま使用しましたか？", False),
        ],
        "rules": [
            (lambda a: y(a, "E-1"), 30, "flame",
             "特定の1人・1作品だけを学習させています。画風そのものは保護されませんが、クリエイターの反発が強い行為です。"),
            (lambda a: y(a, "E-2"), 50, "legal",
             "海賊版や無断転載のデータを使うと、権利者の利益を不当に害するとして、問題になりやすいです。"),
            (lambda a: y(a, "E-3"), 40, "flame",
             "モデルを配布・販売すると、被害が広がります。不正競争の観点からも議論されている領域です。（→ 中3論文の検討課題）"),
            (lambda a: y(a, "E-4"), 25, "flame",
             "作家の名前や作品名をモデル名やタグに使うと、作家の評判を利用していると見られ、炎上しやすいです。"),
        ],
    },
    "F": {
        "name": "ルートF：偽装・透明性・表示",
        "short": "偽装・表示",
        "laws": ["景品表示法 第5条1号（優良誤認表示）", "刑法 第246条（詐欺罪）", "各プラットフォームのAI表示ルール"],
        "questions": [
            ("F-1", "【手描き偽装】AI生成物なのに、「完全手描き」「自分で執筆した」と偽って公表・販売しますか？", True),
            ("F-2", "【証拠の提示能力】AIを疑われたときに、タイムラプス動画や制作途中のPSD（レイヤー）データを提示できますか？", False),
            ("F-3", "【AI利用の明記】プラットフォームが推奨する「AI生成物マーク」やハッシュタグを明記して公表しますか？", True),
        ],
        "rules": [
            (lambda a: y(a, "F-1"), 80, "legal",
             "AI生成物を手描きと偽って販売・応募すると、購入者や審査側をだますことになり、詐欺や景品表示法違反にあたるおそれがあります。"),
            (lambda a: n(a, "F-3") and not y(a, "F-1"), 20, "flame",
             "AI使用を明記しないと、後から「隠していた」と疑われて、炎上しやすくなります。"),
            (lambda a: y(a, "F-2") and not y(a, "F-1"), 10, "good",
             "制作過程を示せるため、疑いをかけられても説明しやすいです。"),
            (lambda a: y(a, "F-3") and not y(a, "F-1"), 20, "good",
             "AI使用を明記すれば、透明性が保たれ、トラブルを避けやすくなります。"),
        ],
    },
}

RISK_ROUTES = ["A", "C", "D", "E", "F"]  # 危険度を計算するルート（Bは著作権獲得率）
ALL_ROUTES = ["A", "B", "C", "D", "E", "F"]


# =========================================================
# スコアの計算
# =========================================================
def compute_risk(route, a):
    legal = flame = good = 0
    reasons = []
    for cond, pts, kind, text in ROUTES[route]["rules"]:
        if cond(a):
            if kind == "legal":
                legal += pts
            elif kind == "flame":
                flame += pts
            else:
                good += pts
            reasons.append((kind, text))
    total = max(0, min(100, legal + flame) - good)
    return {"legal": min(100, legal), "flame": min(100, flame), "total": total, "reasons": reasons}


def compute_b(a):
    gain = 0
    reasons = []
    for qid, (pts, text) in ROUTES["B"]["gain"].items():
        if y(a, qid):
            gain += pts
            reasons.append(text)
    return min(100, gain), reasons


def risk_level(score):
    """PDFの基準：80〜100=高リスク / 40〜79=中リスク / 0〜39=低リスク"""
    if score >= 80:
        return ("high", "🔴 高リスク（違法懸念）",
                "公表・販売を直ちに中止してください。著作権法・不正競争防止法・名誉毀損罪などに抵触するおそれがあります。")
    if score >= 40:
        return ("mid", "🟡 中リスク（炎上・グレー）",
                "現行法上、直ちに違法とは言い切れませんが、社会的な炎上や損害賠償請求のリスクが高いため、AI表示を推奨します。")
    return ("low", "🟢 低リスク（適正利用）",
            "規約を守り、適正に公開・利用できる可能性が高いです。")


def show_box(level, text):
    {"high": st.error, "mid": st.warning, "low": st.success}[level](text)


# =========================================================
# レーダーチャート（SVGで描画。追加のライブラリは不要）
# =========================================================
def radar_svg(labels, values, size=460):
    cx = cy = size / 2
    radius = size / 2 - 95
    count = len(labels)

    def point(i, v):
        ang = -math.pi / 2 + 2 * math.pi * i / count
        return cx + radius * v / 100 * math.cos(ang), cy + radius * v / 100 * math.sin(ang)

    parts = [f'<svg viewBox="0 0 {size} {size}" width="100%" '
             f'style="max-width:{size}px;color:inherit" xmlns="http://www.w3.org/2000/svg">']
    for ring in (25, 50, 75, 100):
        pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in (point(i, ring) for i in range(count)))
        parts.append(f'<polygon points="{pts}" fill="none" stroke="currentColor" stroke-opacity="0.25"/>')
    for i in range(count):
        px, py = point(i, 100)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" '
                     f'stroke="currentColor" stroke-opacity="0.25"/>')
    data = " ".join(f"{px:.1f},{py:.1f}" for px, py in (point(i, v) for i, v in enumerate(values)))
    parts.append(f'<polygon points="{data}" fill="#e74c3c" fill-opacity="0.35" stroke="#e74c3c" stroke-width="2"/>')
    for i, (label, v) in enumerate(zip(labels, values)):
        px, py = point(i, 100)
        lx, ly = point(i, 122)
        anchor = "middle" if abs(lx - cx) < 10 else ("start" if lx > cx else "end")
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="14" '
                     f'fill="currentColor">{label}</text>')
        parts.append(f'<text x="{lx:.1f}" y="{ly + 16:.1f}" text-anchor="{anchor}" font-size="13" '
                     f'fill="#e74c3c">{v}点</text>')
    parts.append("</svg>")
    return "".join(parts)


# =========================================================
# 画面の状態
#   step: "mode"（モード選択）→ "route"（ルート選択）→ "ask"（質問）→ "result"（結果）
# =========================================================
ss = st.session_state
if "step" not in ss:
    ss.step = "mode"
    ss.mode = None
    ss.targets = []
    ss.queue = []
    ss.idx = 0
    ss.answers = {}


def set_mode(mode):
    ss.mode = mode
    ss.step = "route"


def pick(target):
    ss.targets = ALL_ROUTES if target == "ALL" else [target]
    ss.queue = [(r, q) for r in ss.targets for q in ROUTES[r]["questions"]
                if ss.mode == "detail" or q[2]]
    ss.idx = 0
    ss.answers = {}
    ss.step = "ask"


def answer(qid, value):
    ss.answers[qid] = value
    ss.idx += 1
    if ss.idx >= len(ss.queue):
        ss.step = "result"


def back():
    if ss.step == "result":
        ss.step = "ask"
        ss.idx = len(ss.queue) - 1
        ss.answers.pop(ss.queue[ss.idx][1][0], None)
    elif ss.idx > 0:
        ss.idx -= 1
        ss.answers.pop(ss.queue[ss.idx][1][0], None)
    else:
        ss.step = "route"


def go_route():
    ss.step = "route"


def reset():
    ss.step = "mode"
    ss.mode = None


# =========================================================
# 結果の表示
# =========================================================
def show_risk_detail(route, res):
    c1, c2, c3 = st.columns(3)
    c1.metric("危険度スコア", f"{res['total']} / 100")
    c2.metric("⚖️ 法的危険度", f"{res['legal']} / 100")
    c3.metric("🔥 倫理・炎上リスク", f"{res['flame']} / 100")
    st.progress(res["total"] / 100)
    level, label, advice = risk_level(res["total"])
    show_box(level, f"{label}　{advice}")
    icons = {"legal": "⚖️", "flame": "🔥", "good": "✅"}
    for kind, text in res["reasons"]:
        st.write(f"{icons[kind]} {text}")
    if not res["reasons"]:
        st.write("目立ったリスクの要因は見つかりませんでした。")
    st.caption("関連する法令など： " + " ／ ".join(ROUTES[route]["laws"]))


def show_b_detail(a):
    gain, reasons = compute_b(a)
    st.metric("著作権獲得率", f"{gain} / 100")
    st.progress(gain / 100)
    if gain >= 70:
        st.success("🟢 あなたの著作権が発生する可能性が高いです（加筆・編集した創作部分）。")
    elif gain >= 40:
        st.warning("🟡 グレーです。創作的寄与があるかは個別判断になり、基準があいまいです。")
    else:
        st.error("🔴 著作権が認められない可能性が高いです。（短いプロンプトのみ等はパブリックドメイン扱い）")
    for text in reasons:
        st.write("✅ " + text)
    st.caption("関連する法令など： " + " ／ ".join(ROUTES["B"]["laws"]))


def show_answers(a):
    with st.expander("あなたの回答を見る"):
        for route, (qid, text, _) in ss.queue:
            v = a.get(qid)
            st.write(f"{qid}：{'はい' if v else 'いいえ'}　（{text}）")


# =========================================================
# 画面表示
# =========================================================
st.title("🛡 生成AI 総合リスク・権利帰属 判定システム")
st.caption("※ 探究学習用のプロトタイプです。法的な助言ではありません。")

total_detail = sum(len(r["questions"]) for r in ROUTES.values())
total_quick = sum(1 for r in ROUTES.values() for q in r["questions"] if q[2])

if ss.step == "mode":
    st.subheader("診断モードを選んでください")
    st.button(f"⚡ クイック診断（約3分・各ルート2〜3問・全{total_quick}問）", on_click=set_mode,
              args=("quick",), use_container_width=True, key="mode_quick")
    st.button(f"🔍 精密詳細診断（約10分・全{total_detail}問）", on_click=set_mode,
              args=("detail",), use_container_width=True, key="mode_detail")

elif ss.step == "route":
    mode_name = "クイック診断" if ss.mode == "quick" else "精密詳細診断"
    st.caption(f"モード：{mode_name}")
    st.subheader("診断するルートを選んでください")
    cols = st.columns(2)
    for i, key in enumerate(ALL_ROUTES):
        cols[i % 2].button(ROUTES[key]["name"], on_click=pick, args=(key,),
                           use_container_width=True, key=f"route_{key}")
    st.button("📊 全ルートをまとめて診断（レーダーチャート付き）", on_click=pick, args=("ALL",),
              use_container_width=True, key="route_all")
    st.button("← モード選択に戻る", on_click=reset, key="to_mode")

elif ss.step == "ask":
    route, (qid, text, _) = ss.queue[ss.idx]
    st.caption(ROUTES[route]["name"])
    st.progress(ss.idx / len(ss.queue))
    st.caption(f"質問 {ss.idx + 1} / {len(ss.queue)}")
    st.subheader(f"{qid}　{text}")
    col1, col2 = st.columns(2)
    col1.button("はい", on_click=answer, args=(qid, True),
                use_container_width=True, key=f"yes_{ss.idx}")
    col2.button("いいえ", on_click=answer, args=(qid, False),
                use_container_width=True, key=f"no_{ss.idx}")
    st.button("← ひとつ前に戻る", on_click=back, key=f"back_{ss.idx}")

elif ss.step == "result":
    a = ss.answers
    if ss.mode == "quick":
        st.info("クイック診断は主要な質問だけなので、結果は目安です。くわしく知りたいときは精密詳細診断を使ってください。")

    if len(ss.targets) > 1:
        # ---- 全ルートの総合結果 ----
        results = {r: compute_risk(r, a) for r in RISK_ROUTES}
        overall = max(res["total"] for res in results.values())
        level, label, advice = risk_level(overall)
        st.subheader("総合結果")
        show_box(level, f"最も高いルートの危険度は {overall} / 100：{label}　{advice}")
        st.markdown(radar_svg([ROUTES[r]["short"] for r in RISK_ROUTES],
                              [results[r]["total"] for r in RISK_ROUTES]),
                    unsafe_allow_html=True)
        st.subheader("ルートB：自分の著作権")
        show_b_detail(a)
        st.subheader("ルートごとの詳細")
        for r in RISK_ROUTES:
            lv, lb, _ = risk_level(results[r]["total"])
            with st.expander(f"{ROUTES[r]['name']}　{results[r]['total']}点　{lb}"):
                show_risk_detail(r, results[r])
    else:
        # ---- 1ルートの結果 ----
        route = ss.targets[0]
        st.subheader(ROUTES[route]["name"])
        if route == "B":
            show_b_detail(a)
        else:
            show_risk_detail(route, compute_risk(route, a))

    show_answers(a)
    col1, col2 = st.columns(2)
    col1.button("← 回答を修正する", on_click=back, key="back_result")
    col2.button("別のルート・モードで診断する", on_click=reset, key="reset_result")

st.divider()
st.caption("参考：文化庁『AIと著作権に関する考え方』／著作権法第30条の4")