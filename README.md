# Blah default reaction artwork

Offline, reproducible conversion of Google's [Noto Animated Emoji](https://googlefonts.github.io/noto-emoji-animation/)
into the seven documents needed by `messages.getAvailableReactions`: 👍, 👎, **❤ (U+2764, no VS16)**, 💯, 🤣, 👀, 🥳, 🫪, and 😜.
The intended remote is `https://github.com/laosb/blah-reaction-art`; intended Blah submodule location:
`third_party/blah-reaction-art`. No server or client changes are included.

Tool code is **MIT** ([LICENSE](LICENSE)); source and adapted artwork are **CC BY 4.0**
([LICENSE-artwork](LICENSE-artwork), [NOTICE](NOTICE)). Ship the artwork attribution with the server/client distribution.

## Use

Python 3.13; the reference environment is Python 3.13.15, Linux aarch64. Install once:

```sh
uv venv --python 3.13.15
uv pip install --python .venv/bin/python --only-binary=:all: -r requirements.txt
.venv/bin/python art.py build
.venv/bin/python art.py check
.venv/bin/python art.py preview
```

`build` generates and validates a temporary tree before replacing `reactions/`; validation failure preserves
existing outputs. `check` regenerates in a temporary directory,
compares the **entire output file set and every byte**, then checks each TGS's syntax/profile, size,
canvas, source-speed timing (unchanged keyframes and exact source poses at every frame), renderer load,
visible bounds at **every integer frame**, transparent effect endpoints,
and exact pixel equality of resting poses at hand-offs. It also validates the WebP format and dimensions.
Both commands are offline. They verify the source hashes before conversion. They exit nonzero on failure.

Only this separate command uses the network:

```sh
.venv/bin/python art.py fetch
```

It refreshes the files and retrieval date/SHA-256 in `sources/manifest.json` from the URLs already recorded there.
Review changed sources before rebuilding. Add another emoji with
`art.py fetch --codepoint 1f604 --title 'Smiling Face'`, then build/check. This records URL, filename,
retrieval date and hash automatically, deriving the reaction string from the codepoints without VS16.
The Blah server owns its reaction vocabulary; Bot API membership is not required. Normalization and particle colors are
generic; there are no emoji-specific branches. Sources require a square canvas, 60 fps and ip=0.
Embedded vector precompositions, null/shape layers, authored precomp time remapping/stretch and alpha/inverted-alpha
mattes are preserved; external assets remain forbidden. Unfamiliar features need validation and visual review.
The added Blah strings are **🥳 U+1F973**, **🫪 U+1FAEA** (Emoji 17), and **😜 U+1F61C**,
each without VS16. They need not belong to Telegram’s Bot API reaction vocabulary.

`requirements.txt` pins Pillow and the rlottie binary distribution exactly. [toolchain.json](toolchain.json)
records Python, platform, zlib, libwebp and the native renderer hash used for the checked-in bytes. Serialization
uses deterministic insertion order (including source field order), six decimal places (nine for rebased frozen
remap values to preserve renderer rounding), no NaN or negative zero,
and compact UTF-8. **Do not alphabetically sort Lottie properties:** the packaged rlottie parses the sorted Noto
thumbs to blank output. Gzip uses level 9, mtime 0 and no filename. WebP is lossless RGBA, method 6, quality 100,
exact transparent RGB, no metadata. Repeated regeneration in the reference toolchain is byte-identical.
Other architectures/native library builds are not claimed byte-identical; `check` detects any such differences.

## Evidence and limits of the research

Research date: 2026-10-28. [research.json](research.json) records checkout HEADs **and hashes of the actual files**;
the local working trees contain changes, so HEAD alone does not identify the inspected code.
Sources below use these abbreviations (paths are relative to the checkout):

| ID | File |
|---|---|
| I-context | Telegram-iOS `submodules/ReactionSelectionNode/Sources/ReactionContextNode.swift` |
| I-node | Telegram-iOS `submodules/ReactionSelectionNode/Sources/ReactionSelectionNode.swift` |
| I-button | Telegram-iOS `submodules/Components/ReactionButtonListComponent/Sources/ReactionButtonListComponent.swift` |
| W-menu | tweb `src/components/chat/reactionsMenu.ts` |
| W-reaction | tweb `src/components/chat/reaction.ts` |
| W-css | tweb `src/scss/partials/_reaction.scss` |
| W-sticker | tweb `src/components/wrappers/sticker.ts` |
| W-effect | tweb `src/components/wrappers/stickerAnimation.ts` |
| T-reaction | TDLib `td/telegram/ReactionManager.cpp` |
| T-sticker | TDLib `td/telegram/StickersManager.cpp` |

