#!/usr/bin/env python3
"""Offline, deterministic Noto -> Blah reaction artwork. Tool code: MIT."""
from __future__ import annotations

import argparse
import copy
import ctypes as C
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

from PIL import Image, ImageChops, ImageDraw, features

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / 'sources'
OUTPUT = ROOT / 'reactions'
SLOTS = ('static_icon', 'appear_animation', 'select_animation', 'activate_animation',
         'effect_animation', 'around_animation', 'center_icon')
FRAMES = dict(appear_animation=43, effect_animation=90, around_animation=90, center_icon=90)
MOTION_LEAD = 6
SOURCE_COMP = 'blah_source'
THUMB_SIZE = 128  # Compatible document thumbnail canvas; see README evidence.
THUMB_TYPE = 'm'
STATIC_SIZE = 72  # Measured iOS star_up/star_reaction_static_icon.webp.
REST_SPAN = 386   # Measured tweb StarReactionSelect first/last visible width.


def require(test, message):
    if not test:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    """Six decimal places; no NaN, negative zero, or integral floats."""
    if isinstance(value, float):
        require(math.isfinite(value), 'Non-finite number')
        value = round(value, 6)
        return int(value) if value.is_integer() else value
    if isinstance(value, list):
        return [canonical(x) for x in value]
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    return value


def encode(value):
    return json.dumps(canonical(value), ensure_ascii=False, sort_keys=False,
                      separators=(',', ':'), allow_nan=False).encode()


def write_json(path, value):
    path.write_text(json.dumps(canonical(value), ensure_ascii=False, sort_keys=True,
                               indent=2, allow_nan=False) + '\n')


