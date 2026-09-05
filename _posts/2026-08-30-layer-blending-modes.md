---
layout: default
title: 乗算って何をしているの？ ペイントソフトのレイヤーモードを数式で眺める
date: 2026-08-30
---

「乗算にすると暗くなる」「スクリーンにすると明るくなる」。ペイントソフトを使っていると、こうした説明をよく見かける。

でも、乗算は本当に何をしているのだろう。なぜ乗算は影に向いていて、スクリーンは光に向いているのだろう。オーバーレイは、何と何を重ねているのだろう。

この記事では、普段使っているレイヤーモードを、できるだけ数式として眺めてみる。対象は、少し理系寄りの絵描き・クリエイター。細かな実装を追いかけるのではなく、「このモードは画素にこういう計算をしているのか」と分かることを目指す。

基本の基準には、CSSやSVGの画像合成を定義している[W3Cの画像合成・ブレンド仕様](https://www.w3.org/TR/compositing-1/)を使う。この仕様には、主要な16種類のブレンドモードと、色のブレンドおよびアルファ合成の数式が定義されている。

そのうえで、Photoshopでよく見かける追加モードも補足する。ソフトによって同じ名前のモードの細部が違うことはあるが、まずは共通する計算の形をつかむことを優先する。

## この記事で扱うモード

先に全体像を示しておく。モード名をクリックすると、それぞれの説明に移動できる。

### W3Cの基本16種類

| モード | 役割 |
| --- | --- |
| [通常](#mode-normal) | 上の色をそのまま重ねる |
| [比較（暗）](#mode-darken) | チャンネルごとに暗い方を選ぶ |
| [乗算](#mode-multiply) | 色を掛けて暗くする |
| [焼き込みカラー](#mode-color-burn) | 暗くしながらコントラストを強める |
| [比較（明）](#mode-lighten) | チャンネルごとに明るい方を選ぶ |
| [スクリーン](#mode-screen) | 反転して掛けて明るくする |
| [覆い焼きカラー](#mode-color-dodge) | 明るくしながらコントラストを変える |
| [オーバーレイ](#mode-overlay) | 下の明暗で乗算とスクリーンを切り替える |
| [ソフトライト](#mode-soft-light) | 明暗を穏やかに動かす |
| [ハードライト](#mode-hard-light) | 上の明暗で乗算とスクリーンを切り替える |
| [差の絶対値](#mode-difference) | 上下の色の差を取り出す |
| [除外](#mode-exclusion) | 差の絶対値より弱い差分を作る |
| [色相](#mode-hue) | 上の色相だけを借りる |
| [彩度](#mode-saturation) | 上の彩度だけを借りる |
| [カラー](#mode-color) | 上の色相と彩度を借りる |
| [輝度](#mode-luminosity) | 上の明るさだけを借りる |

### Photoshopでよく見る追加モード

| モード | 役割 |
| --- | --- |
| [加算](#mode-add) | 色の値を足して明るくする |
| [焼き込み（リニア）](#mode-linear-burn) | 暗い方向へ直線的に変化させる |
| [減算](#mode-subtract) | 上の色を下の色から引く |
| [除算](#mode-divide) | 下の色を上の色で割る |
| [カラー比較（暗）](#mode-darker-color) | 色全体が暗い方を選ぶ |
| [カラー比較（明）](#mode-lighter-color) | 色全体が明るい方を選ぶ |
| [ビビッドライト](#mode-vivid-light) | 焼き込みと覆い焼きを切り替える |
| [リニアライト](#mode-linear-light) | 明るさを直線的に強く動かす |
| [ピンライト](#mode-pin-light) | 比較（暗）と比較（明）を切り替える |
| [ハードミックス](#mode-hard-mix) | 各チャンネルをほぼ二値化する |

## レイヤーモードは「上下の色から新しい色を作る関数」

まず、完全に不透明な2枚のレイヤーを考える。下のレイヤーの色を下地、上のレイヤーの色を重ねる色と考えると分かりやすい。

レイヤーモードは、その2つの色を入力として、選んだルールで新しい色を作る。まずは記号を使わずに書くと、次のような流れである。

```text
下の色 + 上の色 → レイヤーモードのルール → 新しい色
```

以降の式を短く書くために、この3つの色に名前を付ける。

| 記号 | 意味 |
| --- | --- |
| `C_base` | 下のレイヤーの色。下地 |
| `C_top` | 上のレイヤーの色 |
| `C_mode` | レイヤーモードが作った新しい色 |

すると、先ほどの流れは次の式になる。

```text
C_mode = f(C_base, C_top)
```

`f` の中身を入れ替えたものが、乗算・スクリーン・差の絶対値などのレイヤーモードである。

RGBの各チャンネルを `0.0`〜`1.0` に正規化して考える。たとえば、赤チャンネルについて `C_base = 0.3`、`C_top = 0.4` なら、乗算は次のようになる。

```text
0.3 * 0.4 = 0.12
```

3つのチャンネルに同じ計算をすれば、RGBの結果になる。

### まずは数値を入れてみる

下の色を `C_base = 0.25`、上の色を `C_top = 0.4` とすると、代表的なモードはこうなる。

| モード | 計算 | 結果 |
| --- | --- | ---: |
| 乗算 | `0.25 * 0.4` | `0.10` |
| スクリーン | `1 - (1-0.25)(1-0.4)` | `0.55` |
| オーバーレイ | `2 * 0.25 * 0.4` | `0.20` |
| 加算 | `0.25 + 0.4` | `0.65` |

この数字だけでも、乗算が暗くなり、スクリーンが明るくなる理由が見えてくる。

## 半透明のレイヤーでは、式の結果をさらに混ぜる

ここまでの説明は、主に上下の色が完全に不透明な場合のものである。実際のレイヤーには透明度があり、レイヤーモードは色の式を計算して終わりではない。

レイヤーモードを理解するとき、次の2段階に分けると分かりやすい。

1. 上下の色から、モード固有の色 `C_mode` を作る
2. `C_mode` を、上のレイヤーの不透明度や透明部分を使って下に重ねる

```text
C_mode = f(C_base, C_top)
C_out  = アルファ合成(C_base, C_top, C_mode)
```

ここで使う記号は次のとおりである。

| 記号 | 意味 |
| --- | --- |
| `C_out` | 最終的に表示される色 |
| `a_base` | 下のレイヤーのアルファ |
| `a_top` | 上のレイヤーのアルファ |
| `p` | レイヤー設定の不透明度 |
| `m` | マスクなどによる追加の係数 |

上のレイヤーが実際に効く不透明度は、概念的には次になる。

```text
a_top' = a_top * p * m
```

通常の合成では、出力の不透明度は次の式になる。

```text
a_out = a_top' + (1 - a_top') * a_base
```

下のレイヤーが完全に不透明なら、色については次のように考えられる。

```text
C_out = a_top' * C_mode + (1 - a_top') * C_base
```

下のレイヤーと上のレイヤーがどちらも完全に不透明なら、`a_top' = 1` なので、最終的には `C_mode` だけが残る。だから普段は、乗算を `C_base * C_top` と説明できる。

一方、上のレイヤーが50%不透明なら、乗算で作った色をそのまま表示するのではなく、乗算結果と下の色の間を補間する。レイヤーの不透明度を下げると「乗算の濃さ」が変わるのはこのためである。

## 今回の画像

以下の例は、果物の写真を下地に、上半分が虹色・下半分がグレースケールのパターンを上のレイヤーとして重ねたものである。どちらも100%不透明なので、この例では最終出力 `C_out` は各モードが作る色 `C_mode` と同じになる。以降は各モードについて、下地・上のレイヤー・合成結果の順に並べて見る。

<a id="mode-normal"></a>

## 通常

上のレイヤーを、そのまま下に重ねるモードである。

```text
C_mode = C_top
```

{% include blend-result.html mode="normal" label="通常" %}

下のレイヤーが完全に不透明なら、上のレイヤーが100%不透明のときは上の色だけが見える。上が半透明なら、`C_top` と `C_base` の間になる。

「何もしない」ように見えるが、透明度を含めると、通常はレイヤー合成の基準になる大事なモードである。

<a id="mode-darken"></a>

## 比較（暗）

下と上の色をチャンネルごとに比較し、暗い方を選ぶ。

```text
C_mode = min(C_base, C_top)
```

{% include blend-result.html mode="darken" label="比較（暗）" %}

乗算と違って色を混ぜず、各チャンネルの小さい値を選ぶ。暗い線や影だけを残したいときに使われる。

<a id="mode-multiply"></a>

## 乗算

```text
C_mode = C_base * C_top
```

{% include blend-result.html mode="multiply" label="乗算" %}

`0.0`〜`1.0` の範囲なら、結果は必ず入力の小さい方以下になる。白 `1.0` を掛けても相手の色がそのまま残り、黒 `0.0` を掛けると黒になる。

この性質が、影・陰影・線画の色付けに向いている理由である。上のレイヤーに暗い色を置くほど、下の色を暗くする効果が強くなる。

例えば、下が `0.8`、上が `0.5` なら、

```text
0.8 * 0.5 = 0.4
```

となる。

<a id="mode-color-burn"></a>

## 焼き込みカラー

下の色を暗くしながら、コントラストも強めるモードである。

```text
C_base = 1 のとき:
C_mode = 1

C_base < 1 かつ C_top = 0 のとき:
C_mode = 0

C_base < 1 かつ C_top > 0 のとき:
C_mode = 1 - min(1, (1-C_base) / C_top)
```

{% include blend-result.html mode="color-burn" label="焼き込みカラー" %}

結果は通常 `0.0`〜`1.0` に収める。上の色が黒に近づくほど、下の色が急激に暗くなる。

<a id="mode-lighten"></a>

## 比較（明）

下と上の色をチャンネルごとに比較し、明るい方を選ぶ。

```text
C_mode = max(C_base, C_top)
```

{% include blend-result.html mode="lighten" label="比較（明）" %}

黒 `0.0` はほとんど何もせず、白 `1.0` はそのチャンネルを白にする。明るい線や光だけを重ねたいときに使える。

<a id="mode-screen"></a>

## スクリーン

```text
C_mode = 1 - (1 - C_base) * (1 - C_top)
```

{% include blend-result.html mode="screen" label="スクリーン" %}

展開すると、

```text
C_mode = C_base + C_top - C_base * C_top
```

とも書ける。

黒 `0` を入れると、

```text
1 - (1 - C_base) * (1 - 0) = C_base
```

なので黒はほとんど何もしない。白 `1` を入れると、結果は `1` になる。乗算とは逆に、白い部分ほど下の色を明るくする。

光・ハイライト・発光表現に向いているのは、この性質による。

<a id="mode-color-dodge"></a>

## 覆い焼きカラー

下の色を明るくしながら、コントラストを変えるモードである。

```text
C_base = 0 のとき:
C_mode = 0

C_base > 0 かつ C_top = 1 のとき:
C_mode = 1

C_base > 0 かつ C_top < 1 のとき:
C_mode = min(1, C_base / (1-C_top))
```

{% include blend-result.html mode="color-dodge" label="覆い焼きカラー" %}

上の色が白に近づくほど、下の色が急激に明るくなる。強い光や発光の芯を作るのに向いているが、明るさが極端になりやすい。

<a id="mode-overlay"></a>

## オーバーレイ

オーバーレイは、下の色が暗いか明るいかで、乗算寄りかスクリーン寄りかを切り替える。

```text
C_base < 0.5 のとき:
C_mode = 2 * C_base * C_top

C_base >= 0.5 のとき:
C_mode = 1 - 2 * (1-C_base) * (1-C_top)
```

{% include blend-result.html mode="overlay" label="オーバーレイ" %}

暗い下地では乗算のように暗くなり、明るい下地ではスクリーンのように明るくなる。中間の `0.5` 付近を基準にコントラストを強める、と考えるとよい。

例えば `C_base = 0.75`、`C_top = 0.4` なら、下の色が明るいのでスクリーン側を使う。

```text
1 - 2 * (1-0.75) * (1-0.4) = 0.70
```

<a id="mode-soft-light"></a>

## ソフトライト

ソフトライトは、上の色に応じて、下の色を暗くしたり明るくしたりするモードである。オーバーレイよりも変化が穏やかになりやすい。

代表的な式の一つは次のように書ける。

```text
x <= 0.25 のとき:
g(x) = ((16*x - 12)*x + 4)*x

x > 0.25 のとき:
g(x) = sqrt(x)

C_top <= 0.5 のとき:
C_mode = C_base - (1 - 2*C_top) * C_base * (1-C_base)

C_top > 0.5 のとき:
C_mode = C_base + (2*C_top - 1) * (g(C_base)-C_base)
```

{% include blend-result.html mode="soft-light" label="ソフトライト" %}

式は少し長いが、見方は単純である。上の色が50%グレーより暗ければ下を暗くし、明るければ下を明るくする。

<a id="mode-hard-light"></a>

## ハードライト

オーバーレイと似ているが、明るいか暗いかを上の色で判断する。

```text
C_top < 0.5 のとき:
C_mode = 2 * C_base * C_top

C_top >= 0.5 のとき:
C_mode = 1 - 2 * (1-C_base) * (1-C_top)
```

{% include blend-result.html mode="hard-light" label="ハードライト" %}

オーバーレイが「下の画像に光を当てる」感じなら、ハードライトは「上のレイヤーから強い光を当てる」感じである。

<a id="mode-difference"></a>

## 差の絶対値

```text
C_mode = abs(C_base - C_top)
```

{% include blend-result.html mode="difference" label="差の絶対値" %}

下と上の色の差を、絶対値にして取り出す。順番を入れ替えても結果は同じである。

同じ色同士なら、

```text
abs(C_base - C_base) = 0
```

なので黒になる。白 `1.0` を重ねると、

```text
abs(C_base - 1) = 1 - C_base
```

となり、色が反転する。2枚の画像の位置合わせや差分の確認に便利なモードである。

<a id="mode-exclusion"></a>

## 除外

差の絶対値に似ているが、コントラストを弱めたような結果になる。

```text
C_mode = C_base + C_top - 2 * C_base * C_top
```

{% include blend-result.html mode="exclusion" label="除外" %}

黒 `0` では変化せず、白 `1` では色が反転する。中間の色では差の絶対値ほど強い差になりにくい。

<a id="mode-hue"></a>

## 色相

色相は、上のレイヤーから色相だけを借り、下のレイヤーの彩度と明るさを残す。

色を色相 `H`、彩度 `S`、明るさ `L` の3つに分けて考えると、概念的には次のようになる。

```text
C_mode = HSL(H_top, S_base, L_base)
```

{% include blend-result.html mode="hue" label="色相" %}

RGBの赤・緑・青を直接掛けたり足したりするモードではない。「色味だけを変えたい」ときに使う。

<a id="mode-saturation"></a>

## 彩度

上のレイヤーから彩度だけを借り、下のレイヤーの色相と明るさを残す。

```text
C_mode = HSL(H_base, S_top, L_base)
```

{% include blend-result.html mode="saturation" label="彩度" %}

彩度の低い上の色を使うと、下の色を鮮やかさの少ない方向へ動かせる。

<a id="mode-color"></a>

## カラー

上のレイヤーの色相と彩度を使い、下のレイヤーの明るさを残す。

```text
C_mode = HSL(H_top, S_top, L_base)
```

{% include blend-result.html mode="color" label="カラー" %}

モノクロ画像に色を付けたり、線画や陰影の明るさを保ったまま着色したりするときに便利である。

<a id="mode-luminosity"></a>

## 輝度

下のレイヤーの色相と彩度を残し、上のレイヤーの明るさを使う。

```text
C_mode = HSL(H_base, S_base, L_top)
```

{% include blend-result.html mode="luminosity" label="輝度" %}

カラーの反対側の使い方で、色味を保ったまま明るさだけを変えたいときに使える。

ここまでが、W3Cの仕様で定義されている基本16種類である。ここからは、Photoshopでよく見かける追加モードを扱う。

<a id="mode-add"></a>

## 加算

```text
C_mode = C_base + C_top
```

{% include blend-result.html mode="add" label="加算" %}

2つの色の光量を、そのまま足すと考えるモードである。明るい色同士を重ねると、すぐに白に近づく。

表示できる範囲に収める場合は、一般に次のようになる。

```text
C_mode = min(1, C_base + C_top)
```

ソフトによっては別の名前で呼ばれることもあるが、同じ系統のモードとして扱われることが多い。

<a id="mode-linear-burn"></a>

## 焼き込み（リニア）

```text
C_mode = max(0, C_base + C_top - 1)
```

{% include blend-result.html mode="linear-burn" label="焼き込み（リニア）" %}

2つの色を足してから `1` を引くので、暗い方向へ直線的に変化する。減算と似て見えるが、式は異なる。

<a id="mode-subtract"></a>

## 減算

```text
C_mode = max(0, C_base - C_top)
```

{% include blend-result.html mode="subtract" label="減算" %}

上の色を下の色から引くモードである。焼き込み（リニア）と似て見えるが、減算は単純に `C_base - C_top` を計算する。

<a id="mode-divide"></a>

## 除算

```text
C_mode = min(1, C_base / C_top)
```

{% include blend-result.html mode="divide" label="除算" %}

下の色を上の色で割る。`C_top = 0` では式が定義できず、`0` に近いと結果が急激に大きくなるため、実際のソフトでは特別な扱いが入る。この例の画像では、ゼロで割るチャンネルは白 `1` としている。

<a id="mode-darker-color"></a>

## カラー比較（暗）

比較（暗）はチャンネルごとに比較するが、カラー比較（暗）は色全体の明るさを比較して、下か上のどちらか一方の色を選ぶ。

```text
sum(C_base) < sum(C_top) のとき:
C_mode = C_base

sum(C_base) >= sum(C_top) のとき:
C_mode = C_top
```

{% include blend-result.html mode="darker-color" label="カラー比較（暗）" %}

ここで `sum(C)` は、RGB各チャンネルの値を足したものとする。そのため、比較（暗）のようにチャンネルごとに別々の色を組み合わせることはない。

<a id="mode-lighter-color"></a>

## カラー比較（明）

カラー比較（暗）の反対で、色全体の明るさが大きいほうを選ぶ。

```text
sum(C_base) > sum(C_top) のとき:
C_mode = C_base

sum(C_base) <= sum(C_top) のとき:
C_mode = C_top
```

{% include blend-result.html mode="lighter-color" label="カラー比較（明）" %}

比較（暗）と比較（明）の違いと同じように、チャンネル単位の比較ではなく、色全体の比較である。

<a id="mode-vivid-light"></a>

## ビビッドライト

上の色が暗いか明るいかで、焼き込みカラーと覆い焼きカラーを切り替える。

```text
C_top < 0.5 のとき:
C_mode = 焼き込みカラー(C_base, 2*C_top)

C_top >= 0.5 のとき:
C_mode = 覆い焼きカラー(C_base, 2*(C_top-0.5))
```

{% include blend-result.html mode="vivid-light" label="ビビッドライト" %}

コントラストの変化が強く、扱いも難しい。強い陰影や極端な光を作るためのモードと考えるとよい。

<a id="mode-linear-light"></a>

## リニアライト

```text
C_mode = clamp(C_base + 2*C_top - 1, 0, 1)
```

{% include blend-result.html mode="linear-light" label="リニアライト" %}

上の色を2倍してから下の色に加える。50%グレーを基準に、明るい部分は明るく、暗い部分は暗くする。

<a id="mode-pin-light"></a>

## ピンライト

上の色に応じて、比較（暗）または比較（明）に近い処理を切り替える。

```text
C_top < 0.5 のとき:
C_mode = min(C_base, 2*C_top)

C_top >= 0.5 のとき:
C_mode = max(C_base, 2*C_top - 1)
```

{% include blend-result.html mode="pin-light" label="ピンライト" %}

オーバーレイやソフトライトよりも、色の置き換わりが目立ちやすい。

<a id="mode-hard-mix"></a>

## ハードミックス

```text
C_base + C_top < 1 のとき:
C_mode = 0

C_base + C_top >= 1 のとき:
C_mode = 1
```

{% include blend-result.html mode="hard-mix" label="ハードミックス" %}

各チャンネルの結果を0か1に丸めるため、画像がほとんど二値化される。通常の塗りや調整より、ポスターのような極端な効果に向いている。
