---
layout: default
title: ペイントソフトのレイヤーモードは何を計算しているのか――GIMP/GEGLをソースから読む
date: 2026-08-30
---

「乗算にすると暗くなる」「スクリーンにすると明るくなる」。絵を描く人なら一度は使う説明だけれど、実際にはその裏で何が計算されているのだろう。

この記事では、GIMP 3 のソースコードと、その画素処理ライブラリ GEGL の実装を読みながら、レイヤーモードを数式に戻していく。対象にしたソースは、2026年8月30日時点の以下のコミットである。

- [GIMP `84e6bf9`](https://github.com/GNOME/gimp/tree/84e6bf980eeca78bb88d211e97d07f7471daabb4)
- [GEGL `88cd774`](https://github.com/GNOME/gegl/tree/88cd774f2133bf06f9d59de27a0af9ff8ed12aae)

バージョンによって式や既定の色空間が変わる可能性があるので、ここでは「GIMPならいつでもこの式」と断定せず、どのコードを読めば確認できるかも併記する。

## 先に結論：レイヤーモードは二段階の処理

GIMPのレイヤーモードは、ざっくり言えば次の二つに分かれている。

1. 下の色と上の色から、モード固有の色 `B` を作る（blend）
2. `B` を、アルファ・レイヤー不透明度・マスクを使って最終画素にする（composite）

この二段階を分けて考えると、「乗算の式は `D*S` なのに、透明部分では単純な `D*S` にならない」という一見ややこしい挙動も見通しやすい。

### 記号

以下では、RGBの各チャンネルを `0.0`〜`1.0` に正規化して書く。式は、特に断らない限りR・G・Bそれぞれに適用する。

| 記号 | 意味 | GIMPのコード上の名前 |
| --- | --- | --- |
| `D` | 下のレイヤー（backdrop / destination）の色 | `in[c]` |
| `S` | 上のレイヤー（source / layer）の色 | `layer[c]` |
| `B` | モードが作った色 | `comp[c]` |
| `αD` | 下のアルファ | `in[alpha]` |
| `αS` | 上のアルファ | `layer[alpha]` |
| `p` | レイヤーの不透明度 | `opacity` |

マスク値を `m` とすると、合成に使う上レイヤーの有効アルファは概念的に次になる。

```text
αS' = αS * p * m
```

### 通常の「union」合成

最も基本的な合成方式では、出力アルファは次の式になる。

```text
αO = αS' + (1 - αS') * αD
```

色をアルファから分離して保持する、いわゆる straight color として書けば、最終色は次の形になる。

```text
C_out = ((1 - αS') * αD * D
    + (1 - αD) * αS' * S
    + αD * αS' * B) / αO
```

`αO` が0のときは色を見ても意味がないので、実装では色成分を特別扱いしてよい。

GIMPの `gimp_operation_layer_mode_composite_union()` は、この式を展開した形で実装している。つまり、レイヤーモードの式だけでなく、アルファの式も結果を決めている。[GIMPのcomposite実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-composite.c#L42-L94)

下のレイヤーが完全に不透明で `αD = 1`、上のレイヤーも完全に不透明で `αS' = 1` なら、式は単純に次になる。

```text
C_out = B
```

普段「乗算は `D*S`」と説明できるのは、この条件が成立しているときである。

## GIMPのコードを読むときの順番

GIMP本体では、レイヤーモードの一覧と各モードの設定が [`gimp-layer-modes.c`](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimp-layer-modes.c) にまとまっている。

たとえば現在の `Multiply` は、次のように登録されている。

```c
.blend_function = gimp_operation_layer_mode_blend_multiply,
.composite_mode = GIMP_LAYER_COMPOSITE_CLIP_TO_BACKDROP,
.composite_space = GIMP_LAYER_COLOR_SPACE_RGB_LINEAR,
.blend_space = GIMP_LAYER_COLOR_SPACE_RGB_LINEAR
```

実際の色の式は [`gimpoperationlayermode-blend.c`](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-blend.c) にあり、アルファを含む配置は [`gimpoperationlayermode-composite.c`](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-composite.c) にある。

概念的な流れは、GIMPの [`gimpoperationlayermode.c`](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode.c#L662-L845) を縮めるとこうなる。

```c
// 1. 色空間をそろえ、モード固有の色を作る
blend_function(in, layer, blend_out, samples);

// 2. blend_out をアルファと不透明度で最終画素にする
composite_union(in, layer, blend_out, mask, opacity, out, samples);
```

実際のコードは、色空間の変換、インプレース処理、透明画素の高速スキップなども行う。ただし、理解の中心はこの二段階でよい。

## RGBをチャンネルごとに計算するモード一覧

以下の `B` は「blend段階の結果」であり、最終出力 `C_out` そのものではない。`D` と `S` が完全不透明なら、そのまま最終色になる。

### 基本・明暗・反転系

| モード | blend段階の式 `B = f(D, S)` | 直感 |
| --- | --- | --- |
| Normal | `S` | 上の色を使う |
| Addition | `D + S` | 光を足す。1を超えることがある |
| Subtract | `D - S` | 上の色を引く。負になることがある |
| Multiply | `D * S` | 両方が暗いほど暗くなる |
| Screen | `1 - (1 - D) * (1 - S)` | 反転して乗算し、もう一度反転する |
| Darken only | `min(D, S)` | チャンネルごとに暗い方を選ぶ |
| Lighten only | `max(D, S)` | チャンネルごとに明るい方を選ぶ |
| Difference | `abs(D - S)` | 色の差の絶対値 |
| Exclusion | `0.5 - 2 * (D - 0.5) * (S - 0.5)` | Differenceよりコントラストが弱い差分 |

GIMPのコードでも、たとえばMultiplyは次の一行にほぼ対応している。

```c
comp[c] = in[c] * layer[c];
```

ただしコードは毎画素について、入力とレイヤーのアルファが0でない場合だけRGBを計算し、その後で `comp[alpha] = layer[alpha]` としている。[Multiplyの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-blend.c#L1012-L1039)

Screenは次の一行である。

```c
comp[c] = 1.0f - (1.0f - in[c]) * (1.0f - layer[c]);
```

[Screenの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-blend.c#L1118-L1145)

AdditionやSubtractは、現在のGIMPのfloat処理では、blend関数自体が必ず `0.0`〜`1.0` に丸めるわけではない。HDRや内部の色形式まで含めて考える場合は、「1を超えたら即座に255へクリップ」と単純化しないほうがよい。

### コントラスト系

OverlayとHard lightは似ているが、分岐に使う側が違う。

```text
Overlay:
  D < 0.5 なら 2 * D * S
  それ以外は 1 - 2 * (1 - D) * (1 - S)

Hard light:
  S <= 0.5 なら 2 * D * S
  それ以外は 1 - 2 * (1 - D) * (1 - S)
```

Overlayは下の色の明るさで「暗部側の乗算」か「明部側のスクリーン」かを選ぶ。Hard lightは上の色で選ぶ。GIMPのコードでは、Overlayが `in[c] < 0.5f`、Hard lightが `layer[c] > 0.5f` を見ている。

| モード | blend段階の式 | 備考 |
| --- | --- | --- |
| Overlay | `D < 0.5 ? 2DS : 1 - 2(1-D)(1-S)` | 下の色で分岐 |
| Hard light | `S <= 0.5 ? 2DS : 1 - 2(1-D)(1-S)` | 上の色で分岐 |
| Soft light | `(1-D)(D*S) + D*(1-(1-D)(1-S))` | 現在のGIMP実装の式 |
| Linear burn | `D + S - 1` | Linear lightの暗い側 |
| Linear light | `D + 2S - 1` | 上の色を2倍して加算 |
| Pin light | `S > 0.5 ? max(D, 2S-1) : min(D, 2S)` | 明暗側でmin/maxを切り替える |
| Vivid light | `S <= 0.5 ? 1-(1-D)/(2S) : D/(2(1-S))` | Burn/Dodge系。範囲外を制限 |
| Hard mix | `D + S < 1 ? 0 : 1` | ほぼ二値化 |

OverlayのGIMP実装は次のようになっている。

```c
if (in[c] < 0.5f)
  val = 2.0f * in[c] * layer[c];
else
  val = 1.0f - 2.0f * (1.0f - layer[c]) * (1.0f - in[c]);
```

[Overlayの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-blend.c#L1041-L1076)

Soft lightは名前からHard lightの単純な弱版に見えるが、現在のGIMPの関数は、まずMultiplyとScreenを計算し、それらを下の色で補間している。

```c
gfloat multiply = in[c] * layer[c];
gfloat screen   = 1.0f - (1.0f - in[c]) * (1.0f - layer[c]);
gfloat val      = (1.0f - in[c]) * multiply + in[c] * screen;
```

[Soft lightの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-blend.c#L1147-L1179)

### 除算・焼き込み・粒子系

| モード | blend段階の式 | 数値上の注意 |
| --- | --- | --- |
| Dodge | `D / (1-S)` | `S` が1に近いと急激に明るくなる |
| Burn | `1 - (1-D) / S` | `S` が0に近いと急激に変化する |
| Divide | `D / S` | 上の色が0に近いと大きくなる |
| Grain extract | `D - S + 0.5` | 0.5を中心に差を取り出す |
| Grain merge | `D + S - 0.5` | Grain extractの逆向き |

GIMPは単純な `/` を直接使わず、`safe_div()` という補助関数を使う。現在のコードでは、分子が `1e-6` 以下なら0にし、結果をおおむね `±1e6` の範囲に制限している。これは「数学上の分母に小さなεを足す」という実装とは違うので、他ソフトと完全一致するとは限らない。[safe_divとDodge/Burn/Divide](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-blend.c#L38-L69)

### 色差・明るさを使うモード

| モード | 処理 |
| --- | --- |
| Luma darken only | 下と上の輝度を比較し、輝度の低い方のRGB全体を選ぶ |
| Luma lighten only | 下と上の輝度を比較し、輝度の高い方のRGB全体を選ぶ |
| Luminance | 上の輝度を、下の色相・色味に乗せる |

Luma darken/lightenの重みは固定値としてコードに書かれているのではなく、`babl_space_get_rgb_luminance()` から現在のRGB色空間の係数を取得している。したがって、色空間が変われば「明るさ」の比較も変わる。[Luma darken/lightenの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-blend.c#L868-L961)

Luminanceは、下の色の輝度を `Y_D`、上の色の輝度を `Y_S` とすると、概念的には次の処理である。

```text
Y_D = wR * D_R + wG * D_G + wB * D_B
Y_S = wR * S_R + wG * S_G + wB * S_B
B   = D * safe_div(Y_S, Y_D)
```

そのため、上のレイヤーから明るさを借りながら、下のレイヤーの色味を大きく変えずに済む。[Luminanceの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-blend.c#L963-L1010)

## HSV・HSL・LChは「RGBを混ぜる式」ではない

HSVやHSL、LChのモードは、R・G・Bをチャンネルごとに掛けるのではなく、いったん別の表現に読み替えて、一部の成分だけを上のレイヤーから借りる。

| モード | 上のレイヤーから使う成分 | 下のレイヤーから使う成分 |
| --- | --- | --- |
| HSV Hue | Hue | Saturation, Value |
| HSV Saturation | Saturation | Hue, Value |
| HSL Color | Hue, Saturation | Lightness |
| HSV Value | Value | Hue, Saturation |
| LCh Hue | Hue | Lightness, Chroma |
| LCh Chroma | Chroma | Lightness, Hue |
| LCh Color | Hue, Chroma | Lightness |
| LCh Lightness | Lightness | Hue, Chroma |

たとえばHSV Hueは、上のレイヤーに色相があればその色相を使い、下のレイヤーの彩度と明度を保つ。上が無彩色なら色相を取り出せないので、下の色相を残す。[GIMP公式マニュアルのHSV説明](https://docs.gimp.org/3.0/en/layer-mode-group-hsv.html)

GIMPの実装は、必ずしも `RGB -> HSV -> RGB` という関数をそのまま呼ぶ形ではない。最大値・最小値・差分を使った比率計算で同じ成分交換を行い、ゼロ除算を避ける分岐も入れている。[HSVの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-blend.c#L480-L633)

LCh系は、GIMPのコード上ではLabの `L`, `a`, `b` 成分を使っている。`a` と `b` を極座標として見ると、次のように読める。

```text
Chroma = sqrt(a*a + b*b)
Hue    = atan2(b, a)
```

たとえばLCh Chromaでは、下の `a,b` の向きを保ったまま、上の `a,b` の長さを使う。コードにも `hypotf()` と比率計算が現れる。[LChの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode-blend.c#L635-L767)

## 色空間が違えば、同じ式でも結果が違う

ここが、数式一覧だけでは見落としやすいポイントである。

GIMPはモードごとに、どの色空間でblendするかを登録している。現在の設定例は次の通り。

| モードの例 | blendする色空間 |
| --- | --- |
| Multiply, Addition | RGB linear |
| Screen, Overlay, Difference | RGB perceptual |
| HSV Hue/Saturation/Value, HSL Color | RGB non-linear |
| LCh Hue/Chroma/Color/Lightness | Lab |

つまり `0.5` は、常に同じ物理的な明るさを意味するわけではない。Overlayの境界 `0.5` をlinear RGBで判定するのか、知覚的なRGBで判定するのかで、暗部・明部の境界自体が変わる。

この設定は、モードを登録している [`gimp-layer-modes.c`](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimp-layer-modes.c#L438-L573) で確認できる。また実行時には、GIMPが `babl_process()` を使ってblend空間とcomposite空間の間を変換してから、モード関数を呼んでいる。[色空間変換とblend呼び出し](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationlayermode.c#L677-L791)

## 「GIMPのMultiply」と「GEGLのmultiply」は同じか

名前が似ていても、ソース上では別の層にある。

GIMPのレイヤーモードは、上で見たように、色を作る関数とアルファ合成を組み合わせる。一方、GEGLには単体の `gegl:multiply` というpoint composerもあり、対応するソースは次のような数学演算として生成されている。

```c
result = input * value;
```

[GEGLのmultiply](https://github.com/GNOME/gegl/blob/88cd774f2133bf06f9d59de27a0af9ff8ed12aae/operations/generated/multiply.c#L94-L116)

さらにGEGLのSVG系ブレンドには、アルファを式の中に含める `svg:overlay` もある。そこでは、完全不透明時の `D < 0.5` に相当する判定が、premultiplied colorを前提に `2 * cB > aB` と書かれている。

```c
aD = aA + aB - aA * aB;

if (2 * cB > aB)
  out[j] = 2 * cA * cB + cA * (1 - aB) + cB * (1 - aA);
else
  out[j] = aA * aB - 2 * (aB - cB) * (aA - cA)
         + cA * (1 - aB) + cB * (1 - aA);
```

[GEGLのOverlay実装](https://github.com/GNOME/gegl/blob/88cd774f2133bf06f9d59de27a0af9ff8ed12aae/operations/generated/overlay.c#L132-L164)

GEGLのこのファイルは手書きの唯一の実装ではなく、[`svg-12-blend.rb`](https://github.com/GNOME/gegl/blob/88cd774f2133bf06f9d59de27a0af9ff8ed12aae/operations/generated/svg-12-blend.rb) から生成されたファイルである。ソースを読むときは、

- GIMPのレイヤーモードか
- GEGLの単体演算か
- straight colorかpremultiplied colorか
- blend処理かcomposite処理か

を最初に確認しないと、同じ「Overlay」という名前でも式が一致しない。

## composite mode：色だけでなく、どこまで残すかも選ぶ

GIMPには、blend modeとは別にcomposite modeがある。代表的には次のような違いである。

| composite mode | 意味 |
| --- | --- |
| Union | 上と下の領域を合成する。通常のアルファoverに近い |
| Clip to backdrop | 下のレイヤーの不透明領域に結果を制限する |
| Clip to layer | 上のレイヤーの不透明領域に結果を制限する |
| Intersection | 両方が重なる領域だけを残す |

たとえば `Clip to backdrop` では、GIMPのコードは概念的に次を行う。

```text
αO = αD
C_out = B * αS' + D * (1 - αS')
```

`Multiply` や `Screen` など、現在のGIMPで多くの色モードに設定されているのがこの方式である。上のレイヤーが下のレイヤーの外側まで広がっていても、外側のアルファを新しく生やさない。

この仕組みがあるため、「blend式が同じなのに、レイヤーの端の透明部分で見え方が違う」という現象が起こる。色の式を調べるときは、`composite_mode` も一緒に見る必要がある。

## 色を混ぜない特殊モード

すべてのレイヤーモードが、RGBの `D` と `S` から新しい色を作るわけではない。

| モード | 主な処理 |
| --- | --- |
| Dissolve | 乱数で各画素を上か下のどちらかに振り分ける。半透明部分を粒状にする |
| Color Erase | 上の色と下の色の差から、下の色をどれだけ透明にするかを計算する |
| Erase | 上の有効アルファで下のアルファを減らす。通常は `αO = (1 - αS') * αD` |
| Merge | 上下のアルファが重複して数えられないようにして加える。unionでは `αO = min(αD, 1-αS') + αS'` |
| Split | 上下のアルファの差を取り、重なっている部分を透明にする |
| Pass through | 色の式ではなく、グループ内部を下のレイヤーと一緒に合成する指示 |

Dissolveは連続的な数式で色を補間するモードではない。現在の実装では、乱数値と `layer_alpha * opacity * 255` を比較し、当選した画素は上の色、外れた画素は下の色を出力する。[Dissolveの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationdissolve.c#L105-L174)

EraseとSplitは、色よりもアルファを処理するモードである。[Eraseの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationerase.c#L85-L160) [Splitの実装](https://github.com/GNOME/gimp/blob/84e6bf980eeca78bb88d211e97d07f7471daabb4/app/operations/layer-modes/gimpoperationsplit.c#L85-L156)

## Legacy modeには注意する

GIMP 2.10以降、レイヤーモードは変更され、古いファイルとの互換性のためにlegacy modeも残されている。公式マニュアルにも、legacy modeは古いGIMPで作られた画像の読み込みや、他形式との互換性のために使われると説明されている。[GIMP公式マニュアル：Legacy Layer Modes](https://docs.gimp.org/3.0/en/gimp-concepts-layer-modes-legacy.html)

したがって、次の二つは同じとは限らない。

```text
Overlay
Overlay (legacy)
```

特にlegacyのOverlayは、歴史的なバグのため実質的にSoft lightと同じ式になっていると公式マニュアルに記載されている。古いXCFを再現したいのでなければ、現行のDefault側のモードを使うほうが、意図を説明しやすい。

## ソースから自分で一覧を作る

GIMPとGEGLのリポジトリを取得して、まず関数名を一覧するなら次のようにできる。

```bash
git clone --depth 1 https://github.com/GNOME/gimp.git
git clone --depth 1 https://github.com/GNOME/gegl.git

rg -n "^gimp_operation_layer_mode_blend_" \
  gimp/app/operations/layer-modes/gimpoperationlayermode-blend.c

rg -n "GEGL_OP_NAME|description.*blend" \
  gegl/operations/generated gegl/operations/workshop
```

GIMP側だけを調べるなら、次の三つを押さえればよい。

1. `gimp-layer-modes.c`：モード名、blend関数、色空間、composite modeの対応
2. `gimpoperationlayermode-blend.c`：モード固有の色の式
3. `gimpoperationlayermode-composite.c`：アルファ、不透明度、マスクの合成式

## まとめ

レイヤーモードを数式にすると、名前の印象よりずっと機械的である。

- Multiplyは、基本的には `D*S`
- Screenは、反転してから乗算する `1-(1-D)(1-S)`
- Overlayは、下の色を境にMultiplyとScreenを切り替える
- DodgeやBurnは除算なので、0付近の扱いが重要
- HSV・HSL・LChは、RGBを直接混ぜずに成分を交換する
- しかし、これらの式は最終画素そのものではなく、blend段階の結果である
- アルファ、不透明度、マスク、composite mode、色空間が最終結果を決める

絵描きにとっての「モードの使い分け」は経験則に見えるけれど、ソースまで降りていくと、暗くなる・明るくなる・色味だけ変わるという感覚が、かなり素直な数式として現れてくる。