class Renderer:
    """Small independent ctypes adapter to rlottie's public C ABI (no wrapper code)."""
    def __init__(self, data, library=None):
        if library is None:
            package = Path(importlib.util.find_spec('rlottie_python').origin).parent
            library = next((package / n for n in ('librlottie.so', 'librlottie.dylib', 'rlottie.dll')
                            if (package / n).exists()), None)
        require(library is not None, 'Install the pinned rlottie-python binary wheel')
        self.lib = C.CDLL(str(library))
        signatures = {
            'from_data': ([C.c_char_p] * 3, C.c_void_p),
            'destroy': ([C.c_void_p], None),
            'get_totalframe': ([C.c_void_p], C.c_size_t),
            'get_framerate': ([C.c_void_p], C.c_double),
            'render': ([C.c_void_p, C.c_size_t, C.c_void_p] + [C.c_size_t] * 3, None),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.lib, 'lottie_animation_' + name)
            fn.argtypes, fn.restype = args, result
        blob = encode(data)
        self.handle = self.lib.lottie_animation_from_data(blob, sha(blob).encode(), b'')
        require(self.handle, 'rlottie rejected animation')
        self.frames = self.lib.lottie_animation_get_totalframe(self.handle)
        self.fps = self.lib.lottie_animation_get_framerate(self.handle)
        require(self.frames > 0, 'rlottie returned no frames')

    def render(self, frame, size=512):
        buf = C.create_string_buffer(size * size * 4)
        self.lib.lottie_animation_render(self.handle, frame, buf, size, size, size * 4)
        # rlottie uses native-endian premultiplied ARGB; Pillow unpremultiplies it.
        raw = 'BGRa' if sys.byteorder == 'little' else 'aRGB'
        return Image.frombytes('RGBa', (size, size), buf.raw, 'raw', raw).convert('RGBA')

    def close(self):
        if self.handle:
            self.lib.lottie_animation_destroy(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class WasmRenderer:
    """Optional actual tweb tlottie binary, via its exported web ABI."""
    def __init__(self, data, library):
        import wasmtime
        self.store = wasmtime.Store()
        module = wasmtime.Module.from_file(self.store.engine, str(library))
        self.api = wasmtime.Instance(self.store, module, []).exports(self.store)
        blob = encode(data)
        pointer = self.call('alloc', len(blob))
        self.api['memory'].write(self.store, blob, pointer)
        self.handle = self.call('new_with_options', pointer, len(blob), 0, 0, 0)
        self.call('free', pointer, len(blob))
        require(self.handle, 'tlottie rejected animation')
        self.frames = self.call('frame_count', self.handle)
        self.fps = self.call('frame_rate', self.handle)

    def call(self, name, *args):
        return self.api['tlottie_' + name](self.store, *args)

    def render(self, frame, size=512):
        pointer = self.call('render', self.handle, float(frame), size, size, 1)
        require(pointer, 'tlottie render failed')
        data = bytes(self.api['memory'].read(self.store, pointer, pointer + size * size * 4))
        return Image.frombytes('RGBA', (size, size), data)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.call('drop', self.handle)


def prop(value):
    return {'a': 0, 'k': value}


def tween(points):
    """Explicit linear segments; authored overshoot is in the values."""
    keys = []
    for t, value in points:
        value = value if isinstance(value, list) else [value]
        keys.append({'t': t, 's': value, 'i': {'x': [1], 'y': [1]},
                     'o': {'x': [0], 'y': [0]}})
    keys[-1] = {'t': keys[-1]['t'], 's': keys[-1]['s']}
    return {'a': 1, 'k': keys}


def transform(position=(0, 0), anchor=(0, 0), scale=100):
    return {'o': prop(100), 'r': prop(0), 'p': prop(list(position)),
            'a': prop(list(anchor)), 's': prop([scale, scale, 100])}


def document(layers, frames):
    return {'v': '5.8.1', 'tgs': 1, 'fr': 60, 'ip': 0, 'op': frames,
            'w': 512, 'h': 512, 'ddd': 0, 'assets': [], 'layers': layers}


def clean(node):
    """Strip exporter metadata only; preserve every source timeline verbatim."""
    if isinstance(node, list):
        return [clean(x) for x in node]
    if not isinstance(node, dict):
        return node
    return {k: clean(v) for k, v in node.items()
            if k not in {'nm', 'mn', 'ix', 'ln', 'cl', 'markers'}}


def source_composition(source, frames, motion=False):
    """Keep nested composition clocks, visibility, parenting and mattes intact.

    The motion layer's start time is the ONLY change to source playback time.
    Rest layers hold source frame zero, including negative-start precompositions.
    Two equal animated tm keys are intentional: rlottie ignores static tm.
    """
    assets = clean(source.get('assets', []))
    require(all(a['id'] != SOURCE_COMP for a in assets), 'Reserved composition ID')
    assets.append({'id': SOURCE_COMP, 'layers': clean(source['layers'])})

    def layer(index, start, end, moving=False):
        result = {'ty': 0, 'ind': index, 'refId': SOURCE_COMP,
                  'w': source['w'], 'h': source['h'], 'ip': start, 'op': end,
                  'st': start if moving else 0, 'ks': transform()}
        if end < frames:
            # Packaged rlottie includes a layer's op; iOS/tlottie exclude it.
            # Explicit held opacity makes hand-offs exclusive in all three.
            result['ks']['o'] = {'a': 1, 'k': [
                {'t': 0, 's': [100], 'h': 1}, {'t': end, 's': [0]}]}
        if not moving:
            result['tm'] = tween([(0, 0), (frames, 0)])
        return result

    if motion:
        end = MOTION_LEAD + source['op']
        # Noto animations are loops. Close exactly as the source player does:
        # after op-1 show frame zero, with no added easing or stretched motion.
        layers = [layer(1, MOTION_LEAD, end, True), layer(2, 0, MOTION_LEAD),
                  layer(3, end, frames)]
    else:
        layers = [layer(1, 0, frames)]
    return layers, assets


def wrap(layers, frames, anchor, scale, position=(256, 256)):
    layers = copy.deepcopy(layers)
    index = max((x['ind'] for x in layers), default=0) + 1
    for layer in layers:
        if 'parent' not in layer:
            layer['parent'] = index
    parent = {'ty': 3, 'ind': index, 'ip': 0, 'op': frames, 'st': 0,
              'ks': transform(position, anchor, scale)}
    return document(layers + [parent], frames)


def normalized(source):
    require(source['w'] == source['h'] and source['ip'] == 0 and source['fr'] == 60,
            'Source profile requires a square canvas, ip=0 and 60 fps')
    require(source['op'] > 0 and int(source['op']) == source['op'], 'Expected integral source duration')
    validate_compositions(source)
    # Measure the whole motion, including matte results, with the pinned renderer.
    # Use source resolution, not a thumbnail, for stable pixel bounds.
    boxes = []
    with Renderer(source) as renderer:
        rest = renderer.render(0, source['w']).getbbox()
        for frame in range(int(source['op'])):
            box = renderer.render(frame, source['w']).getbbox()
            if box:
                boxes.append(box)
    require(rest and boxes, 'Empty source artwork')
    anchor = [(rest[0] + rest[2]) / 2, (rest[1] + rest[3]) / 2]
    radius = max(max(abs(b[i] - anchor[i % 2]) for i in range(4)) for b in boxes)
    # Match the reference's resting span, while reserving room for motion.
    scale = min(REST_SPAN / max(rest[2] - rest[0], rest[3] - rest[1]),
                244 / radius) * 100
    return anchor, scale


def palette(source):
    # Choose visible colors: source shapes may include colored construction
    # geometry that is hidden by a matte. Never use that as particle paint.
    from collections import Counter
    with Renderer(source) as renderer:
        counts = Counter(pixel[:3] for pixel in renderer.render(0, 128).get_flattened_data()
                         if pixel[3] >= 250)
    # Near-white eye/teeth paint disappears on light chat backgrounds. Prefer
    # the source's contrasting paints when available, without emoji branches.
    contrasting = {rgb: count for rgb, count in counts.items() if min(rgb) < 200}
    colors = []
    for rgb, count in sorted((contrasting or counts).items(), key=lambda pair: (-pair[1], pair[0])):
        if all(sum((a - b) ** 2 for a, b in zip(rgb, c)) > 1600 for c in colors):
            colors.append(rgb)
        if len(colors) == 3:
            break
    require(colors, 'Source has no opaque visible palette')
    return [[channel / 255 for channel in color] for color in colors]


def particles(source, large):
    count, frames = (18, FRAMES['effect_animation']) if large else (14, FRAMES['around_animation'])
    colors = palette(source)
    layers = []
    for i in range(count):
        # The large effect is offset -70 pt on a 240 pt canvas in iOS.
        # Its right-side origin maps exactly onto the 120 pt activation center.
        if large:
            origin = [512 * 190 / 240, 256]
            angle = math.radians(105 + i * 150 / (count - 1))
            radius = 155 + (i % 3) * 27
            end = [origin[0] + math.cos(angle) * radius * 1.5,
                   origin[1] + math.sin(angle) * radius]
            start = [origin[0] + math.cos(angle) * 70,
                     origin[1] + math.sin(angle) * 70]
        else:
            angle = i * math.tau / count - math.pi / 2
            radius = 224 + i % 3 * 10
            start = [256 + math.cos(angle) * 72, 256 + math.sin(angle) * 72]
            end = [256 + math.cos(angle) * radius, 256 + math.sin(angle) * radius]
        delay, finish = 3 + i % 3 * 2, 78 + i % 3 * 3
        ks = transform()
        # The reference burst peaks at f21: expand quickly, then drift/fade.
        spread = [a + (b - a) * .8 for a, b in zip(start, end)]
        ks['p'] = tween([(0, start), (delay, start), (21, spread), (finish, end)])
        ks['o'] = tween([(0, 0), (delay, 0), (delay + 5, 90), (finish - 15, 70), (finish, 0)])
        ks['s'] = tween([(0, [25, 25, 100]), (21, [100, 100, 100]),
                         (finish, [30, 30, 100])])
        diameter = 26 + i % 3 * 6
        if i % 2:
            # A four-vertex diamond path, not a forbidden polystar operator.
            half = diameter / 2
            shape = {'ty': 'sh', 'ks': prop({'c': True,
                     'v': [[0, -half], [half, 0], [0, half], [-half, 0]],
                     'i': [[0, 0]] * 4, 'o': [[0, 0]] * 4})}
            ks['r'] = tween([(0, 0), (finish, 90)])
        else:
            shape = {'ty': 'el', 'p': prop([0, 0]), 's': prop([diameter, diameter])}
        layers.append({'ty': 4, 'ind': i + 1, 'ip': 0, 'op': frames, 'st': 0,
                       'ks': ks, 'shapes': [shape, {'ty': 'fl', 'c': prop(colors[i % len(colors)]),
                                                   'o': prop(100), 'r': 1}]})
    return document(layers, frames)


def convert(source):
    anchor, scale = normalized(source)
    result = {}
    for slot in ('appear_animation', 'select_animation', 'activate_animation', 'center_icon'):
        moving = slot in ('select_animation', 'activate_animation')
        frames = MOTION_LEAD + int(source['op']) + 1 if moving else FRAMES[slot]
        if slot == 'activate_animation':
            frames = max(frames, 61)  # Authored tilt must also finish at rest.
        layers, assets = source_composition(source, frames, moving)
        size = scale * (0.55 if slot == 'center_icon' else 1)
        data = wrap(layers, frames, anchor, size)
        data['assets'] = assets
        root = data['layers'][-1]['ks']
        if slot == 'appear_animation':
            root['s'] = tween([(0, [size * .15] * 2 + [100]),
                               (12, [size * 1.06] * 2 + [100]),
                               (24, [size] * 2 + [100])])
            # Parenting inherits geometry, not opacity. Fade each painted layer.
            for layer in data['layers'][:-1]:
                if not layer.get('td'):
                    layer['ks']['o'] = tween([(0, 0), (6, 100)])
        if slot == 'center_icon':
            root['s'] = tween([(0, [size] * 2 + [100]),
                               (12, [size * 1.08] * 2 + [100]),
                               (30, [size] * 2 + [100])])
        if slot == 'activate_animation':
            root['r'] = tween([(0, 0), (18, -5), (36, 4), (60, 0)])
        result[slot] = canonical(data)
    result['around_animation'] = particles(source, False)
    result['effect_animation'] = particles(source, True)
    still, assets = source_composition(source, 1)
    static = wrap(still, 1, anchor, scale)
    static['assets'] = assets
    with Renderer(static) as renderer:
        result['static_icon'] = renderer.render(0, STATIC_SIZE)
    return result


def source_entries():
    return json.loads((SOURCES / 'manifest.json').read_text())['sources']


def resting_frame(slot, data):
    return data['op'] - 1 if slot == 'appear_animation' else 0


def thumbnail(data, slot):
    # Render the entire canvas, without cropping or changing the authored padding.
    with Renderer(data) as renderer:
        return renderer.render(resting_frame(slot, data), THUMB_SIZE)


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {'version': 1, 'reactions': []}
    for entry in source_entries():
        blob = (SOURCES / entry['file']).read_bytes()
        require(sha(blob) == entry['sha256'], f"Source hash mismatch: {entry['file']}")
        assets = convert(json.loads(blob))
        folder = destination / entry['codepoint']
        folder.mkdir(exist_ok=True)
        reaction = {k: entry[k] for k in ('reaction', 'title')}
        reaction['slots'] = {}
        for slot in SLOTS:
            animated = slot != 'static_icon'
            filename = slot + ('.tgs' if animated else '.webp')
            if animated:
                stream = io.BytesIO()
                with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0, compresslevel=9) as f:
                    f.write(encode(assets[slot]))
                blob = stream.getvalue()
            else:
                stream = io.BytesIO()
                assets[slot].save(stream, 'WEBP', lossless=True, quality=100, method=6, exact=True)
                blob = stream.getvalue()
            (folder / filename).write_bytes(blob)
            reaction['slots'][slot] = {
                'file': f"{entry['codepoint']}/{filename}",
                'mime_type': 'application/x-tgsticker' if animated else 'image/webp',
                'size': len(blob), 'sha256': sha(blob), 'animated': animated,
                'image_size': {'w': 512 if animated else STATIC_SIZE,
                               'h': 512 if animated else STATIC_SIZE},
            }
            if animated:
                thumb_name = slot + '.thumb.webp'
                stream = io.BytesIO()
                thumbnail(assets[slot], slot).save(stream, 'WEBP', lossless=True,
                                                 quality=100, method=6, exact=True)
                thumb_blob = stream.getvalue()
                (folder / thumb_name).write_bytes(thumb_blob)
                reaction['slots'][slot]['thumb'] = {
                    'file': f"{entry['codepoint']}/{thumb_name}", 'type': THUMB_TYPE,
                    'mime_type': 'image/webp', 'size': len(thumb_blob),
                    'sha256': sha(thumb_blob), 'image_size': {'w': THUMB_SIZE, 'h': THUMB_SIZE},
                }
        manifest['reactions'].append(reaction)
    write_json(destination / 'manifest.json', manifest)