Public searches and local fixture searches did **not** yield the seven actual Telegram documents for the original three
reactions. No Telegram account, credentials or authenticated API was used. Telegram Web A's
`src/lib/gramjs/client/mockUtils/createMockedAvailableReaction.ts:16–27` reuses a single animation for several slots
and explicitly says some are unused: that mock is **not** evidence of production per-slot timings.

Real bundled reference assets were measured in tweb `public/assets/tgs/` and iOS
`submodules/TelegramUI/Resources/Animations/star_up/`. None are redistributed in the repository.
The original three reactions' production padding, durations, static dimensions and exact TL attributes
remain **unknown**. We calibrate to the paid Star's measured artwork, adapting its geometry where builtin
emoji use different client paths. These are not recovered production values for 👍/👎/❤.
The [availableReaction API](https://core.telegram.org/constructor/availableReaction)
defines the slot roles; the local client code is the authority for layout and playback.

## Measured Telegram references

Measured using **the actual iOS vendored rlottie**, compiled locally. All TGS/JSON references have a
512×512 canvas and 60 fps. Bounding boxes are `(left,top,right,bottom)`, right/bottom exclusive,
alpha > 0, rendered at 512×512 on **every integer frame**. Frames in the last column are relative to `ip`.
Union boxes below include the effects and are clipped to the reference canvas; they are not just the central
emoji's bounds. Peak means greatest nontransparent pixel count, not greatest bounding-box area.

| Reference | ip→op / duration | First → last bbox | All-frame union bbox | Visible frames; peak area frame |
|---|---|---|---|---|
| tweb StarReactionAppear | 0→43 / 0.717 s | empty → (63,72,449,446) | (10,16,494,477) | 1–42; 31 |
| tweb StarReactionSelect | 0→121 / 2.017 s | (63,72,449,446) → same | (3,8,509,499) | 0–120; 36 |
| tweb StarReaction | 0→125 / 2.083 s | (62,71,450,447) → same | (0,0,512,512) | 0–124; 76 |
| tweb StarReactionEffect1 | 60→150 / 1.500 s | empty → empty | (8,0,511,512) | 1–88; 21 |
| tweb StarReactionEffect2 | 0→83 / 1.383 s | empty → empty | (12,8,511,502) | 3–78; 47 |
| tweb StarReactionEffect3 | 9→94 / 1.417 s | empty → empty | (0,0,512,512) | 1–83; 18 |
| tweb ReactionGeneric | 2→91 / 1.483 s | empty → empty | empty | none |
| iOS star_reaction_appear | 0→46 / 0.767 s | empty → (62,71,450,447) | (11,56,499,489) | 1–45; 27 |
| iOS star_reaction_select / activate / center | 0→125 / 2.083 s | (62,71,450,447) → same | (0,0,512,512) | 0–124; 76 |
| iOS star_reaction_effect | 0→90 / 1.500 s | empty → empty | (8,21,471,500) | 1–81; 48 |
| iOS star_reaction_static_icon.webp | **72×72**, one frame | (8,10,64,63) | same | n/a |

The Star picker's rest spans **386×374**, centered at (256,259), with padding (63,72,63,66).
Appear f42 and Select f0 are **byte-identical RGBA** in rlottie. Select also ends in that resting pose.
We target the same largest resting dimension (386), center the Noto pose at (256,256), and use the same
43-frame entrance. Select/activate durations follow each Noto source at its native speed, with exact
endpoint pixel equality; they do not copy the Star’s duration or late flash.

StarEffect1 starts one frame after the icon and peaks at f21 (0.350 s), with a roughly full-canvas burst.
StarEffect2/3 have multiple differently timed splashes, stars and rings; they are not duplicate central icons.
At tweb's **80 px effect / 22 px paid icon**, the union's width is 78.6 px versus a 16.7 px resting icon,
about **4.7× the visible icon width**. Our builtin center needs a 40 px padded canvas; its roughly 214-unit
rest span and the around effect's roughly 475-unit union give a comparable **4.4×** maximum span ratio.
Our first particles appear at f4, expand rapidly through f21, then drift and fade through f83. Their weight
is deliberately quieter than the paid Star's multi-stage rings/flashes.

**ReactionGeneric is a transform template, not a visible burst.** Its only asset, `comp_0`, has no layers.
Raw rlottie output is correctly empty throughout. W-reaction:232–250 extracts seven `placeholder_` layers;
:1335–1406 draws copies of the current emoji with those positions, opacity and signed scales (×4), on a
separately sized canvas, and :1265 mirrors the container. It combines this flight with a separately obtained
generic effect document. Its raw blank contact-sheet row is intentional; we do not claim it is complete
generic fallback artwork, and our builtin reaction composites do not invoke that fallback path.

Paid Star has distinct layout behavior: W-reaction:1501–1506 uses only the burst over the existing paid
icon, which `src/lib/customEmoji/renderer.ts:989–1002` loops. Its picker uses play-once animations
(W-menu:642–665). iOS I-context:3424–3435 centers Star's 240 pt effect over a 120 pt icon, whereas builtin
large effects are offset ±70 pt. Reference composites respect those differences; the Star's unpadded center
is **not** used to infer builtin center padding. iOS `TelegramCore/Sources/State/AvailableReactions.swift:385–393`
maps the bundled Star resources to slots, using the same effect for around and large application. Its locally
constructed media attributes (:8–29) are not evidence of server-supplied TL document attributes.

Compact measurements, artifact hashes and the renderer binary hash are in
[reference-measurements.json](reference-measurements.json); every frame's bbox/area is in
`.previews/reference-measurements-all-frames.json`. Reproduce measurements and side-by-side comparisons:

```sh
.venv/bin/python art.py references \
  --references /workspace/tweb-c104745bc8/public/assets/tgs \
  --ios-references /workspace/Telegram-iOS-36444c32f3/submodules/TelegramUI/Resources/Animations/star_up \
  --library .cache/ios-build/librlottie.so
```

This optional audit reads external trees; normal build/check/preview need only this repository.

## Per-slot contract and manipulation

All generated TGS: **512×512, fr=60, ip=0**. `op` is the exclusive authored endpoint; previews use 0…op−1.
The packaged rlottie reports op+1 frames, while the iOS fork reports op; endpoint holds also cover the packaged
renderer’s extra frame. Playback mode belongs to the **client**, not a TGS loop flag.

The resting pose is source frame `r`: the `tm` of the single marker with `cm == "rest"`, or 0 when absent.
It must be integral and satisfy `0 ≤ r < op`; duplicate rest markers are rejected. Noto's
[FAQ](https://googlefonts.github.io/noto-emoji-animation/) says the static “start” frame is marked as keyframe “rest”.
Its visible bounding-box center is placed at (256,256). A single scale
targets **386 units in the largest resting dimension**, capped so source motion extends no more than
244 units from that anchor. Actual generated bounds are checked after entrance overshoot/rotation too.
Resting bounds after normalization: 👍/👎 `(83,63)–(429,449)`, ❤ `(63,80)–(449,432)` (iOS rlottie).
All icon slots share this pose/anchor; center uses **55%** of the full scale. Static renders it at 72 px.

| Slot | Chosen file/timing | Actual client geometry, layering and playback (file:line) | Resulting manipulation / endpoint contract |
|---|---|---|---|
| `static_icon` | Lossless transparent WebP, **72×72**, one still; matches bundled iOS static size | T-reaction:881–884 demands WebP; W-menu:679 uses it when animations are disabled; W-reaction:783–795 falls back to it, :863–872 requests 22 px block /14 px inline. I-button:1229–1265 normally takes center. Web A `src/components/common/reactions/ReactionStaticEmoji.tsx:40–47,88–110` uses static directly. | Full normalized rest. Static at 22 px matches center at 40 px because 40×0.55=22; raster filtering can differ slightly. |
| `appear_animation` | TGS, **op=43 (0.717 s)**; matches tweb Star | I-node:550–553 `.once`, same centered frame as still; :330–340 factor 1, offset 0. I-context:1282 defaults picker item to 36 pt, :939 selected item to 1.5×. W-menu:48,611–620 uses 28 px (35 with desktop hover raster scale); :709–730 plays appear then hides it at maxFrame. | Frozen rest scales from 15% at f0 to 106% at f12, settles at f24; painted layers fade 0→100% through f6. f0 transparent; f24–42 hold select f0 exactly. |
| `select_animation` | TGS, **op=source op+7**; counts below | I-node:450 `.still(.start)` or `.loop` if loopIdle; :535–537 first-frame static preview. W-menu:736–745 loads first frame hidden; :790–814 restarts on hover after appear pauses. W-sticker:431–434 forwards loop/autoplay; `src/lib/lottie/lottiePlayer.ts:158–173,985–995` handles completion. Same centered box as appear. | Hold rest through f5; source frame `(r+f) mod source op` plays at output `f+6`, at 60 fps. The final frame closes the native Noto loop at exact rest, with no added easing. Both ends equal appear’s final frame; loops seamlessly. |
| `activate_animation` | TGS, **op=max(source op+7,61)** | I-context:1693 maps largeList to activate; :2716–2720/:3423 sets **120×120 pt** centered on target. I-node:361–363 plays once at 2× raster resolution. Current W-menu/W-reaction use center/around for builtin reactions, with no activate/effect consumer. | Same native-speed Noto timeline as select, plus −5°/+4°/0° rotation at f18/36/60. First/final frames equal full rest. Separate from particles. |
| `effect_animation` | TGS, **op=90 (1.5 s)**; matches iOS Star and tweb Effect1 duration | I-context:1695 maps largeApplication to effect; :2724–2777/:3430–3497 draw **240×240 pt**, center displaced **−70 pt outgoing / +70 pt incoming** from 120 pt activation. Incoming is mirrored. Added above center, `.once`; raster at 2× or 1.33×. No builtin tweb consumer. | **18 particles only**, circles/diamond paths. Origin `(405⅓,256)` maps to activation center: 240×405⅓/512−120=70. Leftward fan, mirrored for incoming. Palette sampled from visible, contrasting source paint at rest `r`. Stagger f3/5/7, fast spread to f21, fade to empty by f84; no central emoji. |
| `around_animation` | TGS, **op=90 (1.5 s)**; matches tweb Effect1 duration | I-context:1694/:3437 expands by full center-canvas width on each side: **3× canvas**, e.g. 120 pt around 40 pt center; :3494 `.once`, above center. W-reaction:1074–1094,1158–1168 uses **80 px**; W-effect:169–180 centers it, :117–120 plays once. Center and around start together at W-reaction:1435–1444. | **14 particles only**, centered (256,256), radial distance 72→224/234/244; diameters 26/32/38. Rapid spread through f21, then drift/fade to empty by f84, hold through f89. Clear center for center_icon; effect lies outside bubble clipping. |
| `center_icon` | TGS, **op=max(source op+7,90)**; covers around and native motion | I-button:172–186,235–274 draws builtin canvas at **2×** logical icon, centered; :832 uses 20 pt icon→40 pt canvas. Idle is still at :1230–1239; I-context/I-node use `.once` on small application. W-reaction:793,863–872 picks static center; W-css:45–53 enlarges to 40 px for 22 px block (offset −9), 28 for 14 inline (offset −7). W-reaction:1205–1221 uses matching overlay; :1422–1444 removes it at end. | Native-speed select timeline at constant **0.55× picker scale**: six-frame rest lead, rotated source loop from `r`, exact rest closure, then rest through the endpoint. First/last frames identical so removal reveals the same idle center. No particles. |

| Emoji | Rest r | Source op | Appear | Select | Activate | Effect | Around | Center |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 👍 | 0 | 72 | 43 | 79 | 79 | 90 | 90 | 90 |
| 👎 | 0 | 72 | 43 | 79 | 79 | 90 | 90 | 90 |
| ❤ | 75 | 110 | 43 | 117 | 117 | 90 | 90 | 117 |
| 💯 | 105 | 135 | 43 | 142 | 142 | 90 | 90 | 142 |
| 🤣 | 59 | 60 | 43 | 67 | 67 | 90 | 90 | 90 |
| 👀 | 0 | 120 | 43 | 127 | 127 | 90 | 90 | 127 |
| 🥳 | 107 | 108 | 43 | 115 | 115 | 90 | 90 | 115 |
| 🫪 | 52 | 168 | 43 | 175 | 175 | 90 | 90 | 175 |
| 😜 | 54 | 95 | 43 | 102 | 102 | 90 | 90 | 102 |

Counts are exclusive `op`, at 60 fps; static icons are one still. Moving slots hold rest for six frames,
then play `r…op−1, 0…r−1, r` at native speed. Only enclosing composition start offsets change;
all live source keyframes, authored precomp time remapping and `sr` remain intact. Center/activate hold
`r` through any minimum-duration extension. Zero-rest outputs remain byte-identical to the previous build.

Rest holds freeze an offset nested composition at time zero using two equal animated remap keys
(rlottie ignores static remapping). Short frozen outputs rebase authored remap clocks in separate copies
at `r`, avoiding rlottie's root-duration clamp; interpolation, geometry and authored stretch remain intact.
An integral nested offset restores the shifted clock after stretch. Static rasters use a full-duration
internal composition, so their authored clocks are never clamped by a one-frame wrapper.
Every output pose is compared exactly with that renderer's raw source, including all frozen entrance frames.
Explicit visibility holds prevent overlap at layer endpoints in renderers that include `op`.
Source markers are consumed during conversion and omitted from outputs.

Tweb’s reaction paths set `skipRatio: 1` and leave speed at 1. Its optional frame skipping advances both
frame index and interval by the same factor, preserving elapsed motion time. iOS advances one frame per
`1/frameRate` timer tick. Appear uses a frozen source pose; its designed entrance and the independent
90-frame particle timelines keep their original timing. Center plays the same native source motion as select.
Preview APNGs use exact 1/60-second delays (identical adjacent frames may be combined into a longer hold). iOS’s large-reaction UI can
dismiss on effect completion or its two-second fallback (`ReactionContextNode.swift:3719–3757`);
this can hide the end of longer activations, but does not change their playback rate.

The 55% center ratio exactly compensates tweb block's 40/22 expansion. iOS's 2× and Web A's 1.9×
(`ReactionAnimatedEmoji.tsx:53–55,187–196`) are different; a single file cannot make all static/animated ratios
mathematically identical. In iOS, idle and animated states both use the same padded center at 40 pt, so there is
no hand-off jump. Full picker→large activation resizing and travel are client-side transforms.

The small and large effects share timing and primitives but differ in count, origin and extent.
No slot contains another slot's central emoji. Parent nulls apply geometric transforms; opacity must be on
painted layers because Lottie parenting does not inherit parent opacity.

The motion amplitudes, 14/18-particle counts, palette, stagger, 6% entrance overshoot
and activation tilt are original design choices, visually calibrated against those reference composites;
they are not measured Telegram production parameters. Both generated bursts reach their maximum painted
area at f21. iOS rlottie measurements of the original three outputs (2026-10-30), including
native center motion; bounds cover every authored integer frame:

| Output (512 canvas) | Rest bbox (first select/center frame) | All-frame motion union |
|---|---|---|
| 👍 select_animation | (83,63,429,449) | (82,57,442,470) |
| 👍 center_icon | (160,149,352,363) | (160,146,358,374) |
| 👎 select_animation | (83,63,429,449) | (83,39,442,455) |
| 👎 center_icon | (160,149,352,363) | (160,136,359,365) |
| ❤ select_animation | (63,80,449,432) | (54,72,458,448) |
| ❤ center_icon | (150,159,362,353) | (145,155,367,362) |
| All three: around_animation | empty | (13,28,489,495) |
| All three: effect_animation | empty | (87,48,394,438) |

## Renderer compatibility and validation policy

The task's description of the checked-out renderers is partly stale: tweb currently imports **tlottie WASM**
from `src/lib/lottie/lottieLoader.ts:17–26`, pinned by `src/vendor/tlottie/README.md` to
`dkaraush/tlottie@758c7cb74444f1c3c9923065c40fdb3aad8b7d60`. iOS supports both rlottie and tlottie through
`submodules/LottieBinding/Sources/MakeLottieInstance.swift:43–76`. We tested the **actual tweb SIMD WASM**,
the **actual iOS vendored rlottie built locally**, and the pinned rlottie-python native renderer.
This is not lottie-web-only validation.

| Rule / claim | Evidence and policy |
|---|---|
| 512×512, 60 fps, ≤3 seconds, ≤64 KiB gzip | Canvas, rate, duration and size limits follow [Telegram's sticker requirements](https://core.telegram.org/stickers) and the real bundled assets above. `check` enforces all four; our longest files are 175/60 = 2.917 s. |
| TGS document thumbnail type / format | **`m`, lossless RGBA WebP.** T-sticker:3348–3360 accepts `m` (also `s`/`t`), :2162–2178 prefers `m` and defaults to WebP; :2945–2960 says server-generated thumbnails are WebP and excludes stripped/progressive sizes. This is a document thumbnail, not a sticker-set TGS thumbnail. |
| Thumbnail pixel size | **128×128 chosen compatible size, not a confirmed production constant.** tweb `src/lib/appManagers/utils/photos/choosePhotoSize.ts:14–60` uses supplied `w/h` (2× request on high-DPI), with no fixed sticker size/type mapping. Its generic `m box 320x320` comment is not a sticker requirement. W-sticker:209–211,709–712 downloads that thumbnail for static TGS. iOS `TelegramCore/Sources/ApiUtils/TelegramMediaFile.swift:165–177` preserves supplied dimensions/type in `CloudDocumentSizeMediaResource`; `StickerResources/Sources/StickerResources.swift:42–49` selects the largest preview. None establishes 128 as mandatory. No authenticated production document was available to confirm its exact raster size. |
| Thumbnail padding / resting frame | Full 512 canvas rendered directly to 128, **no crop**, no added border; center retains 0.55 scale. iOS `StickerResources/Sources/StickerResources.swift:489–514` draws the color/alpha image into its fitted rectangle; its 10 px inset (:466–486) belongs to a blurred placeholder, not server raster padding. W-sticker renders the downloaded image in the existing canvas. First frame for center/select/activate; last authored frame (`op−1`) for appear; empty first frame for both effects. |
| Hard client bounds | iOS `MakeLottieInstance.swift:13–29`: rejects dimension >1536, fps >360, duration >9 s. These are **looser** than sticker authoring guidance. T-sticker:2990–3022 requires sticker/custom-emoji attributes and matching MIME, but does not parse Lottie duration/fps there. `td/telegram/StickerFormat.cpp:152–165` gives TGS 65,536 bytes, ordinary WebP 524,288 bytes (upload limit; not a reaction-specific download validator). |
| No masks/mattes | Not a blanket renderer limitation. iOS `submodules/rlottie/rlottie/src/lottie/lottieparser.cpp:1015–1020` parses mattes and masks; `lottieitem.cpp:191–215,303–330,647–695` renders them. Source **alpha/inverted-alpha track mattes (tt=1/2, td=1)** are retained, with parent linkage and adjacency intact. Removing them changes visible pixels. Both actual client renderers load/render them. Masks themselves are unnecessary here and rejected by our narrower profile. |
| Gradient strokes, star shapes, repeaters, auto-orient | iOS parser :982–986,1021–1022,1156–1168 has implementations/hooks for these documented prohibitions. Parsing alone does not establish complete feature parity; we do **not** need or allow them in this output profile. This is not a claim that every renderer supports every variant. |
| Time stretching | Positive finite authored `sr` is preserved on precomps, like authored time remapping; iOS `lottiemodel.h:626–644` applies it natively. Every source pose and rest hold is validated against that renderer’s raw source in all three renderers. Non-precomp stretch is rejected. |
| Merge paths | Identity merges with ≤1 input path are removed, with exact raw/normalized pixels at every source frame in all three renderers. Real merges are rejected; iOS parser :1169–1171 says unsupported. |
| Expressions, images, solids, text, 3D, layer effects, auto-bezier | Excluded from generated files and rejected by the checker. Only vector precomp/shape/null layers and a small explicit shape-operator allowlist are accepted; no external assets. Precomp time remapping is retained for authored source motion (💯) and used to freeze rest poses. These features are checked with all three renderers, rather than flattened or discarded. Explicit spatial tangents are not auto-bezier. |
| Objects inside canvas | Every authored integer frame is rendered on a **768×768 padded canvas at 1:1 resolution**, so pixels outside the original 512 square are detected rather than silently clipped. This proves rendered frame bounds, not continuous subframe mathematical path bounds or invisible construction geometry. |
| Loops | The document's blanket loop guidance is inappropriate for reaction slots: actual iOS `.once` / `.still(.start)` and tweb completion handlers govern playback. The TGS files do not encode a loop switch. |

To repeat the additional renderer checks (only verification needs client trees):

```sh
uv pip install --python .venv/bin/python -r requirements-verify.txt
.venv/bin/python art.py verify-renderer --library /path/to/ios-build/librlottie.so
.venv/bin/python art.py verify-renderer --wasm /path/to/tweb/src/vendor/tlottie/tlottie.wasm
.venv/bin/python art.py preview --library /path/to/ios-build/librlottie.so --output .previews/ios-rlottie
.venv/bin/python art.py preview --wasm /path/to/tweb/src/vendor/tlottie/tlottie.wasm --output .previews/tweb
```

The iOS rlottie build was made **from a copy** in `.cache/ios-rlottie`, with no client edits:

```sh
mkdir -p .cache
cp -a /workspace/Telegram-iOS-36444c32f3/submodules/rlottie/rlottie .cache/ios-rlottie
cmake -S .cache/ios-rlottie -B .cache/ios-build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_C_COMPILER=clang \
  -DLOTTIE_MODULE=ON -DLOTTIE_THREAD=OFF -DLOTTIE_TEST=OFF \
  '-DCMAKE_CXX_FLAGS=-include limits -Wno-error=deprecated-copy-with-user-provided-copy -Wno-error=sign-compare'
cmake --build .cache/ios-build -j 4
```

`-include limits` supplies a missing transitive standard header on Linux; warnings are downgraded for the newer
Clang. No rendering code was patched. MODULE=ON avoids duplicate image-loader symbols; no images are used.

## Preview review

`preview` creates `.previews/<codepoint>-contact-sheet.png`: seven rows (all slots), five labeled samples
including first/middle/last; and `.previews/<codepoint>/<slot>-f<N>.png` at full resolution for those three frames.
Static icons, frozen entrances and resting thumbnails use the marked pose: 😜 shows its wink and tongue,
and 🫪 its distorted face. Moving slots rotate the complete native loop back to that same pose.
`<codepoint>-composites.png` combines five client layouts, six time samples each:

- tweb block: center canvas 40 px, around 80 px, common center; matches a 22 px bubble icon.
- iOS bubble: center 40 pt, around 120 pt, common center; matches a 20 pt logical icon.
- picker: 28 px canvas, 43-frame appear followed by the source-specific select; frames 42/43 show the exact hand-off.
- iOS large outgoing: 120 pt activate, 240 pt effect centered 70 pt left.
- iOS large incoming: same with effect centered 70 pt right and mirrored.

Each composite also has a full **60 fps APNG** (`<codepoint>-bubble-tweb.png`, `-bubble-ios.png`, `-picker.png`,
`-activate-outgoing-ios.png`, `-activate-incoming-ios.png`). APNGs repeat for convenient review; this does **not**
mean the clients loop these slots. The small UI is magnified after composing at actual sizes. These are geometry
reconstructions rendered by the named engines, not screenshots of a running app, nor simulations of the client's
spring/flight transforms. No simulator/account or server integration was used. `.previews/` is gitignored.

`references` also writes `telegram-reference-contact-sheet.png` (all twelve bundled animations, including
the intentionally empty generic template) and `<codepoint>-reference-composites.png`. The latter pairs
Noto/Telegram at each sample time for bubble, picker, large outgoing/incoming, and particles alone.
These comparisons use paid Star's own geometry (22 px tweb icon and centered large iOS effect), alongside
the builtin geometry our files require. This distinction prevents falsely scaling the reference Star to
40 px or giving its centered burst the builtin's ±70 pt offset. The comparison samples include picker
frames 42/43 and burst peak f21. Native rlottie and tweb WASM previews are also in `ios-rlottie/` and `tweb/`.

## Server manifest

`reactions/manifest.json` is `{version: 1, reactions: [...]}`. Each reaction has `reaction`, `title`, and `slots`.
The seven slot keys are exactly the TL field names. Each slot contains:

| Field | Meaning |
|---|---|
| `file` | POSIX path relative to `reactions/`; safe to bundle directly |
| `mime_type` | `image/webp` or `application/x-tgsticker` |
| `size`, `sha256` | Exact file byte count and lowercase SHA-256 hex |
| `image_size` | `{w: 512, h: 512}` for TGS, `{w: 72, h: 72}` for WebP; use in `documentAttributeImageSize` |
| `animated` | False for WebP, true for all TGS, including center |
| `thumb` | TGS slots only: `{file, type: "m", mime_type: "image/webp", size, sha256, image_size: {w: 128, h: 128}}`; path relative to `reactions/`, exact byte count/hash. No thumb on `static_icon`. |

For **each** document, emit `documentAttributeImageSize(w,h)` and
`documentAttributeSticker(flags=0, alt=reaction, stickerset=inputStickerSetEmpty)`.
For every TGS document, also emit `documentAttributeFilename(file_name="AnimatedSticker.tgs")`.
Tweb requires this filename to recognise TGS (`src/lib/appManagers/appDocsManager.ts:271`);
the MIME type and sticker attribute alone are insufficient.
No mask, mask coordinates, sticker-set ID, custom-emoji attribute or video attribute is needed.
`animated` is the media-format indicator; it does not imply looping or require `documentAttributeAnimated`.
These are deliberately chosen minimal attributes accepted by T-sticker:2990–3022, not recovered Telegram
production sticker-set metadata. Omitting the sticker attribute causes TDLib to discard the document.
The server supplies IDs, access hashes, file references and dc_id itself. Set the availableReaction optional
center/around flag together, serve all seven files, and preserve the heart string exactly as recorded.
Advertise each TGS thumbnail in the document's `thumbs` as
`photoSize(type=thumb.type, w=thumb.image_size.w, h=thumb.image_size.h, size=thumb.size)`.
Serve the thumbnail bytes when `inputDocumentFileLocation.thumb_size == thumb.type` (`"m"`);
the empty thumb size still requests the original document. Do not serve the TGS at the thumbnail location.
The server never needs to decompress/parse Lottie.

Thumbnail generation uses the same pinned rlottie/Pillow/libwebp toolchain and lossless settings as static icons.
`check` regenerates all 54 thumbnails byte-for-byte, checks manifest metadata, still WebP format, 128×128
RGBA, transparent margins/empty effects, and compares every RGBA channel against a fresh source-frame
rlottie render with **zero tolerance**. At 40 px, raster resampling versus native vector rendering can have
small antialiasing differences; geometry and pose are preserved. Generate one comparison sheet per reaction
with `.venv/bin/python art.py preview-thumbnails`: `.previews/<codepoint>-thumbnail-comparison.png`
shows each still and fresh resting render at native 128 px and a 40 px canvas. Transparent cells use a checkerboard.

## Libraries evaluated

| Candidate | License | Decision |
|---|---|---|
| [python-lottie 0.7.2](https://pypi.org/project/lottie/) / `tgs_check` | AGPL-3.0-or-later | Useful converter/checker, but not imported, copied or installed. Straightforward JSON transforms and our explicit checker avoid AGPL coupling. |
| [rlottie-python 1.3.8](https://pypi.org/project/rlottie-python/) | LGPL-2.1 (package; native rlottie components have their own notices) | Chosen binary distribution. Our independent tiny ctypes adapter uses the public C ABI and a content-hash cache key. No wrapper implementation is copied. Native renderer remains replaceable/dynamically loaded; server bundles artwork only. |
| iOS vendored rlottie | Its `COPYING` says LGPL-2.1 with FreeType, pixman, stb and RapidJSON notices | Built separately for compatibility proof; not redistributed. Do not assume this older fork has the current upstream MIT license. |
| [Pillow 12.2.0](https://pypi.org/project/Pillow/) / libwebp 1.6.0 | MIT-CMU / BSD-3-Clause | Chosen deterministic lossless WebP and preview composition. |
| [lottie-web](https://github.com/airbnb/lottie-web/blob/master/LICENSE.md) | MIT | Browser dependency unnecessary for this command-line pipeline; would not prove native rlottie compatibility. |
| [dotlottie-web](https://github.com/LottieFiles/dotlottie-web) / ThorVG | MIT | Viable permissive WASM rendering option, but a different rendering engine from the required rlottie proof. Not a runtime dependency. |
| tweb's [tlottie](https://github.com/dkaraush/tlottie) / optional [wasmtime 38.0.0](https://github.com/bytecodealliance/wasmtime-py) | MIT / Apache-2.0 with LLVM exception | Additional verification of the exact shipped tweb binary; no JavaScript or browser installation required. Optional importlib_resources 7.1.0: Apache-2.0. |

The converter remains one Python program; only the renderer/image encoder need third-party code. It contains
no copied Telegram client implementation and does not vendor their binaries. Sources retain their original bytes.

## Output sizes

Exact per-file byte counts and SHA-256 hashes are in `reactions/manifest.json`. All TGS files remain
below 65,536 bytes. Preserving vector source compositions also in frozen slots trades some compressed
size for exact source-frame rendering, including nested time remapping and negative start offsets.
There are 63 artwork documents and 54 thumbnails across nine reactions.