def validate(data, compressed_size):
    require(data['w'] == data['h'] == 512, 'Canvas must be 512 x 512')
    require(data['fr'] == 60 and data['ip'] == 0, 'Expected 60 fps, ip=0')
    require(1 <= data['op'] <= 180 and int(data['op']) == data['op'], 'Duration outside 1..180 frames')
    require(compressed_size <= 65536, 'TGS exceeds 64 KiB')
    validate_compositions(data)
    def visit(node, path='root'):
        if isinstance(node, list):
            for i, v in enumerate(node):
                visit(v, f'{path}[{i}]')
        elif isinstance(node, dict):
            require(not node.get('ddd') and not node.get('ao'), f'3D/auto-orient: {path}')
            require('x' not in node or not isinstance(node['x'], str), f'Expression: {path}')
            require(not node.get('ef') and not node.get('hasMask') and not node.get('masksProperties'), f'Effects/masks: {path}')
            require(node.get('bm', 0) == 0, f'Blend mode: {path}')
            ty = node.get('ty')
            if isinstance(ty, int):
                require(ty in (0, 3, 4), f'Forbidden layer type: {path}')
                require(('tm' not in node or ty == 0) and node.get('sr', 1) == 1, f'Time remap/stretch: {path}')
                require(node.get('tt', 0) in (0, 1, 2), f'Only alpha/inverted alpha mattes permitted: {path}')
            elif isinstance(ty, str):
                require(ty in {'gr', 'sh', 'fl', 'st', 'tr', 'el', 'rc', 'gf', 'tm'},
                        f'Unverified shape feature {ty}: {path}')
            require(not node.get('ab'), f'Auto-bezier: {path}')
            for k, v in node.items():
                visit(v, path + '.' + k)
    visit(data)


def validate_compositions(data):
    """Only embedded vector compositions; reject dangling/cyclic references."""
    assets = data.get('assets', [])
    require(all('layers' in a and not any(k in a for k in ('p', 'u', 'e')) for a in assets),
            'Only embedded vector composition assets are allowed')
    by_id = {a['id']: a for a in assets}
    require(len(by_id) == len(assets), 'Duplicate asset ID')
    for comp in [data] + assets:
        require(comp.get('fr', 60) == 60, 'Composition must use 60 fps')
        layers = comp['layers']
        ids = {l['ind'] for l in layers}
        require(len(ids) == len(layers), 'Duplicate layer index')
        for i, layer in enumerate(layers):
            require(layer['ty'] in (0, 3, 4), 'Expected vector precomp/null/shape layer')
            require('parent' not in layer or layer['parent'] in ids, 'Missing parent')
            require(layer.get('sr', 1) == 1, 'Unsupported layer stretch')
            if layer['ty'] == 0:
                require(layer.get('refId') in by_id, 'Missing precomposition')
            if layer.get('tt'):
                require(i > 0 and layers[i - 1].get('td') == 1, 'Broken matte adjacency')
    def visit(comp, ancestors):
        for layer in comp['layers']:
            if layer['ty'] == 0:
                ref = layer['refId']
                require(ref not in ancestors, 'Cyclic precomposition')
                visit(by_id[ref], ancestors | {ref})
    for comp in [data] + assets:
        visit(comp, set())


def padded(data):
    """Render outside the nominal canvas to detect escaped artwork, not just clipping."""
    result = wrap(data['layers'], data['op'], (0, 0), 100, (128, 128))
    result['assets'] = copy.deepcopy(data.get('assets', []))
    result['w'] = result['h'] = 768
    return result


def validate_rendering(data, renderer_type=Renderer, library=None, visible=False):
    with renderer_type(data, library) as renderer:
        require(renderer.fps == 60, 'Renderer reports wrong fps')
        # Some renderers optimize entirely static files to a single frame.
        require(renderer.frames in (1, data['op'], data['op'] + 1), 'Renderer frame count mismatch')
        samples = [renderer.render(f, 128) for f in (0, data['op'] // 2, data['op'] - 1)]
        require(any(im.getbbox() for im in samples), 'Animation rendered entirely blank')
    with renderer_type(padded(data), library) as renderer:
        for frame in range(data['op']):
            box = renderer.render(frame, 768).getbbox()  # 1 output pixel / Lottie unit
            require(not visible or box, f'Unexpected blank icon frame {frame}')
            require(not box or (box[0] >= 128 and box[1] >= 128 and box[2] <= 640 and box[3] <= 640),
                    f'Artwork escapes canvas at frame {frame}: {box}')


def validate_tree(destination, renderer_type=Renderer, library=None):
    for path in sorted(destination.glob('*/*.tgs')):
        blob = path.read_bytes()
        data = json.loads(gzip.decompress(blob))
        validate(data, len(blob))
        validate_rendering(data, renderer_type, library, path.stem in
                           ('select_animation', 'activate_animation', 'center_icon'))
        print(f'OK {path.parent.name}/{path.name}: {len(blob):5d} bytes, {data["op"]}/60 s', flush=True)
    for path in destination.glob('*/static_icon.webp'):
        with Image.open(path) as im:
            require(path.stat().st_size <= 524288, 'WebP exceeds TDLib sticker upload limit')
            require(im.format == 'WEBP' and im.size == (STATIC_SIZE, STATIC_SIZE) and not getattr(im, 'is_animated', False), 'Bad static icon')
    validate_thumbnails(destination)
    validate_source_motion(destination, renderer_type, library)
    # Exact same rendered pose at the picker boundary, and at both ends of center.
    for folder in sorted(p for p in destination.iterdir() if p.is_dir()):
        images = {}
        for slot in ('appear_animation', 'select_animation', 'center_icon', 'activate_animation'):
            data = json.loads(gzip.decompress((folder / (slot + '.tgs')).read_bytes()))
            with renderer_type(data, library) as renderer:
                images[slot] = [renderer.render(0), renderer.render(data['op'] - 1)]
        require(images['appear_animation'][0].getbbox() is None, 'Appear must start transparent')
        for slot in ('around_animation', 'effect_animation'):
            data = json.loads(gzip.decompress((folder / (slot + '.tgs')).read_bytes()))
            with renderer_type(data, library) as renderer:
                require(renderer.render(0).getbbox() is None and
                        renderer.render(data['op'] - 1).getbbox() is None,
                        'Effects must start/end transparent')
        rest = images['select_animation'][0].tobytes()
        require(images['appear_animation'][1].tobytes() == rest, 'Appear/select jump')
        require(images['select_animation'][1].tobytes() == rest, 'Select rest/loop jump')
        require(images['activate_animation'][0].tobytes() == rest == images['activate_animation'][1].tobytes(), 'Activate endpoint jump')
        require(images['center_icon'][0].tobytes() == images['center_icon'][1].tobytes(), 'Center endpoint jump')


def validate_source_motion(destination, renderer_type=Renderer, library=None):
    """Guard the clock AND rendered source poses, independently of conversion."""
    def key_times(node, path=()):
        if isinstance(node, list):
            for i, value in enumerate(node):
                yield from key_times(value, path + (i,))
        elif isinstance(node, dict):
            if node.get('a') == 1 and isinstance(node.get('k'), list):
                yield path, [key['t'] for key in node['k']]
            for key, value in node.items():
                yield from key_times(value, path + (key,))

    for entry in source_entries():
        source = json.loads((SOURCES / entry['file']).read_bytes())
        # Compare at source canvas geometry, independently of normalization and
        # its renderer-specific matte rasterization/rounding.
        with renderer_type(source, library) as original:
            poses = [original.render(f, 128).tobytes() for f in range(int(source['op']))]
        for slot in ('select_animation', 'activate_animation'):
            data = json.loads(gzip.decompress((destination / entry['codepoint'] / (slot + '.tgs')).read_bytes()))
            motion = data['layers'][0]
            require(motion['refId'] == SOURCE_COMP and motion['ip'] == motion['st'] == MOTION_LEAD
                    and motion['op'] == MOTION_LEAD + source['op']
                    and motion.get('sr', 1) == 1 and 'tm' not in motion,
                    f'{entry["codepoint"]}/{slot}: source clock must have slope 1, offset {MOTION_LEAD}')
            expected = source.get('assets', []) + [{'id': SOURCE_COMP, 'layers': source['layers']}]
            require(list(key_times(expected)) == list(key_times(data['assets'])),
                    f'{entry["codepoint"]}/{slot}: source keyframe times changed')
            require(canonical(clean(expected)) == data['assets'], 'Source composition changed')
            require(data['op'] >= MOTION_LEAD + source['op'] + 1, 'Source motion truncated')
            # Remove ONLY the outer geometric transform (including authored tilt).
            data['layers'][-1]['ks'] = transform()
            data['w'], data['h'] = source['w'], source['h']
            with renderer_type(data, library) as converted:
                for f, pose in enumerate(poses):
                    require(converted.render(f + MOTION_LEAD, 128).tobytes() == pose,
                            f'{entry["codepoint"]}/{slot}: source pose/timing differs at frame {f}')
        print(f'OK {entry["codepoint"]}: source keyframe clock slope 1; '
              f'all {source["op"]} source poses exact in select/activate', flush=True)


def validate_thumbnails(destination):
    manifest = json.loads((destination / 'manifest.json').read_text())
    require(manifest['version'] == 1, 'Manifest version changed')
    for reaction in manifest['reactions']:
        for slot, record in reaction['slots'].items():
            if slot == 'static_icon':
                require('thumb' not in record, 'Static icon must not have a thumb')
                continue
            thumb = record['thumb']
            source = destination / record['file']
            path = source.with_suffix('.thumb.webp')
            blob = path.read_bytes()
            require(thumb == {'file': path.relative_to(destination).as_posix(),
                             'type': THUMB_TYPE, 'mime_type': 'image/webp',
                             'size': len(blob), 'sha256': sha(blob),
                             'image_size': {'w': THUMB_SIZE, 'h': THUMB_SIZE}},
                    f'Bad thumbnail metadata: {path}')
            with Image.open(path) as im:
                require(im.format == 'WEBP' and im.size == (THUMB_SIZE, THUMB_SIZE)
                        and not getattr(im, 'is_animated', False) and im.mode == 'RGBA',
                        f'Bad thumbnail format/dimensions/alpha: {path}')
                actual = im.copy()
            data = json.loads(gzip.decompress(source.read_bytes()))
            fresh = thumbnail(data, slot)
            # Lossless encoding permits zero tolerance in all RGBA channels.
            delta = ImageChops.difference(actual, fresh)
            require(all(hi == 0 for lo, hi in delta.getextrema()),
                    f'Thumbnail differs from fresh resting render: {path}')
            alpha = actual.getchannel('A')
            if slot in ('effect_animation', 'around_animation'):
                require(alpha.getbbox() is None, f'Effect thumb must be empty: {path}')
            else:
                require(alpha.getextrema()[0] == 0 and alpha.getextrema()[1] > 0, f'Missing visible pose/transparency: {path}')
            print(f'OK {path.parent.name}/{path.name}: {len(blob):5d} bytes, '
                  f'{THUMB_SIZE}x{THUMB_SIZE} RGBA, rest f{resting_frame(slot, data)}, exact', flush=True)


def preview_thumbnails(destination):
    destination.mkdir(parents=True, exist_ok=True)
    for entry in source_entries():
        code = entry['codepoint']
        sheet = Image.new('RGB', (560, 6 * 165 + 35), '#eef1f6')
        draw = ImageDraw.Draw(sheet)
        draw.text((8, 8), '128px: thumb / fresh render       40px: thumb / fresh render', fill='black')
        for row, slot in enumerate(SLOTS[1:]):
            y = 35 + row * 165
            data = json.loads(gzip.decompress((OUTPUT / code / (slot + '.tgs')).read_bytes()))
            with Image.open(OUTPUT / code / (slot + '.thumb.webp')) as im:
                still = im.convert('RGBA')
            with Renderer(data) as renderer:
                images = [still, renderer.render(resting_frame(slot, data), THUMB_SIZE),
                          still.resize((40, 40), Image.Resampling.LANCZOS),
                          renderer.render(resting_frame(slot, data), 40)]
            draw.text((8, y), f'{slot}  f{resting_frame(slot, data)}', fill='black')
            for x, im in zip((8, 152, 320, 400), images):
                for cy in range(0, im.height, 8):
                    for cx in range(0, im.width, 8):
                        draw.rectangle((x+cx, y+22+cy, x+min(cx+7, im.width-1),
                                        y+22+min(cy+7, im.height-1)),
                                       fill='#ffffff' if (cx//8+cy//8)%2 else '#d9dee7')
                sheet.paste(im, (x, y+22), im)
        path = destination / f'{code}-thumbnail-comparison.png'
        sheet.save(path)
        print(f'Thumbnail preview: {path}', flush=True)


def check():
    with tempfile.TemporaryDirectory(prefix='blah-reactions-') as tmp:
        dest = Path(tmp)
        generate(dest)
        expected = {p.relative_to(dest): p.read_bytes() for p in dest.rglob('*') if p.is_file()}
        actual = {p.relative_to(OUTPUT): p.read_bytes() for p in OUTPUT.rglob('*') if p.is_file()}
        differences = [str(p) for p in expected.keys() | actual.keys() if expected.get(p) != actual.get(p)]
        require(not differences, 'Regeneration differs: ' + ', '.join(sorted(differences)))
    validate_tree(OUTPUT)
    print(f'PASS: offline regeneration is byte-identical; source-speed motion, all formats, bounds, '
          f'hand-offs and {len(source_entries()) * 6} exact RGBA thumbnails validated.')


def preview(destination, renderer_type=Renderer, library=None):
    destination.mkdir(parents=True, exist_ok=True)
    for entry in source_entries():
        code = entry['codepoint']
        renderers, data = {}, {}
        for slot in SLOTS[1:]:
            data[slot] = json.loads(gzip.decompress((OUTPUT / code / (slot + '.tgs')).read_bytes()))
            renderers[slot] = renderer_type(data[slot], library)
        def frame(slot, number, size):
            return renderers[slot].render(min(number, data[slot]['op'] - 1), size)
        sheet = Image.new('RGB', (1000, 7 * 180), '#eef1f6')
        draw = ImageDraw.Draw(sheet)
        frame_dir = destination / code
        frame_dir.mkdir(exist_ok=True)
        for row, slot in enumerate(SLOTS):
            draw.text((8, row * 180 + 6), slot, fill='#1b2535')
            count = data[slot]['op'] if slot != 'static_icon' else 1
            for col, f in enumerate([0, count // 4, count // 2, count * 3 // 4, count - 1]):
                im = (frame(slot, f, 144) if slot != 'static_icon' else
                      Image.open(OUTPUT / code / 'static_icon.webp').convert('RGBA').resize((144, 144)))
                if slot != 'static_icon' and col in (0, 2, 4):
                    frame(slot, f, 512).save(frame_dir / f'{slot}-f{f}.png')
                sheet.paste(im, (col * 200 + 28, row * 180 + 23), im)
                draw.text((col * 200 + 8, row * 180 + 164), f'f{f} / {f / 60:.3f}s', fill='#364152')
        sheet.save(destination / f'{code}-contact-sheet.png')
        # Composites use actual client point/pixel geometry, then magnify only
        # the small UI for inspection. Large activation uses native point scale.
        clips = {'bubble-tweb': [], 'bubble-ios': [], 'picker': [],
                 'activate-outgoing-ios': [], 'activate-incoming-ios': []}
        appear_frames = data['appear_animation']['op']
        picker_frames = appear_frames + data['select_animation']['op']
        for f in range(max(picker_frames, data['activate_animation']['op'], data['around_animation']['op'])):
            if f < FRAMES['around_animation']:
                for client, around_size in [('tweb', 80), ('ios', 120)]:
                    im = Image.new('RGBA', (160, 160), '#eef1f6')
                    if client == 'ios':
                        im.alpha_composite(frame('center_icon', f, 40), (60, 60))
                    im.alpha_composite(frame('around_animation', f, around_size),
                                       ((160 - around_size) // 2,) * 2)
                    if client == 'tweb':
                        im.alpha_composite(frame('center_icon', f, 40), (60, 60))
                    clips['bubble-' + client].append(im.convert('RGB').resize((480, 480), Image.Resampling.NEAREST))
            im = Image.new('RGBA', (100, 72), '#eef1f6')
            slot, t = ('appear_animation', f) if f < appear_frames else ('select_animation', f - appear_frames)
            im.alpha_composite(frame(slot, t, 28), (36, 22))
            if f < picker_frames:
                clips['picker'].append(im.convert('RGB').resize((500, 360), Image.Resampling.NEAREST))
            if f < max(data['activate_animation']['op'], data['effect_animation']['op']):
                for incoming in (False, True):
                    im = Image.new('RGBA', (400, 280), '#eef1f6')
                    # iOS inserts effect AFTER the icon, so it is above it.
                    im.alpha_composite(frame('activate_animation', f, 120), (140, 80))
                    effect = frame('effect_animation', f, 240)
                    if incoming:
                        effect = effect.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                    im.alpha_composite(effect, (150 if incoming else 10, 20))
                    clips['activate-' + ('incoming' if incoming else 'outgoing') + '-ios'].append(im.convert('RGB'))
        for name, frames in clips.items():
            # APNG, exact 60 Hz rational frame delay; first frame is animation.
            frames[0].save(destination / f'{code}-{name}.png', save_all=True, append_images=frames[1:],
                           duration=1000 / 60, loop=0, optimize=False)
        composite = Image.new('RGB', (1200, len(clips) * 220), '#eef1f6')
        draw = ImageDraw.Draw(composite)
        for row, (name, frames) in enumerate(clips.items()):
            indices = [0, 12, 24, appear_frames - 1, appear_frames, len(frames) - 1] if name == 'picker' else [0, 10, 20, 35, 50, len(frames) - 1]
            for col, f in enumerate(indices):
                im = frames[f].copy()
                im.thumbnail((196, 180))
                composite.paste(im, (col * 200, row * 220 + 24))
                draw.text((col * 200 + 3, row * 220 + 6), f'{name} f{f}', fill='#1b2535')
        composite.save(destination / f'{code}-composites.png')
        for renderer in renderers.values():
            renderer.__exit__()
        print(f'Previews: {code} -> {destination}', flush=True)


def fetch(codepoint=None, title=None):
    entries = source_entries()
    require(bool(codepoint) == bool(title), 'Adding a source requires both --codepoint and --title')
    if codepoint:
        require(re.fullmatch(r'[0-9a-f]{4,6}(?:_[0-9a-f]{4,6})*', codepoint),
                'Use lowercase hex codepoints separated by underscores')
        require(all(int(c, 16) <= 0x10ffff and not 0xd800 <= int(c, 16) <= 0xdfff
                    for c in codepoint.split('_')), 'Invalid Unicode scalar')
        require(not any(e['codepoint'] == codepoint for e in entries), 'Source already exists; use fetch to refresh')
        entries.append({'codepoint': codepoint, 'title': title, 'file': codepoint + '.json',
                        'reaction': ''.join(chr(int(c, 16)) for c in codepoint.split('_') if c != 'fe0f'),
                        'url': f'https://fonts.gstatic.com/s/e/notoemoji/latest/{codepoint}/lottie.json'})
    downloaded = []
    for entry in entries:
        with urllib.request.urlopen(entry['url'], timeout=60) as response:
            blob = response.read()
        json.loads(blob)
        downloaded.append(blob)
        entry.update(sha256=sha(blob), retrieved_at=datetime.now(timezone.utc).date().isoformat())
    for entry, blob in zip(entries, downloaded):
        (SOURCES / entry['file']).write_bytes(blob)
    write_json(SOURCES / 'manifest.json', {'version': 1, 'sources': entries})


def measure(data, renderer_type=Renderer, library=None):
    """Visible alpha > 0 bounds at every integer frame, exclusive right/bottom."""
    count = int(data['op'] - data['ip'])
    boxes, areas = [], []
    with renderer_type(data, library) as renderer:
        for f in range(count):
            alpha = renderer.render(f).getchannel('A')
            boxes.append(alpha.getbbox())
            areas.append(sum(alpha.histogram()[1:]))
    visible = [i for i, box in enumerate(boxes) if box]
    union = [min(b[i] for b in boxes if b) if i < 2 else max(b[i] for b in boxes if b)
             for i in range(4)] if visible else None
    return {'canvas': [data['w'], data['h']], 'fr': data['fr'], 'ip': data['ip'],
            'op': data['op'], 'duration': count / data['fr'], 'union': union,
            'first': boxes[0], 'middle': boxes[count // 2], 'last': boxes[-1],
            'visible_frames': [visible[0], visible[-1]] if visible else None,
            'peak_area_frame': areas.index(max(areas)), 'peak_area_pixels': max(areas),
            'frames': [{'bbox': b, 'area': a} for b, a in zip(boxes, areas)]}


def references(tweb, ios, destination, renderer_type=Renderer, library=None):
    """Read-only reference audit; no reference artwork is vendored or built into outputs."""
    destination.mkdir(parents=True, exist_ok=True)
    documents, records = {}, {}
    for path in sorted(tweb.glob('*Reaction*.json')):
        documents['tweb/' + path.stem] = (path, json.loads(path.read_bytes()))
    if ios:
        for path in sorted(ios.glob('star_reaction_*.tgs')):
            documents['ios/' + path.stem] = (path, json.loads(gzip.decompress(path.read_bytes())))
    require('tweb/StarReactionAppear' in documents, 'Pass the tweb public/assets/tgs directory')
    for name, (path, data) in documents.items():
        records[name] = {'file': path.name, 'sha256': sha(path.read_bytes()),
                         **measure(data, renderer_type, library)}
        print(f'Measured {name}: {records[name]["union"]}', flush=True)
    if ios:
        path = ios / 'star_reaction_static_icon.webp'
        with Image.open(path) as im:
            records['ios/static_icon'] = {'file': path.name, 'sha256': sha(path.read_bytes()),
                                          'canvas': list(im.size), 'bbox': im.getbbox(),
                                          'size': path.stat().st_size, 'format': im.format}
    for entry in source_entries():
        for slot in SLOTS[1:]:
            path = OUTPUT / entry['codepoint'] / (slot + '.tgs')
            records[entry['codepoint'] + '/' + slot] = {
                'sha256': sha(path.read_bytes()),
                **measure(json.loads(gzip.decompress(path.read_bytes())), renderer_type, library)}
    with renderer_type(documents['tweb/StarReactionAppear'][1], library) as a, \
            renderer_type(documents['tweb/StarReactionSelect'][1], library) as s:
        handoff = a.render(42).tobytes() == s.render(0).tobytes()
    measurements = {'renderer': renderer_type.__name__,
                    'library_sha256': sha(library.read_bytes()) if library else None,
                    'frame_index': 'relative to ip; alpha > 0; bbox right/bottom exclusive; rendered at 512',
                    'star_appear_select_exact_handoff': handoff, 'artwork': records}
    write_json(destination / 'reference-measurements-all-frames.json', measurements)
    summary = copy.deepcopy(measurements)
    for record in summary['artwork'].values():
        record.pop('frames', None)
    write_json(destination / 'reference-measurements.json', summary)

    renderers = {name: renderer_type(data, library) for name, (_, data) in documents.items()}
    def ref(name, f, size):
        d = documents[name][1]
        return renderers[name].render(min(f, int(d['op'] - d['ip']) - 1), size)
    sheet = Image.new('RGB', (1200, len(documents) * 180), '#eef1f6')
    draw = ImageDraw.Draw(sheet)
    for row, name in enumerate(documents):
        m = records[name]
        count = int(m['op'] - m['ip'])
        for col, f in enumerate([0, count // 4, count // 2, count * 3 // 4, count - 1]):
            im = ref(name, f, 144)
            sheet.paste(im, (col * 240 + 45, row * 180 + 22), im)
            draw.text((col * 240 + 4, row * 180 + 5), name, fill='#1b2535')
            draw.text((col * 240 + 4, row * 180 + 163), f'f{f} (absolute {f + m["ip"]})', fill='#364152')
    sheet.save(destination / 'telegram-reference-contact-sheet.png')

    for entry in source_entries():
        code = entry['codepoint']
        own_data = {slot: json.loads(gzip.decompress(
            (OUTPUT / code / (slot + '.tgs')).read_bytes())) for slot in SLOTS[1:]}
        own = {slot: renderer_type(data, library) for slot, data in own_data.items()}
        def frame(slot, f, size):
            return own[slot].render(min(f, own_data[slot]['op'] - 1), size)
        comparisons = Image.new('RGB', (2400, 5 * 230), '#eef1f6')
        draw = ImageDraw.Draw(comparisons)
        names = ['bubble tweb: Noto / paid Star', 'picker: Noto / Star',
                 'large outgoing iOS: Noto / Star', 'large incoming iOS: Noto / Star',
                 'around only: Noto / StarEffect1']
        times = [0, 12, 21, 42, 43, 89]
        for row, label in enumerate(names):
            draw.text((5, row * 230 + 4), label, fill='#1b2535')
            for col, f in enumerate(times):
                pair = []
                for telegram in (False, True):
                    if row == 0:
                        im = Image.new('RGBA', (100, 100), '#eef1f6')
                        burst = ref('tweb/StarReactionEffect1', f, 80) if telegram else frame('around_animation', f, 80)
                        icon = ref('tweb/StarReaction', f, 22) if telegram else frame('center_icon', f, 40)
                        im.alpha_composite(burst, (10, 10))
                        im.alpha_composite(icon, ((100 - icon.width) // 2,) * 2)
                    elif row == 1:
                        im = Image.new('RGBA', (60, 70), '#eef1f6')
                        if telegram:
                            icon = ref('tweb/StarReactionAppear' if f < 43 else 'tweb/StarReactionSelect', f if f < 43 else f - 43, 28)
                        else:
                            icon = frame('appear_animation' if f < 43 else 'select_animation', f if f < 43 else f - 43, 28)
                        im.alpha_composite(icon, (16, 21))
                    elif row in (2, 3):
                        im = Image.new('RGBA', (400, 280), '#eef1f6')
                        if telegram and 'ios/star_reaction_activate' not in documents:
                            ImageDraw.Draw(im).text((20, 120), 'Pass --ios-references for large reference', fill='black')
                        else:
                            icon = ref('ios/star_reaction_activate', f, 120) if telegram else frame('activate_animation', f, 120)
                            effect = ref('ios/star_reaction_effect', f, 240) if telegram else frame('effect_animation', f, 240)
                            im.alpha_composite(icon, (140, 80))
                            # Paid Star is a special centered effect; builtin emoji use +/-70.
                            if row == 3 and not telegram:
                                effect = effect.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                            im.alpha_composite(effect, (80 if telegram else (150 if row == 3 else 10), 20))
                    else:
                        im = Image.new('RGBA', (100, 100), '#eef1f6')
                        effect = ref('tweb/StarReactionEffect1', f, 80) if telegram else frame('around_animation', f, 80)
                        im.alpha_composite(effect, (10, 10))
                    im = im.convert('RGB')
                    im.thumbnail((198, 175))
                    if row < 2:
                        factor = min(198 / im.width, 175 / im.height)
                        im = im.resize((round(im.width * factor), round(im.height * factor)), Image.Resampling.NEAREST)
                    pair.append(im)
                for side, im in enumerate(pair):
                    comparisons.paste(im, (col * 400 + side * 200, row * 230 + 40))
                draw.text((col * 400 + 3, row * 230 + 22), f'f{f}, Noto | Telegram', fill='#364152')
        comparisons.save(destination / f'{code}-reference-composites.png')
        for renderer in own.values():
            renderer.__exit__()
    for renderer in renderers.values():
        renderer.__exit__()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'check', 'fetch', 'preview', 'verify-renderer', 'references', 'preview-thumbnails'])
    parser.add_argument('--library', type=Path, help='Additional rlottie shared library to verify/preview')
    parser.add_argument('--wasm', type=Path, help='Actual tweb tlottie WASM to verify/preview')
    parser.add_argument('--output', type=Path, help='Preview directory (default .previews)')
    parser.add_argument('--references', type=Path, help='Read-only tweb public/assets/tgs directory')
    parser.add_argument('--ios-references', type=Path, help='Read-only iOS Animations/star_up directory')
    parser.add_argument('--codepoint', help='fetch: add a Noto source by lowercase hexadecimal ID')
    parser.add_argument('--title', help='fetch: title for the new reaction')
    args = parser.parse_args()
    require(not (args.library and args.wasm), 'Choose --library OR --wasm')
    require(args.command == 'fetch' or not (args.codepoint or args.title),
            '--codepoint/--title are only for fetch')
    renderer_type = WasmRenderer if args.wasm else Renderer
    library = args.wasm or args.library
    if args.command == 'fetch':
        fetch(args.codepoint, args.title)
    elif args.command == 'build':
        generate(OUTPUT)
        validate_tree(OUTPUT)
    elif args.command == 'check':
        check()
    elif args.command == 'verify-renderer':
        require(library, 'Pass --library or --wasm')
        validate_tree(OUTPUT, renderer_type, library)
    elif args.command == 'preview-thumbnails':
        preview_thumbnails(args.output or ROOT / '.previews')
    elif args.command == 'preview':
        preview(args.output or ROOT / '.previews', renderer_type, library)
    elif args.command == 'references':
        require(args.references, 'Pass --references')
        references(args.references, args.ios_references, args.output or ROOT / '.previews', renderer_type, library)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        sys.exit(str(error))
